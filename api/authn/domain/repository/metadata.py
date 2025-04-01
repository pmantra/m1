from __future__ import annotations

import functools
from typing import Any, Literal, Mapping

import ddtrace.ext
import sqlalchemy.orm
import sqlalchemy.util

from authn.domain import model
from authn.domain.repository import base
from storage.repository import abstract

__all__ = ("UserMetadataRepository",)

trace_wrapper = ddtrace.tracer.wrap(
    span_type=ddtrace.ext.SpanTypes.SQL,
)


class UserMetadataRepository(base.BaseUserRepository[model.UserMetadata]):  # type: ignore[type-var] # Type argument "UserMetadata" of "BaseUserRepository" must be a subtype of "Instance"
    """The UserMetadata and UserMFA objects aren't real tables,

    they are virtual data models which expose aspects of the core user table.

    Eventually we will have extension tables which reflect these objects directly,
    but by then we will not be in Mono.

    As such, "deleting" and "creating" these objects is a matter of emptying or filling these fields.
    This is a bit strange, but it allows us to compose a contract which future developers can rely upon
    when we actually migrate the data.
    """

    model = model.UserMetadata

    def delete(self, *, id: int) -> int:
        values = dict(
            first_name=None,
            last_name=None,
            middle_name=None,
            timezone=None,
            image_id=None,
            zendesk_user_id=None,
        )
        update = self.table.update(
            whereclause=self.table.c.id == id,
            values=values,
        )
        result = self.session.execute(update)
        if not self.is_in_uow:
            self.session.commit()
        return result.rowcount

    def create(  # type: ignore[override,no-untyped-def] # Signature of "create" incompatible with supertype "BaseRepository" #type: ignore[override] # Signature of "create" incompatible with supertype "AbstractRepository" #type: ignore[no-untyped-def] # Function is missing a return type annotation
        self, *, instance: abstract.InstanceT, fetch: Literal[True, False] = True
    ):
        return self.update(instance=instance, fetch=fetch)  # type: ignore[arg-type] # Argument "instance" to "update" of "BaseRepository" has incompatible type "abstract.InstanceT"; expected "UserMetadata"

    @staticmethod
    def instance_to_values(instance: model.UserMetadata) -> dict:  # type: ignore[name-defined] # Name "model.UserMetadata" is not defined
        return dict(
            first_name=instance.first_name,
            last_name=instance.last_name,
            middle_name=instance.middle_name,
            timezone=instance.timezone,
            image_id=instance.image_id,
            zendesk_user_id=instance.zendesk_user_id,
        )

    @classmethod
    @functools.lru_cache(maxsize=1)
    def select_columns(cls) -> tuple[sqlalchemy.sql.ColumnElement, ...] | None:  # type: ignore[override] # Signature of "select_columns" incompatible with supertype "BaseRepository"
        return (
            cls.table.c.id.label("user_id"),
            cls.table.c.first_name,
            cls.table.c.last_name,
            cls.table.c.middle_name,
            cls.table.c.timezone,
            cls.table.c.image_id,
            cls.table.c.zendesk_user_id,
            cls.table.c.created_at,
            cls.table.c.modified_at,
        )

    def deserialize(cls, row: Mapping[str, Any] | None) -> model | None:  # type: ignore[override,valid-type] # Signature of "deserialize" incompatible with supertype "BaseRepository" #type: ignore[valid-type] # Variable "authn.domain.repository.metadata.UserMetadataRepository.model" is not valid as a type
        if row and any(v for f, v in row.items() if f not in cls._GENERATED):
            return cls.model(**row)
        return  # type: ignore[return-value] # Return value expected

    _GENERATED = frozenset({"user_id", "timezone", "created_at", "modified_at"})
