import uuid
from unittest import mock

import factory
import pytest

from cost_breakdown.pytests.factories import CostBreakdownFactory
from direct_payment.billing import models
from direct_payment.billing.billing_admin import (
    BillingAdminService,
    BillValidationException,
    ClinicReverseTransferCreationException,
    ClinicReverseTransferProcessingException,
)
from direct_payment.billing.models import BillStatus, PayorType
from direct_payment.billing.pytests.factories import (
    BillFactory,
    BillProcessingRecordFactory,
)
from direct_payment.treatment_procedure.models.treatment_procedure import (
    TreatmentProcedureStatus,
)
from direct_payment.treatment_procedure.pytests.factories import (
    TreatmentProcedureFactory,
)


@pytest.fixture
def bill_admin():
    return BillingAdminService()


@pytest.fixture
def payor_type(request):
    return request.param


@pytest.fixture
def payor(payor_type, member, employer, clinic):
    if payor_type == models.PayorType.MEMBER:
        return member
    if payor_type == models.PayorType.EMPLOYER:
        return employer
    if payor_type == models.PayorType.CLINIC:
        return clinic
    return


class TestAdminBillProcessing:
    @pytest.mark.parametrize(
        "status, expected_call",
        [
            (models.BillStatus.NEW, "set_new_bill_to_processing"),
            (models.BillStatus.FAILED, "retry_bill"),
        ],
    )
    def test_bill_process_succeeds(self, bill_admin, status, expected_call):
        bill = BillFactory.build(status=status)
        billing_svc = mock.MagicMock()
        with mock.patch.object(billing_svc, expected_call) as mock_method:
            bill_admin.process_bill_in_admin(billing_svc, bill)
            assert mock_method.called

    def test_bill_process_fails(self, bill_admin):
        bill = BillFactory.build(status=models.BillStatus.PROCESSING)
        billing_svc = mock.MagicMock()
        with pytest.raises(BillValidationException):
            bill_admin.process_bill_in_admin(billing_svc, bill)


class TestAdminBillCancel:
    @pytest.mark.parametrize(
        "status",
        [models.BillStatus.NEW, models.BillStatus.FAILED],
    )
    def test_bill_cancel_succeeds(self, billing_service, bill_admin, status):
        bill = billing_service.bill_repo.create(
            instance=BillFactory.build(
                status=status,
                procedure_id=TreatmentProcedureFactory.create(
                    status=TreatmentProcedureStatus.COMPLETED
                ).id,
            )
        )
        res = bill_admin.cancel_bill_in_admin(billing_service, bill)
        assert res.id == bill.id
        assert res.status == models.BillStatus.CANCELLED

    def test_bill_cancel_fails(self, billing_service, bill_admin):
        bill = billing_service.bill_repo.create(
            instance=BillFactory.build(
                status=models.BillStatus.PROCESSING,
                procedure_id=TreatmentProcedureFactory.create(
                    status=TreatmentProcedureStatus.COMPLETED
                ).id,
            )
        )
        with pytest.raises(BillValidationException):
            bill_admin.cancel_bill_in_admin(billing_service, bill)


class TestAdminBillValidation:
    @pytest.mark.parametrize(
        "payor_type",
        [models.PayorType.MEMBER, models.PayorType.EMPLOYER, models.PayorType.CLINIC],
        indirect=True,
    )
    def test_valid_bill_creation_data(
        self, bill_admin, member, clinic, payor_type, payor
    ):
        procedure = TreatmentProcedureFactory.create(
            reimbursement_wallet_id=member.id, fertility_clinic=clinic
        )
        cost_breakdown = CostBreakdownFactory.create(
            treatment_procedure_uuid=procedure.uuid
        )
        bill_admin.validate_bill_view_form_data(
            payor_type=payor_type,
            payor_id=payor.id,
            procedure_id=procedure.id,
            cost_breakdown_id=cost_breakdown.id,
            payment_method=models.PaymentMethod.PAYMENT_GATEWAY,
            requested_status=models.BillStatus.NEW,
        )

    def test_invalid_treatment_procedure_not_found(self, bill_admin, member):
        procedure_id = -1
        with pytest.raises(BillValidationException) as e:
            bill_admin.validate_bill_view_form_data(
                payor_type=models.PayorType.MEMBER,
                payor_id=member.id,
                procedure_id=procedure_id,
                cost_breakdown_id=-1,
                payment_method=models.PaymentMethod.PAYMENT_GATEWAY,
                requested_status=models.BillStatus.NEW,
            )
            assert (
                str(e.value)
                == f"Could not find the requested Treatment Procedure {procedure_id}"
            )

    def test_invalid_treatment_procedure_not_associated(self, bill_admin, member):
        procedure = TreatmentProcedureFactory.create(reimbursement_wallet_id=-1)
        with pytest.raises(BillValidationException) as e:
            bill_admin.validate_bill_view_form_data(
                payor_type=models.PayorType.MEMBER,
                payor_id=member.id,
                procedure_id=procedure.id,
                cost_breakdown_id=-1,
                payment_method=models.PaymentMethod.PAYMENT_GATEWAY,
                requested_status=models.BillStatus.NEW,
            )
            assert (
                str(e.value)
                == f"This Treatment Procedure is not associated with the given payor type {models.PayorType.MEMBER} and id {member.id}."
            )

    def test_invalid_cost_breakdown_not_found(self, bill_admin, member):
        procedure = TreatmentProcedureFactory.create(reimbursement_wallet_id=member.id)
        cost_breakdown_id = -1
        with pytest.raises(BillValidationException) as e:
            bill_admin.validate_bill_view_form_data(
                payor_type=models.PayorType.MEMBER,
                payor_id=member.id,
                procedure_id=procedure.id,
                cost_breakdown_id=cost_breakdown_id,
                payment_method=models.PaymentMethod.PAYMENT_GATEWAY,
                requested_status=models.BillStatus.NEW,
            )
            assert (
                str(e.value)
                == f"Could not find the requested Cost Breakdown {cost_breakdown_id}."
            )

    def test_invalid_cost_breakdown_not_associated(self, bill_admin, member):
        procedure = TreatmentProcedureFactory.create(reimbursement_wallet_id=member.id)
        cost_breakdown = CostBreakdownFactory.create(
            treatment_procedure_uuid=str(uuid.uuid4())
        )
        with pytest.raises(BillValidationException) as e:
            bill_admin.validate_bill_view_form_data(
                payor_type=models.PayorType.MEMBER,
                payor_id=member.id,
                procedure_id=procedure.id,
                cost_breakdown_id=cost_breakdown.id,
                payment_method=models.PaymentMethod.PAYMENT_GATEWAY,
                requested_status=models.BillStatus.NEW,
            )
            assert (
                str(e.value)
                == "The given Cost Breakdown is not associated with the given Treatment Procedure."
            )

    @pytest.mark.parametrize(
        "payment_method,error_message",
        [
            (
                models.PaymentMethod.PAYMENT_GATEWAY,
                "Payment Gateway payment method bills must be created with the NEW status.",
            ),
            (
                models.PaymentMethod.WRITE_OFF,
                "Cannot create FAILED bills via admin. This status can only be applied by the payment gateway.",
            ),
        ],
    )
    def test_invalid_bill_status(
        self, bill_admin, member, payment_method, error_message
    ):
        procedure = TreatmentProcedureFactory.create(reimbursement_wallet_id=member.id)
        cost_breakdown = CostBreakdownFactory.create(
            treatment_procedure_uuid=procedure.uuid
        )
        with pytest.raises(BillValidationException) as e:
            bill_admin.validate_bill_view_form_data(
                payor_type=models.PayorType.MEMBER,
                payor_id=member.id,
                procedure_id=procedure.id,
                cost_breakdown_id=cost_breakdown.id,
                payment_method=payment_method,
                requested_status=models.BillStatus.FAILED,
            )
            assert str(e.value) == error_message


class TestCreateRefundBillsForProcedure:
    def test_single_reverse_transfer_bill_created(
        self, billing_service, bill_admin, member, employer, clinic
    ):
        # given
        procedure = TreatmentProcedureFactory.create(reimbursement_wallet_id=member.id)
        bills = BillFactory.create_batch(
            size=3,
            procedure_id=procedure.id,
            payor_type=factory.Iterator(
                [PayorType.MEMBER, PayorType.EMPLOYER, PayorType.CLINIC]
            ),
            amount=factory.Iterator([10000, 10000, 20000]),
            status=BillStatus.PAID,
            payor_id=factory.Iterator([member.id, employer.id, clinic.id]),
        )
        for bill in bills:
            billing_service.bill_repo.create(instance=bill)
        billing_service.set_new_bill_to_processing = mock.MagicMock()

        # when
        bills_created = bill_admin.create_clinic_reverse_transfer_bills_for_procedure(
            svc=billing_service, procedure_id=procedure.id
        )

        # then
        assert len(bills_created) == 1
        assert bills_created[0].amount == -20000
        billing_service.set_new_bill_to_processing.assert_called()

    def test_multiple_reverse_transfer_bills_created(
        self, billing_service, bill_admin, member, employer, clinic
    ):
        # given
        procedure = TreatmentProcedureFactory.create(reimbursement_wallet_id=member.id)
        bills = BillFactory.create_batch(
            size=4,
            procedure_id=procedure.id,
            payor_type=factory.Iterator(
                [
                    PayorType.MEMBER,
                    PayorType.EMPLOYER,
                    PayorType.CLINIC,
                    PayorType.CLINIC,
                ]
            ),
            amount=factory.Iterator([10000, 10000, 10000, 10000]),
            status=BillStatus.PAID,
            payor_id=factory.Iterator([member.id, employer.id, clinic.id, clinic.id]),
        )
        for bill in bills:
            billing_service.bill_repo.create(instance=bill)
        billing_service.set_new_bill_to_processing = mock.MagicMock()

        # when
        bills_created = bill_admin.create_clinic_reverse_transfer_bills_for_procedure(
            svc=billing_service, procedure_id=procedure.id
        )

        # then
        assert len(bills_created) == 2
        assert bills_created[0].amount == -10000
        assert bills_created[1].amount == -10000
        billing_service.set_new_bill_to_processing.assert_called()

    def test_clinic_bill_partially_reverted_before(
        self, billing_service, bill_admin, member, employer, clinic
    ):
        # given
        procedure = TreatmentProcedureFactory.create(reimbursement_wallet_id=member.id)
        bills = BillFactory.create_batch(
            size=4,
            procedure_id=procedure.id,
            payor_type=factory.Iterator(
                [
                    PayorType.MEMBER,
                    PayorType.EMPLOYER,
                    PayorType.CLINIC,
                    PayorType.CLINIC,
                ]
            ),
            amount=factory.Iterator([10000, 10000, 30000, -10000]),
            status=factory.Iterator(
                [BillStatus.PAID, BillStatus.PAID, BillStatus.PAID, BillStatus.REFUNDED]
            ),
            payor_id=factory.Iterator([member.id, employer.id, clinic.id, clinic.id]),
        )
        bills_with_id = []
        for bill in bills:
            bills_with_id.append(billing_service.bill_repo.create(instance=bill))
        records = BillProcessingRecordFactory.create_batch(
            size=2,
            bill_id=factory.Iterator([bills_with_id[2].id, bills_with_id[3].id]),
            bill_status=factory.Iterator(
                [BillStatus.PAID.value, BillStatus.REFUNDED.value]
            ),
            body=factory.Iterator([{}, {"refund_bill": bills_with_id[2].id}]),
            processing_record_type="payment_gateway_request",
        )
        for record in records:
            billing_service.bill_processing_record_repo.create(instance=record)
        billing_service.set_new_bill_to_processing = mock.MagicMock()

        # when
        bills_created = bill_admin.create_clinic_reverse_transfer_bills_for_procedure(
            svc=billing_service, procedure_id=procedure.id
        )

        # then
        assert len(bills_created) == 1
        assert bills_created[0].amount == -20000
        billing_service.set_new_bill_to_processing.assert_called()

    def test_some_bill_not_paid_yet(
        self, billing_service, bill_admin, member, employer, clinic
    ):
        # given
        procedure = TreatmentProcedureFactory.create(reimbursement_wallet_id=member.id)
        bills = BillFactory.create_batch(
            size=3,
            procedure_id=procedure.id,
            payor_type=factory.Iterator(
                [PayorType.MEMBER, PayorType.EMPLOYER, PayorType.CLINIC]
            ),
            amount=factory.Iterator([10000, 10000, 20000]),
            status=BillStatus.NEW,
            payor_id=factory.Iterator([member.id, employer.id, clinic.id]),
        )
        for bill in bills:
            billing_service.bill_repo.create(instance=bill)
        billing_service.set_new_bill_to_processing = mock.MagicMock()

        # when / then
        with pytest.raises(ClinicReverseTransferCreationException):
            bill_admin.create_clinic_reverse_transfer_bills_for_procedure(
                svc=billing_service, procedure_id=procedure.id
            )

    def test_clinic_bill_already_fully_reverse_transferred(
        self, billing_service, bill_admin, member, employer, clinic
    ):
        # given
        procedure = TreatmentProcedureFactory.create(reimbursement_wallet_id=member.id)
        bills = BillFactory.create_batch(
            size=4,
            procedure_id=procedure.id,
            payor_type=factory.Iterator(
                [
                    PayorType.MEMBER,
                    PayorType.EMPLOYER,
                    PayorType.CLINIC,
                    PayorType.CLINIC,
                ]
            ),
            amount=factory.Iterator([10000, 10000, 20000, -20000]),
            status=factory.Iterator(
                [BillStatus.PAID, BillStatus.PAID, BillStatus.PAID, BillStatus.REFUNDED]
            ),
            payor_id=factory.Iterator([member.id, employer.id, clinic.id, clinic.id]),
        )
        bills_with_id = []
        for bill in bills:
            bills_with_id.append(billing_service.bill_repo.create(instance=bill))
        records = BillProcessingRecordFactory.create_batch(
            size=2,
            bill_id=factory.Iterator([bills_with_id[2].id, bills_with_id[3].id]),
            bill_status=factory.Iterator(
                [BillStatus.PAID.value, BillStatus.REFUNDED.value]
            ),
            body=factory.Iterator([{}, {"refund_bill": bills_with_id[2].id}]),
            processing_record_type="payment_gateway_request",
        )
        for record in records:
            billing_service.bill_processing_record_repo.create(instance=record)
        billing_service.set_new_bill_to_processing = mock.MagicMock()

        # when / then
        with pytest.raises(ClinicReverseTransferCreationException):
            bill_admin.create_clinic_reverse_transfer_bills_for_procedure(
                svc=billing_service, procedure_id=procedure.id
            )

    def test_clinic_bill_reverse_transfer_exception(
        self, billing_service, bill_admin, member, employer, clinic
    ):
        # given
        procedure = TreatmentProcedureFactory.create(reimbursement_wallet_id=member.id)
        bills = BillFactory.create_batch(
            size=3,
            procedure_id=procedure.id,
            payor_type=factory.Iterator(
                [PayorType.MEMBER, PayorType.EMPLOYER, PayorType.CLINIC]
            ),
            amount=factory.Iterator([10000, 10000, 20000]),
            status=BillStatus.PAID,
            payor_id=factory.Iterator([member.id, employer.id, clinic.id]),
        )
        for bill in bills:
            billing_service.bill_repo.create(instance=bill)
        billing_service.set_new_bill_to_processing = mock.MagicMock()
        billing_service.set_new_bill_to_processing.side_effect = Exception()

        # when / then
        with pytest.raises(ClinicReverseTransferProcessingException):
            bill_admin.create_clinic_reverse_transfer_bills_for_procedure(
                svc=billing_service, procedure_id=procedure.id
            )
