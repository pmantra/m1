from unittest import mock

from direct_payment.pharmacy.models.pharmacy_prescription import (
    PharmacyPrescription,
    PrescriptionStatus,
)
from utils.payments import convert_dollars_to_cents
from wallet.pytests.factories import ReimbursementRequestFactory


class TestPharmacyPrescriptionCreation:
    def test_create_pharmacy_prescription(
        self,
        pharmacy_prescription_service,
        treatment_procedure,
        enterprise_user,
        raw_prescription_data,
    ):
        # Given
        cost = convert_dollars_to_cents(
            float(raw_prescription_data["Amount Owed to SMP"])
        )
        pharmacy_prescription = PharmacyPrescription(
            treatment_procedure_id=treatment_procedure.id,
            user_id=enterprise_user.id,
            rx_unique_id=raw_prescription_data["Unique Identifier"],
            maven_benefit_id=raw_prescription_data["Maven Benefit ID"],
            amount_owed=cost,
            ncpdp_number=raw_prescription_data["NCPDP Number"],
            ndc_number=raw_prescription_data["NDC#"],
            rx_name=raw_prescription_data["Drug Name"],
            rx_description=raw_prescription_data["Drug Description"],
            rx_first_name=raw_prescription_data["First Name"],
            rx_last_name=raw_prescription_data["Last Name"],
            rx_order_id=raw_prescription_data["Order Number"],
            rx_received_date=raw_prescription_data["Rx Received Date"],
            scheduled_ship_date=raw_prescription_data["Scheduled Ship Date"],
            scheduled_json=raw_prescription_data,
            status=PrescriptionStatus.SCHEDULED,
        )
        # When
        result = pharmacy_prescription_service.create_pharmacy_prescription(
            instance=pharmacy_prescription
        )

        # Then
        assert result.id is not None
        assert result.treatment_procedure_id is not None
        assert result.shipped_json is None
        assert result.cancelled_json is None
        assert result.status == PrescriptionStatus.SCHEDULED
        assert result.scheduled_json == raw_prescription_data


class TestPharmacyPrescriptionUpdates:
    def test_update_pharmacy_prescription(
        self, pharmacy_prescription_service, new_prescription, raw_prescription_data
    ):
        # Given
        updated_prescription = new_prescription()
        updated_prescription.status = PrescriptionStatus.SHIPPED
        updated_prescription.actual_ship_date = raw_prescription_data[
            "Actual Ship Date"
        ]
        updated_prescription.shipped_json = raw_prescription_data
        expected_update_prescription_args = {"instance": updated_prescription}
        # When
        with mock.patch(
            "direct_payment.pharmacy.pharmacy_prescription_service.PharmacyPrescriptionRepository"
            ".update",
            return_value=updated_prescription,
        ):
            result = pharmacy_prescription_service.update_pharmacy_prescription(
                instance=updated_prescription
            )
            actual_update_prescription_args = (
                pharmacy_prescription_service.pharmacy_prescription_repo.update.call_args.kwargs
            )

        # Then
        assert result.id == updated_prescription.id
        assert result.shipped_json == raw_prescription_data
        assert result.scheduled_json == raw_prescription_data
        assert result.cancelled_json is None
        assert result.status == PrescriptionStatus.SHIPPED
        assert result.actual_ship_date is not None
        assert result.cancelled_date is None
        assert expected_update_prescription_args == actual_update_prescription_args


class TestPharmacyPrescriptionQueries:
    def test_get_no_prescriptions_by_unique_id(self, pharmacy_prescription_service):
        # When/Given
        with mock.patch(
            "direct_payment.pharmacy.pharmacy_prescription_service.PharmacyPrescriptionRepository.get_by_rx_unique_id",
            return_value=None,
        ):
            res = pharmacy_prescription_service.get_prescription_by_unique_id_status(
                rx_unique_id=1, status=PrescriptionStatus.CANCELLED
            )
            # Then
            assert res is None

    def test_get_prescriptions_by_unique_id_and_status(
        self, pharmacy_prescription_service, new_prescription
    ):
        # Given
        given_prescription = new_prescription()
        expected_get_prescription_args = {
            "rx_unique_id": given_prescription.rx_unique_id,
            "status": PrescriptionStatus.SCHEDULED,
        }
        # When
        with mock.patch(
            "direct_payment.pharmacy.pharmacy_prescription_service.PharmacyPrescriptionRepository"
            ".get_by_rx_unique_id",
            return_value=given_prescription,
        ) as mock_get_prescription:
            res = pharmacy_prescription_service.get_prescription_by_unique_id_status(
                rx_unique_id=given_prescription.rx_unique_id,
                status=PrescriptionStatus.SCHEDULED,
            )
            actual_get_prescription_args = (
                pharmacy_prescription_service.pharmacy_prescription_repo.get_by_rx_unique_id.call_args.kwargs
            )
            # Then
            assert res
            assert mock_get_prescription.called
            assert expected_get_prescription_args == actual_get_prescription_args

    def test_get_prescriptions_by_unique_id(
        self, pharmacy_prescription_service, new_prescription
    ):
        # Given
        given_prescription = new_prescription()
        expected_get_prescription_args = {
            "rx_unique_id": given_prescription.rx_unique_id,
            "status": None,
        }
        # When
        with mock.patch(
            "direct_payment.pharmacy.pharmacy_prescription_service.PharmacyPrescriptionRepository"
            ".get_by_rx_unique_id",
            return_value=given_prescription,
        ) as mock_get_prescription:
            res = pharmacy_prescription_service.get_prescription_by_unique_id_status(
                rx_unique_id=given_prescription.rx_unique_id
            )
            actual_get_prescription_args = (
                pharmacy_prescription_service.pharmacy_prescription_repo.get_by_rx_unique_id.call_args.kwargs
            )
            # Then
            assert res
            assert mock_get_prescription.called
            assert expected_get_prescription_args == actual_get_prescription_args

    def test_get_prescriptions_by_reimbursement_request_id(
        self, pharmacy_prescription_service, new_prescription, wallet
    ):
        # Given
        category_association = (
            wallet.reimbursement_organization_settings.allowed_reimbursement_categories[
                0
            ]
        )
        category = category_association.reimbursement_request_category
        rr = ReimbursementRequestFactory.create(
            reimbursement_wallet_id=wallet.id,
            reimbursement_request_category_id=category.id,
        )
        given_prescription = new_prescription(reimbursement_request_id=rr.id)
        expected_get_prescription_args = {"reimbursement_request_ids": {rr.id}}
        # When
        with mock.patch(
            "direct_payment.pharmacy.pharmacy_prescription_service.PharmacyPrescriptionRepository"
            ".get_by_reimbursement_request_ids",
            return_value=given_prescription,
        ) as mock_get_prescription:
            res = pharmacy_prescription_service.get_by_reimbursement_request_ids(
                reimbursement_request_ids={rr.id}
            )
            actual_get_prescription_args = (
                pharmacy_prescription_service.pharmacy_prescription_repo.get_by_reimbursement_request_ids.call_args.kwargs
            )
            # Then
            assert res
            assert mock_get_prescription.called
            assert expected_get_prescription_args == actual_get_prescription_args
