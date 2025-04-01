import dataclasses
from datetime import datetime
from typing import Optional

import sqlalchemy

from cost_breakdown.constants import Tier
from cost_breakdown.errors import NoPatientNameFoundError
from cost_breakdown.models.rte import EligibilityInfo, RxYTDInfo
from cost_breakdown.rte.rte_processor import get_member_first_and_last_name
from cost_breakdown.utils.helpers import (
    get_rx_coverage,
    set_db_copay_coinsurance_to_eligibility_info,
)
from direct_payment.pharmacy.health_plan_ytd_service import (
    HealthPlanYearToDateSpendService,
)
from direct_payment.treatment_procedure.models.treatment_procedure import (
    TreatmentProcedure,
)
from storage.connection import db
from utils.log import logger
from wallet.models.constants import CostSharingCategory, FamilyPlanType
from wallet.models.reimbursement_organization_settings import EmployerHealthPlan
from wallet.models.reimbursement_wallet import MemberHealthPlan

log = logger(__name__)


class RxRteProcessor:
    def __init__(
        self,
        session: sqlalchemy.orm.scoping.ScopedSession = None,  # type: ignore[assignment] # Incompatible default for argument "session" (default has type "None", argument has type "scoped_session")
    ):
        self.session = session or db.session
        self.ytd_spend_repo = HealthPlanYearToDateSpendService(session=session)

    def get_rte(
        self,
        treatment_procedure: TreatmentProcedure,
        member_health_plan: MemberHealthPlan,
        cost_sharing_category: CostSharingCategory,
        tier: Optional[Tier],
    ) -> EligibilityInfo:
        """
        Query health plan year to date table to get the year to date spend amount for certain member or policy
        Args:
            treatment_procedure:
            member_health_plan:
            cost_sharing_category:
            tier:

        Returns: eligibility info added with copay/coinsurance and year to date spend amount
        """
        member_first_name, member_last_name = get_member_first_and_last_name(
            user_id=treatment_procedure.member_id,
            member_health_plan=member_health_plan,
        )
        if not member_first_name or not member_last_name:
            # Log used in alerting
            log.error(
                "RxRTE processor cannot find members name with health plan.",
                treatment_procedure_id=treatment_procedure.uuid,
                member_health_plan_id=member_health_plan.id,
                reimbursement_wallet_id=str(
                    treatment_procedure.reimbursement_wallet_id
                ),
            )
            raise NoPatientNameFoundError("Missing patient name")
        policy_id = self.get_policy_id(member_health_plan)
        ytd_info = self.ytd_info_from_spends(
            policy_id, member_health_plan, member_first_name, member_last_name
        )
        return self.eligibility_info_from_ytd(
            member_health_plan=member_health_plan,
            cost_sharing_category=cost_sharing_category,
            ytd_info=ytd_info,
            tier=tier,
        )

    def ytd_info_from_spends(
        self,
        policy_id: str,
        member_health_plan: MemberHealthPlan,
        member_first_name: str,
        member_last_name: str,
    ) -> RxYTDInfo:
        current_year = datetime.utcnow().year
        family_ytd_deductible = family_ytd_oop = 0
        if member_health_plan.is_family_plan:
            family_ytd_spends = self.ytd_spend_repo.get_all_by_policy(
                policy_id=policy_id, year=current_year
            )
            family_ytd_deductible = sum(
                ytd_spend.deductible_applied_amount for ytd_spend in family_ytd_spends
            )
            family_ytd_oop = sum(
                ytd_spend.oop_applied_amount for ytd_spend in family_ytd_spends
            )

        individual_ytd_spends = self.ytd_spend_repo.get_all_by_member(
            policy_id=policy_id,
            year=current_year,
            first_name=self.normalize_name(member_first_name),
            last_name=self.normalize_name(member_last_name),
        )
        if not individual_ytd_spends:
            ytd_spends_by_policy = self.ytd_spend_repo.get_all_by_policy(
                policy_id=policy_id,
                year=current_year,
            )
            if ytd_spends_by_policy:
                # Log used in alerting
                log.warning(
                    "Found a policy match but not find member match",
                    ytd_spends_by_policy=[
                        dataclasses.asdict(ytd_spend)
                        for ytd_spend in ytd_spends_by_policy
                    ],
                )
        ind_ytd_deductible = sum(
            ytd_spend.deductible_applied_amount for ytd_spend in individual_ytd_spends
        )
        ind_ytd_oop = sum(
            ytd_spend.oop_applied_amount for ytd_spend in individual_ytd_spends
        )
        return RxYTDInfo(
            family_ytd_deductible=family_ytd_deductible,
            family_ytd_oop=family_ytd_oop,
            ind_ytd_deductible=ind_ytd_deductible,
            ind_ytd_oop=ind_ytd_oop,
        )

    def eligibility_info_from_ytd(
        self,
        member_health_plan: MemberHealthPlan,
        cost_sharing_category: CostSharingCategory,
        ytd_info: RxYTDInfo,
        tier: Optional[Tier],
    ) -> EligibilityInfo:
        eligibility_info = EligibilityInfo()
        if (
            member_health_plan.reimbursement_wallet.reimbursement_organization_settings.deductible_accumulation_enabled
        ):
            eligibility_info = set_db_copay_coinsurance_to_eligibility_info(
                eligibility_info=eligibility_info,
                cost_sharings=member_health_plan.employer_health_plan.cost_sharings,
                cost_sharing_category=cost_sharing_category,
                tier=tier,
            )
        coverage = get_rx_coverage(
            ehp=member_health_plan.employer_health_plan,
            plan_size=FamilyPlanType(member_health_plan.plan_type),
            tier=tier,
        )
        if member_health_plan.is_family_plan:
            eligibility_info.family_deductible = coverage.family_deductible
            eligibility_info.family_deductible_remaining = max(
                eligibility_info.family_deductible - ytd_info.family_ytd_deductible, 0
            )
            eligibility_info.family_oop = coverage.family_oop
            eligibility_info.family_oop_remaining = max(
                eligibility_info.family_oop - ytd_info.family_ytd_oop, 0
            )
        eligibility_info.individual_deductible = coverage.individual_deductible
        eligibility_info.individual_deductible_remaining = max(
            eligibility_info.individual_deductible - ytd_info.ind_ytd_deductible, 0
        )
        eligibility_info.individual_oop = coverage.individual_oop
        eligibility_info.individual_oop_remaining = max(
            eligibility_info.individual_oop - ytd_info.ind_ytd_oop, 0
        )
        return eligibility_info

    @staticmethod
    def get_policy_id(member_health_plan):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        employer_health_plan = (
            db.session.query(EmployerHealthPlan)
            .filter(EmployerHealthPlan.id == member_health_plan.employer_health_plan_id)
            .one()
        )
        # For CIGNA, the insurance_id is 10 digit (U+10), where ESI only allows (U+8)
        if employer_health_plan.benefits_payer_id == 1:
            policy_id = member_health_plan.subscriber_insurance_id[:9]
        else:
            policy_id = member_health_plan.subscriber_insurance_id
        return policy_id

    @staticmethod
    def normalize_name(name):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        name = name.strip()
        return name.upper()
