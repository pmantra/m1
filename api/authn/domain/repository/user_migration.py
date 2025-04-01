from __future__ import annotations

import datetime
import functools

import ddtrace.ext
import sqlalchemy as sa
import sqlalchemy.exc
import sqlalchemy.orm
import sqlalchemy.util

from authn.domain import model
from authn.domain.repository import base

__all__ = ("UserMigrationRepository",)

trace_wrapper = ddtrace.tracer.wrap(
    span_type=ddtrace.ext.SpanTypes.SQL,
)


class UserMigrationRepository(base.BaseUserRepository[model.UserMigration]):  # type: ignore[type-var] # Type argument "User" of "BaseUserRepository" must be a subtype of "Instance"
    """A repository for managing user data from the downstream storage backend for our core User model."""

    model = model.UserMigration

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

    @staticmethod
    def instance_to_values(instance: model) -> dict:  # type: ignore[valid-type] # Variable "authn.domain.repository.user.UserRepository.model" is not valid as a type
        values = dict(
            email=instance.email,  # type: ignore[attr-defined] # model? has no attribute "email"
            first_name=instance.first_name,  # type: ignore[attr-defined] # model? has no attribute "first_name"
            middle_name=instance.middle_name,  # type: ignore[attr-defined] # model? has no attribute "middle_name"
            last_name=instance.last_name,  # type: ignore[attr-defined] # model? has no attribute "last_name"
            password=instance.password,  # type: ignore[attr-defined] # model? has no attribute "password"
            username=instance.username,  # type: ignore[attr-defined] # model? has no attribute "username"
            email_confirmed=instance.email_confirmed,  # type: ignore[attr-defined] # model? has no attribute "email_confirmed"
            active=instance.active,  # type: ignore[attr-defined] # model? has no attribute "active"
            id=instance.id,  # type: ignore[attr-defined] # model? has no attribute "id"
            esp_id=instance.esp_id,  # type: ignore[attr-defined] # model? has no attribute "esp_id"
            image_id=instance.image_id,  # type: ignore[attr-defined] # model? has no attribute "image_id"
            zendesk_user_id=instance.zendesk_user_id,  # type: ignore[attr-defined] # model? has no attribute "zendesk_user_id"
            created_at=instance.created_at,  # type: ignore[attr-defined] # model? has no attribute "created_at"
            modified_at=instance.modified_at,  # type: ignore[attr-defined] # model? has no attribute "modified_at"
            mfa_state=instance.mfa_state,  # type: ignore[attr-defined] # model? has no attribute "mfa_state"
            sms_phone_number=instance.sms_phone_number,  # type: ignore[attr-defined] # model? has no attribute "sms_phone_number"
        )
        return values

    @classmethod
    @functools.lru_cache(maxsize=1)
    def select_columns(cls) -> tuple[sqlalchemy.sql.ColumnElement, ...] | None:  # type: ignore[override] # Signature of "select_columns" incompatible with supertype "BaseRepository"
        return (
            cls.table.c.id,
            cls.table.c.esp_id,
            cls.table.c.email,
            cls.table.c.password,
            cls.table.c.username,
            cls.table.c.first_name,
            cls.table.c.middle_name,
            cls.table.c.last_name,
            cls.table.c.email_confirmed,
            cls.table.c.active,
            cls.table.c.image_id,
            cls.table.c.zendesk_user_id,
            cls.table.c.mfa_state,
            cls.table.c.sms_phone_number,
            cls.table.c.created_at,
            cls.table.c.modified_at,
        )


class UserMigrationRepositoryError(Exception):
    ...
