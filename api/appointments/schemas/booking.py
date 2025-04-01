from __future__ import annotations

from marshmallow import Schema as mSchema
from marshmallow import fields as mfields
from marshmallow_v1 import Schema, fields

from appointments.models.needs_and_categories import NeedCategory
from l10n.db_strings.translate import TranslateDBFields
from views.schemas.common import MavenSchema, PaginableArgsSchema, PaginableOutputSchema


class VerticalSchema(MavenSchema):
    id = fields.Integer()
    type = fields.Method("get_type")
    name = fields.String()
    pluralized_display_name = fields.String()
    description = fields.String()

    def get_type(self, obj, context):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        return "vertical"


class SpecialtyLiteSchema(Schema):
    """A lightweight version of SpecialtySchema for booking flow search"""

    id = fields.Integer()
    name = fields.String()


class VerticalLiteSchema(Schema):
    """A lightweight version of VerticalSchema for booking flow search"""

    id = fields.Integer()
    name = fields.String()
    can_prescribe = fields.Boolean()
    description = fields.String()


class SpecialtyKeywordLiteSchema(Schema):
    """A lightweight SpecialtyKeyword Schema for booking flow search"""

    name = fields.String()
    specialty_ids = fields.Method("get_specialty_ids")

    def get_specialty_ids(self, obj, context):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        return [s.id for s in obj.specialties]


class NeedLiteSchema(Schema):
    """A lightweight Need Schema for booking flow search"""

    id = fields.Integer()
    name = fields.String()
    description = fields.String()


class NeedCategoryLiteSchema(Schema):
    """A lightweight NeedCategory Schema for booking flow search"""

    id = fields.Integer()
    name = fields.String()


class PractitionerLiteSchema(Schema):
    """A lightweight PractitionerLite Schema for booking flow search"""

    name = fields.String(attribute="full_name")
    id = fields.Integer()


class BookingFlowSearchDataSchema(Schema):
    verticals = fields.Nested(VerticalLiteSchema, many=True)
    specialties = fields.Nested(SpecialtyLiteSchema, many=True)
    keywords = fields.Nested(SpecialtyKeywordLiteSchema, many=True)
    practitioners = fields.Nested(PractitionerLiteSchema, many=True)
    needs = fields.Nested(NeedLiteSchema, many=True)
    need_categories = fields.Nested(NeedCategoryLiteSchema, many=True)


class BookingFlowSearchSchema(PaginableOutputSchema):
    data = fields.Nested(BookingFlowSearchDataSchema)  # type: ignore[assignment] # Incompatible types in assignment (expression has type "Nested", base class "PaginableOutputSchema" defined the type as "Raw")


class BookingFlowSearchGetSchema(PaginableArgsSchema):
    query = fields.String()
    is_common = fields.Boolean(default=False)


class BookingFlowCategoriesLiteSchema(mSchema):
    id = mfields.Integer()
    name = mfields.Method("get_translated_name")
    image_id = mfields.Method("get_image_id")
    image_url = mfields.Method("get_image_url")

    def get_translated_name(self, obj: NeedCategory) -> str:
        l10n_flag = self.context.get("l10n_flag", False)
        if l10n_flag:
            assert obj.slug
            return TranslateDBFields().get_translated_need_category(
                obj.slug, "name", default=obj.name
            )
        else:
            return obj.name

    def get_image_id(self, obj):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        return obj.image_id_or_default

    def get_image_url(self, obj):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        return obj.image_url(attr_name="image_id_or_default")


class BookingFlowCategoriesGetDataSchema(mSchema):
    categories = mfields.Nested(BookingFlowCategoriesLiteSchema, many=True)


class BookingFlowCategoriesGetSchema(mSchema):
    data = mfields.Nested(BookingFlowCategoriesGetDataSchema)
