from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from enum import Enum
from typing import Any, List


@dataclass
class FertilityStatusItem:
    # The API has other fields that aren't specified as there's no use of them yet
    status_code: str
    updated_at: datetime

    @staticmethod
    def from_dict(data: dict) -> FertilityStatusItem:
        return FertilityStatusItem(
            data["status_code"], datetime.fromisoformat(data["updated_at"])
        )


@dataclass
class GetFertilityStatusHistoryResponse:
    fertility_status_history: List[FertilityStatusItem]

    @staticmethod
    def from_dict(data: Any) -> GetFertilityStatusHistoryResponse:
        fertility = data.get("fertility_status_history") or []
        fertility_status_history = [
            FertilityStatusItem.from_dict(item) for item in fertility
        ]
        return GetFertilityStatusHistoryResponse(
            fertility_status_history=fertility_status_history
        )


class ConditionType(str, Enum):
    CHRONIC_DIABETES = "chronic diabetes"
    GESTATIONAL_DIABETES = "gestational diabetes"
    PREGNANCY = "pregnancy"


class MethodOfConception(str, Enum):
    IUI = "iui"
    IVF = "ivf"
    OTHER_FERTILITY_TREATMENT = "other fertility treatment"
    NO_FERTILITY_TREATMENT = "no fertility treatment"
    FERTILITY_TREATMENT_NOT_SPECIFIED = "fertility treatment not specified"
    UNKNOWN = "unknown"


class Outcome(str, Enum):
    LIVE_BIRTH_TERM = "live birth - term"
    LIVE_BIRTH_PRETERM = "live birth - preterm"
    STILLBIRTH = "stillbirth"
    MISCARRIAGE = "miscarriage"
    UNKNOWN = "unknown"


class ClinicalStatus(str, Enum):
    ACTIVE = "active"
    RESOLVED = "resolved"
    UNKNOWN = "unknown"


class GestationalDiabetesStatus(str, Enum):
    HAS_CHRONIC_DIABETES = "Has chronic diabetes"
    HAS_GDM = "Has gestational diabetes"
    TESTED_NEGATIVE = "Has tested for gestational diabetes and does not have it"
    TEST_RESULT_PENDING = (
        "Has tested for gestational diabetes and doesn’t have results yet"
    )
    NOT_TESTED = "Has not tested for gestational diabetes"


@dataclass
class Alert:
    type: str
    message: str

    @staticmethod
    def from_dict(data: dict) -> Alert:
        return Alert(data["type"], data["message"])

    def to_dict(self) -> dict:
        return {
            "type": self.type,
            "message": self.message,
        }


@dataclass
class Modifier:
    id: int | None = None
    name: str | None = None
    role: str | None = None
    verticals: list[str] | None = None

    def to_dict(self) -> dict:
        data = {
            "id": self.id,
            "name": self.name,
            "role": self.role,
            "verticals": self.verticals,
        }
        return data


@dataclass
class ValueWithModifierAndUpdatedAt:
    value: str | None = None
    modifier: Modifier | None = None
    updated_at: datetime | None = None

    @staticmethod
    def from_dict(data: Any) -> ValueWithModifierAndUpdatedAt:
        updated_at = None
        if data.get("updated_at"):
            updated_at = datetime.fromisoformat(data["updated_at"])
        modifier = Modifier(**data.get("modifier")) if data.get("modifier") else None

        return ValueWithModifierAndUpdatedAt(
            value=data.get("value"),
            modifier=modifier,
            updated_at=updated_at,
        )

    def to_dict(self) -> dict:
        updated_at_str = None
        if self.updated_at:
            updated_at_str = self.updated_at.strftime("%Y-%m-%dT%H:%M:%SZ")

        return {
            "value": self.value,
            "modifier": self.modifier.to_dict() if self.modifier else None,
            "updated_at": updated_at_str,
        }


@dataclass
class MemberCondition:
    id: str | None = None
    user_id: int | None = None
    condition_type: str | None = None
    status: str | None = None
    onset_date: date | None = None
    abatement_date: date | None = None
    estimated_date: date | None = None
    is_first_occurrence: bool | None = None
    method_of_conception: ValueWithModifierAndUpdatedAt | None = None
    outcome: ValueWithModifierAndUpdatedAt | None = None
    modifier: Modifier | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None

    @staticmethod
    def from_dict(data: Any) -> MemberCondition:
        onset_date = None
        abatement_date = None
        estimated_date = None
        created_at = None
        updated_at = None
        if data.get("onset_date"):
            onset_date = date.fromisoformat(data["onset_date"])
        if data.get("abatement_date"):
            abatement_date = date.fromisoformat(data["abatement_date"])
        if data.get("estimated_date"):
            estimated_date = date.fromisoformat(data["estimated_date"])
        if data.get("created_at"):
            created_at = datetime.fromisoformat(data["created_at"])
        if data.get("updated_at"):
            updated_at = datetime.fromisoformat(data["updated_at"])

        method_of_conception = (
            ValueWithModifierAndUpdatedAt.from_dict(data.get("method_of_conception"))
            if data.get("method_of_conception")
            else None
        )

        outcome = (
            ValueWithModifierAndUpdatedAt.from_dict(data.get("outcome"))
            if data.get("outcome")
            else None
        )

        modifier = Modifier(**data.get("modifier")) if data.get("modifier") else None

        return MemberCondition(
            id=data.get("id"),
            user_id=data.get("user_id"),
            condition_type=data.get("condition_type"),
            status=data.get("status"),
            onset_date=onset_date,
            abatement_date=abatement_date,
            estimated_date=estimated_date,
            is_first_occurrence=data.get("is_first_occurrence"),
            method_of_conception=method_of_conception,
            outcome=outcome,
            modifier=modifier,
            created_at=created_at,
            updated_at=updated_at,
        )

    def to_dict(self) -> dict:
        method_of_conception = None
        if self.method_of_conception:
            method_of_conception = self.method_of_conception.to_dict()

        outcome = None
        if self.outcome:
            outcome = self.outcome.to_dict()

        data = {
            "id": self.id,
            "user_id": self.user_id,
            "condition_type": self.condition_type,
            "status": self.status,
            "onset_date": self.onset_date.isoformat() if self.onset_date else None,
            "abatement_date": self.abatement_date.isoformat()
            if self.abatement_date
            else None,
            "estimated_date": self.estimated_date.isoformat()
            if self.estimated_date
            else None,
            "is_first_occurrence": self.is_first_occurrence,
            "method_of_conception": method_of_conception,
            "outcome": outcome,
            "modifier": self.modifier.to_dict() if self.modifier else None,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }

        return data


@dataclass
class PregnancyAndRelatedConditions:
    pregnancy: MemberCondition
    related_conditions: dict[str, MemberCondition]
    alerts: dict[str, list[Alert]]

    @staticmethod
    def from_dict(data: Any) -> PregnancyAndRelatedConditions:
        pregnancy = MemberCondition.from_dict(data["pregnancy"])

        related_conditions = {}
        if data.get("related_conditions"):
            related_conditions = {
                key: MemberCondition.from_dict(value)
                for (key, value) in data["related_conditions"].items()
            }

        alerts = {}
        if data.get("alerts"):
            for (condition_type, alert_list) in data["alerts"].items():
                alerts[condition_type] = [
                    Alert.from_dict(alert) for alert in alert_list
                ]

        return PregnancyAndRelatedConditions(
            pregnancy=pregnancy, related_conditions=related_conditions, alerts=alerts
        )

    def to_dict(self) -> dict:
        related_conditions = {}
        if self.related_conditions:
            related_conditions = {
                key: value.to_dict() for key, value in self.related_conditions.items()
            }

        alerts = {}
        if self.alerts:
            for (condition_type, alert_list) in self.alerts.items():
                alerts[condition_type] = [alert.to_dict() for alert in alert_list]

        return {
            "pregnancy": self.pregnancy.to_dict(),
            "related_conditions": related_conditions,
            "alerts": alerts,
        }
