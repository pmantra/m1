from __future__ import annotations

import dataclasses
from typing import Literal, Optional

import sqlalchemy as sa
from sqlalchemy import and_

from direct_payment.pharmacy.models.ingestion_meta import (
    IngestionMeta,
    JobType,
    TaskStatus,
    TaskType,
)
from direct_payment.pharmacy.repository.util import transaction
from storage.repository import abstract, base


class IngestionMetaRepository(base.BaseRepository[IngestionMeta]):  # type: ignore[type-var] # Type argument "IngestionMeta" of "BaseRepository" must be a subtype of "Instance"
    model = IngestionMeta

    def __init__(
        self,
        session: sa.orm.scoping.ScopedSession = None,  # type: ignore[assignment] # Incompatible default for argument "session" (default has type "None", argument has type "scoped_session")
    ):
        # setting is_in_uow as true since it is hooked up with the transaction wrapper
        super().__init__(session=session, is_in_uow=True)

    def get_by_task_id(self, *, task_id: int) -> Optional[model]:  # type: ignore[valid-type] # Variable "direct_payment.pharmacy.repository.ingestion_meta_repository.IngestionMetaRepository.model" is not valid as a type
        where = self.table.c.task_id == task_id
        result = self.execute_select(where=where)
        return result.first()

    @transaction
    def delete(self, *, task_id: int) -> int:
        delete = self.table.delete(whereclause=self.table.c.task_id == task_id)
        result = self.session.execute(delete)
        affected: int = result.rowcount
        return affected

    @transaction
    def create(self, *, instance: model, fetch: Literal[True, False] = True):  # type: ignore[no-untyped-def,valid-type] # Variable "direct_payment.pharmacy.repository.ingestion_meta_repository.IngestionMetaRepository.model" is not valid as a type
        values = self.instance_to_values(instance=instance)
        insert = self.table.insert(values=values)
        result = self.session.execute(insert)
        pk: int = result.inserted_primary_key[0]
        if fetch and result.rowcount:
            return self.get_by_task_id(task_id=pk)
        return result.rowcount

    def get_most_recent(
        self, *, status: TaskStatus, task_type: TaskType, job_type: JobType
    ) -> Optional[model]:  # type: ignore[valid-type] # Variable "direct_payment.pharmacy.repository.ingestion_meta_repository.IngestionMetaRepository.model" is not valid as a type
        where = and_(
            self.table.c.task_status == status,
            self.table.c.task_type == task_type,
            self.table.c.job_type == job_type,
        )
        order_by = self.table.c.task_updated_at.desc()
        select = sa.select(
            columns=self.select_columns(), whereclause=where, order_by=order_by
        )
        result = self.session.execute(select)
        return result.fetchone()

    @transaction
    def update(  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        self, *, instance: abstract.InstanceT, fetch: Literal[True, False] = True
    ):
        values = self.instance_to_values(instance=instance)
        update = self.table.update(
            whereclause=self.table.c.task_id == instance.task_id, values=values  # type: ignore[attr-defined] # "abstract.InstanceT" has no attribute "task_id"
        )
        result = self.session.execute(update)
        affected: int = result.rowcount
        return affected

    @classmethod
    def identity_columns(cls) -> tuple[sa.Column, ...]:
        return (
            sa.Column(
                "created_at",
                sa.TIMESTAMP,
                nullable=False,
                server_default=sa.FetchedValue(),
            ),
            sa.Column(
                "modified_at",
                sa.TIMESTAMP,
                nullable=False,
                server_default=sa.FetchedValue(),
                server_onupdate=sa.FetchedValue(for_update=True),
            ),
        )

    @staticmethod
    def table_columns() -> tuple[sa.Column, ...]:
        return (
            sa.Column(
                "task_id",
                sa.Integer,
                primary_key=True,
                autoincrement=True,
                nullable=False,
            ),
            sa.Column("most_recent_raw", sa.String, nullable=True),
            sa.Column("most_recent_parsed", sa.String, nullable=True),
            # Add default
            sa.Column("task_started_at", sa.TIMESTAMP, nullable=False),
            sa.Column("task_updated_at", sa.TIMESTAMP, nullable=True),
            sa.Column("max_tries", sa.Integer, nullable=True),
            sa.Column("duration_in_secs", sa.Integer, nullable=True),
            sa.Column("target_file", sa.String, nullable=True),
            sa.Column(
                "task_status", sa.Enum(TaskStatus), default=TaskStatus.INPROGRESS
            ),
            sa.Column("task_type", sa.Enum(TaskType), default=TaskType.INCREMENTAL),
            sa.Column("job_type", sa.Enum(JobType), default=JobType.INGESTION),
        )

    @staticmethod
    def instance_to_values(instance: abstract.InstanceT) -> dict:  # type: ignore[override] # Signature of "instance_to_values" incompatible with supertype "BaseRepository"
        return dataclasses.asdict(instance)  # type: ignore[call-overload] # No overload variant of "asdict" matches argument type "abstract.InstanceT"
