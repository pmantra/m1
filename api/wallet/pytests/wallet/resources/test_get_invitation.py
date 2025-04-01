from datetime import datetime, timedelta
from unittest.mock import patch

import pytest

from pytests.factories import EnterpriseUserFactory, ReimbursementWalletUsersFactory
from wallet.models.constants import WalletState, WalletUserStatus, WalletUserType
from wallet.models.wallet_user_invite import WalletUserInvite
from wallet.pytests.factories import ReimbursementWalletFactory, WalletUserInviteFactory

EXPIRATION_TIME = timedelta(days=3)
TEST_EMAIL = "john@frink.professor"


@pytest.mark.parametrize(
    argnames="wallet_user_type, ",
    argvalues=(
        WalletUserType.EMPLOYEE,
        WalletUserType.DEPENDENT,
    ),
)
def test_get_invitation_happy_path(
    client,
    enterprise_user,
    api_helpers,
    shareable_wallet,
    wallet_user_type,
):
    wallet = shareable_wallet(enterprise_user, wallet_user_type)
    dob = "2000-07-04"
    recipient = EnterpriseUserFactory.create(email=TEST_EMAIL)
    recipient.health_profile.json["birthday"] = dob

    invitation = WalletUserInviteFactory.create(
        created_by_user_id=enterprise_user.id,
        reimbursement_wallet_id=wallet.id,
        date_of_birth_provided=dob,
        email=TEST_EMAIL,
    )

    res = client.get(
        f"/api/v1/reimbursement_wallet/invitation/{invitation.id}",
        headers=api_helpers.json_headers(recipient),
    )

    # Make sure we have updated and claimed the invitation
    invitation_after_access = WalletUserInvite.query.filter(
        WalletUserInvite.id == invitation.id
    ).one()
    assert invitation_after_access.claimed is False
    assert invitation_after_access.id == invitation.id

    assert res.status_code == 200
    content = api_helpers.load_json(res)
    assert content == {
        "message": "Invitation found.",
        "inviter_name": enterprise_user.first_name,
        "survey_url": f"fake-url?member_id_hash={recipient.esp_id}",
    }


@pytest.mark.parametrize(
    argnames=("is_flag_on",),
    argvalues=((True,), (False,)),
)
def test_get_invitation_survey_url_flag(
    client,
    enterprise_user,
    api_helpers,
    shareable_wallet,
    is_flag_on: bool,
):
    wallet = shareable_wallet(enterprise_user, WalletUserType.EMPLOYEE)
    dob = "2000-07-04"
    recipient = EnterpriseUserFactory.create(email=TEST_EMAIL)
    recipient.health_profile.json["birthday"] = dob

    invitation = WalletUserInviteFactory.create(
        created_by_user_id=enterprise_user.id,
        reimbursement_wallet_id=wallet.id,
        date_of_birth_provided=dob,
        email=TEST_EMAIL,
    )
    with patch(
        "wallet.resources.wallet_invitation.use_legacy_survey_monkey_url",
        return_value=is_flag_on,
    ) as mock_use_legacy_survey_monkey_url:
        res = client.get(
            f"/api/v1/reimbursement_wallet/invitation/{invitation.id}",
            headers=api_helpers.json_headers(recipient),
        )
        mock_use_legacy_survey_monkey_url.assert_called_once()

    # Make sure we have updated and claimed the invitation
    invitation_after_access = WalletUserInvite.query.filter(
        WalletUserInvite.id == invitation.id
    ).one()
    assert invitation_after_access.claimed is False
    assert invitation_after_access.id == invitation.id

    assert res.status_code == 200
    content = api_helpers.load_json(res)
    assert len(content) == 3
    assert content["message"] == "Invitation found."
    assert content["inviter_name"] == enterprise_user.first_name
    if is_flag_on:
        assert content["survey_url"] == f"fake-url?member_id_hash={recipient.esp_id}"
    else:
        assert content["survey_url"].endswith("/app/wallet/apply")


@pytest.mark.parametrize(
    argnames="wallet_user_type,",
    argvalues=(
        WalletUserType.EMPLOYEE,
        WalletUserType.DEPENDENT,
    ),
)
def test_get_invitation_happy_path_email_case_insensitive(
    client,
    enterprise_user,
    api_helpers,
    shareable_wallet,
    wallet_user_type,
):
    wallet = shareable_wallet(enterprise_user, wallet_user_type)
    dob = "2000-07-04"
    recipient = EnterpriseUserFactory.create(email=TEST_EMAIL)
    recipient.health_profile.json["birthday"] = dob

    invitation = WalletUserInviteFactory.create(
        created_by_user_id=enterprise_user.id,
        reimbursement_wallet_id=wallet.id,
        date_of_birth_provided=dob,
        email=TEST_EMAIL.upper(),
    )

    res = client.get(
        f"/api/v1/reimbursement_wallet/invitation/{invitation.id}",
        headers=api_helpers.json_headers(recipient),
    )

    # Make sure we have updated and claimed the invitation
    invitation_after_access = WalletUserInvite.query.filter(
        WalletUserInvite.id == invitation.id
    ).one()
    assert invitation_after_access.claimed is False
    assert invitation_after_access.id == invitation.id

    assert res.status_code == 200
    content = api_helpers.load_json(res)
    assert content == {
        "message": "Invitation found.",
        "inviter_name": enterprise_user.first_name,
        "survey_url": f"fake-url?member_id_hash={recipient.esp_id}",
    }


def test_invitation_id_is_not_uuid(client, enterprise_user, api_helpers):
    weird_invitation_id = "this can't b3 a UU1D!"
    res = client.get(
        f"/api/v1/reimbursement_wallet/invitation/{weird_invitation_id}",
        headers=api_helpers.json_headers(enterprise_user),
    )

    assert res.status_code == 404
    content = api_helpers.load_json(res)
    assert content == {
        "message": "Cannot find the invitation.",
        "inviter_name": "",
        "survey_url": "",
    }


def test_expired_invitation(client, enterprise_user, api_helpers):
    dob = "2000-07-04"
    wallet = ReimbursementWalletFactory.create()
    recipient = EnterpriseUserFactory.create(email=TEST_EMAIL)
    recipient.health_profile.json["birthday"] = dob

    invitation = WalletUserInviteFactory.create(
        created_by_user_id=enterprise_user.id,
        reimbursement_wallet_id=wallet.id,
        date_of_birth_provided=dob,
        email=TEST_EMAIL,
        created_at=datetime(2023, 1, 1),
    )
    res = client.get(
        f"/api/v1/reimbursement_wallet/invitation/{invitation.id}",
        headers=api_helpers.json_headers(recipient),
    )

    assert res.status_code == 409
    content = api_helpers.load_json(res)
    assert content == {
        "message": "Invitation expired.",
        "inviter_name": "",
        "survey_url": "",
    }


ALREADY_HAVE_ACTIVE_WALLET_RESPONSE = {
    "message": "It looks like you already have an active wallet.",
    "inviter_name": "",
    "survey_url": "",
}


@pytest.mark.parametrize(
    argnames="wallet_state, expected_response_code",
    argvalues=(
        (WalletState.QUALIFIED, 409),
        (WalletState.PENDING, 200),
        (WalletState.DISQUALIFIED, 200),
        (WalletState.EXPIRED, 200),
        (WalletState.RUNOUT, 200),
    ),
    ids=[
        "1. The wallet state is qualified and should count as an active wallet. wallet.is_shareable used.",
        "2. The wallet state is pending and should not count as an active wallet. wallet.is_shareable used.",
        "3. The wallet state is diqualified and should not count as an active wallet. wallet.is_shareable used.",
        "4. The wallet state is expired and should not count as an active wallet. wallet.is_shareable used.",
        "5. The wallet state has a runout state and should not count as an active wallet. wallet.is_shareable used.",
    ],
)
def test_only_consider_qualified_wallets_when_checking_existing_wallets(
    wallet_state,
    expected_response_code,
    client,
    enterprise_user,
    shareable_wallet,
    api_helpers,
):
    dob = "2000-07-04"

    wallet = shareable_wallet(enterprise_user, WalletUserType.EMPLOYEE)

    existing_partner_wallet = ReimbursementWalletFactory.create(state=wallet_state)
    assert existing_partner_wallet.state == wallet_state

    recipient = EnterpriseUserFactory.create(email=TEST_EMAIL)
    recipient.health_profile.json["birthday"] = dob
    ReimbursementWalletUsersFactory.create(
        reimbursement_wallet_id=existing_partner_wallet.id,
        user_id=recipient.id,
        status=WalletUserStatus.PENDING,  # PENDING or ACTIVE
        type=WalletUserType.DEPENDENT,
    )

    invitation = WalletUserInviteFactory.create(
        created_by_user_id=enterprise_user.id,
        reimbursement_wallet_id=wallet.id,
        date_of_birth_provided=dob,
        email=TEST_EMAIL,
    )

    res = client.get(
        f"/api/v1/reimbursement_wallet/invitation/{invitation.id}",
        headers=api_helpers.json_headers(recipient),
    )

    assert res.status_code == expected_response_code
    content = api_helpers.load_json(res)
    if expected_response_code == 409:
        assert content == {
            "message": "It looks like you already have an active wallet.",
            "inviter_name": "",
            "survey_url": "",
        }
    elif expected_response_code == 200:
        assert content == {
            "message": "Invitation found.",
            "inviter_name": enterprise_user.first_name,
            "survey_url": f"fake-url?member_id_hash={recipient.esp_id}",
        }


def test_invitation_was_already_used(client, enterprise_user, api_helpers):
    dob = "2000-07-04"
    wallet = ReimbursementWalletFactory.create()
    recipient = EnterpriseUserFactory.create(email=TEST_EMAIL)
    recipient.health_profile.json["birthday"] = dob

    invitation = WalletUserInviteFactory.create(
        created_by_user_id=enterprise_user.id,
        reimbursement_wallet_id=wallet.id,
        date_of_birth_provided=dob,
        email=TEST_EMAIL,
        claimed=True,
    )

    res = client.get(
        f"/api/v1/reimbursement_wallet/invitation/{invitation.id}",
        headers=api_helpers.json_headers(recipient),
    )

    assert res.status_code == 409
    content = api_helpers.load_json(res)
    assert content == {
        "message": "Invitation already used.",
        "inviter_name": "",
        "survey_url": "",
    }


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

    res = client.get(
        f"/api/v1/reimbursement_wallet/invitation/{invitation_from_other_user.id}",
        headers=api_helpers.json_headers(recipient),
    )

    assert res.status_code == 409
    content = api_helpers.load_json(res)
    assert content == {
        "message": "Missing profile information.",
        "inviter_name": "",
        "survey_url": "",
    }


def test_cannot_access_other_users_invitation(client, enterprise_user, api_helpers):
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

    res = client.get(
        f"/api/v1/reimbursement_wallet/invitation/{invitation.id}",
        headers=api_helpers.json_headers(malicious_other_recipient),
    )

    assert res.status_code == 409
    content = api_helpers.load_json(res)
    assert content == {
        "message": "Your information did not match the invitation.",
        "inviter_name": "",
        "survey_url": "",
    }

    # Make sure the invitation is no longer usable.
    invite = WalletUserInvite.query.filter(WalletUserInvite.id == invitation.id).one()
    assert (
        invite.claimed is True
    ), "The invitation should be unusable after a data mismatch occurs when it is accessed."
    assert (
        invite.has_info_mismatch is True
    ), "The invitation should record a mismatch in the recipient's information."


def test_invitation_birthday_mismatch(client, enterprise_user, api_helpers):
    wallet = ReimbursementWalletFactory.create(id=123123)

    recipient = EnterpriseUserFactory.create(email=TEST_EMAIL)
    recipient.health_profile.json["birthday"] = "2000-07-04"

    invitation = WalletUserInviteFactory.create(
        created_by_user_id=enterprise_user.id,
        reimbursement_wallet_id=wallet.id,
        date_of_birth_provided="1929-12-11",
        email=TEST_EMAIL,
    )

    res = client.get(
        f"/api/v1/reimbursement_wallet/invitation/{invitation.id}",
        headers=api_helpers.json_headers(recipient),
    )

    assert res.status_code == 409
    content = api_helpers.load_json(res)
    assert content == {
        "message": "Your information did not match the invitation.",
        "inviter_name": "",
        "survey_url": "",
    }

    # Make sure the invitation is no longer usable.
    invite = WalletUserInvite.query.filter(WalletUserInvite.id == invitation.id).one()
    assert (
        invite.claimed is True
    ), "The invitation should be unusable after a data mismatch occurs when it is accessed."


def test_get_invitation_wallet_not_shareable(
    client,
    enterprise_user,
    api_helpers,
):
    wallet = ReimbursementWalletFactory.create(id=123123)
    dob = "2000-07-04"
    recipient = EnterpriseUserFactory.create(email=TEST_EMAIL)
    recipient.health_profile.json["birthday"] = dob

    invitation = WalletUserInviteFactory.create(
        created_by_user_id=enterprise_user.id,
        reimbursement_wallet_id=wallet.id,
        date_of_birth_provided=dob,
        email=TEST_EMAIL,
    )

    res = client.get(
        f"/api/v1/reimbursement_wallet/invitation/{invitation.id}",
        headers=api_helpers.json_headers(recipient),
    )

    # Make sure we have updated and claimed the invitation
    invitation_after_access = WalletUserInvite.query.filter(
        WalletUserInvite.id == invitation.id
    ).one()
    assert invitation_after_access.id == invitation.id

    assert res.status_code == 409
    content = api_helpers.load_json(res)
    # Using an if here because this code is temporary and will be removed with the feature flag
    assert content == {
        "message": "This wallet cannot be shared.",
        "inviter_name": "",
        "survey_url": "",
    }
