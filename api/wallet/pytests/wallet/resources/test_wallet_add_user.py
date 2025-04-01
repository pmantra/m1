import datetime
from unittest.mock import patch

import pytest

from authn.models.user import User
from pytests.factories import EnterpriseUserFactory
from storage.connection import db
from wallet.models.constants import WalletState, WalletUserStatus, WalletUserType
from wallet.models.wallet_user_consent import WalletUserConsent
from wallet.models.wallet_user_invite import WalletUserInvite
from wallet.pytests.factories import (
    ReimbursementWalletFactory,
    ReimbursementWalletUsersFactory,
    WalletUserInviteFactory,
)

RECIPIENT_EMAIL = "joseph.fourier@harmonic.com"


def test_add_user_happy_path(client, enterprise_user, api_helpers):
    wallet = ReimbursementWalletFactory.create(id=123123, state=WalletState.QUALIFIED)
    ReimbursementWalletUsersFactory.create(
        reimbursement_wallet_id=wallet.id,
        user_id=enterprise_user.id,
        status=WalletUserStatus.ACTIVE,
        type=WalletUserType.DEPENDENT,
    )
    payload = {"email": RECIPIENT_EMAIL, "date_of_birth": "2000-10-10"}

    with patch(
        "wallet.resources.wallet_add_user.track_email_from_wallet_user_invite"
    ) as braze_patch:
        res = client.post(
            f"/api/v1/reimbursement_wallet/{wallet.id}/add_user",
            headers=api_helpers.json_headers(enterprise_user),
            data=api_helpers.json_data(payload),
        )
        braze_patch.assert_called_once()
        call_dict = braze_patch.call_args.kwargs

    check_call_info(enterprise_user, RECIPIENT_EMAIL, call_dict)

    assert res.status_code == 200
    content = api_helpers.load_json(res)
    assert content == {"can_retry": False, "message": "Your invite has been sent."}


@pytest.mark.parametrize(
    argnames=("wallet_state",),
    argvalues=(
        (WalletState.PENDING,),
        (WalletState.DISQUALIFIED,),
        (WalletState.EXPIRED,),
        (WalletState.RUNOUT,),
    ),
)
def test_add_user_not_qualified_wallet(
    client, enterprise_user, wallet_state: WalletState, api_helpers
):
    wallet = ReimbursementWalletFactory.create(id=123123, state=wallet_state)
    ReimbursementWalletUsersFactory.create(
        reimbursement_wallet_id=wallet.id,
        user_id=enterprise_user.id,
        status=WalletUserStatus.ACTIVE,
        type=WalletUserType.DEPENDENT,
    )
    payload = {"email": RECIPIENT_EMAIL, "date_of_birth": "2000-10-10"}

    with patch(
        "wallet.resources.wallet_add_user.track_email_from_wallet_user_invite"
    ) as braze_patch:
        res = client.post(
            f"/api/v1/reimbursement_wallet/{wallet.id}/add_user",
            headers=api_helpers.json_headers(enterprise_user),
            data=api_helpers.json_data(payload),
        )
        braze_patch.assert_not_called()

    assert res.status_code == 401
    content = api_helpers.load_json(res)
    assert content == {
        "can_retry": False,
        "message": "Unable to access the Maven Wallet",
    }


def test_add_user_happy_path_email_case(client, enterprise_user, api_helpers):
    wallet = ReimbursementWalletFactory.create(id=123123, state=WalletState.QUALIFIED)
    ReimbursementWalletUsersFactory.create(
        reimbursement_wallet_id=wallet.id,
        user_id=enterprise_user.id,
        status=WalletUserStatus.ACTIVE,
        type=WalletUserType.DEPENDENT,
    )
    email = "CapitalCase@email.com"
    payload = {"email": email, "date_of_birth": "2000-10-10"}

    with patch(
        "wallet.resources.wallet_add_user.track_email_from_wallet_user_invite"
    ) as braze_patch:
        res = client.post(
            f"/api/v1/reimbursement_wallet/{wallet.id}/add_user",
            headers=api_helpers.json_headers(enterprise_user),
            data=api_helpers.json_data(payload),
        )
        braze_patch.assert_called_once()
        call_dict = braze_patch.call_args.kwargs

    check_call_info(enterprise_user, email, call_dict)

    assert res.status_code == 200
    content = api_helpers.load_json(res)
    assert content == {"can_retry": False, "message": "Your invite has been sent."}


def test_add_user_under_13(client, enterprise_user, api_helpers):
    wallet = ReimbursementWalletFactory.create()
    ReimbursementWalletUsersFactory.create(
        user_id=enterprise_user.id,
        reimbursement_wallet_id=wallet.id,
    )

    two_days_ago = datetime.datetime.now() - datetime.timedelta(days=2)
    date_of_birth = two_days_ago.strftime("%Y-%m-%d")
    payload = {"email": RECIPIENT_EMAIL, "date_of_birth": date_of_birth}

    with patch(
        "wallet.resources.wallet_add_user.track_email_from_wallet_user_invite"
    ) as braze_patch:
        res = client.post(
            f"/api/v1/reimbursement_wallet/{wallet.id}/add_user",
            headers=api_helpers.json_headers(enterprise_user),
            data=api_helpers.json_data(payload),
        )
        braze_patch.assert_not_called()

    assert res.status_code == 422
    content = api_helpers.load_json(res)
    assert content == {
        "message": "Recipient must be at least 13 years old.",
        "can_retry": True,
    }
    assert_no_consent_or_invitation_sent(enterprise_user.id, RECIPIENT_EMAIL)


def test_add_user_bad_email_format(client, enterprise_user, api_helpers):
    bad_email_address = "940{3Mail@format"
    wallet = ReimbursementWalletFactory.create()
    ReimbursementWalletUsersFactory.create(
        user_id=enterprise_user.id,
        reimbursement_wallet_id=wallet.id,
    )

    payload = {"email": bad_email_address, "date_of_birth": "2000-01-01"}

    with patch(
        "wallet.resources.wallet_add_user.track_email_from_wallet_user_invite"
    ) as braze_patch:
        res = client.post(
            f"/api/v1/reimbursement_wallet/{wallet.id}/add_user",
            headers=api_helpers.json_headers(enterprise_user),
            data=api_helpers.json_data(payload),
        )
        braze_patch.assert_not_called()

    assert res.status_code == 422
    content = api_helpers.load_json(res)
    assert content == {"message": "Invalid email address.", "can_retry": True}
    assert_no_consent_or_invitation_sent(enterprise_user.id, bad_email_address)


def test_unauthorized(client, enterprise_user, api_helpers):
    wallet = ReimbursementWalletFactory.create(id=123123)
    ReimbursementWalletUsersFactory.create(
        reimbursement_wallet_id=wallet.id,
        user_id=enterprise_user.id,
        status=WalletUserStatus.ACTIVE,
        type=WalletUserType.DEPENDENT,
    )
    payload = {"email": RECIPIENT_EMAIL, "date_of_birth": "2000-10-10"}
    some_other_user = EnterpriseUserFactory.create()

    with patch(
        "wallet.resources.wallet_add_user.track_email_from_wallet_user_invite"
    ) as braze_patch:
        res = client.post(
            f"/api/v1/reimbursement_wallet/{wallet.id}/add_user",
            headers=api_helpers.json_headers(some_other_user),
            data=api_helpers.json_data(payload),
        )
        braze_patch.assert_not_called()

    assert res.status_code == 401
    content = api_helpers.load_json(res)
    assert content == {
        "can_retry": False,
        "message": "Unable to access the Maven Wallet",
    }
    assert_no_consent_or_invitation_sent(some_other_user.id, RECIPIENT_EMAIL)
    assert_no_consent_or_invitation_sent(enterprise_user.id, RECIPIENT_EMAIL)


def test_already_part_of_wallet(client, enterprise_user, api_helpers):
    wallet = ReimbursementWalletFactory.create(id=123123, state=WalletState.QUALIFIED)
    some_other_user = EnterpriseUserFactory.create()
    ReimbursementWalletUsersFactory.create(
        reimbursement_wallet_id=wallet.id,
        user_id=enterprise_user.id,
    )
    ReimbursementWalletUsersFactory.create(
        reimbursement_wallet_id=wallet.id,
        user_id=some_other_user.id,
        status=WalletUserStatus.ACTIVE,
        type=WalletUserType.DEPENDENT,
    )
    payload = {"email": some_other_user.email, "date_of_birth": "2000-10-10"}

    with patch(
        "wallet.resources.wallet_add_user.track_email_from_wallet_user_invite"
    ) as braze_patch:
        res = client.post(
            f"/api/v1/reimbursement_wallet/{wallet.id}/add_user",
            headers=api_helpers.json_headers(enterprise_user),
            data=api_helpers.json_data(payload),
        )
        braze_patch.assert_not_called()

    assert res.status_code == 409
    content = api_helpers.load_json(res)
    assert content == {
        "can_retry": False,
        "message": "The person you are trying to add is already part of your Wallet.",
    }
    assert_no_consent_or_invitation_sent(enterprise_user.id, some_other_user.email)


def test_two_existing_users(client, enterprise_user, api_helpers):
    wallet = ReimbursementWalletFactory.create(id=123123, state=WalletState.QUALIFIED)
    ReimbursementWalletUsersFactory.create(
        reimbursement_wallet_id=wallet.id,
        user_id=enterprise_user.id,
    )

    pending_user = EnterpriseUserFactory.create()
    ReimbursementWalletUsersFactory.create(
        reimbursement_wallet_id=wallet.id,
        user_id=pending_user.id,
        status=WalletUserStatus.PENDING,
        type=WalletUserType.DEPENDENT,
    )

    payload = {"email": RECIPIENT_EMAIL, "date_of_birth": "2000-10-10"}

    with patch(
        "wallet.resources.wallet_add_user.track_email_from_wallet_user_invite"
    ) as braze_patch:
        res = client.post(
            f"/api/v1/reimbursement_wallet/{wallet.id}/add_user",
            headers=api_helpers.json_headers(enterprise_user),
            data=api_helpers.json_data(payload),
        )
        braze_patch.assert_not_called()

    assert res.status_code == 501
    content = api_helpers.load_json(res)
    assert content == {
        "can_retry": False,
        "message": "Please message the Wallet team to add more partners.",
    }
    assert_no_consent_or_invitation_sent(enterprise_user.id, RECIPIENT_EMAIL)


def test_existing_outstanding_invitation(client, enterprise_user, api_helpers):
    wallet = ReimbursementWalletFactory.create(id=123123, state=WalletState.QUALIFIED)
    ReimbursementWalletUsersFactory.create(
        reimbursement_wallet_id=wallet.id,
        user_id=enterprise_user.id,
    )

    WalletUserInviteFactory.create(
        created_by_user_id=enterprise_user.id,
        reimbursement_wallet_id=wallet.id,
        date_of_birth_provided="1961-08-04",
        email="bar@lulu@hi",
    )

    payload = {"email": RECIPIENT_EMAIL, "date_of_birth": "2000-10-10"}

    with patch(
        "wallet.resources.wallet_add_user.track_email_from_wallet_user_invite"
    ) as braze_patch:
        res = client.post(
            f"/api/v1/reimbursement_wallet/{wallet.id}/add_user",
            headers=api_helpers.json_headers(enterprise_user),
            data=api_helpers.json_data(payload),
        )
        braze_patch.assert_not_called()

    assert res.status_code == 501
    content = api_helpers.load_json(res)
    assert content == {
        "can_retry": False,
        "message": "Please message the Wallet team to add more partners.",
    }
    assert_no_consent_or_invitation_sent(enterprise_user.id, RECIPIENT_EMAIL)


def test_existing_expired_invitation(client, enterprise_user, api_helpers):
    wallet = ReimbursementWalletFactory.create(id=123123, state=WalletState.QUALIFIED)
    ReimbursementWalletUsersFactory.create(
        reimbursement_wallet_id=wallet.id,
        user_id=enterprise_user.id,
    )

    WalletUserInviteFactory.create(
        created_by_user_id=enterprise_user.id,
        reimbursement_wallet_id=wallet.id,
        date_of_birth_provided="1961-08-04",
        email="bar@lulu.hi",
        created_at=datetime.datetime(2020, 1, 1),
    )

    payload = {"email": RECIPIENT_EMAIL, "date_of_birth": "2000-10-10"}

    with patch(
        "wallet.resources.wallet_add_user.track_email_from_wallet_user_invite"
    ) as braze_patch:
        res = client.post(
            f"/api/v1/reimbursement_wallet/{wallet.id}/add_user",
            headers=api_helpers.json_headers(enterprise_user),
            data=api_helpers.json_data(payload),
        )
        braze_patch.assert_called_once()
        call_dict = braze_patch.call_args.kwargs

    check_call_info(enterprise_user, RECIPIENT_EMAIL, call_dict)

    assert res.status_code == 200
    content = api_helpers.load_json(res)
    assert content == {"can_retry": False, "message": "Your invite has been sent."}


def test_existing_claimed_invitation(client, enterprise_user, api_helpers):
    wallet = ReimbursementWalletFactory.create(id=123123, state=WalletState.QUALIFIED)
    ReimbursementWalletUsersFactory.create(
        reimbursement_wallet_id=wallet.id,
        user_id=enterprise_user.id,
    )

    WalletUserInviteFactory.create(
        created_by_user_id=enterprise_user.id,
        reimbursement_wallet_id=wallet.id,
        date_of_birth_provided="1972-04-08",
        email="sergei@magnitsky.com",
        claimed=True,
    )

    payload = {"email": RECIPIENT_EMAIL, "date_of_birth": "2000-10-10"}

    with patch(
        "wallet.resources.wallet_add_user.track_email_from_wallet_user_invite"
    ) as braze_patch:
        res = client.post(
            f"/api/v1/reimbursement_wallet/{wallet.id}/add_user",
            headers=api_helpers.json_headers(enterprise_user),
            data=api_helpers.json_data(payload),
        )
        braze_patch.assert_called_once()
        call_dict = braze_patch.call_args.kwargs

    check_call_info(enterprise_user, RECIPIENT_EMAIL, call_dict)
    assert res.status_code == 200
    content = api_helpers.load_json(res)
    assert content == {"can_retry": False, "message": "Your invite has been sent."}


def test_recipient_already_has_pending_invite(client, enterprise_user, api_helpers):
    wallet = ReimbursementWalletFactory.create(id=123123, state=WalletState.QUALIFIED)

    ReimbursementWalletUsersFactory.create(
        reimbursement_wallet_id=wallet.id,
        user_id=enterprise_user.id,
    )

    WalletUserInviteFactory.create(
        created_by_user_id=enterprise_user.id,
        reimbursement_wallet_id=wallet.id,
        # Note - dob shouldn't matter since email is a unique key in the User table
        date_of_birth_provided="2000-10-10",
        email=RECIPIENT_EMAIL,
    )

    payload = {"email": RECIPIENT_EMAIL, "date_of_birth": "2000-10-10"}

    with patch(
        "wallet.resources.wallet_add_user.track_email_from_wallet_user_invite"
    ) as braze_patch:
        res = client.post(
            f"/api/v1/reimbursement_wallet/{wallet.id}/add_user",
            headers=api_helpers.json_headers(enterprise_user),
            data=api_helpers.json_data(payload),
        )
        braze_patch.assert_not_called()

    assert res.status_code == 409
    content = api_helpers.load_json(res)
    assert content == {
        "can_retry": False,
        "message": "The person you are trying to add already has a pending invitation.",
    }


def test_cannot_add_users_to_fake_wallet(client, enterprise_user, api_helpers):
    wallet = ReimbursementWalletFactory.create()
    payload = {"email": RECIPIENT_EMAIL, "date_of_birth": "2000-10-10"}

    with patch(
        "wallet.resources.wallet_add_user.track_email_from_wallet_user_invite"
    ) as braze_patch:
        res = client.post(
            f"/api/v1/reimbursement_wallet/{wallet.id + 123}/add_user",
            headers=api_helpers.json_headers(enterprise_user),
            data=api_helpers.json_data(payload),
        )
        braze_patch.assert_not_called()

    assert res.status_code == 401
    content = api_helpers.load_json(res)
    assert content == {
        "can_retry": False,
        "message": "Unable to access the Maven Wallet",
    }
    assert_no_consent_or_invitation_sent(enterprise_user.id, RECIPIENT_EMAIL)


def assert_no_consent_or_invitation_sent(user_id: int, recipient_email: str):
    invitations = (
        db.session.query(WalletUserInvite)
        .filter(
            WalletUserInvite.created_by_user_id == user_id,
            WalletUserInvite.email == recipient_email,
        )
        .all()
    )
    assert invitations == []

    consent = (
        db.session.query(WalletUserConsent)
        .filter(
            WalletUserConsent.consent_giver_id == user_id,
            WalletUserConsent.recipient_email == recipient_email,
        )
        .all()
    )
    assert consent == []


def check_call_info(
    created_by_user: User, recipient_email: str, call_dict: dict
) -> None:
    """
    Make sure we have the consent and invitation, and that the correct
    Braze information was sent.
    """

    invitation = (
        db.session.query(WalletUserInvite)
        .filter(
            WalletUserInvite.created_by_user_id == created_by_user.id,
            WalletUserInvite.email == recipient_email,
        )
        .one()
    )
    assert invitation
    assert call_dict["wallet_user_invite"] == invitation

    expected_path = f"/app/wallet-invite?wallet-partner-invite={invitation.id}&install_campaign=share_a_wallet"
    invitation_link = call_dict["invitation_link"]

    assert invitation_link.endswith(expected_path)
    assert "//app" not in invitation_link
    assert call_dict["name"] == created_by_user.first_name

    consent = (
        db.session.query(WalletUserConsent)
        .filter(
            WalletUserConsent.consent_giver_id == created_by_user.id,
            WalletUserConsent.recipient_email == recipient_email,
        )
        .one()
    )
    assert consent
