import datetime
import tempfile
from unittest.mock import MagicMock, Mock, patch

import pytest
import pytz
import sqlalchemy.exc

from direct_payment.clinic.pytests.factories import (
    FertilityClinicFactory,
    FertilityClinicLocationFactory,
)
from direct_payment.pharmacy.constants import (
    ENABLE_UNLIMITED_BENEFITS_FOR_SMP,
    SMP_ACTUAL_SHIP_DATE,
    SMP_FERTILITY_CLINIC_1,
    SMP_MAVEN_ID,
    SMP_RX_FILLED_DATE,
    SMP_UNIQUE_IDENTIFIER,
)
from direct_payment.pharmacy.models.pharmacy_prescription import PrescriptionStatus
from direct_payment.pharmacy.tasks.libs.rx_file_processor import (
    FileProcessor,
    process_smp_file,
)
from direct_payment.pharmacy.tasks.libs.smp_cancelled_file import CancelledFileProcessor
from direct_payment.pharmacy.tasks.libs.smp_reimbursement_file import (
    ReimbursementFileProcessor,
)
from direct_payment.pharmacy.tasks.libs.smp_scheduled_file import ScheduledFileProcessor
from direct_payment.pharmacy.tasks.libs.smp_shipped_file import ShippedFileProcessor
from direct_payment.treatment_procedure.models.treatment_procedure import (
    TreatmentProcedureStatus,
)
from pytests.common.global_procedures.factories import GlobalProcedureFactory
from pytests.factories import (
    DefaultUserFactory,
    ReimbursementWalletFactory,
    ReimbursementWalletUsersFactory,
)
from wallet.models.constants import (
    CostSharingCategory,
    ReimbursementRequestState,
    WalletState,
    WalletUserStatus,
    WalletUserType,
)
from wallet.models.reimbursement import ReimbursementRequest
from wallet.models.reimbursement_wallet import ReimbursementWallet
from wallet.models.reimbursement_wallet_user import ReimbursementWalletUsers
from wallet.pytests.factories import (
    ReimbursementOrganizationSettingsFactory,
    ReimbursementRequestFactory,
)

# Import of fixtures from other fixture scopes to avoid duplication
from wallet.pytests.fixtures import (  # noqa: F401
    unlimited_direct_payment_wallet,
    user_for_unlimited_direct_payment_wallet,
    wallet_test_helper,
)
from wallet.repository.member_benefit import MemberBenefitRepository
from wallet.services.member_benefit import MemberBenefitService


@pytest.fixture
def file_processor():
    return ScheduledFileProcessor()


@pytest.fixture
def reimbursement_request(wallet: ReimbursementWallet) -> ReimbursementRequest:
    category_association = (
        wallet.reimbursement_organization_settings.allowed_reimbursement_categories[0]
    )
    category = category_association.reimbursement_request_category
    return ReimbursementRequestFactory.create(
        reimbursement_wallet_id=wallet.id,
        reimbursement_request_category_id=category.id,
    )


@pytest.fixture
def wallet_user(wallet: ReimbursementWallet) -> ReimbursementWalletUsers:
    return ReimbursementWalletUsersFactory.create(
        user_id=wallet.user_id,
        reimbursement_wallet_id=wallet.id,
        status=WalletUserStatus.ACTIVE,
        type=WalletUserType.EMPLOYEE,
    )


@pytest.fixture
def member_benefit_repository(session) -> MemberBenefitRepository:
    return MemberBenefitRepository(session)


class TestFileProcessor:
    def test_process_file(self, file_processor):
        file_mock = MagicMock()
        file_mock.read.return_value = b"header1,header2\nrow1col1,row1col2\n"
        with patch(
            "direct_payment.pharmacy.tasks.libs.rx_file_processor.csv.DictReader",
            return_value=[{"header1": "row1col1", "header2": "row1col2"}],
        ):
            with patch.object(file_processor, "process_row") as mock_process_row:
                file_processor.process_file(file_mock)
                mock_process_row.assert_called_once_with(
                    {"header1": "row1col1", "header2": "row1col2"}
                )

    def test_process_row_success(self, file_processor):
        row_data = {"header1": "row1col1", "header2": "row1col2"}
        with patch.object(file_processor, "validated_row_data", return_value=row_data):
            with patch.object(file_processor, "handle_row") as mock_handle_row:
                file_processor.process_row(row_data)
                mock_handle_row.assert_called_once_with(row_data)

    def test_process_row_failure(self, file_processor):
        row_data = {
            "header1": "row1col1",
            "header2": "row1col2",
            "Maven Benefit ID": "123",
            "Unique Identifier": "456",
        }

        with patch(
            "direct_payment.pharmacy.tasks.libs.rx_file_processor.FileProcessor.get_benefit_id",
            return_value="123",
        ), patch.object(
            file_processor, "validated_row_data", side_effect=Exception("Error")
        ):
            file_processor.process_row(row_data)
            assert file_processor.failed_rows == [
                (
                    "123",
                    "456",
                    "Unable to process row. Event raised to engineering for review.",
                )
            ]

    def test_not_implemented(self):
        with pytest.raises(
            TypeError,
            match="Can't instantiate abstract class FileProcessor with abstract methods "
            "get_file_prefix, handle_row",
        ):
            FileProcessor()


class TestFileProcessorValidation:
    def test_validate_row_data(self, raw_prescription_data):
        # Given
        processor = CancelledFileProcessor()
        # When
        rows = processor.validated_row_data(raw_prescription_data)

        # Then
        assert rows
        assert rows[SMP_MAVEN_ID] == "554691"
        assert rows[SMP_UNIQUE_IDENTIFIER] == "11225658-7065817-0"

    def test_validated_row_data_cleans(self):
        # Given
        processor = CancelledFileProcessor()
        raw_data = {
            "Maven Benefit ID": " 554691 ",
            "Unique Identifier": "11225658-7065817-0  ",
        }
        # When
        rows = processor.validated_row_data(raw_data)

        # Then
        assert rows
        assert rows[SMP_MAVEN_ID] == "554691"
        assert rows[SMP_UNIQUE_IDENTIFIER] == "11225658-7065817-0"

    def test_validated_row_data_missing_returns_none(self):
        # Given
        processor = CancelledFileProcessor()
        raw_data = {
            SMP_MAVEN_ID: "",
            SMP_UNIQUE_IDENTIFIER: "",
        }
        # When
        rows = processor.validated_row_data(raw_data)

        # Then
        assert rows is None

    @pytest.mark.parametrize(
        argnames="status",
        argvalues=(
            TreatmentProcedureStatus.COMPLETED,
            TreatmentProcedureStatus.CANCELLED,
        ),
    )
    def test_get_treatment_procedure_none(
        self, treatment_procedure, new_prescription, status, raw_prescription_data
    ):
        # Given
        processor = CancelledFileProcessor()
        given_prescription = new_prescription(treatment_status=status)
        # When
        actual_treatment_procedure = processor.get_treatment_procedure(
            raw_prescription_data, given_prescription
        )
        # Then
        assert actual_treatment_procedure is None
        assert processor.failed_rows == [
            (
                "554691",
                "11225658-7065817-0",
                "Treatment Procedure not in a processable status.",
            )
        ]

    def test_get_treatment_procedure(
        self, treatment_procedure, new_prescription, raw_prescription_data
    ):
        # Given
        processor = CancelledFileProcessor()
        given_prescription = new_prescription(
            treatment_status=TreatmentProcedureStatus.SCHEDULED
        )
        # When
        actual_treatment_procedure = processor.get_treatment_procedure(
            raw_prescription_data, given_prescription
        )
        # Then
        assert actual_treatment_procedure
        assert processor.failed_rows == []

    def test_validate_wallet_found(self, wallet, wallet_user, raw_prescription_data):
        # Given
        processor = ScheduledFileProcessor()
        wallet.reimbursement_wallet_benefit.maven_benefit_id = "554691"
        # When
        result = processor.validate_wallet(row=raw_prescription_data)

        # Then
        assert result == wallet
        assert processor.failed_rows == []

    def test_validate_wallet_found_multiple_wallets(
        self,
        wallet,
        wallet_user,
        enterprise_user,
        raw_prescription_data,
        member_benefit_repository,
    ):
        # Given
        processor = ReimbursementFileProcessor()
        org_settings = ReimbursementOrganizationSettingsFactory(
            organization_id=enterprise_user.organization.id
        )
        disqualified_wallet = ReimbursementWalletFactory.create(
            member=enterprise_user,
            state=WalletState.DISQUALIFIED,
            reimbursement_organization_settings_id=org_settings.id,
        )
        ReimbursementWalletUsersFactory.create(
            user_id=wallet.user_id,
            reimbursement_wallet_id=disqualified_wallet.id,
            status=WalletUserStatus.ACTIVE,
            type=WalletUserType.EMPLOYEE,
        )
        user_benefit = member_benefit_repository.get_by_user_id(wallet.user_id)

        wallet.reimbursement_wallet_benefit.maven_benefit_id = "554691"
        with patch.object(
            MemberBenefitRepository,
            "get_by_benefit_id",
            return_value=user_benefit,
        ):
            # When
            result = processor.validate_wallet(row=raw_prescription_data)

        # Then
        assert result == wallet
        assert processor.failed_rows == []

    @pytest.mark.parametrize(
        argnames="given_processor, given_benefit_id",
        argvalues=(
            (ShippedFileProcessor(), "554691"),
            (CancelledFileProcessor(), "554691"),
            (ScheduledFileProcessor(), "554691"),
            (ReimbursementFileProcessor(), "M56789"),
        ),
    )
    def test_validate_wallet_not_found(
        self,
        given_processor,
        given_benefit_id,
        wallet,
        raw_prescription_data,
        wallet_user,
    ):
        # Given
        processor = given_processor
        # When
        result = processor.validate_wallet(row=raw_prescription_data)

        # Then
        assert result is None
        assert processor.failed_rows == [
            (given_benefit_id, "11225658-7065817-0", "Wallet not found.")
        ]

    @pytest.mark.parametrize(
        argnames="given_processor",
        argvalues=(
            ShippedFileProcessor(),
            CancelledFileProcessor(),
            ScheduledFileProcessor(),
            ReimbursementFileProcessor(),
        ),
    )
    def test_validate_wallet_file_type(
        self,
        given_processor,
        wallet,
        raw_prescription_data,
        wallet_user,
        member_benefit_repository,
    ):
        # Given
        processor = given_processor
        wallet.reimbursement_wallet_benefit.maven_benefit_id = "554691"
        user_benefit = member_benefit_repository.get_by_user_id(wallet.user_id)
        raw_prescription_data["User Benefit ID"] = user_benefit.benefit_id
        with patch.object(
            MemberBenefitRepository,
            "get_by_benefit_id",
            return_value=user_benefit,
        ):
            # When
            result = processor.validate_wallet(row=raw_prescription_data)

        # Then
        assert result == wallet
        assert processor.failed_rows == []

    @pytest.mark.parametrize(
        argnames="is_member_on_file",
        argvalues=(True, False),
    )
    def test_validate_shared_wallet(
        self,
        is_member_on_file,
        wallet,
        raw_prescription_data,
        wallet_user,
        member_benefit_repository,
    ):
        # Given
        processor = ReimbursementFileProcessor()
        # Create a dependent
        active_user = DefaultUserFactory.create()
        ReimbursementWalletUsersFactory.create(
            user_id=active_user.id,
            reimbursement_wallet_id=wallet.id,
            type=WalletUserType.DEPENDENT,
            status=WalletUserStatus.ACTIVE,
        )
        benefit_service = MemberBenefitService(
            member_benefit_repo=member_benefit_repository
        )
        benefit_service.add_for_user(user_id=active_user.id)

        # Set the user_id to either the member or the dependent based on test params
        given_user_id = wallet.user_id if is_member_on_file else active_user.id

        member_benefit = member_benefit_repository.get_by_user_id(given_user_id)

        raw_prescription_data["User Benefit ID"] = member_benefit.benefit_id
        with patch.object(
            MemberBenefitRepository,
            "get_by_benefit_id",
            return_value=member_benefit,
        ):
            # When
            result = processor.validate_wallet(row=raw_prescription_data)

        # Then
        assert result == wallet
        assert processor.failed_rows == []

    def test_validate_user_found(self, wallet, raw_prescription_data, wallet_user):
        # Given
        processor = ScheduledFileProcessor()
        wallet.reimbursement_wallet_benefit.maven_benefit_id = "554691"
        wallet_user.member.first_name = "Brittany"
        wallet_user.member.last_name = "Fun"

        # When
        result = processor.validate_user(row=raw_prescription_data, wallet=wallet)
        # Then
        assert result == wallet_user.member
        assert processor.failed_rows == []

    def test_validate_user_not_found(self, wallet, raw_prescription_data, wallet_user):
        # Given
        processor = ScheduledFileProcessor()
        wallet.reimbursement_wallet_benefit.maven_benefit_id = "554691"
        # When
        result = processor.validate_user(row=raw_prescription_data, wallet=wallet)
        # Then
        assert result is None
        assert processor.failed_rows == [
            ("554691", "11225658-7065817-0", "User not found.")
        ]

    def test_validate_user_no_wallet(self, raw_prescription_data):
        # Given
        processor = ScheduledFileProcessor()
        # When
        result = processor.validate_user(row=raw_prescription_data, wallet=None)

        # Then
        assert result is None

    @pytest.mark.parametrize(
        argnames="given_processor, rx_enabled",
        argvalues=(
            (ShippedFileProcessor(), True),
            (CancelledFileProcessor(), True),
            (ScheduledFileProcessor(), True),
            (ReimbursementFileProcessor(), False),
        ),
    )
    def test_validate_org_settings_valid(
        self, given_processor, rx_enabled, wallet, raw_prescription_data, wallet_user
    ):
        # Given
        wallet.reimbursement_wallet_benefit.maven_benefit_id = "554691"
        wallet.reimbursement_organization_settings.rx_direct_payment_enabled = (
            rx_enabled
        )
        wallet_user.member.first_name = "Brittany"
        wallet_user.member.last_name = "Fun"

        # When
        result = given_processor.validate_org_settings(
            row=raw_prescription_data,
            rx_enabled=rx_enabled,
            wallet=wallet,
            user=wallet_user.member,
        )

        # Then
        assert result
        assert given_processor.failed_rows == []

    def test_validate_org_settings_invalid(
        self, wallet, raw_prescription_data, wallet_user
    ):
        # Given
        processor = ScheduledFileProcessor()
        wallet.reimbursement_wallet_benefit.maven_benefit_id = "554691"
        wallet_user.member.member_profile.country_code = "MX"

        # When
        result = processor.validate_org_settings(
            row=raw_prescription_data,
            rx_enabled=False,
            wallet=wallet,
            user=wallet_user.member,
        )
        # Then
        assert result is None
        assert processor.failed_rows == [
            ("554691", "11225658-7065817-0", "Problem with configurations.")
        ]

    def test_validate_org_settings_invalid_reimbursement(
        self, wallet, raw_prescription_data, wallet_user
    ):
        # Given (default factory org settings sets rx enabled as True)
        processor = ReimbursementFileProcessor()

        # When
        result = processor.validate_org_settings(
            row=raw_prescription_data,
            rx_enabled=False,
            wallet=wallet,
            user=wallet_user.member,
        )
        # Then
        assert result is None
        assert processor.failed_rows == [
            ("M56789", "11225658-7065817-0", "Problem with configurations.")
        ]

    def test_validate_fertility_clinic_found(self, raw_prescription_data):
        # Given
        processor = ScheduledFileProcessor()
        fertility_clinic = FertilityClinicFactory.create(name=SMP_FERTILITY_CLINIC_1)
        FertilityClinicLocationFactory.create(fertility_clinic=fertility_clinic)

        # When
        result = processor.validate_fertility_clinic(row=raw_prescription_data)

        # Then
        assert result
        assert processor.failed_rows == []

    def test_validate_fertility_clinic_not_found(self, raw_prescription_data):
        # Given
        processor = ScheduledFileProcessor()
        fertility_clinic = FertilityClinicFactory.create(name="Non-Matching")
        FertilityClinicLocationFactory.create(fertility_clinic=fertility_clinic)

        # When
        result = processor.validate_fertility_clinic(row=raw_prescription_data)
        # Then
        assert result is None
        assert processor.failed_rows == [
            ("554691", "11225658-7065817-0", "Fertility Clinic not found.")
        ]

    def test_validate_category_found(self, wallet_cycle_based, raw_prescription_data):
        # Given
        processor = ScheduledFileProcessor()
        # When
        result = processor.validate_category(
            row=raw_prescription_data, wallet=wallet_cycle_based
        )

        # Then
        assert result
        assert processor.failed_rows == []

    def test_validate_category_not_found(self, wallet, raw_prescription_data):
        # Given
        processor = ScheduledFileProcessor()
        # When
        result = processor.validate_category(row=raw_prescription_data, wallet=wallet)
        # Then
        assert result is None
        assert processor.failed_rows == [
            ("554691", "11225658-7065817-0", "Reimbursement Category not found.")
        ]

    def test_validate_cost_sharing_category(self, wallet, raw_prescription_data):
        # Given
        processor = ReimbursementFileProcessor()
        global_procedure = GlobalProcedureFactory.create(id=1, type="pharmacy")
        # When
        result = processor.validate_cost_sharing_category(
            row=raw_prescription_data, global_procedure=global_procedure
        )

        # Then
        assert result == CostSharingCategory.GENERIC_PRESCRIPTIONS
        assert processor.failed_rows == []

    def test_validate_cost_sharing_category_not_found(
        self, wallet, raw_prescription_data
    ):
        # Given
        processor = ReimbursementFileProcessor()
        global_procedure = GlobalProcedureFactory.create(
            id=1, type="pharmacy", cost_sharing_category=None
        )
        # When
        result = processor.validate_cost_sharing_category(
            row=raw_prescription_data, global_procedure=global_procedure
        )

        # Then
        assert result is None
        assert processor.failed_rows == [
            ("M56789", "11225658-7065817-0", "Cost Sharing Category not found.")
        ]

    @pytest.mark.parametrize(
        argnames="wallet_state",
        argvalues=(
            WalletState.QUALIFIED,
            WalletState.RUNOUT,
        ),
    )
    def test_validate_wallet_state_success(
        self,
        wallet_state,
        wallet,
        raw_prescription_data,
    ):
        # Given
        processor = ReimbursementFileProcessor()
        wallet.state = wallet_state
        # When
        found_wallet = processor.validate_wallet_state(
            wallet=wallet, row=raw_prescription_data
        )

        # Then
        assert found_wallet
        assert found_wallet.state == wallet_state

    @pytest.mark.parametrize(
        argnames="wallet_state",
        argvalues=(
            WalletState.PENDING,
            WalletState.DISQUALIFIED,
            WalletState.EXPIRED,
        ),
    )
    def test_validate_wallet_state_failure(
        self,
        wallet_state,
        wallet,
        raw_prescription_data,
    ):
        # Given
        processor = ReimbursementFileProcessor()
        wallet.state = wallet_state
        # When
        found_wallet = processor.validate_wallet_state(wallet, raw_prescription_data)

        # Then
        assert found_wallet is None
        assert processor.failed_rows == [
            (
                "M56789",
                "11225658-7065817-0",
                "Wallet state not allowed for auto processed reimbursements.",
            )
        ]

    @pytest.mark.parametrize(
        argnames="enable_unlimited",
        argvalues=[True, False],
    )
    def test_validate_wallet_balance_none(
        self, enable_unlimited, wallet, wallet_user, raw_prescription_data, ff_test_data
    ):
        # Given
        ff_test_data.update(
            ff_test_data.flag(ENABLE_UNLIMITED_BENEFITS_FOR_SMP).variations(
                enable_unlimited
            )
        )

        processor = ReimbursementFileProcessor()
        category_association = wallet.get_or_create_wallet_allowed_categories[0]

        amount = category_association.reimbursement_request_category_maximum
        ReimbursementRequestFactory.create(
            wallet=wallet,
            category=category_association.reimbursement_request_category,
            state=ReimbursementRequestState.APPROVED,
            amount=amount,
        )
        # When
        processor.validate_wallet_balance(
            raw_prescription_data,
            wallet,
            category_association.reimbursement_request_category,
        )
        # Then
        assert processor.failed_rows == [
            ("M56789", "11225658-7065817-0", "No wallet balance remaining.")
        ]

    @pytest.mark.parametrize(
        argnames="enable_unlimited",
        argvalues=[True, False],
    )
    def test_validate_wallet_balance(
        self, enable_unlimited, wallet, raw_prescription_data, wallet_user, ff_test_data
    ):
        # Given
        ff_test_data.update(
            ff_test_data.flag(ENABLE_UNLIMITED_BENEFITS_FOR_SMP).variations(
                enable_unlimited
            )
        )
        processor = ReimbursementFileProcessor()
        category_association = wallet.get_or_create_wallet_allowed_categories[0]

        # When
        balance = processor.validate_wallet_balance(
            raw_prescription_data,
            wallet,
            category_association.reimbursement_request_category,
        )

        # Then
        assert balance
        assert processor.failed_rows == []

    def test_validate_wallet_balance_for_unlimited_category(
        self,
        unlimited_direct_payment_wallet,  # noqa: F811
        raw_prescription_data,
        ff_test_data,
    ):
        # Given
        ff_test_data.update(
            ff_test_data.flag(ENABLE_UNLIMITED_BENEFITS_FOR_SMP).variations(True)
        )
        processor = ReimbursementFileProcessor()
        category_association = (
            unlimited_direct_payment_wallet.get_or_create_wallet_allowed_categories[0]
        )

        # When
        balance = processor.validate_wallet_balance(
            raw_prescription_data,
            unlimited_direct_payment_wallet,
            category_association.reimbursement_request_category,
        )

        # Then
        assert balance
        assert processor.failed_rows == []


class TestPharmacyPrescriptionHelpers:
    def test_get_pharmacy_prescription(self, new_prescription, raw_prescription_data):
        # Given
        given_unique_id = "11225658-7065817-0"
        given_processor = ReimbursementFileProcessor()
        given_prescription = new_prescription()
        # When
        found_prescription = given_processor.get_pharmacy_prescription(
            row=raw_prescription_data
        )
        # Then
        assert found_prescription == given_prescription
        assert found_prescription.rx_unique_id == given_unique_id

    def test_get_pharmacy_prescription_none(self, raw_prescription_data):
        # Given
        given_processor = ReimbursementFileProcessor()
        # When
        found_prescription = given_processor.get_pharmacy_prescription(
            row=raw_prescription_data
        )
        # Then
        assert found_prescription is None

    def test_create_pharmacy_prescription(self, raw_prescription_data):
        # Given
        given_processor = ReimbursementFileProcessor()
        given_unique_id = "11225658-7065817-0"
        given_user_benefit_id = "M56789"
        row = raw_prescription_data
        given_prescription_params = {
            "user_benefit_id": given_user_benefit_id,
            "status": PrescriptionStatus.PAID,
            "amount_owed": 13.66,
            "reimbursement_json": raw_prescription_data,
            "actual_ship_date": datetime.datetime.strptime(
                row[SMP_ACTUAL_SHIP_DATE], "%m/%d/%Y"
            ),
            "rx_filled_date": datetime.datetime.strptime(
                row[SMP_RX_FILLED_DATE], "%m/%d/%Y"
            ),
        }
        # When
        created_prescription = given_processor.create_pharmacy_prescription(
            row=row, prescription_params=given_prescription_params
        )
        # Then
        assert created_prescription
        assert created_prescription.rx_unique_id == given_unique_id
        assert created_prescription.user_benefit_id == given_user_benefit_id

    def test_update_pharmacy_prescription(
        self, new_prescription, wallet, reimbursement_request
    ):
        # Given
        given_processor = ReimbursementFileProcessor()
        given_prescription = new_prescription()

        given_prescription_params = {
            "reimbursement_request_id": reimbursement_request.id,
            "user_id": wallet.user_id,
        }
        # When
        updated_prescription = given_processor.update_pharmacy_prescription(
            prescription=given_prescription,
            prescription_params=given_prescription_params,
        )
        # Then
        assert updated_prescription
        assert updated_prescription.rx_unique_id == given_prescription.rx_unique_id
        assert updated_prescription.user_id == wallet.user_id

    def test_update_pharmacy_prescription_exception(self, new_prescription, wallet):
        # Given
        given_processor = ReimbursementFileProcessor()
        given_prescription = new_prescription()

        given_prescription_params = {
            "reimbursement_request_id": "ABC132",
            "user_id": wallet.user_id,
        }
        # When/Then
        with pytest.raises(sqlalchemy.exc.IntegrityError):
            given_processor.update_pharmacy_prescription(
                prescription=given_prescription,
                prescription_params=given_prescription_params,
            )


class TestProcessSmpFile:
    @pytest.mark.parametrize(
        argnames="base_file, processor",
        argvalues=(
            ("Maven_Rx_Shipped", ShippedFileProcessor()),
            ("Maven_Rx_Canceled", CancelledFileProcessor()),
            ("Maven_Rx_Scheduled", ScheduledFileProcessor()),
            ("Maven_Rx_Reimbursement", ReimbursementFileProcessor()),
        ),
    )
    def test_process_smp_file_empty_file(
        self,
        base_file,
        processor,
    ):
        # Given
        mock_temp_file = tempfile.NamedTemporaryFile()  # empty
        date_time = datetime.datetime.now(pytz.timezone("America/New_York")).strftime(
            "%Y%m%d"
        )
        base_file_name = f"{base_file}_{date_time}"

        with patch("paramiko.SSHClient") as mock_ssh, patch(
            "direct_payment.pharmacy.tasks.libs.rx_file_processor.process_smp_file",
            return_value=True,
        ), patch(
            "direct_payment.pharmacy.tasks.libs.common._send_file_receipt",
            return_value=True,
        ), patch(
            "direct_payment.pharmacy.tasks.libs.common.create_temp_file",
            return_value=mock_temp_file,
        ):
            mock_ftp = mock_ssh.return_value.open_sftp.return_value = Mock()
            mock_ftp.listdir.return_value = [base_file_name]
            # When
            processed = process_smp_file(processor=processor)
            # Then
            assert processed is False

    def test_process_smp_shipped_file(
        self,
        smp_shipped_file,
    ):
        # Given
        mock_temp_file = smp_shipped_file()
        date_time = datetime.datetime.now(pytz.timezone("America/New_York")).strftime(
            "%Y%m%d"
        )
        base_file_name = f"Maven_Rx_Shipped_{date_time}"

        with patch("paramiko.SSHClient") as mock_ssh, patch(
            "direct_payment.pharmacy.tasks.libs.rx_file_processor.process_smp_file",
            return_value=True,
        ), patch(
            "direct_payment.pharmacy.tasks.libs.common._send_file_receipt",
            return_value=True,
        ), patch(
            "direct_payment.pharmacy.tasks.libs.common.create_temp_file",
            return_value=mock_temp_file,
        ):
            mock_ftp = mock_ssh.return_value.open_sftp.return_value = Mock()
            mock_ftp.listdir.return_value = [base_file_name]
            # When
            shipped_processor = ShippedFileProcessor()
            processed = process_smp_file(processor=shipped_processor)
            # Then
            assert processed

    def test_process_smp_cancelled_file(
        self,
        smp_cancelled_file,
    ):
        # Given
        mock_temp_file = smp_cancelled_file()
        date_time = datetime.datetime.now(pytz.timezone("America/New_York")).strftime(
            "%Y%m%d"
        )
        base_file_name = f"Maven_Rx_Canceled_{date_time}"

        with patch("paramiko.SSHClient") as mock_ssh, patch(
            "direct_payment.pharmacy.tasks.libs.rx_file_processor.process_smp_file",
            return_value=True,
        ), patch(
            "direct_payment.pharmacy.tasks.libs.common.create_temp_file",
            return_value=mock_temp_file,
        ):
            mock_ftp = mock_ssh.return_value.open_sftp.return_value = Mock()
            mock_ftp.listdir.return_value = [base_file_name]
            # When
            cancelled_processor = CancelledFileProcessor()
            processed = process_smp_file(processor=cancelled_processor)
            # Then
            assert processed

    def test_process_smp_scheduled_file(
        self,
        smp_scheduled_file,
    ):
        # Given
        mock_temp_file = smp_scheduled_file()
        date_time = datetime.datetime.now(pytz.timezone("America/New_York")).strftime(
            "%Y%m%d"
        )
        base_file_name = f"Maven_Rx_Scheduled_{date_time}"

        with patch("paramiko.SSHClient") as mock_ssh, patch(
            "direct_payment.pharmacy.tasks.libs.rx_file_processor.process_smp_file",
            return_value=True,
        ), patch(
            "direct_payment.pharmacy.tasks.libs.common.create_temp_file",
            return_value=mock_temp_file,
        ):
            mock_ftp = mock_ssh.return_value.open_sftp.return_value = Mock()
            mock_ftp.listdir.return_value = [base_file_name]
            # When
            scheduled_processor = ScheduledFileProcessor()
            processed = process_smp_file(processor=scheduled_processor)
            # Then
            assert processed

    def test_process_smp_reimbursement_file(
        self,
        smp_reimbursement_file,
    ):
        # Given
        mock_temp_file = smp_reimbursement_file()
        date_time = datetime.datetime.now(pytz.timezone("America/New_York")).strftime(
            "%Y%m%d"
        )
        base_file_name = f"Maven_Rx_Reimbursement_{date_time}"

        with patch("paramiko.SSHClient") as mock_ssh, patch(
            "direct_payment.pharmacy.tasks.libs.rx_file_processor.process_smp_file",
            return_value=True,
        ), patch(
            "direct_payment.pharmacy.tasks.libs.common.create_temp_file",
            return_value=mock_temp_file,
        ):
            mock_ftp = mock_ssh.return_value.open_sftp.return_value = Mock()
            mock_ftp.listdir.return_value = [base_file_name]
            # When
            reimbursement_processor = ReimbursementFileProcessor()
            processed = process_smp_file(processor=reimbursement_processor)
            # Then
            assert processed

    @pytest.mark.parametrize(
        "processor,file_content,expected_result",
        [
            (
                ScheduledFileProcessor(),
                ("header1,header2\nvalue1,value2\n", "test.csv"),
                True,
            ),
            (
                ReimbursementFileProcessor(),
                ("header1,header2\nvalue1,value2\n", "test.csv"),
                True,
            ),
            (
                CancelledFileProcessor(),
                ("header1,header2\nvalue1,value2\n", "test.csv"),
                True,
            ),
            (ScheduledFileProcessor(), (None, None), False),
            (ScheduledFileProcessor(), ("", "test.csv"), False),
        ],
    )
    def test_process_smp_file_gcs(
        self,
        mock_pharmacy_file_handler,
        processor,
        file_content,
        expected_result,
        smp_gcs_ff_enabled,
    ):
        smp_gcs_ff_enabled(True)
        mock_pharmacy_file_handler.get_pharmacy_ingestion_file.return_value = (
            file_content
        )

        with patch(
            "direct_payment.pharmacy.tasks.libs.rx_file_processor.PharmacyFileHandler",
            return_value=mock_pharmacy_file_handler,
        ), patch.object(processor, "process_row") as mock_process:
            # When
            result = process_smp_file(processor)
            # Then
            assert result is expected_result
            mock_pharmacy_file_handler.get_pharmacy_ingestion_file.assert_called_once_with(
                file_prefix=processor.get_file_prefix(),
                file_type=processor.file_type,
                input_date=None,
            )
            if expected_result:
                mock_process.assert_called_once()
            else:
                mock_process.assert_not_called()

    def test_process_smp_file_gcs_shipped_file(
        self, mock_pharmacy_file_handler, smp_gcs_ff_enabled
    ):
        smp_gcs_ff_enabled(True)
        mock_pharmacy_file_handler.get_pharmacy_ingestion_file.return_value = (
            "header1,header2\nvalue1,value2\n",
            "shipped.csv",
        )

        processor = ShippedFileProcessor()

        with patch(
            "direct_payment.pharmacy.tasks.libs.rx_file_processor.PharmacyFileHandler",
            return_value=mock_pharmacy_file_handler,
        ), patch.object(processor, "process_row") as mock_process:
            # When
            result = process_smp_file(processor)
            # Then
            assert result is True
            mock_pharmacy_file_handler.get_pharmacy_ingestion_file.assert_called_once_with(
                file_prefix=processor.get_file_prefix(),
                file_type=processor.file_type,
                input_date=None,
            )
            mock_pharmacy_file_handler.send_file_receipt.assert_called_once_with(
                "header1,header2\nvalue1,value2\n", "shipped.csv"
            )
            mock_process.assert_called_once()

    def test_process_smp_file_gcs_handler_error(
        self, mock_pharmacy_file_handler, smp_gcs_ff_enabled
    ):
        smp_gcs_ff_enabled(True)
        mock_pharmacy_file_handler.get_pharmacy_ingestion_file.side_effect = Exception(
            "GCS Error"
        )

        processor = ScheduledFileProcessor()

        with patch(
            "direct_payment.pharmacy.tasks.libs.rx_file_processor.PharmacyFileHandler",
            return_value=mock_pharmacy_file_handler,
        ):
            # When
            result = process_smp_file(processor)

            # Then
            assert result is False
            mock_pharmacy_file_handler.get_pharmacy_ingestion_file.assert_called_once_with(
                file_prefix=processor.get_file_prefix(),
                file_type=processor.file_type,
                input_date=None,
            )

    def test_process_smp_file_gcs_process_error(
        self, mock_pharmacy_file_handler, smp_gcs_ff_enabled
    ):
        smp_gcs_ff_enabled(True)
        # Reset mock
        mock_pharmacy_file_handler.get_pharmacy_ingestion_file.reset_mock()
        mock_pharmacy_file_handler.get_pharmacy_ingestion_file.return_value = (
            "content",
            "test.csv",
        )

        with patch(
            "direct_payment.pharmacy.tasks.libs.rx_file_processor.PharmacyFileHandler",
            return_value=mock_pharmacy_file_handler,
        ), patch.object(
            ScheduledFileProcessor,
            "process_file",
            side_effect=Exception("Process Error"),
        ):
            # When
            result = process_smp_file(ScheduledFileProcessor())

            # Then
            assert result is False
