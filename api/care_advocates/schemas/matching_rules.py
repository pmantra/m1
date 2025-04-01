from marshmallow import Schema, ValidationError, fields, validates_schema

from care_advocates.models.matching_rules import MatchingRuleType


class MatchingRuleSchema(Schema):
    id = fields.Integer(required=False)
    entity = fields.Method("get_matching_rule_entity")
    type = fields.Method("get_matching_rule_type")
    all = fields.Boolean(required=True)
    identifiers = fields.List(fields.String())

    def get_matching_rule_entity(self, obj):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        return obj.entity.value

    def get_matching_rule_type(self, obj):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        return obj.type.value


class MatchingRuleUpdateSchema(Schema):
    id = fields.Integer(required=False)
    entity = fields.String(required=True)
    type = fields.String(required=True)
    all = fields.Boolean(required=True)
    identifiers = fields.List(fields.String(), required=True)

    @validates_schema
    def validate_all(self, data, **kwargs):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        type_ = data.get("type")
        if type_ not in [e.value for e in MatchingRuleType]:
            raise ValidationError("Not a valid matching rule type")


class MatchingRuleCreateSchema(MatchingRuleSchema):
    entity = fields.String(required=True)  # type: ignore[assignment] # Incompatible types in assignment (expression has type "String", base class "MatchingRuleSchema" defined the type as "Method")
    type = fields.String(required=True)  # type: ignore[assignment] # Incompatible types in assignment (expression has type "String", base class "MatchingRuleSchema" defined the type as "Method")

    @validates_schema
    def validate_all(self, data, **kwargs):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        all_ = data.get("all") or False
        identifiers = data.get("identifiers") or []
        if all_ and any(identifiers):
            raise ValidationError(
                "Having `all` set to `true` cannot be combined with `identifiers`"
            )


class AssignableAdvocateMatchingRuleSchema(Schema):
    id = fields.Integer()
    matching_rules = fields.List(fields.Nested(MatchingRuleSchema))


class AssignableAdvocateMatchingRuleCreateSchema(Schema):
    id = fields.Integer()
    matching_rules = fields.List(fields.Nested(MatchingRuleCreateSchema))


class AssignableAdvocateMatchingRuleUpdateSchema(Schema):
    matching_rules = fields.List(fields.Nested(MatchingRuleUpdateSchema))
