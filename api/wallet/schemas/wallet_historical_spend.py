from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class WalletHistoricalSpendPostRequest:
    __slots__ = ("reimbursement_organization_settings_id", "file_id")
    reimbursement_organization_settings_id: str
    file_id: str

    @classmethod
    def from_dict(cls, data: dict) -> "WalletHistoricalSpendPostRequest":
        return cls(**data)
