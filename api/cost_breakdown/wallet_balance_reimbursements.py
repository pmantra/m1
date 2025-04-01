from __future__ import annotations

from datetime import date, datetime
from traceback import format_exc
from typing import List, Optional, Tuple

from maven import feature_flags
from sqlalchemy.orm import joinedload

from authn.models.user import User
from common import stats
from common.global_procedures.procedure import ProcedureService
from cost_breakdown.constants import ClaimType
from cost_breakdown.errors import (
    InvalidDirectPaymentClaimCreationRequestException,
    WalletBalanceReimbursementsException,
)
from cost_breakdown.models.cost_breakdown import (
    CostBreakdown,
    ReimbursementRequestToCostBreakdown,
)
from direct_payment.clinic.models.clinic import FertilityClinic
from direct_payment.treatment_procedure.models.treatment_procedure import (
    TreatmentProcedure,
    TreatmentProcedureStatus,
)
from storage.connection import db
from utils.log import logger
from wallet.models.constants import (
    BenefitTypes,
    ReimbursementRequestState,
    ReimbursementRequestType,
)
from wallet.models.currency import Money
from wallet.models.reimbursement import (
    ReimbursementOrgSettingCategoryAssociation,
    ReimbursementRequest,
)
from wallet.models.reimbursement_wallet import MemberHealthPlan, ReimbursementWallet
from wallet.models.reimbursement_wallet_credit import ReimbursementCycleCredits
from wallet.repository.health_plan import (
    HEALTH_PLAN_YOY_FLAG,
    OLD_BEHAVIOR,
    HealthPlanRepository,
)
from wallet.services.currency import DEFAULT_CURRENCY_CODE, CurrencyService
from wallet.utils.alegeus.claims.create import (
    VALID_REIMBURSEMENT_REQUEST_STATES_BY_CLAIM_TYPE,
    create_direct_payment_claim_in_alegeus,
)
from wallet.utils.common import create_refund_reimbursement_request

log = logger(__name__)


def incr_metric(method_name, pod_name, tags):  # type: ignore[no-untyped-def] # Function is missing a type annotation
    stats.increment(
        metric_name=f"api.cost_breakdown.tasks.calculate_cost_breakdown.{method_name}",
        pod_name=pod_name,
        tags=tags,
    )


def deduct_balance(
    treatment_procedure: TreatmentProcedure,
    cost_breakdown: CostBreakdown,
    wallet: ReimbursementWallet,
    procedure_service_client: ProcedureService = None,  # type: ignore[assignment] # Incompatible default for argument "procedure_service_client" (default has type "None", argument has type "ProcedureService")
) -> bool:
    log.info(
        "Start deduct_balance",
        cost_breakdown_id=cost_breakdown.id,
        treatment_procedure_id=treatment_procedure.id,
        treatment_procedure_status=treatment_procedure.status,
        reimbursement_wallet_id=wallet.id,
    )

    if treatment_procedure.status in [
        TreatmentProcedureStatus.COMPLETED,
        TreatmentProcedureStatus.PARTIALLY_COMPLETED,
    ]:
        clinic = FertilityClinic.query.get(treatment_procedure.fertility_clinic_id)
        if not clinic:
            # TODO: should this be an alert?
            log.error(
                "Could not find fertility clinic",
                fertility_clinic_id=treatment_procedure.fertility_clinic_id,
            )
            return False

        member = User.query.get(treatment_procedure.member_id)
        if not member:
            # TODO: should this be an alert?
            log.error("Could not find member", member_id=treatment_procedure.member_id)
            return False

        # If there exists a cost breakdown calculation which triggered creation of direct
        # payment reimbursement request, we want the get the difference between the
        # current and the previous cost breakdown to create new reimbursement requests
        previous_cost_breakdown_with_reimbursement_requests: Optional[CostBreakdown]
        has_previous_employee_deductible: bool
        (
            previous_cost_breakdown_with_reimbursement_requests,
            has_previous_employee_deductible,
        ) = _get_previous_cost_breakdown_with_reimbursement_requests(
            cost_breakdown.treatment_procedure_uuid
        )

        employee_reimbursement_request = _create_employee_reimbursement_request(
            treatment_procedure=treatment_procedure,
            wallet=wallet,
            clinic=clinic,
            member=member,
            cost_breakdown=cost_breakdown,
            previous_cost_breakdown_with_reimbursement_requests=previous_cost_breakdown_with_reimbursement_requests,
            has_previous_employee_deductible=has_previous_employee_deductible,
        )

        employer_reimbursement_request = _create_employer_reimbursement_request(
            treatment_procedure=treatment_procedure,
            wallet=wallet,
            clinic=clinic,
            member=member,
            cost_breakdown=cost_breakdown,
            previous_cost_breakdown_with_reimbursement_requests=previous_cost_breakdown_with_reimbursement_requests,
        )

        # Save Reimbursement Requests first
        requests_to_save = []
        if employer_reimbursement_request is not None:
            requests_to_save.append(
                (employer_reimbursement_request, ClaimType.EMPLOYER)
            )
        if employee_reimbursement_request is not None:
            requests_to_save.append(
                (employee_reimbursement_request, ClaimType.EMPLOYEE_DEDUCTIBLE)
            )
        if len(requests_to_save) > 0:
            _save_reimbursement_request(
                treatment_procedure, cost_breakdown, requests_to_save
            )

        # Submit either or both claims
        for reimbursement_request, claim_type in requests_to_save:
            if reimbursement_request.amount < 0:
                # TODO: PAY-5443 - add a way to top up Alegeus accounts when rolling back an incorrect charge
                # NOTE: This log has a monitor attached. Do not adjust the message without updating the monitor.
                log.error(
                    "Reimbursement Claims with negative amounts cannot be submitted to Alegeus.",
                    cost_breakdown_id=cost_breakdown.id,
                    reimbursement_request_id=reimbursement_request.id,
                    amount=reimbursement_request.amount,
                )
            else:
                _create_direct_payment_claim(
                    treatment_procedure.id,
                    cost_breakdown.id,
                    wallet,
                    reimbursement_request,
                    claim_type,
                )

        if _should_deduct_credits(
            cost_breakdown=cost_breakdown,
            previous_cost_breakdown_with_reimbursement_requests=previous_cost_breakdown_with_reimbursement_requests,
            wallet=wallet,
            treatment_procedure=treatment_procedure,
        ):
            procedure_service_client = procedure_service_client or ProcedureService()
            global_procedure = procedure_service_client.get_procedure_by_id(
                procedure_id=treatment_procedure.global_procedure_id,
            )
            if not global_procedure:
                log.error(
                    "Could not find reimbursement wallet global procedure",
                    treatment_procedure_id=treatment_procedure.id,
                    global_procedure_id=treatment_procedure.global_procedure_id,
                )
                return False

            if treatment_procedure.cost_credit is None:
                log.error(
                    "Treatment procedure has no cost credit",
                    treatment_procedure_id=treatment_procedure.id,
                )
                return False

            reimbursement_credits = _get_reimbursement_credits(
                wallet=wallet, treatment_procedure=treatment_procedure
            )
            if not reimbursement_credits:
                log.error(
                    "No reimbursement credit found for this cycle based wallet",
                    treatment_procedure_id=treatment_procedure.id,
                    reimbursement_request_category_id=treatment_procedure.reimbursement_request_category_id,
                )
                return False
            reimbursement_credits.deduct_credits_for_reimbursement_and_procedure(
                reimbursement_request=employer_reimbursement_request,
                global_procedure=global_procedure,  # type: ignore[arg-type] # incompatible type "Union[GlobalProcedure, PartialProcedure]"; expected "GlobalProcedure"
                treatment_procedure_cost=treatment_procedure.cost_credit,
            )

    return True


def add_back_balance(treatment_procedure: TreatmentProcedure) -> None:
    """
    Function to revert deduct balance, this will fully revert all reimbursement requests,
    reimbursement claims wallet credits if cycled based and send refund claims to Alegeus,
    then store .
    """
    log.info(
        "Start add back wallet balance",
        treatment_procedure_id=treatment_procedure.id,
        treatment_procedure_status=treatment_procedure.status,
        reimbursement_wallet_id=treatment_procedure.reimbursement_wallet_id,
        member_id=treatment_procedure.member_id,
    )
    if treatment_procedure.status not in {
        TreatmentProcedureStatus.COMPLETED,
        TreatmentProcedureStatus.PARTIALLY_COMPLETED,
    }:
        raise WalletBalanceReimbursementsException(
            "Treatment procedure is not in completed or partially completed status"
        )

    if not treatment_procedure.cost_breakdown_id:
        raise WalletBalanceReimbursementsException(
            "No cost breakdown result for this treatment procedure"
        )

    rr_to_cbs = (
        db.session.query(
            ReimbursementRequestToCostBreakdown,
        )
        .filter(
            ReimbursementRequestToCostBreakdown.treatment_procedure_uuid
            == treatment_procedure.uuid,
            ReimbursementRequestToCostBreakdown.cost_breakdown_id
            == treatment_procedure.cost_breakdown_id,
        )
        .options(joinedload(ReimbursementRequestToCostBreakdown.reimbursement_request))
        .all()
    )

    reversed_reimbursement_requests = []
    employer_reimbursement_request = None
    for rr_to_cb in rr_to_cbs:
        rr = rr_to_cb.reimbursement_request
        if rr.amount < 0:
            raise WalletBalanceReimbursementsException(
                "Reimbursement request has already been refunded"
            )
        if rr_to_cb.claim_type == ClaimType.EMPLOYER:
            employer_reimbursement_request = rr
        log.info(
            "Creating reverse reimbursement request",
            reversed_reimbursement_request_id=rr.id,
            reversed_rr_to_cb_id=rr_to_cb.id,
            claim_type=rr_to_cb.claim_type,
        )
        reversed_reimbursement_request = create_refund_reimbursement_request(
            original_request=rr, refund_amount=rr.amount
        )
        reversed_reimbursement_requests.append(
            (reversed_reimbursement_request, rr_to_cb.claim_type)
        )
        db.session.add(reversed_reimbursement_request)
        db.session.commit()
        reversed_rr_to_cb = _create_reversed_cost_breakdown_to_reimbursement_request(
            rr_to_cb=rr_to_cb,
            reversed_reimbursement_request=reversed_reimbursement_request,
        )
        db.session.add(reversed_rr_to_cb)
        db.session.commit()

    wallet = ReimbursementWallet.query.get(treatment_procedure.reimbursement_wallet_id)
    for reversed_reimbursement_request, claim_type in reversed_reimbursement_requests:
        _create_direct_payment_claim(
            treatment_procedure_id=treatment_procedure.id,
            cost_breakdown_id=treatment_procedure.cost_breakdown_id,
            wallet=wallet,
            reimbursement_request=reversed_reimbursement_request,
            claim_type=claim_type,
        )

    benefit_type = wallet.category_benefit_type(
        request_category_id=treatment_procedure.reimbursement_request_category_id
    )
    if benefit_type == BenefitTypes.CYCLE and employer_reimbursement_request:
        reimbursement_credits = _get_reimbursement_credits(
            wallet=wallet, treatment_procedure=treatment_procedure
        )
        reimbursement_credits.add_back_credits_for_reimbursement_and_procedure(
            employer_reimbursement_request
        )
    log.info(
        "Successfully add back wallet balance",
        treatment_procedure_id=treatment_procedure.id,
        treatment_procedure_status=treatment_procedure.status,
        reimbursement_wallet_id=treatment_procedure.reimbursement_wallet_id,
        member_id=treatment_procedure.member_id,
    )


def _create_reversed_cost_breakdown_to_reimbursement_request(
    rr_to_cb: ReimbursementRequestToCostBreakdown,
    reversed_reimbursement_request: ReimbursementRequest,
) -> ReimbursementRequestToCostBreakdown:
    data = {
        c.name: getattr(rr_to_cb, c.name)
        for c in ReimbursementRequestToCostBreakdown.__table__.columns
    }
    data.pop("id", None)
    data.pop("created_at", None)
    data.pop("modified_at", None)
    data["reimbursement_request_id"] = reversed_reimbursement_request.id
    return ReimbursementRequestToCostBreakdown(**data)


def _should_deduct_credits(  # type: ignore[no-untyped-def] # Function is missing a return type annotation
    cost_breakdown: CostBreakdown,
    previous_cost_breakdown_with_reimbursement_requests: Optional[CostBreakdown],
    wallet: ReimbursementWallet,
    treatment_procedure: TreatmentProcedure,
):
    result = False
    if (
        # Deduct full credit cost (or all remaining credits) if employer responsibility > 0.
        cost_breakdown.total_employer_responsibility != 0
        # No need to deduct credits if there's zero credit cost
        and treatment_procedure.cost_credit != 0
        # No need to deduct credits if there are previous cost breakdown calculations, since
        # the treatment_procedure.cost_credit is not changed.
        and previous_cost_breakdown_with_reimbursement_requests is None
    ):
        benefit_type = wallet.category_benefit_type(
            request_category_id=treatment_procedure.reimbursement_request_category_id
        )
        if benefit_type == BenefitTypes.CYCLE:
            # and also credits are only valid for cycle benefits

            result = True
    log.info(
        "Should deduct credits for procedure",
        result=result,
        cost_breakdown_id=str(cost_breakdown.id),
        treatment_procedure_id=str(treatment_procedure.id),
    )
    return result


def _create_employee_reimbursement_request(
    treatment_procedure: TreatmentProcedure,
    wallet: ReimbursementWallet,
    clinic: FertilityClinic,
    member: User,
    cost_breakdown: CostBreakdown,
    previous_cost_breakdown_with_reimbursement_requests: Optional[CostBreakdown],
    has_previous_employee_deductible: bool,
) -> Optional[ReimbursementRequest]:
    previous_deductible = 0
    claim_amount = None
    if (
        previous_cost_breakdown_with_reimbursement_requests is not None
        and has_previous_employee_deductible
    ):
        previous_deductible = (
            previous_cost_breakdown_with_reimbursement_requests.deductible
        )

    if should_submit_a_deductible_claim(
        user_id=treatment_procedure.member_id,
        wallet=wallet,
        effective_date=datetime.fromordinal(treatment_procedure.start_date.toordinal())
        if treatment_procedure.start_date
        else None,  # convert treatment procedure date to datetime
    ):
        # Determine claim amount:
        if should_submit_this_deductible_claim(cost_breakdown.deductible):
            claim_amount = cost_breakdown.deductible - previous_deductible
        elif previous_deductible != 0:
            # When we should not submit a deductible claim now, but we did it before, we
            # need to create a reimbursement request with the amount -previous_deductible
            # to offset the effect of the previous cost breakdown
            claim_amount = -previous_deductible

        if claim_amount is not None:
            employee_reimbursement_request = (
                _generate_direct_billing_reimbursement_request(
                    treatment_procedure,
                    clinic,
                    member,
                    wallet,
                    claim_amount,
                    ReimbursementRequestState.DENIED,
                )
            )
            return employee_reimbursement_request
    return None


def _create_employer_reimbursement_request(
    treatment_procedure: TreatmentProcedure,
    wallet: ReimbursementWallet,
    clinic: FertilityClinic,
    member: User,
    cost_breakdown: CostBreakdown,
    previous_cost_breakdown_with_reimbursement_requests: Optional[CostBreakdown],
) -> Optional[ReimbursementRequest]:
    # Note: Reimbursement request will always be in currency
    total_employer_responsibility = cost_breakdown.total_employer_responsibility - (
        cost_breakdown.hra_applied or 0
    )
    if previous_cost_breakdown_with_reimbursement_requests is not None:
        previous_employer_responsibility = (
            previous_cost_breakdown_with_reimbursement_requests.total_employer_responsibility
            - (previous_cost_breakdown_with_reimbursement_requests.hra_applied or 0)
        )
        total_employer_responsibility = (
            total_employer_responsibility - previous_employer_responsibility
        )
    if total_employer_responsibility != 0:
        return _generate_direct_billing_reimbursement_request(
            treatment_procedure,
            clinic,
            member,
            wallet,
            total_employer_responsibility,
            ReimbursementRequestState.APPROVED,
        )
    return None


def _generate_direct_billing_reimbursement_request(
    treatment_procedure: TreatmentProcedure,
    clinic: FertilityClinic,
    member: User,
    wallet: ReimbursementWallet,
    amount: int,
    state: ReimbursementRequestState,
) -> ReimbursementRequest:
    reimbursement_request = ReimbursementRequest(
        label=treatment_procedure.procedure_name,
        service_provider=clinic.name,
        person_receiving_service=member.full_name,
        person_receiving_service_id=member.id,
        amount=amount,
        category=treatment_procedure.reimbursement_request_category,
        wallet=wallet,
        service_start_date=datetime.combine(
            treatment_procedure.start_date, datetime.min.time()  # type: ignore[arg-type] # Argument 1 to "combine" of "datetime" has incompatible type "Optional[date]"; expected "date"
        ),
        service_end_date=(
            datetime.combine(treatment_procedure.end_date, datetime.min.time())
            if treatment_procedure.end_date
            else None
        ),
        reimbursement_type=ReimbursementRequestType.DIRECT_BILLING,
        state=state,
    )
    currency_service = CurrencyService()
    transaction: Money = currency_service.to_money(
        amount=amount, currency_code=DEFAULT_CURRENCY_CODE
    )
    currency_service.process_reimbursement_request(
        transaction=transaction, request=reimbursement_request
    )
    return reimbursement_request


def _save_reimbursement_request(  # type: ignore[no-untyped-def] # Function is missing a return type annotation
    treatment_procedure: TreatmentProcedure,
    cost_breakdown: CostBreakdown,
    reimbursement_requests: List[Tuple[ReimbursementRequest, ClaimType]],
):
    reimbursement_request_list: List[ReimbursementRequest] = [
        reimbursement_request for (reimbursement_request, _) in reimbursement_requests
    ]
    try:
        db.session.add_all(reimbursement_request_list)

        log.info(
            "Reimbursement request created for treatment procedure",
            treatment_procedure_id=str(treatment_procedure.id),
            cost_breakdown_id=str(cost_breakdown.id),
            reimbursement_request_ids=[
                reimbursement_request.id
                for reimbursement_request in reimbursement_request_list
            ],
        )

        # flush() is needed so all reimbursement requests created is not in the pending state.
        # If we don't call flush(), inserting reimbursement_request_to_cost_breakdown_record below will fail
        # because of the IntegrityError from the foreign key "reimbursement_request_to_cost_breakdown_ibfk_2"
        db.session.flush(reimbursement_request_list)

        for reimbursement_request, claim_type in reimbursement_requests:
            reimbursement_request_to_cost_breakdown_record = (
                ReimbursementRequestToCostBreakdown(
                    claim_type=claim_type,
                    treatment_procedure_uuid=cost_breakdown.treatment_procedure_uuid,
                    reimbursement_request_id=reimbursement_request.id,
                    cost_breakdown_id=cost_breakdown.id,
                )
            )
            db.session.add(reimbursement_request_to_cost_breakdown_record)

            log.info(
                "Reimbursement request to cost breakdown created for treatment procedure",
                claim_type=claim_type.name,
                treatment_procedure_id=str(treatment_procedure.id),
                cost_breakdown_id=str(cost_breakdown.id),
                reimbursement_request_id=str(reimbursement_request.id),
            )

        db.session.commit()

        incr_metric("deduct_balance", stats.PodNames.BENEFITS_EXP, ["success:true"])
    except Exception as e:
        log.error(
            "Reimbursement request creation for treatment procedure failed",
            treatment_procedure_id=str(treatment_procedure.id),
            cost_breakdown_id=str(cost_breakdown.id),
            reimbursement_request_ids=[
                reimbursement_request.id
                for reimbursement_request in reimbursement_request_list
            ],
            error_msg=str(e),
            error_type=e.__class__.__name__,
        )
        db.session.rollback()
        incr_metric(
            "deduct_balance",
            stats.PodNames.BENEFITS_EXP,
            [
                "success:false",
                "reason:create_reimbursement_request",
            ],
        )
        raise e


def should_submit_a_deductible_claim(
    user_id: int | None,
    wallet: ReimbursementWallet,
    effective_date: datetime | date | None,
) -> bool:
    if wallet.reimbursement_organization_settings.deductible_accumulation_enabled:
        return False

    if user_id is None or effective_date is None:
        log.error(
            "Invalid request for a health plan when attempting to submit a deductible claim.",
            user_id=user_id,
            wallet=wallet,
            effective_date=effective_date,
        )
        return False

    if (
        feature_flags.str_variation(HEALTH_PLAN_YOY_FLAG, default=OLD_BEHAVIOR)
        != OLD_BEHAVIOR
    ):
        health_plan_repo = HealthPlanRepository(db.session)
        employer_health_plan = (
            health_plan_repo.get_employer_plan_by_wallet_and_member_id(
                member_id=user_id, wallet_id=wallet.id, effective_date=effective_date
            )
        )
        return bool(employer_health_plan and employer_health_plan.is_hdhp)
    else:
        member_health_plan = MemberHealthPlan.query.filter_by(
            member_id=user_id,
            reimbursement_wallet_id=wallet.id,
        ).one_or_none()
        return member_health_plan and member_health_plan.employer_health_plan.is_hdhp


def should_submit_this_deductible_claim(deductible: int) -> bool:
    return deductible is not None and deductible > 0


def _create_direct_payment_claim(  # type: ignore[no-untyped-def] # Function is missing a return type annotation
    treatment_procedure_id: int,
    cost_breakdown_id: int,
    wallet: ReimbursementWallet,
    reimbursement_request: ReimbursementRequest,
    claim_type: ClaimType,
):
    try:
        if (
            reimbursement_request.state
            not in VALID_REIMBURSEMENT_REQUEST_STATES_BY_CLAIM_TYPE.get(claim_type, [])
            or reimbursement_request.reimbursement_type
            != ReimbursementRequestType.DIRECT_BILLING
        ):
            error_message = (
                f"The reimbursement request (id:{reimbursement_request.id}, "
                f"state:{reimbursement_request.state}, "
                f"claim_type:{claim_type.name} "
                f"type:{reimbursement_request.reimbursement_type}) is invalid for direct payment claim"
            )
            raise InvalidDirectPaymentClaimCreationRequestException(error_message)

        create_direct_payment_claim_in_alegeus(
            wallet, reimbursement_request, claim_type
        )

        log.info(
            "Successfully send direct payment claims to Alegeus",
            treatment_procedure_id=str(treatment_procedure_id),
            cost_breakdown_id=str(cost_breakdown_id),
            wallet_id=str(wallet.id),
            claim_type=claim_type.name,
            reimbursement_request=str(reimbursement_request.id),
        )
    # Handle the exception without rethrowing it, since the source of truth of direct
    # payment claims is in Maven DB.
    except Exception as e:
        # Note: this log is used for alerting. If you change the log message, update the monitor.
        log.exception(
            "Error creating direct payment claim.",
            error=str(e),
            error_type=type(e).__name__,
            error_details=format_exc(),
            treatment_procedure_id=str(treatment_procedure_id),
            cost_breakdown_id=str(cost_breakdown_id),
            wallet_id=str(wallet.id),
            claim_type=claim_type.name,
            reimbursement_request=str(reimbursement_request.id),
        )


def _get_previous_cost_breakdown_with_reimbursement_requests(
    treatment_procedure_uuid: Optional[str],
) -> Tuple[Optional[CostBreakdown], bool]:
    if treatment_procedure_uuid is None:
        return None, False

    try:
        query_records = (
            db.session.query(ReimbursementRequestToCostBreakdown, CostBreakdown)
            .join(
                CostBreakdown,
                ReimbursementRequestToCostBreakdown.cost_breakdown_id
                == CostBreakdown.id,
            )
            .filter(
                ReimbursementRequestToCostBreakdown.treatment_procedure_uuid
                == treatment_procedure_uuid
            )
            .order_by(CostBreakdown.id.desc())
            .all()
        )

        if len(query_records) == 0:
            return None, False

        reimbursement_request_to_cost_breakdown_records: List[
            ReimbursementRequestToCostBreakdown
        ]
        cost_breakdown_records: List[CostBreakdown]
        reimbursement_request_to_cost_breakdown_records, cost_breakdown_records = list(  # type: ignore[assignment] # Incompatible types in assignment (expression has type "Tuple[Any, ...]", variable has type "List[ReimbursementRequestToCostBreakdown]") #type: ignore[assignment] # Incompatible types in assignment (expression has type "Tuple[Any, ...]", variable has type "List[CostBreakdown]")
            zip(*[(record[0], record[1]) for record in query_records])
        )

        previous_cost_breakdown_id = cost_breakdown_records[0].id

        employee_deductible_from_previous_cost_breakdown = list(
            filter(
                lambda x: x.cost_breakdown_id == previous_cost_breakdown_id
                and x.claim_type == ClaimType.EMPLOYEE_DEDUCTIBLE,
                reimbursement_request_to_cost_breakdown_records,
            )
        )

        return (
            cost_breakdown_records[0],
            len(employee_deductible_from_previous_cost_breakdown) != 0,
        )
    except Exception as e:
        log.error(
            "Error in _get_previous_cost_breakdown_with_reimbursement_requests",
            treatment_procedure_uuid=treatment_procedure_uuid,
            error_type=e.__class__.__name__,
            error_message=str(e),
        )
        return None, False


def _get_reimbursement_credits(
    treatment_procedure: TreatmentProcedure, wallet: ReimbursementWallet
) -> ReimbursementCycleCredits:
    reimbursement_credits = (
        ReimbursementCycleCredits.query.join(
            ReimbursementOrgSettingCategoryAssociation,
            ReimbursementOrgSettingCategoryAssociation.id
            == ReimbursementCycleCredits.reimbursement_organization_settings_allowed_category_id,
        )
        .filter(
            ReimbursementCycleCredits.reimbursement_wallet_id == wallet.id,
            ReimbursementOrgSettingCategoryAssociation.reimbursement_request_category_id
            == treatment_procedure.reimbursement_request_category_id,
        )
        .first()
    )
    return reimbursement_credits
