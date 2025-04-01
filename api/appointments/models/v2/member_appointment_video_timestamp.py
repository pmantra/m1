from __future__ import annotations  # needed for python 3.9 type annotations

import json
from dataclasses import dataclass, field
from datetime import datetime

from utils.log import logger

log = logger(__name__)


@dataclass
class AppointmentVideoTimestampStruct:
    id: int
    provider_id: int
    member_id: int
    member_started_at: datetime
    member_ended_at: datetime
    json_str: str
    json_data: dict = field(init=False)
    scheduled_start: datetime
    scheduled_end: datetime
    practitioner_started_at: datetime
    practitioner_ended_at: datetime
    cancelled_at: datetime
    disputed_at: datetime
    phone_call_at: datetime

    def __post_init__(self) -> None:
        """
        :raises json.decoder.JSONDecodeError: Incorrectly formatted time in JSON for
            member_disconnected_at or practitioner_disconnected_at
        """
        if not self.json_str:
            self.json_data = {}
        else:
            try:
                self.json_data = json.loads(self.json_str)
            except json.decoder.JSONDecodeError as e:
                log.error(
                    "Incorrectly formatted json",
                    appointment_id=self.id,
                    json_str=self.json_str,
                )
                raise e
