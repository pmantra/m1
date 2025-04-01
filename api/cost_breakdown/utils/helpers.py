from __future__ import annotations

import datetime
from typing import Callable, List, Optional

from maven import feature_flags
from sqlalchemy import case

from cost_breakdown.constants import AmountType, PlanCoverage, Tier
from cost_breakdown.errors import (
    NoCostSharingFoundError,
    NoIrsDeductibleFoundError,
    TieredConfigurationError,
)
from cost_breakdown.models.cost_breakdown import (
    CostBreakdown,
    CostBreakdownIrsMinimumDeductible,
)
from cost_breakdown.models.rte import EligibilityInfo
from direct_payment.clinic.models.clinic import FertilityClinicLocation
from direct_payment.treatment_procedure.models.treatment_procedure import (
    TreatmentProcedure,
    TreatmentProcedureStatus,
)
from storage.connection import db
from utils.log import logger
from wallet.models.constants import (
    BenefitTypes,
    CostSharingCategory,
    CostSharingType,
    CoverageType,
    FamilyPlanType,
)
from wallet.models.reimbursement import ReimbursementRequest
from wallet.models.reimbursement_organization_settings import (
    EmployerHealthPlan,
    EmployerHealthPlanCostSharing,
)
from wallet.models.reimbursement_wallet import MemberHealthPlan, ReimbursementWallet
from wallet.utils.common import get_pending_reimbursement_requests_costs

log = logger(__name__)


def get_amount_type(plan: MemberHealthPlan) -> AmountType:
    if plan and plan.is_family_plan:
        return AmountType.FAMILY
    else:
        return AmountType.INDIVIDUAL


def get_irs_limit(is_individual: bool) -> int:
    irs_limit = CostBreakdownIrsMinimumDeductible.query.filter_by(
        year=datetime.date.today().year
    ).one_or_none()
    if irs_limit is None:
        raise NoIrsDeductibleFoundError("no irs deductible found for this year")
    if is_individual:
        threshold = irs_limit.individual_amount
    else:
        threshold = irs_limit.family_amount
    return threshold


def get_cycle_based_wallet_balance_from_credit(  # type: ignore[no-untyped-def] # Function is missing a return type annotation
    wallet: ReimbursementWallet,
    category_id: int,
    cost_credit: int,
    cost: int,
):
    benefit_type = wallet.category_benefit_type(request_category_id=category_id)
    if benefit_type != BenefitTypes.CYCLE:
        log.error("Wallet is not a credit wallet.", wallet_id=wallet.id)
        return None
    category_credit_balance = wallet.available_credit_amount_by_category.get(
        category_id
    )
    prorated_amount = (
        1 if cost_credit == 0 else min(category_credit_balance / cost_credit, 1)
    )
    wallet_balance = prorated_amount * cost
    return wallet_balance


def get_scheduled_procedure_costs(
    wallet: ReimbursementWallet, remaining_balance: int
) -> int:
    """
    Returns:
        int: Sum of treatment_procedure cost (employer responsibility) for scheduled treatment_procedures
        associated with the wallet. If cycle based credits are returned. If currency cents returned.
    """
    scheduled_tps_with_cost_breakdowns = (
        db.session.query(TreatmentProcedure, CostBreakdown)
        .join(CostBreakdown, TreatmentProcedure.cost_breakdown_id == CostBreakdown.id)
        .filter(
            TreatmentProcedure.reimbursement_wallet_id == wallet.id,
            TreatmentProcedure.status == TreatmentProcedureStatus.SCHEDULED,
        )
        .all()
    )
    scheduled_costs = _compute_scheduled_costs(
        wallet, remaining_balance, scheduled_tps_with_cost_breakdowns
    )

    return scheduled_costs


def get_scheduled_procedure_costs_for_clinic_portal(
    wallet: ReimbursementWallet, remaining_balance: int
) -> int:
    """
    Returns:
        int: Sum of treatment_procedure cost (employer responsibility) for scheduled treatment_procedures
        associated with the wallet. If cycle based credits are returned. If currency cents returned. \
        For clinic portal - the absence of a cost breakdown for a cycle based treatment can be handled by using the
        cycle cost stamped on the treatment procedure. While this is not guaranteed as accurate, since the CB may
        evaluate to 0 employer responsibility, product is okay with this to achieve an immediate update to the
        member's credit balance in clinic portal.
    """

    scheduled_tps_with_or_without_cost_breakdowns = (
        db.session.query(TreatmentProcedure, CostBreakdown)
        .outerjoin(
            CostBreakdown, TreatmentProcedure.cost_breakdown_id == CostBreakdown.id
        )
        .filter(
            TreatmentProcedure.reimbursement_wallet_id == wallet.id,
            TreatmentProcedure.status == TreatmentProcedureStatus.SCHEDULED,
        )
        .order_by(case([(CostBreakdown.id != None, 0)], else_=1))
        .all()
    )
    scheduled_costs = _compute_scheduled_costs(
        wallet, remaining_balance, scheduled_tps_with_or_without_cost_breakdowns
    )

    return scheduled_costs


def _compute_scheduled_costs(
    wallet: ReimbursementWallet,
    remaining_balance: int,
    scheduled_tps_with_or_without_cost_breakdowns: list,
) -> int:
    scheduled_costs = 0
    for tp, cb in scheduled_tps_with_or_without_cost_breakdowns:
        benefit_type = wallet.category_benefit_type(
            request_category_id=tp.reimbursement_request_category_id
        )
        # if the caller used join, cb will never be none. If the caller used outer-left then none cb is possible.
        # if a cb exists, check the cb total resp -
        if cb and cb.total_employer_responsibility > 0:
            if benefit_type == BenefitTypes.CYCLE:
                # we don't want a negative balance
                scheduled_costs += min(
                    tp.cost_credit if tp.cost_credit is not None else 0,
                    remaining_balance - scheduled_costs,
                )
            else:
                scheduled_costs += cb.total_employer_responsibility

        # because of the asynch nature of cb generation - this value may be inaccurate, if the CB claims 0 employer
        # responsibility. However, product is okay with this compromise. Enter the following block only if the cost
        # breakdown is missing.
        elif cb is None:
            if benefit_type == BenefitTypes.CYCLE:
                # we don't want a negative balance
                scheduled_costs += min(
                    tp.cost_credit if tp.cost_credit is not None else 0,
                    remaining_balance - scheduled_costs,
                )
            else:
                scheduled_costs += min(tp.cost, remaining_balance - scheduled_costs)
    return scheduled_costs


def get_scheduled_tp_and_pending_rr_costs(
    wallet: ReimbursementWallet, remaining_balance: int
) -> int:
    """
    Returns:
        int: Sum of scheduled treatment_procedures and pending reimbursement requests
        associated with the wallet
    """
    return _compute_scheduled_tp_and_pending_rr_costs(
        wallet, remaining_balance, get_scheduled_procedure_costs
    )


def get_scheduled_tp_and_pending_rr_costs_for_clinic_portal(
    wallet: ReimbursementWallet, remaining_balance: int
) -> int:
    """
    Returns:
        int: Sum of scheduled treatment_procedures and pending reimbursement requests
        associated with the wallet
    """
    return _compute_scheduled_tp_and_pending_rr_costs(
        wallet, remaining_balance, get_scheduled_procedure_costs_for_clinic_portal
    )


def _compute_scheduled_tp_and_pending_rr_costs(
    wallet: ReimbursementWallet,
    remaining_balance: int,
    scheduled_costs_computation_fn: Callable,
) -> int:
    scheduled_costs = scheduled_costs_computation_fn(
        wallet=wallet, remaining_balance=remaining_balance
    )
    # For cycle based wallets we don't want to show a negative balance, so
    # we recalculate remaining balance given scheduled costs
    updated_remaining_balance = remaining_balance - scheduled_costs
    pending_reimbursements = get_pending_reimbursement_requests_costs(
        wallet=wallet, remaining_balance=updated_remaining_balance
    )
    pending_costs = scheduled_costs + pending_reimbursements
    return pending_costs


def is_plan_tiered(ehp: EmployerHealthPlan) -> bool:
    if _employer_health_plan_deprecated(ehp):
        return False
    return (
        len(list(filter(lambda coverage: coverage.tier is not None, ehp.coverage))) > 0
    )


def get_medical_coverage(
    ehp: EmployerHealthPlan, plan_size: FamilyPlanType, tier: Optional[Tier] = None
) -> PlanCoverage:
    return _get_coverage(
        ehp=ehp, plan_size=plan_size, coverage_type=CoverageType.MEDICAL, tier=tier
    )


def get_rx_coverage(
    ehp: EmployerHealthPlan, plan_size: FamilyPlanType, tier: Optional[Tier] = None
) -> PlanCoverage:
    return _get_coverage(
        ehp=ehp, plan_size=plan_size, coverage_type=CoverageType.RX, tier=tier
    )


def _get_coverage(
    ehp: EmployerHealthPlan,
    coverage_type: CoverageType,
    plan_size: FamilyPlanType,
    tier: Optional[Tier] = None,
) -> PlanCoverage:
    if (
        not feature_flags.bool_variation("enable-switch-ehp-coverage", default=False)
    ) and _employer_health_plan_deprecated(ehp=ehp):
        log.info(
            "Fetching employer health plan coverage using deprecated model",
            employer_health_plan_id=ehp.id,
        )
        if tier is not None:
            log.error(
                "EmployerHealthPlans with deprecated coverage configuration cannot be tiered.",
                employer_health_plan_id=ehp.id,
            )
            raise ValueError(
                "EmployerHealthPlans with deprecated coverage configuration cannot be tiered."
            )
        if coverage_type == CoverageType.MEDICAL:
            return PlanCoverage(
                individual_deductible=ehp.ind_deductible_limit,
                family_deductible=ehp.fam_deductible_limit,
                individual_oop=ehp.ind_oop_max_limit,
                family_oop=ehp.fam_oop_max_limit,
                max_oop_per_covered_individual=ehp.max_oop_per_covered_individual,
                is_deductible_embedded=ehp.is_deductible_embedded,
                is_oop_embedded=ehp.is_oop_embedded,
            )
        elif coverage_type == CoverageType.RX:
            return PlanCoverage(
                individual_deductible=ehp.rx_ind_deductible_limit,
                family_deductible=ehp.rx_fam_deductible_limit,
                individual_oop=ehp.rx_ind_oop_max_limit,
                family_oop=ehp.rx_fam_oop_max_limit,
                max_oop_per_covered_individual=ehp.max_oop_per_covered_individual,
                is_deductible_embedded=ehp.is_deductible_embedded,
                is_oop_embedded=ehp.is_oop_embedded,
            )
        else:
            log.error(
                "Invalid coverage type for deprecated employer health plan coverage model",
                employer_health_plan_id=ehp.id,
            )
            raise ValueError(
                "Invalid coverage type for deprecated employer health plan coverage model"
            )
    log.info(
        "Fetching employer health plan coverage using new model",
        employer_health_plan_id=ehp.id,
    )
    coverage_match = list(
        filter(
            lambda coverage: coverage.tier == tier
            and coverage.coverage_type == coverage_type
            and coverage.plan_type == plan_size,
            ehp.coverage,
        )
    )
    if len(coverage_match) > 1:
        raise TieredConfigurationError(
            "Found multiple configuration matches for Employer Health Plan Coverage."
        )
    if len(coverage_match) < 1:
        raise TieredConfigurationError(
            "Found no matching Employer Health Plan Coverage configurations."
        )
    coverage = coverage_match[0]
    return PlanCoverage(
        individual_deductible=coverage.individual_deductible,
        family_deductible=coverage.family_deductible,
        individual_oop=coverage.individual_oop,
        family_oop=coverage.family_oop,
        max_oop_per_covered_individual=coverage.max_oop_per_covered_individual,
        is_deductible_embedded=coverage.is_deductible_embedded,
        is_oop_embedded=coverage.is_oop_embedded,
    )


def get_calculation_tier(
    ehp: EmployerHealthPlan,
    fertility_clinic_location: FertilityClinicLocation,
    treatment_procedure_start: datetime.date,
) -> Tier:
    if not is_plan_tiered(ehp):
        log.error("Error retrieving tier - EmployerHealthPlan is not tiered")
        raise ValueError("Error retrieving tier - EmployerHealthPlan is not tiered")
    if not ehp.tiers:
        return Tier.SECONDARY
    tier_match = list(
        filter(
            lambda tier: tier.fertility_clinic_location_id
            == fertility_clinic_location.id
            and tier.start_date <= treatment_procedure_start <= tier.end_date,
            ehp.tiers,
        )
    )
    return Tier.PREMIUM if tier_match else Tier.SECONDARY


def _employer_health_plan_deprecated(ehp: EmployerHealthPlan) -> bool:
    return ehp.created_at.replace(
        tzinfo=datetime.timezone.utc
    ) < datetime.datetime.strptime("23/10/2024 23:59", "%d/%m/%Y %H:%M").replace(
        tzinfo=datetime.timezone.utc
    )


def get_effective_date_from_cost_breakdown(
    cost_breakdown: CostBreakdown,
) -> datetime.datetime | None:
    effective_date = None
    if cost_breakdown.treatment_procedure_uuid is not None:
        # Get the date from the associated procedure
        procedure_date = (
            db.session.query(TreatmentProcedure.start_date)
            .filter(
                TreatmentProcedure.uuid == cost_breakdown.treatment_procedure_uuid,
                TreatmentProcedure.cost_breakdown_id == cost_breakdown.id,
            )
            .scalar()
        )
        if procedure_date:
            effective_date = datetime.datetime(
                year=procedure_date.year,
                month=procedure_date.month,
                day=procedure_date.day,
            )
    elif cost_breakdown.reimbursement_request_id is not None:
        effective_date = (
            db.session.query(ReimbursementRequest.service_start_date)
            .filter(ReimbursementRequest.id == cost_breakdown.reimbursement_request_id)
            .scalar()
        )
    return effective_date


def set_db_copay_coinsurance_to_eligibility_info(
    eligibility_info: EligibilityInfo,
    cost_sharings: List[EmployerHealthPlanCostSharing],
    cost_sharing_category: CostSharingCategory,
    tier: Optional[Tier] = None,
) -> EligibilityInfo:
    copay = coinsurance = coinsurance_min = coinsurance_max = None
    ignore_deductible: bool = False
    is_second_tier = True if tier and tier == Tier.SECONDARY else False
    for cost_sharing_entry in cost_sharings:
        if cost_sharing_entry.cost_sharing_category == cost_sharing_category:
            if cost_sharing_entry.cost_sharing_type == CostSharingType.COPAY:
                copay = (
                    cost_sharing_entry.absolute_amount
                    if not is_second_tier
                    else cost_sharing_entry.second_tier_absolute_amount
                )
            elif (
                cost_sharing_entry.cost_sharing_type
                == CostSharingType.COPAY_NO_DEDUCTIBLE
            ):
                copay = (
                    cost_sharing_entry.absolute_amount
                    if not is_second_tier
                    else cost_sharing_entry.second_tier_absolute_amount
                )
                ignore_deductible = True
            elif cost_sharing_entry.cost_sharing_type == CostSharingType.COINSURANCE:
                coinsurance = (
                    cost_sharing_entry.percent
                    if not is_second_tier
                    else cost_sharing_entry.second_tier_percent
                )
            elif (
                cost_sharing_entry.cost_sharing_type
                == CostSharingType.COINSURANCE_NO_DEDUCTIBLE
            ):
                coinsurance = (
                    cost_sharing_entry.percent
                    if not is_second_tier
                    else cost_sharing_entry.second_tier_percent
                )
                ignore_deductible = True
            elif (
                cost_sharing_entry.cost_sharing_type == CostSharingType.COINSURANCE_MIN
            ):
                coinsurance_min = (
                    cost_sharing_entry.absolute_amount
                    if not is_second_tier
                    else cost_sharing_entry.second_tier_absolute_amount
                )
            elif (
                cost_sharing_entry.cost_sharing_type == CostSharingType.COINSURANCE_MAX
            ):
                coinsurance_max = (
                    cost_sharing_entry.absolute_amount
                    if not is_second_tier
                    else cost_sharing_entry.second_tier_absolute_amount
                )

    if copay is not None:
        log.info("Copay found for rte check.", copay=copay)
        eligibility_info.copay = copay
    elif coinsurance is not None:
        log.info(
            "Coinsurance found for rte check.",
            coinsurance=coinsurance,
        )
        eligibility_info.coinsurance = coinsurance
        eligibility_info.coinsurance_max = coinsurance_max
        eligibility_info.coinsurance_min = coinsurance_min
    else:
        # Log used in alerting
        log.error(
            "Maven managed plan did not find cost sharing.",
            cost_sharings=" ".join(str(c_s.id) for c_s in cost_sharings),
        )
        raise NoCostSharingFoundError(
            f"No cost sharing found for employer health plan"
            f"cost sharing category {cost_sharing_category}"
        )
    eligibility_info.ignore_deductible = ignore_deductible
    return eligibility_info
