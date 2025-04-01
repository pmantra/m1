from dataclasses import dataclass

import sqlalchemy.orm

from appointments.utils import query_utils  # TODO this should be moved to common


@dataclass
class ProviderSchedulingConstraintsStruct:
    default_prep_buffer: int
    booking_buffer: int
    max_capacity: int
    daily_intro_capacity: int


class ProviderRepositoryV2:
    def __init__(self, session: sqlalchemy.orm.Session):
        self.session = session

        # Load queries
        queries = query_utils.load_queries_from_file(
            "providers/repository/v2/queries/provider.sql"
        )
        self._get_provider_scheduling_query = queries[0]
        self._is_member_matched_to_coach_with_specialty_query = queries[1]

    def get_scheduling_constraints(
        self, provider_id: int
    ) -> ProviderSchedulingConstraintsStruct:
        row = self.session.execute(
            self._get_provider_scheduling_query, {"provider_id": provider_id}
        ).fetchone()
        return ProviderSchedulingConstraintsStruct(**row)

    def is_member_matched_to_coach_with_specialty(
        self, member_id: int, specialty_slug: str
    ) -> bool:
        row = self.session.execute(
            self._is_member_matched_to_coach_with_specialty_query,
            {"member_id": member_id, "specialty_slug": specialty_slug},
        ).fetchone()
        return row[0]
