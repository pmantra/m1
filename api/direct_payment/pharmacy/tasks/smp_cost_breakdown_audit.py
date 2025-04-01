"""
In order to provide an audit stage for us to make sure cost breakdown results are correct, this module provides API
for user to provide a time range [start_time - 24 hours window], to get corresponding treatment procedure and
cost break down for review.
"""

from __future__ import annotations

import dataclasses
from datetime import datetime
from typing import List, Optional, Tuple

import sqlalchemy
from maven import feature_flags

from common import stats
from common.global_procedures.procedure import ProcedureService
from cost_breakdown.constants import CostBreakdownTriggerSource, Tier
from cost_breakdown.cost_breakdown_processor import CostBreakdownProcessor
from cost_breakdown.errors import NoCostSharingFoundError, NoPatientNameFoundError
from cost_breakdown.models.cost_breakdown import CostBreakdown, SystemUser
from cost_breakdown.models.rte import EligibilityInfo
from cost_breakdown.rte.rte_processor import (
    RTEProcessor,
    get_member_first_and_last_name,
)
from cost_breakdown.utils.helpers import (
    get_medical_coverage,
    get_rx_coverage,
    is_plan_tiered,
    set_db_copay_coinsurance_to_eligibility_info,
)
from direct_payment.billing.billing_service import BillingService
from direct_payment.billing.models import PayorType
from direct_payment.pharmacy.models.pharmacy_prescription import PharmacyPrescription
from direct_payment.pharmacy.repository.pharmacy_prescription import (
    PharmacyPrescriptionRepository,
)
from direct_payment.treatment_procedure.models.treatment_procedure import (
    TreatmentProcedure,
    TreatmentProcedureStatus,
    TreatmentProcedureType,
)
from direct_payment.treatment_procedure.repository.treatment_procedure import (
    TreatmentProcedureRepository,
)
from storage import connection
from utils.log import logger
from wallet.models.constants import CostSharingCategory, FamilyPlanType
from wallet.models.reimbursement_organization_settings import EmployerHealthPlan
from wallet.models.reimbursement_wallet import MemberHealthPlan, ReimbursementWallet
from wallet.repository.health_plan import (
    HEALTH_PLAN_YOY_FLAG,
    OLD_BEHAVIOR,
    HealthPlanRepository,
)

log = logger(__name__)

METRIC_NAME = "smp_cost_breakdown_audit.error.count"


@dataclasses.dataclass
class Results:
    drug_name: str
    price: int
    category: CostSharingCategory
    applied_to_deductible: int
    applied_to_coinsurance: int
    applied_to_copay: int
    total_member_resp: int
    total_employer_resp: int
    user_id: int
    status: str
    treatment_procedure_id: int
    cost_share: int = None  # type: ignore[assignment] # Incompatible types in assignment (expression has type "None", variable has type "int")
    cost_share_min: int = None  # type: ignore[assignment] # Incompatible types in assignment (expression has type "None", variable has type "int")
    cost_share_max: int = None  # type: ignore[assignment] # Incompatible types in assignment (expression has type "None", variable has type "int")
    oop_applied: int = None  # type: ignore[assignment] # Incompatible types in assignment (expression has type "None", variable has type "int")
    deductible_remaining_pre_cb: int = None  # type: ignore[assignment] # Incompatible types in assignment (expression has type "None", variable has type "int")
    oop_remaining_pre_cb: int = None  # type: ignore[assignment] # Incompatible types in assignment (expression has type "None", variable has type "int")
    not_covered: int = None  # type: ignore[assignment] # Incompatible types in assignment (expression has type "None", variable has type "int")
    member_ytd_charges: int = None  # type: ignore[assignment] # Incompatible types in assignment (expression has type "None", variable has type "int")
    family_ytd_charges: int = None  # type: ignore[assignment] # Incompatible types in assignment (expression has type "None", variable has type "int")


@dataclasses.dataclass
class UserInfo:
    org_name: str
    benefit_id: str
    wallet_id: int
    user_id: int
    treatment_procedure_id: int
    member_health_plan_id: int = None  # type: ignore[assignment] # Incompatible types in assignment (expression has type "None", variable has type "int")
    is_hdhp: bool = None  # type: ignore[assignment] # Incompatible types in assignment (expression has type "None", variable has type "bool")
    deductible_embedded: int = None  # type: ignore[assignment] # Incompatible types in assignment (expression has type "None", variable has type "int")
    oopm_embedded: int = None  # type: ignore[assignment] # Incompatible types in assignment (expression has type "None", variable has type "int")
    rx_integrated: bool = None  # type: ignore[assignment] # Incompatible types in assignment (expression has type "None", variable has type "bool")
    is_family_plan: str = None  # type: ignore[assignment] # Incompatible types in assignment (expression has type "None", variable has type "str")
    subscriber_id: str = None  # type: ignore[assignment] # Incompatible types in assignment (expression has type "None", variable has type "str")
    employer_health_plan_name: str = None  # type: ignore[assignment] # Incompatible types in assignment (expression has type "None", variable has type "str")
    ind_ded_ytd: int = None  # type: ignore[assignment] # Incompatible types in assignment (expression has type "None", variable has type "int")
    ind_ded_limit: int = None  # type: ignore[assignment] # Incompatible types in assignment (expression has type "None", variable has type "int")
    ind_oopm_ytd: int = None  # type: ignore[assignment] # Incompatible types in assignment (expression has type "None", variable has type "int")
    ind_oopm_limit: int = None  # type: ignore[assignment] # Incompatible types in assignment (expression has type "None", variable has type "int")
    fam_ded_ytd: int = None  # type: ignore[assignment] # Incompatible types in assignment (expression has type "None", variable has type "int")
    fam_ded_limit: int = None  # type: ignore[assignment] # Incompatible types in assignment (expression has type "None", variable has type "int")
    fam_oopm_ytd: int = None  # type: ignore[assignment] # Incompatible types in assignment (expression has type "None", variable has type "int")
    fam_oopm_limit: int = None  # type: ignore[assignment] # Incompatible types in assignment (expression has type "None", variable has type "int")


@dataclasses.dataclass
class ErrorInfo:
    user_id: int
    treatment_procedure_id: int
    wallet_id: int
    benefit_id: str
    error_message: str
    org_name: str
    status: str = None  # type: ignore[assignment] # Incompatible types in assignment (expression has type "None", variable has type "str")
    drug_name: str = None  # type: ignore[assignment] # Incompatible types in assignment (expression has type "None", variable has type "str")
    price: int = ""  # type: ignore[assignment] # Incompatible types in assignment (expression has type "str", variable has type "int")
    category: str = None  # type: ignore[assignment] # Incompatible types in assignment (expression has type "None", variable has type "str")
    member_health_plan_id: int = None  # type: ignore[assignment] # Incompatible types in assignment (expression has type "None", variable has type "int")
    is_hdhp: bool = None  # type: ignore[assignment] # Incompatible types in assignment (expression has type "None", variable has type "bool")
    deductible_embedded: int = None  # type: ignore[assignment] # Incompatible types in assignment (expression has type "None", variable has type "int")
    oopm_embedded: int = None  # type: ignore[assignment] # Incompatible types in assignment (expression has type "None", variable has type "int")
    rx_integrated: bool = None  # type: ignore[assignment] # Incompatible types in assignment (expression has type "None", variable has type "bool")
    is_family_plan: str = None  # type: ignore[assignment] # Incompatible types in assignment (expression has type "None", variable has type "str")
    subscriber_id: str = None  # type: ignore[assignment] # Incompatible types in assignment (expression has type "None", variable has type "str")
    employer_health_plan_name: str = None  # type: ignore[assignment] # Incompatible types in assignment (expression has type "None", variable has type "str")
    ind_ded_limit: int = None  # type: ignore[assignment] # Incompatible types in assignment (expression has type "None", variable has type "int")
    ind_oopm_limit: int = None  # type: ignore[assignment] # Incompatible types in assignment (expression has type "None", variable has type "int")
    fam_ded_limit: int = None  # type: ignore[assignment] # Incompatible types in assignment (expression has type "None", variable has type "int")
    fam_oopm_limit: int = None  # type: ignore[assignment] # Incompatible types in assignment (expression has type "None", variable has type "int")


class RxAudit:
    def __init__(
        self,
        session: sqlalchemy.orm.Session = None,  # type: ignore[assignment] # Incompatible default for argument "session" (default has type "None", argument has type "Session")
    ):
        self.session = session or connection.db.session
        self.billing_service = BillingService(session=self.session)  # type: ignore[arg-type] # Argument "session" to "BillingService" has incompatible type "Union[Session, Any]"; expected "Optional[scoped_session]"
        self.pharmacy_prescription_repo = PharmacyPrescriptionRepository(
            session=self.session  # type: ignore[arg-type] # Argument "session" to "PharmacyPrescriptionRepository" has incompatible type "Union[Session, Any]"; expected "Optional[scoped_session]"
        )
        self.procedure_service_client = ProcedureService(internal=True)
        self.treatment_procedure_repo = TreatmentProcedureRepository(
            session=self.session  # type: ignore[arg-type] # Argument "session" to "TreatmentProcedureRepository" has incompatible type "Union[Session, Any]"; expected "Optional[scoped_session]"
        )
        self.cost_breakdown_processor = CostBreakdownProcessor(
            procedure_service_client=self.procedure_service_client,
            system_user=SystemUser(
                trigger_source=CostBreakdownTriggerSource.ADMIN.value
            ),
        )

    def calculate_cost_breakdown_audit_for_time_range(
        self,
        start_time: Optional[datetime] = None,
    ) -> (Results, UserInfo, ErrorInfo):  # type: ignore[syntax] # Syntax error in type annotation
        cost_breakdown_results = []
        users = {}
        errors = {}

        start_time: datetime = (  # type: ignore[no-redef] # Name "start_time" already defined on line 154
            start_time.replace(hour=0, minute=0, second=0, microsecond=0)
            if start_time
            else datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
        )
        end_time: datetime = start_time.replace(  # type: ignore[union-attr] # Item "None" of "Optional[datetime]" has no attribute "replace"
            hour=23, minute=59, second=59, microsecond=999999
        )

        pharmacy_prescriptions = self.pharmacy_prescription_repo.get_by_time_range(
            start_time, end_time
        )

        if not pharmacy_prescriptions:
            log.error(
                "SMP audit: No Pharmacy Prescriptions found for time provided.",
                time=start_time,
            )
            stats.increment(
                metric_name=METRIC_NAME,
                pod_name=stats.PodNames.PAYMENTS_PLATFORM,
                tags=["reason:no_pharmacy_prescriptions"],
            )
            self._set_error_info(
                error_message="No Pharmacy Prescriptions found for time provided.",
                errors=errors,
            )
            return cost_breakdown_results, users, errors

        # Call Global Procedures one time to get a list of all the existing procedures
        global_procedures = self._get_rx_global_procedures(pharmacy_prescriptions)
        if not global_procedures:
            log.error(
                "Global Procedures request failed to retrieve data.",
            )
            stats.increment(
                metric_name=METRIC_NAME,
                pod_name=stats.PodNames.PAYMENTS_PLATFORM,
                tags=["reason:global_procedure_request_failed"],
            )
            self._set_error_info(
                error_message="Global Procedures request failed to retrieve data.",
                errors=errors,
            )
            return cost_breakdown_results, users, errors

        if (
            feature_flags.str_variation(HEALTH_PLAN_YOY_FLAG, default=OLD_BEHAVIOR)
            != OLD_BEHAVIOR
        ):
            health_plan_repo = HealthPlanRepository(session=self.session)

        for pharmacy_prescription in pharmacy_prescriptions:
            treatment_procedure = TreatmentProcedure.query.get(
                pharmacy_prescription.treatment_procedure_id
            )
            wallet = ReimbursementWallet.query.get(
                treatment_procedure.reimbursement_wallet_id
            )
            if not wallet:
                kwarg_errors = self._create_error_kwargs(
                    pharmacy_prescription=pharmacy_prescription
                )
                self._add_errors(
                    treatment_procedure=treatment_procedure,
                    errors=errors,
                    reason="invalid_wallet_id",
                    log_message="Invalid wallet ID",
                    benefit_id=pharmacy_prescription.maven_benefit_id,
                    cost_breakdown_results=cost_breakdown_results,
                    **kwarg_errors,
                )
                continue
            if (
                feature_flags.str_variation(HEALTH_PLAN_YOY_FLAG, default=OLD_BEHAVIOR)
                != OLD_BEHAVIOR
            ):
                member_health_plan = (
                    health_plan_repo.get_member_plan_by_wallet_and_member_id(
                        member_id=treatment_procedure.member_id,
                        wallet_id=wallet.id,
                        effective_date=treatment_procedure.start_date,
                    )
                )
            else:
                member_health_plan = MemberHealthPlan.query.filter(
                    MemberHealthPlan.member_id == treatment_procedure.member_id
                ).one_or_none()
            if (
                not member_health_plan
                and wallet.reimbursement_organization_settings.deductible_accumulation_enabled
            ):
                kwarg_errors = self._create_error_kwargs(
                    pharmacy_prescription=pharmacy_prescription
                )
                self._add_errors(
                    treatment_procedure=treatment_procedure,
                    errors=errors,
                    reason="missing_member_health_plan",
                    log_message="Member Health Plan missing for a ded accumulated org.",
                    benefit_id=pharmacy_prescription.maven_benefit_id,
                    cost_breakdown_results=cost_breakdown_results,
                    wallet=wallet,
                    **kwarg_errors,
                )
                continue

            existing_global_procedure = global_procedures.get(
                treatment_procedure.global_procedure_id
            )
            if not existing_global_procedure:
                kwarg_errors = self._create_error_kwargs(
                    pharmacy_prescription=pharmacy_prescription,
                    member_health_plan=member_health_plan,
                )
                self._add_errors(
                    treatment_procedure=treatment_procedure,
                    errors=errors,
                    reason="global_procedure_not_found",
                    log_message="Could not find existing Global Procedure record.",
                    benefit_id=pharmacy_prescription.maven_benefit_id,
                    cost_breakdown_results=cost_breakdown_results,
                    wallet=wallet,
                    **kwarg_errors,
                )
                continue

            gp_category = existing_global_procedure.get("cost_sharing_category")
            if not gp_category:
                kwarg_errors = self._create_error_kwargs(
                    pharmacy_prescription=pharmacy_prescription,
                    member_health_plan=member_health_plan,
                )
                self._add_errors(
                    treatment_procedure=treatment_procedure,
                    errors=errors,
                    reason="missing_cost_sharing_category",
                    log_message="Missing Cost Sharing Category.",
                    benefit_id=pharmacy_prescription.maven_benefit_id,
                    cost_breakdown_results=cost_breakdown_results,
                    wallet=wallet,
                    **kwarg_errors,
                )
                continue

            category = CostSharingCategory[gp_category.upper()]
            cost_breakdown = CostBreakdown.query.get(
                treatment_procedure.cost_breakdown_id
            )
            if not cost_breakdown:
                kwarg_errors = self._create_error_kwargs(
                    pharmacy_prescription=pharmacy_prescription,
                    member_health_plan=member_health_plan,
                    category=category,
                )
                self._add_errors(
                    treatment_procedure=treatment_procedure,
                    errors=errors,
                    reason="missing_cost_breakdown",
                    log_message="Cost Breakdown not created.",
                    benefit_id=pharmacy_prescription.maven_benefit_id,
                    cost_breakdown_results=cost_breakdown_results,
                    wallet=wallet,
                    **kwarg_errors,
                )
                continue

            eligibility_info = ytd_results = None
            if member_health_plan:
                rx_integrated = member_health_plan.employer_health_plan.rx_integrated
                try:
                    if rx_integrated:
                        rte_transaction = cost_breakdown.rte_transaction
                        pverify_response = rte_transaction.response
                        ytd_results = self._get_rx_integrated_ytd_results(
                            pverify_response
                        )
                        eligibility_info = self._get_rx_integrated_cost_share(
                            pverify_response
                        )
                    else:
                        ytd_results = self._get_ytd_results(
                            member_health_plan,
                            treatment_procedure,
                        )
                        eligibility_info = EligibilityInfo()
                except Exception as e:
                    kwarg_errors = self._create_error_kwargs(
                        pharmacy_prescription=pharmacy_prescription,
                        member_health_plan=member_health_plan,
                        category=category,
                    )
                    self._add_errors(
                        treatment_procedure=treatment_procedure,
                        errors=errors,
                        reason="audit_rte_error",
                        log_message=f"RTE transaction error: {e}",
                        benefit_id=pharmacy_prescription.maven_benefit_id,
                        cost_breakdown_results=cost_breakdown_results,
                        wallet=wallet,
                        **kwarg_errors,
                    )
                    continue
            try:
                user_info = self.get_user_info(
                    wallet=wallet,
                    benefit_id=pharmacy_prescription.maven_benefit_id,
                    treatment_procedure=treatment_procedure,
                    member_health_plan=member_health_plan,
                    errors=errors,
                    ytd_result=ytd_results,
                )
            except Exception as e:
                kwarg_errors = self._create_error_kwargs(
                    pharmacy_prescription=pharmacy_prescription,
                    member_health_plan=member_health_plan,
                    category=category,
                )
                self._add_errors(
                    treatment_procedure=treatment_procedure,
                    errors=errors,
                    reason="audit_user_info_error",
                    log_message=f"Error gathering UserInfo data: {e}",
                    benefit_id=pharmacy_prescription.maven_benefit_id,
                    cost_breakdown_results=cost_breakdown_results,
                    wallet=wallet,
                    **kwarg_errors,
                )
                continue

            if user_info.user_id not in users:
                users[user_info.user_id] = user_info

            try:
                cost_share, cost_share_data = self._get_cost_sharing(
                    member_health_plan=member_health_plan,
                    category=category,
                    eligibility_info=eligibility_info,  # type: ignore[arg-type] # Argument "eligibility_info" to "_get_cost_sharing" of "RxAudit" has incompatible type "Optional[EligibilityInfo]"; expected "EligibilityInfo"
                    cost_breakdown=cost_breakdown,
                    treatment_procedure=treatment_procedure,
                )
            except NoCostSharingFoundError:
                kwarg_errors = self._create_error_kwargs(
                    pharmacy_prescription=pharmacy_prescription,
                    member_health_plan=member_health_plan,
                    category=category,
                )
                self._add_errors(
                    treatment_procedure=treatment_procedure,
                    errors=errors,
                    reason="missing_cost_share",
                    log_message="No cost sharing found.",
                    benefit_id=pharmacy_prescription.maven_benefit_id,
                    cost_breakdown_results=cost_breakdown_results,
                    wallet=wallet,
                    **kwarg_errors,
                )
                continue

            result = self.get_result(
                pharmacy_prescription=pharmacy_prescription,
                category=category,
                cost_breakdown=cost_breakdown,
                treatment_procedure=treatment_procedure,
                user_info=user_info,
                cost_share_data=cost_share_data,
                cost_share=cost_share,
                member_health_plan=member_health_plan,
                wallet=wallet,
            )
            cost_breakdown_results.append(result)
        self._update_error_users(users, errors)
        return cost_breakdown_results, users, errors

    def get_result(
        self,
        pharmacy_prescription: PharmacyPrescription,
        category: CostSharingCategory,
        cost_breakdown: CostBreakdown,
        treatment_procedure: TreatmentProcedure,
        user_info: UserInfo,
        cost_share_data: EligibilityInfo,
        cost_share: int,
        member_health_plan: Optional[MemberHealthPlan],
        wallet: ReimbursementWallet,
    ) -> Results:
        # Calculated amount for audit purposes only
        deductible_remaining, oop_remaining = self._get_remaining_amounts(
            user_info, member_health_plan, cost_breakdown
        )
        individual_treatment_procedures = self.get_procedure_ids(
            member_health_plan, wallet, treatment_procedure.member_id
        )
        family_treatment_procedures = self.get_procedure_ids(member_health_plan, wallet)
        results = Results(
            drug_name=pharmacy_prescription.rx_name,  # type: ignore[arg-type] # Argument "drug_name" to "Results" has incompatible type "Optional[str]"; expected "str"
            price=pharmacy_prescription.amount_owed,  # type: ignore[arg-type] # Argument "price" to "Results" has incompatible type "Optional[int]"; expected "int"
            category=category.value,  # type: ignore[arg-type] # Argument "category" to "Results" has incompatible type "Union[str, str, str, str, str]"; expected "CostSharingCategory"
            applied_to_deductible=cost_breakdown.deductible,
            applied_to_coinsurance=cost_breakdown.coinsurance,
            applied_to_copay=cost_breakdown.copay,
            total_member_resp=cost_breakdown.total_member_responsibility,
            total_employer_resp=cost_breakdown.total_employer_responsibility,
            user_id=treatment_procedure.member_id,
            status=treatment_procedure.status.value,  # type: ignore[attr-defined] # "str" has no attribute "value"
            cost_share=cost_share,
            cost_share_min=cost_share_data.coinsurance_min if cost_share_data else None,  # type: ignore[arg-type] # Argument "cost_share_min" to "Results" has incompatible type "Optional[int]"; expected "int"
            cost_share_max=cost_share_data.coinsurance_max if cost_share_data else None,  # type: ignore[arg-type] # Argument "cost_share_max" to "Results" has incompatible type "Optional[int]"; expected "int"
            oop_applied=cost_breakdown.oop_applied,
            deductible_remaining_pre_cb=deductible_remaining,
            oop_remaining_pre_cb=oop_remaining,
            not_covered=cost_breakdown.overage_amount,
            treatment_procedure_id=treatment_procedure.id,
            member_ytd_charges=self.get_total_ytd_bills(
                individual_treatment_procedures
            ),
            family_ytd_charges=self.get_total_ytd_bills(family_treatment_procedures),
        )
        return results

    def get_user_info(
        self,
        wallet: ReimbursementWallet,
        benefit_id: str,
        treatment_procedure: TreatmentProcedure,
        member_health_plan: Optional[MemberHealthPlan],
        errors: dict,
        ytd_result: Optional[dict],
    ) -> UserInfo:
        org_name = wallet.reimbursement_organization_settings.organization.name
        if not member_health_plan:
            self._set_error_info(
                error_message="Member Health Plan missing, assuming fully covered.",
                errors=errors,
                treatment_procedure=treatment_procedure,
                benefit_id=benefit_id,
                cost_breakdown_results=None,  # type: ignore[arg-type] # Argument "cost_breakdown_results" to "_set_error_info" of "RxAudit" has incompatible type "None"; expected "List[Union[Results, ErrorInfo]]"
                append_result=False,
            )
            return UserInfo(
                org_name=org_name,
                benefit_id=benefit_id,
                wallet_id=wallet.id,
                user_id=treatment_procedure.member_id,
                treatment_procedure_id=treatment_procedure.id,
            )
        else:
            employer_health_plan = member_health_plan.employer_health_plan
            tier = None
            if is_plan_tiered(ehp=employer_health_plan):
                tier = Tier.PREMIUM
            coverage = self._get_coverage(
                employer_health_plan,
                plan_size=FamilyPlanType(member_health_plan.plan_type),
                tier=tier,
            )

            return UserInfo(
                org_name=org_name,
                benefit_id=benefit_id,
                wallet_id=wallet.id,
                user_id=treatment_procedure.member_id,
                treatment_procedure_id=treatment_procedure.id,
                member_health_plan_id=member_health_plan.id,
                subscriber_id=member_health_plan.subscriber_insurance_id,
                employer_health_plan_name=employer_health_plan.name,
                is_hdhp=employer_health_plan.is_hdhp,
                deductible_embedded=coverage.get("deductible_embedded"),  # type: ignore[arg-type] # Argument "ind_ded_limit" to "UserInfo" has incompatible type "Optional[Any]"; expected "int"
                oopm_embedded=coverage.get("oopm_embedded"),  # type: ignore[arg-type] # Argument "ind_ded_limit" to "UserInfo" has incompatible type "Optional[Any]"; expected "int"
                rx_integrated=employer_health_plan.rx_integrated,
                is_family_plan=(
                    "Family" if member_health_plan.is_family_plan else "Individual"
                ),
                ind_ded_limit=coverage.get("ind_ded_limit"),  # type: ignore[arg-type] # Argument "ind_ded_limit" to "UserInfo" has incompatible type "Optional[Any]"; expected "int"
                ind_oopm_limit=coverage.get("ind_oopm_limit"),  # type: ignore[arg-type] # Argument "ind_oopm_limit" to "UserInfo" has incompatible type "Optional[Any]"; expected "int"
                ind_ded_ytd=coverage.get("individual_ytd_deductible"),  # type: ignore[union-attr,arg-type] # Item "None" of "Optional[Dict[Any, Any]]" has no attribute "get" #type: ignore[arg-type] # Argument "ind_ded_ytd" to "UserInfo" has incompatible type "Optional[Any]"; expected "int"
                ind_oopm_ytd=coverage.get("individual_oop"),  # type: ignore[union-attr,arg-type] # Item "None" of "Optional[Dict[Any, Any]]" has no attribute "get" #type: ignore[arg-type] # Argument "ind_oopm_ytd" to "UserInfo" has incompatible type "Optional[Any]"; expected "int"
                fam_ded_ytd=coverage.get("family_ytd_deductible"),  # type: ignore[union-attr,arg-type] # Item "None" of "Optional[Dict[Any, Any]]" has no attribute "get" #type: ignore[arg-type] # Argument "fam_ded_ytd" to "UserInfo" has incompatible type "Optional[Any]"; expected "int"
                fam_oopm_ytd=coverage.get("family_oop"),  # type: ignore[union-attr,arg-type] # Item "None" of "Optional[Dict[Any, Any]]" has no attribute "get" #type: ignore[arg-type] # Argument "fam_oopm_ytd" to "UserInfo" has incompatible type "Optional[Any]"; expected "int"
                fam_oopm_limit=coverage.get("fam_oopm_limit"),  # type: ignore[arg-type] # Argument "fam_oopm_limit" to "UserInfo" has incompatible type "Optional[Any]"; expected "int"
                fam_ded_limit=coverage.get("fam_ded_limit"),  # type: ignore[arg-type] # Argument "fam_ded_limit" to "UserInfo" has incompatible type "Optional[Any]"; expected "int"
            )

    def _get_rx_global_procedures(
        self,
        pharmacy_prescriptions: List[PharmacyPrescription],
    ) -> Optional[dict]:
        treatment_procedure_ids = [
            rx.treatment_procedure_id for rx in pharmacy_prescriptions
        ]
        global_procedure_ids_set = {
            tp.global_procedure_id
            for tp in TreatmentProcedure.query.with_entities(
                TreatmentProcedure.global_procedure_id
            )
            .filter(TreatmentProcedure.id.in_(treatment_procedure_ids))
            .all()
        }
        return self._mapped_rx_global_procedures(global_procedure_ids_set)

    def _mapped_rx_global_procedures(
        self, global_procedure_ids: set[str]
    ) -> Optional[dict]:
        found_procedures = self.procedure_service_client.get_procedures_by_ids(
            procedure_ids=list(global_procedure_ids)
        )
        if not found_procedures:
            log.info("No global procedures found.")
            return None

        return {
            global_procedure["id"]: global_procedure  # type: ignore[typeddict-item] # TypedDict "PartialProcedure" has no key "id"
            for global_procedure in found_procedures
        }

    @staticmethod
    def _get_rx_integrated_ytd_results(pverify_response: dict) -> dict:
        def calculate_ytd_amounts(amount, remaining, ytd_type):  # type: ignore[no-untyped-def] # Function is missing a type annotation
            missing_string = ""
            if amount is not None and remaining is not None:
                return amount - remaining
            if amount is None:
                missing_string += f"Missing {ytd_type} "
            if remaining is None:
                missing_string += f"Missing {ytd_type}_remaining"
            return missing_string

        individual_ytd_deductible = calculate_ytd_amounts(
            pverify_response.get("individual_deductible"),
            pverify_response.get("individual_deductible_remaining"),
            "individual_deductible",
        )

        family_ytd_deductible = calculate_ytd_amounts(
            pverify_response.get("family_deductible"),
            pverify_response.get("family_deductible_remaining"),
            "family_deductible",
        )

        individual_oop_ytd = calculate_ytd_amounts(
            pverify_response.get("individual_oop"),
            pverify_response.get("individual_oop_remaining"),
            "individual_oop",
        )

        family_oop_ytd = calculate_ytd_amounts(
            pverify_response.get("family_oop"),
            pverify_response.get("family_oop_remaining"),
            "family_oop",
        )

        return {
            "individual_ytd_deductible": individual_ytd_deductible,
            "individual_oop": individual_oop_ytd,
            "family_ytd_deductible": family_ytd_deductible,
            "family_oop": family_oop_ytd,
        }

    @staticmethod
    def _get_rx_integrated_cost_share(pverify_response) -> EligibilityInfo:  # type: ignore[no-untyped-def] # Function is missing a type annotation for one or more arguments
        return EligibilityInfo(
            coinsurance=pverify_response.get("coinsurance"),
            copay=pverify_response.get("copay"),
            coinsurance_min=pverify_response.get("coinsurance_min"),
            coinsurance_max=pverify_response.get("coinsurance_max"),
        )

    def _get_ytd_results(
        self,
        member_health_plan: MemberHealthPlan,
        treatment_procedure: TreatmentProcedure,
    ) -> dict:
        member_first_name, member_last_name = get_member_first_and_last_name(
            user_id=treatment_procedure.member_id,
            member_health_plan=member_health_plan,
        )
        if not member_first_name or not member_last_name:
            raise NoPatientNameFoundError("Missing patient name")

        policy_id = self.cost_breakdown_processor.rx_rte_processor.get_policy_id(
            member_health_plan
        )
        ytd_info = self.cost_breakdown_processor.rx_rte_processor.ytd_info_from_spends(
            policy_id, member_health_plan, member_first_name, member_last_name
        )
        return {
            "individual_ytd_deductible": ytd_info.ind_ytd_deductible,
            "individual_oop": ytd_info.ind_ytd_oop,
            "family_ytd_deductible": ytd_info.family_ytd_deductible,
            "family_oop": ytd_info.family_ytd_oop,
        }

    def _get_cost_sharing(
        self,
        member_health_plan: Optional[MemberHealthPlan],
        category: CostSharingCategory,
        eligibility_info: EligibilityInfo,
        cost_breakdown: CostBreakdown,
        treatment_procedure: TreatmentProcedure,
    ) -> Optional[int, dict]:  # type: ignore[valid-type] # Optional[...] must have exactly one type argument
        cost_share = cost_share_info = None
        if member_health_plan:
            employer_health_plan = member_health_plan.employer_health_plan
            tier = None
            if is_plan_tiered(ehp=employer_health_plan):
                tier = Tier.PREMIUM
            if employer_health_plan.rx_integrated:
                rte_processor = RTEProcessor()
                cost_share_info = rte_processor._get_copay_coinsurance(
                    eligibility_info=eligibility_info,
                    cost_sharings=employer_health_plan.cost_sharings,
                    cost_sharing_category=category,
                    procedure_type=treatment_procedure.procedure_type,  # type: ignore[arg-type] # Argument "procedure_type" to "_get_copay_coinsurance" of "RTEProcessor" has incompatible type "str"; expected "TreatmentProcedureType"
                    tier=tier,
                )
            else:
                cost_share_info = set_db_copay_coinsurance_to_eligibility_info(
                    eligibility_info=eligibility_info,
                    cost_sharings=member_health_plan.employer_health_plan.cost_sharings,
                    cost_sharing_category=category,
                    tier=tier,
                )

            cost_share = getattr(cost_share_info, "copay", None) or getattr(
                cost_share_info, "coinsurance", None
            )
        return cost_share, cost_share_info

    @staticmethod
    def _get_remaining_amounts(
        user_info: UserInfo,
        member_health_plan: Optional[MemberHealthPlan],
        cost_breakdown: CostBreakdown,
    ) -> Tuple[int, int]:
        def calculate_remaining(post_total_remaining, applied_amount):  # type: ignore[no-untyped-def] # Function is missing a type annotation
            post_total_remaining = post_total_remaining if post_total_remaining else 0
            applied_amount = applied_amount if applied_amount else 0
            return post_total_remaining + applied_amount

        deductible_remaining = oop_remaining = None
        if member_health_plan:
            if not user_info.is_family_plan or user_info.deductible_embedded:
                deductible_remaining = calculate_remaining(
                    cost_breakdown.deductible_remaining, cost_breakdown.deductible
                )
            else:
                deductible_remaining = calculate_remaining(
                    cost_breakdown.family_deductible_remaining,
                    cost_breakdown.deductible,
                )
            if not user_info.is_family_plan or user_info.oopm_embedded:
                oop_remaining = calculate_remaining(
                    cost_breakdown.oop_remaining, cost_breakdown.oop_applied
                )
            else:
                oop_remaining = calculate_remaining(
                    cost_breakdown.family_oop_remaining, cost_breakdown.oop_applied
                )
        return deductible_remaining, oop_remaining  # type: ignore[return-value] # Incompatible return value type (got "Tuple[Optional[Any], Optional[Any]]", expected "Tuple[int, int]")

    @staticmethod
    def _set_error_info(  # type: ignore[no-untyped-def] # Function is missing a type annotation for one or more arguments
        error_message: str,
        errors: dict,
        treatment_procedure: TreatmentProcedure = None,  # type: ignore[assignment] # Incompatible default for argument "treatment_procedure" (default has type "None", argument has type "TreatmentProcedure")
        benefit_id=None,
        cost_breakdown_results: List[Results | ErrorInfo] = None,  # type: ignore[assignment] # Incompatible default for argument "cost_breakdown_results" (default has type "None", argument has type "List[Union[Results, ErrorInfo]]")
        append_result: bool = True,
        wallet: ReimbursementWallet = None,  # type: ignore[assignment] # Incompatible default for argument "wallet" (default has type "None", argument has type "ReimbursementWallet")
        **kwargs,
    ) -> dict:
        org_name = (
            wallet.reimbursement_organization_settings.organization.name
            if wallet
            else None
        )
        if treatment_procedure:
            error_info = ErrorInfo(
                user_id=treatment_procedure.member_id,
                treatment_procedure_id=treatment_procedure.id,
                wallet_id=treatment_procedure.reimbursement_wallet_id,
                benefit_id=benefit_id,
                error_message=error_message,
                org_name=org_name,
                status=treatment_procedure.status.value,  # type: ignore[attr-defined] # "str" has no attribute "value"
                **kwargs,
            )
            if error_info.treatment_procedure_id not in errors:
                errors[error_info.treatment_procedure_id] = error_info
            if append_result:
                cost_breakdown_results.append(error_info)  # type: ignore[union-attr] # Item "None" of "Optional[List[Union[Results, ErrorInfo]]]" has no attribute "append"
        else:
            errors["general_error"] = error_message
        return errors

    def _add_errors(  # type: ignore[no-untyped-def] # Function is missing a return type annotation #type: ignore[no-untyped-def] # Function is missing a type annotation for one or more arguments
        self,
        treatment_procedure: TreatmentProcedure,
        errors: dict,
        reason: str,
        log_message: str,
        benefit_id: str,
        cost_breakdown_results: List[Results | ErrorInfo],
        wallet: ReimbursementWallet = None,  # type: ignore[assignment] # Incompatible default for argument "wallet" (default has type "None", argument has type "ReimbursementWallet")
        append_result: bool = True,
        **kwargs,
    ):
        log.error(
            log_message,
            wallet_id=str(treatment_procedure.reimbursement_wallet_id),
            treatment_procedure_id=treatment_procedure.id,
        )
        stats.increment(
            metric_name=METRIC_NAME,
            pod_name=stats.PodNames.PAYMENTS_PLATFORM,
            tags=[f"reason:{reason}"],
        )
        self._set_error_info(
            log_message,
            errors,
            treatment_procedure,
            benefit_id,
            cost_breakdown_results,
            append_result,
            wallet,
            **kwargs,
        )

    def _create_error_kwargs(
        self,
        pharmacy_prescription: Optional[PharmacyPrescription] = None,  # type: ignore[assignment] # Incompatible default for argument "pharmacy_prescription" (default has type "None", argument has type "PharmacyPrescription")
        member_health_plan: Optional[MemberHealthPlan] = None,  # type: ignore[assignment] # Incompatible default for argument "member_health_plan" (default has type "None", argument has type "MemberHealthPlan")
        category: Optional[CostSharingCategory] = None,  # type: ignore[assignment] # Incompatible default for argument "category" (default has type "None", argument has type "CostSharingCategory")
    ) -> dict:
        pharmacy_errors = self._pharmacy_prescription_errors(pharmacy_prescription)  # type: ignore[arg-type] # Argument 1 to "_pharmacy_prescription_errors" of "RxAudit" has incompatible type "Optional[PharmacyPrescription]"; expected "PharmacyPrescription"
        member_health_plan_errors = self._member_health_plan_errors(member_health_plan)  # type: ignore[arg-type] # Argument 1 to "_member_health_plan_errors" of "RxAudit" has incompatible type "Optional[MemberHealthPlan]"; expected "MemberHealthPlan"
        category_errors = {"category": category.value} if category else {}
        return {
            **pharmacy_errors,
            **member_health_plan_errors,
            **category_errors,
        }

    @staticmethod
    def _pharmacy_prescription_errors(pharmacy_prescription: PharmacyPrescription):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        pharmacy_errors = {}
        if pharmacy_prescription:
            pharmacy_errors = {
                "price": pharmacy_prescription.amount_owed,
                "drug_name": pharmacy_prescription.rx_name,
            }
        return pharmacy_errors

    def _member_health_plan_errors(self, member_health_plan: MemberHealthPlan):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        member_health_errors = {}
        if member_health_plan:
            mhp = {
                "member_health_plan_id": member_health_plan.id,
                "subscriber_id": member_health_plan.subscriber_insurance_id,
                "is_family_plan": (
                    "Family" if member_health_plan.is_family_plan else "Individual"
                ),
            }
            employer_health_plan = member_health_plan.employer_health_plan
            ehp = {}
            if employer_health_plan:
                tier = None
                if is_plan_tiered(ehp=employer_health_plan):
                    tier = Tier.PREMIUM
                coverage = self._get_coverage(
                    employer_health_plan=employer_health_plan,
                    plan_size=FamilyPlanType(member_health_plan.plan_type),
                    tier=tier,
                )
                ehp = {
                    "is_hdhp": employer_health_plan.is_hdhp,
                    "rx_integrated": employer_health_plan.rx_integrated,
                    "employer_health_plan_name": employer_health_plan.name,
                    "deductible_embedded": coverage.get("deductible_embedded"),
                    "oopm_embedded": coverage.get("oopm_embedded"),
                    "ind_ded_limit": coverage.get("ind_ded_limit"),
                    "ind_oopm_limit": coverage.get("ind_oopm_limit"),
                    "fam_oopm_limit": coverage.get("fam_oopm_limit"),
                    "fam_ded_limit": coverage.get("fam_ded_limit"),
                }
            member_health_errors = {**mhp, **ehp}
        return member_health_errors

    @staticmethod
    def _get_coverage(
        employer_health_plan: EmployerHealthPlan,
        plan_size: FamilyPlanType,
        tier: Optional[Tier],
    ) -> dict:
        coverage = {}
        if employer_health_plan:
            rx_integrated = employer_health_plan.rx_integrated
            if rx_integrated:
                coverage_raw = get_medical_coverage(
                    ehp=employer_health_plan, plan_size=plan_size, tier=tier
                )
            else:
                coverage_raw = get_rx_coverage(
                    ehp=employer_health_plan, plan_size=plan_size, tier=tier
                )
            coverage = {
                "ind_ded_limit": coverage_raw.individual_deductible,
                "ind_oopm_limit": coverage_raw.individual_oop,
                "fam_oopm_limit": coverage_raw.family_oop,
                "fam_ded_limit": coverage_raw.family_deductible,
                "deductible_embedded": coverage_raw.is_deductible_embedded,
                "oopm_embedded": coverage_raw.is_oop_embedded,
            }
        return coverage

    @staticmethod
    def _update_error_users(users: dict, errors: dict):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        for _, value in errors.items():
            if value.user_id not in users:
                user_info = UserInfo(
                    org_name=value.org_name,
                    benefit_id=value.benefit_id,
                    wallet_id=value.wallet_id,
                    user_id=value.user_id,
                    treatment_procedure_id=value.treatment_procedure_id,
                )
                users[user_info.user_id] = user_info

    def get_procedure_ids(
        self,
        member_health_plan: Optional[MemberHealthPlan],
        wallet: ReimbursementWallet,
        member_id: int = None,  # type: ignore[assignment] # Incompatible default for argument "member_id" (default has type "None", argument has type "int")
    ) -> list[int]:
        treatment_status = [
            TreatmentProcedureStatus.COMPLETED,
            TreatmentProcedureStatus.SCHEDULED,
            TreatmentProcedureStatus.PARTIALLY_COMPLETED,
        ]
        rx_integrated = None
        if member_health_plan:
            rx_integrated = member_health_plan.employer_health_plan.rx_integrated

        procedure_type = None if rx_integrated else TreatmentProcedureType.PHARMACY
        treatment_procedures = self.treatment_procedure_repo.get_treatments_since_datetime_from_statuses_type_wallet_ids(
            wallet_ids=[wallet.id],
            statuses=treatment_status,
            procedure_type=procedure_type,
            member_id=member_id,
        )
        return [tp.id for tp in treatment_procedures]

    def get_total_ytd_bills(self, procedure_ids) -> int:  # type: ignore[no-untyped-def] # Function is missing a type annotation for one or more arguments
        total_amount = 0
        if procedure_ids:
            bills = self.billing_service.get_money_movement_bills_by_procedure_ids_payor_type_ytd(
                procedure_ids=procedure_ids,
                payor_type=PayorType.MEMBER,
            )
            total_amount = sum(bill.amount for bill in bills)
        return total_amount
