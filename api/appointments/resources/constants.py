from typing import TypedDict

from flask_restful import abort
from marshmallow_v1 import fields

from common.services.api import AuthenticatedResource
from views.schemas.common import MavenSchema


class PractitionerScheduleResource(AuthenticatedResource):
    def _check_practitioner(self, practitioner_id: int) -> None:
        if not practitioner_id == self.user.id:
            abort(403, message="You can only update your own schedule!")


class OverflowReportRequest(TypedDict):
    token: str
    report: str


class OverflowReportArgs(MavenSchema):
    token = fields.String(required=True)
    report = fields.String(required=True)

    class Meta:
        strict = True
