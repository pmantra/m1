from __future__ import annotations

from dataclasses import dataclass
from traceback import format_exc

from common import stats
from common.services.api import PermissionedUserResource
from eligibility.service import EnterpriseVerificationService
from utils.log import logger
from wallet.models.constants import AllowedMembers, WalletState, WalletUserStatus
from wallet.repository.reimbursement_wallet import (
    ReimbursementOrganizationSettings,
    ReimbursementWalletRepository,
    UserWalletAndOrgInfo,
)
from wallet.schemas.reimbursement_wallet_dashboard import (
    ReimbursementWalletDashboardSchema,
)
from wallet.services.reimbusement_wallet_dashboard import get_dashboard_cards
from wallet.utils.eligible_wallets import get_eligible_wallet_org_settings

log = logger(__name__)


@dataclass(frozen=True)
class CanApplyForWalletResult:
    can_apply_for_wallet: bool
    """Whether the user can apply for the wallet."""
    show_prompt_to_ask_for_invitation: bool
    """
    Whether to show the user a prompt to ask his/her partner for an invitation.
    This can only be TRUE if the wallet's allowed_members is SHAREABLE.
    """


def can_apply_for_wallet(
    user_id: int,
    evs: EnterpriseVerificationService | None = None,
    user_reimb_org_settings_list: list[ReimbursementOrganizationSettings] | None = None,
) -> CanApplyForWalletResult:
    to_return = True
    evs = evs or EnterpriseVerificationService()
    other_eligible_user_ids = evs.get_other_user_ids_in_family(user_id=user_id)
    log.info(
        "Checking if user can apply for a wallet.",
        user_id=user_id,
        other_user_ids_in_family=other_eligible_user_ids,
    )
    # If the user's reimbursement org settings list hasn't already been
    # provided by the caller, then we need to call it here.
    # First, check the Reimbursement Organization Settings that the user
    if user_reimb_org_settings_list is None:
        try:
            user_reimb_org_settings_list = _get_roses_from_eligibility(
                user_id, e9y_service=evs
            )
        except Exception as e:
            log.exception(
                "Unable to infer ROSids from eligibility",
                user_id=user_id,
                exception=str(e),
                reason=format_exc(),
            )
            return CanApplyForWalletResult(False, False)

    # In practice, this should always be a list of length 1.
    if len(user_reimb_org_settings_list) > 1:
        log.warn(
            "Multiple possible ReimbursementOrgSettings",
            ros_ids=", ".join(str(ros.id) for ros in user_reimb_org_settings_list),
            user_id=str(user_id),
        )
    elif len(user_reimb_org_settings_list) == 0:
        log.warn(
            "No ReimbursementOrgSettings",
            user_id=str(user_id),
        )
        return CanApplyForWalletResult(False, False)
    reimb_org_setting = user_reimb_org_settings_list[0]
    log.info(
        "Found ReimbursementOrganizationSettings for user",
        user_id=str(user_id),
        reimbursement_organization_settings_id=f'"{reimb_org_setting.id}"',
    )
    linked_rows: list[UserWalletAndOrgInfo]
    if other_eligible_user_ids:
        linked_rows = (
            ReimbursementWalletRepository().get_user_wallet_and_org_info_for_user_ids(
                other_eligible_user_ids
            )
        )
    else:
        linked_rows = []

    # Next, we will perform checks based on the allowed_members of the ROS.

    # Check whether the user shares eligibility with someone who
    # is an ACTIVE RWU of a PENDING or QUALIFIED wallet.
    # If so, then we return show_apply_for_wallet as False
    # in order to prompt the user to request an invitation from
    # their partner.
    if reimb_org_setting.allowed_members in (
        AllowedMembers.SINGLE_ANY_USER,
        AllowedMembers.SHAREABLE,
    ):
        # SINGLE_ANY_USER has no Share A Wallet support.
        # If there is any ACTIVE or PENDING wallet
        # for anyone in who shares the eligibility, then we prevent the user
        # from applying.

        # SHAREABLE has Share A Wallet support. If there is any ACTIVE or PENDING wallet
        # for anyone in who shares the eligibility, then we prevent the user
        # from applying and show the prompt for the user to request an invitation.
        # Otherwise, we allow the user to apply.
        log_potential_sharability_discrepancy(
            linked_rows=linked_rows,
            user_id=user_id,
            user_ros_allowed_members=reimb_org_setting.allowed_members,  # type: ignore
            user_ros_id=reimb_org_setting.id,
        )
        can_apply = not any_member_has_active_or_pending_wallet(linked_rows)
        show_sharing_prompt = (
            reimb_org_setting.allowed_members == AllowedMembers.SHAREABLE
        ) and (not can_apply)
        log.info(
            "Can Apply for Wallet result",
            can_apply=can_apply,
            show_sharing_prompt=show_sharing_prompt,
            user_id=str(user_id),
        )
        return CanApplyForWalletResult(
            can_apply_for_wallet=can_apply,
            show_prompt_to_ask_for_invitation=show_sharing_prompt,
        )

    # If none of the above applies, then the user has eligibility which supports
    # user-level wallets. can_apply_for_wallet is preceded by a check for whether
    # the user has a wallet, so we know at this point that the user DOES NOT have a wallet.

    # The code below operates on the assumption that a user can be linked to one or more ROS ids - since the e9y
    # api returns a list. In practice, a user should be linked to only one ROS if this is a subpop based org.
    # If this is a non subpop based org with multiple ROS-es (so non MMB) - it will only be single_user or
    # single_employee, so an intersection between the user ROS and family ROS should disqualify them.
    # Specifically for PWC - the family members of employees in SINGLE_EMPLOYEE ROS will be in a different subpop and
    # so the family members will be not be blocked/
    if other_eligible_user_ids:
        other_eligible_user_ids = list(other_eligible_user_ids)
        stats.increment(
            metric_name="wallet.resources.reimbursement_wallet_dashboard._can_apply_for_wallet__family_members_exist",
            pod_name=stats.PodNames.BENEFITS_EXP,
        )
        user_ros_ids = [ros.id for ros in user_reimb_org_settings_list]
        log.info(
            "Queried eligibility for eligible ROS's",
            user_id=user_id,
            user_ros_ids=user_ros_ids,
        )
        if not user_ros_ids:
            log.warning(
                "User cannot be linked to any ROS and is deemed ineligible to apply for a wallet.",
                user_id=user_id,
            )
            stats.increment(
                metric_name="wallet.resources.reimbursement_wallet_dashboard._can_apply_for_wallet__FALSE",
                pod_name=stats.PodNames.BENEFITS_EXP,
            )
            return CanApplyForWalletResult(False, False)
        log.info(
            "Computed linked rows for family members with wallets.",
            other_eligible_user_ids=other_eligible_user_ids,
            linked_rows_cnt=len(linked_rows),
            linked_rows=linked_rows,
        )
        if linked_rows:
            stats.increment(
                metric_name="wallet.resources.reimbursement_wallet_dashboard._can_apply_for_wallet__family_members_have_wallet",
                pod_name=stats.PodNames.BENEFITS_EXP,
            )
        # This is checking the verification
        for row in linked_rows:
            msg = ""
            partner_user_id = row.user_id
            partner_user_type = row.user_type
            partner_ros_allowed_members = AllowedMembers(row.ros_allowed_members)
            partner_ros_id = row.ros_id
            # Here we check for values of allowed_members on an ROS that prevent anyone else in the household
            # from having a wallet.
            if partner_ros_allowed_members in (
                # Can't apply if someone in the household has a shareable wallet
                AllowedMembers.SHAREABLE,
                # Can't apply if the household is limited to 1 wallet
                AllowedMembers.SINGLE_ANY_USER,
            ):
                to_return = False
                msg = (
                    "Another member of the household belongs to a "
                    "reimbursement org setting that either enforces shared "
                    "wallets, or enforces a single wallet per household."
                )
            # If the previous check passed, check if the partners has the ROS as (one of) the users' - and if so
            # does the ROS prohibit multiple members
            elif partner_ros_id in user_ros_ids and partner_ros_allowed_members in (
                AllowedMembers.SINGLE_DEPENDENT_ONLY,
                AllowedMembers.SINGLE_EMPLOYEE_ONLY,
            ):
                to_return = False
                msg = (
                    "Another member of the household belongs to the same "
                    "reimbursement org setting as the user, and this "
                    "reimbursement org setting allows the ownership of a "
                    "wallet by only one household member."
                )
            if not to_return:
                log.info(
                    "User cannot apply for wallet.",
                    detailed_message=msg,
                    user_id=user_id,
                    user_ros_ids=user_ros_ids,
                    partener_user_id=partner_user_id,
                    partner_ros_id=str(partner_ros_id),
                    partner_ros_allowed_members=partner_ros_allowed_members,
                    partner_user_type=partner_user_type,
                    partner_allowed_members=partner_ros_allowed_members,
                )
                stats.increment(
                    metric_name="wallet.resources.reimbursement_wallet_dashboard._can_apply_for_wallet__FALSE",
                    pod_name=stats.PodNames.BENEFITS_EXP,
                )
                return CanApplyForWalletResult(False, False)
    log.info(
        "User can apply for wallet.",
        user_id=user_id,
        can_apply=to_return,
        show_prompt_to_ask_for_invitation=False,
    )
    stats.increment(
        metric_name="wallet.resources.reimbursement_wallet_dashboard._can_apply_for_wallet__TRUE",
        pod_name=stats.PodNames.BENEFITS_EXP,
    )
    return CanApplyForWalletResult(
        can_apply_for_wallet=to_return, show_prompt_to_ask_for_invitation=False
    )


def _get_roses_from_eligibility(
    user_id: int, e9y_service: EnterpriseVerificationService | None = None
) -> list[ReimbursementOrganizationSettings]:
    """
    Since this function is internal and called only after confirming that a qualified or pending wallet does not exist,
    we will not filter existing wallets out. get_eligible_wallet_org_settings does not account for disqualified wallets
    and filters those ros ids out when filter_out_existing_wallets is set to True.
    """
    try:
        # get the ROS-es (should be 1) associated with this user.
        roses = get_eligible_wallet_org_settings(
            user_id=user_id, e9y_svc=e9y_service, filter_out_existing_wallets=False
        )
        return roses
    except Exception as e:
        log.exception(
            "Unable to infer ROSids from eligibility",
            user_id=user_id,
            exception=str(e),
            reason=format_exc(),
        )
        return []


class ReimbursementWalletDashboardResource(PermissionedUserResource):
    def get(self) -> dict:
        wallet_dashboard_cards = get_dashboard_cards(self.user)
        data = {"data": wallet_dashboard_cards, "show_apply_for_wallet": True}
        schema = ReimbursementWalletDashboardSchema()

        wallet_repository = ReimbursementWalletRepository()
        user_has_wallet = wallet_repository.get_any_user_has_wallet([self.user.id])
        if not user_has_wallet:
            can_apply_for_wallet_result = can_apply_for_wallet(self.user.id)
            data[
                "show_apply_for_wallet"
            ] = can_apply_for_wallet_result.can_apply_for_wallet
            data[
                "show_prompt_to_ask_for_invitation"
            ] = can_apply_for_wallet_result.show_prompt_to_ask_for_invitation
        else:
            # The user already has a wallet
            data["show_apply_for_wallet"] = False
            data["show_prompt_to_ask_for_invitation"] = False
        return schema.dump(data)


def any_member_has_active_or_pending_single_user_wallet(
    linked_rows: list[UserWalletAndOrgInfo],
) -> bool:
    return any(
        info.wallet_state in (WalletState.QUALIFIED, WalletState.PENDING)
        and info.ros_allowed_members
        in (AllowedMembers.SINGLE_ANY_USER.value, AllowedMembers.SHAREABLE.value)
        for info in linked_rows
    )


def any_member_has_active_or_pending_wallet(
    linked_rows: list[UserWalletAndOrgInfo],
) -> bool:
    return any(
        info.wallet_state in (WalletState.QUALIFIED.value, WalletState.PENDING.value)
        for info in linked_rows
    )


def log_potential_sharability_discrepancy(
    linked_rows: list[UserWalletAndOrgInfo],
    user_id: int,
    user_ros_allowed_members: AllowedMembers,
    user_ros_id: int,
) -> None:
    for info in linked_rows:
        if has_single_any_user_discrepancy(
            user_ros_allowed_members, info
        ) or has_sharability_discrepancy(user_ros_allowed_members, info):
            # There is an alert on this log.
            log.info(
                "There is a discrepancy in the ROS allowed_members for members of the same household.",
                user_id=str(user_id),
                user_ros_id=f'"{user_ros_id}"',
                user_ros_allowed_members=user_ros_allowed_members.value,
                other_user_id=str(info.user_id),
                other_ros_id=f'"{info.ros_id}"',
                other_ros_allowed_members=info.ros_allowed_members,
            )


def has_single_any_user_discrepancy(
    allowed_members: AllowedMembers,
    linked_row: UserWalletAndOrgInfo,
) -> bool:
    """
    Checks whether the user has SINGLE_ANY_USER eligiblity and the other
    person in the household has SHAREABLE eligility.
    """
    return (
        (allowed_members == AllowedMembers.SINGLE_ANY_USER)
        and linked_row.wallet_state
        in (WalletState.QUALIFIED.value, WalletState.PENDING.value)
        and linked_row.ros_allowed_members == AllowedMembers.SHAREABLE.value
        and linked_row.user_status == WalletUserStatus.ACTIVE.value
    )


def has_sharability_discrepancy(
    allowed_members: AllowedMembers,
    linked_row: UserWalletAndOrgInfo,
) -> bool:
    """
    Checks whether the user has SHAREABLE eligiblity and the other
    person in the household does not have SHAREABLE eligility.
    """
    return (
        (allowed_members == AllowedMembers.SHAREABLE)
        and linked_row.wallet_state
        in (WalletState.QUALIFIED.value, WalletState.PENDING.value)
        and linked_row.ros_allowed_members != AllowedMembers.SHAREABLE.value
        and linked_row.user_status == WalletUserStatus.ACTIVE.value
    )
