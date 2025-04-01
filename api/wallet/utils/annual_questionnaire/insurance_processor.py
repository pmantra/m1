from __future__ import annotations

from datetime import date, datetime, time, timedelta, timezone

import ddtrace
from sqlalchemy.orm.exc import MultipleResultsFound

from authn.models.user import User
from common import stats
from storage import connection
from storage.connection import db
from utils.braze import send_user_wallet_attributes
from utils.log import logger
from wallet.models.annual_insurance_questionnaire_response import (
    AnnualInsuranceQuestionnaireResponse,
)
from wallet.models.constants import (
    AnnualQuestionnaireSyncStatus,
    MemberHealthPlanPatientRelationship,
)
from wallet.models.reimbursement_organization_settings import EmployerHealthPlan
from wallet.models.reimbursement_wallet import MemberHealthPlan, ReimbursementWallet
from wallet.repository.health_plan import HealthPlanRepository
from wallet.utils.annual_questionnaire.processor import (
    process_direct_payment_survey_response_json,
)

log = logger(__name__)
ddtrace.tracer.wrap()

MAX_BACKDATE_DAYS = 180


@ddtrace.tracer.wrap()
def process_direct_payment_insurance_response(
    questionnaire_response: AnnualInsuranceQuestionnaireResponse,
    effective_date: date,
) -> MemberHealthPlan | None:
    """
    :param questionnaire_response: THe users response to the survey and related date
    :param effective_date: The date as of which the plan is being created
    :return: A member health plan if successfully created and persisted, None otherwise
    """
    _update_response_status(
        questionnaire_response,
        AnnualQuestionnaireSyncStatus.MEMBER_HEALTH_PLAN_CREATION_INITIATED,
    )
    metric_name = "wallet.utils.annual_questionnaire.insurance_processor.process_direct_payment_insurance_response"
    try:
        log.info(
            "Processing DP insurance response",
            questionnaire_response_uuid=str(questionnaire_response.uuid),
            questionnaire_response_id=str(questionnaire_response.id),
            questionnaire_type=str(questionnaire_response.questionnaire_type),
            effective_date=str(effective_date),
        )
        user: User = User.query.get(questionnaire_response.submitting_user_id)
        mhp = _process_direct_payment_insurance_response(
            questionnaire_response, effective_date, user
        )
        connection.db.session.add(mhp)
        connection.db.session.commit()

        _inject_user_added_health_plan_info_attribute(user)

        stats.increment(
            metric_name=metric_name,
            pod_name=stats.PodNames.BENEFITS_EXP,
            tags=["success:true"],
        )
        log.info(
            "Processed DP insurance response and successfully committed member health plan to DB.",
            questionnaire_response_uuid=str(questionnaire_response.uuid),
            questionnaire_response_id=str(questionnaire_response.id),
            questionnaire_type=str(questionnaire_response.questionnaire_type),
            effective_date=str(effective_date),
            member_health_plan_id=str(mhp.id),
        )
        _update_response_status(
            questionnaire_response,
            AnnualQuestionnaireSyncStatus.MEMBER_HEALTH_PLAN_CREATION_SUCCESS,
        )
        return mhp
    except ValueError as e:
        connection.db.session.rollback()
        log.error(
            "Unable to create Member Health Plan. Nothing committed.", error=str(e)
        )
        stats.increment(
            metric_name=metric_name,
            pod_name=stats.PodNames.BENEFITS_EXP,
            tags=["success:false"],
        )
        # TODO update the code to get better error granularity
        _update_response_status(
            questionnaire_response,
            AnnualQuestionnaireSyncStatus.MEMBER_HEALTH_PLAN_GENERIC_ERROR,
        )
    except Exception as e:
        connection.db.session.rollback()
        log.error(
            "Unexpected error creating Member Health Plan. Nothing committed.",
            error=str(e),
        )
        stats.increment(
            metric_name=metric_name,
            pod_name=stats.PodNames.BENEFITS_EXP,
            tags=["success:false"],
        )
        _update_response_status(
            questionnaire_response,
            AnnualQuestionnaireSyncStatus.MEMBER_HEALTH_PLAN_GENERIC_ERROR,
        )
    return None


@ddtrace.tracer.wrap()
def _process_direct_payment_insurance_response(
    payload: AnnualInsuranceQuestionnaireResponse,
    effective_date: date,
    user: User,
) -> MemberHealthPlan | None:
    # 1. convert the response json to a data class
    resp = process_direct_payment_survey_response_json(payload.user_response_json)
    # 2. use the wallet id to find the wallet
    wallet: ReimbursementWallet = ReimbursementWallet.query.get(payload.wallet_id)
    if not wallet:
        raise ValueError(f"No Wallet found for id {payload.wallet_id}.")
    # 3. use the employer plan id to get the plan
    health_plan_repo: HealthPlanRepository = HealthPlanRepository(db.session)

    ehp: EmployerHealthPlan = health_plan_repo.get_employer_plan(
        id=resp.employer_health_plan_id
    )
    if not ehp:
        raise ValueError(
            f"No Employer health plan found for id {resp.employer_health_plan_id}."
        )

    # check for discrepancies
    if (
        wallet_org_id := wallet.reimbursement_organization_settings.organization_id
    ) != (ehp_org_id := ehp.reimbursement_organization_settings.organization_id):
        raise ValueError(
            f"Mismatch between employer org id {ehp_org_id} and wallet org id {wallet_org_id}."
        )

    user_dob = _get_dob(user)

    is_subscriber = (
        resp.member_health_plan_patient_relationship
        == MemberHealthPlanPatientRelationship.CARDHOLDER
    )

    subscriber_plan_start_at = None  # decision pending
    if (not is_subscriber) and (
        subscriber := _get_subscriber_member_health_record(
            resp.subscriber_insurance_id, ehp, health_plan_repo
        )
    ):
        subscriber_plan_start_at = subscriber.plan_start_at

    plan_start_at = _compute_plan_start_at(
        wallet_id=wallet.id,
        member_id=user.id,
        ehp=ehp,
        subscriber_plan_start_at=subscriber_plan_start_at,
        effective_date=effective_date,
    )

    mhp = health_plan_repo.create_member_health_plan(
        employer_health_plan_id=ehp.id,
        reimbursement_wallet_id=wallet.id,
        member_id=user.id,
        subscriber_insurance_id=resp.subscriber_insurance_id,
        plan_type=resp.family_plan_type,
        is_subscriber=is_subscriber,
        subscriber_first_name=resp.subscriber_first_name,
        subscriber_last_name=resp.subscriber_last_name,
        subscriber_date_of_birth=resp.subscriber_date_of_birth,
        patient_first_name=user.first_name,
        patient_last_name=user.last_name,
        patient_date_of_birth=user_dob,
        patient_sex=resp.patient_sex,
        patient_relationship=resp.member_health_plan_patient_relationship,
        plan_start_at=plan_start_at,
        plan_end_at=datetime.combine(ehp.end_date, time(23, 59, 59, 0)),
    )
    log.info(
        "Created in memory member health plan",
        survey_response_uuid=str(payload.uuid),
        survey_response_id=str(payload.id),
        questionnaire_type=payload.questionnaire_type,
        employer_plan_id=str(resp.employer_health_plan_id),
        member_health_plan_id=str(mhp.id),
    )
    return mhp


def _get_dob(user: User) -> date | None:
    try:
        user_dob_str_or_date = user.date_of_birth
        if isinstance(user_dob_str_or_date, str):
            return (
                date.fromisoformat(user_dob_str_or_date)
                if user_dob_str_or_date
                else None
            )
        if isinstance(user_dob_str_or_date, date):
            return user_dob_str_or_date
        return None
    except Exception:
        log.warn("Could not get date of birth.")
        return None


def _get_subscriber_member_health_record(
    subscriber_id: str,
    employer_health_plan: EmployerHealthPlan,
    health_repo: HealthPlanRepository,
) -> MemberHealthPlan | None:

    try:
        to_return = health_repo.get_subscriber_member_health_plan(
            subscriber_id=subscriber_id,
            employer_health_plan_id=employer_health_plan.id,
            plan_start_at_earliest=datetime.combine(
                employer_health_plan.start_date, time(0, 0, 0, 0)
            ),
            plan_end_at_latest=datetime.combine(
                employer_health_plan.end_date, time(23, 59, 59, 0)
            ),
        )
        return to_return

    except MultipleResultsFound:
        stats.increment(
            metric_name="wallet.utils.annual_questionnaire.insurance_processor._get_subscriber_member_health_record",
            pod_name=stats.PodNames.BENEFITS_EXP,
        )
        log.warn(
            "Subscriber_id is linked to multiple member health plans with is_subscriber = True.",
            subscriber_id=str(subscriber_id),
            employer_health_plan=str(employer_health_plan.id),
            tags=["multiple_subscribers"],
        )
        return None


def _compute_plan_start_at(
    *,
    wallet_id: int,
    member_id: int,
    ehp: EmployerHealthPlan,
    subscriber_plan_start_at: datetime | None,
    effective_date: date,
) -> datetime:
    log.info(
        "Computing plan start datetime",
        wallet_id=str(wallet_id),
        member_id=str(member_id),
        ehp_id=str(ehp.id),
    )
    if ehp.start_date > ehp.end_date:
        log.error(
            "Unable to compute plan start datetime - employer plan start date is after plan end date.",
            wallet_id=str(wallet_id),
            member_id=str(member_id),
            ehp_id=str(ehp.id),
            subscriber_plan_start_at=str(subscriber_plan_start_at),
            ehp_start_date=str(ehp.start_date),
            ehp_end_date=str(ehp.end_date),
        )
        raise ValueError(
            f"Employer plan start date {ehp.start_date} is after plan end date {ehp.end_date}."
        )
    if ehp.start_date >= effective_date:
        # the EHP start date is not in the past
        reason = "The employer health plan start date is not in the past."
        plan_start_at = ehp.start_date
    elif ehp.end_date < effective_date:
        # the EHP start and end date are both in the past
        # set the start date to the earliest of (EHP.end_date,  today - MAX_BACKDATE_DAYS)
        reason = "The employer health plan start and end date are in the past."
        plan_start_at = min(
            effective_date - timedelta(days=MAX_BACKDATE_DAYS), ehp.end_date
        )
    else:
        # the EHP start date is in the past, the end date is not in the past
        # set the start date to today - MAX_BACKDATE_DAYS
        reason = "The employer health plan start date is in the past, and the end date is not in the past."
        plan_start_at = max(
            effective_date - timedelta(days=MAX_BACKDATE_DAYS), ehp.start_date
        )

    # this date cannot be earlier than the subscriber start date
    if subscriber_plan_start_at and plan_start_at < subscriber_plan_start_at.date():
        reason = "The subscribers plan start is after the computed plan start at and will be instead used."
        to_return = subscriber_plan_start_at
    else:
        to_return = datetime.combine(plan_start_at, time(0, 0, 0, 0))

    log.info(
        "Computed plan start datetime.",
        plan_start_at=str(to_return),
        wallet_id=str(wallet_id),
        member_id=str(member_id),
        ehp_id=str(ehp.id),
        subscriber_plan_start_at=str(subscriber_plan_start_at),
        ehp_start_date=str(ehp.start_date),
        ehp_end_date=str(ehp.end_date),
        reason=reason,
    )
    return to_return


@ddtrace.tracer.wrap()
def _update_response_status(
    questionnaire_response: AnnualInsuranceQuestionnaireResponse,
    new_status: AnnualQuestionnaireSyncStatus,
) -> None:
    # Do not let updating the response status break anything else.
    try:
        log.info(
            "Updating the questionnaire response status.",
            questionnaire_response_uuid=str(questionnaire_response.uuid),
            questionnaire_response_id=str(questionnaire_response.id),
            questionnaire_response_status_current=str(
                questionnaire_response.sync_status
            ),
            questionnaire_response_status_new=str(new_status),
        )
        questionnaire_response.sync_status = new_status
        questionnaire_response.modified_at = datetime.now(timezone.utc)
        connection.db.session.commit()
    except Exception as e:
        log.error(
            "Unable to persist questionnaire response status.",
            error=str(e),
            questionnaire_response_uuid=str(questionnaire_response.uuid),
            questionnaire_response_id=str(questionnaire_response.id),
            questionnaire_response_status_current=str(
                questionnaire_response.sync_status
            ),
            questionnaire_response_status_new=str(new_status),
        )
        connection.db.session.rollback()


def _inject_user_added_health_plan_info_attribute(user: User) -> None:
    send_user_wallet_attributes(
        external_id=user.esp_id,
        wallet_added_health_insurance_datetime=datetime.now(timezone.utc),
    )
