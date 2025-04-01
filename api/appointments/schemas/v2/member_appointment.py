from __future__ import annotations  # needed for python 3.9 type annotations

from dataclasses import asdict, dataclass, field, replace
from datetime import datetime

from marshmallow import fields as marshmallow_fields
from marshmallow import validate

from appointments.models.constants import AppointmentTypes
from appointments.schemas.appointments import PrivacyType
from l10n.db_strings.translate import TranslateDBFields
from models.profiles import CareTeamTypes
from utils.log import logger
from views.schemas.base import MavenSchemaV3
from views.schemas.common_v3 import MavenDateTime

log = logger(__name__)


@dataclass
class MemberAppointmentServiceResponseCertifiedState:
    id: int
    name: str
    abbreviation: str


@dataclass
class MemberAppointmentServiceResponseVertical:
    id: int
    name: str
    slug: str | None
    description: str
    can_prescribe: bool
    filter_by_state: bool

    def translate(self) -> MemberAppointmentServiceResponseVertical:
        """
        Translates the vertical in place
        Must be called with a locale set (from flask or "flask_babel.force_locale")
        """
        if self.slug:
            return replace(
                self,
                name=TranslateDBFields().get_translated_vertical(
                    self.slug, "name", self.name
                ),
                description=TranslateDBFields().get_translated_vertical(
                    self.slug, "description", self.description
                ),
            )
        else:
            log.warn(
                "No slug found for vertical while translating",
                id=self.id,
                name=self.name,
            )
            return self


@dataclass
class MemberAppointmentServiceResponseProvider:
    id: int
    avatar_url: str | None
    verticals: list[
        MemberAppointmentServiceResponseVertical
    ]  # deprecated, `vertical` is preferred
    vertical: MemberAppointmentServiceResponseVertical = field(init=False)
    certified_states: list[MemberAppointmentServiceResponseCertifiedState]
    name: str
    first_name: str
    care_team_type: CareTeamTypes
    can_prescribe: bool
    messaging_enabled: bool
    is_care_advocate: bool
    can_member_interact: bool

    def __post_init__(self) -> None:
        if len(self.verticals) == 0:
            log.error("Provider has no vertical", provider_id=self.id)
        if len(self.verticals) == 1:
            self.vertical = self.verticals[0]
        elif len(self.verticals) > 1:
            log.warning("Provider has more than one vertical", provider_id=self.id)
            self.vertical = self.verticals[0]

    def translate(self) -> MemberAppointmentServiceResponseProvider:
        # __post_init__ will be called again by replace, so we do not need to set vertical
        return replace(
            self,
            verticals=[v.translate() for v in self.verticals],
        )


@dataclass
class MemberAppointmentServiceResponseNeed:
    id: int
    name: str


@dataclass
class MemberAppointmentByIdServiceResponse:
    id: int
    state: str
    product_id: int
    pre_session_notes: str
    cancelled_at: datetime
    scheduled_start: datetime
    scheduled_end: datetime
    privacy: PrivacyType
    appointment_type: str
    rx_enabled: bool
    video_practitioner_token: str | None
    video_member_token: str | None
    video_session_id: str | None
    member_tel_number: str
    member_state: str
    survey_types: list[str]
    provider: MemberAppointmentServiceResponseProvider
    member_started_at: datetime
    member_ended_at: datetime
    practitioner_started_at: datetime
    practitioner_ended_at: datetime
    member_disconnected_at: datetime
    practitioner_disconnected_at: datetime
    phone_call_at: datetime
    need: MemberAppointmentServiceResponseNeed | None

    def get_response_dict(self) -> dict:
        res_dict = asdict(self)
        for k, v in res_dict.items():
            if isinstance(v, datetime):
                res_dict[k] = v.isoformat()
        return res_dict

    def translate(self) -> MemberAppointmentByIdServiceResponse:
        return replace(self, provider=self.provider.translate())


class MemberAppointmentVerticalGetResponse(MavenSchemaV3):
    id = marshmallow_fields.Integer(required=True)
    name = marshmallow_fields.String(required=True)
    description = marshmallow_fields.String(required=True)
    can_prescribe = marshmallow_fields.Boolean(required=True)
    filter_by_state = marshmallow_fields.Boolean(required=True)


class MemberAppointmentGetResponseCertifiedState(MavenSchemaV3):
    id = marshmallow_fields.Integer(required=True)
    name = marshmallow_fields.String(required=True)
    abbreviation = marshmallow_fields.String(required=True)


class MemberAppointmentGetResponseNeed(MavenSchemaV3):
    id = marshmallow_fields.Integer(required=True)
    name = marshmallow_fields.String(required=True)


class MemberAppointmentGetResponseProvider(MavenSchemaV3):
    id = marshmallow_fields.Integer(required=True)
    name = marshmallow_fields.String(required=True)
    first_name = marshmallow_fields.String(required=True)
    avatar_url = marshmallow_fields.String(required=False)
    can_prescribe = marshmallow_fields.Boolean(required=True)
    care_team_type = marshmallow_fields.String(
        validate=validate.OneOf([d.value for d in CareTeamTypes]),
        error="Invalid Care Team Type",
    )
    certified_states = marshmallow_fields.List(
        marshmallow_fields.Nested(MemberAppointmentGetResponseCertifiedState)
    )
    messaging_enabled = marshmallow_fields.Boolean()
    verticals = marshmallow_fields.List(
        marshmallow_fields.Nested(MemberAppointmentVerticalGetResponse),
        required=True,
    )
    vertical = marshmallow_fields.Nested(
        MemberAppointmentVerticalGetResponse, required=True
    )
    is_care_advocate = marshmallow_fields.Boolean(required=True)
    can_member_interact = marshmallow_fields.Boolean(required=True)


class MemberAppointmentByIdGetResponse(MavenSchemaV3):
    id = marshmallow_fields.Integer(required=True)
    state = marshmallow_fields.String(required=True, allow_none=True)
    product_id = marshmallow_fields.Integer(required=True)
    provider = marshmallow_fields.Nested(
        MemberAppointmentGetResponseProvider,
        required=True,
        many=False,
    )
    pre_session_notes = marshmallow_fields.String(required=True, allow_none=True)
    cancelled_at = MavenDateTime(required=True, allow_none=True)
    scheduled_start = MavenDateTime(required=True)
    scheduled_end = MavenDateTime(required=True)
    privacy = PrivacyType = marshmallow_fields.String(
        validate=validate.OneOf([d.value for d in PrivacyType]),
        error="Invalid Privacy Type",
    )
    appointment_type = marshmallow_fields.String(
        validate=validate.OneOf([d.value for d in AppointmentTypes]),
        error="Invalid Appointment Type",
    )
    rx_enabled = marshmallow_fields.Boolean()
    video_practitioner_token = marshmallow_fields.String(required=True, allow_none=True)
    video_member_token = marshmallow_fields.String(required=True, allow_none=True)
    video_session_id = marshmallow_fields.String(required=True, allow_none=True)
    member_tel_number = marshmallow_fields.String(required=True, allow_none=True)
    member_state = marshmallow_fields.String(required=True, allow_none=True)
    member_started_at = MavenDateTime(required=True, allow_none=True)
    member_ended_at = MavenDateTime(required=True, allow_none=True)
    practitioner_started_at = MavenDateTime(required=True, allow_none=True)
    practitioner_ended_at = MavenDateTime(required=True, allow_none=True)
    member_disconnected_at = MavenDateTime(required=True, allow_none=True)
    practitioner_disconnected_at = MavenDateTime(required=True, allow_none=True)
    phone_call_at = MavenDateTime(required=True, allow_none=True)
    survey_types = marshmallow_fields.List(marshmallow_fields.String())
    need = marshmallow_fields.Nested(
        MemberAppointmentGetResponseNeed, required=True, many=False, allow_none=True
    )
