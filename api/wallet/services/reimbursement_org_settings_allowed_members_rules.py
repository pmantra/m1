from __future__ import annotations

from wallet.models.constants import AllowedMembers, WalletUserType
from wallet.models.models import WalletUserTypeAndAllowedMembers

# Valid Combinations of Allowed Member Settings for Employees and their dependents.
# source: https://docs.google.com/document/d/1jA2xnnoRkibd6DoCsOfjI0Q-vQf5Z8J71CXUpELwwFQ/edit#bookmark=id.wx23emv9lyzi
# fmt: off
VALID_COMBINATIONS = frozenset(
    {
        (
            WalletUserTypeAndAllowedMembers(WalletUserType.EMPLOYEE, AllowedMembers.SHAREABLE),
            WalletUserTypeAndAllowedMembers(WalletUserType.DEPENDENT, AllowedMembers.SHAREABLE),
        ),
        (
            WalletUserTypeAndAllowedMembers(WalletUserType.EMPLOYEE, AllowedMembers.MULTIPLE_PER_MEMBER),
            WalletUserTypeAndAllowedMembers(WalletUserType.DEPENDENT, AllowedMembers.MULTIPLE_PER_MEMBER),
        ),
        (
            WalletUserTypeAndAllowedMembers(WalletUserType.EMPLOYEE, AllowedMembers.MULTIPLE_PER_MEMBER),
            WalletUserTypeAndAllowedMembers(WalletUserType.DEPENDENT, AllowedMembers.SINGLE_DEPENDENT_ONLY),
        ),
        (
            WalletUserTypeAndAllowedMembers(WalletUserType.EMPLOYEE, AllowedMembers.MULTIPLE_PER_MEMBER),
            WalletUserTypeAndAllowedMembers(WalletUserType.DEPENDENT, AllowedMembers.MULTIPLE_DEPENDENT_ONLY),
        ),
        (
            WalletUserTypeAndAllowedMembers(WalletUserType.EMPLOYEE, AllowedMembers.SINGLE_EMPLOYEE_ONLY),
            WalletUserTypeAndAllowedMembers(WalletUserType.DEPENDENT, AllowedMembers.MULTIPLE_PER_MEMBER),
        ),
        (
            WalletUserTypeAndAllowedMembers(WalletUserType.EMPLOYEE, AllowedMembers.SINGLE_EMPLOYEE_ONLY),
            WalletUserTypeAndAllowedMembers(WalletUserType.DEPENDENT, AllowedMembers.SINGLE_DEPENDENT_ONLY),
        ),
        (
            WalletUserTypeAndAllowedMembers(WalletUserType.EMPLOYEE, AllowedMembers.SINGLE_EMPLOYEE_ONLY),
            WalletUserTypeAndAllowedMembers(WalletUserType.DEPENDENT, AllowedMembers.MULTIPLE_DEPENDENT_ONLY),
        ),
        (
            WalletUserTypeAndAllowedMembers(WalletUserType.EMPLOYEE, AllowedMembers.SINGLE_ANY_USER),
            WalletUserTypeAndAllowedMembers(WalletUserType.DEPENDENT, AllowedMembers.SINGLE_ANY_USER),
        ),
    }
)
# fmt: on

ALL_VALID_WALLET_USER_TYPE_AND_ALLOWED_MEMBERS = {
    node for pair in VALID_COMBINATIONS for node in pair
}


def is_valid_wallet_user_type_and_allowed_members(
    wallet_user_type_1: WalletUserType,
    allowed_members_1: AllowedMembers,
) -> bool:
    return (
        WalletUserTypeAndAllowedMembers(wallet_user_type_1, allowed_members_1)
        in ALL_VALID_WALLET_USER_TYPE_AND_ALLOWED_MEMBERS
    )


def is_combination_allowed(
    wallet_user_type_1: WalletUserType,
    allowed_members_1: AllowedMembers,
    wallet_user_type_2: WalletUserType,
    allowed_members_2: AllowedMembers,
) -> bool:
    node1 = WalletUserTypeAndAllowedMembers(wallet_user_type_1, allowed_members_1)
    node2 = WalletUserTypeAndAllowedMembers(wallet_user_type_2, allowed_members_2)
    return any(n in VALID_COMBINATIONS for n in {(node1, node2), (node2, node1)})
