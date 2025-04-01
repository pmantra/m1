from __future__ import annotations

import enum
from dataclasses import dataclass
from typing import Any

from utils.log import logger

log = logger(__name__)


class HdcExportEventType(enum.Enum):
    HEALTH_PROFILE = "health_profile"
    RISK_FLAG = "risk_flag"
    FHIR = "fhir"
    ASSESSMENT_COMPLETION = "assessment_completion"


@dataclass
class HdcExportItem:
    event_type: HdcExportEventType
    label: str = ""
    value: Any = None  # value depends on event_type & label

    @staticmethod
    def from_json(input: Any) -> HdcExportItem:
        args = HdcExportItem(
            event_type=HdcExportEventType(input["event_type"]),
            label=input.get("label", ""),
            value=input.get("value", None),
        )
        return args
