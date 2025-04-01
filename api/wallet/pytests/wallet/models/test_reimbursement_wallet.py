import datetime
from unittest import mock
from unittest.mock import patch

import pymysql.err
import pytest
from sqlalchemy import and_
from sqlalchemy.exc import IntegrityError

from authn.models.user import User
from messaging.models.messaging import Message
from pytests.factories import ChannelFactory, OrganizationEmployeeDependentFactory
from storage.connection import db
from wallet.constants import NUM_CREDITS_PER_CYCLE
from wallet.models.constants import (
    AllowedMembers,
    CardStatus,
    CategoryRuleAccessLevel,
    CategoryRuleAccessSource,
    ReimbursementRequestExpenseTypes,
    WalletUserStatus,
    WalletUserType,
)
from wallet.models.reimbursement_wallet_user import ReimbursementWalletUsers
from wallet.pytests.factories import (
    ReimbursementWalletAllowedCategorySettingsFactory,
    ReimbursementWalletFactory,
    ReimbursementWalletUsersFactory,
)

REIMBURSED_AMOUNT = 100


def test_create_reimbursement_sources_from_attachments(
    enterprise_user, enterprise_user_assets
):
    wallet = ReimbursementWalletFactory.create()
    channel = ChannelFactory.create()
    ReimbursementWalletUsersFactory.create(
        user_id=enterprise_user.id,
        channel_id=channel.id,
        reimbursement_wallet_id=wallet.id,
    )
    message = Message(
        attachments=enterprise_user_assets, user=enterprise_user, channel=channel
    )
    wallet.create_sources_from_message(message)
    source_attachments = {source.user_asset for source in wallet.sources}
    assert set(enterprise_user_assets) == source_attachments


def test_create_reimbursement_sources_from_attachments_when_sources_exist(
    enterprise_user, enterprise_user_assets
):
    wallet = ReimbursementWalletFactory.create()
    channel = ChannelFactory.create()
    ReimbursementWalletUsersFactory.create(
        user_id=enterprise_user.id,
        channel_id=channel.id,
        reimbursement_wallet_id=wallet.id,
    )
    message = Message(
        attachments=enterprise_user_assets, user=enterprise_user, channel=channel
    )
    wallet.create_sources_from_message(message)
    source_count = len(wallet.sources)

    wallet.create_sources_from_message(message)
    # Assert no additional sources were added on second run
    assert len(wallet.sources) == source_count


def test_reimbursement_wallet_total_available_amount__active_plans(
    two_category_wallet_with_active_plans,
):
    assert two_category_wallet_with_active_plans.total_available_amount == 15_000


def test_reimbursement_wallet_total_available_amount__one_active_one_inactive_plan(
    two_category_wallet_with_active_and_inactive_plans,
):
    assert (
        two_category_wallet_with_active_and_inactive_plans.total_available_amount
        == 10_000
    )


def test_reimbursement_wallet_total_available_amount__inactive_plans(
    two_category_wallet_with_inactive_plans,
):
    assert two_category_wallet_with_inactive_plans.total_available_amount == 0


def test_reimbursement_wallet_available_currency_amount_by_category_active_plans(
    two_category_wallet_with_active_plans,
):
    assert set(
        two_category_wallet_with_active_plans.available_currency_amount_by_category.values()
    ) == {4800, 9800}


def test_reimbursement_wallet_available_currency_amount_by_category_inactive_plans(
    two_category_wallet_with_inactive_plans,
):
    assert (
        set(
            two_category_wallet_with_inactive_plans.available_currency_amount_by_category.values()
        )
        == set()
    )


def test_reimbursement_wallet_available_currency_amount_by_category_active_plan_no_reimbursement_requests(
    two_category_wallet_with_active_plans_no_reimbursement_requests,
):
    assert set(
        two_category_wallet_with_active_plans_no_reimbursement_requests.available_currency_amount_by_category.values()
    ) == {5_000, 10_000}


def test_reimbursement_wallet_available_credit_amount_by_category(
    qualified_alegeus_wallet_hra_cycle_based_categories,
):
    assert set(
        qualified_alegeus_wallet_hra_cycle_based_categories.available_credit_amount_by_category.values()
    ) == {2 * NUM_CREDITS_PER_CYCLE, 3 * NUM_CREDITS_PER_CYCLE}


def test_reimbursement_wallet_available_credit_amount_by_category_with_transactions(
    cycle_benefits_wallet,
):
    assert set(cycle_benefits_wallet.available_credit_amount_by_category.values()) == {
        36
    }


def test_reimbursement_wallet_total_available_amount_alltime__active_plans(
    two_category_wallet_with_active_plans,
):
    assert (
        two_category_wallet_with_active_plans.total_available_amount_alltime == 15_000
    )


def test_reimbursement_wallet_total_available_amount_alltime__one_active_one_inactive_plan(
    two_category_wallet_with_active_and_inactive_plans,
):
    assert (
        two_category_wallet_with_active_and_inactive_plans.total_available_amount_alltime
        == 15_000
    )


def test_reimbursement_wallet_total_available_amount_alltime__inactive_plans(
    two_category_wallet_with_inactive_plans,
):
    assert (
        two_category_wallet_with_inactive_plans.total_available_amount_alltime == 15_000
    )


def test_reimbursement_wallet_total_reimbursed_amount__active_plans(
    two_category_wallet_with_active_plans,
):
    assert two_category_wallet_with_active_plans.total_reimbursed_amount == 200


def test_reimbursement_wallet_total_reimbursed_amount__one_active_one_inactive_plan(
    two_category_wallet_with_active_and_inactive_plans,
):
    assert (
        two_category_wallet_with_active_and_inactive_plans.total_reimbursed_amount
        == 100
    )


def test_reimbursement_wallet_total_reimbursed_amount__inactive_plans(
    two_category_wallet_with_inactive_plans,
):
    assert two_category_wallet_with_inactive_plans.total_reimbursed_amount == 0


def test_reimbursement_wallet_total_reimbursed_amount_alltime__active_plans(
    two_category_wallet_with_active_plans,
):
    assert two_category_wallet_with_active_plans.total_reimbursed_amount_alltime == 200


def test_reimbursement_wallet_total_reimbursed_amount_alltime__one_active_one_inactive_plan(
    two_category_wallet_with_active_and_inactive_plans,
):
    assert (
        two_category_wallet_with_active_and_inactive_plans.total_reimbursed_amount_alltime
        == 200
    )


def test_reimbursement_wallet_total_reimbursed_amount_alltime__inactive_plans(
    two_category_wallet_with_inactive_plans,
):
    assert (
        two_category_wallet_with_inactive_plans.total_reimbursed_amount_alltime == 200
    )


def test_reimbursement_wallet_total_approved_amount__active_plans(
    two_category_wallet_with_active_plans,
):
    assert two_category_wallet_with_active_plans.total_approved_amount == 400


def test_reimbursement_wallet_total_approved_amount__one_active_one_inactive_plan(
    two_category_wallet_with_active_and_inactive_plans,
):
    assert (
        two_category_wallet_with_active_and_inactive_plans.total_approved_amount == 200
    )


def test_reimbursement_wallet_total_approved_amount__inactive_plans(
    two_category_wallet_with_inactive_plans,
):
    assert two_category_wallet_with_inactive_plans.total_approved_amount == 0


def test_reimbursement_wallet_total_approved_amount_alltime__active_plans(
    two_category_wallet_with_active_plans,
):
    assert two_category_wallet_with_active_plans.total_approved_amount_alltime == 400


def test_reimbursement_wallet_total_approved_amount_alltime__one_active_one_inactive_plan(
    two_category_wallet_with_active_and_inactive_plans,
):
    assert (
        two_category_wallet_with_active_and_inactive_plans.total_approved_amount_alltime
        == 400
    )


def test_reimbursement_wallet_total_approved_amount_alltime__inactive_plans(
    two_category_wallet_with_inactive_plans,
):
    assert two_category_wallet_with_inactive_plans.total_approved_amount_alltime == 400


def test_get_first_name_last_name_and_dob_returns_ey9_first_name_last_name(
    qualified_alegeus_wallet_hra,
    eligibility_factories,
):
    e9y_member = eligibility_factories.VerificationFactory.create(
        user_id=1,
        organization_id=qualified_alegeus_wallet_hra.reimbursement_organization_settings.organization_id,
    )
    with patch(
        "eligibility.service.EnterpriseVerificationService.get_verification_for_user_and_org"
    ) as mock_get_verification:
        mock_get_verification.return_value = e9y_member
        (
            first_name,
            last_name,
            date_of_birth,
        ) = qualified_alegeus_wallet_hra.get_first_name_last_name_and_dob()
        assert first_name == e9y_member.first_name
        assert last_name == e9y_member.last_name
        assert date_of_birth == e9y_member.date_of_birth


def test_get_first_name_last_name_and_dob_returns_member_profile_first_and_last_name(
    qualified_alegeus_wallet_hra,
):
    with patch(
        "eligibility.service.EnterpriseVerificationService.get_verification_for_user_and_org"
    ) as mock_get_verification:
        mock_get_verification.return_value = None
        (
            first_name,
            last_name,
            date_of_birth,
        ) = qualified_alegeus_wallet_hra.get_first_name_last_name_and_dob()
        assert first_name == qualified_alegeus_wallet_hra.member.first_name
        assert last_name == qualified_alegeus_wallet_hra.member.last_name
        # if there is no dob in organization_employee or e9y, get_first_name_last_name_and_dob need to return empty
        assert date_of_birth == ""


def test_get_first_name_last_name_and_dob_returns_empty(
    qualified_alegeus_wallet_hra,
):
    qualified_alegeus_wallet_hra.member.first_name = ""
    qualified_alegeus_wallet_hra.member.last_name = ""
    with patch(
        "eligibility.service.EnterpriseVerificationService.get_verification_for_user_and_org"
    ) as mock_get_verification:
        mock_get_verification.return_value = None
        (
            first_name,
            last_name,
            date_of_birth,
        ) = qualified_alegeus_wallet_hra.get_first_name_last_name_and_dob()
        assert first_name == ""
        assert last_name == ""
        assert date_of_birth == ""


def test_get_debit_banner_not_debit_card_eligible(
    qualified_alegeus_wallet_hra,
):
    (debit_banner) = qualified_alegeus_wallet_hra.get_debit_banner(None)
    assert debit_banner is None


def test_get_debit_banner_debit_card_eligible(
    qualified_alegeus_wallet_hra,
):
    qualified_alegeus_wallet_hra.reimbursement_organization_settings.debit_card_enabled = (
        True
    )
    (debit_banner) = qualified_alegeus_wallet_hra.get_debit_banner(None)
    assert debit_banner == "REQUEST_DEBIT_BANNER"


def test_get_debit_banner_unmet_hdhp(
    qualified_alegeus_wallet_hra,
):
    qualified_alegeus_wallet_hra.reimbursement_organization_settings.debit_card_enabled = (
        True
    )
    (debit_banner) = qualified_alegeus_wallet_hra.get_debit_banner(False)
    assert debit_banner == "HDHP_DEBIT_BANNER"


def test_get_debit_banner_debit_new_card(
    wallet_debitcardinator, qualified_alegeus_wallet_hra
):
    qualified_alegeus_wallet_hra.reimbursement_organization_settings.debit_card_enabled = (
        True
    )
    wallet_debitcardinator(qualified_alegeus_wallet_hra, card_status=CardStatus.NEW)
    debit_banner = qualified_alegeus_wallet_hra.get_debit_banner(None)
    assert debit_banner == "NEW_DEBIT_BANNER"


def test_get_debit_banner_debit_closed_card(
    wallet_debitcardinator, qualified_alegeus_wallet_hra
):
    qualified_alegeus_wallet_hra.reimbursement_organization_settings.debit_card_enabled = (
        True
    )
    wallet_debitcardinator(qualified_alegeus_wallet_hra, card_status=CardStatus.CLOSED)
    debit_banner = qualified_alegeus_wallet_hra.get_debit_banner(None)
    assert debit_banner is None


def test_get_debit_banner_debit_active_card(
    wallet_debitcardinator, qualified_alegeus_wallet_hra
):
    qualified_alegeus_wallet_hra.reimbursement_organization_settings.debit_card_enabled = (
        True
    )
    wallet_debitcardinator(qualified_alegeus_wallet_hra, card_status=CardStatus.ACTIVE)
    debit_banner = qualified_alegeus_wallet_hra.get_debit_banner(None)
    assert debit_banner is None


def test_get_employee_member(qualified_alegeus_wallet_hra, factories):
    # qualified_alegeus_wallet_hra was set to have an active employee already
    active_employee = (
        db.session.query(User)
        .join(
            ReimbursementWalletUsers,
            and_(
                ReimbursementWalletUsers.reimbursement_wallet_id
                == qualified_alegeus_wallet_hra.id,
                User.id == ReimbursementWalletUsers.user_id,
            ),
        )
        .filter(
            ReimbursementWalletUsers.status == WalletUserStatus.ACTIVE,
            ReimbursementWalletUsers.type == WalletUserType.EMPLOYEE,
        )
        .one_or_none()
    )
    assert active_employee is not None

    some_other_user = factories.DefaultUserFactory.create()
    # Add some other dependent
    ReimbursementWalletUsersFactory.create(
        user_id=some_other_user.id,
        reimbursement_wallet_id=qualified_alegeus_wallet_hra.id,
        type=WalletUserType.DEPENDENT,
        status=WalletUserStatus.ACTIVE,
    )

    result = qualified_alegeus_wallet_hra.employee_member
    assert result == active_employee


def test_all_active_users(qualified_alegeus_wallet_hra, factories):
    # qualified_alegeus_wallet_hra was set to have an active employee RWU already
    ReimbursementWalletUsers.query.delete()
    assert ReimbursementWalletUsers.query.all() == []

    active_user = factories.DefaultUserFactory.create()
    denied_user = factories.DefaultUserFactory.create()
    pending_user = factories.DefaultUserFactory.create()

    # Add some other dependent
    ReimbursementWalletUsersFactory.create(
        user_id=active_user.id,
        reimbursement_wallet_id=qualified_alegeus_wallet_hra.id,
        type=WalletUserType.DEPENDENT,
        status=WalletUserStatus.ACTIVE,
    )

    ReimbursementWalletUsersFactory.create(
        user_id=pending_user.id,
        reimbursement_wallet_id=qualified_alegeus_wallet_hra.id,
        type=WalletUserType.DEPENDENT,
        status=WalletUserStatus.DENIED,
    )

    ReimbursementWalletUsersFactory.create(
        user_id=denied_user.id,
        reimbursement_wallet_id=qualified_alegeus_wallet_hra.id,
        type=WalletUserType.DEPENDENT,
        status=WalletUserStatus.DENIED,
    )

    result = qualified_alegeus_wallet_hra.all_active_users
    assert len(result) == 1
    assert result[0].id == active_user.id


def test_get_employee_member_none(pending_alegeus_wallet_hra_without_rwu, factories):
    some_other_user = factories.DefaultUserFactory.create()
    ReimbursementWalletUsersFactory.create(
        user_id=some_other_user.id,
        reimbursement_wallet_id=pending_alegeus_wallet_hra_without_rwu.id,
        type=WalletUserType.DEPENDENT,
        status=WalletUserStatus.ACTIVE,
    )
    result = pending_alegeus_wallet_hra_without_rwu.employee_member
    assert result is None


def test_get_authorized_users(qualified_alegeus_wallet_hra):
    dependent = OrganizationEmployeeDependentFactory.create(
        reimbursement_wallet=qualified_alegeus_wallet_hra,
        alegeus_dependent_id="abc123",
    )
    dependent.reimbursement_wallet = qualified_alegeus_wallet_hra

    result = qualified_alegeus_wallet_hra.authorized_users
    assert len(result) == 1
    assert result[0].id == dependent.id


@pytest.mark.parametrize(
    argnames="country_code, allowed_member, primary_expense_type, ros_dp_enabled, exp",
    argvalues=(
        (
            "US",
            AllowedMembers.SHAREABLE,
            ReimbursementRequestExpenseTypes.FERTILITY,
            True,
            True,
        ),
        (
            "US",
            AllowedMembers.SINGLE_ANY_USER,
            ReimbursementRequestExpenseTypes.FERTILITY,
            True,
            False,
        ),
        (
            "US",
            AllowedMembers.SINGLE_ANY_USER,
            ReimbursementRequestExpenseTypes.CHILDCARE,
            True,
            False,
        ),
        (
            "CA",
            AllowedMembers.SINGLE_ANY_USER,
            ReimbursementRequestExpenseTypes.FERTILITY,
            True,
            False,
        ),
        (
            "CA",
            AllowedMembers.SINGLE_ANY_USER,
            ReimbursementRequestExpenseTypes.CHILDCARE,
            True,
            False,
        ),
        (
            "US",
            AllowedMembers.SHAREABLE,
            ReimbursementRequestExpenseTypes.FERTILITY,
            False,
            False,
        ),
    ),
    ids=[
        "1. AllowedMembers respected, wallet is sharable - US user with eligible primary expense type and sharable ros",
        "2. AllowedMembers respected, wallet is not sharable - non-sharable ros",
        "3. AllowedMembers respected, wallet is not sharable - ineligible primary expense type",
        "4. AllowedMembers respected, wallet is not sharable - non US member",
        "5. AllowedMembers respected, wallet is not sharable - non US member and ineligible primary expense type",
        "6. AllowedMembers respected, wallet is not sharable - reimbursement_organization_settings is not dp enabled",
    ],
)
def test_is_shareable(
    enterprise_user,
    qualified_direct_payment_enabled_wallet,
    country_code,
    allowed_member,
    primary_expense_type,
    ros_dp_enabled,
    exp,
):
    enterprise_user.member_profile.country_code = country_code
    qualified_direct_payment_enabled_wallet.reimbursement_organization_settings.allowed_members = (
        allowed_member
    )
    qualified_direct_payment_enabled_wallet.reimbursement_organization_settings.direct_payment_enabled = (
        ros_dp_enabled
    )
    qualified_direct_payment_enabled_wallet.primary_expense_type = primary_expense_type
    res = qualified_direct_payment_enabled_wallet.is_shareable

    assert res == exp


def test_get_or_create_wallet_allowed_categories(
    ff_test_data, qualified_wallet, category_association_with_setting, session
):
    allowed_categories = (
        qualified_wallet.reimbursement_organization_settings.allowed_reimbursement_categories
    )
    assert (
        allowed_categories == qualified_wallet.get_or_create_wallet_allowed_categories
    )


@pytest.mark.parametrize(
    argnames=("access_level", "len_expected_categories"),
    argvalues=[
        (CategoryRuleAccessLevel.NO_ACCESS, 1),
        (CategoryRuleAccessLevel.FULL_ACCESS, 2),
    ],
)
def test_get_or_create_wallet_allowed_categories_with_rules(
    qualified_wallet,
    category_associations_with_a_rule,
    access_level,
    len_expected_categories,
    ff_test_data,
    qualified_wallet_eligibility_verification,
    mock_enterprise_verification_service,
):
    # Given context 3 total categories (1 failing setting 1 setting updated based on params 1 no rules)
    qualified_wallet_eligibility_verification.record[
        "employee_start_date"
    ] = datetime.datetime.utcnow().date()
    mock_enterprise_verification_service.get_verification_for_user.return_value = (
        qualified_wallet_eligibility_verification
    )
    allowed_category, setting = category_associations_with_a_rule[0]
    ReimbursementWalletAllowedCategorySettingsFactory.create(
        reimbursement_organization_settings_allowed_category_id=allowed_category.id,
        reimbursement_wallet_id=qualified_wallet.id,
        access_level=access_level,
        access_level_source=CategoryRuleAccessSource.RULES,
    )
    # When
    with mock.patch(
        "wallet.utils.alegeus.enrollments.enroll_wallet.configure_account"
    ) as mock_configure_account:
        mock_configure_account.return_value = True, []
        allowed_categories = qualified_wallet.get_or_create_wallet_allowed_categories
        assert len(allowed_categories) == len_expected_categories


def test_get_or_create_wallet_allowed_categories_with_rule_exception_retry(
    qualified_wallet,
    category_association_with_rule,
    qualified_wallet_eligibility_verification,
    mock_enterprise_verification_service,
):

    qualified_wallet_eligibility_verification.record[
        "employee_start_date"
    ] = datetime.datetime.utcnow().date() - datetime.timedelta(days=399)
    mock_enterprise_verification_service.get_verification_for_user.return_value = (
        qualified_wallet_eligibility_verification
    )
    allowed_category, _ = category_association_with_rule
    # When
    with mock.patch(
        "wallet.utils.alegeus.enrollments.enroll_wallet.configure_account"
    ) as mock_configure_account, patch(
        "wallet.services.reimbursement_category_activation_visibility.CategoryActivationService.get_wallet_allowed_categories"
    ) as get_categories:
        expected_allowed_categories = (
            qualified_wallet.reimbursement_organization_settings.allowed_reimbursement_categories
        )
        mock_configure_account.return_value = True, []
        get_categories.side_effect = [
            IntegrityError("foo", {}, pymysql.err.IntegrityError()),
            expected_allowed_categories,
        ]
        allowed_categories = qualified_wallet.get_or_create_wallet_allowed_categories
        assert allowed_categories == expected_allowed_categories


def test_get_wallet_allowed_categories(
    qualified_wallet, category_association_with_setting
):
    # Given
    expected_allowed_categories = (
        qualified_wallet.reimbursement_organization_settings.allowed_reimbursement_categories
    )
    # When
    allowed_categories = qualified_wallet.get_wallet_allowed_categories
    # Then
    assert expected_allowed_categories == allowed_categories


def test_get_wallet_allowed_categories_doesnt_call_alegeus(
    qualified_wallet, category_association_with_setting
):
    # When
    with mock.patch(
        "wallet.utils.alegeus.enrollments.enroll_wallet.configure_account"
    ) as mock_configure_account:
        _ = qualified_wallet.get_wallet_allowed_categories

    # Then
    mock_configure_account.assert_not_called()
