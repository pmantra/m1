from __future__ import annotations

import random
from typing import List, Tuple

import pytest

from wallet.models.constants import (
    AllowedMembers,
    ReimbursementRequestExpenseTypes,
    WalletState,
    WalletUserStatus,
)
from wallet.models.reimbursement_wallet import ReimbursementWallet
from wallet.pytests.factories import (
    ReimbursementWalletFactory,
    ReimbursementWalletUsersFactory,
)


@pytest.fixture()
def single_category_wallet(request, enterprise_user):
    category_setting: Tuple[str, int | None, str | None] = request.param

    wallet: ReimbursementWallet = ReimbursementWalletFactory.create(
        reimbursement_organization_settings__allowed_reimbursement_categories=[
            category_setting
        ],
        state=WalletState.QUALIFIED,
    )

    ReimbursementWalletUsersFactory.create(
        reimbursement_wallet_id=wallet.id,
        user_id=enterprise_user.id,
    )

    return wallet


@pytest.fixture()
def multi_category_wallet(request, enterprise_user):
    category_settings: List[Tuple[str, int | None, str | None]] = request.param

    wallet: ReimbursementWallet = ReimbursementWalletFactory.create(
        reimbursement_organization_settings__allowed_reimbursement_categories=category_settings,
        state=WalletState.QUALIFIED,
    )

    ReimbursementWalletUsersFactory.create(
        reimbursement_wallet_id=wallet.id,
        user_id=enterprise_user.id,
    )

    return wallet


@pytest.fixture
def shareable_wallet(ff_test_data):
    def fn(enterprise_user, wallet_user_type):
        wallet = ReimbursementWalletFactory.create(
            member=enterprise_user,
            id=random.randint(1, 1000),
            primary_expense_type=ReimbursementRequestExpenseTypes.FERTILITY,
            state=WalletState.QUALIFIED,
        )
        wallet.reimbursement_organization_settings.direct_payment_enabled = True
        wallet.reimbursement_organization_settings.allowed_members = (
            AllowedMembers.SHAREABLE
        )
        enterprise_user.member_profile.country_code = "US"
        ReimbursementWalletUsersFactory.create(
            user_id=enterprise_user.id,
            reimbursement_wallet_id=wallet.id,
            type=wallet_user_type,
            status=WalletUserStatus.ACTIVE,
        )
        return wallet

    return fn
