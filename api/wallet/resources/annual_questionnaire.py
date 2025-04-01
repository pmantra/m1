from __future__ import annotations

from flask import request
from flask_restful import abort
from werkzeug.exceptions import BadRequest

from authn.models.user import User
from common import stats
from common.services.api import PermissionedUserResource
from direct_payment.clinic.resources.clinic_auth import ClinicAuthorizedResource
from eligibility import service as e9y_svc
from utils.log import logger
from wallet.models.reimbursement_wallet import ReimbursementWallet
from wallet.resources.common import WalletResourceMixin
from wallet.services.annual_questionnaire_lib import (
    create_insurance_questionnaire_dict,
    handle_insurance_survey_response,
    is_any_questionnaire_needed_for_user_and_wallet,
    is_questionnaire_needed_for_user_and_wallet,
)

log = logger(__name__)


class AnnualQuestionnaireResource(PermissionedUserResource, WalletResourceMixin):
    def get(self, wallet_id: int) -> dict:
        log.info(
            "Annual insurance questionnaire requested for wallet ",
            wallet_id=str(wallet_id),
        )
        wallet = self._get_wallet_if_allowed(wallet_id)
        log.info("Wallet loaded for get questionnaire.", wallet_id=str(wallet_id))
        to_return = create_insurance_questionnaire_dict(
            wallet=wallet,
            user=self.user,
            input_plan_year=request.args.get("plan_year"),
        )
        return to_return

    def post(self, wallet_id: int) -> tuple[str | dict, int]:
        log.info(
            "Annual insurance questionnaire response posted for wallet ",
            wallet_id=str(wallet_id),
        )
        # check that the user has access to this wallet
        wallet = self._get_wallet_if_allowed(wallet_id)
        log.info("Wallet loaded for post questionnaire.", wallet_id=str(wallet_id))
        survey_response = request.json if request.is_json else None
        to_return = handle_insurance_survey_response(self.user, wallet, survey_response)
        log.info("Handled insurance survey.", response=to_return)
        return to_return

    def _get_wallet_if_allowed(self, wallet_id: int) -> ReimbursementWallet:
        wallet = self._wallet_or_404(self.user, wallet_id)
        if wallet and not e9y_svc.EnterpriseVerificationService().get_verification_for_user_and_org(
            user_id=self.user.id,
            organization_id=wallet.reimbursement_organization_settings.organization_id,
        ):
            abort(403, message="Not Authorized for Wallet")
        return wallet


class AnnualQuestionnaireNeededResource(PermissionedUserResource, WalletResourceMixin):
    def load_wallet_after_user_and_wallet_checks(
        self, wallet_id: int
    ) -> ReimbursementWallet | None:

        try:
            wallet = self._wallet_or_404(self.user, wallet_id)
            if not e9y_svc.EnterpriseVerificationService().get_verification_for_user_and_org(
                user_id=self.user.id,
                organization_id=wallet.reimbursement_organization_settings.organization_id,
            ):
                log.info("User failed e9y verification.", user_id=str(self.user.id))
                return None
            else:
                log.info(
                    "Found Wallet.", user_id=str(self.user.id), wallet_id=str(wallet_id)
                )
                return wallet
        except Exception:
            log.info("User does not have wallet.", uuser_id=str(self.user.id))
            return None

    def get(self, wallet_id: int) -> dict[str, bool]:
        log.info(
            "Annual insurance questionnaire needed requested for wallet.",
            wallet_id=str(wallet_id),
        )
        wallet = self.load_wallet_after_user_and_wallet_checks(wallet_id)
        if not wallet:
            to_return = {"needs_survey": False, "needs_any_survey": False}
            log.info(
                "Wallet not found. No surveys needed.",
                wallet_id=str(wallet_id),
                needs_survey=to_return,
            )
            return to_return

        needs_survey = _is_questionnaire_needed(self.user, wallet)
        flag_str = request.args.get("any_survey", "False")
        any_survey_enabled = flag_str and flag_str.lower() in {"true", "1"}
        # if needs_survey is true and any_survey_enabled is true then needs_any_survey is trivially true
        needs_any_survey = (
            (needs_survey or _is_any_questionnaire_needed(self.user, wallet))
            if any_survey_enabled
            else False
        )
        to_return = {"needs_survey": needs_survey, "needs_any_survey": needs_any_survey}
        log.info(
            "Survey check results",
            wallet_id=str(wallet_id),
            request_args=request.args,
            any_survey_enabled=any_survey_enabled,
            result=to_return,
        )
        return to_return


class AnnualQuestionnaireNeededInClinicPortalResource(
    ClinicAuthorizedResource, WalletResourceMixin
):
    def get(self, wallet_id: int) -> dict[str, bool]:
        member_user_id = request.args.get("member_user_id")

        log.info(
            "Checking if any annual insurance questionnaire is needed for wallet and member by a clinic user.",
            clinic_user_id=str(self.user.id),
            wallet_id=str(wallet_id),
            member_id=str(member_user_id),
        )
        if not member_user_id or not member_user_id.isdigit():
            raise BadRequest("member_user_id parameter must be a valid integer")
        user = User.query.get(member_user_id)
        wallet = self._wallet_or_404(user, wallet_id)
        needs_survey = _is_questionnaire_needed(user, wallet)
        # if needs_survey is true then needs_any_survey is trivially true
        needs_any_survey = needs_survey or _is_any_questionnaire_needed(user, wallet)
        to_return = {"needs_survey": needs_survey, "needs_any_survey": needs_any_survey}
        stats.increment(
            metric_name="wallet.resources.annual_questionnaire.user_needs_to_take_survey",
            pod_name=stats.PodNames.BENEFITS_EXP,
            tags=[f"are_surveys_needed:{needs_survey or needs_any_survey }"],
        )
        log.info(
            "Checked if any annual insurance questionnaire is needed for wallet and member by a clinic user.",
            clinic_user_id=str(self.user.id),
            wallet_id=str(wallet_id),
            member_id=str(member_user_id),
            to_return=to_return,
        )
        return to_return


def _is_questionnaire_needed(user: User, wallet: ReimbursementWallet) -> bool:
    """
    Returns true if the survey needs to be filled for the current year.
    :param wallet: The users wallet
    :return: True id the survey is needed. False otherwise.
    """
    return is_questionnaire_needed_for_user_and_wallet(user, wallet)


def _is_any_questionnaire_needed(user: User, wallet: ReimbursementWallet) -> bool:
    """
    Returns true if the survey needs to be filled for any in scope year.
    The in scope years will vary based on the time of the year and the user. E.g. the next plan year will come in
    scope when the wallet's user is 30 days from the start of the next plan year
    :param wallet: The user's wallet
    :return: True if the survey is needed. False otherwise or if in legacy mode.
    """
    return is_any_questionnaire_needed_for_user_and_wallet(user, wallet)
