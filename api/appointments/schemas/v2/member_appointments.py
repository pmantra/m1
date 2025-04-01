from __future__ import annotations  # needed for python 3.9 type annotations

import enum
from dataclasses import dataclass, replace
from datetime import datetime
from typing import List

from marshmallow import fields as marshmallow_fields
from marshmallow import validate

from appointments.models.constants import AppointmentTypes
from appointments.schemas.appointments import PrivacyType
from appointments.schemas.v2.member_appointment import (
    MemberAppointmentGetResponseNeed,
    MemberAppointmentGetResponseProvider,
    MemberAppointmentServiceResponseNeed,
    MemberAppointmentServiceResponseProvider,
)
from views.schemas.base import MavenSchemaV3, PaginableOutputSchemaV3
from views.schemas.common_v3 import MavenDateTime


class OrderDirections(str, enum.Enum):
    asc = "asc"
    desc = "desc"


class MemberAppointmentsListGetRequestSchema(MavenSchemaV3):
    order_direction = marshmallow_fields.String(
        required=False,
        default=OrderDirections.desc,
        validate=validate.OneOf([d.value for d in OrderDirections]),
        error="Invalid ordering direction",
    )
    limit = marshmallow_fields.Integer(required=False, load_default=5)
    offset = marshmallow_fields.Integer(required=False, load_default=0)
    scheduled_start = MavenDateTime(required=True)
    scheduled_end = MavenDateTime(required=True)


class MemberAppointmentVerticalGetResponse(MavenSchemaV3):
    id = marshmallow_fields.Integer(required=True)
    name = marshmallow_fields.String(required=True)
    description = marshmallow_fields.String(required=True)
    can_prescribe = marshmallow_fields.Boolean(required=True)
    filter_by_state = marshmallow_fields.Boolean(required=True)


class MemberAppointmentsListGetResponseElement(MavenSchemaV3):
    id = marshmallow_fields.Integer(required=True)
    state = marshmallow_fields.String(required=True, allow_none=True)
    product_id = marshmallow_fields.Integer(required=True)
    provider = marshmallow_fields.Nested(
        MemberAppointmentGetResponseProvider,
        required=True,
    )
    privacy = marshmallow_fields.String(
        validate=validate.OneOf([d.value for d in PrivacyType]),
        error="Invalid Privacy Type",
    )
    appointment_type = marshmallow_fields.String(
        validate=validate.OneOf([d.value for d in AppointmentTypes]),
        error="Invalid Appointment Type",
    )
    pre_session_notes = marshmallow_fields.String(required=True, allow_none=True)
    cancelled_at = MavenDateTime(required=True, allow_none=True)
    scheduled_start = MavenDateTime(required=True)
    scheduled_end = MavenDateTime(required=True)
    member_started_at = MavenDateTime(required=True, allow_none=True)
    member_ended_at = MavenDateTime(required=True, allow_none=True)
    practitioner_started_at = MavenDateTime(required=True, allow_none=True)
    practitioner_ended_at = MavenDateTime(required=True, allow_none=True)
    member_disconnected_at = MavenDateTime(required=True, allow_none=True)
    practitioner_disconnected_at = MavenDateTime(required=True, allow_none=True)
    phone_call_at = MavenDateTime(required=True, allow_none=True)
    survey_types = marshmallow_fields.List(marshmallow_fields.String())
    need = marshmallow_fields.Nested(MemberAppointmentGetResponseNeed, many=False)


class MemberAppointmentsListGetResponse(PaginableOutputSchemaV3):
    data = marshmallow_fields.Nested(  # type: ignore[assignment] # Incompatible types in assignment (expression has type "Nested", base class "PaginableOutputSchemaV3" defined the type as "RawWithDefaultV3")
        MemberAppointmentsListGetResponseElement, many=True, required=True
    )


@dataclass
class MemberAppointmentsListServiceResponseElement:
    id: int
    state: str | None
    product_id: int
    provider: MemberAppointmentServiceResponseProvider
    pre_session_notes: str
    cancelled_at: datetime
    scheduled_start: datetime
    scheduled_end: datetime
    privacy: str
    appointment_type: AppointmentTypes
    member_started_at: datetime
    member_ended_at: datetime
    practitioner_started_at: datetime
    practitioner_ended_at: datetime
    member_disconnected_at: datetime
    practitioner_disconnected_at: datetime
    phone_call_at: datetime
    survey_types: List[str]
    need: MemberAppointmentServiceResponseNeed

    def translate(self) -> MemberAppointmentsListServiceResponseElement:
        """
        Must be called with a locale set (from flask or "flask_babel.force_locale")
        """
        return replace(self, provider=self.provider.translate())
