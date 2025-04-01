from typing import Optional

import sqlalchemy

from direct_payment.pharmacy.models.ingestion_meta import (
    IngestionMeta,
    JobType,
    TaskStatus,
    TaskType,
)
from direct_payment.pharmacy.repository.ingestion_meta_repository import (
    IngestionMetaRepository,
)
from storage.connection import db


class IngestionMetaService:
    def __init__(
        self,
        session: sqlalchemy.orm.scoping.ScopedSession = None,  # type: ignore[assignment] # Incompatible default for argument "session" (default has type "None", argument has type "scoped_session")
        ingestion_meta_repository: IngestionMetaRepository = None,  # type: ignore[assignment] # Incompatible default for argument "ingestion_meta_repository" (default has type "None", argument has type "IngestionMetaRepository")
    ):
        self.session = session or db.session
        self.repository = ingestion_meta_repository or IngestionMetaRepository(
            session=session
        )

    def create(self, *, instance: IngestionMeta):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        return self.repository.create(instance=instance, fetch=True)

    def get_most_recent_task(  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        self, *, status: TaskStatus, task_type: TaskType, job_type: JobType
    ):
        return self.repository.get_most_recent(
            status=status, task_type=task_type, job_type=job_type
        )

    def update_task(  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        self,
        *,
        task: IngestionMeta,
        task_updated_at: int,
        most_recent_raw: Optional[str] = None,
        task_status: Optional[TaskStatus] = None,
    ):
        if most_recent_raw:
            task.most_recent_raw = most_recent_raw
        if task_updated_at:
            task.task_updated_at = task_updated_at
        if task_status:
            task.task_status = task_status
        task.duration_in_secs = task_updated_at - task.task_started_at
        self.repository.create(instance=task)
