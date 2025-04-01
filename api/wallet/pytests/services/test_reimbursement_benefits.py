from unittest.mock import patch

import pytest

from models.enterprise import Organization
from pytests.factories import EnterpriseUserFactory, MemberFactory
from wallet.models.constants import (
    MemberType,
    ReimbursementRequestExpenseTypes,
    WalletState,
    WalletUserStatus,
)
from wallet.models.reimbursement_organization_settings import (
    ReimbursementOrganizationSettings,
)
from wallet.models.reimbursement_wallet import ReimbursementWallet
from wallet.models.reimbursement_wallet_user import ReimbursementWalletUsers
from wallet.pytests.factories import ReimbursementWalletBenefitFactory
from wallet.services.reimbursement_benefits import (
    assign_benefit_id,
    find_maven_gold_wallet_user_objs,
    get_member_type,
    get_member_type_details,
    get_member_type_details_from_user,
    get_member_type_details_from_wallet,
)


@pytest.fixture(scope="function")
def gold_member_wallet(qualified_alegeus_wallet_hra):
    wallet = qualified_alegeus_wallet_hra
    wallet_user = ReimbursementWalletUsers.query.filter(
        ReimbursementWalletUsers.reimbursement_wallet_id == wallet.id
    ).one()
    wallet.reimbursement_organization_settings.direct_payment_enabled = True
    wallet_user.member.member_profile.country_code = "US"
    wallet.primary_expense_type = ReimbursementRequestExpenseTypes.FERTILITY
    return wallet


def test_assign_benefit_id(db, qualified_alegeus_wallet_hra):
    assign_benefit_id(qualified_alegeus_wallet_hra)

    # expire and reload to enable loading the benefit backref
    db.session.expire(qualified_alegeus_wallet_hra)
    wallet = ReimbursementWallet.query.get(qualified_alegeus_wallet_hra.id)

    assert wallet.reimbursement_wallet_benefit


def test_assign_benefit_id__duplication_exception(qualified_alegeus_wallet_hra):
    qualified_alegeus_wallet_hra.reimbursement_wallet_benefit = (
        ReimbursementWalletBenefitFactory.create()
    )

    with pytest.raises(ValueError):
        assign_benefit_id(qualified_alegeus_wallet_hra)


def test_assign_benefit_id__logging(qualified_alegeus_wallet_hra, logs):
    error_msg = "Failed to assign Benefit ID"
    with patch(
        "wallet.services.reimbursement_benefits.generate_wallet_benefit",
        side_effect=Exception("db error"),
    ):
        assign_benefit_id(qualified_alegeus_wallet_hra)
        log = next((r for r in logs if error_msg in r["event"]), None)
        assert log is not None


def test_get_member_type_details__access_not_wallet_eligible():
    # use a generic enterprise user not from wallet fixtures
    user = EnterpriseUserFactory.create()
    member_type_details = get_member_type_details(user)
    assert member_type_details.member_type == MemberType.MAVEN_ACCESS
    assert member_type_details.flags.wallet_organization is False
    assert member_type_details.flags.direct_payment is False


def test_get_member_type_details__access_wallet_eligible(basic_user_for_wallet):
    member_type_details = get_member_type_details(basic_user_for_wallet)
    assert member_type_details.member_type == MemberType.MAVEN_ACCESS
    assert member_type_details.flags.wallet_organization is True
    assert member_type_details.flags.direct_payment is False


def test_get_member_type_details__green_with_wallet(
    basic_user_for_wallet, basic_qualified_wallet
):
    member_type_details = get_member_type_details(basic_user_for_wallet)
    assert member_type_details.member_type == MemberType.MAVEN_GREEN
    assert member_type_details.flags.wallet_organization is True
    assert member_type_details.flags.direct_payment is False


def test_get_member_type_details__gold_eligible(wallet_test_helper):
    organization = wallet_test_helper.create_organization_with_wallet_enabled(
        reimbursement_organization_parameters={"direct_payment_enabled": True}
    )
    wallet_test_helper.add_lifetime_family_benefit(
        organization.reimbursement_organization_settings[0]
    )
    user = wallet_test_helper.create_user_for_organization(
        organization,
        member_profile_parameters={
            "country_code": "CA",
        },
    )
    wallet = wallet_test_helper.create_pending_wallet(user)
    wallet_test_helper.qualify_wallet(wallet)

    member_type_details = get_member_type_details(user)
    assert member_type_details.member_type == MemberType.MAVEN_GREEN
    assert member_type_details.flags.wallet_organization is True
    assert member_type_details.flags.direct_payment is True
    assert member_type_details.flags.member_country is False
    assert member_type_details.flags.member_track is True
    assert member_type_details.flags.wallet_active is True
    assert member_type_details.flags.wallet_expense_type is False


def test_get_member_type_details__gold(
    user_for_direct_payment_wallet, direct_payment_wallet
):
    member_type_details = get_member_type_details(user_for_direct_payment_wallet)
    assert member_type_details.member_type == MemberType.MAVEN_GOLD
    assert member_type_details.flags.wallet_organization is True
    assert member_type_details.flags.direct_payment is True
    assert member_type_details.flags.member_country is True
    assert member_type_details.flags.member_track is True
    assert member_type_details.flags.wallet_active is True
    assert member_type_details.flags.wallet_expense_type is True


@pytest.mark.parametrize(
    argnames=("wallet_state", "expected_type"),
    argvalues=[
        (WalletState.EXPIRED, MemberType.MAVEN_ACCESS),
        (WalletState.DISQUALIFIED, MemberType.MAVEN_ACCESS),
        (WalletState.PENDING, MemberType.MAVEN_ACCESS),
        (WalletState.RUNOUT, MemberType.MAVEN_GREEN),
        (WalletState.QUALIFIED, MemberType.MAVEN_GREEN),
    ],
)
def test_get_member_type__green(
    basic_user_for_wallet,
    basic_qualified_wallet,
    wallet_state,
    expected_type,
):
    basic_qualified_wallet.state = wallet_state
    member_type = get_member_type(basic_user_for_wallet)
    assert member_type == expected_type


@pytest.mark.parametrize(
    argnames=("wallet_state", "expected_type"),
    argvalues=[
        (WalletState.EXPIRED, MemberType.MAVEN_ACCESS),
        (WalletState.DISQUALIFIED, MemberType.MAVEN_ACCESS),
        (WalletState.PENDING, MemberType.MAVEN_ACCESS),
        (WalletState.RUNOUT, MemberType.MAVEN_GOLD),
        (WalletState.QUALIFIED, MemberType.MAVEN_GOLD),
    ],
)
def test_get_member_type__gold(
    user_for_direct_payment_wallet, direct_payment_wallet, wallet_state, expected_type
):
    direct_payment_wallet.state = wallet_state
    member_type = get_member_type(user_for_direct_payment_wallet)
    assert member_type == expected_type


def test_get_member_type_details_from_wallet__gold(direct_payment_wallet):
    member_type_details = get_member_type_details_from_wallet(direct_payment_wallet)
    assert member_type_details.member_type == MemberType.MAVEN_GOLD


def test_get_member_type_details_from_wallet__expired(direct_payment_wallet):
    direct_payment_wallet.state = WalletState.EXPIRED
    member_type_details = get_member_type_details_from_wallet(direct_payment_wallet)
    assert member_type_details.member_type == MemberType.MAVEN_GREEN


def test_get_member_type_details_from_user__access():
    # use a generic enterprise user not from wallet fixtures
    user = EnterpriseUserFactory.create()
    member_type_details = get_member_type_details_from_user(user)
    assert member_type_details.member_type == MemberType.MAVEN_ACCESS


def test_get_member_type_details_from_user__marketplace():
    # use a generic marketplace user not from wallet fixtures
    user = MemberFactory.create()
    member_type_details = get_member_type_details_from_user(user)
    assert member_type_details.member_type == MemberType.MARKETPLACE


class TestMavenGoldWalletUserObjs:
    @pytest.mark.parametrize(
        argnames="wallet_state", argvalues=[WalletState.QUALIFIED, WalletState.RUNOUT]
    )
    def test_gold_wallet_users(self, enterprise_user, gold_member_wallet, wallet_state):
        gold_member_wallet.state = wallet_state
        assert len(find_maven_gold_wallet_user_objs()) == 1

    def test_direct_payment_not_enabled(self, enterprise_user, gold_member_wallet):
        gold_member_wallet.reimbursement_organization_settings.direct_payment_enabled = (
            False
        )
        assert len(find_maven_gold_wallet_user_objs()) == 0

    def test_primary_expense_not_fertility(self, enterprise_user, gold_member_wallet):
        gold_member_wallet.primary_expense_type = (
            ReimbursementRequestExpenseTypes.SURROGACY
        )
        assert len(find_maven_gold_wallet_user_objs()) == 0

    def test_country_code_not_us(self, enterprise_user, gold_member_wallet):
        enterprise_user.member_profile.country_code = "UK"
        assert len(find_maven_gold_wallet_user_objs()) == 0

    def test_wallet_not_qualified(self, enterprise_user, gold_member_wallet):
        gold_member_wallet.state = WalletState.PENDING
        assert len(find_maven_gold_wallet_user_objs()) == 0

    def test_wallet_user_not_active(self, enterprise_user, gold_member_wallet):
        wallet_user = ReimbursementWalletUsers.query.filter_by(
            user_id=enterprise_user.id
        ).one()
        wallet_user.status = WalletUserStatus.PENDING
        assert len(find_maven_gold_wallet_user_objs()) == 0

    def test_additional_filter(self, enterprise_user, gold_member_wallet):
        assert (
            len(
                find_maven_gold_wallet_user_objs(
                    filters=[
                        ReimbursementOrganizationSettings.rx_direct_payment_enabled
                        == True
                    ],
                )
            )
            == 0
        )

        assert (
            len(
                find_maven_gold_wallet_user_objs(
                    filters=[Organization.id.in_([enterprise_user.organization.id])],
                )
            )
            == 1
        )
