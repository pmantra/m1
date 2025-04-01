from __future__ import annotations

from datetime import datetime, timedelta
from unittest.mock import Mock, patch
from uuid import UUID

import pytest

from pytests.factories import EnterpriseUserFactory, ReimbursementWalletUsersFactory
from wallet.models.constants import ConsentOperation, WalletUserType
from wallet.models.reimbursement_wallet_user import ReimbursementWalletUsers
from wallet.models.wallet_user_consent import WalletUserConsent
from wallet.models.wallet_user_invite import WalletUserInvite
from wallet.pytests.factories import (
    ReimbursementWalletFactory,
    WalletUserConsentFactory,
    WalletUserInviteFactory,
)
from wallet.pytests.wallet.resources.conftest import shareable_wallet  # noqa: F401
from wallet.resources.wallet_invitation import check_invitation

EXPIRATION_TIME = timedelta(days=3)
TEST_EMAIL = "stubble@gillette.shave"


@pytest.fixture(scope="function")
def shareable_wallet_and_user(shareable_wallet, enterprise_user):  # noqa: F811
    """
    Returns a tuple (shareable_reimbursement_wallet, invitation_recipient)
    with the user's DOB set to 2000-07-04.
    """
    dob = "2000-07-04"
    wallet = shareable_wallet(enterprise_user, WalletUserType.EMPLOYEE)
    recipient = EnterpriseUserFactory.create(email=TEST_EMAIL)
    recipient.health_profile.json["birthday"] = dob
    return wallet, recipient


def test_post_invitation_decision_accept(
    client,
    enterprise_user,
    api_helpers,
    shareable_wallet_and_user,
):
    wallet, recipient = shareable_wallet_and_user

    invitation = WalletUserInviteFactory.create(
        created_by_user_id=enterprise_user.id,
        reimbursement_wallet_id=wallet.id,
        date_of_birth_provided=recipient.health_profile.json["birthday"],
        email=TEST_EMAIL,
    )

    original_consent_entry = WalletUserConsentFactory.create(
        consent_giver_id=enterprise_user.id,
        consent_recipient_id=None,
        recipient_email=recipient.email,
        reimbursement_wallet_id=wallet.id,
        operation=ConsentOperation.GIVE_CONSENT,
    )

    body = {"accept": True}
    with patch(
        "wallet.services.reimbursement_wallet_messaging.send_general_ticket_to_zendesk"
    ) as zendesk_ticket_mock, patch(
        "wallet.resources.wallet_invitation.successfully_enroll_partner"
    ) as enroll_mock, patch(
        "wallet.resources.wallet_invitation.BrazeClient"
    ) as braze_client_mock:
        return_mock = Mock()
        braze_client_mock.return_value = return_mock

        enroll_mock.return_value = True
        zendesk_ticket_mock.return_value = 2923
        res = client.post(
            f"/api/v1/reimbursement_wallet/invitation/{invitation.id}",
            headers=api_helpers.json_headers(recipient),
            data=api_helpers.json_data(body),
        )
        assert return_mock.track_user.call_count == 1

    # Make sure we have updated and claimed the invitation.
    assert_invitation_exists_and_status(invitation.id, is_claimed=True)

    assert res.status_code == 200
    content = api_helpers.load_json(res)
    assert content == {"message": "The invitation has been accepted."}

    updated_consent_entry = WalletUserConsent.query.filter(
        WalletUserConsent.id == original_consent_entry.id
    ).one()
    assert updated_consent_entry.consent_recipient_id == recipient.id
    consent_from_recipient = WalletUserConsent.query.filter(
        WalletUserConsent.consent_giver_id == recipient.id,
        WalletUserConsent.consent_recipient_id == enterprise_user.id,
    ).one()
    assert consent_from_recipient

    # Tests for new RWU
    rwu = ReimbursementWalletUsers.query.filter(
        ReimbursementWalletUsers.reimbursement_wallet_id == wallet.id,
        ReimbursementWalletUsers.user_id == recipient.id,
    ).one()
    assert rwu.channel_id is not None and rwu.zendesk_ticket_id is not None

    # Make sure we sent the email via braze
    notification_mock_kwargs = return_mock.track_user.call_args.kwargs
    assert len(notification_mock_kwargs) == 1
    events = notification_mock_kwargs["events"]
    assert len(events) == 1
    event = events[0]
    assert event.external_id == enterprise_user.esp_id
    assert event.name == "share_a_wallet_partner_joined"
    assert event.properties == {
        "partner_a_name": enterprise_user.first_name,
        "partner_b_name": recipient.first_name,
    }


def test_invitation_id_is_not_uuid(client, enterprise_user, api_helpers):
    weird_invitation_id = "this can't b3 a UU1D!"
    body = {"accept": True}
    res = client.post(
        f"/api/v1/reimbursement_wallet/invitation/{weird_invitation_id}",
        headers=api_helpers.json_headers(enterprise_user),
        data=api_helpers.json_data(body),
    )

    assert res.status_code == 404
    content = api_helpers.load_json(res)
    assert content == {"message": "Cannot find the invitation."}


def test_post_invitation_decision_decline(
    client, enterprise_user, api_helpers, shareable_wallet_and_user
):
    wallet, recipient = shareable_wallet_and_user

    invitation = WalletUserInviteFactory.create(
        created_by_user_id=enterprise_user.id,
        reimbursement_wallet_id=wallet.id,
        date_of_birth_provided=recipient.health_profile.json["birthday"],
        email=TEST_EMAIL,
    )

    WalletUserConsentFactory.create(
        consent_giver_id=enterprise_user.id,
        consent_recipient_id=None,
        recipient_email=recipient.email,
        reimbursement_wallet_id=wallet.id,
        operation=ConsentOperation.GIVE_CONSENT,
    )

    body = {"accept": False}

    res = client.post(
        f"/api/v1/reimbursement_wallet/invitation/{invitation.id}",
        headers=api_helpers.json_headers(recipient),
        data=api_helpers.json_data(body),
    )

    # Make sure we have updated and claimed the invitation
    assert_invitation_exists_and_status(invitation.id, is_claimed=True)

    assert res.status_code == 200
    content = api_helpers.load_json(res)
    assert content == {"message": "The invitation has been declined."}

    consent_from_recipient = WalletUserConsent.query.filter(
        WalletUserConsent.consent_giver_id == recipient.id,
        WalletUserConsent.consent_recipient_id == enterprise_user.id,
    ).one_or_none()
    assert consent_from_recipient is None


def test_cannot_join_wallet_without_enrolling(
    client,
    enterprise_user,
    api_helpers,
    shareable_wallet_and_user,
):
    wallet, recipient = shareable_wallet_and_user

    invitation = WalletUserInviteFactory.create(
        created_by_user_id=enterprise_user.id,
        reimbursement_wallet_id=wallet.id,
        date_of_birth_provided=recipient.health_profile.json["birthday"],
        email=TEST_EMAIL,
    )

    WalletUserConsentFactory.create(
        consent_giver_id=enterprise_user.id,
        consent_recipient_id=None,
        recipient_email=recipient.email,
        reimbursement_wallet_id=wallet.id,
        operation=ConsentOperation.GIVE_CONSENT,
    )
    body = {"accept": True}
    with patch(
        "wallet.services.reimbursement_wallet_messaging.send_general_ticket_to_zendesk"
    ) as zendesk_ticket_mock, patch(
        "wallet.resources.wallet_invitation.successfully_enroll_partner"
    ) as enroll_mock:
        enroll_mock.return_value = False
        zendesk_ticket_mock.return_value = 2923
        res = client.post(
            f"/api/v1/reimbursement_wallet/invitation/{invitation.id}",
            headers=api_helpers.json_headers(recipient),
            data=api_helpers.json_data(body),
        )
    # Do not yet claim the invitation.
    assert_invitation_exists_and_status(invitation.id, is_claimed=False)

    consent_from_recipient = WalletUserConsent.query.filter(
        WalletUserConsent.consent_giver_id == recipient.id,
        WalletUserConsent.consent_recipient_id == enterprise_user.id,
    ).one_or_none()
    assert consent_from_recipient is None

    assert res.status_code == 500
    content = api_helpers.load_json(res)
    assert content == {"message": "Unable to accept invitation."}

    # Tests for new RWU
    rwu = ReimbursementWalletUsers.query.filter(
        ReimbursementWalletUsers.reimbursement_wallet_id == wallet.id,
        ReimbursementWalletUsers.user_id == recipient.id,
    ).one()
    assert rwu.channel_id is not None and rwu.zendesk_ticket_id is not None


def test_try_to_join_wallet_with_2_users(
    client, enterprise_user, api_helpers, shareable_wallet_and_user
):
    """
    This test case happens when Partner A invites Partner B to join the wallet.
    Partner A also contacts the CSR team to invite Partner C to join the wallet.
    Partner C joins the wallet first.
    Then Partner B tries to join the wallet, but we don't have a consent record
    between Partner B and Partner C, so the CSR team needs to handle this, and
    we should not let Partner B accept the invitation.
    """
    wallet, recipient = shareable_wallet_and_user

    invitation = WalletUserInviteFactory.create(
        created_by_user_id=enterprise_user.id,
        reimbursement_wallet_id=wallet.id,
        date_of_birth_provided=recipient.health_profile.json["birthday"],
        email=TEST_EMAIL,
    )
    some_other_user = EnterpriseUserFactory.create()

    ReimbursementWalletUsersFactory.create(
        reimbursement_wallet_id=wallet.id,
        user_id=some_other_user.id,
    )

    WalletUserConsentFactory.create(
        consent_giver_id=enterprise_user.id,
        consent_recipient_id=None,
        recipient_email=recipient.email,
        reimbursement_wallet_id=wallet.id,
        operation=ConsentOperation.GIVE_CONSENT,
    )

    body = {"accept": True}
    res = client.post(
        f"/api/v1/reimbursement_wallet/invitation/{invitation.id}",
        headers=api_helpers.json_headers(recipient),
        data=api_helpers.json_data(body),
    )

    # Do not yet claim the invitation.
    assert_invitation_exists_and_status(invitation.id, is_claimed=False)

    assert res.status_code == 501
    content = api_helpers.load_json(res)
    assert content == {"message": "Please message the Wallet team to join the wallet."}

    consent_from_recipient = WalletUserConsent.query.filter(
        WalletUserConsent.consent_giver_id == recipient.id,
        WalletUserConsent.consent_recipient_id == enterprise_user.id,
    ).one_or_none()
    assert consent_from_recipient is None


def test_expired_invitation(
    client, enterprise_user, api_helpers, shareable_wallet_and_user
):
    wallet, recipient = shareable_wallet_and_user

    invitation = WalletUserInviteFactory.create(
        created_by_user_id=enterprise_user.id,
        reimbursement_wallet_id=wallet.id,
        date_of_birth_provided=recipient.health_profile.json["birthday"],
        email=TEST_EMAIL,
        created_at=datetime(2023, 1, 1),
    )
    body = {"accept": False}
    res = client.post(
        f"/api/v1/reimbursement_wallet/invitation/{invitation.id}",
        headers=api_helpers.json_headers(recipient),
        data=api_helpers.json_data(body),
    )

    assert res.status_code == 409
    content = api_helpers.load_json(res)
    assert content == {"message": "Invitation expired."}


def test_invitation_was_already_used(
    client, enterprise_user, api_helpers, shareable_wallet_and_user
):
    wallet, recipient = shareable_wallet_and_user

    invitation = WalletUserInviteFactory.create(
        created_by_user_id=enterprise_user.id,
        reimbursement_wallet_id=wallet.id,
        date_of_birth_provided=recipient.health_profile.json["birthday"],
        email=TEST_EMAIL,
        claimed=True,
    )

    body = {"accept": False}
    res = client.post(
        f"/api/v1/reimbursement_wallet/invitation/{invitation.id}",
        headers=api_helpers.json_headers(recipient),
        data=api_helpers.json_data(body),
    )

    assert res.status_code == 200
    content = api_helpers.load_json(res)
    assert content == {"message": "Invitation already used."}


def test_invitation_birthday_not_set(client, enterprise_user, api_helpers):
    wallet = ReimbursementWalletFactory.create(id=123123)
    recipient = EnterpriseUserFactory.create(email=TEST_EMAIL)
    if "birthday" in recipient.health_profile.json:
        del recipient.health_profile.json["birthday"]

    invitation_from_other_user = WalletUserInviteFactory.create(
        created_by_user_id=enterprise_user.id,
        reimbursement_wallet_id=wallet.id,
        date_of_birth_provided="2000-01-01",
        email=TEST_EMAIL,
        created_at=datetime(2023, 1, 1),
    )

    body = {"accept": False}
    res = client.post(
        f"/api/v1/reimbursement_wallet/invitation/{invitation_from_other_user.id}",
        headers=api_helpers.json_headers(recipient),
        data=api_helpers.json_data(body),
    )

    assert res.status_code == 409
    content = api_helpers.load_json(res)
    assert content == {"message": "Your information did not match the invitation."}


def test_cannot_access_other_users_invitation(
    client, enterprise_user, api_helpers, shareable_wallet_and_user
):
    wallet, recipient = shareable_wallet_and_user

    invitation = WalletUserInviteFactory.create(
        created_by_user_id=enterprise_user.id,
        reimbursement_wallet_id=wallet.id,
        date_of_birth_provided=recipient.health_profile.json["birthday"],
        email=TEST_EMAIL,
    )

    malicious_other_recipient = EnterpriseUserFactory.create(email="sneaky@evil.corp")
    malicious_other_recipient.health_profile.json[
        "birthday"
    ] = recipient.health_profile.json["birthday"]

    body = {"accept": False}
    res = client.post(
        f"/api/v1/reimbursement_wallet/invitation/{invitation.id}",
        headers=api_helpers.json_headers(malicious_other_recipient),
        data=api_helpers.json_data(body),
    )

    assert res.status_code == 409
    content = api_helpers.load_json(res)
    assert content == {"message": "Your information did not match the invitation."}

    # Make sure the invitation is no longer usable after a data mismatch.
    # The invitation should record a mismatch in the recipient's information.
    assert_invitation_exists_and_status(invitation.id, True, True)


def test_invitation_birthday_mismatch(
    client, enterprise_user, api_helpers, shareable_wallet_and_user
):
    wallet, recipient = shareable_wallet_and_user

    invitation = WalletUserInviteFactory.create(
        created_by_user_id=enterprise_user.id,
        reimbursement_wallet_id=wallet.id,
        date_of_birth_provided="1929-12-11",
        email=TEST_EMAIL,
    )

    body = {"accept": True}
    res = client.post(
        f"/api/v1/reimbursement_wallet/invitation/{invitation.id}",
        headers=api_helpers.json_headers(recipient),
        data=api_helpers.json_data(body),
    )

    assert res.status_code == 409
    content = api_helpers.load_json(res)
    assert content == {"message": "Your information did not match the invitation."}

    # The invitation should be unusable after a data mismatch occurs when it is accessed.
    assert_invitation_exists_and_status(invitation.id, is_claimed=True)


def test_invitation_wallet_on_non_sharable_wallet(
    client,
    enterprise_user,
    api_helpers,
):
    exp_status_code = 409
    exp_message = {"message": "This wallet cannot be shared."}
    wallet = ReimbursementWalletFactory.create(id=123123)

    recipient = EnterpriseUserFactory.create(email=TEST_EMAIL)
    recipient.health_profile.json["birthday"] = "2000-07-04"

    invitation = WalletUserInviteFactory.create(
        created_by_user_id=enterprise_user.id,
        reimbursement_wallet_id=wallet.id,
        date_of_birth_provided="2000-07-04",
        email=TEST_EMAIL,
    )
    WalletUserConsentFactory.create(
        consent_giver_id=enterprise_user.id,
        consent_recipient_id=None,
        recipient_email=recipient.email,
        reimbursement_wallet_id=wallet.id,
        operation=ConsentOperation.GIVE_CONSENT,
    )
    body = {"accept": True}

    with patch(
        "wallet.services.reimbursement_wallet_messaging.send_general_ticket_to_zendesk"
    ), patch("wallet.resources.wallet_invitation.successfully_enroll_partner"), patch(
        "wallet.resources.wallet_invitation.BrazeClient"
    ) as braze_client_mock:
        return_mock = Mock()
        braze_client_mock.return_value = return_mock
        res = client.post(
            f"/api/v1/reimbursement_wallet/invitation/{invitation.id}",
            headers=api_helpers.json_headers(recipient),
            data=api_helpers.json_data(body),
        )

    assert res.status_code == exp_status_code
    content = api_helpers.load_json(res)
    assert content == exp_message

    # Make sure the invitation is no longer usable.test_post_invitation_decision_accept
    assert_invitation_exists_and_status(invitation.id, is_claimed=True)


def test_check_invitation_happy_path(
    enterprise_user,
    shareable_wallet_and_user,
):
    wallet, recipient = shareable_wallet_and_user

    invitation = WalletUserInviteFactory.create(
        created_by_user_id=enterprise_user.id,
        reimbursement_wallet_id=wallet.id,
        date_of_birth_provided=recipient.health_profile.json["birthday"],
        email=TEST_EMAIL,
    )

    result = check_invitation(recipient, str(invitation.id), invitation)

    assert result is None
    # Make sure we have updated and claimed the invitation.
    assert_invitation_exists_and_status(invitation.id, is_claimed=False)


def test_check_invitation_try_to_join_wallet_with_2_users(
    enterprise_user,
    shareable_wallet_and_user,
):
    """
    This test case happens when Partner A invites Partner B to join the wallet.
    Partner A also contacts the CSR team to invite Partner C to join the wallet.
    Partner C joins the wallet first.
    Then Partner B tries to join the wallet, but we don't have a consent record
    between Partner B and Partner C, so the CSR team needs to handle this, and
    we should not let Partner B accept the invitation.
    """
    wallet, recipient = shareable_wallet_and_user

    invitation = WalletUserInviteFactory.create(
        created_by_user_id=enterprise_user.id,
        reimbursement_wallet_id=wallet.id,
        date_of_birth_provided=recipient.health_profile.json["birthday"],
        email=TEST_EMAIL,
    )
    some_other_user = EnterpriseUserFactory.create()

    ReimbursementWalletUsersFactory.create(
        reimbursement_wallet_id=wallet.id,
        user_id=some_other_user.id,
    )

    result = check_invitation(recipient, str(invitation.id), invitation)

    assert result == (
        {"message": "Please message the Wallet team to join the wallet."},
        501,
    )
    # Make sure we have updated and claimed the invitation.
    # Do not yet claim the invitation.
    assert_invitation_exists_and_status(invitation.id, is_claimed=False)


def test_check_invitation_expired_invitation(
    enterprise_user, shareable_wallet_and_user
):
    wallet, recipient = shareable_wallet_and_user

    invitation = WalletUserInviteFactory.create(
        created_by_user_id=enterprise_user.id,
        reimbursement_wallet_id=wallet.id,
        date_of_birth_provided=recipient.health_profile.json["birthday"],
        email=TEST_EMAIL,
        created_at=datetime(1900, 1, 1),
    )
    result = check_invitation(recipient, str(invitation.id), invitation)
    assert result == ({"message": "Invitation expired."}, 409)

    assert_invitation_exists_and_status(invitation.id, is_claimed=False)


def test_check_invitation_invitation_was_already_used(
    enterprise_user, shareable_wallet_and_user
):
    wallet, recipient = shareable_wallet_and_user

    invitation = WalletUserInviteFactory.create(
        created_by_user_id=enterprise_user.id,
        reimbursement_wallet_id=wallet.id,
        date_of_birth_provided=recipient.health_profile.json["birthday"],
        email=TEST_EMAIL,
        claimed=True,
    )

    result = check_invitation(recipient, str(invitation.id), invitation)
    assert result == ({"message": "Invitation already used."}, 200)

    assert_invitation_exists_and_status(invitation.id, is_claimed=True)


def test_check_invitation_birthday_not_set(enterprise_user):
    wallet = ReimbursementWalletFactory.create(id=123123)
    recipient = EnterpriseUserFactory.create(email=TEST_EMAIL)
    if "birthday" in recipient.health_profile.json:
        del recipient.health_profile.json["birthday"]

    invitation_from_other_user = WalletUserInviteFactory.create(
        created_by_user_id=enterprise_user.id,
        reimbursement_wallet_id=wallet.id,
        date_of_birth_provided="2000-01-01",
        email=TEST_EMAIL,
        created_at=datetime(2023, 1, 1),
    )

    result = check_invitation(
        recipient, str(invitation_from_other_user.id), invitation_from_other_user
    )
    assert result == (
        {"message": "Your information did not match the invitation."},
        409,
    )

    assert_invitation_exists_and_status(invitation_from_other_user.id, is_claimed=True)


def test_check_invitation_cannot_access_other_users_invitation(enterprise_user):
    dob = "2000-07-04"
    wallet = ReimbursementWalletFactory.create(id=123123)
    # This is the true recipient
    true_recipient = EnterpriseUserFactory.create(email=TEST_EMAIL)
    true_recipient.health_profile.json["birthday"] = dob

    malicious_other_recipient = EnterpriseUserFactory.create(email="sneaky@evil.corp")
    malicious_other_recipient.health_profile.json["birthday"] = dob

    invitation = WalletUserInviteFactory.create(
        created_by_user_id=enterprise_user.id,
        reimbursement_wallet_id=wallet.id,
        date_of_birth_provided=dob,
        email=TEST_EMAIL,
    )

    result = check_invitation(malicious_other_recipient, str(invitation.id), invitation)
    assert result == (
        {"message": "Your information did not match the invitation."},
        409,
    )

    assert_invitation_exists_and_status(invitation.id, True, True)


def test_check_invitation_invitation_birthday_mismatch(
    enterprise_user, shareable_wallet_and_user
):
    wallet, recipient = shareable_wallet_and_user

    invitation = WalletUserInviteFactory.create(
        created_by_user_id=enterprise_user.id,
        reimbursement_wallet_id=wallet.id,
        date_of_birth_provided="1929-12-11",
        email=TEST_EMAIL,
    )

    result = check_invitation(recipient, str(invitation.id), invitation)
    assert result == (
        {"message": "Your information did not match the invitation."},
        409,
    )

    assert_invitation_exists_and_status(invitation.id, True, True)


def test_check_invitation_non_sharable_wallet(enterprise_user):
    wallet = ReimbursementWalletFactory.create(id=123123)

    recipient = EnterpriseUserFactory.create(email=TEST_EMAIL)
    recipient.health_profile.json["birthday"] = "2000-07-04"

    invitation = WalletUserInviteFactory.create(
        created_by_user_id=enterprise_user.id,
        reimbursement_wallet_id=wallet.id,
        date_of_birth_provided="2000-07-04",
        email=TEST_EMAIL,
    )

    result = check_invitation(recipient, str(invitation.id), invitation)
    # This shouldn't be possible because you shouldn't be able to share
    # the wallet if it isn't shareable.
    assert result == ({"message": "This wallet cannot be shared."}, 409)

    assert_invitation_exists_and_status(invitation.id, is_claimed=True)


def assert_invitation_exists_and_status(
    invitation_id: UUID,
    is_claimed: bool | None = None,
    has_info_mismatch: bool | None = None,
) -> None:
    invitation = WalletUserInvite.query.filter(
        WalletUserInvite.id == invitation_id
    ).one()
    if is_claimed is not None:
        assert invitation.claimed is is_claimed
    if has_info_mismatch is not None:
        assert invitation.has_info_mismatch is has_info_mismatch
