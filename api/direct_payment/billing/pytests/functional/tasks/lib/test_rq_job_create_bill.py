import datetime
import uuid
from functools import partial
from unittest import mock

import pytest

from common.payments_gateway import Customer, Transaction
from cost_breakdown.pytests.factories import CostBreakdownFactory
from direct_payment.billing.constants import MEMBER_BILLING_OFFSET_DAYS
from direct_payment.billing.models import BillStatus, PaymentMethodType, PayorType
from direct_payment.billing.pytests import factories
from direct_payment.billing.pytests.factories import (
    BillFactory,
    BillProcessingRecordFactory,
)
from direct_payment.billing.tasks.rq_job_create_bill import (
    create_and_process_member_refund_bills,
    create_member_and_employer_bill,
    create_member_bill,
)
from direct_payment.clinic.pytests.factories import FertilityClinicLocationFactory
from direct_payment.invoicing.pytests.factories import (
    OrganizationInvoicingSettingsFactory,
)
from direct_payment.invoicing.repository.organization_invoicing_settings import (
    OrganizationInvoicingSettingsRepository,
)
from direct_payment.notification.lib.tasks.rq_send_notification import (
    send_notification_event,
)
from direct_payment.treatment_procedure.models.treatment_procedure import (
    TreatmentProcedureStatus,
)
from direct_payment.treatment_procedure.pytests.factories import (
    TreatmentProcedureFactory,
)
from storage import connection
from wallet.pytests.factories import ReimbursementWalletBenefitFactory

T_MINUS_1 = datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(days=-1)
T_PLUS_1 = datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(days=1)


def date_str_with_offset():
    return (
        (
            datetime.datetime.now(datetime.timezone.utc).replace(microsecond=0)
            + datetime.timedelta(days=MEMBER_BILLING_OFFSET_DAYS)
        )
        .isoformat("T", "milliseconds")
        .replace(".000", ":000Z")
    )


def date_str_wo_offset():
    return (
        datetime.datetime.now(datetime.timezone.utc)
        .replace(microsecond=0)
        .isoformat("T", "milliseconds")
        .replace(".000", ":000Z")
    )


@pytest.fixture
def mocked_customer():
    def fn(payment_method_type=PaymentMethodType.card):
        return Customer.create_from_dict(
            {
                "customer_id": "00112233-4455-6677-8899-aabbccddeeff",
                "customer_setup_status": "succeeded",
                "payment_method_types": [payment_method_type.value],
                "payment_methods": [
                    {
                        "payment_method_type": payment_method_type.value,
                        "last4": "1234",
                        "brand": "visa",
                        "payment_method_id": "made_up",
                    }
                ],
            }
        )

    return fn


@pytest.fixture
def mocked_employer_payor():
    def fn(payment_method_type=PaymentMethodType.us_bank_account):
        return Customer.create_from_dict(
            {
                "customer_id": "99112233-4455-6677-8899-aabbccddeeff",
                "customer_setup_status": "succeeded",
                "payment_method_types": [payment_method_type.value],
                "payment_methods": [
                    {
                        "payment_method_type": payment_method_type.value,
                        "last4": "4321",
                        "brand": "",
                        "payment_method_id": "made_up_again",
                    }
                ],
            }
        )

    return fn


@pytest.fixture
def mocked_transaction():
    return Transaction(
        transaction_id=uuid.uuid4(),
        transaction_data={"transaction": "data"},
        status="pending",
        metadata={"source_id": "1", "source_type": "Type"},
    )


def estimate_bills_setup(
    billing_service,
    bill_wallet,
    member_responsibility,
    tp_status,
    estimate_amount,
    bill_amount,
    bill_status,
    create_bpr,
):
    cb = CostBreakdownFactory.create(total_member_responsibility=member_responsibility)
    clinic = FertilityClinicLocationFactory.build(
        name="Maven Fertility",
        city="Brooklyn",
        subdivision_code="US-NY",
    )
    tp = TreatmentProcedureFactory.create(
        status=tp_status,
        cost_breakdown_id=cb.id,
        reimbursement_wallet_id=bill_wallet.id,
        procedure_name="IVF Freeze All",
        fertility_clinic_location=clinic,
        fertility_clinic_location_id=clinic.id,
    )
    if estimate_amount:
        billing_service.bill_repo.create(
            instance=BillFactory.build(
                procedure_id=tp.id,
                is_ephemeral=True,
                processing_scheduled_at_or_after=None,
                status=BillStatus.NEW,
                amount=estimate_amount,
                payor_id=bill_wallet.id,
            )
        )
    if bill_amount and bill_status:
        paid_bill = billing_service.bill_repo.create(
            instance=BillFactory.build(
                procedure_id=tp.id,
                is_ephemeral=False,
                processing_scheduled_at_or_after=datetime.datetime.now(
                    datetime.timezone.utc
                ),
                status=bill_status,
                amount=bill_amount,
                payor_id=bill_wallet.id,
            )
        )
    if create_bpr:
        billing_service.bill_processing_record_repo.create(
            instance=BillProcessingRecordFactory.build(
                processing_record_type="test",
                bill_id=paid_bill.id,
                bill_status=bill_status.value,
                created_at=datetime.datetime.now(datetime.timezone.utc)
                - datetime.timedelta(days=7),
            )
        )
    return tp.id, cb.id


class TestCreateAndProcessMemberRefundBills:
    def test_create_and_process_member_refund_bills(
        self,
        billing_service,
        random_reimbursement_wallet_with_benefit,
        mocked_transaction,
    ):
        wallet = random_reimbursement_wallet_with_benefit()
        bill = factories.BillFactory.build(
            payor_type=PayorType.MEMBER,
            status=BillStatus.PAID,
            amount=7000,
            last_calculated_fee=210,
            payor_id=wallet.id,
            procedure_id=TreatmentProcedureFactory.create(
                status=TreatmentProcedureStatus.COMPLETED,
            ).id,
        )
        _ = CostBreakdownFactory.create(
            id=bill.cost_breakdown_id,
            wallet_id=bill.payor_id,
            total_member_responsibility=bill.amount,
        )
        bill = billing_service.bill_repo.create(instance=bill)
        _ = billing_service.bill_processing_record_repo.create(
            instance=factories.BillProcessingRecordFactory.build(
                processing_record_type="payment_gateway_request",
                bill_id=bill.id,
                bill_status=bill.status.value,
            )
        )
        _ = billing_service.bill_repo.create(
            instance=factories.BillFactory.build(
                payor_type=PayorType.MEMBER,
                status=BillStatus.PAID,
                amount=7000,
                payor_id=wallet.id,
                is_ephemeral=True,
                procedure_id=TreatmentProcedureFactory.create(
                    status=TreatmentProcedureStatus.SCHEDULED
                ).id,
            )
        )
        _ = billing_service.bill_repo.create(
            instance=factories.BillFactory.build(
                payor_type=PayorType.MEMBER,
                status=BillStatus.PAID,
                amount=7000,
                payor_id=wallet.id,
                is_ephemeral=True,
                procedure_id=TreatmentProcedureFactory.create(
                    status=TreatmentProcedureStatus.SCHEDULED,
                ).id,
            )
        )

        with mock.patch(
            "common.payments_gateway.client.PaymentsGatewayClient.create_transaction",
            return_value=mocked_transaction,
        ):
            create_and_process_member_refund_bills(bill.procedure_id)
            res = billing_service.get_bills_by_procedure_ids([bill.procedure_id])
            assert len(res) == 2
            refunds = [b for b in res if b.id != bill.id]
            assert len(refunds) == 1
            refund = refunds[0]
            assert refund.amount == -bill.amount
            assert refund.last_calculated_fee == -bill.last_calculated_fee
            assert refund.status == BillStatus.PROCESSING
            assert (
                billing_service.get_member_estimate_by_procedure([bill.procedure_id])
                is None
            )
            orig_bprs = (
                billing_service.bill_processing_record_repo.get_bill_processing_records(
                    [bill.id]
                )
            )
            assert len(orig_bprs) == 2
            assert {bpr.bill_status for bpr in orig_bprs} == {
                BillStatus.PAID.value,
                BillStatus.REFUNDED.value,
            }
            ref_bprs = (
                billing_service.bill_processing_record_repo.get_bill_processing_records(
                    [refund.id]
                )
            )
            assert len(ref_bprs) == 2
            # processing is marked twice on the bill - one either side of payment gateway submission
            assert [bpr.bill_status for bpr in ref_bprs] == [
                BillStatus.PROCESSING.value,
                BillStatus.PROCESSING.value,
            ]


class TestCreateAndProcessMemberBills:
    @pytest.mark.parametrize(
        argnames=" treatment_procedure_status, total_member_responsibility, paid_amt, last_calculated_fee, "
        "payment_method_type, additional_msg_data, non_zero_auto_process_max, exp_bill_status, exp_notification_event, "
        "exp_amt_type_key, exp_amt, exp_date_key, exp_date_str, exp_notification_from_rq_code",
        ids=[
            "0. Member responsibility increased at treatment completion with a previous bill",
            "1. Member responsibility increased at treatment partial completion with a previous bill ",
            "2. Member responsibility increased at treatment completion without a previous bill",
            "3. Member responsibility decreased at treatment completion with previous bill process refund immediately",
            "4. Treatment completed with 0 member responsibility -> no notification sent, bill set to paid immediately ",
            "5. Member responsibility of less than AUTO_PROCESS_MAX_AMOUNT at treatment completion without a previous "
            "bill, no notification sent ",
        ],
        argvalues=[
            (
                TreatmentProcedureStatus.COMPLETED,
                10000,
                5000,
                150,
                PaymentMethodType.card,
                {"original_payment_amount": "$50.00"},
                False,
                BillStatus.NEW,
                "mmb_payment_adjusted_addl_charge",
                "additional_charge_amount",
                "$51.50",
                "payment_date",
                date_str_with_offset(),
                True,
            ),
            (
                TreatmentProcedureStatus.PARTIALLY_COMPLETED,
                10000,
                5000,
                150,
                PaymentMethodType.card,
                {"original_payment_amount": "$50.00"},
                False,
                BillStatus.NEW,
                "mmb_payment_adjusted_addl_charge",
                "additional_charge_amount",
                "$51.50",
                "payment_date",
                date_str_with_offset(),
                True,
            ),
            (
                TreatmentProcedureStatus.COMPLETED,
                10000,
                0,
                300,
                PaymentMethodType.card,
                {},
                False,
                BillStatus.NEW,
                "mmb_upcoming_payment_reminder",
                "payment_amount",
                "$103.00",
                "payment_date",
                date_str_with_offset(),
                True,
            ),
            (
                TreatmentProcedureStatus.COMPLETED,
                5000,
                10000,
                300,
                PaymentMethodType.card,
                {"original_payment_amount": "$103.00"},
                False,
                BillStatus.PROCESSING,
                "mmb_payment_adjusted_refund",
                "refund_amount",
                "$51.50",
                "refund_date",
                date_str_wo_offset(),
                False,
            ),
            (
                TreatmentProcedureStatus.COMPLETED,
                0,
                0,
                0,
                PaymentMethodType.card,
                {"original_payment_amount": "$0.00"},
                False,
                BillStatus.PAID,
                None,
                None,
                None,
                None,
                None,
                False,
            ),
            (
                TreatmentProcedureStatus.COMPLETED,
                10,
                0,
                300,
                PaymentMethodType.card,
                {},
                45,
                BillStatus.PAID,
                None,
                None,
                None,
                None,
                None,
                False,
            ),
        ],
    )
    def test_create_member_bills(
        self,
        billing_service,
        bill_wallet,
        mocked_customer,
        mocked_transaction,
        treatment_procedure_status,
        total_member_responsibility,
        paid_amt,
        last_calculated_fee,
        payment_method_type,
        additional_msg_data,
        non_zero_auto_process_max,
        exp_bill_status,
        exp_notification_event,
        exp_amt_type_key,
        exp_amt,
        exp_date_key,
        exp_date_str,
        exp_notification_from_rq_code,
    ):
        wallet_benefit = ReimbursementWalletBenefitFactory.create()
        bill_wallet.reimbursement_wallet_benefit = wallet_benefit
        cost_breakdown = CostBreakdownFactory.create(
            wallet_id=bill_wallet.id,
            total_member_responsibility=total_member_responsibility,
        )
        treatment_procedure = TreatmentProcedureFactory.create(
            reimbursement_wallet_id=bill_wallet.id,
            status=treatment_procedure_status,
        )
        remaining_member_resp = total_member_responsibility
        pre_created_bill_ids = set()
        if paid_amt:
            bill = factories.BillFactory.build(
                payor_type=PayorType.MEMBER,
                status=BillStatus.PAID,
                amount=paid_amt,
                last_calculated_fee=last_calculated_fee,  # 3 / 100 * paid_amt,
                cost_breakdown_id=cost_breakdown.id,
                procedure_id=treatment_procedure.id,
                payor_id=bill_wallet.id,
            )
            bill = billing_service.bill_repo.create(instance=bill)
            _ = billing_service.bill_processing_record_repo.create(
                instance=factories.BillProcessingRecordFactory.build(
                    processing_record_type="payment_gateway_response",
                    bill_id=bill.id,
                    bill_status=bill.status.value,
                )
            )
            pre_created_bill_ids.add(bill.id)
            remaining_member_resp = remaining_member_resp - paid_amt

        with mock.patch(
            "common.payments_gateway.client.PaymentsGatewayClient.get_customer",
            return_value=mocked_customer(payment_method_type),
        ), mock.patch(
            "common.payments_gateway.client.PaymentsGatewayClient.create_transaction",
            return_value=mocked_transaction,
        ), mock.patch(
            "direct_payment.billing.tasks.rq_job_create_bill.send_notification_event.delay",
            side_effect=send_notification_event,
        ) as mock_send_notification_event, mock.patch(
            "utils.braze.send_event_by_ids"
        ) as mock_send_event_by_ids, mock.patch(
            "direct_payment.billing.billing_service.get_auto_process_max_amount",
            return_value=non_zero_auto_process_max,
        ):
            create_member_bill(
                treatment_procedure.id,
                cost_breakdown.id,
                bill_wallet.id,
                treatment_procedure_status,
            )
        bills = billing_service.get_bills_by_procedure_ids([treatment_procedure.id])
        res_bills = [b for b in bills if b.id not in pre_created_bill_ids]
        assert len(res_bills) == 1
        assert res_bills[0].amount == remaining_member_resp
        assert res_bills[0].status == exp_bill_status
        assert mock_send_notification_event.called is exp_notification_from_rq_code
        assert mock_send_event_by_ids.called == bool(exp_notification_event)
        if exp_notification_event:
            event_properties = {
                "benefit_id": wallet_benefit.maven_benefit_id,
                "payment_amount": f"${total_member_responsibility / 100:,.2f}",
                exp_date_key: exp_date_str,
                "payment_method_type": (
                    res_bills[0].payment_method_type.value
                    if res_bills[0].payment_method_type
                    else ""
                ),
                "payment_method_last4": (
                    res_bills[0].payment_method_label
                    if res_bills[0].payment_method_label
                    else ""
                ),
                exp_amt_type_key: exp_amt,
            }
            if exp_notification_event == "mmb_upcoming_payment_reminder":
                event_properties["clinic_name"] = "name"
                event_properties["clinic_location"] = "New York City, NY"
            event_properties.update(additional_msg_data)
            assert mock_send_event_by_ids.called
            kwargs_ = mock_send_event_by_ids.call_args.kwargs
            assert kwargs_["event_name"] == exp_notification_event
            assert kwargs_["event_data"].keys() == event_properties.keys()
            for k in kwargs_["event_data"].keys():
                if "_date" not in k:
                    assert kwargs_["event_data"][k] == event_properties[k]
                else:
                    res_dt = datetime.datetime.fromisoformat(
                        kwargs_["event_data"][k].replace("Z", "+00:00")
                    ).date()
                    exp_dt = datetime.datetime.fromisoformat(
                        event_properties[k].replace("Z", "")
                    ).date()
                    assert res_dt == exp_dt

    @pytest.mark.parametrize(
        argnames=" treatment_procedure_status, total_member_responsibility, total_employer_responsibility, "
        "member_prev_bill, ex_mem_bill, ex_emp_bill, ex_clin_bill",
        ids=[
            "0. Member responsibility increased at treatment completion with a previous bill-> send notification",
            "1. Member responsibility increased at treatment partial completion with previous bill-> send notification",
            "2. Member responsibility increased at treatment completion with 0 previous bill-> send notification",
            "3. Member responsibility increased at treatment completion with a previous bill, 0 employer bill clinic "
            "bill created",
            "4. Member responsibility decreased at treatment partial completion with a PAID previous bill-> ",
            "5. Member responsibility decreased at treatment partial completion with a NEW previous bill,0 employer "
            "bill, Clinic bill gets created.-> ",
        ],
        argvalues=[
            (
                TreatmentProcedureStatus.COMPLETED,
                10000,
                7000,
                partial(
                    factories.BillFactory.build,
                    payor_type=PayorType.MEMBER,
                    status=BillStatus.PAID,
                    amount=5000,
                    last_calculated_fee=150,
                    payment_method_type=PaymentMethodType.card,
                ),
                partial(
                    factories.BillFactory.build,
                    payor_type=PayorType.MEMBER,
                    status=BillStatus.NEW,
                    amount=5000,
                    last_calculated_fee=150,
                    payment_method_type=PaymentMethodType.card,
                ),
                partial(
                    factories.BillFactory.build,
                    payor_type=PayorType.EMPLOYER,
                    status=BillStatus.PROCESSING,
                    amount=7000,
                    last_calculated_fee=0,
                    payor_id=uuid.uuid4(),
                    payment_method_type=PaymentMethodType.us_bank_account,
                ),
                None,
            ),
            (
                TreatmentProcedureStatus.PARTIALLY_COMPLETED,
                12000,
                6000,
                partial(
                    factories.BillFactory.build,
                    payor_type=PayorType.MEMBER,
                    status=BillStatus.PAID,
                    amount=5000,
                    last_calculated_fee=150,
                    payment_method_type=PaymentMethodType.card,
                ),
                partial(
                    factories.BillFactory.build,
                    payor_type=PayorType.MEMBER,
                    status=BillStatus.NEW,
                    amount=7000,
                    last_calculated_fee=0,
                    payment_method_type=PaymentMethodType.us_bank_account,
                ),
                partial(
                    factories.BillFactory.build,
                    payor_type=PayorType.EMPLOYER,
                    status=BillStatus.PROCESSING,
                    amount=6000,
                    last_calculated_fee=0,
                    payor_id=uuid.uuid4(),
                    payment_method_type=PaymentMethodType.us_bank_account,
                ),
                None,
            ),
            (
                TreatmentProcedureStatus.COMPLETED,
                10000,
                7000,
                partial(
                    factories.BillFactory.build,
                    payor_type=PayorType.MEMBER,
                    status=BillStatus.PAID,
                    amount=0,
                    last_calculated_fee=0,
                    payment_method_type=PaymentMethodType.card,
                ),
                partial(
                    factories.BillFactory.build,
                    payor_type=PayorType.MEMBER,
                    status=BillStatus.NEW,
                    amount=10000,
                    last_calculated_fee=300,
                    payment_method_type=PaymentMethodType.card,
                ),
                partial(
                    factories.BillFactory.build,
                    payor_type=PayorType.EMPLOYER,
                    status=BillStatus.PROCESSING,
                    amount=7000,
                    last_calculated_fee=0,
                    payor_id=uuid.uuid4(),
                    payment_method_type=PaymentMethodType.us_bank_account,
                ),
                None,
            ),
            (
                TreatmentProcedureStatus.COMPLETED,
                10000,
                0,
                partial(
                    factories.BillFactory.build,
                    payor_type=PayorType.MEMBER,
                    status=BillStatus.PROCESSING,
                    amount=5000,
                    last_calculated_fee=150,
                    payment_method_type=PaymentMethodType.card,
                ),
                partial(
                    factories.BillFactory.build,
                    payor_type=PayorType.MEMBER,
                    status=BillStatus.NEW,
                    amount=5000,
                    last_calculated_fee=150,
                    payment_method_type=PaymentMethodType.card,
                ),
                partial(
                    factories.BillFactory.build,
                    payor_type=PayorType.EMPLOYER,
                    status=BillStatus.PAID,
                    amount=0,
                    last_calculated_fee=0,
                    payor_id=uuid.uuid4(),
                    payment_method_type=None,
                ),
                partial(
                    factories.BillFactory.build,
                    payor_type=PayorType.CLINIC,
                    status=BillStatus.PROCESSING,
                    amount=10000,
                    last_calculated_fee=0,
                ),
            ),
            (
                TreatmentProcedureStatus.PARTIALLY_COMPLETED,
                10000,
                7000,
                partial(
                    factories.BillFactory.build,
                    payor_type=PayorType.MEMBER,
                    status=BillStatus.PAID,
                    amount=20000,
                    last_calculated_fee=600,
                    payment_method_type=PaymentMethodType.card,
                ),
                partial(
                    factories.BillFactory.build,
                    payor_type=PayorType.MEMBER,
                    status=BillStatus.PROCESSING,
                    amount=-10000,
                    last_calculated_fee=-300,
                    payment_method_type=PaymentMethodType.card,
                ),
                partial(
                    factories.BillFactory.build,
                    payor_type=PayorType.EMPLOYER,
                    status=BillStatus.PROCESSING,
                    amount=7000,
                    last_calculated_fee=0,
                    payor_id=uuid.uuid4(),
                    payment_method_type=PaymentMethodType.us_bank_account,
                ),
                None,
            ),
            (
                TreatmentProcedureStatus.PARTIALLY_COMPLETED,
                12000,
                0,
                partial(
                    factories.BillFactory.build,
                    payor_type=PayorType.MEMBER,
                    status=BillStatus.PAID,
                    amount=20000,
                    last_calculated_fee=600,
                    payment_method_type=PaymentMethodType.card,
                ),
                partial(
                    factories.BillFactory.build,
                    payor_type=PayorType.MEMBER,
                    status=BillStatus.PROCESSING,
                    amount=-8000,
                    last_calculated_fee=-240,
                    payment_method_type=PaymentMethodType.card,
                ),
                partial(
                    factories.BillFactory.build,
                    payor_type=PayorType.EMPLOYER,
                    status=BillStatus.PAID,
                    amount=0,
                    last_calculated_fee=0,
                    payor_id=uuid.uuid4(),
                    payment_method_type=None,
                ),
                partial(
                    factories.BillFactory.build,
                    payor_type=PayorType.CLINIC,
                    status=BillStatus.PROCESSING,
                    amount=12000,
                    last_calculated_fee=0,
                ),
            ),
        ],
    )
    def test_create_member_and_employer_bills(
        self,
        billing_service,
        bill_wallet,
        mocked_customer,
        mocked_employer_payor,
        mocked_transaction,
        treatment_procedure_status,
        total_member_responsibility,
        total_employer_responsibility,
        member_prev_bill,
        ex_mem_bill,
        ex_emp_bill,
        ex_clin_bill,
    ):
        wallet_benefit = ReimbursementWalletBenefitFactory.create()
        bill_wallet.reimbursement_wallet_benefit = wallet_benefit
        bill_wallet.reimbursement_organization_settings.payments_customer_id = str(
            uuid.uuid4()
        )
        cost_breakdown = CostBreakdownFactory.create(
            wallet_id=bill_wallet.id,
            total_member_responsibility=total_member_responsibility,
            total_employer_responsibility=total_employer_responsibility,
        )
        treatment_procedure = TreatmentProcedureFactory.create(
            reimbursement_wallet_id=bill_wallet.id,
            status=treatment_procedure_status,
            cost=total_member_responsibility + total_employer_responsibility,
        )
        pre_created_bill_ids = set()
        if member_prev_bill:
            member_prev_bill = member_prev_bill(
                cost_breakdown_id=cost_breakdown.id,
                procedure_id=treatment_procedure.id,
                payor_id=bill_wallet.id,
            )
            member_prev_bill = billing_service.bill_repo.create(
                instance=member_prev_bill
            )
            _ = billing_service.bill_processing_record_repo.create(
                instance=factories.BillProcessingRecordFactory.build(
                    processing_record_type="payment_gateway_response",
                    bill_id=member_prev_bill.id,
                    bill_status=member_prev_bill.status.value,
                )
            )
            pre_created_bill_ids.add(member_prev_bill.id)
        if ex_mem_bill:
            ex_mem_bill = ex_mem_bill(
                cost_breakdown_id=cost_breakdown.id,
                procedure_id=treatment_procedure.id,
                payor_id=bill_wallet.id,
            )
        ex_emp_bill = ex_emp_bill(
            cost_breakdown_id=cost_breakdown.id,
            procedure_id=treatment_procedure.id,
            payor_id=bill_wallet.reimbursement_organization_settings.id,
        )
        if ex_clin_bill:
            ex_clin_bill = ex_clin_bill(
                cost_breakdown_id=cost_breakdown.id,
                procedure_id=treatment_procedure.id,
                payor_id=treatment_procedure.fertility_clinic_id,
            )

        with mock.patch(
            "common.payments_gateway.client.PaymentsGatewayClient.get_customer",
            side_effect=[
                mocked_customer(
                    ex_mem_bill.payment_method_type if ex_mem_bill else None
                ),
                mocked_employer_payor(),
            ],
        ):
            with mock.patch(
                "common.payments_gateway.client.PaymentsGatewayClient.create_transaction",
                return_value=mocked_transaction,
            ):
                with mock.patch("utils.braze.send_event_by_ids"):
                    create_member_and_employer_bill(
                        treatment_procedure.id,
                        cost_breakdown.id,
                        bill_wallet.id,
                        treatment_procedure_status,
                    )
        bills = billing_service.get_bills_by_procedure_ids([treatment_procedure.id])
        res_bills = {b.payor_type: b for b in bills if b.id not in pre_created_bill_ids}
        assert len(res_bills) == sum(
            [
                ex_mem_bill is not None,
                ex_emp_bill is not None,
                ex_clin_bill is not None,
            ]
        )
        if ex_mem_bill:
            res_mem_bill = res_bills[PayorType.MEMBER]
            assert res_mem_bill.status == ex_mem_bill.status
            assert res_mem_bill.amount == ex_mem_bill.amount
            assert res_mem_bill.last_calculated_fee == ex_mem_bill.last_calculated_fee
            assert res_mem_bill.payment_method_type == ex_mem_bill.payment_method_type
        else:
            assert res_bills.get(PayorType.MEMBER) is None

        res_emp_bill = res_bills[PayorType.EMPLOYER]
        assert res_emp_bill.status == ex_emp_bill.status
        assert res_emp_bill.amount == ex_emp_bill.amount
        assert res_emp_bill.last_calculated_fee == ex_emp_bill.last_calculated_fee
        assert res_emp_bill.payment_method_type == ex_emp_bill.payment_method_type

        if ex_clin_bill:
            res_clin_bill = res_bills[PayorType.CLINIC]
            assert res_clin_bill.status == ex_clin_bill.status
            assert res_clin_bill.amount == ex_clin_bill.amount
            assert res_clin_bill.last_calculated_fee == ex_clin_bill.last_calculated_fee
            assert res_clin_bill.payment_method_type == ex_clin_bill.payment_method_type

    @pytest.mark.parametrize(
        argnames="total_member_responsibility, total_employer_responsibility, create_ois_flag, "
        "ois_bill_cutoff_at_buffer_days, ex_mem_bill, ex_emp_bill, ex_clin_bill",
        ids=[
            "1. Feature flag on, no organization invoicing setting, non 0 employer bill created and in processing",
            "2. Feature flag on, organization invoicing setting, non 0 buffer, non 0 employer bill created and in new state",
            "3. Feature flag on, no organization invoicing setting, 0 employer bill created and paid. clinic bill created and in processing",
            "4. Feature flag on, organization invoicing setting, non 0 buffer, 0 employer bill created and in new state",
            "5. Feature flag on, organization invoicing setting, 0 buffer, non 0 employer bill created and in new state",
            "6. Feature flag on, organization invoicing setting, 0 buffer, 0 employer bill created and in new state",
        ],
        argvalues=[
            (
                10000,
                7000,
                False,
                None,
                partial(
                    factories.BillFactory.build,
                    payor_type=PayorType.MEMBER,
                    status=BillStatus.NEW,
                    amount=10000,
                    last_calculated_fee=300,
                    payment_method_type=PaymentMethodType.card,
                ),
                partial(
                    factories.BillFactory.build,
                    payor_type=PayorType.EMPLOYER,
                    status=BillStatus.PROCESSING,
                    amount=7000,
                    last_calculated_fee=0,
                    payor_id=uuid.uuid4(),
                    payment_method_type=PaymentMethodType.us_bank_account,
                ),
                None,
            ),
            (
                10000,
                7000,
                True,
                10,
                partial(
                    factories.BillFactory.build,
                    payor_type=PayorType.MEMBER,
                    status=BillStatus.NEW,
                    amount=10000,
                    last_calculated_fee=300,
                    payment_method_type=PaymentMethodType.card,
                ),
                partial(
                    factories.BillFactory.build,
                    payor_type=PayorType.EMPLOYER,
                    status=BillStatus.NEW,
                    amount=7000,
                    last_calculated_fee=0,
                    payor_id=uuid.uuid4(),
                    payment_method_type=PaymentMethodType.us_bank_account,
                ),
                None,
            ),
            (
                11000,
                0,
                False,
                None,
                partial(
                    factories.BillFactory.build,
                    payor_type=PayorType.MEMBER,
                    status=BillStatus.NEW,
                    amount=11000,
                    last_calculated_fee=330,
                    payment_method_type=PaymentMethodType.card,
                ),
                partial(
                    factories.BillFactory.build,
                    payor_type=PayorType.EMPLOYER,
                    status=BillStatus.PAID,
                    amount=0,
                    last_calculated_fee=0,
                    payor_id=uuid.uuid4(),
                    payment_method_type=None,
                ),
                partial(
                    factories.BillFactory.build,
                    payor_type=PayorType.CLINIC,
                    status=BillStatus.PROCESSING,
                    amount=11000,
                    last_calculated_fee=0,
                ),
            ),
            (
                12000,
                0,
                True,
                10,
                partial(
                    factories.BillFactory.build,
                    payor_type=PayorType.MEMBER,
                    status=BillStatus.NEW,
                    amount=12000,
                    last_calculated_fee=360,
                    payment_method_type=PaymentMethodType.card,
                ),
                partial(
                    factories.BillFactory.build,
                    payor_type=PayorType.EMPLOYER,
                    status=BillStatus.NEW,
                    amount=0,
                    last_calculated_fee=0,
                    payor_id=uuid.uuid4(),
                    payment_method_type=None,
                ),
                None,
            ),
            (
                10000,
                7000,
                True,
                0,
                partial(
                    factories.BillFactory.build,
                    payor_type=PayorType.MEMBER,
                    status=BillStatus.NEW,
                    amount=10000,
                    last_calculated_fee=300,
                    payment_method_type=PaymentMethodType.card,
                ),
                partial(
                    factories.BillFactory.build,
                    payor_type=PayorType.EMPLOYER,
                    status=BillStatus.NEW,
                    amount=7000,
                    last_calculated_fee=0,
                    payor_id=uuid.uuid4(),
                    payment_method_type=PaymentMethodType.us_bank_account,
                ),
                None,
            ),
            (
                12000,
                0,
                True,
                0,
                partial(
                    factories.BillFactory.build,
                    payor_type=PayorType.MEMBER,
                    status=BillStatus.NEW,
                    amount=12000,
                    last_calculated_fee=360,
                    payment_method_type=PaymentMethodType.card,
                ),
                partial(
                    factories.BillFactory.build,
                    payor_type=PayorType.EMPLOYER,
                    status=BillStatus.NEW,
                    amount=0,
                    last_calculated_fee=0,
                    payor_id=uuid.uuid4(),
                    payment_method_type=None,
                ),
                None,
            ),
        ],
    )
    def test_create_member_and_delayed_employer_bills(
        self,
        billing_service,
        bill_wallet,
        mocked_customer,
        mocked_employer_payor,
        mocked_transaction,
        ff_test_data,
        total_member_responsibility,
        total_employer_responsibility,
        create_ois_flag,
        ois_bill_cutoff_at_buffer_days,
        ex_mem_bill,
        ex_emp_bill,
        ex_clin_bill,
    ):
        wallet_benefit = ReimbursementWalletBenefitFactory.create()
        bill_wallet.reimbursement_wallet_benefit = wallet_benefit
        bill_wallet.reimbursement_organization_settings.payments_customer_id = str(
            uuid.uuid4()
        )
        if create_ois_flag:
            ois_repo = OrganizationInvoicingSettingsRepository(
                session=connection.db.session, is_in_uow=True
            )
            ois_repo.create(
                instance=(
                    OrganizationInvoicingSettingsFactory.build(
                        organization_id=bill_wallet.reimbursement_organization_settings.organization_id,
                        bill_processing_delay_days=14,
                        bill_cutoff_at_buffer_days=ois_bill_cutoff_at_buffer_days,
                    )
                )
            )
        cost_breakdown = CostBreakdownFactory.create(
            wallet_id=bill_wallet.id,
            total_member_responsibility=total_member_responsibility,
            total_employer_responsibility=total_employer_responsibility,
        )
        treatment_procedure = TreatmentProcedureFactory.create(
            reimbursement_wallet_id=bill_wallet.id,
            status=TreatmentProcedureStatus.COMPLETED,
            cost=total_member_responsibility + total_employer_responsibility,
        )

        if ex_mem_bill:
            ex_mem_bill = ex_mem_bill(
                cost_breakdown_id=cost_breakdown.id,
                procedure_id=treatment_procedure.id,
                payor_id=bill_wallet.id,
            )
        ex_emp_bill = ex_emp_bill(
            cost_breakdown_id=cost_breakdown.id,
            procedure_id=treatment_procedure.id,
            payor_id=bill_wallet.reimbursement_organization_settings.id,
        )
        if ex_clin_bill:
            ex_clin_bill = ex_clin_bill(
                cost_breakdown_id=cost_breakdown.id,
                procedure_id=treatment_procedure.id,
                payor_id=treatment_procedure.fertility_clinic_id,
            )

        with mock.patch(
            "common.payments_gateway.client.PaymentsGatewayClient.get_customer",
            side_effect=[
                mocked_customer(
                    ex_mem_bill.payment_method_type if ex_mem_bill else None
                ),
                mocked_employer_payor(),
            ],
        ):
            with mock.patch(
                "common.payments_gateway.client.PaymentsGatewayClient.create_transaction",
                return_value=mocked_transaction,
            ):
                with mock.patch("utils.braze.send_event_by_ids"):
                    create_member_and_employer_bill(
                        treatment_procedure.id,
                        cost_breakdown.id,
                        bill_wallet.id,
                        TreatmentProcedureStatus.COMPLETED,
                    )
        bills = billing_service.get_bills_by_procedure_ids([treatment_procedure.id])
        res_bills = {b.payor_type: b for b in bills}

        assert len(res_bills) == sum(
            [
                ex_mem_bill is not None,
                ex_emp_bill is not None,
                ex_clin_bill is not None,
            ]
        )
        if ex_mem_bill:
            res_mem_bill = res_bills[PayorType.MEMBER]
            assert res_mem_bill.status == ex_mem_bill.status
            assert res_mem_bill.amount == ex_mem_bill.amount
            assert res_mem_bill.last_calculated_fee == ex_mem_bill.last_calculated_fee
            assert res_mem_bill.payment_method_type == ex_mem_bill.payment_method_type
        else:
            assert res_bills.get(PayorType.MEMBER) is None

        res_emp_bill = res_bills[PayorType.EMPLOYER]
        assert res_emp_bill.status == ex_emp_bill.status
        assert res_emp_bill.amount == ex_emp_bill.amount
        assert res_emp_bill.last_calculated_fee == ex_emp_bill.last_calculated_fee
        assert res_emp_bill.payment_method_type == ex_emp_bill.payment_method_type

        if ex_clin_bill:
            res_clin_bill = res_bills[PayorType.CLINIC]
            assert res_clin_bill.status == ex_clin_bill.status
            assert res_clin_bill.amount == ex_clin_bill.amount
            assert res_clin_bill.last_calculated_fee == ex_clin_bill.last_calculated_fee
            assert res_clin_bill.payment_method_type == ex_clin_bill.payment_method_type

    @pytest.mark.parametrize(
        argnames="treatment_procedure_status, total_member_responsibility, total_employer_responsibility,  "
        "member_prev_bill, ex_mem_bill_1,  ex_mem_bill_2, ex_emp_bill,  ex_clin_bill,exp_bill_cnt",
        ids=[
            "0. Member responsibility decreased at treatment completion with a previous NEW bill - previous bill "
            "is cancelled and a new member bill and employer bill created.",
            "1. Member responsibility decreased at treatment completion with a previous NEW bill - previous bill "
            "is cancelled and a new member bill, 0 employer bill and a clinic bill created.",
        ],
        argvalues=[
            (
                TreatmentProcedureStatus.PARTIALLY_COMPLETED,
                11000,
                7000,
                partial(
                    factories.BillFactory.build,
                    payor_type=PayorType.MEMBER,
                    status=BillStatus.NEW,
                    amount=15000,
                    last_calculated_fee=450,
                    payment_method_type=PaymentMethodType.card,
                ),
                partial(
                    factories.BillFactory.build,
                    payor_type=PayorType.MEMBER,
                    status=BillStatus.REFUNDED,
                    amount=-4000,
                    last_calculated_fee=-120,
                    payment_method_type=PaymentMethodType.card,
                ),
                partial(
                    factories.BillFactory.build,
                    payor_type=PayorType.MEMBER,
                    status=BillStatus.NEW,
                    amount=11000,
                    last_calculated_fee=330,
                    payment_method_type=PaymentMethodType.card,
                ),
                partial(
                    factories.BillFactory.build,
                    payor_type=PayorType.EMPLOYER,
                    status=BillStatus.PROCESSING,
                    amount=7000,
                    last_calculated_fee=0,
                    payor_id=uuid.uuid4(),
                    payment_method_type=PaymentMethodType.us_bank_account,
                ),
                None,
                3,
            ),
            (
                TreatmentProcedureStatus.COMPLETED,
                11000,
                0,
                partial(
                    factories.BillFactory.build,
                    payor_type=PayorType.MEMBER,
                    status=BillStatus.NEW,
                    amount=15000,
                    last_calculated_fee=450,
                    payment_method_type=PaymentMethodType.card,
                ),
                partial(
                    factories.BillFactory.build,
                    payor_type=PayorType.MEMBER,
                    status=BillStatus.REFUNDED,
                    amount=-4000,
                    last_calculated_fee=-120,
                    payment_method_type=PaymentMethodType.card,
                ),
                partial(
                    factories.BillFactory.build,
                    payor_type=PayorType.MEMBER,
                    status=BillStatus.NEW,
                    amount=11000,
                    last_calculated_fee=330,
                    payment_method_type=PaymentMethodType.card,
                ),
                partial(
                    factories.BillFactory.build,
                    payor_type=PayorType.EMPLOYER,
                    status=BillStatus.PAID,
                    amount=0,
                    last_calculated_fee=0,
                    payor_id=uuid.uuid4(),
                    payment_method_type=None,
                ),
                partial(
                    factories.BillFactory.build,
                    payor_type=PayorType.CLINIC,
                    status=BillStatus.PROCESSING,
                    amount=11000,
                    last_calculated_fee=0,
                ),
                4,
            ),
        ],
    )
    def test_create_member_and_employer_bills_cancellation(
        self,
        billing_service,
        bill_wallet,
        mocked_customer,
        mocked_employer_payor,
        mocked_transaction,
        treatment_procedure_status,
        total_member_responsibility,
        total_employer_responsibility,
        member_prev_bill,
        ex_mem_bill_1,
        ex_mem_bill_2,
        ex_emp_bill,
        ex_clin_bill,
        exp_bill_cnt,
    ):
        wallet_benefit = ReimbursementWalletBenefitFactory.create()
        bill_wallet.reimbursement_wallet_benefit = wallet_benefit
        bill_wallet.reimbursement_organization_settings.payments_customer_id = str(
            uuid.uuid4()
        )
        cost_breakdown = CostBreakdownFactory.create(
            wallet_id=bill_wallet.id,
            total_member_responsibility=total_member_responsibility,
            total_employer_responsibility=total_employer_responsibility,
        )
        treatment_procedure = TreatmentProcedureFactory.create(
            reimbursement_wallet_id=bill_wallet.id,
            status=treatment_procedure_status,
            cost=total_member_responsibility + total_employer_responsibility,
        )

        member_prev_bill = member_prev_bill(
            cost_breakdown_id=cost_breakdown.id,
            procedure_id=treatment_procedure.id,
            payor_id=bill_wallet.id,
        )
        member_prev_bill = billing_service.bill_repo.create(instance=member_prev_bill)
        ex_mem_bill_1 = ex_mem_bill_1(
            cost_breakdown_id=cost_breakdown.id,
            procedure_id=treatment_procedure.id,
            payor_id=bill_wallet.id,
        )
        ex_mem_bill_2 = ex_mem_bill_2(
            cost_breakdown_id=cost_breakdown.id,
            procedure_id=treatment_procedure.id,
            payor_id=bill_wallet.id,
        )
        ex_emp_bill = ex_emp_bill(
            cost_breakdown_id=cost_breakdown.id,
            procedure_id=treatment_procedure.id,
            payor_id=bill_wallet.reimbursement_organization_settings.id,
        )
        if ex_clin_bill:
            ex_clin_bill = ex_clin_bill(
                cost_breakdown_id=cost_breakdown.id,
                procedure_id=treatment_procedure.id,
                payor_id=treatment_procedure.fertility_clinic_id,
            )

        with mock.patch(
            "common.payments_gateway.client.PaymentsGatewayClient.get_customer",
            side_effect=[
                mocked_customer(ex_mem_bill_1.payment_method_type),
                mocked_customer(ex_mem_bill_2.payment_method_type),
                mocked_employer_payor(),
            ],
        ):
            with mock.patch(
                "common.payments_gateway.client.PaymentsGatewayClient.create_transaction",
                return_value=mocked_transaction,
            ):
                with mock.patch("utils.braze.send_event_by_ids"):
                    create_member_and_employer_bill(
                        treatment_procedure.id,
                        cost_breakdown.id,
                        bill_wallet.id,
                        treatment_procedure_status,
                    )
        bills = billing_service.get_bills_by_procedure_ids([treatment_procedure.id])
        exp_cancelled_bill = billing_service.get_bill_by_id(member_prev_bill.id)
        assert exp_cancelled_bill.status == BillStatus.CANCELLED
        res_bills = {
            (b.payor_type, b.status): b for b in bills if b.id != member_prev_bill.id
        }
        assert len(res_bills) == exp_bill_cnt

        res_mem_bill_1 = res_bills[(ex_mem_bill_1.payor_type, ex_mem_bill_1.status)]
        assert res_mem_bill_1.status == ex_mem_bill_1.status
        assert res_mem_bill_1.amount == ex_mem_bill_1.amount
        assert res_mem_bill_1.last_calculated_fee == ex_mem_bill_1.last_calculated_fee
        assert res_mem_bill_1.payment_method_type == ex_mem_bill_1.payment_method_type

        res_mem_bill_2 = res_bills[(ex_mem_bill_2.payor_type, ex_mem_bill_2.status)]
        assert res_mem_bill_2.status == ex_mem_bill_2.status
        assert res_mem_bill_2.amount == ex_mem_bill_2.amount
        assert res_mem_bill_2.last_calculated_fee == ex_mem_bill_2.last_calculated_fee
        assert res_mem_bill_2.payment_method_type == ex_mem_bill_2.payment_method_type

        res_emp_bill = res_bills[ex_emp_bill.payor_type, ex_emp_bill.status]
        assert res_emp_bill.status == ex_emp_bill.status
        assert res_emp_bill.amount == ex_emp_bill.amount
        assert res_emp_bill.last_calculated_fee == ex_emp_bill.last_calculated_fee
        assert res_emp_bill.payment_method_type == ex_emp_bill.payment_method_type

        if ex_clin_bill:
            res_clin_bill = res_bills[(ex_clin_bill.payor_type, ex_clin_bill.status)]
            assert res_clin_bill.status == ex_clin_bill.status
            assert res_clin_bill.amount == ex_clin_bill.amount
            assert res_clin_bill.last_calculated_fee == ex_clin_bill.last_calculated_fee
            assert res_clin_bill.payment_method_type == ex_clin_bill.payment_method_type

    def test_create_member_bill_estimates_cancelled(
        self,
        bill_wallet,
        billing_service,
    ):
        cb = CostBreakdownFactory.create()
        tp = TreatmentProcedureFactory.create(
            status=TreatmentProcedureStatus.COMPLETED,
            cost_breakdown_id=cb.id,
            reimbursement_wallet_id=bill_wallet.id,
        )
        billing_service.bill_repo.create(
            instance=factories.BillFactory.build(
                procedure_id=tp.id,
                payor_type=PayorType.MEMBER,
                payor_id=bill_wallet.id,
                status=BillStatus.NEW,
                processing_scheduled_at_or_after=None,
                is_ephemeral=True,
            )
        )
        create_member_bill(
            wallet_id=bill_wallet.id,
            treatment_procedure_id=tp.id,
            treatment_procedure_status=TreatmentProcedureStatus.COMPLETED,
            cost_breakdown_id=cb.id,
        )
        canceled_estimate = billing_service.get_estimates_by_procedure_ids(
            procedure_ids=[tp.id], status=[BillStatus.CANCELLED]
        )[0]
        assert canceled_estimate.is_ephemeral is True
        assert (
            len(
                billing_service.get_estimates_by_procedure_ids(
                    procedure_ids=[tp.id], status=[BillStatus.REFUNDED]
                )
            )
            == 1
        )
        res_bills = billing_service.get_bills_by_procedure_ids(procedure_ids=[tp.id])
        assert len(res_bills) == 1
        res_bill = res_bills.pop()
        assert res_bill.status == BillStatus.PAID
        assert res_bill.amount == 0
        assert (
            len(billing_service.get_estimates_by_procedure_ids(procedure_ids=[tp.id]))
            == 2
        )

    def test_cancel_member_estimates_for_procedures_fail_partway(
        self,
        billing_service,
        bill_wallet,
    ):
        cb = CostBreakdownFactory.create()
        tp = TreatmentProcedureFactory.create(
            status=TreatmentProcedureStatus.COMPLETED,
            cost_breakdown_id=cb.id,
            reimbursement_wallet_id=bill_wallet.id,
        )
        billing_service.bill_repo.create(
            instance=factories.BillFactory.build(
                amount=10000,
                payor_type=PayorType.MEMBER,
                payor_id=bill_wallet.id,
                status=BillStatus.NEW,
                procedure_id=tp.id,
                processing_scheduled_at_or_after=None,
                is_ephemeral=True,
            )
        )
        with pytest.raises(KeyError):
            with mock.patch(
                "direct_payment.billing.billing_service.BillingService._cancel_bill_without_commit",
                side_effect=KeyError,
            ):
                create_member_bill(
                    wallet_id=bill_wallet.id,
                    treatment_procedure_id=tp.id,
                    treatment_procedure_status=TreatmentProcedureStatus.COMPLETED,
                    cost_breakdown_id=cb.id,
                )
                assert (
                    billing_service.get_bills_by_procedure_ids(
                        procedure_ids=[tp.id],
                        payor_id=bill_wallet.id,
                        payor_type=PayorType.MEMBER,
                        status=[BillStatus.REFUNDED, BillStatus.CANCELLED],
                    )
                    == []
                )
                assert (
                    len(
                        billing_service.get_bills_by_procedure_ids(
                            procedure_ids=[tp.id],
                            payor_id=bill_wallet.id,
                            payor_type=PayorType.MEMBER,
                            status=[BillStatus.NEW],
                        )
                    )
                    == 1
                )

    def test_tp_scheduled_no_bills_or_estimate_existed_zero_amount(
        self,
        bill_wallet,
        billing_service,
    ):
        cb = CostBreakdownFactory.create()
        tp = TreatmentProcedureFactory.create(
            status=TreatmentProcedureStatus.SCHEDULED,
            cost_breakdown_id=cb.id,
            reimbursement_wallet_id=bill_wallet.id,
        )
        create_member_bill(
            wallet_id=bill_wallet.id,
            treatment_procedure_id=tp.id,
            treatment_procedure_status=TreatmentProcedureStatus.SCHEDULED,
            cost_breakdown_id=cb.id,
        )
        estimate = billing_service.get_member_estimate_by_procedure(procedure_id=tp.id)
        assert estimate.is_ephemeral is True
        assert estimate.processing_scheduled_at_or_after is None
        assert estimate.status == BillStatus.NEW
        assert estimate.amount == 0

    def test_tp_scheduled_no_bills_or_estimate_existed_nonzero_amount(
        self,
        bill_wallet,
        billing_service,
    ):
        cb = CostBreakdownFactory.create(total_member_responsibility=2000)
        tp = TreatmentProcedureFactory.create(
            status=TreatmentProcedureStatus.SCHEDULED,
            cost_breakdown_id=cb.id,
            reimbursement_wallet_id=bill_wallet.id,
        )
        create_member_bill(
            wallet_id=bill_wallet.id,
            treatment_procedure_id=tp.id,
            treatment_procedure_status=TreatmentProcedureStatus.SCHEDULED,
            cost_breakdown_id=cb.id,
        )
        estimate = billing_service.get_member_estimate_by_procedure(procedure_id=tp.id)
        assert estimate.is_ephemeral is True
        assert estimate.processing_scheduled_at_or_after is None
        assert estimate.status == BillStatus.NEW
        assert estimate.amount == 2000

    def test_tp_scheduled_less_estimate_existed_no_bills(
        self,
        bill_wallet,
        billing_service,
    ):
        """
        Test scenario where an estimate already existed and a cost breakdown is run to yield an increased member
        responsibility. We want to verify that the previous estimate is cancelled and a new one for the correct
        amount is generated,and that no other bills are created.
        """
        procedure_id, cost_breakdown_id = estimate_bills_setup(
            billing_service=billing_service,
            bill_wallet=bill_wallet,
            member_responsibility=2000,
            tp_status=TreatmentProcedureStatus.SCHEDULED,
            estimate_amount=1000,
            bill_amount=None,
            bill_status=None,
            create_bpr=False,
        )
        create_member_bill(
            wallet_id=bill_wallet.id,
            treatment_procedure_id=procedure_id,
            treatment_procedure_status=TreatmentProcedureStatus.SCHEDULED,
            cost_breakdown_id=cost_breakdown_id,
        )
        assert (
            len(
                billing_service.get_bills_by_procedure_ids(procedure_ids=[procedure_id])
            )
            == 0
        )
        assert (
            len(
                billing_service.get_estimates_by_procedure_ids(
                    procedure_ids=[procedure_id], status=[BillStatus.REFUNDED]
                )
            )
            == 1
        )
        old_estimate = billing_service.get_estimates_by_procedure_ids(
            procedure_ids=[procedure_id], status=[BillStatus.CANCELLED]
        )
        assert len(old_estimate) == 1
        assert old_estimate[0].amount == 1000
        estimate = billing_service.get_member_estimate_by_procedure(
            procedure_id=procedure_id
        )
        assert estimate.is_ephemeral is True
        assert estimate.processing_scheduled_at_or_after is None
        assert estimate.status == BillStatus.NEW
        assert estimate.amount == 2000

    def test_tp_scheduled_more_estimate_existed_no_bills(
        self,
        bill_wallet,
        billing_service,
    ):
        """
        Test scenario where an estimate already existed and a cost breakdown is run to yield a lesser member
        responsibility. We want to verify that the previous estimate is cancelled and a new one for the correct
        amount is generated,and that no other bills are created.
        """
        procedure_id, cost_breakdown_id = estimate_bills_setup(
            billing_service=billing_service,
            bill_wallet=bill_wallet,
            member_responsibility=2000,
            tp_status=TreatmentProcedureStatus.SCHEDULED,
            estimate_amount=3000,
            bill_amount=None,
            bill_status=None,
            create_bpr=False,
        )
        create_member_bill(
            wallet_id=bill_wallet.id,
            treatment_procedure_id=procedure_id,
            treatment_procedure_status=TreatmentProcedureStatus.SCHEDULED,
            cost_breakdown_id=cost_breakdown_id,
        )
        assert (
            len(
                billing_service.get_bills_by_procedure_ids(procedure_ids=[procedure_id])
            )
            == 0
        )
        assert (
            len(
                billing_service.get_estimates_by_procedure_ids(
                    procedure_ids=[procedure_id], status=[BillStatus.REFUNDED]
                )
            )
            == 1
        )
        assert (
            len(
                billing_service.get_estimates_by_procedure_ids(
                    procedure_ids=[procedure_id], status=[BillStatus.CANCELLED]
                )
            )
            == 1
        )
        estimate = billing_service.get_member_estimate_by_procedure(
            procedure_id=procedure_id
        )
        assert estimate.is_ephemeral is True
        assert estimate.processing_scheduled_at_or_after is None
        assert estimate.status == BillStatus.NEW
        assert estimate.amount == 2000

    def test_tp_scheduled_equal_estimate_existed_no_bills(
        self,
        bill_wallet,
        billing_service,
    ):
        """
        Test scenario where an estimate already existed and a cost breakdown is run to yield an equivalent member
        responsibility. We want to verify that the estimate amount remains unchanged and no other bills are created.
        """
        procedure_id, cost_breakdown_id = estimate_bills_setup(
            billing_service=billing_service,
            bill_wallet=bill_wallet,
            member_responsibility=2000,
            tp_status=TreatmentProcedureStatus.SCHEDULED,
            estimate_amount=2000,
            bill_amount=None,
            bill_status=None,
            create_bpr=False,
        )
        create_member_bill(
            wallet_id=bill_wallet.id,
            treatment_procedure_id=procedure_id,
            treatment_procedure_status=TreatmentProcedureStatus.SCHEDULED,
            cost_breakdown_id=cost_breakdown_id,
        )
        assert (
            len(
                billing_service.get_bills_by_procedure_ids(procedure_ids=[procedure_id])
            )
            == 0
        )
        estimate = billing_service.get_member_estimate_by_procedure(
            procedure_id=procedure_id
        )
        assert estimate.is_ephemeral is True
        assert estimate.processing_scheduled_at_or_after is None
        assert estimate.status == BillStatus.NEW
        assert estimate.amount == 2000

    def test_tp_scheduled_negative_delta_paid_bill_with_estimate(
        self,
        bill_wallet,
        billing_service,
        mocked_transaction,
    ):
        """
        Test scenario where member was already issued a bill for 4000 and it is in a PAID state, they have an estimate
        to be charged 2000 more,
        and cost breakdown has yielded a decreased member responsibility of 2000. We want to refund the 2000 the
        member was overcharged, and no new estimate should be generated, the pre-existing estimate should be cancelled.
        """
        procedure_id, cost_breakdown_id = estimate_bills_setup(
            billing_service=billing_service,
            bill_wallet=bill_wallet,
            member_responsibility=2000,
            tp_status=TreatmentProcedureStatus.SCHEDULED,
            estimate_amount=2000,
            bill_amount=4000,
            bill_status=BillStatus.PAID,
            create_bpr=True,
        )
        with mock.patch(
            "common.payments_gateway.client.PaymentsGatewayClient.create_transaction",
            return_value=mocked_transaction,
        ) as pg_mock:
            create_member_bill(
                wallet_id=bill_wallet.id,
                treatment_procedure_id=procedure_id,
                treatment_procedure_status=TreatmentProcedureStatus.SCHEDULED,
                cost_breakdown_id=cost_breakdown_id,
            )
            assert (
                len(
                    billing_service.get_bills_by_procedure_ids(
                        procedure_ids=[procedure_id]
                    )
                )
                == 2
            )
            estimates = billing_service.get_estimates_by_procedure_ids(
                procedure_ids=[procedure_id], status=[BillStatus.CANCELLED]
            )
            assert len(estimates) == 1
            estimate = estimates[0]
            assert estimate.status == BillStatus.CANCELLED
            assert estimate.amount == 2000
            assert (
                len(
                    billing_service.get_bills_by_procedure_ids(
                        procedure_ids=[procedure_id], status=[BillStatus.PAID]
                    )
                )
                == 1
            )
            assert (
                len(
                    billing_service.get_estimates_by_procedure_ids(
                        procedure_ids=[procedure_id], status=[BillStatus.REFUNDED]
                    )
                )
                == 1
            )
            processing_refund = billing_service.get_bills_by_procedure_ids(
                procedure_ids=[procedure_id], status=[BillStatus.PROCESSING]
            )
            assert len(processing_refund) == 1
            assert processing_refund[0].amount == -2000
            assert processing_refund[0].is_ephemeral is False
            assert processing_refund[0].processing_scheduled_at_or_after is not None
            assert (
                billing_service.get_member_estimate_by_procedure(
                    procedure_id=procedure_id
                )
                is None
            )
            assert pg_mock.call_count == 1

    def test_tp_scheduled_negative_delta_new_bill_with_estimate(
        self,
        bill_wallet,
        billing_service,
        mocked_customer,
    ):
        """
        Test scenario where member was already issued a bill for 4000 but it is in a NEW state
        and cost breakdown has yielded a decreased member responsibility of 2000. We want to cancel the
        original bill of 4000 and have an estimate of 2000 ultimately.

        Note that without a major refactor of the billing service, the best way to handle setting the delta bill to be
        an estimate is to check for the TP status deep inside the billing code. So note this side effect - if a TP
        is in scheduled the delta_bill becomes an estimate, otherwise it is not an estimate bill.
        """
        procedure_id, cost_breakdown_id = estimate_bills_setup(
            billing_service=billing_service,
            bill_wallet=bill_wallet,
            member_responsibility=2000,
            tp_status=TreatmentProcedureStatus.SCHEDULED,
            estimate_amount=2000,
            bill_amount=4000,
            bill_status=BillStatus.NEW,
            create_bpr=False,
        )
        create_member_bill(
            wallet_id=bill_wallet.id,
            treatment_procedure_id=procedure_id,
            treatment_procedure_status=TreatmentProcedureStatus.SCHEDULED,
            cost_breakdown_id=cost_breakdown_id,
        )
        assert (
            len(
                billing_service.get_bills_by_procedure_ids(procedure_ids=[procedure_id])
            )
            == 2
        )
        cancelled = billing_service.get_bills_by_procedure_ids(
            procedure_ids=[procedure_id], status=[BillStatus.CANCELLED]
        )
        assert len(cancelled) == 1
        assert cancelled[0].amount == 4000
        processing_refund = billing_service.get_bills_by_procedure_ids(
            procedure_ids=[procedure_id], status=[BillStatus.REFUNDED]
        )
        assert len(processing_refund) == 1
        assert processing_refund[0].amount == -2000
        assert processing_refund[0].is_ephemeral is False
        assert processing_refund[0].processing_scheduled_at_or_after is not None
        estimate = billing_service.get_member_estimate_by_procedure(
            procedure_id=procedure_id
        )
        assert estimate.status == BillStatus.NEW
        assert estimate.amount == 2000

    def test_tp_scheduled_negative_delta_paid_bill_no_estimate(
        self,
        bill_wallet,
        billing_service,
        mocked_transaction,
    ):
        """
        Test scenario where member was already issued a bill for 4000 and it is in a PAID state
        and cost breakdown has yielded a decreased member responsibility of 2000, and there is no pre-existing estimate.
        We want to refund the delta of 2000, with no estimate needed.
        """
        procedure_id, cost_breakdown_id = estimate_bills_setup(
            billing_service=billing_service,
            bill_wallet=bill_wallet,
            member_responsibility=2000,
            tp_status=TreatmentProcedureStatus.SCHEDULED,
            estimate_amount=None,
            bill_amount=4000,
            bill_status=BillStatus.PAID,
            create_bpr=True,
        )
        with mock.patch(
            "common.payments_gateway.client.PaymentsGatewayClient.create_transaction",
            return_value=mocked_transaction,
        ) as pg_mock:
            create_member_bill(
                wallet_id=bill_wallet.id,
                treatment_procedure_id=procedure_id,
                treatment_procedure_status=TreatmentProcedureStatus.SCHEDULED,
                cost_breakdown_id=cost_breakdown_id,
            )
            assert (
                len(
                    billing_service.get_bills_by_procedure_ids(
                        procedure_ids=[procedure_id]
                    )
                )
                == 2
            )
            processing_refund = billing_service.get_bills_by_procedure_ids(
                procedure_ids=[procedure_id], status=[BillStatus.PROCESSING]
            )
            assert len(processing_refund) == 1
            assert processing_refund[0].amount == -2000
            assert processing_refund[0].is_ephemeral is False
            assert processing_refund[0].processing_scheduled_at_or_after is not None
            assert (
                billing_service.get_member_estimate_by_procedure(
                    procedure_id=procedure_id
                )
                is None
            )
            assert pg_mock.call_count == 1

    def test_tp_scheduled_negative_delta_new_bill_no_estimate(
        self,
        bill_wallet,
        billing_service,
    ):
        """
        Test scenario where member was already issued a bill for 4000 but it is in a NEW state
        and cost breakdown has yielded a decreased member responsibility of 2000. We want to cancel the
        original bill of 4000 and issue an estimate for the delta of 2000.
        """
        procedure_id, cost_breakdown_id = estimate_bills_setup(
            billing_service=billing_service,
            bill_wallet=bill_wallet,
            member_responsibility=2000,
            tp_status=TreatmentProcedureStatus.SCHEDULED,
            estimate_amount=None,
            bill_amount=4000,
            bill_status=BillStatus.NEW,
            create_bpr=False,
        )
        create_member_bill(
            wallet_id=bill_wallet.id,
            treatment_procedure_id=procedure_id,
            treatment_procedure_status=TreatmentProcedureStatus.SCHEDULED,
            cost_breakdown_id=cost_breakdown_id,
        )
        assert (
            len(
                billing_service.get_bills_by_procedure_ids(procedure_ids=[procedure_id])
            )
            == 2
        )
        cancelled = billing_service.get_bills_by_procedure_ids(
            procedure_ids=[procedure_id], status=[BillStatus.CANCELLED]
        )
        assert len(cancelled) == 1
        assert cancelled[0].amount == 4000
        processing_refund = billing_service.get_bills_by_procedure_ids(
            procedure_ids=[procedure_id], status=[BillStatus.REFUNDED]
        )
        assert len(processing_refund) == 1
        assert processing_refund[0].amount == -2000
        assert processing_refund[0].is_ephemeral is False
        assert processing_refund[0].processing_scheduled_at_or_after is not None
        estimate = billing_service.get_member_estimate_by_procedure(
            procedure_id=procedure_id
        )
        assert estimate.status == BillStatus.NEW
        assert estimate.amount == 2000

    def test_tp_scheduled_positive_delta_with_estimate(
        self,
        bill_wallet,
        billing_service,
    ):
        """
        Test scenario where member was already issued a bill for 4000 and it is in a PAID state
        and cost breakdown has yielded a increased member responsibility of 6000, and there is a pre-existing estimate.
        We want to verify there is only an estimate of 2000 in addition to the paid bill.
        """
        procedure_id, cost_breakdown_id = estimate_bills_setup(
            billing_service=billing_service,
            bill_wallet=bill_wallet,
            member_responsibility=6000,
            tp_status=TreatmentProcedureStatus.SCHEDULED,
            estimate_amount=2000,
            bill_amount=4000,
            bill_status=BillStatus.PAID,
            create_bpr=True,
        )
        estimate = billing_service.get_member_estimate_by_procedure(
            procedure_id=procedure_id
        )
        create_member_bill(
            wallet_id=bill_wallet.id,
            treatment_procedure_id=procedure_id,
            treatment_procedure_status=TreatmentProcedureStatus.SCHEDULED,
            cost_breakdown_id=cost_breakdown_id,
        )
        after_estimate = billing_service.get_member_estimate_by_procedure(
            procedure_id=procedure_id
        )
        assert after_estimate.status == BillStatus.NEW
        assert after_estimate.id == estimate.id
        assert after_estimate.amount == 2000
        assert (
            len(
                billing_service.get_bills_by_procedure_ids(procedure_ids=[procedure_id])
            )
            == 1
        )

    def test_tp_scheduled_positive_delta_no_estimate(
        self,
        bill_wallet,
        billing_service,
    ):
        """
        Test scenario where member was already issued a bill for 4000 and it is in a PAID state
        and cost breakdown has yielded a increased member responsibility of 6000, and there is no pre-existing estimate.
        We want to verify there is only an estimate of 2000 in addition to the paid bill.
        """
        procedure_id, cost_breakdown_id = estimate_bills_setup(
            billing_service=billing_service,
            bill_wallet=bill_wallet,
            member_responsibility=6000,
            tp_status=TreatmentProcedureStatus.SCHEDULED,
            estimate_amount=None,
            bill_amount=4000,
            bill_status=BillStatus.PAID,
            create_bpr=True,
        )
        assert (
            billing_service.get_member_estimate_by_procedure(procedure_id=procedure_id)
            is None
        )
        create_member_bill(
            wallet_id=bill_wallet.id,
            treatment_procedure_id=procedure_id,
            treatment_procedure_status=TreatmentProcedureStatus.SCHEDULED,
            cost_breakdown_id=cost_breakdown_id,
        )
        estimate = billing_service.get_member_estimate_by_procedure(
            procedure_id=procedure_id
        )
        assert estimate.status == BillStatus.NEW
        assert estimate.amount == 2000
        assert (
            len(
                billing_service.get_bills_by_procedure_ids(procedure_ids=[procedure_id])
            )
            == 1
        )

    def test_tp_completed_positive_delta(
        self,
        bill_wallet,
        billing_service,
    ):
        """
        Test scenario where member was already issued a bill for 4000 and it is in a PAID state
        and cost breakdown has yielded a increased member responsibility of 6000, and there is a pre-existing estimate.
        We want to verify the estimate is canceled and a new bill is created for the delta
        """
        procedure_id, cost_breakdown_id = estimate_bills_setup(
            billing_service=billing_service,
            bill_wallet=bill_wallet,
            member_responsibility=6000,
            tp_status=TreatmentProcedureStatus.COMPLETED,
            estimate_amount=2000,
            bill_amount=4000,
            bill_status=BillStatus.PAID,
            create_bpr=True,
        )
        create_member_bill(
            wallet_id=bill_wallet.id,
            treatment_procedure_id=procedure_id,
            treatment_procedure_status=TreatmentProcedureStatus.COMPLETED,
            cost_breakdown_id=cost_breakdown_id,
        )
        assert (
            billing_service.get_member_estimate_by_procedure(procedure_id=procedure_id)
            is None
        )
        assert (
            len(
                billing_service.get_estimates_by_procedure_ids(
                    procedure_ids=[procedure_id],
                    status=[BillStatus.CANCELLED, BillStatus.REFUNDED],
                )
            )
            == 2
        )
        assert (
            len(
                billing_service.get_bills_by_procedure_ids(
                    procedure_ids=[procedure_id], status=[BillStatus.PAID]
                )
            )
            == 1
        )
        assert (
            len(
                billing_service.get_bills_by_procedure_ids(
                    procedure_ids=[procedure_id], status=[BillStatus.NEW]
                )
            )
            == 1
        )
        assert (
            len(
                billing_service.get_bills_by_procedure_ids(procedure_ids=[procedure_id])
            )
            == 2
        )

    def test_tp_completed_negative_delta_paid(
        self,
        bill_wallet,
        billing_service,
        mocked_transaction,
    ):
        """
        Test scenario where member was already issued a bill for 4000 and it is in a PAID state
        and cost breakdown has yielded a decreased member responsibility of 2000, and there is a pre-existing estimate.
        We want to verify the estimate is canceled and a refund of 2000 is created.
        """
        procedure_id, cost_breakdown_id = estimate_bills_setup(
            billing_service=billing_service,
            bill_wallet=bill_wallet,
            member_responsibility=2000,
            tp_status=TreatmentProcedureStatus.COMPLETED,
            estimate_amount=2000,
            bill_amount=4000,
            bill_status=BillStatus.PAID,
            create_bpr=True,
        )
        with mock.patch(
            "common.payments_gateway.client.PaymentsGatewayClient.create_transaction",
            return_value=mocked_transaction,
        ) as pg_mock:
            create_member_bill(
                wallet_id=bill_wallet.id,
                treatment_procedure_id=procedure_id,
                treatment_procedure_status=TreatmentProcedureStatus.COMPLETED,
                cost_breakdown_id=cost_breakdown_id,
            )
            assert (
                billing_service.get_member_estimate_by_procedure(
                    procedure_id=procedure_id
                )
                is None
            )
            assert (
                len(
                    billing_service.get_estimates_by_procedure_ids(
                        procedure_ids=[procedure_id],
                        status=[BillStatus.CANCELLED, BillStatus.REFUNDED],
                    )
                )
                == 2
            )
            assert (
                len(
                    billing_service.get_bills_by_procedure_ids(
                        procedure_ids=[procedure_id], status=[BillStatus.PAID]
                    )
                )
                == 1
            )
            new_bills = billing_service.get_bills_by_procedure_ids(
                procedure_ids=[procedure_id], status=[BillStatus.PROCESSING]
            )
            assert len(new_bills) == 1
            assert new_bills[0].amount == -2000
            assert (
                len(
                    billing_service.get_bills_by_procedure_ids(
                        procedure_ids=[procedure_id]
                    )
                )
                == 2
            )
            assert pg_mock.call_count == 1

    def test_tp_completed_negative_delta_new(
        self,
        bill_wallet,
        billing_service,
    ):
        """
        Test scenario where member was already issued a bill for 4000 and it is in a NEW state,
        and cost breakdown has yielded a decreased member responsibility of 2000, and there is a pre-existing estimate.
        We want to verify the pre-existing bill and estimate are cancelled, and a bill for the delta is created.
        """
        procedure_id, cost_breakdown_id = estimate_bills_setup(
            billing_service=billing_service,
            bill_wallet=bill_wallet,
            member_responsibility=2000,
            tp_status=TreatmentProcedureStatus.PARTIALLY_COMPLETED,
            estimate_amount=2000,
            bill_amount=4000,
            bill_status=BillStatus.NEW,
            create_bpr=False,
        )
        create_member_bill(
            wallet_id=bill_wallet.id,
            treatment_procedure_id=procedure_id,
            treatment_procedure_status=TreatmentProcedureStatus.PARTIALLY_COMPLETED,
            cost_breakdown_id=cost_breakdown_id,
        )
        assert (
            billing_service.get_member_estimate_by_procedure(procedure_id=procedure_id)
            is None
        )
        assert (
            len(
                billing_service.get_estimates_by_procedure_ids(
                    procedure_ids=[procedure_id],
                    status=[BillStatus.CANCELLED, BillStatus.REFUNDED],
                )
            )
            == 2
        )
        assert (
            len(
                billing_service.get_bills_by_procedure_ids(
                    procedure_ids=[procedure_id], status=[BillStatus.CANCELLED]
                )
            )
            == 1
        )
        assert (
            len(
                billing_service.get_bills_by_procedure_ids(
                    procedure_ids=[procedure_id], status=[BillStatus.REFUNDED]
                )
            )
            == 1
        )
        new_bills = billing_service.get_bills_by_procedure_ids(
            procedure_ids=[procedure_id], status=[BillStatus.NEW]
        )
        assert len(new_bills) == 1
        assert new_bills[0].amount == 2000
        assert (
            len(
                billing_service.get_bills_by_procedure_ids(procedure_ids=[procedure_id])
            )
            == 3
        )

    def test_tp_completed_no_delta_paid(
        self,
        bill_wallet,
        billing_service,
    ):
        """
        Test scenario where member was already issued a bill for 2000 and it is in a PAID state
        and cost breakdown with no change to member responsibility, and there is a pre-existing estimate.
        We want to verify the estimate is canceled and no other bills are created.
        """
        procedure_id, cost_breakdown_id = estimate_bills_setup(
            billing_service=billing_service,
            bill_wallet=bill_wallet,
            member_responsibility=2000,
            tp_status=TreatmentProcedureStatus.COMPLETED,
            estimate_amount=2000,
            bill_amount=2000,
            bill_status=BillStatus.PAID,
            create_bpr=True,
        )
        create_member_bill(
            wallet_id=bill_wallet.id,
            treatment_procedure_id=procedure_id,
            treatment_procedure_status=TreatmentProcedureStatus.COMPLETED,
            cost_breakdown_id=cost_breakdown_id,
        )
        assert (
            billing_service.get_member_estimate_by_procedure(procedure_id=procedure_id)
            is None
        )
        assert (
            len(
                billing_service.get_estimates_by_procedure_ids(
                    procedure_ids=[procedure_id],
                    status=[BillStatus.CANCELLED, BillStatus.REFUNDED],
                )
            )
            == 2
        )
        assert (
            len(
                billing_service.get_bills_by_procedure_ids(procedure_ids=[procedure_id])
            )
            == 1
        )

    def test_tp_scheduled_no_delta_paid_no_estimate(
        self,
        bill_wallet,
        billing_service,
    ):
        """
        Test scenario where member was already issued a bill for 2000 and it is in a PAID state
        and cost breakdown with no change to member responsibility, and there is no pre-existing estimate.
        We want to verify that no estimates or bills are created.
        """
        procedure_id, cost_breakdown_id = estimate_bills_setup(
            billing_service=billing_service,
            bill_wallet=bill_wallet,
            member_responsibility=2000,
            tp_status=TreatmentProcedureStatus.SCHEDULED,
            estimate_amount=None,
            bill_amount=2000,
            bill_status=BillStatus.PAID,
            create_bpr=True,
        )
        create_member_bill(
            wallet_id=bill_wallet.id,
            treatment_procedure_id=procedure_id,
            treatment_procedure_status=TreatmentProcedureStatus.SCHEDULED,
            cost_breakdown_id=cost_breakdown_id,
        )
        assert (
            billing_service.get_member_estimate_by_procedure(procedure_id=procedure_id)
            is None
        )
        assert (
            len(
                billing_service.get_bills_by_procedure_ids(procedure_ids=[procedure_id])
            )
            == 1
        )

    def test_tp_canceled(
        self,
        bill_wallet,
        billing_service,
    ):
        """
        Test scenario where member was already issued a bill for 4000 and it is in a NEW state,
        and there is a pre-existing estimate.
        We want to verify the estimate is canceled, bill is canceled, and a refund is created.
        """
        procedure_id, cost_breakdown_id = estimate_bills_setup(
            billing_service=billing_service,
            bill_wallet=bill_wallet,
            member_responsibility=4000,
            tp_status=TreatmentProcedureStatus.CANCELLED,
            estimate_amount=2000,
            bill_amount=4000,
            bill_status=BillStatus.NEW,
            create_bpr=True,
        )
        create_member_bill(
            wallet_id=bill_wallet.id,
            treatment_procedure_id=procedure_id,
            treatment_procedure_status=TreatmentProcedureStatus.CANCELLED,
            cost_breakdown_id=cost_breakdown_id,
        )
        assert (
            billing_service.get_member_estimate_by_procedure(procedure_id=procedure_id)
            is None
        )
        assert (
            len(
                billing_service.get_estimates_by_procedure_ids(
                    procedure_ids=[procedure_id],
                    status=[BillStatus.CANCELLED, BillStatus.REFUNDED],
                )
            )
            == 2
        )
        assert (
            len(
                billing_service.get_bills_by_procedure_ids(
                    procedure_ids=[procedure_id],
                    status=[BillStatus.CANCELLED, BillStatus.REFUNDED],
                )
            )
            == 0
        )
        assert (
            len(
                billing_service.get_bills_by_procedure_ids(
                    procedure_ids=[procedure_id], status=[BillStatus.PROCESSING]
                )
            )
            == 0
        )
