import pytest

from direct_payment.pharmacy.models.pharmacy_prescription import PrescriptionStatus
from direct_payment.pharmacy.pytests import factories
from wallet.pytests.factories import ReimbursementRequestFactory


class TestPharmacyPrescriptionRepositoryBase:
    def test_create_pharmacy_prescription(
        self, pharmacy_prescription_repository, treatment_procedure, enterprise_user
    ):
        # Given
        prescription = factories.PharmacyPrescriptionFactory(
            treatment_procedure_id=treatment_procedure.id, user_id=enterprise_user.id
        )
        # When
        created = pharmacy_prescription_repository.create(instance=prescription)
        # Then
        assert created.id

    def test_update_pharmacy_prescription(
        self, pharmacy_prescription_repository, new_prescription
    ):
        # Given
        updated_shipped_json = {
            "Rx Received Date": "8/1/2023",
            "NCPDP Number": "42",
            "Patient Name": "Brittany Ibarra",
            "Maven Member ID": "554691",
            "NDC#": "44087-1150-01",
            "Drug Name": "OVIDREL 250 MCG/0.5ML SUBCUTANEOUS INJECTABLE",
            "Drug Description": "OVIDREL 250 MCG/0.5ML SUBCUTANEOUS INJECTABLE",
            "Rx Quantity": " 1",
            "Rx #": "12",
            "Order Number": " 107",
            "Cash List Price": "0",
            "EMD Maven Coupons": "5.35",
            "SMP Maven Discounts": "53.5",
            "Other Savings": "48.15",
            "Amount Owed to SMP": "567891",
            "SMP Patient ID": "Advanced Fertility Center Of Chicago",
            "Prescribing Clinic": "7065817",
            "Fill Number": "7065817-12",
            "Unique Identifier": "09/01/2023",
            "Actual Ship Date": "8/2/2023",
        }
        given_prescription = new_prescription()
        given_prescription.shipped_json = updated_shipped_json

        # When
        created = pharmacy_prescription_repository.update(instance=given_prescription)
        # Then
        assert created.id
        assert created.shipped_json == updated_shipped_json

    def test_get_pharmacy_prescription(
        self, pharmacy_prescription_repository, new_prescription
    ):
        # Given/When
        given_prescription = new_prescription()
        retrieved = pharmacy_prescription_repository.get(id=given_prescription.id)

        # Then
        assert retrieved == given_prescription

    def test_get_no_pharmacy_prescription(self, pharmacy_prescription_repository):
        retrieved = pharmacy_prescription_repository.get(id=-1)
        assert retrieved is None


class TestPharmacyPrescriptionRepositoryByRxUniqueId:
    def test_get_by_rx_unique_id_only(
        self,
        pharmacy_prescription_repository,
        multiple_prescriptions,
    ):
        # Given/When
        prescription = pharmacy_prescription_repository.get_by_rx_unique_id(
            rx_unique_id="test_1"
        )
        # Then
        assert prescription

    def test_get_by_rx_unique_id_only_not_found(
        self,
        pharmacy_prescription_repository,
        multiple_prescriptions,
    ):
        # Given/When
        prescription = pharmacy_prescription_repository.get_by_rx_unique_id(
            rx_unique_id="unknown"
        )
        # Then
        assert prescription is None

    @pytest.mark.parametrize(
        argnames="status, rx_unique_id",
        argvalues=(
            # Scheduled
            (PrescriptionStatus.SCHEDULED, "test_1"),
            # Shipped
            (PrescriptionStatus.SHIPPED, "test_2"),
            # Cancelled
            (PrescriptionStatus.CANCELLED, "test_3"),
        ),
    )
    def test_get_by_rx_unique_and_status(
        self,
        pharmacy_prescription_repository,
        multiple_prescriptions,
        status,
        rx_unique_id,
    ):
        # Given/When
        prescription = pharmacy_prescription_repository.get_by_rx_unique_id(
            rx_unique_id=rx_unique_id, status=status
        )
        # Then
        assert prescription

    def test_get_by_rx_unique_and_status_not_found(
        self,
        pharmacy_prescription_repository,
        multiple_prescriptions,
    ):
        # Given/When
        prescription = pharmacy_prescription_repository.get_by_rx_unique_id(
            rx_unique_id="test_1", status=PrescriptionStatus.CANCELLED
        )
        # Then
        assert prescription is None


class TestGetPrescriptionByReimbursementRequest:
    def test_get_by_reimbursement_request_ids(
        self, pharmacy_prescription_repository, new_prescription, wallet
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
        # When
        prescription = (
            pharmacy_prescription_repository.get_by_reimbursement_request_ids(
                reimbursement_request_ids=[rr.id]
            )
        )
        assert prescription[0] == given_prescription

    def test_get_by_reimbursement_request_ids_not_found(
        self,
        pharmacy_prescription_repository,
    ):
        # Given/When
        prescription = (
            pharmacy_prescription_repository.get_by_reimbursement_request_ids(
                reimbursement_request_ids=["987654"]
            )
        )
        assert prescription == []
