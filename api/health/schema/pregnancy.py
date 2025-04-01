from marshmallow import fields

from views.schemas.base import MavenSchemaV3


class AlertSchema(MavenSchemaV3):
    type = fields.String(required=True)
    message = fields.String(required=True)


class ModifierSchema(MavenSchemaV3):
    id = fields.Integer(required=False)
    name = fields.String(required=False)
    role = fields.String(required=False)
    verticals = fields.List(fields.String(), required=False)


class ValueWithModifierAndUpdatedAtSchema(MavenSchemaV3):
    value = fields.String(required=True, allow_none=True)
    modifier = fields.Nested(ModifierSchema, required=True, allow_none=True)
    updated_at = fields.DateTime(required=True, allow_none=True)


class MemberConditionSchema(MavenSchemaV3):
    id = fields.String(required=False, allow_none=True)
    condition_type = fields.String(required=False, allow_none=True)
    status = fields.String(required=True, allow_none=False)
    onset_date = fields.Date(required=False, allow_none=True)
    abatement_date = fields.Date(required=False, allow_none=True)
    estimated_date = fields.Date(required=False, allow_none=True)
    is_first_occurrence = fields.Boolean(required=False, allow_none=True)
    method_of_conception = fields.Nested(
        ValueWithModifierAndUpdatedAtSchema, required=False, allow_none=True
    )
    outcome = fields.Nested(
        ValueWithModifierAndUpdatedAtSchema, required=False, allow_none=True
    )
    modifier = fields.Nested(ModifierSchema, required=True, allow_none=True)
    created_at = fields.DateTime(required=False, allow_none=True)
    updated_at = fields.DateTime(required=False, allow_none=True)


class PatchMemberConditionSchema(MavenSchemaV3):
    id = fields.String(required=False, allow_none=True)
    user_id = fields.Integer(required=False, allow_none=True)
    status = fields.String(required=False, allow_none=True)
    abatement_date = fields.Date(required=False, allow_none=True)
    estimated_date = fields.Date(required=False, allow_none=True)
    is_first_occurrence = fields.Boolean(required=False, allow_none=True)
    method_of_conception = fields.Nested(
        ValueWithModifierAndUpdatedAtSchema, required=False, allow_none=True
    )
    outcome = fields.Nested(
        ValueWithModifierAndUpdatedAtSchema, required=False, allow_none=True
    )
    modifier = fields.Nested(ModifierSchema, required=False, allow_none=True)
    updated_at = fields.DateTime(required=False, allow_none=True)


class PutPregnancyAndRelatedConditionsRequestSchema(MavenSchemaV3):
    pregnancy = fields.Nested(MemberConditionSchema, required=True, allow_none=False)
    related_conditions = fields.Method("get_related_conditions")

    def get_related_conditions(self, obj) -> dict:  # type: ignore[no-untyped-def] # Function is missing a type annotation
        return {
            key: MemberConditionSchema().dump(value)
            for (key, value) in obj.related_conditions.items()
        }


class PatchPregnancyAndRelatedConditionsRequestSchema(MavenSchemaV3):
    pregnancy = fields.Nested(
        PatchMemberConditionSchema, required=True, allow_none=False
    )
    related_conditions = fields.Method("get_related_conditions")

    def get_related_conditions(self, obj) -> dict:  # type: ignore[no-untyped-def] # Function is missing a type annotation
        return {
            key: PatchMemberConditionSchema().dump(value)
            for (key, value) in obj.related_conditions.items()
        }


class PregnancyAndRelatedConditionsSchema(MavenSchemaV3):
    pregnancy = fields.Nested(MemberConditionSchema, required=True)
    # Marshmallow native fields.Dict() does not handle nested schema well.
    # Using custom methods to process fields in dict type.
    related_conditions = fields.Method("get_related_conditions")
    alerts = fields.Method("get_alerts")

    def get_related_conditions(self, obj) -> dict:  # type: ignore[no-untyped-def] # Function is missing a type annotation
        return {
            key: MemberConditionSchema().dump(value)
            for (key, value) in obj.related_conditions.items()
        }

    def get_alerts(self, obj) -> dict:  # type: ignore[no-untyped-def] # Function is missing a type annotation
        return {key: AlertSchema().dump(value) for (key, value) in obj.alerts.items()}
