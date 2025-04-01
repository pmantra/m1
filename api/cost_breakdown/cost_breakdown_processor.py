from __future__ import annotations

import dataclasses
import datetime
from typing import List, Optional, Tuple, Union

import sqlalchemy
import structlog.contextvars
from maven import feature_flags
from sqlalchemy import func
from sqlalchemy.sql.expression import and_, or_

from common import stats
from common.global_procedures.procedure import ProcedureService
from cost_breakdown import errors
from cost_breakdown.constants import (
    ENABLE_UNLIMITED_BENEFITS_FOR_CB,
    AmountType,
    CostBreakdownType,
    Tier,
)
from cost_breakdown.cost_breakdown_data_service import CostBreakdownDataService
from cost_breakdown.models.cost_breakdown import (
    CalcConfigAudit,
    CostBreakdown,
    CostBreakdownData,
    DeductibleAccumulationYTDInfo,
    ExtraAppliedAmount,
    HDHPAccumulationYTDInfo,
    SystemUser,
)
from cost_breakdown.models.rte import EligibilityInfo
from cost_breakdown.rte.rte_processor import get_member_first_and_last_name
from cost_breakdown.rte.rx_rte_processor import RxRteProcessor
from cost_breakdown.utils.helpers import (
    get_amount_type,
    get_calculation_tier,
    is_plan_tiered,
)
from direct_payment.treatment_procedure.models.treatment_procedure import (
    TreatmentProcedure,
    TreatmentProcedureStatus,
    TreatmentProcedureType,
)
from payer_accumulator.common import TreatmentAccumulationStatus
from payer_accumulator.models.payer_accumulation_reporting import (
    AccumulationTreatmentMapping,
)
from storage.connection import db
from utils.log import logger
from wallet.models.constants import (
    CostSharingCategory,
    ReimbursementRequestState,
    ReimbursementRequestType,
)
from wallet.models.reimbursement import (
    ReimbursementRequest,
    ReimbursementRequestCategory,
)
from wallet.models.reimbursement_organization_settings import EmployerHealthPlan
from wallet.models.reimbursement_wallet import MemberHealthPlan, ReimbursementWallet
from wallet.models.reimbursement_wallet_user import ReimbursementWalletUsers
from wallet.repository.health_plan import (
    HEALTH_PLAN_YOY_FLAG,
    NEW_BEHAVIOR,
    OLD_BEHAVIOR,
    HealthPlanRepository,
)
from wallet.services.reimbursement_wallet import ReimbursementWalletService
from wallet.utils.alegeus.enrollments.enroll_wallet import (
    get_alegeus_hdhp_plan_year_to_date_spend,
)
from wallet.utils.annual_questionnaire.utils import (
    FdcHdhpCheckResults,
    check_if_wallet_is_fdc_hdhp,
)

log = logger(__name__)

METRIC_PREFIX = "api.cost_breakdown.cost_breakdown_processor"


class CostBreakdownProcessor:
    extra_applied_amount: Optional[ExtraAppliedAmount] = None

    def __init__(
        self,
        session: sqlalchemy.orm.Session = None,  # type: ignore[assignment] # Incompatible default for argument "session" (default has type "None", argument has type "Session")
        procedure_service_client: ProcedureService = None,  # type: ignore[assignment] # Incompatible default for argument "procedure_service_client" (default has type "None", argument has type "ProcedureService")
        system_user: SystemUser = None,  # type: ignore[assignment] # Incompatible default for argument "system_user" (default has type "None", argument has type "SystemUser")
    ):
        self.session = session or db.session
        self.procedure_service_client = procedure_service_client or ProcedureService()
        self.rx_rte_processor = RxRteProcessor(session=self.session)  # type: ignore[arg-type]
        self.calc_config = CalcConfigAudit(system_user=system_user)  # type: ignore[arg-type]

    def get_cost_breakdown_for_treatment_procedure(
        self,
        wallet: ReimbursementWallet,
        treatment_procedure: TreatmentProcedure,
        wallet_balance: Optional[int] = None,
        store_to_db: Optional[bool] = True,
        override_rte_result: Optional[EligibilityInfo] = None,
    ) -> CostBreakdown:
        """
        wallet: The reimbursement wallet used to calculate cost breakdown.
        treatment_procedure: The treatment procedure used to calculate cost breakdown.
        wallet_balance: available wallet balance in cents, if it's None by default it will use reimbursement wallet's
        balance, if it's specified then the overridden amount will be used.
        """
        stats.increment(
            metric_name=f"{METRIC_PREFIX}",
            pod_name=stats.PodNames.PAYMENTS_PLATFORM,
            tags=["attempt:true"],
        )

        # Although we do not pass the treatment_procedure_uuid into the cost breakdown logic
        # We keep it attached to all relevant logs via context here.
        structlog.contextvars.bind_contextvars(
            treatment_procedure_uuid=treatment_procedure.uuid
            if treatment_procedure
            else treatment_procedure,
            reimbursement_wallet_id=str(wallet.id)
            if wallet
            else wallet,  # prevent rounding of snowflake ids
        )
        if treatment_procedure.status == TreatmentProcedureStatus.SCHEDULED:
            before_this_date = treatment_procedure.created_at
            self.calc_config.should_include_pending = True
        elif treatment_procedure.status == TreatmentProcedureStatus.CANCELLED:
            raise errors.UnsupportedTreatmentProcedureException(
                "Cannot calculate cost breakdown for a CANCELLED procedure"
            )
        else:
            if not treatment_procedure.completed_date:
                raise errors.UnsupportedTreatmentProcedureException(
                    "No treatment procedure completed date"
                )
            before_this_date = treatment_procedure.completed_date

        if not treatment_procedure.start_date:
            raise errors.UnsupportedTreatmentProcedureException(
                "No treatment procedure start date!"
            )

        self.calc_config.trigger_object_status = treatment_procedure.status.value  # type: ignore[attr-defined] # "str" has no attribute "value"

        effective_date = datetime.datetime.combine(
            treatment_procedure.start_date, datetime.datetime.min.time()  # type: ignore[arg-type]
        )

        if (
            feature_flags.str_variation(HEALTH_PLAN_YOY_FLAG, default=OLD_BEHAVIOR)
            != OLD_BEHAVIOR
        ):
            employer_health_plan = self._get_employer_health_plan(
                member_id=treatment_procedure.member_id,
                wallet_id=wallet.id,
                effective_date=effective_date,
            )
        else:
            member_health_plan = self._get_member_health_plan(
                member_id=treatment_procedure.member_id,
                wallet_id=wallet.id,
                effective_date=effective_date,
            )
            employer_health_plan = (
                member_health_plan.employer_health_plan
                if member_health_plan and member_health_plan.employer_health_plan
                else None
            )

        if employer_health_plan and is_plan_tiered(ehp=employer_health_plan):
            if treatment_procedure.procedure_type == TreatmentProcedureType.PHARMACY:
                tier = Tier.PREMIUM
            else:
                tier = get_calculation_tier(
                    ehp=employer_health_plan,
                    fertility_clinic_location=treatment_procedure.fertility_clinic_location,
                    treatment_procedure_start=treatment_procedure.start_date,
                    # type: ignore[arg-type] # Argument "treatment_procedure_start" to "get_calculation_tier" has incompatible type "Optional[date]"; expected "date"
                )
        else:
            tier = None

        fdc_hdhp_check = None
        fdc_hdhp_check = check_if_wallet_is_fdc_hdhp(
            wallet=wallet,
            user_id=treatment_procedure.member_id,
            effective_date=effective_date,
        )

        data_service = self.cost_breakdown_data_service_from_treatment_procedure(
            cost=treatment_procedure.cost,
            member_id=treatment_procedure.member_id,
            wallet=wallet,
            reimbursement_category=treatment_procedure.reimbursement_request_category,
            procedure_type=treatment_procedure.procedure_type,  # type: ignore[arg-type] # Argument "procedure_type" to "cost_breakdown_data_service_from_treatment_procedure" of "CostBreakdownProcessor" has incompatible type "str"; expected "TreatmentProcedureType"
            before_this_date=before_this_date,
            asof_date=effective_date,
            service_start_date=treatment_procedure.start_date,
            global_procedure_id=treatment_procedure.global_procedure_id,
            wallet_balance_override=wallet_balance,
            should_include_pending=self.calc_config.should_include_pending,
            tier=tier,
            fdc_hdhp_check=fdc_hdhp_check,
            treatment_procedure_id=treatment_procedure.id,
        )
        if override_rte_result:
            data_service.override_rte_result = override_rte_result
            self.calc_config.eligibility_info = override_rte_result
        cost_breakdown_data = self._run_data_service(data_service)

        cost_breakdown = CostBreakdown(
            treatment_procedure_uuid=treatment_procedure.uuid,
            wallet_id=wallet.id,
            member_id=treatment_procedure.member_id,
            is_unlimited=cost_breakdown_data.is_unlimited,
            total_member_responsibility=cost_breakdown_data.total_member_responsibility,
            total_employer_responsibility=cost_breakdown_data.total_employer_responsibility,
            beginning_wallet_balance=cost_breakdown_data.beginning_wallet_balance,
            ending_wallet_balance=cost_breakdown_data.ending_wallet_balance,
            deductible=cost_breakdown_data.deductible,
            oop_applied=cost_breakdown_data.oop_applied,
            hra_applied=cost_breakdown_data.hra_applied,
            coinsurance=cost_breakdown_data.coinsurance,
            copay=cost_breakdown_data.copay,
            oop_remaining=cost_breakdown_data.oop_remaining,
            overage_amount=cost_breakdown_data.overage_amount,
            deductible_remaining=cost_breakdown_data.deductible_remaining,
            family_deductible_remaining=cost_breakdown_data.family_deductible_remaining,
            family_oop_remaining=cost_breakdown_data.family_oop_remaining,
            amount_type=get_amount_type(data_service.member_health_plan),
            cost_breakdown_type=cost_breakdown_data.cost_breakdown_type,
            rte_transaction_id=cost_breakdown_data.rte_transaction_id,
            calc_config=dataclasses.asdict(
                self.calc_config,
                dict_factory=lambda x: {k: v for (k, v) in x if v is not None},
            ),
        )

        if store_to_db:
            self._store_cost_breakdown_to_db(cost_breakdown, wallet)

        stats.increment(
            metric_name=f"{METRIC_PREFIX}",
            pod_name=stats.PodNames.PAYMENTS_PLATFORM,
            tags=["success:true"],
        )
        return cost_breakdown

    def get_cost_breakdown_for_reimbursement_request(
        self,
        reimbursement_request: ReimbursementRequest,
        user_id: int,
        cost_sharing_category: Optional[str],
        wallet_balance_override: Optional[int],
        override_rte_result: Optional[EligibilityInfo] = None,
        override_tier: Optional[Tier] = None,
    ) -> CostBreakdown:
        stats.increment(
            metric_name=f"{METRIC_PREFIX}",
            pod_name=stats.PodNames.PAYMENTS_PLATFORM,
            tags=["attempt:true"],
        )
        # Although we do not pass the reimbursement request id into the cost breakdown logic
        # We keep it attached to all relevant logs via context here.
        structlog.contextvars.bind_contextvars(
            reimbursement_request_id=str(reimbursement_request.id)
            if reimbursement_request
            else None,
            reimbursement_wallet_id=str(reimbursement_request.reimbursement_wallet_id)
            if reimbursement_request
            else None,  # prevent rounding of snowflake ids
        )
        self.calc_config.trigger_object_status = reimbursement_request.state.value  # type: ignore[attr-defined] # "str" has no attribute "value"

        data_service = self.cost_breakdown_data_service_from_reimbursement_request(
            reimbursement_request=reimbursement_request,
            asof_date=reimbursement_request.service_start_date,
            user_id=user_id,
            cost_sharing_category=cost_sharing_category,
            wallet_balance_override=wallet_balance_override,
            tier=override_tier,
        )
        if override_rte_result:
            data_service.override_rte_result = override_rte_result
            self.calc_config.eligibility_info = override_rte_result
        cost_breakdown_data = self._run_data_service(data_service)

        cost_breakdown = CostBreakdown(
            wallet_id=reimbursement_request.reimbursement_wallet_id,
            member_id=reimbursement_request.person_receiving_service_id,
            reimbursement_request_id=reimbursement_request.id,
            total_member_responsibility=cost_breakdown_data.total_member_responsibility,
            total_employer_responsibility=cost_breakdown_data.total_employer_responsibility,
            is_unlimited=cost_breakdown_data.is_unlimited,
            beginning_wallet_balance=cost_breakdown_data.beginning_wallet_balance,
            ending_wallet_balance=cost_breakdown_data.ending_wallet_balance,
            deductible=cost_breakdown_data.deductible,
            deductible_remaining=cost_breakdown_data.deductible_remaining,
            family_deductible_remaining=cost_breakdown_data.family_deductible_remaining,
            coinsurance=cost_breakdown_data.coinsurance,
            copay=cost_breakdown_data.copay,
            oop_applied=cost_breakdown_data.oop_applied,
            hra_applied=cost_breakdown_data.hra_applied,
            oop_remaining=cost_breakdown_data.oop_remaining,
            family_oop_remaining=cost_breakdown_data.family_oop_remaining,
            overage_amount=cost_breakdown_data.overage_amount,
            amount_type=AmountType(cost_breakdown_data.amount_type),
            cost_breakdown_type=CostBreakdownType(
                cost_breakdown_data.cost_breakdown_type
            ),
            rte_transaction_id=cost_breakdown_data.rte_transaction_id,
            calc_config=dataclasses.asdict(self.calc_config),
        )

        stats.increment(
            metric_name=f"{METRIC_PREFIX}",
            pod_name=stats.PodNames.PAYMENTS_PLATFORM,
            tags=["success:true"],
        )
        return cost_breakdown

    def _run_data_service(
        self, data_service: CostBreakdownDataService
    ) -> CostBreakdownData:
        """
        Unify error handling across reimbursement request and treatment procedure cost breakdown data generation
        """
        try:
            return data_service.get_cost_breakdown_data()
        except (
            errors.ActionableCostBreakdownException,
            errors.CostBreakdownInvalidInput,
        ) as e:
            # This log has a datadog alert that notifies RTE ops. Do not change the message without changing the alert.
            log.error(
                "Cost breakdown calculations have failed due to missing or invalid data.",
                cost=data_service.cost,
                wallet_balance=data_service.wallet_balance,
                using_override_rte_result=bool(data_service.override_rte_result),
                error_message=str(e),
            )
            raise e
        except Exception as e:
            # This log has a datadog alert that notifies RTE ops. Do not change the message without changing the alert.
            log.error(
                "Cost breakdown calculations have failed due to an unexpected error.",
                cost=data_service.cost,
                wallet_balance=data_service.wallet_balance,
                using_override_rte_result=bool(data_service.override_rte_result),
                error_message=str(e),
            )
            raise e

    def _wallet_balance_from_wallet(  # type: ignore[no-untyped-def] # Function is missing a type annotation for one or more arguments
        self, reimbursement_category_id, wallet
    ) -> int:
        available_categories = wallet.get_or_create_wallet_allowed_categories
        if reimbursement_category_id not in [
            category_assoc.reimbursement_request_category_id
            for category_assoc in available_categories
        ]:
            log.error(
                "Invalid reimbursement category!",
                wallet_id=str(wallet.id),
                reimbursement_category_id=reimbursement_category_id,
            )
            raise errors.InvalidReimbursementCategoryIDError(
                f"The reimbursement category {reimbursement_category_id} is not available for this wallet."
            )
        wallet_balance = wallet.available_currency_amount_by_category.get(
            reimbursement_category_id
        )
        if wallet_balance is None:
            log.error(
                "Missing wallet balance for reimbursement category!",
                wallet_id=str(wallet.id),
                reimbursement_category_id=reimbursement_category_id,
            )
            stats.increment(
                metric_name=f"{METRIC_PREFIX}",
                pod_name=stats.PodNames.PAYMENTS_PLATFORM,
                tags=["success:false", "reason:invalid_reimbursement_category"],
            )
            raise errors.InvalidReimbursementCategoryIDError(
                f"No wallet balance found for reimbursement category {reimbursement_category_id} in this wallet's organization settings. "
                "This may be due to an inactive reimbursement plan or a missing reimbursement_request_category_maximum."
            )
        return wallet_balance

    def _get_member_health_plan(  # type: ignore[no-untyped-def]
        self, member_id: int, wallet_id: int, effective_date: datetime.datetime
    ):
        if (
            feature_flags.str_variation(HEALTH_PLAN_YOY_FLAG, default=OLD_BEHAVIOR)
            != OLD_BEHAVIOR
        ):
            health_plan_repo = HealthPlanRepository(session=self.session)

            member_health_plan = (
                health_plan_repo.get_member_plan_by_wallet_and_member_id(
                    member_id=member_id,
                    wallet_id=wallet_id,
                    effective_date=effective_date,
                )
            )
        else:
            member_health_plan = (
                self.session.query(MemberHealthPlan)
                .filter_by(
                    member_id=member_id,
                    # Note: added more specificity here, previously was just going by member_id
                    reimbursement_wallet_id=wallet_id,
                )
                .one_or_none()
            )
        return member_health_plan

    def _get_employer_health_plan(
        self, member_id: int, wallet_id: int, effective_date: datetime.datetime
    ) -> Optional[EmployerHealthPlan]:
        health_plan_repo = HealthPlanRepository(db.session)
        return health_plan_repo.get_employer_plan_by_wallet_and_member_id(
            member_id=member_id, wallet_id=wallet_id, effective_date=effective_date
        )

    def cost_breakdown_data_service_from_treatment_procedure(
        self,
        cost: int,
        member_id: int,
        wallet: ReimbursementWallet,
        reimbursement_category: ReimbursementRequestCategory,
        procedure_type: TreatmentProcedureType,
        before_this_date: datetime.datetime,
        asof_date: datetime.datetime,
        service_start_date: Optional[datetime.date],
        global_procedure_id: Optional[str] = None,
        wallet_balance_override: Optional[int] = None,
        should_include_pending: Optional[bool] = False,
        tier: Optional[Tier] = None,
        fdc_hdhp_check: Optional[FdcHdhpCheckResults] = None,
        treatment_procedure_id: Optional[int] = None,
    ) -> CostBreakdownDataService:
        """
        Abbreviate the complicated construction of a CostBreakdownGenerator for treatment procedures.
        """
        return self.cost_breakdown_service_from_data(
            cost=cost,
            member_id=member_id,
            wallet=wallet,
            reimbursement_category=reimbursement_category,
            procedure_type=procedure_type,
            before_this_date=before_this_date,
            asof_date=asof_date,
            service_start_date=service_start_date,
            global_procedure_id=global_procedure_id,
            wallet_balance_override=wallet_balance_override,
            should_include_pending=should_include_pending,
            tier=tier,
            fdc_hdhp_check=fdc_hdhp_check,
            treatment_procedure_id=treatment_procedure_id,
        )

    def cost_breakdown_data_service_from_reimbursement_request(
        self,
        user_id: int,
        reimbursement_request: ReimbursementRequest,
        asof_date: datetime.datetime,
        cost_sharing_category: Optional[str] = None,
        global_procedure_id: Optional[str] = None,
        wallet_balance_override: Optional[int] = None,
        tier: Optional[Tier] = None,
    ) -> CostBreakdownDataService:
        """
        Abbreviate the complicated construction of a CostBreakdownGenerator for reimbursement requests.
        """
        is_valid_user = (
            self.session.query(ReimbursementWalletUsers.user_id)
            .filter(
                ReimbursementWalletUsers.user_id == user_id,
                ReimbursementWalletUsers.reimbursement_wallet_id
                == reimbursement_request.reimbursement_wallet_id,
            )
            .scalar()
        )
        if is_valid_user is None:
            log.error(
                "Reimbursement Request is not associated with the provided user's wallet",
                user_id=str(user_id),
                wallet_id=str(reimbursement_request.reimbursement_wallet_id),
                retrieved=is_valid_user,
            )
            raise errors.CostBreakdownInvalidInput(
                "This Reimbursement Request is not associated with the provided user's wallet. "
                "Missing a ReimbursementWalletUser association."
            )
        if not tier:
            if (
                feature_flags.str_variation(HEALTH_PLAN_YOY_FLAG, default=OLD_BEHAVIOR)
                != OLD_BEHAVIOR
            ):
                employer_health_plan = self._get_employer_health_plan(
                    member_id=user_id,
                    wallet_id=reimbursement_request.reimbursement_wallet_id,
                    effective_date=reimbursement_request.service_start_date,
                )
            else:
                member_health_plan = self._get_member_health_plan(
                    member_id=user_id,
                    wallet_id=reimbursement_request.reimbursement_wallet_id,
                    effective_date=reimbursement_request.service_start_date,
                )

                employer_health_plan = (
                    member_health_plan.employer_health_plan
                    if member_health_plan and member_health_plan.employer_health_plan
                    else None
                )
            if employer_health_plan and is_plan_tiered(ehp=employer_health_plan):
                tier = Tier.SECONDARY
            else:
                tier = None

        return self.cost_breakdown_service_from_data(
            cost=reimbursement_request.amount,
            member_id=user_id,
            wallet=reimbursement_request.wallet,
            reimbursement_category=reimbursement_request.category,
            procedure_type=TreatmentProcedureType(
                reimbursement_request.procedure_type
            ),  # type casting required due to the TreatmentProcedureType without the circular import hack
            before_this_date=datetime.datetime.now(tz=datetime.timezone.utc),
            asof_date=asof_date,
            service_start_date=reimbursement_request.service_start_date,
            cost_sharing_category=cost_sharing_category,
            global_procedure_id=global_procedure_id,
            wallet_balance_override=wallet_balance_override,
            tier=tier,
            reimbursement_request_id=reimbursement_request.id,
        )

    def cost_breakdown_service_from_data(
        self,
        cost: int,
        member_id: int,
        wallet: ReimbursementWallet,
        reimbursement_category: ReimbursementRequestCategory,
        procedure_type: TreatmentProcedureType,
        before_this_date: datetime.datetime,
        asof_date: datetime.datetime,
        service_start_date: Optional[datetime.date],
        cost_sharing_category: Optional[str] = None,
        global_procedure_id: Optional[str] = None,
        wallet_balance_override: Optional[int] = None,
        should_include_pending: Optional[bool] = False,
        tier: Optional[Tier] = None,
        fdc_hdhp_check: Optional[FdcHdhpCheckResults] = None,
        treatment_procedure_id: Optional[int] = None,
        reimbursement_request_id: Optional[int] = None,
    ) -> CostBreakdownDataService:
        """
        Validates and processes CostBreakdownDataService's required data and constructs the service from the results.
        Does not run Cost Breakdown logic.
        """
        enable_unlimited_benefits: bool = feature_flags.bool_variation(
            ENABLE_UNLIMITED_BENEFITS_FOR_CB, default=False
        )
        is_unlimited: bool = False

        if wallet_balance_override is not None:
            wallet_balance = wallet_balance_override
        else:
            if enable_unlimited_benefits:
                category_association = reimbursement_category.get_category_association(
                    reimbursement_wallet=wallet
                )
                wallet_service = ReimbursementWalletService()
                category_balance = wallet_service.get_wallet_category_balance(
                    wallet=wallet, category_association=category_association
                )
                wallet_balance = category_balance.current_balance
                is_unlimited = category_balance.is_unlimited
            else:
                wallet_balance = self._wallet_balance_from_wallet(
                    reimbursement_category.id, wallet
                )

        if self.extra_applied_amount and not is_unlimited:
            wallet_balance = max(
                0, wallet_balance - self.extra_applied_amount.wallet_balance_applied
            )
            log.info(
                "Applying an extra amount to the wallet balance",
                amount=self.extra_applied_amount.wallet_balance_applied,
            )
        elif self.extra_applied_amount and is_unlimited:
            log.info(
                "Extra amount applied to unlimited category balance",
                amount=self.extra_applied_amount.wallet_balance_applied,
                reimbursement_category_id=str(reimbursement_category.id),
                wallet_id=str(wallet.id),
            )

        member_health_plan = self._get_member_health_plan(
            member_id=member_id, wallet_id=wallet.id, effective_date=asof_date
        )
        self.calc_config.member_health_plan_id = (
            member_health_plan.id if member_health_plan else None
        )
        self.calc_config.tier = tier
        self.calc_config.reimbursement_organization_settings_id = (
            wallet.reimbursement_organization_settings_id
        )
        self.calc_config.health_plan_configuration.is_family_plan = (
            member_health_plan.is_family_plan if member_health_plan else "N/A"
        )
        self.calc_config.asof_date = asof_date.isoformat() if asof_date else None
        family_effective_date = None
        if (
            feature_flags.str_variation(HEALTH_PLAN_YOY_FLAG, default=OLD_BEHAVIOR)
            != OLD_BEHAVIOR
        ):
            if member_health_plan and member_health_plan.is_family_plan:
                family_effective_date = HealthPlanRepository(
                    session=self.session
                ).get_family_member_plan_effective_date(
                    subscriber_id=member_health_plan.subscriber_insurance_id,
                    effective_date=asof_date,
                )
        self.calc_config.family_asof_date = (
            family_effective_date.isoformat() if family_effective_date else None  # type: ignore[attr-defined]
        )

        patient_first_name, patient_last_name = get_member_first_and_last_name(
            member_health_plan=member_health_plan, user_id=member_id
        )
        if not patient_first_name or not patient_last_name:
            # TODO: Update monitor to expect more than just treatment procedure
            log.error(
                "Cost breakdown processor error: retrieving names for RTE",
                member_health_plan_id=member_health_plan.id,
                reimbursement_wallet_id=str(wallet.id),
            )
            raise errors.NoPatientNameFoundError("Missing patient name")

        if cost_sharing_category is None:
            if global_procedure_id is None:
                raise errors.NoCostSharingCategory(
                    "Must provide a Cost Sharing category or a Global Procedure id to calculate Cost Breakdown."
                )
            else:
                # http call to procedure service
                cost_sharing_category: CostSharingCategory = self.get_treatment_cost_sharing_category(  # type: ignore[no-redef] # Name "cost_sharing_category" already defined on line 380
                    global_procedure_id
                )

        sequential_deductible_accumulation_member_responsibilities = None
        sequential_hdhp_member_responsibilities = None
        alegeus_ytd_spend = 0
        rx_ytd_spend = None
        is_deductible_accumulation_enabled = (
            wallet.reimbursement_organization_settings.deductible_accumulation_enabled
        )
        self.calc_config.sequential_date = before_this_date.isoformat()

        # Health Profile validation
        if is_deductible_accumulation_enabled and member_health_plan is None:
            log.error(
                "No member health plan for deductible accumulation.",
            )
            stats.increment(
                metric_name=f"{METRIC_PREFIX}",
                pod_name=stats.PodNames.PAYMENTS_PLATFORM,
                tags=[
                    "success:false",
                    "reason:no_member_health_plan_deductible_accumulation",
                ],
            )
            raise errors.NoMemberHealthPlanError(
                "No member health plan provided for deductible accumulation."
            )

        is_hdhp = (
            member_health_plan.employer_health_plan.is_hdhp
            if member_health_plan
            else False
        )
        if CostBreakdownDataService.will_run_eligibility_info(
            is_deductible_accumulation_enabled, member_health_plan
        ):
            # note: deductible_accumulation and hdhp can exist together, but the accumulation flow takes priority
            if is_deductible_accumulation_enabled:
                sequential_deductible_accumulation_member_responsibilities = self.get_sequential_member_responsibility_for_deductible_accumulation(
                    member_health_plan=member_health_plan,
                    procedure_type=procedure_type,
                    before_this_date=before_this_date,
                    should_include_pending=should_include_pending,
                    family_effective_date=family_effective_date,
                )
                self.calc_config.sequential_deductible_accumulation_member_responsibility = (
                    sequential_deductible_accumulation_member_responsibilities
                )
            elif is_hdhp:
                sequential_hdhp_member_responsibilities = (
                    self.get_hdhp_non_alegeus_sequential_ytd_spend(
                        member_id=member_health_plan.member_id,
                        reimbursement_wallet_id=wallet.id,
                        before_this_date=before_this_date,
                        member_health_plan=member_health_plan,
                        should_include_pending=should_include_pending,
                        family_effective_date=family_effective_date,
                    )
                )
                self.calc_config.sequential_hdhp_member_responsibilities = (
                    sequential_hdhp_member_responsibilities
                )
                # http call to alegeus
                alegeus_ytd_spend = self.get_hdhp_alegeus_sequential_ytd_spend(
                    member_health_plan=member_health_plan
                )
                self.calc_config.alegeus_ytd_spend = alegeus_ytd_spend
            if (
                procedure_type == TreatmentProcedureType.PHARMACY
                and not CostBreakdownDataService.is_pharmacy_procedure_with_rx_integration(
                    procedure_type, member_health_plan
                )
            ):
                policy_id = self.rx_rte_processor.get_policy_id(member_health_plan)
                rx_ytd_spend = self.rx_rte_processor.ytd_info_from_spends(
                    policy_id=policy_id,
                    member_health_plan=member_health_plan,
                    member_first_name=patient_first_name,
                    member_last_name=patient_last_name,
                )
                self.calc_config.rx_ytd_spend = rx_ytd_spend  # type: ignore[assignment] # Incompatible types in assignment (expression has type "RxYTDInfo", variable has type "int")

        # These values should be passed from treatment procedure/reimbursement request
        # default to past logic, sending today's date if they're null
        if service_start_date is None:
            service_start_date = datetime.date.today()

        generator = CostBreakdownDataService(
            member_first_name=patient_first_name,
            member_last_name=patient_last_name,
            member_health_plan=member_health_plan,
            wallet_balance=wallet_balance,
            is_unlimited=is_unlimited,
            cost=cost,
            procedure_type=procedure_type,
            cost_sharing_category=cost_sharing_category,  # type: ignore[arg-type] # Argument "cost_sharing_category" to "CostBreakdownDataService" has incompatible type "Optional[str]"; expected "CostSharingCategory"
            deductible_accumulation_enabled=is_deductible_accumulation_enabled,
            sequential_deductible_accumulation_member_responsibilities=sequential_deductible_accumulation_member_responsibilities,
            sequential_hdhp_responsibilities=sequential_hdhp_member_responsibilities,
            alegeus_ytd_spend=alegeus_ytd_spend,
            rx_ytd_spend=rx_ytd_spend,
            tier=tier,
            fdc_hdhp_check=fdc_hdhp_check,
            service_start_date=service_start_date,
            treatment_procedure_id=treatment_procedure_id,
            reimbursement_request_id=reimbursement_request_id,
        )
        return generator

    def _store_cost_breakdown_to_db(
        self, cost_breakdown: CostBreakdown, wallet: ReimbursementWallet
    ) -> None:
        try:
            self.session.add(cost_breakdown)
            self.session.commit()
        except Exception as e:
            log.error(
                "Could not persist cost breakdown into database",
                wallet_id=wallet.id,
                error=e,
            )
            stats.increment(
                metric_name=f"{METRIC_PREFIX}",
                pod_name=stats.PodNames.PAYMENTS_PLATFORM,
                tags=["success:false", "reason:db_failure"],
            )
            raise e

    def get_treatment_cost_sharing_category(  # type: ignore[no-untyped-def] # Function is missing a type annotation for one or more arguments
        self,
        global_procedure_id,
    ) -> CostSharingCategory:
        procedure = self.procedure_service_client.get_procedure_by_id(
            procedure_id=global_procedure_id
        )
        if not procedure:
            log.error(
                "Unable to get global procedure from procedure service",
                global_procedure_id=global_procedure_id,
            )
            stats.increment(
                metric_name=f"{METRIC_PREFIX}",
                pod_name=stats.PodNames.PAYMENTS_PLATFORM,
                tags=["success:false", "reason:no_global_procedure_found"],
            )
            raise errors.NoGlobalProcedureFoundError(
                f"No global procedure found for global procedure id {global_procedure_id}"
            )

        cost_sharing_category = procedure["cost_sharing_category"].upper()
        if procedure["is_partial"] and len(procedure["parent_procedure_ids"]) > 0:
            parent = self.procedure_service_client.get_procedure_by_id(
                procedure_id=procedure["parent_procedure_ids"][0],
            )
            if parent:
                cost_sharing_category = parent["cost_sharing_category"].upper()

        if cost_sharing_category not in CostSharingCategory.__members__:
            raise errors.NoGlobalProcedureCostSharingCategoryFoundError(
                f"No global procedure cost sharing category found for global procedure id {global_procedure_id}"
            )
        return CostSharingCategory[cost_sharing_category]

    # Deductible Accumulation Sequential Payments
    def _get_all_sequential_reimbursement_request_data(
        self,
        member_health_plan: MemberHealthPlan,
        before_this_date: datetime.datetime,
        should_include_pending: Optional[bool] = False,
        family_effective_date: Optional[datetime.datetime] = None,
    ) -> List[Tuple[ReimbursementRequest, CostBreakdown]]:
        # Get all relevant past cost breakdowns.
        most_recent_cost_breakdowns = (
            self.session.query(func.max(CostBreakdown.id))
            .filter(
                CostBreakdown.wallet_id == member_health_plan.reimbursement_wallet_id,
                # Cost breakdown record is not None:
                CostBreakdown.reimbursement_request_id is not None,
            )
            .group_by(CostBreakdown.reimbursement_request_id)
            .all()
        )
        most_recent_cost_breakdown_ids = list(
            map(lambda row: row[0], most_recent_cost_breakdowns)
        )
        if not most_recent_cost_breakdown_ids:
            return []

        states = [
            ReimbursementRequestState.APPROVED,
            ReimbursementRequestState.REIMBURSED,
        ]
        if should_include_pending:
            states += [
                ReimbursementRequestState.NEW,
                ReimbursementRequestState.PENDING,
            ]
        base_query = (
            self.session.query(ReimbursementRequest, CostBreakdown)
            .join(
                CostBreakdown,
                ReimbursementRequest.id == CostBreakdown.reimbursement_request_id,
            )
            .join(
                AccumulationTreatmentMapping,
                ReimbursementRequest.id
                == AccumulationTreatmentMapping.reimbursement_request_id,
                isouter=True,  # left outer join means this query picks up mapped and unmapped procedures
            )
            .filter(
                # Using the most recent cost breakdown
                CostBreakdown.id.in_(most_recent_cost_breakdown_ids),
                # Match the right member health plan
                ReimbursementRequest.reimbursement_wallet_id
                == member_health_plan.reimbursement_wallet_id,
                or_(
                    # Normal RRs
                    ReimbursementRequest.state.in_(states),
                    # Member responsibility of 100% is also accumulated, but as DENIED.
                    # This is a pre-existing Care Advocate workflow based around what shouldn't be tracked in alegeus
                    and_(
                        ReimbursementRequest.state == ReimbursementRequestState.DENIED,
                        CostBreakdown.total_employer_responsibility == 0,
                        ReimbursementRequest.amount
                        == CostBreakdown.total_member_responsibility,
                    ),
                ),
                # Only Manual RRs
                ReimbursementRequest.reimbursement_type
                == ReimbursementRequestType.MANUAL,
                or_(
                    # reimbursements picked up by data sourcing but not sent yet, or sent but rejected
                    AccumulationTreatmentMapping.treatment_accumulation_status.in_(
                        [
                            TreatmentAccumulationStatus.PAID,
                            TreatmentAccumulationStatus.WAITING,
                            TreatmentAccumulationStatus.ROW_ERROR,
                            TreatmentAccumulationStatus.REJECTED,
                        ]
                    ),
                    # reimbursements not picked up by data sourcing
                    AccumulationTreatmentMapping.id.is_(None),
                ),
                CostBreakdown.created_at < before_this_date,
            )
        )

        # get reimbursements which should be considered in pricing, but have not been sent to insurance yet
        # These will show in pverify data after they have been sent to insurance
        sequential_reimbursement_requests = base_query.all()

        # Filter for the reimbursement requests that are within the member health plans start and end dates
        if (
            feature_flags.str_variation(HEALTH_PLAN_YOY_FLAG, default=OLD_BEHAVIOR)
            != OLD_BEHAVIOR
        ):
            effective_plan_start_date = (
                family_effective_date
                if family_effective_date
                else member_health_plan.plan_start_at
            )
            if (
                feature_flags.str_variation(HEALTH_PLAN_YOY_FLAG, default=OLD_BEHAVIOR)
                == NEW_BEHAVIOR
            ):
                plan_end_at = member_health_plan.plan_end_at
                if plan_end_at is not None:
                    base_query = base_query.filter(
                        ReimbursementRequest.service_start_date
                        >= effective_plan_start_date,
                        ReimbursementRequest.service_start_date
                        <= member_health_plan.plan_end_at,
                    )
                else:
                    base_query = base_query.filter(
                        ReimbursementRequest.service_start_date
                        >= effective_plan_start_date,
                    )

                sequential_reimbursement_requests = base_query.all()
            else:
                log.info(
                    "Member Health Plan Year Over Year Migration",
                    query="_get_all_sequential_reimbursement_request_data",
                    member_id=str(member_health_plan.member_id),
                    wallet_id=str(member_health_plan.reimbursement_wallet_id),
                    effective_date=effective_plan_start_date,
                )

        return sequential_reimbursement_requests

    def _get_ded_accumulation_sequential_treatment_procedure_data(
        self,
        member_health_plan: MemberHealthPlan,
        before_this_date: datetime.datetime,
        should_include_pending: Optional[bool] = False,
        family_effective_date: Optional[datetime.datetime] = None,
    ) -> List[Tuple[TreatmentProcedure, CostBreakdown]]:
        statuses = [
            TreatmentProcedureStatus.COMPLETED,
            TreatmentProcedureStatus.PARTIALLY_COMPLETED,
        ]
        if should_include_pending:
            statuses.append(TreatmentProcedureStatus.SCHEDULED)
        # Get all relevant past cost breakdowns.
        base_query = (
            self.session.query(TreatmentProcedure, CostBreakdown)
            .join(
                CostBreakdown, TreatmentProcedure.cost_breakdown_id == CostBreakdown.id
            )
            .join(
                AccumulationTreatmentMapping,
                TreatmentProcedure.uuid
                == AccumulationTreatmentMapping.treatment_procedure_uuid,
                isouter=True,  # left outer join means this query picks up mapped and unmapped procedures
            )
            .filter(
                # Match the right member health plan
                TreatmentProcedure.reimbursement_wallet_id
                == member_health_plan.reimbursement_wallet_id,
                # Anything except cancelled procedures
                TreatmentProcedure.status.in_(statuses),
                or_(
                    # procedures picked up by data sourcing but not sent yet, or sent but rejected
                    AccumulationTreatmentMapping.treatment_accumulation_status.in_(
                        [
                            TreatmentAccumulationStatus.PAID,
                            TreatmentAccumulationStatus.WAITING,
                            TreatmentAccumulationStatus.ROW_ERROR,
                            TreatmentAccumulationStatus.REJECTED,
                        ]
                    ),
                    # procedures not yet picked up by data sourcing
                    AccumulationTreatmentMapping.treatment_procedure_uuid.is_(None),
                ),
            )
        )

        if should_include_pending:
            base_query = base_query.filter(
                TreatmentProcedure.created_at < before_this_date,
            )
        else:
            base_query = base_query.filter(
                TreatmentProcedure.completed_date < before_this_date,
            )

        # used by admin recalculator tool to override existing cost breakdowns for sequential treatment procedures
        if (
            self.extra_applied_amount
            and self.extra_applied_amount.assumed_paid_procedures
        ):
            base_query = base_query.filter(
                TreatmentProcedure.id.notin_(
                    self.extra_applied_amount.assumed_paid_procedures
                ),
            )
        # These will show in pverify data after they have been sent to insurance
        sequential_treatment_procedures = base_query.all()

        # Filter for the treatment procedures that are within the member health plans start and end dates
        if (
            feature_flags.str_variation(HEALTH_PLAN_YOY_FLAG, default=OLD_BEHAVIOR)
            != OLD_BEHAVIOR
        ):
            effective_plan_start_date = (
                family_effective_date
                if family_effective_date
                else member_health_plan.plan_start_at
            )
            if (
                feature_flags.str_variation(HEALTH_PLAN_YOY_FLAG, default=OLD_BEHAVIOR)
                == NEW_BEHAVIOR
            ):
                plan_end_at = member_health_plan.plan_end_at
                if plan_end_at is not None:
                    base_query = base_query.filter(
                        TreatmentProcedure.start_date >= effective_plan_start_date,
                        TreatmentProcedure.start_date <= plan_end_at,
                    )
                else:
                    base_query = base_query.filter(
                        TreatmentProcedure.start_date >= effective_plan_start_date,
                    )
                sequential_treatment_procedures = base_query.all()
            else:
                log.info(
                    "Member Health Plan Year Over Year Migration",
                    query="_get_ded_accumulation_sequential_treatment_procedure_data",
                    member_id=str(member_health_plan.member_id),
                    wallet_id=str(member_health_plan.reimbursement_wallet_id),
                    effective_date=effective_plan_start_date,
                )

        return sequential_treatment_procedures

    def get_sequential_member_responsibility_for_deductible_accumulation(
        self,
        member_health_plan: MemberHealthPlan,
        procedure_type: TreatmentProcedureType,
        before_this_date: datetime.datetime,
        should_include_pending: Optional[bool] = False,
        family_effective_date: Optional[datetime.datetime] = None,
    ) -> DeductibleAccumulationYTDInfo:
        """
        For deductible accumulation treatment procedures and reimbursement requests,
        if multiple procedures are scheduled at the same time, the year to date spend amount comes from four sources:
        1. pverify medical plan year to date amount
        2. (Estimation only) all scheduled treatment procedures before the current treatment procedure
        3. Any New and Pending (Estimation only), Approved, or Reimbursed manual claims that have a cost breakdown but no accumulation
        4. All completed procedures before the current treatment procedure that are ready for accumulation
           but haven't been sent to a payer yet.
        """

        treatment_procedure_responsibilities = (
            self._get_ded_accumulation_sequential_treatment_procedure_data(
                member_health_plan=member_health_plan,
                before_this_date=before_this_date,
                should_include_pending=should_include_pending,
                family_effective_date=family_effective_date,
            )
        )

        reimbursement_request_responsibilities = (
            self._get_all_sequential_reimbursement_request_data(
                member_health_plan=member_health_plan,
                before_this_date=before_this_date,
                should_include_pending=should_include_pending,
                family_effective_date=family_effective_date,
            )
        )

        total_responsibilities = (
            treatment_procedure_responsibilities
            + reimbursement_request_responsibilities
        )

        # deductible and oop_applied should default to 0, not None, but they are nullable
        individual_deductibles_applied: int = 0
        individual_oops_applied: int = 0
        family_deductibles_applied: int = 0
        family_oops_applied: int = 0
        cost_breakdown_ids: [int] = []  # type: ignore[valid-type] # Bracketed expression "[...]" is not valid as a type

        applied_treatments: List[Union[TreatmentProcedure, ReimbursementRequest]] = []
        for (
            procedure,
            cost_breakdown,
        ) in total_responsibilities:
            if not member_health_plan.employer_health_plan.rx_integrated:
                # if rx not integrated, only collect all scheduled medical or pharmacy procedures
                if procedure.procedure_type != procedure_type:
                    continue
            applied_treatments.append(procedure)
            cost_breakdown_ids.append(cost_breakdown.id)

            if isinstance(procedure, TreatmentProcedure):
                member_id = procedure.member_id
            else:
                # TODO: when requests for dependents are handled differently, revise this logic
                if procedure.person_receiving_service_member_status == "MEMBER":
                    member_id = procedure.person_receiving_service_id
                else:
                    # If the procedure is not associated with a member, person_receiving_service_id is not a member_id.
                    member_id = None
            if member_id == member_health_plan.member_id:
                # All procedures for a wallet != all procedures for this individual
                individual_deductibles_applied += (
                    cost_breakdown.deductible
                    if cost_breakdown.deductible is not None
                    else 0
                )
                individual_oops_applied += (
                    cost_breakdown.oop_applied
                    if cost_breakdown.oop_applied is not None
                    else 0
                )

            family_deductibles_applied += (
                cost_breakdown.deductible
                if cost_breakdown.deductible is not None
                else 0
            )
            family_oops_applied += (
                cost_breakdown.oop_applied
                if cost_breakdown.oop_applied is not None
                else 0
            )

        if self.extra_applied_amount:
            log.info(
                "Applying an extra amount to oop.",
                oop=self.extra_applied_amount.oop_applied,
            )
            individual_deductibles_applied += self.extra_applied_amount.oop_applied
            individual_oops_applied += self.extra_applied_amount.oop_applied
            family_deductibles_applied += self.extra_applied_amount.oop_applied
            family_oops_applied += self.extra_applied_amount.oop_applied

        applied_info = DeductibleAccumulationYTDInfo(
            individual_deductible_applied=individual_deductibles_applied,
            individual_oop_applied=individual_oops_applied,
            family_deductible_applied=family_deductibles_applied,
            family_oop_applied=family_oops_applied,
        )
        log.info(
            "Applied sequential payments to deductible accumulation procedure (Reimbursement or Treatment) ",
            applied_treatments=[
                [procedure.id, procedure.uuid, procedure.cost]
                for procedure in applied_treatments
                if isinstance(procedure, TreatmentProcedure)
            ],
            applied_reimbursements=[
                [str(procedure.id), procedure.amount]
                for procedure in applied_treatments
                if isinstance(procedure, ReimbursementRequest)
            ],
            applied=applied_info,
        )
        self.calc_config.sequential_cost_breakdown_ids = cost_breakdown_ids
        self.calc_config.sequential_procedure_ids = [tp.id for tp in applied_treatments]
        return applied_info

    # HDHP Sequential Payments
    def get_hdhp_non_alegeus_sequential_ytd_spend(
        self,
        member_id: int,
        reimbursement_wallet_id: int,
        before_this_date: datetime.datetime,
        member_health_plan: MemberHealthPlan,
        should_include_pending: Optional[bool] = False,
        family_effective_date: Optional[datetime.datetime] = None,
    ) -> HDHPAccumulationYTDInfo:
        """
        For hdhp ytd spend, if multiple procedures are scheduled at the same time,
        the year to date spend amount comes from four sources:
        1. pverify medical plan year to date amount
        2. (Estimation only) all scheduled treatment procedures before the current procedure
        3. (Estimation only) all pending reimbursement requests with a cost breakdown before the current procedure
        4. alegeus hdhp plan applied amount (this includes completed procedures member spend)
        """
        if should_include_pending:
            treatment_procedures_responsibilities = (
                self._get_scheduled_treatment_procedures_for_hdhp(
                    reimbursement_wallet_id=reimbursement_wallet_id,
                    before_this_date=before_this_date,
                    member_health_plan=member_health_plan,
                    family_effective_date=family_effective_date,
                )
            )
        else:
            treatment_procedures_responsibilities = []

        reimbursement_request_responsibilities = (
            self._get_scheduled_reimbursement_requests_for_hdhp(
                reimbursement_wallet_id=reimbursement_wallet_id,
                before_this_date=before_this_date,
                member_health_plan=member_health_plan,
                should_include_pending=should_include_pending,
                family_effective_date=family_effective_date,
            )
        )

        combined_tp_rr_responsibility = (
            treatment_procedures_responsibilities
            + reimbursement_request_responsibilities
        )
        # sum responsibilities
        sequential_member_responsibilities = self._sum_hdhp_member_responsibilities(
            member_id=member_id,
            tp_member_responsibilities=treatment_procedures_responsibilities,
            rr_member_responsibilities=reimbursement_request_responsibilities,
        )
        sequential_family_responsibilities = sum(
            [
                c_b.total_member_responsibility
                for _, c_b in combined_tp_rr_responsibility
            ],
            start=0,
        )
        # TODO: Sum sequential responsibilities in admin using member/family split
        if self.extra_applied_amount:
            log.info(
                "Applying an extra amount to oop.",
                oop=self.extra_applied_amount.oop_applied,
            )
            sequential_member_responsibilities += self.extra_applied_amount.oop_applied
            sequential_family_responsibilities += self.extra_applied_amount.oop_applied

        # log data
        applied_treatment_procedure = [
            [t_p.id, t_p.uuid, t_p.cost, t_p.member_id]
            for t_p, _ in treatment_procedures_responsibilities
        ]
        applied_reimbursement_requests = [
            [str(rr.id), rr.amount, rr.person_receiving_service_id]
            for rr, _ in reimbursement_request_responsibilities
        ]
        log.info(
            "Applied sequential payments to hdhp treatment procedure",
            applied_treatment_procedure=applied_treatment_procedure,
            applied_reimbursement_requests=applied_reimbursement_requests,
            member_id=member_id,
            member_responsibilities=sequential_member_responsibilities,
            family_responsibilities=sequential_family_responsibilities,
        )
        self.calc_config.sequential_cost_breakdown_ids = [
            cb.id for _, cb in combined_tp_rr_responsibility
        ]
        self.calc_config.sequential_procedure_ids = [
            tp_rr.id for tp_rr, _ in combined_tp_rr_responsibility
        ]
        # return ytd data
        return HDHPAccumulationYTDInfo(
            sequential_member_responsibilities=sequential_member_responsibilities,
            sequential_family_responsibilities=sequential_family_responsibilities,
        )

    def _get_scheduled_treatment_procedures_for_hdhp(
        self,
        reimbursement_wallet_id: int,
        before_this_date: datetime.datetime,
        member_health_plan: MemberHealthPlan,
        family_effective_date: Optional[datetime.datetime] = None,
    ) -> List[Tuple[TreatmentProcedure, CostBreakdown]]:
        # get all the sequential treatment procedures
        scheduled_treatment_procedures_query = (
            self.session.query(TreatmentProcedure, CostBreakdown)
            .join(
                CostBreakdown, TreatmentProcedure.cost_breakdown_id == CostBreakdown.id
            )
            .filter(
                TreatmentProcedure.reimbursement_wallet_id == reimbursement_wallet_id,
                TreatmentProcedure.status == TreatmentProcedureStatus.SCHEDULED,
            )
        )
        scheduled_treatment_procedures_query = (
            scheduled_treatment_procedures_query.filter(
                TreatmentProcedure.created_at < before_this_date,
            )
        )

        # used by admin recalculator tool to override existing cost breakdowns for sequential treatment procedures
        if (
            self.extra_applied_amount
            and self.extra_applied_amount.assumed_paid_procedures
        ):
            scheduled_treatment_procedures_query = (
                scheduled_treatment_procedures_query.filter(
                    TreatmentProcedure.id.notin_(
                        self.extra_applied_amount.assumed_paid_procedures
                    ),
                )
            )

        # Filter for the treatment procedures that are within the member health plans start and end dates
        if (
            feature_flags.str_variation(HEALTH_PLAN_YOY_FLAG, default=OLD_BEHAVIOR)
            != OLD_BEHAVIOR
        ):
            effective_plan_start_date = (
                family_effective_date
                if family_effective_date
                else member_health_plan.plan_start_at
            )
            if (
                feature_flags.str_variation(HEALTH_PLAN_YOY_FLAG, default=OLD_BEHAVIOR)
                == NEW_BEHAVIOR
            ):
                plan_end_at = member_health_plan.plan_end_at
                if plan_end_at is not None:
                    scheduled_treatment_procedures_query = (
                        scheduled_treatment_procedures_query.filter(
                            TreatmentProcedure.start_date >= effective_plan_start_date,
                            TreatmentProcedure.start_date <= plan_end_at,
                        )
                    )
                else:
                    scheduled_treatment_procedures_query = (
                        scheduled_treatment_procedures_query.filter(
                            TreatmentProcedure.start_date >= effective_plan_start_date,
                        )
                    )
            else:
                log.info(
                    "Member Health Plan Year Over Year Migration",
                    query="_get_scheduled_treatment_procedures_for_hdhp",
                    member_id=str(member_health_plan.member_id),
                    wallet_id=str(member_health_plan.reimbursement_wallet_id),
                    effective_date=effective_plan_start_date,
                )

        return scheduled_treatment_procedures_query.all()

    def _get_scheduled_reimbursement_requests_for_hdhp(
        self,
        reimbursement_wallet_id: int,
        before_this_date: datetime.datetime,
        member_health_plan: MemberHealthPlan,
        should_include_pending: Optional[bool] = False,
        family_effective_date: Optional[datetime.datetime] = None,
    ) -> List[Tuple[ReimbursementRequest, CostBreakdown]]:
        if should_include_pending:
            reimbursement_request_query = (
                self.session.query(ReimbursementRequest, CostBreakdown)
                .join(
                    CostBreakdown,
                    CostBreakdown.reimbursement_request_id == ReimbursementRequest.id,
                )
                .filter(
                    ReimbursementRequest.reimbursement_wallet_id
                    == reimbursement_wallet_id,
                    ReimbursementRequest.reimbursement_type
                    == ReimbursementRequestType.MANUAL,
                    ReimbursementRequest.state.in_(
                        [
                            ReimbursementRequestState.NEW,
                            ReimbursementRequestState.PENDING,
                            # Approved/reimbursed request amounts are in wallet_balance
                            # Similarly to how HDHP only counts SCHEDULED treatment procedures
                            # ReimbursementRequestState.APPROVED,
                            # ReimbursementRequestState.REIMBURSED,
                        ]
                    ),
                )
            )
            # Note: this gets flaky about <= vs <
            reimbursement_request_query = reimbursement_request_query.filter(
                ReimbursementRequest.service_start_date < before_this_date,
            )
            # Filter for the reimbursement requests that are within the member health plans start and end dates
            if (
                feature_flags.str_variation(HEALTH_PLAN_YOY_FLAG, default=OLD_BEHAVIOR)
                != OLD_BEHAVIOR
            ):
                effective_plan_start_date = (
                    family_effective_date
                    if family_effective_date
                    else member_health_plan.plan_start_at
                )
                if (
                    feature_flags.str_variation(
                        HEALTH_PLAN_YOY_FLAG, default=OLD_BEHAVIOR
                    )
                    == NEW_BEHAVIOR
                ):
                    plan_end_at = member_health_plan.plan_end_at
                    if plan_end_at is not None:
                        reimbursement_request_query = (
                            reimbursement_request_query.filter(
                                ReimbursementRequest.service_start_date
                                >= effective_plan_start_date,
                                ReimbursementRequest.service_start_date
                                <= member_health_plan.plan_end_at,
                            )
                        )
                    else:
                        reimbursement_request_query = (
                            reimbursement_request_query.filter(
                                ReimbursementRequest.service_start_date
                                >= effective_plan_start_date,
                            )
                        )
                else:
                    log.info(
                        "Member Health Plan Year Over Year Migration",
                        query="_get_scheduled_reimbursement_requests_for_hdhp",
                        member_id=str(member_health_plan.member_id),
                        wallet_id=str(member_health_plan.reimbursement_wallet_id),
                        effective_date=effective_plan_start_date,
                    )
            return reimbursement_request_query.all()
        else:
            return []

    def _sum_hdhp_member_responsibilities(
        self,
        member_id: int,
        tp_member_responsibilities: List[Tuple[TreatmentProcedure, CostBreakdown]],
        rr_member_responsibilities: List[Tuple[ReimbursementRequest, CostBreakdown]],
    ) -> int:
        tp_sequential_member_responsibilities = sum(
            [
                c_b.total_member_responsibility
                for t_p, c_b in tp_member_responsibilities
                if t_p.member_id == member_id
            ],
            start=0,
        )
        rr_sequential_member_responsibilities = sum(
            [
                c_b.total_member_responsibility
                for r_r, c_b in rr_member_responsibilities
                if r_r.person_receiving_service_id == member_id
                # Because non-members can also be recorded in person_receiving_service_id
                and r_r.person_receiving_service_member_status == "MEMBER"
            ],
            start=0,
        )
        return (
            tp_sequential_member_responsibilities
            + rr_sequential_member_responsibilities
        )

    def get_hdhp_alegeus_sequential_ytd_spend(
        self, member_health_plan: MemberHealthPlan
    ) -> int:
        try:
            alegeus_ytd_spend: Optional[int] = get_alegeus_hdhp_plan_year_to_date_spend(
                member_health_plan.reimbursement_wallet
            )
            if alegeus_ytd_spend is None:
                alegeus_ytd_spend = 0
        except Exception as e:
            log.error(
                "failed to retrieve ytd spend from alegeus",
                error=str(e),
                wallet_id=member_health_plan.reimbursement_wallet_id,
            )
            raise e
        return alegeus_ytd_spend
