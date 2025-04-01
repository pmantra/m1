import pytest

from wallet.models.constants import AllowedMembers, WalletUserType
from wallet.services.reimbursement_org_settings_allowed_members_rules import (
    is_combination_allowed,
    is_valid_wallet_user_type_and_allowed_members,
)


@pytest.mark.parametrize(
    argnames="wallet_user_type, allowed_members, exp",
    argvalues=(
        (WalletUserType.EMPLOYEE, AllowedMembers.SHAREABLE, True),
        (WalletUserType.EMPLOYEE, AllowedMembers.SINGLE_DEPENDENT_ONLY, False),
    ),
    ids=["1. Valid input", "2. Invalid Input"],
)
def test_is_valid_wallet_user_type_and_allowed_members(
    wallet_user_type, allowed_members, exp
):
    assert (
        is_valid_wallet_user_type_and_allowed_members(wallet_user_type, allowed_members)
        == exp
    )


@pytest.mark.parametrize(
    argnames="wallet_user_type_1, allowed_members_1, wallet_user_type_2, allowed_members_2, exp",
    argvalues=(
        (
            WalletUserType.EMPLOYEE,
            AllowedMembers.SHAREABLE,
            WalletUserType.DEPENDENT,
            AllowedMembers.SHAREABLE,
            True,
        ),
        (
            WalletUserType.EMPLOYEE,
            AllowedMembers.SHAREABLE,
            WalletUserType.DEPENDENT,
            AllowedMembers.SINGLE_DEPENDENT_ONLY,
            False,
        ),
    ),
    ids=["1. Valid input", "2. Invalid Input"],
)
def test_is_combination_allowed(
    wallet_user_type_1,
    allowed_members_1,
    wallet_user_type_2,
    allowed_members_2,
    exp,
):
    assert (
        is_combination_allowed(
            wallet_user_type_1,
            allowed_members_1,
            wallet_user_type_2,
            allowed_members_2,
        )
        == exp
    )
