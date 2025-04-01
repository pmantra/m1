from __future__ import annotations

import functools
from datetime import datetime

import ddtrace.ext
import sqlalchemy as sa
import sqlalchemy.orm
import sqlalchemy.util

from authn.domain import model
from storage.repository import base

__all__ = ("UserAuthRepository",)


trace_wrapper = ddtrace.tracer.wrap(
    span_type=ddtrace.ext.SpanTypes.SQL,
)


class UserAuthRepository(base.BaseRepository[model.UserAuth]):  # type: ignore[type-var] # Type argument "UserAuth" of "BaseRepository" must be a subtype of "Instance"
    """A repository for managing user auth objects."""

    model = model.UserAuth

    @trace_wrapper
    def get_by_user_id(self, *, user_id: int) -> model:  # type: ignore[valid-type] # Variable "authn.domain.repository.user_auth.UserAuthRepository.model" is not valid as a type
        """Get an individual user auth by its user ID."""

        where = self.table.c.user_id == user_id
        result = self.execute_select(where=where)
        row = result.first()
        return self.deserialize(row)

    @trace_wrapper
    def get_all_by_time_range(self, *, end: datetime.date, start: datetime.date | None = None) -> list[model]:  # type: ignore[valid-type] # Variable "authn.domain.repository.user_auth.UserAuthRepository.model" is not valid as a type
        """Get a list of user auth by the modified time range"""

        if start:
            where_clauses = [
                self.table.c.modified_at <= end,
                self.table.c.modified_at >= start,
            ]
        else:
            where_clauses = [
                self.table.c.modified_at <= end,
            ]
        result = self.execute_select(where=sa.and_(*where_clauses))
        rows = result.fetchall()
        return self.deserialize_list(rows=rows)  # type: ignore[arg-type] # Argument 1 to "deserialize_list" of "BaseRepository" has incompatible type "List[RowProxy]"; expected "Optional[List[Mapping[str, Any]]]"

    @trace_wrapper
    def get_by_external_id(self, *, external_id: str) -> model:  # type: ignore[valid-type] # Variable "authn.domain.repository.user_auth.UserAuthRepository.model" is not valid as a type
        """Get an individual user auth by its external ID."""

        where = self.table.c.external_id == external_id
        result = self.execute_select(where=where)
        row = result.first()
        return self.deserialize(row)

    @trace_wrapper
    def get_all_without_user_auth_external_id(
        self, limit: int = None, offset: int = None  # type: ignore[assignment] # Incompatible default for argument "limit" (default has type "None", argument has type "int") #type: ignore[assignment] # Incompatible default for argument "offset" (default has type "None", argument has type "int")
    ) -> list[int]:
        """Locate a list of User IDs that do not yet have a UserAuth external_id."""
        where = (self.table.c.external_id == None) | (self.table.c.external_id == "")
        select = sqlalchemy.select(columns=[self.table.c.user_id], whereclause=where)
        if limit is not None:
            select = select.limit(limit)
        if offset is not None:
            select = select.offset(offset)

        result = self.session.execute(select)

        rows = result.fetchall()
        return [row.user_id for row in rows]

    @trace_wrapper
    def bulk_insert_user_auth(self, *, user_ids: list[int] = None) -> int:  # type: ignore[assignment] # Incompatible default for argument "user_ids" (default has type "None", argument has type "List[int]")
        """Bulk inserts user ids into the user_auth table."""
        if user_ids is None or len(user_ids) == 0:
            return 0

        id_mappings = [{"user_id": user_id} for user_id in user_ids]
        result = self.session.execute(self.table.insert(id_mappings))
        self.session.commit()
        return result.rowcount

    @trace_wrapper
    def update_by_user_id(self, *, user_id: int = None, external_id: str) -> int:  # type: ignore[assignment] # Incompatible default for argument "user_id" (default has type "None", argument has type "int")
        """Update a user auth object by its user ID."""
        if not user_id or not external_id:
            return  # type: ignore[return-value] # Return value expected

        where = self.table.c.user_id == user_id
        values = dict(external_id=external_id)
        update = self.table.update(whereclause=where, values=values)
        result = self.session.execute(update)
        self.session.commit()
        return result.rowcount

    def delete_by_user_id(self, *, user_id: int = None) -> int:  # type: ignore[assignment] # Incompatible default for argument "user_id" (default has type "None", argument has type "int")
        """Deletes a user auth object by its user ID."""
        if user_id is None:
            return  # type: ignore[return-value] # Return value expected

        delete = self.table.delete(whereclause=self.table.c.user_id == user_id)
        result = self.session.execute(delete)
        affected: int = result.rowcount
        return affected

    def create(self, *, instance: model.UserAuth) -> model.UserAuth:  # type: ignore[name-defined,override] # Name "model.UserAuth" is not defined #type: ignore[override] # Signature of "create" incompatible with supertype "BaseRepository" #type: ignore[override] # Signature of "create" incompatible with supertype "AbstractRepository"
        """Creates the user auth object"""
        if instance.user_id is None:
            return
        values = self.instance_to_values(instance=instance)
        insert = self.table.insert(values=values)
        self.session.execute(insert)
        return self.get_by_user_id(user_id=instance.user_id)

    def set_refresh_token(self, *, user_id: int, refresh_token: str):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        """Sets the user auth object's refresh token"""
        if not refresh_token or not user_id:
            return

        user_auth = self.get_by_user_id(user_id=user_id)
        if not user_auth:
            return

        user_auth.refresh_token = refresh_token
        return self.update(instance=user_auth)

    @staticmethod
    def instance_to_values(instance: model) -> dict:  # type: ignore[valid-type] # Variable "authn.domain.repository.user_auth.UserAuthRepository.model" is not valid as a type
        return dict(
            user_id=instance.user_id,  # type: ignore[attr-defined] # model? has no attribute "user_id"
            external_id=instance.external_id,  # type: ignore[attr-defined] # model? has no attribute "external_id"
            refresh_token=instance.refresh_token,  # type: ignore[attr-defined] # model? has no attribute "refresh_token"
        )

    @classmethod
    @functools.lru_cache(maxsize=1)
    def make_table(cls) -> sqlalchemy.Table:
        table_name = cls.table_name()
        table_columns = cls.table_columns()
        return sqlalchemy.Table(
            table_name,
            cls.metadata,
            *table_columns,
            info=dict(bind_key="default"),
        )

    @staticmethod
    def table_columns() -> tuple[sqlalchemy.Column, ...]:
        return (
            sa.Column("id", sa.Integer, primary_key=True),
            sa.Column(
                "user_id",
                sa.Integer,
                sa.ForeignKey("user.id"),
                nullable=False,
                unique=True,
            ),
            sa.Column("external_id", sa.String, unique=True),
            sa.Column("refresh_token", sa.String),
            sa.Column(
                "created_at",
                sa.DateTime,
                nullable=True,
            ),
            sa.Column(
                "modified_at",
                sa.DateTime,
                nullable=True,
            ),
        )
