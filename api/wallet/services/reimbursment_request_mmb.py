from typing import List, Optional

from sqlalchemy.orm import joinedload

from cost_breakdown.models.cost_breakdown import CostBreakdown
from utils.log import logger
from wallet.models.constants import ReimbursementRequestState, ReimbursementRequestType
from wallet.models.reimbursement import (
    ReimbursementRequest,
    ReimbursementRequestCategory,
)
from wallet.models.reimbursement_wallet import ReimbursementWallet
from wallet.utils.admin_helpers import FlashMessage

log = logger(__name__)


class ReimbursementRequestMMBService:
    def is_mmb(self, reimbursement_request: ReimbursementRequest) -> bool:
        """
        True if a reimbursement request belongs to an MMB-enabled organization.
        """
        org_setting = reimbursement_request.wallet.reimbursement_organization_settings
        return org_setting.direct_payment_enabled

    def update_request_for_cost_breakdown(
        self, reimbursement_request: ReimbursementRequest, cost_breakdown: CostBreakdown
    ) -> ReimbursementRequest:
        """
        Apply changes to a reimbursement request's amount and state based on cost breakdown data.
        Should run when a cost breakdown is saved for a reimbursement request.
        """
        is_deductible_accumulation = (
            reimbursement_request.wallet.reimbursement_organization_settings.deductible_accumulation_enabled
        )
        log.info(
            "Updating a reimbursement request from the cost breakdown.",
            is_deductible_accumulation=is_deductible_accumulation,
            original_state=reimbursement_request.state,
            original_amount=reimbursement_request.amount,
        )
        # If member responsibility is 100% of the amount,
        if reimbursement_request.amount == cost_breakdown.total_member_responsibility:
            log.info("Member Responsibility equals the Reimbursement Request Amount")
            if is_deductible_accumulation:
                reimbursement_request.state = ReimbursementRequestState.DENIED  # type: ignore[assignment] # Incompatible types in assignment (expression has type "ReimbursementRequestState", variable has type "str")
                # An accumulation mapping should be added
                # via AccumulationMappingService.should_accumulate_reimbursement_request_pre_approval
            else:
                reimbursement_request.state = ReimbursementRequestState.PENDING  # type: ignore[assignment] # Incompatible types in assignment (expression has type "ReimbursementRequestState", variable has type "str")
                # An accumulation mapping will be added after Peak One approves and the RR is updated to DENIED
        # if employer responsibility is 100% of the amount, business as usual.
        elif (
            reimbursement_request.amount == cost_breakdown.total_employer_responsibility
        ):
            log.info("Employer Responsibility equals the Reimbursement Request Amount")
            reimbursement_request.state = ReimbursementRequestState.PENDING  # type: ignore[assignment] # Incompatible types in assignment (expression has type "ReimbursementRequestState", variable has type "str")
            # There is nothing to accumulate here as there is no member payment.
        # If member responsibility is some of the amount,
        else:
            log.info("Neither Responsibility equals the Reimbursement Request Amount")
            if is_deductible_accumulation:
                reimbursement_request.state = ReimbursementRequestState.PENDING  # type: ignore[assignment] # Incompatible types in assignment (expression has type "ReimbursementRequestState", variable has type "str")
                reimbursement_request.amount = (
                    cost_breakdown.total_employer_responsibility
                )
                reimbursement_request.transaction_amount = (
                    cost_breakdown.total_employer_responsibility
                )
                reimbursement_request.usd_amount = (
                    cost_breakdown.total_employer_responsibility
                )
                # An accumulation mapping will be added after Peak One approves and the RR is updated to APPROVED
            else:
                reimbursement_request.state = ReimbursementRequestState.PENDING  # type: ignore[assignment] # Incompatible types in assignment (expression has type "ReimbursementRequestState", variable has type "str")
                # This will be set to DENIED after Peak One approves, but will not be accumulated
        log.info(
            "Updating a reimbursement request from the cost breakdown.",
            is_deductible_accumulation=is_deductible_accumulation,
            new_state=reimbursement_request.state,
            new_amount=reimbursement_request.amount,
        )
        return reimbursement_request

    def get_related_requests_missing_cost_breakdowns(
        self, reimbursement_request: ReimbursementRequest
    ) -> List[ReimbursementRequest]:
        """
        Find any past reimbursement requests without a cost breakdown that should be impacting this request.
        """
        return (
            ReimbursementRequest.query.join(
                ReimbursementRequest.wallet,
            )
            .join(
                CostBreakdown,
                CostBreakdown.reimbursement_request_id == ReimbursementRequest.id,
                isouter=True,
            )
            .filter(
                # Only manual RRs should have cost breakdowns with this relationship type
                ReimbursementRequest.reimbursement_type
                == ReimbursementRequestType.MANUAL,
                # We're only interested in other RRs on this wallet
                ReimbursementWallet.id == reimbursement_request.reimbursement_wallet_id,
                # They should be past reimbursement requests
                # Note: If we change how sequential payments work, also change this
                ReimbursementRequest.service_start_date
                <= reimbursement_request.service_start_date,
                # They should be missing a cost breakdown
                CostBreakdown.id.is_(None),
                ReimbursementRequest.id != reimbursement_request.id,
            )
            .options(
                joinedload(ReimbursementRequest.category).options(
                    joinedload(ReimbursementRequestCategory.category_expense_types)
                )
            )
            .all()
        )

    @staticmethod
    def handle_messages_for_state_change(messages: Optional[List[FlashMessage]]) -> str:
        """
        Takes input from handle_reimbursement_request_state_change. Returns a single combined message.
        """
        if messages:
            return "<br />".join(
                message.message if message.message is not None else ""
                for message in messages
            )
        return ""
