from __future__ import annotations

import functools

import ddtrace
import sqlalchemy

from models.tracks import MemberTrack
from storage.repository import base

__all__ = ("MemberTrackRepository",)

trace_wrapper = ddtrace.tracer.wrap(span_type=ddtrace.ext.SpanTypes.SQL)


class MemberTrackRepository(base.BaseRepository[MemberTrack]):
    model = MemberTrack

    @classmethod
    @functools.lru_cache(maxsize=1)
    def make_table(cls) -> sqlalchemy.Table:
        return cls.model.__table__

    @classmethod
    def table_name(cls) -> str:
        return cls.model.__tablename__

    @staticmethod
    def table_columns() -> tuple[sqlalchemy.Column, ...]:
        # This function is only used during BaseRepository.make_table,
        # which is being overriden here, so there is no need implement table_columns()
        return ()

    @trace_wrapper
    def get_by_user_id(self, *, user_id: int) -> list[MemberTrack] | None:
        if user_id is None:
            return None

        return (
            self.session.query(MemberTrack).filter(MemberTrack.user_id == user_id).all()
        )

    @trace_wrapper
    def get_active_tracks(self, *, user_id: int) -> list[MemberTrack] | None:
        if not user_id:
            return  # type: ignore[return-value] # Return value expected

        return (
            self.session.query(MemberTrack)
            .filter(MemberTrack.user_id == user_id, MemberTrack.active.is_(True))
            .all()
        )

    @trace_wrapper
    def get_inactive_tracks(self, *, user_id: int) -> list[MemberTrack] | None:
        if not user_id:
            return  # type: ignore[return-value] # Return value expected

        return (
            self.session.query(MemberTrack)
            .filter(MemberTrack.user_id == user_id, MemberTrack.inactive.is_(True))
            .all()
        )

    @trace_wrapper
    def get_scheduled_tracks(self, *, user_id: int) -> list[MemberTrack] | None:
        if not user_id:
            return  # type: ignore[return-value] # Return value expected

        return (
            self.session.query(MemberTrack)
            .filter(MemberTrack.user_id == user_id, MemberTrack.scheduled.is_(True))
            .all()
        )
