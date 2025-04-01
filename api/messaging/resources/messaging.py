from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any

import stripe
from flask import jsonify, make_response, request
from flask.typing import ResponseReturnValue
from flask_babel import gettext
from flask_restful import abort
from marshmallow.exceptions import ValidationError
from marshmallow_v1 import UnmarshallingError
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import joinedload, load_only
from stripe.error import StripeError

from appointments.models.payments import Credit
from authn.models.user import User
from common import stats
from common.services import ratelimiting
from common.services.api import AuthenticatedResource, HasUserResource
from common.services.stripe import StripeCustomerClient
from common.services.stripe_constants import PAYMENTS_STRIPE_API_KEY
from l10n.db_strings.translate import TranslateDBFields  # noqa
from messaging.logic.message_credit import (
    MessageCreditException,
    allocate_message_credits,
    pay_with_credits,
)
from messaging.models.messaging import (
    Channel,
    Message,
    MessageBilling,
    MessageCredit,
    MessageProduct,
)
from messaging.repository.message import (
    get_sms_messaging_notifications_enabled,
    set_sms_messaging_notifications_enabled,
)
from messaging.schemas.messaging import (
    ChannelMessagesSchema,
    ChannelParticipantsSchema,
    ChannelSchema,
    MessageBillingGETSchema,
    MessageBillingSchema,
    MessagePOSTArgs,
    MessageProductsSchema,
    MessageSchema,
)
from messaging.schemas.messaging_v3 import (
    ChannelMessagesSchemaV3,
    ChannelParticipantsSchemaV3,
    ChannelSchemaV3,
    ChannelsGETArgsV3,
    ChannelsSchemaV3,
    ChannelsUnreadMessagesResourceV3,
    MessageBillingGETSchemaV3,
    MessageBillingSchemaV3,
    MessagePOSTArgsV3,
    MessageSchemaV3,
)
from messaging.services.messaging import (
    filter_channels,
    get_channel_ids_for_user,
    get_channels_by_id,
)
from messaging.utils.common import get_wallet_by_channel_id
from models.enterprise import UserAsset, UserAssetState
from models.tracks import MemberTrack
from providers.service.provider import ProviderService
from storage.connection import db
from tasks.messaging import send_to_zendesk
from tasks.notifications import notify_new_message
from tasks.queues import schedule_fn
from tracks.utils.common import get_active_member_track_modifiers
from utils.constants import (
    MESSAGE_CREATION_ERROR_COUNT_METRICS,
    MESSAGE_CREATION_SUCCESS_COUNT_METRICS,
    MessageCreationFailureReason,
)
from utils.flag_groups import (
    BILLING_GET_MARSHMALLOW_V3_MIGRATION,
    BILLING_POST_MARSHMALLOW_V3_MIGRATION,
    MESSAGES_GET_MARSHMALLOW_V3_MIGRATION,
)
from utils.log import LogLevel, generate_user_trace_log, logger
from utils.marshmallow_experiment import marshmallow_experiment_enabled
from utils.service_owner_mapper import service_ns_team_mapper
from views.schemas.common import PaginableArgsSchema
from views.schemas.common_v3 import PaginableArgsSchemaV3

log = logger(__name__)


class ChannelsResource(AuthenticatedResource):
    @db.from_app_replica
    def get(self) -> ResponseReturnValue:
        try:
            schema_in = ChannelsGETArgsV3()
            args: dict[str, Any] = schema_in.load(request.args)
        except (UnmarshallingError, ValidationError) as e:
            log.warn(
                "Validation error during parsing of ChannelsResource args",
                exception=str(e),
            )
            return {"message": gettext("input_error_getting_channels")}, 400

        include_empty = args.get("empty", True)
        offset = args.get("offset", 0)
        limit = args.get("limit", 10)
        order_direction = args.get("order_direction", "desc")

        # include empty channels (no messages)
        min_message_count = 0
        if self.user.is_care_coordinator:
            min_message_count = 2

        sorted_channel_ids = get_channel_ids_for_user(
            user=self.user,
            min_count_of_messages_in_channel=min_message_count,
            sort_descending=(order_direction == "desc"),
        )

        total_channels = len(sorted_channel_ids)
        channels_to_return = get_channels_by_id(
            channel_ids=sorted_channel_ids,
            limit=limit,
            offset=offset,
        )
        # filter out channels with no messages
        channels_to_return = filter_channels(
            channels_to_return,
            # always include wallet channels
            include_wallet=True,
            # include empty channels if requested
            include_no_messages=include_empty,
        )

        pagination = {
            "limit": limit,
            "offset": offset,
            "total": total_channels,
            "order_direction": order_direction,
        }
        message_notifications_consent = get_sms_messaging_notifications_enabled(
            user_id=self.user.id
        )
        results = {
            "data": channels_to_return,
            "pagination": pagination,
            "message_notifications_consent": message_notifications_consent,
        }
        try:
            schema_out = ChannelsSchemaV3()
            schema_out.context["include_profile"] = True
            schema_out.context["user"] = self.user
            schema_out.context["headers"] = request.headers
            response: ResponseReturnValue = schema_out.dump(results)
        except (UnmarshallingError, ValidationError) as e:
            log.warn(
                "Validation error during serialization of ChannelsResource response",
                exception=str(e),
            )
            return {"message": gettext("serializing_error_getting_channels")}, 400

        return response

    def post_request(self, request: dict) -> dict:
        # We need `item or 0` since some clients send `null`, which MarshmallowV1
        # interprets as 0.
        if "user_ids" in request:
            return {"user_ids": [int(item or 0) for item in request["user_ids"]]}
        return {}

    @ratelimiting.ratelimited(attempts=60, cooldown=60)
    def post(self) -> ResponseReturnValue:
        """
        Create/Open a channel. If all participants have already created a channel
        before, this will return the previous channel. Otherwise it will create.
        """
        args = self.post_request(request.json if request.is_json else None)
        user_ids: list[int] = args.get("user_ids") or []
        if not user_ids:
            abort(400, message=gettext("cant_open_a_channel_with_only_yourself"))
        if self.user.id in user_ids:
            abort(400, message=gettext("you_are_already_included_in_the_channel"))
        if len(user_ids) > 1:
            abort(400, message=gettext("we_dont_support_multi_party_messaging"))

        users = db.session.query(User).filter(User.id.in_(user_ids)).all()
        if len(user_ids) != len(users):
            abort(400, message=gettext("one_or_more_users_not_found"))

        if (self.user.is_practitioner and not users[0].is_member) or (
            self.user.is_member and not users[0].is_practitioner
        ):
            abort(
                400,
                message=gettext(
                    "channel_can_only_be_opened_between_a_member_and_a_practitioner"
                ),
            )

        channel = Channel.get_or_create_channel(self.user, users)
        db.session.commit()
        schema_out = ChannelSchema()
        schema_out.context["include_profile"] = True
        schema_out.context["user"] = self.user
        data = schema_out.dump(channel).data
        data["new_messages"] = len(channel.new_message_ids(self.user.id))
        return data, 201


class GetChannelMixin(HasUserResource):
    def _get_channel(self, channel_id: int) -> Channel:
        channel = Channel.query.get_or_404(channel_id)
        if self.user not in [p.user for p in channel.participants]:
            log.error(
                "Channel not found for channel id",
                channel_id=channel_id,
                user_id=self.user.id,
            )
            abort(404, message="Channel not found")
        return channel


class ChannelStatusResource(AuthenticatedResource, GetChannelMixin):
    def get(self, channel_id: int) -> ResponseReturnValue:
        # launch darkly flag
        experiment_enabled = marshmallow_experiment_enabled(
            "experiment-marshmallow-channel-status-resource",
            self.user.esp_id if self.user else None,
            self.user.email if self.user else None,
            default=False,
        )
        channel = self._get_channel(channel_id)

        schema = ChannelSchemaV3() if experiment_enabled else ChannelSchema()
        schema.context["include_profile"] = True  # type: ignore[attr-defined]
        schema.context["user"] = self.user  # type: ignore[attr-defined]
        data = schema.dump(channel) if experiment_enabled else schema.dump(channel).data  # type: ignore[attr-defined]

        return data


class ChannelParticipantsResource(AuthenticatedResource, GetChannelMixin):
    def get(self, channel_id: int) -> ResponseReturnValue:
        # launch darkly flag
        experiment_enabled = marshmallow_experiment_enabled(
            "experiment-marshmallow-channel-participants-resource",
            self.user.esp_id if self.user else None,
            self.user.email if self.user else None,
            default=False,
        )
        channel = self._get_channel(channel_id)
        schema = (
            ChannelParticipantsSchemaV3()
            if experiment_enabled
            else ChannelParticipantsSchema()
        )
        schema.context["include_profile"] = True  # type: ignore[attr-defined]
        schema.context["user"] = self.user  # type: ignore[attr-defined]
        return (
            schema.dump({"data": channel.participants})  # type: ignore[attr-defined]
            if experiment_enabled
            else schema.dump({"data": channel.participants}).data  # type: ignore[attr-defined]
        )


class ChannelMessagesResource(AuthenticatedResource, GetChannelMixin):
    def get(self, channel_id: int) -> ResponseReturnValue:
        """
        Gets messages associated with a channel.
        """
        experiment_enabled = marshmallow_experiment_enabled(
            str(MESSAGES_GET_MARSHMALLOW_V3_MIGRATION),
            self.user.esp_id if self.user else None,
            self.user.email if self.user else None,
            default=False,
        )
        user_id = self.user.id
        channel: Channel = self._get_channel(channel_id)
        if experiment_enabled:
            schema_in = PaginableArgsSchemaV3()
            args = schema_in.load(request.args)  # type: ignore[no-redef]
        else:
            schema_in = PaginableArgsSchema()
            args = schema_in.load(request.args).data  # type: ignore[no-redef]

        offset = args.get("offset", 0)
        limit = args.get("limit", 10)
        order_direction = args.get("order_direction", "desc")

        messages_query = db.session.query(Message).filter(
            Message.channel_id == channel.id,
            Message.status == True,
        )
        total: int = messages_query.count()

        if "desc" == order_direction:
            messages_query = messages_query.order_by(Message.id.desc())
        else:
            messages_query = messages_query.order_by(Message.id)
        messages: list[Message] = messages_query.offset(offset).limit(limit).all()

        contains_null_author = False
        # set the read bit
        for m in messages:
            if m.user_id == 0 or m.user is None:
                contains_null_author = True

            m.mark_as_read_by(user_id)
            # need to explicitly commit as mark_as_read_by() doesn't
            try:
                db.session.commit()
            except IntegrityError:
                db.session.rollback()

        if contains_null_author:
            stats.increment(
                metric_name="api.resources.messaging.get_channel_messages.null_author",
                pod_name=stats.PodNames.TEST_POD,
            )

        pagination = {
            "limit": limit,
            "offset": offset,
            "total": total,
            "order_direction": order_direction,
        }
        results = {"data": messages, "pagination": pagination}
        if experiment_enabled:
            schema = ChannelMessagesSchemaV3()
            schema.context["include_profile"] = True
            schema.context["user"] = self.user
            return schema.dump(results)
        else:
            schema = ChannelMessagesSchema()
            schema.context["include_profile"] = True
            schema.context["user"] = self.user
            return schema.dump(results).data

    @staticmethod
    def _increment_message_creation_count_metric(
        is_internal_channel: bool,
        is_wallet_channel: bool,
        pod_name: stats.PodNames = stats.PodNames.VIRTUAL_CARE,
        failure_reason: MessageCreationFailureReason = MessageCreationFailureReason.NONE,
    ) -> None:
        stats.increment(
            metric_name=(
                MESSAGE_CREATION_SUCCESS_COUNT_METRICS
                if failure_reason == MessageCreationFailureReason.NONE
                else MESSAGE_CREATION_ERROR_COUNT_METRICS
            ),
            pod_name=pod_name,
            tags=[
                f"is_internal_channel:{is_internal_channel}",
                f"is_wallet_channel:{is_wallet_channel}",
                f"failure_reason:{failure_reason.name}",
            ],
        )
        return None

    def post(self, channel_id: int) -> ResponseReturnValue:
        """
        Posts a message into the channel.
        """
        # launch darkly flag
        experiment_enabled = marshmallow_experiment_enabled(
            "experiment-marshmallow-channel-messages-resource",
            self.user.esp_id if self.user else None,
            self.user.email if self.user else None,
            default=False,
        )
        channel: Channel = Channel.query.get_or_404(channel_id)
        is_internal: bool = channel.internal
        is_wallet_channel: bool = channel.is_wallet
        wallet = get_wallet_by_channel_id(channel.id)

        if not channel.participants or (
            len(channel.participants) == 1 and wallet is None
        ):

            generate_user_trace_log(
                log,
                LogLevel.ERROR,
                self.user.id,
                "Unable to post message in channel: no participants found",
                channel_id=channel_id,
            )

            self._increment_message_creation_count_metric(
                is_internal,
                is_wallet_channel,
                failure_reason=MessageCreationFailureReason.NO_PARTICIPANT_FOUND,
            )
            user_message = gettext(
                "unable_to_post_message_in_channel_no_participants_found"
            )
            user_message = user_message.format(channel_id=channel_id)

            abort(400, message=user_message)
        if self.user not in [p.user for p in channel.participants]:
            generate_user_trace_log(
                log,
                LogLevel.ERROR,
                self.user.id,
                "Unable to post message in channel: user is not a participant",
                channel_id=channel_id,
            )

            self._increment_message_creation_count_metric(
                is_internal,
                is_wallet_channel,
                failure_reason=MessageCreationFailureReason.USER_NOT_A_PARTICIPANT,
            )

            user_message = gettext(
                "unable_to_post_message_in_channel_user_is_not_a_participant"
            )
            user_message = user_message.format(channel_id=channel_id)

            abort(403, message=user_message)

        provider_profile: User | None = None
        for p in channel.participants:
            u = p.user
            if not u.is_practitioner:
                continue
            provider_profile = u.practitioner_profile
            if (
                not u.practitioner_profile.active
                or not u.practitioner_profile.messaging_enabled
            ):
                # failure_reason will be overriden but just to be explicit we will define it first
                failure_reason = MessageCreationFailureReason.NONE
                if not u.practitioner_profile.messaging_enabled:
                    failure_reason = (
                        MessageCreationFailureReason.PRACTITIONER_HAS_MESSAGING_DISABLED
                    )
                if not u.practitioner_profile.active:
                    failure_reason = MessageCreationFailureReason.INACTIVE_PRACTITIONER

                generate_user_trace_log(
                    log,
                    LogLevel.ERROR,
                    self.user.id,
                    "Unable to post message in channel, inactive or messaging disabled practitioner",
                    user_not_messaging_enabled=u.id,
                    channel_id=channel_id,
                    failure_reason=str(failure_reason.name),
                )

                self._increment_message_creation_count_metric(
                    is_internal,
                    is_wallet_channel,
                    failure_reason=failure_reason,
                )

                user_message = gettext(
                    "unable_to_post_message_in_channel_inactive_or_messaging_disabled_practitioner"
                )
                user_message = user_message.format(channel_id=channel_id)

                abort(400, message=user_message)

        # don't post message if member is doula_only and provider doesn't support doula_only
        active_member_tracks = (
            db.session.query(MemberTrack)
            .filter(
                MemberTrack.active,
                MemberTrack.user_id == self.user.id,
            )
            .all()
        )
        client_track_ids = [track.client_track_id for track in active_member_tracks]
        member_track_modifiers = get_active_member_track_modifiers(active_member_tracks)
        if provider_profile and not ProviderService.provider_can_member_interact(
            provider=provider_profile,
            modifiers=member_track_modifiers,
            client_track_ids=client_track_ids,
        ):
            generate_user_trace_log(
                log,
                LogLevel.ERROR,
                self.user.id,
                "Unable to post message in channel, member cannot interact with this provider",
                channel_id=channel_id,
                provider_id=provider_profile.user_id if provider_profile else None,
                provider_verticals=(
                    str(provider_profile.verticals) if provider_profile else None
                ),
            )
            self._increment_message_creation_count_metric(
                is_internal,
                is_wallet_channel,
                failure_reason=MessageCreationFailureReason.MEMBER_CANNOT_MESSAGE_PRACTITIONER,
            )
            user_message = gettext(
                "unable_to_post_message_in_channel_member_cannot_message_practitioner"
            )
            abort(400, message=user_message)

        # Temporary fix -- see https://mavenclinic.atlassian.net/browse/DISCO-3071
        request_json = request.json if request.is_json else None
        if (
            request_json
            and "source" in request_json
            and request_json["source"] == "Promote Messaging"
        ):
            request_json["source"] = "promote_messaging"

        schema_in = MessagePOSTArgsV3() if experiment_enabled else MessagePOSTArgs()
        args = (
            schema_in.load(request_json)  # type: ignore[attr-defined]
            if experiment_enabled
            else schema_in.load(request_json).data  # type: ignore[attr-defined]
        )

        if len(args.get("body", "")) > Message.MAX_CHARS and self.user.is_member:
            generate_user_trace_log(
                log,
                LogLevel.ERROR,
                self.user.id,
                "Message is too long",
                channel_id=channel_id,
            )

            self._increment_message_creation_count_metric(
                is_internal,
                is_wallet_channel,
                failure_reason=MessageCreationFailureReason.MESSAGE_TOO_LONG,
            )
            user_message = gettext("message_is_too_long")
            user_message = user_message.format(max_n_chars=Message.MAX_CHARS)

            abort(400, message=user_message)

        attachments = []
        for asset_id in args.get("attachments", []):
            asset = (
                UserAsset.query.options(
                    load_only("user_id", "state", "content_type"),
                    joinedload("_message"),
                )
                .filter_by(id=int(asset_id))
                .one_or_none()
            )
            if asset is None:
                generate_user_trace_log(
                    log,
                    LogLevel.ERROR,
                    self.user.id,
                    "Could not find asset matching requested identifier",
                    channel_id=channel_id,
                    asset_id=asset_id,
                )

                self._increment_message_creation_count_metric(
                    is_internal,
                    is_wallet_channel,
                    failure_reason=MessageCreationFailureReason.NO_ASSET_MATCHED,
                )

                user_message = gettext(
                    "could_not_find_asset_matching_requested_identifier"
                )
                user_message = user_message.format(asset_id=asset_id)

                abort(404, message=user_message)
            if not (asset.user_id == self.user.id):
                generate_user_trace_log(
                    log,
                    LogLevel.ERROR,
                    self.user.id,
                    "Cannot attach asset belonging to another user",
                    channel_id=channel_id,
                    asset_id=asset_id,
                )

                self._increment_message_creation_count_metric(
                    is_internal,
                    is_wallet_channel,
                    failure_reason=MessageCreationFailureReason.ASSET_BELONGING_TO_ANOTHER_USER,
                )
                user_message = gettext("cannot_attach_asset_belonging_to_another_user")
                abort(403, message=user_message)
            if asset.state != UserAssetState.COMPLETE:

                generate_user_trace_log(
                    log,
                    LogLevel.ERROR,
                    self.user.id,
                    "Cannot attach asset to message, asset state is not COMPLETE",
                    channel_id=channel_id,
                    asset_id=asset_id,
                )

                self._increment_message_creation_count_metric(
                    is_internal,
                    is_wallet_channel,
                    failure_reason=MessageCreationFailureReason.ASSET_NOT_COMPLETE,
                )

                user_message = gettext(
                    "cannot_attach_asset_to_message_asset_state_is_not_complete"
                )

                abort(409, message=user_message)
            if asset.message is not None:

                generate_user_trace_log(
                    log,
                    LogLevel.ERROR,
                    self.user.id,
                    "Cannot attach asset to multiple messages at once",
                    channel_id=channel_id,
                    asset_id=asset_id,
                )

                self._increment_message_creation_count_metric(
                    is_internal,
                    is_wallet_channel,
                    failure_reason=MessageCreationFailureReason.ATTACH_ASSET_TO_MULTIPLE_MESSAGES,
                )
                user_message = gettext(
                    "cannot_attach_asset_to_multiple_messages_at_once"
                )

                abort(409, message=user_message)
            if not asset.content_type.startswith(("image/", "application/pdf")):

                generate_user_trace_log(
                    log,
                    LogLevel.ERROR,
                    self.user.id,
                    "Only image and PDF file types are supported.",
                    channel_id=channel_id,
                    asset_id=asset_id,
                    content_type=asset.content_type,
                )

                self._increment_message_creation_count_metric(
                    is_internal,
                    is_wallet_channel,
                    failure_reason=MessageCreationFailureReason.NON_IMAGE_ASSET,
                )
                user_message = gettext("only_image_and_pdf_file_types_are_supported")

                abort(409, message=user_message)
            attachments.append(asset)

        new_message: Message = Message(
            user_id=self.user.id,
            channel_id=channel.id,
            body=args.get("body"),
            attachments=attachments,
            source=args.get("source"),
        )

        db.session.add(new_message)

        try:
            allocate_message_credits(channel, new_message, self.user)
        except MessageCreditException as e:
            if e.user_is_enterprise:
                user_message = gettext(
                    "exception_allocating_message_credits_enterprise_user"
                )
                failure_reason = (
                    MessageCreationFailureReason.MESSAGE_CREDITS_ALLOCATION_EXCEPTION_ENTERPRISE
                )
                log_level = LogLevel.ERROR
            else:
                user_message = gettext(
                    "exception_allocating_message_credits_marketplace_user"
                )
                failure_reason = (
                    MessageCreationFailureReason.MESSAGE_CREDITS_ALLOCATION_EXCEPTION
                )
                log_level = LogLevel.INFO
            generate_user_trace_log(
                log,
                log_level,
                self.user.id,
                "Message credit exception allocating message credits",
                channel_id=channel_id,
                message_id=new_message.id,
                user_is_enterprise=e.user_is_enterprise,
            )
            self._increment_message_creation_count_metric(
                is_internal,
                is_wallet_channel,
                failure_reason=failure_reason,
            )
            return abort(400, message=user_message)
        except Exception as e:
            generate_user_trace_log(
                log,
                LogLevel.ERROR,
                self.user.id,
                "Exception allocating message credits",
                channel_id=channel_id,
                exception_type=e.__class__.__name__,
                exception_message=str(e),
            )

            self._increment_message_creation_count_metric(
                is_internal,
                is_wallet_channel,
                failure_reason=MessageCreationFailureReason.GENERAL_ALLOCATION_EXCEPTION,
            )
            user_message = gettext("general_exception_allocating_message_credits")
            return abort(400, message=user_message)

        db.session.commit()
        generate_user_trace_log(
            log,
            LogLevel.INFO,
            self.user.id,
            "Successfully create a message",
            channel_id=channel_id,
            message_id=new_message.id,
            has_attachements=len(attachments) > 0,
        )

        self._increment_message_creation_count_metric(
            is_internal,
            is_wallet_channel,
            failure_reason=MessageCreationFailureReason.NONE,
        )

        if wallet:
            wallet.create_sources_from_message(new_message)

        service_ns_tag = "messaging_system"
        team_ns_tag = service_ns_team_mapper.get(service_ns_tag)
        if channel.internal:
            schedule_fn(
                send_to_zendesk,
                new_message.id,
                user_id=self.user.id,
                service_ns=service_ns_tag,
                team_ns=team_ns_tag,
                caller=self.__class__.__name__,
            )

        # notify other participants
        others = [p.user for p in channel.participants if p.user != self.user]
        for each_user in others:
            schedule_fn(
                notify_new_message,
                each_user.id,
                new_message.id,
                service_ns=service_ns_tag,
                team_ns=team_ns_tag,
                caller=self.__class__.__name__,
            )

        schema_out = MessageSchemaV3() if experiment_enabled else MessageSchema()
        if experiment_enabled:
            return schema_out.dump(new_message), 201  # type: ignore[attr-defined]
        else:
            return schema_out.dump(new_message).data, 201  # type: ignore[attr-defined]


class ChannelsUnreadMessagesResource(AuthenticatedResource):
    @db.from_app_replica
    def get(self) -> ResponseReturnValue:

        user_id = self.user.id

        try:
            schema = ChannelsUnreadMessagesResourceV3()
            log.info(
                "Getting count of channels with unread messages for user",
                user_id=user_id,
            )

            total_unread_channel_count = Channel.count_unread_channels_for_user(
                user_id=user_id
            )

            response = schema.dump({"count": total_unread_channel_count})
        except Exception as e:
            log.warn(
                "Exception raised when attempting to return the count of unread channel messages for user",
                exception=str(e),
                user_id=user_id,
            )
            return abort(
                400, message="Could not return count of unread channel messages"
            )

        return response


class MessageAcknowledgementResource(AuthenticatedResource):
    def post(self, message_id: int) -> ResponseReturnValue:
        """
        Acknowledge a message.
        """
        message = Message.query.get_or_404(message_id)

        if message.user_id == self.user.id:
            abort(403, message="You cannot acknowledge your own message.")

        if self.user.is_practitioner:
            abort(403, message="Only member can acknowledge.")

        if message.is_acknowledged_by(self.user.id):
            abort(409, message="Already acknowledged")

        message.mark_as_acknowledged_by(self.user.id)
        db.session.commit()
        return "", 204


class MessageResource(AuthenticatedResource):
    def get(self, message_id: int) -> ResponseReturnValue:
        message = Message.query.get_or_404(message_id)
        if self.user not in [p.user for p in message.channel.participants]:
            abort(404, message="Message not found")

        message.mark_as_read_by(self.user.id)
        # need to commit session as mark_as_read_by() doesn't
        db.session.commit()

        schema = MessageSchema()
        return schema.dump(message).data

    @ratelimiting.ratelimited(attempts=60, cooldown=60)
    def put(self, message_id: int) -> ResponseReturnValue:
        message = Message.query.get_or_404(message_id)
        if self.user.id != message.user_id:
            abort(
                403,
                message="You can't edit this message because you are not the author.",
            )
        if any(p["is_read"] for p in message.meta if p["user_id"] != self.user.id):
            abort(409, message="You can't edit this message because it has been read.")
        schema_in = MessagePOSTArgs(only=["body"])
        args = schema_in.load(request.json if request.is_json else None).data
        body = args.get("body")
        if not body:
            abort(400, message="Message content can't be empty.")

        message.body = body
        db.session.add(message)
        db.session.commit()

        schema_out = MessageSchema()
        return schema_out.dump(message).data


class MessageBillingResource(AuthenticatedResource):
    @classmethod
    def _pay_with_card(cls, user: User, amount: int) -> stripe.Charge:
        try:
            stripe_client = StripeCustomerClient(PAYMENTS_STRIPE_API_KEY)
            cards = stripe_client.list_cards(user=user)
            if not cards:
                abort(400, message=gettext("no_card_on_file_error"))
            charge = stripe_client.create_charge(
                amount, user=user, capture=True, stripe_card_id=cards[0].id
            )
            if not charge:
                abort(400, message=gettext("cannot_charge_customer_error"))
        except StripeError as e:
            message = gettext("cannot_charge_customer_stripe_error")
            log.error(
                message,
                user_id=user.id,
                error=str(e),
            )
            abort(400, message=message)

        return charge

    def get(self) -> ResponseReturnValue:
        """
        Retrieves the number of available message credits.
        """
        # launch darkly flag
        experiment_enabled = marshmallow_experiment_enabled(
            str(BILLING_GET_MARSHMALLOW_V3_MIGRATION),
            self.user.esp_id if self.user else None,
            self.user.email if self.user else None,
            default=False,
        )
        try:
            msg_credits = (
                db.session.query(MessageCredit)
                .filter(
                    MessageCredit.user_id == self.user.id,
                    MessageCredit.message_id.is_(None),
                )
                .count()
            )
            if experiment_enabled:
                schema = MessageBillingGETSchemaV3()
                resp = schema.dump(
                    {
                        "available_messages": msg_credits,
                        "modified_at": datetime.utcnow(),
                    }
                )
            else:
                schema = MessageBillingGETSchema()
                resp = schema.dump(
                    {
                        "available_messages": msg_credits,
                        "modified_at": datetime.utcnow(),
                    }
                ).data
        except Exception as err:
            message = gettext("available_credits_error")
            log.exception(
                str(message), exception=err.__class__.__name__, message=str(err)
            )
            abort(400, message=message)
        return resp

    def post(self) -> ResponseReturnValue:
        """
        Record the messaging product purchase.
        This is the API endpoint gets called *AFTER* add/charge a card on Stripe has happened.
        All of which are already existing.
        """
        experiment_enabled = marshmallow_experiment_enabled(
            str(BILLING_POST_MARSHMALLOW_V3_MIGRATION),
            self.user.esp_id if self.user else None,
            self.user.email if self.user else None,
            default=False,
        )
        args = get_post_request(request.json if request.is_json else None)

        product_id = args.get("product_id")
        product = MessageProduct.query.get_or_404(product_id)
        available_credits = Credit.available_for_user(self.user).all()

        balance, used_credits = pay_with_credits(product.price, available_credits)
        maven_credit_used = product.price - balance
        purchase_info = {
            "maven_credit_used": str(maven_credit_used),
            "quantity": product.number_of_messages,
            "price": str(product.price),
        }
        stripe_charge_id = None
        if balance > 0:
            charge = self._pay_with_card(self.user, balance)
            stripe_charge_id = charge.id
            stripe_info = {
                "stripe_charge_id": stripe_charge_id,
                "stripe_customer_id": charge.customer,
                "stripe_card_id": charge.source.id,
                "stripe_charge_amount": str(Decimal(charge.amount) / 100),
                "card_last4": charge.source.last4,
                "card_brand": charge.source.brand,
                "charged_at": datetime.fromtimestamp(charge.created).isoformat(),
            }
            purchase_info.update(stripe_info)

        purchase = MessageBilling.create(
            user_id=self.user.id,
            message_product_id=product.id,
            stripe_id=stripe_charge_id,
            json=purchase_info,
        )
        MessageCredit.create(
            count=product.number_of_messages,
            user_id=self.user.id,
            message_billing_id=purchase.id,
        )
        db.session.commit()

        # Record message billing in used credits
        log.debug(f"used_credits {used_credits}")
        for credit in used_credits:
            credit.message_billing_id = purchase.id
        db.session.add_all(used_credits)
        db.session.commit()

        output = {
            "available_messages": sum(
                1 for c in purchase.user.message_credits if c.message_id is None
            )
        }
        output.update(**purchase.json)
        if experiment_enabled:
            schema_out = MessageBillingSchemaV3()
            return schema_out.dump(output), 201
        else:
            schema_out = MessageBillingSchema()
            return schema_out.dump(output).data, 201


def get_post_request(request_json: dict) -> dict:
    if not request_json or "product_id" not in request_json:
        return {}
    return {"product_id": int(request_json["product_id"] or 0)}


class MessageProductsResource(AuthenticatedResource):
    def get(self) -> ResponseReturnValue:
        products = (
            db.session.query(MessageProduct)
            .filter(MessageProduct.is_active.is_(True))
            .all()
        )
        schema = MessageProductsSchema()
        return schema.dump({"data": products}).data


class MessageNotificationsConsentResource(AuthenticatedResource):
    def post(self) -> ResponseReturnValue:
        user_id = self.user.id
        log.info("setting sms consent as true", user_id=user_id)
        # Try to find an existing user by user_id
        set_sms_messaging_notifications_enabled(user_id=user_id)

        return {}, 200

    def get(self) -> ResponseReturnValue:
        user_id = self.user.id
        consent_enabled = get_sms_messaging_notifications_enabled(user_id=user_id)

        return make_response(
            jsonify({"message_notifications_consent": consent_enabled}), 200
        )
