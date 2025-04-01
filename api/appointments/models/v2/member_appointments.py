from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime

from utils.log import logger

log = logger(__name__)


@dataclass
class MemberAppointmentsListElement:
    id: int
    product_id: int
    client_notes: str  # aka: pre_session_notes
    cancelled_at: datetime
    disputed_at: datetime  # used in get_state(), removed in response
    json_str: str
    json_data: dict = field(init=False)
    member_started_at: datetime
    member_ended_at: datetime
    scheduled_start: datetime
    scheduled_end: datetime
    privacy: str
    privilege_type: str
    practitioner_started_at: datetime
    practitioner_ended_at: datetime
    phone_call_at: datetime

    # From json
    member_disconnected_at: datetime | None = field(init=False)
    practitioner_disconnected_at: datetime | None = field(init=False)

    def __post_init__(self) -> None:
        """
        :raises ValueError: Incorrectly formatted time in JSON for
                            member_disconnected_at or practitioner_disconnected_at
        """
        try:
            self.json_data = json.loads(self.json_str)
        except json.decoder.JSONDecodeError as e:
            log.error(
                "Incorrectly formatted json",
                appointment_id=self.id,
                json_str=self.json_str,
            )
            raise e

        # Set fields from JSON
        if member_disconnected_at := self.json_data.get("member_disconnected_at"):
            try:
                self.member_disconnected_at = datetime.fromisoformat(
                    member_disconnected_at
                )
            except ValueError:
                raise ValueError(
                    f"Invalid member_disconnected_at date: {member_disconnected_at!r}"
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
                raise ValueError(
                    f"Invalid practitioner_disconnected_at date: {practitioner_disconnected_at!r}"
                )
        else:
            self.practitioner_disconnected_at = None
