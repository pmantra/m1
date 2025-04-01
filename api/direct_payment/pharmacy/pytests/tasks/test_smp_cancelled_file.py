from unittest.mock import patch

from direct_payment.pharmacy.models.pharmacy_prescription import PrescriptionStatus
from direct_payment.pharmacy.tasks.libs.smp_cancelled_file import CancelledFileProcessor
from direct_payment.treatment_procedure.models.treatment_procedure import (
    TreatmentProcedure,
    TreatmentProcedureStatus,
)


class TestSMPCancelledFile:
    def test_process_cancelled_success(
        self,
        wallet,
        smp_cancelled_file,
        pharmacy_prescription_service,
        new_prescription,
    ):
        # Given
        given_prescription = new_prescription()
        rx_unique_id = given_prescription.rx_unique_id
        given_cancelled_file = smp_cancelled_file(
            unique_identifier=rx_unique_id,
            benefit_id=given_prescription.maven_benefit_id,
        )

        # When
        with patch(
            "direct_payment.pharmacy.tasks.libs.smp_cancelled_file.trigger_cost_breakdown",
            return_value=True,
        ):
            processor = CancelledFileProcessor()
            processor.process_file(given_cancelled_file)
            treatment_procedures = TreatmentProcedure.query.all()
            prescription = (
                pharmacy_prescription_service.get_prescription_by_unique_id_status(
                    rx_unique_id=rx_unique_id
                )
            )

        # Then
        assert len(treatment_procedures) == 1
        assert treatment_procedures[0].status == TreatmentProcedureStatus.CANCELLED
        assert treatment_procedures[0].cancelled_date
        assert prescription
        assert prescription.status == PrescriptionStatus.CANCELLED
        assert prescription.cancelled_json is not None

    def test_process_cancelled_file_dry(self, smp_cancelled_file):
        # Given/When
        processor = CancelledFileProcessor(dry_run=True)
        processor.process_file(smp_cancelled_file())
        treatment_plans = TreatmentProcedure.query.all()

        # Then
        assert len(treatment_plans) == 0

    def test_process_cancelled_fails_file_validation(
        self,
        wallet,
        smp_cancelled_file,
        pharmacy_prescription_service,
        new_prescription,
    ):
        # Given
        given_prescription = new_prescription()
        rx_unique_id = given_prescription.rx_unique_id
        cancelled_file = smp_cancelled_file(unique_identifier="")

        # When
        processor = CancelledFileProcessor()
        processor.process_file(cancelled_file)
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
        assert prescription.cancelled_json is None

    def test_process_cancelled_file_wrong_benefit_ids(
        self,
        wallet,
        smp_cancelled_file,
        pharmacy_prescription_service,
        new_prescription,
    ):
        # Given
        given_prescription = new_prescription()
        rx_unique_id = given_prescription.rx_unique_id
        cancelled_file = smp_cancelled_file(unique_identifier=rx_unique_id)

        # When
        processor = CancelledFileProcessor()
        processor.process_file(cancelled_file)
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
        assert prescription.cancelled_json is None

    def test_process_cancelled_no_prescription(
        self, wallet, smp_cancelled_file, pharmacy_prescription_service
    ):
        # Given/When
        processor = CancelledFileProcessor()
        processor.process_file(smp_cancelled_file())
        treatment_procedures = TreatmentProcedure.query.all()
        prescription = (
            pharmacy_prescription_service.get_prescription_by_unique_id_status(
                rx_unique_id="7065817-12"
            )
        )
        # Then
        assert len(treatment_procedures) == 0
        assert prescription is None

    def test_process_cancelled_prescription_canceled(
        self,
        wallet,
        smp_cancelled_file,
        pharmacy_prescription_service,
        new_prescription,
    ):
        # Given
        given_prescription = new_prescription(status=PrescriptionStatus.CANCELLED)

        rx_unique_id = given_prescription.rx_unique_id
        cancelled_file = smp_cancelled_file(
            unique_identifier=rx_unique_id,
            benefit_id=given_prescription.maven_benefit_id,
        )

        # When
        processor = CancelledFileProcessor()
        processor.process_file(cancelled_file)
        prescription = (
            pharmacy_prescription_service.get_prescription_by_unique_id_status(
                rx_unique_id=rx_unique_id,
            )
        )
        # Then
        assert prescription.status == PrescriptionStatus.CANCELLED

    def test_process_cancelled_cost_breakdown_failed(
        self,
        wallet,
        smp_cancelled_file,
        pharmacy_prescription_service,
        new_prescription,
    ):
        # Given
        given_prescription = new_prescription()
        rx_unique_id = given_prescription.rx_unique_id
        given_cancelled_file = smp_cancelled_file(
            unique_identifier=rx_unique_id,
            benefit_id=given_prescription.maven_benefit_id,
        )

        # When
        with patch(
            "direct_payment.pharmacy.tasks.libs.smp_cancelled_file.trigger_cost_breakdown",
        ) as mock_cost_breakdown:
            mock_cost_breakdown.side_effect = Exception("cost breakdown failure")
            processor = CancelledFileProcessor()
            processor.process_file(given_cancelled_file)
            treatment_procedures = TreatmentProcedure.query.all()
            prescription = (
                pharmacy_prescription_service.get_prescription_by_unique_id_status(
                    rx_unique_id=rx_unique_id
                )
            )

        # Then
        assert len(treatment_procedures) == 1
        assert treatment_procedures[0].status == TreatmentProcedureStatus.CANCELLED
        assert treatment_procedures[0].cancelled_date
        assert prescription
        assert prescription.status == PrescriptionStatus.CANCELLED
        assert prescription.cancelled_json is not None

    def test_process_cancelled_processes_with_exceptions(
        self,
        wallet,
        smp_cancelled_file,
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
            "Ship Date,Rx Canceled Date"
            f"\r\n8/1/2023,5710365,Jane,Doe,{rxs[0].maven_benefit_id},44087-1150-01,OVIDREL 250 MCG/0.5ML SUBCUTANEOUS "
            "INJECTABLE,OVIDREL 250 MCG/0.5ML SUBCUTANEOUS INJECTABLE,1,7065817,107,0,5.35,53.5,48.15,567891,"
            f"Advanced Fertility Center Of Chicago,7065817,12,{rxs[0].rx_unique_id},09/02/2023,2023/09/01"
            f"\r\n8/1/2023,5710365,Jane,Doe,{rxs[1].maven_benefit_id},44087-1150-01,OVIDREL 250 MCG/0.5ML SUBCUTANEOUS "
            "INJECTABLE,OVIDREL 250 MCG/0.5ML SUBCUTANEOUS INJECTABLE,1,7065817,107,0,5.35,53.5,48.15,567891,"
            f"Advanced Fertility Center Of Chicago,7065817,12,{rxs[1].rx_unique_id},09/02/2023,09/03/2023"
            f"\r\n8/1/2023,5710365,Jane,Doe,{rxs[2].maven_benefit_id},44087-1150-01,OVIDREL 250 MCG/0.5ML SUBCUTANEOUS "
            "INJECTABLE,OVIDREL 250 MCG/0.5ML SUBCUTANEOUS INJECTABLE,1,7065817,107,0,5.35,53.5,48.15,567891,"
            f"Advanced Fertility Center Of Chicago,7065817,12,{rxs[2].rx_unique_id},09/02/2023,09/03/2023"
        )
        given_cancelled_file = smp_cancelled_file(raw_data=data)
        # When
        with patch(
            "direct_payment.pharmacy.tasks.libs.smp_cancelled_file.trigger_cost_breakdown",
            return_value=True,
        ):
            processor = CancelledFileProcessor()
            processor.process_file(given_cancelled_file)
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
        assert prescription_one.cancelled_json is None
        assert prescription_two.status == PrescriptionStatus.CANCELLED
        assert prescription_two.cancelled_json is not None
        assert prescription_three.status == PrescriptionStatus.CANCELLED
        assert prescription_three.cancelled_json is not None
