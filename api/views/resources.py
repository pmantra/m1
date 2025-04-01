from typing import Any, Dict, List

import marshmallow
from flask import request
from httpproblem import Problem
from marshmallow import ValidationError
from sqlalchemy import func, orm

from common.services import api
from learn.services import article_thumbnail_service, article_title_service
from learn.utils.resource_utils import populate_estimated_read_times_and_media_types
from models import marketing
from views.schemas import common_v3


class ResourceGetSchema(common_v3.PaginableArgsSchemaV3, common_v3.ImageSizesMixin):
    content_types = common_v3.CSVStringField(
        default=[ct.name for ct in marketing.LibraryContentTypes]
    )
    tags = common_v3.CSVStringField()
    slugs = common_v3.CSVStringField(max_size=104)  # 2 per week


class ResourceSchema(marshmallow.Schema, common_v3.ImageSchemaMixin):
    assessment_id = marshmallow.fields.Integer(default=None)
    resource_id = marshmallow.fields.Function(lambda obj: obj.id)
    content_type = marshmallow.fields.String()
    title = marshmallow.fields.String()
    description = marshmallow.fields.String(default=None)
    slug = marshmallow.fields.String()
    type = marshmallow.fields.Function(lambda obj: obj.article_type)
    estimated_read_time_minutes = marshmallow.fields.Integer(default=None)
    media_type = marshmallow.fields.Function(lambda obj: obj.media_type)


class ResourcesResource(api.AuthenticatedResource):
    def get(self) -> List[Dict[str, Any]]:
        try:
            data: Dict[str, Any] = ResourceGetSchema().load(request.args)
        except ValidationError as validation_error:
            raise Problem(400, validation_error.messages)
        tags = data.get("tags")
        slugs = data.get("slugs")

        query = marketing.Resource.query.options(
            orm.joinedload(marketing.Resource.tags),
            orm.joinedload(marketing.Resource.image),
        ).filter(
            marketing.Resource.published_at < func.now(),
            marketing.Resource.resource_type == marketing.ResourceTypes.ENTERPRISE.name,
        )

        if tags:
            query = query.filter(
                marketing.Resource.tags.any(marketing.Tag.name.in_(tags))  # type: ignore[attr-defined] # "str" has no attribute "in_"
            )
        if slugs:
            query = query.filter(marketing.Resource.slug.in_(slugs))
        if data.get("order_direction") == "asc":
            query = query.order_by(marketing.Resource.published_at.asc())
        else:
            query = query.order_by(marketing.Resource.published_at.desc())
        if "offset" in data:
            query = query.offset(data["offset"])
        # Default limit is 10 (from PaginableArgsSchema)
        if "limit" in data:
            query = query.limit(data["limit"])

        resources = query.all()

        resources = populate_estimated_read_times_and_media_types(resources)

        title_service = article_title_service.LocalizedArticleTitleService()
        title_service.populate_remote_resource_titles(resources)

        thumb_service = article_thumbnail_service.ArticleThumbnailService()
        resources_with_thumbnails = thumb_service.get_thumbnails_for_resources(
            resources
        )

        resp = [
            ResourceSchema(context={"image_sizes": data.get("image_sizes", [])}).dump(
                resource
            )
            for resource in resources_with_thumbnails
        ]
        return resp
