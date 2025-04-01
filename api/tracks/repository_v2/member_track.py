from dataclasses import dataclass
from datetime import date, datetime

from sqlalchemy.orm.scoping import ScopedSession

from models.tracks.client_track import TrackModifiers
from tracks.utils import query_utils

from .errors import MissingQueryError, QueryNotFoundError


@dataclass
class BaseMemberTrackData:
    id: int
    name: str
    anchor_date: date
    length_in_days: int


@dataclass
class ActiveMemberTrackData(BaseMemberTrackData):
    activated_at: datetime
    start_date: date
    org_id: int
    org_name: str
    org_vertical_group_version: str
    org_bms_enabled: bool
    org_rx_enabled: bool
    org_education_only: bool
    org_display_name: str
    track_modifiers: list[TrackModifiers]
    org_benefits_url: str


@dataclass
class InactiveMemberTrackData(BaseMemberTrackData):
    activated_at: datetime
    ended_at: datetime


@dataclass
class ScheduledMemberTrackData(BaseMemberTrackData):
    start_date: date


@dataclass
class EnrolledMemberTrackData(BaseMemberTrackData):
    activated_at: datetime
    start_date: date
    org_id: int
    org_name: str
    org_display_name: str
    is_active: bool


class MemberTrackRepository:
    def __init__(self, session: ScopedSession):
        self.session = session

        # Load queries
        queries = query_utils.load_queries_from_directory(
            "tracks/repository_v2/queries/"
        )
        if len(queries) == 0:
            raise QueryNotFoundError()
        if len(queries) < 1:
            raise MissingQueryError()

        active_member_tracks_queries = queries.get("get_active_member_tracks")
        if active_member_tracks_queries:
            self._get_active_member_tracks_query = active_member_tracks_queries[0]

        inactive_member_tracks_queries = queries.get("get_inactive_member_tracks")
        if inactive_member_tracks_queries:
            self._get_inactive_member_tracks_query = inactive_member_tracks_queries[0]

        scheduled_member_tracks_queries = queries.get("get_scheduled_member_tracks")
        if scheduled_member_tracks_queries:
            self._get_scheduled_member_tracks_query = scheduled_member_tracks_queries[0]

        all_enrolled_tracks_queries = queries.get("get_all_enrolled_tracks")
        if all_enrolled_tracks_queries:
            self._get_all_enrolled_tracks_query = all_enrolled_tracks_queries[0]

    def get_active_member_tracks(
        self,
        user_id: int,
    ) -> list[ActiveMemberTrackData]:
        query = self._get_active_member_tracks_query
        result = self.session.execute(query, {"user_id": user_id}).fetchall()
        return self.deserialize_list(ActiveMemberTrackData, result)

    def get_all_enrolled_tracks(
        self, user_id: int, active_only: bool = True
    ) -> list[EnrolledMemberTrackData]:
        query = self._get_all_enrolled_tracks_query
        result = self.session.execute(query, {"user_id": user_id}).fetchall()
        result = self.deserialize_list(EnrolledMemberTrackData, result)
        if active_only:
            result = [row for row in result if row.is_active]
        return result

    def get_inactive_member_tracks(
        self,
        user_id: int,
    ) -> list[InactiveMemberTrackData]:
        query = self._get_inactive_member_tracks_query
        result = self.session.execute(query, {"user_id": user_id}).fetchall()
        return self.deserialize_list(InactiveMemberTrackData, result)

    def get_scheduled_member_tracks(
        self,
        user_id: int,
    ) -> list[ScheduledMemberTrackData]:
        query = self._get_scheduled_member_tracks_query
        result = self.session.execute(query, {"user_id": user_id}).fetchall()
        return self.deserialize_list(ScheduledMemberTrackData, result)

    @classmethod
    def deserialize_list(cls, data_class, rows) -> list:  # type: ignore[no-untyped-def] # Function is missing a type annotation for one or more arguments
        if rows is None:
            return []

        result = []
        for row in rows:
            row_dict = dict(row.items())

            # track_modifiers is a comma separated array of strings
            if "track_modifiers" in row_dict:
                if row_dict["track_modifiers"]:
                    row_dict["track_modifiers"] = [
                        TrackModifiers(modifier.strip())
                        for modifier in row_dict["track_modifiers"].split(",")
                    ]
                else:
                    row_dict["track_modifiers"] = []
            result.append(data_class(**row_dict))

        return result
