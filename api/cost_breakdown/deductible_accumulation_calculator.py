import dataclasses
from decimal import Decimal
from typing import Optional, Tuple

from cost_breakdown import errors
from cost_breakdown.models.rte import EligibilityInfo
from utils.log import logger
from wallet.models.reimbursement_wallet import MemberHealthPlan

log = logger(__name__)


@dataclasses.dataclass
class MemberTotalChargeBreakdown:
    member_responsibility: int = 0
    coinsurance: int = 0
    copay: int = 0
    overage_amount: int = 0


@dataclasses.dataclass
class MemberBaseChargeBreakdown:
    member_responsibility: int = 0
    copay: int = 0
    coinsurance: int = 0


@dataclasses.dataclass
class BenefitsAccumulationSummary:
    __slots__ = (
        "individual_deductible_remaining",
        "family_deductible_remaining",
        "deductible_apply",
        "individual_oop_remaining",
        "family_oop_remaining",
        "oop_apply",
    )
    individual_deductible_remaining: int
    family_deductible_remaining: int
    deductible_apply: int
    individual_oop_remaining: int
    family_oop_remaining: int
    oop_apply: int


class DeductibleAccumulationCalculator:
    def calculate_member_cost_breakdown(
        self,
        treatment_cost: int,
        is_unlimited: bool,
        wallet_balance: int,
        member_health_plan: MemberHealthPlan,
        eligibility_info: EligibilityInfo,
    ) -> MemberTotalChargeBreakdown:
        log.info(
            "Calculating member cost breakdown values for member health plan",
            member_health_plan_id=member_health_plan.id,
        )
        is_individual = not member_health_plan.is_family_plan
        if (
            eligibility_info.is_oop_embedded is None
            or eligibility_info.is_deductible_embedded is None
        ):
            raise ValueError("Embedded settings not found on EligibilityInfo")
        relevant_deductible_remaining = self._choose_remaining(
            is_individual=is_individual,
            is_embedded=eligibility_info.is_deductible_embedded,
            individual_remaining=eligibility_info.individual_deductible_remaining,  # type: ignore[arg-type] # Argument "individual_remaining" to "_choose_remaining" of "DeductibleAccumulationCalculator" has incompatible type "Optional[int]"; expected "int"
            family_remaining=eligibility_info.family_deductible_remaining,  # type: ignore[arg-type] # Argument "family_remaining" to "_choose_remaining" of "DeductibleAccumulationCalculator" has incompatible type "Optional[int]"; expected "int"
        )
        relevant_oop_remaining = self._choose_remaining(
            is_individual=is_individual,
            is_embedded=eligibility_info.is_oop_embedded,
            individual_remaining=eligibility_info.individual_oop_remaining,  # type: ignore[arg-type] # Argument "individual_remaining" to "_choose_remaining" of "DeductibleAccumulationCalculator" has incompatible type "Optional[int]"; expected "int"
            family_remaining=eligibility_info.family_oop_remaining,  # type: ignore[arg-type] # Argument "family_remaining" to "_choose_remaining" of "DeductibleAccumulationCalculator" has incompatible type "Optional[int]"; expected "int"
            max_limit=eligibility_info.max_oop_per_covered_individual,
        )
        member_charge_summary = self._calculate_member_total_charge(
            treatment_cost=treatment_cost,
            deductible_remaining=relevant_deductible_remaining
            if not eligibility_info.ignore_deductible
            else 0,
            oop_remaining=relevant_oop_remaining,
            is_unlimited=is_unlimited,
            wallet_balance=wallet_balance,
            copay=eligibility_info.copay,  # type: ignore[arg-type] # Argument "copay" to "_calculate_member_total_charge" of "DeductibleAccumulationCalculator" has incompatible type "Optional[int]"; expected "int"
            coinsurance=eligibility_info.coinsurance,  # type: ignore[arg-type] # Argument "coinsurance" to "_calculate_member_total_charge" of "DeductibleAccumulationCalculator" has incompatible type "Optional[Decimal]"; expected "int"
            coinsurance_min=eligibility_info.coinsurance_min,
            coinsurance_max=eligibility_info.coinsurance_max,
        )
        return member_charge_summary

    def _calculate_member_total_charge(
        self,
        treatment_cost: int,
        deductible_remaining: int,
        oop_remaining: int,
        is_unlimited: bool,
        wallet_balance: int,
        copay: int,
        coinsurance: int,
        coinsurance_min: Optional[int],
        coinsurance_max: Optional[int],
    ) -> MemberTotalChargeBreakdown:
        base_member_charge = self._calc_base_member_charge(
            treatment_cost=treatment_cost,
            deductible_remaining=deductible_remaining,
            oop_remaining=oop_remaining,
            coinsurance=coinsurance,
            coinsurance_min=coinsurance_min,
            coinsurance_max=coinsurance_max,
            copay=copay,
        )
        cost_remainder = treatment_cost - base_member_charge.member_responsibility
        if is_unlimited or cost_remainder <= wallet_balance:
            return MemberTotalChargeBreakdown(
                member_responsibility=base_member_charge.member_responsibility,
                copay=base_member_charge.copay,
                coinsurance=base_member_charge.coinsurance,
            )
        else:
            overage_amount = cost_remainder - wallet_balance
            member_charge = base_member_charge.member_responsibility + overage_amount
            return MemberTotalChargeBreakdown(
                member_responsibility=member_charge,
                overage_amount=overage_amount,
                copay=base_member_charge.copay,
                coinsurance=base_member_charge.coinsurance,
            )

    def calculate_accumulation_values(
        self,
        member_health_plan: MemberHealthPlan,
        eligibility_info: EligibilityInfo,
        member_charge: int,
    ) -> BenefitsAccumulationSummary:
        log.info(
            "Calculating accumulation values for member health plan",
            member_health_plan_id=member_health_plan.id,
        )
        is_individual = not member_health_plan.is_family_plan
        if (
            eligibility_info.is_oop_embedded is None
            or eligibility_info.is_deductible_embedded is None
        ):
            raise ValueError("Embedded settings not found on EligibilityInfo")

        if eligibility_info.ignore_deductible:
            deductible_apply = 0
            individual_deductible_remaining = (
                eligibility_info.individual_deductible_remaining
            )
            family_deductible_remaining = eligibility_info.family_deductible_remaining
        else:
            (
                deductible_apply,
                individual_deductible_remaining,
                family_deductible_remaining,
            ) = self._apply_charge_to_individual_family_limit(
                is_individual=is_individual,
                is_embedded=eligibility_info.is_deductible_embedded,
                individual_remaining=eligibility_info.individual_deductible_remaining,
                family_remaining=eligibility_info.family_deductible_remaining,
                member_charge=member_charge,
            )
        (
            oop_apply,
            individual_oop_remaining,
            family_oop_remaining,
        ) = self._apply_charge_to_individual_family_limit(
            is_individual=is_individual,
            is_embedded=eligibility_info.is_oop_embedded,
            individual_remaining=eligibility_info.individual_oop_remaining,
            family_remaining=eligibility_info.family_oop_remaining,
            member_charge=member_charge,
        )
        return BenefitsAccumulationSummary(
            individual_deductible_remaining=individual_deductible_remaining,  # type: ignore[arg-type] # Argument "individual_deductible_remaining" to "BenefitsAccumulationSummary" has incompatible type "int | None"; expected "int"
            family_deductible_remaining=family_deductible_remaining,  # type: ignore[arg-type] # Argument "family_deductible_remaining" to "BenefitsAccumulationSummary" has incompatible type "Optional[int]"; expected "int"
            deductible_apply=deductible_apply,
            individual_oop_remaining=individual_oop_remaining,
            family_oop_remaining=family_oop_remaining,  # type: ignore[arg-type] # Argument "family_oop_remaining" to "BenefitsAccumulationSummary" has incompatible type "Optional[int]"; expected "int"
            oop_apply=oop_apply,
        )

    @staticmethod
    def _choose_remaining(
        is_individual: bool,
        is_embedded: bool,
        individual_remaining: int,
        family_remaining: int,
        max_limit: Optional[int] = None,
    ) -> int:
        if is_individual:
            return individual_remaining
        elif is_embedded:
            try:
                return min(individual_remaining, family_remaining)
            except TypeError as e:
                log.error(
                    "Missing required data for embedded cost breakdown calculations",
                    individual_remaining=individual_remaining,
                    family_remaining=family_remaining,
                )
                raise errors.ActionableCostBreakdownException(
                    "Missing required individual or family data for embedded calculations."
                ) from e
        else:
            # PAY-6009: the individual max limit is only applied to non-embedded plans
            return min(family_remaining, max_limit) if max_limit else family_remaining

    @staticmethod
    def _calc_base_member_charge(
        treatment_cost: int,
        deductible_remaining: int,
        oop_remaining: int,
        copay: int,
        coinsurance: int,
        coinsurance_min: Optional[int],
        coinsurance_max: Optional[int],
    ) -> MemberBaseChargeBreakdown:
        try:
            if treatment_cost <= deductible_remaining:
                # if the cost is entirely covered by the deductible, the member's responsibility is the cost
                return MemberBaseChargeBreakdown(member_responsibility=treatment_cost)

            # if the cost is greater than the deductible, the member's responsibility is more complicated
            cost_without_deductible = treatment_cost - deductible_remaining
            if coinsurance is not None:
                coinsurance = int(round(Decimal(coinsurance) * cost_without_deductible))
                if coinsurance_max is not None and coinsurance_min is not None:
                    if coinsurance >= coinsurance_max:
                        coinsurance_charge = coinsurance_max
                    elif coinsurance_min < coinsurance < coinsurance_max:
                        coinsurance_charge = coinsurance
                    else:
                        coinsurance_charge = coinsurance_min
                elif coinsurance_max is not None and coinsurance >= coinsurance_max:
                    coinsurance_charge = coinsurance_max
                elif coinsurance_min is not None and coinsurance <= coinsurance_min:
                    coinsurance_charge = coinsurance_min
                else:
                    coinsurance_charge = coinsurance
                member_charge = coinsurance_charge + deductible_remaining
                coinsurance = coinsurance_charge
            elif copay is not None:
                member_charge = copay + deductible_remaining
            else:
                raise errors.ActionableCostBreakdownException(
                    "Cannot calculate a base member charge with null copay and coinsurance values."
                )

            fair_member_charge = min(member_charge, oop_remaining, treatment_cost)
            if copay is not None and fair_member_charge < copay:
                copay = fair_member_charge
            if coinsurance is not None and fair_member_charge < coinsurance:
                coinsurance = fair_member_charge
        except TypeError as e:
            # This should catch any attempts to do comparisons/subtraction/min with null values
            log.error(
                "Missing required data for base member charge calculations.",
                treatment_cost=treatment_cost,
                deductible_remaining=deductible_remaining,
                oop_remaining=oop_remaining,
                copay=copay,
                coinsurance=coinsurance,
            )
            raise errors.ActionableCostBreakdownException(
                "Missing required data for base member charge calculations."
            ) from e
        return MemberBaseChargeBreakdown(
            member_responsibility=fair_member_charge,
            copay=copay or 0,
            coinsurance=coinsurance or 0,
        )

    @staticmethod
    def _apply_charge_to_individual_family_limit(
        is_individual: bool,
        is_embedded: bool,
        individual_remaining: Optional[int],
        family_remaining: Optional[int],
        member_charge: int,
    ) -> Tuple[int, int, Optional[int]]:
        log.info(
            "Applying member charge to benefits calculations",
            is_embedded=is_embedded,
        )
        try:
            if is_individual:
                return (  # type: ignore[return-value] # Incompatible return value type (got "Tuple[Optional[int], int, None]", expected "Tuple[int, int, Optional[int]]")
                    min(individual_remaining, member_charge),  # type: ignore[type-var] # Value of type variable "SupportsRichComparisonT" of "min" cannot be "Optional[int]"
                    max(individual_remaining - member_charge, 0),
                    None,
                )
            elif is_embedded:
                remaining = min(individual_remaining, family_remaining)  # type: ignore[type-var] # Value of type variable "SupportsRichComparisonT" of "min" cannot be "Optional[int]"
                apply_amount = min(remaining, member_charge)  # type: ignore[type-var] # Value of type variable "SupportsRichComparisonT" of "min" cannot be "Optional[int]"
                individual_remaining = max(individual_remaining - apply_amount, 0)
            else:
                apply_amount = min(family_remaining, member_charge)  # type: ignore[type-var] # Value of type variable "SupportsRichComparisonT" of "min" cannot be "Optional[int]"
                individual_remaining = None
            family_remaining = max(family_remaining - apply_amount, 0)
            return apply_amount, individual_remaining, family_remaining  # type: ignore[return-value] # Incompatible return value type (got "Tuple[Optional[int], Optional[int], Union[int, Any]]", expected "Tuple[int, int, Optional[int]]")
        except TypeError as e:
            # This should catch any attempts to do comparisons/subtraction/min with null values
            log.error(
                "Missing required data for member charge benefits calculations.",
                is_individual=is_individual,
                is_embedded=is_embedded,
                individual_remaining=individual_remaining,
                family_remaining=family_remaining,
                member_charge=member_charge,
            )
            raise errors.ActionableCostBreakdownException(
                "Missing required data for member charge benefits calculations.",
            ) from e
