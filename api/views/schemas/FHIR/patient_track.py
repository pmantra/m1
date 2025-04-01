from marshmallow import Schema, fields

from models.tracks import MemberTrack
from models.tracks.client_track import TrackModifiers


class MemberTrackSchema(Schema):
    id = fields.Integer()
    name = fields.String()
    display_name = fields.String()
    start_date = fields.Method("get_start_date")
    scheduled_end = fields.Method("get_scheduled_end")
    ended_at = fields.DateTime(format="iso")
    track_modifiers = fields.List(fields.Enum(enum=TrackModifiers, by_value=True))

    def get_scheduled_end(self, track: MemberTrack) -> str:
        return track.get_display_scheduled_end_date().isoformat()

    def get_start_date(self, track: MemberTrack) -> str:
        return track.created_at.isoformat()


class PatientTracksSchema(Schema):
    active_tracks = fields.Nested(
        MemberTrackSchema,
        only=[
            "id",
            "start_date",
            "scheduled_end",
            "name",
            "display_name",
            "track_modifiers",
        ],
        many=True,
    )
    inactive_tracks = fields.Nested(
        MemberTrackSchema,
        only=[
            "id",
            "start_date",
            "scheduled_end",
            "name",
            "ended_at",
            "display_name",
            "track_modifiers",
        ],
        many=True,
    )
