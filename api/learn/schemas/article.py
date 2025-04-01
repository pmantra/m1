import marshmallow

from learn.models import article_type
from views.schemas import banner


class ImageSchema(marshmallow.Schema):
    url = marshmallow.fields.String(required=True)
    description = marshmallow.fields.String()


class RelatedReadSchema(marshmallow.Schema):
    title = marshmallow.fields.String(required=True)
    thumbnail = marshmallow.fields.Nested(ImageSchema(many=False))
    slug = marshmallow.fields.String(required=True)
    type = marshmallow.fields.String(
        validate=marshmallow.validate.OneOf(
            [type.value for type in article_type.ArticleType]
        )
    )


class MedicallyReviewedSchema(marshmallow.Schema):
    reviewers = marshmallow.fields.String()


class ArticleSchema(marshmallow.Schema):
    id = marshmallow.fields.String()  # May be null if this is a preview
    content_type = marshmallow.fields.String()  # May be null if this is a preview
    title = marshmallow.fields.String(required=True)
    medically_reviewed = marshmallow.fields.Nested(MedicallyReviewedSchema)
    hero_image = marshmallow.fields.Nested(ImageSchema, required=True)
    rich_text = marshmallow.fields.Dict(required=True)
    related_reads = marshmallow.fields.Nested(RelatedReadSchema(many=True))
    rich_text_includes = marshmallow.fields.List(marshmallow.fields.Dict)
    type = marshmallow.fields.String(
        validate=marshmallow.validate.OneOf(
            [type.value for type in article_type.ArticleType]
        ),
        required=True,
    )
    disclaimer = marshmallow.fields.String(required=True)
    saved = marshmallow.fields.Boolean()
    banner = marshmallow.fields.Nested(banner.Banner)
