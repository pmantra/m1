from __future__ import annotations

import datetime
import json
import traceback
from dataclasses import dataclass
from decimal import Decimal
from typing import List, Optional, Tuple

import flask_login as login
from flask import flash
from markupsafe import Markup
from maven import feature_flags

from authn.models.user import User
from common.global_procedures.procedure import ProcedureService
from cost_breakdown.constants import (
    AmountType,
    CostBreakdownTriggerSource,
    CostBreakdownType,
    Tier,
)
from cost_breakdown.cost_breakdown_data_service import CostBreakdownDataService
from cost_breakdown.cost_breakdown_processor import (
    CostBreakdownProcessor,
    get_amount_type,
)
from cost_breakdown.errors import CostBreakdownCalculatorValidationError
from cost_breakdown.models.cost_breakdown import (
    AdminDetail,
    CalcConfigAudit,
    CostBreakdown,
    ExtraAppliedAmount,
    SystemUser,
)
from cost_breakdown.models.rte import EligibilityInfo
from cost_breakdown.utils.helpers import (
    get_calculation_tier,
    get_medical_coverage,
    get_rx_coverage,
    is_plan_tiered,
    set_db_copay_coinsurance_to_eligibility_info,
)
from direct_payment.clinic.models.clinic import FertilityClinicLocation
from direct_payment.treatment_procedure.models.treatment_procedure import (
    TreatmentProcedure,
    TreatmentProcedureType,
)
from payer_accumulator.accumulation_mapping_service import AccumulationMappingService
from payer_accumulator.models.accumulation_treatment_mapping import (
    AccumulationTreatmentMapping,
)
from storage.connection import db
from utils.braze_events import reimbursement_request_updated_new_to_pending
from utils.log import logger
from wallet.models.constants import (
    CostSharingCategory,
    FamilyPlanType,
    MemberType,
    ReimbursementRequestAutoProcessing,
    ReimbursementRequestState,
)
from wallet.models.reimbursement import ReimbursementRequest
from wallet.models.reimbursement_organization_settings import EmployerHealthPlan
from wallet.models.reimbursement_wallet import MemberHealthPlan, ReimbursementWallet
from wallet.repository.health_plan import (
    HEALTH_PLAN_YOY_FLAG,
    OLD_BEHAVIOR,
    HealthPlanRepository,
)
from wallet.repository.reimbursement_wallet import ReimbursementWalletRepository
from wallet.services.reimbursement_request import ReimbursementRequestService
from wallet.services.reimbursement_request_state_change import (
    handle_reimbursement_request_state_change,
)
from wallet.services.reimbursment_request_mmb import ReimbursementRequestMMBService

log = logger(__name__)


class DecimalEncoder(json.JSONEncoder):
    def default(self, o):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        if isinstance(o, Decimal):
            return str(o)
        return super().default(o)


@dataclass
class CostBreakdownPreviewRow:
    member_id: str
    total_member_responsibility: int
    total_employer_responsibility: int
    is_unlimited: bool
    beginning_wallet_balance: int
    ending_wallet_balance: int
    deductible: int
    oop_applied: int
    deductible_remaining: Optional[int]
    oop_remaining: Optional[int]
    family_deductible_remaining: Optional[int]
    family_oop_remaining: Optional[int]
    cost: int
    overage_amount: int
    procedure_name: str
    procedure_type: str
    amount_type: AmountType
    cost_breakdown_type: CostBreakdownType
    cost_sharing_category: str
    coinsurance: Optional[int] = 0
    copay: Optional[int] = 0
    hra_applied: Optional[int] = 0


@dataclass
class RTEOverride:
    ytd_ind_deductible: str = ""
    ytd_ind_oop: str = ""
    ytd_family_deductible: str = ""
    ytd_family_oop: str = ""
    hra_remaining: str = ""
    ind_oop_remaining: str = ""
    family_oop_remaining: str = ""

    def data_is_present(self) -> bool:
        if (
            self.ytd_ind_deductible == ""
            and self.ytd_ind_oop == ""
            and self.ytd_family_deductible == ""
            and self.ytd_family_oop == ""
            and self.hra_remaining == ""
            and self.family_oop_remaining == ""
            and self.ind_oop_remaining == ""
        ):
            return False
        return True


class CalculatorRTE:
    """
    Cost Breakdown Calculators allow user-provided RTE values to substitute for PVerify RTE results.
    We have shared validation and data formatting related to this functionality.
    """

    @classmethod
    def validate_rte_override(
        cls,
        member_health_plan: MemberHealthPlan | None,
        rte_override_data: RTEOverride,
    ) -> bool:
        should_override_rte_result = False
        if member_health_plan is not None:
            employer_health_plan = member_health_plan.employer_health_plan
            should_override_rte_result = cls.should_override_rte_result(
                member_health_plan=member_health_plan,
                employer_health_plan=employer_health_plan,
                rte_override_data=rte_override_data,
            )
        elif rte_override_data.data_is_present():
            raise ValueError(
                "Cannot override RTE for a procedure without a member health plan where RTE will not be called."
            )
        return should_override_rte_result

    @staticmethod
    def should_override_rte_result(
        member_health_plan: MemberHealthPlan,
        employer_health_plan: EmployerHealthPlan,
        rte_override_data: RTEOverride,
    ) -> bool:
        # if none of the ytd values is present, there's no need to override the RTE result
        if not rte_override_data.data_is_present():
            return False

        # if ytd values are specified, don't run RTE and use default values in employer health plan table
        # we also need to make sure certain ytd values are present based on the health plan type
        if employer_health_plan.is_hdhp:
            # for family plan check for family OOP override
            if member_health_plan.is_family_plan:
                if (
                    rte_override_data.ytd_family_oop == ""
                    or rte_override_data.family_oop_remaining == ""
                ):
                    raise ValueError(
                        "For a family HDHP plan please specify YTD and remaining family OOP amount."
                    )
                else:
                    return True
            # for individual plan check for individual OOP override
            else:
                if (
                    rte_override_data.ytd_ind_oop == ""
                    or rte_override_data.ind_oop_remaining == ""
                ):
                    raise ValueError(
                        "For an individual HDHP plan please speciy YTD and remaining individual OOP amount."
                    )
                else:
                    return True
        if member_health_plan.is_family_plan:
            deductible_embedded_match = list(
                filter(
                    lambda coverage: coverage.is_deductible_embedded is True
                    and coverage.plan_type
                    == FamilyPlanType(member_health_plan.plan_type),
                    employer_health_plan.coverage,
                )
            )
            oop_embedded_match = list(
                filter(
                    lambda coverage: coverage.is_oop_embedded is True
                    and coverage.plan_type
                    == FamilyPlanType(member_health_plan.plan_type),
                    employer_health_plan.coverage,
                )
            )
            is_deductible_embedded_possible = (
                True if deductible_embedded_match else False
            )
            is_oop_embedded_possible = True if oop_embedded_match else False

            if is_deductible_embedded_possible and not is_oop_embedded_possible:
                if (
                    rte_override_data.ytd_ind_deductible == ""
                    or rte_override_data.ytd_family_deductible == ""
                    or rte_override_data.ytd_family_oop == ""
                ):
                    raise ValueError(
                        "For a family plan with an embedded deductible and non embedded OOP, "
                        "please specify YTD individual deductible amount, YTD family deductible amount, "
                        "and YTD family OOP amount."
                    )
            elif not is_deductible_embedded_possible and is_oop_embedded_possible:
                if (
                    rte_override_data.ytd_ind_oop == ""
                    or rte_override_data.ytd_family_oop == ""
                    or rte_override_data.ytd_family_deductible == ""
                ):
                    raise ValueError(
                        "For a family plan with a non-embedded deductible and an embedded OOP, "
                        "please specify YTD individual OOP amount, YTD family OOP amount, "
                        "and YTD family deductible amount."
                    )
            elif is_deductible_embedded_possible and is_oop_embedded_possible:
                if (
                    rte_override_data.ytd_ind_deductible == ""
                    or rte_override_data.ytd_ind_oop == ""
                    or rte_override_data.ytd_family_deductible == ""
                    or rte_override_data.ytd_family_oop == ""
                ):
                    raise ValueError(
                        "For a family plan where both deductible and OOP are embedded, "
                        "please specify YTD individual deductible amount, YTD individual OOP amount, "
                        "YTD family deductible amount, and YTD family OOP amount."
                    )
            elif (
                rte_override_data.ytd_family_deductible == ""
                or rte_override_data.ytd_family_oop == ""
            ):
                raise ValueError(
                    "For a family plan where both deductible and OOP are non-embedded, "
                    "please specify YTD family deductible amount and YTD family OOP amount."
                )
        else:
            if (
                rte_override_data.ytd_ind_deductible == ""
                or rte_override_data.ytd_ind_oop == ""
            ):
                raise ValueError(
                    "For an individual plan, "
                    "please specify YTD individual deductible amount and YTD individual OOP amount."
                )

        if (
            not employer_health_plan.hra_enabled
            and rte_override_data.hra_remaining != ""
        ):
            raise ValueError(
                "Employer health plan did not enable hra but hra remaining overrided amount is provided."
            )
        return True

    @staticmethod
    def _cost_sharing_from_procedure(
        cost_breakdown_processor: CostBreakdownProcessor,
        global_procedure_id: str | None,
    ) -> CostSharingCategory:
        cost_sharing_category = (
            cost_breakdown_processor.get_treatment_cost_sharing_category(
                global_procedure_id=global_procedure_id
            )
        )
        if not cost_sharing_category:
            raise ValueError(
                f"Cannot retrieve cost sharing category from global procedure service for global procedure id {global_procedure_id}"
            )
        return cost_sharing_category

    @staticmethod
    def _get_treatment_procedure_calculation_tier(
        employer_health_plan: EmployerHealthPlan,
        treatment_procedure_type: TreatmentProcedureType,
        start_date: datetime.date,
        fertility_clinic_location: Optional[FertilityClinicLocation] = None,
    ) -> Tier:
        if treatment_procedure_type == TreatmentProcedureType.PHARMACY:
            return Tier.PREMIUM
        else:
            if not fertility_clinic_location:
                raise ValueError(
                    "Fertility clinic location required on tiered medical cost breakdown"
                )
            return get_calculation_tier(
                ehp=employer_health_plan,
                fertility_clinic_location=fertility_clinic_location,
                treatment_procedure_start=start_date,
            )

    @staticmethod
    def _is_rx_non_integrated(
        procedure_type: TreatmentProcedureType,
        member_health_plan: MemberHealthPlan,
    ) -> bool:
        return (
            procedure_type == TreatmentProcedureType.PHARMACY
            and not CostBreakdownDataService.is_pharmacy_procedure_with_rx_integration(
                procedure_type=procedure_type,
                member_health_plan=member_health_plan,
            )
        )

    @classmethod
    def get_eligibility_info_override(
        cls,
        cost_breakdown_processor: CostBreakdownProcessor,
        treatment_procedure: TreatmentProcedure,
        member_health_plan: MemberHealthPlan,
        rte_override_data: RTEOverride,
    ) -> EligibilityInfo | None:
        # get cost_sharing_category
        cost_sharing_category = cls._cost_sharing_from_procedure(
            cost_breakdown_processor=cost_breakdown_processor,
            global_procedure_id=treatment_procedure.global_procedure_id,
        )
        employer_health_plan: EmployerHealthPlan = (
            member_health_plan.employer_health_plan
        )
        if employer_health_plan.is_hdhp:
            return EligibilityInfo(
                individual_oop=cls.convert_string_to_int(rte_override_data.ytd_ind_oop)
                if rte_override_data.ytd_ind_oop
                else None,
                individual_oop_remaining=cls.convert_string_to_int(
                    rte_override_data.ind_oop_remaining
                )
                if rte_override_data.ind_oop_remaining
                else None,
                family_oop=cls.convert_string_to_int(rte_override_data.ytd_family_oop)
                if rte_override_data.ytd_family_oop
                else None,
                family_oop_remaining=cls.convert_string_to_int(
                    rte_override_data.family_oop_remaining
                )
                if rte_override_data.family_oop_remaining
                else None,
            )
        # get tier if applicable
        tier = None
        if (
            member_health_plan
            and member_health_plan.employer_health_plan
            and is_plan_tiered(ehp=member_health_plan.employer_health_plan)
        ):
            tier = cls._get_treatment_procedure_calculation_tier(
                employer_health_plan=member_health_plan.employer_health_plan,
                treatment_procedure_type=treatment_procedure.procedure_type,  # type: ignore[arg-type]
                fertility_clinic_location=treatment_procedure.fertility_clinic_location,
                start_date=treatment_procedure.start_date,  # type: ignore[arg-type]
            )
        # override = replace pverify response
        eligibility_info_override = cls._eligibility_info_override(
            member_health_plan=member_health_plan,
            procedure_type=treatment_procedure.procedure_type,  # type: ignore[arg-type]
            cost_sharing_category=cost_sharing_category,
            rte_override_data=rte_override_data,
            tier=tier,
        )
        return eligibility_info_override

    @classmethod
    def _eligibility_info_override(
        cls,
        member_health_plan: MemberHealthPlan,
        procedure_type: TreatmentProcedureType,
        cost_sharing_category: CostSharingCategory,
        rte_override_data: RTEOverride,
        tier: Optional[Tier] = None,
    ) -> EligibilityInfo:
        # TODO: see if any of the logic in here is a duplicate of logic in the cost breakdown data service.
        ytd_ind_deductible = cls.convert_string_to_int(
            rte_override_data.ytd_ind_deductible
        )
        ytd_ind_oop = cls.convert_string_to_int(rte_override_data.ytd_ind_oop)
        ytd_family_deductible = cls.convert_string_to_int(
            rte_override_data.ytd_family_deductible
        )
        ytd_family_oop = cls.convert_string_to_int(rte_override_data.ytd_family_oop)
        # override here for hra management during a loop of procedures
        hra_remaining = cls.convert_string_to_int(rte_override_data.hra_remaining)
        amount_type = get_amount_type(member_health_plan)
        employer_health_plan = member_health_plan.employer_health_plan

        eligibility_info = EligibilityInfo()
        if (
            member_health_plan.reimbursement_wallet.reimbursement_organization_settings.deductible_accumulation_enabled
        ):
            eligibility_info = set_db_copay_coinsurance_to_eligibility_info(
                eligibility_info=eligibility_info,
                cost_sharings=employer_health_plan.cost_sharings,
                cost_sharing_category=cost_sharing_category,
                tier=tier,
            )

        if amount_type == AmountType.INDIVIDUAL:
            if cls._is_rx_non_integrated(procedure_type, member_health_plan):
                coverage = get_rx_coverage(
                    ehp=employer_health_plan,
                    plan_size=FamilyPlanType(member_health_plan.plan_type),
                    tier=tier,
                )
                eligibility_info.individual_deductible = coverage.individual_deductible
                eligibility_info.individual_oop = coverage.individual_oop
            else:
                coverage = get_medical_coverage(
                    ehp=employer_health_plan,
                    plan_size=FamilyPlanType(member_health_plan.plan_type),
                    tier=tier,
                )
                eligibility_info.individual_deductible = coverage.individual_deductible
                eligibility_info.individual_oop = coverage.individual_oop

            eligibility_info.individual_deductible_remaining = max(
                eligibility_info.individual_deductible - ytd_ind_deductible, 0
            )
            eligibility_info.individual_oop_remaining = max(
                eligibility_info.individual_oop - ytd_ind_oop, 0
            )
        else:
            if cls._is_rx_non_integrated(procedure_type, member_health_plan):
                coverage = get_rx_coverage(
                    ehp=employer_health_plan,
                    plan_size=FamilyPlanType(member_health_plan.plan_type),
                    tier=tier,
                )
                eligibility_info.family_deductible = coverage.family_deductible
                eligibility_info.family_oop = coverage.family_oop
                eligibility_info.individual_deductible = coverage.individual_deductible
                eligibility_info.individual_oop = coverage.individual_oop
            else:
                coverage = get_medical_coverage(
                    ehp=employer_health_plan,
                    plan_size=FamilyPlanType(member_health_plan.plan_type),
                    tier=tier,
                )
                eligibility_info.family_deductible = coverage.family_deductible
                eligibility_info.family_oop = coverage.family_oop
                eligibility_info.individual_deductible = coverage.individual_deductible
                eligibility_info.individual_oop = coverage.individual_oop

                eligibility_info.family_deductible_remaining = max(
                    eligibility_info.family_deductible - ytd_family_deductible, 0
                )
                eligibility_info.family_oop_remaining = max(
                    eligibility_info.family_oop - ytd_family_oop, 0
                )

            eligibility_info.family_deductible_remaining = max(
                eligibility_info.family_deductible - ytd_family_deductible, 0
            )
            eligibility_info.family_oop_remaining = max(
                eligibility_info.family_oop - ytd_family_oop, 0
            )
            if coverage.is_deductible_embedded:
                eligibility_info.individual_deductible_remaining = max(
                    eligibility_info.individual_deductible - ytd_ind_deductible, 0
                )
            if coverage.is_oop_embedded:
                eligibility_info.individual_oop_remaining = max(
                    eligibility_info.individual_oop - ytd_ind_oop, 0
                )
        eligibility_info.is_deductible_embedded = coverage.is_deductible_embedded
        eligibility_info.is_oop_embedded = coverage.is_oop_embedded
        # Should be null in most cases
        eligibility_info.max_oop_per_covered_individual = (
            coverage.max_oop_per_covered_individual
        )
        eligibility_info.hra_remaining = hra_remaining if hra_remaining != 0 else None  # type: ignore[assignment] # Incompatible types in assignment (expression has type "int", variable has type "str")
        return eligibility_info

    @staticmethod
    def convert_string_to_int(string: str) -> int:
        if string == "":
            return 0
        else:
            return int(Decimal(string) * 100)


class CalculatorValidation:
    """
    Validation relating to inputs into Cost Breakdown Calculators.
    """

    @staticmethod
    def _validate_treatment_procedures(
        treatment_id_list: Optional[str],
    ) -> List[TreatmentProcedure]:
        if not treatment_id_list:
            raise CostBreakdownCalculatorValidationError(
                "No treatment procedure specified, please at least specify one treatment procedure id, "
                "or multiple procedure ids separated by commas."
            )

        treatment_id_strings = [
            tp_id.strip() for tp_id in treatment_id_list.strip().split(",")
        ]

        for treatment_id in treatment_id_strings:
            if not treatment_id.isdigit():
                raise CostBreakdownCalculatorValidationError(
                    f"{treatment_id} is not a valid integer"
                )
        treatment_ids = set(map(int, treatment_id_strings))

        treatment_procedures = TreatmentProcedure.query.filter(
            TreatmentProcedure.id.in_(list(treatment_ids))
        ).all()

        found_procedure_ids = set(procedure.id for procedure in treatment_procedures)
        if found_procedure_ids != treatment_ids:
            missing_ids = treatment_ids.difference(found_procedure_ids)
            raise CostBreakdownCalculatorValidationError(
                f"Could not find all treatment procedures for the given ids. Missing: {list(missing_ids)}"
            )
        return treatment_procedures

    @staticmethod
    def _validate_user_for_procedures(
        treatment_procedures: List[TreatmentProcedure],
    ) -> User:
        user_ids = set(procedure.member_id for procedure in treatment_procedures)
        if len(user_ids) > 1:
            raise CostBreakdownCalculatorValidationError(
                f"Treatments don't belong to the same user, found multiple users: {user_ids}"
            )
        user_id = user_ids.pop()
        user = User.query.get(user_id)
        return user

    @staticmethod
    def _validate_user(user_id: int) -> User:
        user = User.query.get(user_id)
        if not user:
            raise CostBreakdownCalculatorValidationError("User not found")
        return user

    @staticmethod
    def _validate_wallet_for_procedures(
        treatment_procedures: List[TreatmentProcedure], user: User
    ) -> ReimbursementWallet:
        wallet_ids = set(
            procedure.reimbursement_wallet_id for procedure in treatment_procedures
        )
        if len(wallet_ids) > 1:
            raise CostBreakdownCalculatorValidationError(
                f"Treatments don't belong to the same wallet, found multiple wallet ids: {wallet_ids}"
            )
        wallet_id = wallet_ids.pop()

        # will raise error for no wallet here
        wallet = CalculatorValidation._validate_wallet(user.id)
        if wallet.id != wallet_id:
            raise CostBreakdownCalculatorValidationError(
                "This user is not associated with this procedure's wallet."
            )
        return wallet

    @staticmethod
    def _validate_wallet(user_id: int) -> ReimbursementWallet:
        wallet_repo = ReimbursementWalletRepository(session=db.session)
        wallet = wallet_repo.get_current_wallet_by_active_user_id(user_id=user_id)
        if not wallet:
            raise CostBreakdownCalculatorValidationError(
                "No Qualified wallet associated with this user."
            )
        return wallet

    @staticmethod
    def _validate_health_plan(
        start_dates: List[datetime.datetime],
        user: User,
        wallet: ReimbursementWallet,
    ) -> MemberHealthPlan | None:
        if (
            feature_flags.str_variation(HEALTH_PLAN_YOY_FLAG, default=OLD_BEHAVIOR)
            != OLD_BEHAVIOR
        ):
            member_health_plans = HealthPlanRepository(
                session=db.session
            ).get_all_plans_for_multiple_dates(
                member_id=user.id,
                wallet_id=wallet.id,
                all_dates=start_dates,
            )
            if len(member_health_plans) == 0:
                # No member health plan is a valid response.
                member_health_plan = None
            elif len(member_health_plans) > 1:
                raise CostBreakdownCalculatorValidationError(
                    "Treatments don't belong to the same health plan, found multiple relevant member health plans. "
                    f"Plan ids: {[mhp.id for mhp in member_health_plans]}"
                )
            else:
                member_health_plan = member_health_plans[0]
        else:
            member_health_plan = MemberHealthPlan.query.filter(  # noqa -- refactor, not use of non-repo query
                MemberHealthPlan.member_id == user.id,
                MemberHealthPlan.reimbursement_wallet_id == wallet.id,
            ).one_or_none()
        return member_health_plan


class CostBreakdownExtras(CalculatorValidation):
    """
    Used by the CostBreakdownRecalculationView and ReimbursementRequestCalculatorView
    """

    @staticmethod
    def _new_cost_breakdown_processor() -> CostBreakdownProcessor:
        procedure_client = ProcedureService(internal=True)
        return CostBreakdownProcessor(procedure_service_client=procedure_client)

    @staticmethod
    def _format_cost_breakdown(
        initial_cost: int,
        cost_breakdown: CostBreakdown,
    ) -> dict:
        cents_to_dollars = lambda cents: Decimal(cents) / 100 if cents else 0
        return {
            "cost": cents_to_dollars(initial_cost),
            "total_member_responsibility": cents_to_dollars(
                cost_breakdown.total_member_responsibility
            ),
            "total_employer_responsibility": cents_to_dollars(
                cost_breakdown.total_employer_responsibility
            ),
            "is_unlimited": cost_breakdown.is_unlimited,
            "beginning_wallet_balance": cents_to_dollars(
                cost_breakdown.beginning_wallet_balance
            ),
            "ending_wallet_balance": cents_to_dollars(
                cost_breakdown.ending_wallet_balance
            ),
            "deductible": cents_to_dollars(cost_breakdown.deductible),
            "deductible_remaining": cents_to_dollars(
                cost_breakdown.deductible_remaining
            ),
            "family_deductible_remaining": cents_to_dollars(
                cost_breakdown.family_deductible_remaining
            ),
            "coinsurance": cents_to_dollars(cost_breakdown.coinsurance),
            "copay": cents_to_dollars(cost_breakdown.copay),
            "oop_remaining": cents_to_dollars(cost_breakdown.oop_remaining),
            "oop_applied": cents_to_dollars(cost_breakdown.oop_applied),
            "hra_applied": cents_to_dollars(cost_breakdown.hra_applied),
            "family_oop_remaining": cents_to_dollars(
                cost_breakdown.family_oop_remaining
            ),
            "overage_amount": cents_to_dollars(cost_breakdown.overage_amount),
            "amount_type": (
                cost_breakdown.amount_type.value  # type: ignore[union-attr,attr-defined] # Item "str" of "Union[str, AmountType]" has no attribute "value" #type: ignore[attr-defined] # "str" has no attribute "value" #type: ignore[attr-defined] # "str" has no attribute "value"
                if cost_breakdown.amount_type
                else None
            ),
            "cost_breakdown_type": (
                cost_breakdown.cost_breakdown_type.value  # type: ignore[union-attr,attr-defined] # Item "str" of "Union[str, CostBreakdownType]" has no attribute "value" #type: ignore[attr-defined] # "str" has no attribute "value" #type: ignore[attr-defined] # "str" has no attribute "value"
                if cost_breakdown.cost_breakdown_type
                else None
            ),
            "rte_transaction_id": cost_breakdown.rte_transaction_id,
            "calc_config": (
                json.dumps(cost_breakdown.calc_config, cls=DecimalEncoder)
                if cost_breakdown.calc_config
                else None
            ),
        }

    @staticmethod
    def get_calc_config_audit(
        extra_applied_amount: ExtraAppliedAmount | None = None,
        should_include_pending: bool = False,
    ) -> CalcConfigAudit:
        return CalcConfigAudit(
            system_user=SystemUser(
                trigger_source=CostBreakdownTriggerSource.ADMIN.value,
                admin_detail=AdminDetail(
                    user_id=login.current_user.id, email=login.current_user.email
                ),
            ),
            extra_applied_amount=extra_applied_amount,
            should_include_pending=should_include_pending,
        )

    def update_reimbursement_request_on_cost_breakdown(
        self,
        member_id: int,
        reimbursement_request: ReimbursementRequest,
        cost_breakdown: CostBreakdown,
        member_health_plan: MemberHealthPlan,
        cost_breakdown_description: Optional[str] = None,
    ) -> None:
        # update user member status
        reimbursement_request_service = ReimbursementRequestService()
        self._update_member_status(
            reimbursement_request_service=reimbursement_request_service,
            member_id=member_id,
            reimbursement_request=reimbursement_request,
        )

        # prepare for cost breakdown + reimbursement request + accumulation logic flow
        mapping = None
        mapping_message = ""
        old_reimbursement_state = ReimbursementRequestState(reimbursement_request.state)
        original_amount = reimbursement_request.amount

        if (
            reimbursement_request.auto_processed
            != ReimbursementRequestAutoProcessing.RX
        ):
            if reimbursement_request.state == ReimbursementRequestState.NEW:
                log.info(
                    "Reimbursement Request is NEW, saved cost breakdown will apply changes.",
                    reimbursement_request_id=str(reimbursement_request.id),
                )
                self._reimbursement_request_update_state_amount_and_description(
                    reimbursement_request=reimbursement_request,
                    cost_breakdown=cost_breakdown,
                    member_health_plan=member_health_plan,
                    cost_breakdown_description=cost_breakdown_description,
                    original_amount=original_amount,
                )

                # handle payer accumulation logic for mapping
                (
                    mapping,
                    mapping_message,
                ) = self._reimbursement_request_accumulation_mapping(
                    reimbursement_request=reimbursement_request,
                    cost_breakdown=cost_breakdown,
                    mapping_message=mapping_message,
                )

        try:
            self._save_reimbursement_request_cost_breakdown_changes(
                reimbursement_request=reimbursement_request,
                cost_breakdown=cost_breakdown,
                mapping=mapping,
            )
        except Exception as e:
            flash(
                f"Failed to persist cost breakdown and/or reimbursement request into database."
                f"Error: {str(e)} {traceback.format_exc()}",
                "error",
            )
            raise e
        if (
            reimbursement_request.auto_processed
            == ReimbursementRequestAutoProcessing.RX
        ):
            reimbursement_request.state = ReimbursementRequestState.PENDING
        if (
            old_reimbursement_state != reimbursement_request.state
            and reimbursement_request.state == ReimbursementRequestState.PENDING
        ):
            # alegeus logic to be consistent with the ReimbursementRequest view update_model
            success, mapping_message = self._attempt_alegeus_submission(
                reimbursement_request=reimbursement_request,
                old_reimbursement_state=old_reimbursement_state,
                mapping_message=mapping_message,
            )
            if not success:
                flash(Markup(mapping_message), "error")
                log.error(
                    "Failed to send a claim to Alegeus for the updated reimbursement request.",
                    error_message=mapping_message,
                    reimbursement_request_id=str(reimbursement_request.id),
                )
                mapping_message = ""
        formatted_cost_breakdown = self._format_cost_breakdown(
            initial_cost=original_amount, cost_breakdown=cost_breakdown
        )
        cost_breakdown_description = self._format_cost_breakdown_for_response(
            formatted_cost_breakdown, linebreak="<br />"
        )
        flash(
            Markup(
                f"Cost Breakdown <{cost_breakdown.id}> saved!{cost_breakdown_description}"
            ),
            "success",
        )
        if mapping_message:
            flash(Markup(mapping_message), "success")
        log.info(
            "Reimbursement Request Cost Breakdown Calculator complete.",
            reimbursement_request_id=reimbursement_request.id,
            updated_amount=reimbursement_request.transaction_amount,
            updated_state=reimbursement_request.state,
        )

        self._handle_cost_share_notification(
            reimbursement_request_service=reimbursement_request_service,
            reimbursement_request=reimbursement_request,
            old_reimbursement_state=old_reimbursement_state,
        )

    def _update_member_status(
        self,
        reimbursement_request_service: ReimbursementRequestService,
        member_id: int,
        reimbursement_request: ReimbursementRequest,
    ) -> None:
        """Update the member status for the reimbursement request."""
        reimbursement_request.person_receiving_service_member_status = reimbursement_request_service.reimbursement_wallets.get_wallet_user_member_status(
            member_id,
            reimbursement_request.reimbursement_wallet_id,
        )
        log.info(
            "Reimbursement Request member status updated.",
            reimbursement_request_id=str(reimbursement_request.id),
            new_status=reimbursement_request.person_receiving_service_member_status,
        )

    def _reimbursement_request_update_state_amount_and_description(
        self,
        reimbursement_request: ReimbursementRequest,
        cost_breakdown: CostBreakdown,
        member_health_plan: MemberHealthPlan,
        cost_breakdown_description: Optional[str],
        original_amount: int,
    ) -> None:
        rr_mmb_service = ReimbursementRequestMMBService()
        # update reimbursement request state + amount
        # request may become PENDING or DENIED depending on input.
        # amount may become equal to the total employer responsibility or remain the same.
        reimbursement_request = rr_mmb_service.update_request_for_cost_breakdown(
            reimbursement_request, cost_breakdown
        )

        # update reimbursement request description
        existing_description = reimbursement_request.description
        if not cost_breakdown_description:
            formatted_cost_breakdown = self._format_cost_breakdown(
                initial_cost=original_amount, cost_breakdown=cost_breakdown
            )
            cost_breakdown_description = self._format_cost_breakdown_for_response(
                formatted_cost_breakdown, linebreak="\n"
            )
        reimbursement_request.description = (
            existing_description
            + f"{member_health_plan.employer_health_plan.name}\n"
            + cost_breakdown_description
        )
        log.info("Reimbursement Request description ready to be updated on save.")

    def _reimbursement_request_accumulation_mapping(
        self,
        reimbursement_request: ReimbursementRequest,
        cost_breakdown: CostBreakdown,
        mapping_message: str,
    ) -> Tuple[Optional[AccumulationTreatmentMapping], str]:
        mapping_service = AccumulationMappingService(session=db.session)
        mapping = None

        if mapping_service.should_accumulate_reimbursement_request_pre_approval(
            reimbursement_request, cost_breakdown
        ):
            mapping = mapping_service.create_valid_reimbursement_request_mapping(
                reimbursement_request=reimbursement_request
            )
            mapping_message = (
                "An accumulation mapping has been created for this cost breakdown."
            )
        elif mapping_service.should_accumulate_reimbursement_request_post_approval(
            reimbursement_request, cost_breakdown
        ):
            mapping_message = "An accumulation mapping will be created for this reimbursement request after review by Peak One."
        log.info(
            "Mapping logic response to saving a cost breakdown.",
            reimbursement_request_id=str(reimbursement_request.id),
            mapping_message=mapping_message,
        )
        return mapping, mapping_message

    def _save_reimbursement_request_cost_breakdown_changes(
        self,
        reimbursement_request: ReimbursementRequest,
        cost_breakdown: CostBreakdown,
        mapping: Optional[AccumulationTreatmentMapping],
    ) -> None:
        try:
            if mapping:
                db.session.add(mapping)
            db.session.add(cost_breakdown)
            db.session.add(reimbursement_request)
            db.session.commit()
            log.info(
                "Successfully saved changes from the Reimbursement Request Calculator",
                reimbursement_request_id=str(reimbursement_request.id),
                updated_amount=reimbursement_request.transaction_amount,
                updated_state=reimbursement_request.state,
            )
        except Exception as e:
            log.error(
                "Failed to save a Cost Breakdown from the Reimbursement Request calculator.",
                reimbursement_request_id=reimbursement_request.id,
                error_message=str(e),
                traceback=traceback.format_exc(),
            )
            raise e

    def _handle_cost_share_notification(
        self,
        reimbursement_request_service: ReimbursementRequestService,
        reimbursement_request: ReimbursementRequest,
        old_reimbursement_state: ReimbursementRequestState,
    ) -> None:
        if (
            reimbursement_request_service.is_cost_share_breakdown_applicable(
                reimbursement_request.wallet
            )
            and reimbursement_request.auto_processed
            != ReimbursementRequestAutoProcessing.RX
            and old_reimbursement_state is ReimbursementRequestState.NEW
            and reimbursement_request.state is ReimbursementRequestState.PENDING
        ):
            try:
                reimbursement_request_updated_new_to_pending(
                    wallet=reimbursement_request.wallet,
                    member_type=MemberType.MAVEN_GOLD,
                )
            except Exception as e:
                log.exception(
                    "Failed to send braze event for pending reimbursement request",
                    error=e,
                    reimbursement_request_id=reimbursement_request.id,
                    person_receiving_service_id=reimbursement_request.person_receiving_service_id,
                )

    def _attempt_alegeus_submission(  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        self,
        reimbursement_request: ReimbursementRequest,
        old_reimbursement_state: ReimbursementRequestState,
        mapping_message: str,
    ):
        try:
            log.info(
                "Attempt to send the claim to Alegeus.",
                reimbursement_request_id=str(reimbursement_request.id),
                updated_amount=reimbursement_request.transaction_amount,
                updated_state=reimbursement_request.state,
                auto_processed=reimbursement_request.auto_processed,
            )
            # NOTE this sets the reimbursement request state back to NEW if submission fails
            messages = handle_reimbursement_request_state_change(
                reimbursement_request=reimbursement_request,
                old_state=old_reimbursement_state,
            )
            mapping_message += (
                ReimbursementRequestMMBService.handle_messages_for_state_change(
                    messages
                )
            )
            if reimbursement_request.state == ReimbursementRequestState.NEW:
                error_message = (
                    "Failure to send the updated Reimbursement Request to Alegeus. "
                    "<br />Error: "
                    + "<br />".join(message.message for message in messages)
                )
                # Update model for changes again.
                db.session.add(reimbursement_request)
                db.session.commit()
                return False, error_message
            else:
                return True, mapping_message
        except Exception as e:
            log.error(
                "Failed to submit changes to Alegeus from the Reimbursement Request calculator.",
                reimbursement_request_id=reimbursement_request.id,
                error_message=str(e),
                traceback=traceback.format_exc(),
            )
            error_message = (
                f"Failed to send updates to Alegeus.<br /> "
                f"Error: {str(e)} {traceback.format_exc()}",
                "error",
            )
            return False, error_message

    @staticmethod
    def _format_cost_breakdown_for_response(
        formatted_cost_breakdown: dict, linebreak: str = "\n"
    ) -> str:
        return (
            f"{linebreak}{linebreak}"
            f"Treatment Cost: ${formatted_cost_breakdown.get('cost')}{linebreak}"
            f"Member Responsibility: ${formatted_cost_breakdown.get('total_member_responsibility')}{linebreak}"
            f"- Deductible: ${formatted_cost_breakdown.get('deductible')}{linebreak}"
            f"- Coinsurance: ${formatted_cost_breakdown.get('coinsurance')}{linebreak}"
            f"- Copay: ${formatted_cost_breakdown.get('copay')}{linebreak}"
            f"- Not Covered: ${formatted_cost_breakdown.get('overage_amount')}{linebreak}"
            f"Employer Responsibility: ${formatted_cost_breakdown.get('total_employer_responsibility')}{linebreak}"
            f"{linebreak}"
            f"Unlimited Benefit: ${formatted_cost_breakdown.get('is_unlimited')}{linebreak}"
            f"Beginning Wallet Balance: ${formatted_cost_breakdown.get('beginning_wallet_balance')}{linebreak}"
            f"Ending Wallet Balance: ${formatted_cost_breakdown.get('ending_wallet_balance')}"
        )
