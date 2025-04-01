from __future__ import annotations

from marshmallow import fields, missing

from views.schemas.base import (
    BooleanWithDefault,
    IntegerWithDefaultV3,
    MavenSchemaV3,
    NestedWithDefaultV3,
    PaginableArgsSchemaV3,
    PaginableOutputSchemaV3,
    StringWithDefaultV3,
)


class BookingFlowSearchGetSchemaV3(PaginableArgsSchemaV3):
    query = StringWithDefaultV3(load_default="", dump_default="")
    is_common = BooleanWithDefault(load_default=False, dump_default=False)


class VerticalLiteSchemaV3(MavenSchemaV3):
    """A lightweight version of VerticalSchema for booking flow search"""

    id = fields.Integer()
    name = fields.String()
    can_prescribe = fields.Boolean()
    description = fields.String()


class SpecialtyKeywordLiteSchemaV3(MavenSchemaV3):
    """A lightweight SpecialtyKeyword Schema for booking flow search"""

    name = fields.String()
    specialty_ids = fields.Method("get_specialty_ids")

    @staticmethod
    def get_specialty_ids(obj):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        if isinstance(obj, dict):
            if "specialties" in obj:
                return [s["id"] for s in obj["specialties"]]
            else:
                return missing
        return [s.id for s in obj.specialties]


class SpecialtyLiteSchemaV3(MavenSchemaV3):
    """A lightweight version of SpecialtySchema for booking flow search"""

    id = fields.Integer()
    name = fields.String()


class NeedLiteSchemaV3(MavenSchemaV3):
    """A lightweight Need Schema for booking flow search"""

    id = IntegerWithDefaultV3(default=0)
    name = StringWithDefaultV3(default="")
    description = StringWithDefaultV3(default="")


class NeedCategoryLiteSchemaV3(MavenSchemaV3):
    """A lightweight NeedCategory Schema for booking flow search"""

    id = fields.Integer()
    name = fields.String()


class PractitionerLiteSchemaV3(MavenSchemaV3):
    """A lightweight PractitionerLite Schema for booking flow search"""

    name = fields.String(attribute="full_name")
    id = fields.Integer()


class BookingFlowSearchDataSchemaV3(MavenSchemaV3):
    verticals = NestedWithDefaultV3(VerticalLiteSchemaV3, many=True, dump_default=[])
    specialties = NestedWithDefaultV3(SpecialtyLiteSchemaV3, many=True, dump_default=[])
    keywords = NestedWithDefaultV3(
        SpecialtyKeywordLiteSchemaV3, many=True, dump_default=[]
    )
    practitioners = NestedWithDefaultV3(
        PractitionerLiteSchemaV3, many=True, dump_default=[]
    )
    needs = NestedWithDefaultV3(NeedLiteSchemaV3, many=True, dump_default=[])
    need_categories = NestedWithDefaultV3(
        NeedCategoryLiteSchemaV3, many=True, dump_default=[]
    )


class BookingFlowSearchSchemaV3(PaginableOutputSchemaV3):
    data = fields.Nested(BookingFlowSearchDataSchemaV3)  # type: ignore[assignment] # Incompatible types in assignment (expression has type "Nested", base class "PaginableOutputSchemaV3" defined the type as "RawWithDefaultV3")
