from __future__ import annotations

from datetime import datetime, timezone
from traceback import format_exc

from sqlalchemy.orm.exc import MultipleResultsFound, NoResultFound

from common import stats
from storage import connection
from tasks.queues import job
from utils.log import logger
from wallet import alegeus_api
from wallet.models.annual_insurance_questionnaire_response import (
    AnnualInsuranceQuestionnaireResponse,
)
from wallet.models.constants import AnnualQuestionnaireSyncStatus
from wallet.models.models import AnnualInsuranceQuestionnaireHDHPData
from wallet.models.reimbursement_wallet import ReimbursementWallet
from wallet.services.reimbursement_category_activation_visibility import (
    CategoryActivationService,
)
from wallet.utils.admin_helpers import FlashMessageCategory
from wallet.utils.alegeus.enrollments.enroll_wallet import configure_account
from wallet.utils.insurance.process_questionnaire import (
    create_wallet_hdhp_plan,
    get_hdhp_questionnaire_response,
)

# TODO - fix the hard-coding to 2024
COVERAGE_YEAR = 2024

log = logger(__name__)


@job("high_mem", service_ns="wallet", team_ns="benefits_experience")
def process_annual_questionnaire(
    wallet_id: int,
    questionnaire_uuid: str,
    questionnaire_data: AnnualInsuranceQuestionnaireHDHPData,
    plan_year: int,
    is_legacy_mode: bool,
) -> str | None:
    """Accepts a response to HDHP survey questions and determines if a new wallet hdhp plan needs to be created."""
    log.info(
        "starting process_annual_questionnaire",
        wallet_id=str(wallet_id),
        questionnaire_uuid=questionnaire_uuid,
        plan_year=plan_year,
        is_legacy_mode=is_legacy_mode,
    )
    stats.increment(
        metric_name="wallet.tasks.insurance.accept_async_processing_questionnaire",
        pod_name=stats.PodNames.BENEFITS_EXP,
    )
    questionnaire_response = _load_questionnaire(questionnaire_uuid)
    wallet_id_str = str(wallet_id)
    try:
        coverage_tier = get_hdhp_questionnaire_response(questionnaire_data)
        if not coverage_tier:
            log.info(
                "Survey indicates that wallet does not need an HDHP plan",
                wallet_id=wallet_id_str,
            )
            return  # type: ignore[return-value] # Return value expected

        log.info(
            "Processing annual insurance questionnaire for wallet.",
            wallet_id=wallet_id_str,
            coverage_tier=coverage_tier,
        )
        try:
            wallet = (
                connection.db.session.query(ReimbursementWallet)
                .filter(ReimbursementWallet.id == wallet_id)
                .one()
            )
        except NoResultFound:
            status = AnnualQuestionnaireSyncStatus.MISSING_WALLET_ERROR
        except MultipleResultsFound:
            status = AnnualQuestionnaireSyncStatus.MULTIPLE_WALLETS_ERROR
            log.error(
                "Wallet load error.",
                wallet_id=wallet_id_str,
                questionnaire_uuid=questionnaire_uuid,
                status=status,
            )
        else:
            plan = create_wallet_hdhp_plan(
                wallet, coverage_tier, plan_year, is_legacy_mode
            )
            if not plan:
                status = AnnualQuestionnaireSyncStatus.PLAN_ERROR
                log.warning(
                    "Unable to create HDHP plan.",
                    wallet_id=wallet_id_str,
                    questionnaire_uuid=questionnaire_uuid,
                )
            else:
                api = alegeus_api.AlegeusApi()
                start_date = CategoryActivationService().get_start_date_for_user_allowed_category(
                    allowed_category=None, plan=plan, user_id=wallet.user_id  # type: ignore[arg-type]
                )
                success, messages = configure_account(
                    api=api,
                    wallet=wallet,
                    plan=plan,
                    prefunded_amount=0,
                    coverage_tier=coverage_tier,
                    start_date=start_date,
                    messages=[],
                )
                msg_str = " ".join(msg.message for msg in messages)
                if success:
                    if messages[0].category == FlashMessageCategory.INFO:
                        status = (
                            AnnualQuestionnaireSyncStatus.ALEGEUS_PRE_EXISTING_ACCOUNT
                        )
                    else:
                        status = AnnualQuestionnaireSyncStatus.ALEGEUS_SUCCESS
                    log.info(f"Alegus sync status: {status} messages: {msg_str}")
                else:
                    status = AnnualQuestionnaireSyncStatus.ALEGEUS_FAILURE
                    log.error(
                        "Unable to update member HDHP plan/sync with Alegeus",
                        wallet_id=wallet_id_str,
                        questionnaire_uuid=questionnaire_uuid,
                        error=msg_str,
                        status=status,
                    )
    except Exception:
        status = AnnualQuestionnaireSyncStatus.UNKNOWN_ERROR
        log.error(
            "Failure processing annual insurance questionnaire.",
            wallet_id=wallet_id_str,
            questionnaire_uuid=questionnaire_uuid,
            reason=format_exc(),
        )
    # TODO: setup log alerting in Datadog to slack ops if this fails
    _update_questionnaire_response_status(questionnaire_response, status)
    log.info(
        "Persisted annual insurance questionnaire sync status",
        wallet_id=wallet_id_str,
        questionnaire_uuid=questionnaire_uuid,
        status=status,
    )

    return status


def _load_questionnaire(
    questionnaire_uuid: str,
) -> AnnualInsuranceQuestionnaireResponse:
    try:
        res = (
            connection.db.session.query(AnnualInsuranceQuestionnaireResponse)
            .filter(AnnualInsuranceQuestionnaireResponse.uuid == questionnaire_uuid)
            .one()
        )
        return res
    except NoResultFound:
        msg = "Unable to load questionnaire. This should never happen!"
        log.error(msg, questionnaire_uuid=questionnaire_uuid)
        raise NoResultFound(msg)
    except MultipleResultsFound:
        msg = "Multiple questionnaires found. This should never happen!"
        log.error(msg, questionnaire_uuid=questionnaire_uuid)
        raise MultipleResultsFound(msg)


def _update_questionnaire_response_status(
    questionnaire_response: AnnualInsuranceQuestionnaireResponse,
    status: AnnualQuestionnaireSyncStatus,
) -> None:
    questionnaire_response.sync_status = status
    now_ = datetime.now(timezone.utc)
    questionnaire_response.modified_at = now_
    if status in {
        AnnualQuestionnaireSyncStatus.ALEGEUS_SUCCESS,
        AnnualQuestionnaireSyncStatus.ALEGEUS_FAILURE,
        AnnualQuestionnaireSyncStatus.ALEGEUS_PRE_EXISTING_ACCOUNT,
    }:
        questionnaire_response.sync_attempt_at = now_
    connection.db.session.commit()
    log.info(
        "Updated the questionnaire status.",
        questionnaire_response_uuid=str(questionnaire_response.uuid),
        status=str(status),
    )
