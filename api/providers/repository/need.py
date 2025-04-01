from __future__ import annotations

from typing import List

import sqlalchemy.orm

from providers.models.need import Need


class NeedRepository:
    def __init__(self, session: sqlalchemy.orm.scoping.ScopedSession):
        self.session = session

    def get_needs_by_ids(self, need_ids: list[int]) -> list[Need]:
        if not need_ids:
            return []

        query = """
            SELECT
                need.id,
                need.name,
                need.description,
                need.slug
            FROM
                need
            WHERE need.id in :need_ids
        """
        result = self.session.execute(query, {"need_ids": need_ids})
        rows = result.fetchall()
        return [Need(**row) for row in rows]

    def get_needs_by_slugs(self, need_slugs: list[str]) -> List[Need]:
        if not need_slugs:
            return []

        query = """
            SELECT
                need.id,
                need.slug,
                need.name,
                need.description
            FROM
                need
            WHERE need.slug in :need_slugs
        """
        result = self.session.execute(query, {"need_slugs": need_slugs})
        rows = result.fetchall()
        return [Need(**row) for row in rows]

    def add_slug_to_need(self, need_id: int, slug: str) -> int | None:
        if not need_id or not slug:
            return  # type: ignore[return-value] # Return value expected

        query = """
            UPDATE
                need
            SET
                need.slug = :slug
            WHERE need.id = :need_id
        """
        self.session.execute(query, {"need_id": need_id, "slug": slug})
        return need_id
