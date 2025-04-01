import marshmallow


class TopicSchema(marshmallow.Schema):
    id = marshmallow.fields.String(required=True)
    title = marshmallow.fields.String(required=True)
    slug = marshmallow.fields.String(required=True)
