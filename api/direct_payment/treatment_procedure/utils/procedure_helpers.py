from __future__ import annotations

from collections import defaultdict
from datetime import date, datetime, timedelta
from typing import Collection, Iterable, List, Mapping, Optional

from flask import request
from flask_restful import abort
from marshmallow import ValidationError
from maven import feature_flags
from pytz import timezone
from rq.job import Dependency, Job
from sqlalchemy.orm.exc import MultipleResultsFound

from authn.models.user import User
from common import stats
from common.global_procedures.procedure import GlobalProcedure, ProcedureService
from cost_breakdown.tasks.calculate_cost_breakdown import (
    calculate_cost_breakdown,
    calculate_cost_breakdown_async,
)
from cost_breakdown.utils.helpers import get_scheduled_tp_and_pending_rr_costs
from direct_payment.billing.tasks.rq_job_create_bill import (
    create_and_process_member_refund_bills,
)
from direct_payment.clinic.constants import PROCEDURE_BACKDATE_LIMIT_DAYS
from direct_payment.clinic.models.clinic import FertilityClinic
from direct_payment.clinic.models.fee_schedule import FeeScheduleGlobalProcedures
from direct_payment.clinic.models.user import FertilityClinicUserProfile
from direct_payment.clinic.utils.aggregate_procedures_utils import (
    get_benefit_e9y_start_and_expiration_date,
)
from direct_payment.treatment_procedure.constant import (
    ENABLE_UNLIMITED_BENEFITS_FOR_TP_VALIDATION,
)
from direct_payment.treatment_procedure.models.treatment_procedure import (
    TreatmentProcedure,
    TreatmentProcedureStatus,
)
from direct_payment.treatment_procedure.repository import treatment_procedure
from utils.cache import redis_client
from utils.log import logger
from wallet.models.constants import (
    BenefitTypes,
    FertilityProgramTypes,
    PatientInfertilityDiagnosis,
    WalletDirectPaymentState,
    WalletState,
    WalletUserStatus,
)
from wallet.models.models import CategoryBalance
from wallet.models.reimbursement_wallet import ReimbursementWallet
from wallet.models.reimbursement_wallet_user import ReimbursementWalletUsers
from wallet.services.reimbursement_wallet import ReimbursementWalletService

log = logger(__name__)
metric_prefix = "api.direct_payment.treatment_procedure.utils.procedure_helpers"


def validate_procedures(
    treatment_procedures_args: List[dict],
    headers: Mapping[str, str] = None,  # type: ignore[assignment] # Incompatible default for argument "headers" (default has type "None", argument has type "Mapping[str, str]")
) -> None:
    if len(treatment_procedures_args) < 1:
        return

    # ensure all procedures are for the same member
    member_id_set = {tp["member_id"] for tp in treatment_procedures_args}
    if len(member_id_set) > 1:
        raise ValidationError(
            "More than one member found in list of procedures. Please only include procedures for "
            "a single member."
        )

    count_benefits = 0
    count_procedure_map = defaultdict(int)
    member_id = member_id_set.pop()

    try:
        wallet_user = (
            ReimbursementWalletUsers.query.join(
                ReimbursementWallet,
                ReimbursementWalletUsers.reimbursement_wallet_id
                == ReimbursementWallet.id,
            )
            .filter(
                ReimbursementWalletUsers.user_id == member_id,
                ReimbursementWalletUsers.status == WalletUserStatus.ACTIVE,
                ReimbursementWallet.state.in_(
                    [WalletState.QUALIFIED, WalletState.RUNOUT]
                ),
            )
            .one_or_none()
        )
    except MultipleResultsFound:
        raise ValidationError(f"Multiple wallets found for member: {member_id}")
    if not wallet_user:
        raise ValidationError(f"Wallet not found for member: {member_id}")

    wallet = wallet_user.wallet
    reimbursement_category = wallet.get_direct_payment_category

    if not reimbursement_category:
        raise ValidationError("Wallet has no direct payment category.")

    benefit_type = wallet.category_benefit_type(
        request_category_id=reimbursement_category.id
    )

    enable_unlimited_benefits: bool = feature_flags.bool_variation(
        ENABLE_UNLIMITED_BENEFITS_FOR_TP_VALIDATION, default=False
    )

    if enable_unlimited_benefits:
        category_association = reimbursement_category.get_category_association(
            reimbursement_wallet=wallet
        )
        wallet_service = ReimbursementWalletService()
        category_balance: CategoryBalance = wallet_service.get_wallet_category_balance(
            category_association=category_association, wallet=wallet
        )
    else:
        currency_balance = wallet.available_currency_amount_by_category
        category_currency_balance = currency_balance.get(reimbursement_category.id)
        credit_balance = wallet.available_credit_amount_by_category
        category_credit_balance = credit_balance.get(reimbursement_category.id)

    # get all global procedures for treatment_procedures_args
    global_procedure_ids = list(
        {tp["global_procedure_id"] for tp in treatment_procedures_args}
    )
    global_procedures = ProcedureService().get_procedures_by_ids(
        procedure_ids=global_procedure_ids, headers=headers
    )
    if not global_procedures:
        stats.increment(
            metric_name=f"{metric_prefix}.procedure_service",
            pod_name=stats.PodNames.BENEFITS_EXP,
            tags=[
                "error:true",
                "error_cause:validate_procedures",
            ],
        )
        raise ValidationError("Global procedures not found.")

    global_procedures_by_id = {gp["id"]: gp for gp in global_procedures}  # type: ignore[typeddict-item] # TypedDict "PartialProcedure" has no key "id"

    # process by start date to ensure we calculate remaining benefits in order
    treatment_procedures_args.sort(key=lambda procedure: procedure["start_date"])

    org_excluded_procedures_ids = [
        ep.global_procedure_id
        for ep in wallet.reimbursement_organization_settings.excluded_procedures
    ]

    for procedure in treatment_procedures_args:
        global_procedure_id = procedure["global_procedure_id"]
        global_procedure = global_procedures_by_id.get(global_procedure_id)
        validate_procedure(
            procedure,
            wallet,
            global_procedure,  # type: ignore[arg-type] # Argument 3 to "validate_procedure" has incompatible type "Union[GlobalProcedure, PartialProcedure, None]"; expected "Dict[Any, Any]"
            org_excluded_procedures_ids,
        )

        if not global_procedure:
            raise ValidationError(
                f"No global procedure found for procedure id: {global_procedure_id}"
            )

        # check if member has enough remaining benefits
        # since we allow one procedure to be partially covered, we only care if there were not enough
        # benefits to cover entire procedure
        if enable_unlimited_benefits:
            if category_balance.benefit_type == BenefitTypes.CYCLE:
                # Check if the cost exceeds the available balance
                procedure_credits = global_procedure["credits"]

                if procedure_credits > 0:
                    balance_with_procedure = (
                        category_balance.available_balance
                        - count_benefits
                        - procedure_credits
                    )

                    if balance_with_procedure < 0:
                        log.info(
                            "Procedure cost exceeds available balance",
                            procedure_id=str(global_procedure_id),
                            wallet_id=str(wallet.id),
                            balance_with_procedure=str(balance_with_procedure),
                            available_balance=str(category_balance.available_balance),
                            procedure_cost=str(procedure_credits),
                        )
                        raise ValidationError(
                            "Procedures must be either fully or partially covered by remaining Maven benefits "
                            "in order to be billed through this portal. Please remove one or more of these "
                            "procedures and bill the member directly at the Maven discounted rate for self-pay patients."
                        )

                    count_benefits += procedure_credits

            elif category_balance.benefit_type == BenefitTypes.CURRENCY:
                # Check if the cost exceeds the available balance
                fertility_clinic_id = procedure["fertility_clinic_id"]
                clinic = FertilityClinic.query.get(fertility_clinic_id)
                fee_schedule_gp = FeeScheduleGlobalProcedures.query.filter(
                    FeeScheduleGlobalProcedures.global_procedure_id
                    == global_procedure_id,
                    FeeScheduleGlobalProcedures.fee_schedule_id
                    == clinic.fee_schedule_id,
                ).one_or_none()

                if not fee_schedule_gp:
                    raise ValidationError(
                        f"Fee schedule does not exist for procedure with id: {global_procedure_id}"
                    )

                if category_balance.is_unlimited:
                    log.info(
                        "Unlimited benefits enabled for wallet - TP cost does not exceed balance",
                        procedure_id=str(global_procedure_id),
                        wallet_id=str(wallet.id),
                        category_id=str(category_balance.id),
                    )
                    continue

                balance_with_procedure = (
                    category_balance.available_balance
                    - count_benefits
                    - fee_schedule_gp.cost
                )

                if balance_with_procedure < 0:
                    log.info(
                        "Procedure cost exceeds available balance",
                        procedure_id=str(global_procedure_id),
                        wallet_id=str(wallet.id),
                        balance_with_procedure=str(balance_with_procedure),
                        available_balance=str(category_balance.available_balance),
                        procedure_cost=str(fee_schedule_gp.cost),
                    )
                    raise ValidationError(
                        "Procedures must be either fully or partially covered by remaining Maven benefits "
                        "in order to be billed through this portal. Please remove one or more of these "
                        "procedures and bill the member directly at the Maven discounted rate for self-pay patients."
                    )

                count_benefits += fee_schedule_gp.cost

        else:
            if benefit_type == BenefitTypes.CYCLE:
                existing_scheduled_tps_and_pending_requests_amount = (
                    get_scheduled_tp_and_pending_rr_costs(
                        wallet, category_credit_balance
                    )
                )

                if global_procedure["credits"] > 0:  # type: ignore[typeddict-item] # TypedDict "PartialProcedure" has no key "credits"
                    curr_balance = (
                        category_credit_balance
                        - existing_scheduled_tps_and_pending_requests_amount
                        - count_benefits
                    )
                    if curr_balance <= 0:
                        raise ValidationError(
                            "Procedures must be either fully or partially covered by remaining Maven benefits "
                            "in order to be billed through this portal. Please remove one or more of these "
                            "procedures and bill the member directly at the Maven discounted rate for self-pay patients."
                        )

                count_benefits += global_procedure["credits"]  # type: ignore[typeddict-item] # TypedDict "PartialProcedure" has no key "credits"
            else:
                fertility_clinic_id = procedure["fertility_clinic_id"]
                clinic = FertilityClinic.query.get(fertility_clinic_id)
                fee_schedule_gp = FeeScheduleGlobalProcedures.query.filter(
                    FeeScheduleGlobalProcedures.global_procedure_id
                    == global_procedure_id,
                    FeeScheduleGlobalProcedures.fee_schedule_id
                    == clinic.fee_schedule_id,
                ).one_or_none()
                if not fee_schedule_gp:
                    raise ValidationError(
                        f"Fee schedule does not exist for procedure with id: {global_procedure_id}"
                    )

                existing_scheduled_tps_and_pending_requests_amount = (
                    get_scheduled_tp_and_pending_rr_costs(
                        wallet, category_currency_balance
                    )
                )

                curr_balance = (
                    category_currency_balance
                    - existing_scheduled_tps_and_pending_requests_amount
                    - count_benefits
                )
                if curr_balance <= 0:
                    raise ValidationError(
                        "Procedures must be either fully or partially covered by remaining Maven benefits "
                        "in order to be billed through this portal. Please remove one or more of these "
                        "procedures and bill the member directly at the Maven discounted rate for self-pay patients."
                    )

                count_benefits += fee_schedule_gp.cost

        count_procedure_map[global_procedure["id"]] += 1  # type: ignore[typeddict-item] # TypedDict "PartialProcedure" has no key "id"

    # check if member has reached annual limit for procedures if cycle-based benefit
    if benefit_type == BenefitTypes.CYCLE:
        for gp_id, count in count_procedure_map.items():
            validate_annual_limit_procedure(
                global_procedure=global_procedures_by_id[gp_id],  # type: ignore[arg-type] # Argument "global_procedure" to "validate_annual_limit_procedure" has incompatible type "Union[GlobalProcedure, PartialProcedure]"; expected "GlobalProcedure"
                member_id=member_id,
                new_procedure_count=count,
            )


def validate_procedure(
    treatment_procedure_args: dict,
    wallet: ReimbursementWallet,
    global_procedure: dict,
    excluded_procedures_ids: Collection = (),
) -> None:

    # If answer to infertility Dx question is NOT_SURE, only diagnostic procedure can be added
    infertility_diagnosis = treatment_procedure_args.get("infertility_diagnosis")
    if (
        infertility_diagnosis == PatientInfertilityDiagnosis.NOT_SURE.value
        and not global_procedure["is_diagnostic"]
    ):
        raise ValidationError("Only Diagnostic procedures can be added.")

    procedure_id = treatment_procedure_args["global_procedure_id"]
    member_id = treatment_procedure_args["member_id"]

    # validate patient wallet eligibility for procedures
    wallet_eligibility_state = get_wallet_patient_eligibility_state(
        wallet=wallet,
        infertility_diagnosis=infertility_diagnosis,
        global_procedure=global_procedure,
    )
    if wallet_eligibility_state == WalletDirectPaymentState.WALLET_CLOSED:
        raise ValidationError(
            f"User {member_id} is ineligible for this procedure: {procedure_id}"
        )
    elif wallet_eligibility_state == WalletDirectPaymentState.FERTILITY_DX_REQUIRED:
        raise ValidationError(
            f"User {member_id} requires a fertility diagnosis and is ineligible for this procedure: {procedure_id}"
        )
    elif (
        wallet_eligibility_state == WalletDirectPaymentState.DIAGNOSTIC_ONLY
        and not global_procedure["is_diagnostic"]
    ):
        raise ValidationError(
            f"User {member_id} can only add diagnostic procedures and is ineligible for this procedure: {procedure_id}"
        )

    # check against org excluded procedures
    if procedure_id in excluded_procedures_ids:
        raise ValidationError("Global procedure is excluded by org.")

    # check that start date is within the member's eligibility dates and up to 30 days before current date
    (
        member_eligibility_start_date,
        benefit_expires_date,
    ) = get_benefit_e9y_start_and_expiration_date(wallet, member_id)

    backdate_limit_date = date.today() - timedelta(days=PROCEDURE_BACKDATE_LIMIT_DAYS)

    if (
        member_eligibility_start_date is not None
        and treatment_procedure_args["start_date"] < member_eligibility_start_date
    ):
        log.info(
            f"Start date cannot be earlier than the member's eligibility start date for global procedure with uuid: {procedure_id}.",
            procedure_id=procedure_id,
            member_eligibility_date=member_eligibility_start_date,
            start_date=treatment_procedure_args["start_date"],
        )
        raise ValidationError(
            f"Start date cannot be earlier than the member's eligibility start date for global procedure with uuid: {procedure_id}."
        )
    if (
        benefit_expires_date is not None
        and treatment_procedure_args["start_date"] > benefit_expires_date
    ):
        log.info(
            f"Start date cannot be after the member's eligibility has ended for global procedure with uuid: {procedure_id}.",
            procedure_id=procedure_id,
            member_eligibility_date=member_eligibility_start_date,
            start_date=treatment_procedure_args["start_date"],
        )
        raise ValidationError(
            f"Start date cannot be after the member's eligibility has ended for global procedure with uuid: {procedure_id}."
        )
    if treatment_procedure_args["start_date"] < backdate_limit_date:
        log.info(
            f"Start date cannot be earlier than {PROCEDURE_BACKDATE_LIMIT_DAYS} days ago",
            procedure_id=procedure_id,
            start_date=treatment_procedure_args["start_date"],
        )
        raise ValidationError(
            f"Start date cannot be earlier than {PROCEDURE_BACKDATE_LIMIT_DAYS} days ago for global procedure with uuid: {procedure_id}."
        )

    # check start and end dates
    if (
        treatment_procedure_args.get("end_date")
        and treatment_procedure_args["end_date"]
        < treatment_procedure_args["start_date"]
    ):
        log.info(
            "End date must be on or after start date",
            procedure_id=procedure_id,
            start_date=treatment_procedure_args["start_date"],
            end_date=treatment_procedure_args["end_date"],
        )
        raise ValidationError(
            f"End date must be on or after start date for global procedure with uuid: {procedure_id}."
        )


def validate_edit_procedure(  # type: ignore[no-untyped-def] # Function is missing a return type annotation
    procedure_args: dict, treatment_procedure: TreatmentProcedure
):
    if treatment_procedure.status != TreatmentProcedureStatus.SCHEDULED:
        raise ValidationError("Cannot edit a completed procedure.")
    if procedure_args.get("status") == TreatmentProcedureStatus.CANCELLED.value:
        if procedure_args.get("end_date") is None:
            raise ValidationError("Cancellation date required.")
    elif (
        procedure_args.get("status") == TreatmentProcedureStatus.COMPLETED.value
        or procedure_args.get("status")
        == TreatmentProcedureStatus.PARTIALLY_COMPLETED.value
    ):
        if (
            procedure_args.get("end_date") is None
            or procedure_args.get("end_date") > date.today()
        ):
            raise ValidationError("End date must be today or in the past.")

    if (
        procedure_args.get("end_date")
        and procedure_args.get("status") != TreatmentProcedureStatus.CANCELLED.value
        and (
            procedure_args.get("end_date")
            < (procedure_args.get("start_date") or treatment_procedure.start_date)
        )
    ):
        raise ValidationError(
            f"End date must be on or after start date for procedure with id: {treatment_procedure.id}."
        )

    if (
        procedure_args.get("status")
        == TreatmentProcedureStatus.PARTIALLY_COMPLETED.value
        and procedure_args.get("partial_global_procedure_id") is None
    ):
        raise ValidationError(
            "Stage of cycle required for partially completed procedures."
        )


def validate_annual_limit_procedure(
    global_procedure: GlobalProcedure,
    member_id: int,
    new_procedure_count: int,
) -> None:
    annual_limit = global_procedure["annual_limit"]
    if not annual_limit:
        return

    member = User.query.get(member_id)
    if not member:
        abort(404, message="A member could not be found for the given information.")

    member_timezone = timezone(member.timezone)
    member_time_now = datetime.utcnow().astimezone(member_timezone)
    beginning_of_year = datetime(
        member_time_now.year, 1, 1, tzinfo=member_timezone
    ).date()
    end_of_year = datetime(member_time_now.year, 12, 31, tzinfo=member_timezone).date()

    existing_procedures = TreatmentProcedure.query.filter(
        TreatmentProcedure.member_id == member_id,
        TreatmentProcedure.global_procedure_id == global_procedure["id"],
        TreatmentProcedure.status != TreatmentProcedureStatus.CANCELLED,
        TreatmentProcedure.start_date.between(beginning_of_year, end_of_year),
    ).all()
    total_count_procedures = len(existing_procedures) + new_procedure_count

    if total_count_procedures > annual_limit:
        raise ValidationError(
            f"Member reached annual limit for procedure: {global_procedure['name']}. "
            "Please remove this procedure and bill outside the portal."
        )


def validate_fc_user_new_procedure(
    user: User, treatment_procedures_args: List[dict]
) -> None:
    procedure_clinic_id_set = {
        tp["fertility_clinic_id"] for tp in treatment_procedures_args
    }
    validate_fc_user(user=user, clinic_id_set=procedure_clinic_id_set)


def validate_fc_user(user: User, clinic_id_set: set) -> None:
    fc_user = FertilityClinicUserProfile.query.filter(
        FertilityClinicUserProfile.user_id == user.id
    ).one()
    allowed_clinics = fc_user.clinics

    # check stripe setup
    for clinic_id in clinic_id_set:
        clinic = FertilityClinic.query.get(clinic_id)
        # TODO: check setup complete via payments service
        if not clinic:
            raise ValidationError("Could not find clinic.")
        if not clinic.payments_recipient_id:
            raise ValidationError(
                "Account not enabled to receive payouts. You will not be able to add or complete "
                "procedures until you have finished setting up your account. Please update in account "
                "settings or contact your billing administrator."
            )

    # ensure fertility clinic user is allowed to add these procedures
    allowed_clinic_id_set = {clinic.id for clinic in allowed_clinics}
    if not clinic_id_set.issubset(allowed_clinic_id_set):
        abort(
            403,
            message="Fertility Clinic User does not have permission to add these procedures.",
        )


def get_member_procedures(
    fc_user: FertilityClinicUserProfile, member_id: int
) -> List[TreatmentProcedure]:
    # filter out by fertility clinic user allowed clinics
    fc_user = FertilityClinicUserProfile.query.filter(
        FertilityClinicUserProfile.user_id == fc_user.id
    ).one()
    allowed_clinic_ids = [clinic.id for clinic in fc_user.clinics]

    return TreatmentProcedure.query.filter(
        TreatmentProcedure.member_id == member_id,
        TreatmentProcedure.fertility_clinic_id.in_(allowed_clinic_ids),
        TreatmentProcedure.status != TreatmentProcedureStatus.PARTIALLY_COMPLETED,
    ).all()


def get_wallet_patient_eligibility_state(
    wallet: ReimbursementWallet,
    infertility_diagnosis: Optional[PatientInfertilityDiagnosis],
    global_procedure: dict,
) -> WalletDirectPaymentState:
    """
    Use this to validate that procedures can be added to a user's treatment plan
    :param  wallet: ReimbursementWallet
    :param  infertility_diagnosis: diagnostic result for patient (infertile, not infertile, not sure)
    :param  global_procedure: global procedure being added for patient
    :return: One of the wallet eligibility states such that we know what procedures are available to the patient
        WALLET_OPEN: All procedures allowed to the clinic are available to be added.
        WALLET_CLOSED: No procedures can be added, but existing procedures can be cancelled.
        DIAGNOSTIC_ONLY: Only procedures with the diagnostic flag may be added.
        FERTILITY_DX_REQUIRED: Requires fertility diagnosis to determine status
    """
    state = WalletDirectPaymentState.WALLET_CLOSED  # Default to closed

    wallet_state = wallet.state
    org_settings = wallet.reimbursement_organization_settings
    dp_enabled = org_settings.direct_payment_enabled
    program_type = org_settings.fertility_program_type
    # descoped for 1/1
    # taxable_only = org_settings.fertility_allows_taxable
    dx_required_procedure_ids = {
        p.global_procedure_id for p in org_settings.dx_required_procedures
    }

    if wallet_state in (WalletState.RUNOUT, WalletState.EXPIRED):
        state = WalletDirectPaymentState.WALLET_CLOSED
    elif not dp_enabled:
        state = WalletDirectPaymentState.WALLET_CLOSED
    else:
        if program_type == FertilityProgramTypes.CARVE_OUT:
            if dx_required_procedure_ids:
                if infertility_diagnosis == PatientInfertilityDiagnosis.NOT_SURE:
                    state = WalletDirectPaymentState.DIAGNOSTIC_ONLY
                elif (
                    infertility_diagnosis
                    == PatientInfertilityDiagnosis.MEDICALLY_INFERTILE
                ):
                    state = WalletDirectPaymentState.WALLET_OPEN
                elif (
                    infertility_diagnosis
                    == PatientInfertilityDiagnosis.MEDICALLY_FERTILE
                ) or not infertility_diagnosis:
                    # taxable_only logic has been removed here as it's not needed for 1/1 launch but keeping if/else
                    # structure in place to be easily integrated back in once this is ready
                    if global_procedure["is_diagnostic"]:
                        state = WalletDirectPaymentState.WALLET_OPEN
                    elif global_procedure["id"] in dx_required_procedure_ids:
                        state = WalletDirectPaymentState.FERTILITY_DX_REQUIRED
                    else:
                        state = WalletDirectPaymentState.WALLET_OPEN
            else:
                state = WalletDirectPaymentState.WALLET_OPEN
        elif program_type == FertilityProgramTypes.WRAP_AROUND:
            if dx_required_procedure_ids:
                if not infertility_diagnosis:
                    state = WalletDirectPaymentState.FERTILITY_DX_REQUIRED
                elif infertility_diagnosis == PatientInfertilityDiagnosis.NOT_SURE:
                    state = WalletDirectPaymentState.DIAGNOSTIC_ONLY
                elif (
                    infertility_diagnosis
                    == PatientInfertilityDiagnosis.MEDICALLY_INFERTILE
                ):
                    state = WalletDirectPaymentState.WALLET_CLOSED
                elif (
                    infertility_diagnosis
                    == PatientInfertilityDiagnosis.MEDICALLY_FERTILE
                ):
                    state = WalletDirectPaymentState.WALLET_OPEN
            else:
                # Wraparound always requires a diagnosis, we shouldn't be hitting this case
                log.error(
                    f"Wrap Around wallet {wallet.id} should require a diagnosis in reimbursement org settings"
                )
                stats.increment(
                    metric_name=f"{metric_prefix}.get_wallet_patient_eligibility_state",
                    pod_name=stats.PodNames.BENEFITS_EXP,
                    tags=[
                        "error:true",
                        "error_cause:wraparound_wallet_diagnosis_required",
                    ],
                )
                raise ValidationError(
                    "Incorrect Wallet configuration: Wraparound wallet should require a diagnosis"
                )

    return state


def process_partial_procedure(
    treatment_procedure: TreatmentProcedure,
    procedure_args: dict,
    repository: treatment_procedure.TreatmentProcedureRepository,
    headers: Mapping[str, str] = None,  # type: ignore[assignment] # Incompatible default for argument "headers" (default has type "None", argument has type "Mapping[str, str]")
) -> TreatmentProcedure:
    partial_global_procedure = ProcedureService().get_procedure_by_id(
        procedure_id=procedure_args.get("partial_global_procedure_id"), headers=headers
    )
    if not partial_global_procedure:
        stats.increment(
            metric_name=f"{metric_prefix}.procedure_service",
            pod_name=stats.PodNames.BENEFITS_EXP,
            tags=[
                "error:true",
                "error_cause:process_partial_procedure",
            ],
        )
        raise ValidationError("Could not find reimbursement wallet global procedure")

    validate_partial_global_procedure(treatment_procedure, partial_global_procedure)  # type: ignore[arg-type] # Argument 2 to "validate_partial_global_procedure" has incompatible type "Union[GlobalProcedure, PartialProcedure]"; expected "Dict[Any, Any]"

    partial_procedure = repository.create(
        member_id=treatment_procedure.member_id,
        infertility_diagnosis=treatment_procedure.infertility_diagnosis,
        reimbursement_wallet_id=treatment_procedure.reimbursement_wallet_id,
        reimbursement_request_category_id=treatment_procedure.reimbursement_request_category_id,
        fee_schedule_id=treatment_procedure.fee_schedule_id,
        global_procedure_id=partial_global_procedure["id"],  # type: ignore[typeddict-item] # TypedDict "PartialProcedure" has no key "id"
        global_procedure_name=partial_global_procedure["name"],  # type: ignore[typeddict-item] # TypedDict "PartialProcedure" has no key "name"
        global_procedure_credits=partial_global_procedure["credits"],  # type: ignore[typeddict-item] # TypedDict "PartialProcedure" has no key "credits"
        fertility_clinic_id=treatment_procedure.fertility_clinic_id,
        fertility_clinic_location_id=treatment_procedure.fertility_clinic_location_id,
        start_date=treatment_procedure.start_date,
        end_date=procedure_args.get("end_date"),
        status=TreatmentProcedureStatus.PARTIALLY_COMPLETED,
        completed_date=procedure_args.get("end_date"),
        global_procedure_type=treatment_procedure.procedure_type,
    )

    # cancel original procedure and link partial procedure
    repository.update(
        treatment_procedure_id=treatment_procedure.id,
        status=TreatmentProcedureStatus.CANCELLED,
        start_date=treatment_procedure.start_date,
        end_date=procedure_args.get("end_date"),
        partial_procedure_id=partial_procedure.id,
    )
    # trigger refund
    trigger_cost_breakdown(treatment_procedure=treatment_procedure, new_procedure=False)

    return partial_procedure


def validate_partial_global_procedure(  # type: ignore[no-untyped-def] # Function is missing a return type annotation
    treatment_procedure: TreatmentProcedure, partial_global_procedure: dict
):
    if not partial_global_procedure["is_partial"]:
        raise ValidationError("Partial global procedure id is not a partial procedure.")

    if not (
        treatment_procedure.global_procedure_id
        in partial_global_procedure["parent_procedure_ids"]
    ):
        raise ValidationError(
            "Partial global procedure is not a valid child procedure of treatment procedure."
        )


def get_cycle_treatment_currency_cost(
    treatment_procedure: TreatmentProcedure,
) -> Optional[int]:
    fee_schedule_gp = FeeScheduleGlobalProcedures.query.filter(
        FeeScheduleGlobalProcedures.global_procedure_id
        == treatment_procedure.global_procedure_id,
        FeeScheduleGlobalProcedures.fee_schedule_id
        == treatment_procedure.fee_schedule_id,
    ).one_or_none()
    if not fee_schedule_gp:
        log.error(
            "Fee schedule does not exist for procedure",
            global_procedure_id=treatment_procedure.global_procedure_id,
            fee_schedule_id=treatment_procedure.fee_schedule_id,
        )
        return None
    return fee_schedule_gp.cost


def trigger_cost_breakdown(  # type: ignore[no-untyped-def] # Function is missing a type annotation for one or more arguments
    treatment_procedure: TreatmentProcedure, new_procedure: bool = False, use_async=True
) -> bool:
    success = None
    if new_procedure:
        log.info(
            "New treatment procedure created. Initiating cost breakdown.",
            treatment_procedure_id=treatment_procedure.id,
        )
        success = run_cost_breakdown(treatment_procedure, use_async=use_async)
    elif (
        treatment_procedure.status == TreatmentProcedureStatus.COMPLETED
        or treatment_procedure.status == TreatmentProcedureStatus.PARTIALLY_COMPLETED
    ):
        log.info(
            "Treatment procedure completed. Initiating cost breakdown.",
            treatment_procedure_id=treatment_procedure.id,
        )
        success = run_cost_breakdown(treatment_procedure, use_async=use_async)
    elif treatment_procedure.status == TreatmentProcedureStatus.CANCELLED:
        log.info(
            "Treatment procedure cancelled. Initiating refund.",
            treatment_procedure_id=treatment_procedure.id,
        )
        if use_async:
            create_and_process_member_refund_bills.delay(
                treatment_procedure_id=treatment_procedure.id
            )
        else:
            create_and_process_member_refund_bills(
                treatment_procedure_id=treatment_procedure.id
            )
        success = True
    if not success:
        stats.increment(
            metric_name=f"{metric_prefix}.trigger_cost_breakdown",
            pod_name=stats.PodNames.BENEFITS_EXP,
            tags=["error:true", "error_cause:failed_cost_breakdown"],
        )
        log.error(
            "Error running cost breakdown",
            treatment_procedure_id=treatment_procedure.id,
        )
        return False
    return True


def run_cost_breakdown(treatment_procedure: TreatmentProcedure, use_async=True) -> bool:  # type: ignore[no-untyped-def] # Function is missing a type annotation for one or more arguments
    if use_async:
        # this one should match the settings for api/cost_breakdown/tasks/calculate_cost_breakdown.py
        redis_cli = redis_client()
        key = f"cost_breakdown_rq:{treatment_procedure.reimbursement_wallet_id}"
        pending_job_ids: List[str] = redis_cli.lrange(key, 0, -1)

        # if there are pending cost breakdown RQ jobs for the same wallet, then wait them to run for sequential payments
        if pending_job_ids:
            log.info(
                "Found pending cost breakdown RQ jobs, wait until they finish",
                pending_job_ids=pending_job_ids,
                wallet_id=treatment_procedure.reimbursement_wallet_id,
            )
            dependencies: Dependency = Dependency(
                jobs=[id.decode() for id in pending_job_ids],  # type: ignore[attr-defined] # "str" has no attribute "decode"; maybe "encode"?
                allow_failure=True,
            )
            job: Job = calculate_cost_breakdown_async.delay(
                depends_on=dependencies,
                wallet_id=treatment_procedure.reimbursement_wallet_id,
                treatment_procedure_id=treatment_procedure.id,
            )
        else:
            log.info(
                "No pending cost breakdown RQ jobs for wallet, current job will be executed next within this wallet",
                pending_job_ids=pending_job_ids,
                wallet_id=treatment_procedure.reimbursement_wallet_id,
            )
            job: Job = calculate_cost_breakdown_async.delay(  # type: ignore[no-redef] # Name "job" already defined on line 642
                wallet_id=treatment_procedure.reimbursement_wallet_id,
                treatment_procedure_id=treatment_procedure.id,
            )
        redis_cli.lpush(key, job.id)
        expire_seconds = 600  # 10 minutes
        redis_cli.expire(key, expire_seconds)
    else:
        calculate_cost_breakdown(
            wallet_id=treatment_procedure.reimbursement_wallet_id,
            treatment_procedure_id=treatment_procedure.id,
            use_async=False,
        )
    return True


def get_global_procedure_ids(
    treatment_procedures: Iterable[TreatmentProcedure] | Iterable[dict],
) -> List[str]:
    for procedure in treatment_procedures:
        if isinstance(procedure, TreatmentProcedure):
            yield procedure.global_procedure_id
            if procedure.partial_procedure:
                yield procedure.partial_procedure.global_procedure_id

        elif isinstance(procedure, dict):
            yield procedure["global_procedure_id"]
            if "partial_procedure" in procedure:
                yield procedure["partial_procedure"]["global_procedure_id"]


def get_mapped_global_procedures(member_procedures: list[TreatmentProcedure]) -> dict:
    global_procedure_ids = set(get_global_procedure_ids(member_procedures))
    found_procedures = ProcedureService().get_procedures_by_ids(
        procedure_ids=list(global_procedure_ids), headers=request.headers  # type: ignore[arg-type] # Argument "headers" to "get_procedures_by_ids" of "ProcedureService" has incompatible type "EnvironHeaders"; expected "Optional[Mapping[str, str]]"
    )
    if not found_procedures:
        log.info("No global procedures found.")
        return None  # type: ignore[return-value] # Incompatible return value type (got "None", expected "Dict[Any, Any]")

    return {
        global_procedure["id"]: global_procedure  # type: ignore[typeddict-item] # TypedDict "PartialProcedure" has no key "id"
        for global_procedure in found_procedures
    }
