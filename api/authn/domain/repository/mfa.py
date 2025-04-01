from __future__ import annotations

import functools
from typing import Any, Literal, Mapping

import ddtrace.ext
import sqlalchemy.orm
import sqlalchemy.util

from authn.domain import model
from authn.domain.repository import base
from storage.repository import abstract

__all__ = ("UserMFARepository",)

trace_wrapper = ddtrace.tracer.wrap(
    span_type=ddtrace.ext.SpanTypes.SQL,
)


class UserMFARepository(base.BaseUserRepository[model.UserMFA]):  # type: ignore[type-var] # Type argument "UserMFA" of "BaseUserRepository" must be a subtype of "Instance"
    """The UserMetadata and UserMFA objects aren't real tables,

    they are virtual data models which expose aspects of the core user table.

    Eventually we will have extension tables which reflect these objects directly,
    but by then we will not be in Mono.

    As such, "deleting" and "creating" these objects is a matter of emptying or filling these fields.
    This is a bit strange, but it allows us to compose a contract which future developers can rely upon
    when we actually migrate the data.
    """

    model = model.UserMFA

    @trace_wrapper
    def delete(self, *, id: int) -> int:
        values = dict(
            sms_phone_number=None,
            authy_id=None,
            mfa_state=None,
            otp_secret=None,
        )
        update = self.table.update(
            whereclause=self.table.c.id == id,
            values=values,
        )
        result = self.session.execute(update)
        if not self.is_in_uow:
            self.session.commit()
        return result.rowcount

    @trace_wrapper
    def create(  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        self, *, instance: abstract.InstanceT, fetch: Literal[True, False] = True
    ):
        return self.update(instance=instance, fetch=fetch)  # type: ignore[arg-type] # Argument "instance" to "update" of "BaseRepository" has incompatible type "abstract.InstanceT"; expected "UserMFA"

    @staticmethod
    def instance_to_values(instance: model.UserMFA) -> dict:  # type: ignore[name-defined] # Name "model.UserMFA" is not defined
        return dict(
            sms_phone_number=instance.sms_phone_number,
            authy_id=instance.external_user_id,
            mfa_state=instance.mfa_state,
            otp_secret=instance.otp_secret,
        )

    @classmethod
    @functools.lru_cache(maxsize=1)
    def select_columns(cls) -> tuple[sqlalchemy.sql.ColumnElement, ...] | None:  # type: ignore[override] # Signature of "select_columns" incompatible with supertype "BaseRepository"
        enabled = sqlalchemy.literal("enabled")
        verified_case = sqlalchemy.case(
            [(cls.table.c.mfa_state == enabled, sqlalchemy.true())],
            else_=sqlalchemy.false(),
        )
        return (
            cls.table.c.id.label("user_id"),
            verified_case.label("verified"),
            cls.table.c.authy_id.label("external_user_id"),
            cls.table.c.sms_phone_number,
            cls.table.c.mfa_state,
            cls.table.c.otp_secret,
            cls.table.c.created_at,
            cls.table.c.modified_at,
        )

    def deserialize(cls, row: Mapping[str, Any] | None) -> model | None:  # type: ignore[override,valid-type] # Signature of "deserialize" incompatible with supertype "BaseRepository" #type: ignore[valid-type] # Variable "authn.domain.repository.mfa.UserMFARepository.model" is not valid as a type
        if row and any(v for f, v in row.items()):
            return cls.model(**row)
        return  # type: ignore[return-value] # Return value expected
