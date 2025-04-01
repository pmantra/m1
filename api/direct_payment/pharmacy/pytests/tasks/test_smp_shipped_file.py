import datetime
from unittest.mock import patch

from freezegun import freeze_time

from common.global_procedures.procedure import ProcedureService
from direct_payment.pharmacy.models.pharmacy_prescription import PrescriptionStatus
from direct_payment.pharmacy.tasks.libs.smp_shipped_file import ShippedFileProcessor
from direct_payment.treatment_procedure.models.treatment_procedure import (
    TreatmentProcedure,
    TreatmentProcedureStatus,
)
from direct_payment.treatment_procedure.pytests.factories import (
    TreatmentProcedureFactory,
)
from pytests.common.global_procedures.factories import GlobalProcedureFactory
from wallet.pytests.factories import ReimbursementRequestCategoryFactory


class TestSMPShippedFile:
    def test_process_shipped_success(
        self,
        smp_shipped_file,
        pharmacy_prescription_service,
        new_prescription,
    ):
        # Given
        given_prescription = new_prescription()
        rx_unique_id = given_prescription.rx_unique_id
        shipped_file = smp_shipped_file(
            unique_identifier=rx_unique_id,
            benefit_id=given_prescription.maven_benefit_id,
        )
        mock_rx_received_date_from_file = datetime.date(2023, 8, 1)

        # When
        with patch(
            "direct_payment.pharmacy.tasks.libs.smp_shipped_file.trigger_cost_breakdown",
            return_value=True,
        ):
            processor = ShippedFileProcessor()
            processor.process_file(shipped_file)
            treatment_procedures = TreatmentProcedure.query.all()
            prescription = (
                pharmacy_prescription_service.get_prescription_by_unique_id_status(
                    rx_unique_id=rx_unique_id
                )
            )
        # Then
        assert len(treatment_procedures) == 1
        assert treatment_procedures[0].status == TreatmentProcedureStatus.COMPLETED
        assert treatment_procedures[0].completed_date
        # Below shows the rx received date from the mock file is what is set for start/end date
        assert treatment_procedures[0].start_date == mock_rx_received_date_from_file
        assert treatment_procedures[0].end_date == mock_rx_received_date_from_file
        assert prescription
        assert prescription.status == PrescriptionStatus.SHIPPED
        assert prescription.shipped_json is not None

    def test_process_shipped_rx_cost_adjusted_Y(
        self, smp_shipped_file, pharmacy_prescription_service, new_prescription
    ):
        # Given
        given_prescription = new_prescription()
        rx_unique_id = given_prescription.rx_unique_id
        updated_cost = given_prescription.amount_owed + 1
        shipped_file = smp_shipped_file(
            unique_identifier=rx_unique_id,
            benefit_id=given_prescription.maven_benefit_id,
            rx_adjusted="Y",
            cost=str(updated_cost / 100),
        )

        # When
        with patch(
            "direct_payment.pharmacy.tasks.libs.smp_shipped_file.trigger_cost_breakdown",
            return_value=True,
        ):
            processor = ShippedFileProcessor()
            processor.process_file(shipped_file)
            treatment_procedures = TreatmentProcedure.query.all()
            prescription = (
                pharmacy_prescription_service.get_prescription_by_unique_id_status(
                    rx_unique_id=rx_unique_id
                )
            )

        # Then
        assert len(treatment_procedures) == 1
        assert treatment_procedures[0].status == TreatmentProcedureStatus.COMPLETED
        assert treatment_procedures[0].cost == updated_cost
        assert prescription
        assert prescription.status == PrescriptionStatus.SHIPPED
        assert prescription.shipped_json is not None
        assert prescription.amount_owed == updated_cost

    def test_process_shipped_rx_ndc_number_adjusted_Y(
        self, smp_shipped_file, pharmacy_prescription_service, new_prescription
    ):
        # Given
        given_prescription = new_prescription()
        given_new_ndc_number = "0000"
        rx_unique_id = given_prescription.rx_unique_id
        shipped_file = smp_shipped_file(
            unique_identifier=rx_unique_id,
            benefit_id=given_prescription.maven_benefit_id,
            rx_adjusted="Y",
            ndc=given_new_ndc_number,
            cost=str(given_prescription.amount_owed / 100),
        )
        given_global_procedure = GlobalProcedureFactory.create(
            id=2, name="Found Procedure", type="pharmacy"
        )
        # When
        with patch(
            "direct_payment.pharmacy.tasks.libs.smp_shipped_file.trigger_cost_breakdown",
            return_value=True,
        ), patch.object(
            ProcedureService,
            "get_procedures_by_ndc_numbers",
            return_value=[given_global_procedure],
        ):
            processor = ShippedFileProcessor()
            processor.process_file(shipped_file)
            treatment_procedures = TreatmentProcedure.query.all()
            prescription = (
                pharmacy_prescription_service.get_prescription_by_unique_id_status(
                    rx_unique_id=rx_unique_id
                )
            )
        # Then
        assert len(treatment_procedures) == 1
        assert treatment_procedures[0].status == TreatmentProcedureStatus.COMPLETED
        assert prescription.ndc_number == given_new_ndc_number
        assert prescription.status == PrescriptionStatus.SHIPPED
        assert prescription.shipped_json is not None

    def test_process_shipped_rx_ndc_number_adjusted_Y__fails(
        self, smp_shipped_file, pharmacy_prescription_service, new_prescription
    ):
        # Given
        given_prescription = new_prescription()
        given_new_ndc_number = "0000"
        rx_unique_id = given_prescription.rx_unique_id
        shipped_file = smp_shipped_file(
            unique_identifier=rx_unique_id,
            benefit_id=given_prescription.maven_benefit_id,
            rx_adjusted="Y",
            ndc=given_new_ndc_number,
            cost=str(given_prescription.amount_owed / 100),
        )

        # When
        with patch(
            "direct_payment.pharmacy.tasks.libs.smp_shipped_file.trigger_cost_breakdown",
            return_value=True,
        ), patch.object(
            ProcedureService,
            "get_procedures_by_ndc_numbers",
            return_value=[],
        ), patch.object(
            ProcedureService,
            "get_procedure_by_id",
            return_value=None,
        ), patch.object(
            ProcedureService, "create_global_procedure", return_value=None
        ):
            processor = ShippedFileProcessor()
            processor.process_file(shipped_file)
            treatment_procedures = TreatmentProcedure.query.all()
            prescription = (
                pharmacy_prescription_service.get_prescription_by_unique_id_status(
                    rx_unique_id=rx_unique_id
                )
            )

        # Then
        assert len(treatment_procedures) == 1
        assert treatment_procedures[0].status == TreatmentProcedureStatus.SCHEDULED
        assert prescription.status == PrescriptionStatus.SCHEDULED
        assert prescription.shipped_json is None

    def test_process_shipped_rx_adjusted_N(
        self, smp_shipped_file, pharmacy_prescription_service, new_prescription
    ):
        # Given
        given_prescription = new_prescription()
        scheduled_cost = given_prescription.amount_owed
        rx_unique_id = given_prescription.rx_unique_id
        shipped_file = smp_shipped_file(
            unique_identifier=rx_unique_id,
            benefit_id=given_prescription.maven_benefit_id,
        )
        # When
        with patch(
            "direct_payment.pharmacy.tasks.libs.smp_shipped_file.trigger_cost_breakdown",
            return_value=True,
        ):
            processor = ShippedFileProcessor()
            processor.process_file(shipped_file)
            treatment_procedures = TreatmentProcedure.query.all()
            prescription = (
                pharmacy_prescription_service.get_prescription_by_unique_id_status(
                    rx_unique_id=rx_unique_id
                )
            )
        # Then
        assert len(treatment_procedures) == 1
        assert treatment_procedures[0].status == TreatmentProcedureStatus.COMPLETED
        assert treatment_procedures[0].cost == scheduled_cost
        assert prescription
        assert prescription.status == PrescriptionStatus.SHIPPED
        assert prescription.shipped_json is not None
        assert prescription.amount_owed == scheduled_cost

    def test_process_shipped_file_dry(self, smp_shipped_file):
        # Given/When
        processor = ShippedFileProcessor(dry_run=True)
        processor.process_file(smp_shipped_file())
        treatment_plans = TreatmentProcedure.query.all()

        # Then
        assert len(treatment_plans) == 0

    def test_process_shipped_fails_file_validation(
        self,
        smp_shipped_file,
        pharmacy_prescription_service,
        new_prescription,
    ):
        # Given
        given_prescription = new_prescription()
        rx_unique_id = given_prescription.rx_unique_id
        shipped_file = smp_shipped_file(unique_identifier="")

        # When
        processor = ShippedFileProcessor()
        processor.process_file(shipped_file)
        treatment_procedures = TreatmentProcedure.query.all()
        prescription = (
            pharmacy_prescription_service.get_prescription_by_unique_id_status(
                rx_unique_id=rx_unique_id
            )
        )
        # Then
        assert len(treatment_procedures) == 1
        assert treatment_procedures[0].status == TreatmentProcedureStatus.SCHEDULED
        assert prescription
        assert prescription.status == PrescriptionStatus.SCHEDULED
        assert prescription.shipped_json is None

    def test_process_shipped_file_wrong_benefit_ids(
        self,
        smp_shipped_file,
        pharmacy_prescription_service,
        new_prescription,
    ):
        # Given
        given_prescription = new_prescription()
        rx_unique_id = given_prescription.rx_unique_id
        shipped_file = smp_shipped_file(unique_identifier=rx_unique_id)

        # When
        processor = ShippedFileProcessor()
        processor.process_file(shipped_file)
        treatment_procedures = TreatmentProcedure.query.all()
        prescription = (
            pharmacy_prescription_service.get_prescription_by_unique_id_status(
                rx_unique_id=rx_unique_id
            )
        )

        # Then
        assert len(treatment_procedures) == 1
        assert treatment_procedures[0].status == TreatmentProcedureStatus.SCHEDULED
        assert prescription
        assert prescription.status == PrescriptionStatus.SCHEDULED
        assert prescription.shipped_json is None

    def test_process_shipped_no_prescription(
        self, smp_shipped_file, pharmacy_prescription_service
    ):
        # Given
        shipped_file = smp_shipped_file()

        # When
        processor = ShippedFileProcessor()
        processor.process_file(shipped_file)
        treatment_procedures = TreatmentProcedure.query.all()
        prescription = (
            pharmacy_prescription_service.get_prescription_by_unique_id_status(
                rx_unique_id="7065817-12"
            )
        )
        # Then
        assert len(treatment_procedures) == 0
        assert prescription is None

    def test_process_shipped_prescription_canceled(
        self, smp_shipped_file, pharmacy_prescription_service, new_prescription
    ):
        # Given
        given_prescription = new_prescription(status=PrescriptionStatus.CANCELLED)

        rx_unique_id = given_prescription.rx_unique_id
        shipped_file = smp_shipped_file(
            unique_identifier=rx_unique_id,
            benefit_id=given_prescription.maven_benefit_id,
        )

        # When
        processor = ShippedFileProcessor()
        processor.process_file(shipped_file)
        treatment_procedures = TreatmentProcedure.query.all()
        prescription = (
            pharmacy_prescription_service.get_prescription_by_unique_id_status(
                rx_unique_id=rx_unique_id,
            )
        )
        # Then
        assert len(treatment_procedures) == 1
        assert treatment_procedures[0].status == TreatmentProcedureStatus.SCHEDULED
        assert prescription.status == PrescriptionStatus.CANCELLED

    def test_process_shipped_cost_breakdown_trigger_exception(
        self,
        smp_shipped_file,
        pharmacy_prescription_service,
        new_prescription,
    ):
        # Given
        given_prescription = new_prescription()
        rx_unique_id = given_prescription.rx_unique_id
        shipped_file = smp_shipped_file(
            unique_identifier=rx_unique_id,
            benefit_id=given_prescription.maven_benefit_id,
        )

        # When
        with patch(
            "direct_payment.pharmacy.tasks.libs.smp_shipped_file.trigger_cost_breakdown",
        ) as mock_cost_breakdown:
            mock_cost_breakdown.side_effect = Exception("Cost breakdown failure.")
            processor = ShippedFileProcessor()
            processor.process_file(shipped_file)
            treatment_procedures = TreatmentProcedure.query.all()
            prescription = (
                pharmacy_prescription_service.get_prescription_by_unique_id_status(
                    rx_unique_id=rx_unique_id
                )
            )
        # Then
        assert len(treatment_procedures) == 1
        assert treatment_procedures[0].status == TreatmentProcedureStatus.COMPLETED
        assert prescription
        assert prescription.status == PrescriptionStatus.SHIPPED
        assert prescription.shipped_json is not None

    def test_process_shipped_process_with_exceptions(
        self,
        smp_shipped_file,
        pharmacy_prescription_service,
        multiple_prescriptions,
    ):
        # Given
        rxs = multiple_prescriptions
        for rx in rxs:
            rx.status = PrescriptionStatus.SCHEDULED
            pharmacy_prescription_service.update_pharmacy_prescription(instance=rx)

        data = (
            "Rx Received Date,NCPDP Number,First Name,Last Name,Maven Benefit ID,NDC#,Drug Name,Drug Description,"
            "Rx Quantity,Order Number,Cash List Price,EMD Maven Coupons,SMP Maven Discounts,Other Savings,"
            "Amount Owed to SMP,SMP Patient ID,Prescribing Clinic,Rx #,Fill Number,Unique Identifier,Scheduled "
            "Ship Date,Rx Adjusted,Actual Ship Date"
            f"\r\n8/1/2023,5710365,Jane,Doe,{rxs[0].maven_benefit_id},44087-1150-01,OVIDREL 250 MCG/0.5ML SUBCUTANEOUS "
            "INJECTABLE,OVIDREL 250 MCG/0.5ML SUBCUTANEOUS INJECTABLE,1,7065817,107,0,5.35,53.5,48.15,567891,"
            f"Advanced Fertility Center Of Chicago,7065817,12,{rxs[0].rx_unique_id},09/02/2023,N,2023/09/01"
            f"\r\n8/1/2023,5710365,Jane,Doe,{rxs[1].maven_benefit_id},44087-1150-01,OVIDREL 250 MCG/0.5ML SUBCUTANEOUS "
            "INJECTABLE,OVIDREL 250 MCG/0.5ML SUBCUTANEOUS INJECTABLE,1,7065817,107,0,5.35,53.5,48.15,567891,"
            f"Advanced Fertility Center Of Chicago,7065817,12,{rxs[1].rx_unique_id},09/02/2023,N,09/03/2023"
            f"\r\n8/1/2023,5710365,Jane,Doe,{rxs[2].maven_benefit_id},44087-1150-01,OVIDREL 250 MCG/0.5ML SUBCUTANEOUS "
            "INJECTABLE,OVIDREL 250 MCG/0.5ML SUBCUTANEOUS INJECTABLE,1,7065817,107,0,5.35,53.5,48.15,567891,"
            f"Advanced Fertility Center Of Chicago,7065817,12,{rxs[2].rx_unique_id},09/02/2023,N,09/03/2023"
        )
        shipped_file = smp_shipped_file(raw_data=data)
        # When
        with patch(
            "direct_payment.pharmacy.tasks.libs.smp_shipped_file.trigger_cost_breakdown",
            return_value=True,
        ):
            processor = ShippedFileProcessor()
            processor.process_file(shipped_file)
            treatment_procedures = TreatmentProcedure.query.all()
            prescription_one = (
                pharmacy_prescription_service.get_prescription_by_unique_id_status(
                    rx_unique_id=rxs[0].rx_unique_id
                )
            )
            prescription_two = (
                pharmacy_prescription_service.get_prescription_by_unique_id_status(
                    rx_unique_id=rxs[1].rx_unique_id
                )
            )
            prescription_three = (
                pharmacy_prescription_service.get_prescription_by_unique_id_status(
                    rx_unique_id=rxs[2].rx_unique_id
                )
            )
        # Then
        assert len(treatment_procedures) == 3
        assert prescription_one.status == PrescriptionStatus.SCHEDULED
        assert prescription_one.shipped_json is None
        assert prescription_two.status == PrescriptionStatus.SHIPPED
        assert prescription_two.shipped_json is not None
        assert prescription_three.status == PrescriptionStatus.SHIPPED
        assert prescription_three.shipped_json is not None

    def test_process_shipped_fails_no_effective_global_procedure(
        self,
        smp_shipped_file,
        pharmacy_prescription_service,
        new_prescription,
    ):
        # Given
        given_prescription = new_prescription()
        given_new_ndc_number = "0000"
        rx_unique_id = given_prescription.rx_unique_id
        shipped_file = smp_shipped_file(
            unique_identifier=rx_unique_id,
            benefit_id=given_prescription.maven_benefit_id,
            rx_adjusted="Y",
            ndc=given_new_ndc_number,
            cost=str(given_prescription.amount_owed / 100),
            rx_received_date="08/01/2024",
        )

        # When
        with patch(
            "direct_payment.pharmacy.tasks.libs.smp_shipped_file.trigger_cost_breakdown",
            return_value=True,
        ), patch.object(
            ProcedureService,
            "get_procedures_by_ndc_numbers",
            return_value=[],
        ), patch.object(
            ProcedureService,
            "get_procedure_by_id",
            return_value=None,
        ), patch.object(
            ProcedureService, "create_global_procedure", return_value=None
        ):
            processor = ShippedFileProcessor()
            processor.process_file(shipped_file)
            treatment_procedures = TreatmentProcedure.query.all()
            prescription = (
                pharmacy_prescription_service.get_prescription_by_unique_id_status(
                    rx_unique_id=rx_unique_id
                )
            )
        # Then
        assert processor.failed_rows == [
            (
                given_prescription.maven_benefit_id,
                "11225658-7065817-0",
                "Failed to update record with new Global Procedure.",
            )
        ]
        assert len(treatment_procedures) == 1
        assert treatment_procedures[0].status == TreatmentProcedureStatus.SCHEDULED
        assert treatment_procedures[0].completed_date is None
        assert prescription
        assert prescription.status == PrescriptionStatus.SCHEDULED
        assert prescription.shipped_json is None

    def test_process_shipped_success_effective_global_procedure(
        self,
        smp_shipped_file,
        pharmacy_prescription_service,
        new_prescription,
    ):
        # Given
        given_prescription = new_prescription()
        given_new_ndc_number = "0000"
        rx_unique_id = given_prescription.rx_unique_id
        shipped_file = smp_shipped_file(
            unique_identifier=rx_unique_id,
            benefit_id=given_prescription.maven_benefit_id,
            rx_adjusted="Y",
            ndc=given_new_ndc_number,
            cost=str(given_prescription.amount_owed / 100),
            rx_received_date="08/01/2024",
        )
        given_procedure_effective = GlobalProcedureFactory.create(
            id=1,
            name="Test",
            type="pharmacy",
            start_date=datetime.date(2024, 1, 1),
            end_date=datetime.date(2025, 12, 31),
        )

        # When
        with patch(
            "direct_payment.pharmacy.tasks.libs.smp_shipped_file.trigger_cost_breakdown",
            return_value=True,
        ), patch.object(
            ProcedureService,
            "get_procedures_by_ndc_numbers",
            return_value=[given_procedure_effective],
        ), patch.object(
            ProcedureService,
            "get_procedure_by_id",
            return_value=None,
        ), patch.object(
            ProcedureService, "create_global_procedure", return_value=None
        ):
            processor = ShippedFileProcessor()
            processor.process_file(shipped_file)
            treatment_procedures = TreatmentProcedure.query.all()
            prescription = (
                pharmacy_prescription_service.get_prescription_by_unique_id_status(
                    rx_unique_id=rx_unique_id
                )
            )
        # Then
        assert len(treatment_procedures) == 1
        assert treatment_procedures[0].status == TreatmentProcedureStatus.COMPLETED
        assert treatment_procedures[0].completed_date
        assert prescription
        assert prescription.status == PrescriptionStatus.SHIPPED
        assert prescription.shipped_json

    @freeze_time("2024-01-01 12:00:00")
    def test_get_next_timestamp_initial_row(self):
        # Given
        processor = ShippedFileProcessor()
        # When
        timestamp = processor.get_next_timestamp()
        # Then
        assert timestamp == datetime.datetime(
            2024, 1, 1, 12, 0, 0, tzinfo=datetime.timezone.utc
        )

    @freeze_time("2024-01-01 12:00:00")
    def test_get_next_timestamp_sequential(self):
        # Given
        processor = ShippedFileProcessor()
        # When
        first = processor.get_next_timestamp()
        second = processor.get_next_timestamp()
        third = processor.get_next_timestamp()

        # Then
        assert first < second < third
        assert second == datetime.datetime(
            2024, 1, 1, 12, 0, 1, tzinfo=datetime.timezone.utc
        )
        assert third == datetime.datetime(
            2024, 1, 1, 12, 0, 2, tzinfo=datetime.timezone.utc
        )

    def test_get_next_timestamp_across_time_boundary(self):
        # Given
        processor = ShippedFileProcessor()
        with freeze_time("2024-01-01 12:00:00") as frozen_time:
            # When
            first = processor.get_next_timestamp()
            second = processor.get_next_timestamp()

            frozen_time.tick(delta=datetime.timedelta(seconds=1))
            third = processor.get_next_timestamp()

            # Then
            assert (second - first).seconds == 1
            assert third == datetime.datetime(
                2024, 1, 1, 12, 0, 2, tzinfo=datetime.timezone.utc
            )

    @freeze_time("2024-01-01 12:00:00")
    def test_treatment_procedure_completion_timestamps(self, new_prescription):
        # Given
        processor = ShippedFileProcessor()
        prescription1 = new_prescription()
        category = ReimbursementRequestCategoryFactory.create(label="fertility")
        treatment_procedure_2 = TreatmentProcedureFactory.create(
            reimbursement_request_category=category
        )
        prescription2 = new_prescription(
            unique_id="test_unique_id", treatment_procedure_id=treatment_procedure_2.id
        )

        base_row = {
            "Maven Benefit ID": "123456",
            "Amount Owed to SMP": "48.00",
            "Unique Identifier": "7065817-12",
            "Actual Ship Date": "01/01/2024",
            "Rx Adjusted": "N",
            "NDC#": "12345678901",
            "Drug Name": "Test Drug",
            "Drug Description": "Test Description",
            "Scheduled Ship Date": "01/01/2024",
            "Rx Received Date": "01/01/2024",
        }

        row1 = {
            **base_row,
            "Maven Benefit ID": prescription1.maven_benefit_id,
            "Unique Identifier": prescription1.rx_unique_id,
        }
        row2 = {
            **base_row,
            "Maven Benefit ID": prescription2.maven_benefit_id,
            "Unique Identifier": "test_unique_id",
        }

        with patch.object(
            processor, "get_valid_pharmacy_prescription_from_file"
        ) as mock_get_rx, patch(
            "direct_payment.pharmacy.tasks.libs.smp_shipped_file.trigger_cost_breakdown",
            return_value=True,
        ):
            mock_get_rx.side_effect = [prescription1, prescription2]
            # When
            processor.handle_row(row1)
            processor.handle_row(row2)

            treatment_procedures = TreatmentProcedure.query.order_by(
                TreatmentProcedure.completed_date
            ).all()
            # Then
            assert len(treatment_procedures) == 2
            assert treatment_procedures[0].completed_date == datetime.datetime(
                2024, 1, 1, 12, 0, 0, tzinfo=datetime.timezone.utc
            )
            assert treatment_procedures[1].completed_date == datetime.datetime(
                2024, 1, 1, 12, 0, 1, tzinfo=datetime.timezone.utc
            )
