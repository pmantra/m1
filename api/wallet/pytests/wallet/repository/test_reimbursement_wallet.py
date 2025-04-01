from __future__ import annotations

from datetime import datetime, timedelta
from typing import List, Set
from unittest import mock

import pytest

from authn.models.user import User
from pytests.factories import EnterpriseUserFactory, ReimbursementWalletFactory
from wallet.models.constants import (
    ReimbursementRequestExpenseTypes,
    ReimbursementRequestState,
    WalletState,
    WalletUserMemberStatus,
    WalletUserStatus,
    WalletUserType,
)
from wallet.models.models import (
    MemberBenefitProfile,
    MemberWalletSummary,
    OrganizationWalletSettings,
)
from wallet.models.reimbursement_organization_settings import (
    ReimbursementOrganizationSettings,
    ReimbursementOrgSettingCategoryAssociation,
)
from wallet.models.reimbursement_wallet import ReimbursementWallet
from wallet.models.reimbursement_wallet_benefit import ReimbursementWalletBenefit
from wallet.models.reimbursement_wallet_user import ReimbursementWalletUsers
from wallet.pytests.factories import (
    ReimbursementAccountFactory,
    ReimbursementCycleCreditsFactory,
    ReimbursementCycleMemberCreditTransactionFactory,
    ReimbursementOrganizationSettingsFactory,
    ReimbursementRequestCategoryExpenseTypesFactory,
    ReimbursementRequestFactory,
    ReimbursementWalletNonMemberDependentFactory,
    ReimbursementWalletUsersFactory,
)
from wallet.repository.reimbursement_wallet import (
    ReimbursementWalletRepository,
    WalletRWUInfo,
)
from wallet.services.reimbursement_benefits import assign_benefit_id


@pytest.fixture
def reimbursement_wallet_repository(session):
    return ReimbursementWalletRepository(session)


class TestReimbursementWalletRepository:
    def test_get_user_account_type_in_wallet_member(
        self,
        reimbursement_request_data,
        reimbursement_wallet_repository,
        enterprise_user,
    ):
        assert (
            reimbursement_wallet_repository.get_wallet_user_member_status(
                enterprise_user.id, reimbursement_request_data["wallet_id"]
            )
            == WalletUserMemberStatus.MEMBER
        )

    def test_get_user_account_type_in_wallet_non_member(
        self,
        reimbursement_request_data,
        reimbursement_wallet_repository,
    ):

        assert (
            reimbursement_wallet_repository.get_wallet_user_member_status(
                12345, reimbursement_request_data["wallet_id"]
            )
            == WalletUserMemberStatus.NON_MEMBER
        )

    def test_get_user_account_type_in_wallet_not_associated_with_wallet(
        self,
        reimbursement_request_data,
        reimbursement_wallet_repository,
    ):
        assert (
            reimbursement_wallet_repository.get_wallet_user_member_status(
                456, reimbursement_request_data["wallet_id"]
            )
            is None
        )

    def test_get_users_in_wallet_gets_members_and_dependents(
        self,
        enterprise_user,
        reimbursement_wallet_repository,
        qualified_alegeus_wallet_hdhp_single,
    ):
        # add non-member dependent
        ReimbursementWalletNonMemberDependentFactory.create(
            id=12345,
            first_name="Test",
            last_name="User",
            reimbursement_wallet_id=qualified_alegeus_wallet_hdhp_single.id,
        )

        # add inactive wallet user to ensure users are properly filtered
        other_user = EnterpriseUserFactory.create(
            id=99, first_name="John", last_name="Doe"
        )

        ReimbursementWalletUsersFactory.create(
            user_id=other_user.id,
            reimbursement_wallet_id=qualified_alegeus_wallet_hdhp_single.id,
            type=WalletUserType.DEPENDENT,
            status=WalletUserStatus.PENDING,
        )

        data = reimbursement_wallet_repository.get_users_in_wallet(
            qualified_alegeus_wallet_hdhp_single.id
        )
        assert data == [
            (12345, "Test", "User", "DEPENDENT", "NON_MEMBER"),
            (
                enterprise_user.id,
                enterprise_user.first_name,
                enterprise_user.last_name,
                "EMPLOYEE",
                "MEMBER",
            ),
        ]

    def test_get_wallet_rwu_info(
        self, reimbursement_wallet_repository, enterprise_user
    ):
        ros: ReimbursementOrganizationSettings = (
            ReimbursementOrganizationSettingsFactory.create(
                organization_id=enterprise_user.organization_v2.id,
                allowed_reimbursement_categories__no_categories=True,
            )
        )
        qualified_wallet = ReimbursementWalletFactory.create(
            user_id=enterprise_user.id,
            state=WalletState.QUALIFIED,
            reimbursement_organization_settings_id=ros.id,
        )
        qualified_rwu = ReimbursementWalletUsersFactory.create(
            reimbursement_wallet_id=qualified_wallet.id,
            status=WalletUserStatus.ACTIVE,
            type=WalletUserType.EMPLOYEE,
            user_id=enterprise_user.id,
        )
        dependent = EnterpriseUserFactory.create()
        dependent_rwu = ReimbursementWalletUsersFactory.create(
            reimbursement_wallet_id=qualified_wallet.id,
            status=WalletUserStatus.DENIED,
            type=WalletUserType.DEPENDENT,
            user_id=dependent.id,
        )

        other_user = EnterpriseUserFactory.create()
        disqualified_wallet = ReimbursementWalletFactory.create(
            user_id=other_user.id,
            state=WalletState.DISQUALIFIED,
            reimbursement_organization_settings_id=ros.id,
        )
        denied_rwu = ReimbursementWalletUsersFactory.create(
            reimbursement_wallet_id=disqualified_wallet.id,
            status=WalletUserStatus.DENIED,
            type=WalletUserType.DEPENDENT,
            user_id=other_user.id,
        )
        result = reimbursement_wallet_repository.get_wallet_rwu_info(
            [qualified_rwu.user_id, dependent_rwu.user_id, denied_rwu.user_id], ros.id
        )
        assert len(result) == 3
        assert (
            WalletRWUInfo(
                state=qualified_wallet.state.value,
                user_id=qualified_rwu.user_id,
                rwu_status=qualified_rwu.status.value,
                wallet_id=qualified_wallet.id,
            )
            in result
        )
        assert (
            WalletRWUInfo(
                state=qualified_wallet.state.value,
                user_id=dependent_rwu.user_id,
                rwu_status=dependent_rwu.status.value,
                wallet_id=dependent_rwu.reimbursement_wallet_id,
            )
            in result
        )
        assert (
            WalletRWUInfo(
                state=disqualified_wallet.state.value,
                user_id=denied_rwu.user_id,
                rwu_status=denied_rwu.status.value,
                wallet_id=denied_rwu.reimbursement_wallet_id,
            )
            in result
        )

    def test_get_num_existing_rwus(
        self, reimbursement_wallet_repository, enterprise_user
    ):
        ros: ReimbursementOrganizationSettings = (
            ReimbursementOrganizationSettingsFactory.create(
                organization_id=enterprise_user.organization_v2.id,
                allowed_reimbursement_categories__no_categories=True,
            )
        )
        qualified_wallet = ReimbursementWalletFactory.create(
            user_id=enterprise_user.id,
            state=WalletState.QUALIFIED,
            reimbursement_organization_settings_id=ros.id,
        )
        for user_status in (
            WalletUserStatus.ACTIVE,
            WalletUserStatus.DENIED,
            WalletUserStatus.PENDING,
            WalletUserStatus.REVOKED,
        ):
            other_user = EnterpriseUserFactory.create(
                first_name="John", last_name="Doe"
            )
            ReimbursementWalletUsersFactory.create(
                user_id=other_user.id,
                status=user_status,
                reimbursement_wallet_id=qualified_wallet.id,
                type=WalletUserType.EMPLOYEE,
            )

        result = reimbursement_wallet_repository.get_num_existing_rwus(
            qualified_wallet.id
        )
        assert result == 2

    def test_get_wallet_and_rwu_not_found(self, reimbursement_wallet_repository):
        result = reimbursement_wallet_repository.get_wallet_and_rwu(
            wallet_id=123,
            user_id=321,
        )
        assert result.wallet is None
        assert result.rwu is None

    def test_get_wallet_and_rwu_happy_path(
        self, reimbursement_wallet_repository, enterprise_user
    ):
        ros: ReimbursementOrganizationSettings = (
            ReimbursementOrganizationSettingsFactory.create(
                organization_id=enterprise_user.organization_v2.id,
                allowed_reimbursement_categories__no_categories=True,
            )
        )
        wallet = ReimbursementWalletFactory.create(
            user_id=enterprise_user.id,
            reimbursement_organization_settings_id=ros.id,
        )
        rwu = ReimbursementWalletUsersFactory.create(
            reimbursement_wallet_id=wallet.id,
            status=WalletUserStatus.ACTIVE,
            type=WalletUserType.EMPLOYEE,
            user_id=enterprise_user.id,
        )
        wallet_and_rwu = reimbursement_wallet_repository.get_wallet_and_rwu(
            wallet_id=wallet.id,
            user_id=enterprise_user.id,
        )
        assert wallet == wallet_and_rwu.wallet
        assert rwu == wallet_and_rwu.rwu

    def test_get_wallet_and_rwu_wallet_without_rwu(
        self, reimbursement_wallet_repository, enterprise_user
    ):
        ros: ReimbursementOrganizationSettings = (
            ReimbursementOrganizationSettingsFactory.create(
                organization_id=enterprise_user.organization_v2.id,
                allowed_reimbursement_categories__no_categories=True,
            )
        )
        wallet = ReimbursementWalletFactory.create(
            user_id=enterprise_user.id,
            reimbursement_organization_settings_id=ros.id,
        )
        wallet_and_rwu = reimbursement_wallet_repository.get_wallet_and_rwu(
            wallet_id=wallet.id,
            user_id=enterprise_user.id,
        )
        assert wallet == wallet_and_rwu.wallet
        assert wallet_and_rwu.rwu is None

    def test_get_users_in_wallet_no_wallets(self, reimbursement_wallet_repository):
        result = reimbursement_wallet_repository.get_any_user_has_wallet(
            [23424, 1232, 112]
        )
        assert result is False

    def test_get_users_in_wallet_disqualified_wallet(
        self, reimbursement_wallet_repository, pending_alegeus_wallet_hra_without_rwu
    ):
        user = EnterpriseUserFactory.create()
        pending_alegeus_wallet_hra_without_rwu.state = WalletState.DISQUALIFIED
        ReimbursementWalletUsersFactory.create(
            reimbursement_wallet_id=pending_alegeus_wallet_hra_without_rwu.id,
            status=WalletUserStatus.ACTIVE,
            type=WalletUserType.DEPENDENT,
            user_id=user.id,
        )
        result = reimbursement_wallet_repository.get_any_user_has_wallet([user.id])
        assert result is False

    def test_get_users_in_wallet_happy_path(
        self, reimbursement_wallet_repository, pending_alegeus_wallet_hra_without_rwu
    ):
        user = EnterpriseUserFactory.create()
        pending_alegeus_wallet_hra_without_rwu.state = WalletState.QUALIFIED
        ReimbursementWalletUsersFactory.create(
            reimbursement_wallet_id=pending_alegeus_wallet_hra_without_rwu.id,
            status=WalletUserStatus.ACTIVE,
            type=WalletUserType.DEPENDENT,
            user_id=user.id,
        )
        result = reimbursement_wallet_repository.get_any_user_has_wallet([user.id])
        assert result is True

    def test_get_wallet_by_user_pending_happy_path(
        self, reimbursement_wallet_repository, pending_alegeus_wallet_hra_without_rwu
    ):
        user = EnterpriseUserFactory.create()
        pending_alegeus_wallet_hra_without_rwu.state = WalletState.QUALIFIED
        ReimbursementWalletUsersFactory.create(
            reimbursement_wallet_id=pending_alegeus_wallet_hra_without_rwu.id,
            status=WalletUserStatus.PENDING,
            type=WalletUserType.DEPENDENT,
            user_id=user.id,
        )
        result = reimbursement_wallet_repository.get_wallet_by_active_user_id(user.id)
        assert result == pending_alegeus_wallet_hra_without_rwu

    def test_get_wallet_by_user_active_happy_path(
        self, reimbursement_wallet_repository, pending_alegeus_wallet_hra_without_rwu
    ):
        user = EnterpriseUserFactory.create()
        pending_alegeus_wallet_hra_without_rwu.state = WalletState.QUALIFIED
        ReimbursementWalletUsersFactory.create(
            reimbursement_wallet_id=pending_alegeus_wallet_hra_without_rwu.id,
            status=WalletUserStatus.ACTIVE,
            type=WalletUserType.DEPENDENT,
            user_id=user.id,
        )
        result = reimbursement_wallet_repository.get_wallet_by_active_user_id(user.id)
        assert result == pending_alegeus_wallet_hra_without_rwu

    def test_get_wallet_by_user_multiple_wallets(
        self,
        reimbursement_wallet_repository,
        qualified_alegeus_wallet_hdhp_single,
        pending_alegeus_wallet_hra_without_rwu,
    ):
        user = EnterpriseUserFactory.create()
        pending_alegeus_wallet_hra_without_rwu.state = WalletState.QUALIFIED
        ReimbursementWalletUsersFactory.create(
            reimbursement_wallet_id=qualified_alegeus_wallet_hdhp_single.id,
            status=WalletUserStatus.ACTIVE,
            type=WalletUserType.DEPENDENT,
            user_id=user.id,
            modified_at=datetime(2024, 1, 1),
        )
        ReimbursementWalletUsersFactory.create(
            reimbursement_wallet_id=pending_alegeus_wallet_hra_without_rwu.id,
            status=WalletUserStatus.ACTIVE,
            type=WalletUserType.DEPENDENT,
            user_id=user.id,
            modified_at=datetime(2024, 1, 2),
        )
        result = reimbursement_wallet_repository.get_wallet_by_active_user_id(user.id)
        assert result == pending_alegeus_wallet_hra_without_rwu

    def test_get_wallet_by_user_no_active_wallets(
        self,
        reimbursement_wallet_repository,
        qualified_alegeus_wallet_hdhp_single,
        pending_alegeus_wallet_hra_without_rwu,
    ):
        user = EnterpriseUserFactory.create()
        pending_alegeus_wallet_hra_without_rwu.state = WalletState.QUALIFIED
        setup = (
            (qualified_alegeus_wallet_hdhp_single, WalletUserStatus.DENIED),
            (pending_alegeus_wallet_hra_without_rwu, WalletUserStatus.DENIED),
        )
        for wallet, status in setup:
            ReimbursementWalletUsersFactory.create(
                reimbursement_wallet_id=wallet.id,
                status=status,
                type=WalletUserType.DEPENDENT,
                user_id=user.id,
            )
        result = reimbursement_wallet_repository.get_wallet_by_active_user_id(user.id)
        assert result is None

    def test_get_wallet_states_by_user_id(
        self,
        reimbursement_wallet_repository,
        qualified_alegeus_wallet_hdhp_single,
        pending_alegeus_wallet_hra,
        pending_alegeus_wallet_hra_without_rwu,
    ):
        user = EnterpriseUserFactory.create()
        other_user = EnterpriseUserFactory.create()

        pending_wallet = pending_alegeus_wallet_hra_without_rwu
        pending_wallet.state = WalletState.PENDING

        qualified_wallet = pending_alegeus_wallet_hra
        qualified_wallet.state = WalletState.QUALIFIED

        # Yes, we're abusing the purpose of the wallet
        expired_wallet = qualified_alegeus_wallet_hdhp_single
        expired_wallet.state = WalletState.EXPIRED
        setup = (
            # These two should show up
            (user.id, pending_wallet.id, WalletUserStatus.PENDING),
            (user.id, qualified_wallet.id, WalletUserStatus.ACTIVE),
            # These two should be excluded
            (user.id, expired_wallet.id, WalletUserStatus.DENIED),
            (other_user.id, expired_wallet.id, WalletUserStatus.ACTIVE),
        )
        for user_id, wallet_id, status in setup:
            ReimbursementWalletUsersFactory.create(
                user_id=user_id,
                reimbursement_wallet_id=wallet_id,
                status=status,
                type=WalletUserType.EMPLOYEE,
            )
        result = reimbursement_wallet_repository.get_wallet_states_for_user(user.id)
        assert result == {WalletState.PENDING.value, WalletState.QUALIFIED.value}

    def test_get_active_user_in_wallet_happy_path(
        self,
        enterprise_user,
        reimbursement_wallet_repository,
        qualified_alegeus_wallet_hdhp_single,
    ):

        wallet_user = reimbursement_wallet_repository.get_active_user_in_wallet(
            enterprise_user.id, qualified_alegeus_wallet_hdhp_single.id
        )

        assert wallet_user.user_id == enterprise_user.id
        assert (
            wallet_user.reimbursement_wallet_id
            == qualified_alegeus_wallet_hdhp_single.id
        )
        assert wallet_user.type == WalletUserType.EMPLOYEE
        assert wallet_user.status == WalletUserStatus.ACTIVE
        assert wallet_user.zendesk_ticket_id == 1234

    @pytest.mark.parametrize(
        argnames="user_id,wallet_id",
        argvalues=[
            (1, 123),
            (2, 1),
        ],
        ids=[
            "correct user id but wrong wallet_id",
            "wrong user id with correct wallet id",
        ],
    )
    def test_is_active_user_in_wallet_failure_scenarios(
        self,
        reimbursement_wallet_repository,
        user_id,
        wallet_id,
        qualified_alegeus_wallet_hdhp_single,
    ):
        assert (
            reimbursement_wallet_repository.get_active_user_in_wallet(
                user_id, wallet_id
            )
            is None
        )


class TestGetEligibleWallets:
    @staticmethod
    def test_get_eligible_wallets(
        reimbursement_wallet_repository: ReimbursementWalletRepository,
        enterprise_user: User,
        wallet_org_settings: ReimbursementOrganizationSettings,
    ):
        # Given an org setting and a user

        # When
        eligible_wallet_settings: List[
            MemberWalletSummary
        ] = reimbursement_wallet_repository.get_eligible_wallets(
            user_id=enterprise_user.id
        )

        # Then
        assert eligible_wallet_settings

    @staticmethod
    def test_get_eligible_wallets_missing_resource(
        reimbursement_wallet_repository: ReimbursementWalletRepository,
        enterprise_user: User,
    ):
        # Given an org setting and a user
        ReimbursementOrganizationSettingsFactory.create(
            organization_id=enterprise_user.organization_v2.id,
            benefit_overview_resource=None,
        )

        # When
        eligible_wallet_settings: List[
            MemberWalletSummary
        ] = reimbursement_wallet_repository.get_eligible_wallets(
            user_id=enterprise_user.id
        )

        # Then
        assert eligible_wallet_settings

    @staticmethod
    def test_get_eligible_wallets_no_categories(
        reimbursement_wallet_repository: ReimbursementWalletRepository,
        enterprise_user: User,
    ):
        # Given an org setting and a user
        ReimbursementOrganizationSettingsFactory.create(
            organization_id=enterprise_user.organization_v2.id,
            allowed_reimbursement_categories__no_categories=True,
        )

        # When
        eligible_wallet_settings: List[
            MemberWalletSummary
        ] = reimbursement_wallet_repository.get_eligible_wallets(
            user_id=enterprise_user.id
        )

        # Then
        assert eligible_wallet_settings


class TestGetClinicPortalWalletSummaries:
    @staticmethod
    @pytest.mark.parametrize(
        argnames=("wallet_state", "wallet_user_status"),
        argvalues=[
            (WalletState.PENDING, WalletUserStatus.PENDING),
            (WalletState.PENDING, WalletUserStatus.ACTIVE),
            (WalletState.PENDING, WalletUserStatus.DENIED),
            (WalletState.QUALIFIED, WalletUserStatus.PENDING),
            (WalletState.QUALIFIED, WalletUserStatus.ACTIVE),
            (WalletState.QUALIFIED, WalletUserStatus.DENIED),
            (WalletState.RUNOUT, WalletUserStatus.PENDING),
            (WalletState.RUNOUT, WalletUserStatus.ACTIVE),
            (WalletState.RUNOUT, WalletUserStatus.DENIED),
            (WalletState.EXPIRED, WalletUserStatus.PENDING),
            (WalletState.EXPIRED, WalletUserStatus.ACTIVE),
            (WalletState.EXPIRED, WalletUserStatus.DENIED),
            (WalletState.DISQUALIFIED, WalletUserStatus.PENDING),
            (WalletState.DISQUALIFIED, WalletUserStatus.ACTIVE),
            (WalletState.DISQUALIFIED, WalletUserStatus.DENIED),
        ],
    )
    def test_get_wallets(
        reimbursement_wallet_repository: ReimbursementWalletRepository,
        enterprise_user: User,
        qualified_alegeus_wallet_hdhp_single: ReimbursementWallet,
        active_wallet_user: ReimbursementWalletUsers,
        wallet_state: WalletState,
        wallet_user_status: WalletUserStatus,
    ):
        # Given
        qualified_alegeus_wallet_hdhp_single.state = wallet_state
        active_wallet_user.status = wallet_user_status

        # When
        enrolled_wallets: List[
            MemberWalletSummary
        ] = reimbursement_wallet_repository.get_clinic_portal_wallet_summaries(
            user_id=enterprise_user.id
        )

        # Then
        assert all(wallet.wallet_id is not None for wallet in enrolled_wallets)
        assert enrolled_wallets

    @staticmethod
    def test_get_wallets_direct_payment(
        reimbursement_wallet_repository: ReimbursementWalletRepository,
        enterprise_user: User,
        direct_payment_wallet,
        active_wallet_user: ReimbursementWalletUsers,
    ):
        # When
        enrolled_wallets: List[
            MemberWalletSummary
        ] = reimbursement_wallet_repository.get_clinic_portal_wallet_summaries(
            user_id=enterprise_user.id
        )

        # Then
        assert enrolled_wallets

    @staticmethod
    def test_get_wallets_no_direct_payment_category_configured(
        reimbursement_wallet_repository: ReimbursementWalletRepository,
        user_for_direct_payment_wallet: User,
        direct_payment_wallet_without_dp_category_access,
    ):
        # Given
        # When
        enrolled_wallets: List[
            MemberWalletSummary
        ] = reimbursement_wallet_repository.get_clinic_portal_wallet_summaries(
            user_id=user_for_direct_payment_wallet.id
        )

        # Then
        assert enrolled_wallets


class TestGetWalletSummaries:
    @staticmethod
    @pytest.mark.parametrize(
        argnames=("wallet_state", "wallet_user_status"),
        argvalues=[
            (WalletState.PENDING, WalletUserStatus.PENDING),
            (WalletState.PENDING, WalletUserStatus.ACTIVE),
            (WalletState.PENDING, WalletUserStatus.DENIED),
            (WalletState.QUALIFIED, WalletUserStatus.PENDING),
            (WalletState.QUALIFIED, WalletUserStatus.ACTIVE),
            (WalletState.QUALIFIED, WalletUserStatus.DENIED),
            (WalletState.RUNOUT, WalletUserStatus.PENDING),
            (WalletState.RUNOUT, WalletUserStatus.ACTIVE),
            (WalletState.RUNOUT, WalletUserStatus.DENIED),
            (WalletState.EXPIRED, WalletUserStatus.PENDING),
            (WalletState.EXPIRED, WalletUserStatus.ACTIVE),
            (WalletState.EXPIRED, WalletUserStatus.DENIED),
            (WalletState.DISQUALIFIED, WalletUserStatus.PENDING),
            (WalletState.DISQUALIFIED, WalletUserStatus.ACTIVE),
            (WalletState.DISQUALIFIED, WalletUserStatus.DENIED),
        ],
    )
    def test_get_wallet_summaries(
        reimbursement_wallet_repository: ReimbursementWalletRepository,
        enterprise_user: User,
        qualified_alegeus_wallet_hdhp_single: ReimbursementWallet,
        active_wallet_user: ReimbursementWalletUsers,
        wallet_state: WalletState,
        wallet_user_status: WalletUserStatus,
    ):
        # Given
        qualified_alegeus_wallet_hdhp_single.state = wallet_state
        active_wallet_user.status = wallet_user_status

        # When
        enrolled_wallets: List[
            MemberWalletSummary
        ] = reimbursement_wallet_repository.get_wallet_summaries(
            user_id=enterprise_user.id
        )

        # Then
        assert bool(enrolled_wallets)

    @staticmethod
    def test_get_wallet_summaries_direct_payment(
        reimbursement_wallet_repository: ReimbursementWalletRepository,
        enterprise_user: User,
        qualified_direct_payment_enabled_wallet: ReimbursementWallet,
        active_wallet_user: ReimbursementWalletUsers,
    ):
        # Given
        # TODO: Fix the test fixture setup, as direct_payment_enabled_wallet isn't really a direct payment wallet since
        # user setup and expense types are incorrect on the categories.
        enterprise_user.member_profile.country_code = "US"
        for (
            category
        ) in (
            qualified_direct_payment_enabled_wallet.reimbursement_organization_settings.allowed_reimbursement_categories
        ):
            ReimbursementRequestCategoryExpenseTypesFactory.create(
                reimbursement_request_category_id=category.reimbursement_request_category_id,
                expense_type=ReimbursementRequestExpenseTypes.FERTILITY,
            )

        # When
        enrolled_wallets: List[
            MemberWalletSummary
        ] = reimbursement_wallet_repository.get_wallet_summaries(
            user_id=enterprise_user.id
        )

        # Then
        assert bool(enrolled_wallets)

    @staticmethod
    def test_get_wallet_summaries_populates_obj(
        reimbursement_wallet_repository: ReimbursementWalletRepository,
        enterprise_user: User,
        qualified_alegeus_wallet_hdhp_single: ReimbursementWallet,
        active_wallet_user: ReimbursementWalletUsers,
    ):
        # Given
        qualified_alegeus_wallet_hdhp_single.state = WalletState.QUALIFIED
        active_wallet_user.status = WalletUserStatus.ACTIVE

        # When
        enrolled_wallets: List[
            MemberWalletSummary
        ] = reimbursement_wallet_repository.get_wallet_summaries(
            user_id=enterprise_user.id
        )

        # Then
        assert enrolled_wallets[0] == MemberWalletSummary(
            wallet=qualified_alegeus_wallet_hdhp_single,
            wallet_id=qualified_alegeus_wallet_hdhp_single.id,
            wallet_state=qualified_alegeus_wallet_hdhp_single.state,
            wallet_user_status=active_wallet_user.status,
            payments_customer_id=qualified_alegeus_wallet_hdhp_single.payments_customer_id,
            channel_id=active_wallet_user.channel_id,
            is_shareable=qualified_alegeus_wallet_hdhp_single.is_shareable,
            org_id=qualified_alegeus_wallet_hdhp_single.reimbursement_organization_settings.organization_id,
            org_settings_id=qualified_alegeus_wallet_hdhp_single.reimbursement_organization_settings_id,
            direct_payment_enabled=qualified_alegeus_wallet_hdhp_single.reimbursement_organization_settings.direct_payment_enabled,
            member_id_hash=enterprise_user.esp_id,
            org_survey_url=qualified_alegeus_wallet_hdhp_single.reimbursement_organization_settings.survey_url,
            overview_resource_title=mock.ANY,
            overview_resource_id=mock.ANY,
            faq_resource_title=mock.ANY,
            faq_resource_content_type=mock.ANY,
            faq_resource_slug=mock.ANY,
        )


class TestGetMemberType:
    @staticmethod
    def test_get_member_type_calls_get_member_type(
        reimbursement_wallet_repository: ReimbursementWalletRepository,
        enterprise_user: User,
    ):
        # Given
        # When
        with mock.patch(
            "wallet.repository.reimbursement_wallet.get_member_type"
        ) as mock_get_member_type:
            reimbursement_wallet_repository.get_member_type(user_id=enterprise_user.id)

        # Then
        mock_get_member_type.assert_called_with(user=enterprise_user)


class TestSearchByWalletBenefitId:
    @staticmethod
    def test_search_by_wallet_benefit_id_not_found(
        reimbursement_wallet_repository: ReimbursementWalletRepository,
        enterprise_user: User,
        qualified_alegeus_wallet_hdhp_single: ReimbursementWallet,
    ):
        # Given
        date_of_birth = enterprise_user.health_profile.birthday
        last_name = enterprise_user.last_name
        wallet_benefit: ReimbursementWalletBenefit = assign_benefit_id(
            wallet=qualified_alegeus_wallet_hdhp_single
        )

        # When
        profile: MemberBenefitProfile = (
            reimbursement_wallet_repository.search_by_wallet_benefit_id(
                last_name=last_name + "huh",
                date_of_birth=date_of_birth,
                benefit_id=wallet_benefit.maven_benefit_id,
            )
        )

        # Then
        assert not profile

    @staticmethod
    def test_search_by_wallet_benefit_id_case_insensitive(
        reimbursement_wallet_repository: ReimbursementWalletRepository,
        enterprise_user: User,
        qualified_alegeus_wallet_hdhp_single: ReimbursementWallet,
    ):
        # Given
        date_of_birth = enterprise_user.health_profile.birthday
        last_name = enterprise_user.last_name
        wallet_benefit: ReimbursementWalletBenefit = assign_benefit_id(
            wallet=qualified_alegeus_wallet_hdhp_single
        )

        # When
        profile: MemberBenefitProfile = (
            reimbursement_wallet_repository.search_by_wallet_benefit_id(
                last_name=last_name.upper(),
                date_of_birth=date_of_birth,
                benefit_id=wallet_benefit.maven_benefit_id,
            )
        )

        # Then
        assert profile.user_id == enterprise_user.id

    @staticmethod
    def test_search_by_wallet_benefit_id(
        reimbursement_wallet_repository: ReimbursementWalletRepository,
        enterprise_user: User,
        qualified_alegeus_wallet_hdhp_single: ReimbursementWallet,
    ):
        # Given
        date_of_birth = enterprise_user.health_profile.birthday
        last_name = enterprise_user.last_name
        wallet_benefit: ReimbursementWalletBenefit = assign_benefit_id(
            wallet=qualified_alegeus_wallet_hdhp_single
        )

        # When
        profile: MemberBenefitProfile = (
            reimbursement_wallet_repository.search_by_wallet_benefit_id(
                last_name=last_name,
                date_of_birth=date_of_birth,
                benefit_id=wallet_benefit.maven_benefit_id,
            )
        )

        # Then
        assert profile == MemberBenefitProfile(
            user_id=enterprise_user.id,
            benefit_id=wallet_benefit.maven_benefit_id,
            date_of_birth=date_of_birth,
            email=enterprise_user.email,
            first_name=enterprise_user.first_name,
            last_name=enterprise_user.last_name,
            phone=enterprise_user.member_profile.phone_number,
        )

    @staticmethod
    def test_search_by_wallet_benefit_id_multiple_wallet_users(
        reimbursement_wallet_repository: ReimbursementWalletRepository,
        enterprise_user: User,
        qualified_alegeus_wallet_hdhp_single: ReimbursementWallet,
    ):
        # Given
        date_of_birth = enterprise_user.health_profile.birthday
        last_name = enterprise_user.last_name
        wallet_benefit: ReimbursementWalletBenefit = assign_benefit_id(
            wallet=qualified_alegeus_wallet_hdhp_single
        )
        second_user: User = EnterpriseUserFactory.create()
        ReimbursementWalletUsersFactory.create(
            user_id=second_user.id,
            reimbursement_wallet_id=qualified_alegeus_wallet_hdhp_single.id,
        )

        # When
        profile: MemberBenefitProfile = (
            reimbursement_wallet_repository.search_by_wallet_benefit_id(
                last_name=last_name,
                date_of_birth=date_of_birth,
                benefit_id=wallet_benefit.maven_benefit_id,
            )
        )

        # Then
        assert profile == MemberBenefitProfile(
            user_id=enterprise_user.id,
            benefit_id=wallet_benefit.maven_benefit_id,
            date_of_birth=date_of_birth,
            email=enterprise_user.email,
            first_name=enterprise_user.first_name,
            last_name=enterprise_user.last_name,
            phone=enterprise_user.member_profile.phone_number,
        )

    @staticmethod
    def test_search_by_wallet_benefit_id_multiple_wallet_users_none_found(
        reimbursement_wallet_repository: ReimbursementWalletRepository,
        enterprise_user: User,
        qualified_alegeus_wallet_hdhp_single: ReimbursementWallet,
    ):
        # Given
        date_of_birth = enterprise_user.health_profile.birthday
        last_name = enterprise_user.last_name
        wallet_benefit: ReimbursementWalletBenefit = assign_benefit_id(
            wallet=qualified_alegeus_wallet_hdhp_single
        )
        second_user: User = EnterpriseUserFactory.create(
            last_name=last_name, health_profile__date_of_birth=date_of_birth
        )
        ReimbursementWalletUsersFactory.create(
            user_id=second_user.id,
            reimbursement_wallet_id=qualified_alegeus_wallet_hdhp_single.id,
        )

        # When
        profile: MemberBenefitProfile = (
            reimbursement_wallet_repository.search_by_wallet_benefit_id(
                last_name=last_name,
                date_of_birth=date_of_birth,
                benefit_id=wallet_benefit.maven_benefit_id,
            )
        )

        # Then
        assert not profile


class TestGetEligibleWalletOrgSettings:
    @staticmethod
    def test_get_eligible_wallet_org_settings_reimbursement_wallet(
        reimbursement_wallet_repository: ReimbursementWalletRepository,
        wallet_org_settings: ReimbursementOrganizationSettings,
        enterprise_user: User,
    ):
        """Member is eligible for a reimbursement wallet"""
        # Given
        # When
        settings: List[
            OrganizationWalletSettings
        ] = reimbursement_wallet_repository.get_eligible_org_wallet_settings(
            user_id=enterprise_user.id,
            organization_id=enterprise_user.organization_v2.id,
        )

        # Then
        assert settings[0].direct_payment_enabled is False

    @staticmethod
    def test_get_eligible_wallet_org_settings_direct_payment_wallet(
        reimbursement_wallet_repository: ReimbursementWalletRepository,
        wallet_org_settings: ReimbursementOrganizationSettings,
        enterprise_user: User,
    ):
        """Member is eligible for a DP wallet"""
        # Given
        wallet_org_settings.direct_payment_enabled = True

        # When
        settings: List[
            OrganizationWalletSettings
        ] = reimbursement_wallet_repository.get_eligible_org_wallet_settings(
            user_id=enterprise_user.id,
            organization_id=enterprise_user.organization_v2.id,
        )

        # Then
        assert settings[0].direct_payment_enabled is True

    @staticmethod
    def test_get_eligible_wallet_org_settings_only_inactive_ros(
        reimbursement_wallet_repository: ReimbursementWalletRepository,
        wallet_org_settings: ReimbursementOrganizationSettings,
        enterprise_user: User,
    ):
        """
        Organization used to offer wallet
            - #4 - Org used to offer wallet
        """
        # Given
        wallet_org_settings.ended_at = datetime.today() - timedelta(days=1)

        # When
        settings: List[
            OrganizationWalletSettings
        ] = reimbursement_wallet_repository.get_eligible_org_wallet_settings(
            user_id=enterprise_user.id,
            organization_id=enterprise_user.organization_v2.id,
        )

        # Then
        assert len(settings) == 1 and settings[0].org_settings_id is None

    @staticmethod
    def test_get_eligible_wallet_org_settings_no_eligible_ros(
        reimbursement_wallet_repository: ReimbursementWalletRepository,
        enterprise_user: User,
    ):
        """
        Organization does NOT offer wallet
            - Case #2 - Org offers wallet but Member is not eligible for a ROS
            - Case #3 - Org does not offer wallet
        """
        # Given
        # When
        settings: List[
            OrganizationWalletSettings
        ] = reimbursement_wallet_repository.get_eligible_org_wallet_settings(
            user_id=enterprise_user.id,
            organization_id=enterprise_user.organization_v2.id,
        )

        # Then
        assert len(settings) == 1 and settings[0].org_settings_id is None

    @staticmethod
    def test_get_eligible_wallet_org_settings_no_eligible_wallets_org_name(
        reimbursement_wallet_repository: ReimbursementWalletRepository,
        enterprise_user: User,
    ):
        # Given
        enterprise_user.organization_v2.display_name = "Best Company Ever"
        enterprise_user.organization_v2.name = "Best_Company_Ever"

        # When
        settings: List[
            OrganizationWalletSettings
        ] = reimbursement_wallet_repository.get_eligible_org_wallet_settings(
            user_id=enterprise_user.id,
            organization_id=enterprise_user.organization_v2.id,
        )

        # Then
        assert settings[0].organization_name == "Best Company Ever"

    @staticmethod
    def test_get_eligible_wallet_org_settings_no_eligible_wallets_org_name_fallback(
        reimbursement_wallet_repository: ReimbursementWalletRepository,
        enterprise_user: User,
    ):
        # Given
        enterprise_user.organization_v2.display_name = None
        enterprise_user.organization_v2.name = "Best_Company_Ever"

        # When
        settings: List[
            OrganizationWalletSettings
        ] = reimbursement_wallet_repository.get_eligible_org_wallet_settings(
            user_id=enterprise_user.id,
            organization_id=enterprise_user.organization_v2.id,
        )

        # Then
        assert settings[0].organization_name == "Best_Company_Ever"

    @staticmethod
    def test_get_eligible_wallet_org_settings_reimbursement_wallet_org_name(
        reimbursement_wallet_repository: ReimbursementWalletRepository,
        wallet_org_settings: ReimbursementOrganizationSettings,
        enterprise_user: User,
    ):
        # Given
        enterprise_user.organization_v2.display_name = "Best Company Ever"
        enterprise_user.organization_v2.name = "Best_Company_Ever"

        # When
        settings: List[
            OrganizationWalletSettings
        ] = reimbursement_wallet_repository.get_eligible_org_wallet_settings(
            user_id=enterprise_user.id,
            organization_id=enterprise_user.organization_v2.id,
        )
        setting = settings[0]

        # Then
        assert setting.organization_name == "Best Company Ever"

    @staticmethod
    def test_get_eligible_wallet_org_settings_reimbursement_wallet_org_name_fallback(
        reimbursement_wallet_repository: ReimbursementWalletRepository,
        wallet_org_settings: ReimbursementOrganizationSettings,
        enterprise_user: User,
    ):
        # Given
        enterprise_user.organization_v2.display_name = None
        enterprise_user.organization_v2.name = "Best_Company_Ever"

        # When
        settings: List[
            OrganizationWalletSettings
        ] = reimbursement_wallet_repository.get_eligible_org_wallet_settings(
            user_id=enterprise_user.id,
            organization_id=enterprise_user.organization_v2.id,
        )
        setting = settings[0]

        # Then
        assert setting.organization_name == "Best_Company_Ever"

    @staticmethod
    def test_get_eligible_wallet_org_settings_reimbursement_wallet_correct_mapped_fields(
        reimbursement_wallet_repository: ReimbursementWalletRepository,
        wallet_org_settings: ReimbursementOrganizationSettings,
        enterprise_user: User,
    ):
        # Given
        # When
        settings: List[
            OrganizationWalletSettings
        ] = reimbursement_wallet_repository.get_eligible_org_wallet_settings(
            user_id=enterprise_user.id,
            organization_id=enterprise_user.organization_v2.id,
        )
        setting = settings[0]

        # Then
        assert setting == OrganizationWalletSettings(
            direct_payment_enabled=wallet_org_settings.direct_payment_enabled,
            organization_id=wallet_org_settings.organization_id,
            organization_name=mock.ANY,
            org_settings_id=wallet_org_settings.id,
            fertility_program_type=wallet_org_settings.fertility_program_type,
            fertility_allows_taxable=wallet_org_settings.fertility_allows_taxable,
            excluded_procedures=mock.ANY,
            dx_required_procedures=mock.ANY,
        )


class TestGetWalletsAndRwusForUser:
    @staticmethod
    @pytest.mark.parametrize(
        argnames=(
            "wallet_state",
            "rwu_status",
            "wallet_filter",
            "rwu_filter",
            "returned",
        ),
        argvalues=[
            (
                WalletState.QUALIFIED,
                WalletUserStatus.ACTIVE,
                {WalletState.QUALIFIED},
                {},
                True,
            ),
            (
                WalletState.QUALIFIED,
                WalletUserStatus.ACTIVE,
                {},
                {WalletUserStatus.ACTIVE},
                True,
            ),
            (
                WalletState.QUALIFIED,
                WalletUserStatus.ACTIVE,
                {WalletState.QUALIFIED},
                {WalletUserStatus.ACTIVE},
                True,
            ),
            (WalletState.QUALIFIED, WalletUserStatus.ACTIVE, {}, {}, True),
            (
                WalletState.QUALIFIED,
                WalletUserStatus.ACTIVE,
                {WalletState.DISQUALIFIED},
                {},
                False,
            ),
            (
                WalletState.QUALIFIED,
                WalletUserStatus.ACTIVE,
                {},
                {WalletUserStatus.DENIED},
                False,
            ),
            (
                WalletState.QUALIFIED,
                WalletUserStatus.ACTIVE,
                {WalletState.DISQUALIFIED},
                {WalletUserStatus.DENIED},
                False,
            ),
        ],
    )
    def test_get_wallets_and_rwus_for_user_with_filters(
        reimbursement_wallet_repository: ReimbursementWalletRepository,
        enterprise_user: User,
        qualified_alegeus_wallet_hdhp_single: ReimbursementWallet,
        active_wallet_user: ReimbursementWalletUsers,
        wallet_state: WalletState,
        rwu_status: WalletUserStatus,
        wallet_filter: Set[WalletState],
        rwu_filter: Set[WalletUserStatus],
        returned: bool,
    ):
        # Given
        qualified_alegeus_wallet_hdhp_single.state = wallet_state
        active_wallet_user.status = rwu_status

        # When
        wallets_and_rwus = (
            reimbursement_wallet_repository.get_wallets_and_rwus_for_user(
                user_id=enterprise_user.id,
                wallet_states=wallet_filter,
                rwu_statuses=rwu_filter,
            )
        )

        # Then
        assert len(wallets_and_rwus) == returned

    @staticmethod
    def test_get_wallets_and_rwus_for_user_single_wallet(
        reimbursement_wallet_repository: ReimbursementWalletRepository,
        enterprise_user: User,
        qualified_alegeus_wallet_hdhp_single: ReimbursementWallet,
        active_wallet_user: ReimbursementWalletUsers,
    ):
        # Given

        # When
        wallets_and_rwus = (
            reimbursement_wallet_repository.get_wallets_and_rwus_for_user(
                user_id=enterprise_user.id,
            )
        )

        # Then
        assert len(wallets_and_rwus) == 1
        assert wallets_and_rwus[0] == (
            qualified_alegeus_wallet_hdhp_single,
            active_wallet_user,
        )

    @staticmethod
    def test_get_wallets_and_rwus_for_user_multiple_wallets(
        reimbursement_wallet_repository: ReimbursementWalletRepository,
        wallet_org_settings: ReimbursementOrganizationSettings,
        enterprise_user: User,
    ):
        # Given
        num_of_wallets = 3
        expected_wallets_and_rwus = []
        for i in range(num_of_wallets):
            wallet = ReimbursementWalletFactory.create(
                state=WalletState.QUALIFIED,
                reimbursement_organization_settings_id=wallet_org_settings.id,
            )
            wallet.created_at = datetime.today() - timedelta(days=i)
            rwu = ReimbursementWalletUsersFactory.create(
                reimbursement_wallet_id=wallet.id, user_id=enterprise_user.id
            )
            expected_wallets_and_rwus.append((wallet, rwu))

        # When
        wallets_and_rwus = (
            reimbursement_wallet_repository.get_wallets_and_rwus_for_user(
                user_id=enterprise_user.id
            )
        )

        # Then
        assert len(wallets_and_rwus) == num_of_wallets
        assert wallets_and_rwus == expected_wallets_and_rwus


class TestGetWalletsForROS:
    @staticmethod
    def test_get_wallets_by_ros(
        reimbursement_wallet_repository: ReimbursementWalletRepository,
        enterprise_user: User,
        qualified_alegeus_wallet_hdhp_single: ReimbursementWallet,
    ):
        """Simple test with wallet record against the ROS"""
        # Given
        ros_id: int = (
            qualified_alegeus_wallet_hdhp_single.reimbursement_organization_settings_id
        )

        # When
        wallets = reimbursement_wallet_repository.get_wallets_by_ros(ros_id=ros_id)

        # Then
        assert len(wallets) == 1
        assert wallets[0] == qualified_alegeus_wallet_hdhp_single

    @staticmethod
    def test_get_wallets_by_ros_multiple_ros(
        reimbursement_wallet_repository: ReimbursementWalletRepository,
        enterprise_user: User,
        qualified_alegeus_wallet_hdhp_single: ReimbursementWallet,
    ):
        """Test the ROS join when there are multiple ROS's in the test setup"""
        # Given
        another_ros: ReimbursementOrganizationSettings = (
            ReimbursementOrganizationSettingsFactory.create(
                organization_id=enterprise_user.organization_v2.id
            )
        )

        # When
        wallets = reimbursement_wallet_repository.get_wallets_by_ros(
            ros_id=another_ros.id
        )

        # Then
        assert not wallets

    @staticmethod
    def test_get_wallets_by_ros_none_found(
        reimbursement_wallet_repository: ReimbursementWalletRepository,
        enterprise_user: User,
        wallet_org_settings: ReimbursementOrganizationSettings,
    ):
        """Test nothing is returned when ROS has no wallets created against it"""
        # When
        wallets = reimbursement_wallet_repository.get_wallets_by_ros(
            ros_id=wallet_org_settings.id
        )

        # Then
        assert not wallets

    @staticmethod
    @pytest.mark.parametrize(
        argnames=("state_filter", "is_returned"),
        argvalues=[
            (None, True),
            ({}, False),
            ({WalletState.PENDING}, False),
            ({WalletState.PENDING, WalletState.QUALIFIED}, True),
        ],
    )
    def test_get_wallets_by_ros_with_state_filter(
        reimbursement_wallet_repository: ReimbursementWalletRepository,
        enterprise_user: User,
        qualified_alegeus_wallet_hdhp_single: ReimbursementWallet,
        state_filter: set[WalletState],
        is_returned: bool,
    ):
        """Test the optional wallet_states filter"""
        # Given
        ros_id: int = (
            qualified_alegeus_wallet_hdhp_single.reimbursement_organization_settings_id
        )
        qualified_alegeus_wallet_hdhp_single.state = WalletState.QUALIFIED

        # When
        wallets = reimbursement_wallet_repository.get_wallets_by_ros(
            ros_id=ros_id, wallet_states=state_filter
        )

        # Then
        assert (len(wallets) > 0) == is_returned


class TestGetApprovedAmountsForCategory:
    @staticmethod
    def test_get_approved_amount_for_category(
        reimbursement_wallet_repository: ReimbursementWalletRepository,
        enterprise_user: User,
        qualified_alegeus_wallet_hdhp_single: ReimbursementWallet,
    ):
        # Given
        category: ReimbursementOrgSettingCategoryAssociation = qualified_alegeus_wallet_hdhp_single.reimbursement_organization_settings.allowed_reimbursement_categories[
            0
        ]
        ReimbursementRequestFactory.create(
            reimbursement_request_category_id=category.reimbursement_request_category_id,
            reimbursement_wallet_id=qualified_alegeus_wallet_hdhp_single.id,
            state=ReimbursementRequestState.APPROVED,
            amount=500,
            benefit_currency_code="USD",
            transaction_amount=500,
            transaction_currency_code="USD",
            usd_amount=500,
        )
        ReimbursementRequestFactory.create(
            reimbursement_request_category_id=category.reimbursement_request_category_id,
            reimbursement_wallet_id=qualified_alegeus_wallet_hdhp_single.id,
            state=ReimbursementRequestState.APPROVED,
            amount=200,
            benefit_currency_code="USD",
            transaction_amount=200,
            transaction_currency_code="USD",
            usd_amount=200,
        )
        # When
        amount = reimbursement_wallet_repository.get_approved_amount_for_category(
            wallet_id=qualified_alegeus_wallet_hdhp_single.id,
            category_id=category.reimbursement_request_category_id,
        )

        # Then
        assert amount == 700

    @staticmethod
    def test_get_approved_amount_for_category_no_requests(
        reimbursement_wallet_repository: ReimbursementWalletRepository,
        enterprise_user: User,
        qualified_alegeus_wallet_hdhp_single: ReimbursementWallet,
    ):
        # Given
        category: ReimbursementOrgSettingCategoryAssociation = qualified_alegeus_wallet_hdhp_single.reimbursement_organization_settings.allowed_reimbursement_categories[
            0
        ]

        # When
        amount = reimbursement_wallet_repository.get_approved_amount_for_category(
            wallet_id=qualified_alegeus_wallet_hdhp_single.id,
            category_id=category.reimbursement_request_category_id,
        )

        # Then
        assert amount == 0


class TestGetReimbursedAmountsForCategory:
    @staticmethod
    def test_get_reimbursed_amount_for_category(
        reimbursement_wallet_repository: ReimbursementWalletRepository,
        enterprise_user: User,
        qualified_alegeus_wallet_hdhp_single: ReimbursementWallet,
    ):
        # Given
        category: ReimbursementOrgSettingCategoryAssociation = qualified_alegeus_wallet_hdhp_single.reimbursement_organization_settings.allowed_reimbursement_categories[
            0
        ]
        ReimbursementRequestFactory.create(
            reimbursement_request_category_id=category.reimbursement_request_category_id,
            reimbursement_wallet_id=qualified_alegeus_wallet_hdhp_single.id,
            state=ReimbursementRequestState.REIMBURSED,
            amount=500,
            benefit_currency_code="USD",
            transaction_amount=500,
            transaction_currency_code="USD",
            usd_amount=500,
        )
        ReimbursementRequestFactory.create(
            reimbursement_request_category_id=category.reimbursement_request_category_id,
            reimbursement_wallet_id=qualified_alegeus_wallet_hdhp_single.id,
            state=ReimbursementRequestState.REIMBURSED,
            amount=200,
            benefit_currency_code="USD",
            transaction_amount=200,
            transaction_currency_code="USD",
            usd_amount=200,
        )
        # When
        amount = reimbursement_wallet_repository.get_reimbursed_amount_for_category(
            wallet_id=qualified_alegeus_wallet_hdhp_single.id,
            category_id=category.reimbursement_request_category_id,
        )

        # Then
        assert amount == 700

    @staticmethod
    def test_get_reimbursed_amount_for_category_no_requests(
        reimbursement_wallet_repository: ReimbursementWalletRepository,
        enterprise_user: User,
        qualified_alegeus_wallet_hdhp_single: ReimbursementWallet,
    ):
        # Given
        category: ReimbursementOrgSettingCategoryAssociation = qualified_alegeus_wallet_hdhp_single.reimbursement_organization_settings.allowed_reimbursement_categories[
            0
        ]

        # When
        amount = reimbursement_wallet_repository.get_reimbursed_amount_for_category(
            wallet_id=qualified_alegeus_wallet_hdhp_single.id,
            category_id=category.reimbursement_request_category_id,
        )

        # Then
        assert amount == 0


class TestGetUsedCreditsForCategory:
    @staticmethod
    def test_get_credit_balance_for_category(
        reimbursement_wallet_repository: ReimbursementWalletRepository,
        enterprise_user: User,
    ):
        # Given
        org_settings = ReimbursementOrganizationSettingsFactory(
            organization_id=enterprise_user.organization_v2.id,
            allowed_reimbursement_categories__cycle_based=True,
            direct_payment_enabled=True,
        )

        wallet = ReimbursementWalletFactory.create(
            reimbursement_organization_settings=org_settings,
            member=enterprise_user,
            state=WalletState.QUALIFIED,
        )
        category_association = (
            wallet.reimbursement_organization_settings.allowed_reimbursement_categories[
                0
            ]
        )
        category_association.is_direct_payment_eligible = True
        credits = ReimbursementCycleCreditsFactory.create(
            reimbursement_wallet_id=wallet.id,
            reimbursement_organization_settings_allowed_category_id=category_association.id,
            amount=12,
        )
        ReimbursementCycleMemberCreditTransactionFactory.create(
            reimbursement_cycle_credits_id=credits.id,
            amount=12,
            notes="Initial Fund",
        )
        request = ReimbursementRequestFactory.create(
            reimbursement_request_category_id=category_association.reimbursement_request_category_id,
            reimbursement_wallet_id=wallet.id,
            state=ReimbursementRequestState.APPROVED,
            amount=200,
            benefit_currency_code="USD",
            transaction_amount=200,
            transaction_currency_code="USD",
            usd_amount=200,
        )
        ReimbursementCycleMemberCreditTransactionFactory.create(
            reimbursement_cycle_credits_id=credits.id,
            reimbursement_request_id=request.id,
            amount=-5,
            notes="linked to reimbursement request",
        )
        ReimbursementCycleMemberCreditTransactionFactory.create(
            reimbursement_cycle_credits_id=credits.id,
            reimbursement_request_id=None,
            amount=2,
            notes="Adding 2 more credits",
        )

        # When
        credits_remaining = (
            reimbursement_wallet_repository.get_credit_balance_for_category(
                wallet_id=wallet.id, category_association_id=category_association.id
            )
        )

        # Then
        assert credits_remaining == 9


class TestGetNonUSDWallets:
    @staticmethod
    @pytest.mark.parametrize(
        argnames=("currency_code", "wallet_state", "returned"),
        argvalues=[
            ("USD", WalletState.QUALIFIED, False),
            ("USD", WalletState.RUNOUT, False),
            ("USD", WalletState.PENDING, False),
            ("USD", WalletState.EXPIRED, False),
            ("USD", WalletState.DISQUALIFIED, False),
            ("GBP", WalletState.QUALIFIED, True),
            ("GBP", WalletState.RUNOUT, True),
            ("GBP", WalletState.PENDING, False),
            ("GBP", WalletState.EXPIRED, False),
            ("GBP", WalletState.DISQUALIFIED, False),
        ],
    )
    def test_get_non_usd_wallets(
        reimbursement_wallet_repository: ReimbursementWalletRepository,
        enterprise_user: User,
        qualified_alegeus_wallet_hdhp_single: ReimbursementWallet,
        currency_code: str,
        wallet_state: WalletState,
        returned: bool,
    ):
        # Given
        qualified_alegeus_wallet_hdhp_single.state = wallet_state
        category_association = qualified_alegeus_wallet_hdhp_single.get_or_create_wallet_allowed_categories[
            0
        ]
        category_association.currency_code = currency_code

        # When
        wallets = reimbursement_wallet_repository.get_non_usd_wallets()

        # Then
        assert bool(wallets) == returned

        if returned:
            assert wallets[0] == qualified_alegeus_wallet_hdhp_single

    @staticmethod
    @pytest.mark.parametrize(
        argnames="filters", argvalues=["wallet_ids-only", "ros_ids-only", "both"]
    )
    def test_get_non_usd_wallets_with_filters_found(
        reimbursement_wallet_repository: ReimbursementWalletRepository,
        enterprise_user: User,
        qualified_alegeus_wallet_hdhp_single: ReimbursementWallet,
        filters: str,
    ):
        # Given
        category_association = qualified_alegeus_wallet_hdhp_single.get_or_create_wallet_allowed_categories[
            0
        ]
        category_association.currency_code = "GBP"

        if filters == "both":
            kwargs = {
                "wallet_ids": [qualified_alegeus_wallet_hdhp_single.id],
                "ros_ids": [
                    qualified_alegeus_wallet_hdhp_single.reimbursement_organization_settings_id
                ],
            }
        elif filters == "wallet_ids-only":
            kwargs = {"wallet_ids": [qualified_alegeus_wallet_hdhp_single.id]}
        elif filters == "ros_ids-only":
            kwargs = {
                "ros_ids": [
                    qualified_alegeus_wallet_hdhp_single.reimbursement_organization_settings_id
                ]
            }

        # When
        wallets = reimbursement_wallet_repository.get_non_usd_wallets(**kwargs)

        # Then
        assert len(wallets)
        assert wallets[0] == qualified_alegeus_wallet_hdhp_single

    @staticmethod
    def test_get_non_usd_wallets_distinct_wallets(
        reimbursement_wallet_repository: ReimbursementWalletRepository,
        enterprise_user: User,
        two_category_wallet: ReimbursementWallet,
    ):
        # Given
        two_category_wallet.state = WalletState.QUALIFIED
        for (
            category_association
        ) in two_category_wallet.get_or_create_wallet_allowed_categories:
            category_association.currency_code = "GBP"

        # When
        wallets = reimbursement_wallet_repository.get_non_usd_wallets()

        # Then
        assert len(wallets) == 1
        assert wallets[0] == two_category_wallet

    @staticmethod
    @pytest.mark.parametrize(
        argnames="filters", argvalues=["wallet_ids-only", "ros_ids-only", "both"]
    )
    def test_get_non_usd_wallets_with_filters_not_found(
        reimbursement_wallet_repository: ReimbursementWalletRepository,
        enterprise_user: User,
        qualified_alegeus_wallet_hdhp_single: ReimbursementWallet,
        filters: str,
    ):
        # Given
        category_association = qualified_alegeus_wallet_hdhp_single.get_or_create_wallet_allowed_categories[
            0
        ]
        category_association.currency_code = "GBP"

        if filters == "both":
            kwargs = {
                "wallet_ids": [qualified_alegeus_wallet_hdhp_single.id + 1],
                "ros_ids": [
                    qualified_alegeus_wallet_hdhp_single.reimbursement_organization_settings_id
                    + 1
                ],
            }
        elif filters == "wallet_ids-only":
            kwargs = {"wallet_ids": [qualified_alegeus_wallet_hdhp_single.id + 1]}
        elif filters == "ros_ids-only":
            kwargs = {
                "ros_ids": [
                    qualified_alegeus_wallet_hdhp_single.reimbursement_organization_settings_id
                    + 1
                ]
            }

        # When
        wallets = reimbursement_wallet_repository.get_non_usd_wallets(**kwargs)

        # Then
        assert not len(wallets)


class TestGetReimbursementAccount:
    @staticmethod
    def test_get_reimbursement_account(
        reimbursement_wallet_repository: ReimbursementWalletRepository,
        enterprise_user: User,
        qualified_alegeus_wallet_hdhp_single: ReimbursementWallet,
    ):
        # Given
        category_association = qualified_alegeus_wallet_hdhp_single.get_or_create_wallet_allowed_categories[
            0
        ]
        expected_account = ReimbursementAccountFactory.create(
            wallet=qualified_alegeus_wallet_hdhp_single,
            plan=category_association.reimbursement_request_category.reimbursement_plan,
        )

        # When
        account = reimbursement_wallet_repository.get_reimbursement_account(
            wallet=qualified_alegeus_wallet_hdhp_single,
            category=category_association.reimbursement_request_category,
        )

        # Then
        assert account == expected_account

    @staticmethod
    def test_get_reimbursement_account_not_found(
        reimbursement_wallet_repository: ReimbursementWalletRepository,
        enterprise_user: User,
        qualified_alegeus_wallet_hdhp_single: ReimbursementWallet,
    ):
        # Given
        category_association = qualified_alegeus_wallet_hdhp_single.get_or_create_wallet_allowed_categories[
            0
        ]

        # When

        account = reimbursement_wallet_repository.get_reimbursement_account(
            wallet=qualified_alegeus_wallet_hdhp_single,
            category=category_association.reimbursement_request_category,
        )

        # Then
        assert not account
