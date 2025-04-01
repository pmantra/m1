from datetime import datetime, timedelta

from wallet.models.constants import WalletUserStatus, WalletUserType
from wallet.pytests.factories import (
    ReimbursementWalletFactory,
    ReimbursementWalletUsersFactory,
    WalletUserInviteFactory,
)


def test_get_wallet_users_happy_path(client, enterprise_user, api_helpers, factories):
    wallet = ReimbursementWalletFactory.create(id=123123)

    active_user = factories.DefaultUserFactory.create(
        first_name="Victor", last_name="Wemby"
    )

    pending_user = factories.DefaultUserFactory.create(
        first_name="A", last_name="B", email="mirzakhani@viazovska.com"
    )
    denied_user = factories.DefaultUserFactory.create(
        first_name="Inacty", last_name="McGee"
    )

    expired_time = datetime(year=2023, month=10, day=1)
    # Untouched, expired invitation
    WalletUserInviteFactory.create(
        created_at=expired_time,
        modified_at=expired_time,
        email="barry@lolo.toot",
        created_by_user_id=enterprise_user.id,
        reimbursement_wallet_id=wallet.id,
    )
    # Untouched, unexpired invitation
    untouched_unexpired_invite = WalletUserInviteFactory.create(
        email="figalli@maggi.caffarelli",
        created_by_user_id=enterprise_user.id,
        reimbursement_wallet_id=wallet.id,
    )
    # Claimed invitation for pending user
    # Should not matter
    WalletUserInviteFactory.create(
        email="mirzakhani@viazovska.com",
        created_by_user_id=enterprise_user.id,
        reimbursement_wallet_id=wallet.id,
        claimed=True,
    )

    # Declined invitation, should not show
    WalletUserInviteFactory.create(
        email="decline@isocline.geo",
        created_by_user_id=enterprise_user.id,
        reimbursement_wallet_id=wallet.id,
        claimed=True,
        has_info_mismatch=False,
    )
    # Invitation for someone whose name did not match the health profile
    WalletUserInviteFactory.create(
        email="kotomi@ryan.elder",
        created_by_user_id=enterprise_user.id,
        reimbursement_wallet_id=wallet.id,
        has_info_mismatch=True,
        claimed=True,
    )
    # Invitation not created by this user.
    WalletUserInviteFactory.create(
        email="emmy@noether.math",
        # Realistically, then pending user would never create an
        # invitation - this is just for the sake of having a different
        # user_id as the creator
        created_by_user_id=pending_user.id,
        reimbursement_wallet_id=wallet.id,
        has_info_mismatch=False,
    )

    setup = (
        # User, status, type
        (enterprise_user, WalletUserStatus.ACTIVE, WalletUserType.EMPLOYEE),
        (active_user, WalletUserStatus.ACTIVE, WalletUserType.DEPENDENT),
        (pending_user, WalletUserStatus.PENDING, WalletUserType.DEPENDENT),
        (denied_user, WalletUserStatus.DENIED, WalletUserType.DEPENDENT),
    )

    for user, status, wallet_user_type in setup:
        ReimbursementWalletUsersFactory.create(
            user_id=user.id,
            reimbursement_wallet_id=wallet.id,
            status=status,
            type=wallet_user_type,
        )

    res = client.get(
        f"/api/v1/reimbursement_wallet/{wallet.id}/users",
        headers=api_helpers.json_headers(enterprise_user),
    )

    assert res.status_code == 200
    content = api_helpers.load_json(res)
    users_list = content["users"]
    assert len(users_list) == 6

    users_list.sort(key=lambda dict_obj: dict_obj["title"])
    assert users_list[0] == {
        "title": "Victor Wemby",
        "status": "Approved",
        "can_cancel_invitation": False,
        "invitation_id": "",
    }
    assert users_list[1] == {
        "title": "barry@lolo.toot",
        "status": "Invitation expired",
        "can_cancel_invitation": False,
        "invitation_id": "",
    }
    assert users_list[2] == {
        "title": "emmy@noether.math",
        "status": "Invitation sent",
        "can_cancel_invitation": False,
        "invitation_id": "",
    }
    assert users_list[3] == {
        "title": "figalli@maggi.caffarelli",
        "status": "Invitation sent",
        "can_cancel_invitation": True,
        "invitation_id": str(untouched_unexpired_invite.id),
    }
    assert users_list[4] == {
        "title": "kotomi@ryan.elder",
        "status": (
            "The info you entered does not match your partner's "
            "account. Please add partner again to send a new "
            "invitation."
        ),
        "can_cancel_invitation": False,
        "invitation_id": "",
    }
    assert users_list[5] == {
        "title": "mirzakhani@viazovska.com",
        "status": "Pending approval",
        "can_cancel_invitation": False,
        "invitation_id": "",
    }


def test_get_wallet_users_ops_rwu_invitation_display(
    client, enterprise_user, api_helpers, factories
):
    # This should NOT be possible based on the backend code,
    # but could happen if ops manually adds the user.
    # If the invitation was NOT marked as claimed, but the
    # user was added on the wallet, then we do not want to
    # show the invitation status.
    wallet = ReimbursementWalletFactory.create(id=123123)

    pending_user = factories.DefaultUserFactory.create(email="barry@lolo.toot")
    expired_time = datetime(year=2023, month=10, day=1)
    # Untouched, expired invitation
    WalletUserInviteFactory.create(
        created_at=expired_time,
        modified_at=expired_time,
        email="barry@lolo.toot",
        created_by_user_id=enterprise_user.id,
        reimbursement_wallet_id=wallet.id,
    )

    # User, status, type
    setup = (
        (enterprise_user, WalletUserStatus.ACTIVE, WalletUserType.EMPLOYEE),
        # If Ops created the RWU manually
        (pending_user, WalletUserStatus.PENDING, WalletUserType.DEPENDENT),
    )
    for user, status, wallet_user_type in setup:
        ReimbursementWalletUsersFactory.create(
            user_id=user.id,
            reimbursement_wallet_id=wallet.id,
            status=status,
            type=wallet_user_type,
        )

    res = client.get(
        f"/api/v1/reimbursement_wallet/{wallet.id}/users",
        headers=api_helpers.json_headers(enterprise_user),
    )

    assert res.status_code == 200
    content = api_helpers.load_json(res)
    users_list = content["users"]
    assert len(users_list) == 1

    # Even though the invitation hasn't been claimed, we should show
    # the invited user (who is now a PENDING RWU) as pending.
    assert users_list[0] == {
        "title": "barry@lolo.toot",
        "status": "Pending approval",
        "can_cancel_invitation": False,
        "invitation_id": "",
    }


def test_get_wallet_users_unauthorized(client, enterprise_user, api_helpers):
    wallet = ReimbursementWalletFactory.create()
    other_wallet = ReimbursementWalletFactory.create()
    ReimbursementWalletUsersFactory.create(
        user_id=enterprise_user.id,
        reimbursement_wallet_id=wallet.id,
    )

    res = client.get(
        f"/api/v1/reimbursement_wallet/{other_wallet.id}/users",
        headers=api_helpers.json_headers(enterprise_user),
    )

    assert res.status_code == 401
    content = api_helpers.load_json(res)
    assert content["message"] == "User is not authorized to access the wallet."


def test_get_wallet_users_shows_most_recent_invite(
    client,
    enterprise_user,
    api_helpers,
):
    wallet = ReimbursementWalletFactory.create(id=123123)

    yesterday = datetime.now() - timedelta(days=1)
    # Create a claimed invitation from yesterday
    WalletUserInviteFactory.create(
        created_at=yesterday,
        modified_at=yesterday,
        email="cauchy@bunyakovsky.schwarz",
        created_by_user_id=enterprise_user.id,
        reimbursement_wallet_id=wallet.id,
        claimed=True,
    )

    # Create an unclaimed, more recent invitation
    untouched_unexpired_invite = WalletUserInviteFactory.create(
        email="cauchy@bunyakovsky.schwarz",
        created_by_user_id=enterprise_user.id,
        reimbursement_wallet_id=wallet.id,
    )

    ReimbursementWalletUsersFactory.create(
        user_id=enterprise_user.id,
        reimbursement_wallet_id=wallet.id,
        status=WalletUserStatus.ACTIVE,
        type=WalletUserType.DEPENDENT,
    )

    res = client.get(
        f"/api/v1/reimbursement_wallet/{wallet.id}/users",
        headers=api_helpers.json_headers(enterprise_user),
    )

    assert res.status_code == 200
    content = api_helpers.load_json(res)
    users_list = content["users"]
    assert len(users_list) == 1

    assert users_list[0] == {
        "title": "cauchy@bunyakovsky.schwarz",
        "status": "Invitation sent",
        "can_cancel_invitation": True,
        "invitation_id": str(untouched_unexpired_invite.id),
    }
