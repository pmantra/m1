from __future__ import annotations

from datetime import datetime
from re import compile

from dateutil.relativedelta import relativedelta
from flask import current_app, request

from authn.models.user import User
from common.services.api import PermissionedUserResource
from storage.connection import db
from utils.braze import track_email_from_wallet_user_invite
from utils.log import logger
from wallet.models.constants import (
    ConsentOperation,
    ShareWalletMessages,
    WalletState,
    WalletUserStatus,
)
from wallet.models.models import (
    ReimbursementWallet,
    WalletAddUserPostRequest,
    WalletAddUserPostResponse,
)
from wallet.models.reimbursement_wallet_user import ReimbursementWalletUsers
from wallet.models.wallet_user_consent import WalletUserConsent
from wallet.models.wallet_user_invite import WalletUserInvite

VALID_EMAIL_REG = compile(
    r"[a-zA-Z0-9\+\.\_\%\-\+]{1,256}"
    r"@"
    r"[a-zA-Z0-9][a-zA-Z0-9\-]{1,64}"
    r"\."
    r"[a-zA-Z0-9][a-zA-Z0-9\-]{1,25}"
)
AGE_REQUIREMENT_YEARS = 13

log = logger(__name__)


class WalletAddUserResource(PermissionedUserResource):
    def post(self, wallet_id: int) -> tuple[dict, int]:
        """Send an invitation to a join a Reimbursement Wallet / Maven Wallet."""
        add_user_request = WalletAddUserPostRequest.from_request(
            request.json if request.is_json else None
        )
        log.info(
            "Recieved request to add user to wallet",
            wallet_id=f"'{wallet_id}'",
            user_id=str(self.user.id),
        )
        validation_error = request_validation_error(add_user_request)
        if validation_error:
            log.info(
                "Validation error when trying to add user to the wallet",
                wallet_id=f"'{wallet_id}'",
                user_id=str(self.user.id),
            )
            return validation_error

        wallet_state = (
            db.session.query(ReimbursementWallet.state)
            .filter(ReimbursementWallet.id == wallet_id)
            .scalar()
        )
        if wallet_state != WalletState.QUALIFIED:
            # Note that the user should not progress to this point because the ability
            # to invite users requires that the wallet is QUALIFIED.
            log.info(
                "User tried to share a wallet that is not QUALIFIED.",
                wallet_id=f"'{wallet_id}'",
                user_id=str(self.user.id),
            )
            return get_post_response(ShareWalletMessages.NO_ACCESS.value, 401)

        # Make sure this user eligible to invite others to the wallet.
        all_rwus_and_emails: list[tuple[ReimbursementWallet, str]] = (
            db.session.query(ReimbursementWalletUsers, User.email)
            .join(User, User.id == ReimbursementWalletUsers.user_id)
            .filter(
                ReimbursementWalletUsers.reimbursement_wallet_id == wallet_id,
            )
            .all()
        )

        pending_or_active_rwus = []
        emails_of_pending_or_active_wallet_users: list[str] = []
        active_user_ids = set()
        for rwu, email in all_rwus_and_emails:
            if rwu.status in [WalletUserStatus.ACTIVE, WalletUserStatus.PENDING]:
                pending_or_active_rwus.append(rwu)
                emails_of_pending_or_active_wallet_users.append(email)
                if rwu.status == WalletUserStatus.ACTIVE:
                    active_user_ids.add(rwu.user_id)

        if self.user.id not in active_user_ids:
            log.info(
                "User attempted to access wallet without authorization.",
                user_id=str(self.user.id),
                wallet_id=str(wallet_id),
            )
            # Either the wallet_id doesn't exist or the inviting user isn't
            # active
            return get_post_response(ShareWalletMessages.NO_ACCESS.value, 401)

        # If the recipient is already an active user of the wallet, return
        # an error.
        user_id_of_recipient = (
            db.session.query(User.id)
            .filter(User.email == add_user_request.email)
            .scalar()
        )

        if user_id_of_recipient is not None and user_id_of_recipient in active_user_ids:
            # The recipient is a user who is already an active user of the wallet
            return get_post_response(ShareWalletMessages.ALREADY_A_MEMBER.value, 409)

        # Take a shot to avoid a potential DB query:
        if len(pending_or_active_rwus) >= 2:
            return abort_contact_csr()

        # Now we need to query the DB to consider all the outstanding invitations
        outstanding_invitations = (
            db.session.query(WalletUserInvite)
            .filter(
                WalletUserInvite.reimbursement_wallet_id == wallet_id,
                WalletUserInvite.email.notin_(emails_of_pending_or_active_wallet_users),  # type: ignore[attr-defined] # "str" has no attribute "notin_"
                WalletUserInvite.claimed == False,
            )
            .all()
        )

        outstanding_unexpired_invitations = [
            inv for inv in outstanding_invitations if not inv.is_expired()
        ]

        # See if the recipient already has a pending invitation for this wallet.
        recipient_has_pending_invitations = any(
            inv.email.strip().casefold() == add_user_request.email
            for inv in outstanding_unexpired_invitations
        )

        if recipient_has_pending_invitations:
            return get_post_response(
                ShareWalletMessages.ALREADY_PENDING.value,
                409,
            )

        # See whether you already have 2 active or pending wallet users.
        num_outstanding_unexpired_invitations = len(outstanding_unexpired_invitations)
        if len(pending_or_active_rwus) + num_outstanding_unexpired_invitations >= 2:
            # We currently require the CSR team to manually
            # add users to wallets with at least 2 pending or active users
            # (including outstanding invitations).
            return abort_contact_csr()

        delete_existing_rwu_if_exists(all_rwus_and_emails, add_user_request.email)

        invitation = create_and_add_invitation(
            self.user.id, wallet_id, add_user_request
        )
        add_consent(invitation)
        db.session.commit()

        # At-least-once delivery pattern. Make sure we send the email at least once.
        base_url = current_app.config["BASE_URL"].rstrip("/")
        invitation_link = f"{base_url}/app/wallet-invite?wallet-partner-invite={invitation.id}&install_campaign=share_a_wallet"
        track_email_from_wallet_user_invite(
            wallet_user_invite=invitation,
            name=self.user.first_name,
            invitation_link=invitation_link,
        )

        return get_post_response(ShareWalletMessages.SENT.value, 200)


def request_validation_error(
    add_user_request: WalletAddUserPostRequest,
) -> tuple[dict, int] | None:
    """
    Returns tuple<body, error code> if there's a validation error.
    Returns None otherwise.
    """
    if not is_valid_email_format(add_user_request.email):
        log.info("Invalid email in invitation request.")
        return get_post_response(ShareWalletMessages.INVALID_EMAIL.value, 422, True)
    elif not is_valid_date_of_birth(add_user_request.date_of_birth):
        log.info("Invalid date of birth in invitation request.")
        return get_post_response(ShareWalletMessages.INVALID_AGE.value, 422, True)
    return None


def is_valid_email_format(email: str) -> bool:
    """Checks whether an email address matches our standard."""
    return bool(VALID_EMAIL_REG.match(email))


def is_valid_date_of_birth(date_of_birth: str) -> bool:
    """
    Checks whether the DOB is in YYYY-MM-DD format and represents
    someone who is at least 13 years old
    """
    try:
        dob_datetime = datetime.strptime(date_of_birth, "%Y-%m-%d")
        age_years = relativedelta(datetime.now(), dob_datetime).years
        return age_years >= AGE_REQUIREMENT_YEARS
    except ValueError:
        return False


def abort_contact_csr() -> tuple:
    """
    We currently require the CSR team to manually add users to wallets with
    at least 2 pending or active users (including outstanding invitations).
    """
    return get_post_response(ShareWalletMessages.WALLET_TEAM_HELP_NEEDED.value, 501)


def delete_existing_rwu_if_exists(
    all_rwus_and_emails: list, recipient_email: str
) -> None:
    """
    If the recipient is a DENIED user of the wallet, then we should delete
    the old record and replace it with a new one when the user rejoins the wallet.
    """
    for rwu, email in all_rwus_and_emails:
        if rwu.status == WalletUserStatus.DENIED and email == recipient_email:
            db.session.delete(rwu)
            break


def create_and_add_invitation(
    user_id: int, wallet_id: int, add_user_request: WalletAddUserPostRequest
) -> WalletUserInvite:
    """
    Creates a WalletUserInvite and adds a it to the database.
    Does not commit.
    """
    invitation = WalletUserInvite(
        created_by_user_id=user_id,
        reimbursement_wallet_id=wallet_id,
        date_of_birth_provided=add_user_request.date_of_birth,
        email=add_user_request.email,
    )
    db.session.add(invitation)
    return invitation


def add_consent(invitation: WalletUserInvite) -> None:
    """
    Adds consent from the sending user to the recipient to the database.
    Does not commit.
    """
    consent = WalletUserConsent(
        consent_giver_id=invitation.created_by_user_id,
        # We don't necessarily have a recipient user id yet.
        # Even if the recipient is a user, we will populate
        # the consent_recipient_id when the recipient accepts
        # the invitation.
        consent_recipient_id=None,
        recipient_email=invitation.email,
        reimbursement_wallet_id=invitation.reimbursement_wallet_id,
        operation=ConsentOperation.GIVE_CONSENT,
    )
    db.session.add(consent)


def get_post_response(
    message: str, http_status_code: int, can_retry: bool = False
) -> tuple[dict, int]:
    """Builds the response tuple<JSON response, status code>"""

    response: dict = WalletAddUserPostResponse(message=message, can_retry=can_retry)
    return response, http_status_code
