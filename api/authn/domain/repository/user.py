from __future__ import annotations

import datetime
import functools

import ddtrace.ext
import sqlalchemy as sa
import sqlalchemy.exc
import sqlalchemy.orm
import sqlalchemy.util

from authn.domain import model
from authn.domain.repository import base, user_auth
from authn.models.user import MFAState

__all__ = ("UserRepository",)

trace_wrapper = ddtrace.tracer.wrap(
    span_type=ddtrace.ext.SpanTypes.SQL,
)

ALLOWED_USER_FILTERS = {"email", "email_like"}


class UserRepository(base.BaseUserRepository[model.User]):  # type: ignore[type-var] # Type argument "User" of "BaseUserRepository" must be a subtype of "Instance"
    """A repository for managing user data from the downstream storage backend for our core User model."""

    model = model.User

    @trace_wrapper
    def fetch(
        self, filters: str = None, limit: int = 250, offset: int = None  # type: ignore[assignment] # Incompatible default for argument "filters" (default has type "None", argument has type "str") #type: ignore[assignment] # Incompatible default for argument "offset" (default has type "None", argument has type "int")
    ) -> list[model]:  # type: ignore[valid-type] # Variable "authn.domain.repository.user.UserRepository.model" is not valid as a type
        select = self._build_fetch_query(filters, limit, offset)
        result = self.session.execute(select)
        rows = result.fetchall()
        return self.deserialize_list(rows)

    def _build_fetch_query(self, filters, limit, offset):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        columns = self.select_columns()
        select = sqlalchemy.select(columns=columns)

        if filters is not None:
            for k, v in filters.items():
                if k not in ALLOWED_USER_FILTERS:
                    raise UserRepositoryError(f"Filter {k} is not currently allowed")
                if k == "email":
                    select = select.where(self.table.c.email == v)
                if k == "email_like":
                    select = select.where(self.table.c.email.like(v))

        if limit is not None:
            select = select.limit(limit)
        if offset is not None:
            select = select.offset(offset)

        return select

    @trace_wrapper
    def get_by_email(self, email: str) -> model | None:  # type: ignore[valid-type] # Variable "authn.domain.repository.user.UserRepository.model" is not valid as a type
        """Locate a User object with an email."""
        where = self.table.c.email == email
        result = self.execute_select(where=where)
        row = result.first()
        return self.deserialize(row)

    @trace_wrapper
    def get_all_by_ids(self, ids: list[int]) -> list[model]:  # type: ignore[valid-type] # Variable "authn.domain.repository.user.UserRepository.model" is not valid as a type
        """Locate a list of User objects by ids."""
        where = self.table.c.id.in_(ids)
        result = self.execute_select(where=where)
        rows = result.fetchall()
        return self.deserialize_list(rows)  # type: ignore[arg-type] # Argument 1 to "deserialize_list" of "BaseRepository" has incompatible type "List[RowProxy]"; expected "Optional[List[Mapping[str, Any]]]"

    @trace_wrapper
    def get_all_by_time_range(self, end: datetime.date, start: datetime.date | None = None) -> list[model]:  # type: ignore[valid-type] # Variable "authn.domain.repository.user.UserRepository.model" is not valid as a type
        """Get a list of users by the modified time range"""
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
    def get_all_without_auth(
        self, limit: int = None, offset: int = None, user_ids: list[int] = None  # type: ignore[assignment] # Incompatible default for argument "limit" (default has type "None", argument has type "int") #type: ignore[assignment] # Incompatible default for argument "offset" (default has type "None", argument has type "int") #type: ignore[assignment] # Incompatible default for argument "user_ids" (default has type "None", argument has type "List[int]")
    ) -> list[int]:
        """Locate a list of User IDs that do not yet have a UserAuth object."""
        auth_table = user_auth.UserAuthRepository.table
        join = self.table.outerjoin(auth_table, self.table.c.id == auth_table.c.user_id)
        where = auth_table.c.user_id == None
        if user_ids is not None:
            where = where & self.table.c.id.in_(user_ids)
        select = sqlalchemy.select(
            columns=[self.table.c.id], whereclause=where
        ).select_from(join)
        if limit is not None:
            select = select.limit(limit)
        if offset is not None:
            select = select.offset(offset)

        result = self.session.execute(select)

        rows = result.fetchall()
        return [row.id for row in rows]

    @trace_wrapper
    def get_users_mfa_enabled(
        self, limit: int = None, offset: int = None, user_ids: list[int] = None  # type: ignore[assignment] # Incompatible default for argument "limit" (default has type "None", argument has type "int") #type: ignore[assignment] # Incompatible default for argument "offset" (default has type "None", argument has type "int") #type: ignore[assignment] # Incompatible default for argument "user_ids" (default has type "None", argument has type "List[int]")
    ) -> list[int]:

        auth_table = user_auth.UserAuthRepository.table
        join = self.table.join(auth_table, self.table.c.id == auth_table.c.user_id)
        where = (
            (self.table.c.mfa_state == MFAState.ENABLED)
            & (self.table.c.sms_phone_number != None)
            & (self.table.c.email != None)
        )
        if user_ids is not None:
            where = where & self.table.c.id.in_(user_ids)
        select = sqlalchemy.select(
            columns=[
                self.table.c.email,
                auth_table.c.external_id,
                self.table.c.sms_phone_number,
                self.table.c.id,
            ],
            whereclause=where,
        ).select_from(join)
        if limit is not None:
            select = select.limit(limit)
        if offset is not None:
            select = select.offset(offset)

        result = self.session.execute(select)
        rows = result.fetchall()

        return rows

    @staticmethod
    def instance_to_values(instance: model) -> dict:  # type: ignore[valid-type] # Variable "authn.domain.repository.user.UserRepository.model" is not valid as a type
        values = dict(
            email=instance.email,  # type: ignore[attr-defined] # model? has no attribute "email"
            first_name=instance.first_name,  # type: ignore[attr-defined] # model? has no attribute "first_name"
            last_name=instance.last_name,  # type: ignore[attr-defined] # model? has no attribute "last_name"
            password=instance.password,  # type: ignore[attr-defined] # model? has no attribute "password"
            username=instance.username,  # type: ignore[attr-defined] # model? has no attribute "username"
            email_confirmed=instance.email_confirmed,  # type: ignore[attr-defined] # model? has no attribute "email_confirmed"
            active=instance.active,  # type: ignore[attr-defined] # model? has no attribute "active"
        )
        return values

    @classmethod
    @functools.lru_cache(maxsize=1)
    def select_columns(cls) -> tuple[sqlalchemy.sql.ColumnElement, ...] | None:  # type: ignore[override] # Signature of "select_columns" incompatible with supertype "BaseRepository"
        return (
            cls.table.c.id,
            cls.table.c.email,
            cls.table.c.password,
            cls.table.c.username,
            cls.table.c.first_name,
            cls.table.c.last_name,
            cls.table.c.email_confirmed,
            cls.table.c.active,
            cls.table.c.created_at,
            cls.table.c.modified_at,
        )


class UserRepositoryError(Exception):
    ...
