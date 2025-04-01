from __future__ import annotations

from ddtrace import tracer
from maven import feature_flags

from cost_breakdown.models.cost_breakdown import CostBreakdown
from direct_payment.billing import models as billing_models
from direct_payment.billing.models import Bill
from direct_payment.payments.constants import (
    ENABLE_UNLIMITED_BENEFITS_FOR_PAYMENTS_HELPER,
)
from direct_payment.payments.models import (
    DashboardLayoutResult,
    PaymentRecordForReimbursementWallet,
    UpcomingPaymentsAndSummaryForReimbursementWallet,
    UpcomingPaymentsResultForReimbursementWallet,
    UpcomingPaymentSummaryForReimbursementWallet,
)
from direct_payment.payments.payments_helper import PaymentsHelper
from direct_payment.treatment_procedure.models.treatment_procedure import (
    TreatmentProcedure,
)
from storage.connection import db
from utils.log import logger
from wallet.models.constants import BenefitTypes, WalletState
from wallet.models.models import CategoryBalance
from wallet.models.reimbursement_wallet import ReimbursementWallet
from wallet.schemas.constants import ClientLayout
from wallet.services.reimbursement_wallet import ReimbursementWalletService

BenefitTypeToClientLayoutMap = {
    BenefitTypes.CYCLE: ClientLayout.ZERO_CYCLES,
    BenefitTypes.CURRENCY: ClientLayout.ZERO_CURRENCY,
}

log = logger(__name__)


class PaymentRecordsHelper:
    def __init__(self) -> None:
        self.wallet_service = ReimbursementWalletService()

    @tracer.wrap()
    def get_upcoming_payments_for_reimbursement_wallet(
        self, wallet: ReimbursementWallet
    ) -> UpcomingPaymentsResultForReimbursementWallet | None:
        """
        Creates a payload with information needed to populate the member dashboard for the
        /v1/reimbursement_wallet endpoint.
        """
        payments_helper = PaymentsHelper(db.session)

        # A bill must have a procedure id, so we can start by looking at
        # all the procedures affiliated with the wallet, acquire all the
        # bills for those procedures, and then filter from there.
        sorted_treatment_procedures = (
            payments_helper.treatment_procedure_repo.get_all_treatments_from_wallet_id(
                wallet.id
            )
        )

        procedure_ids = [tp.id for tp in sorted_treatment_procedures]

        # Include both member and employer bills
        upcoming_bills_and_historic_bills = (
            payments_helper.billing_service.get_bills_by_procedure_ids(
                procedure_ids=procedure_ids,
                exclude_payor_types=[billing_models.PayorType.CLINIC],
                status=billing_models.UPCOMING_STATUS + billing_models.HISTORIC_STATUS,
            )
        )

        upcoming_bills = [
            b
            for b in upcoming_bills_and_historic_bills
            if b.status in billing_models.UPCOMING_STATUS
        ]
        historic_bills = [
            b
            for b in upcoming_bills_and_historic_bills
            if b.status in billing_models.HISTORIC_STATUS
        ]

        estimates = payments_helper.billing_service.get_estimates_by_procedure_ids(
            procedure_ids
        )
        sorted_treatment_procedures = _filter_procedures(
            sorted_treatment_procedures, estimates, upcoming_bills, historic_bills
        )

        cost_breakdowns = CostBreakdown.query.filter(
            CostBreakdown.id.in_(
                frozenset(bill.cost_breakdown_id for bill in upcoming_bills)
            )
        ).all()

        make_list = lambda x: [y.id for y in x]
        log.info(
            "Pulled raw data to create payment records",
            wallet_id=str(wallet.id),
            len_sorted_treatment_procedures=len(sorted_treatment_procedures),
            len_upcoming_bills=len(upcoming_bills),
            len_historic_bills=len(historic_bills),
            len_estimates=len(estimates),
            len_upcoming_cost_breakdowns=len(cost_breakdowns),
            data_sorted_sorted_treatment_procedures=make_list(
                sorted_treatment_procedures
            ),
            data_upcoming_bills=make_list(upcoming_bills),
            data_historic_bills=make_list(historic_bills),
            data_estimates=make_list(estimates),
            data_cost_breakdowns=make_list(cost_breakdowns),
        )

        # Build the mappings from all queried data.
        procedure_map = {
            procedure.id: procedure for procedure in sorted_treatment_procedures
        }
        cost_breakdown_map = {
            cost_breakdown.id: cost_breakdown for cost_breakdown in cost_breakdowns
        }
        upcoming_member_bills = [
            bill
            for bill in upcoming_bills
            if bill.payor_type == billing_models.PayorType.MEMBER
        ]
        upcoming_member_positive_bills: list[Bill] = [
            bill
            for bill in upcoming_bills
            if bill.payor_type == billing_models.PayorType.MEMBER and bill.amount > 0
        ]
        member_bill_procedure_ids = frozenset(
            bill.procedure_id for bill in upcoming_member_bills
        )

        upcoming_member_payment_records = (
            payments_helper.return_upcoming_records_for_reimbursement_wallet(
                bills=upcoming_member_bills,
                bill_procedure_ids=member_bill_procedure_ids,
                procedure_map=procedure_map,
                cost_breakdown_map=cost_breakdown_map,
            )
        )
        if not upcoming_member_payment_records:
            # If we have no upcoming records, then we null the entire response
            return None

        upcoming_payments_and_summary = compute_summary_for_reimbursement_wallet(
            upcoming_member_payment_records
        )

        latest_upcoming_member_bill = (
            max(upcoming_member_positive_bills, key=lambda b: b.id if b else 0)  # type: ignore
            if upcoming_member_positive_bills
            else None
        )
        latest_upcoming_member_cb = (
            cost_breakdown_map[latest_upcoming_member_bill.cost_breakdown_id]
            if latest_upcoming_member_bill
            else None
        )
        dashboard_layout_result = _compute_dashboard_layout_result(
            wallet=wallet,
            bill=latest_upcoming_member_bill,
            cost_breakdown_for_bill=latest_upcoming_member_cb,
            wallet_service=self.wallet_service,
        )

        return UpcomingPaymentsResultForReimbursementWallet(
            upcoming_payments_and_summary=upcoming_payments_and_summary,
            show_benefit_amount=dashboard_layout_result.show_benefit_amount,
            client_layout=dashboard_layout_result.client_layout,
            num_errors=compute_num_errors(upcoming_member_payment_records),
        )


def compute_summary_for_reimbursement_wallet(
    upcoming_records: list[PaymentRecordForReimbursementWallet],
) -> UpcomingPaymentsAndSummaryForReimbursementWallet:
    # for the summary we only care about records that have a bill
    filtered_records = [r for r in upcoming_records if r and r.bill_uuid is not None]
    log.info(
        "Computing Summary for upcoming_records",
        len_upcoming_records=len(upcoming_records),
        len_filtered_records=len(filtered_records),
        filtered_records_bills=[str(r.bill_uuid) for r in filtered_records],
    )
    if not filtered_records:
        return UpcomingPaymentsAndSummaryForReimbursementWallet(None, [])
    # sort these by processing_scheduled_at_or_after ascending
    earliest_record = min(filtered_records, key=lambda b: b.processing_scheduled_at_or_after if b.processing_scheduled_at_or_after else b.created_at)  # type: ignore
    total_member_amount = None
    total_benefit_amount = None
    benefit_remaining = filtered_records[-1].benefit_remaining

    for upcoming_record in filtered_records:
        if not total_member_amount:
            total_member_amount = upcoming_record.member_amount
        else:
            total_member_amount += upcoming_record.member_amount or 0
        if not total_benefit_amount:
            total_benefit_amount = upcoming_record.benefit_amount
        else:
            total_benefit_amount += upcoming_record.benefit_amount or 0

    summary = UpcomingPaymentSummaryForReimbursementWallet(
        total_member_amount=total_member_amount,
        member_method=earliest_record.member_method,
        total_benefit_amount=total_benefit_amount,
        benefit_remaining=benefit_remaining,
        procedure_title=earliest_record.procedure_title,
    )
    return UpcomingPaymentsAndSummaryForReimbursementWallet(summary, filtered_records)


def _compute_dashboard_layout_result(
    wallet: ReimbursementWallet,
    bill: Bill | None,
    cost_breakdown_for_bill: CostBreakdown | None,
    wallet_service: ReimbursementWalletService,
) -> DashboardLayoutResult:
    """Computes the member's dashboard layout."""

    # Is the wallet enabled for direct payments?
    if not wallet.reimbursement_organization_settings.direct_payment_enabled:
        # We don't care what the layout is.
        return DashboardLayoutResult(ClientLayout.RUNOUT, False)

    if wallet.state == WalletState.RUNOUT:
        return DashboardLayoutResult(ClientLayout.RUNOUT, False)

    enable_unlimited: bool = feature_flags.bool_variation(
        ENABLE_UNLIMITED_BENEFITS_FOR_PAYMENTS_HELPER, default=False
    )

    if enable_unlimited:
        category = wallet.get_direct_payment_category
        if not category:
            raise Exception("No direct payment category affiliated with the wallet.")
        category_association = category.get_category_association(
            reimbursement_wallet=wallet
        )
        category_balance: CategoryBalance = wallet_service.get_wallet_category_balance(
            category_association=category_association, wallet=wallet
        )
        has_remaining_balance = (
            True
            if category_balance.is_unlimited
            else category_balance.current_balance > 0
        )
        benefit_type = category_balance.benefit_type

    else:
        # Compute balance information for the wallet, which has
        # either CYCLES or CURRENCY
        _, available_balance, benefit_type = wallet.get_direct_payment_balances()
        if available_balance is None:
            raise Exception(
                "No cycles or currency categories affiliated with the wallet."
            )
        has_remaining_balance = available_balance > 0

    # Does the wallet have a positive balance?
    if not has_remaining_balance:
        return DashboardLayoutResult(BenefitTypeToClientLayoutMap[benefit_type], False)  # type: ignore[index] # Invalid index type "Optional[BenefitTypes]" for "Dict[BenefitTypes, ClientLayout]"; expected type "BenefitTypes"

    # The wallet has a positive balance.

    # If there are any upcoming treatments, then there will be a
    # most recent upcoming treatment.
    if bill is None:
        return DashboardLayoutResult(ClientLayout.NO_PAYMENTS, False)

    # The member has a payment responsibility for the most recent treatment procedure.
    if (
        cost_breakdown_for_bill
        and cost_breakdown_for_bill.total_employer_responsibility > 0
    ):
        return DashboardLayoutResult(ClientLayout.MEMBER, True)
    return DashboardLayoutResult(ClientLayout.MEMBER, False)


def compute_num_errors(payments: list[PaymentRecordForReimbursementWallet]) -> int:  # type: ignore[no-untyped-def] # Function is missing a return type annotation
    return sum(1 for payment in payments if payment.error_type is not None)


def _filter_procedures(
    treatment_procedures: list[TreatmentProcedure],
    estimates: list[Bill],
    upcoming_bills: list[Bill],
    historic_bills: list[Bill],
) -> list[TreatmentProcedure]:
    """
    Typically we expect the following cases of (NEW< FAILED AND PROCESSING) bills and estimates linked to a TP for
    upcoming items:
    1. TP scheduled: 1 NEW estimate
    2. (During transition) - TP scheduled: 0 or 1 NEW estimate. >= 1 MEMBER bills. Bills may be in PROCESSING, NEW or
    FAILED.
    3. TP completed - 0 Estimates, >= 1 MEMBER bills. Bills may be in PROCESSING, NEW or FAILED (since restricting to
    upcoming), >=1 EMPLOYER bill
    However, due to errors in CB or member bill creation, or an accidental admin deletion it's possible that MEMBER
    bills or estimates go missing - so you could have a TP with no Bills (unlikely but possible).
    Or a TP with an employer bill and an estimate (very improbable but bugs happen)

    If the member bill is missing, there is an employer bill and there is no estimate, we retain the TP. It will show as
    pending in the UI.

    If the member bill is missing, there is an employer bill, and it has an estimate, don't retain the tp. It will show
    in the estimate section.

    If the member bill is missing, there is no employer bill, and it has no estimate, retain the tp. It will show how as
    pending in the UI.

    upcoming_bills - contains all employer and member bills for this member.
    treatment_procedures is all tps linked to this member.
    estimates - all estimates linked to this member

    """
    to_return = []
    log.info(
        "Pruning treatment_procedures",
        treatment_procedures_cnt=len(treatment_procedures),
        estimates_len=len(estimates),
        upcoming_bills_len=len(upcoming_bills),
        historic_bills=len(historic_bills),
    )
    if treatment_procedures:
        # these are the procs that have estimates.
        estimate_procs = {e.procedure_id for e in estimates}

        # these are procs that have historic bills but no upcoming bills
        historic_procs = {h.procedure_id for h in historic_bills}

        # these are the procs that have upcoming bills.
        upcoming_procs = {b.procedure_id for b in upcoming_bills}

        # these are the procs have estimates but do not have upcoming bills.
        only_estimates = estimate_procs.difference(upcoming_procs)
        # these are the procs that have historic bills but do not have upcoming bills
        only_historic = historic_procs.difference(upcoming_procs)

        # we return the procs that have at least one bill (they may also have an estimate)
        to_return = [
            t
            for t in treatment_procedures
            if (t.id not in only_estimates and t.id not in only_historic)
        ]
        log.info(
            "Returning TPs that have upcoming bills",
            estimate_procs=estimate_procs,
            upcoming_procs=upcoming_procs,
            historic_procs=historic_procs,
            only_estimates=only_estimates,
            only_historic=only_historic,
            procedures_that_have_an_upcoming_bill=to_return,
        )
    log.info("Pruned treatment_procedures", to_return=to_return)
    return to_return
