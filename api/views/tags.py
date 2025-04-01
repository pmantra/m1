from __future__ import annotations

import datetime

from flask import request
from sqlalchemy.sql.expression import false

from common.services.api import AuthenticatedResource
from models.marketing import Resource, ResourceContentTypes, Tag
from storage.connection import db
from utils.log import logger
from views.schemas.base import MavenSchemaV3, OrderDirectionFieldV3

log = logger(__name__)


class TagsGetSchema(MavenSchemaV3):
    order_direction = OrderDirectionFieldV3(
        load_default="desc", dump_default="desc", required=False
    )


class TagsResource(AuthenticatedResource):
    def get(self) -> list[dict]:
        schema = TagsGetSchema()
        if schema.load(request.args)["order_direction"] == "desc":
            order_by = Tag.modified_at.desc()
        else:
            order_by = Tag.modified_at.asc()
        # TODO: [multitrack] Allow clients to ask for a particular track's tags
        member_track = self.user.current_member_track
        if member_track:
            resource_track_filter = member_track.allowed_resources_query()
        else:
            # List no tags associated with resources.
            resource_track_filter = false()
        tags = (
            db.session.query(Tag)
            .join(Tag.resources, isouter=True)
            .filter(
                (Resource.content_type != ResourceContentTypes.on_demand_class.name)
                & resource_track_filter
                & (Resource.published_at <= datetime.datetime.utcnow())
            )
            .order_by(order_by)
            .all()
        )
        return format_tag_response(tags)


def format_tag_response(tags: list[Tag]) -> list[dict]:
    return [
        {"id": tag.id, "name": tag.name, "display_name": tag.display_name}
        for tag in tags
    ]
