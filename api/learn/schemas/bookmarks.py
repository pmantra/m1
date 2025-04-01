from marshmallow import Schema, fields

from views import library


class SavedResourcesSchema(Schema):
    saved_resources = fields.List(fields.Nested(library.ArticleResourceSchema))
