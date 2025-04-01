from __future__ import annotations

import functools
from typing import List, Optional

import ddtrace.ext
import sqlalchemy as sa
import sqlalchemy.orm

from appointments.utils import query_utils
from clinical_documentation.models.mpractice_template import MPracticeTemplate
from mpractice.error import MissingQueryError, QueryNotFoundError
from storage.repository.base import BaseRepository

__all__ = ("MPracticeTemplateRepository",)


trace_wrapper = ddtrace.tracer.wrap(
    span_type=ddtrace.ext.SpanTypes.SQL,
)

MPRACTICE_TABLE_NAME = "mpractice_template"


class MPracticeTemplateRepository(BaseRepository[MPracticeTemplate]):
    model = MPracticeTemplate

    def __init__(
        self,
        session: sqlalchemy.orm.scoping.ScopedSession = None,  # type: ignore[assignment] # Incompatible default for argument "session" (default has type "None", argument has type "scoped_session")
        is_in_uow: bool = False,
    ):
        super().__init__(session=session, is_in_uow=is_in_uow)
        queries = query_utils.load_queries_from_file(
            "clinical_documentation/repository/queries/mpractice_template.sql"
        )
        if len(queries) == 0:
            raise QueryNotFoundError()
        if len(queries) != 9:
            raise MissingQueryError()
        self._get_mpractice_template_by_id = queries[0]
        self._get_mpractice_templates_by_owner = queries[1]
        self._get_mpractice_templates_by_title = queries[2]
        self._create_mpractice_template = queries[3]
        self._delete_mpractice_template_by_id = queries[4]
        self._edit_mpractice_template_title_and_text = queries[5]
        self._edit_mpractice_template_title = queries[6]
        self._edit_mpractice_template_text = queries[7]
        self._edit_mpractice_template = queries[8]

    def get(self, id: int) -> MPracticeTemplate | None:
        row = self.session.execute(
            self._get_mpractice_template_by_id,
            {"id": id},
        ).first()
        if row is None:
            return None
        return self.deserialize(row)

    def get_mpractice_templates_by_owner(
        self, owner_id: int
    ) -> List[MPracticeTemplate]:
        rows = self.session.execute(
            self._get_mpractice_templates_by_owner,
            {"owner_id": owner_id},
        ).fetchall()
        if rows is None:
            return []
        return [self.deserialize(row) for row in rows]

    def get_mpractice_templates_by_title(
        self, owner_id: int, title: str
    ) -> MPracticeTemplate | None:
        row = self.session.execute(
            self._get_mpractice_templates_by_title,
            {"owner_id": owner_id, "title": title},
        ).first()
        if row is None:
            return None
        return self.deserialize(row)

    def create_mpractice_template(
        self, owner_id: int, sort_order: int, is_global: bool, title: str, text: str
    ) -> MPracticeTemplate | None:
        result = self.session.execute(
            sa.text(self._create_mpractice_template),
            {
                "owner_id": owner_id,
                "sort_order": sort_order,
                "is_global": is_global,
                "title": title,
                "text": text,
            },
        )

        pk: int = result.lastrowid
        return self.affected_or_instance(affected=1, id=pk, fetch=True)

    def edit_mpractice_template_by_id(
        self,
        template_id: int,
        owner_id: int,
        title: Optional[str],
        text: Optional[str],
        # sort_order: Optional[int],
        # is_global: Optional[bool],
    ) -> MPracticeTemplate | None:
        if owner_id is None:
            return None

        if title is None and text is None:
            return self.get(id=template_id)

        if title is not None and text is not None:
            self.session.execute(
                sa.text(self._edit_mpractice_template_title_and_text),
                {
                    "template_id": template_id,
                    "owner_id": owner_id,
                    "title": title,
                    "text": text,
                },
            )

        if title is not None:
            self.session.execute(
                sa.text(self._edit_mpractice_template_title),
                {"template_id": template_id, "owner_id": owner_id, "title": title},
            )

        if text is not None:
            self.session.execute(
                sa.text(self._edit_mpractice_template_text),
                {"template_id": template_id, "owner_id": owner_id, "text": text},
            )

        # todo: in the future, dynamically create the query
        # params = { "template_id": template_id, "owner_id": owner_id }
        # if sort_order is not None:
        #     params["sort_order"] = sort_order
        #
        # if is_global is not None:
        #     params["is_global"] = is_global
        #
        # if text is not None:
        #     params["text"] = text
        #
        # if title is not None:
        #     params["title"] = title
        #
        # row = self.session.execute(
        #     self._edit_mpractice_template_by_id, params
        # ).first()

        return self.affected_or_instance(affected=1, id=template_id, fetch=True)

    def delete_mpractice_template_by_id(self, template_id: int, owner_id: int) -> bool:
        result = self.session.execute(
            sa.text(self._delete_mpractice_template_by_id),
            {"owner_id": owner_id, "template_id": template_id},
        )
        affected: int = result.rowcount
        return affected > 0

    @classmethod
    @functools.lru_cache(maxsize=1)
    def table_name(cls) -> str:
        return MPRACTICE_TABLE_NAME

    @classmethod
    def table_columns(cls) -> tuple[sqlalchemy.Column, ...]:
        return (
            sa.Column("id", sa.Integer, nullable=False),
            sa.Column("owner_id", sa.Integer, nullable=False),
            sa.Column("sort_order", sa.Integer, nullable=False),
            sa.Column("text", sa.String, nullable=False),
            sa.Column("title", sa.String, nullable=False),
            sa.Column("is_global", sa.Boolean, nullable=False),
            sa.Column("created_at", sa.DateTime, nullable=False),
            sa.Column("modified_at", sa.DateTime, nullable=True),
        )
