from datetime import datetime, timedelta

from pytests.factories import EnterpriseUserFactory
from wallet.models.constants import (
    ConsentOperation,
    WalletState,
    WalletUserStatus,
    WalletUserType,
)
from wallet.models.wallet_user_consent import WalletUserConsent
from wallet.models.wallet_user_invite import WalletUserInvite
from wallet.pytests.factories import (
    ReimbursementWalletFactory,
    ReimbursementWalletUsersFactory,
    WalletUserInviteFactory,
)

EXPIRATION_TIME = timedelta(days=3)
TEST_EMAIL = "goedel@escher.bach"


def test_add_user_happy_path(client, enterprise_user, api_helpers):
    wallet = ReimbursementWalletFactory.create(id=123123, state=WalletState.QUALIFIED)
    ReimbursementWalletUsersFactory.create(
        reimbursement_wallet_id=wallet.id,
        user_id=enterprise_user.id,
        status=WalletUserStatus.ACTIVE,
        type=WalletUserType.DEPENDENT,
    )
    invitation = WalletUserInviteFactory.create(
        created_by_user_id=enterprise_user.id,
        reimbursement_wallet_id=wallet.id,
        date_of_birth_provided="2000-01-01",
        email=TEST_EMAIL,
    )

    res = client.delete(
        f"/api/v1/reimbursement_wallet/invitation/{invitation.id}",
        headers=api_helpers.json_headers(enterprise_user),
    )

    # Make sure we have the revoked consent
    consent = WalletUserConsent.query.filter(
        WalletUserConsent.consent_giver_id == enterprise_user.id,
        WalletUserConsent.recipient_email == TEST_EMAIL,
        WalletUserConsent.operation == ConsentOperation.REVOKE_CONSENT,
    ).one()
    assert consent

    # Make sure we have updated and claimed the invitation
    invitation_after_cancellation = WalletUserInvite.query.filter(
        WalletUserInvite.created_by_user_id == enterprise_user.id,
        WalletUserInvite.email == TEST_EMAIL,
    ).one()
    assert invitation_after_cancellation
    assert invitation_after_cancellation.id == invitation.id
    assert invitation_after_cancellation.claimed is True

    assert res.status_code == 200
    content = api_helpers.load_json(res)
    assert content == {"message": "Invitation canceled."}


def test_invitation_id_is_not_uuid(client, enterprise_user, api_helpers):
    wallet = ReimbursementWalletFactory.create()
    ReimbursementWalletUsersFactory.create(
        user_id=enterprise_user.id,
        reimbursement_wallet_id=wallet.id,
    )
    weird_invitation_id = "this can't b3 a UU1D!"
    res = client.delete(
        f"/api/v1/reimbursement_wallet/invitation/{weird_invitation_id}",
        headers=api_helpers.json_headers(enterprise_user),
    )

    assert res.status_code == 404
    content = api_helpers.load_json(res)
    assert content == {"message": "Cannot find the invitation."}

    assert_no_consent_changes(enterprise_user.id, TEST_EMAIL)


def test_expired_invitation(client, enterprise_user, api_helpers):
    wallet = ReimbursementWalletFactory.create()
    ReimbursementWalletUsersFactory.create(
        user_id=enterprise_user.id,
        reimbursement_wallet_id=wallet.id,
    )
    invitation = WalletUserInviteFactory.create(
        created_by_user_id=enterprise_user.id,
        reimbursement_wallet_id=wallet.id,
        date_of_birth_provided="2000-01-01",
        email=TEST_EMAIL,
        created_at=datetime(2023, 1, 1),
    )
    res = client.delete(
        f"/api/v1/reimbursement_wallet/invitation/{invitation.id}",
        headers=api_helpers.json_headers(enterprise_user),
    )

    assert res.status_code == 410
    content = api_helpers.load_json(res)
    assert content == {"message": "Invitation has already expired."}

    assert_no_consent_changes(enterprise_user.id, TEST_EMAIL)


def test_invitation_was_already_used(client, enterprise_user, api_helpers):
    wallet = ReimbursementWalletFactory.create()
    ReimbursementWalletUsersFactory.create(
        user_id=enterprise_user.id,
        reimbursement_wallet_id=wallet.id,
    )
    invitation = WalletUserInviteFactory.create(
        created_by_user_id=enterprise_user.id,
        reimbursement_wallet_id=wallet.id,
        date_of_birth_provided="2000-01-01",
        email=TEST_EMAIL,
        claimed=True,
    )

    res = client.delete(
        f"/api/v1/reimbursement_wallet/invitation/{invitation.id}",
        headers=api_helpers.json_headers(enterprise_user),
    )

    assert res.status_code == 410
    content = api_helpers.load_json(res)
    assert content == {"message": "Invitation already used."}

    assert_no_consent_changes(enterprise_user.id, TEST_EMAIL)


def test_cannot_cancel_invite_you_did_not_send(client, enterprise_user, api_helpers):
    wallet = ReimbursementWalletFactory.create(id=123123)
    other_user = EnterpriseUserFactory.create(id=123123)
    ReimbursementWalletUsersFactory.create(
        reimbursement_wallet_id=wallet.id,
        user_id=enterprise_user.id,
        status=WalletUserStatus.ACTIVE,
        type=WalletUserType.DEPENDENT,
    )
    invitation_from_other_user = WalletUserInviteFactory.create(
        created_by_user_id=other_user.id,
        reimbursement_wallet_id=wallet.id,
        date_of_birth_provided="2000-01-01",
        email=TEST_EMAIL,
        created_at=datetime(2023, 1, 1),
    )

    res = client.delete(
        f"/api/v1/reimbursement_wallet/invitation/{invitation_from_other_user.id}",
        headers=api_helpers.json_headers(enterprise_user),
    )

    assert res.status_code == 404
    content = api_helpers.load_json(res)
    assert content == {"message": "Cannot find the invitation."}

    assert_no_consent_changes(enterprise_user.id, TEST_EMAIL)


def assert_no_consent_changes(user_id: int, recipient_email: str):
    consent = WalletUserConsent.query.filter(
        WalletUserConsent.consent_giver_id == user_id,
        WalletUserConsent.recipient_email == recipient_email,
    ).all()
    assert consent == []
