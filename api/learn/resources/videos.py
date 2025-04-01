import dataclasses
from typing import Any

from flask.globals import request
from httpproblem import Problem
from marshmallow.exceptions import ValidationError

from common.services import api
from learn.services.video_service import VideoService
from views.schemas import common_v3
from views.schemas.base import MavenSchemaV3


class VideoseGetSchema(MavenSchemaV3):
    slugs = common_v3.CSVStringField(max_size=52, required=True)  # 1 per week


class VideosResource(api.EnterpriseResource):
    def get(self) -> dict[str, list[dict[str, Any]]]:
        self._user_is_enterprise_else_403()

        try:
            data = VideoseGetSchema().load(request.args)
        except ValidationError as validation_error:
            raise Problem(400, validation_error.messages)
        slugs = data.get("slugs")

        video_service = VideoService()
        videos = video_service.get_values(identifier_values=slugs)
        return {"videos": [dataclasses.asdict(video) for slug, video in videos.items()]}
