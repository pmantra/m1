from __future__ import annotations

from typing import Any, Dict, List, Tuple, Type, overload

from flask import request
from flask_babel import lazy_gettext
from marshmallow_v1 import fields, validate

from authn.models.user import User
from common.constants import current_web_origin
from l10n.db_strings.schema import TranslatedPractitionerProfileSchemaV1
from messaging.models.messaging import Channel, Message, MessageSourceEnum
from models.profiles import MemberProfile, PractitionerProfile
from models.verticals_and_specialties import CX_VERTICAL_NAME
from phone_support.service.phone_support import get_inbound_phone_number
from utils.log import logger
from views.schemas.common import (
    HasContextProtocol,
    MavenDateTime,
    MavenSchema,
    MemberProfileSchema,
    PaginableOutputSchema,
    PractitionerProfileSchema,
    UserProfilesSchema,
    UserSchema,
)
from views.schemas.common import (
    _other_user_field_exclusions as practitioner_profile_other_user_field_exclusions,
)
from wallet.utils.common import get_wallet_id_by_channel_id, is_attached_to_wallet

log = logger(__name__)

MESSAGE_REPLY_SLA_USER_MESSAGE_CA_DEFAULT = lazy_gettext(
    "message_reply_sla_user_message_ca_default"
)
MESSAGE_REPLY_SLA_USER_MESSAGE_PROVIDER_DEFAULT = lazy_gettext(
    "message_reply_sla_user_message_provider_default"
)
MESSAGE_REPLY_SLA_USER_MESSAGE_WALLET = lazy_gettext(
    "message_reply_sla_user_message_wallet"
)

MESSAGE_REPLY_SLA_USER_MESSAGE_WALLET_WITH_INBOUND_PHONE_NUMBER = lazy_gettext(
    "message_reply_sla_user_message_wallet_with_inbound_phone_number"
)


class ParticipantSchema(MavenSchema):
    user = fields.Nested(UserSchema, exclude=("created_at",))
    is_initiator = fields.Boolean()
    is_anonymous = fields.Boolean()
    max_chars = fields.Integer()


# Custom practitioner profile schema for specific use in channels response
# payloads. This provides the ability to exclude fields without impacting the
# practitioner profile schema used elsewhere.
# https://docs.google.com/spreadsheets/d/1KNVRejXg7xBOgDkvH2SucM81PuAVRtxbs_LybAj9UKk/edit#gid=152098691
class PractitionerProfileInChannelSchema(TranslatedPractitionerProfileSchemaV1):
    # When a practitioner user makes a request for channels, the
    # UserProfilesSchema.get_practitioner_profile does not pass the additional
    # excludes because the requesting user matches the user being serialized.
    # this leads to many additional queries that are not needed to satisfy
    # channel requests.
    class Meta:
        # To ensure the channels resp always excludes the desired fields we
        # extend them here with more that we dont utilize
        exclude = list(
            practitioner_profile_other_user_field_exclusions.union(
                [
                    # fields that have been confirmed to not be used by any
                    # client. See google sheets link above
                    "country_code",
                    "subdivision_code",
                    "certified_subdivisions",
                    # fields that are required to exist but not accessed by any
                    # client. for these we will set an acceptable default value
                    # in the data_handler below
                    "agreements",
                    "certified_subdivision_codes",
                ]
            )
        )


# A data handler is used to apply post-serialize overrides. This is required due
# to marshmallow_v1's property load behavior which loads data for all fields on
# the model that are not ignored. This prevents us from loading useless and
# costly data.
@PractitionerProfileInChannelSchema.data_handler
def practitioner_profile_in_channel_data_handler(
    self: PractitionerProfileInChannelSchema,
    data: dict,
    obj: PractitionerProfile,
) -> dict[str, Any]:

    # define overrides in func scope to protect from downstream modifications
    # being reflected in future instances. Pass-by-ref protection.
    overrides = {
        # Not accessed but required to exist by legacy clients.
        "agreements": {"subscription": False},
        "certified_subdivision_codes": [],
    }
    # inject all overrides listed above
    if data and isinstance(data, dict):
        data.update(overrides)
    return data


# Custom member profile schema for specific use in channels response
# payloads. This provides the ability to exclude fields without impacting the
# member profile schema used elsewhere.
# https://docs.google.com/spreadsheets/d/1KNVRejXg7xBOgDkvH2SucM81PuAVRtxbs_LybAj9UKk/edit#gid=152098691
class MemberProfileInChannelSchema(MemberProfileSchema):
    class Meta:
        exclude = (
            # fields that have been confirmed to not be used by any
            # client. See google sheets link above
            "dashboard",
            "subdivision_code",
            "tel_region",
            # fields that are required to exist but not accessed by any
            # client. for these we will set an acceptable default value
            # in the data_handler below
            "can_book_cx",
        )


# A data handler is used to apply post-serialize overrides. This is required due
# to marshmallow_v1's property load behavior which loads data for all fields on
# the model that are not ignored. This prevents us from loading useless and
# costly data.
@MemberProfileInChannelSchema.data_handler
def member_profile_in_channel_data_handler(
    self: MemberProfileInChannelSchema,
    data: dict,
    obj: MemberProfile,
) -> dict[str, Any]:
    # define overrides in func scope to protect from downstream modifications
    # being reflected in future instances. Pass-by-ref protection.
    overrides = {
        # Not accessed but required to exist by legacy clients.
        "can_book_cx": False,
    }
    # inject all overrides listed above
    if data and isinstance(data, dict):
        data.update(overrides)
    return data


# Custom user profile schema for specific use in channels response payloads.
# This provides the ability to exclude fields without impacting the user profile
# schema used elsewhere. We override 2 key getters and pass in a replacement
# class to use.
# https://docs.google.com/spreadsheets/d/1KNVRejXg7xBOgDkvH2SucM81PuAVRtxbs_LybAj9UKk/edit#gid=152098691
class UserProfilesInChannelSchema(UserProfilesSchema):
    def get_member_profile(
        self,
        profiles: dict[str, MemberProfile],
        context: dict[str, Any],
        profile_schema: Type[MemberProfileSchema] | None = MemberProfileInChannelSchema,
    ) -> dict[str, Any]:
        return super().get_member_profile(
            profiles,
            context,
            profile_schema=profile_schema,
        )

    def get_practitioner_profile(
        self,
        profiles: dict[str, PractitionerProfile],
        context: dict[str, Any],
        profile_schema: (
            Type[PractitionerProfileSchema] | None
        ) = PractitionerProfileInChannelSchema,
    ) -> dict[str, Any]:
        return super().get_practitioner_profile(
            profiles,
            context,
            profile_schema=profile_schema,
        )


# Custom user schema for specific use in channels response payloads. This
# provides the ability to exclude fields without impacting the user schema used
# elsewhere.
# https://docs.google.com/spreadsheets/d/1KNVRejXg7xBOgDkvH2SucM81PuAVRtxbs_LybAj9UKk/edit#gid=152098691
class UserInChannelSchema(UserSchema):
    class Meta:
        exclude = (
            # fields that have been confirmed to not be used by any
            # client. See google sheets link above
            "test_group",
            "created_at",
            "subscription_plans",
            "feature_flag",
            "feature_flags",
            "care_team_with_type",
            # fields that are required to exist but not accessed by any
            # client. for these we will set an acceptable default value
            # in the data_handler below
            "care_coordinators",
        )

    active_tracks = fields.Method(
        "get_active_tracks"
    )  # use a method so we can manually use a V3 schema

    def get_profiles(
        self,
        user: User,
        context: dict[str, Any],
        profiles_schema: Type[UserProfilesSchema] | None = UserProfilesInChannelSchema,
    ) -> dict[str, Any] | None:
        return super().get_profiles(
            user,
            context,
            profiles_schema=profiles_schema,
        )

    def get_active_tracks(self, user: User, _: Any) -> List[Dict[str, Any]]:
        from messaging.schemas.messaging_v3 import (  # avoid circular dependency :/
            MemberTrackInChannelSchemaV3,
        )

        return [
            MemberTrackInChannelSchemaV3().dump(active_track)
            for active_track in user.active_tracks
        ]


# A data handler is used to apply post-serialize overrides. This is required due
# to marshmallow_v1's property load behavior which loads data for all fields on
# the model that are not ignored. This prevents us from loading useless and
# costly data.
@UserInChannelSchema.data_handler
def user_in_channel_data_handler(
    self: UserInChannelSchema,
    data: dict,
    obj: User,
) -> dict[str, Any]:
    # define overrides in func scope to protect from downstream modifications
    # being reflected in future instances. Pass-by-ref protection.
    overrides = {
        # Not accessed but required to exist by legacy clients.
        "care_coordinators": [],
    }
    # inject all overrides listed above
    if data and isinstance(data, dict):
        data.update(overrides)
    return data


# Custom participant schema for specific use in channels response payloads. This
# provides the ability to exclude fields without impacting the participant
# schema used elsewhere.
# https://docs.google.com/spreadsheets/d/1KNVRejXg7xBOgDkvH2SucM81PuAVRtxbs_LybAj9UKk/edit#gid=152098691
class ParticipantInChannelSchema(MavenSchema):
    user = fields.Nested(UserInChannelSchema, exclude=("created_at",))
    is_initiator = fields.Boolean()
    is_anonymous = fields.Boolean()
    max_chars = fields.Integer()


class MessageUsersSchema(MavenSchema):
    user_id = fields.Integer()
    is_read = fields.Boolean()
    is_acknowledged = fields.Boolean()


class IncludeCountryMixin:
    def __init__(
        self: HasContextProtocol,
        *args: Tuple,
        **kwargs: Any,
    ) -> None:
        super().__init__(*args, **kwargs)
        self.context["include_country_info"] = True


class AttachmentSchema(MavenSchema):
    id = fields.Function(lambda asset: asset.external_id)
    file_name = fields.String()
    content_type = fields.String()
    content_length = fields.Integer()
    thumbnail = fields.Function(lambda asset: asset.direct_thumbnail_url())


class MessageSchema(IncludeCountryMixin, MavenSchema):
    id = fields.Integer()
    body = fields.String()
    created_at = MavenDateTime()
    meta = fields.Nested(MessageUsersSchema, many=True)
    author = fields.Method("get_author")

    def get_author(
        self,
        message: Message,
        context: dict[str, Any],
        user_schema: Type[UserSchema] | None = None,
    ) -> dict[str, Any]:
        if not user_schema:
            # if not explicitly specified, default to the stripped down schema
            user_schema = UserInChannelSchema

        if message.user:
            schema = user_schema()
            schema.context = context
            data = schema.dump(message.user).data
            return data

        elif message.availability_notification_request_id:
            return _get_request_availability_bot_user_information()
        else:
            return _get_reimbursements_bot_user_information()


class MessageInChannelsSchema(MessageSchema):
    id = fields.Integer()
    body = fields.String()
    created_at = MavenDateTime()
    meta = fields.Nested(MessageUsersSchema, many=True)
    author = fields.Method("get_author")

    def get_author(
        self,
        message: Message,
        context: dict[str, Any],
        user_schema: Type[UserSchema] | None = UserInChannelSchema,
    ) -> dict[str, Any]:
        return super().get_author(
            message,
            context,
            user_schema=user_schema,
        )


def _get_reimbursements_bot_user_information() -> dict[str, Any]:
    """Information for a mock user for Maven Wallet channels"""
    schema = UserSchema(exclude=["care_coordinators", "test_group", "created_at"])
    data = schema.dump({}).data
    data["first_name"] = "Maven Wallet"
    data["full_name"] = "Maven Wallet"
    data["name"] = "Maven Wallet"
    data["email"] = "wallet@mavenclinic.com"
    profiles_schema = PractitionerProfileSchema().dump({"response_time": 24}).data
    profiles_schema["verticals"] = [CX_VERTICAL_NAME]
    data["profiles"] = {"practitioner": profiles_schema}
    data["role"] = "practitioner"
    data["is_initiator"] = True
    data["max_chars"] = 0
    return data


def _get_request_availability_bot_user_information() -> dict[str, Any]:
    """Information for a mock user for Availability Requests"""
    schema = UserSchema(exclude=["care_coordinators", "test_group"])
    data = schema.dump({}).data
    data["first_name"] = "Maven Request Availability"
    data["full_name"] = "Maven Request Availability"
    data["name"] = "Maven Request Availability"
    data["email"] = "no-reply@mavenclinic.com"
    profiles_schema = PractitionerProfileSchema().dump({"response_time": 24}).data
    profiles_schema["verticals"] = [CX_VERTICAL_NAME]
    data["profiles"] = {"practitioner": profiles_schema}
    data["role"] = "practitioner"
    data["is_initiator"] = True
    data["max_chars"] = 0
    # fmt: off
    # TODO: until the multiple versions of black are resolved, this
    # will continue to cause issues with the type checker. Remove #fmt: off after.
    data[
        "avatar_url"
    ] = f"{current_web_origin()}/img/messages/Maven_Message-Avatar@2x.png"
    # fmt: on
    return data


# fmt: off
# TODO: until the multiple versions of black are resolved, `...` position
# will continue to cause issues with the type checker. Remove #fmt: off after.
@overload
def include_attachments(
    schema: MessageSchema,
    data: dict[str, Any],
    message: Message,
) -> dict[str, Any]:
    ...


@overload
def include_attachments(
    schema: MessageSchema,
    data: list[dict[str, Any]],
    message: list[Message],
) -> list[dict[str, Any]]:
    ...
# fmt: on


# not included in messaging_v3
# never actually hit in v1 so not ported to v3
@MessageSchema.data_handler
def include_attachments(
    schema: MessageSchema,
    data: dict[str, Any] | list[dict[str, Any]],
    message: Message | list[Message],
) -> dict[str, Any] | list[dict[str, Any]]:
    if (
        request.headers["User-Agent"] == "MAVEN_ANDROID"
        and "X-Maven-Client" not in request.headers
    ):
        log.warning(
            "Omitting attachments for backwards compatibility with android client."
        )
        return data

    if isinstance(data, dict) and isinstance(message, Message):
        data["attachments"] = (
            AttachmentSchema().dump(message.attachments, many=True).data
        )
        return data
    elif isinstance(data, list) and isinstance(message, list):
        for d, m in zip(data, message):
            d["attachments"] = AttachmentSchema().dump(m.attachments, many=True).data
        return data

    raise ValueError(
        f"data and message must both be either dicts or a lists, got message: {message}, data: {data}"
    )


# fmt: off
# TODO: until the multiple versions of black are resolved, `...` position
# will continue to cause issues with the type checker. Remove #fmt: off after.
@overload
def add_maven_wallet_author(
    schema: MessageSchema,
    data: dict[str, Any],
    message: Message,
) -> dict[str, Any]:
    ...


@overload
def add_maven_wallet_author(
    schema: MessageSchema,
    data: list[dict[str, Any]],
    message: list[Message],
) -> list[dict[str, Any]]:
    ...
# fmt: on


# not included in messaging_v3
# not needed so wasn't ported to v3
@MessageSchema.data_handler
def add_maven_wallet_author(
    schema: MessageSchema,
    data: dict[str, Any] | list[dict[str, Any]],
    message: Message | list[Message],
) -> dict[str, Any] | list[dict[str, Any]]:
    channel_ids_to_check = []
    zipped_list: list[Tuple[dict[str, Any], Message]] = []
    if isinstance(data, dict) and isinstance(message, Message):
        zipped_list.append((data, message))
    elif isinstance(data, list) and isinstance(message, list):
        zipped_list.extend(zip(data, message))
    for _d, m in zipped_list:
        if m.user is None:
            channel_ids_to_check.append(m.channel.id)

    attached_channel_ids = is_attached_to_wallet(channel_ids_to_check)

    for d, m in zipped_list:
        # if there is no user marked as the author and the channel is attached
        # to a wallet then set the author to the reimbursements bot
        if not m.user and m.channel.id in attached_channel_ids:
            d["author"] = _get_reimbursements_bot_user_information()

    return data


class ChannelSchema(IncludeCountryMixin, MavenSchema):
    id = fields.Integer()
    name = fields.String()
    internal = fields.Boolean()
    privilege_type = fields.String()
    participants = fields.Nested(ParticipantInChannelSchema, many=True)
    new_messages = fields.Method("get_new_messages")
    total_messages = fields.Method("get_total_messages")
    last_message = fields.Nested(MessageInChannelsSchema, many=False, allow_null=True)
    wallet_id = fields.Method("get_wallet_id")
    can_accept_messages = fields.Method("get_can_accept_messages")
    reply_sla_user_message = fields.Method("get_reply_sla_user_message")

    def get_wallet_id(
        self,
        channel: Channel,
        context: dict[str, Any],
    ) -> str | None:
        wallet_id = get_wallet_id_by_channel_id(channel.id)

        if not wallet_id:
            return None

        # TODO: the conversion to string is not necessary again. Check
        # get_wallet_id_by_channel_id.
        return str(wallet_id)

    def get_new_messages(
        self,
        channel: Channel,
        context: dict[str, Any],
    ) -> int:
        new_messages = 0
        user = context.get("user")
        if channel and user:
            new_messages = len(channel.new_message_ids(user.id))
        return new_messages

    def get_total_messages(
        self,
        channel: Channel,
        context: dict[str, Any],
    ) -> int:
        total = 0
        if channel and channel.messages:
            total = len(channel.messages)
        return total

    # TODO: extract this to messaging/services/messaging after the refactor of
    # the GET /channels endpoint.
    # Aaron Jones 2023-11-03
    def get_can_accept_messages(
        self,
        channel: Channel,
        context: dict[str, Any],
    ) -> bool:
        # note these are direct copy/pasta of the logic found in the message
        # post handler here
        # https://gitlab.com/maven-clinic/maven/maven/-/blob/4fca56dbb1d8c5bfcad47acb270e37bb6c3dfb0b/api/messaging/resources/messaging.py#L308
        # during the refactor of this code to the service folder DRY up the
        # logic. Additionally each of these could be their own helper.

        # there must be participants in this channel

        if not channel.participants:
            return False
        # the practitioner must be available
        for p in channel.participants:
            u = p.user
            if u.is_practitioner and (
                not u.practitioner_profile.active
                or not u.practitioner_profile.messaging_enabled
            ):
                return False

        # if the only participant is wallet then we can't accept messages
        if len(channel.participants) == 1 and not channel.is_wallet:
            return False

        # the channel can accept messages
        return True

    def get_reply_sla_user_message(
        self,
        channel: Channel,
        context: dict[str, Any],
    ) -> str:
        """
        Get the response time SLA user messages within this channel.
        """
        # wallet specific response SLA
        if channel.is_wallet:
            inbound_phone_number = get_inbound_phone_number(user=channel.member)
            if inbound_phone_number:
                # Remove 'tel' from inbound_phone_number, which is in RFC3966 standard
                inbound_phone_number = inbound_phone_number.replace("tel:", "")
                return MESSAGE_REPLY_SLA_USER_MESSAGE_WALLET_WITH_INBOUND_PHONE_NUMBER.format(
                    phone_number=inbound_phone_number
                )

            return MESSAGE_REPLY_SLA_USER_MESSAGE_WALLET

        # if a channel is marked as internal, then it is CA specific
        if channel.internal:
            return MESSAGE_REPLY_SLA_USER_MESSAGE_CA_DEFAULT

        # return the provider specific SLA for non-CAs
        return MESSAGE_REPLY_SLA_USER_MESSAGE_PROVIDER_DEFAULT


# fmt: off
# TODO: until the multiple versions of black are resolved, `...` position
# will continue to cause issues with the type checker. Remove #fmt: off after.
@overload
def add_maven_wallet_participant(
    schema: ChannelSchema,
    data: dict[str, Any],
    message: Channel,
) -> dict[str, Any]:
    ...


@overload
def add_maven_wallet_participant(
    schema: ChannelSchema,
    data: list[dict[str, Any]],
    message: list[Channel],
) -> list[dict[str, Any]]:
    ...
# fmt: on


@ChannelSchema.data_handler
def add_maven_wallet_participant(
    schema: ChannelSchema,
    data: dict[str, Any] | list[dict[str, Any]],
    channel: Channel | list[Channel],
) -> dict[str, Any] | list[dict[str, Any]]:
    # Collect all channel IDs for which we need to check attachment to a wallet
    channel_ids_to_check = []

    zipped_list: list[Tuple[dict[str, Any], Message]] = []
    if isinstance(data, dict) and isinstance(channel, Channel):
        zipped_list.append((data, channel))
    elif isinstance(data, list) and isinstance(channel, list):
        zipped_list.extend(zip(data, channel))

    for _d, c in zipped_list:
        if isinstance(c, dict):
            channel_ids_to_check.append(c.get("id"))
        else:
            channel_ids_to_check.append(c.id)

    # Make a single database query to check if these channel IDs are attached to a wallet
    attached_channel_ids = is_attached_to_wallet(channel_ids_to_check)
    for d, c in zipped_list:
        if c.id in attached_channel_ids:
            user = _get_reimbursements_bot_user_information()
            wallet_participant = {
                "is_anonymous": False,
                "is_initiator": True,
                "max_chars": user["max_chars"],
                "user": user,
            }
            d["participants"].append(wallet_participant)
    return data


class ChannelParticipantsSchema(MavenSchema):
    data = fields.Nested(ParticipantSchema, many=True)


class ChannelMessagesSchema(PaginableOutputSchema):
    data = fields.Nested(MessageSchema, many=True)  # type: ignore[assignment]


class MessagePOSTArgs(MavenSchema):
    body = fields.String()
    attachments = fields.List(
        fields.String(validate=lambda v: v.isdigit()),
        validate=validate.Length(
            max=10,
            error="Message failed to send with too many attachments. Limit of 10 attachments.",
        ),
    )
    source = fields.Enum(
        choices=[s.value for s in MessageSourceEnum], missing=None, allow_none=True
    )


class MessageAckPOSTArgs(MavenSchema):
    ack_id = fields.Integer()


class MessageAckSchema(MavenSchema):
    ack_id = fields.Integer(attribute="id")
    display_message = fields.String()


class MessageAcksSchema(MavenSchema):
    data = fields.Nested(MessageAckSchema, many=True)


class MessageProductSchema(MavenSchema):
    id = fields.Integer()
    number_messages = fields.Integer(attribute="number_of_messages")
    price = fields.Decimal(as_string=True)


class MessageProductsSchema(MavenSchema):
    data = fields.Nested(MessageProductSchema, many=True)


class MessageBillingSchema(MavenSchema):
    maven_credit_used = fields.String()
    stripe_charge_id = fields.String()
    card_brand = fields.String()
    card_last4 = fields.String()
    charged_at = MavenDateTime()
    available_messages = fields.Integer()


class MessageBillingGETSchema(MavenSchema):
    available_messages = fields.Integer()
    modified_at = MavenDateTime()
