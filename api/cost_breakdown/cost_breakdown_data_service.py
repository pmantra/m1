import datetime
from typing import Optional, Tuple

from maven import feature_flags

from common import stats
from cost_breakdown import errors
from cost_breakdown.constants import (
    DISABLE_COST_BREAKDOWN_FOR_PAYER,
    CostBreakdownType,
    Tier,
)
from cost_breakdown.deductible_accumulation_calculator import (
    DeductibleAccumulationCalculator,
)
from cost_breakdown.errors import (
    NoFamilyDeductibleOopRemaining,
    NoIndividualDeductibleOopRemaining,
    PayerDisabledCostBreakdownException,
)
from cost_breakdown.models.cost_breakdown import (
    CostBreakdownData,
    DeductibleAccumulationYTDInfo,
    HDHPAccumulationYTDInfo,
    RteIdType,
)
from cost_breakdown.models.rte import EligibilityInfo, RTETransaction, RxYTDInfo
from cost_breakdown.rte.rte_processor import RTEProcessor
from cost_breakdown.utils.helpers import (
    get_amount_type,
    get_irs_limit,
    get_medical_coverage,
    get_rx_coverage,
    set_db_copay_coinsurance_to_eligibility_info,
)
from direct_payment.treatment_procedure.models.treatment_procedure import (
    TreatmentProcedureType,
)
from utils.log import logger
from wallet.models.constants import CostSharingCategory, FamilyPlanType
from wallet.models.reimbursement_organization_settings import EmployerHealthPlan
from wallet.models.reimbursement_wallet import MemberHealthPlan
from wallet.utils.annual_questionnaire.utils import FdcHdhpCheckResults

log = logger(__name__)


def increment_stat(prefix_append=None, tags=None):  # type: ignore[no-untyped-def] # Function is missing a type annotation
    """Helper maintaining a consistent metric name even though this points to the wrong file. Watch the dot."""
    metric_name = "api.cost_breakdown.cost_breakdown_processor"
    if prefix_append:
        metric_name += f".{prefix_append}"
    stats.increment(
        metric_name=metric_name,
        pod_name=stats.PodNames.PAYMENTS_PLATFORM,
        tags=tags,
    )


class CostBreakdownDataService:
    """
    1. Collects all required params. Avoids passing whole models, prefers passing specific (typed) values.
    2. Generates data for a cost breakdown, but does not create a db object
    3. DB objects should be created outside the data service
    """

    override_rte_result: Optional[EligibilityInfo] = None

    def __init__(
        self,
        member_first_name: str,
        member_last_name: str,
        member_health_plan: MemberHealthPlan,
        wallet_balance: int,
        cost: int,
        procedure_type: TreatmentProcedureType,
        cost_sharing_category: CostSharingCategory,
        deductible_accumulation_enabled: bool,
        service_start_date: datetime.date,
        is_unlimited: bool = False,
        sequential_deductible_accumulation_member_responsibilities: Optional[
            DeductibleAccumulationYTDInfo
        ] = None,
        sequential_hdhp_responsibilities: Optional[HDHPAccumulationYTDInfo] = None,
        alegeus_ytd_spend: int = 0,
        rx_ytd_spend: Optional[RxYTDInfo] = None,
        tier: Optional[Tier] = None,
        fdc_hdhp_check: Optional[FdcHdhpCheckResults] = None,
        treatment_procedure_id: Optional[int] = None,
        reimbursement_request_id: Optional[int] = None,
    ):
        self.member_first_name = member_first_name
        self.member_last_name = member_last_name
        self.member_health_plan = member_health_plan
        self.is_unlimited = is_unlimited  # If the category has unlimited benefits
        self.wallet_balance = wallet_balance  # from reimbursement wallet
        self.cost = cost  # from claim, treatment procedure, etc
        self.procedure_type = procedure_type  # from claim, treatment procedure, etc
        self.cost_sharing_category = cost_sharing_category  # from procedures service
        self.deductible_accumulation_enabled = (
            deductible_accumulation_enabled  # from org settings
        )
        self.service_start_date = service_start_date
        self.sequential_deductible_accumulation_member_responsibilities = sequential_deductible_accumulation_member_responsibilities  # from past treatment procedures
        self.sequential_hdhp_responsibilities = (
            sequential_hdhp_responsibilities  # from past treatment procedures for hdhp
        )
        self.alegeus_ytd_spend = alegeus_ytd_spend  # from alegeus for hdhp
        self.rx_ytd_spend = rx_ytd_spend  # from the HealthPlanYearToDateSpendService

        self.rte_processor = RTEProcessor()
        self.deductible_accumulation_calculator = DeductibleAccumulationCalculator()
        self.tier = tier
        self.fdc_hdhp_check = fdc_hdhp_check
        self.treatment_procedure_id = treatment_procedure_id
        self.reimbursement_request_id = reimbursement_request_id

    def get_cost_breakdown_data(self) -> CostBreakdownData:
        # note: deductible_accumulation and hdhp can exist together, but the accumulation flow always takes priority
        if self.deductible_accumulation_enabled:
            if not self.member_health_plan:
                raise errors.NoMemberHealthPlanError(
                    "No member health plan provided for deductible accumulation plan."
                )
            log.info("Generating a deductible_accumulation_enabled Cost Breakdown")
            cost_breakdown_data = self.get_deductible_accumulation_data()
        elif (
            self.member_health_plan
            and self.member_health_plan.employer_health_plan.is_hdhp
        ):
            log.info("Generating a hdhp Cost Breakdown")
            cost_breakdown_data = self.get_hdhp_data()
        else:
            if self.fdc_hdhp_check in [
                FdcHdhpCheckResults.FDC_YES_HDHP_UNKNOWN,
                FdcHdhpCheckResults.FDC_UNKNOWN,
            ]:
                log.error(
                    "Unexpected Cost Breakdown Logic",
                    error="Need a HDHP survey.",
                    fdc_hdhp_check=self.fdc_hdhp_check,
                )
                raise errors.ActionableCostBreakdownException(
                    "This user needs to take the HDHP survey to allow us to determine "
                    "if we should calculate a cost breakdown using First Dollar or HDHP logic."
                )
            elif self.fdc_hdhp_check == FdcHdhpCheckResults.FDC_YES_HDHP_YES:
                log.error(
                    "Unexpected Cost Breakdown Logic",
                    error="HDHP expected.",
                    fdc_hdhp_check=self.fdc_hdhp_check,
                )
                raise errors.ActionableCostBreakdownException(
                    "This user is missing a member health plan that would allow us to calculate HDHP costs for them."
                )
            elif self.fdc_hdhp_check == FdcHdhpCheckResults.FDC_NO:
                log.error(
                    "Unexpected Cost Breakdown Logic",
                    error="Deductible Accumulation Expected",
                    fdc_hdhp_check=self.fdc_hdhp_check,
                )
                raise errors.ActionableCostBreakdownException(
                    "Attempted to calculate First Dollar Coverage while not configured for First Dollar Coverage. "
                    "Please check this user and organization's configuration."
                )

            # If there's no FdcHdhpCheckResults or if FdcHdhpCheckResults == FDC_YES_HDHP_NO
            log.info(
                "Generating a fully covered Cost Breakdown",
                fdc_hdhp_check=self.fdc_hdhp_check,
            )
            cost_breakdown_data = self.get_fully_covered_data()
        # PAY-6251 we need to handle the edge case of a negative wallet balance to avoid overcharging member
        if (
            isinstance(cost_breakdown_data, CostBreakdownData)
            and cost_breakdown_data.beginning_wallet_balance < 0
            and cost_breakdown_data.total_member_responsibility > self.cost
        ):
            cost_breakdown_data = self.default_negative_wallet_cost_breakdown(
                cb_data=cost_breakdown_data, cost=self.cost
            )
        return cost_breakdown_data

    def default_negative_wallet_cost_breakdown(
        self, cb_data: CostBreakdownData, cost: int
    ) -> CostBreakdownData:
        # PAY-6251 we need to handle the edge case of a negative wallet balance to avoid overcharging member
        log.warning(
            "Negative wallet balance with member charge more than procedure cost detected. Defaulting to charge member cost of procedure and revert wallet changes",
            treatment_procedure_id=str(self.treatment_procedure_id),
            reimbursement_request_id=str(self.reimbursement_request_id),
            member_responsibility_before_default=cb_data.total_member_responsibility,
            ending_wallet_balance_before_default=cb_data.ending_wallet_balance,
        )
        cb_data.total_member_responsibility = cost
        cb_data.ending_wallet_balance = (
            cb_data.beginning_wallet_balance
            if cb_data.beginning_wallet_balance <= 0
            else max(0, cb_data.beginning_wallet_balance - cost)
        )
        cb_data.deductible_remaining = (
            max(
                cb_data.deductible_remaining,
                cb_data.deductible_remaining + cb_data.deductible - cost,
            )
            if cb_data.deductible_remaining is not None
            else None
        )
        cb_data.oop_remaining = (
            max(
                cb_data.oop_remaining,
                cb_data.oop_remaining + cb_data.oop_applied - cost,
            )
            if cb_data.oop_remaining is not None
            else None
        )
        cb_data.family_deductible_remaining = (
            max(
                cb_data.family_deductible_remaining,
                cb_data.family_deductible_remaining + cb_data.deductible - cost,
            )
            if cb_data.family_deductible_remaining is not None
            else None
        )
        cb_data.family_oop_remaining = (
            max(
                cb_data.family_oop_remaining,
                cb_data.family_oop_remaining + cb_data.oop_applied - cost,
            )
            if cb_data.family_oop_remaining is not None
            else None
        )
        cb_data.oop_applied = min(cb_data.oop_applied or 0, cost)
        cb_data.deductible = min(cb_data.deductible or 0, cost)
        cb_data.hra_applied = (
            min(cb_data.hra_applied, cost) if cb_data.hra_applied is not None else None
        )
        cb_data.coinsurance = min(cb_data.coinsurance or 0, cost)
        cb_data.copay = min(cb_data.copay or 0, cost)
        cb_data.overage_amount = min(cb_data.overage_amount, cost)
        return cb_data

    @staticmethod
    def will_run_eligibility_info(
        deductible_accumulation_enabled: bool, member_health_plan: MemberHealthPlan
    ) -> bool:
        payer_name = (
            member_health_plan
            and member_health_plan.employer_health_plan.benefits_payer
            and member_health_plan.employer_health_plan.benefits_payer.payer_name.value
        )
        disabled_payers = feature_flags.json_variation(
            DISABLE_COST_BREAKDOWN_FOR_PAYER, default={"disabled_payers": []}
        ).get("disabled_payers")
        if (
            disabled_payers
            and payer_name
            and payer_name.strip().lower() in disabled_payers
        ):
            log.info(
                "Cost breakdown disabled for payer",
                payer_name=payer_name,
                disabled_payers=disabled_payers,
            )
            raise PayerDisabledCostBreakdownException(
                f"Cost breakdown disabled for payer {payer_name}."
            )
        # Cases in which we run get_deductible_accumulation_data or get_hdhp_data
        # Cases where sequential payments and rx integration matter
        return bool(member_health_plan and deductible_accumulation_enabled) or bool(
            member_health_plan and member_health_plan.employer_health_plan.is_hdhp
        )

    def get_deductible_accumulation_data(self) -> CostBreakdownData:
        increment_stat(prefix_append="deductible_accumulation")
        if self.member_health_plan.employer_health_plan.is_payer_not_integrated:
            eligibility_info = self.get_eligibility_info_payer_not_integrated_plan()
            rte_id = None
        else:
            eligibility_info, rte_id = self.get_eligibility_info()

        self._add_sequential_responsibility_for_deductible_accumulation(
            eligibility_info
        )
        member_charge_breakdown = (
            self.deductible_accumulation_calculator.calculate_member_cost_breakdown(
                treatment_cost=self.cost,
                is_unlimited=self.is_unlimited,
                wallet_balance=self.wallet_balance,
                member_health_plan=self.member_health_plan,
                eligibility_info=eligibility_info,
            )
        )
        member_charge = member_charge_breakdown.member_responsibility
        benefits_accumulation_breakdown = (
            self.deductible_accumulation_calculator.calculate_accumulation_values(
                member_health_plan=self.member_health_plan,
                eligibility_info=eligibility_info,
                member_charge=member_charge,
            )
        )
        employer_charge = self.cost - member_charge
        ending_wallet_balance = (
            0 if self.is_unlimited else (self.wallet_balance - employer_charge)
        )
        hra_applied: int = 0
        if (
            self.member_health_plan.employer_health_plan.hra_enabled
            and eligibility_info.hra_remaining is not None
        ):
            hra_applied = min(member_charge, eligibility_info.hra_remaining)
            member_charge -= hra_applied
            employer_charge += hra_applied

        return CostBreakdownData(
            rte_transaction_id=rte_id,
            total_member_responsibility=member_charge,
            total_employer_responsibility=employer_charge,
            is_unlimited=self.is_unlimited,
            beginning_wallet_balance=0 if self.is_unlimited else self.wallet_balance,
            ending_wallet_balance=ending_wallet_balance,
            amount_type=get_amount_type(self.member_health_plan),
            cost_breakdown_type=CostBreakdownType.DEDUCTIBLE_ACCUMULATION,
            deductible=benefits_accumulation_breakdown.deductible_apply,
            deductible_remaining=benefits_accumulation_breakdown.individual_deductible_remaining,
            coinsurance=member_charge_breakdown.coinsurance,
            copay=member_charge_breakdown.copay,
            overage_amount=member_charge_breakdown.overage_amount,
            oop_applied=benefits_accumulation_breakdown.oop_apply,
            hra_applied=hra_applied,
            oop_remaining=benefits_accumulation_breakdown.individual_oop_remaining,
            family_deductible_remaining=benefits_accumulation_breakdown.family_deductible_remaining,
            family_oop_remaining=benefits_accumulation_breakdown.family_oop_remaining,
        )

    def _add_sequential_responsibility_for_deductible_accumulation(
        self, eligibility_info: EligibilityInfo
    ) -> EligibilityInfo:
        if self.member_health_plan.is_family_plan:
            eligibility_info.family_deductible_remaining = max(
                eligibility_info.family_deductible_remaining
                - self.sequential_deductible_accumulation_member_responsibilities.family_deductible_applied,  # type: ignore[union-attr] # Item "None" of "Optional[DeductibleAccumulationYTDInfo]" has no attribute "family_deductible_applied"
                0,
            )
            if eligibility_info.is_deductible_embedded:
                eligibility_info.individual_deductible_remaining = max(
                    eligibility_info.individual_deductible_remaining
                    - self.sequential_deductible_accumulation_member_responsibilities.individual_deductible_applied,  # type: ignore[union-attr] # Item "None" of "Optional[DeductibleAccumulationYTDInfo]" has no attribute "individual_deductible_applied"
                    0,
                )
            eligibility_info.family_oop_remaining = max(
                eligibility_info.family_oop_remaining
                - self.sequential_deductible_accumulation_member_responsibilities.family_oop_applied,  # type: ignore[union-attr] # Item "None" of "Optional[DeductibleAccumulationYTDInfo]" has no attribute "family_oop_applied"
                0,
            )
            if eligibility_info.is_oop_embedded:
                eligibility_info.individual_oop_remaining = max(
                    eligibility_info.individual_oop_remaining
                    - self.sequential_deductible_accumulation_member_responsibilities.individual_oop_applied,  # type: ignore[union-attr] # Item "None" of "Optional[DeductibleAccumulationYTDInfo]" has no attribute "individual_oop_applied"
                    0,
                )
        else:
            eligibility_info.individual_deductible_remaining = max(
                eligibility_info.individual_deductible_remaining
                - self.sequential_deductible_accumulation_member_responsibilities.individual_deductible_applied,  # type: ignore[union-attr] # Item "None" of "Optional[DeductibleAccumulationYTDInfo]" has no attribute "individual_deductible_applied"
                0,
            )
            eligibility_info.individual_oop_remaining = max(
                eligibility_info.individual_oop_remaining
                - self.sequential_deductible_accumulation_member_responsibilities.individual_oop_applied,  # type: ignore[union-attr] # Item "None" of "Optional[DeductibleAccumulationYTDInfo]" has no attribute "individual_oop_applied"
                0,
            )
        return eligibility_info

    def get_hdhp_data(self) -> CostBreakdownData:
        """
        Calculate the CostBreakdown for HDHP (High Deductible Health Plans).

        For HDHPs, the IRS has dictated a minimum OOP spend that must be met for individual or family to utilize
        the wallet benefit.
        Until that threshold is met, a member is responsible for costs.
        Once that IRS threshold is met, any wallet balance is put towards a treatment cost and is the employer's
        responsibility, with the member paying any remaining cost after that point.
        """
        increment_stat(prefix_append="hdhp")
        eligibility_info, rte_id = self.get_eligibility_info()
        is_individual = self.member_health_plan.is_family_plan is False
        irs_threshold = get_irs_limit(is_individual=is_individual)
        if is_individual:
            oop_ytd_spend = (
                (
                    eligibility_info.individual_oop
                    - eligibility_info.individual_oop_remaining
                )
                + self.sequential_hdhp_responsibilities.sequential_member_responsibilities  # type: ignore[union-attr] # Item "None" of "Optional[HDHPAccumulationYTDInfo]" has no attribute "sequential_member_responsibilities"
            )
        else:
            oop_ytd_spend = (
                (eligibility_info.family_oop - eligibility_info.family_oop_remaining)
                + self.sequential_hdhp_responsibilities.sequential_family_responsibilities  # type: ignore[union-attr] # Item "None" of "Optional[HDHPAccumulationYTDInfo]" has no attribute "sequential_family_responsibilities"
            )
        oop_ytd_spend += self.alegeus_ytd_spend
        if oop_ytd_spend < irs_threshold:
            log.info(
                "Out of Pocket Year to Date Spend is under the HDHP IRS Threshold."
            )
            if self.cost <= irs_threshold - oop_ytd_spend:
                log.info("Cost is under IRS - OOP")
                member_responsibility = deductible = self.cost
                employer_responsibility = 0
                wallet_balance_remaining = (
                    0 if self.is_unlimited else self.wallet_balance
                )
                overage_amount = 0
            else:
                log.info("Cost is not under IRS - OOP")
                member_responsibility = deductible = max(
                    irs_threshold - oop_ytd_spend, 0
                )
                remaining = self.cost - member_responsibility
                if self.is_unlimited or self.wallet_balance >= remaining:
                    log.info(
                        "Wallet balance can cover the remaining amount.",
                        is_unlimited=self.is_unlimited,
                    )
                    employer_responsibility = remaining
                    wallet_balance_remaining = (
                        0 if self.is_unlimited else (self.wallet_balance - remaining)
                    )
                    overage_amount = 0
                else:
                    log.info("Wallet balance cannot cover the remaining amount.")
                    employer_responsibility = self.wallet_balance
                    remaining = remaining - self.wallet_balance
                    member_responsibility += remaining
                    overage_amount = remaining
                    wallet_balance_remaining = 0

            return CostBreakdownData(
                rte_transaction_id=rte_id,
                total_member_responsibility=member_responsibility,
                total_employer_responsibility=employer_responsibility,
                deductible=deductible,
                is_unlimited=self.is_unlimited,
                beginning_wallet_balance=0
                if self.is_unlimited
                else self.wallet_balance,
                ending_wallet_balance=wallet_balance_remaining,
                amount_type=get_amount_type(self.member_health_plan),
                cost_breakdown_type=CostBreakdownType.HDHP,
                overage_amount=overage_amount,
            )
        else:
            log.info("HDHP plan treated as fully covered.")
            return self.get_fully_covered_data(rte_id=rte_id)

    def get_fully_covered_data(self, rte_id: RteIdType = None) -> CostBreakdownData:
        increment_stat(prefix_append="first_dollar_coverage")
        if self.is_unlimited or self.cost <= self.wallet_balance:
            member_responsibility = 0
            employer_responsibility = self.cost
            wallet_balance_remaining = (
                0 if self.is_unlimited else self.wallet_balance - self.cost
            )
            overage_amount = 0
        else:
            member_responsibility = self.cost - self.wallet_balance
            employer_responsibility = self.wallet_balance
            wallet_balance_remaining = 0
            overage_amount = self.cost - self.wallet_balance

        return CostBreakdownData(
            rte_transaction_id=rte_id,
            total_member_responsibility=member_responsibility,
            total_employer_responsibility=employer_responsibility,
            is_unlimited=self.is_unlimited,
            beginning_wallet_balance=0 if self.is_unlimited else self.wallet_balance,
            ending_wallet_balance=wallet_balance_remaining,
            amount_type=get_amount_type(self.member_health_plan),
            cost_breakdown_type=CostBreakdownType.FIRST_DOLLAR_COVERAGE,
            overage_amount=overage_amount,
        )

    def get_eligibility_info(self) -> Tuple[EligibilityInfo, RteIdType]:
        # If we have an override, we don't request real EligibilityInfo
        if self.override_rte_result is not None:
            log.info("Using RTE Override.")
            return self.override_rte_result, None

        # Requesting real EligibilityInfo:
        if (
            self.procedure_type == TreatmentProcedureType.MEDICAL
            or self.is_pharmacy_procedure_with_rx_integration(
                self.procedure_type, self.member_health_plan
            )
        ):
            return self._medical_or_rx_integrated_rte_request()
        else:
            return self._rx_not_integrated_rte_request()

    def get_eligibility_info_payer_not_integrated_plan(self) -> EligibilityInfo:
        """
        Don't run Pverify RTE check, use maven managed table to get member's eligibility information,
        the year-to-date spend is covered by sequential payments
        """
        employer_health_plan: EmployerHealthPlan = (
            self.member_health_plan.employer_health_plan
        )
        coverage = get_medical_coverage(
            ehp=employer_health_plan,
            plan_size=FamilyPlanType(self.member_health_plan.plan_type),
            tier=self.tier,
        )
        eligibility_info = EligibilityInfo(
            individual_deductible=coverage.individual_deductible,
            individual_deductible_remaining=coverage.individual_deductible,
            family_deductible=coverage.family_deductible,
            family_deductible_remaining=coverage.family_deductible,
            individual_oop=coverage.individual_oop,
            individual_oop_remaining=coverage.individual_oop,
            family_oop=coverage.family_oop,
            family_oop_remaining=coverage.family_oop,
            max_oop_per_covered_individual=coverage.max_oop_per_covered_individual,
            is_oop_embedded=coverage.is_oop_embedded,
            is_deductible_embedded=coverage.is_deductible_embedded,
        )

        cost_sharings = employer_health_plan.cost_sharings
        return set_db_copay_coinsurance_to_eligibility_info(
            eligibility_info=eligibility_info,
            cost_sharings=cost_sharings,
            cost_sharing_category=self.cost_sharing_category,
            tier=self.tier,
        )

    @staticmethod
    def is_pharmacy_procedure_with_rx_integration(  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        procedure_type: TreatmentProcedureType,
        member_health_plan: Optional[MemberHealthPlan],
    ):
        return (
            procedure_type == TreatmentProcedureType.PHARMACY
            and member_health_plan is not None
            and member_health_plan.employer_health_plan.rx_integrated is True
        )

    def _medical_or_rx_integrated_rte_request(
        self,
    ) -> Tuple[EligibilityInfo, RteIdType]:
        log.info("Medical or RX integrated RTE request.")
        try:
            rte_transaction = (
                self.rte_processor.pverify_api.get_real_time_eligibility_data(
                    plan=self.member_health_plan,
                    cost_sharing_category=self.cost_sharing_category,
                    member_first_name=self.member_first_name,
                    member_last_name=self.member_last_name,
                    is_second_tier=True if self.tier == Tier.SECONDARY else False,
                    service_start_date=self.service_start_date,
                    treatment_procedure_id=self.treatment_procedure_id,
                    reimbursement_request_id=self.reimbursement_request_id,
                )
            )
        except Exception as e:
            log.exception(
                "Exception calling pverify.",
                member_health_plan_id=self.member_health_plan,
                error=e,
            )
            raise

        # note: _get_deductible_oop only needs the rte transaction id
        eligibility_info = self.rte_processor._get_deductible_oop(
            rte_transaction=rte_transaction,
            employer_health_plan=self.member_health_plan.employer_health_plan,
            plan_size=FamilyPlanType(self.member_health_plan.plan_type),
            tier=self.tier,
        )

        if self.deductible_accumulation_enabled:
            eligibility_info = self.rte_processor._get_copay_coinsurance(
                eligibility_info=eligibility_info,
                cost_sharings=self.member_health_plan.employer_health_plan.cost_sharings,
                cost_sharing_category=self.cost_sharing_category,
                procedure_type=self.procedure_type,
                tier=self.tier,
            )

        self._validate_real_time_eligibility_info(
            eligibility_info=eligibility_info, rte_transaction=rte_transaction
        )
        return eligibility_info, rte_transaction.id

    def _rx_not_integrated_rte_request(self) -> Tuple[EligibilityInfo, RteIdType]:
        log.info("Non-RX integrated RTE request")
        if self.rx_ytd_spend is None:
            raise errors.ActionableCostBreakdownException(
                "Missing year to date spend information for Non-RX integrated RTE request."
            )

        employer_health_plan = self.member_health_plan.employer_health_plan
        eligibility_info = EligibilityInfo()
        if self.deductible_accumulation_enabled:
            eligibility_info = set_db_copay_coinsurance_to_eligibility_info(
                eligibility_info=eligibility_info,
                cost_sharings=employer_health_plan.cost_sharings,
                cost_sharing_category=self.cost_sharing_category,
                tier=self.tier,
            )
        coverage = get_rx_coverage(
            ehp=employer_health_plan,
            plan_size=FamilyPlanType(self.member_health_plan.plan_type),
            tier=self.tier,
        )
        if self.member_health_plan.is_family_plan:
            eligibility_info.family_deductible = coverage.family_deductible
            eligibility_info.family_deductible_remaining = max(
                eligibility_info.family_deductible
                - self.rx_ytd_spend.family_ytd_deductible,
                0,
            )
            eligibility_info.family_oop = coverage.family_oop
            eligibility_info.family_oop_remaining = max(
                eligibility_info.family_oop - self.rx_ytd_spend.family_ytd_oop, 0
            )
        eligibility_info.individual_deductible = coverage.individual_deductible
        eligibility_info.individual_deductible_remaining = max(
            eligibility_info.individual_deductible
            - self.rx_ytd_spend.ind_ytd_deductible,
            0,
        )
        eligibility_info.individual_oop = coverage.individual_oop
        eligibility_info.individual_oop_remaining = max(
            eligibility_info.individual_oop - self.rx_ytd_spend.ind_ytd_oop, 0
        )
        eligibility_info.is_deductible_embedded = coverage.is_deductible_embedded
        eligibility_info.is_oop_embedded = coverage.is_oop_embedded
        # max_oop_per_covered_individual will usually be null, which is both valid and correct.
        eligibility_info.max_oop_per_covered_individual = (
            coverage.max_oop_per_covered_individual
        )
        # RX RTE doesn't hit pverify, so we have no RTE id.
        return eligibility_info, None

    def _validate_real_time_eligibility_info(
        self, eligibility_info: EligibilityInfo, rte_transaction: RTETransaction
    ) -> None:
        is_family_plan: bool = self.member_health_plan.is_family_plan

        is_individual_deductible_or_oop_null: bool = (
            eligibility_info.individual_deductible_remaining is None
            or eligibility_info.individual_oop_remaining is None
        )
        is_family_deductible_or_oop_null: bool = (
            eligibility_info.family_deductible_remaining is None
            or eligibility_info.family_oop_remaining is None
        )

        if is_family_plan:
            if is_family_deductible_or_oop_null:
                log.error(
                    "RTEProcessor issue: no family ytd amount returned for family plan",
                    member_health_plan_id=self.member_health_plan.id,
                    rte_transacton_id=rte_transaction.id,
                    family_deductible_remaining=eligibility_info.family_deductible_remaining,
                    family_oop_remaining=eligibility_info.family_oop_remaining,
                )
                raise NoFamilyDeductibleOopRemaining(
                    "No family deductible remaining or oop remaining for family plan, "
                    f"rte transaction id: {rte_transaction.id}, "
                    f"member health plan id: {self.member_health_plan.id}"
                )
            if (
                eligibility_info.is_deductible_embedded
                and eligibility_info.individual_deductible_remaining is None
            ):
                log.error(
                    "RTEProcessor issue: no individual ytd deductible returned for embedded family plan",
                    member_health_plan_id=self.member_health_plan.id,
                    rte_transacton_id=rte_transaction.id,
                    is_deductible_embedded=eligibility_info.is_deductible_embedded,
                    is_oop_embedded=eligibility_info.is_oop_embedded,
                    family_deductible_remaining=eligibility_info.family_deductible_remaining,
                    family_oop_remaining=eligibility_info.family_oop_remaining,
                    individual_deductible_remaining=eligibility_info.individual_deductible_remaining,
                    individual_oop_remaining=eligibility_info.individual_oop_remaining,
                )
                raise NoIndividualDeductibleOopRemaining(
                    plan=self.member_health_plan,
                    rte_transaction=rte_transaction,
                    message="No individual ytd deductible returned for embedded family plan, "
                    f"rte transaction id: {rte_transaction.id}, "
                    f"member health plan id: {self.member_health_plan.id}",
                )

            if (
                eligibility_info.is_oop_embedded
                and eligibility_info.individual_oop_remaining is None
            ):
                log.error(
                    "RTEProcessor issue: no individual ytd oop returned for embedded family plan",
                    member_health_plan_id=self.member_health_plan.id,
                    rte_transacton_id=rte_transaction.id,
                    is_deductible_embedded=eligibility_info.is_deductible_embedded,
                    is_oop_embedded=eligibility_info.is_oop_embedded,
                    family_deductible_remaining=eligibility_info.family_deductible_remaining,
                    family_oop_remaining=eligibility_info.family_oop_remaining,
                    individual_deductible_remaining=eligibility_info.individual_deductible_remaining,
                    individual_oop_remaining=eligibility_info.individual_oop_remaining,
                )
                raise NoIndividualDeductibleOopRemaining(
                    rte_transaction=rte_transaction,
                    plan=self.member_health_plan,
                    message="No individual oop remaining for embedded family plan, "
                    f"rte transaction id: {rte_transaction.id}, "
                    f"member health plan id: {self.member_health_plan.id}",
                )

        if not is_family_plan and is_individual_deductible_or_oop_null:
            log.error(
                "RTEProcessor issue: no individual ytd amount returned for individual plan",
                member_health_plan_id=self.member_health_plan.id,
                rte_transacton_id=rte_transaction.id,
                individual_deductible_remaining=eligibility_info.individual_deductible_remaining,
                individual_oop_remaining=eligibility_info.individual_oop_remaining,
            )
            raise NoIndividualDeductibleOopRemaining(
                plan=self.member_health_plan,
                rte_transaction=rte_transaction,
                message="No individual deductible remaining or oop remaining for individual plan, "
                f"rte transaction id: {rte_transaction.id}, "
                f"member health plan id: {self.member_health_plan.id}",
            )
