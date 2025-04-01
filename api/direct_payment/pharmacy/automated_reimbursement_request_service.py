from __future__ import annotations

import datetime
import traceback
from typing import List, Optional

from common.global_procedures.constants import UNAUTHENTICATED_PROCEDURE_SERVICE_URL
from common.global_procedures.procedure import ProcedureService
from cost_breakdown.constants import ClaimType, CostBreakdownTriggerSource
from cost_breakdown.cost_breakdown_processor import CostBreakdownProcessor
from cost_breakdown.models.cost_breakdown import CostBreakdown, SystemUser
from cost_breakdown.utils.helpers import get_cycle_based_wallet_balance_from_credit
from cost_breakdown.wallet_balance_reimbursements import (
    should_submit_a_deductible_claim,
    should_submit_this_deductible_claim,
)
from direct_payment.pharmacy.errors import NoReimbursementMethodError, PharmacyException
from direct_payment.pharmacy.models.pharmacy_prescription import PharmacyPrescription
from direct_payment.pharmacy.pharmacy_prescription_service import (
    PharmacyPrescriptionService,
)
from direct_payment.pharmacy.tasks.libs.common import IS_INTEGRATIONS_K8S_CLUSTER
from storage.connection import db
from utils.log import logger
from wallet.models.constants import (
    FERTILITY_EXPENSE_TYPES,
    BenefitTypes,
    ReimbursementMethod,
    ReimbursementRequestAutoProcessing,
    ReimbursementRequestExpenseTypes,
    ReimbursementRequestState,
    WalletUserMemberStatus,
)
from wallet.models.currency import Money
from wallet.models.reimbursement import (
    ReimbursementClaim,
    ReimbursementRequest,
    ReimbursementRequestCategory,
)
from wallet.models.reimbursement_organization_settings import (
    ReimbursementOrgSettingsExpenseType,
)
from wallet.models.reimbursement_wallet import ReimbursementWallet
from wallet.services.currency import DEFAULT_CURRENCY_CODE, CurrencyService
from wallet.services.reimbursement_request import ReimbursementRequestService
from wallet.utils.admin_helpers import FlashMessage, FlashMessageCategory
from wallet.utils.alegeus.claims.create import create_auto_processed_claim_in_alegeus
from wallet.utils.alegeus.claims.sync import WalletClaims, sync_pending_claims
from wallet.utils.events import send_reimbursement_request_state_event

log = logger(__name__)


class AutomatedReimbursementRequestService:
    def __init__(self) -> None:
        self.cost_breakdown_processor = CostBreakdownProcessor(
            procedure_service_client=(
                ProcedureService(base_url=UNAUTHENTICATED_PROCEDURE_SERVICE_URL)
                if IS_INTEGRATIONS_K8S_CLUSTER
                else ProcedureService(internal=True)
            ),
            system_user=SystemUser(
                trigger_source=CostBreakdownTriggerSource.CLINIC.value
            ),
        )
        self.reimbursement_request_service = ReimbursementRequestService(
            session=db.session
        )

    @staticmethod
    def get_reimbursement_request(
        pharmacy_prescription: PharmacyPrescription,
    ) -> ReimbursementRequest | None:
        if pharmacy_prescription.reimbursement_request_id:
            return db.session.query(ReimbursementRequest).get(
                pharmacy_prescription.reimbursement_request_id
            )
        return None

    @staticmethod
    def get_cost_breakdown_from_reimbursement_request(
        reimbursement_request_id: int,
    ) -> Optional[CostBreakdown]:
        """Returns the most recent Cost Breakdown record"""
        return (
            db.session.query(CostBreakdown)
            .filter_by(reimbursement_request_id=reimbursement_request_id)
            .order_by(CostBreakdown.id.desc())
            .first()
        )

    def get_member_status(self, user_id: int, wallet_id: int) -> WalletUserMemberStatus:
        """Returns the user member status - Member or Non Member"""
        return self.reimbursement_request_service.reimbursement_wallets.get_wallet_user_member_status(
            user_id=user_id, wallet_id=wallet_id
        )

    def get_reimbursement_request_cost_breakdown(
        self, reimbursement_request: ReimbursementRequest, user_id: int
    ) -> CostBreakdown:
        """Returns a Cost Breakdown record for the given Reimbursement Request"""
        benefit_type = reimbursement_request.wallet.category_benefit_type(
            request_category_id=reimbursement_request.reimbursement_request_category_id
        )
        wallet_balance_override = self.get_wallet_override(
            reimbursement_request=reimbursement_request, benefit_type=benefit_type
        )
        cost_breakdown = (
            self.cost_breakdown_processor.get_cost_breakdown_for_reimbursement_request(
                reimbursement_request=reimbursement_request,
                user_id=user_id,
                cost_sharing_category=reimbursement_request.cost_sharing_category,
                wallet_balance_override=wallet_balance_override,
            )
        )
        return cost_breakdown

    def create_reimbursement_request(
        self,
        request_params: dict,
        wallet: ReimbursementWallet,
        category: ReimbursementRequestCategory | None,
    ) -> ReimbursementRequest:
        """Creates a Reimbursement Request from params provided and updates the currency amounts."""
        reimbursement_request = ReimbursementRequest(
            wallet=wallet, category=category, **request_params
        )
        updated_reimbursement_request = self.update_reimbursement_request_currency(
            reimbursement_request=reimbursement_request, amount=request_params["amount"]
        )
        return updated_reimbursement_request

    @staticmethod
    def update_reimbursement_request_from_cost_breakdown(
        cost_breakdown: CostBreakdown, reimbursement_request: ReimbursementRequest
    ) -> ReimbursementRequest:
        """Given a Cost Breakdown this updates the Reimbursement Request state and amount based off of the
        total member/employer responsibilities.
        """
        if reimbursement_request.amount == cost_breakdown.total_member_responsibility:
            reimbursement_request.state = ReimbursementRequestState.DENIED  # type: ignore[assignment]

        elif (
            reimbursement_request.amount == cost_breakdown.total_employer_responsibility
        ):
            reimbursement_request.state = ReimbursementRequestState.APPROVED  # type: ignore[assignment]

        else:
            reimbursement_request.amount = cost_breakdown.total_employer_responsibility

            reimbursement_request.transaction_amount = (
                cost_breakdown.total_employer_responsibility
            )
            reimbursement_request.usd_amount = (
                cost_breakdown.total_employer_responsibility
            )
            reimbursement_request.state = ReimbursementRequestState.APPROVED  # type: ignore[assignment]

        return reimbursement_request

    @staticmethod
    def get_wallet_override(
        reimbursement_request: ReimbursementRequest,
        benefit_type: Optional[BenefitTypes],
    ) -> Optional[int]:
        """Provides the wallet override amount for cycle-based wallets"""
        wallet_balance_override = None
        if benefit_type == BenefitTypes.CYCLE:
            if reimbursement_request.cost_credit is None:
                raise ValueError(
                    "A cost credit value is required for the reimbursement request "
                    "to calculate this cost breakdown, because it is on a cycle-based wallet."
                )
            wallet_balance_override = get_cycle_based_wallet_balance_from_credit(
                wallet=reimbursement_request.wallet,
                category_id=reimbursement_request.reimbursement_request_category_id,
                cost_credit=reimbursement_request.cost_credit,
                cost=reimbursement_request.amount,
            )
            log.info(
                "Wallet Balance Override",
                wallet_balance_override=wallet_balance_override,
                wallet_id=str(reimbursement_request.wallet.id),
            )
        return wallet_balance_override

    @staticmethod
    def update_reimbursement_request_currency(
        reimbursement_request: ReimbursementRequest, amount: int
    ) -> ReimbursementRequest:
        """Helper method that updates the Reimbursement Request currency fields."""
        currency_service = CurrencyService()
        transaction: Money = currency_service.to_money(
            amount=amount, currency_code=DEFAULT_CURRENCY_CODE
        )
        reimbursement_request = currency_service.process_reimbursement_request(
            transaction=transaction, request=reimbursement_request
        )
        return reimbursement_request

    @staticmethod
    def should_submit_dtr_claim(
        reimbursement_request: ReimbursementRequest,
        cost_breakdown: CostBreakdown,
    ) -> bool:
        """
        Determines whether a Deductible Tracking Plan (DTR) claim should be submitted
        to Alegeus for a member with a High Deductible Health Plan (HDHP). This method
        applies to members with non-deductible accumulation settings and a deductible greater than 0.
        """
        should_submit_deductible = should_submit_a_deductible_claim(
            user_id=reimbursement_request.person_receiving_service_id,
            wallet=reimbursement_request.wallet,
            effective_date=reimbursement_request.service_start_date,
        )
        if should_submit_deductible:
            # At this point, if there is a claim it will always be DTR so don't resubmit
            if reimbursement_request.claims:
                return False
            return should_submit_this_deductible_claim(
                deductible=cost_breakdown.deductible
            )
        return False

    @staticmethod
    def should_submit_hra_claim(
        reimbursement_request: ReimbursementRequest,
        cost_breakdown: CostBreakdown,
    ) -> bool:
        """
        Determines whether a Health Reimbursement Arrangement (HRA) claim should be
        submitted to Alegeus based on the reimbursement request and the employer's
        financial responsibility. This is the plan that maps to Alegeus to know where to reimburse the member from
        """
        return (
            reimbursement_request.state == ReimbursementRequestState.APPROVED
            and cost_breakdown.total_employer_responsibility > 0
        )

    @staticmethod
    def should_accumulate_automated_rx_reimbursement_request(
        reimbursement_request: ReimbursementRequest, cost_breakdown: CostBreakdown
    ) -> bool:
        """
        Create an accumulation mapping if deductible accumulation is enabled and member paid for some or all of the
        RX cost.
        """
        return (
            reimbursement_request.wallet.reimbursement_organization_settings.deductible_accumulation_enabled
            and cost_breakdown.total_member_responsibility > 0
        )

    @staticmethod
    def get_reimbursement_method(
        wallet: ReimbursementWallet,
        expense_type: ReimbursementRequestExpenseTypes | None,
    ) -> ReimbursementMethod:
        """Determines the Reimbursement Method for wallet to send to Alegeus based on org settings."""
        org_settings = wallet.reimbursement_organization_settings
        if expense_type:
            org_settings_expense_type = (
                ReimbursementOrgSettingsExpenseType.query.filter_by(
                    reimbursement_organization_settings_id=org_settings.id,
                    expense_type=expense_type,
                ).one_or_none()
            )
            if (
                org_settings_expense_type
                and org_settings_expense_type.reimbursement_method
            ):
                return org_settings_expense_type.reimbursement_method

        if wallet.reimbursement_method:
            return wallet.reimbursement_method  # type: ignore[return-value]
        else:
            log.error(
                "Could not find a ReimbursementOrgSettingsExpenseType.",
                wallet_id=str(wallet.id),
                org_settings_id=str(org_settings.id),
            )
            raise NoReimbursementMethodError(
                "Missing ReimbursementOrgSettingsExpenseType for reimbursement method."
            )

    @staticmethod
    def reset_reimbursement_request(
        reimbursement_request: ReimbursementRequest,
        original_amount: int,
        cost_breakdown: CostBreakdown | None,
    ) -> None:
        """Helper method that resets the Reimbursement Request back to the NEW state"""
        reimbursement_request.state = ReimbursementRequestState.NEW  # type: ignore[assignment]
        reimbursement_request.amount = original_amount
        reimbursement_request.transaction_amount = original_amount
        reimbursement_request.usd_amount = original_amount

        db.session.add(reimbursement_request)
        if cost_breakdown:
            db.session.delete(cost_breakdown)

        db.session.commit()
        log.error(
            "Reset Reimbursement Request back to original state due to failure.",
            reimbursement_request=str(reimbursement_request.id),
            wallet_id=str(reimbursement_request.wallet.id),
        )

    def submit_auto_processed_request_to_alegeus(
        self,
        reimbursement_request: ReimbursementRequest,
        wallet: ReimbursementWallet,
        cost_breakdown: CostBreakdown,
        reimbursement_method: ReimbursementMethod,
    ) -> List:
        """
        Submits an auto-processed reimbursement request to Alegeus.
        This method updates the reimbursement request based on the provided cost breakdown
        and commits the changes to the database. It checks if claims
        already exist and either syncs pending claims or submits new ones.
        """
        messages = []
        try:
            reimbursement_request = (
                self.update_reimbursement_request_from_cost_breakdown(
                    cost_breakdown=cost_breakdown,
                    reimbursement_request=reimbursement_request,
                )
            )
            db.session.add(reimbursement_request)
            db.session.commit()
            log.info(
                "Updating a reimbursement request from the cost breakdown.",
                reimbursement_request_id=str(reimbursement_request.id),
                updated_amount=reimbursement_request.transaction_amount,
                updated_state=reimbursement_request.state,
            )
        except Exception as e:
            log.error(
                "Failed to update Reimbursement Request from Cost Breakdown.",
                reimbursement_request_id=str(reimbursement_request.id),
                cost_breakdown_id=str(cost_breakdown.id),
                error_message=str(e),
                traceback=traceback.format_exc(),
            )
            raise PharmacyException(
                "Failed to persist cost breakdown or reimbursement reqeust into database."
            )

        original_state = reimbursement_request.state
        if reimbursement_request.claims:
            claim_ids = [claim.id for claim in reimbursement_request.claims]

            wallet_to_claim = WalletClaims(
                wallet=wallet,
                claims=reimbursement_request.claims,
            )
            sync_pending_claims([wallet_to_claim])
            db.session.expire(reimbursement_request)

            claims_after_sync = ReimbursementClaim.query.filter(
                ReimbursementClaim.id.in_(claim_ids)
            ).all()

            # determine how many claims the request should have
            total_claims_to_submit = self._total_claims_to_submit(
                reimbursement_request=reimbursement_request,
                cost_breakdown=cost_breakdown,
            )
            if claims_after_sync and len(claims_after_sync) == total_claims_to_submit:
                messages.append(
                    FlashMessage(
                        message="Claims have already been submitted to Alegeus for this Reimbursement Request",
                        category=FlashMessageCategory.INFO,
                    )
                )
            else:
                # If the Claim is removed during the sync, ReimbursementRequestState is set back to NEW
                # Setting state back to the original state to continue submitting Claim to Alegeus
                reimbursement_request.state = original_state
                self._submit_auto_processed_claims_to_alegeus(
                    cost_breakdown=cost_breakdown,
                    reimbursement_request=reimbursement_request,
                    reimbursement_method=reimbursement_method,
                )
        else:
            messages.append(
                FlashMessage(
                    message="Attempting to submit new Claim in Alegeus for this Reimbursement Request",
                    category=FlashMessageCategory.INFO,
                )
            )
            self._submit_auto_processed_claims_to_alegeus(
                cost_breakdown=cost_breakdown,
                reimbursement_request=reimbursement_request,
                reimbursement_method=reimbursement_method,
            )

        messages.append(
            FlashMessage(
                message="Successfully processed auto-processed RX claim(s) to Alegeus for this Reimbursement Request.",
                category=FlashMessageCategory.SUCCESS,
            )
        )
        send_reimbursement_request_state_event(reimbursement_request)
        return messages

    @staticmethod
    def _get_requests_to_process(
        should_submit_dtr: bool,
        should_submit_hra: bool,
        reimbursement_request: ReimbursementRequest,
        reimbursement_method: ReimbursementMethod,
    ) -> List:
        """Collects the reimbursement requests to process based on eligibility."""
        requests_to_process = []
        if should_submit_dtr:
            # We don't want DTR requests to be reimbursed so to be sure we're setting the Reimbursement Method to 0
            requests_to_process.append(
                (reimbursement_request, ClaimType.EMPLOYEE_DEDUCTIBLE, None)
            )
        if should_submit_hra:
            requests_to_process.append(
                (reimbursement_request, ClaimType.EMPLOYER, reimbursement_method)  # type: ignore[arg-type]
            )
        log.info(
            "Auto-processed reimbursement request to process",
            reimbursement_request_id=str(reimbursement_request.id),
            submit_hra=should_submit_hra,
            submit_dtr=should_submit_dtr,
        )
        return requests_to_process

    @staticmethod
    def return_category_expense_type(
        category: ReimbursementRequestCategory | None,
    ) -> ReimbursementRequestExpenseTypes | None:
        """
        Returns the first overlapping fertility expense type from the given category's expense types.
        """
        if category:
            overlapping_fertility_expense_types = set(category.expense_types) & set(
                FERTILITY_EXPENSE_TYPES
            )
            if overlapping_fertility_expense_types:
                if (
                    ReimbursementRequestExpenseTypes.FERTILITY
                    in overlapping_fertility_expense_types
                ):
                    return ReimbursementRequestExpenseTypes.FERTILITY
                else:
                    return list(overlapping_fertility_expense_types)[
                        0
                    ]  # Return the first matching type
        return None

    def _submit_auto_processed_claims_to_alegeus(
        self,
        cost_breakdown: CostBreakdown,
        reimbursement_request: ReimbursementRequest,
        reimbursement_method: ReimbursementMethod,
    ) -> None:
        """Processes and submits the claims to Alegeus."""
        should_submit_dtr = self.should_submit_dtr_claim(
            reimbursement_request=reimbursement_request, cost_breakdown=cost_breakdown
        )
        should_submit_hra = self.should_submit_hra_claim(
            reimbursement_request=reimbursement_request, cost_breakdown=cost_breakdown
        )
        requests_to_process = self._get_requests_to_process(
            reimbursement_request=reimbursement_request,
            reimbursement_method=reimbursement_method,
            should_submit_dtr=should_submit_dtr,
            should_submit_hra=should_submit_hra,
        )

        for request, claim_type, method in requests_to_process:
            wallet = request.wallet
            # If HDHP plan we only want to send a claim for the DTR amount not any overages from wallet balance
            reimbursement_amount = (
                cost_breakdown.deductible
                if claim_type == ClaimType.EMPLOYEE_DEDUCTIBLE
                else reimbursement_request.usd_reimbursement_amount
            )
            create_auto_processed_claim_in_alegeus(
                wallet=wallet,
                reimbursement_request=request,
                reimbursement_amount=reimbursement_amount,
                claim_type=claim_type,
                reimbursement_mode=method,
            )
            log.info(
                "Successfully sent auto-approved rx claims to Alegeus",
                cost_breakdown_id=str(cost_breakdown.id),
                wallet_id=str(wallet.id),
                claim_type=claim_type.name,
                reimbursement_request=str(request.id),
            )

    @staticmethod
    def check_for_duplicate_automated_rx_reimbursement(
        reimbursement_request: ReimbursementRequest,
        auto_processed: Optional[ReimbursementRequestAutoProcessing] = None,
    ) -> list:
        results = []
        # Expected fields
        duplicate_rr_query = ReimbursementRequest.query.filter_by(
            reimbursement_wallet_id=reimbursement_request.reimbursement_wallet_id,
            person_receiving_service=reimbursement_request.person_receiving_service,
            person_receiving_service_id=reimbursement_request.person_receiving_service_id,
            reimbursement_request_category_id=reimbursement_request.reimbursement_request_category_id,
            auto_processed=auto_processed,
        )
        # datetime filter to cover the entire date
        date_min = datetime.datetime.combine(
            reimbursement_request.service_start_date.date()
            - datetime.timedelta(days=60),
            datetime.time.min,
        )
        date_max = datetime.datetime.combine(
            reimbursement_request.service_start_date.date(), datetime.time.max
        )
        duplicate_rr_query = duplicate_rr_query.filter(
            ReimbursementRequest.service_start_date >= date_min,
            ReimbursementRequest.service_start_date <= date_max,
            ReimbursementRequest.id != str(reimbursement_request.id),
            ReimbursementRequest.service_provider.ilike("%SMP%"),
        )
        duplicate_rr = duplicate_rr_query.all()
        duplicate_ids = [rr.id for rr in duplicate_rr]
        # If we're looking for auto reimbursed RRs, check for associated pharmacy prescriptions
        # Otherwise return all duplicates found
        if auto_processed == ReimbursementRequestAutoProcessing.RX:
            pharmacy_prescription_service = PharmacyPrescriptionService(
                session=db.session
            )
            prescriptions = (
                pharmacy_prescription_service.get_by_reimbursement_request_ids(
                    duplicate_ids
                )
            )
            if prescriptions:
                results = duplicate_ids
        else:
            results = duplicate_ids

        if results:
            log.info(
                f"Duplicate reimbursement request found for wallet {reimbursement_request.reimbursement_wallet_id}: "
                f"ids: {results} "
            )
        return results

    def _total_claims_to_submit(
        self, reimbursement_request: ReimbursementRequest, cost_breakdown: CostBreakdown
    ) -> int:
        """Determines the number of expected claims to submit for a given Reimbursement Request"""
        should_submit_deductible = should_submit_a_deductible_claim(
            user_id=reimbursement_request.person_receiving_service_id,
            wallet=reimbursement_request.wallet,
            effective_date=reimbursement_request.service_start_date,
        ) and should_submit_this_deductible_claim(deductible=cost_breakdown.deductible)
        if should_submit_deductible:
            return 2
        if self.should_submit_hra_claim(
            reimbursement_request=reimbursement_request, cost_breakdown=cost_breakdown
        ):
            return 1
        return 0
