import csv
from unittest import mock
from unittest.mock import Mock, patch

import pytest
import sqlalchemy

from direct_payment.pharmacy.constants import (
    ENABLE_UNLIMITED_BENEFITS_FOR_SMP,
    SMPMemberType,
)
from direct_payment.pharmacy.tasks.libs.smp_eligibility_file import (
    HEADERS,
    _create_eligibility_file,
    _get_smp_eligibility_member_type,
    ship_eligibility_file_to_smp,
)
from pytests.factories import MemberProfileFactory
from wallet.models.constants import (
    ReimbursementRequestExpenseTypes,
    ReimbursementRequestState,
    WalletState,
    WalletUserStatus,
    WalletUserType,
)
from wallet.pytests.factories import (
    MemberHealthPlanFactory,
    ReimbursementOrganizationSettingsFactory,
    ReimbursementRequestCategoryExpenseTypesFactory,
    ReimbursementRequestFactory,
    ReimbursementWalletUsersFactory,
)

# Import of fixtures from other fixture scopes to avoid duplication
from wallet.pytests.fixtures import (  # noqa: F401
    unlimited_direct_payment_wallet,
    user_for_unlimited_direct_payment_wallet,
    wallet_test_helper,
)
from wallet.services.reimbursement_wallet import ReimbursementWalletService
from wallet.utils.annual_questionnaire.utils import HDHPCheckResults


@pytest.fixture
def smp_user(wallet, enterprise_user):
    ReimbursementWalletUsersFactory.create(
        user_id=enterprise_user.id,
        reimbursement_wallet_id=wallet.id,
        status=WalletUserStatus.ACTIVE,
        type=WalletUserType.EMPLOYEE,
    )
    MemberHealthPlanFactory.create(
        reimbursement_wallet=wallet, member_id=enterprise_user.id
    )
    return enterprise_user


def assert_empty_file(buffer):
    buffer.seek(0)
    reader = csv.reader(buffer)
    rows = [row for row in reader]
    assert rows[0] == HEADERS
    assert len(rows) == 1


class TestCreateEligibilityFile:
    @pytest.mark.parametrize(
        argnames="enable_unlimited,rx_enabled,expected_member_type",
        argvalues=[
            (False, True, SMPMemberType.GOLD.value),
            (False, False, SMPMemberType.GOLD_REIMBURSEMENT.value),
            (True, True, SMPMemberType.GOLD.value),
            (True, False, SMPMemberType.GOLD_REIMBURSEMENT.value),
        ],
    )
    def test_has_wallet_balance(
        self,
        enable_unlimited,
        rx_enabled,
        expected_member_type,
        wallet,
        smp_user,
        ff_test_data,
    ):
        ff_test_data.update(
            ff_test_data.flag(ENABLE_UNLIMITED_BENEFITS_FOR_SMP).variations(
                enable_unlimited
            )
        )
        wallet.reimbursement_organization_settings.rx_direct_payment_enabled = (
            rx_enabled
        )
        buffer = _create_eligibility_file()
        buffer.seek(0)
        reader = csv.reader(buffer)
        rows = [row for row in reader]
        assert rows[0] == HEADERS
        assert (
            ",".join(rows[1])
            == f"{smp_user.first_name},{smp_user.last_name},2000-01-01,{wallet.reimbursement_wallet_benefit.maven_benefit_id},{wallet.reimbursement_organization_settings.organization.name},{expected_member_type},{smp_user.member_benefit.benefit_id}"
        )

    @pytest.mark.parametrize(
        argnames="enable_unlimited",
        argvalues=[True, False],
    )
    def test_no_wallet_balance_currency(
        self, enable_unlimited, wallet, smp_user, ff_test_data
    ):
        ff_test_data.update(
            ff_test_data.flag(ENABLE_UNLIMITED_BENEFITS_FOR_SMP).variations(
                enable_unlimited
            )
        )
        wallet.reimbursement_organization_settings.rx_direct_payment_enabled = True

        category_associations = (
            wallet.reimbursement_organization_settings.allowed_reimbursement_categories
        )
        category = category_associations[0].reimbursement_request_category
        ReimbursementRequestFactory.create(
            wallet=wallet,
            category=category,
            amount=5000,
            state=ReimbursementRequestState.REIMBURSED,
        )
        buffer = _create_eligibility_file()
        buffer.seek(0)
        reader = csv.reader(buffer)
        rows = [row for row in reader]
        assert rows[0] == HEADERS
        assert (
            ",".join(rows[1])
            == f"{smp_user.first_name},{smp_user.last_name},2000-01-01,{wallet.reimbursement_wallet_benefit.maven_benefit_id},{wallet.reimbursement_organization_settings.organization.name},{SMPMemberType.GOLD_X.value},{smp_user.member_benefit.benefit_id}"
        )

    @pytest.mark.parametrize(
        argnames="enable_unlimited",
        argvalues=[True, False],
    )
    def test_no_wallet_balance_cycles(
        self, enable_unlimited, wallet_cycle_based, enterprise_user, ff_test_data
    ):
        ff_test_data.update(
            ff_test_data.flag(ENABLE_UNLIMITED_BENEFITS_FOR_SMP).variations(
                enable_unlimited
            )
        )

        wallet_cycle_based.reimbursement_organization_settings.rx_direct_payment_enabled = (
            True
        )
        wallet_cycle_based.cycle_credits[0].amount = 0

        buffer = _create_eligibility_file()
        buffer.seek(0)
        reader = csv.reader(buffer)
        rows = [row for row in reader]
        assert rows[0] == HEADERS
        assert (
            ",".join(rows[1])
            == f"{enterprise_user.first_name},{enterprise_user.last_name},,{wallet_cycle_based.reimbursement_wallet_benefit.maven_benefit_id},{wallet_cycle_based.reimbursement_organization_settings.organization.name},{SMPMemberType.GOLD_X.value},{enterprise_user.member_benefit.benefit_id}"
        )

    def test_file_name_with_quotes(self, wallet, smp_user):
        smp_user.first_name = 'first "name"'
        smp_user.last_name = 'last "name"'
        wallet.reimbursement_organization_settings.rx_direct_payment_enabled = True
        buffer = _create_eligibility_file()
        buffer.seek(0)
        reader = csv.reader(buffer)
        rows = [row for row in reader]
        assert rows[0] == HEADERS
        assert (
            ",".join(rows[1])
            == f"first name,last name,2000-01-01,{wallet.reimbursement_wallet_benefit.maven_benefit_id},{wallet.reimbursement_organization_settings.organization.name},{SMPMemberType.GOLD.value},{smp_user.member_benefit.benefit_id}"
        )

    def test_no_health_profile(self, wallet, smp_user):
        smp_user.health_profile = None
        wallet.reimbursement_organization_settings.rx_direct_payment_enabled = True
        buffer = _create_eligibility_file()
        buffer.seek(0)
        reader = csv.reader(buffer)
        rows = [row for row in reader]
        assert rows[0] == HEADERS
        assert (
            ",".join(rows[1])
            == f"{smp_user.first_name},{smp_user.last_name},,{wallet.reimbursement_wallet_benefit.maven_benefit_id},{wallet.reimbursement_organization_settings.organization.name},{SMPMemberType.GOLD.value},{smp_user.member_benefit.benefit_id}"
        )

    @pytest.mark.parametrize(
        argnames="rx_enabled,deductible_accumulation_enabled,hdhp_status,expected_member_type",
        argvalues=[
            (True, True, None, SMPMemberType.GOLD_X_NO_HEALTH_PLAN.value),
            (
                True,
                False,
                HDHPCheckResults.HDHP_YES,
                SMPMemberType.GOLD_X_NO_HEALTH_PLAN.value,
            ),
            (True, False, HDHPCheckResults.HDHP_NO, SMPMemberType.GOLD.value),
            (True, False, HDHPCheckResults.HDHP_UNKNOWN, SMPMemberType.GOLD.value),
            (True, False, None, SMPMemberType.GOLD.value),
            (False, True, None, SMPMemberType.GOLD_REIMBURSEMENT.value),
        ],
    )
    def test_no_health_plan(
        self,
        wallet,
        enterprise_user,
        rx_enabled,
        deductible_accumulation_enabled,
        hdhp_status,
        expected_member_type,
    ):
        ReimbursementWalletUsersFactory.create(
            user_id=enterprise_user.id,
            reimbursement_wallet_id=wallet.id,
            status=WalletUserStatus.ACTIVE,
            type=WalletUserType.EMPLOYEE,
        )
        wallet.reimbursement_organization_settings.rx_direct_payment_enabled = (
            rx_enabled
        )
        wallet.reimbursement_organization_settings.deductible_accumulation_enabled = (
            deductible_accumulation_enabled
        )

        with mock.patch(
            "direct_payment.pharmacy.tasks.libs.smp_eligibility_file.questionnaire_utils.check_if_is_hdhp",
            return_value=hdhp_status,
        ):
            buffer = _create_eligibility_file()
            buffer.seek(0)
            reader = csv.reader(buffer)
            rows = [row for row in reader]
            assert rows[0] == HEADERS
            assert (
                ",".join(rows[1])
                == f"{enterprise_user.first_name},{enterprise_user.last_name},2000-01-01,{wallet.reimbursement_wallet_benefit.maven_benefit_id},{wallet.reimbursement_organization_settings.organization.name},{expected_member_type},{enterprise_user.member_benefit.benefit_id}"
            )

    def test_inactive_user(self, wallet, enterprise_user):
        ReimbursementWalletUsersFactory.create(
            user_id=enterprise_user.id,
            reimbursement_wallet_id=wallet.id,
            status=WalletUserStatus.DENIED,
            type=WalletUserType.EMPLOYEE,
        )
        wallet.reimbursement_organization_settings.rx_direct_payment_enabled = True
        buffer = _create_eligibility_file()
        assert_empty_file(buffer)

    @pytest.mark.parametrize(
        argnames="wallet_state",
        argvalues=[
            WalletState.DISQUALIFIED,
            WalletState.EXPIRED,
            WalletState.PENDING,
            WalletState.RUNOUT,
        ],
    )
    def test_wallet_ineligible(self, wallet, smp_user, wallet_state):
        wallet.state = wallet_state
        buffer = _create_eligibility_file()
        assert_empty_file(buffer)

    def test_non_us_member(self, wallet, smp_user):
        MemberProfileFactory.create(user=smp_user, country_code="UK")
        wallet.reimbursement_organization_settings.rx_direct_payment_enabled = True
        buffer = _create_eligibility_file()
        assert_empty_file(buffer)

    def test_non_mmb_wallet_primary_expense_type(self, wallet, smp_user):
        wallet.primary_expense_type = ReimbursementRequestExpenseTypes.MATERNITY
        buffer = _create_eligibility_file()
        assert_empty_file(buffer)

    @pytest.mark.parametrize(
        argnames="enable_unlimited",
        argvalues=[True, False],
    )
    def test_no_direct_payment_category(
        self, enable_unlimited, wallet, smp_user, ff_test_data
    ):
        ff_test_data.update(
            ff_test_data.flag(ENABLE_UNLIMITED_BENEFITS_FOR_SMP).variations(
                enable_unlimited
            )
        )

        org_settings = ReimbursementOrganizationSettingsFactory(
            organization_id=smp_user.organization.id,
            rx_direct_payment_enabled=True,
            direct_payment_enabled=True,
        )
        wallet.reimbursement_organization_settings = org_settings
        category_association = (
            wallet.reimbursement_organization_settings.allowed_reimbursement_categories[
                0
            ]
        )
        request_category = category_association.reimbursement_request_category
        ReimbursementRequestCategoryExpenseTypesFactory.create(
            reimbursement_request_category=request_category,
            expense_type=ReimbursementRequestExpenseTypes.MATERNITY,
        )

        buffer = _create_eligibility_file()
        assert_empty_file(buffer)

    def test_has_user_benefit_id(self, wallet, smp_user, ff_test_data):
        wallet.reimbursement_organization_settings.rx_direct_payment_enabled = True
        HEADERS.append("User_Benefit_ID")
        buffer = _create_eligibility_file()
        buffer.seek(0)
        reader = csv.reader(buffer)
        rows = [row for row in reader]
        assert rows[0] == HEADERS
        assert (
            ",".join(rows[1])
            == f"{smp_user.first_name},{smp_user.last_name},2000-01-01,{wallet.reimbursement_wallet_benefit.maven_benefit_id},{wallet.reimbursement_organization_settings.organization.name},{SMPMemberType.GOLD.value},{smp_user.member_benefit.benefit_id}"
        )

    def test_member_benefit_repository_exception(self, wallet, smp_user):
        wallet.reimbursement_organization_settings.rx_direct_payment_enabled = True

        with mock.patch(
            "direct_payment.pharmacy.tasks.libs.smp_eligibility_file.MemberBenefitRepository.get_by_user_id",
            side_effect=sqlalchemy.orm.exc.NoResultFound("Database error"),
        ):
            buffer = _create_eligibility_file()
            buffer.seek(0)
            reader = csv.reader(buffer)
            rows = [row for row in reader]
            assert rows[0] == HEADERS
            assert len(rows) == 1  # Only headers should be present


class TestShipEligibilityFile:
    def test_ship_eligibility_file_gcs_path(
        self, smp_gcs_ff_enabled, wallet, smp_user, mock_gcs_client
    ):
        # Given
        smp_gcs_ff_enabled(True)
        wallet.reimbursement_organization_settings.rx_direct_payment_enabled = True

        with mock.patch(
            "direct_payment.pharmacy.tasks.libs.smp_eligibility_file.PharmacyFileHandler"
        ) as mock_handler:
            mock_instance = mock_handler.return_value
            mock_instance.upload_eligibility_file.return_value = True
            # When
            result = ship_eligibility_file_to_smp()
            # Then
            assert result is True
            mock_instance.upload_eligibility_file.assert_called_once()

    def test_ship_eligibility_file_gcs_error(
        self, smp_gcs_ff_enabled, wallet, smp_user, mock_gcs_client
    ):
        smp_gcs_ff_enabled(True)
        wallet.reimbursement_organization_settings.rx_direct_payment_enabled = True

        with mock.patch(
            "direct_payment.pharmacy.tasks.libs.smp_eligibility_file.PharmacyFileHandler"
        ) as mock_handler:
            mock_instance = mock_handler.return_value
            mock_instance.upload_eligibility_file.return_value = False  # Upload failed

            # Should return False but not raise
            result = ship_eligibility_file_to_smp()
            assert result is False
            mock_instance.upload_eligibility_file.assert_called_once()

    def test_ship_eligibility_file_gcs_raises(
        self, smp_gcs_ff_enabled, wallet, smp_user, mock_gcs_client
    ):
        smp_gcs_ff_enabled(True)
        wallet.reimbursement_organization_settings.rx_direct_payment_enabled = True

        with mock.patch(
            "direct_payment.pharmacy.tasks.libs.smp_eligibility_file.PharmacyFileHandler"
        ) as mock_handler:
            mock_instance = mock_handler.return_value
            mock_instance.upload_eligibility_file.return_value = False

            result = ship_eligibility_file_to_smp()
            assert result is False
            mock_instance.upload_eligibility_file.assert_called_once()

    def test_ship_eligibility_file_sftp(
        self, smp_gcs_ff_enabled, mock_pharmacy_file_handler, wallet, smp_user
    ):
        # Given
        smp_gcs_ff_enabled(False)
        wallet.reimbursement_organization_settings.rx_direct_payment_enabled = True

        with patch("paramiko.SSHClient") as mock_ssh:
            mock_ftp = mock_ssh.return_value.open_sftp.return_value = Mock()
            mock_ftp.listdir.return_value = []

            # When
            result = ship_eligibility_file_to_smp()

            # Then
            assert result is True
            mock_ftp.putfo.assert_called_once()
            mock_pharmacy_file_handler.upload_eligibility_file.assert_not_called()


class TestGetSmpEligibilityMemberType:
    def test_gold_rx_enabled_with_unlimited_category(
        self, unlimited_direct_payment_wallet  # noqa: F811
    ):
        # Given
        org_setting = (
            unlimited_direct_payment_wallet.reimbursement_organization_settings
        )
        org_setting.rx_direct_payment_enabled = True  # Enable RX
        direct_payment_category = (
            unlimited_direct_payment_wallet.get_direct_payment_category
        )
        member = unlimited_direct_payment_wallet.reimbursement_wallet_users[0].member
        ReimbursementRequestFactory.create(
            amount=999999999,
            state=ReimbursementRequestState.REIMBURSED,
            wallet=unlimited_direct_payment_wallet,
            category=direct_payment_category,
        )

        # When
        member_type: SMPMemberType = _get_smp_eligibility_member_type(
            member=member,
            wallet=unlimited_direct_payment_wallet,
            direct_payment_category=direct_payment_category,
            org_setting=org_setting,
            wallet_service=ReimbursementWalletService(),
            enable_unlimited=True,
        )

        # Then
        assert member_type == SMPMemberType.GOLD

    def test_gold_rx_disabled_with_unlimited_category(
        self, unlimited_direct_payment_wallet  # noqa: F811
    ):
        # Given
        org_setting = (
            unlimited_direct_payment_wallet.reimbursement_organization_settings
        )
        org_setting.rx_direct_payment_enabled = False  # Disable RX
        direct_payment_category = (
            unlimited_direct_payment_wallet.get_direct_payment_category
        )
        member = unlimited_direct_payment_wallet.reimbursement_wallet_users[0].member
        ReimbursementRequestFactory.create(
            amount=999999999,
            state=ReimbursementRequestState.REIMBURSED,
            wallet=unlimited_direct_payment_wallet,
            category=direct_payment_category,
        )

        # When
        member_type: SMPMemberType = _get_smp_eligibility_member_type(
            member=member,
            wallet=unlimited_direct_payment_wallet,
            direct_payment_category=direct_payment_category,
            org_setting=org_setting,
            wallet_service=ReimbursementWalletService(),
            enable_unlimited=True,
        )

        # Then
        assert member_type == SMPMemberType.GOLD_REIMBURSEMENT

    @pytest.mark.parametrize(argnames="enable_unlimited", argvalues=[True, False])
    def test_gold_rx_enabled_with_limited_category(
        self, wallet, smp_user, enable_unlimited
    ):
        # Given
        org_setting = wallet.reimbursement_organization_settings
        org_setting.rx_direct_payment_enabled = True  # Enable RX
        direct_payment_category = wallet.get_direct_payment_category
        member = wallet.reimbursement_wallet_users[0].member

        # When
        member_type: SMPMemberType = _get_smp_eligibility_member_type(
            member=member,
            wallet=wallet,
            direct_payment_category=direct_payment_category,
            org_setting=org_setting,
            wallet_service=ReimbursementWalletService(),
            enable_unlimited=enable_unlimited,
        )

        # Then
        assert member_type == SMPMemberType.GOLD

    @pytest.mark.parametrize(argnames="enable_unlimited", argvalues=[True, False])
    def test_gold_rx_enabled_with_limited_category_depleted_balance(
        self, wallet, smp_user, enable_unlimited
    ):
        # Given
        org_setting = wallet.reimbursement_organization_settings
        org_setting.rx_direct_payment_enabled = True  # Enable RX
        direct_payment_category = wallet.get_direct_payment_category
        member = wallet.reimbursement_wallet_users[0].member
        ReimbursementRequestFactory.create(
            amount=999999999,
            state=ReimbursementRequestState.REIMBURSED,
            wallet=wallet,
            category=direct_payment_category,
        )

        # When
        member_type: SMPMemberType = _get_smp_eligibility_member_type(
            member=member,
            wallet=wallet,
            direct_payment_category=direct_payment_category,
            org_setting=org_setting,
            wallet_service=ReimbursementWalletService(),
            enable_unlimited=enable_unlimited,
        )

        # Then
        assert member_type == SMPMemberType.GOLD_X

    @pytest.mark.parametrize(argnames="enable_unlimited", argvalues=[True, False])
    def test_gold_rx_disabled_with_limited_category(
        self, wallet, smp_user, enable_unlimited
    ):
        # Given
        org_setting = wallet.reimbursement_organization_settings
        org_setting.rx_direct_payment_enabled = False  # Disable RX
        direct_payment_category = wallet.get_direct_payment_category
        member = wallet.reimbursement_wallet_users[0].member

        # When
        member_type: SMPMemberType = _get_smp_eligibility_member_type(
            member=member,
            wallet=wallet,
            direct_payment_category=direct_payment_category,
            org_setting=org_setting,
            wallet_service=ReimbursementWalletService(),
            enable_unlimited=enable_unlimited,
        )

        # Then
        assert member_type == SMPMemberType.GOLD_REIMBURSEMENT
