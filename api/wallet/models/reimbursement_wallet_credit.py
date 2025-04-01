from __future__ import annotations

import datetime
from typing import Optional

from sqlalchemy import BigInteger, Column, ForeignKey, Integer
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import relationship

from common import stats
from common.global_procedures.procedure import GlobalProcedure
from models.base import TimeLoggedSnowflakeModelBase, db
from utils.log import logger
from wallet.models.constants import ReimbursementRequestType
from wallet.models.reimbursement import ReimbursementRequest
from wallet.models.reimbursement_wallet_credit_transaction import (
    ReimbursementCycleMemberCreditTransaction,
)

log = logger(__name__)

METRIC_NAME = "api.wallet.models.reimbursement_wallet_credit"


class ReimbursementCycleCredits(TimeLoggedSnowflakeModelBase):
    __tablename__ = "reimbursement_cycle_credits"

    reimbursement_wallet_id = Column(
        BigInteger, ForeignKey("reimbursement_wallet.id"), nullable=False
    )
    reimbursement_organization_settings_allowed_category_id = Column(
        BigInteger,
        ForeignKey("reimbursement_organization_settings_allowed_category.id"),
        nullable=False,
    )
    amount = Column(
        Integer,
        nullable=False,
        doc="Amount of credits available per category per wallet.",
    )

    reimbursement_wallet = relationship("ReimbursementWallet", backref="cycle_credits")
    reimbursement_organization_settings_allowed_category = relationship(
        "ReimbursementOrgSettingCategoryAssociation"
    )
    transactions = relationship(
        ReimbursementCycleMemberCreditTransaction,
        primaryjoin="ReimbursementCycleMemberCreditTransaction.reimbursement_cycle_credits_id==ReimbursementCycleCredits.id",
    )

    def __repr__(self) -> str:
        return f"<ReimbursementCycleCredit={self.amount} ReimbursementWallet={self.reimbursement_wallet_id}>"

    def edit_credit_balance(
        self,
        amount: int,
        reimbursement_request_id: int | None = None,
        global_procedures_id: str | None = None,
        notes: str | None = None,
    ) -> int:
        if amount is None:
            raise ValueError("No Transaction Amount Specified")
        if self.amount + amount < 0:
            raise ValueError("Cycle Credit Balance cannot be negative")

        if reimbursement_request_id:
            rr = ReimbursementRequest.query.get(reimbursement_request_id)
            if not rr:
                raise ValueError("Invalid Reimbursement Request ID - Not found")
            if not rr or rr.reimbursement_wallet_id != self.reimbursement_wallet_id:
                raise ValueError(
                    "Invalid Reimbursement Request ID - Reimbursement Request wallet_id doesn't match this wallet"
                )
            if (
                rr.reimbursement_request_category_id
                != self.reimbursement_organization_settings_allowed_category.reimbursement_request_category_id
            ):
                raise ValueError(
                    "Invalid Reimbursement Request ID - Reimbursement Request category_id doesn't match this allowed category"
                )
        # TODO re-add global_procedure_id after type migration
        transaction = ReimbursementCycleMemberCreditTransaction(
            amount=amount,
            reimbursement_cycle_credits_id=self.id,
            reimbursement_request_id=reimbursement_request_id,
            # global_procedures_id=global_procedures_id,
            notes=notes,
            created_at=datetime.datetime.now(),  # noqa
        )
        self.amount += amount
        try:
            db.session.add(transaction)
            db.session.add(self)
            db.session.commit()
            log.info(
                "Cycle based credit update successful",
                cycle_credits_id=self.id,
                reimbursement_request_id=reimbursement_request_id,
                global_procedures_id=global_procedures_id,
                transaction_id=transaction.id,
            )
            stats.increment(
                metric_name=f"{METRIC_NAME}.edit_credit_balance",
                pod_name=stats.PodNames.BENEFITS_EXP,
                tags=["success:true"],
            )
        except SQLAlchemyError as e:
            log.error(
                "Cycle based credit update failed",
                cycle_credits_id=self.id,
                reimbursement_request_id=reimbursement_request_id,
                global_procedures_id=global_procedures_id,
                error=e,
            )
            db.session.rollback()
            stats.increment(
                metric_name=f"{METRIC_NAME}.edit_credit_balance",
                pod_name=stats.PodNames.BENEFITS_EXP,
                tags=["success:false", "reason:create_credit_transaction"],
            )
            raise e

        return self.amount

    def deduct_credits_for_reimbursement_and_procedure(
        self,
        reimbursement_request: Optional[ReimbursementRequest],
        global_procedure: GlobalProcedure,
        treatment_procedure_cost: int,
    ) -> int:
        if not reimbursement_request or not global_procedure:
            raise ValueError("Invalid reimbursement request or global procedure")

        # Allow for usage of partial credits if we don't have enough for the entire procedure
        amount = min(treatment_procedure_cost, self.amount) * -1
        log.info(
            "Editing Credit Balance in the calculate_cost_breakdown workflow",
            num_credits=str(amount),
            reimbursement_request_id=str(reimbursement_request.id),
            global_procedures_id=str(global_procedure["id"]),
        )
        return self.edit_credit_balance(
            amount,
            reimbursement_request_id=reimbursement_request.id,
            global_procedures_id=global_procedure["id"],
        )

    def add_back_credits_for_reimbursement_and_procedure(
        self,
        reimbursement_request: ReimbursementRequest,
    ) -> int:
        """
        Function to add back credits for completed/partially completed treatment procedure,
        it takes the employer reimbursement request, find its corresponding cycle credit transaction,
        and create a new row with negative amount.
        """
        transactions = ReimbursementCycleMemberCreditTransaction.query.filter(
            ReimbursementCycleMemberCreditTransaction.reimbursement_request_id
            == reimbursement_request.id
        ).all()
        if len(transactions) != 1:
            raise ValueError(
                "The reimbursement request has multiple credit transactions"
            )
        transaction = transactions[0]
        if transaction.amount > 0:
            raise ValueError("Cycle based transaction has been refunded before")
        if transaction.amount == 0:
            return self.amount

        return self.edit_credit_balance(
            amount=-1 * transaction.amount,
            reimbursement_request_id=transaction.reimbursement_request_id,
            notes=f"Refund for transaction {transaction.id}",
        )

    def deduct_credits_for_manual_reimbursement(
        self,
        reimbursement_request: ReimbursementRequest,
    ) -> int:
        if not reimbursement_request:
            raise ValueError("Invalid reimbursement request")

        if reimbursement_request.reimbursement_type != ReimbursementRequestType.MANUAL:
            raise ValueError("Reimbursement request is not manual")

        if reimbursement_request.cost_credit is None:
            raise ValueError("Reimbursement request missing credit cost")

        # Allow for usage of partial credits if there isn't enough
        amount = min(reimbursement_request.cost_credit, self.amount) * -1

        return self.edit_credit_balance(
            amount,
            reimbursement_request_id=reimbursement_request.id,
        )
