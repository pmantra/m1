from __future__ import annotations

from sqlalchemy import extract
from sqlalchemy.orm.exc import MultipleResultsFound

from storage.connection import db
from utils.log import logger
from wallet.annual_insurance_questionnaire_constants import ORGID_TO_HDHP_PLAN_NAME_MAP
from wallet.models.constants import AlegeusCoverageTier
from wallet.models.models import AnnualInsuranceQuestionnaireHDHPData
from wallet.models.reimbursement import ReimbursementPlan, ReimbursementWalletPlanHDHP
from wallet.models.reimbursement_wallet import ReimbursementWallet

log = logger(__name__)


def get_hdhp_questionnaire_response(
    questionnaire_data: AnnualInsuranceQuestionnaireHDHPData,
) -> (bool, AlegeusCoverageTier | None):  # type: ignore[syntax] # Syntax error in type annotation
    wallet_user_hdhp = questionnaire_data.survey_responder_has_hdhp
    wallet_partner_hdhp = questionnaire_data.partner_has_hdhp
    coverage_type = None
    if wallet_user_hdhp and wallet_partner_hdhp:
        coverage_type = AlegeusCoverageTier.FAMILY
    elif wallet_user_hdhp or wallet_partner_hdhp:
        coverage_type = AlegeusCoverageTier.SINGLE
    return coverage_type


def create_wallet_hdhp_plan(
    wallet: ReimbursementWallet,
    coverage_tier: AlegeusCoverageTier,
    coverage_year: int,
    legacy_mode: bool,
) -> ReimbursementPlan | None:
    if legacy_mode:
        return _create_wallet_hdhp_plan_legacy_version(
            wallet, coverage_tier, coverage_year
        )
    else:
        return _create_wallet_hdhp_plan_new_version(
            wallet, coverage_tier, coverage_year
        )


def _create_wallet_hdhp_plan_legacy_version(
    wallet: ReimbursementWallet, coverage_tier: AlegeusCoverageTier, coverage_year: int
) -> ReimbursementPlan | None:
    org_id = wallet.reimbursement_organization_settings.organization_id
    org_plan_id = ORGID_TO_HDHP_PLAN_NAME_MAP.get(org_id)
    wallet_id_str = str(wallet.id)
    if org_plan_id:
        # org plan ids are of the form BLAHHDHP2024 or BLAHHDHP24
        expected_suffix = str(coverage_year % 100)
        if org_plan_id.endswith(expected_suffix):
            plan = _get_plan(org_plan_id)
            if plan:
                log.info(
                    "ReimbursementPlan found.",
                    org_plan_id=org_plan_id,
                    reimbursement_wallet_id=wallet_id_str,
                    alegeus_coverage_tier=coverage_tier,
                )
                wallet_hdhp_plan = ReimbursementWalletPlanHDHP(
                    reimbursement_plan_id=plan.id,
                    reimbursement_wallet_id=wallet_id_str,
                    alegeus_coverage_tier=coverage_tier,
                )
                db.session.add(wallet_hdhp_plan)
                db.session.commit()
                log.info(
                    "Wallet HDHP Plan created.",
                    reimbursement_wallet_id=wallet_id_str,
                    wallet_hdhp_plan_id=wallet_hdhp_plan.id,
                )
                return plan
            else:
                log.error(
                    "ReimbursementPlan not found.",
                    estimated_plan_id=org_plan_id,
                    reimbursement_wallet_id=wallet_id_str,
                    alegeus_coverage_tier=coverage_tier,
                )
        else:
            log.error(
                f"Org plan ID does not end with {expected_suffix}.",
                org_plan_id=org_plan_id,
                reimbursement_wallet_id=wallet_id_str,
            )
    else:
        log.error(
            "Org plan id was not found.",
            org_id=org_id,
            reimbursement_wallet_id=wallet_id_str,
        )
    return None


def _create_wallet_hdhp_plan_new_version(
    wallet: ReimbursementWallet, coverage_tier: AlegeusCoverageTier, plan_year: int
) -> ReimbursementPlan | None:
    wallet_id_str = str(wallet.id)
    log.info(
        "Attempting to create HDHP plan.",
        wallet_id=wallet_id_str,
        coverage_tier=coverage_tier,
        coverage_year=plan_year,
    )
    org_id = wallet.reimbursement_organization_settings.organization_id

    try:
        reimbursement_plan = (
            db.session.query(ReimbursementPlan)
            .filter(
                ReimbursementPlan.organization_id == org_id,
                extract("year", ReimbursementPlan.start_date) == plan_year,
                ReimbursementPlan.is_hdhp,
            )
            .order_by(ReimbursementPlan.start_date)
            .one_or_none()
        )
    except MultipleResultsFound:
        log.error(
            "Multiple HDHP reimbursement plans found. Cannot proceed",
            wallet_id=wallet_id_str,
            org_id=str(org_id),
            plan_year=plan_year,
        )
        return None
    if reimbursement_plan:
        log.info(
            "ReimbursementPlan found in DB.",
            reimbursement_plan_id=str(reimbursement_plan.id),
            wallet_id=wallet_id_str,
            coverage_tier=coverage_tier,
            coverage_year=plan_year,
        )
        wallet_hdhp_plan = ReimbursementWalletPlanHDHP(
            reimbursement_plan_id=reimbursement_plan.id,
            reimbursement_wallet_id=wallet_id_str,
            alegeus_coverage_tier=coverage_tier,
        )
        log.info(
            "Wallet HDHP Plan created in memory.",
            reimbursement_wallet_id=wallet_id_str,
            wallet_hdhp_plan_id=wallet_hdhp_plan.id,
        )
        db.session.add(wallet_hdhp_plan)
        db.session.commit()
        log.info(
            "Wallet HDHP Plan committed to DB.",
            reimbursement_wallet_id=wallet_id_str,
            wallet_hdhp_plan_id=str(wallet_hdhp_plan.id),
            coverage_tier=coverage_tier,
            coverage_year=plan_year,
        )
        return reimbursement_plan
    log.info(
        "ReimbursementPlan not found in DB.",
        wallet_id=wallet_id_str,
        coverage_tier=coverage_tier,
        coverage_year=plan_year,
    )
    return None


def _get_plan(org_plan_id: str) -> ReimbursementPlan:
    to_return = None
    try:
        to_return = ReimbursementPlan.query.filter_by(
            alegeus_plan_id=org_plan_id
        ).one_or_none()
        return to_return
    except MultipleResultsFound:
        log.error(
            "Found more that one plan for this org. This should never happen.",
            alegeus_plan_id=org_plan_id,
        )
    return to_return  # type: ignore[return-value] # Incompatible return value type (got "Optional[Any]", expected "ReimbursementPlan")
