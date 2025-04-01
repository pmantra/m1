from marshmallow_v1 import fields

from data_admin.maker_base import _MakerBase
from models.tracks.member_track import TrackChangeReason
from storage.connection import db
from views.schemas.common import MavenSchema


class TrackChangeReasonSchema(MavenSchema):
    name = fields.String()
    display_name = fields.String()
    description = fields.String(null=True)


class TrackChangeReasonMaker(_MakerBase):
    spec_class = TrackChangeReasonSchema(strict=True)  # type: ignore[assignment] # Incompatible types in assignment (expression has type "TrackChangeReasonSchema", base class "_MakerBase" defined the type as "None")

    def create_object(self, spec):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        spec_data = self.spec_class.load(spec).data  # type: ignore[has-type] # Cannot determine type of "spec_class"
        track_change_reason = TrackChangeReason(
            name=spec_data.get("name"),
            display_name=spec_data.get("display_name"),
            description=spec_data.get("description"),
        )

        db.session.add(track_change_reason)

        return track_change_reason
