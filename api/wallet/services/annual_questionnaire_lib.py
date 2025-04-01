from __future__ import annotations

import json
from datetime import date, datetime, timezone
from enum import Enum
from traceback import format_exc

from babel import get_locale_identifier
from dateutil.relativedelta import relativedelta
from ddtrace import tracer
from flask_babel import get_locale
from sqlalchemy import distinct, exists, extract
from sqlalchemy.exc import IntegrityError

from authn.models.user import User
from common import stats
from common.health_data_collection.base_api import make_hdc_request
from l10n.config import CUSTOM_LOCALE_HEADER
from storage import connection
from utils.log import logger
from wallet.annual_insurance_questionnaire_constants import (
    ANNUAL_INSURANCE_FORM_DP_WALLET_SCREENER_BRANCHING,
    CONTENTFUL_WIDGET_MAPPING,
    CONTENTFUL_WIDGETS_WITH_OPTIONS,
    MAX_SURVEY_DAYS_IN_ADVANCE,
    MEDICAL_EXPENSE_TYPES,
    ORG_ID_AMAZON,
    ORG_ID_OHIO,
    PAYER_PLAN_TITLE,
)
from wallet.models.annual_insurance_questionnaire_response import (
    AnnualInsuranceQuestionnaireResponse,
)
from wallet.models.constants import (
    AnnualQuestionnaireRequestStatus,
    AnnualQuestionnaireSyncStatus,
    QuestionnaireType,
    ReimbursementRequestExpenseTypes,
    WalletState,
)
from wallet.models.models import AnnualInsuranceQuestionnaireHDHPData
from wallet.models.reimbursement import ReimbursementPlan
from wallet.models.reimbursement_organization_settings import (
    EmployerHealthPlan,
    ReimbursementOrganizationSettings,
)
from wallet.models.reimbursement_wallet import ReimbursementWallet
from wallet.repository.health_plan import HealthPlanRepository
from wallet.tasks.insurance import process_annual_questionnaire
from wallet.utils.annual_questionnaire.insurance_processor import (
    process_direct_payment_insurance_response,
)
from wallet.utils.annual_questionnaire.processor import (
    process_traditional_survey_response_json,
)

log = logger(__name__)

QUESTIONNAIRE = "questionnaire"
STATUS = "status"


class AnnualQuestionnaireCategory(str, Enum):
    # Updated slugs
    DP_WALLET_SCREENER = "annual_insurance_survey_dp_wallet_screener"
    DP_WALLET_SURVEY = "annual_insurance_survey_dp_wallet_survey"
    DP_WALLET_SURVEY_OHIO = "annual_insurance_survey_dp_wallet_survey_ohio"
    DP_WALLET_SURVEY_AMAZON = "annual_insurance_survey_dp_wallet_survey_amazon"
    TRAD_WALLET_HDHP_SURVEY = "annual_insurance_survey_trad_wallet_hdhp_survey"


ORG_ANNUAL_QUESTIONNAIRE_CATEGORY_DICT: dict[int, AnnualQuestionnaireCategory] = {
    ORG_ID_AMAZON: AnnualQuestionnaireCategory.DP_WALLET_SURVEY_AMAZON,  # AMAZON
    ORG_ID_OHIO: AnnualQuestionnaireCategory.DP_WALLET_SURVEY_OHIO,  # OHIO
}


def is_questionnaire_needed_for_wallet_expense_type(
    wallet: ReimbursementWallet,
) -> bool:
    if wallet.primary_expense_type not in [
        ReimbursementRequestExpenseTypes.FERTILITY,
        ReimbursementRequestExpenseTypes.PRESERVATION,
        ReimbursementRequestExpenseTypes.MATERNITY,
        ReimbursementRequestExpenseTypes.MENOPAUSE,
    ]:
        log.info(
            "Wallet primary expense type is not one of the categories that needs the survey.",
            wallet_id=str(wallet.id),
            primary_expense_type=wallet.primary_expense_type,
        )
        return False
    return True


@tracer.wrap()
def handle_survey_response_for_hdhp(
    user_id: int,
    wallet: ReimbursementWallet,
    survey_response: dict,
    survey_year: int,
    reimbursement_plan_integration_enabled: bool = True,
    questionnaire_type: QuestionnaireType = QuestionnaireType.LEGACY,
) -> tuple[str, int]:
    """
    Processes and persists the survey response in the db (if successfully processed).
    :param survey_year:
    :type survey_year:
    :param user_id: The current user.
    :param wallet: The current wallet.
    :param survey_response: The survey response submitted by the UI.
    :param reimbursement_plan_integration_enabled: Set to true to create reimbursement plans and alegeus entries.
    :param questionnaire_type: The questionnaire type
    :return: Tuple of status message and status code
    """
    # check that the response is well-formed
    if not _validate_survey_response(survey_response):
        return "Request body does not match schema.", 404

    answers = survey_response["answers"]
    wallet_id = wallet.id
    questionnaire_resp = AnnualInsuranceQuestionnaireResponse(
        wallet_id=wallet_id,
        questionnaire_id=survey_response["id"],
        user_response_json=json.dumps(answers),
        submitting_user_id=user_id,
        sync_status=AnnualQuestionnaireSyncStatus.RESPONSE_RECORDED,
        sync_attempt_at=None,
        survey_year=survey_year,
        questionnaire_type=questionnaire_type,
    )
    try:
        connection.db.session.add(questionnaire_resp)
        connection.db.session.commit()
        log.info(
            "Questionnaire response for wallet persisted to the table.",
            wallet_id=str(wallet_id),
            user_id=str(user_id),
            questionnaire_resp_uuid=questionnaire_resp.uuid,
            survey_year=survey_year,
            alegeus_integration_enabled=reimbursement_plan_integration_enabled,
        )
    except IntegrityError:
        log.info(
            "Attempting to add a duplicate entry for wallet to the table.",
            wallet_id=str(wallet_id),
            user_id=str(user_id),
            questionnaire_resp_uuid=questionnaire_resp.uuid,
            survey_year=survey_year,
            reason=format_exc(),
        )
        connection.db.session.rollback()
        return "User has already completed this questionnaire.", 409
    if reimbursement_plan_integration_enabled:
        _insurance_integration(wallet, questionnaire_resp, answers)
    return "Response Accepted.", 200


def _load_contentful_survey(
    category: AnnualQuestionnaireCategory, user_id: int
) -> dict:
    log.info(f"Querying hdc with user_id: {user_id}")

    # pass locale info to hdc to return results in the correct language
    locale = get_locale()
    locale_header = get_locale_identifier((locale.language, locale.territory))

    response = make_hdc_request(
        url=f"/assessments/{category}",
        params={"user_id": user_id},
        extra_headers={
            "X-Maven-User-ID": str(user_id),
            CUSTOM_LOCALE_HEADER: locale_header,
        },
        method="GET",
    )
    if not response or response.status_code != 200:
        log.error(f"Querying hdc with user_id: {user_id} failed.")
        raise Exception(
            "Call to HDC for Annual Insurance Questionnaire failed: "  # type: ignore[attr-defined] # "Response" has no attribute "content"
            f"{response.content if response else 'Unknown Error'}"  # type: ignore[attr-defined] # "Response" has no attribute "content"
        )

    return response.json()


def _to_return_dict(
    contentful_dict: dict,
) -> dict:
    to_return = {
        "id": contentful_dict["id"],
        "title": contentful_dict["title"],
        "body": contentful_dict["questions"][0]["body"],
        "expandableDetails": {
            "header": contentful_dict["questions"][1]["body"],
            "content": contentful_dict["questions"][1]["microcopy"],
        },
        "questions": [],
    }

    questions = contentful_dict["questions"][2:]
    for question in questions:
        op_question = {
            "id": question["slug"],
            "text": question["body"],
            "options": [],
        }

        # being cautious here
        for option in question.get("options", []):
            if option["label"] and option["value"]:
                op_question["options"].append(
                    {"text": option["label"], "value": option["value"]}
                )

        to_return["questions"].append(op_question)

    return to_return


def _validate_survey_response(survey_response: dict) -> bool:
    # TODO add validation against the survey schema in contentful
    return {"id", "answers"}.issubset(survey_response.keys())


@tracer.wrap()
def _insurance_integration(
    wallet: ReimbursementWallet,
    questionnaire_resp: AnnualInsuranceQuestionnaireResponse,
    answers: dict,
) -> None:
    log.info(
        "Async processing questionnaire data for insurance",
        wallet_id=str(questionnaire_resp.wallet_id),
        response_id=questionnaire_resp.uuid,
    )
    metric_name = (
        "wallet.services.annual_questionnaire_lib.submit_async_processing_questionnaire"
    )
    stats.increment(
        metric_name=metric_name,
        pod_name=stats.PodNames.BENEFITS_EXP,
    )

    hdhp_resp = process_traditional_survey_response_json(
        questionnaire_resp.user_response_json
    )
    questionnaire_data = AnnualInsuranceQuestionnaireHDHPData(
        survey_responder_has_hdhp=hdhp_resp.self_hdhp,
        partner_has_hdhp=hdhp_resp.partner_hdhp,
    )

    if not hdhp_resp.self_hdhp and not hdhp_resp.partner_hdhp:
        log.info(
            "HDHP plan not needed per questionnaire response. Skipping RQ spawn.",
            wallet_id=str(questionnaire_resp.wallet_id),
            response_uuid=questionnaire_resp.uuid,
            response_id=str(questionnaire_resp.id),
            plan_year=questionnaire_resp.survey_year,
        )
        _update_questionnaire_status(
            questionnaire_resp,
            AnnualQuestionnaireSyncStatus.HDHP_REIMBURSEMENT_PLAN_NOT_NEEDED,
        )
        return

    ros = wallet.reimbursement_organization_settings
    is_fdc = not ros.deductible_accumulation_enabled and ros.first_dollar_coverage
    log.info(
        "Async processing questionnaire data for insurance in new persistence mode",
        wallet_id=str(questionnaire_resp.wallet_id),
        response_uuid=questionnaire_resp.uuid,
        hdhp_resp=hdhp_resp,
        questionnaire_data=questionnaire_data,
        plan_year=questionnaire_resp.survey_year,
        ros_organization_id=str(ros.organization_id),
        ros_direct_payment_enabled=ros.direct_payment_enabled,
        ros_deductible_accumulation_enabled=ros.deductible_accumulation_enabled,
        ros_first_dollar_coverage=ros.first_dollar_coverage,
        legacy_mode=False,
        is_fdc=is_fdc,
    )
    stats.increment(
        metric_name=metric_name,
        pod_name=stats.PodNames.BENEFITS_EXP,
    )
    _update_questionnaire_status(
        questionnaire_resp,
        AnnualQuestionnaireSyncStatus.ASYNCH_PROCESSING_INITIATED,
    )
    process_annual_questionnaire.delay(
        wallet_id=wallet.id,
        questionnaire_uuid=questionnaire_resp.uuid,
        questionnaire_data=questionnaire_data,
        plan_year=questionnaire_resp.survey_year,
        is_legacy_mode=False,
    )


def _update_questionnaire_status(
    questionnaire_resp: AnnualInsuranceQuestionnaireResponse,
    status: AnnualQuestionnaireSyncStatus,
) -> None:
    questionnaire_resp.sync_status = status
    questionnaire_resp.modified_at = datetime.now(timezone.utc)
    connection.db.session.commit()


def is_questionnaire_needed_for_user_and_wallet(
    user: User, wallet: ReimbursementWallet
) -> bool:
    """
    I'm just a user looking at a wallet asking if a questionnaire needs to be answered.
    :param user: The user
    :param wallet: The wallet (which can have multiple users)
    :return: True if all conditions are satisfied. False otherwise
    a survey
    """
    target_date = datetime.now(timezone.utc).date()
    log.info(
        "Checking if the questionnaire is needed for wallet and user (single year).",
        user_id=str(user.id),
        wallet_id=str(wallet.id),
        target_date=str(target_date),
    )

    to_return = _check_if_survey_needed_for_target_date(user, wallet, target_date)
    log.info(
        "Questionnaire needed for wallet and user (single year).",
        user_id=str(user.id),
        wallet_id=str(wallet.id),
        survey_needed=to_return,
    )
    return to_return


def is_any_questionnaire_needed_for_user_and_wallet(
    user: User, wallet: ReimbursementWallet
) -> bool:
    """
    Does this wallet, this org and this wallet expense type need the questionnaire answered for either the current year
    or the next one?
    :param user: The user
    :param wallet:
    :return: True if all conditions are satisfied. False otherwise
    a survey
    """
    current_date = datetime.now(timezone.utc).date()
    # Check the plan for a date MAX_SURVEY_DAYS_IN_ADVANCE from today. This is the nearest day out from today that we
    # want to ask a survey for, I.e if the plan changes MAX_SURVEY_DAYS_IN_ADVANCE +1 days from today we do not want to
    # launch a survey.
    potential_new_plan_date = current_date + relativedelta(
        days=MAX_SURVEY_DAYS_IN_ADVANCE
    )
    log.info(
        "Checking if the questionnaire is needed for wallet and user (multiple years).",
        user_id=str(user.id),
        wallet_id=str(wallet.id),
        current_date=current_date,
        potential_new_plan_date=potential_new_plan_date,
    )
    to_return = _check_if_survey_needed_for_target_date(
        user, wallet, current_date
    ) or _check_if_survey_needed_for_target_date(user, wallet, potential_new_plan_date)

    log.info(
        "Questionnaire needed for wallet and user (multiple years).",
        user_id=str(user.id),
        wallet_id=str(wallet.id),
        survey_needed=to_return,
    )
    return to_return


def _check_if_survey_needed_for_target_date(
    user: User, wallet: ReimbursementWallet, target_date: date
) -> bool:
    plan_year = get_plan_year_if_survey_needed_for_target_date(
        user, wallet, target_date
    )
    to_return = plan_year is not None
    log.info(
        "Survey is needed?",
        user_id=str(user.id),
        wallet_id=str(wallet.id),
        target_date=str(target_date),
        plan_year=plan_year,
        survey_needed=to_return,
    )
    return to_return


def get_plan_year_if_survey_needed_for_target_date(
    user: User, wallet: ReimbursementWallet, target_date: date
) -> int | None:
    plan_start_date = _get_plan_start_date_if_survey_needed_for_target_date(
        user, wallet, target_date
    )
    return plan_start_date.year if plan_start_date else None


def _get_plan_start_date_if_survey_needed_for_target_date(
    user: User, wallet: ReimbursementWallet, target_date: date
) -> date | None:

    survey_needed = True
    reason = ""
    plan_start_date = None
    # check if wallet state is not RUNOUT/QUALIFIED
    if wallet.state not in {WalletState.RUNOUT, WalletState.QUALIFIED}:
        reason = "Wallet state is not RUNOUT/QUALIFIED."
        survey_needed = False

    # check if the wallet's primary expense type is medical -
    if survey_needed and not _wallet_has_medical_primary_expense_type(wallet):
        reason = "Wallet does not have medical primary expense type."
        survey_needed = False

    # check if a member health/reimbursement plan already exists for the target_date
    if survey_needed and _plan_already_exists(user, wallet, target_date):
        reason = "Member Health Plan/HDHP Wallet Reimbursement Plan already exists."
        survey_needed = False

    # get the plan start date
    if survey_needed and not (
        plan_start_date := _get_plan_start_date(wallet, target_date)
    ):
        reason = "No plan year found for wallet (Employer Health Plan/HDHP Reimbursement Plan missing for target date)."
        survey_needed = False

    # check if survey has been taken for the plan year
    if survey_needed and has_survey_been_taken(
        user_id=user.id, wallet_id=wallet.id, survey_year=plan_start_date.year
    ):
        reason = "Survey has already been taken."
        survey_needed = False

    if survey_needed:
        log.info(
            "Survey is needed, and plan_year found.",
            user_id=str(user.id),
            wallet_id=str(wallet.id),
            target_date=str(target_date),
            plan_start_date=plan_start_date,
            plan_year=plan_start_date.year,
        )
        return plan_start_date
    else:
        log.info(
            "Survey not needed.",
            reason=reason,
            user_id=str(user.id),
            wallet_id=str(wallet.id),
            wallet_state=str(wallet.state),
            target_date=str(target_date),
            plan_start_date=plan_start_date,
        )
    return None


def _wallet_has_medical_primary_expense_type(wallet: ReimbursementWallet) -> bool:
    to_return = wallet.primary_expense_type in MEDICAL_EXPENSE_TYPES
    log.info(
        "Primary expense type is medical?",
        wallet_id=str(wallet.id),
        primary_expense_type=str(wallet.primary_expense_type),
        is_medical_expense_type=to_return,
    )
    return to_return


def _plan_already_exists(
    user: User, wallet: ReimbursementWallet, target_date: date
) -> bool:
    if _use_dp_deductible_accumulation_flow(wallet):
        hpr = HealthPlanRepository(connection.db.session)
        mhp = hpr.get_member_plan_by_wallet_and_member_id(
            member_id=user.id, wallet_id=wallet.id, effective_date=target_date
        )
        if mhp:
            log.info(
                "Found member health plan.",
                member_id=str(user.id),
                wallet_id=str(wallet.id),
                effective_date=str(target_date),
                member_health_plan_id=str(mhp.id),
            )
            return True
        else:
            log.info(
                "No member health plan found.",
                member_id=str(user.id),
                wallet_id=str(wallet.id),
                effective_date=str(target_date),
            )
            return False
    else:
        from wallet.utils.annual_questionnaire.utils import (
            check_if_hdhp_reimbursement_plan_exists_for_wallet_on_date,
        )

        to_ret = check_if_hdhp_reimbursement_plan_exists_for_wallet_on_date(
            wallet, target_date
        )
        log.info(
            "Checked if reimbursement plan exists for wallet on date",
            wallet_id=str(wallet.id),
            effective_date=str(target_date),
            reimbursement_plan_exists=to_ret,
        )
        return to_ret


def _get_plan_start_date(wallet: ReimbursementWallet, target_date: date) -> date | None:
    if _use_dp_deductible_accumulation_flow(wallet):
        plan_start_date = _get_plan_start_date_for_dp_wallet(wallet, target_date)
    else:
        plan_start_date = _get_plan_start_date_for_trad_or_fdc_wallet(
            wallet, target_date
        )
    return plan_start_date


def _get_plan_start_date_from_plan_year(
    wallet: ReimbursementWallet, plan_year: int
) -> date | None:
    if _use_dp_deductible_accumulation_flow(wallet):
        plan_start_date = _get_plan_start_date_from_plan_year_for_dp_wallet(
            wallet, plan_year
        )
    else:
        plan_start_date = _get_plan_start_date_from_plan_year_for_trad_or_fdc_wallet(
            wallet, plan_year
        )
    return plan_start_date


# TODO - move the query to HealthPlanRepository
def _get_plan_start_date_for_dp_wallet(
    wallet: ReimbursementWallet, target_date: date
) -> date | None:
    # get the org
    organization_id = wallet.reimbursement_organization_settings.organization_id
    log.info(
        "Getting plan start date for DP wallet.",
        wallet_id=str(wallet.id),
        target_date=str(target_date),
        organization_id=str(organization_id),
    )

    # get the employer health plans for all ros-es for this org. The DB represents the linkage between employer plan and
    # ROS as 1:1. This is inaccurate since operations treat this as 1:n and the ROS id stamped on the employer plan is
    # stamped arbitrarily. All the ROS's linked to the emp plan do belong to the same org.
    results = (
        connection.db.session.query(distinct(EmployerHealthPlan.start_date))
        .join(
            ReimbursementOrganizationSettings,
            EmployerHealthPlan.reimbursement_org_settings_id
            == ReimbursementOrganizationSettings.id,
        )
        .filter(
            ReimbursementOrganizationSettings.organization_id == organization_id,
            target_date >= EmployerHealthPlan.start_date,
            target_date <= EmployerHealthPlan.end_date,
        )
        .all()
    )
    to_return = _get_plan_start_date_from_results(organization_id, wallet, results)

    return to_return


# TODO - move the query to HealthPlanRepository
def _get_plan_start_date_from_plan_year_for_dp_wallet(
    wallet: ReimbursementWallet, plan_year: int
) -> date | None:
    # get the org
    organization_id = wallet.reimbursement_organization_settings.organization_id
    log.info(
        "Getting plan start_date for DP wallet from plan year.",
        wallet_id=str(wallet.id),
        plan_year=plan_year,
        organization_id=str(organization_id),
    )
    # get the employer health plans for all ros-es for this org. The DB represents the linkage between employer plan and
    # ROS as 1:1. This is inaccurate since operations treat this as 1:n and the ROS id stamped on the employer plan is
    # stamped arbitrarily. All the ROS's linked to the emp plan do belong to the same org.
    results = (
        connection.db.session.query(distinct(EmployerHealthPlan.start_date))
        .join(
            ReimbursementOrganizationSettings,
            EmployerHealthPlan.reimbursement_org_settings_id
            == ReimbursementOrganizationSettings.id,
        )
        .filter(
            ReimbursementOrganizationSettings.organization_id == organization_id,
            extract("year", EmployerHealthPlan.start_date) == plan_year,
        )
        .all()
    )
    to_return = _get_plan_start_date_from_results(organization_id, wallet, results)
    return to_return


def _get_plan_start_date_for_trad_or_fdc_wallet(
    wallet: ReimbursementWallet, target_date: date
) -> date | None:
    # Trad wallets will not have member health plans.so get them off the HDHP reimbursement plan.
    # FDC wallets may or may not have a member health plan - but their org must have an HDHP reimbursement plan
    # For traditional andFDC , only HDHP information is needed and so check that they have an HDHP plan.
    # The reimbursement plan table is badly abused - HDHP plans are assumed to apply at the org level but reimbursement
    # plans are applied by ops at the ROS level.
    # For this reason we will pull reimbursement plans based on org id and flag if there are start or end date
    # discrepancies.
    ros = wallet.reimbursement_organization_settings
    org_id = ros.organization_id
    # get all the distinct reimbursement plan ranges for this org id. Assuming here that plan years for ROS's in an org
    # are the same - e.g. all 2024 plans start on 1/1/24, and there isn't an outlier that starts on 3/1
    log.info(
        "Getting plan start date for TRAD/FDC wallet.",
        wallet_id=str(wallet.id),
        target_date=str(target_date),
        organization_id=org_id,
        direct_payment_enabled=ros.direct_payment_enabled,
        deductible_accumulation_enabled=ros.deductible_accumulation_enabled,
        first_dollar_coverage=ros.first_dollar_coverage,
    )
    results = (
        connection.db.session.query(distinct(ReimbursementPlan.start_date))
        .filter(
            ReimbursementPlan.organization_id == org_id,
            ReimbursementPlan.start_date <= target_date,
            ReimbursementPlan.end_date >= target_date,
            ReimbursementPlan.is_hdhp,
        )
        .order_by(ReimbursementPlan.start_date)
        .all()
    )
    to_return = _get_plan_start_date_from_results(org_id, wallet, results)
    return to_return


def _get_plan_start_date_from_plan_year_for_trad_or_fdc_wallet(
    wallet: ReimbursementWallet, plan_year: int
) -> date | None:
    log.info(
        "Getting plan start date for TRAD/FDC wallet from plan_year.",
        wallet_id=str(wallet.id),
        plan_year=str(plan_year),
    )
    # Trad wallets will not have member health plans.so get them off the reimbursement plan.
    # For traditional, only HDHP information is needed and so check that they have an HDHP plan.
    # The reimbursement plan table is badly abused - HDHP plans are assumed to apply at the org level but reimbursement
    # plans are applied by ops at the ROS level.
    # For this reason we will pull reimbursement plans based on org id and flag if there are start or end date
    # discrepancies.
    org_id = wallet.reimbursement_organization_settings.organization_id
    # get all the distinct reimbursement plan ranges for this org id. Assuming here that plan years for ROS's in an org
    # are the same - e.g. all 2024 plans start on 1/1/24, and there isn't an outlier that starts on 3/1

    results = (
        connection.db.session.query(distinct(ReimbursementPlan.start_date))
        .filter(
            ReimbursementPlan.organization_id == org_id,
            extract("year", ReimbursementPlan.start_date) == plan_year,
            ReimbursementPlan.is_hdhp,
        )
        .order_by(ReimbursementPlan.start_date)
        .all()
    )
    to_return = _get_plan_start_date_from_results(org_id, wallet, results)
    return to_return


def _get_plan_start_date_from_results(
    organization_id: int, wallet: ReimbursementWallet, results: list
) -> date | None:
    plan_start_dates = [sd[0] for sd in results]
    if not plan_start_dates:
        log.warning(
            "This org has no employer plans. Unable to derive plan start date",
            organization_id=str(organization_id),
            wallet_id=str(wallet.id),
        )
        to_return = None
    else:
        if len(plan_start_dates) > 1:
            log.warning(
                "This org has overlapping employer plans for today with different start dates. Defaulting to the first",
                organization_id=str(organization_id),
                emp_plan_start_dates=plan_start_dates,
                wallet_id=str(wallet.id),
            )
        to_return = plan_start_dates.pop()
        log.info(
            "Found employer plan start date.",
            organization_id=str(organization_id),
            wallet_id=str(wallet.id),
            emp_plan_start_date=to_return,
        )
    return to_return


# TODO - move the query to HealthPlanRepository
def _get_employer_plan_from_plan_year_for_dp_wallet_if_needed(
    questionnaire_type: QuestionnaireType, wallet: ReimbursementWallet, plan_year: int
) -> list[tuple[str | None, int]]:
    if questionnaire_type != QuestionnaireType.DIRECT_PAYMENT_HEALTH_INSURANCE or (
        not wallet.reimbursement_organization_settings.direct_payment_enabled
    ):
        log.info(
            "Employer plan names not needed.",
            _wallet_id=wallet.id,
            _questionnaire_type=questionnaire_type.value,
            dp_enabled=wallet.reimbursement_organization_settings.direct_payment_enabled,
        )
        return []

    # get the org
    organization_id = wallet.reimbursement_organization_settings.organization_id
    log.info(
        "Getting employer plan names and idsr.",
        wallet_id=str(wallet.id),
        plan_year=plan_year,
        organization_id=str(organization_id),
    )
    # get the employer health plans for all ros-es for this org. The DB represents the linkage between employer plan and
    # ROS as 1:1. This is inaccurate since operations treat this as 1:n and the ROS id stamped on the employer plan is
    # stamped arbitrarily. All the ROS's linked to the emp plan do belong to the same org.
    results = (
        connection.db.session.query(EmployerHealthPlan.name, EmployerHealthPlan.id)
        .join(
            ReimbursementOrganizationSettings,
            EmployerHealthPlan.reimbursement_org_settings_id
            == ReimbursementOrganizationSettings.id,
        )
        .filter(
            ReimbursementOrganizationSettings.organization_id == organization_id,
            extract("year", EmployerHealthPlan.start_date) == plan_year,
        )
        .all()
    )
    return results


def has_survey_been_taken(user_id: int, wallet_id: int, survey_year: int) -> bool:
    exists_query = connection.db.session.query(
        exists().where(
            (AnnualInsuranceQuestionnaireResponse.wallet_id == wallet_id)
            & (AnnualInsuranceQuestionnaireResponse.survey_year == survey_year)
            & (AnnualInsuranceQuestionnaireResponse.submitting_user_id == user_id)
        )
    )

    to_return = exists_query.scalar()
    log.info(
        "Survey has been taken?",
        wallet_id=str(wallet_id),
        survey_year=survey_year,
        user_id=str(user_id),
        has_survey_been_taken=to_return,
    )
    return to_return


def create_insurance_questionnaire_dict(
    *,
    wallet: ReimbursementWallet,
    user: User,
    input_plan_year: str | None,
    previous_type: QuestionnaireType | None = None,
) -> dict:
    """
    Create the dictionary that will be returned to the client. Contains questionnaire status & questionnaire if needed.
    :param wallet:
    :param user
    :param input_plan_year:
    :param previous_type:
    :return: dict of return message and an optional survey
    """
    # TODO - for now trusting that the UI is not going to send random years. Need to change this to a more robust check.
    if input_plan_year and has_survey_been_taken(
        user_id=user.id, wallet_id=wallet.id, survey_year=int(input_plan_year)
    ):
        log.info(
            "Survey previously completed.",
            user_id=str(user.id),
            wallet_id=str(wallet.id),
            survey_year=int(input_plan_year),
        )
        return {STATUS: AnnualQuestionnaireRequestStatus.COMPLETED.value}
    if input_plan_year:
        start_date = _get_plan_start_date_from_plan_year(wallet, int(input_plan_year))
        log.info(
            "Start date derived from plan year.",
            user_id=str(user.id),
            wallet_id=str(wallet.id),
            input_plan_year=int(input_plan_year),
            start_date=start_date,
        )
    else:
        start_date = _earliest_plan_start_date_if_survey_needed_for_user_and_wallet(
            user, wallet
        )
        log.info(
            "Start date derived from user and wallet. Earliest picked.",
            user_id=str(user.id),
            wallet_id=str(wallet.id),
            start_date=start_date,
        )

    if start_date:
        start_date_str = start_date.strftime("%m/%d/%Y")
        (
            questionnaire_category,
            questionnaire_type,
        ) = get_followup_questionnaire_category_and_type(wallet, previous_type)
        survey_dict = _load_contentful_survey(questionnaire_category, user_id=user.id)
        processed_dict = _create_output_dict(
            survey_dict,
            subtext=f"Plan start date: {start_date_str}",
            plan_year=str(start_date.year),
            questionnaire_type=questionnaire_type,
            employer_plans=_get_employer_plan_from_plan_year_for_dp_wallet_if_needed(
                questionnaire_type, wallet, start_date.year
            ),
        )
        to_return = {
            STATUS: AnnualQuestionnaireRequestStatus.REQUIRED.value,
            QUESTIONNAIRE: processed_dict,
        }
        log.info(
            "Questionnaire constructed.",
            wallet_id=str(wallet.id),
            user_id=str(user.id),
            input_plan_year=input_plan_year,
            required_start_date=start_date_str,
            questionnaire_category=str(questionnaire_category),
            questionnaire_type=str(questionnaire_type),
        )
        return to_return
    else:
        log.info(
            "Unable to derive plan start date. No questionnaire constructed.",
            wallet_id=str(wallet.id),
            user_id=str(user.id),
            input_plan_year=input_plan_year,
        )
        return {STATUS: AnnualQuestionnaireRequestStatus.NOT_REQUIRED.value}


def get_followup_questionnaire_category_and_type(
    wallet: ReimbursementWallet, previous_type: QuestionnaireType | None = None
) -> tuple[AnnualQuestionnaireCategory, QuestionnaireType]:
    organization_id = wallet.reimbursement_organization_settings.organization_id
    if _use_dp_deductible_accumulation_flow(wallet):
        # if the previous survey was the screener return the followup insurance form.
        if previous_type in {
            QuestionnaireType.DIRECT_PAYMENT_HEALTH_INSURANCE_SCREENER,
        }:

            category = ORG_ANNUAL_QUESTIONNAIRE_CATEGORY_DICT.get(
                organization_id, AnnualQuestionnaireCategory.DP_WALLET_SURVEY
            )
            to_return = (category, QuestionnaireType.DIRECT_PAYMENT_HEALTH_INSURANCE)
        # if the previous survey was not the screener return the screener. e.g. previous form was 2024 survey, next form
        # is the screener for the 2025 survey
        else:
            to_return = (
                AnnualQuestionnaireCategory.DP_WALLET_SCREENER,
                QuestionnaireType.DIRECT_PAYMENT_HEALTH_INSURANCE_SCREENER,
            )
    else:
        to_return = (
            AnnualQuestionnaireCategory.TRAD_WALLET_HDHP_SURVEY,
            QuestionnaireType.DIRECT_PAYMENT_HDHP
            if wallet.reimbursement_organization_settings.direct_payment_enabled
            else QuestionnaireType.TRADITIONAL_HDHP,
        )
    log.info(
        "Got questionnaire category and type",
        wallet_id=str(wallet.id),
        previous_type=previous_type,
        organization_id=organization_id,
        questionnaire_category=str(to_return[0]),
        questionnaire_type=str(to_return[1]),
    )
    return to_return


def _earliest_plan_start_date_if_survey_needed_for_user_and_wallet(
    user: User, wallet: ReimbursementWallet
) -> date | None:
    current_date = datetime.now(timezone.utc).date()
    # Check the plan for a date MAX_SURVEY_DAYS_IN_ADVANCE from today. This is the nearest day out from today that we
    # want to ask a survey for, I.e if the plan changes MAX_SURVEY_DAYS_IN_ADVANCE +1 days from today we do not want to
    # launch a survey.
    potential_new_plan_date = current_date + relativedelta(
        days=MAX_SURVEY_DAYS_IN_ADVANCE
    )
    log.info(
        "Pulling earliest survey year if the questionnaire is needed for wallet and user (multiple years).",
        user_id=str(user.id),
        wallet_id=str(wallet.id),
        current_date=current_date,
        potential_new_plan_date=potential_new_plan_date,
    )
    to_return = _get_plan_start_date_if_survey_needed_for_target_date(
        user, wallet, current_date
    ) or _get_plan_start_date_if_survey_needed_for_target_date(
        user, wallet, potential_new_plan_date
    )

    log.info(
        "The earliest start date of a plan that needs a survey response. (None implies not needed)",
        user_id=str(user.id),
        wallet_id=str(wallet.id),
        plan_start_date=to_return,
    )
    return to_return


def _create_output_dict(
    contentful_dict: dict,
    subtext: str,
    questionnaire_type: QuestionnaireType,
    plan_year: str,
    employer_plans: list | None,
) -> dict:
    to_return = {
        "id": contentful_dict["id"],
        "title": contentful_dict["title"],
        "body": contentful_dict["questions"][0]["body"],
        "expandableDetails": {
            "header": contentful_dict["questions"][1]["body"],
            "content": contentful_dict["questions"][1]["microcopy"],
        },
        "questions": [],
        "subtext": subtext,
        "questionnaire_type": questionnaire_type.value,
        "plan_year": plan_year,
    }

    questions = contentful_dict["questions"][2:]
    for question in questions:
        op_question = {
            "id": question["slug"],
            "element_type": CONTENTFUL_WIDGET_MAPPING[question["widget_type"]],
        }
        # grouped questions
        if (
            question.get("header")
            and question.get("microcopy")
            and "group_" in question["microcopy"]
        ):
            op_question.update(
                {
                    "text": question["header"],
                    "place_holder_text": question["body"],
                    "group_number": int(question["microcopy"].split("_")[1]),
                }
            )
        else:
            op_question["text"] = question["body"]

        if question["widget_type"] in CONTENTFUL_WIDGETS_WITH_OPTIONS:
            if employer_plans and PAYER_PLAN_TITLE in question["body"]:
                # have to commit the id to string - otherwise jsonification mangles it
                op_question["options"] = [
                    {"text": ep.name or "", "value": str(ep.id)}
                    for ep in employer_plans
                ]
                log.info(
                    "Enriching employer plans for question",
                    slug=question["slug"],
                    employer_plan_options=op_question["options"],
                )
            else:
                op_question["options"] = []
                q_options = question.get("options", [])  # being cautious here
                for option in q_options:
                    if option["label"] and option["value"]:
                        op_question["options"].append(
                            {"text": option["label"], "value": option["value"]}
                        )

        to_return["questions"].append(op_question)

    return to_return


@tracer.wrap()
def handle_insurance_survey_response(
    user: User, wallet: ReimbursementWallet, survey_response: dict
) -> tuple[str | dict, int]:
    """
    Processes and persists the survey response in the db (if successfully processed).
    :param user: The current user.
    :param wallet: The current wallet.
    :param survey_response: The survey response submitted by the UI.
    :return: Tuple of status message and status code
    """
    validated, error_reason = _validate_response(survey_response)
    if not validated:
        log.error(
            "Unable to validate survey response.",
            reason=error_reason,
            user_id=str(user.id),
            wallet_id=str(wallet.id),
        )
        return f"Request body does not match schema. Reason: {error_reason}", 404

    questionnaire_type = QuestionnaireType(survey_response.get("questionnaire_type"))
    plan_year: str = survey_response.get("plan_year")
    stats.increment(
        metric_name="wallet.services.annual_questionnaire_lib.handle_insurance_survey_response.",
        pod_name=stats.PodNames.BENEFITS_EXP,
        tags=[
            f"questionnaire_type:{questionnaire_type}",
            f"plan_year: {plan_year}",
        ],
    )
    single_response_flag = survey_response.get("single_questionnaire")
    log.info(
        "Handling Survey Response",
        user_id=str(user.id),
        wallet_id=str(wallet.id),
        survey_response=survey_response,
        questionnaire_id=survey_response["id"],
        questionnaire_type=questionnaire_type.value,
        input_plan_year=plan_year,
        single_response_flag=single_response_flag,
    )

    if questionnaire_type == QuestionnaireType.DIRECT_PAYMENT_HEALTH_INSURANCE_SCREENER:
        res = _handle_screener(user, wallet, plan_year, survey_response)
    elif questionnaire_type == QuestionnaireType.DIRECT_PAYMENT_HEALTH_INSURANCE:
        res = _handle_dp_insurance_survey_response(
            user, wallet, plan_year, survey_response
        )
    elif questionnaire_type in {
        QuestionnaireType.TRADITIONAL_HDHP,
        QuestionnaireType.DIRECT_PAYMENT_HDHP,
    }:
        res = handle_survey_response_for_hdhp(
            user_id=user.id,
            wallet=wallet,
            survey_response=survey_response,
            survey_year=int(plan_year),
            reimbursement_plan_integration_enabled=True,
            questionnaire_type=questionnaire_type,
        )
    else:
        res = f"Unsupported questionnaire type :{questionnaire_type}", 409

    # if conditions are met, do not create the follow up survey.
    if (
        single_response_flag
        or res[1] != 200
        or questionnaire_type
        == QuestionnaireType.DIRECT_PAYMENT_HEALTH_INSURANCE_SCREENER  # handled in screener logic
    ):
        log.info(
            "Handling complete.",
            user_id=str(user.id),
            wallet_id=str(wallet.id),
            survey_response=survey_response,
            questionnaire_id=survey_response["id"],
            questionnaire_type=questionnaire_type.value,
            input_plan_year=plan_year,
            single_response_flag=single_response_flag,
            res=res,
        )
        return res

    next_plan_year = int(plan_year) + 1
    return _create_follow_up_survey_response(
        user, wallet, str(next_plan_year), questionnaire_type
    )


def _validate_response(survey_response: dict) -> tuple[bool, str]:
    error_reason = ""
    required = {"id", "answers", "questionnaire_type", "plan_year"}
    missing = required - survey_response.keys()
    if missing:
        error_reason = f" Keys: {missing} are missing from payload"
    if not error_reason:
        questionnaire_type_str = survey_response.get("questionnaire_type")
        try:
            _ = QuestionnaireType(questionnaire_type_str)
        except ValueError:
            error_reason = f"Questionnaire_type: {questionnaire_type_str} blank, missing or invalid."
    id_ = survey_response.get("id")
    if not error_reason and not id_:
        error_reason = "Blank id."
    answers = survey_response.get("answers")
    if not error_reason and not answers:
        error_reason = "Empty answers list."

    return not error_reason, error_reason


@tracer.wrap()
def _handle_screener(
    user: User, wallet: ReimbursementWallet, plan_year: str, survey_response: dict
) -> tuple[str | dict, int]:
    answers = survey_response["answers"]
    user_choice = answers[ANNUAL_INSURANCE_FORM_DP_WALLET_SCREENER_BRANCHING]
    stats.increment(
        metric_name="wallet.services.annual_questionnaire_lib._handle_screener.user_choice",
        pod_name=stats.PodNames.BENEFITS_EXP,
        tags=[f"user_choice:{user_choice}"],
    )

    if user_choice == "yes":
        return _create_follow_up_survey_response(
            user,
            wallet,
            plan_year,
            QuestionnaireType.DIRECT_PAYMENT_HEALTH_INSURANCE_SCREENER,
        )
    else:
        user_id = user.id
        wallet_id = wallet.id
        log.info(
            "User has responded no. Follow up surveys unnecessary for this plan year. Persisting response to DB and "
            "returning terminal screener",
            user_id=str(user_id),
            wallet_id=str(wallet_id),
            plan_year=plan_year,
            questionnaire_id=survey_response["id"],
        )
        questionnaire_resp = AnnualInsuranceQuestionnaireResponse(
            wallet_id=wallet_id,
            questionnaire_id=survey_response["id"],
            user_response_json=json.dumps(answers),
            submitting_user_id=user_id,
            sync_status=AnnualQuestionnaireSyncStatus.MEMBER_HEALTH_PLAN_NOT_NEEDED,
            sync_attempt_at=None,
            survey_year=int(plan_year),
            questionnaire_type=QuestionnaireType.DIRECT_PAYMENT_HEALTH_INSURANCE_SCREENER,
        )
        try:
            connection.db.session.add(questionnaire_resp)
            connection.db.session.commit()
            log.info(
                "Questionnaire response for wallet persisted to the table.",
                user_id=str(user_id),
                wallet_id=str(wallet_id),
                questionnaire_resp_uuid=questionnaire_resp.uuid,
            )
        except IntegrityError:
            log.info(
                "Attempting to add a duplicate entry for wallet to the table.",
                user_id=str(user_id),
                wallet_id=str(wallet_id),
                reason=format_exc(),
                questionnaire_id=survey_response["id"],
            )
            connection.db.session.rollback()
            return "User has already completed this questionnaire.", 409
        return _create_follow_up_survey_response(
            user,
            wallet,
            str(int(plan_year) + 1),
            QuestionnaireType.DIRECT_PAYMENT_HEALTH_INSURANCE_SCREENER_TERMINAL,
        )


def _create_follow_up_survey_response(
    user: User,
    wallet: ReimbursementWallet,
    plan_year: str,
    previous_questionnaire_type: QuestionnaireType,
) -> tuple[str | dict, int]:
    log.info(
        "Creating follow up survey response",
        user_id=str(user.id),
        wallet_id=str(wallet.id),
        plan_year=plan_year,
        previous_questionnaire_type=str(previous_questionnaire_type),
    )
    created_survey_dict = create_insurance_questionnaire_dict(
        wallet=wallet,
        user=user,
        input_plan_year=plan_year,
        previous_type=previous_questionnaire_type,
    )
    if created_survey_dict[STATUS] == AnnualQuestionnaireRequestStatus.REQUIRED:
        log.info("Created and returning post screen-survey")
        to_return = created_survey_dict, 201
        log.info("create follow up survey response", response=to_return)
    elif created_survey_dict[STATUS] == AnnualQuestionnaireRequestStatus.COMPLETED:
        to_return = (
            "Accepted previous questionnaire.User has already completed the follow up questionnaire.",
            200,
        )
    else:
        to_return = (
            "Accepted previous questionnaire. User does not need to complete the follow up questionnaire.",
            200,
        )

    log.info(
        "create follow up survey response",
        response_msg=to_return[0]
        if to_return[1] == 200
        else "Follow up survey payload in message (not logged)",
        response_code=to_return[1],
        follow_up_needed=to_return[1] == 201,
    )

    return to_return


@tracer.wrap()
def _handle_dp_insurance_survey_response(
    user: User, wallet: ReimbursementWallet, plan_year: str, survey_response: dict
) -> tuple[str, int]:
    log.info(
        "Handling response to DP insurance survey",
        user_id=str(user.id),
        wallet_id=str(wallet.id),
        plan_year=plan_year,
        questionnaire_id=survey_response["id"],
    )
    questionnaire_resp = AnnualInsuranceQuestionnaireResponse(
        wallet_id=wallet.id,
        questionnaire_id=survey_response["id"],
        user_response_json=json.dumps(survey_response["answers"]),
        submitting_user_id=user.id,
        sync_status=AnnualQuestionnaireSyncStatus.RESPONSE_RECORDED,
        sync_attempt_at=None,
        survey_year=plan_year,
        questionnaire_type=QuestionnaireType.DIRECT_PAYMENT_HEALTH_INSURANCE,
    )
    try:
        connection.db.session.add(questionnaire_resp)
        connection.db.session.commit()
        log.info(
            "Questionnaire response for wallet persisted to the table.",
            wallet_id=str(wallet.id),
            user_id=str(user.id),
            questionnaire_resp_uuid=questionnaire_resp.uuid,
            survey_year=plan_year,
        )
    except IntegrityError:
        log.info(
            "Attempting to add a duplicate entry for wallet to the table.",
            wallet_id=str(wallet.id),
            user_id=str(user.id),
            questionnaire_resp_uuid=questionnaire_resp.uuid,
            survey_year=plan_year,
            reason=format_exc(),
        )
        connection.db.session.rollback()
        return "User has already completed this questionnaire.", 409
    _ = process_direct_payment_insurance_response(
        questionnaire_resp, datetime.now(timezone.utc).date()
    )
    return "Response Accepted.", 200


def _use_dp_deductible_accumulation_flow(wallet: ReimbursementWallet) -> bool:
    ros = wallet.reimbursement_organization_settings
    to_return = (
        ros.direct_payment_enabled
        and ros.deductible_accumulation_enabled  # defer to deductible_accumulation_enabled
    )
    log.info(
        "Use direct_payment_flow?",
        wallet_id=str(wallet.id),
        ros_id=str(ros.id),
        direct_payment_enabled=ros.direct_payment_enabled,
        deductible_accumulation_enabled=ros.deductible_accumulation_enabled,
        first_dollar_coverage=ros.first_dollar_coverage,
        to_return=to_return,
    )
    if ros.deductible_accumulation_enabled and ros.first_dollar_coverage:
        log.warning(
            "Reimbursement org setting is set to be both deductible accumulation enabled, and first dollar "
            "coverage. This is wrong.",
            wallet_id=str(wallet.id),
            ros_id=str(ros.id),
        )
    return to_return
