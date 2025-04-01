import marshmallow as marshmallow

from learn.schemas.article import ImageSchema


class AccordionItemSchema(marshmallow.Schema):
    title = marshmallow.fields.String(required=True)
    rich_text = marshmallow.fields.Raw(required=True)


class AccordionSchema(marshmallow.Schema):
    id = marshmallow.fields.String(required=True)
    entry_type = marshmallow.fields.String(required=True)
    heading_level = marshmallow.fields.String(required=True)
    items = marshmallow.fields.Nested(AccordionItemSchema(many=True), required=True)


class CalloutSchema(marshmallow.Schema):
    id = marshmallow.fields.String(required=True)
    entry_type = marshmallow.fields.String(required=True)
    rich_text = marshmallow.fields.Raw(required=True)  # nested JSON


class EmbeddedImageSchema(marshmallow.Schema):
    id = marshmallow.fields.String(required=True)
    entry_type = marshmallow.fields.String(required=True)
    image = marshmallow.fields.Nested(ImageSchema(many=False))
    caption = marshmallow.fields.Raw(required=False)  # nested JSON


class EmbeddedVideoSchema(marshmallow.Schema):
    id = marshmallow.fields.String(required=True)
    entry_type = marshmallow.fields.String(required=True)
    video_link = marshmallow.fields.String(required=True)
    thumbnail = marshmallow.fields.Nested(ImageSchema(many=False))
    captions_link = marshmallow.fields.String(required=True)
