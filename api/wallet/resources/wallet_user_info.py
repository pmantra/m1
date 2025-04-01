from __future__ import annotations

from typing import List, TypedDict

from common.services.api import InternalServiceResource
from eligibility import service as e9y_service
from utils.log import logger
from wallet.models.constants import WalletState, WalletUserStatus
from wallet.models.reimbursement_organization_settings import (
    ReimbursementOrganizationSettings,
)
from wallet.repository.reimbursement_wallet import (
    ReimbursementWalletRepository,
    WalletRWUInfo,
)
from wallet.repository.wallet_user_invite import WalletUserInviteRepository
from wallet.resources.reimbursement_wallet_dashboard import can_apply_for_wallet
from wallet.resources.wallet_invitation import check_invitation
from wallet.utils.eligible_wallets import get_eligible_wallet_org_settings

log = logger(__name__)


class WalletUserInfoResponse(TypedDict):
    """Container for the WalletUserInfo GET endpoint response."""

    allow_application: bool
    reimbursement_organization_settings_id: str
    """Empty string if the id is not found."""
    existing_wallet_id: str | None
    """
    NULL if there is a higher priority error before we check this
    or if the user is not an PENDING or ACTIVE RWU.
    Otherwise, this is the string of the wallet_id that the WQS may update.
    """
    existing_wallet_state: str | None
    """
    NULL if there is a higher priority error before we check this
    or if there is no existing wallet at all.
    Otherwise, this is the string of the state of the wallet that the WQS may update.
    """
    is_share_a_wallet: bool
    """
    Whether the user must apply via the Share a Wallet workflow.
    Defaults to FALSE even when there is a higher priority error.
    """


class WalletUserInfoResource(InternalServiceResource):
    def get(self):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        """
        Returns the reimbursement_organization_settings.ids that
        a user is eligible for.
        Also, if there is a condition preventing the user from applying
        for a new wallet (e.g. the user already has a wallet), then we return that as well.

        Response:
        {
            "allow_application": bool,
            "reimbursement_organization_settings_id": str,
            "existing_wallet_id": str | None,
            "existing_wallet_state": str | None
        }
        """
        user_id = self.user.id
        invitation = WalletUserInviteRepository().get_latest_unclaimed_invite(user_id)
        potential_error = check_invitation(self.user, "", invitation)
        wallet_repo = ReimbursementWalletRepository()
        if potential_error is None:
            wallet_and_rwu = wallet_repo.get_wallet_and_rwu(
                invitation.reimbursement_wallet_id, user_id
            )
            wallet = wallet_and_rwu.wallet
            rwu = wallet_and_rwu.rwu
            if wallet is None:
                log.error(
                    "Wallet not found.",
                    invitation_id=str(invitation.id),
                    user_id=str(self.user.id),
                )
            elif wallet.state != WalletState.QUALIFIED:
                log.error(
                    "User should not be able to apply to a non-QUALIFIED wallet",
                    invitation_id=str(invitation.id),
                    wallet_id=str(wallet.id),
                    user_id=str(self.user.id),
                )
            elif rwu is not None and rwu.status != WalletUserStatus.DENIED:
                log.error(
                    "User can only reapply if the user was previously denied.",
                    invitation_id=str(invitation.id),
                    wallet_id=str(wallet.id),
                    user_id=str(self.user.id),
                )
            else:
                # This user can apply via Share a Wallet
                log.info(
                    "User can apply via Share a Wallet.",
                    user_id=str(user_id),
                    invitation_id=str(invitation.id),
                    wallet_id=str(invitation.reimbursement_wallet_id),
                )
                return (
                    WalletUserInfoResponse(
                        allow_application=True,
                        reimbursement_organization_settings_id=str(
                            wallet.reimbursement_organization_settings_id
                        ),
                        existing_wallet_id=str(wallet.id),
                        existing_wallet_state=wallet.state.value,  # type: ignore
                        is_share_a_wallet=True,
                    ),
                    200,
                )

        # We should consider DISQUALIFIED wallets in this call, so we need to make sure
        # they are not getting filtered out.
        e9y_svc = e9y_service.EnterpriseVerificationService()
        reimb_org_settings = get_eligible_wallet_org_settings(
            user_id, e9y_svc=e9y_svc, filter_out_existing_wallets=False
        )
        # In practice, this should always be a list of length 1.
        if len(reimb_org_settings) > 1:
            log.warn(
                "Wallet Auto Qualification - multiple possible ReimbursementOrgSettings",
                user_id=str(user_id),
            )
        elif len(reimb_org_settings) == 0:
            log.warn(
                "Wallet Auto Qualification -  no ReimbursementOrgSettings",
                user_id=str(user_id),
            )
            return (
                WalletUserInfoResponse(
                    allow_application=False,
                    reimbursement_organization_settings_id="",
                    existing_wallet_id=None,
                    existing_wallet_state=None,
                    is_share_a_wallet=False,
                ),
                200,
            )

        reimb_org_setting: ReimbursementOrganizationSettings = reimb_org_settings[0]
        # 1. Is the organization whitelisted for the automatic wallet survey
        # and qualification workflow?
        # This helps prevent users from attempting to take an automated survey
        # for an organization that is not whitelisted.
        log.info(
            "Found ReimbursementOrganizationSettings for user",
            user_id=str(user_id),
            reimbursement_organization_settings_id=f'"{reimb_org_setting.id}"',
        )
        # We want to get the user's current wallet data
        # If the user is already an active or pending user of a PENDING or QUALIFIED wallet, then
        # we want to prevent the user from applying for the wallet.
        # 2. Are there any existing wallets in the household?
        # Bear in mind that these wallets are restricted to the SAME reimbursement_organization_settings_id
        wallet_rwu_info_list: List[
            WalletRWUInfo
        ] = ReimbursementWalletRepository().get_wallet_rwu_info(
            [user_id], reimb_org_setting.id
        )
        wallet_info_str = ", ".join(
            f"[wallet_id: {w_rwu_info.wallet_id}, rwu_status: {w_rwu_info.rwu_status}, state: {w_rwu_info.state}]"
            for w_rwu_info in wallet_rwu_info_list
        )
        log.info(
            "Got WalletRWUInfo",
            user_id=str(user_id),
            info=wallet_info_str,
        )
        if wallet_rwu_info := get_pending_or_active_rwu(wallet_rwu_info_list):
            log.info(
                "Wallet Auto Qualification, user already has an active wallet.",
                user_id=str(self.user.id),
                organization_id=str(reimb_org_setting.organization_id),
            )
            return (
                WalletUserInfoResponse(
                    allow_application=False,
                    reimbursement_organization_settings_id=str(reimb_org_setting.id),
                    existing_wallet_id=str(wallet_rwu_info.wallet_id),
                    existing_wallet_state=str(wallet_rwu_info.state),
                    is_share_a_wallet=False,
                ),
                200,
            )
        if wallet_rwu_info := get_disqualified_rwu(wallet_rwu_info_list):
            log.info(
                "Wallet Auto Qualification, user already has a DISQUALIFIED wallet.",
                user_id=str(self.user.id),
                organization_id=str(reimb_org_setting.organization_id),
                wallet_id=f'"{wallet_rwu_info.wallet_id}"',
            )
            return (
                WalletUserInfoResponse(
                    allow_application=True,
                    reimbursement_organization_settings_id=str(reimb_org_setting.id),
                    existing_wallet_id=str(wallet_rwu_info.wallet_id),
                    existing_wallet_state=str(wallet_rwu_info.state),
                    is_share_a_wallet=False,
                ),
                200,
            )
        allow_application = can_apply_for_wallet(
            self.user.id, evs=e9y_svc, user_reimb_org_settings_list=reimb_org_settings
        ).can_apply_for_wallet
        log.info(
            "Allow application",
            user_id=str(user_id),
            allow_application=allow_application,
        )
        if not wallet_rwu_info_list:
            return (
                WalletUserInfoResponse(
                    allow_application=allow_application,
                    reimbursement_organization_settings_id=str(reimb_org_setting.id),
                    existing_wallet_id=None,
                    existing_wallet_state=None,
                    is_share_a_wallet=False,
                ),
                200,
            )
        # RUNOUT and EXPIRED states should not be possible given the eligibility check.
        if runout_or_expired := get_runout_or_expired_info(wallet_rwu_info_list):
            # If there is a runout / expired wallet with the same exact ROS,
            # then we want to know about it. This would be EXCEPTIONALLY rare.
            # We do not want to reuse these wallets.
            log.info(
                "Found eligible wallet, but it's EXPIRED / RUNOUT",
                user_id=(self.user.id),
                reimbursement_org_setting_id=f'"{reimb_org_setting}"',
                wallet_id=f'"{runout_or_expired.user_id}"',
                state=str(runout_or_expired.state),
            )
        existing_wallet_id: str | None
        existing_wallet_state: str | None
        wallet_rwu_info = get_non_runout_or_expired_info(wallet_rwu_info_list)
        if wallet_rwu_info is None:
            existing_wallet_id = None
            existing_wallet_state = None
        else:
            existing_wallet_id = str(wallet_rwu_info.wallet_id)
            existing_wallet_state = wallet_rwu_info.state
        return (
            WalletUserInfoResponse(
                allow_application=allow_application,
                reimbursement_organization_settings_id=str(reimb_org_setting.id),
                existing_wallet_id=existing_wallet_id,
                existing_wallet_state=existing_wallet_state,
                is_share_a_wallet=False,
            ),
            200,
        )


def get_pending_or_active_rwu(
    wallet_rwu_info_list: List[WalletRWUInfo],
) -> WalletRWUInfo | None:
    return next(
        (
            wallet_rwu_info
            for wallet_rwu_info in wallet_rwu_info_list
            if wallet_rwu_info.state
            in (WalletState.QUALIFIED.value, WalletState.PENDING.value)
            and wallet_rwu_info.rwu_status
            in (WalletUserStatus.PENDING.value, WalletUserStatus.ACTIVE.value)
        ),
        None,
    )


def get_runout_or_expired_info(
    wallet_rwu_info_list: List[WalletRWUInfo],
) -> WalletRWUInfo | None:
    return next(
        (
            wallet_rwu_info
            for wallet_rwu_info in wallet_rwu_info_list
            if wallet_rwu_info.state
            in (WalletState.EXPIRED.value, WalletState.RUNOUT.value)
        ),
        None,
    )


def get_non_runout_or_expired_info(
    wallet_rwu_info_list: List[WalletRWUInfo],
) -> WalletRWUInfo | None:
    return next(
        (
            wallet_rwu_info
            for wallet_rwu_info in wallet_rwu_info_list
            if wallet_rwu_info.state
            not in (WalletState.EXPIRED.value, WalletState.RUNOUT.value)
        ),
        None,
    )


def get_disqualified_rwu(
    wallet_rwu_info_list: List[WalletRWUInfo],
) -> WalletRWUInfo | None:
    """
    If a wallet is DISQUALIFIED and the associated RWU is in any status,
    then we should allow a reapplication,
    """
    return next(
        (
            wallet_rwu_info
            for wallet_rwu_info in wallet_rwu_info_list
            if wallet_rwu_info.state == WalletState.DISQUALIFIED.value
        ),
        None,
    )
