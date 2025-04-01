#
# This file contains base fixtures to help create Wallet-related objects.
#
# These objects are intended to be shared and this file can be included via conftest from other modules using:
# # import the new-style wallet fixtures
# from wallet.pytests.fixtures import *  # noqa: F403,F401
#
import datetime
from typing import Optional
from unittest import mock

import pytest

from models.tracks import TrackName
from pytests.factories import OrganizationFactory
from wallet.models.constants import (
    AlegeusAccountType,
    BenefitTypes,
    ReimbursementRequestExpenseTypes,
    WalletState,
    WalletUserType,
)
from wallet.models.reimbursement_organization_settings import (
    ReimbursementOrganizationSettings,
)
from wallet.pytests.factories import (
    EnterpriseUserFactory,
    ReimbursementAccountTypeFactory,
    ReimbursementOrganizationSettingsFactory,
    ReimbursementOrgSettingCategoryAssociationFactory,
    ReimbursementPlanFactory,
    ReimbursementRequestCategoryExpenseTypesFactory,
    ReimbursementRequestCategoryFactory,
    ReimbursementWalletFactory,
    ReimbursementWalletUsersFactory,
)
from wallet.services.currency import DEFAULT_CURRENCY_CODE
from wallet.services.reimbursement_wallet_state_change import handle_wallet_state_change

###
### Helper methods
###


class WalletTestHelper:
    @classmethod
    def create_organization_with_wallet_enabled(
        cls, reimbursement_organization_parameters=None
    ):
        organization = OrganizationFactory.create(
            name="Wallet Test Organization",
            alegeus_employer_id="MVNABC123",
            allowed_tracks=[
                TrackName.FERTILITY,
                TrackName.PARTNER_FERTILITY,
                TrackName.EGG_FREEZING,
                TrackName.PREGNANCY,
                TrackName.PARTNER_PREGNANT,
                TrackName.ADOPTION,
                TrackName.SURROGACY,
            ],
        )

        reimbursement_organization_parameters_kwargs = (
            reimbursement_organization_parameters or {}
        )

        ReimbursementOrganizationSettingsFactory.create(
            organization=organization, **reimbursement_organization_parameters_kwargs
        )

        return organization

    @classmethod
    def create_user_for_organization(
        cls, organization, user_parameters=None, member_profile_parameters=None
    ):
        # OE is deprecated but still used by the Member Tracks factory to connect entities
        # Don't add parameters here just to pass tests. Use the new e9y infrastructure as possible.
        # If you *must* use parameters on the OE, add a comment indicating why.
        user_parameters_kwargs = user_parameters or {}
        member_profile_parameters_kwargs = member_profile_parameters or {}
        member_profile_parameters_kwargs = {
            "member_profile__" + key: val
            for key, val in member_profile_parameters_kwargs.items()
        }

        return EnterpriseUserFactory.create(
            tracks__client_track__organization=organization,
            tracks__name=TrackName.FERTILITY,
            **user_parameters_kwargs,
            **member_profile_parameters_kwargs,
        )

    @classmethod
    def create_pending_wallet(cls, user, wallet_parameters=None):
        wallet_parameters_kwargs = wallet_parameters or {}
        wallet = ReimbursementWalletFactory.create(
            reimbursement_organization_settings=user.organization_v2.reimbursement_organization_settings[
                0
            ],
            member=user,
            state=WalletState.PENDING,
            **wallet_parameters_kwargs,
        )
        ReimbursementWalletUsersFactory.create(
            wallet=wallet, member=user, type=WalletUserType.EMPLOYEE
        )
        return wallet

    @classmethod
    def qualify_wallet(cls, wallet):
        def assign_payments_customer_mock_side_effect(wallet, headers):
            wallet.payments_customer_id = "00000000-0000-0000-0000-000000000000"
            return True

        # Do the actual post-qualification while mocking as little as possible
        with mock.patch(
            "wallet.services.reimbursement_wallet_state_change.configure_wallet_in_alegeus"
        ) as mock_configure_wallet_in_alegeus, mock.patch(
            "wallet.services.reimbursement_wallet_state_change.assign_payments_customer_id_to_wallet"
        ) as assign_payments_customer_mock:
            mock_configure_wallet_in_alegeus.return_value = (
                True,
                [],
            )  # no setting up in Alegeus for default
            assign_payments_customer_mock.side_effect = (
                assign_payments_customer_mock_side_effect
            )

            wallet.state = WalletState.QUALIFIED
            handle_wallet_state_change(wallet, WalletState.PENDING)

        return wallet

    @classmethod
    def add_currency_benefit(
        cls,
        reimbursement_organization_settings: ReimbursementOrganizationSettings,
        alegeus_account_type: AlegeusAccountType,
        alegeus_plan_id: str,
        start_date: datetime.date,
        end_date: datetime.date,
        expense_types: list[ReimbursementRequestExpenseTypes],
        category_label: str,
        category_short_label: str,
        reimbursement_request_category_maximum: Optional[int],
        is_unlimited: bool = False,
    ):
        plan = ReimbursementPlanFactory.create(
            reimbursement_account_type=ReimbursementAccountTypeFactory.create(
                alegeus_account_type=alegeus_account_type.value
            ),
            alegeus_plan_id=alegeus_plan_id,
            start_date=start_date,
            end_date=end_date,
            is_hdhp=False,
        )
        category = ReimbursementRequestCategoryFactory.create(
            label=category_label,
            short_label=category_short_label,
            reimbursement_plan=plan,
        )
        for expense_type in expense_types:
            ReimbursementRequestCategoryExpenseTypesFactory.create(
                reimbursement_request_category=category,
                expense_type=expense_type,
            )
        ReimbursementOrgSettingCategoryAssociationFactory.create(
            reimbursement_organization_settings=reimbursement_organization_settings,
            reimbursement_request_category=category,
            reimbursement_request_category_maximum=None
            if is_unlimited
            else reimbursement_request_category_maximum,
            is_unlimited=is_unlimited,
            currency_code=DEFAULT_CURRENCY_CODE,
            benefit_type=BenefitTypes.CURRENCY,
            num_cycles=None,
        )

    @classmethod
    def add_lifetime_family_benefit(cls, reimbursement_organization_settings):
        """
        Add a pre-configured Family-building benefit suitable for most wallet testing.
        """
        cls.add_currency_benefit(
            reimbursement_organization_settings=reimbursement_organization_settings,
            alegeus_account_type=AlegeusAccountType.HRA,
            alegeus_plan_id="WTOLPBP",
            start_date=datetime.date(year=2020, month=1, day=1),
            end_date=datetime.date(year=2119, month=12, day=31),
            category_label="Fertility, Adoption, and Surrogacy",
            category_short_label="Family Building",
            expense_types=[
                ReimbursementRequestExpenseTypes.FERTILITY,
                ReimbursementRequestExpenseTypes.ADOPTION,
                ReimbursementRequestExpenseTypes.SURROGACY,
            ],
            reimbursement_request_category_maximum=25_000_00,
        )

    @classmethod
    def add_lifetime_unlimited_family_benefit(cls, reimbursement_organization_settings):
        """
        Add a pre-configured Family-building benefit with unlimited funds.
        """
        cls.add_currency_benefit(
            reimbursement_organization_settings=reimbursement_organization_settings,
            alegeus_account_type=AlegeusAccountType.HRA,
            alegeus_plan_id="ULMTDWTOLPBP",
            start_date=datetime.date(year=2020, month=1, day=1),
            end_date=datetime.date(year=2119, month=12, day=31),
            category_label="Fertility, Adoption, and Surrogacy",
            category_short_label="Family Building",
            expense_types=[
                ReimbursementRequestExpenseTypes.FERTILITY,
                ReimbursementRequestExpenseTypes.ADOPTION,
                ReimbursementRequestExpenseTypes.SURROGACY,
            ],
            is_unlimited=True,
            reimbursement_request_category_maximum=None,
        )

    @classmethod
    def add_lifetime_family_benefit_cycle(cls, reimbursement_organization_settings):
        plan = ReimbursementPlanFactory.create(
            reimbursement_account_type=ReimbursementAccountTypeFactory.create(
                alegeus_account_type="HRA"
            ),
            alegeus_plan_id="WTOLPBP",
            start_date=datetime.date(year=2020, month=1, day=1),
            end_date=datetime.date(year=2119, month=12, day=31),
            is_hdhp=False,
        )
        category = ReimbursementRequestCategoryFactory.create(
            label="Fertility, Adoption, and Surrogacy",
            short_label="Family Building",
            reimbursement_plan=plan,
        )
        ReimbursementRequestCategoryExpenseTypesFactory.create(
            reimbursement_request_category=category,
            expense_type=ReimbursementRequestExpenseTypes.FERTILITY,
        )
        ReimbursementOrgSettingCategoryAssociationFactory.create(
            reimbursement_organization_settings=reimbursement_organization_settings,
            reimbursement_request_category=category,
            reimbursement_request_category_maximum=None,
            benefit_type=BenefitTypes.CYCLE,
            num_cycles=10,
        )

    @classmethod
    def add_hdhp_plan(
        cls,
        reimbursement_organization_settings: ReimbursementOrganizationSettings,
    ):
        ReimbursementPlanFactory.create(
            organization_id=reimbursement_organization_settings.id,
            reimbursement_account_type=ReimbursementAccountTypeFactory.create(
                alegeus_account_type=AlegeusAccountType.DTR
            ),
            alegeus_plan_id="WTODTR",
            start_date=datetime.date(year=2020, month=1, day=1),
            end_date=datetime.date(year=2119, month=12, day=31),
            is_hdhp=True,
        )


###
### Fixtures
###


@pytest.fixture(scope="function")
def wallet_test_helper() -> WalletTestHelper:
    return WalletTestHelper()


#
# Basic fixtures: Use these if you don't need anything special!
#


@pytest.fixture(scope="function")
def basic_organization_with_wallet_enabled(wallet_test_helper):
    """
    Provide a wallet-enabled organization for basic tests
    """

    organization = wallet_test_helper.create_organization_with_wallet_enabled(
        reimbursement_organization_parameters={
            "allowed_reimbursement_categories__no_categories": True
        }
    )
    wallet_test_helper.add_lifetime_family_benefit(
        organization.reimbursement_organization_settings[0]
    )

    return organization


@pytest.fixture(scope="function")
def basic_user_for_wallet(wallet_test_helper, basic_organization_with_wallet_enabled):
    """
    Provide a member for basic wallet-eligible tests
    """

    return wallet_test_helper.create_user_for_organization(
        basic_organization_with_wallet_enabled
    )


@pytest.fixture(scope="function")
def basic_pending_wallet(wallet_test_helper, basic_user_for_wallet):
    """
    Provide a pending wallet for basic wallet tests
    """
    return wallet_test_helper.create_pending_wallet(basic_user_for_wallet)


@pytest.fixture(scope="function")
def basic_qualified_wallet(wallet_test_helper, basic_pending_wallet):
    """
    Provide a qualified wallet for basic wallet tests
    """
    return wallet_test_helper.qualify_wallet(basic_pending_wallet)


#
# Fixtures for more detailed use cases
#


@pytest.fixture(scope="function")
def user_for_direct_payment_wallet(wallet_test_helper):
    organization = wallet_test_helper.create_organization_with_wallet_enabled(
        reimbursement_organization_parameters={
            "direct_payment_enabled": True,
            "allowed_reimbursement_categories__no_categories": True,
        }
    )
    wallet_test_helper.add_lifetime_family_benefit(
        organization.reimbursement_organization_settings[0]
    )
    return wallet_test_helper.create_user_for_organization(
        organization,
        member_profile_parameters={
            "country_code": "US",
            "subdivision_code": "US-NY",
        },
    )


@pytest.fixture(scope="function")
def user_for_unlimited_direct_payment_wallet(wallet_test_helper):
    organization = wallet_test_helper.create_organization_with_wallet_enabled(
        reimbursement_organization_parameters={
            "direct_payment_enabled": True,
            "allowed_reimbursement_categories__no_categories": True,
        }
    )
    wallet_test_helper.add_lifetime_unlimited_family_benefit(
        organization.reimbursement_organization_settings[0]
    )
    return wallet_test_helper.create_user_for_organization(
        organization,
        member_profile_parameters={
            "country_code": "US",
            "subdivision_code": "US-NY",
        },
    )


@pytest.fixture(scope="function")
def user_for_direct_payment_cycle_based_wallet(wallet_test_helper):
    organization = wallet_test_helper.create_organization_with_wallet_enabled(
        reimbursement_organization_parameters={
            "direct_payment_enabled": True,
            "allowed_reimbursement_categories__no_categories": True,
        }
    )
    wallet_test_helper.add_lifetime_family_benefit_cycle(
        organization.reimbursement_organization_settings[0]
    )
    return wallet_test_helper.create_user_for_organization(
        organization,
        member_profile_parameters={
            "country_code": "US",
            "subdivision_code": "US-NY",
        },
    )


@pytest.fixture(scope="function")
def direct_payment_wallet(wallet_test_helper, user_for_direct_payment_wallet):
    """
    Provide a qualified wallet for direct payments tests
    """
    wallet = wallet_test_helper.create_pending_wallet(
        user_for_direct_payment_wallet,
        wallet_parameters={
            "primary_expense_type": ReimbursementRequestExpenseTypes.FERTILITY
        },
    )
    wallet_test_helper.qualify_wallet(wallet)

    return wallet


@pytest.fixture(scope="function")
def unlimited_direct_payment_wallet(
    wallet_test_helper, user_for_unlimited_direct_payment_wallet
):
    """
    Provide a qualified wallet for direct payments tests
    """
    wallet = wallet_test_helper.create_pending_wallet(
        user_for_unlimited_direct_payment_wallet,
        wallet_parameters={
            "primary_expense_type": ReimbursementRequestExpenseTypes.FERTILITY
        },
    )
    wallet_test_helper.qualify_wallet(wallet)

    return wallet


@pytest.fixture(scope="function")
def direct_payment_cycle_based_wallet(
    wallet_test_helper, user_for_direct_payment_cycle_based_wallet
):
    """
    Provide a qualified wallet for direct payments tests with cycle based category
    """
    wallet = wallet_test_helper.create_pending_wallet(
        user_for_direct_payment_cycle_based_wallet,
        wallet_parameters={
            "primary_expense_type": ReimbursementRequestExpenseTypes.FERTILITY
        },
    )
    wallet_test_helper.qualify_wallet(wallet)

    return wallet
