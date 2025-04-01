from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime

from appointments.schemas.appointments import PrivacyType
from models.common import PrivilegeType
from utils.log import logger

log = logger(__name__)


@dataclass
class VideoStruct:
    session_id: str | None = None
    member_token: str | None = None
    practitioner_token: str | None = None

    def to_dict(self) -> dict:
        """
        Convert to dictionary
        """
        fields = {field for field in self.__annotations__}
        return {f.strip("_"): getattr(self, f) for f in fields}


@dataclass
class MemberAppointmentStruct:
    id: int
    schedule_event_id: int
    member_schedule_id: int
    product_id: int
    client_notes: str
    cancelled_at: datetime
    scheduled_start: datetime
    scheduled_end: datetime
    privacy: PrivacyType
    privilege_type: PrivilegeType
    member_started_at: datetime
    member_ended_at: datetime
    practitioner_started_at: datetime
    practitioner_ended_at: datetime
    disputed_at: datetime
    video: VideoStruct
    plan_segment_id: int
    phone_call_at: datetime
    json_str: str

    # From json
    member_disconnected_at: datetime | None = field(init=False)
    practitioner_disconnected_at: datetime | None = field(init=False)

    def __post_init__(self) -> None:
        # Load video json field
        if isinstance(self.video, str) and self.video:
            try:
                self.video = VideoStruct(**json.loads(self.video))
            except json.decoder.JSONDecodeError:
                log.error(
                    "Incorrectly formatted video json",
                    appointment_id=self.id,
                    video_json=self.video,
                )
                self.video = VideoStruct()

        # Load appointment json field
        try:
            self.json_data = json.loads(self.json_str)
        except json.decoder.JSONDecodeError:
            log.error(
                "Incorrectly formatted json",
                appointment_id=self.id,
                json_str=self.json_str,
            )
            self.json_data = {}

        # Set fields from JSON
        if member_disconnected_at := self.json_data.get("member_disconnected_at"):
            try:
                self.member_disconnected_at = datetime.fromisoformat(
                    member_disconnected_at
                )
            except ValueError:
                log.error(
                    "Invalid member_disconnected_at date",
                    member_disconnected_at=str(member_disconnected_at),
                )
        else:
            self.member_disconnected_at = None

        if practitioner_disconnected_at := self.json_data.get(
            "practitioner_disconnected_at"
        ):
            try:
                self.practitioner_disconnected_at = datetime.fromisoformat(
                    practitioner_disconnected_at
                )
            except ValueError:
                log.error(
                    "Invalid practitioner_disconnected_at date",
                    practitioner_disconnected_at=str(practitioner_disconnected_at),
                )
        else:
            self.practitioner_disconnected_at = None
