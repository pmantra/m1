# for marshmallow v3
from __future__ import annotations

from typing import Any, Type

from marshmallow import fields, post_dump, validate

from authn.models.user import User
from common.constants import current_web_origin
from l10n.db_strings.schema import TranslatedPractitionerProfileSchemaV3
from messaging.models.messaging import Channel, Message, MessageSourceEnum
from messaging.schemas.messaging import (
    MESSAGE_REPLY_SLA_USER_MESSAGE_CA_DEFAULT,
    MESSAGE_REPLY_SLA_USER_MESSAGE_PROVIDER_DEFAULT,
    MESSAGE_REPLY_SLA_USER_MESSAGE_WALLET,
    MESSAGE_REPLY_SLA_USER_MESSAGE_WALLET_WITH_INBOUND_PHONE_NUMBER,
    IncludeCountryMixin,
)
from models.profiles import MemberProfile, PractitionerProfile
from models.tracks import MemberTrack
from models.verticals_and_specialties import CX_VERTICAL_NAME
from phone_support.service.phone_support import get_inbound_phone_number
from utils.log import logger
from views.schemas.base import (
    BooleanWithDefault,
    IntegerWithDefaultV3,
    ListWithDefaultV3,
    MavenDateTimeV3,
    MavenSchemaV3,
    MemberProfileSchemaV3,
    NestedWithDefaultV3,
    PaginableArgsSchemaV3,
    PaginableOutputSchemaV3,
    PractitionerProfileSchemaV3,
    StringWithDefaultV3,
    UserProfilesSchemaV3,
    UserSchemaV3,
)
from views.schemas.common import (
    _other_user_field_exclusions as practitioner_profile_other_user_field_exclusions,
)
from views.schemas.common_v3 import MavenDateTime
from views.schemas.FHIR.patient_track import MemberTrackSchema
from wallet.utils.common import get_wallet_id_by_channel_id, is_attached_to_wallet

log = logger(__name__)


def _get_reimbursements_bot_user_information_v3() -> dict[str, Any]:
    """Information for a bot user for Maven Wallet channels"""
    profiles_schema = {
        "faq_password": None,
        "address": {
            "city": "",
            "zip_code": "",
            "country": "",
            "street_address": "",
            "state": "",
        },
        "can_prescribe_to_member": False,
        "can_member_interact": True,
        "user_id": 0,
        "cancellation_policy": None,
        "is_cx": None,
        "messaging_enabled": False,
        "care_team_type": None,
        "country": None,
        "categories": None,
        "subdivision_code": "",
        "work_experience": "",
        "certified_subdivision_codes": [],
        "response_time": 24,
        "rating": None,
        "agreements": {"subscription": False},
        "tel_region": None,
        "languages": None,
        "verticals": ["Care Advocate"],
        "country_code": "",
        "certifications": None,
        "reference_quote": "",
        "next_availability": None,
        "can_prescribe": False,
        "tel_number": "",
        "state": None,
        "awards": "",
        "vertical_objects": [],
        "certified_states": [],
        "specialties": None,
        "years_experience": 0,
        "education": "",
        "phone_number": "",
    }
    data = {
        "first_name": "Maven Wallet",
        "full_name": "Maven Wallet",
        "name": "Maven Wallet",
        "email": "wallet@mavenclinic.com",
        "profiles": {"practitioner": profiles_schema},
        "role": "practitioner",
        "is_initiator": True,
        "max_chars": 0,
        "last_name": "",
        "middle_name": "",
        "subscription_plans": None,
        "country": None,
        "id": 0,
        "image_id": 0,
        "image_url": None,
        "esp_id": None,
        "username": None,
        "organization": None,
        "encoded_id": None,
        "avatar_url": "",
    }
    return data


def _get_request_availability_bot_user_information_v3() -> dict[str, Any]:
    """Information for a bot user for Availability Requests"""
    profiles_schema = {
        "faq_password": None,
        "address": {
            "city": "",
            "zip_code": "",
            "country": "",
            "street_address": "",
            "state": "",
        },
        "can_prescribe_to_member": False,
        "can_member_interact": True,
        "user_id": 0,
        "cancellation_policy": None,
        "is_cx": None,
        "messaging_enabled": False,
        "care_team_type": None,
        "country": None,
        "categories": None,
        "subdivision_code": "",
        "work_experience": "",
        "certified_subdivision_codes": [],
        "response_time": 24,
        "rating": None,
        "agreements": {"subscription": False},
        "tel_region": None,
        "languages": None,
        "verticals": [CX_VERTICAL_NAME],
        "country_code": "",
        "certifications": None,
        "reference_quote": "",
        "next_availability": None,
        "can_prescribe": False,
        "tel_number": "",
        "state": None,
        "awards": "",
        "vertical_objects": [],
        "certified_states": [],
        "specialties": None,
        "years_experience": 0,
        "education": "",
        "phone_number": "",
    }
    data = {
        "first_name": "Maven Request Availability",
        "full_name": "Maven Request Availability",
        "name": "Maven Request Availability",
        "email": "no-reply@mavenclinic.com",
        "profiles": {"practitioner": profiles_schema},
        "role": "practitioner",
        "is_initiator": True,
        "max_chars": 0,
        "avatar_url": f"{current_web_origin()}/img/messages/Maven_Message-Avatar@2x.png",
        "subscription_plans": None,
        "esp_id": None,
        "image_id": 0,
        "username": None,
        "id": 0,
        "last_name": "",
        "created_at": None,
        "image_url": None,
        "middle_name": "",
        "organization": None,
        "country": None,
        "encoded_id": None,
    }
    # fmt: off
    # TODO: until the multiple versions of black are resolved, this
    # will continue to cause issues with the type checker. Remove #fmt: off after.
    # fmt: on
    return data


class ChannelsGETArgsV3(PaginableArgsSchemaV3):
    empty = BooleanWithDefault(dump_default=False, load_default=False)


# Custom member profile schema for specific use in channels response
# payloads. This provides the ability to exclude fields without impacting the
# member profile schema used elsewhere.
# https://docs.google.com/spreadsheets/d/1KNVRejXg7xBOgDkvH2SucM81PuAVRtxbs_LybAj9UKk/edit#gid=152098691
class MemberProfileInChannelSchemaV3(MemberProfileSchemaV3):
    class Meta:
        exclude = (
            # fields that have been confirmed to not be used by any
            # client. See google sheets link above
            "subdivision_code",
            "tel_region",
            # fields that are required to exist but not accessed by any
            # client. for these we will set an acceptable default value
            # in the data_handler below
            "can_book_cx",
            "user_flags",
        )

    @post_dump
    def member_profile_in_channel_data_handler(  # type: ignore[no-untyped-def] # Function is missing a type annotation for one or more arguments
        self,
        data: dict,
        **kwargs,
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


# Custom practitioner profile schema for specific use in channels response
# payloads. This provides the ability to exclude fields without impacting the
# practitioner profile schema used elsewhere.
# https://docs.google.com/spreadsheets/d/1KNVRejXg7xBOgDkvH2SucM81PuAVRtxbs_LybAj9UKk/edit#gid=152098691
class PractitionerProfileInChannelSchemaV3(TranslatedPractitionerProfileSchemaV3):
    # When a practitioner user makes a request for channels, the
    # UserProfilesSchema.get_practitioner_profile does not pass the additional
    # excludes because the requesting user matches the user being serialized.
    # this leads to many additional queries that are not needed to satisfy
    # channel requests.
    class Meta:
        # To ensure the channels resp always excludes the desired fields we
        # extend them here with more that we don't utilize
        exclude = list(
            practitioner_profile_other_user_field_exclusions.union(
                [
                    # fields that have been confirmed to not be used by any
                    # client. See google sheets link above
                    "country_code",
                    "subdivision_code",
                    # "certified_subdivisions",
                    # fields that are required to exist but not accessed by any
                    # client. for these we will set an acceptable default value
                    # in the data_handler below
                    "agreements",
                    "certified_subdivision_codes",
                ]
            )
        )

    @post_dump
    def practitioner_profile_in_channel_data_handler(  # type: ignore[no-untyped-def] # Function is missing a type annotation for one or more arguments
        self,
        data: dict,
        **kwargs,
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


# Custom user profile schema for specific use in channels response payloads.
# This provides the ability to exclude fields without impacting the user profile
# schema used elsewhere. We override 2 key getters and pass in a replacement
# class to use.
# https://docs.google.com/spreadsheets/d/1KNVRejXg7xBOgDkvH2SucM81PuAVRtxbs_LybAj9UKk/edit#gid=152098691
class UserProfilesInChannelSchemaV3(UserProfilesSchemaV3):
    def get_member_profile(
        self,
        profiles: dict[str, MemberProfile],
        profile_schema: (
            Type[MemberProfileSchemaV3] | None
        ) = MemberProfileInChannelSchemaV3,
    ) -> dict[str, Any]:
        return super().get_member_profile(
            profiles,
            profile_schema=profile_schema,
        )

    def get_practitioner_profile(
        self,
        profiles: dict[str, PractitionerProfile],
        profile_schema: (
            Type[PractitionerProfileSchemaV3] | None
        ) = PractitionerProfileInChannelSchemaV3,
    ) -> dict[str, Any]:
        return super().get_practitioner_profile(
            profiles,
            profile_schema=profile_schema,
        )


class MemberTrackInChannelSchemaV3(MemberTrackSchema):
    dashboard = fields.Method(
        "get_dashboard"
    )  # DO NOT REMOVE. some front-end clients rely on this field,
    # even though it is completely useless in this context.

    def get_dashboard(self, member_track: MemberTrack) -> str:
        return member_track.dashboard


# Custom user schema for specific use in channels response payloads. This
# provides the ability to exclude fields without impacting the user schema used
# elsewhere.
# https://docs.google.com/spreadsheets/d/1KNVRejXg7xBOgDkvH2SucM81PuAVRtxbs_LybAj9UKk/edit#gid=152098691
class UserInChannelSchemaV3(UserSchemaV3):
    class Meta:
        exclude = (
            # fields that have been confirmed to not be used by any
            # client. See google sheets link above
            "test_group",
            "created_at",
            "subscription_plans",
            # fields that are required to exist but not accessed by any
            # client. for these we will set an acceptable default value
            # in the data_handler below
            "care_coordinators",
            "organization",
        )

    active_tracks = fields.Nested(MemberTrackInChannelSchemaV3, many=True)

    def get_profiles(
        self,
        user: User,
        profiles_schema: (
            Type[UserProfilesSchemaV3] | None
        ) = UserProfilesInChannelSchemaV3,
    ) -> dict[str, Any] | None:
        return super().get_profiles(
            user,
            profiles_schema=profiles_schema,
        )

    @post_dump
    def user_in_channel_data_handler(  # type: ignore[no-untyped-def] # Function is missing a type annotation for one or more arguments
        self,
        data: dict,
        **kwargs,
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
class ParticipantInChannelSchemaV3(MavenSchemaV3):
    user = fields.Nested(UserInChannelSchemaV3, exclude=("created_at",))
    is_initiator = BooleanWithDefault(dump_default=False)
    is_anonymous = BooleanWithDefault(dump_default=False)
    max_chars = IntegerWithDefaultV3(dump_default=0)


class MessageUsersSchemaV3(MavenSchemaV3):
    user_id = IntegerWithDefaultV3(dump_default=0)
    is_read = BooleanWithDefault(dump_default=False)
    is_acknowledged = BooleanWithDefault(dump_default=False)


class MessageSchemaV3(IncludeCountryMixin, MavenSchemaV3):
    id = IntegerWithDefaultV3(dump_default=0)
    body = StringWithDefaultV3(dump_default="")
    created_at = MavenDateTimeV3()
    meta = fields.Nested(MessageUsersSchemaV3, many=True)
    author = fields.Method(serialize="get_author")

    def get_author(
        self,
        message: Message,
        user_schema: Type[UserSchemaV3] | None = None,
    ) -> dict[str, Any]:
        if not user_schema:
            # if not explicitly specified, default to the stripped down schema
            user_schema = UserInChannelSchemaV3
        if message.user:
            schema = user_schema()
            schema.context = self.context
            data = schema.dump(message.user)
            return data

        elif message.availability_notification_request_id:
            return _get_request_availability_bot_user_information_v3()
        else:
            return _get_reimbursements_bot_user_information_v3()

    @post_dump(pass_original=True, pass_many=True)
    def include_attachments(
        self,
        data: dict[str, Any] | list[dict[str, Any]],
        message: Message | list[Message],
        many: bool,
    ) -> dict[str, Any] | list[dict[str, Any]]:
        if isinstance(data, dict) and isinstance(message, Message):
            data["attachments"] = AttachmentSchemaV3().dump(
                message.attachments, many=True  # type: ignore[union-attr]
            )
            return data

        elif isinstance(data, list) and isinstance(message, list):
            for d, m in zip(data, message):
                d["attachments"] = AttachmentSchemaV3().dump(m.attachments, many=True)
            return data

        raise ValueError(
            f"data and message must both be either dicts or a lists, got message{type(message)}: {message}, data{type(data)}: {data}"
        )


class AttachmentSchemaV3(MavenSchemaV3):
    id = fields.Function(
        lambda asset: asset.external_id if hasattr(asset, "external_id") else None
    )
    file_name = StringWithDefaultV3(default="")
    content_type = StringWithDefaultV3(default="")
    content_length = IntegerWithDefaultV3(default=0)
    thumbnail = fields.Function(
        lambda asset: asset.direct_thumbnail_url()
        if hasattr(asset, "direct_thumbnail_url")
        else None
    )


class MessageInChannelsSchemaV3(MessageSchemaV3):
    id = IntegerWithDefaultV3(dump_default=0)
    body = StringWithDefaultV3(dump_default="")
    created_at = MavenDateTimeV3()
    meta = fields.Nested(MessageUsersSchemaV3, many=True)
    author = fields.Method(serialize="get_author")

    def get_author(
        self,
        message: Message,
        user_schema: Type[UserSchemaV3] | None = UserInChannelSchemaV3,
    ) -> dict[str, Any]:
        return super().get_author(
            message,
            user_schema=user_schema,
        )


class ChannelSchemaV3(IncludeCountryMixin, MavenSchemaV3):
    id = IntegerWithDefaultV3(dump_default=0)
    name = StringWithDefaultV3(dump_default="")
    internal = BooleanWithDefault(dump_default=False)
    privilege_type = StringWithDefaultV3(dump_default="")
    participants = fields.Nested(ParticipantInChannelSchemaV3, many=True)
    new_messages = fields.Method(serialize="get_new_messages")
    total_messages = fields.Method(serialize="get_total_messages")
    last_message = NestedWithDefaultV3(
        MessageInChannelsSchemaV3, many=False, allow_null=True
    )
    wallet_id = fields.Method(serialize="get_wallet_id")
    can_accept_messages = fields.Method(serialize="get_can_accept_messages")
    reply_sla_user_message = fields.Method(serialize="get_reply_sla_user_message")

    @staticmethod
    def get_wallet_id(
        channel: Channel,
    ) -> str | None:
        wallet_id = get_wallet_id_by_channel_id(channel.id)

        if not wallet_id:
            return None

        # TODO: the conversion to string is not necessary again. Check
        # get_wallet_id_by_channel_id.
        return str(wallet_id)

    def get_new_messages(self, channel: Channel) -> int:
        new_messages = 0
        user = self.context.get("user")
        if channel and user:
            new_messages = len(channel.new_message_ids(user.id))
        return new_messages

    def get_total_messages(
        self,
        channel: Channel,
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
    ) -> bool:
        # note these are direct copy/pasta of the logic found in the message
        # post handler here
        # https://gitlab.com/maven-clinic/maven/maven/-/blob/4fca56dbb1d8c5bfcad47acb270e37bb6c3dfb0b/api/messaging/resources/messaging.py#L308
        # during the refactor of this code to the service folder DRY up the
        # logic. Additionally, each of these could be their own helper.
        if isinstance(channel, dict):
            return False
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

    @post_dump
    def add_maven_wallet_participant(  # type: ignore[no-untyped-def] # Function is missing a type annotation for one or more arguments
        self,
        data: dict[str, Any],
        **kwargs,
    ) -> dict[str, Any]:
        # Make a single database query to check if these channel IDs are attached to a wallet
        attached_channel_ids = is_attached_to_wallet([data["id"]])
        if data["id"] in attached_channel_ids:
            user = _get_reimbursements_bot_user_information_v3()
            wallet_participant = {
                "is_anonymous": False,
                "is_initiator": True,
                "max_chars": user["max_chars"],
                "user": user,
            }
            data["participants"].append(wallet_participant)
        return data


class ChannelsSchemaV3(PaginableOutputSchemaV3):
    data = NestedWithDefaultV3(ChannelSchemaV3, many=True, dump_default=[])  # type: ignore[assignment]
    message_notifications_consent = BooleanWithDefault(dump_default=False)


class ChannelMessagesSchemaV3(PaginableOutputSchemaV3):
    data = NestedWithDefaultV3(MessageSchemaV3, many=True, dump_default=[])  # type: ignore[assignment]


class MessageBillingSchemaV3(MavenSchemaV3):
    maven_credit_used = StringWithDefaultV3(default="")
    stripe_charge_id = StringWithDefaultV3(default="")
    card_brand = StringWithDefaultV3(default="")
    card_last4 = StringWithDefaultV3(default="")
    charged_at = MavenDateTime()
    available_messages = IntegerWithDefaultV3(dump_default=0)


class MessageBillingGETSchemaV3(MavenSchemaV3):
    available_messages = IntegerWithDefaultV3(dump_default=0)
    modified_at = MavenDateTime()


class MessagePOSTArgsV3(MavenSchemaV3):
    body = StringWithDefaultV3(default="")
    attachments = ListWithDefaultV3(
        fields.String(validate=lambda v: v.isdigit()),
        validate=validate.Length(
            max=10,
            error="Message failed to send with too many attachments. Limit of 10 attachments.",
        ),
        default=[],
    )
    source = fields.Enum(enum=MessageSourceEnum, missing=None, allow_none=True)


class ParticipantSchemaV3(MavenSchemaV3):
    user = NestedWithDefaultV3(UserSchemaV3, exclude=("created_at",))
    is_initiator = fields.Boolean()
    is_anonymous = fields.Boolean()
    max_chars = IntegerWithDefaultV3(default=0)


class ChannelParticipantsSchemaV3(MavenSchemaV3):
    data = NestedWithDefaultV3(ParticipantSchemaV3, many=True, default=[])


class ChannelsUnreadMessagesResourceV3(MavenSchemaV3):
    count = IntegerWithDefaultV3(dump_default=0)
