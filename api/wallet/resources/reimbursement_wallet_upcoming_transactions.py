from dataclasses import dataclass
from datetime import datetime
from typing import Dict, List, Optional

from flask import request
from flask_restful import abort

from common.services.api import PermissionedUserResource
from cost_breakdown.models.cost_breakdown import CostBreakdown
from direct_payment.billing import models
from direct_payment.billing.billing_service import BillingService
from direct_payment.billing.models import PayorType
from direct_payment.treatment_procedure.models.treatment_procedure import (
    TreatmentProcedure,
    TreatmentProcedureStatus,
)
from direct_payment.treatment_procedure.repository.treatment_procedure import (
    TreatmentProcedureRepository,
)
from utils.log import logger
from wallet.models.constants import BenefitTypes
from wallet.models.reimbursement_wallet import ReimbursementWallet
from wallet.resources.common import WalletResourceMixin
from wallet.schemas.reimbursement_wallet_upcoming_transaction import (
    ReimbursementWalletUpcomingTransactionRequestSchema,
    ReimbursementWalletUpcomingTransactionResponseSchema,
)

log = logger(__name__)

LIMIT = 100


class UpcomingTransactionRecordAPIException(Exception):
    def __init__(self, error_code, message, **kwargs):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        self.error_code = error_code
        self.message = message
        self.kwargs = kwargs
        super().__init__(self.message)

    def log_and_abort(self) -> None:
        log.error(self.message, **self.kwargs)
        abort(self.error_code, message=self.message)


@dataclass
class UpcomingTransactionRecord:
    __slots__ = (
        "maven_responsibility",
        "status",
        "time",
        "treatment_procedure",
        "bill_uuid",
    )
    maven_responsibility: int
    status: str
    time: datetime
    treatment_procedure: TreatmentProcedure
    bill_uuid: str


class UserReimbursementWalletUpcomingTransactionsResource(
    PermissionedUserResource, WalletResourceMixin
):
    @staticmethod
    def _format_currency_amount(amount_in_cents: int) -> str:
        return f"${amount_in_cents / 100:,.2f}"

    @staticmethod
    def _format_credit_amount(number_of_cycle_credits: int) -> str:
        return f"{number_of_cycle_credits} cycle credits"

    @staticmethod
    def _convert_to_dict(
        upcoming_transaction_record: UpcomingTransactionRecord,
        benefit_type: BenefitTypes,
    ) -> dict:
        maven_responsibility: int = upcoming_transaction_record.maven_responsibility
        treatment_procedure = upcoming_transaction_record.treatment_procedure

        maven_responsibility_str = (
            UserReimbursementWalletUpcomingTransactionsResource._format_currency_amount(
                maven_responsibility
            )
            if benefit_type == BenefitTypes.CURRENCY
            else UserReimbursementWalletUpcomingTransactionsResource._format_credit_amount(
                maven_responsibility
            )
        )

        return {
            "bill_uuid": upcoming_transaction_record.bill_uuid,
            "procedure_uuid": treatment_procedure.uuid,
            "procedure_name": treatment_procedure.procedure_name,
            "procedure_details": f"{treatment_procedure.created_at.strftime('%b %d, %Y')} | Covered by Maven",
            "status": upcoming_transaction_record.status,
            "maven_responsibility": maven_responsibility_str,
        }

    @staticmethod
    def _get_upcoming_transaction_from_scheduled_treatment_procedures(
        treatment_procedures: List[TreatmentProcedure], benefit_type: BenefitTypes
    ) -> List[UpcomingTransactionRecord]:
        cost_breakdown_mapping: Dict[int, TreatmentProcedure] = {
            treatment_procedure.cost_breakdown_id: treatment_procedure
            for treatment_procedure in treatment_procedures
        }

        cost_breakdown_ids = list(cost_breakdown_mapping.keys())
        cost_breakdowns: List[CostBreakdown] = CostBreakdown.query.filter(
            CostBreakdown.id.in_(cost_breakdown_ids)
        ).all()

        def _create_upcoming_transaction_record(
            cost_breakdown: CostBreakdown,
        ) -> Optional[UpcomingTransactionRecord]:
            treatment_procedure: TreatmentProcedure = cost_breakdown_mapping.get(  # type: ignore[assignment] # Incompatible types in assignment (expression has type "Optional[TreatmentProcedure]", variable has type "TreatmentProcedure")
                cost_breakdown.id
            )
            if not treatment_procedure:
                return None

            maven_responsibility = (
                cost_breakdown.total_employer_responsibility
                if benefit_type == BenefitTypes.CURRENCY
                else treatment_procedure.cost_credit
            )

            return UpcomingTransactionRecord(
                maven_responsibility=maven_responsibility,  # type: ignore[arg-type] # Argument "maven_responsibility" to "UpcomingTransactionRecord" has incompatible type "Optional[int]"; expected "int"
                status="NEW",
                time=cost_breakdown.created_at,
                treatment_procedure=treatment_procedure,
                bill_uuid="",
            )

        return [
            upcoming_transaction
            for upcoming_transaction in list(
                map(_create_upcoming_transaction_record, cost_breakdowns)
            )
            if upcoming_transaction is not None
        ]

    @staticmethod
    def _get_upcoming_transactions_from_completed_treatment_procedures(
        treatment_procedures: List[TreatmentProcedure],
        reimbursement_organization_settings_id: int,
        benefit_type: BenefitTypes,
    ) -> List[UpcomingTransactionRecord]:
        billing_service = BillingService()
        treatment_procedure_mapping: Dict[int, TreatmentProcedure] = {
            treatment_procedure.id: treatment_procedure
            for treatment_procedure in treatment_procedures
        }

        bills = billing_service.get_bills_by_procedure_ids(
            procedure_ids=list(treatment_procedure_mapping.keys()),
            payor_type=PayorType.EMPLOYER,
            payor_id=reimbursement_organization_settings_id,
            status=models.UPCOMING_STATUS,
        )

        def _create_upcoming_transaction_record(
            bill: models.Bill,
        ) -> Optional[UpcomingTransactionRecord]:
            treatment_procedure = treatment_procedure_mapping.get(bill.procedure_id)

            if not treatment_procedure:
                return None

            return UpcomingTransactionRecord(
                maven_responsibility=bill.amount  # type: ignore[arg-type] # Argument "maven_responsibility" to "UpcomingTransactionRecord" has incompatible type "Optional[int]"; expected "int"
                if benefit_type == BenefitTypes.CURRENCY
                else treatment_procedure.cost_credit,
                status="PROCESSING",
                time=bill.created_at,  # type: ignore[arg-type] # Argument "time" to "UpcomingTransactionRecord" has incompatible type "Optional[datetime]"; expected "datetime"
                treatment_procedure=treatment_procedure,
                bill_uuid=str(bill.uuid),
            )

        return [
            upcoming_transaction
            for upcoming_transaction in list(
                map(_create_upcoming_transaction_record, bills)
            )
            if upcoming_transaction is not None
        ]

    def get(self, id: int):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        try:
            log.info("Start of UserReimbursementWalletUpcomingTransactionsResource.get")
            self._user_or_404(self.user.id)

            offset = 0
            if request and request.args:
                schema = ReimbursementWalletUpcomingTransactionRequestSchema()
                args = schema.load(request.args).data
                offset = args.get("offset", 0)

            wallet: ReimbursementWallet = self._wallet_or_404(
                user=self.user, wallet_id=id
            )

            _, available_balance, benefit_type = wallet.get_direct_payment_balances()

            if available_balance is None or benefit_type is None:
                raise UpcomingTransactionRecordAPIException(
                    500,
                    "Cannot get available direct payment balance or benefit type",
                    wallet_id=id,
                )

            treatment_procedure_repo = TreatmentProcedureRepository()
            treatment_procedures: List[
                TreatmentProcedure
            ] = treatment_procedure_repo.get_all_treatments_from_wallet_id(id)

            schema = ReimbursementWalletUpcomingTransactionResponseSchema()  # type: ignore[assignment] # Incompatible types in assignment (expression has type "ReimbursementWalletUpcomingTransactionResponseSchema", variable has type "ReimbursementWalletUpcomingTransactionRequestSchema")
            if len(treatment_procedures) == 0:
                log.info("No upcoming transactions", wallet_id=wallet.id)
                return (
                    schema.dump(
                        schema.load(
                            {
                                "limit": LIMIT,
                                "offset": offset,
                                "total": 0,
                                "upcoming": [],
                                "balance_after_upcoming_transactions": "",
                            }
                        )
                    ),
                    200,
                )

            # Get upcoming transactions from SCHEDULED treatment procedures
            scheduled_treatment_procedures = list(
                filter(
                    lambda treatment_procedure: treatment_procedure.status
                    == TreatmentProcedureStatus.SCHEDULED,
                    treatment_procedures,
                )
            )

            upcoming_transactions_from_scheduled_treatment_procedures: List[
                UpcomingTransactionRecord
            ] = self._get_upcoming_transaction_from_scheduled_treatment_procedures(
                scheduled_treatment_procedures, benefit_type
            )

            # Get upcoming transactions from COMPLETED or PARTIALLY_COMPLETED treatment procedures
            completed_treatment_procedures = list(
                filter(
                    lambda treatment_procedure: treatment_procedure.status
                    in (
                        TreatmentProcedureStatus.COMPLETED,
                        TreatmentProcedureStatus.PARTIALLY_COMPLETED,
                    ),
                    treatment_procedures,
                )
            )

            upcoming_transactions_from_completed_treatment_procedures = (
                self._get_upcoming_transactions_from_completed_treatment_procedures(
                    completed_treatment_procedures,
                    wallet.reimbursement_organization_settings_id,
                    benefit_type,
                )
            )

            upcoming_transactions = sorted(
                upcoming_transactions_from_scheduled_treatment_procedures
                + upcoming_transactions_from_completed_treatment_procedures,
                key=lambda upcoming_transaction: upcoming_transaction.time,
            )

            # Apply offer, limit based on the time of the upcoming transactions
            start_index = offset
            end_index = min(offset + LIMIT, len(upcoming_transactions))
            returned_upcoming_transactions = upcoming_transactions[
                start_index:end_index
            ]
            total = len(returned_upcoming_transactions)
            pending_amount = sum(
                upcoming_transaction.maven_responsibility
                for upcoming_transaction in upcoming_transactions_from_scheduled_treatment_procedures
            )

            balance_after_upcoming_transactions: str = (
                self._format_currency_amount(available_balance - pending_amount)
                if benefit_type == BenefitTypes.CURRENCY
                else self._format_credit_amount(available_balance - pending_amount)
            )

            return (
                schema.dump(
                    schema.load(
                        {
                            "limit": LIMIT,
                            "offset": offset,
                            "total": total,
                            "upcoming": list(
                                map(
                                    lambda trx: self._convert_to_dict(
                                        trx, benefit_type
                                    ),
                                    returned_upcoming_transactions,
                                )
                            ),
                            "balance_after_upcoming_transactions": balance_after_upcoming_transactions,
                        }
                    )
                ),
                200,
            )
        except UpcomingTransactionRecordAPIException as e:
            e.log_and_abort()
        except Exception as e:
            error_msg = "Exception thrown"
            log.error(error_msg, error=str(e))
            abort(500, message=error_msg)
