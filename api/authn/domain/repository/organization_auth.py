from __future__ import annotations

import datetime
import functools
from typing import Any, Mapping

import ddtrace.ext
import sqlalchemy as sa
import sqlalchemy.orm
import sqlalchemy.util

from authn.domain.model import OrganizationAuth
from storage.repository import abstract, base

__all__ = ("OrganizationAuthRepository",)

trace_wrapper = ddtrace.tracer.wrap(
    span_type=ddtrace.ext.SpanTypes.SQL,
)


class OrganizationAuthRepository(base.BaseRepository[OrganizationAuth]):  # type: ignore[type-var] # Type argument "OrganizationAuth" of "BaseRepository" must be a subtype of "Instance"
    """A repository for managing organization auth objects."""

    model = OrganizationAuth

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
                "organization_id",
                sa.Integer,
                nullable=False,
                unique=True,
            ),
            sa.Column("mfa_required", sa.Boolean, nullable=False),
            sa.Column(
                "created_at", sa.DateTime, nullable=True, server_default=sa.func.now()
            ),
            sa.Column(
                "modified_at",
                sa.DateTime,
                nullable=True,
                server_default=sa.func.now(),
                onupdate=sa.func.now(),
            ),
        )

    @trace_wrapper
    def create(self, *, instance: OrganizationAuth) -> OrganizationAuth | None:
        """Creates the organization auth object and insert to table"""

        if instance.organization_id is None:
            return None
        values = self.instance_to_values(instance=instance)
        insert = self.table.insert(values=values)
        self.session.execute(insert)
        if not self.is_in_uow:
            self.session.commit()
        return self.get_by_organization_id(organization_id=instance.organization_id)

    @staticmethod
    def instance_to_values(instance: model) -> dict:  # type: ignore[valid-type] # Variable "authn.domain.repository.organization_auth.OrganizationAuthRepository.model" is not valid as a type
        return dict(
            id=instance.id,  # type: ignore[attr-defined] # model? has no attribute "id"
            organization_id=instance.organization_id,  # type: ignore[attr-defined] # model? has no attribute "organization_id"
            mfa_required=int(instance.mfa_required),  # type: ignore[attr-defined] # model? has no attribute "mfa_required"
        )

    @trace_wrapper
    def delete_by_organization_id(self, *, organization_id: int) -> int:
        """Delete the organization record by the organization_id"""

        if organization_id is None:
            return 0
        where = self.table.c.organization_id == organization_id
        delete = self.table.delete(whereclause=where)
        result = self.session.execute(delete)
        if not self.is_in_uow:
            self.session.commit()
        impacted_row: int = result.rowcount

        return impacted_row

    @trace_wrapper
    def update_by_organization_id(
        self, *, organization_id: int, new_mfa_required: bool
    ) -> int:
        if organization_id is None:
            return 0
        where = self.table.c.organization_id == organization_id
        values = dict(mfa_required=int(new_mfa_required))
        update = self.table.update(whereclause=where, values=values)
        result = self.session.execute(update)
        if not self.is_in_uow:
            self.session.commit()

        return result.rowcount

    @trace_wrapper
    def get_by_organization_id(self, *, organization_id: int) -> OrganizationAuth:
        """Get an organization auth by the organization ID."""

        where = self.table.c.organization_id == organization_id
        result = self.execute_select(where=where)
        row = result.first()

        return self.deserialize(row)  # type: ignore[return-value] # Incompatible return value type (got "None", expected "OrganizationAuth")

    @trace_wrapper
    def get_all_by_time_range(
        self, *, end: datetime.date, start: datetime.date | None = None
    ) -> list[OrganizationAuth]:
        """Get a list of user external identities by the modified time range"""
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

    @classmethod
    def deserialize(cls, row: Mapping[str, Any] | None) -> abstract.InstanceT | None:  # type: ignore[override] # Signature of "deserialize" incompatible with supertype "BaseRepository"
        if row is None:
            return  # type: ignore[return-value] # Return value expected

        row_data = dict(row)
        row_data["mfa_required"] = False if row_data["mfa_required"] == 0 else True

        return cls.model(**row_data)  # type: ignore[return-value] # Incompatible return value type (got "OrganizationAuth", expected "Optional[abstract.InstanceT]")
