from marshmallow_v1 import fields

from appointments.schemas.appointments import MinimalAppointmentsSchema
from views.schemas.common import (
    CountrySchema,
    MavenDateTime,
    RestrictableMavenSchema,
    RestrictedString,
    UserMeActiveTrackSchema,
    UserSchema,
)


class MemberProfileDataSchema(RestrictableMavenSchema):
    id = fields.Integer()
    first_name = fields.String(default=None)  # type: ignore[arg-type] # Argument "default" to "String" has incompatible type "None"; expected "str"
    last_name = fields.String(default=None)  # type: ignore[arg-type] # Argument "default" to "String" has incompatible type "None"; expected "str"
    email = RestrictedString(default=None)  # type: ignore[arg-type] # Argument "default" to "RestrictedString" has incompatible type "None"; expected "str"
    country = fields.Nested(CountrySchema, only=("name", "abbr"))
    state = fields.Function(lambda obj: obj.state.abbreviation)
    image = fields.Function(lambda obj: obj.avatar_url)
    created_at = MavenDateTime(default=None)
    care_coordinators = fields.Nested(
        UserSchema, only=("first_name", "last_name"), many=True
    )
    active_tracks = fields.Nested(
        UserMeActiveTrackSchema,
        only=("name", "current_phase"),
        many=True,
    )
    phone_number = fields.String(default=None)  # type: ignore[arg-type] # Argument "default" to "String" has incompatible type "None"; expected "str"
    has_care_plan = fields.Boolean(default=False)
    care_plan_id = fields.Integer(default=None)  # type: ignore[arg-type] # Argument "default" to "Integer" has incompatible type "None"; expected "int"
    organization = fields.Method("_get_organization")

    def _restricted(self, attr, obj) -> bool:  # type: ignore[no-untyped-def] # Function is missing a type annotation for one or more arguments
        return not self.context["user"].is_care_coordinator

    def _get_organization(self, model, context):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        org = context["organization"]
        if org:
            return {
                "id": org.id,
                "name": org.name,
                "education_only": org.education_only,
                "rx_enabled": org.rx_enabled,
            }
        return None


class MemberProfileSummaryResultSchema(RestrictableMavenSchema):
    member_profile_data = fields.Nested(MemberProfileDataSchema)
    upcoming_appointment_data = fields.Nested(MinimalAppointmentsSchema, default={})
