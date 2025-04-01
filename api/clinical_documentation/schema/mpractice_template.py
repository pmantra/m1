from marshmallow import Schema, fields

from views.schemas.base import (
    BooleanWithDefault,
    IntegerWithDefaultV3,
    MavenDateTimeV3,
    MavenSchemaV3,
    StringWithDefaultV3,
)
from views.schemas.common_v3 import OrderDirectionField


class MPracticeTemplateSchema(MavenSchemaV3):
    id = IntegerWithDefaultV3(dump_default=0, required=True)
    owner_id = IntegerWithDefaultV3(dump_default=0, required=True)
    is_global = BooleanWithDefault(dump_default=0, required=True)
    title = StringWithDefaultV3(dump_default="", required=True)
    text = StringWithDefaultV3(dump_default="", required=True)
    sort_order = IntegerWithDefaultV3(dump_default=0, required=True)
    created_at = MavenDateTimeV3(dump_default=None, required=False)
    modified_at = MavenDateTimeV3(dump_default=None, required=False)


class MPracticeTemplateLitePaginationSchema(Schema):
    total = fields.Integer(required=False)
    order_direction = OrderDirectionField(
        dump_default="desc", load_default="desc", required=False
    )


class GetMPracticeTemplatesResponseSchema(Schema):
    data = fields.List(fields.Nested(MPracticeTemplateSchema), required=True)
    pagination = fields.Nested(MPracticeTemplateLitePaginationSchema)


class GetMPracticeTemplateResponseSchema(MavenSchemaV3):
    data = fields.Nested(MPracticeTemplateSchema)


class PostMPracticeTemplateRequestSchema(MavenSchemaV3):
    is_global = BooleanWithDefault(dump_default=0, required=True)
    title = StringWithDefaultV3(dump_default="", required=True)
    text = StringWithDefaultV3(dump_default="", required=True)
    sort_order = IntegerWithDefaultV3(dump_default=0, required=True)


class PatchMPracticeTemplateRequestSchema(MavenSchemaV3):
    is_global = BooleanWithDefault(dump_default=0, required=False)
    title = StringWithDefaultV3(dump_default="", required=False)
    text = StringWithDefaultV3(dump_default="", required=False)
    sort_order = IntegerWithDefaultV3(dump_default=0, required=False)
