import dataclasses
import datetime
import enum
from dataclasses import dataclass
from typing import Optional


class TaskStatus(enum.Enum):
    SUCCESS = "SUCCESS"
    INPROGRESS = "INPROGRESS"
    FAILED = "FAILED"


class TaskType(enum.Enum):
    INCREMENTAL = "INCREMENTAL"
    FIXUP = "FIXUP"


class JobType(enum.Enum):
    INGESTION = "INGESTION"
    PARSER = "PARSER"


@dataclass
class IngestionMeta:
    task_id: Optional[int]
    most_recent_raw: Optional[str]
    most_recent_parsed: Optional[str]
    task_started_at: int
    task_updated_at: Optional[int]
    max_tries: Optional[int]
    duration_in_secs: Optional[int]
    target_file: Optional[str]
    task_status: TaskStatus = TaskStatus.INPROGRESS
    task_type: TaskType = TaskType.INCREMENTAL
    job_type: JobType = JobType.INGESTION
    created_at: Optional[datetime.datetime] = dataclasses.field(
        default_factory=datetime.datetime.utcnow
    )
    modified_at: Optional[datetime.datetime] = dataclasses.field(
        default_factory=datetime.datetime.utcnow
    )
