import marshmallow

from learn.models.article_type import ArticleType


class ImageSchema(marshmallow.Schema):
    url = marshmallow.fields.String(required=True)
    description = marshmallow.fields.String()


class ArticleSchema(marshmallow.Schema):
    id = marshmallow.fields.String()  # May be null if this is a preview
    content_type = marshmallow.fields.String()  # May be null if this is a preview
    title = marshmallow.fields.String(required=True)
    rich_text = marshmallow.fields.Dict(required=True)
    rich_text_includes = marshmallow.fields.List(marshmallow.fields.Dict, required=True)
    type = marshmallow.fields.String(
        validate=marshmallow.validate.Equal(ArticleType.RICH_TEXT.value),
        required=True,
    )
