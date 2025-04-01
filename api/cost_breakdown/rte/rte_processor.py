from __future__ import annotations

from typing import List, Optional, Tuple

from authn.models.user import User
from cost_breakdown.constants import Tier
from cost_breakdown.errors import (
    NoFamilyDeductibleOopRemaining,
    NoIndividualDeductibleOopRemaining,
    NoPatientNameFoundError,
    TieredRTEError,
)
from cost_breakdown.models.rte import (
    EligibilityInfo,
    RTETransaction,
    TieredRTEErrorData,
)
from cost_breakdown.rte.pverify_api import PverifyAPI
from cost_breakdown.utils.helpers import (
    get_medical_coverage,
    set_db_copay_coinsurance_to_eligibility_info,
)
from direct_payment.treatment_procedure.models.treatment_procedure import (
    TreatmentProcedure,
    TreatmentProcedureType,
)
from utils.log import logger
from wallet.models.constants import CostSharingCategory, FamilyPlanType
from wallet.models.reimbursement_organization_settings import (
    EmployerHealthPlan,
    EmployerHealthPlanCostSharing,
)
from wallet.models.reimbursement_wallet import MemberHealthPlan

log = logger(__name__)


def get_member_name_from_user_id(user_id: int) -> Tuple[Optional[str], Optional[str]]:
    member = User.query.get(user_id)
    if member:
        (member_first_name, member_last_name) = (
            member.first_name,
            member.last_name,
        )
        if member_first_name and member_last_name:
            return member_first_name, member_last_name
        else:
            log.error(f"Missing dependent name for user {user_id}")
    else:
        log.error(f"No member found for user {user_id}")
    return None, None


def get_member_first_and_last_name(
    member_health_plan: Optional[MemberHealthPlan], user_id: int
) -> Tuple[Optional[str], Optional[str]]:
    if member_health_plan:
        if not member_health_plan.is_subscriber:
            member_first_name, member_last_name = (
                member_health_plan.patient_first_name,
                member_health_plan.patient_last_name,
            )
        else:
            member_first_name, member_last_name = (
                member_health_plan.subscriber_first_name,
                member_health_plan.subscriber_last_name,
            )
        if member_first_name and member_last_name:
            return member_first_name, member_last_name
    log.error(
        "Missing member name for health plan, fallback to use user name",
        member_health_plan_id=member_health_plan.id if member_health_plan else None,
        is_subscriber=member_health_plan.is_subscriber if member_health_plan else None,
    )
    return get_member_name_from_user_id(user_id)


class RTEProcessor:
    def __init__(self) -> None:
        self.pverify_api = PverifyAPI()

    def get_rte(
        self,
        treatment_procedure: TreatmentProcedure,
        member_health_plan: MemberHealthPlan,
        cost_sharing_category: CostSharingCategory,
        tier: Optional[Tier],
    ) -> (EligibilityInfo, int):  # type: ignore[syntax] # Syntax error in type annotation
        patient_first_name, patient_last_name = get_member_first_and_last_name(
            user_id=treatment_procedure.member_id, member_health_plan=member_health_plan
        )
        if not patient_first_name or not patient_last_name:
            log.error(
                "RTE processor error: retrieving RTE",
                treatment_procedure_id=treatment_procedure.uuid,
                member_health_plan_id=member_health_plan.id,
                reimbursement_wallet_id=str(
                    treatment_procedure.reimbursement_wallet_id
                ),
            )
            raise NoPatientNameFoundError("Missing patient name")
        try:
            rte_transaction = self.pverify_api.get_real_time_eligibility_data(
                plan=member_health_plan,
                cost_sharing_category=cost_sharing_category,
                member_first_name=patient_first_name,
                member_last_name=patient_last_name,
                is_second_tier=True if tier == Tier.SECONDARY else False,
                service_start_date=treatment_procedure.start_date,
            )
        except Exception as e:
            log.exception(
                "Exception calling pverify.",
                treatment_procedure_uuid=treatment_procedure.uuid,
                member_health_plan_id=member_health_plan.id,
                error=e,
            )
            raise
        employer_health_plan = member_health_plan.employer_health_plan
        eligibility_info = self._get_deductible_oop(
            rte_transaction=rte_transaction,
            employer_health_plan=employer_health_plan,
            plan_size=FamilyPlanType(member_health_plan.plan_type),
            tier=tier,
        )
        if (
            member_health_plan.reimbursement_wallet.reimbursement_organization_settings.deductible_accumulation_enabled
        ):
            eligibility_info = self._get_copay_coinsurance(
                eligibility_info=eligibility_info,
                cost_sharings=employer_health_plan.cost_sharings,
                cost_sharing_category=cost_sharing_category,
                procedure_type=treatment_procedure.procedure_type,  # type: ignore[arg-type] # Argument "procedure_type" to "_get_copay_coinsurance" of "RTEProcessor" has incompatible type "str"; expected "TreatmentProcedureType"
                tier=tier,
            )
        is_individual_plan = member_health_plan.is_family_plan is False
        is_individual_deductible_or_oop_null = (
            eligibility_info.individual_deductible_remaining is None
            or eligibility_info.individual_oop_remaining is None
        )
        is_family_deductible_or_oop_null = (
            eligibility_info.family_deductible_remaining is None
            or eligibility_info.family_oop_remaining is None
        )

        if is_individual_plan and is_individual_deductible_or_oop_null:
            log.error(
                "RTEProcessor issue: eligibility issue with individual plan.",
                member_health_plan_id=member_health_plan.id,
                treatment_procedure_id=treatment_procedure.uuid,
                rte_transacton_id=rte_transaction.id,
                deductible=eligibility_info.individual_deductible,
                out_of_pocket=eligibility_info.individual_oop,
            )
            raise NoIndividualDeductibleOopRemaining(
                plan=member_health_plan,
                rte_transaction=rte_transaction,
                message="No individual deductible remaining or oop remaining, "
                f"rte transaction id: {rte_transaction.id}, "
                f"member health plan id: {member_health_plan.id}",
            )

        if is_individual_plan is False and is_family_deductible_or_oop_null:
            log.error(
                "RTEProcessor issue: eligibility issue with family plan.",
                member_health_plan_id=member_health_plan.id,
                treatment_procedure_id=treatment_procedure.uuid,
                rte_transacton_id=rte_transaction.id,
                deductible=eligibility_info.family_deductible,
                out_of_pocket=eligibility_info.family_oop,
            )
            raise NoFamilyDeductibleOopRemaining(
                "No family deductible remaining or oop remaining, "
                f"rte transaction id: {rte_transaction.id}, "
                f"member health plan id: {member_health_plan.id}"
            )

        return eligibility_info, rte_transaction.id

    def _get_deductible_oop(
        self,
        rte_transaction: RTETransaction,
        employer_health_plan: EmployerHealthPlan,
        plan_size: FamilyPlanType,
        tier: Optional[Tier] = None,
    ) -> EligibilityInfo:
        eligibility_info = EligibilityInfo(**rte_transaction.response)
        coverage = get_medical_coverage(
            ehp=employer_health_plan, plan_size=plan_size, tier=tier
        )

        errors: List[TieredRTEErrorData] = []
        rte_value, coverage_value = None, None
        for attr_name in [
            "individual_deductible",
            "individual_oop",
            "family_deductible",
            "family_oop",
        ]:
            try:
                # compare RTE values and expected values from coverage in the employer plan.
                rte_value = getattr(eligibility_info, attr_name)
                coverage_value = getattr(coverage, attr_name)
            except AttributeError:
                errors.append(
                    TieredRTEErrorData(
                        attr_name=attr_name,
                        rte_value=rte_value,
                        coverage_value=coverage_value,
                    )
                )
                continue

            if rte_value is None and coverage_value is None:
                log.warning(
                    "Missing default value for rte_transaction and employer_health_plan",
                    attr_name=attr_name,
                    employer_health_plan=employer_health_plan.id,
                    rte_transaction=rte_transaction.id,
                )
            elif not rte_value:
                log.info(
                    "Setting default for rte_transaction and employer_health_plan.",
                    attr_name=attr_name,
                    employer_health_plan=employer_health_plan.id,
                    rte_transaction=rte_transaction.id,
                )
                eligibility_info.__setattr__(attr_name, coverage_value)
            elif tier and rte_value != coverage_value:
                log.error(
                    "Tiered calculation has different RTE and configured values",
                    attr_name=attr_name,
                    rte_value=rte_value,
                    coverage_value=coverage_value,
                    tier=tier,
                    rte_transaction_id=rte_transaction.id,
                    employer_health_plan_id=str(employer_health_plan.id),
                )
                errors.append(
                    TieredRTEErrorData(
                        attr_name=attr_name,
                        rte_value=rte_value,
                        coverage_value=coverage_value,
                    )
                )
        if len(errors):
            raise TieredRTEError(
                "RTE returned oop and deductible values that don't match the tier's Employer Health Plan coverage.",
                tier=tier,
                errors=errors,
                plan=employer_health_plan,
            )

        if eligibility_info.individual_deductible == 0:
            eligibility_info.individual_deductible_remaining = 0
        if eligibility_info.individual_oop == 0:
            eligibility_info.individual_oop_remaining = 0
        if eligibility_info.family_deductible == 0:
            eligibility_info.family_deductible_remaining = 0
        if eligibility_info.family_oop == 0:
            eligibility_info.family_oop_remaining = 0

        eligibility_info.is_oop_embedded = coverage.is_oop_embedded
        eligibility_info.is_deductible_embedded = coverage.is_deductible_embedded
        # max_oop_per_covered_individual will usually be null, which is both valid and correct.
        eligibility_info.max_oop_per_covered_individual = (
            coverage.max_oop_per_covered_individual
        )
        return eligibility_info

    def _get_copay_coinsurance(
        self,
        eligibility_info: EligibilityInfo,
        cost_sharings: List[EmployerHealthPlanCostSharing],
        cost_sharing_category: CostSharingCategory,
        procedure_type: TreatmentProcedureType,
        tier: Optional[Tier] = None,
    ) -> EligibilityInfo:
        log.info("Eligibility Info", info=eligibility_info)
        if (
            (eligibility_info.copay is not None)
            and (eligibility_info.coinsurance is not None)
        ) or procedure_type == TreatmentProcedureType.PHARMACY:
            log.info("Using employer health plan default for rte check.")
            # if both copay and coinsurance are returned from rte or it's a pharmacy procedure, then default value from
            # employer health plan table will be used
            eligibility_info.copay = None
            eligibility_info.coinsurance = None

        # if coinsurance and copay both returned by pverify, if one of the values is 0 default to using the other one
        if eligibility_info.copay and eligibility_info.coinsurance == 0.0:
            log.info("Defaulting to copay for rte check.")
            eligibility_info.coinsurance = None
        if eligibility_info.coinsurance and eligibility_info.copay == 0:
            log.info("Defaulting to coinsurance for rte check.")
            eligibility_info.copay = None

        if not tier and (
            (eligibility_info.copay is not None)
            ^ (eligibility_info.coinsurance is not None)
        ):
            return eligibility_info
        return set_db_copay_coinsurance_to_eligibility_info(
            eligibility_info=eligibility_info,
            cost_sharings=cost_sharings,
            cost_sharing_category=cost_sharing_category,
            tier=tier,
        )
