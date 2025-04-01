from __future__ import annotations

import ddtrace.ext

from providers.domain.model import Provider
from storage.connection import db

__all__ = ("ProviderRepository",)


trace_wrapper = ddtrace.tracer.wrap(
    span_type=ddtrace.ext.SpanTypes.SQL,
)


class ProviderRepository:
    """A repository for managing user data from the downstream storage backend for our Provider model."""

    @trace_wrapper
    def get_by_user_id(self, user_id: int) -> Provider | None:
        return (
            db.session.query(Provider).filter(Provider.user_id == user_id).one_or_none()
        )

    @trace_wrapper
    def get_by_user_ids(self, provider_ids: list[int]) -> list[Provider]:
        return (
            db.session.query(Provider).filter(Provider.user_id.in_(provider_ids)).all()
        )
