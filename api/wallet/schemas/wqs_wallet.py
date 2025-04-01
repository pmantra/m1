from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from wallet.models.constants import (
    ReimbursementRequestExpenseTypes,
    WalletState,
    WalletUserStatus,
    WalletUserType,
)


@dataclass(frozen=True)
class WQSWalletPOSTRequest:
    __slots__ = (
        "reimbursement_organization_settings_id",
        "state",
        "wallet_user_status",
        "wallet_user_type",
        "primary_expense_type",
        "is_inside_the_usa",
        "dependent_first_name",
        "dependent_last_name",
    )
    reimbursement_organization_settings_id: str
    state: WalletState
    wallet_user_status: WalletUserStatus
    wallet_user_type: WalletUserType
    primary_expense_type: Optional[ReimbursementRequestExpenseTypes]
    is_inside_the_usa: Optional[bool]
    dependent_first_name: Optional[str]
    dependent_last_name: Optional[str]

    @staticmethod
    def from_request(request: dict) -> WQSWalletPOSTRequest:
        state = WalletState(request["state"])
        wallet_user_type = WalletUserType(request["wallet_user_type"])
        wallet_user_status = WalletUserStatus(request["wallet_user_status"])

        primary_expense_type: Optional[ReimbursementRequestExpenseTypes] = (
            ReimbursementRequestExpenseTypes[request["primary_expense_type"]]
            if request.get("primary_expense_type") is not None
            else None
        )

        is_inside_the_usa: Optional[bool] = (
            request["is_inside_the_usa"]
            if request.get("is_inside_the_usa") is not None
            else None
        )

        return WQSWalletPOSTRequest(
            reimbursement_organization_settings_id=str(
                request["reimbursement_organization_settings_id"]
            ),
            state=state,
            wallet_user_type=wallet_user_type,
            wallet_user_status=wallet_user_status,
            primary_expense_type=primary_expense_type,
            is_inside_the_usa=is_inside_the_usa,
            dependent_first_name=request.get("dependent_first_name"),
            dependent_last_name=request.get("dependent_last_name"),
        )


@dataclass(frozen=True)
class WQSWalletPUTRequest:
    __slots__ = (
        "state",
        "wallet_user_status",
        "wallet_user_type",
        "primary_expense_type",
        "is_inside_the_usa",
        "dependent_first_name",
        "dependent_last_name",
    )

    state: WalletState
    wallet_user_status: WalletUserStatus
    wallet_user_type: WalletUserType
    primary_expense_type: ReimbursementRequestExpenseTypes | None
    is_inside_the_usa: bool | None
    dependent_first_name: str | None
    dependent_last_name: str | None

    @staticmethod
    def from_request(request: dict) -> WQSWalletPUTRequest:
        state_str: str = request.get("state", "")
        wallet_user_status_str: str = request.get("wallet_user_status", "")
        wallet_user_type_str = request.get(
            "wallet_user_type", WalletUserType.DEPENDENT.value
        )
        primary_expense_type: Optional[ReimbursementRequestExpenseTypes] = (
            ReimbursementRequestExpenseTypes[request["primary_expense_type"]]
            if request.get("primary_expense_type") is not None
            else None
        )

        is_inside_the_usa: bool | None = request.get("is_inside_the_usa")

        return WQSWalletPUTRequest(
            state=WalletState(state_str),
            wallet_user_status=WalletUserStatus(wallet_user_status_str),
            wallet_user_type=WalletUserType(wallet_user_type_str),
            primary_expense_type=primary_expense_type,
            is_inside_the_usa=is_inside_the_usa,
            dependent_first_name=request.get("dependent_first_name"),
            dependent_last_name=request.get("dependent_last_name"),
        )
