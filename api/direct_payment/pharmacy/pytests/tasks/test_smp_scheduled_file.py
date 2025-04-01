import datetime
from unittest.mock import patch

import pytest

from common.global_procedures.procedure import ProcedureService
from direct_payment.clinic.pytests.factories import (
    FertilityClinicFactory,
    FertilityClinicLocationFactory,
)
from direct_payment.pharmacy.constants import SMP_FERTILITY_CLINIC_1
from direct_payment.pharmacy.models.pharmacy_prescription import PrescriptionStatus
from direct_payment.pharmacy.tasks.libs.smp_scheduled_file import ScheduledFileProcessor
from direct_payment.treatment_procedure.models.treatment_procedure import (
    TreatmentProcedure,
    TreatmentProcedureType,
)
from pytests.common.global_procedures.factories import GlobalProcedureFactory
from wallet.models.constants import WalletState, WalletUserStatus, WalletUserType
from wallet.pytests.factories import ReimbursementWalletUsersFactory


class TestSMPScheduledFile:
    def test_process_scheduled_temp_success(
        self,
        wallet,
        smp_scheduled_file,
        pharmacy_prescription_service,
        enterprise_user,
    ):
        # Given
        rwu = ReimbursementWalletUsersFactory.create(
            user_id=enterprise_user.id,
            reimbursement_wallet_id=wallet.id,
            status=WalletUserStatus.ACTIVE,
            type=WalletUserType.EMPLOYEE,
        )
        fertility_clinic = FertilityClinicFactory.create(name=SMP_FERTILITY_CLINIC_1)
        FertilityClinicLocationFactory.create(fertility_clinic=fertility_clinic)

        given_procedure = GlobalProcedureFactory.create(id=1, type="pharmacy")
        given_rx_unique_id = "7065817-12"
        mock_rx_received_date_from_file = datetime.date(2023, 8, 1)

        with patch.object(
            ProcedureService,
            "get_procedures_by_ndc_numbers",
            return_value=[given_procedure],
        ), patch(
            "direct_payment.pharmacy.tasks.libs.smp_scheduled_file.trigger_cost_breakdown",
            return_value=True,
        ):
            # When
            processor = ScheduledFileProcessor()
            processor.process_file(smp_scheduled_file())
            treatment_plans = TreatmentProcedure.query.all()
            prescription = (
                pharmacy_prescription_service.get_prescription_by_unique_id_status(
                    rx_unique_id=given_rx_unique_id
                )
            )

        # Then
        assert len(treatment_plans) == 1
        assert treatment_plans[0].cost == 4815
        assert isinstance(treatment_plans[0].start_date, datetime.date)
        assert treatment_plans[0].member_id == rwu.user_id
        # Below shows the rx received date from the mock file is what is set for start/end date
        assert treatment_plans[0].start_date == mock_rx_received_date_from_file
        assert treatment_plans[0].end_date == mock_rx_received_date_from_file
        assert prescription
        assert treatment_plans[0].procedure_type == TreatmentProcedureType.PHARMACY

    def test_process_scheduled_temp_dry(self, wallet, smp_scheduled_file):
        # Given/When
        processor = ScheduledFileProcessor(dry_run=True)
        processor.process_file(smp_scheduled_file())
        treatment_plans = TreatmentProcedure.query.all()

        # Then
        assert len(treatment_plans) == 0

    def test_process_scheduled_temp_fails_file_validation(self, smp_scheduled_file):
        # Given/When
        processor = ScheduledFileProcessor()
        processor.process_file(smp_scheduled_file(benefit_id=""))
        treatment_plans = TreatmentProcedure.query.all()
        # Then
        assert len(treatment_plans) == 0

    @pytest.mark.parametrize(
        argnames="given_status",
        argvalues=(
            PrescriptionStatus.SCHEDULED,
            PrescriptionStatus.SHIPPED,
            PrescriptionStatus.CANCELLED,
        ),
    )
    def test_process_scheduled_temp_found_prescription(
        self,
        given_status,
        smp_scheduled_file,
        new_prescription,
        pharmacy_prescription_service,
    ):
        # Given
        given_prescription = new_prescription(status=given_status)
        # When
        processor = ScheduledFileProcessor()
        processor.process_file(
            smp_scheduled_file(unique_identifier=given_prescription.rx_unique_id)
        )
        treatment_plans = TreatmentProcedure.query.all()
        prescription = (
            pharmacy_prescription_service.get_prescription_by_unique_id_status(
                rx_unique_id=given_prescription.rx_unique_id
            )
        )
        # Then
        assert len(treatment_plans) == 1
        assert prescription

    def test_process_scheduled_temp_fails_invalid_wallet(
        self, wallet, smp_scheduled_file
    ):
        # Given
        ReimbursementWalletUsersFactory.create(
            user_id=wallet.member.id,
            reimbursement_wallet_id=wallet.id,
            status=WalletUserStatus.ACTIVE,
            type=WalletUserType.EMPLOYEE,
        )
        # When
        processor = ScheduledFileProcessor()
        processor.process_file(smp_scheduled_file(benefit_id="0000"))
        treatment_plans = TreatmentProcedure.query.all()
        # Then
        assert len(treatment_plans) == 0

    def test_process_scheduled_temp_fails_invalid_wallet_user(
        self, wallet, smp_scheduled_file
    ):
        # Given/When
        processor = ScheduledFileProcessor()
        processor.process_file(smp_scheduled_file())
        treatment_plans = TreatmentProcedure.query.all()
        # Then
        assert len(treatment_plans) == 0

    def test_process_scheduled_temp_fails_invalid_patient_name(
        self, wallet, smp_scheduled_file, enterprise_user
    ):
        # Given
        ReimbursementWalletUsersFactory.create(
            user_id=enterprise_user.id,
            reimbursement_wallet_id=wallet.id,
        )
        # When
        processor = ScheduledFileProcessor()
        processor.process_file(smp_scheduled_file(first_name="unknown"))
        treatment_plans = TreatmentProcedure.query.all()
        # Then
        assert len(treatment_plans) == 0

    @pytest.mark.parametrize(
        argnames="wallet_state,rx_enabled,country_code",
        argvalues=(
            # not qualified, rx_enabled, country_code = "US"
            (WalletState.PENDING, True, "US"),
            # qualified, rx_enabled = False, country_code = "US"
            (WalletState.QUALIFIED, False, "US"),
            # qualified, rx_enabled, country_code = "SE"
            (WalletState.QUALIFIED, True, "SE"),
        ),
    )
    def test_process_scheduled_temp_fails_config_check(
        self,
        wallet,
        smp_scheduled_file,
        wallet_state,
        rx_enabled,
        country_code,
        enterprise_user,
    ):
        # Given
        wallet_user = ReimbursementWalletUsersFactory.create(
            user_id=enterprise_user.id,
            reimbursement_wallet_id=wallet.id,
        )
        wallet.state = wallet_state
        wallet.reimbursement_organization_settings.rx_direct_payment_enabled = (
            rx_enabled
        )
        wallet_user.member.member_profile.country_code = country_code
        # When
        processor = ScheduledFileProcessor()
        processor.process_file(smp_scheduled_file())
        treatment_plans = TreatmentProcedure.query.all()
        # Then
        assert len(treatment_plans) == 0

    def test_process_scheduled_temp_fails_no_fertility_clinic(
        self, wallet, smp_scheduled_file, enterprise_user
    ):
        # Given
        ReimbursementWalletUsersFactory.create(
            user_id=enterprise_user.id,
            reimbursement_wallet_id=wallet.id,
        )
        FertilityClinicFactory.create(name="unknown")

        # When
        processor = ScheduledFileProcessor()
        processor.process_file(smp_scheduled_file())
        treatment_plans = TreatmentProcedure.query.all()

        # Then
        assert len(treatment_plans) == 0

    def test_process_scheduled_temp_fails_no_mapped_fertility_clinic_name(
        self, wallet, smp_scheduled_file, enterprise_user
    ):
        # Given
        ReimbursementWalletUsersFactory.create(
            user_id=enterprise_user.id,
            reimbursement_wallet_id=wallet.id,
            status=WalletUserStatus.ACTIVE,
            type=WalletUserType.EMPLOYEE,
        )
        FertilityClinicFactory.create(name=SMP_FERTILITY_CLINIC_1)
        invalid_file = smp_scheduled_file(ncpdp=0000)
        # When
        processor = ScheduledFileProcessor()
        processor.process_file(invalid_file)
        treatment_plans = TreatmentProcedure.query.all()

        # Then
        assert len(treatment_plans) == 0

    def test_process_scheduled_temp_no_global_procedure(
        self, wallet, smp_scheduled_file, enterprise_user
    ):
        # Given
        ReimbursementWalletUsersFactory.create(
            user_id=enterprise_user.id,
            reimbursement_wallet_id=wallet.id,
        )
        fertility_clinic = FertilityClinicFactory.create(name=SMP_FERTILITY_CLINIC_1)
        FertilityClinicLocationFactory.create(fertility_clinic=fertility_clinic)

        given_procedure_bad_type = GlobalProcedureFactory.create(
            id=1, name="Test", type="medical"
        )
        with patch.object(
            ProcedureService,
            "get_procedures_by_ndc_numbers",
            return_value=[given_procedure_bad_type],
        ):
            # When
            processor = ScheduledFileProcessor()
            processor.process_file(smp_scheduled_file())

        treatment_plans = TreatmentProcedure.query.all()
        # Then
        assert len(treatment_plans) == 0

    def test_process_scheduled_temp_fails_no_category(
        self, wallet, smp_scheduled_file, enterprise_user
    ):
        # Given
        ReimbursementWalletUsersFactory.create(
            user_id=enterprise_user.id,
            reimbursement_wallet_id=wallet.id,
            status=WalletUserStatus.ACTIVE,
            type=WalletUserType.EMPLOYEE,
        )
        fertility_clinic = FertilityClinicFactory.create(name=SMP_FERTILITY_CLINIC_1)
        FertilityClinicLocationFactory.create(fertility_clinic=fertility_clinic)
        given_procedure = GlobalProcedureFactory.create(id=1, type="pharmacy")
        wallet.reimbursement_organization_settings.direct_payment_enabled = False
        with patch.object(
            ProcedureService,
            "get_procedures_by_ndc_numbers",
            return_value=[given_procedure],
        ):
            # When
            processor = ScheduledFileProcessor()
            processor.process_file(smp_scheduled_file())
            treatment_plans = TreatmentProcedure.query.all()

        # Then
        assert len(treatment_plans) == 0

    def test_process_scheduled_cost_breakdown_trigger_exception(
        self,
        wallet,
        smp_scheduled_file,
        pharmacy_prescription_service,
        enterprise_user,
    ):
        # Given
        rwu = ReimbursementWalletUsersFactory.create(
            user_id=enterprise_user.id,
            reimbursement_wallet_id=wallet.id,
            status=WalletUserStatus.ACTIVE,
            type=WalletUserType.EMPLOYEE,
        )
        fertility_clinic = FertilityClinicFactory.create(name=SMP_FERTILITY_CLINIC_1)
        FertilityClinicLocationFactory.create(fertility_clinic=fertility_clinic)

        given_procedure = GlobalProcedureFactory.create(id=1, type="pharmacy")
        given_rx_unique_id = "7065817-12"
        with patch.object(
            ProcedureService,
            "get_procedures_by_ndc_numbers",
            return_value=[given_procedure],
        ), patch(
            "direct_payment.pharmacy.tasks.libs.smp_scheduled_file.trigger_cost_breakdown",
        ) as mock_cost_breakdown:
            mock_cost_breakdown.side_effect = Exception("Failed cost breakdown.")
            # When
            processor = ScheduledFileProcessor()
            processor.process_file(smp_scheduled_file())
            treatment_plans = TreatmentProcedure.query.all()
            prescription = (
                pharmacy_prescription_service.get_prescription_by_unique_id_status(
                    rx_unique_id=given_rx_unique_id
                )
            )

        # Then
        assert len(treatment_plans) == 1
        assert treatment_plans[0].cost == 4815
        assert isinstance(treatment_plans[0].start_date, datetime.date)
        assert treatment_plans[0].member_id == rwu.user_id
        assert prescription
        assert treatment_plans[0].procedure_type == TreatmentProcedureType.PHARMACY

    def test_process_scheduled_processes_with_exceptions(
        self,
        wallet,
        smp_scheduled_file,
        pharmacy_prescription_service,
        enterprise_user,
    ):
        # Given
        rwu = ReimbursementWalletUsersFactory.create(
            user_id=enterprise_user.id,
            reimbursement_wallet_id=wallet.id,
            status=WalletUserStatus.ACTIVE,
            type=WalletUserType.EMPLOYEE,
        )
        fertility_clinic = FertilityClinicFactory.create(name=SMP_FERTILITY_CLINIC_1)
        FertilityClinicLocationFactory.create(fertility_clinic=fertility_clinic)

        given_procedure = GlobalProcedureFactory.create(id=1, type="pharmacy")
        given_data = (
            "Rx Received Date,NCPDP Number,First Name,Last Name,Maven Benefit ID,NDC#,Drug Name,Drug Description,"
            "Rx Quantity,Order Number,Cash List Price,EMD Maven Coupons,SMP Maven Discounts,Other Savings,"
            "Amount Owed to SMP,SMP Patient ID,Prescribing Clinic,Rx #,Fill Number,Unique Identifier,Scheduled "
            "Ship "
            "Date\r\n2023/08/01,5710365,Jane,Doe,12345,44087-1150-01,OVIDREL 250 MCG/0.5ML SUBCUTANEOUS "
            "INJECTABLE,OVIDREL 250 MCG/0.5ML SUBCUTANEOUS INJECTABLE,1,7065817,107,0,5.35,53.5,48.15,567891,"
            "Advanced Fertility Center Of Chicago,7065817,12,7065817-12,2023/09/01"
            "Date\r\n8/1/2023,5710365,Jane,Doe,12345,44087-1150-01,OVIDREL 250 MCG/0.5ML SUBCUTANEOUS "
            "INJECTABLE,OVIDREL 250 MCG/0.5ML SUBCUTANEOUS INJECTABLE,1,7065817,107,0,5.35,53.5,48.15,567891,"
            "Advanced Fertility Center Of Chicago,7065817,12,7065817-13,09/01/2023"
        )
        with patch.object(
            ProcedureService,
            "get_procedures_by_ndc_numbers",
            return_value=[given_procedure],
        ), patch(
            "direct_payment.pharmacy.tasks.libs.smp_scheduled_file.trigger_cost_breakdown",
            return_value=True,
        ):
            # When
            processor = ScheduledFileProcessor()
            processor.process_file(smp_scheduled_file(raw_data=given_data))
            treatment_procedures = TreatmentProcedure.query.all()
            prescription = (
                pharmacy_prescription_service.get_prescription_by_unique_id_status(
                    rx_unique_id="7065817-13"
                )
            )

        # Then
        assert len(treatment_procedures) == 1
        assert treatment_procedures[0].cost == 4815
        assert isinstance(treatment_procedures[0].start_date, datetime.date)
        assert treatment_procedures[0].member_id == rwu.user_id
        assert prescription
        assert prescription.treatment_procedure_id == treatment_procedures[0].id
        assert treatment_procedures[0].procedure_type == TreatmentProcedureType.PHARMACY

    def test_process_scheduled_fails_no_effective_global_procedure(
        self,
        wallet,
        smp_scheduled_file,
        pharmacy_prescription_service,
        enterprise_user,
    ):
        # Given
        fertility_clinic = FertilityClinicFactory.create(name=SMP_FERTILITY_CLINIC_1)
        FertilityClinicLocationFactory.create(fertility_clinic=fertility_clinic)
        given_scheduled_file = smp_scheduled_file(rx_received_date="08/01/2023")
        ReimbursementWalletUsersFactory.create(
            user_id=enterprise_user.id,
            reimbursement_wallet_id=wallet.id,
            status=WalletUserStatus.ACTIVE,
            type=WalletUserType.EMPLOYEE,
        )

        with patch.object(
            ProcedureService,
            "get_procedures_by_ndc_numbers",
            return_value=[],
        ), patch(
            "direct_payment.pharmacy.tasks.libs.smp_scheduled_file.trigger_cost_breakdown",
            return_value=True,
        ):
            # When
            processor = ScheduledFileProcessor()
            processor.process_file(given_scheduled_file)
            treatment_plans = TreatmentProcedure.query.all()

        # Then
        assert len(treatment_plans) == 0
        assert processor.failed_rows == [
            ("12345", "7065817-12", "Global Procedure not found.")
        ]

    def test_process_scheduled_success_effective_global_procedure(
        self,
        wallet,
        smp_scheduled_file,
        pharmacy_prescription_service,
        enterprise_user,
    ):
        # Given
        given_rx_unique_id = "7065817-12"
        given_reimbursement_file = smp_scheduled_file(rx_received_date="08/01/2024")
        rwu = ReimbursementWalletUsersFactory.create(
            user_id=enterprise_user.id,
            reimbursement_wallet_id=wallet.id,
            status=WalletUserStatus.ACTIVE,
            type=WalletUserType.EMPLOYEE,
        )
        fertility_clinic = FertilityClinicFactory.create(name=SMP_FERTILITY_CLINIC_1)
        FertilityClinicLocationFactory.create(fertility_clinic=fertility_clinic)
        given_procedure_effective = GlobalProcedureFactory.create(
            id=1,
            name="Test",
            type="pharmacy",
            start_date=datetime.date(2024, 1, 1),
            end_date=datetime.date(2025, 12, 31),
        )

        with patch.object(
            ProcedureService,
            "get_procedures_by_ndc_numbers",
            return_value=[given_procedure_effective],
        ), patch(
            "direct_payment.pharmacy.tasks.libs.smp_scheduled_file.trigger_cost_breakdown",
            return_value=True,
        ):
            # When
            processor = ScheduledFileProcessor()
            processor.process_file(given_reimbursement_file)
            treatment_plans = TreatmentProcedure.query.all()
            prescription = (
                pharmacy_prescription_service.get_prescription_by_unique_id_status(
                    rx_unique_id=given_rx_unique_id
                )
            )
            # Then
            assert processor.failed_rows == []
            assert prescription
            assert prescription.rx_unique_id == given_rx_unique_id
            assert prescription.user_id == wallet.user_id

            assert len(treatment_plans) == 1
            assert treatment_plans[0].cost == 4815
            assert isinstance(treatment_plans[0].start_date, datetime.date)
            assert treatment_plans[0].member_id == rwu.user_id
            assert treatment_plans[0].procedure_type == TreatmentProcedureType.PHARMACY
