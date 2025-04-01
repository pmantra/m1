from __future__ import annotations

import datetime
import math
from decimal import Decimal
from typing import Optional
from unittest import mock

import pytest

from authn.models.user import User
from cost_breakdown.pytests.factories import CostBreakdownFactory
from direct_payment.treatment_procedure.models.treatment_procedure import (
    TreatmentProcedureStatus,
)
from direct_payment.treatment_procedure.pytests.factories import (
    TreatmentProcedureFactory,
)
from direct_payment.treatment_procedure.repository.treatment_procedure import (
    TreatmentProcedureRepository,
)
from pytests.factories import OrganizationEmployeeDependentFactory
from wallet.constants import NUM_CREDITS_PER_CYCLE
from wallet.models.constants import (
    BenefitTypes,
    DashboardState,
    MemberType,
    ReimbursementRequestState,
    WalletState,
    WalletUserStatus,
)
from wallet.models.models import (
    CategoryBalance,
    MemberWalletStateSchema,
    MemberWalletSummary,
    WalletBalance,
)
from wallet.models.organization_employee_dependent import OrganizationEmployeeDependent
from wallet.models.reimbursement_wallet import ReimbursementWallet
from wallet.models.reimbursement_wallet_user import ReimbursementWalletUsers
from wallet.pytests.factories import (
    MemberWalletSummaryFactory,
    ReimbursementOrganizationSettingsFactory,
    ReimbursementOrgSettingCategoryAssociationFactory,
    ReimbursementRequestCategoryFactory,
    ReimbursementRequestExchangeRatesFactory,
    ReimbursementRequestFactory,
    ReimbursementWalletFactory,
)
from wallet.repository.member_benefit import MemberBenefitRepository
from wallet.repository.reimbursement_request import ReimbursementRequestRepository
from wallet.repository.reimbursement_wallet import ReimbursementWalletRepository
from wallet.services.currency import DEFAULT_CURRENCY_CODE, CurrencyService
from wallet.services.reimbursement_wallet import (
    CopyWalletValidationError,
    ReimbursementWalletService,
)


class MockReimbursementWalletRepository(ReimbursementWalletRepository):
    session = None


class MockReimbursementRequestRepository(ReimbursementRequestRepository):
    session = None


class MockTreatmentProcedureRepository(TreatmentProcedureRepository):
    session = None


class MockMemberBenefitRepository(MemberBenefitRepository):
    session = None


@pytest.fixture(scope="function")
def mock_wallet_repository():
    with mock.patch(
        "wallet.pytests.services.test_reimbursement_wallet.MockReimbursementWalletRepository",
        spec_set=True,
        autospec=True,
    ) as m:
        yield m.return_value


@pytest.fixture(scope="function")
def mock_requests_repository():
    with mock.patch(
        "wallet.pytests.services.test_reimbursement_wallet.MockReimbursementRequestRepository",
        spec_set=True,
        autospec=True,
    ) as m:
        yield m.return_value


@pytest.fixture(scope="function")
def mock_procedures_repository():
    with mock.patch(
        "wallet.pytests.services.test_reimbursement_wallet.MockTreatmentProcedureRepository",
        spec_set=True,
        autospec=True,
    ) as m:
        yield m.return_value


@pytest.fixture(scope="function")
def mock_member_benefit_repository():
    with mock.patch(
        "wallet.pytests.services.test_reimbursement_wallet.MockMemberBenefitRepository",
        spec_set=True,
        autospec=True,
    ) as m:
        yield m.return_value


@pytest.fixture(scope="function")
def wallet_service(
    mock_wallet_repository,
    mock_requests_repository,
    mock_member_benefit_repository,
    mock_procedures_repository,
):
    return ReimbursementWalletService(
        wallet_repo=mock_wallet_repository,
        requests_repo=mock_requests_repository,
        member_benefit_repo=mock_member_benefit_repository,
        procedures_repo=mock_procedures_repository,
    )


class TestResolveShowWallet:
    @staticmethod
    @pytest.mark.parametrize(
        argnames=("is_eligible", "current_state", "expected"),
        argvalues=[
            (True, WalletState.QUALIFIED, True),
            (True, WalletState.PENDING, True),
            (True, WalletState.DISQUALIFIED, True),
            (True, WalletState.RUNOUT, True),
            (True, WalletState.EXPIRED, True),
            (True, None, True),  # Eligible for wallet, no wallet
            (False, WalletState.QUALIFIED, True),
            (False, WalletState.PENDING, True),
            (False, WalletState.DISQUALIFIED, True),
            (False, WalletState.RUNOUT, True),
            (False, WalletState.EXPIRED, False),  # Expired wallet
            (False, None, False),  # Not eligible for wallet, no wallet
        ],
    )
    def test_resolve_show_wallet(
        wallet_service: ReimbursementWalletService,
        is_eligible: bool,
        current_state: WalletState | None,
        expected: bool,
    ):
        # Given

        # When
        show_wallet: bool = wallet_service._resolve_show_wallet(
            is_eligible=is_eligible, current_state=current_state
        )

        # Then
        assert show_wallet == expected


class TestResolveDashboardState:
    @staticmethod
    @pytest.mark.parametrize(
        argnames=("is_eligible", "current_state", "expected"),
        argvalues=[
            (True, None, DashboardState.APPLY),
            (True, WalletState.PENDING, DashboardState.PENDING),
            (True, WalletState.QUALIFIED, DashboardState.QUALIFIED),
            (True, WalletState.DISQUALIFIED, DashboardState.APPLY),
            (True, WalletState.RUNOUT, DashboardState.RUNOUT),
            (False, WalletState.PENDING, DashboardState.PENDING),
            (False, WalletState.QUALIFIED, DashboardState.QUALIFIED),
            (False, WalletState.DISQUALIFIED, DashboardState.DISQUALIFIED),
            (False, WalletState.RUNOUT, DashboardState.RUNOUT),
            (True, WalletState.EXPIRED, DashboardState.APPLY),
            (False, WalletState.EXPIRED, None),
        ],
    )
    def test_resolve_dashboard_state(
        wallet_service: ReimbursementWalletService,
        is_eligible: bool,
        current_state: WalletState | None,
        expected: DashboardState | None,
    ):
        # Given

        # When
        show_wallet: DashboardState | None = wallet_service._resolve_dashboard_state(
            is_eligible=is_eligible, current_state=current_state
        )

        # Then
        assert show_wallet == expected


class TestGetMemberWalletState:
    @staticmethod
    def test_get_member_wallet_state_calls_repo_methods(
        wallet_service: ReimbursementWalletService, enterprise_user: User
    ):
        # When
        wallet_service.get_member_wallet_state(user=enterprise_user)

        # Then
        wallet_service.wallet_repo.get_eligible_wallets.assert_called_with(
            user_id=enterprise_user.id
        )
        wallet_service.wallet_repo.get_member_type.assert_called_with(
            user_id=enterprise_user.id
        )

    @staticmethod
    def test_get_member_wallet_state_returns_correct_type(
        wallet_service: ReimbursementWalletService, enterprise_user: User
    ):
        # When
        returned = wallet_service.get_member_wallet_state(user=enterprise_user)

        # Then
        assert isinstance(returned, MemberWalletStateSchema)

    @staticmethod
    def test_get_member_wallet_state_eligible_field(
        wallet_service: ReimbursementWalletService,
        disqualified_member_wallet_summary_reimbursement: MemberWalletSummary,
        enterprise_user: User,
    ):
        # Given
        wallet_service.wallet_repo.get_eligible_wallets.return_value = [
            mock.MagicMock(),
            mock.MagicMock(),
        ]
        wallet_service.wallet_repo.get_wallet_summaries.return_value = [
            disqualified_member_wallet_summary_reimbursement
        ]

        # When
        mws: MemberWalletStateSchema = wallet_service.get_member_wallet_state(
            user=enterprise_user
        )

        # Then
        assert len(mws.eligible) == 3

    @staticmethod
    @pytest.mark.parametrize(
        argnames=("member_type", "is_populated"),
        argvalues=[
            (MemberType.MARKETPLACE, False),
            (MemberType.MAVEN_ACCESS, True),
            (MemberType.MAVEN_GREEN, True),
            (MemberType.MAVEN_GOLD, True),
        ],
    )
    def test_get_member_wallet_state_benefit_id(
        wallet_service: ReimbursementWalletService,
        active_member_wallet_summary_reimbursement: MemberWalletSummary,
        enterprise_user: User,
        member_type: MemberType,
        is_populated: bool,
    ):
        # Given
        wallet_service.wallet_repo.get_eligible_wallets.return_value = [
            mock.MagicMock(),
        ]
        wallet_service.wallet_repo.get_wallet_summaries.return_value = [
            active_member_wallet_summary_reimbursement
        ]
        wallet_service.wallet_repo.get_member_type.return_value = member_type
        wallet_service.member_benefit_repo.get_member_benefit_id.return_value = (
            "M999999999"
        )

        # When
        mws: MemberWalletStateSchema = wallet_service.get_member_wallet_state(
            user=enterprise_user
        )

        # Then
        assert (mws.summary.member_benefit_id is not None) == is_populated

    @staticmethod
    @pytest.mark.parametrize(
        argnames=("member_type", "is_returned"),
        argvalues=[
            (MemberType.MARKETPLACE, False),
            (MemberType.MAVEN_ACCESS, True),
            (MemberType.MAVEN_GREEN, True),
            (MemberType.MAVEN_GOLD, True),
        ],
    )
    def test_get_member_wallet_state_pharmacy_information(
        wallet_service: ReimbursementWalletService,
        active_member_wallet_summary_reimbursement: MemberWalletSummary,
        enterprise_user: User,
        member_type: MemberType,
        is_returned: bool,
    ):
        # Given
        wallet_service.wallet_repo.get_eligible_wallets.return_value = [
            mock.MagicMock(),
        ]
        wallet_service.wallet_repo.get_wallet_summaries.return_value = [
            active_member_wallet_summary_reimbursement
        ]
        wallet_service.wallet_repo.get_member_type.return_value = member_type
        rx_information = {
            "name": "SMP Pharmacy",
            "url": "https://www.mavenclinic.com/app/resources/content/r/mavenrx-smp-pharmacy",
        }

        # When
        with mock.patch(
            "wallet.services.reimbursement_wallet.get_pharmacy_details_for_wallet"
        ) as mock_get_rx:
            mock_get_rx.return_value = rx_information
            mws: MemberWalletStateSchema = wallet_service.get_member_wallet_state(
                user=enterprise_user
            )

        # Then
        if is_returned:
            assert mws.summary.pharmacy.serialize() == rx_information
        else:
            assert mws.summary.pharmacy is None

    @staticmethod
    def test_get_member_wallet_calls_resolve_show_wallet(
        wallet_service: ReimbursementWalletService,
        active_member_wallet_summary_reimbursement: MemberWalletSummary,
        enterprise_user: User,
    ):
        # Given
        wallet_state = WalletState.QUALIFIED
        eligible_wallets = [active_member_wallet_summary_reimbursement]

        wallet_service.wallet_repo.get_wallet_summaries.return_value = eligible_wallets

        # When
        with mock.patch(
            "wallet.services.reimbursement_wallet.ReimbursementWalletService._resolve_show_wallet"
        ) as mock_resolve_show_wallet:
            wallet_service.get_member_wallet_state(user=enterprise_user)

        # Then
        mock_resolve_show_wallet.assert_called_with(
            current_state=wallet_state, is_eligible=bool(eligible_wallets)
        )

    @staticmethod
    def test_get_member_wallet_calls_resolve_dashboard_state(
        wallet_service: ReimbursementWalletService,
        active_member_wallet_summary_reimbursement: MemberWalletSummary,
        enterprise_user: User,
    ):
        # Given
        wallet_state = WalletState.QUALIFIED
        eligible_wallets = [active_member_wallet_summary_reimbursement]

        wallet_service.wallet_repo.get_wallet_summaries.return_value = eligible_wallets

        # When
        with mock.patch(
            "wallet.services.reimbursement_wallet.ReimbursementWalletService._resolve_dashboard_state"
        ) as mock_resolve_dashboard_state:
            wallet_service.get_member_wallet_state(user=enterprise_user)

        # Then
        mock_resolve_dashboard_state.assert_called_with(
            current_state=wallet_state, is_eligible=bool(eligible_wallets)
        )

    @staticmethod
    def test_get_member_wallet_populates_summary_wallet_fields_enrolled_wallet_is_shareable(
        wallet_service: ReimbursementWalletService,
        enterprise_user: User,
    ):
        # Given
        wallet_service.wallet_repo.get_wallet_summaries.return_value = [
            MemberWalletSummaryFactory.create(
                wallet_id=453536,
                channel_id=5346753,
                wallet_state=WalletState.QUALIFIED,
                wallet_user_status=WalletUserStatus.ACTIVE,
                is_shareable=True,
            ),
            MemberWalletSummaryFactory.create(
                wallet_id=4365467,
                channel_id=365346,
                wallet_state=WalletState.DISQUALIFIED,
                wallet_user_status=WalletUserStatus.ACTIVE,
                is_shareable=False,
            ),
        ]

        # When
        wallet_state = wallet_service.get_member_wallet_state(user=enterprise_user)

        # Then
        assert wallet_state.summary.is_shareable is True
        assert wallet_state.summary.wallet_id == 453536
        assert wallet_state.summary.channel_id == 5346753

    @staticmethod
    @pytest.mark.parametrize(
        argnames=("wallet_state", "rwu_status", "show_wallet", "dashboard_state"),
        argvalues=[
            (
                WalletState.PENDING,
                WalletUserStatus.PENDING,
                True,
                DashboardState.PENDING,
            ),
            (
                WalletState.PENDING,
                WalletUserStatus.ACTIVE,
                True,
                DashboardState.PENDING,
            ),
            (
                WalletState.PENDING,
                WalletUserStatus.DENIED,
                True,
                DashboardState.DISQUALIFIED,
            ),
            (
                WalletState.QUALIFIED,
                WalletUserStatus.PENDING,
                True,
                DashboardState.PENDING,
            ),
            (
                WalletState.QUALIFIED,
                WalletUserStatus.ACTIVE,
                True,
                DashboardState.QUALIFIED,
            ),
            (
                WalletState.QUALIFIED,
                WalletUserStatus.DENIED,
                True,
                DashboardState.DISQUALIFIED,
            ),
            (
                WalletState.RUNOUT,
                WalletUserStatus.PENDING,
                True,
                DashboardState.PENDING,
            ),
            (WalletState.RUNOUT, WalletUserStatus.ACTIVE, True, DashboardState.RUNOUT),
            (
                WalletState.RUNOUT,
                WalletUserStatus.DENIED,
                True,
                DashboardState.DISQUALIFIED,
            ),
            (WalletState.EXPIRED, WalletUserStatus.PENDING, False, None),
            (WalletState.EXPIRED, WalletUserStatus.ACTIVE, False, None),
            (WalletState.EXPIRED, WalletUserStatus.DENIED, False, None),
            (
                WalletState.DISQUALIFIED,
                WalletUserStatus.PENDING,
                True,
                DashboardState.DISQUALIFIED,
            ),
            (
                WalletState.DISQUALIFIED,
                WalletUserStatus.ACTIVE,
                True,
                DashboardState.DISQUALIFIED,
            ),
            (
                WalletState.DISQUALIFIED,
                WalletUserStatus.DENIED,
                True,
                DashboardState.DISQUALIFIED,
            ),
        ],
    )
    def test_get_member_wallet_summary_fields_existing_wallet(
        wallet_service: ReimbursementWalletService,
        active_member_wallet_summary_reimbursement: MemberWalletSummary,
        enterprise_user: User,
        wallet_state: WalletState,
        rwu_status: WalletUserStatus,
        show_wallet: bool,
        dashboard_state: DashboardState,
    ):
        # Given
        wallet_service.wallet_repo.get_wallet_summaries.return_value = [
            MemberWalletSummaryFactory.create(
                wallet_id=4365467,
                channel_id=365346,
                wallet_state=wallet_state,
                wallet_user_status=rwu_status,
            )
        ]
        wallet_service.wallet_repo.get_eligible_wallets.return_value = []

        # When
        wallet_state = wallet_service.get_member_wallet_state(user=enterprise_user)

        # Then
        assert wallet_state.summary.dashboard_state == dashboard_state
        assert wallet_state.summary.show_wallet == show_wallet

    @staticmethod
    def test_get_member_wallet_summary_fields_eligible_wallet(
        wallet_service: ReimbursementWalletService,
        active_member_wallet_summary_reimbursement: MemberWalletSummary,
        enterprise_user: User,
    ):
        # Given
        wallet_service.wallet_repo.get_wallet_summaries.return_value = []
        wallet_service.wallet_repo.get_eligible_wallets.return_value = [
            MemberWalletSummaryFactory.create(
                wallet_id=None,
                channel_id=None,
                wallet_state=None,
                wallet_user_status=None,
            )
        ]

        # When
        wallet_state = wallet_service.get_member_wallet_state(user=enterprise_user)

        # Then
        assert wallet_state.summary.dashboard_state == DashboardState.APPLY
        assert wallet_state.summary.show_wallet is True

    @staticmethod
    def test_get_member_wallet_summary_fields_not_eligible(
        wallet_service: ReimbursementWalletService,
        active_member_wallet_summary_reimbursement: MemberWalletSummary,
        enterprise_user: User,
    ):
        # Given
        wallet_service.wallet_repo.get_wallet_summaries.return_value = []
        wallet_service.wallet_repo.get_eligible_wallets.return_value = []

        # When
        wallet_state = wallet_service.get_member_wallet_state(user=enterprise_user)

        # Then
        assert wallet_state.summary.dashboard_state is None
        assert wallet_state.summary.show_wallet is False

    @staticmethod
    @pytest.mark.parametrize(
        argnames=("wallet_state", "rwu_status", "show_wallet", "dashboard_state"),
        argvalues=[
            (
                WalletState.PENDING,
                WalletUserStatus.PENDING,
                True,
                DashboardState.PENDING,
            ),
            (
                WalletState.PENDING,
                WalletUserStatus.ACTIVE,
                True,
                DashboardState.PENDING,
            ),
            (WalletState.PENDING, WalletUserStatus.DENIED, True, DashboardState.APPLY),
            (
                WalletState.QUALIFIED,
                WalletUserStatus.PENDING,
                True,
                DashboardState.PENDING,
            ),
            (
                WalletState.QUALIFIED,
                WalletUserStatus.ACTIVE,
                True,
                DashboardState.QUALIFIED,
            ),
            (
                WalletState.QUALIFIED,
                WalletUserStatus.DENIED,
                True,
                DashboardState.APPLY,
            ),
            (
                WalletState.RUNOUT,
                WalletUserStatus.PENDING,
                True,
                DashboardState.PENDING,
            ),
            (WalletState.RUNOUT, WalletUserStatus.ACTIVE, True, DashboardState.RUNOUT),
            (WalletState.RUNOUT, WalletUserStatus.DENIED, True, DashboardState.APPLY),
            (WalletState.EXPIRED, WalletUserStatus.PENDING, True, DashboardState.APPLY),
            (WalletState.EXPIRED, WalletUserStatus.ACTIVE, True, DashboardState.APPLY),
            (WalletState.EXPIRED, WalletUserStatus.DENIED, True, DashboardState.APPLY),
            (
                WalletState.DISQUALIFIED,
                WalletUserStatus.PENDING,
                True,
                DashboardState.APPLY,
            ),
            (
                WalletState.DISQUALIFIED,
                WalletUserStatus.ACTIVE,
                True,
                DashboardState.APPLY,
            ),
            (
                WalletState.DISQUALIFIED,
                WalletUserStatus.DENIED,
                True,
                DashboardState.APPLY,
            ),
        ],
    )
    def test_get_member_wallet_summary_fields_existing_wallet_and_eligible_wallet(
        wallet_service: ReimbursementWalletService,
        active_member_wallet_summary_reimbursement: MemberWalletSummary,
        enterprise_user: User,
        wallet_state: WalletState,
        rwu_status: WalletUserStatus,
        show_wallet: bool,
        dashboard_state: DashboardState,
    ):
        # Given
        wallet_service.wallet_repo.get_wallet_summaries.return_value = [
            MemberWalletSummaryFactory.create(
                wallet_id=4365467,
                channel_id=365346,
                wallet_state=wallet_state,
                wallet_user_status=rwu_status,
            )
        ]
        wallet_service.wallet_repo.get_eligible_wallets.return_value = [
            MemberWalletSummaryFactory.create(
                wallet_id=None,
                channel_id=None,
                wallet_state=None,
                wallet_user_status=None,
            )
        ]

        # When
        wallet_state = wallet_service.get_member_wallet_state(user=enterprise_user)

        # Then
        assert wallet_state.summary.dashboard_state == dashboard_state
        assert wallet_state.summary.show_wallet == show_wallet


class TestResolveEligibleState:
    @staticmethod
    @pytest.mark.parametrize(
        argnames=("wallet_state", "wallet_user_status", "expected_wallet_state"),
        argvalues=[
            (WalletState.PENDING, WalletUserStatus.PENDING, WalletState.PENDING),
            (WalletState.PENDING, WalletUserStatus.ACTIVE, WalletState.PENDING),
            (WalletState.PENDING, WalletUserStatus.DENIED, WalletState.DISQUALIFIED),
            (WalletState.QUALIFIED, WalletUserStatus.PENDING, WalletState.PENDING),
            (WalletState.QUALIFIED, WalletUserStatus.ACTIVE, WalletState.QUALIFIED),
            (WalletState.QUALIFIED, WalletUserStatus.DENIED, WalletState.DISQUALIFIED),
            (WalletState.RUNOUT, WalletUserStatus.PENDING, WalletState.PENDING),
            (WalletState.RUNOUT, WalletUserStatus.ACTIVE, WalletState.RUNOUT),
            (WalletState.RUNOUT, WalletUserStatus.DENIED, WalletState.DISQUALIFIED),
            (WalletState.EXPIRED, WalletUserStatus.PENDING, WalletState.EXPIRED),
            (WalletState.EXPIRED, WalletUserStatus.ACTIVE, WalletState.EXPIRED),
            (WalletState.EXPIRED, WalletUserStatus.DENIED, WalletState.EXPIRED),
            (
                WalletState.DISQUALIFIED,
                WalletUserStatus.PENDING,
                WalletState.DISQUALIFIED,
            ),
            (
                WalletState.DISQUALIFIED,
                WalletUserStatus.ACTIVE,
                WalletState.DISQUALIFIED,
            ),
            (
                WalletState.DISQUALIFIED,
                WalletUserStatus.DENIED,
                WalletState.DISQUALIFIED,
            ),
        ],
    )
    def test_resolve_eligible_state(
        wallet_service: ReimbursementWalletService,
        wallet_state: WalletState,
        wallet_user_status: WalletUserStatus,
        expected_wallet_state: WalletState,
    ):
        # Given

        # When
        wallet_state: WalletState = wallet_service.resolve_eligible_state(
            default_wallet_state=wallet_state, wallet_user_status=wallet_user_status
        )

        # Then
        assert wallet_state == expected_wallet_state


class TestIsDisqualified:
    @staticmethod
    @pytest.mark.parametrize(
        argnames=("wallet_state", "wallet_user_status", "expected"),
        argvalues=[
            (WalletState.PENDING, WalletUserStatus.PENDING, False),
            (WalletState.PENDING, WalletUserStatus.ACTIVE, False),
            (WalletState.PENDING, WalletUserStatus.DENIED, True),
            (WalletState.QUALIFIED, WalletUserStatus.PENDING, False),
            (WalletState.QUALIFIED, WalletUserStatus.ACTIVE, False),
            (WalletState.QUALIFIED, WalletUserStatus.DENIED, True),
            (WalletState.RUNOUT, WalletUserStatus.PENDING, False),
            (WalletState.RUNOUT, WalletUserStatus.ACTIVE, False),
            (WalletState.RUNOUT, WalletUserStatus.DENIED, True),
            (WalletState.EXPIRED, WalletUserStatus.PENDING, False),
            (WalletState.EXPIRED, WalletUserStatus.ACTIVE, False),
            (WalletState.EXPIRED, WalletUserStatus.DENIED, True),
            (WalletState.DISQUALIFIED, WalletUserStatus.PENDING, True),
            (WalletState.DISQUALIFIED, WalletUserStatus.ACTIVE, True),
            (WalletState.DISQUALIFIED, WalletUserStatus.DENIED, True),
        ],
    )
    def test_is_disqualified(
        wallet_service: ReimbursementWalletService,
        wallet_state: WalletState,
        wallet_user_status: WalletUserStatus,
        expected: bool,
        active_member_wallet_summary_reimbursement: MemberWalletSummary,
    ):
        # Given
        wallet_settings = MemberWalletSummaryFactory.create(
            wallet_state=wallet_state, wallet_user_status=wallet_user_status
        )

        # When
        # Then
        assert wallet_service.is_disqualified(settings=wallet_settings) == expected


class TestIsEnrolled:
    @staticmethod
    @pytest.mark.parametrize(
        argnames=("wallet_state", "wallet_user_status", "expected"),
        argvalues=[
            (WalletState.PENDING, WalletUserStatus.PENDING, True),
            (WalletState.PENDING, WalletUserStatus.ACTIVE, True),
            (WalletState.PENDING, WalletUserStatus.DENIED, False),
            (WalletState.QUALIFIED, WalletUserStatus.PENDING, True),
            (WalletState.QUALIFIED, WalletUserStatus.ACTIVE, True),
            (WalletState.QUALIFIED, WalletUserStatus.DENIED, False),
            (WalletState.RUNOUT, WalletUserStatus.PENDING, True),
            (WalletState.RUNOUT, WalletUserStatus.ACTIVE, True),
            (WalletState.RUNOUT, WalletUserStatus.DENIED, False),
            (WalletState.EXPIRED, WalletUserStatus.PENDING, False),
            (WalletState.EXPIRED, WalletUserStatus.ACTIVE, False),
            (WalletState.EXPIRED, WalletUserStatus.DENIED, False),
            (WalletState.DISQUALIFIED, WalletUserStatus.PENDING, False),
            (WalletState.DISQUALIFIED, WalletUserStatus.ACTIVE, False),
            (WalletState.DISQUALIFIED, WalletUserStatus.DENIED, False),
        ],
    )
    def test_is_enrolled(
        wallet_service: ReimbursementWalletService,
        wallet_state: WalletState,
        wallet_user_status: WalletUserStatus,
        expected: bool,
    ):
        # Given
        wallet_settings = MemberWalletSummaryFactory.create(
            wallet_state=wallet_state,
            wallet_user_status=wallet_user_status,
        )

        # When
        # Then
        assert wallet_service.is_enrolled(settings=wallet_settings) == expected


class TestFormatMemberSurveyUrl:
    @staticmethod
    def test_correct_url_returned_auto_qualification(
        wallet_service: ReimbursementWalletService,
        enterprise_user: User,
    ):
        # Given
        expected_url = "/app/wallet/apply"

        # When
        url = wallet_service.get_member_survey_url()

        # Then
        assert url.endswith(expected_url)


class TestGetWalletBalance:
    @staticmethod
    @pytest.mark.parametrize(
        argnames=(
            "is_unlimited",
            "spent_amount",
            "expected_spent_amount",
            "expected_limit_amount",
            "expected_pending_amount",
            "expected_available_balance_amount",
            "expected_current_balance_amount",
        ),
        argvalues=[
            pytest.param(
                False,
                10_000_00,
                10_000_00,
                25_000_00,
                0,
                15_000_00,
                15_000_00,
                id="rw_limited_under_limit",
            ),
            pytest.param(
                False,
                10_000_000_00,
                10_000_000_00,
                25_000_00,
                0,
                0,
                0,
                id="rw_limited_over_limit",
            ),
            pytest.param(
                True,
                125_000_00,
                125_000_00,
                None,
                0,
                math.inf,
                math.inf,
                id="rw_unlimited_under_limit",
            ),
        ],
    )
    def test_get_wallet_balance_reimbursement_wallet(
        wallet_service: ReimbursementWalletService,
        basic_qualified_wallet: ReimbursementWallet,
        basic_user_for_wallet: User,
        is_unlimited: bool,
        spent_amount: int,
        expected_spent_amount: int,
        expected_pending_amount: int,
        expected_limit_amount: Optional[int],
        expected_available_balance_amount: Optional[int],
        expected_current_balance_amount: Optional[int],
    ):
        # Given
        category_association = (
            basic_qualified_wallet.get_or_create_wallet_allowed_categories[0]
        )
        category_association.is_unlimited = is_unlimited
        wallet_service.wallet_repo.get_reimbursed_amount_for_category.return_value = (
            spent_amount
        )
        rwu = basic_user_for_wallet.reimbursement_wallet_users[0]

        # When
        wallet_balance: WalletBalance = wallet_service.get_wallet_balance(
            wallet=basic_qualified_wallet,
            rwu=basic_user_for_wallet.reimbursement_wallet_users[0],
        )

        # Then
        category_balance: CategoryBalance = wallet_balance.categories[0]
        assert wallet_balance == WalletBalance(
            id=basic_qualified_wallet.id,
            state=WalletState.QUALIFIED,
            user_status=rwu.status,
            categories=[
                CategoryBalance(
                    id=category_association.reimbursement_request_category_id,
                    name=category_association.reimbursement_request_category.label,
                    active=True,
                    is_unlimited=is_unlimited,
                    benefit_type=category_association.benefit_type,
                    currency_code="USD",
                    direct_payment_category=False,
                    limit_amount=expected_limit_amount,
                    pending_amount=expected_pending_amount,
                    spent_amount=expected_spent_amount,
                )
            ],
        )
        assert category_balance.available_balance == expected_available_balance_amount
        assert category_balance.current_balance == expected_current_balance_amount

    @staticmethod
    @pytest.mark.parametrize(
        argnames=(
            "is_unlimited",
            "spent_amount",
            "pending_reimbursement_amount",
            "scheduled_tp_with_cb_amount",
            "scheduled_tp_without_cb_amount",
            "cb_member_responsibility_amount",
            "cb_employer_responsibility_amount",
            "expected_limit_amount",
            "expected_spent_amount",
            "expected_pending_amount",
            "expected_available_balance_amount",
            "expected_current_balance_amount",
        ),
        argvalues=[
            pytest.param(
                False,
                10_000_00,
                5_000_00,
                2_000_00,
                3_000_00,
                1_000_00,
                1_000_00,
                25_000_00,
                10_000_00,
                9_000_00,
                6_000_00,
                15_000_00,
                id="dp_limited_under_limit_tp_with_cb_has_employer_responsibility",
            ),
            pytest.param(
                False,
                10_000_00,
                5_000_00,
                2_000_00,
                3_000_00,
                2_000_00,
                0,
                25_000_00,
                10_000_00,
                8_000_00,
                7_000_00,
                15_000_00,
                id="dp_limited_under_limit_tp_with_cb_without_employer_responsibility",
            ),
            pytest.param(
                False,
                20_000_00,
                7_000_00,
                2_000_00,
                3_000_00,
                1_000_00,
                1_000_00,
                25_000_00,
                20_000_00,
                5_000_00,
                0,
                5_000_00,
                id="dp_limited_over_limit_tp_with_cb_has_employer_responsibility",
            ),
            pytest.param(
                False,
                20_000_00,
                7_000_00,
                2_000_00,
                3_000_00,
                2_000_00,
                0,
                25_000_00,
                20_000_00,
                5_000_00,
                0,
                5_000_00,
                id="dp_limited_over_limit_tp_with_cb_without_employer_responsibility",
            ),
            pytest.param(
                False,
                30_000_00,
                7_000_00,
                2_000_00,
                3_000_00,
                2_000_00,
                0,
                25_000_00,
                30_000_00,
                0,
                0,
                0,
                id="dp_limited_over_limit_already",
            ),
            pytest.param(
                True,
                10_000_00,
                5_000_00,
                2_000_00,
                3_000_00,
                1_000_00,
                1_000_00,
                None,
                10_000_00,
                9_000_00,
                math.inf,
                math.inf,
                id="dp_unlimited_tp_with_cb_has_employer_responsibility",
            ),
            pytest.param(
                True,
                10_000_00,
                5_000_00,
                2_000_00,
                3_000_00,
                2_000_00,
                0,
                None,
                10_000_00,
                8_000_00,
                math.inf,
                math.inf,
                id="dp_unlimited_tp_with_cb_without_employer_responsibility",
            ),
        ],
    )
    def test_get_wallet_balance_direct_payment_currency(
        wallet_service: ReimbursementWalletService,
        direct_payment_wallet: ReimbursementWallet,
        user_for_direct_payment_wallet: User,
        is_unlimited: bool,
        spent_amount: int,
        pending_reimbursement_amount: int,
        scheduled_tp_with_cb_amount: int,
        scheduled_tp_without_cb_amount: int,
        cb_member_responsibility_amount: int,
        cb_employer_responsibility_amount: int,
        expected_spent_amount: int,
        expected_limit_amount: Optional[int],
        expected_pending_amount: int,
        expected_available_balance_amount: int,
        expected_current_balance_amount: int,
    ):
        # Given
        category_association = (
            direct_payment_wallet.get_or_create_wallet_allowed_categories[0]
        )
        category_association.is_unlimited = is_unlimited
        wallet_service.wallet_repo.get_approved_amount_for_category.return_value = (
            spent_amount
        )
        rwu = user_for_direct_payment_wallet.reimbursement_wallet_users[0]

        # Create a pending reimbursement
        pending_reimbursement = ReimbursementRequestFactory.create(
            reimbursement_wallet_id=direct_payment_wallet.id,
            reimbursement_request_category_id=category_association.reimbursement_request_category_id,
            amount=pending_reimbursement_amount,
            state=ReimbursementRequestState.PENDING,
        )
        wallet_service.requests_repo.get_pending_reimbursements.return_value = [
            pending_reimbursement
        ]

        # Create a SCHEDULED treatment
        cb = CostBreakdownFactory.create(
            total_member_responsibility=cb_member_responsibility_amount,
            total_employer_responsibility=cb_employer_responsibility_amount,
        )
        scheduled_tp = TreatmentProcedureFactory.create(
            cost_breakdown_id=cb.id,
            reimbursement_wallet_id=direct_payment_wallet.id,
            reimbursement_request_category=category_association.reimbursement_request_category,
            status=TreatmentProcedureStatus.SCHEDULED,
            cost=scheduled_tp_with_cb_amount,
        )
        scheduled_tp_without_cb = TreatmentProcedureFactory.create(
            cost_breakdown_id=None,
            reimbursement_wallet_id=direct_payment_wallet.id,
            reimbursement_request_category=category_association.reimbursement_request_category,
            status=TreatmentProcedureStatus.SCHEDULED,
            cost=scheduled_tp_without_cb_amount,
        )
        wallet_service.procedures_repo.get_scheduled_procedures_and_cbs.return_value = [
            (scheduled_tp, cb),
            (scheduled_tp_without_cb, None),
        ]

        # When
        wallet_balance: WalletBalance = wallet_service.get_wallet_balance(
            wallet=direct_payment_wallet, rwu=rwu, include_procedures_without_cb=True
        )

        # Then
        category_balance: CategoryBalance = wallet_balance.categories[0]
        assert wallet_balance == WalletBalance(
            id=direct_payment_wallet.id,
            state=WalletState.QUALIFIED,
            user_status=rwu.status,
            categories=[
                CategoryBalance(
                    id=category_association.reimbursement_request_category_id,
                    name=category_association.reimbursement_request_category.label,
                    active=True,
                    is_unlimited=is_unlimited,
                    benefit_type=category_association.benefit_type,
                    currency_code="USD",
                    direct_payment_category=True,
                    limit_amount=expected_limit_amount,
                    pending_amount=expected_pending_amount,
                    spent_amount=expected_spent_amount,
                )
            ],
        )
        assert category_balance.available_balance == expected_available_balance_amount
        assert category_balance.current_balance == expected_current_balance_amount

    @staticmethod
    @pytest.mark.parametrize(
        argnames=(
            "spent_amount",
            "pending_reimbursement_amount",
            "scheduled_tp_with_cb_amount",
            "scheduled_tp_without_cb_amount",
            "cb_member_responsibility_amount",
            "cb_employer_responsibility_amount",
            "expected_limit_amount",
            "expected_spent_amount",
            "expected_pending_amount",
            "expected_available_balance_amount",
            "expected_current_balance_amount",
        ),
        argvalues=[
            pytest.param(
                30,
                10,
                10,
                10,
                1_000_00,
                1_000_00,
                120,
                0,
                30,
                60,
                90,
                id="dp_cycle_under_limit_tp_with_cb_has_employer_responsibility",
            ),
            pytest.param(
                30,
                10,
                10,
                10,
                1_000_00,
                0,
                120,
                0,
                20,
                70,
                90,
                id="dp_cycle_under_limit_tp_with_cb_without_employer_responsibility",
            ),
            pytest.param(
                50,
                30,
                30,
                40,
                1_000_00,
                1_000_00,
                120,
                0,
                70,
                0,
                70,
                id="dp_cycle_over_limit_tp_with_cb_has_employer_responsibility",
            ),
            pytest.param(
                50,
                30,
                30,
                40,
                1_000_00,
                0,
                120,
                0,
                70,
                0,
                70,
                id="dp_cycle_over_limit_tp_with_cb_without_employer_responsibility",
            ),
            pytest.param(
                150,
                30,
                30,
                40,
                1_000_00,
                0,
                120,
                0,
                0,
                0,
                0,
                id="dp_cycle_over_limit_already",
            ),
        ],
    )
    def test_get_wallet_balance_direct_payment_cycle(
        wallet_service: ReimbursementWalletService,
        direct_payment_cycle_based_wallet: ReimbursementWallet,
        user_for_direct_payment_cycle_based_wallet: User,
        spent_amount: int,
        pending_reimbursement_amount: int,
        scheduled_tp_with_cb_amount: int,
        scheduled_tp_without_cb_amount: int,
        cb_member_responsibility_amount: int,
        cb_employer_responsibility_amount: int,
        expected_spent_amount: int,
        expected_limit_amount: Optional[int],
        expected_pending_amount: int,
        expected_available_balance_amount: int,
        expected_current_balance_amount: int,
    ):
        # Given
        category_association = (
            direct_payment_cycle_based_wallet.get_or_create_wallet_allowed_categories[0]
        )
        limit_credits = category_association.num_cycles * NUM_CREDITS_PER_CYCLE
        # Don't let remaining go below 0
        remaining_credits = max(limit_credits - spent_amount, 0)

        cycle_credit = wallet_service.credits_repo.get_cycle_credit_by_category(
            reimbursement_wallet_id=direct_payment_cycle_based_wallet.id,
            category_id=category_association.reimbursement_request_category_id,
        )
        cycle_credit.amount = remaining_credits

        rwu = user_for_direct_payment_cycle_based_wallet.reimbursement_wallet_users[0]

        pending_reimbursement = ReimbursementRequestFactory.create(
            reimbursement_wallet_id=direct_payment_cycle_based_wallet.id,
            reimbursement_request_category_id=category_association.reimbursement_request_category_id,
            amount=1,
            cost_credit=pending_reimbursement_amount,
            state=ReimbursementRequestState.PENDING,
        )
        wallet_service.requests_repo.get_pending_reimbursements.return_value = [
            pending_reimbursement
        ]

        # Create a SCHEDULED treatment
        cb = CostBreakdownFactory.create(
            total_member_responsibility=cb_member_responsibility_amount,
            total_employer_responsibility=cb_employer_responsibility_amount,
        )
        scheduled_tp = TreatmentProcedureFactory.create(
            cost_breakdown_id=cb.id,
            reimbursement_wallet_id=direct_payment_cycle_based_wallet.id,
            reimbursement_request_category=category_association.reimbursement_request_category,
            status=TreatmentProcedureStatus.SCHEDULED,
            cost_credit=scheduled_tp_with_cb_amount,
        )
        scheduled_tp_without_cb = TreatmentProcedureFactory.create(
            cost_breakdown_id=None,
            reimbursement_wallet_id=direct_payment_cycle_based_wallet.id,
            reimbursement_request_category=category_association.reimbursement_request_category,
            status=TreatmentProcedureStatus.SCHEDULED,
            cost_credit=scheduled_tp_without_cb_amount,
        )
        wallet_service.procedures_repo.get_scheduled_procedures_and_cbs.return_value = [
            (scheduled_tp, cb),
            (scheduled_tp_without_cb, None),
        ]

        # When
        wallet_balance: WalletBalance = wallet_service.get_wallet_balance(
            wallet=direct_payment_cycle_based_wallet,
            rwu=rwu,
            include_procedures_without_cb=True,
        )

        # Then
        category_balance: CategoryBalance = wallet_balance.categories[0]
        assert wallet_balance == WalletBalance(
            id=direct_payment_cycle_based_wallet.id,
            state=WalletState.QUALIFIED,
            user_status=rwu.status,
            categories=[
                CategoryBalance(
                    id=category_association.reimbursement_request_category_id,
                    name=category_association.reimbursement_request_category.label,
                    active=True,
                    is_unlimited=False,
                    benefit_type=category_association.benefit_type,
                    currency_code=None,
                    direct_payment_category=True,
                    limit_amount=expected_limit_amount,
                    remaining_credits=remaining_credits,
                    pending_amount=expected_pending_amount,
                    spent_amount=expected_spent_amount,
                )
            ],
        )
        assert category_balance.available_balance == expected_available_balance_amount
        assert category_balance.current_balance == expected_current_balance_amount

    @staticmethod
    def test_get_wallet_balance_reimbursement_wallet_expired_plan(
        wallet_service: ReimbursementWalletService,
        basic_qualified_wallet: ReimbursementWallet,
        basic_user_for_wallet: User,
    ):
        # Given
        category_association = (
            basic_qualified_wallet.get_or_create_wallet_allowed_categories[0]
        )
        SPENT_AMOUNT = 1_000_00
        wallet_service.wallet_repo.get_reimbursed_amount_for_category.return_value = (
            SPENT_AMOUNT
        )
        category_association.reimbursement_request_category.reimbursement_plan.end_date = datetime.date.today() - datetime.timedelta(
            weeks=2
        )
        rwu = basic_user_for_wallet.reimbursement_wallet_users[0]

        # When
        wallet_balance: WalletBalance = wallet_service.get_wallet_balance(
            wallet=basic_qualified_wallet, rwu=rwu
        )

        # Then
        assert wallet_balance == WalletBalance(
            id=basic_qualified_wallet.id,
            state=WalletState.QUALIFIED,
            user_status=rwu.status,
            categories=[
                CategoryBalance(
                    id=category_association.reimbursement_request_category_id,
                    name=category_association.reimbursement_request_category.label,
                    active=False,
                    is_unlimited=False,
                    benefit_type=category_association.benefit_type,
                    currency_code="USD",
                    direct_payment_category=False,
                    limit_amount=category_association.reimbursement_request_category_maximum,
                    pending_amount=0,
                    spent_amount=SPENT_AMOUNT,
                )
            ],
        )


class TestPriorSpendCalculation:
    @staticmethod
    def test__calculate_prior_spend(
        wallet_service: ReimbursementWalletService,
        basic_qualified_wallet: ReimbursementWallet,
        basic_user_for_wallet: User,
    ):
        # Given
        category = basic_qualified_wallet.reimbursement_organization_settings.allowed_reimbursement_categories[
            0
        ]
        reimbursements = ReimbursementRequestFactory.create_batch(
            size=10,
            reimbursement_wallet_id=basic_qualified_wallet.id,
            reimbursement_request_category_id=category.reimbursement_request_category_id,
            amount=100_00,
            usd_amount=100_00,
            benefit_currency_code="USD",
        )
        wallet_service.requests_repo.get_reimbursed_reimbursements.return_value = (
            reimbursements
        )

        # When
        prior_spend = wallet_service._calculate_prior_spend(
            wallet_id=basic_qualified_wallet.id,
            category_id=category.reimbursement_request_category_id,
        )

        # Then
        assert prior_spend == {
            "benefit_currency_amount": {
                "amount": 1000_00,
                "currency_code": "USD",
            },
            "usd_amount": {
                "amount": 1000_00,
                "currency_code": "USD",
            },
        }

    @staticmethod
    def test__calculate_prior_spend_no_reimbursements(
        wallet_service: ReimbursementWalletService,
        basic_qualified_wallet: ReimbursementWallet,
        basic_user_for_wallet: User,
    ):
        # Given
        category = basic_qualified_wallet.reimbursement_organization_settings.allowed_reimbursement_categories[
            0
        ]
        wallet_service.requests_repo.get_reimbursed_reimbursements.return_value = []

        # When
        prior_spend = wallet_service._calculate_prior_spend(
            wallet_id=basic_qualified_wallet.id,
            category_id=category.reimbursement_request_category_id,
        )

        # Then
        assert prior_spend == {
            "benefit_currency_amount": {
                "amount": 0,
                "currency_code": None,
            },
            "usd_amount": {
                "amount": 0,
                "currency_code": "USD",
            },
        }

    @staticmethod
    def test__calculate_prior_spend_mixed_currencies(
        wallet_service: ReimbursementWalletService,
        basic_qualified_wallet: ReimbursementWallet,
        basic_user_for_wallet: User,
    ):
        # Given
        category = basic_qualified_wallet.reimbursement_organization_settings.allowed_reimbursement_categories[
            0
        ]
        usd_reimbursements = ReimbursementRequestFactory.create_batch(
            size=10,
            reimbursement_wallet_id=basic_qualified_wallet.id,
            reimbursement_request_category_id=category.reimbursement_request_category_id,
            amount=100_00,
            usd_amount=100_00,
            benefit_currency_code="USD",
        )
        gbp_reimbursements = ReimbursementRequestFactory.create_batch(
            size=2,
            reimbursement_wallet_id=basic_qualified_wallet.id,
            reimbursement_request_category_id=category.reimbursement_request_category_id,
            amount=100_00,
            usd_amount=90_00,
            benefit_currency_code="GBP",
        )
        wallet_service.requests_repo.get_reimbursed_reimbursements.return_value = (
            usd_reimbursements + gbp_reimbursements
        )

        # When - Then
        with pytest.raises(
            Exception, match="Mix of currencies detected when calculating prior spend"
        ):
            wallet_service._calculate_prior_spend(
                wallet_id=basic_qualified_wallet.id,
                category_id=category.reimbursement_request_category_id,
            )

    @staticmethod
    def test__calculate_prior_spend_missing_currency_code(
        wallet_service: ReimbursementWalletService,
        basic_qualified_wallet: ReimbursementWallet,
        basic_user_for_wallet: User,
    ):
        # Given
        category = basic_qualified_wallet.reimbursement_organization_settings.allowed_reimbursement_categories[
            0
        ]
        reimbursements = ReimbursementRequestFactory.create_batch(
            size=10,
            reimbursement_wallet_id=basic_qualified_wallet.id,
            reimbursement_request_category_id=category.reimbursement_request_category_id,
            amount=100_00,
            usd_amount=100_00,
            benefit_currency_code=None,
        )
        wallet_service.requests_repo.get_reimbursed_reimbursements.return_value = (
            reimbursements
        )

        # When - Then
        with pytest.raises(
            Exception, match="Missing currency code when calculating prior spend"
        ):
            wallet_service._calculate_prior_spend(
                wallet_id=basic_qualified_wallet.id,
                category_id=category.reimbursement_request_category_id,
            )

    @staticmethod
    def test_create_prior_spend_reimbursement_request(
        wallet_service: ReimbursementWalletService,
        basic_qualified_wallet: ReimbursementWallet,
        basic_user_for_wallet: User,
    ):
        # Given
        amount = 1_234_56
        source_currency: str = "USD"
        target_currency: str = "AUD"
        ros_kwargs = {
            "organization_id": basic_qualified_wallet.reimbursement_organization_settings.organization_id,
            "allowed_reimbursement_categories": [
                ("fertility", 500000, target_currency)
            ],
        }
        another_ros = ReimbursementOrganizationSettingsFactory.create(**ros_kwargs)
        category_association = another_ros.allowed_reimbursement_categories[0]
        another_wallet = ReimbursementWalletFactory.create(
            reimbursement_organization_settings=another_ros, state=WalletState.QUALIFIED
        )
        ReimbursementRequestExchangeRatesFactory.create(
            source_currency=source_currency,
            target_currency=target_currency,
            exchange_rate=Decimal("2.0"),
            trading_date=datetime.date(2024, 1, 1),
        )

        # When
        reimbursement_request = wallet_service.create_prior_spend_reimbursement_request(
            amount=amount,
            currency_code=source_currency,
            wallet=another_wallet,
            category=category_association.reimbursement_request_category,
        )

        # Then
        assert reimbursement_request.wallet == another_wallet
        assert (
            reimbursement_request.category
            == category_association.reimbursement_request_category
        )
        assert reimbursement_request.transaction_amount == amount
        assert reimbursement_request.transaction_currency_code == source_currency
        assert reimbursement_request.amount == (amount * 2)
        assert reimbursement_request.benefit_currency_code == target_currency
        assert reimbursement_request.state == ReimbursementRequestState.REIMBURSED
        assert reimbursement_request.label == "Prior Spend Adjustment"


class TestExpireWalletsForROS:
    @staticmethod
    def test_expire_wallet_and_rwus(
        wallet_service: ReimbursementWalletService,
        basic_qualified_wallet: ReimbursementWallet,
        basic_user_for_wallet: User,
    ):
        # Given
        assert basic_qualified_wallet.state == WalletState.QUALIFIED
        for rwu in basic_qualified_wallet.reimbursement_wallet_users:
            assert rwu.status == WalletUserStatus.ACTIVE

        # When
        wallet_service.expire_wallet_and_rwus(wallet=basic_qualified_wallet)

        # Then
        assert basic_qualified_wallet.state == WalletState.EXPIRED

        for rwu in basic_qualified_wallet.reimbursement_wallet_users:
            assert rwu.status == WalletUserStatus.DENIED

    @staticmethod
    def test_expire_wallets_for_ros(
        wallet_service: ReimbursementWalletService,
        basic_qualified_wallet: ReimbursementWallet,
        basic_user_for_wallet: User,
    ):
        # Given
        ros_id: int = basic_qualified_wallet.reimbursement_organization_settings_id
        assert basic_qualified_wallet.state == WalletState.QUALIFIED
        for rwu in basic_qualified_wallet.reimbursement_wallet_users:
            assert rwu.status == WalletUserStatus.ACTIVE

        wallet_service.wallet_repo.get_wallets_by_ros.return_value = [
            basic_qualified_wallet
        ]

        # When
        metadata = wallet_service.expire_wallets_for_ros(ros_id=ros_id)

        # Then
        assert basic_qualified_wallet.state == WalletState.EXPIRED

        for rwu in basic_qualified_wallet.reimbursement_wallet_users:
            assert rwu.status == WalletUserStatus.DENIED

        assert metadata[0] == {
            "wallet_id": basic_qualified_wallet.id,
            "previous_wallet_state": "QUALIFIED",
            "updated_wallet_state": "EXPIRED",
            "updated_at": mock.ANY,
        }

    @staticmethod
    def test_expire_wallets_for_ros_with_filter(
        wallet_service: ReimbursementWalletService,
        basic_qualified_wallet: ReimbursementWallet,
        basic_user_for_wallet: User,
    ):
        # Given
        ros_id: int = basic_qualified_wallet.reimbursement_organization_settings_id

        # When
        wallet_service.expire_wallets_for_ros(
            ros_id=ros_id, wallet_states={WalletState.PENDING}
        )

        # Then
        wallet_service.wallet_repo.get_wallets_by_ros.assert_called_with(
            ros_id=ros_id, wallet_states={WalletState.PENDING}
        )


class TestCopyWallet:
    @staticmethod
    def test__can_copy_from(
        wallet_service: ReimbursementWalletService,
        basic_qualified_wallet: ReimbursementWallet,
    ):
        # Given
        basic_qualified_wallet.state = WalletState.EXPIRED
        wallet_service.requests_repo.wallet_has_unresolved_reimbursements.return_value = (
            False
        )

        # When
        can_copy_from = wallet_service._can_copy_from(wallet=basic_qualified_wallet)

        # Then
        assert can_copy_from is True

    @staticmethod
    @pytest.mark.parametrize(
        argnames=("wallet_state", "has_pending"),
        argvalues=[
            (WalletState.PENDING, True),
            (WalletState.QUALIFIED, True),
            (WalletState.DISQUALIFIED, True),
            (WalletState.EXPIRED, True),
            (WalletState.RUNOUT, True),
            (WalletState.PENDING, False),
            (WalletState.QUALIFIED, False),
            (WalletState.DISQUALIFIED, False),
            (WalletState.RUNOUT, False),
        ],
    )
    def test__can_copy_from_raises_exception(
        wallet_service: ReimbursementWalletService,
        basic_qualified_wallet: ReimbursementWallet,
        wallet_state: WalletState,
        has_pending: bool,
    ):
        # Given
        basic_qualified_wallet.state = wallet_state
        wallet_service.requests_repo.wallet_has_unresolved_reimbursements.return_value = (
            has_pending
        )

        # When - Then
        with pytest.raises(CopyWalletValidationError):
            wallet_service._can_copy_from(wallet=basic_qualified_wallet)

    @staticmethod
    def test__can_copy_from_raises_exception_for_multiple_categories(
        wallet_service: ReimbursementWalletService,
        basic_qualified_wallet: ReimbursementWallet,
    ):
        # Given
        basic_qualified_wallet.state = WalletState.EXPIRED
        wallet_service.requests_repo.wallet_has_unresolved_reimbursements.return_value = (
            False
        )
        category = ReimbursementRequestCategoryFactory.create(label="another_category")
        ReimbursementOrgSettingCategoryAssociationFactory.create(
            reimbursement_organization_settings_id=basic_qualified_wallet.reimbursement_organization_settings_id,
            reimbursement_request_category_id=category.id,
            reimbursement_request_category_maximum=20000,
            currency_code="USD",
            benefit_type=BenefitTypes.CURRENCY,
        )

        # When - Then
        with pytest.raises(
            CopyWalletValidationError,
            match="Source ROS does not have a single category",
        ):
            wallet_service._can_copy_from(wallet=basic_qualified_wallet)

    @staticmethod
    def test__can_copy_to(
        wallet_service: ReimbursementWalletService,
        basic_qualified_wallet: ReimbursementWallet,
    ):
        # Given
        ros_kwargs = {
            "organization_id": basic_qualified_wallet.reimbursement_organization_settings.organization_id
        }

        another_ros = ReimbursementOrganizationSettingsFactory.create(**ros_kwargs)

        # When
        can_copy_to = wallet_service._can_copy_to(
            wallet=basic_qualified_wallet, ros=another_ros
        )

        # Then
        assert can_copy_to is True

    @staticmethod
    @pytest.mark.parametrize(
        argnames=("same_org", "multiple_categories"),
        argvalues=[
            (False, False),
            (True, True),
            (False, True),
        ],
    )
    def test__can_copy_to_raises_exception(
        wallet_service: ReimbursementWalletService,
        basic_qualified_wallet: ReimbursementWallet,
        same_org: bool,
        multiple_categories: bool,
    ):
        # Given
        ros_kwargs = {}

        if same_org:
            ros_kwargs[
                "organization_id"
            ] = (
                basic_qualified_wallet.reimbursement_organization_settings.organization_id
            )

        if multiple_categories:
            ros_kwargs["allowed_reimbursement_categories"] = [
                ("adoption", 500000, "USD"),
                ("surrogacy", 500000, "GBP"),
            ]

        another_ros = ReimbursementOrganizationSettingsFactory.create(**ros_kwargs)

        # When
        with pytest.raises(CopyWalletValidationError):
            wallet_service._can_copy_to(wallet=basic_qualified_wallet, ros=another_ros)

    @staticmethod
    def test__copy_wallet_and_adjacent_objs(
        wallet_service: ReimbursementWalletService,
        basic_qualified_wallet: ReimbursementWallet,
    ):
        # Given
        OrganizationEmployeeDependentFactory.create(
            reimbursement_wallet_id=basic_qualified_wallet.id,
        )
        target_ros = ReimbursementOrganizationSettingsFactory.create(
            organization_id=basic_qualified_wallet.reimbursement_organization_settings.organization_id
        )

        # When
        copied_objs: dict = wallet_service._copy_wallet_and_adjacent_objs(
            source=basic_qualified_wallet, target=target_ros
        )
        new_wallet: ReimbursementWallet = copied_objs["wallet"]
        new_rwus: list[ReimbursementWalletUsers] = copied_objs["rwus"]
        new_oeds: list[OrganizationEmployeeDependent] = copied_objs["oeds"]

        # Then
        # Old objects
        for rwu in basic_qualified_wallet.reimbursement_wallet_users:
            assert rwu.channel_id is None
        # Updated fields
        assert new_wallet.state == WalletState.PENDING
        assert new_wallet.reimbursement_organization_settings_id == target_ros.id
        assert (
            f"\nDuplicated from wallet ID: {str(basic_qualified_wallet.id)}"
            in new_wallet.note
        )
        # Copied fields
        assert new_wallet.user_id == basic_qualified_wallet.user_id
        assert (
            new_wallet.reimbursement_method
            == basic_qualified_wallet.reimbursement_method
        )
        assert (
            new_wallet.primary_expense_type
            == basic_qualified_wallet.primary_expense_type
        )
        assert new_wallet.taxation_status == basic_qualified_wallet.taxation_status
        assert (
            new_wallet.initial_eligibility_member_id
            == basic_qualified_wallet.initial_eligibility_member_id
        )
        assert (
            new_wallet.initial_eligibility_verification_id
            == basic_qualified_wallet.initial_eligibility_verification_id
        )
        assert (
            new_wallet.initial_eligibility_member_2_id
            == basic_qualified_wallet.initial_eligibility_member_2_id
        )
        assert (
            new_wallet.initial_eligibility_member_2_version
            == basic_qualified_wallet.initial_eligibility_member_2_version
        )
        assert (
            new_wallet.initial_eligibility_verification_2_id
            == basic_qualified_wallet.initial_eligibility_verification_2_id
        )
        # Null fields
        assert new_wallet.reimbursement_wallet_debit_card_id is None
        assert new_wallet.payments_customer_id is None
        assert new_wallet.alegeus_id is None

        for idx, rwu in enumerate(basic_qualified_wallet.reimbursement_wallet_users):
            # Updated fields
            assert new_rwus[idx].status == WalletUserStatus.ACTIVE
            assert new_rwus[idx].reimbursement_wallet_id == new_wallet.id
            # Copied fields
            assert new_rwus[idx].user_id == rwu.user_id
            assert new_rwus[idx].zendesk_ticket_id == rwu.zendesk_ticket_id
            assert new_rwus[idx].channel_id == rwu.channel_id
            assert new_rwus[idx].type == rwu.type
            # Null fields
            assert new_rwus[idx].alegeus_dependent_id is None

        for idx, oed in enumerate(basic_qualified_wallet.authorized_users):
            # Updated fields
            assert new_oeds[idx].reimbursement_wallet_id == new_wallet.id
            assert new_oeds[idx].alegeus_dependent_id is not None
            # Copied fields
            assert new_oeds[idx].first_name == oed.first_name
            assert new_oeds[idx].last_name == oed.last_name
            assert new_oeds[idx].middle_name == oed.middle_name

    @staticmethod
    def test_copy_wallet_with_prior_spend(
        wallet_service: ReimbursementWalletService,
        basic_qualified_wallet: ReimbursementWallet,
        basic_user_for_wallet: User,
    ):
        # Given
        basic_qualified_wallet.state = WalletState.EXPIRED
        wallet_service.requests_repo.wallet_has_unresolved_reimbursements.return_value = (
            False
        )
        source_currency: str = "USD"
        target_currency: str = "AUD"
        ros_kwargs = {
            "organization_id": basic_qualified_wallet.reimbursement_organization_settings.organization_id,
            "allowed_reimbursement_categories": [
                ("fertility", 500000, target_currency)
            ],
        }
        another_ros = ReimbursementOrganizationSettingsFactory.create(**ros_kwargs)
        ReimbursementRequestExchangeRatesFactory.create(
            source_currency=source_currency,
            target_currency=target_currency,
            exchange_rate=Decimal("2.0"),
            trading_date=datetime.date(2024, 1, 1),
        )

        # When
        with mock.patch(
            "wallet.services.reimbursement_wallet.ReimbursementWalletService._calculate_prior_spend"
        ) as mock__calculate_prior_spend:
            mock__calculate_prior_spend.return_value = {
                "benefit_currency_amount": {
                    "amount": 10_00,
                    "currency_code": "USD",
                },
                "usd_amount": {
                    "amount": 10_00,
                    "currency_code": "USD",
                },
            }

            created_objs: dict = wallet_service.copy_wallet(
                source=basic_qualified_wallet,
                target=another_ros,
                create_prior_spend_entry=True,
            )

        # Then
        assert created_objs["wallet"]
        assert created_objs["prior_spend_entry"]

    @staticmethod
    def test_copy_wallet_with_prior_spend_but_amount_is_zero(
        wallet_service: ReimbursementWalletService,
        basic_qualified_wallet: ReimbursementWallet,
        basic_user_for_wallet: User,
    ):
        # Given
        basic_qualified_wallet.state = WalletState.EXPIRED
        wallet_service.requests_repo.wallet_has_unresolved_reimbursements.return_value = (
            False
        )
        source_currency: str = "USD"
        target_currency: str = "AUD"
        ros_kwargs = {
            "organization_id": basic_qualified_wallet.reimbursement_organization_settings.organization_id,
            "allowed_reimbursement_categories": [
                ("fertility", 500000, target_currency)
            ],
        }
        another_ros = ReimbursementOrganizationSettingsFactory.create(**ros_kwargs)
        ReimbursementRequestExchangeRatesFactory.create(
            source_currency=source_currency,
            target_currency=target_currency,
            exchange_rate=Decimal("2.0"),
            trading_date=datetime.date(2024, 1, 1),
        )

        # When
        with mock.patch(
            "wallet.services.reimbursement_wallet.ReimbursementWalletService._calculate_prior_spend"
        ) as mock__calculate_prior_spend:
            mock__calculate_prior_spend.return_value = {
                "benefit_currency_amount": {
                    "amount": 0,
                    "currency_code": None,
                },
                "usd_amount": {
                    "amount": 0,
                    "currency_code": "USD",
                },
            }

            created_objs: dict = wallet_service.copy_wallet(
                source=basic_qualified_wallet,
                target=another_ros,
                create_prior_spend_entry=True,
            )

        # Then
        assert created_objs["wallet"]
        assert not created_objs["prior_spend_entry"]

    @staticmethod
    def test_copy_wallet_without_prior_spend(
        wallet_service: ReimbursementWalletService,
        basic_qualified_wallet: ReimbursementWallet,
        basic_user_for_wallet: User,
    ):
        # Given
        basic_qualified_wallet.state = WalletState.EXPIRED
        wallet_service.requests_repo.wallet_has_unresolved_reimbursements.return_value = (
            False
        )
        source_currency: str = "USD"
        target_currency: str = "AUD"
        ros_kwargs = {
            "organization_id": basic_qualified_wallet.reimbursement_organization_settings.organization_id,
            "allowed_reimbursement_categories": [
                ("fertility", 500000, target_currency)
            ],
        }
        another_ros = ReimbursementOrganizationSettingsFactory.create(**ros_kwargs)
        ReimbursementRequestExchangeRatesFactory.create(
            source_currency=source_currency,
            target_currency=target_currency,
            exchange_rate=Decimal("2.0"),
            trading_date=datetime.date(2024, 1, 1),
        )

        # When
        created_objs: dict = wallet_service.copy_wallet(
            source=basic_qualified_wallet,
            target=another_ros,
            create_prior_spend_entry=False,
        )

        # Then
        assert created_objs["wallet"]
        assert not created_objs["prior_spend_entry"]

    @staticmethod
    def test_copy_and_persist_wallet_objs_calls_copy_wallet(
        wallet_service: ReimbursementWalletService,
        basic_qualified_wallet: ReimbursementWallet,
        basic_user_for_wallet: User,
    ):
        # Given
        another_ros = ReimbursementOrganizationSettingsFactory.create()

        # When
        with mock.patch(
            "wallet.services.reimbursement_wallet.ReimbursementWalletService.copy_wallet"
        ) as mock_copy_wallet:
            wallet_service.copy_and_persist_wallet_objs(
                source=basic_qualified_wallet,
                target=another_ros,
                create_prior_spend_entry=True,
            )

        # Then
        mock_copy_wallet.assert_called_with(
            source=basic_qualified_wallet,
            target=another_ros,
            create_prior_spend_entry=True,
        )

    @staticmethod
    def test_copy_and_persist_wallet_objs_committed(
        wallet_service: ReimbursementWalletService,
        basic_qualified_wallet: ReimbursementWallet,
        basic_user_for_wallet: User,
    ):
        # Given
        another_ros = ReimbursementOrganizationSettingsFactory.create()

        # When
        with mock.patch(
            "wallet.services.reimbursement_wallet.ReimbursementWalletService.copy_wallet"
        ):
            wallet_service.copy_and_persist_wallet_objs(
                source=basic_qualified_wallet,
                target=another_ros,
                create_prior_spend_entry=True,
            )

        # Then
        wallet_service.wallet_repo.session.commit.assert_called()

    @staticmethod
    def test_copy_and_persist_wallet_objs_rollback(
        wallet_service: ReimbursementWalletService,
        basic_qualified_wallet: ReimbursementWallet,
        basic_user_for_wallet: User,
    ):
        # Given
        another_ros = ReimbursementOrganizationSettingsFactory.create()

        # When
        with mock.patch(
            "wallet.services.reimbursement_wallet.ReimbursementWalletService.copy_wallet"
        ) as mock_copy_wallet, pytest.raises(Exception):
            mock_copy_wallet.side_effect = Exception("Ohhh no!")

            wallet_service.copy_and_persist_wallet_objs(
                source=basic_qualified_wallet,
                target=another_ros,
                create_prior_spend_entry=True,
            )

        # Then
        wallet_service.wallet_repo.session.rollback.assert_called()


class TestAlegeusLTMCalculation:
    @staticmethod
    def test_calculate_usd_ltm_for_year(
        wallet_service: ReimbursementWalletService,
        basic_qualified_wallet: ReimbursementWallet,
        basic_user_for_wallet: User,
        currency_service: CurrencyService,
    ):
        # Given
        category_association = (
            basic_qualified_wallet.get_or_create_wallet_allowed_categories[0]
        )
        category_association.currency_code = "AUD"
        prior_spend_usd_amount = 10_000_00
        remaining_usd_amount = 12_000_000

        # When
        with mock.patch(
            "wallet.services.reimbursement_wallet.ReimbursementWalletService._calculate_prior_spend"
        ) as mock_calculate_prior_spend, mock.patch(
            "wallet.services.currency.CurrencyService.convert"
        ) as mock_convert:
            mock_calculate_prior_spend.return_value = {
                "benefit_currency_amount": {
                    "amount": 20_000_00,
                    "currency_code": "AUD",
                },
                "usd_amount": {
                    "amount": prior_spend_usd_amount,
                    "currency_code": "USD",
                },
            }
            mock_convert.return_value = remaining_usd_amount, None

            updated_usd_ltm = wallet_service.calculate_usd_ltm_for_year(
                year=2025,
                wallet=basic_qualified_wallet,
                category_association=category_association,
                currency_service=currency_service,
            )

        # Then
        assert updated_usd_ltm == prior_spend_usd_amount + remaining_usd_amount

    @staticmethod
    def test_calculate_usd_ltm_for_year_no_prior_spend(
        wallet_service: ReimbursementWalletService,
        basic_qualified_wallet: ReimbursementWallet,
        basic_user_for_wallet: User,
        currency_service: CurrencyService,
    ):
        # Given
        category_association = (
            basic_qualified_wallet.get_or_create_wallet_allowed_categories[0]
        )
        category_association.currency_code = "AUD"
        remaining_usd_amount = 12_000_000

        # When
        with mock.patch(
            "wallet.services.reimbursement_wallet.ReimbursementWalletService._calculate_prior_spend"
        ) as mock_calculate_prior_spend, mock.patch(
            "wallet.services.currency.CurrencyService.convert"
        ) as mock_convert:
            mock_calculate_prior_spend.return_value = {
                "benefit_currency_amount": {
                    "amount": 0,
                    "currency_code": None,
                },
                "usd_amount": {
                    "amount": 0,
                    "currency_code": DEFAULT_CURRENCY_CODE,
                },
            }
            mock_convert.return_value = remaining_usd_amount, None

            updated_usd_ltm = wallet_service.calculate_usd_ltm_for_year(
                year=2025,
                wallet=basic_qualified_wallet,
                category_association=category_association,
                currency_service=currency_service,
            )

        # Then
        assert updated_usd_ltm == remaining_usd_amount

    @staticmethod
    def test_calculate_usd_ltm_for_year_calls_correct_args(
        wallet_service: ReimbursementWalletService,
        basic_qualified_wallet: ReimbursementWallet,
        basic_user_for_wallet: User,
        currency_service: CurrencyService,
    ):
        # Given
        category_association = (
            basic_qualified_wallet.get_or_create_wallet_allowed_categories[0]
        )
        category_association.currency_code = "AUD"
        prior_spend_amount = 20_000_00
        prior_spend_usd_amount = 10_000_00
        remaining_usd_amount = 12_000_000
        year: int = 2025
        as_of_date = datetime.date(year=year, month=1, day=1)

        # When
        with mock.patch(
            "wallet.services.reimbursement_wallet.ReimbursementWalletService._calculate_prior_spend"
        ) as mock_calculate_prior_spend, mock.patch(
            "wallet.services.currency.CurrencyService.convert"
        ) as mock_convert:
            mock_calculate_prior_spend.return_value = {
                "benefit_currency_amount": {
                    "amount": 20_000_00,
                    "currency_code": "AUD",
                },
                "usd_amount": {
                    "amount": prior_spend_usd_amount,
                    "currency_code": "USD",
                },
            }
            mock_convert.return_value = remaining_usd_amount, None

            wallet_service.calculate_usd_ltm_for_year(
                year=year,
                wallet=basic_qualified_wallet,
                category_association=category_association,
                currency_service=currency_service,
            )

        # Then
        mock_calculate_prior_spend.assert_called_with(
            wallet_id=basic_qualified_wallet.id,
            category_id=category_association.reimbursement_request_category_id,
            end_date=as_of_date,
        )

        mock_convert.assert_called_with(
            amount=category_association.reimbursement_request_category_maximum
            - prior_spend_amount,
            source_currency_code=category_association.currency_code,
            target_currency_code=DEFAULT_CURRENCY_CODE,
            as_of_date=as_of_date,
        )

    @staticmethod
    def test_calculate_usd_ltm_for_year_currency_mismatch(
        wallet_service: ReimbursementWalletService,
        basic_qualified_wallet: ReimbursementWallet,
        basic_user_for_wallet: User,
        currency_service: CurrencyService,
    ):
        # Given
        category_association = (
            basic_qualified_wallet.get_or_create_wallet_allowed_categories[0]
        )
        category_association.currency_code = "AUD"
        prior_spend_usd_amount = 10_000_00
        remaining_usd_amount = 12_000_000

        # When
        with mock.patch(
            "wallet.services.reimbursement_wallet.ReimbursementWalletService._calculate_prior_spend"
        ) as mock_calculate_prior_spend, mock.patch(
            "wallet.services.currency.CurrencyService.convert"
        ) as mock_convert, pytest.raises(
            Exception, match="Prior spend currency different from LTM currency"
        ):
            mock_calculate_prior_spend.return_value = {
                "benefit_currency_amount": {
                    "amount": 20_000_00,
                    "currency_code": "GBP",
                },
                "usd_amount": {
                    "amount": prior_spend_usd_amount,
                    "currency_code": "USD",
                },
            }
            mock_convert.return_value = remaining_usd_amount, None

            wallet_service.calculate_usd_ltm_for_year(
                year=2025,
                wallet=basic_qualified_wallet,
                category_association=category_association,
                currency_service=currency_service,
            )

    @staticmethod
    @pytest.mark.parametrize(
        argnames=("benefit_type", "currency_code", "amount"),
        argvalues=[
            (BenefitTypes.CYCLE, None, None),
            (BenefitTypes.CURRENCY, None, None),
            (BenefitTypes.CURRENCY, "USD", None),
            (BenefitTypes.CURRENCY, None, 10_000_00),
        ],
    )
    def test_calculate_usd_ltm_for_year_incompatible_category_association(
        wallet_service: ReimbursementWalletService,
        basic_qualified_wallet: ReimbursementWallet,
        basic_user_for_wallet: User,
        currency_service: CurrencyService,
        benefit_type: str,
        currency_code: str,
        amount: int,
    ):
        # Given
        category_association = (
            basic_qualified_wallet.get_or_create_wallet_allowed_categories[0]
        )
        category_association.benefit_type = benefit_type
        category_association.currency_code = currency_code
        category_association.reimbursement_request_category_maximum = amount

        # When
        with pytest.raises(
            Exception, match="Incompatible category association configuration"
        ):
            wallet_service.calculate_usd_ltm_for_year(
                year=2025,
                wallet=basic_qualified_wallet,
                category_association=category_association,
                currency_service=currency_service,
            )

    @staticmethod
    def test_calculate_ltm_updates(
        wallet_service: ReimbursementWalletService,
        basic_qualified_wallet: ReimbursementWallet,
        basic_user_for_wallet: User,
        currency_service: CurrencyService,
    ):
        # Given
        category_association = (
            basic_qualified_wallet.get_or_create_wallet_allowed_categories[0]
        )
        category_association.benefit_type = BenefitTypes.CURRENCY
        category_association.currency_code = "GBP"
        category_association.reimbursement_request_category_maximum = 10_000_00

        wallet_service.wallet_repo.get_non_usd_wallets.return_value = [
            basic_qualified_wallet
        ]
        currency_service.currency_code_repo.get_minor_unit.return_value = 2

        # When
        with mock.patch(
            "wallet.services.reimbursement_wallet.ReimbursementWalletService.calculate_usd_ltm_for_year"
        ) as mock_calculate_usd_ltm_for_year:
            mock_calculate_usd_ltm_for_year.return_value = 123_456_78
            updates = wallet_service.calculate_ltm_updates(
                year=2025, currency_service=currency_service
            )

        # Then
        plan = category_association.reimbursement_request_category.reimbursement_plan
        assert len(updates) == 1
        assert updates[0] == {
            "usd_amount": Decimal("123456.78"),
            "employee_id": basic_qualified_wallet.alegeus_id,
            "employer_id": basic_qualified_wallet.reimbursement_organization_settings.organization.alegeus_employer_id,
            "account_type": plan.reimbursement_account_type.alegeus_account_type,
        }
