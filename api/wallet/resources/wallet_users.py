from __future__ import annotations

from dataclasses import asdict

from ddtrace import tracer
from flask_restful import abort

from authn.models.user import User
from common.services.api import PermissionedUserResource
from storage.connection import db
from utils.log import logger
from wallet.models.constants import WalletUserStatus
from wallet.models.models import WalletUser, WalletUsersGetResponse
from wallet.models.reimbursement_wallet_user import ReimbursementWalletUsers
from wallet.models.wallet_user_invite import WalletUserInvite

log = logger(__name__)


class WalletUsersResource(PermissionedUserResource):
    def get(self, wallet_id):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        """View all of the wallet users associated with a wallet."""
        # Keep in mind that User.email is a unique key.
        # This prevents most of the "duplicate" scenarios.
        wallet_user_info = (
            db.session.query(
                ReimbursementWalletUsers.user_id,
                ReimbursementWalletUsers.status,
                User.first_name,
                User.last_name,
                User.email,
            )
            .join(User, User.id == ReimbursementWalletUsers.user_id)
            .filter(
                ReimbursementWalletUsers.reimbursement_wallet_id == wallet_id,
            )
            .all()
        )

        # If the user who made the request is not authorized to access the wallet,
        # then return the 401 Unauthorized response.
        if all(self.user.id != info[0] for info in wallet_user_info):
            log.warn(
                "User tried to access a wallet without authorization.",
                user_id=self.user.id,
                reimbursement_wallet_id=wallet_id,
            )
            abort(401, message="User is not authorized to access the wallet.")

        invites = (
            db.session.query(
                WalletUserInvite,
            )
            .filter(
                WalletUserInvite.reimbursement_wallet_id == wallet_id,
            )
            .all()
        )

        # We only care about the most recent invitation for each user
        filtered_invites = get_most_recent_invite_for_each_user(invites)

        # Now you know the user is authorized to see the wallet.

        wallet_users = format_wallet_users(
            wallet_user_info, self.user.id, filtered_invites
        )
        response = WalletUsersGetResponse(users=wallet_users)

        return asdict(response)


@tracer.wrap()
def get_most_recent_invite_for_each_user(
    invites: list[WalletUserInvite],
) -> list[WalletUserInvite]:
    """
    Returns the most recently modified invitation per recipient based on the
    WalletUserInvite.modified_at field.
    """
    email_to_last_invitation: dict[str, WalletUserInvite] = {}
    for invite in invites:
        if (
            invite.email in email_to_last_invitation
            and email_to_last_invitation[invite.email].modified_at <= invite.modified_at
        ) or (invite.email not in email_to_last_invitation):
            email_to_last_invitation[invite.email] = invite
    return list(email_to_last_invitation.values())


@tracer.wrap()
def format_wallet_users(
    db_result_tuples: list,
    user_id_of_requester: int,
    invitations: list[WalletUserInvite],
) -> list[WalletUser]:
    """
    Returns a list of WalletUser objects from the database response
    db_result_tuples is a list of tuples of the form:
    (
        ReimbursementWalletUsers.user_id,
        ReimbursementWalletUsers.status,
        User.first_name,
        User.last_name
    )
    """
    # Map<WalletUserStatus, set[str] emails of users with that status>
    active_user_emails = set()
    pending_user_emails = set()
    for db_result_tuple in db_result_tuples:
        status, email = db_result_tuple[1], db_result_tuple[-1]
        if status == WalletUserStatus.ACTIVE:
            active_user_emails.add(email)
        elif status == WalletUserStatus.PENDING:
            pending_user_emails.add(email)

    result = []
    pending_or_active_rwu_emails = set()
    for user_id, status, first_name, last_name, email in db_result_tuples:
        if user_id != user_id_of_requester and status != WalletUserStatus.DENIED:
            normalized_email = email.strip().casefold()
            if status == WalletUserStatus.PENDING:
                title = normalized_email
                status_string = "Pending approval"
                pending_or_active_rwu_emails.add(normalized_email)
            elif status == WalletUserStatus.ACTIVE:
                title = f"{first_name} {last_name}"
                status_string = "Approved"
                pending_or_active_rwu_emails.add(normalized_email)
            else:
                continue
            result.append(WalletUser(title=title, status=status_string))
    for invitation in invitations:
        # We do not want to show recipients whose invitations to the
        # Maven Wallet were claimed unless there was an info mismatch.
        if invitation.claimed and (not invitation.has_info_mismatch):
            # The recipient has used the invitation and is
            # an active, pending user, or denied user.
            continue
        # If the recipient is ALREADY pending or active, then do not display any information
        # about the invitation
        if invitation.email.strip().casefold() in pending_or_active_rwu_emails:
            continue
        # Otherwise, the user was denied (don't show)
        # or the invitation has not been claimed.
        title = invitation.email
        can_cancel_invitation = False
        invitation_id = ""
        if invitation.has_info_mismatch:
            # This happens when the recipient tries to access the invitation,
            # but the recipient's name and date of birth do not match the
            # name and date of birth provided by the sender.
            status = (
                "The info you entered does not match your partner's "
                "account. Please add partner again to send a new "
                "invitation."
            )
        elif invitation.is_expired():
            # The recipient is expired.
            status = "Invitation expired"
        else:
            # The invitation has been sent, but has not been used
            # by the recipient.
            status = "Invitation sent"
            if invitation.created_by_user_id == user_id_of_requester:
                invitation_id = str(invitation.id)
                can_cancel_invitation = True

        result.append(
            WalletUser(
                title=title,
                status=status,
                invitation_id=invitation_id,
                can_cancel_invitation=can_cancel_invitation,
            )
        )

    return result
