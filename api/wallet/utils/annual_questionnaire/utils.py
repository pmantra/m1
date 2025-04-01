from __future__ import annotations

import datetime
from enum import Enum
from functools import partial
from typing import Callable, Optional

from sqlalchemy import and_, exists

from storage import connection
from utils.log import logger
from wallet.models.constants import QuestionnaireType
from wallet.models.reimbursement import ReimbursementPlan, ReimbursementWalletPlanHDHP
from wallet.models.reimbursement_organization_settings import (
    ReimbursementOrganizationSettings,
)
from wallet.models.reimbursement_wallet import ReimbursementWallet
from wallet.repository.health_plan import HealthPlanRepository
from wallet.utils.annual_questionnaire.processor import (
    process_traditional_survey_response_json,
)
from wallet.utils.annual_questionnaire.repository import (
    AnnualInsuranceResponseRepository,
)

log = logger(__name__)


class FdcHdhpCheckResults(str, Enum):
    FDC_NO = "FDC_NO"
    FDC_UNKNOWN = "FDC_UNKNOWN"
    FDC_YES_HDHP_NO = "FDC_YES_HDHP_NO"
    FDC_YES_HDHP_YES = "FDC_YES_HDHP_YES"
    FDC_YES_HDHP_UNKNOWN = "FDC_YES_HDHP_UNKNOWN"


def check_if_wallet_is_fdc_hdhp(
    wallet: ReimbursementWallet, user_id: int, effective_date: datetime.date
) -> FdcHdhpCheckResults:
    ros: ReimbursementOrganizationSettings = wallet.reimbursement_organization_settings
    log_fn = partial(_log_reason, wallet.id, user_id, effective_date, ros.id)
    log.info(
        "Checking if wallet is FDC and HDHP",
        wallet_id=str(wallet.id),
        user_id=str(user_id),
        effective_date=str(effective_date),
    )

    if not ros.direct_payment_enabled:
        log_fn(reason="Traditional wallet.", result=FdcHdhpCheckResults.FDC_NO)
        return FdcHdhpCheckResults.FDC_NO

    if not ros.first_dollar_coverage:
        log_fn(
            reason="ROS has first_dollar_coverage set to False.",
            result=FdcHdhpCheckResults.FDC_NO,
        )
        return FdcHdhpCheckResults.FDC_NO

    if ros.deductible_accumulation_enabled:
        log_fn(
            reason="Unable to make a decision when FDC and DA are both set to True.",
            result=FdcHdhpCheckResults.FDC_UNKNOWN,
        )
        return FdcHdhpCheckResults.FDC_UNKNOWN

    # deductible_accumulation_enabled and first_dollar_coverage should be mutually exclusive at the ROS level,
    # but this is not currently enforced by the DB.

    log.info("Running checks that are relevant when FDC is true and DA is False.")
    if _get_linked_employer_hp_hdhp_status_if_available(
        wallet, user_id, effective_date
    ):
        log_fn(
            reason="The wallet belongs to an FDC non-DA ROS and has a member plan linked to an employer HDHP.",
            result=FdcHdhpCheckResults.FDC_YES_HDHP_YES,
        )
        return FdcHdhpCheckResults.FDC_YES_HDHP_YES

    if check_if_hdhp_reimbursement_plan_exists_for_wallet_on_date(
        wallet=wallet, effective_date=effective_date
    ):
        log_fn(
            reason="The wallet belongs to an FDC non-DA ROS and has an associated HDHP Reimbursement Plan.",
            result=FdcHdhpCheckResults.FDC_YES_HDHP_YES,
        )
        return FdcHdhpCheckResults.FDC_YES_HDHP_YES

    if not _check_if_hdhp_exists_for_org(ros.organization_id, effective_date):
        log_fn(
            reason="There is no linked Alegeus HDHP plan for this FDC non-DA ROS's org.",
            result=FdcHdhpCheckResults.FDC_YES_HDHP_NO,
        )
        return FdcHdhpCheckResults.FDC_YES_HDHP_NO

    return _parse_response(wallet, user_id, effective_date, log_fn)


class HDHPCheckResults(str, Enum):
    HDHP_NO = "HDHP_NO"
    HDHP_YES = "HDHP_YES"
    HDHP_UNKNOWN = "HDHP_UNKNOWN"


def check_if_is_hdhp(
    wallet: ReimbursementWallet,
    user_id: int,
    effective_date: datetime.date,
    has_health_plan: Optional[bool],
) -> HDHPCheckResults:
    org_settings = wallet.reimbursement_organization_settings
    log_fn = partial(
        _log_hdhp_reason, wallet.id, user_id, effective_date, org_settings.id
    )
    if not org_settings.direct_payment_enabled:
        # Traditional Wallet
        log_fn(
            reason="This is a non-direct payment wallet which cannot be HDHP.",
            result=HDHPCheckResults.HDHP_NO,
        )
        return HDHPCheckResults.HDHP_NO

    if org_settings.deductible_accumulation_enabled:
        # Deductible Accumulation Wallet
        log_fn(
            reason="Deductible accumulation users are not treated as HDHP users.",
            result=HDHPCheckResults.HDHP_NO,
        )
        return HDHPCheckResults.HDHP_NO

    if has_health_plan and _get_linked_employer_hp_hdhp_status_if_available(
        wallet, user_id, effective_date
    ):
        # Is associated with an HDHP plan via member health plan
        log_fn(
            reason="This user has a health plan with a HDHP plan associated.",
            result=HDHPCheckResults.HDHP_YES,
        )
        return HDHPCheckResults.HDHP_YES

    if check_if_hdhp_reimbursement_plan_exists_for_wallet_on_date(
        wallet=wallet, effective_date=effective_date
    ):
        # There is an HDHP plan on the wallet
        log_fn(
            reason="There is a HDHP plan on this user's wallet, but no health plan.",
            result=HDHPCheckResults.HDHP_YES,
        )
        return HDHPCheckResults.HDHP_YES

    if not _check_if_hdhp_exists_for_org(org_settings.organization_id, effective_date):
        log_fn(
            reason="This user cannot be on a HDHP plan, as no HDHP plan is associated with their org.",
            result=HDHPCheckResults.HDHP_NO,
        )
        return HDHPCheckResults.HDHP_NO

    survey_response = _parse_response(wallet, user_id, effective_date, log_fn)
    if survey_response == FdcHdhpCheckResults.FDC_YES_HDHP_YES:
        log_fn(
            reason="Survey results indicate this user is on a HDHP plan.",
            result=HDHPCheckResults.HDHP_YES,
        )
        return HDHPCheckResults.HDHP_YES
    elif survey_response == FdcHdhpCheckResults.FDC_YES_HDHP_NO:
        log_fn(
            reason="Survey results indicate this user is not on a HDHP plan.",
            result=HDHPCheckResults.HDHP_NO,
        )
        return HDHPCheckResults.HDHP_NO
    else:
        log_fn(
            reason="Missing HDHP data associated with wallet and missing survey results.",
            result=HDHPCheckResults.HDHP_UNKNOWN,
        )
        return HDHPCheckResults.HDHP_UNKNOWN


def _parse_response(
    wallet: ReimbursementWallet,
    user_id: int,
    effective_date: datetime.date,
    log_fn: Callable,
) -> FdcHdhpCheckResults:
    log.info("Falling back to using the survey response.")
    reason = "No response found."
    if resp := AnnualInsuranceResponseRepository(
        connection.db.session
    ).get_response_for_wallet_id_member_id_year(
        wallet_id=wallet.id, user_id=user_id, plan_year=effective_date.year
    ):
        # parse the response
        if resp.questionnaire_type == QuestionnaireType.DIRECT_PAYMENT_HDHP:
            parsed_resp = process_traditional_survey_response_json(
                resp.user_response_json
            )
            is_hdhp = parsed_resp.self_hdhp or parsed_resp.partner_hdhp
            log_fn(
                reason="There is a survey response for this user in the annual questionnaire table.",
                result=(
                    FdcHdhpCheckResults.FDC_YES_HDHP_YES
                    if is_hdhp
                    else FdcHdhpCheckResults.FDC_YES_HDHP_NO
                ),
                is_hdhp=is_hdhp,
            )
            return (
                FdcHdhpCheckResults.FDC_YES_HDHP_YES
                if is_hdhp
                else FdcHdhpCheckResults.FDC_YES_HDHP_NO
            )
        else:
            reason = "The survey response linked to this user, wallet and year has the wrong questionnaire type."

    log_fn(reason=reason, result=FdcHdhpCheckResults.FDC_YES_HDHP_UNKNOWN)
    return FdcHdhpCheckResults.FDC_YES_HDHP_UNKNOWN


def _log_reason(
    wallet_id: int,
    user_id: int,
    effective_date: datetime.date,
    ros_id: int,
    reason: str,
    result: FdcHdhpCheckResults,
    is_hdhp: bool | None = None,
    warn: bool = False,
) -> None:
    log_fields = {
        "wallet_id": str(wallet_id),
        "user_id": str(user_id),
        "effective_date": str(effective_date),
        "ros_id": str(ros_id),
        "reason": reason,
        "result": result.value,
        "is_hdhp": str(is_hdhp),
    }
    fn = log.warn if warn else log.info
    fn("FDC and HDHP check on wallet", extra=log_fields)


def _log_hdhp_reason(
    wallet_id: int,
    user_id: int,
    effective_date: datetime.date,
    ros_id: int,
    reason: str,
    result: FdcHdhpCheckResults,
    is_hdhp: bool | None = None,
    warn: bool = False,
) -> None:
    log_fields = {
        "wallet_id": str(wallet_id),
        "user_id": str(user_id),
        "effective_date": str(effective_date),
        "ros_id": str(ros_id),
        "reason": reason,
        "result": result.value,
        "is_hdhp": str(is_hdhp),  # need this for _parse_response
    }
    fn = log.warn if warn else log.info
    fn("HDHP check on wallet", extra=log_fields)


def check_if_hdhp_reimbursement_plan_exists_for_wallet_on_date(
    wallet: ReimbursementWallet, effective_date: datetime.date
) -> bool:
    return connection.db.session.query(
        exists().where(
            and_(
                ReimbursementWalletPlanHDHP.reimbursement_plan_id
                == ReimbursementPlan.id,
                ReimbursementPlan.is_hdhp,
                ReimbursementPlan.start_date <= effective_date,
                ReimbursementPlan.end_date >= effective_date,
                ReimbursementWalletPlanHDHP.reimbursement_wallet_id == wallet.id,
            )
        )
    ).scalar()


def _check_if_hdhp_exists_for_org(
    organization_id: int, effective_date: datetime.date
) -> bool:
    return connection.db.session.query(
        exists().where(
            and_(
                ReimbursementPlan.is_hdhp,
                ReimbursementPlan.start_date <= effective_date,
                ReimbursementPlan.end_date >= effective_date,
                ReimbursementPlan.organization_id == organization_id,
            )
        )
    ).scalar()


def _get_linked_employer_hp_hdhp_status_if_available(
    wallet: ReimbursementWallet, user_id: int, effective_date: datetime.date
) -> bool:
    health_plan_repo = HealthPlanRepository(connection.db.session)
    ehp = health_plan_repo.get_employer_plan_by_wallet_and_member_id(
        member_id=user_id,
        wallet_id=wallet.id,
        effective_date=effective_date,
    )
    found_hdhp = bool(ehp) and ehp.is_hdhp
    return found_hdhp
