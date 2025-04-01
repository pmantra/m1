from __future__ import annotations
from decimal import Decimal
from typing import List

from cost_breakdown.models.cost_breakdown import CostBreakdown
from direct_payment.billing.billing_service import BillingService
from direct_payment.billing.models import Bill, PayorType
from direct_payment.clinic.models.clinic import FertilityClinicLocation
from direct_payment.clinic.repository.clinic_location import (
    FertilityClinicLocationRepository,
)
from direct_payment.payments.models import (
    BillProcedureCostBreakdown,
    EstimateBreakdown,
    EstimateDetail,
    EstimateSummaryForReimbursementWallet,
    LabelCost,
)
from direct_payment.payments.constants import (
    EstimateText,
    PaymentText,
    DetailLabel,
    EstimateTitles,
    ESTIMATED_BOILERPLATE,
)
from direct_payment.treatment_procedure.models.treatment_procedure import (
    TreatmentProcedure,
)
from direct_payment.treatment_procedure.repository.treatment_procedure import (
    TreatmentProcedureRepository,
)
from storage.connection import db
from utils.log import logger

log = logger(__name__)


class EstimatesHelper:
    def __init__(self, session=None):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        self.session = session or db.session
        self.billing_service = BillingService(session=session)
        self.treatment_procedure_repo = TreatmentProcedureRepository(session)
        self.clinic_loc_repo = FertilityClinicLocationRepository(session=session)

    def get_estimates_summary_by_wallet(
        self, wallet_id: int
    ) -> EstimateSummaryForReimbursementWallet | None:
        estimate_objects = self._get_bills_to_details_by_wallet(wallet_id=wallet_id)
        payment_text = PaymentText.DEFAULT.value
        if not len(estimate_objects):
            return None
        total_member_estimate = 0
        estimate_bill_uuid = (
            estimate_objects[0].bill.uuid if len(estimate_objects) == 1 else None
        )
        if estimate_bill_uuid:
            procedure_name = estimate_objects[0].procedure.procedure_name
            estimated_text = procedure_name
        else:
            estimated_text = EstimateText.ESTIMATED_TOTAL.value.format(
                number_of_estimated_objects=len(estimate_objects)
            )
        for estimate_object in estimate_objects:
            total_member_estimate += estimate_object.bill.amount
        if total_member_estimate == 0:
            payment_text = PaymentText.EMPLOYER.value
        return EstimateSummaryForReimbursementWallet(
            estimate_text=estimated_text,
            total_estimates=len(estimate_objects),
            total_member_estimate=self.format_cents_to_usd_str(
                cents=total_member_estimate
            ),
            payment_text=payment_text,
            estimate_bill_uuid=estimate_bill_uuid,  # type: ignore[arg-type] # Argument "estimate_bill_uuid" to "EstimateSummaryForReimbursementWallet" has incompatible type "Optional[UUID]"; expected "Optional[str]"
        )

    def get_estimates_by_wallet(self, wallet_id: int) -> List[EstimateDetail]:
        estimate_details = []
        # get estimate bills for wallet
        estimate_objects = self._get_bills_to_details_by_wallet(wallet_id=wallet_id)
        # loop through bills to fill out estimate object with bill + tp + cost breakdown + clinic info
        for estimate_object in estimate_objects:
            estimate_details.append(
                self._form_estimate_detail(
                    bill=estimate_object.bill,
                    procedure=estimate_object.procedure,
                    cost_breakdown=estimate_object.cost_breakdown,
                )
            )
        return estimate_details

    def get_estimate_detail_by_uuid(self, bill_uuid: str) -> EstimateDetail:
        bill = self.billing_service.get_bill_by_uuid(bill_uuid=bill_uuid)
        if not bill:
            return None  # type: ignore[return-value] # Incompatible return value type (got "None", expected "EstimateDetail")
        procedures = self.treatment_procedure_repo.get_treatments_by_ids(
            treatment_procedure_ids=[bill.procedure_id]
        )
        if procedures and len(procedures) == 1:
            procedure = procedures[0]
        else:
            log.error(
                "Unable to retrieve estimate: Missing procedure data for bill",
                bill_uuid=bill_uuid,
            )
            raise EstimateMissingCriticalDataException()
        cost_breakdown = self._get_cost_breakdown(bill=bill)
        return self._form_estimate_detail(
            bill=bill,
            procedure=procedure,
            cost_breakdown=cost_breakdown,
        )

    def get_clinic_name_and_location_strings(  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        self,
        procedure: TreatmentProcedure,
    ):
        clinic = self._get_clinic_location(procedure=procedure)
        if not clinic:
            return "", ""
        clinic_state = (
            clinic.subdivision_code.split("-")[1]
            if clinic.subdivision_code and len(clinic.subdivision_code.split("-")) == 2
            else ""
        )
        return clinic.name, (
            f"{clinic.city}, {clinic_state}" if clinic and clinic.city else ""
        )

    def _form_estimate_detail(
        self,
        bill: Bill,
        procedure: TreatmentProcedure,
        cost_breakdown: CostBreakdown,
    ) -> EstimateDetail:
        clinic_name, clinic_location = self.get_clinic_name_and_location_strings(
            procedure
        )
        log.info(
            "Forming EstimateDetail:",
            bill=bill.uuid,
            treatment_procedure=procedure.id,
            cost_breakdown=cost_breakdown.id,
        )
        if (
            not procedure.cost_credit
            or cost_breakdown.total_employer_responsibility == 0
        ):
            credits_used = None
        elif procedure.cost_credit == 1:
            credits_used = "1 credit"
        else:
            credits_used = f"{procedure.cost_credit} credits"
        member_amt = self.format_cents_to_usd_str(cents=bill.amount)
        if bill.amount == cost_breakdown.total_member_responsibility:
            log.info(
                "Estimate Type", estimate_type="initial_estimate", bill_id=str(bill.id)
            )
            responsibility_breakdown_items = [
                LabelCost(
                    label=DetailLabel.DEDUCTIBLE.value,
                    cost=self.format_cents_to_usd_str(cents=cost_breakdown.deductible),
                ),
                LabelCost(
                    label=DetailLabel.COINSURANCE.value,
                    cost=self.format_cents_to_usd_str(cents=cost_breakdown.coinsurance),
                ),
                LabelCost(
                    label=DetailLabel.COPAY.value,
                    cost=self.format_cents_to_usd_str(cents=cost_breakdown.copay),
                ),
            ]
        else:
            log.info(
                "Estimate Type",
                estimate_type="adjustment_estimate",
                bill_id=str(bill.id),
            )
            responsibility_breakdown_items = [
                LabelCost(
                    label=DetailLabel.TOTAL_MEMBER_RESPONSIBILITY.value,
                    cost=self.format_cents_to_usd_str(
                        cents=cost_breakdown.total_member_responsibility
                    ),
                ),
                LabelCost(
                    label=DetailLabel.PREVIOUS_CHARGES.value,
                    cost=f"""-{self.format_cents_to_usd_str(
                        cents=cost_breakdown.total_member_responsibility - bill.amount)}""",
                ),
                LabelCost(
                    label=DetailLabel.ESTIMATE_ADJUSTMENT.value,
                    cost=self.format_cents_to_usd_str(cents=bill.amount),
                ),
            ]
        return EstimateDetail(
            procedure_id=procedure.id,
            bill_uuid=str(bill.uuid),
            procedure_title=procedure.procedure_name,
            clinic=clinic_name,
            clinic_location=clinic_location,
            estimate_creation_date=bill.created_at.strftime("%b %d, %Y"),  # type: ignore[union-attr] # Item "None" of "Optional[datetime]" has no attribute "strftime"
            estimate_creation_date_raw=bill.created_at,  # type: ignore[arg-type] # Argument "estimate_creation_date_raw" to "EstimateDetail" has incompatible type "datetime | None"; expected "datetime"
            estimated_member_responsibility=member_amt,
            estimated_total_cost=self.format_cents_to_usd_str(cents=procedure.cost),
            estimated_boilerplate=ESTIMATED_BOILERPLATE,
            credits_used=credits_used,
            responsibility_breakdown=EstimateBreakdown(
                title=EstimateTitles.YOUR_RESPONSIBILITY.value,
                total_cost=member_amt,
                items=responsibility_breakdown_items,
            ),
            covered_breakdown=EstimateBreakdown(
                title=EstimateTitles.COVERED_AMOUNT.value,
                total_cost=self.format_cents_to_usd_str(
                    cents=cost_breakdown.total_employer_responsibility
                ),
                items=[
                    LabelCost(
                        label=DetailLabel.MAVEN_BENEFIT.value,
                        cost=self.format_cents_to_usd_str(
                            cents=cost_breakdown.total_employer_responsibility
                        ),
                    ),
                ],
            ),
        )

    def _get_bills_to_details_by_wallet(
        self, wallet_id: int
    ) -> List[BillProcedureCostBreakdown]:
        bills = self.billing_service.get_estimates_by_payor(
            payor_id=wallet_id, payor_type=PayorType.MEMBER
        )
        if not bills:
            return []
        estimates_objects = []
        # get treatment procedures for those estimates
        procedure_ids = {bill.procedure_id for bill in bills}
        procedures = self.treatment_procedure_repo.get_treatments_by_ids(
            treatment_procedure_ids=list(procedure_ids)
        )
        procedure_ids_to_procedures = {
            procedure.id: procedure for procedure in procedures
        }
        # get cost breakdowns for the estimates
        cost_breakdown_ids = {bill.cost_breakdown_id for bill in bills}
        cost_breakdowns = self.session.query(CostBreakdown).filter(
            CostBreakdown.id.in_(cost_breakdown_ids)
        )
        cost_breakdown_ids_to_cost_breakdowns = {cb.id: cb for cb in cost_breakdowns}
        # loop through bills to fill out estimate map with bill + tp + cost breakdown
        for bill in bills:
            procedure = procedure_ids_to_procedures.get(bill.procedure_id)
            if not procedure:
                log.error(
                    "Unable to retrieve estimate: Missing procedure data for bill",
                    bill_uuid=bill.uuid,
                )
                raise EstimateMissingCriticalDataException()
            cost_breakdown = cost_breakdown_ids_to_cost_breakdowns.get(
                bill.cost_breakdown_id
            )
            if not cost_breakdown:
                log.error(
                    "Unable to retrieve estimate: Missing cost breakdown data for bill",
                    bill_uuid=bill.uuid,
                )
                raise EstimateMissingCriticalDataException()
            estimates_objects.append(
                BillProcedureCostBreakdown(
                    bill=bill, procedure=procedure, cost_breakdown=cost_breakdown
                )
            )
        return estimates_objects

    def _get_clinic_location(
        self, procedure: TreatmentProcedure
    ) -> FertilityClinicLocation:
        clinic_location = self.clinic_loc_repo.get(
            fertility_clinic_location_id=procedure.fertility_clinic_location_id
        )
        return clinic_location

    def _get_cost_breakdown(self, bill: Bill) -> CostBreakdown:
        cost_breakdown = (
            self.session.query(CostBreakdown)
            .filter(CostBreakdown.id == bill.cost_breakdown_id)
            .one_or_none()
        )
        if not cost_breakdown:
            log.error(
                "Unable to retrieve estimate: Missing CostBreakdown data for bill",
                bill_uuid=bill.uuid,
            )
            raise EstimateMissingCriticalDataException()
        return cost_breakdown

    def format_cents_to_usd_str(self, cents: int) -> str:
        return f"${Decimal(cents) / 100:,.2f}"


class EstimateMissingCriticalDataException(Exception):
    pass
