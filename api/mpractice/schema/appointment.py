from __future__ import annotations

from marshmallow import fields, validates_schema

from mpractice.schema.note import (
    ProviderAddendaAndQuestionnaireSchemaV3,
    StructuredInternalNoteSchemaV3,
)
from views.schemas.base import (
    BooleanWithDefault,
    CountrySchemaV3,
    IntegerWithDefaultV3,
    MavenDateTimeV3,
    MavenSchemaV3,
    OrganizationSchemaV3,
    StringWithDefaultV3,
    TelNumberV3,
    USAStateStringFieldAllowNoneV3,
    validate_geo_info,
)
from views.schemas.common_v3 import (
    CSVIntegerField,
    CSVStringField,
    PaginableArgsSchemaV3,
    PaginableOutputSchemaV3,
)


class VerticalSchemaV3(MavenSchemaV3):
    id = IntegerWithDefaultV3(dump_default=0, required=True)
    filter_by_state = fields.Boolean(required=False)


class MemberProfileSchemaV3(MavenSchemaV3):
    care_plan_id = IntegerWithDefaultV3(dump_default=None, required=False)
    subdivision_code = StringWithDefaultV3(dump_default="", required=False)
    state = USAStateStringFieldAllowNoneV3()
    tel_number = TelNumberV3(required=False)

    @validates_schema
    def validate_subdivision_code(self, data):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        validate_geo_info(
            country=None, state=None, subdivision_code=data.get("subdivision_code")
        )


class PractitionerProfileSchemaV3(MavenSchemaV3):
    can_prescribe = BooleanWithDefault(dump_default=False, required=False)
    messaging_enabled = BooleanWithDefault(dump_default=False, required=False)
    certified_subdivision_codes = fields.List(
        StringWithDefaultV3(dump_default=""), required=False
    )
    vertical_objects = fields.Nested(VerticalSchemaV3, many=True)

    @validates_schema
    def validate_certified_subdivision_code(self, data):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        if data.get("certified_subdivision_codes"):
            for subdivision_code in data.get("certified_subdivision_codes"):
                validate_geo_info(
                    country=None, state=None, subdivision_code=subdivision_code
                )


class MPracticeProfilesSchemaV3(MavenSchemaV3):
    member = fields.Nested(MemberProfileSchemaV3, required=False)
    practitioner = fields.Nested(PractitionerProfileSchemaV3, required=False)


class MPracticeUserSchemaV3(MavenSchemaV3):
    id = IntegerWithDefaultV3(dump_default=0, required=True)
    name = StringWithDefaultV3(dump_default="", required=False)
    profiles = fields.Nested(MPracticeProfilesSchemaV3, required=False)


class MPracticeMemberSchemaV3(MavenSchemaV3):
    id = IntegerWithDefaultV3(dump_default=0, required=True)
    name = StringWithDefaultV3(dump_default="", required=True)
    first_name = StringWithDefaultV3(dump_default="", required=False)
    email = StringWithDefaultV3(dump_default="", required=False)
    country = fields.Nested(CountrySchemaV3, required=False)
    organization = fields.Nested(OrganizationSchemaV3, required=False)
    profiles = fields.Nested(MPracticeProfilesSchemaV3, required=False)
    created_at = MavenDateTimeV3(required=False)


class DoseSpotPharmacySchemaV3(MavenSchemaV3):
    PharmacyId = StringWithDefaultV3(dump_default="", required=False)
    Pharmacy = StringWithDefaultV3(dump_default="", required=False)
    State = StringWithDefaultV3(dump_default="", required=False)
    ZipCode = StringWithDefaultV3(dump_default="", required=False)
    PrimaryFax = StringWithDefaultV3(dump_default="", required=False)
    StoreName = StringWithDefaultV3(dump_default="", required=False)
    Address1 = StringWithDefaultV3(dump_default="", required=False)
    Address2 = StringWithDefaultV3(dump_default="", required=False)
    PrimaryPhone = StringWithDefaultV3(dump_default="", required=False)
    PrimaryPhoneType = StringWithDefaultV3(dump_default="", required=False)
    City = StringWithDefaultV3(dump_default="", required=False)
    IsPreferred = fields.Boolean(dump_default=None, required=False)
    IsDefault = fields.Boolean(dump_default=None, required=False)
    ServiceLevel = IntegerWithDefaultV3(dump_default=0, required=False)


class NeedSchemaV3(MavenSchemaV3):
    id = IntegerWithDefaultV3(dump_default=0, required=True)
    name = StringWithDefaultV3(dump_default="", required=False)
    description = StringWithDefaultV3(dump_default="", required=False)


class PrescriptionInfoSchemaV3(MavenSchemaV3):
    pharmacy_id = StringWithDefaultV3(dump_default="", required=False)
    pharmacy_info = fields.Nested(
        DoseSpotPharmacySchemaV3, default=None, required=False
    )
    enabled = BooleanWithDefault(dump_default=False, required=False)


class ProductSchemaV3(MavenSchemaV3):
    practitioner = fields.Nested(MPracticeUserSchemaV3, required=False)
    vertical_id = IntegerWithDefaultV3(dump_default=0, required=False)


class SessionMetaInfoSchemaV3(MavenSchemaV3):
    created_at = MavenDateTimeV3(required=False)
    draft = BooleanWithDefault(dump_default=None, required=False)
    notes = StringWithDefaultV3(dump_default="", required=False)


class VideoSchemaV3(MavenSchemaV3):
    session_id = StringWithDefaultV3(dump_default="", required=False)
    member_token = StringWithDefaultV3(dump_default="", required=False)
    practitioner_token = StringWithDefaultV3(dump_default="", required=False)


class ProviderAppointmentSchemaV3(MavenSchemaV3):
    id = IntegerWithDefaultV3(dump_default=0, required=True)
    appointment_id = IntegerWithDefaultV3(dump_default=0, required=True)
    scheduled_start = MavenDateTimeV3(required=True)
    scheduled_end = MavenDateTimeV3(required=False)
    cancelled_at = MavenDateTimeV3(required=False)
    cancellation_policy = StringWithDefaultV3(dump_default="", required=False)
    cancelled_note = StringWithDefaultV3(dump_default="", required=False)
    member_started_at = MavenDateTimeV3(required=False)
    member_ended_at = MavenDateTimeV3(required=False)
    member_disconnected_at = MavenDateTimeV3(required=False)
    practitioner_started_at = MavenDateTimeV3(required=False)
    practitioner_ended_at = MavenDateTimeV3(required=False)
    practitioner_disconnected_at = MavenDateTimeV3(required=False)
    phone_call_at = MavenDateTimeV3(required=False)
    privacy = StringWithDefaultV3(dump_default="", required=False)
    privilege_type = StringWithDefaultV3(dump_default="", required=False)
    purpose = StringWithDefaultV3(dump_default="", required=False)
    state = StringWithDefaultV3(dump_default="", required=False)
    pre_session = fields.Nested(SessionMetaInfoSchemaV3, required=False)
    post_session = fields.Nested(SessionMetaInfoSchemaV3, required=False)
    need = fields.Nested(NeedSchemaV3, required=False)
    video = fields.Nested(VideoSchemaV3, required=False)
    product = fields.Nested(ProductSchemaV3, required=False)
    member = fields.Nested(MPracticeMemberSchemaV3, required=False)
    prescription_info = fields.Nested(PrescriptionInfoSchemaV3, required=False)
    rx_enabled = BooleanWithDefault(dump_default=False, required=False)
    rx_reason = StringWithDefaultV3(dump_default="", required=False)
    rx_written_via = StringWithDefaultV3(dump_default="", required=False)
    structured_internal_note = fields.Nested(
        StructuredInternalNoteSchemaV3, required=False
    )
    provider_addenda = fields.Nested(
        ProviderAddendaAndQuestionnaireSchemaV3, required=False
    )


class ProviderAppointmentForListSchemaV3(MavenSchemaV3):
    id = IntegerWithDefaultV3(dump_default=0, required=True)
    appointment_id = IntegerWithDefaultV3(dump_default=0, required=True)
    scheduled_start = MavenDateTimeV3(required=True)
    scheduled_end = MavenDateTimeV3(required=True)
    member = fields.Nested(MPracticeMemberSchemaV3, required=True)
    repeat_patient = fields.Boolean(required=False)
    state = StringWithDefaultV3(dump_default="", required=False)
    privacy = StringWithDefaultV3(dump_default="", required=False)
    privilege_type = StringWithDefaultV3(dump_default="", required=False)
    rescheduled_from_previous_appointment_time = MavenDateTimeV3(required=False)
    cancelled_at = MavenDateTimeV3(required=False)
    post_session = fields.Nested(SessionMetaInfoSchemaV3, required=False)


class GetProviderAppointmentsRequestSchemaV3(PaginableArgsSchemaV3):
    scheduled_start = MavenDateTimeV3(required=False)
    scheduled_end = MavenDateTimeV3(required=False)
    practitioner_id = fields.Integer(required=False)
    member_id = fields.Integer(required=False)
    schedule_event_ids = CSVIntegerField(required=False)
    exclude_statuses = CSVStringField(required=False)


class GetProviderAppointmentsResponseSchemaV3(PaginableOutputSchemaV3):
    data = fields.Nested(ProviderAppointmentForListSchemaV3, many=True, required=True)  # type: ignore[assignment] # Incompatible types in assignment (expression has type "Nested", base class "PaginableOutputSchemaV3" defined the type as "Raw")


class GetProviderAppointmentRequestSchemaV3(MavenSchemaV3):
    include_soft_deleted_question_sets = BooleanWithDefault(
        default=False, required=False
    )
