from __future__ import annotations

from traceback import format_exc
from uuid import UUID

from flask import request

from authn.models.user import User
from braze.client import BrazeClient, BrazeEvent
from common.services.api import AuthenticatedResource
from eligibility.service import successfully_enroll_partner
from messaging.models.messaging import Channel, ChannelUsers, Message
from storage.connection import db
from utils.launchdarkly import use_legacy_survey_monkey_url
from utils.log import logger
from views.schemas.common import get_survey_url_from_wallet
from wallet.models.constants import (
    ConsentOperation,
    WalletInvitationMessages,
    WalletState,
    WalletUserStatus,
    WalletUserType,
)
from wallet.models.models import (
    DeleteInvitationResponse,
    GetInvitationResponse,
    PostInvitationRequest,
    PostInvitationResponse,
)
from wallet.models.reimbursement_organization_settings import (
    ReimbursementOrganizationSettings,
)
from wallet.models.reimbursement_wallet import ReimbursementWallet
from wallet.models.reimbursement_wallet_user import ReimbursementWalletUsers
from wallet.models.wallet_user_consent import WalletUserConsent
from wallet.models.wallet_user_invite import WalletUserInvite
from wallet.repository.reimbursement_wallet import ReimbursementWalletRepository
from wallet.services.reimbursement_wallet_messaging import open_zendesk_ticket

log = logger(__name__)


class WalletInvitationResource(AuthenticatedResource):
    def get(self, invitation_id: str) -> tuple[dict, int]:
        """Handles the workflow for a recipient retrieving an invitation."""
        if not is_valid_uuid(invitation_id):
            log.info(
                "Share a Wallet - GET, invalid invitation_id",
                user_id=str(self.user.id),
                invitation_id=invitation_id,
            )
            return build_get_response("Cannot find the invitation.", 404)

        # We must check that the recipient of the invitation has entered a
        # birthday in his/her health profile.
        json = self.user.health_profile and self.user.health_profile.json

        if not json or "birthday" not in json:
            # The user hasn't set his/her birthday.
            # In this scenario, the client devices should prompt the recipient
            # to enter his/her birthday in the HealthProfile. We do not mark
            # the invitation as claimed in this case.
            log.info(
                "Share a Wallet - Recipient did not set birthday in profile.",
                user_id=str(self.user.id),
                invitation_id=invitation_id,
            )
            return build_get_response("Missing profile information.", 409)

        # "YYYY-MM-DD" format
        dob_of_recipient = json["birthday"].strip()
        invitation = WalletUserInvite.query.filter(
            WalletUserInvite.id == invitation_id
        ).one_or_none()
        if not invitation:
            log.info(
                "Share a Wallet - GET, cannot find invitation.",
                user_id=str(self.user.id),
                invitation_id=invitation_id,
            )
            return build_get_response("Cannot find the invitation.", 404)
        if (
            invitation.email.strip().casefold() != self.user.email.strip().casefold()
            or invitation.date_of_birth_provided.strip() != dob_of_recipient
        ):

            error = ""
            if invitation.date_of_birth_provided.strip() != dob_of_recipient:
                error = "birthday mismatch"
            if (
                invitation.email.strip().casefold()
                != self.user.email.strip().casefold()
            ):
                error += " email mismatch"
            log.info(
                "Share a Wallet - GET invitation, information mismatch.",
                user_id=str(self.user.id),
                invitation_id=invitation_id,
                error=error,
            )
            invitation.has_info_mismatch = True
            mark_invitation_as_claimed(invitation)
            return build_get_response(
                "Your information did not match the invitation.", 409
            )
        if invitation.is_expired():
            log.info(
                "Share a Wallet - GET invitation, invitation expired.",
                user_id=str(self.user.id),
                invitation_id=invitation_id,
            )
            return build_get_response("Invitation expired.", 409)
        if invitation.claimed:
            log.info(
                "Share a Wallet - GET invitation, invitation already claimed.",
                user_id=str(self.user.id),
                invitation_id=invitation_id,
            )
            return build_get_response("Invitation already used.", 409)
        if recipient_is_already_wallet_member(self.user.id):
            log.info(
                "Share a Wallet - GET invitation, recipient is already a member of a wallet.",
                user_id=str(self.user.id),
                invitation_id=invitation_id,
            )
            mark_invitation_as_claimed(invitation)
            return build_get_response(
                "It looks like you already have an active wallet.", 409
            )

        if not _is_wallet_on_invite_sharable(invitation):
            log.info(
                "Share a Wallet - GET invitation, wallet is not shareable.",
                user_id=str(self.user.id),
                invitation_id=invitation_id,
            )
            mark_invitation_as_claimed(invitation)
            return build_get_response("This wallet cannot be shared.", 409)
        survey_url = get_survey_url_from_wallet()
        if use_legacy_survey_monkey_url():
            survey_url = (
                db.session.query(ReimbursementOrganizationSettings.survey_url)
                .join(
                    ReimbursementWallet,
                    ReimbursementWallet.reimbursement_organization_settings_id
                    == ReimbursementOrganizationSettings.id,
                )
                .filter(ReimbursementWallet.id == invitation.reimbursement_wallet_id)
                .one()[0]
            )
            survey_url = survey_url.rstrip("/") + f"?member_id_hash={self.user.esp_id}"

        inviter_first_name = (
            db.session.query(User.first_name)
            .filter(User.id == invitation.created_by_user_id)
            .scalar()
        )
        inviter_first_name = inviter_first_name or "A Maven Member"

        # Do not mark it as claimed yet. We will do this when the recipient
        # decides declines the invitation or after the user completes the survey
        # and the client sends an accept request to the backend.
        log.info(
            "Share a Wallet - GET, found invitation.",
            user_id=str(self.user.id),
            invitation_id=invitation_id,
        )
        return build_get_response(
            WalletInvitationMessages.INVITE_FOUND.value,
            200,
            inviter_name=inviter_first_name,
            survey_url=survey_url,
        )

    def delete(self, invitation_id: str) -> tuple[dict, int]:
        """Handles the workflow for canceling an invitation."""
        # The user sending the cancel request MUST be the user who
        # sent the invitation.
        if not is_valid_uuid(invitation_id):
            log.info(
                "Share a Wallet - Cannot find invitatation to delete.",
                invitation_id=invitation_id,
                user_id=str(self.user.id),
            )
            return build_delete_response(
                WalletInvitationMessages.INVITE_NOT_FOUND.value, 404
            )

        invitation = WalletUserInvite.query.filter(
            WalletUserInvite.id == invitation_id,
            WalletUserInvite.created_by_user_id == self.user.id,
        ).one_or_none()

        if invitation is None:
            log.info(
                "Share a Wallet - Cannot find invitatation to delete.",
                invitation_id=invitation_id,
                user_id=str(self.user.id),
            )
            return build_delete_response(
                WalletInvitationMessages.INVITE_NOT_FOUND.value, 404
            )
        if invitation.is_expired():
            log.info(
                "Share a Wallet - Tried to cancel invitation that is expired.",
                invitation_id=invitation_id,
                user_id=str(self.user.id),
            )
            return build_delete_response(
                WalletInvitationMessages.ALREADY_EXPIRED.value, 410
            )
        if invitation.claimed:
            log.info(
                "Share a Wallet - Tried to cancel invitation that was already claimed / canceled.",
                invitation_id=invitation_id,
                user_id=str(self.user.id),
            )
            return build_delete_response(
                WalletInvitationMessages.ALREADY_USED.value, 410
            )
        try:
            revoke_consent = WalletUserConsent(
                consent_giver_id=self.user.id,
                consent_recipient_id=None,
                reimbursement_wallet_id=invitation.reimbursement_wallet_id,
                recipient_email=invitation.email,
                operation=ConsentOperation.REVOKE_CONSENT,
            )

            invitation.claimed = True
            db.session.add(revoke_consent)
            db.session.add(invitation)
            db.session.commit()
            log.info(
                "Share a Wallet - DELETE, successfully canceled invitation.",
                invitation_id=invitation_id,
                user_id=str(self.user.id),
            )
            return build_delete_response(
                WalletInvitationMessages.INVITE_CANCELED.value, 200
            )
        except Exception as exc:
            log.error(
                "Share a Wallet - DELETE, encountered an exception while trying to cancel an invitation.",
                error=str(exc),
                invitation_id=invitation_id,
                user_id=str(self.user.id),
                traceback=format_exc(),
            )
            return build_delete_response(
                WalletInvitationMessages.INVITE_CANCELED_FAILURE.value, 500
            )

    def post(self, invitation_id: str) -> tuple[dict, int]:
        """
        Handles the workflow for deciding to accept or cancel an invitation.
        """
        if not is_valid_uuid(invitation_id):
            log.info(
                "Invalid invitation id.",
                user_id=str(self.user.id),
                invitation_id=invitation_id,
            )
            return build_post_response(
                WalletInvitationMessages.INVITE_NOT_FOUND.value, 404
            )

        post_request = PostInvitationRequest.from_request(
            request.json if request.is_json else None
        )
        invitation = WalletUserInvite.query.filter(
            WalletUserInvite.id == invitation_id
        ).one_or_none()

        check_response = check_invitation(self.user, invitation_id, invitation)
        if check_response:
            return check_response
        # You CAN invite someone who is already active on another wallet.
        if not post_request.accept:
            log.info(
                "User declined invitation.",
                user_id=str(self.user.id),
                invitation_id=invitation_id,
            )
            # The recipient has declined the invitation.
            mark_invitation_as_claimed(invitation)
            return build_post_response(
                WalletInvitationMessages.INVITE_DECLINED.value, 200
            )

        # We can't tell yet if the person is the dependent or the employee
        rwu = ReimbursementWalletUsers.query.filter(
            ReimbursementWalletUsers.reimbursement_wallet_id,
            ReimbursementWalletUsers.user_id == self.user.id,
        ).one_or_none()
        if rwu is None:
            log.info(
                "Creating new RWU.",
                user_id=str(self.user.id),
                invitation_id=invitation_id,
            )
            channel = create_channel_and_channel_users(self.user.id)
            rwu = ReimbursementWalletUsers(
                reimbursement_wallet_id=invitation.reimbursement_wallet_id,
                user_id=self.user.id,
                status=WalletUserStatus.PENDING,
                type=WalletUserType.DEPENDENT,
                channel_id=channel.id,
            )
            db.session.add(rwu)
            db.session.commit()
            # Must add the zendesk_ticket after the RWU
            # is in the database
            open_zendesk_ticket(rwu)
        else:
            log.info(
                "Updating existing RWU.",
                user_id=str(self.user.id),
                invitation_id=invitation_id,
            )
            rwu.status = WalletUserStatus.PENDING
            if rwu.channel_id is None:
                channel = create_channel_and_channel_users(self.user.id)
                rwu.channel_id = channel.id
                db.session.add(rwu)
                db.session.commit()
            if rwu.zendesk_ticket_id is None:
                open_zendesk_ticket(rwu)

        # Legal requirement: When the invitation recipient accepts the
        # invitation, this is interpreted as consent to the inviter.
        # Hence, we update consent from the sender to the recipient
        # with the recipient's user_id, and we write an entry where
        # the recipient consents to the sender.
        if successfully_enroll_partner(
            invitation.created_by_user_id, self.user, invitation_id
        ):
            consent_from_sender = (
                WalletUserConsent.query.filter(
                    WalletUserConsent.consent_giver_id == invitation.created_by_user_id,
                    WalletUserConsent.reimbursement_wallet_id
                    == invitation.reimbursement_wallet_id,
                    WalletUserConsent.recipient_email == self.user.email,
                )
                .order_by(WalletUserConsent.created_at.desc())
                .first()
            )
            consent_from_sender.consent_recipient_id = self.user.id
            consent_from_recipient_to_sender = WalletUserConsent(
                consent_giver_id=self.user.id,
                consent_recipient_id=consent_from_sender.consent_giver_id,
                recipient_email=None,
                reimbursement_wallet_id=invitation.reimbursement_wallet_id,
                operation=ConsentOperation.GIVE_CONSENT,
            )
            invitation.claimed = True
            db.session.add_all(
                [consent_from_sender, consent_from_recipient_to_sender, invitation, rwu]
            )
            db.session.commit()
            log.info(
                "Share a Wallet - Successfully accepted and enrolled a user.",
                invitation_id=invitation_id,
                user_id=str(self.user.id),
            )
            send_join_wallet_notification(
                invitation.created_by_user_id,
                self.user.id,
                invitation_id=str(invitation_id),
            )
            return build_post_response(
                WalletInvitationMessages.INVITE_ACCEPTED.value, 200
            )
        return build_post_response(
            WalletInvitationMessages.INVITED_ACCEPTED_FAILURE.value, 500
        )


def send_join_wallet_notification(  # type: ignore[return] # Missing return statement
    sender_user_id: int, recipient_user_id: int, invitation_id: str
) -> list[tuple]:
    """
    Sends a notification to Partner A that Partner B has joined the wallet.
    """
    result = (
        db.session.query(User.id, User.esp_id, User.first_name)
        .filter(User.id.in_([sender_user_id, recipient_user_id]))
        .all()
    )
    if result[0][0] == recipient_user_id:
        # Make sure the sender comes first
        result[0], result[1] = result[1], result[0]
    sender_info, recipient_info = result
    _, sender_esp_id, sender_first_name = sender_info
    recipient_first_name = recipient_info[-1]
    notify_sender_when_recipient_accepts_wallet_invitation(
        sender_esp_id=sender_esp_id,
        invitation_sender_name=sender_first_name,
        invitation_recipient_name=recipient_first_name,
        invitation_id=invitation_id,
    )


def notify_sender_when_recipient_accepts_wallet_invitation(  # type: ignore[no-untyped-def] # Function is missing a return type annotation
    sender_esp_id: str,
    invitation_sender_name: str,
    invitation_recipient_name: str,
    invitation_id: str,
):
    """
    Share a Wallet.
    Sends a Braze notification to the invitation sender when the
    invitation recipient has accepted the sender's invitation.
    """
    braze_client = BrazeClient()
    braze_event = BrazeEvent(
        external_id=sender_esp_id,
        name="share_a_wallet_partner_joined",
        properties={
            "partner_a_name": invitation_sender_name,
            "partner_b_name": invitation_recipient_name,
        },
    )
    braze_client.track_user(events=[braze_event])

    log.info(
        "Share a Wallet - Notified Partner A that Partner B accepted the invite.",
        invitation_id=invitation_id,
    )


def create_channel_and_channel_users(user_id: int) -> Channel:
    """
    Creates channel and channel_users objects for a user.
    Persists the items in the database.
    Returns the channel.
    """
    channel = Channel(
        name="Maven Wallet",
        internal=True,
        comment={"user_ids": user_id},
    )
    channel_user = ChannelUsers(
        channel=channel,
        user_id=user_id,
        is_initiator=False,
        max_chars=Message.MAX_CHARS,
    )
    db.session.add_all([channel, channel_user])
    db.session.commit()
    return channel


def is_valid_uuid(string: str) -> bool:
    # We should avoid a DB query if it can't be a UUID.
    try:
        UUID(string)
        return True
    except ValueError:
        return False


def recipient_is_already_wallet_member(user_id: int) -> bool:
    """Returns whether recipient is already a member of any wallet."""
    return bool(
        db.session.query(ReimbursementWalletUsers)
        .join(
            ReimbursementWallet,
            ReimbursementWalletUsers.reimbursement_wallet_id == ReimbursementWallet.id,
        )
        .filter(
            ReimbursementWalletUsers.user_id == user_id,
            ReimbursementWalletUsers.status.in_(
                (WalletUserStatus.ACTIVE, WalletUserStatus.PENDING)
            ),
            ReimbursementWallet.state == WalletState.QUALIFIED,
        )
        .count()
    )


def mark_invitation_as_claimed(invitation: WalletUserInvite) -> None:
    """Marks an invitation as claimed and persists it in the DB."""
    invitation.claimed = True
    db.session.add(invitation)
    db.session.commit()


def build_get_response(
    message: str, response_code: int, inviter_name: str = "", survey_url: str = ""
) -> tuple[dict, int]:
    """
    Returns a tuple[response body, HTTP status code] for the GET verb.
    """
    response: dict = GetInvitationResponse(
        message=message, inviter_name=inviter_name, survey_url=survey_url
    )
    return response, response_code


def build_delete_response(message: str, response_code: int) -> tuple[dict, int]:
    """
    Returns a tuple[response body, HTTP status code] for the DELETE verb.
    """
    response: dict = DeleteInvitationResponse(message=message)
    return response, response_code


def build_post_response(message: str, response_code: int) -> tuple[dict, int]:
    """
    Returns a tuple[response body, HTTP status code] for the POST verb.
    """
    response: dict = PostInvitationResponse(message=message)
    return response, response_code


def _is_wallet_on_invite_sharable(invite: WalletUserInvite) -> bool:
    # load wallet - trusting that this is a legitimate wallet id
    wallet = ReimbursementWallet.query.get(invite.reimbursement_wallet_id)
    to_return = wallet.is_shareable
    log.info(
        "Checking shareability of wallet on invitation.",
        reimbursement_wallet_id=invite.reimbursement_wallet_id,
        is_shareable=to_return,
    )
    return to_return


def check_invitation(
    user: User,
    provided_invitation_id: str,
    invitation: WalletUserInvite | None,
) -> tuple[dict, int] | None:
    """
    Determines whether the invitation is valid and returns a tuple error if not.
    Returns NULL otherwise.
    Checks:
    * Date of birth and email match
    * Invitation is not expired
    * Invitation is not claimed
    * User is not already a member of the wallet
    * The wallet is shareable
    * There is only 1 member on the wallet
    """
    if not invitation:
        log.info(
            "Cannot find invitation id.",
            user_id=str(user.id),
            invitation_id=provided_invitation_id,
        )
        return build_post_response(WalletInvitationMessages.INVITE_NOT_FOUND.value, 404)

    # We must check that the recipient of the invitation has entered a
    # birthday in his/her health profile.
    json = user.health_profile and user.health_profile.json
    if (
        invitation.email.strip().casefold() != user.email.strip().casefold()
        or (not json)
        or (invitation.date_of_birth_provided != json.get("birthday"))
    ):
        log.info(
            # It would be really difficult to see this log since
            # it would almost certainly be caught in the GET endpoint.
            "Invitation information mismatch.",
            user_id=str(user.id),
            invitation_id=str(invitation.id),
        )
        invitation.has_info_mismatch = True
        mark_invitation_as_claimed(invitation)
        return build_post_response(
            WalletInvitationMessages.INFORMATION_DOES_NOT_MATCH.value, 409
        )

    if invitation.is_expired():
        log.info(
            "Invitation expired.",
            user_id=str(user.id),
            invitation_id=str(invitation.id),
        )
        return build_post_response(WalletInvitationMessages.EXPIRED.value, 409)

    if invitation.claimed:
        # We must first check whether this invitation allowed the user to apply for the wallet
        # via the WQS. This would mean that the UI is making a POST request to accept the invitation
        # from the legacy workflow that used SurveyMonkey. In this case, we should gracefully return a 200
        # to avoid showing an error.
        # The user may be DENIED, PENDING, or ACTIVE - the case does not matter
        # since the legacy UI will always fire this POST request.
        # Realistically, after the legacy UI code is deprecated, the user should never enter this
        # block of code because the GET endpoint will always be called first, and it will prevent
        # the user from proceeding because the invitation is already claimed.
        log.info(
            "Invitation already claimed.",
            user_id=str(user.id),
            invitation_id=str(invitation.id),
        )
        return build_post_response(WalletInvitationMessages.ALREADY_USED.value, 200)

    if recipient_is_already_wallet_member(user.id):
        log.info(
            "User is already a wallet member.",
            user_id=str(user.id),
            invitation_id=provided_invitation_id,
        )
        mark_invitation_as_claimed(invitation)
        return build_post_response(
            WalletInvitationMessages.ALREADY_ACTIVE_WALLET.value, 409
        )

    # Very edgy case - wallet org becomes unsharable/member loses gold between the time that invitation was accepted
    # and the survey completed.
    if not _is_wallet_on_invite_sharable(invitation):
        mark_invitation_as_claimed(invitation)
        log.info(
            "Wallet is not shareable.",
            user_id=str(user.id),
            invitation_id=str(invitation.id),
        )
        return build_post_response(
            WalletInvitationMessages.UNSHARABLE_WALLET.value, 409
        )

    num_existing_rwus = ReimbursementWalletRepository().get_num_existing_rwus(
        invitation.reimbursement_wallet_id
    )
    if num_existing_rwus >= 2:
        # We currently require the CSR team to manually add users to
        # wallets with at least 2 pending or active users (including
        # outstanding invitations).
        log.info(
            "Wallet already has 2 or more users.",
            user_id=str(user.id),
            invitation_id=str(invitation.id),
        )
        return build_post_response(
            WalletInvitationMessages.WALLET_TEAM_HELP_NEEDED.value, 501
        )
    return None
