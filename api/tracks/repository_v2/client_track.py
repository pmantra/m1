from dataclasses import dataclass
from typing import List

from sqlalchemy.orm.scoping import ScopedSession

from tracks.utils import query_utils
from utils.log import logger

from .errors import MissingQueryError, QueryNotFoundError

log = logger(__name__)


@dataclass
class AvailableClientTrackData:
    id: int
    name: str
    active: bool


class ClientTrackRepository:
    def __init__(self, session: ScopedSession):
        self.session = session
        queries = query_utils.load_queries_from_directory(
            "tracks/repository_v2/queries/"
        )

        if len(queries) == 0:
            raise QueryNotFoundError()
        if len(queries) < 1:
            raise MissingQueryError()

        available_client_tracks = queries.get("get_available_tracks")
        if available_client_tracks:
            self._get_available_tracks = available_client_tracks[0]

    def get_all_available_tracks(
        self, user_id: int, client_track_ids: List[int], organization_ids: List[int]
    ) -> List[AvailableClientTrackData]:
        """
        Get the tracks that are currently available for a user who is enrolled under a specific org list.
        (excludes active enrolled tracks)
        """
        query = self._get_available_tracks
        result = self.session.execute(
            query,
            {
                "user_id": user_id,
                "client_track_ids": client_track_ids,
                "organization_ids": organization_ids,
            },
        ).fetchall()
        result = self.deserialize_list(AvailableClientTrackData, result)
        return result

    @classmethod
    def deserialize_list(cls, data_class, rows) -> list:  # type: ignore[no-untyped-def] # Function is missing a type annotation for one or more arguments
        if rows is None:
            return []

        result = []
        for row in rows:
            row_dict = dict(row.items())

            result.append(data_class(**row_dict))

        return result
