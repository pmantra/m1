from marshmallow_v1 import fields

from views.schemas.common import (
    PaginableOutputSchema,
    RestrictedString,
    RestrictedUSOrganizationSchema,
    UserSchema,
)
from views.schemas.common_v3 import (
    IntegerWithDefaultV3,
    NestedWithDefaultV3,
    PaginableOutputSchemaV3,
    RestrictedStringV3,
    RestrictedUSOrganizationSchemaV3,
    UserSchemaV3,
)


class MemberSearchResultSchema(RestrictedUSOrganizationSchema):
    id = fields.Integer()
    first_name = RestrictedString(default=None)  # type: ignore[arg-type] # Argument "default" to "RestrictedString" has incompatible type "None"; expected "str"
    last_name = RestrictedString(default=None)  # type: ignore[arg-type] # Argument "default" to "RestrictedString" has incompatible type "None"; expected "str"
    email = RestrictedString(default=None)  # type: ignore[arg-type] # Argument "default" to "RestrictedString" has incompatible type "None"; expected "str"
    care_coordinators = fields.Nested(
        UserSchema, only=("first_name", "last_name"), many=True
    )


class MemberSearchResultSchemaV3(RestrictedUSOrganizationSchemaV3):
    id = IntegerWithDefaultV3()
    first_name = RestrictedStringV3(default=None)  # type: ignore[arg-type] # Argument "default" to "RestrictedString" has incompatible type "None"; expected "str"
    last_name = RestrictedStringV3(default=None)  # type: ignore[arg-type] # Argument "default" to "RestrictedString" has incompatible type "None"; expected "str"
    email = RestrictedStringV3(default=None)  # type: ignore[arg-type] # Argument "default" to "RestrictedString" has incompatible type "None"; expected "str"
    care_coordinators = NestedWithDefaultV3(
        UserSchemaV3, only=("first_name", "last_name"), many=True, default=[]
    )


class MemberSearchResultsSchema(PaginableOutputSchema):
    data = fields.Nested(MemberSearchResultSchema, many=True)  # type: ignore[assignment] # Incompatible types in assignment (expression has type "Nested", base class "PaginableOutputSchema" defined the type as "Raw")


class MemberSearchResultsSchemaV3(PaginableOutputSchemaV3):
    data = NestedWithDefaultV3(MemberSearchResultSchemaV3, many=True, default=[])  # type: ignore[assignment] # Incompatible types in assignment (expression has type "Nested", base class "PaginableOutputSchema" defined the type as "Raw")
