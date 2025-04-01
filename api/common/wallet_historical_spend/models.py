from __future__ import annotations

import dataclasses
import datetime
from dataclasses import dataclass
from traceback import format_exc
from typing import Dict, List, Optional

from utils.log import logger
from wallet.models.reimbursement_wallet import ReimbursementWallet

log = logger(__name__)


@dataclass
class Adjustment:
    balance_id: str
    wallet_id: str
    user_id: str
    value: int
    is_currency: bool
    reimbursement_request_id: str | None = None

    @classmethod
    def create_adjustment_dict(
        cls,
        entry: LedgerEntry,
        wallet: ReimbursementWallet,
        is_currency: bool,
        value: int,
        reimbursement_request_id: str | None = None,
    ) -> dict:
        adjustment = cls(
            balance_id=entry.balance_id,
            wallet_id=str(wallet.id),
            user_id=str(wallet.user_id),
            value=value,
            is_currency=is_currency,
            reimbursement_request_id=reimbursement_request_id,
        )
        return adjustment.to_dict()

    def to_dict(self) -> dict:
        return dataclasses.asdict(self)


@dataclass
class LedgerEntry:
    id: str
    configuration_id: str
    reimbursement_organization_settings_id: str
    employee_id: str
    first_name: str
    last_name: str
    date_of_birth: str
    calculated_spend: int
    calculated_cycles: int
    category: str
    balance_id: str
    file_id: str
    most_recent_auth_date: datetime.date
    created_at: datetime.datetime
    historical_spend: int
    historical_cycles_used: int
    service_date: Optional[str]
    adjustment_id: Optional[str]
    dependent_first_name: Optional[str]
    dependent_last_name: Optional[str]
    dependent_date_of_birth: Optional[str]
    dependent_id: Optional[str]
    subscriber_id: Optional[str]

    @classmethod
    def create_ledger_entries_from_dict(
        cls, input_list: List[Dict]
    ) -> List[LedgerEntry]:
        required_fields = [
            "id",
            "configuration_id",
            "reimbursement_organization_settings_id",
            "employee_id",
            "first_name",
            "last_name",
            "date_of_birth",
            "calculated_spend",
            "calculated_cycles",
            "category",
            "balance_id",
            "file_id",
            "most_recent_auth_date",
            "historical_spend",
            "historical_cycles_used",
            "created_at",
        ]
        entries = []
        for entry in input_list:
            missing_fields = [field for field in required_fields if field not in entry]
            try:
                if missing_fields:
                    log.error(
                        "Missing required response fields.",
                        missing_fields=missing_fields,
                        entry_id=entry.get("id"),
                        file_id=entry.get("file_id"),
                    )
                    raise ValueError(
                        f"Missing required fields: {', '.join(missing_fields)}"
                    )
                entries.append(
                    LedgerEntry(
                        id=entry["id"],
                        configuration_id=entry["configuration_id"],
                        reimbursement_organization_settings_id=entry[
                            "reimbursement_organization_settings_id"
                        ],
                        employee_id=entry["employee_id"],
                        first_name=entry["first_name"],  # type: ignore[arg-type]
                        last_name=entry["last_name"],  # type: ignore[arg-type]
                        date_of_birth=entry["date_of_birth"],  # type: ignore[arg-type]
                        calculated_spend=entry["calculated_spend"],
                        calculated_cycles=entry["calculated_cycles"],
                        historical_spend=entry["historical_spend"],
                        historical_cycles_used=entry["historical_cycles_used"],
                        category=entry["category"],
                        balance_id=entry["balance_id"],
                        file_id=entry["file_id"],
                        service_date=entry.get("service_date"),
                        most_recent_auth_date=format_date(entry["most_recent_auth_date"]),  # type: ignore[arg-type]
                        adjustment_id=entry.get("adjustment_id"),
                        dependent_first_name=entry.get("dependent_first_name"),
                        dependent_last_name=entry.get("dependent_last_name"),
                        dependent_date_of_birth=entry.get("dependent_date_of_birth"),
                        dependent_id=entry.get("dependent_id"),
                        subscriber_id=entry.get("subscriber_id"),
                        created_at=format_datetime(entry["created_at"]),  # type: ignore[arg-type]
                    )
                )
            except (KeyError, ValueError):
                log.exception(
                    "Exception creating Ledger entry from response.",
                    ledger_entry_id=entry.get("id"),
                    reason=format_exc(),
                )
        return entries


def format_date(date_str: Optional[str]) -> Optional[datetime.date]:
    """Convert a string to a date object if provided."""
    if date_str:
        return datetime.date.fromisoformat(date_str)
    return None


def format_datetime(date_str: Optional[str]) -> Optional[datetime.date]:
    """Convert a string to a datetime object if provided."""
    if date_str:
        return datetime.datetime.fromisoformat(date_str)
    return None
