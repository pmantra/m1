import marshmallow as marshmallow
from help.schemas.article import ImageSchema


class AccordionItemSchema(marshmallow.Schema):
    title = marshmallow.fields.String(required=True)
    rich_text = marshmallow.fields.Raw(required=True)


class AccordionSchema(marshmallow.Schema):
    id = marshmallow.fields.String(required=True)
    entry_type = marshmallow.fields.String(required=True)
    heading_level = marshmallow.fields.String(required=True)
    items = marshmallow.fields.Nested(AccordionItemSchema(many=True), required=True)


class EmbeddedImageSchema(marshmallow.Schema):
    id = marshmallow.fields.String(required=True)
    entry_type = marshmallow.fields.String(required=True)
    image = marshmallow.fields.Nested(ImageSchema(many=False))
    caption = marshmallow.fields.Raw(required=False)  # nested JSON
