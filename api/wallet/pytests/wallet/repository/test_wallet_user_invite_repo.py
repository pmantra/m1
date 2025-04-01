from __future__ import annotations

import pytest

from storage.connection import db  # noqa: F401, F811
from wallet.models.constants import WalletState
from wallet.pytests.factories import ReimbursementWalletFactory, WalletUserInviteFactory
from wallet.repository.wallet_user_invite import WalletUserInviteRepository


@pytest.fixture
def wallet_user_invite_repo(db):  # noqa: F811
    return WalletUserInviteRepository(db.session)


def test_get_latest_unclaimed_invite_unhappy(wallet_user_invite_repo, enterprise_user):
    wallet = ReimbursementWalletFactory.create(
        state=WalletState.QUALIFIED, user_id=enterprise_user.id
    )
    claimed_invite = WalletUserInviteFactory.create(
        email=enterprise_user.email,
        reimbursement_wallet_id=wallet.id,
        created_by_user_id=enterprise_user.id,  # Not at all realistic
        date_of_birth_provided="2000-01-01",
        claimed=True,
    )
    assert claimed_invite is not None

    result = wallet_user_invite_repo.get_latest_unclaimed_invite(enterprise_user.id)

    assert result is None


def test_get_latest_unclaimed_invite_happy(wallet_user_invite_repo, enterprise_user):
    wallet = ReimbursementWalletFactory.create(
        state=WalletState.QUALIFIED, user_id=enterprise_user.id
    )
    unclaimed_invite = WalletUserInviteFactory.create(
        email=enterprise_user.email,
        reimbursement_wallet_id=wallet.id,
        created_by_user_id=enterprise_user.id,  # Not at all realistic
        date_of_birth_provided="2000-01-01",
        claimed=False,
    )

    result = wallet_user_invite_repo.get_latest_unclaimed_invite(enterprise_user.id)

    assert result == unclaimed_invite
