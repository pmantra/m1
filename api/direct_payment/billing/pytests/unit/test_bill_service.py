import datetime
import json
import uuid
from collections import defaultdict
from datetime import date
from functools import partial
from unittest import mock
from unittest.mock import PropertyMock, patch

import factory
import pytest
import sqlalchemy
from requests import Response

from common.payments_gateway import (
    Customer,
    PaymentsGatewayException,
    RefundPayload,
    Transaction,
    TransactionPayload,
    TransferReversePayload,
)
from cost_breakdown.pytests.factories import CostBreakdownFactory
from direct_payment.billing import errors
from direct_payment.billing.billing_service import (
    REFUND_BILL,
    from_employer_bill_create_clinic_bill_and_process,
    from_employer_bill_create_clinic_bill_with_billing_service,
    retry_failed_bills,
)
from direct_payment.billing.constants import DEFAULT_GATEWAY_ERROR_RESPONSE, OTHER_MAVEN
from direct_payment.billing.errors import (
    InvalidBillTreatmentProcedureCancelledError,
    InvalidEphemeralBillOperationError,
    InvalidRefundBillCreationError,
)
from direct_payment.billing.models import (
    BillErrorTypes,
    BillStatus,
    CardFunding,
    PaymentMethod,
    PaymentMethodType,
    PayorType,
)
from direct_payment.billing.pytests import factories
from direct_payment.clinic.pytests.factories import (
    FeeScheduleFactory,
    FeeScheduleGlobalProceduresFactory,
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
from direct_payment.treatment_procedure.repository.treatment_procedure import (
    TreatmentProcedureRepository,
)
from pytests import freezegun
from pytests.factories import MemberBenefitFactory
from wallet.models.constants import WalletState
from wallet.models.reimbursement_wallet import ReimbursementWallet
from wallet.pytests.factories import (
    ReimbursementRequestCategoryFactory,
    ReimbursementWalletBenefitFactory,
    ReimbursementWalletFactory,
    ReimbursementWalletUsersFactory,
)

TEST_WALLET_ID = 121010121
REUSABLE_UUID = uuid.uuid4()
BILL_AMOUNT = 1000
A_BENEFIT_ID = "1233321"
A_MEMBER_LEVEL_BENEFIT_ID = "M123456789"
CURRENT_TIME = datetime.datetime(2024, 3, 1, 10, 30, 0)
OFFSET_TIME = datetime.datetime(2024, 3, 8, 10, 30, 0)


@pytest.fixture
def bill_processing_record_statuses():
    return [
        [BillStatus.PROCESSING, BillStatus.PAID],
        [BillStatus.PROCESSING],
        [BillStatus.NEW, BillStatus.PROCESSING, BillStatus.PAID],
        [BillStatus.NEW, BillStatus.PROCESSING, BillStatus.PAID, BillStatus.REFUNDED],
        [BillStatus.NEW],
    ]


@pytest.fixture
def reimbursement_wallet_with_benefit(enterprise_user):
    to_return = ReimbursementWalletFactory.create(
        id=TEST_WALLET_ID, state=WalletState.QUALIFIED
    )
    ReimbursementWalletBenefitFactory.create(
        reimbursement_wallet=to_return, maven_benefit_id=A_BENEFIT_ID
    )
    return to_return


@pytest.fixture
def reimbursement_wallet_user(reimbursement_wallet_with_benefit, enterprise_user):
    to_return = ReimbursementWalletUsersFactory.create(
        reimbursement_wallet_id=reimbursement_wallet_with_benefit.id,
        user_id=enterprise_user.id,
    )
    return to_return


@pytest.fixture
def member_benefit(reimbursement_wallet_user):
    to_return = MemberBenefitFactory.create(
        user_id=reimbursement_wallet_user.user_id,
        benefit_id=A_MEMBER_LEVEL_BENEFIT_ID,
    )
    return to_return


@pytest.fixture
def bill_for_multi_refund_fixture():
    def fn(billing_service, bpr_statuses, refund_factor, create_refund_bill=True):
        bill = billing_service.bill_repo.create(
            instance=(
                factories.BillFactory.build(
                    status=BillStatus.PAID,
                    amount=1_000_000,
                    last_calculated_fee=30_000,
                    procedure_id=TreatmentProcedureFactory.create(
                        status=TreatmentProcedureStatus.COMPLETED,
                    ).id,
                )
            )
        )
        trans_id = uuid.uuid4()
        for bpr_status in bpr_statuses:
            bpr = factories.BillProcessingRecordFactory.build(
                bill_id=bill.id,
                transaction_id=trans_id,
                processing_record_type="a_string",
                bill_status=bpr_status.value,
                created_at=datetime.datetime.now(),
            )
            if BillStatus.REFUNDED == bpr_status:
                refund_bill = None
                if create_refund_bill:
                    refund_bill = billing_service.bill_repo.create(
                        instance=(
                            factories.BillFactory.build(
                                status=BillStatus.REFUNDED,
                                amount=-bill.amount * refund_factor,
                                procedure_id=bill.procedure_id,
                                cost_breakdown_id=bill.cost_breakdown_id,
                                label=bill.label,
                                last_calculated_fee=-bill.last_calculated_fee
                                * refund_factor,
                            )
                        )
                    )
                bpr.body = {REFUND_BILL: refund_bill.id if refund_bill else 12345}
            _ = billing_service.bill_processing_record_repo.create(instance=(bpr))
        return bill

    return fn


@pytest.fixture
def create_cancelled_tp():
    def fn(input_wallet):
        tp_repo = TreatmentProcedureRepository()
        tp = TreatmentProcedureFactory.create()
        cat = ReimbursementRequestCategoryFactory.create(
            label="category",
        )
        with patch.object(
            ReimbursementWallet,
            "get_direct_payment_category",
            new=PropertyMock(return_value=cat),
        ):

            fee_schedule = FeeScheduleFactory.create()
            FeeScheduleGlobalProceduresFactory.create(
                fee_schedule=fee_schedule,
                global_procedure_id=tp.global_procedure_id,
                cost=10000,
            )
            tp = tp_repo.create(
                member_id=tp.member_id,
                reimbursement_wallet_id=input_wallet.id,
                reimbursement_request_category_id=cat.id,
                fee_schedule_id=fee_schedule.id,
                global_procedure_id=tp.global_procedure_id,
                global_procedure_name=tp.procedure_name,
                global_procedure_credits=tp.cost_credit,
                fertility_clinic_id=tp.fertility_clinic_id,
                fertility_clinic_location_id=tp.fertility_clinic_location_id,
                start_date=tp.start_date,
                status=TreatmentProcedureStatus.CANCELLED,
            )
        return tp

    return fn


class TestBillQueries:
    def test_get_bills_by_procedure_missing_payor(self, billing_service):
        with pytest.raises(TypeError):
            billing_service.get_bills_by_procedure_ids(
                procedure_ids=[1, 2],
                payor_id=None,
                payor_type=PayorType.MEMBER,
            )

    def test_get_bills_by_procedure_missing_type(self, billing_service):
        with pytest.raises(TypeError):
            billing_service.get_bills_by_procedure_ids(
                procedure_ids=[1, 2],
                payor_id=100,
                payor_type=None,
            )

    def test_get_no_bills_by_procedure(self, billing_service):
        res = billing_service.get_bills_by_procedure_ids(
            procedure_ids=[1, 2],
            payor_id=0,
            payor_type=PayorType.MEMBER,
        )
        assert res == []

    @pytest.mark.parametrize(
        argnames="expected_tp_expected_bills,",
        argvalues=(
            [
                {0: [0], 1: [1, 3], 2: [4]},
                {2: [4]},
                {1: [1, 3]},
                {
                    1: [1, 3],
                    2: [4],
                },
            ]
        ),
        ids=[
            "all procedures",
            "last procedure",
            "first procedure",
            "two procedures",
        ],
    )
    def test_get_member_paid_by_procedure_ids(
        self,
        billing_service,
        member_bills_for_procedures_specific_times,
        member_paid_with_bpr_for_bills,
        expected_tp_expected_bills,
    ):
        tps = [tp for tp in expected_tp_expected_bills]
        results = billing_service.get_member_paid_by_procedure_ids(procedure_ids=tps)
        expected = defaultdict(list)
        for expected_tp, expected_bills in expected_tp_expected_bills.items():
            for bill in expected_bills:
                expected[expected_tp].append(
                    member_bills_for_procedures_specific_times[bill]
                )
        for tp, bills in results.items():
            assert len(bills) == len(expected[tp])
            for bill in bills:
                assert bill in expected[tp]

    def test_get_estimates_by_procedure(
        self, billing_service, several_bills_two_estimates
    ):
        procedure_ids = [
            b.procedure_id for b in several_bills_two_estimates if b.is_ephemeral
        ]
        all_procedure_estimates = billing_service.get_estimates_by_procedure_ids(
            procedure_ids
        )

        assert len(all_procedure_estimates) == len(procedure_ids)

    @pytest.mark.parametrize(
        "past_bill_count, past_bill_fees, expected_fee",
        [
            (0, [0], 0),
            (3, [1, 5, 0], 6),
            (2, [10, -5], 5),
        ],
    )
    def test_calculate_past_bill_fees_for_procedure(
        self, billing_service, past_bill_count, past_bill_fees, expected_fee
    ):
        current_bill = billing_service.bill_repo.create(
            instance=factories.BillFactory.build()
        )
        for bill_fee in past_bill_fees:
            _ = billing_service.bill_repo.create(
                instance=factories.BillFactory.build(
                    last_calculated_fee=bill_fee,
                    procedure_id=current_bill.procedure_id,
                    payor_id=current_bill.payor_id,
                )
            )

        fee = billing_service.calculate_past_bill_fees_for_procedure(
            current_bill=current_bill
        )
        assert fee == expected_fee

    @pytest.mark.parametrize(
        argnames="inp_proc_id, inp_payor_type,inp_bills_to_build, exp_indices",
        ids=[
            "0. Only member bills that have money movement are returned",
            "1. No employer bills, nothing returned.",
            "2. Only member bills that have money movement are returned.",
            "3. Since there are no bills, nothing is returned.",
            "4. Since there are no member bills that have cash movement, nothing is returned.",
        ],
        argvalues=(
            # 0. Only member bills that have money movement are returned. Employer bills, cancelled member bills. and
            # refunded member bills that were used to cancel bill are not returned.
            (
                1,
                PayorType.MEMBER,
                [
                    (PayorType.MEMBER, BillStatus.NEW, []),
                    (PayorType.MEMBER, BillStatus.PAID, [False, True]),
                    (PayorType.MEMBER, BillStatus.CANCELLED, []),
                    (PayorType.MEMBER, BillStatus.REFUNDED, []),
                    (PayorType.MEMBER, BillStatus.CANCELLED, [False, True]),
                    (PayorType.MEMBER, BillStatus.REFUNDED, [True, False]),
                    (PayorType.EMPLOYER, BillStatus.REFUNDED, [True, False]),
                ],
                [0, 1, 5],
            ),
            # 1. Since there are no employer bills, none are returned.
            (
                2,
                PayorType.EMPLOYER,
                [
                    (PayorType.MEMBER, BillStatus.NEW, []),
                    (PayorType.MEMBER, BillStatus.PAID, [False, True]),
                    (PayorType.MEMBER, BillStatus.CANCELLED, []),
                    (PayorType.MEMBER, BillStatus.REFUNDED, []),
                    (PayorType.MEMBER, BillStatus.CANCELLED, [False, True]),
                    (PayorType.MEMBER, BillStatus.REFUNDED, [True, False]),
                ],
                [],
            ),
            # 2. Only member bills that have money movement are returned. Employer bills, cancelled member bills. and
            # refunded member bills that were used to cancel bill are not returned.
            (
                3,
                PayorType.MEMBER,
                [
                    (PayorType.MEMBER, BillStatus.NEW, []),
                    (PayorType.MEMBER, BillStatus.PAID, [False, True]),
                    (PayorType.MEMBER, BillStatus.CANCELLED, []),
                    (PayorType.MEMBER, BillStatus.REFUNDED, []),
                    (PayorType.MEMBER, BillStatus.CANCELLED, [False, True]),
                    (PayorType.EMPLOYER, BillStatus.REFUNDED, [True, False]),
                ],
                [0, 1],
            ),
            # 3. Since there are no bills, nothing is returned.
            (4, PayorType.MEMBER, [], []),
            # 4. Since there are no member bills that have cash movement, nothing is returned.
            (
                5,
                PayorType.MEMBER,
                [
                    (PayorType.MEMBER, BillStatus.CANCELLED, []),
                    (PayorType.MEMBER, BillStatus.REFUNDED, []),
                    (PayorType.MEMBER, BillStatus.CANCELLED, [False, True]),
                ],
                [],
            ),
        ),
    )
    def test_get_money_movement_bills_by_procedure_id_payor_type(
        self,
        billing_service,
        inp_proc_id,
        inp_payor_type,
        inp_bills_to_build,
        exp_indices,
    ):

        exp = []

        for i, (p_type, status, bpr_has_trans_id_list) in enumerate(inp_bills_to_build):
            bill = billing_service.bill_repo.create(
                instance=factories.BillFactory.build(
                    payor_type=p_type, procedure_id=inp_proc_id, status=status
                )
            )
            trans = uuid.uuid4()
            for has_trans in bpr_has_trans_id_list:
                billing_service.bill_processing_record_repo.create(
                    instance=factories.BillProcessingRecordFactory.build(
                        bill_id=bill.id,
                        bill_status=bill.status.value,
                        transaction_id=trans if has_trans else None,
                        # these 2 fields do not matter
                        processing_record_type="payment_gateway_request",
                        body="",
                    )
                )
            if i in exp_indices:
                exp.append(bill)

        res = billing_service.get_money_movement_bills_by_procedure_id_payor_type(
            inp_proc_id, inp_payor_type
        )
        assert res == exp

    @pytest.mark.parametrize(
        argnames="pr_time, exp_bill_indices",
        argvalues=(
            (
                datetime.datetime(2024, 3, 10, 9, 30, 1),
                [3],
            ),
            (
                datetime.datetime(2024, 3, 11, 9, 30, 1),
                [3, 4],
            ),
            (
                datetime.datetime(2024, 3, 10, 8, 30, 1),
                [],
            ),
        ),
        ids=[
            "0. 1 bill with processing time earlier than threshold, PAID & EMPLOYER excluded",
            "1. Two bills with processing time earlier than threshold, FAILED excluded",
            "2. No bills with processing time earlier than threshold",
        ],
    )
    def test_get_processable_new_member_bills(
        self,
        billing_service,
        new_member_bills_for_processing,
        pr_time,
        exp_bill_indices,
    ):
        exp_bill_ids = {new_member_bills_for_processing[i].id for i in exp_bill_indices}
        res = billing_service.get_processable_new_member_bills_y(
            processing_time_threshold=pr_time
        )
        assert {b.id for b in res} == exp_bill_ids

    @pytest.mark.parametrize(
        ids=[
            "1. 1 payor id, 2 bills found in window",
            "2. 2 payor ids, 3 bills found in window",
            "3. 1 payor id, 1 bills found in window",
            "4. 1 payor id, No bills found in window - no payor id match",
            "5. 1 payor id, No bills found in window",
        ],
        argnames="payor_ids, start_datetime,  end_datetime,  exp_indices",
        argvalues=(
            (
                [1],
                datetime.datetime(2024, 1, 2, 10, 11, 30),
                datetime.datetime(2024, 3, 2, 10, 11, 30),
                {3, 4},
            ),
            (
                [1, 2],
                datetime.datetime(2024, 1, 2, 10, 11, 30),
                datetime.datetime(2024, 3, 2, 10, 11, 30),
                {3, 4, 5},
            ),
            (
                [2],
                datetime.datetime(2024, 1, 2, 10, 11, 30),
                datetime.datetime(2024, 3, 2, 10, 11, 30),
                {5},
            ),
            (
                [3],
                datetime.datetime(2024, 1, 2, 10, 11, 30),
                datetime.datetime(2024, 3, 2, 10, 11, 30),
                {},
            ),
            (
                [2],
                datetime.datetime(2024, 5, 2, 10, 11, 30),
                datetime.datetime(2024, 7, 2, 10, 11, 30),
                {},
            ),
        ),
    )
    def test_get_new_employer_bills_for_payor_ids_in_datetime_range(
        self,
        billing_service,
        multiple_pre_created_bills,
        payor_ids,
        start_datetime,
        end_datetime,
        exp_indices,
    ):
        bills_param = [
            (
                1,
                PayorType.MEMBER,
                1000,
                BillStatus.NEW,
                datetime.datetime(2024, 1, 2, 10, 11, 30),
            ),
            (
                1,
                PayorType.MEMBER,
                -1000,
                BillStatus.NEW,
                datetime.datetime(2024, 2, 2, 10, 11, 30),
            ),
            (
                2,
                PayorType.MEMBER,
                1500,
                BillStatus.FAILED,
                datetime.datetime(2024, 1, 2, 10, 11, 30),
            ),
            (
                1,
                PayorType.EMPLOYER,
                2000,
                BillStatus.NEW,
                datetime.datetime(2024, 1, 2, 10, 11, 30),
            ),
            (
                1,
                PayorType.EMPLOYER,
                3000,
                BillStatus.NEW,
                datetime.datetime(2024, 2, 2, 10, 11, 30),
            ),
            (
                2,
                PayorType.EMPLOYER,
                3000,
                BillStatus.NEW,
                datetime.datetime(2024, 2, 2, 10, 11, 30),
            ),
            (
                2,
                PayorType.EMPLOYER,
                3000,
                BillStatus.FAILED,
                datetime.datetime(2024, 2, 2, 10, 11, 30),
            ),
            (
                3,
                PayorType.CLINIC,
                15100,
                BillStatus.NEW,
                datetime.datetime(2024, 2, 2, 10, 11, 30),
            ),
        ]
        exp_bill_uuids = set()
        for i, (payor_id, payor_type, amount, status, created_at) in enumerate(
            bills_param
        ):
            bill = factories.BillFactory.build(
                payor_id=payor_id,
                payor_type=payor_type,
                amount=amount,
                status=status,
                created_at=created_at,
            )
            bill = billing_service.bill_repo.create(instance=bill)
            if i in exp_indices:
                exp_bill_uuids.add(bill.uuid)
        res = billing_service.get_new_employer_bills_for_payor_ids_in_datetime_range(
            payor_ids, start_datetime, end_datetime
        )
        assert {r.uuid for r in res} == exp_bill_uuids

    @pytest.mark.parametrize(
        argnames="payor_types, statuses, exp_indices",
        argvalues=(
            ([PayorType.MEMBER], [BillStatus.NEW], [1, 4]),
            ([PayorType.MEMBER], [BillStatus.NEW, BillStatus.PAID], [0, 1, 4]),
            ([PayorType.MEMBER], [], [0, 1, 4, 5]),
            ([PayorType.MEMBER], None, [0, 1, 4, 5]),
            ([PayorType.EMPLOYER], [BillStatus.REFUNDED], [3]),
            ([PayorType.EMPLOYER], [], [2, 3]),
            ([PayorType.MEMBER, PayorType.EMPLOYER], None, [0, 1, 2, 3, 4, 5]),
            ([], [BillStatus.NEW, BillStatus.PAID], [0, 1, 2, 4]),
        ),
        ids=[
            "0. All NEW MEMBER bills",
            "1. All NEW and PAID  MEMBER bills",
            "2. All MEMBER bills",
            "3. All MEMBER bills redux",
            "4. All REFUNDED EMPLOYER bills",
            "5. All EMPLOYER bills",
            "6. All MEMBER and EMPLOYER bills",
            "7. All NEW and PAID bills",
        ],
    )
    def test_get_by_payor_types_statuses(
        self,
        billing_service,
        multiple_pre_created_bills,
        payor_types,
        statuses,
        exp_indices,
    ):
        res = billing_service.get_by_payor_types_statuses(
            payor_types,
            statuses,
        )
        res_ids = {b.id for b in res}
        exp_bill_ids = {multiple_pre_created_bills[i].id for i in exp_indices}
        assert res_ids == exp_bill_ids


class TestBillRetry:
    def test_invalid_bill_status(self, billing_service):
        bill = factories.BillFactory.build(status=BillStatus.PAID)
        with pytest.raises(errors.InvalidBillStatusChange):
            billing_service.retry_bill(bill, initiated_by="test")

    def test_missing_customer_id(self, billing_service, bill_wallet, failed_bill):
        bill_wallet.payments_customer_id = None
        with pytest.raises(errors.MissingPaymentGatewayInformation):
            billing_service.retry_bill(failed_bill, initiated_by="test")

    def test_create_transaction_fails(self, billing_service, failed_bill):
        mock_response = Response()
        mock_response.status_code = 503
        mock_response.encoding = "application/json"
        mock_response._content = json.dumps({"failure": "data"}).encode("utf-8")
        create_transaction_mock = mock.Mock(
            side_effect=PaymentsGatewayException(
                "Mock Error", code=503, response=mock_response
            )
        )
        billing_service.payment_gateway_client.create_transaction = (
            create_transaction_mock
        )
        with mock.patch(
            "direct_payment.billing.billing_service.BillingService._add_bill_processing_record"
        ) as add_bill_processing_record, pytest.raises(PaymentsGatewayException):
            billing_service.retry_bill(failed_bill, initiated_by="test")
            assert add_bill_processing_record.call_count == 2

    def test_successful_charge(self, billing_service, failed_bill):
        mock_response = Response()
        mock_response.status_code = 200
        mock_response.encoding = "application/json"
        mock_response._content = json.dumps({"success": "data"}).encode("utf-8")
        create_transaction_mock = mock.Mock(
            return_value=Transaction(
                transaction_id=uuid.uuid4(),
                transaction_data={"transaction": "data"},
                status="pending",
                metadata={"source_id": "1", "source_type": "Type"},
            )
        )
        billing_service.payment_gateway_client.create_transaction = (
            create_transaction_mock
        )
        with mock.patch(
            "direct_payment.billing.billing_service.BillingService._add_bill_processing_record"
        ) as add_bill_processing_record:
            billing_service.retry_bill(failed_bill, initiated_by="test")
            assert add_bill_processing_record.call_count == 2

    @pytest.mark.parametrize("attempt_count", [0, 1, 3])
    def test_retry_count(
        self, billing_service, create_mock_response_fixture, attempt_count
    ):
        bill = factories.BillFactory.build(status=BillStatus.FAILED)
        bill = billing_service.bill_repo.create(instance=bill)
        if attempt_count:
            processing_records = factories.BillProcessingRecordFactory.build_batch(
                size=attempt_count,
                processing_record_type="payment_gateway_request",
                bill_id=bill.id,
            )
            for processing_record in processing_records:
                billing_service.bill_processing_record_repo.create(
                    instance=processing_record
                )
        with patch(
            "direct_payment.billing.billing_service.payments_customer_id",
        ) as _get_customer_id_from_payor_mock:
            with patch(
                "common.base_triforce_client.BaseTriforceClient.make_service_request",
            ) as mock_make_request:
                _get_customer_id_from_payor_mock.return_value = 100
                mock_response = create_mock_response_fixture(
                    transaction_data={"test_key": "test_transaction_data"},
                    uuid_param_str=str(uuid.uuid4()),
                    metadata={"source_id": "test_pg", "source_type": "test_pg_type"},
                )
                mock_make_request.return_value = mock_response
                billing_service.retry_bill(bill, initiated_by="test")
                call_args = mock_make_request.call_args.kwargs["data"]
                call_metadata = call_args["metadata"]
                assert call_metadata["bill_attempt"] == attempt_count + 1


class TestBillProcessing:
    @pytest.mark.parametrize(
        argvalues=[
            (
                10000,
                "100.00",
                PayorType.MEMBER,
                PaymentMethodType.us_bank_account,
                "member_bank_account",
                0,
                "0.00",
                True,
                BillStatus.PROCESSING,
                True,
                "charge",
                "customer_id",
                [BillStatus.PROCESSING.value, BillStatus.PROCESSING.value],
                "processing_at",
                None,
                None,
            ),
            (
                5000,
                "50.00",
                PayorType.MEMBER,
                PaymentMethodType.card,
                "member_card",
                150,
                "1.50",
                True,
                BillStatus.PROCESSING,
                True,
                "charge",
                "customer_id",
                [BillStatus.PROCESSING.value, BillStatus.PROCESSING.value],
                "processing_at",
                None,
                None,
            ),
            (
                15000,
                "150.00",
                PayorType.MEMBER,
                None,
                None,
                0,
                "0.00",
                True,
                BillStatus.PROCESSING,
                True,
                "charge",
                "customer_id",
                [BillStatus.PROCESSING.value, BillStatus.PROCESSING.value],
                "processing_at",
                None,
                None,
            ),
            (
                0,
                "0.00",
                PayorType.MEMBER,
                PaymentMethodType.card,
                "member_bank_card",
                True,
                0,
                "0.00",
                BillStatus.PAID,
                False,
                "charge",
                "customer_id",
                [BillStatus.PROCESSING.value, BillStatus.PAID.value],
                "paid_at",
                None,
                None,
            ),
            (
                10000,
                "100.00",
                PayorType.EMPLOYER,
                PaymentMethodType.us_bank_account,
                "employer_bank_account",
                0,
                "0.00",
                True,
                BillStatus.PROCESSING,
                True,
                "charge",
                "customer_id",
                [BillStatus.PROCESSING.value, BillStatus.PROCESSING.value],
                "processing_at",
                None,
                None,
            ),
            (
                10000,
                "100.00",
                PayorType.CLINIC,
                None,
                None,
                0,
                "0.00",
                False,
                BillStatus.PROCESSING,
                True,
                "transfer",
                "recipient_id",
                [BillStatus.PROCESSING.value, BillStatus.PROCESSING.value],
                "processing_at",
                {
                    "end_date": datetime.date(2024, 1, 3),
                    "uuid": "ffda15d3-bee8-4a74-9c5f-035f91a11668",
                    "reimbursement_wallet_id": TEST_WALLET_ID,
                },
                "Payment from Maven Clinic for Member: REPL_STR, Procedure ID: "
                "ffda15d3-bee8-4a74-9c5f-035f91a11668, Procedure End Date: Jan 03, 2024",
            ),
        ],
        argnames="input_amount, expected_copay_passthrough, payor_type, payment_method_type, payment_method_id, "
        "last_calculated_fee, expected_recouped_fee, add_payment_info_to_payload, expected_bill_status, expect_payment,"
        "exp_transaction_type, exp_cust_type_id, exp_bpr_statuses, exp_display_date, mock_tp_dict, exp_descrip_in_td",
    )
    def test_set_bill_to_processing(
        self,
        billing_service,
        reimbursement_wallet_with_benefit,
        reimbursement_wallet_user,
        create_mock_response_fixture,
        input_amount,
        expected_copay_passthrough,
        payor_type,
        payment_method_type,
        payment_method_id,
        last_calculated_fee,
        expected_recouped_fee,
        add_payment_info_to_payload,
        expected_bill_status,
        expect_payment,
        exp_transaction_type,
        exp_cust_type_id,
        exp_bpr_statuses,
        exp_display_date,
        mock_tp_dict,
        exp_descrip_in_td,
    ):
        input_bill = billing_service.bill_repo.create(
            instance=factories.BillFactory.build(
                amount=input_amount,
                payor_type=payor_type,
                payor_id=(
                    reimbursement_wallet_with_benefit.id
                    if payor_type == PayorType.MEMBER
                    else 12345
                ),
                status=BillStatus.NEW,
                payment_method_type=payment_method_type,
                payment_method_id=payment_method_id,
                last_calculated_fee=last_calculated_fee,
                procedure_id=8675309,
            )
        )
        # for intra bill consistency
        if payor_type != PayorType.MEMBER:
            _ = billing_service.bill_repo.create(
                instance=factories.BillFactory.build(
                    payor_type=PayorType.MEMBER,
                    payor_id=reimbursement_wallet_with_benefit.id,
                    procedure_id=8675309,
                )
            )

        # The test data is a static as possible to avoid internal changes leaving the test as passing since the data is
        # being sent to an external system.
        expected_metadata = {
            "source_type": "TreatmentProcedure",
            "source_id": str(input_bill.procedure_id),
            "bill_uuid": str(input_bill.uuid),
            "copay_passthrough": expected_copay_passthrough,
            "recouped_fee": expected_recouped_fee,
            "initiated_by": "direct_payment.billing.billing_service",
            "bill_attempt": 1,
            "payer_type": payor_type.value.lower(),
        }

        mocked_cust_uuid = uuid.uuid4()
        with patch(
            "direct_payment.billing.billing_service.payments_customer_id",
        ) as _get_customer_id_from_payor_mock:
            with patch(
                "common.base_triforce_client.BaseTriforceClient.make_service_request",
            ) as mock_make_request:
                # fake a call to get the customer id
                _get_customer_id_from_payor_mock.return_value = mocked_cust_uuid
                # create the transaction data
                expected_called_transaction_data = {
                    "transaction_type": exp_transaction_type,
                    "amount": input_amount + last_calculated_fee,
                    exp_cust_type_id: str(mocked_cust_uuid),
                }
                if exp_descrip_in_td:
                    expected_called_transaction_data[
                        "description"
                    ] = exp_descrip_in_td.replace(
                        "REPL_STR",
                        f"{reimbursement_wallet_user.member.first_name} "
                        f"{reimbursement_wallet_user.member.last_name}, "
                        f"Benefit ID: {reimbursement_wallet_user.member.member_benefit.benefit_id}",
                    )

                if add_payment_info_to_payload:
                    expected_called_transaction_data["payment_method_id"] = (
                        payment_method_id or ""
                    )
                # fake the return to the PG server.
                mock_response = create_mock_response_fixture(
                    transaction_data=expected_called_transaction_data,
                    uuid_param_str=str(uuid.uuid4()),
                    metadata=expected_metadata,
                )
                mock_make_request.return_value = mock_response

                if mock_tp_dict:
                    mock_tp_dict["member_id"] = reimbursement_wallet_user.user_id
                with patch(
                    "direct_payment.billing.billing_service.get_treatment_procedure_as_dict_from_id",
                    return_value=mock_tp_dict,
                ):
                    # process the bill
                    res_bill = billing_service.set_new_bill_to_processing(input_bill)
                # get the bprs linked to the bill sorted by id. #TODO make this the default method behaviour
                res_bprs = sorted(
                    billing_service.bill_processing_record_repo.get_bill_processing_records(
                        [res_bill.id]
                    ),
                    key=lambda x: x.id,
                )
                # bill is as expected
                assert res_bill.status == expected_bill_status
                assert res_bill.display_date == exp_display_date
                # bprs have the expected statuses in the expected order
                res_bpr_statuses = [res_bpr.bill_status for res_bpr in res_bprs]
                assert res_bpr_statuses == exp_bpr_statuses
                if expect_payment:
                    # check that the PG server was called only once and that was called with the expected params
                    assert mock_make_request.call_count == 1
                    call_args = mock_make_request.call_args.kwargs["data"]
                    call_metadata = call_args["metadata"]
                    transaction_data = call_args["transaction_data"]
                    assert transaction_data == expected_called_transaction_data
                    assert call_metadata == expected_metadata
                else:
                    assert mock_make_request.call_count == 0

    def test_set_bill_to_processing_missing_customer_id(self, billing_service):
        with pytest.raises(errors.MissingPaymentGatewayInformation):
            test_bill = factories.BillFactory.build(
                status=BillStatus.NEW,
            )
            test_bill = billing_service.bill_repo.create(instance=test_bill)
            billing_service.set_new_bill_to_processing(test_bill)

    @pytest.mark.parametrize(
        argvalues=[
            (0, True, -1, 1000),
            (2, True, -0.95, 1100),
            (2, False, -0.95, 1200),
        ],
        argnames="bill_to_refund_index,  diff_procedure_id_flag, factor, procedure_id",
        ids=[
            "Bill with 2 records",
            "Bill with 3 records",
            "All bills have the same procedure id",
        ],
    )
    def test_set_bill_to_processing_for_refunds(
        self,
        billing_service,
        random_reimbursement_wallet_with_benefit,
        create_mock_response_fixture,
        bill_to_refund_index,
        diff_procedure_id_flag,
        factor,
        procedure_id,
    ):
        bill_processing_record_statuses = [
            [BillStatus.PROCESSING, BillStatus.PAID],  # Bill 0
            [BillStatus.PROCESSING],  # Bill 1
            [BillStatus.NEW, BillStatus.PROCESSING, BillStatus.PAID],  # Bill 2
            [BillStatus.NEW, BillStatus.PAID, BillStatus.REFUNDED],  # Bill 3
        ]

        record_dict_coll = self._generate_bill_processing_records_dict(
            billing_service,
            random_reimbursement_wallet_with_benefit,
            bill_processing_record_statuses,
            diff_procedure_id_flag,
            procedure_id,
        )

        bills = [v["bill"] for v in record_dict_coll.values()]
        paid_bill_to_refund = bills[bill_to_refund_index]

        refund_bill = billing_service.bill_repo.create(
            instance=factories.BillFactory.build(
                amount=paid_bill_to_refund.amount * factor,
                status=BillStatus.NEW,
                procedure_id=paid_bill_to_refund.procedure_id,
                payor_id=paid_bill_to_refund.payor_id,
            )
        )
        refund_fn = partial(
            billing_service.set_new_bill_to_processing,
            input_bill=refund_bill,
            headers=None,
        )

        self._common_refund_testing_fn(
            billing_service,
            create_mock_response_fixture,
            paid_bill_to_refund,
            refund_fn,
            abs(refund_bill.amount),
            abs(refund_bill.last_calculated_fee),
        )

    @pytest.mark.parametrize(
        argvalues=[
            (0, True, 1000, PayorType.MEMBER),
            (2, True, 1100, PayorType.MEMBER),
            (2, False, 1200, PayorType.MEMBER),
            (0, True, 1000, PayorType.MEMBER),
            (2, True, 1100, PayorType.MEMBER),
            (2, False, 1200, PayorType.MEMBER),
        ],
        argnames="bill_to_refund_index,  diff_procedure_id_flag,  procedure_id, payer_type",
        ids=[
            "Bill with 2 records member refund",
            "Bill with 3 records member refund",
            "All bills have the same procedure id member refund",
            "Bill with 2 records clinic reverse transfer",
            "Bill with 3 records clinic reverse transfer",
            "All bills have the same procedure id clinic reverse transfer",
        ],
    )
    def test_set_new_refund_or_reverse_bill_to_processing(
        self,
        billing_service,
        random_reimbursement_wallet_with_benefit,
        create_mock_response_fixture,
        bill_to_refund_index,
        diff_procedure_id_flag,
        procedure_id,
        payer_type,
    ):
        bill_processing_record_statuses = [
            [BillStatus.PROCESSING, BillStatus.PAID],  # Bill 0
            [BillStatus.PROCESSING],  # Bill 1
            [BillStatus.NEW, BillStatus.PROCESSING, BillStatus.PAID],  # Bill 2
            [BillStatus.NEW, BillStatus.PAID, BillStatus.REFUNDED],  # Bill 3
        ]
        record_dict_coll = self._generate_bill_processing_records_dict(
            billing_service,
            random_reimbursement_wallet_with_benefit,
            bill_processing_record_statuses,
            diff_procedure_id_flag,
            procedure_id,
            payer_type,
        )
        package = list(record_dict_coll.values())[bill_to_refund_index]
        bill = package["bill"]
        bpr = (
            package["records"][-1] if package["records"] else None
        )  # new bills have no BPRs

        refund_bill = billing_service.create_full_refund_bill_from_bill(bill, bpr)
        refund_fn = partial(
            billing_service.set_new_refund_or_reverse_bill_to_processing,
            refund_or_reverse_transfer_bill=refund_bill,
            linked_bill=bill,
            linked_bill_pr=bpr,
            attempt_count=1,
            initiated_by="test",
            headers=None,
        )

        self._common_refund_testing_fn(
            billing_service,
            create_mock_response_fixture,
            bill,
            refund_fn,
            abs(refund_bill.amount),
            abs(refund_bill.last_calculated_fee),
        )

    def test_set_new_refund_or_reverse_bill_to_processing_blocked(
        self,
        billing_service,
        random_reimbursement_wallet_with_benefit,
        create_mock_response_fixture,
    ):
        linked_bill = billing_service.bill_repo.create(
            instance=(
                factories.BillFactory.build(
                    payor_type=PayorType.EMPLOYER,
                    status=BillStatus.PAID,
                    procedure_id=TreatmentProcedureFactory.create(
                        status=TreatmentProcedureStatus.COMPLETED,
                    ).id,
                    amount=100000,
                )
            )
        )

        refund_bill = billing_service.create_full_refund_bill_from_bill(
            linked_bill, None
        )
        with mock.patch(
            "direct_payment.billing.billing_service.can_employer_bill_be_processed",
            return_value=False,
        ):
            res = billing_service.set_new_refund_or_reverse_bill_to_processing(
                refund_or_reverse_transfer_bill=refund_bill,
                linked_bill=linked_bill,
                linked_bill_pr=None,
                attempt_count=1,
                initiated_by="test",
                record_type="billing_service_workflow",
                headers=None,
            )
        assert res.status == BillStatus.NEW

    @pytest.mark.parametrize(
        argvalues=[
            PayorType.MEMBER,
            PayorType.EMPLOYER,
        ],
        argnames="payer_type",
    )
    def test_handle_refund_or_reverse_transfer_bill__refund(
        self,
        payer_type,
        billing_service,
        bill_processing_record_repository,
    ):
        # Given
        refund_bill = billing_service.bill_repo.create(
            instance=factories.BillFactory.build(
                amount=-BILL_AMOUNT,
                status=BillStatus.NEW.value,
                payor_type=payer_type,
                processing_scheduled_at_or_after=datetime.datetime.now(
                    datetime.timezone.utc
                ),
            )
        )
        linked_bill = billing_service.bill_repo.create(
            instance=factories.BillFactory.build(
                amount=BILL_AMOUNT,
                status=BillStatus.NEW.value,
                payor_type=payer_type,
            )
        )
        bpr = bill_processing_record_repository.create(
            instance=factories.BillProcessingRecordFactory.build(
                bill_id=linked_bill.id,
                processing_record_type="payment_gateway_request",
                bill_status=BillStatus.PROCESSING.value,
            )
        )
        mock_response = Response()
        mock_response.status_code = 200
        mock_response.encoding = "application/json"
        mock_response._content = json.dumps({"success": "data"}).encode("utf-8")
        create_transaction_mock = mock.Mock(
            return_value=Transaction(
                transaction_id=uuid.uuid4(),
                transaction_data={"transaction": "data"},
                status="pending",
                metadata={"source_id": "1", "source_type": "Type"},
            )
        )
        billing_service.payment_gateway_client.create_transaction = (
            create_transaction_mock
        )
        # When
        billing_service._handle_refund_or_reverse_transfer_bill(
            refund_or_reverse_transfer_bill=refund_bill,
            linked_bill=linked_bill,
            linked_charge_trans=bpr,
            attempt_count=1,
            initiated_by="test",
            headers=None,
        )

        # Then
        assert create_transaction_mock.call_args.kwargs == {
            "transaction_payload": TransactionPayload(
                transaction_data=RefundPayload(
                    transaction_type="charge_refund",
                    amount=BILL_AMOUNT,
                    transaction_id=str(bpr.transaction_id),
                ),
                metadata={
                    "source_type": "TreatmentProcedure",
                    "source_id": str(refund_bill.procedure_id),
                    "bill_uuid": str(refund_bill.uuid),
                    "copay_passthrough": "-10.00",
                    "recouped_fee": "0.00",
                    "initiated_by": "test",
                    "bill_attempt": 1,
                    "payer_type": payer_type.value.lower(),
                },
            ),
            "headers": None,
        }

    def test_handle_refund_or_reverse_transfer_bill__reverse_transfer(
        self,
        billing_service,
        bill_processing_record_repository,
    ):
        # Given
        reverse_transfer_bill = billing_service.bill_repo.create(
            instance=factories.BillFactory.build(
                amount=-BILL_AMOUNT,
                status=BillStatus.NEW.value,
                payor_type=PayorType.CLINIC,
            )
        )
        transfer_bill = billing_service.bill_repo.create(
            instance=factories.BillFactory.build(
                amount=BILL_AMOUNT,
                status=BillStatus.NEW.value,
                payor_type=PayorType.CLINIC,
            )
        )
        bpr = bill_processing_record_repository.create(
            instance=factories.BillProcessingRecordFactory.build(
                bill_id=transfer_bill.id,
                processing_record_type="payment_gateway_request",
                bill_status=BillStatus.PROCESSING.value,
            )
        )
        mock_response = Response()
        mock_response.status_code = 200
        mock_response.encoding = "application/json"
        mock_response._content = json.dumps({"success": "data"}).encode("utf-8")
        create_transaction_mock = mock.Mock(
            return_value=Transaction(
                transaction_id=uuid.uuid4(),
                transaction_data={"transaction": "data"},
                status="pending",
                metadata={"source_id": "1", "source_type": "Type"},
            )
        )
        billing_service.payment_gateway_client.create_transaction = (
            create_transaction_mock
        )
        # When
        billing_service._handle_refund_or_reverse_transfer_bill(
            refund_or_reverse_transfer_bill=reverse_transfer_bill,
            linked_bill=transfer_bill,
            linked_charge_trans=bpr,
            attempt_count=1,
            initiated_by="test",
            headers=None,
        )

        # Then
        assert create_transaction_mock.call_args.kwargs == {
            "transaction_payload": TransactionPayload(
                transaction_data=TransferReversePayload(
                    transaction_type="transfer_reverse",
                    amount=BILL_AMOUNT,
                    transaction_id=str(bpr.transaction_id),
                ),
                metadata={
                    "source_type": "TreatmentProcedure",
                    "source_id": str(reverse_transfer_bill.procedure_id),
                    "bill_uuid": str(reverse_transfer_bill.uuid),
                    "copay_passthrough": "-10.00",
                    "recouped_fee": "0.00",
                    "initiated_by": "test",
                    "bill_attempt": 1,
                    "payer_type": "clinic",
                },
            ),
            "headers": None,
        }

    def _common_refund_testing_fn(
        self,
        billing_service,
        create_mock_response_fixture,
        paid_bill_to_refund,
        refund_fn,
        abs_refund_bill_amount,
        abs_refund_bill_fee,
    ):
        with patch(
            "common.base_triforce_client.BaseTriforceClient.make_service_request",
        ) as mock_make_request:
            mock_response = create_mock_response_fixture(
                transaction_data={"test_key": "test_transaction_data"},
                uuid_param_str=str(uuid.uuid4()),
                metadata={"source_id": "test_pg", "source_type": "test_pg_type"},
            )
            mock_make_request.return_value = mock_response
            with mock.patch(
                "direct_payment.billing.billing_service.get_benefit_id_from_wallet_id",
                return_value="ben_1234",
            ), patch(
                "direct_payment.notification.notification_service.send_event",
                return_value={"success": "true"},
            ) as mock_send_event:
                res_bill = refund_fn()
            assert mock_make_request.call_count == 1
            assert res_bill.status == BillStatus.PROCESSING
            data = mock_make_request.call_args_list[0].kwargs["data"]
            transaction_data = data["transaction_data"]
            assert (
                transaction_data["amount"]
                == abs_refund_bill_amount + abs_refund_bill_fee
            )
            assert transaction_data["transaction_type"] == "charge_refund"
            bpr_repo = billing_service.bill_processing_record_repo
            # Test the row that was inserted in the bill_processing_record to block dupe refunds of the paid bill
            results = bpr_repo.execute_select(
                where=sqlalchemy.and_(
                    bpr_repo.table.c.bill_id == paid_bill_to_refund.id,
                    bpr_repo.table.c.bill_status == BillStatus.REFUNDED.value,
                )
            ).fetchall()
            assert len(results) == 1  # Only one refunded row
            refund_block_row = bpr_repo.deserialize(results[0])
            assert refund_block_row.body["refund_bill"] == res_bill.id

            # Test that row(s) was(were) inserted in bill_processing_records for the refunded bill in PROCESSING state
            results = bpr_repo.execute_select(
                where=sqlalchemy.and_(
                    bpr_repo.table.c.bill_id == res_bill.id,
                    bpr_repo.table.c.bill_status == BillStatus.PROCESSING.value,
                )
            ).fetchall()
            # There may be more than one depending on payment gateway
            assert len(results) > 0
            # notification tests
            assert mock_send_event.called
            assert (
                mock_send_event.call_args.kwargs["event_name"]
                == "mmb_payment_adjusted_refund"
            )

            # Test that row(s) was(were) inserted in bill repo for the refunded bill in PROCESSING state
            results = billing_service.bill_repo.execute_select(
                where=sqlalchemy.and_(
                    billing_service.bill_repo.table.c.id == res_bill.id,
                    billing_service.bill_repo.table.c.status
                    == BillStatus.PROCESSING.value,
                    billing_service.bill_repo.table.c.amount == res_bill.amount,
                )
            ).fetchall()
            assert len(results) == 1
            # check that it's still a refund
            assert results[0].amount < 0

    @pytest.mark.parametrize(
        argvalues=[
            (-1, BillStatus.CANCELLED),
            (-0.5, BillStatus.NEW),
        ],
        argnames="factor, expected_state",
    )
    def test_set_bill_to_processing_to_refund_new_bill(
        self, billing_service, factor, expected_state
    ):
        bill = factories.BillFactory.build(
            amount=BILL_AMOUNT,
            status=BillStatus.NEW,
            procedure_id=TreatmentProcedureFactory.create(
                status=TreatmentProcedureStatus.COMPLETED,
            ).id,
        )
        bill = billing_service.bill_repo.create(instance=bill)
        refund_bill = factories.BillFactory.build(
            amount=BILL_AMOUNT * factor,
            status=BillStatus.NEW,
            procedure_id=bill.procedure_id,
        )
        with mock.patch(
            "direct_payment.billing.billing_service.payments_customer_id",
            return_value=uuid.uuid4(),
        ):
            with mock.patch(
                "common.payments_gateway.client.PaymentsGatewayClient.get_customer",
                return_value=Customer.create_from_dict(
                    {
                        "customer_id": "00112233-4455-6677-8899-aabbccddeeff",
                        "customer_setup_status": "succeeded",
                        "payment_method_types": [PaymentMethodType.card],
                        "payment_methods": [
                            {
                                "payment_method_type": PaymentMethodType.card.value,
                                "last4": "1234",
                                "brand": "visa",
                                "payment_method_id": "made_up",
                            }
                        ],
                    }
                ),
            ):
                refund_bill = billing_service.bill_repo.create(instance=refund_bill)
                res = billing_service.set_new_bill_to_processing(refund_bill)

        assert res.status == expected_state

    def test_set_bill_to_processing_to_refund_new_bill_missing_linked_charge(
        self, billing_service
    ):
        with pytest.raises(errors.MissingLinkedChargeInformation):
            test_bill = factories.BillFactory.build(
                amount=-1000,
                status=BillStatus.NEW,
            )
            test_bill = billing_service.bill_repo.create(instance=test_bill)
            billing_service.set_new_bill_to_processing(test_bill)

    @pytest.mark.parametrize(
        argvalues=[
            (2, True, -1.95, 1400, BillStatus.NEW),
            (2, False, -1.5, 1500, BillStatus.NEW),
            (1, True, -0.95, 1600, BillStatus.NEW),
            (3, True, -0.95, 1700, BillStatus.NEW),
            (0, True, -0.95, 1800, BillStatus.PROCESSING),
            (4, False, -1.5, 1900, BillStatus.NEW),
        ],
        argnames="bill_to_refund_index, diff_procedure_id_flag, factor, procedure_id, bill_status",
        ids=[
            "Bill with 3 records, refund amt too large",
            "All bills have the same procedure id, refund amt too large",
            "Bill is in processing, cannot be refunded",
            "Bill has already been refunded",
            "Input Bill is not new",
            "Bill in NEW state, but refund amount too large",
        ],
    )
    def test_set_bill_to_processing_for_refunds_failure(
        self,
        billing_service,
        random_reimbursement_wallet_with_benefit,
        bill_processing_record_statuses,
        bill_to_refund_index,
        diff_procedure_id_flag,
        factor,
        procedure_id,
        bill_status,
    ):

        record_dict_coll = self._generate_bill_processing_records_dict(
            billing_service,
            random_reimbursement_wallet_with_benefit,
            bill_processing_record_statuses,
            diff_procedure_id_flag,
            procedure_id,
        )

        bills = [v["bill"] for v in record_dict_coll.values()]
        paid_bill_to_refund = bills[bill_to_refund_index]

        refund_bill = billing_service.bill_repo.create(
            instance=factories.BillFactory.build(
                amount=paid_bill_to_refund.amount * factor,
                status=bill_status,
                procedure_id=paid_bill_to_refund.procedure_id,
            )
        )
        with pytest.raises(ValueError):
            billing_service.set_new_bill_to_processing(refund_bill)

    def test_sending_ephemeral_bill_to_payment_gateway_failure(
        self, billing_service, bill_wallet
    ):
        bill = billing_service.bill_repo.create(
            instance=(
                factories.BillFactory.build(
                    status=BillStatus.NEW,
                    amount=1_000_000,
                    last_calculated_fee=30_000,
                    payment_method_label="1234",
                    is_ephemeral=True,
                    payor_id=bill_wallet.id,
                )
            )
        )
        with pytest.raises(InvalidEphemeralBillOperationError):
            billing_service.set_new_bill_to_processing(bill)

    def test_sending_bill_with_cancelled_tp_to_payment_gateway_failure(
        self, billing_service, bill_wallet, create_cancelled_tp
    ):
        cancelled_treatment_procedure = create_cancelled_tp(bill_wallet)
        bill = billing_service.bill_repo.create(
            instance=(
                factories.BillFactory.build(
                    amount=1_000_000,
                    last_calculated_fee=30_000,
                    payment_method_label="1234",
                    payor_id=bill_wallet.id,
                    procedure_id=cancelled_treatment_procedure.id,
                )
            )
        )
        with pytest.raises(InvalidBillTreatmentProcedureCancelledError):
            billing_service.set_new_bill_to_processing(bill)

    def test_sending_refund_bill_with_cancelled_tp_to_payment_gateway(
        self,
        billing_service,
        bill_wallet,
        create_cancelled_tp,
        bill_processing_record_repository,
    ):
        cancelled_treatment_procedure = create_cancelled_tp(bill_wallet)

        bill = billing_service.bill_repo.create(
            instance=(
                factories.BillFactory.build(
                    status=BillStatus.PROCESSING,
                    amount=-1_000_000,
                    last_calculated_fee=30_000,
                    payment_method_label="1234",
                    payor_id=bill_wallet.id,
                    procedure_id=cancelled_treatment_procedure.id,
                    payor_type=PayorType.MEMBER,
                )
            )
        )
        linked_bill = billing_service.bill_repo.create(
            instance=factories.BillFactory.build(
                amount=abs(bill.amount),
                status=BillStatus.PROCESSING,
                procedure_id=cancelled_treatment_procedure.id,
                payor_type=PayorType.EMPLOYER,
            )
        )
        bpr = bill_processing_record_repository.create(
            instance=factories.BillProcessingRecordFactory.build(
                bill_id=linked_bill.id,
                processing_record_type="payment_gateway_request",
                bill_status=BillStatus.PROCESSING,
            )
        )

        mock_response = Response()
        mock_response.status_code = 200
        mock_response.encoding = "application/json"
        mock_response._content = json.dumps({"success": "data"}).encode("utf-8")
        create_transaction_mock = mock.Mock(
            return_value=Transaction(
                transaction_id=uuid.uuid4(),
                transaction_data={"transaction": "data"},
                status="pending",
                metadata={"source_id": "1", "source_type": "Type"},
            )
        )
        billing_service.payment_gateway_client.create_transaction = (
            create_transaction_mock
        )

        billing_service.set_new_refund_or_reverse_bill_to_processing(
            bill, linked_bill, bpr, 1
        )

    @pytest.mark.parametrize(
        ids=[
            "0. Original MEMBER bill in NEW status, abs(refund amt) == (new bill amt), expect a PAID 0 Bill ",
            "1. Original MEMBER bill in NEW status, abs(refund amt) < (new bill amt), expect a non 0 NEW bill ",
            "2. Original MEMBER bill in FAILED status, abs(refund amt) == (new bill amt), expect a PAID 0 Bill ",
            "3. Original MEMBER bill in FAILED status, abs(refund amt) < (new bill amt), expect a non 0 NEW bill ",
            "4. Original EMPLOYER bill in NEW status, abs(refund amt) == (new bill amt), expect a PAID 0 Bill ",
            "5. Original EMPLOYER bill in NEW status, abs(refund amt) < (new bill amt), expect a non 0 NEW bill ",
            "6. Original EMPLOYER bill in FAILED status, abs(refund amt) == (new bill amt), expect a PAID 0 Bill ",
            "7. Original EMPLOYER bill in FAILED status, abs(refund amt) < (new bill amt), expect a non 0 NEW bill ",
            "8. Original Invoiceed EMPLOYER bill in NEW status, abs(refund amt) == (new bill amt), expect a NEW 0 Bill ",
            "9. Original Invoiceed  EMPLOYER bill in NEW status, abs(refund amt) < (new bill amt), expect a non 0 NEW bill ",
        ],
        argvalues=[
            (
                PayorType.MEMBER,
                [10000, -10000, 0],
                BillStatus.NEW,
                True,
                BillStatus.PAID,
                BillStatus.CANCELLED,
                BillStatus.REFUNDED,
                True,
            ),
            (
                PayorType.MEMBER,
                [10000, -90000, 1000],
                BillStatus.NEW,
                True,
                BillStatus.NEW,
                BillStatus.CANCELLED,
                BillStatus.REFUNDED,
                True,
            ),
            (
                PayorType.MEMBER,
                [10000, -10000, 0],
                BillStatus.FAILED,
                True,
                BillStatus.PAID,
                BillStatus.CANCELLED,
                BillStatus.REFUNDED,
                True,
            ),
            (
                PayorType.MEMBER,
                [1000, -9000, 100],
                BillStatus.FAILED,
                True,
                BillStatus.NEW,
                BillStatus.CANCELLED,
                BillStatus.REFUNDED,
                True,
            ),
            (
                PayorType.EMPLOYER,
                [10000, -10000, 0],
                BillStatus.NEW,
                True,
                BillStatus.PAID,
                BillStatus.CANCELLED,
                BillStatus.REFUNDED,
                True,
            ),
            (
                PayorType.EMPLOYER,
                [10000, -90000, 1000],
                BillStatus.NEW,
                True,
                BillStatus.NEW,
                BillStatus.CANCELLED,
                BillStatus.REFUNDED,
                True,
            ),
            (
                PayorType.EMPLOYER,
                [1000, -1000, 0],
                BillStatus.FAILED,
                True,
                BillStatus.PAID,
                BillStatus.CANCELLED,
                BillStatus.REFUNDED,
                True,
            ),
            (
                PayorType.EMPLOYER,
                [1000, -9000, 100],
                BillStatus.FAILED,
                True,
                BillStatus.NEW,
                BillStatus.CANCELLED,
                BillStatus.REFUNDED,
                True,
            ),
            (
                PayorType.EMPLOYER,
                [1000, -1000, 0],
                BillStatus.NEW,
                False,
                BillStatus.NEW,
                BillStatus.NEW,
                BillStatus.NEW,
                False,
            ),
            (
                PayorType.EMPLOYER,
                [1000, -900, 100],
                BillStatus.NEW,
                False,
                BillStatus.NEW,
                BillStatus.NEW,
                BillStatus.NEW,
                False,
            ),
        ],
        argnames=[
            "payor_type",
            "amts",
            "inp_status",
            "invoiced",
            "exp_delta_bill_status",
            "exp_inp_bill_status",
            "exp_refund_bill_status",
            "exp_bprs",
        ],
    )
    def test_cancel_bill(
        self,
        billing_service,
        payor_type,
        amts,
        inp_status,
        invoiced,
        exp_delta_bill_status,
        exp_inp_bill_status,
        exp_refund_bill_status,
        exp_bprs,
    ):
        bill = billing_service.bill_repo.create(
            instance=(
                factories.BillFactory.build(
                    payor_type=payor_type,
                    status=inp_status,
                    procedure_id=12321,
                    amount=amts[0],
                )
            )
        )
        refund_bill, delta_bill = (
            billing_service.bill_repo.create(
                instance=(
                    factories.BillFactory.build(
                        status=BillStatus.NEW, procedure_id=12321, amount=amt
                    )
                )
            )
            for amt in amts[1:]
        )
        with mock.patch(
            "direct_payment.billing.billing_service.can_employer_bill_be_processed",
            return_value=invoiced,
        ):
            res = billing_service.cancel_bill(
                bill, refund_bill, delta_bill, "billing_service_workflow"
            )
        assert res.status == exp_inp_bill_status
        assert res.procedure_id == bill.procedure_id
        assert res.uuid == bill.uuid
        assert res.id == bill.id
        recs = billing_service.bill_processing_record_repo.get_bill_processing_records(
            [bill.id]
        )
        assert len(recs) == int(exp_bprs)
        if exp_bprs:
            rec = recs[-1]
            assert rec.bill_status == BillStatus.CANCELLED.value
            assert rec.bill_id == res.id
            assert rec.body == {"offset_bill": bill.id, "refund_bill": refund_bill.id}
        # test that the refund bill that initiated the cancel has been correctly closed out
        reloaded_refund_bill = billing_service.get_bill_by_id(refund_bill.id)
        assert reloaded_refund_bill.status == exp_refund_bill_status
        if exp_bprs:
            bprs = (
                billing_service.bill_processing_record_repo.get_bill_processing_records(
                    [reloaded_refund_bill.id]
                )
            )
            assert {bpr.bill_status for bpr in bprs} == {
                BillStatus.PROCESSING.value,
                BillStatus.REFUNDED.value,
            }
        res_delta_bill = billing_service.bill_repo.get_by_ids([delta_bill.id])[0]
        assert res_delta_bill.status == exp_delta_bill_status

    @pytest.mark.parametrize(
        argvalues=[
            BillStatus.PAID,
            BillStatus.REFUNDED,
        ],
        argnames="status",
    )
    def test_cancel_bill_failure(self, billing_service, status):
        bill = billing_service.bill_repo.create(
            instance=(factories.BillFactory.build(status=status, procedure_id=123211))
        )
        refund_bill = billing_service.bill_repo.create(
            instance=(
                factories.BillFactory.build(
                    status=BillStatus.NEW, procedure_id=123211, amount=-bill.amount
                )
            )
        )
        delta_bill = billing_service.bill_repo.create(
            instance=(
                factories.BillFactory.build(
                    status=BillStatus.NEW, procedure_id=123211, amount=0
                )
            )
        )
        with pytest.raises(ValueError):
            billing_service.cancel_bill(
                bill, refund_bill, delta_bill, "billing_service_workflow"
            )

    @pytest.mark.parametrize(
        argvalues=[
            [
                BillStatus.NEW,
                PayorType.MEMBER,
                1,
                BillStatus.CANCELLED,
                "cancelled_at",
                1,
            ],
            [
                BillStatus.FAILED,
                PayorType.MEMBER,
                1,
                BillStatus.CANCELLED,
                "cancelled_at",
                1,
            ],
            [BillStatus.NEW, PayorType.EMPLOYER, 1, BillStatus.NEW, "created_at", 0],
            [
                BillStatus.NEW,
                PayorType.MEMBER,
                -1,
                BillStatus.CANCELLED,
                "cancelled_at",
                1,
            ],
            [
                BillStatus.FAILED,
                PayorType.MEMBER,
                -1,
                BillStatus.CANCELLED,
                "cancelled_at",
                1,
            ],
            [
                BillStatus.NEW,
                PayorType.EMPLOYER,
                -1,
                BillStatus.CANCELLED,
                "cancelled_at",
                1,
            ],
        ],
        argnames="status, payor_type, days_offset, exp_status, exp_display_date, exp_len_rec",
        ids=[
            "1. New Member Bill scheduled processing in the future- cancellation expected",
            "2. Failed Member Bill scheduled processing in the future- cancellation expected",
            "3. New Employer bill, scheduled processing in the future - no cancellation expected",
            "4. New Member Bill scheduled processing in the past- cancellation expected",
            "5. Failed Member Bill scheduled processing in the past- cancellation expected",
            "6. New Employer bill, scheduled processing in the past - cancellation expected",
        ],
    )
    def test_cancel_bill_with_offsetting_refund(
        self,
        ff_test_data,
        billing_service,
        status,
        payor_type,
        days_offset,
        exp_status,
        exp_display_date,
        exp_len_rec,
    ):
        bill = billing_service.bill_repo.create(
            instance=factories.BillFactory.build(
                status=status,
                procedure_id=TreatmentProcedureFactory.create(
                    status=TreatmentProcedureStatus.COMPLETED
                ).id,
                processing_scheduled_at_or_after=datetime.datetime.today()
                + datetime.timedelta(days=days_offset),
                payor_type=payor_type,
            )
        )

        res = billing_service.cancel_bill_with_offsetting_refund(
            bill=bill, record_type="admin_billing_workflow", initiated_by="test"
        )
        assert res.status == exp_status
        assert res.procedure_id == bill.procedure_id
        assert res.uuid == bill.uuid
        assert res.id == bill.id
        assert res.display_date == exp_display_date
        recs = billing_service.bill_processing_record_repo.get_bill_processing_records(
            [bill.id]
        )
        assert len(recs) == exp_len_rec
        if exp_len_rec:
            rec = recs[-1]
            assert rec.bill_status == BillStatus.CANCELLED.value
            assert rec.bill_id == res.id

    @pytest.mark.parametrize(
        argvalues=[
            BillStatus.PROCESSING,
            BillStatus.PAID,
        ],
        argnames="status",
    )
    def test_cancel_bill_without_refund_failure(self, billing_service, status):
        bill = billing_service.bill_repo.create(
            instance=(factories.BillFactory.build(status=status, procedure_id=123211))
        )
        with pytest.raises(errors.InvalidInputBillStatus):
            billing_service.cancel_bill_with_offsetting_refund(
                bill=bill, record_type="admin_billing_workflow", initiated_by="test"
            )

    @pytest.mark.parametrize(
        ids=[
            "1. No Pre-existing refund - spawn out a full refund bill.",
            "2. A Partial refund exists - spawn out a partial refund bill for the balance.",
            "3. Fully refunded, cannot add any more refunds.",
        ],
        argvalues=[
            ([BillStatus.PAID], 0, True),
            ([BillStatus.PAID, BillStatus.REFUNDED], 0.3, True),
            ([BillStatus.PAID, BillStatus.REFUNDED], 1, False),
        ],
        argnames="bpr_statuses, refund_factor, exp_refund_bill",
    )
    def test_create_full_refund_bill_from_potentially_partially_refunded_paid_bill(
        self,
        billing_service,
        bill_for_multi_refund_fixture,
        bpr_statuses,
        refund_factor,
        exp_refund_bill,
    ):
        bill = bill_for_multi_refund_fixture(
            billing_service, bpr_statuses, refund_factor
        )
        with freezegun.freeze_time(CURRENT_TIME):
            res = billing_service.create_full_refund_bill_from_potentially_partially_refunded_paid_bill(
                bill,
                "admin_billing_workflow",
            )
        assert (res is not None) == exp_refund_bill
        if res:
            res_bprs = (
                billing_service.bill_processing_record_repo.get_bill_processing_records(
                    [res.id]
                )
            )
            bill_bpr = (
                billing_service.bill_processing_record_repo.get_bill_processing_records(
                    [bill.id]
                )
            )[0]
            assert res.status == BillStatus.NEW
            assert res.amount == bill.amount * (refund_factor - 1)
            assert res.payment_method_id == bill.payment_method_id
            assert res.payment_method_type == bill.payment_method_type
            assert res.payment_method_label == bill.payment_method_label
            assert res.last_calculated_fee == bill.last_calculated_fee * (
                refund_factor - 1
            )
            assert res.created_at == CURRENT_TIME
            assert res.processing_scheduled_at_or_after == res.created_at
            assert len(res_bprs) == 1
            assert res_bprs[0].body == {"to_refund_bill": bill.id}
            assert res_bprs[0].transaction_id == bill_bpr.transaction_id

    @pytest.mark.parametrize(
        ids=[
            "1. Previous refund bill was hard deleted.",
            "2. Too many refunds.",
        ],
        argvalues=[
            ([BillStatus.PAID, BillStatus.REFUNDED], 0, False),
            ([BillStatus.PAID, BillStatus.REFUNDED, BillStatus.REFUNDED], 0.3, True),
        ],
        argnames="bpr_statuses, ref_factor, create_refunds",
    )
    def test_create_full_refund_bill_from_potentially_partially_refunded_paid_bill_error(
        self,
        billing_service,
        bill_for_multi_refund_fixture,
        bpr_statuses,
        ref_factor,
        create_refunds,
    ):

        bill = bill_for_multi_refund_fixture(
            billing_service, bpr_statuses, ref_factor, create_refunds
        )
        with pytest.raises(InvalidRefundBillCreationError):
            _ = billing_service.create_full_refund_bill_from_potentially_partially_refunded_paid_bill(
                bill,
                "admin_billing_workflow",
            )

    @pytest.mark.parametrize(
        ids=[
            "1. NEW bill Card with no card_funding and existing credit card_funding.",
            "2. NEW bill Bank with no card_funding without existing card_funding.",
            "3. FAILED bill Card with card_funding and existing debit card_funding.",
            "4. FAILED bill Card with card_funding without existing card_funding.",
            "5. FAILED bill Bank with null card_funding and existing prepaid card_funding.",
        ],
        argvalues=[
            (
                BillStatus.NEW,
                CardFunding.CREDIT,
                [PaymentMethodType.card.value],
                [
                    {
                        "payment_method_type": PaymentMethodType.card.value,
                        "last4": "1234",
                        "brand": "visa",
                        "payment_method_id": "987654",
                    }
                ],
            ),
            (
                BillStatus.NEW,
                None,
                [PaymentMethodType.us_bank_account.value],
                [
                    {
                        "payment_method_type": PaymentMethodType.us_bank_account.value,
                        "last4": "1234",
                        "brand": "bank",
                        "payment_method_id": "987654",
                    }
                ],
            ),
            (
                BillStatus.FAILED,
                CardFunding.DEBIT,
                [PaymentMethodType.card.value],
                [
                    {
                        "payment_method_type": PaymentMethodType.card.value,
                        "last4": "3334",
                        "brand": "visa",
                        "payment_method_id": "98760001",
                        "card_funding": "CREDIT",
                    }
                ],
            ),
            (
                BillStatus.FAILED,
                None,
                [PaymentMethodType.card.value],
                [
                    {
                        "payment_method_type": PaymentMethodType.card.value,
                        "last4": "3334",
                        "brand": "visa",
                        "payment_method_id": "98760001",
                        "card_funding": "CREDIT",
                    }
                ],
            ),
            (
                BillStatus.FAILED,
                CardFunding.PREPAID,
                [PaymentMethodType.us_bank_account.value],
                [
                    {
                        "payment_method_type": PaymentMethodType.us_bank_account.value,
                        "last4": "1234",
                        "brand": "bank",
                        "payment_method_id": "987654",
                        "card_funding": None,
                    }
                ],
            ),
        ],
        argnames="bill_status, existing_card_funding, payment_method_types, payment_methods",
    )
    def test_update_payment_method_on_bill(
        self,
        billing_service,
        bill_status,
        existing_card_funding,
        payment_method_types,
        payment_methods,
    ):
        bill = billing_service.bill_repo.create(
            instance=(
                factories.BillFactory.build(
                    status=bill_status,
                    amount=1_000_000,
                    last_calculated_fee=30_000,
                    card_funding=existing_card_funding,
                )
            )
        )
        exp_res = f"Payment method update on bill: {bill.id} succeeded."

        with mock.patch(
            "common.payments_gateway.client.PaymentsGatewayClient.get_customer",
            return_value=Customer.create_from_dict(
                {
                    "customer_id": "00112233-4455-6677-8899-aabbccddeeff",
                    "customer_setup_status": "succeeded",
                    "payment_method_types": payment_method_types,
                    "payment_methods": payment_methods,
                }
            ),
        ), mock.patch(
            "direct_payment.billing.billing_service.payments_customer_id",
        ) as _get_customer_id_from_payor_mock:
            _get_customer_id_from_payor_mock.return_value = 1
            res = billing_service.update_payment_method_on_bill(
                bill, record_type="admin_billing_workflow"
            )
            updated_bill = billing_service.get_bill_by_id(bill.id)
            assert res == exp_res
            assert updated_bill.payment_method_label == payment_methods[0].get("last4")
            assert updated_bill.payment_method_type.value == payment_methods[0].get(
                "payment_method_type"
            )
            assert updated_bill.payment_method_id == payment_methods[0].get(
                "payment_method_id"
            )
            res_card_funding = (
                updated_bill.card_funding.value if updated_bill.card_funding else None
            )
            assert res_card_funding == payment_methods[0].get("card_funding")

    @pytest.mark.parametrize(
        argvalues=[
            BillStatus.REFUNDED,
            BillStatus.CANCELLED,
            BillStatus.PROCESSING,
            BillStatus.PAID,
        ],
        argnames="bill_status",
    )
    def test_update_payment_method_on_bill_invalid_bills(
        self, billing_service, bill_status
    ):
        bill = billing_service.bill_repo.create(
            instance=(
                factories.BillFactory.build(
                    status=bill_status, amount=1_000_000, last_calculated_fee=30_000
                )
            )
        )

        res = billing_service.update_payment_method_on_bill(
            bill, record_type="admin_billing_workflow"
        )
        assert (
            res
            == f"Bill <{bill.id}> is not in status NEW or FAILED. Update payment method failed."
        )

    def test_update_payment_method_on_bill_invalid_payor_type(
        self,
        billing_service,
    ):
        bill = billing_service.bill_repo.create(
            instance=(
                factories.BillFactory.build(
                    status=BillStatus.NEW,
                    amount=1_000_000,
                    last_calculated_fee=30_000,
                    payor_type=PayorType.CLINIC,
                )
            )
        )

        res = billing_service.update_payment_method_on_bill(
            bill, record_type="admin_billing_workflow"
        )
        assert (
            res
            == f"Bill <{bill.id}> is not an EMPLOYER or MEMBER bill. Update payment method failed."
        )

    @pytest.mark.parametrize(
        ids=(
            [
                "No Refunds in table, all rows in date range - success and failures",
                "One FAILED Refund in table;all rows in date range",
                "One PAID Refund in table(ignored);  all rows in date range",
                "One Refund in table, some rows in date range",
            ]
        ),
        argnames="refunded_bills,  start_date, end_date,  expected_results_indices",
        argvalues=(
            # No Refunds in table, all rows in date range - success and failures
            (
                [],
                date(2018, 11, 12),
                date(2018, 11, 20),
                [1, 4],
            ),
            # One FAILED Refund in table;all rows in date range
            (
                [
                    factories.BillFactory.build(
                        payor_id=1,
                        amount=-20,
                        payor_type=PayorType.MEMBER,
                        status=BillStatus.FAILED,
                    )
                ],
                date(2018, 11, 12),
                date(2018, 11, 20),
                [4],
            ),
            # One PAID Refund in table(ignored);  all rows in date range
            (
                [
                    factories.BillFactory.build(
                        payor_id=1,
                        amount=-20,
                        payor_type=PayorType.MEMBER,
                        status=BillStatus.PAID,
                    )
                ],
                date(2018, 11, 12),
                date(2018, 11, 20),
                [1, 4],
            ),
            # One Refund in table filters out the rows in date range
            (
                [
                    factories.BillFactory.build(
                        payor_id=3,
                        amount=-20,
                        payor_type=PayorType.MEMBER,
                        status=BillStatus.FAILED,
                    )
                ],
                date(2018, 11, 14),
                date(2018, 11, 15),
                [],
            ),
        ),
    )
    def test_compute_new_member_bills_to_process(
        self,
        billing_service,
        multiple_pre_created_bills,
        refunded_bills,
        start_date,
        end_date,
        expected_results_indices,
    ):
        expected_bill_uuids = {
            multiple_pre_created_bills[i].uuid for i in expected_results_indices
        }
        [billing_service.bill_repo.create(instance=bill) for bill in refunded_bills]

        bills = billing_service.compute_new_member_bills_to_process(
            start_date, end_date
        )
        result_bill_uuids = {bill.uuid for bill in bills}
        assert expected_bill_uuids == result_bill_uuids

    @pytest.mark.parametrize(
        ids=(
            [
                "No Refunds in table, all rows in date range - success and failures",
                "One FAILED Refund in table;all rows in date range",
                "One PAID Refund in table(ignored);  all rows in date range",
                "One Refund in table, some rows in date range",
            ]
        ),
        argnames="refunded_bills,  start_date, end_date,  expected_results_indices",
        argvalues=(
            # No Refunds in table, all rows in date range - success and failures
            (
                [],
                date(2018, 11, 12),
                date(2018, 11, 20),
                [1, 4],
            ),
            # One FAILED Refund in table;all rows in date range
            (
                [
                    factories.BillFactory.build(
                        payor_id=1,
                        amount=-20,
                        payor_type=PayorType.MEMBER,
                        status=BillStatus.FAILED,
                    )
                ],
                date(2018, 11, 12),
                date(2018, 11, 20),
                [1, 4],
            ),
            # One PAID Refund in table(ignored);  all rows in date range
            (
                [
                    factories.BillFactory.build(
                        payor_id=1,
                        amount=-20,
                        payor_type=PayorType.MEMBER,
                        status=BillStatus.PAID,
                    )
                ],
                date(2018, 11, 12),
                date(2018, 11, 20),
                [1, 4],
            ),
            # One Refund in table filters out the rows in date range
            (
                [
                    factories.BillFactory.build(
                        payor_id=3,
                        amount=-20,
                        payor_type=PayorType.MEMBER,
                        status=BillStatus.FAILED,
                    )
                ],
                date(2018, 11, 14),
                date(2018, 11, 15),
                [4],
            ),
        ),
    )
    def test_compute_new_member_bills(
        self,
        billing_service,
        multiple_pre_created_bills,
        refunded_bills,
        start_date,
        end_date,
        expected_results_indices,
    ):
        expected_bill_uuids = {
            multiple_pre_created_bills[i].uuid for i in expected_results_indices
        }
        [billing_service.bill_repo.create(instance=bill) for bill in refunded_bills]

        bills = billing_service.compute_new_member_bills(start_date, end_date)
        result_bill_uuids = {bill.uuid for bill in bills}
        assert expected_bill_uuids == result_bill_uuids

    @pytest.mark.parametrize(
        argvalues=[
            (0, -1, True, 100, PayorType.MEMBER),
            (2, -0.5, True, 200, PayorType.MEMBER),
            (0, -1.1, False, 300, PayorType.MEMBER),
            (2, -1.5, False, 400, PayorType.MEMBER),
            (1, -1, False, 500, PayorType.MEMBER),
            (3, -0.5, False, 600, PayorType.MEMBER),
            (4, -1, True, 700, PayorType.MEMBER),
            (4, -1.5, False, 700, PayorType.MEMBER),
            (0, -1, False, 100, PayorType.EMPLOYER),
            (2, -0.5, False, 200, PayorType.EMPLOYER),
        ],
        argnames="bill_index, refund_factor, not_none_expected, procedure_id, payor_type",
        ids=(
            "Last state paid, abs(refund) = amount",
            "Last state paid, abs(refund) < amount",
            "Last state paid, abs(refund) > amount (1)",
            "Last state paid, abs(refund) > amount (2)",
            "Last state not paid, abs(refund) = amount",
            "Last state not paid, abs(refund) < amount",
            "Last state NEW, abs(refund) < amount",
            "Last state NEW, abs(refund) > amount",
            "Last state paid, abs(refund) = amount, none expected - payor type different",
            "Last state paid, abs(refund) < amount, none expected - payor type different",
        ),
    )
    def test_compute_linked_paid_or_new_bill_and_trans_for_refund_or_transfer_reverse(
        self,
        billing_service,
        random_reimbursement_wallet_with_benefit,
        bill_processing_record_statuses,
        bill_index,
        refund_factor,
        not_none_expected,
        procedure_id,
        payor_type,
    ):
        record_dict_coll = self._generate_bill_processing_records_dict(
            billing_service,
            random_reimbursement_wallet_with_benefit,
            bill_processing_record_statuses,
            True,
            procedure_id,
            payor_type,
        )

        bills = [v["bill"] for v in record_dict_coll.values()]
        old_bill = bills[bill_index]
        refund_bill = factories.BillFactory.build(
            amount=old_bill.amount * refund_factor, procedure_id=old_bill.procedure_id
        )
        if not_none_expected:
            # TODO @Rajneesh, make less awful
            exp_rec = (
                None
                if old_bill.status == BillStatus.NEW
                else record_dict_coll[old_bill.id]["records"][-1]
            )
            exp_bill = old_bill
        else:
            exp_rec, exp_bill = None, None
        (
            res_bill,
            res_rec,
        ) = billing_service.compute_linked_paid_or_new_bill_and_trans_for_refund_or_transfer_reverse(
            refund_bill
        )
        assert res_rec == exp_rec
        assert (exp_bill, res_bill) == (None, None) or exp_bill.id == res_bill.id

    @pytest.mark.parametrize(
        ids=[
            "Last Bill NEW status, valid refund (1)",
            "Last Bill NEW status, valid refund (1)",
            "Last Bill NEW status, invalid refund",
            "Bill with PAID status present, valid refund (1)",
            "Bill with PAID status present, valid refund (1)",
            "Bill with PAID status present, invalid refund",
            "Last Bill NEW status, invalid refund - Payor type mismatch",
            "Bill with PAID status present, invalid refund (1) - Payor type mismatch",
            "Last Bill FAILED status, valid refund (1)",
        ],
        argvalues=[
            (0, 5, 1, 3000, PayorType.MEMBER, 4, True, False),
            (0, 5, 0.5, 3100, PayorType.MEMBER, 4, True, False),
            (0, 5, 1.1, 3200, PayorType.MEMBER, 4, False, False),
            (0, 4, 1, 3000, PayorType.MEMBER, 2, True, True),
            (0, 4, 0.5, 3100, PayorType.MEMBER, 2, True, True),
            (0, 4, 1.1, 3200, PayorType.MEMBER, 2, False, False),
            (0, 5, 0.5, 3100, PayorType.EMPLOYER, 2, False, False),
            (0, 4, 1, 3000, PayorType.EMPLOYER, 2, False, False),
            (5, 6, 1, 3100, PayorType.MEMBER, 0, True, False),
        ],
        argnames="st_idx, no_of_bills_to_include, refund_factor, procedure_id,payor_type, expected_bill_index, exp_res, exp_rec_flg",
    )
    def test_compute_linked_paid_or_new_bill_and_trans_for_refund_one_procedure_id(
        self,
        billing_service,
        random_reimbursement_wallet_with_benefit,
        bill_processing_record_statuses,
        st_idx,
        no_of_bills_to_include,
        refund_factor,
        procedure_id,
        payor_type,
        expected_bill_index,
        exp_res,
        exp_rec_flg,
    ):
        # All these bills will have the same procedure id
        bill_processing_record_statuses = [
            [BillStatus.PROCESSING, BillStatus.PAID],  # Bill 0
            [BillStatus.PROCESSING],  # Bill 1
            [BillStatus.NEW, BillStatus.PROCESSING, BillStatus.PAID],  # Bill 2
            [BillStatus.NEW, BillStatus.PAID, BillStatus.REFUNDED],  # Bill 3
            [BillStatus.NEW],  # Bill 4
            [BillStatus.PROCESSING, BillStatus.FAILED],  # Bill 5
        ]

        record_dict_coll = self._generate_bill_processing_records_dict(
            billing_service,
            random_reimbursement_wallet_with_benefit,
            bill_processing_record_statuses[st_idx:no_of_bills_to_include],
            False,
            procedure_id,
            payor_type,
        )

        created_bills = [v["bill"] for v in record_dict_coll.values()]
        refund_linked_bill = created_bills[expected_bill_index]

        refund_bill = factories.BillFactory.build(
            amount=refund_linked_bill.amount * refund_factor,
            procedure_id=refund_linked_bill.procedure_id,
        )
        if exp_res:
            # TODO @Rajneesh, make less awful
            exp_rec = (
                record_dict_coll[refund_linked_bill.id]["records"][-1]
                if exp_rec_flg
                else None
            )
            exp_bill = refund_linked_bill
        else:
            exp_rec, exp_bill = None, None
        (
            res_bill,
            res_rec,
        ) = billing_service.compute_linked_paid_or_new_bill_and_trans_for_refund_or_transfer_reverse(
            refund_bill
        )
        assert exp_rec == res_rec
        assert (exp_bill, res_bill) == (None, None) or exp_bill.id == res_bill.id

    @staticmethod
    def _generate_bill_processing_records_dict(
        billing_service,
        random_reimbursement_wallet_with_benefit,
        inp_bill_processing_record_statuses,
        diff_procedure_id_flag,
        procedure_id,
        payor_type=PayorType.MEMBER,
    ):
        record_dict = {}
        created_at = datetime.datetime.now().replace(microsecond=0)
        _ = TreatmentProcedureFactory.create(
            id=procedure_id,
            status=TreatmentProcedureStatus.COMPLETED,
        )
        for i, record_statuses in enumerate(inp_bill_processing_record_statuses):
            status = (
                BillStatus.PAID
                if record_statuses[-1] in (BillStatus.PAID, BillStatus.REFUNDED)
                else record_statuses[-1]
            )
            created_at = created_at + datetime.timedelta(seconds=10 * i)
            if payor_type == PayorType.MEMBER:
                bill_wallet = random_reimbursement_wallet_with_benefit()
                bill = factories.BillFactory.build(
                    amount=BILL_AMOUNT,
                    status=status.value,
                    procedure_id=procedure_id,
                    created_at=created_at,
                    payor_type=payor_type,
                    payor_id=bill_wallet.id,
                )
                _ = CostBreakdownFactory.create(
                    id=bill.cost_breakdown_id,
                    wallet_id=bill.payor_id,
                    total_member_responsibility=BILL_AMOUNT,
                )
            else:
                bill = factories.BillFactory.build(
                    amount=BILL_AMOUNT,
                    status=status.value,
                    procedure_id=procedure_id,
                    created_at=created_at,
                    payor_type=payor_type,
                )
                _ = CostBreakdownFactory.create(
                    wallet_id=bill.payor_id,
                    total_employer_responsibility=BILL_AMOUNT,
                )
            procedure_id += int(diff_procedure_id_flag)
            if diff_procedure_id_flag:
                _ = TreatmentProcedureFactory.create(
                    id=procedure_id,
                    status=TreatmentProcedureStatus.COMPLETED,
                )
            bill = billing_service.bill_repo.create(instance=bill)
            record_dict[bill.id] = {"bill": bill, "records": []}
            if (
                status != BillStatus.NEW
            ):  # new bills dont get a bpr. @Rajneesh TODO change this for consistency
                for r_count, status in enumerate(record_statuses):
                    created_at = created_at + datetime.timedelta(
                        seconds=10
                    )  # 10 sec gap between records
                    record = factories.BillProcessingRecordFactory.build(
                        bill_id=bill.id,
                        processing_record_type=f"test_{bill.id}_{r_count}",
                        bill_status=status.value,
                        created_at=created_at,
                    )
                    record = billing_service.bill_processing_record_repo.create(
                        instance=record
                    )
                    record_dict[bill.id]["records"].append(record)
        return record_dict

    @pytest.mark.parametrize(
        argvalues=[(False, 101010, {0: True, 3: False}), (True, 201012, {0: True})],
        argnames="diff_procedure_id_flag, procedure_id, expected_bill_index_to_bpr",
    )
    def test_compute_all_linked_paid_or_new_bill_and_trans_for_procedure(
        self,
        billing_service,
        random_reimbursement_wallet_with_benefit,
        diff_procedure_id_flag,
        procedure_id,
        expected_bill_index_to_bpr,
    ):
        # All these bills will have the same procedure id
        bill_processing_record_statuses = [
            [BillStatus.NEW, BillStatus.PROCESSING, BillStatus.PAID],  # Bill 0
            [BillStatus.NEW, BillStatus.PROCESSING],  # Bill 1
            [
                BillStatus.NEW,
                BillStatus.PROCESSING,
                BillStatus.PAID,
                BillStatus.REFUNDED,
            ],  # Bill 2
            [BillStatus.NEW],  # Bill 3
        ]

        record_dict_coll = self._generate_bill_processing_records_dict(
            billing_service,
            random_reimbursement_wallet_with_benefit,
            bill_processing_record_statuses,
            diff_procedure_id_flag,
            procedure_id,
        )

        expected = set()
        for i, id in enumerate(record_dict_coll):
            if i in expected_bill_index_to_bpr:
                bill = record_dict_coll[id]["bill"]
                bpr_id = (
                    record_dict_coll[id]["records"][-1].id
                    if record_dict_coll[id]["records"]
                    else None
                )
                expected.add((bill.id, bpr_id))
        res = (
            billing_service.compute_all_linked_paid_or_new_bill_and_trans_for_procedure(
                procedure_id
            )
        )
        res = {(bill.id, bpr.id if bpr else None) for (bill, bpr) in res}
        assert res == expected

    @pytest.mark.parametrize(
        "id, error_code, expected_err",
        [
            (1011, 400, "GeneralPaymentProcessorError"),
            (2011, 422, "ValidationErrorResponse"),
            (3011, 429, "RateLimitPaymentProcessorError"),
            (4011, 503, "ConnectionPaymentProcessorError"),
            (5011, 666, DEFAULT_GATEWAY_ERROR_RESPONSE),
        ],
    )
    def test_payment_gateway_exceptions(
        self, id, billing_service, error_code, expected_err
    ):
        bill = factories.BillFactory.build(id=id, status=BillStatus.NEW)
        billing_service.bill_repo.create(instance=bill)
        mock_response = Response()
        mock_response.status_code = error_code
        mock_response.encoding = "application/json"
        ex_payload = "This is the error message."
        mock_response._content = ex_payload.encode("utf-8")
        create_transaction_mock = mock.Mock(
            side_effect=PaymentsGatewayException(
                "Mock Error", code=error_code, response=mock_response
            )
        )
        billing_service.payment_gateway_client.create_transaction = (
            create_transaction_mock
        )
        with pytest.raises(PaymentsGatewayException):
            with patch(
                "direct_payment.billing.billing_service.payments_customer_id",
            ) as _get_customer_id_from_payor_mock:
                _get_customer_id_from_payor_mock.return_value = 1
                billing_service.set_new_bill_to_processing(bill)
        res = billing_service.get_bill_by_id(bill.id)
        # check that the bill has the expected status and error
        assert res.status == BillStatus.FAILED
        assert res.error_type == OTHER_MAVEN
        # reload the bill records
        updated_bill_recs = (
            billing_service.bill_processing_record_repo.get_bill_processing_records(
                [bill.id]
            )
        )
        assert len(updated_bill_recs) == 2
        assert [br.bill_status for br in updated_bill_recs] == [
            BillStatus.PROCESSING.value,
            BillStatus.FAILED.value,
        ]
        # the last bill record was the one that was inserted.
        assert updated_bill_recs[-1].body == {
            "gateway_error": expected_err,
            "gateway_response": ex_payload,
        }


@pytest.fixture
def create_mock_response_fixture():
    def create_mock_response(transaction_data, uuid_param_str, metadata):
        content = json.dumps(
            {
                "transaction_id": uuid_param_str,
                "transaction_data": transaction_data,
                "status": "completed",
                "metadata": metadata or {},
            }
        )
        mock_response = Response()
        mock_response._content = content.encode("utf-8")
        mock_response.status_code = 200
        return mock_response

    return create_mock_response


class TestBillCreation:
    @pytest.mark.parametrize(
        argnames="payor_type, amount, label, payor_id, treatment_procedure_id, cost_breakdown_id, payment_method_type,"
        "inp_payment_method_id, expected_fee, exp_payment_method_id, exp_created_at, exp_proc_scheduled_at_or_after",
        argvalues=[
            (
                PayorType.EMPLOYER,
                10000,
                None,
                10,
                20,
                30,
                PaymentMethodType.card.value,
                "payment_method_id_0",
                300,
                "payment_method_id_0",
                CURRENT_TIME,
                CURRENT_TIME,
            ),
            (
                PayorType.EMPLOYER,
                10200,
                "Label",
                10,
                20,
                30,
                PaymentMethodType.us_bank_account.value,
                "payment_method_id_1",
                0,
                "payment_method_id_1",
                CURRENT_TIME,
                CURRENT_TIME,
            ),
            (
                PayorType.EMPLOYER,
                0,
                "Label",
                10,
                20,
                30,
                PaymentMethodType.us_bank_account.value,
                "payment_method_id_2",
                0,
                None,
                CURRENT_TIME,
                CURRENT_TIME,
            ),
            (
                PayorType.CLINIC,
                10000,
                None,
                101,
                20,
                30,
                None,
                None,
                0,
                None,
                CURRENT_TIME,
                CURRENT_TIME,
            ),
            (
                PayorType.CLINIC,
                20000,
                "Label",
                101,
                20,
                30,
                None,
                None,
                0,
                None,
                CURRENT_TIME,
                CURRENT_TIME,
            ),
            (
                PayorType.CLINIC,
                0,
                "Label",
                101,
                20,
                30,
                None,
                None,
                0,
                None,
                CURRENT_TIME,
                CURRENT_TIME,
            ),
            (
                PayorType.CLINIC,
                -20000,
                "Label",
                101,
                20,
                30,
                None,
                None,
                0,
                None,
                CURRENT_TIME,
                CURRENT_TIME,
            ),
            (
                PayorType.MEMBER,
                0,
                "Label",
                101,
                20,
                30,
                PaymentMethodType.us_bank_account.value,
                "payment_method_id_3",
                0,
                None,
                CURRENT_TIME,
                CURRENT_TIME,
            ),
            (
                PayorType.MEMBER,
                10001,
                "Label",
                101,
                20,
                30,
                PaymentMethodType.card.value,
                "payment_method_id_4",
                300,
                "payment_method_id_4",
                CURRENT_TIME,
                OFFSET_TIME,
            ),
            (
                PayorType.MEMBER,
                10001,
                "Label",
                101,
                20,
                30,
                None,
                None,
                0,
                None,
                CURRENT_TIME,
                OFFSET_TIME,
            ),
            (
                PayorType.EMPLOYER,
                10001,
                "Label",
                101,
                20,
                30,
                None,
                None,
                0,
                None,
                CURRENT_TIME,
                CURRENT_TIME,
            ),
        ],
    )
    def test_create_bill(
        self,
        billing_service,
        payor_type,
        amount,
        label,
        payor_id,
        treatment_procedure_id,
        cost_breakdown_id,
        payment_method_type,
        inp_payment_method_id,
        expected_fee,
        exp_payment_method_id,
        exp_created_at,
        exp_proc_scheduled_at_or_after,
    ):
        with mock.patch(
            "direct_payment.billing.billing_service.payments_customer_id",
            return_value=uuid.uuid4(),
        ):
            if payment_method_type:
                payment_method_type_ = [payment_method_type]
                payment_methods = [
                    {
                        "payment_method_type": payment_method_type,
                        "last4": "1234",
                        "brand": "visa",
                        "payment_method_id": inp_payment_method_id,
                    }
                ]
            else:
                payment_method_type_ = ("",)
                payment_methods = []
            with freezegun.freeze_time(exp_created_at):
                with mock.patch(
                    "common.payments_gateway.client.PaymentsGatewayClient.get_customer",
                    return_value=Customer.create_from_dict(
                        {
                            "customer_id": "00112233-4455-6677-8899-aabbccddeeff",
                            "customer_setup_status": "succeeded",
                            "payment_method_types": payment_method_type_,
                            "payment_methods": payment_methods,
                        }
                    ),
                ):
                    _ = TreatmentProcedureFactory.create(
                        id=treatment_procedure_id,
                        status=TreatmentProcedureStatus.COMPLETED,
                    ).id
                    result = billing_service.create_bill(
                        payor_type,
                        amount,
                        label,
                        payor_id,
                        treatment_procedure_id,
                        cost_breakdown_id,
                    )
        assert result.id is not None
        assert result.uuid is not None
        assert result.payor_type == payor_type
        assert result.amount == amount
        assert result.last_calculated_fee == expected_fee
        assert result.label == label
        assert result.payor_type == payor_type
        assert result.payor_id == payor_id
        assert result.procedure_id == treatment_procedure_id
        assert result.cost_breakdown_id == cost_breakdown_id
        assert result.status == BillStatus.NEW
        assert result.modified_at == result.created_at
        assert result.payment_method_id == exp_payment_method_id
        assert result.created_at == exp_created_at
        assert result.processing_scheduled_at_or_after == exp_proc_scheduled_at_or_after

    @pytest.mark.parametrize(
        argnames="card_funding, expected_fee, expected_card_funding",
        argvalues=[
            ("PREPAID", 0, CardFunding.PREPAID),
            ("DEBIT", 0, CardFunding.DEBIT),
            ("CREDIT", 3, CardFunding.CREDIT),
            ("UNKNOWN", 0, CardFunding.UNKNOWN),
            ("", 3, None),
        ],
        ids=[
            "prepaid card",
            "debit card",
            "credit card",
            "unknown card funding",
            "empty card funding",
        ],
    )
    def test_create_bill_with_fee_calculation(
        self,
        billing_service,
        card_funding,
        expected_fee,
        expected_card_funding,
        ff_test_data,
    ):
        with mock.patch(
            "direct_payment.billing.billing_service.payments_customer_id",
            return_value=uuid.uuid4(),
        ):
            payment_method_type_ = ["card"]
            payment_methods = [
                {
                    "payment_method_type": "card",
                    "last4": "1234",
                    "brand": "visa",
                    "payment_method_id": "pm1",
                    "card_funding": card_funding,
                }
            ]

            with mock.patch(
                "common.payments_gateway.client.PaymentsGatewayClient.get_customer",
                return_value=Customer.create_from_dict(
                    {
                        "customer_id": "00112233-4455-6677-8899-aabbccddeeff",
                        "customer_setup_status": "succeeded",
                        "payment_method_types": payment_method_type_,
                        "payment_methods": payment_methods,
                    }
                ),
            ):
                tp_id = TreatmentProcedureFactory.create(
                    status=TreatmentProcedureStatus.COMPLETED
                ).id
                result = billing_service.create_bill(
                    PayorType.MEMBER,
                    100,
                    "label",
                    101,
                    tp_id,
                    20,
                )

            assert result.id is not None
            assert result.uuid is not None
            assert result.amount == 100
            assert result.last_calculated_fee == expected_fee
            assert result.label == "label"
            assert result.payor_type == PayorType.MEMBER
            assert result.payor_id == 101
            assert result.procedure_id == tp_id
            assert result.cost_breakdown_id == 20
            assert isinstance(result.created_at, datetime.datetime)
            assert result.status == BillStatus.NEW
            assert result.modified_at == result.created_at
            assert result.payment_method_id == "pm1"
            assert result.card_funding == expected_card_funding

    @pytest.mark.parametrize(
        argnames="payor_type",
        argvalues=(
            PayorType.EMPLOYER,
            PayorType.MEMBER,
        ),
    )
    def test_create_bill_missing_customer_id(self, billing_service, payor_type):
        with pytest.raises(errors.PaymentsGatewaySetupError):
            _ = billing_service.create_bill(
                payor_type=PayorType.MEMBER,
                amount=10000,
                payor_id=100000,
                label="does_not_matter",
                treatment_procedure_id=10101,
                cost_breakdown_id=20102,
            )

    @pytest.mark.parametrize(
        argnames="payor_type, status, amount, fee, create_bpr, is_ephemeral",
        argvalues=[
            (PayorType.EMPLOYER, BillStatus.NEW, 9000, 100, False, False),
            (PayorType.EMPLOYER, BillStatus.PAID, 8000, 200, True, False),
            (PayorType.MEMBER, BillStatus.PAID, 7000, 300, True, False),
            (PayorType.MEMBER, BillStatus.NEW, 6000, 0, False, False),
            (PayorType.CLINIC, BillStatus.NEW, 6000, 0, False, False),
            (PayorType.CLINIC, BillStatus.PAID, 6000, 0, False, False),
            (PayorType.MEMBER, BillStatus.NEW, 0, 0, False, True),
        ],
    )
    def test_create_full_refund_bill_from_bill(
        self,
        billing_service,
        payor_type,
        status,
        amount,
        fee,
        create_bpr,
        is_ephemeral,
    ):
        bill = factories.BillFactory.build(
            payor_type=payor_type,
            status=status,
            amount=amount,
            last_calculated_fee=fee,
            is_ephemeral=is_ephemeral,
            procedure_id=TreatmentProcedureFactory.create(
                status=TreatmentProcedureStatus.COMPLETED
            ).id,
        )
        bill = billing_service.bill_repo.create(instance=bill)
        bpr = None
        if create_bpr:
            bpr = billing_service.bill_processing_record_repo.create(
                instance=factories.BillProcessingRecordFactory.build(
                    processing_record_type="payment_gateway_request",
                    bill_id=bill.id,
                    bill_status=bill.status.value,
                )
            )

        with freezegun.freeze_time(CURRENT_TIME):
            result = billing_service.create_full_refund_bill_from_bill(bill, bpr)
        assert result.payor_type == bill.payor_type
        assert result.label == bill.label
        assert result.payor_type == bill.payor_type
        assert result.payor_id == bill.payor_id
        assert result.procedure_id == bill.procedure_id
        assert result.cost_breakdown_id == bill.cost_breakdown_id
        assert result.status == BillStatus.NEW
        assert result.payment_method_id == bill.payment_method_id
        assert result.payment_method_type == bill.payment_method_type
        # costs should be in the opposite direction
        assert result.amount == bill.amount * -1
        assert result.last_calculated_fee == bill.last_calculated_fee * -1
        # ensure that things that shouldn't be inherited weren't inherited
        assert result.id != bill.id
        assert result.uuid != bill.uuid
        assert result.modified_at == result.created_at
        assert result.cancelled_at is None
        assert result.refunded_at is None
        assert result.paid_at is None
        assert result.failed_at is None
        assert result.processing_at is None
        assert result.created_at == CURRENT_TIME
        assert result.processing_scheduled_at_or_after == result.created_at

    @pytest.mark.parametrize(
        argnames="payor_type, status, amount, fee, create_bpr, is_ephemeral",
        argvalues=[
            (PayorType.EMPLOYER, BillStatus.PROCESSING, 8000, 200, True, False),
            (PayorType.MEMBER, BillStatus.NEW, -6000, 400, False, False),
            (PayorType.MEMBER, BillStatus.NEW, 0, 0, False, False),
        ],
    )
    def test_create_full_refund_bill_from_bill_with_error(
        self, billing_service, payor_type, status, amount, fee, create_bpr, is_ephemeral
    ):
        bill = factories.BillFactory.build(
            payor_type=payor_type, status=status, amount=amount, last_calculated_fee=fee
        )
        bill = billing_service.bill_repo.create(instance=bill)
        bpr = None
        if create_bpr:
            bpr = billing_service.bill_processing_record_repo.create(
                instance=factories.BillProcessingRecordFactory.build(
                    processing_record_type="payment_gateway_request",
                    bill_id=bill.id,
                    bill_status=bill.status.value,
                )
            )
        with pytest.raises(InvalidRefundBillCreationError):
            _ = billing_service.create_full_refund_bill_from_bill(bill, bpr)

    @pytest.mark.parametrize(
        "new_responsibility, past_bill_amounts, expected_amount, expected_past_amount",
        [
            (100, [], 100, 0),
            (100, [20], 80, 20),
            (100, [200], -100, 200),
            (10, [10, 20, 100], -120, 130),
            (10, [20, -10], None, 10),
            (10, [10], None, 10),
            (0, [], 0, 0),
            (0, [0], None, 0),
        ],
    )
    def test_calculate_bill_amount_from_new_responsibility(
        self,
        billing_service,
        bill_procedure,
        bill_wallet,
        new_responsibility,
        past_bill_amounts,
        expected_amount,
        expected_past_amount,
    ):
        bills = factories.BillFactory.build_batch(
            size=len(past_bill_amounts),
            amount=factory.Iterator(past_bill_amounts),
            procedure_id=bill_procedure.id,
            payor_type=PayorType.MEMBER,
            payor_id=bill_wallet.id,
        )
        _ = [billing_service.bill_repo.create(instance=bill) for bill in bills]
        (
            amount,
            past_amount,
        ) = billing_service.calculate_new_and_past_bill_amount_from_new_responsibility(
            new_responsibility=new_responsibility,
            procedure_id=bill_procedure.id,
            payor_type=PayorType.MEMBER,
            payor_id=bill_wallet.id,
        )
        assert amount == expected_amount
        assert past_amount == expected_past_amount


class TestPaymentGatewayEventProcessing:
    @pytest.mark.parametrize(
        argnames="message, expected_msg",
        argvalues=[
            (
                {},
                {
                    "The event_type key is missing from the message.",
                    "The message_payload key is missing from the message.",
                },
            ),
            (
                {"unknown_key": None},
                {
                    "The event_type key is missing from the message.",
                    "The message_payload key is missing from the message.",
                },
            ),
            (
                {"event_type": "billing_event"},
                {
                    "The message_payload key is missing from the message.",
                },
            ),
            (
                {"message_payload": {"key": "value"}},
                {
                    "The event_type key is missing from the message.",
                },
            ),
            (
                {"event_type": None},
                {
                    "Received unsupported event_type None from payment gateway.",
                    "The message_payload key is missing from the message.",
                },
            ),
            (
                {"event_type": "unknown_event_type"},
                {
                    "Received unsupported event_type unknown_event_type from payment gateway.",
                    "The message_payload key is missing from the message.",
                },
            ),
            (
                {
                    "event_type": "billing_event",
                    "message_payload": None,
                    "error_payload": None,
                },
                {
                    "The message_payload is None.",
                    "The error_payload is None.",
                },
            ),
            (
                {
                    "event_type": "billing_event",
                    "message_payload": {},
                    "error_payload": {},
                },
                {
                    "The message_payload is empty.",
                },
            ),
            (
                {
                    "event_type": "billing_event",
                    "message_payload": ["clearly_wrong"],
                    "error_payload": ["also_wrong"],
                },
                {
                    "The message_payload does not implement Mapping.",
                    "The error_payload does not implement Mapping.",
                },
            ),
            (
                {
                    "event_type": "payment_method_attach_event",
                    "message_payload": {
                        "customer_id": "clearly_wrong",
                        "payment_method": {},
                    },
                },
                {
                    "customer_id='clearly_wrong' is badly formed hexadecimal UUID string.",
                    "payment_method is missing key: payment_method_type. "
                    "payment_method is missing key: last4. "
                    "payment_method is missing key: payment_method_id.",
                },
            ),
            (
                {
                    "event_type": "payment_method_attach_event",
                    "message_payload": {
                        "customer_id": str(REUSABLE_UUID),
                        "payment_method": None,
                    },
                },
                {
                    f"Unable to find exactly 1 matching employer clinic or member id for {REUSABLE_UUID}",
                    "payment_method was None in the message_payload.",
                },
            ),
            (
                {
                    "event_type": "payment_method_attach_event",
                    "message_payload": {
                        "customer_id": "    ",
                        "payment_method": ["clearly wrong"],
                    },
                },
                {
                    "customer_id is blank or missing in message_payload.",
                    "payment_method does not implement Mapping.",
                },
            ),
            (
                {
                    "event_type": "payment_method_attach_event",
                    "message_payload": {
                        "customer_id": str(REUSABLE_UUID),
                        "payment_method": {
                            "payment_method_type": "",
                            "last4": "clearly_wrong_000",
                            "brand": "visa",
                            "payment_method_id": "something_made_up",
                        },
                    },
                },
                {
                    f"Unable to find exactly 1 matching employer clinic or member id for {REUSABLE_UUID}",
                    "value mapped to : payment_method_type in payment_method is blank or None. "
                    "payment_method has last_4='clearly_wrong_000' which is not exactly 4 characters long.",
                },
            ),
        ],
    )
    def test_process_payment_gateway_event_message_errors(
        self, billing_service, message, expected_msg
    ):
        with pytest.raises(errors.BillingServicePGMessageProcessingError) as ex_info:
            billing_service.process_payment_gateway_event_message(message)
        assert set(ex_info.value.args[0]) == expected_msg

    def test_process_payment_gateway_event_message_error_bill_not_found(
        self, billing_service
    ):
        reusable_uuid = str(uuid.uuid4())
        message = {
            "event_type": "billing_event",
            "message_payload": {
                "transaction_id": str(reusable_uuid),
                "transaction_data": {},
                "status": {},
                "metadata": {"source_id": "source_id", "source_type": "source_type"},
            },
        }
        expected_msg = {
            "Unable to find matching bill from metadata "
            f"transaction_id={reusable_uuid}, metadata_bill_uuid=None"
        }
        with pytest.raises(errors.BillingServicePGMessageProcessingError) as ex_info:
            billing_service.process_payment_gateway_event_message(message)
        assert set(ex_info.value.args[0]) == expected_msg

    @pytest.mark.parametrize(
        argnames="message_status, bill_status_to_records, bill_index, bill_amount, fees, payor_type, error_payload, "
        "exp_status, exp_error_type, exp_create_clinic_bill_cnt, exp_create_member_employer_bill_cnt, exp_notification_sent, exp_notification",
        argvalues=[
            (
                "pending",
                [(BillStatus.PROCESSING, [BillStatus.PROCESSING])],
                0,
                [BILL_AMOUNT],
                [0],
                PayorType.MEMBER,
                {},
                BillStatus.PROCESSING,
                None,
                0,
                0,
                False,
                None,
            ),
            (
                "pending",
                [(BillStatus.FAILED, [BillStatus.PROCESSING, BillStatus.FAILED])],
                0,
                [BILL_AMOUNT],
                [0],
                PayorType.MEMBER,
                {},
                BillStatus.PROCESSING,
                None,
                0,
                0,
                False,
                None,
            ),
            (
                "completed",
                [
                    (
                        BillStatus.PROCESSING,
                        [BillStatus.PROCESSING, BillStatus.PROCESSING],
                    )
                ],
                0,
                [BILL_AMOUNT],
                [0],
                PayorType.MEMBER,
                {},
                BillStatus.PAID,
                None,
                0,
                0,
                True,
                "mmb_payment_confirmed",
            ),
            (
                "completed",
                [
                    (
                        BillStatus.PROCESSING,
                        [BillStatus.PROCESSING, BillStatus.PROCESSING],
                    )
                ],
                0,
                [BILL_AMOUNT * -1],
                [0],
                PayorType.MEMBER,
                {},
                BillStatus.REFUNDED,
                None,
                0,
                0,
                True,
                "mmb_refund_confirmation",
            ),
            (
                "completed",
                [
                    (
                        BillStatus.PROCESSING,
                        [BillStatus.PROCESSING, BillStatus.PROCESSING],
                    ),
                    (
                        BillStatus.PROCESSING,
                        [BillStatus.PROCESSING, BillStatus.PROCESSING],
                    ),
                ],
                1,
                [BILL_AMOUNT, BILL_AMOUNT * -1],
                [0, 0],
                PayorType.MEMBER,
                {},
                BillStatus.REFUNDED,
                None,
                0,
                0,
                True,
                "mmb_refund_confirmation",
            ),
            (
                "completed",
                [
                    (
                        BillStatus.PROCESSING,
                        [BillStatus.PROCESSING, BillStatus.PROCESSING],
                    ),
                    (
                        BillStatus.PROCESSING,
                        [BillStatus.PROCESSING, BillStatus.PROCESSING],
                    ),
                ],
                0,
                [BILL_AMOUNT, BILL_AMOUNT * -1],
                [0, 0],
                PayorType.MEMBER,
                {},
                BillStatus.PAID,
                None,
                0,
                0,
                True,
                "mmb_payment_confirmed",
            ),
            (
                "completed",
                [
                    (
                        BillStatus.PAID,
                        [BillStatus.PROCESSING, BillStatus.PROCESSING, BillStatus.PAID],
                    )
                ],
                0,
                [BILL_AMOUNT],
                [0],
                PayorType.MEMBER,
                {},
                BillStatus.PAID,
                None,
                0,
                0,
                True,
                "mmb_payment_confirmed",
            ),
            (
                "failed",
                [
                    (
                        BillStatus.PROCESSING,
                        [BillStatus.PROCESSING, BillStatus.PROCESSING],
                    )
                ],
                0,
                [BILL_AMOUNT],
                [0],
                PayorType.MEMBER,
                {"decline_code": "payments_error", "error_detail": "test_details"},
                BillStatus.FAILED,
                OTHER_MAVEN,
                0,
                0,
                True,
                "mmb_payment_processing_error",
            ),
            (
                "failed",
                [
                    (
                        BillStatus.FAILED,
                        [BillStatus.PROCESSING, BillStatus.FAILED],
                    )
                ],
                0,
                [BILL_AMOUNT],
                [0],
                PayorType.MEMBER,
                {"decline_code": "unknown", "error_detail": "test_details"},
                BillStatus.FAILED,
                "UNKNOWN",
                0,
                0,
                True,
                "mmb_payment_processing_error",
            ),
            (
                "failed",
                [
                    (
                        BillStatus.PAID,
                        [BillStatus.PROCESSING, BillStatus.PAID],
                    ),
                    (
                        BillStatus.PROCESSING,
                        [BillStatus.PROCESSING, BillStatus.PROCESSING],
                    ),
                ],
                1,
                [BILL_AMOUNT, BILL_AMOUNT * -1],
                [0, 0],
                PayorType.MEMBER,
                {
                    "decline_code": "new_account_information_available",
                    "error_detail": "test_details",
                },
                BillStatus.FAILED,
                "CONTACT_CARD_ISSUER",
                0,
                0,
                True,
                "mmb_payment_processing_error",
            ),
            (
                "completed",
                [
                    (
                        BillStatus.PROCESSING,
                        [BillStatus.PROCESSING, BillStatus.PROCESSING],
                    )
                ],
                0,
                [BILL_AMOUNT],
                [0],
                PayorType.EMPLOYER,
                {},
                BillStatus.PAID,
                None,
                1,
                0,
                False,
                None,
            ),
            (
                "completed",
                [
                    (
                        BillStatus.PROCESSING,
                        [BillStatus.PROCESSING],
                    )
                ],
                0,
                [BILL_AMOUNT * -1],
                [0],
                PayorType.EMPLOYER,
                {},
                BillStatus.REFUNDED,
                None,
                0,
                0,
                False,
                None,
            ),
            (
                "failed",
                [
                    (
                        BillStatus.PROCESSING,
                        [BillStatus.PROCESSING],
                    )
                ],
                0,
                [BILL_AMOUNT * -1],
                [0],
                PayorType.EMPLOYER,
                {},
                BillStatus.FAILED,
                "UNKNOWN",
                0,
                0,
                False,
                None,
            ),
            (
                "completed",
                [
                    (
                        BillStatus.PROCESSING,
                        [BillStatus.PROCESSING, BillStatus.PROCESSING],
                    )
                ],
                0,
                [BILL_AMOUNT],
                [0.03 * BILL_AMOUNT],
                PayorType.MEMBER,
                {},
                BillStatus.PAID,
                None,
                0,
                0,
                True,
                "mmb_payment_confirmed",
            ),
            (
                "completed",
                [
                    (
                        BillStatus.PROCESSING,
                        [BillStatus.PROCESSING, BillStatus.PROCESSING],
                    )
                ],
                0,
                [BILL_AMOUNT],
                [0],
                PayorType.CLINIC,
                {},
                BillStatus.PAID,
                None,
                0,
                0,
                False,
                None,
            ),
            (
                "failed",
                [
                    (
                        BillStatus.PAID,
                        [BillStatus.PROCESSING, BillStatus.PAID],
                    ),
                    (
                        BillStatus.PROCESSING,
                        [BillStatus.PROCESSING, BillStatus.PROCESSING],
                    ),
                ],
                1,
                [BILL_AMOUNT, BILL_AMOUNT * -1],
                [0, 0],
                PayorType.MEMBER,
                {},
                BillStatus.FAILED,
                "UNKNOWN",
                0,
                0,
                True,
                "mmb_payment_processing_error",
            ),
            (
                "failed",
                [
                    (
                        BillStatus.PAID,
                        [BillStatus.PROCESSING, BillStatus.PAID],
                    ),
                    (
                        BillStatus.PROCESSING,
                        [BillStatus.PROCESSING, BillStatus.PROCESSING],
                    ),
                ],
                1,
                [BILL_AMOUNT, BILL_AMOUNT * -1],
                [0, 0],
                PayorType.MEMBER,
                None,
                BillStatus.FAILED,
                "UNKNOWN",
                0,
                0,
                True,
                "mmb_payment_processing_error",
            ),
            (
                "failed",
                [
                    (
                        BillStatus.PAID,
                        [BillStatus.PROCESSING, BillStatus.PAID],
                    ),
                    (
                        BillStatus.PROCESSING,
                        [BillStatus.PROCESSING, BillStatus.PROCESSING],
                    ),
                ],
                1,
                [BILL_AMOUNT, BILL_AMOUNT * -1],
                [0, 0],
                PayorType.MEMBER,
                {"clearly": "a_bad_value"},
                BillStatus.FAILED,
                "UNKNOWN",
                0,
                0,
                True,
                "mmb_payment_processing_error",
            ),
            (
                "completed",
                [
                    (
                        BillStatus.PROCESSING,
                        [BillStatus.PROCESSING],
                    ),
                    (
                        BillStatus.PAID,
                        [BillStatus.PAID],
                    ),
                ],
                0,
                [-BILL_AMOUNT, BILL_AMOUNT],
                [0, 0],
                PayorType.CLINIC,
                {},
                BillStatus.REFUNDED,
                None,
                0,
                1,
                False,
                None,
            ),
            (
                "failed",
                [
                    (
                        BillStatus.PROCESSING,
                        [BillStatus.PROCESSING],
                    ),
                    (
                        BillStatus.PAID,
                        [BillStatus.PAID],
                    ),
                ],
                0,
                [-BILL_AMOUNT, BILL_AMOUNT],
                [0, 0],
                PayorType.CLINIC,
                {},
                BillStatus.FAILED,
                "UNKNOWN",
                0,
                0,
                False,
                None,
            ),
        ],
        ids=[
            "1. One bill, one record. Gateway acks the payment request."
            "Processing bill stays at processing because of a pending message.",
            "2. One bill, two records. Gateway ack of the payment request was lost."
            "Failed bill moves to processing because of a pending message.",
            "3. One bill, two records. Gateway sends a completed message."
            "Processing bill with +ve amt  moves to paid.",
            "4. One bill, two records. Gateway sends a completed message."
            "Processing bill with -ve amt  moves to refunded.",
            "5. Two bills, two records each - a payment and a refund for that payment both in process in STRIPE."
            "The payment bill moves to REFUNDED because of the completed message",
            "6. Two bills, two records each - a payment and a refund for that payment both in process in STRIPE."
            "The payment bill moves to PAID because of the completed message",
            "7. One Bill, three records, Bill in terminal paid state - further completed messages are absorbed",
            "8. One bill, two records. Gateway sends a failed message."
            "Processing bill moves to Failed.",
            "9. One bill, two records. Gateway sends a failed message."
            "Failed bill moves to Failed.",
            "10. Two bills, two records each - a payment and a refund for that payment both in process in STRIPE."
            "The refund bill moves to Failed because of the failed message",
            "11. One Employer bill, two records. Gateway sends a completed message."
            "Processing bill with +ve amt  moves to paid.",
            "12. Refund employer bill. Gateway sends a completed message."
            "Processing bill with -ve amt  moves to refunded",
            "13. Refund employer bill. Gateway sends a failed message."
            "Processing bill with -ve amt  moves to failed",
            "14. One bill with a fee, two records. Gateway sends a completed message."
            "Processing bill with +ve amt  moves to paid.",
            "15. One Clinic bill, two records. Gateway sends a completed message."
            "Processing bill with +ve amt  moves to paid.",
            "16. One bill, two records. Gateway sends a blank failed message."
            "Processing bill moves to Failed.",
            "17. One bill, two records. Gateway sends a missing failed message."
            "Processing bill moves to Failed.",
            "18. One bill, two records. Gateway sends a malformed failed message."
            "Processing bill moves to Failed.",
            "19. Clinic refund bill. Gateway sends a completed message."
            "Processing bill moves to Refunded, member employer refund bill created",
            "20. Clinic refund bill. Gateway sends a failed message."
            "Processing bill with -ve amt  moves to failed",
        ],
    )
    def test_process_payment_gateway_event_message_billing_event(
        self,
        billing_service,
        reimbursement_wallet,
        reimbursement_wallet_benefit,
        reimbursement_benefit_resource,
        message_status,
        bill_status_to_records,
        bill_index,
        bill_amount,
        fees,
        payor_type,
        error_payload,
        exp_status,
        exp_error_type,
        exp_create_clinic_bill_cnt,
        exp_create_member_employer_bill_cnt,
        exp_notification_sent,
        exp_notification,
    ):
        bills = []
        transaction_ids = []
        # bill_status_to_records_dict represents bills with the corresponding bill records.
        for index, (bill_status, record_statuses) in enumerate(bill_status_to_records):
            transaction_id = uuid.uuid4()
            transaction_ids.append(transaction_id)
            bill = billing_service.bill_repo.create(
                instance=factories.BillFactory.build(
                    amount=bill_amount[index],
                    status=bill_status.value,
                    payor_type=payor_type,
                    payor_id=reimbursement_wallet.id,
                    last_calculated_fee=fees[index],
                    procedure_id=123,
                )
            )
            bills.append(bill)
            for i, record_status in enumerate(record_statuses):
                billing_service.bill_processing_record_repo.create(
                    instance=factories.BillProcessingRecordFactory.build(
                        bill_id=bill.id,
                        bill_status=record_status.value,
                        # 0th BPR is created in the billing service and does not have a transid
                        processing_record_type=(
                            "payment_gateway_event" if i else "billing_service_workflow"
                        ),
                        transaction_id=transaction_id if i else None,
                    )
                )

        modified_bill = bills[bill_index]  # this is the bill we expect to have modified
        modified_bill_rec = (
            billing_service.bill_processing_record_repo.get_bill_processing_records(
                [modified_bill.id]
            )
        )
        # remove modified bill from the bills - these and their recs should be untouched.
        del bills[bill_index]
        non_modified_bill_ids = [bill.id for bill in bills]
        non_modified_bill_recs = (
            billing_service.bill_processing_record_repo.get_bill_processing_records(
                non_modified_bill_ids
            )
        )

        message = {
            "event_type": "billing_event",
            "message_payload": {
                "transaction_id": str(transaction_ids[bill_index]),
                "transaction_data": {
                    "amount": abs(bill_amount[bill_index]) + abs(fees[bill_index])
                },  # PG only deals in +ves
                "status": message_status,
                "metadata": {
                    "source_id": "source_id",
                    "source_type": "source_type",
                    "bill_uuid": str(modified_bill.uuid),
                },
            },
        }
        if error_payload:
            message["error_payload"] = error_payload
        if payor_type == PayorType.CLINIC:
            message["message_payload"]["transaction_data"][
                "description"
            ] = "TEST_DESCRIPTION"

        # The actual fn call.
        with mock.patch(
            "direct_payment.billing.billing_service.from_employer_bill_create_clinic_bill_and_process.delay",
            return_value=None,
        ) as mock_create_clinic_bill_and_process:
            with mock.patch(
                "direct_payment.billing.tasks.rq_job_create_bill.from_clinic_reverse_transfer_bill_create_member_employer_bill_and_process.delay",
                return_value=None,
            ) as mock_create_member_employer_refund_bill_and_process:
                with mock.patch(
                    "direct_payment.billing.billing_service.send_notification_event.delay",
                    side_effect=send_notification_event,
                ):
                    with patch(
                        "utils.braze.send_event_by_ids"
                    ) as mock_send_event_by_ids:
                        billing_service.process_payment_gateway_event_message(message)

        # reload the bill from the db
        res = billing_service.get_bill_by_id(modified_bill.id)
        # check that the bill has the expected status
        assert res.status == exp_status
        assert res.error_type == exp_error_type
        # reload the bill records
        updated_bill_rec = (
            billing_service.bill_processing_record_repo.get_bill_processing_records(
                [modified_bill.id]
            )
        )
        # a new one should have been inserted
        assert len(updated_bill_rec) == len(modified_bill_rec) + 1
        res_non_modified_bill_recs = (
            billing_service.bill_processing_record_repo.get_bill_processing_records(
                non_modified_bill_ids
            )
        )
        assert updated_bill_rec[-1].bill_status == exp_status.value
        assert updated_bill_rec[-1].body == {
            "message_payload": message["message_payload"],
            "error_payload": error_payload or {},
        }

        # confirm that unexpected BPRs were not inserted.
        assert sorted(rec.id for rec in res_non_modified_bill_recs) == sorted(
            rec.id for rec in non_modified_bill_recs
        )
        # confirm that none of the other bills were touched
        for bill in bills:
            bill_from_db = billing_service.get_bill_by_id(bill.id)
            assert bill.status == bill_from_db.status

        # check if an attempt was made to create a clinic bill
        assert (
            mock_create_clinic_bill_and_process.call_count == exp_create_clinic_bill_cnt
        )
        assert (
            mock_create_member_employer_refund_bill_and_process.call_count
            == exp_create_member_employer_bill_cnt
        )
        # test we used the correct employee bill to create the clinic bill
        if mock_create_clinic_bill_and_process.call_count:
            assert (
                mock_create_clinic_bill_and_process.call_args.kwargs["emp_bill_id"]
                == modified_bill.id
            )
        assert mock_send_event_by_ids.called == exp_notification_sent
        if mock_send_event_by_ids.called:
            kwargs = mock_send_event_by_ids.call_args.kwargs
            assert kwargs["event_name"] == exp_notification
            assert kwargs["user_id"] == reimbursement_wallet.user_id

    def test_process_payment_gateway_event_message_bad_transition(
        self,
        billing_service,
    ):
        transaction_id = uuid.uuid4()
        bill = billing_service.bill_repo.create(
            instance=factories.BillFactory.build(
                amount=BILL_AMOUNT, status=BillStatus.PAID
            )
        )

        for i, record_status in enumerate(
            [BillStatus.PROCESSING, BillStatus.PROCESSING, BillStatus.PAID]
        ):
            billing_service.bill_processing_record_repo.create(
                instance=factories.BillProcessingRecordFactory.build(
                    bill_id=bill.id,
                    bill_status=record_status.value,
                    # 0th BPR is created in the billing service and does not have a transid
                    processing_record_type=(
                        "payment_gateway_event" if i else "billing_service_workflow"
                    ),
                    transaction_id=transaction_id if i else None,
                )
            )

        message = {
            "event_type": "billing_event",
            "message_payload": {
                "transaction_id": str(transaction_id),
                "transaction_data": {},
                "status": "pending",
                "metadata": {
                    "source_id": "source_id",
                    "source_type": "source_type",
                    "bill_uuid": str(bill.uuid),
                },
            },
        }
        with pytest.raises(errors.BillingServicePGMessageProcessingError):
            billing_service.process_payment_gateway_event_message(message)

    @pytest.mark.parametrize(
        argnames="bill_amount_to_records, bill_index, msg_amount, msg_bill_uuid, expected_msgs",
        argvalues=[
            (
                [(1000, [BillStatus.PROCESSING])],
                0,
                1001,
                None,
                [
                    "Sanity check failure - amount mismatch bill_amount=1000, transaction_amount=1001"
                ],
            ),
            (
                [(1000, [])],
                0,
                1001,
                None,
                [
                    "Sanity check failure - amount mismatch bill_amount=1000, transaction_amount=1001"
                ],
            ),
            (
                [(2000, [BillStatus.PROCESSING])],
                0,
                2000,
                uuid.uuid4(),
                ["Unable to find matching bill from metadata"],
            ),
            (
                [(2000, [BillStatus.PROCESSING, BillStatus.PROCESSING])],
                0,
                2000,
                uuid.uuid4(),
                ["Sanity check failure - bill uuid mismatch"],
            ),
            (
                [
                    (3000, [BillStatus.PROCESSING, BillStatus.PROCESSING]),
                    (3000, [BillStatus.NEW, BillStatus.PROCESSING]),
                ],
                0,
                3000,
                uuid.uuid4(),
                ["Sanity check failure - bill uuid mismatch "],
            ),
            (
                [(4000, [BillStatus.PROCESSING, BillStatus.PROCESSING])],
                0,
                4004,
                uuid.uuid4(),
                [
                    "Sanity check failure - bill uuid mismatch",
                    "Sanity check failure - amount mismatch bill_amount=4000, transaction_amount=4004",
                ],
            ),
        ],
        ids=[
            "1. Amount check fails - bill found via trans_id",
            "2. Amount check fails - bill found via metadata",
            "3. Bill not found (single bill)",
            "4. Bill UUID check fails (single bill- bill found via trans_id",
            "5. Bill UUID check fails (multiple bills) - bill found via trans_id",
            "6. Amount and Bill UUID checks fail - bill found via trans_id",
        ],
    )
    def test_process_payment_gateway_event_message_sanity_check_failures(
        self,
        billing_service,
        bill_amount_to_records,
        bill_index,
        msg_amount,
        msg_bill_uuid,
        expected_msgs,
    ):
        msg_transaction_id = None
        bills = []
        # bill_status_to_records_dict represents bills with the corresponding bill records.
        for index, (amount, record_statuses) in enumerate(bill_amount_to_records):
            bill_transaction_id = uuid.uuid4()
            if index == bill_index:
                msg_transaction_id = str(bill_transaction_id)
            bill = billing_service.bill_repo.create(
                instance=factories.BillFactory.build(amount=amount)
            )
            bills.append(bill)
            for i, record_status in enumerate(record_statuses):
                billing_service.bill_processing_record_repo.create(
                    instance=factories.BillProcessingRecordFactory.build(
                        bill_id=bill.id,
                        bill_status=record_status.value,
                        # 0th BPR is created in the billing service and does not have a transid
                        processing_record_type=(
                            "payment_gateway_event" if i else "billing_service_workflow"
                        ),
                        transaction_id=bill_transaction_id if i else None,
                    )
                )

        modified_bill = bills[bill_index]  # this is the bill we expect to have modified

        message = {
            "event_type": "billing_event",
            "message_payload": {
                "transaction_id": msg_transaction_id,
                "transaction_data": {
                    "amount": msg_amount,
                },
                "status": "pending",
                "metadata": {
                    "source_id": "source_id",
                    "source_type": "source_type",
                    "bill_uuid": str(msg_bill_uuid or modified_bill.uuid),
                },
            },
        }

        with pytest.raises(errors.BillingServicePGMessageProcessingError) as ex_info:
            billing_service.process_payment_gateway_event_message(message)
        assert len(ex_info.value.args[0]) == len(expected_msgs)
        for res, exp in zip(ex_info.value.args[0], expected_msgs):
            assert exp in res

    @pytest.mark.parametrize(
        argnames="mocked_payor_id, expected_indices, expected_retried_indices, expected_bpr_offsets, inp_last4, "
        "inp_pm_type, inp_pm_id, inp_pm_card_funding, inp_tp_cancelled",
        argvalues=(
            (
                1,
                {0, 1},
                {1},
                [-1, -3],
                "4321",
                PaymentMethodType.card,
                "card_id_1",
                "CREDIT",
                False,
            ),
            (
                2,
                {5, 6, 7},
                {5, 6},
                [-3, -3, -1],
                "4444",
                PaymentMethodType.card,
                "card_id_2",
                "UNKNOWN",
                False,
            ),
            (
                3,
                set(),
                set(),
                [],
                "5555",
                PaymentMethodType.card,
                "card_id_2",
                "",
                False,
            ),
            (
                4,
                set(),
                set(),
                [],
                "7777",
                PaymentMethodType.card,
                "card_id_2",
                None,
                False,
            ),
            (
                1,
                {0, 1},
                {1},
                [-1, -3],
                "4321",
                PaymentMethodType.card,
                "card_id_1",
                "DEBIT",
                False,
            ),
            (
                5,
                set(),
                set(),
                [],
                "8888",
                PaymentMethodType.card,
                "card_id_3",
                None,
                True,
            ),
        ),
        ids=[
            "1. Two bills updated (one new, one failed), and the failed refund ignored.",
            "2. Three bills with different error types updated - only 2 retried",
            "3. No failed bills to update.",
            "4. No failed bill of allowed error type to update",
            "5. Two bills updated (one new, one failed), and card funding is debit",
            "6. No failed bill of allowed error type to update",
        ],
    )
    def test_process_payment_method_attach_event(
        self,
        billing_service,
        reimbursement_wallet,
        reimbursement_wallet_benefit,
        reimbursement_benefit_resource,
        create_cancelled_tp,
        mocked_payor_id,
        expected_indices,
        expected_retried_indices,
        expected_bpr_offsets,
        inp_last4,
        inp_pm_type,
        inp_pm_id,
        inp_pm_card_funding,
        inp_tp_cancelled,
    ):
        bill_factory = partial(
            factories.BillFactory.build,
            payor_type=PayorType.MEMBER,
            payment_method_label="1234",
            payment_method_type=PaymentMethodType.card.value,
            payment_method_id="old_payment_method_id",
        )
        bills_to_create = [
            bill_factory(payor_id=1, status=BillStatus.NEW, amount=1000),
            bill_factory(
                payor_id=1,
                status=BillStatus.FAILED,
                amount=1000,
                error_type=BillErrorTypes.INSUFFICIENT_FUNDS.value,
            ),
            bill_factory(
                payor_id=1,
                status=BillStatus.FAILED,
                amount=-2000,
                error_type=BillErrorTypes.PAYMENT_METHOD_HAS_EXPIRED.value,
            ),
            bill_factory(payor_id=1, status=BillStatus.NEW, amount=-3000),
            bill_factory(payor_id=2, status=BillStatus.PROCESSING, amount=-4000),
            bill_factory(
                payor_id=2,
                status=BillStatus.FAILED,
                amount=5000,
                error_type=BillErrorTypes.INSUFFICIENT_FUNDS.value,
            ),
            bill_factory(
                payor_id=2,
                status=BillStatus.FAILED,
                amount=6000,
                error_type=BillErrorTypes.PAYMENT_METHOD_HAS_EXPIRED.value,
            ),
            bill_factory(
                payor_id=2,
                status=BillStatus.FAILED,
                amount=7000,
                error_type=BillErrorTypes.OTHER_MAVEN.value,
            ),
            bill_factory(payor_id=3, status=BillStatus.PAID, amount=7000),
            bill_factory(
                payor_id=4,
                status=BillStatus.FAILED,
                amount=6000,
                error_type=BillErrorTypes.REQUIRES_AUTHENTICATE_PAYMENT.value,
            ),
            bill_factory(
                payor_id=5,
                status=BillStatus.FAILED,
                amount=6000,
                error_type=BillErrorTypes.OTHER_MAVEN.value,
            ),
        ]
        inp_payload = {
            "event_type": "payment_method_attach_event",
            "message_payload": {
                "customer_id": str(reimbursement_wallet.payments_customer_id),
                "payment_method": {
                    "payment_method_type": inp_pm_type.value,
                    "last4": inp_last4,
                    "brand": "does_not_matter",
                    "payment_method_id": inp_pm_id,
                    "card_funding": inp_pm_card_funding,
                },
            },
        }
        pre_update = {}
        expected_bpr_offsets = iter(expected_bpr_offsets)
        retried_bill_ids = set()
        for i, bill in enumerate(bills_to_create):
            if bill.payor_id == mocked_payor_id:
                bill.payor_id = reimbursement_wallet.id
                if inp_tp_cancelled:
                    tp = create_cancelled_tp(reimbursement_wallet)
                    bill.procedure_id = tp.id
            bill = billing_service.bill_repo.create(instance=bill)
            bpr = billing_service.bill_processing_record_repo.create(
                instance=factories.BillProcessingRecordFactory.build(
                    processing_record_type="payment_gateway_request",
                    bill_id=bill.id,
                    bill_status=bill.status.value,
                )
            )
            if i in expected_indices:
                pre_update[bill.id] = (bill, bpr, next(expected_bpr_offsets))
            if i in expected_retried_indices:
                retried_bill_ids.add(bill.id)

        with mock.patch(
            "direct_payment.billing.billing_service.retry_failed_bills.delay",
            retry_failed_bills,
        ):
            with patch(
                "common.payments_gateway.client.PaymentsGatewayClient.create_transaction",
                side_effect=[
                    Transaction(
                        transaction_id=uuid.uuid4(),
                        transaction_data={"transaction": "data"},
                        status="pending",
                        metadata={"source_id": "1", "source_type": "Type"},
                    )
                ]
                * len(pre_update),
            ):
                with patch(
                    "direct_payment.notification.lib.payment_gateway_handler.send_notification_event.delay",
                    side_effect=send_notification_event,
                ):
                    with patch(
                        "eligibility.service.EnterpriseVerificationService._get_raw_organization_ids_for_user",
                        return_value=[
                            reimbursement_wallet.reimbursement_organization_settings.organization_id
                        ],
                    ):
                        billing_service.process_payment_gateway_event_message(
                            inp_payload
                        )
            exp_bpr_body = {
                "message_payload": inp_payload["message_payload"],
                "delta": {
                    "original_payment_method_data": {
                        "payment_method_label": "1234",
                        "payment_method_type": PaymentMethodType.card.value,
                        "payment_method_id": "old_payment_method_id",
                        "last_calculated_fee": 0,
                    },
                    "replacement_payment_method_data": {
                        "payment_method_label": inp_last4,
                        "payment_method_type": inp_pm_type.value,
                        "payment_method_id": inp_pm_id,
                        "card_funding": inp_pm_card_funding,
                    },
                },
            }
            for base_id, (
                base_bill,
                base_bpr,
                inserted_bpr_offset,
            ) in pre_update.items():
                updated_bill = billing_service.get_bill_by_id(base_id)
                bprs = billing_service.bill_processing_record_repo.get_bill_processing_records(
                    [updated_bill.id]
                )
                inserted_bpr = bprs[inserted_bpr_offset]
                assert (
                    base_bill.payment_method_label != updated_bill.payment_method_label
                )
                exp_bpr_body["delta"]["replacement_payment_method_data"][
                    "last_calculated_fee"
                ] = updated_bill.last_calculated_fee
                assert updated_bill.payment_method_label == inp_last4
                assert (
                    updated_bill.card_funding == CardFunding(inp_pm_card_funding)
                    if inp_pm_card_funding
                    else None
                )
                assert inserted_bpr.id != base_bpr.id
                assert inserted_bpr.body == exp_bpr_body

            for id_ in retried_bill_ids:
                bprs = billing_service.bill_processing_record_repo.get_bill_processing_records(
                    [id_]
                )
                retried_bill = billing_service.get_bill_by_id(id_)
                retried_bpr = bprs[-1]
                # check that we actually retried the bill
                assert retried_bpr.bill_status == BillStatus.PROCESSING.value
                assert retried_bpr.processing_record_type == "payment_gateway_response"
                assert retried_bill.status == BillStatus.PROCESSING


class TestBillRQFunctions:
    @pytest.mark.parametrize(
        argnames="payor_type, bill_status, clinic_bill_statuses, treatment_proc_data",
        argvalues=(
            (
                PayorType.MEMBER,
                BillStatus.PAID,
                [],
                {"cost": 1000, "fertility_clinic_id": 1},
            ),
            (
                PayorType.MEMBER,
                BillStatus.FAILED,
                [],
                {"cost": 1000, "fertility_clinic_id": 1},
            ),
            (
                PayorType.EMPLOYER,
                BillStatus.PAID,
                [],
                {"cost": 1000, "fertility_clinic_id": 0},
            ),
        ),
    )
    def test_from_employer_bill_create_clinic_bill_and_process_failure(
        self,
        billing_service,
        payor_type,
        bill_status,
        clinic_bill_statuses,
        treatment_proc_data,
    ):
        bill = factories.BillFactory.build(payor_type=payor_type, status=bill_status)
        bill = billing_service.bill_repo.create(instance=bill)

        for clinic_bill_status in clinic_bill_statuses:
            clinic_bill = factories.BillFactory.build(
                payor_type=PayorType.CLINIC,
                procedure_id=bill.procedure_id,
                status=clinic_bill_status,
            )
            _ = billing_service.bill_repo.create(instance=clinic_bill)

        with mock.patch(
            "direct_payment.billing.billing_service.get_treatment_procedure_as_dict_from_id",
            return_value=treatment_proc_data,
        ):
            res = from_employer_bill_create_clinic_bill_and_process(emp_bill_id=bill.id)
            assert res == 1

    @pytest.mark.parametrize(
        argnames="pre_existing_clinic_bill_statuses",
        argvalues=(
            [],
            [BillStatus.CANCELLED],
            [BillStatus.CANCELLED, BillStatus.CANCELLED, BillStatus.REFUNDED],
        ),
        ids=[
            "1. No pre-existing clinic bills",
            "2. One pre-existing clinic bills",
            "3. Multiple pre-existing clinic bills",
        ],
    )
    def test_from_employer_bill_create_clinic_bill_and_process(
        self,
        billing_service,
        create_mock_response_fixture,
        pre_existing_clinic_bill_statuses,
    ):
        tp_id = TreatmentProcedureFactory.create(
            status=TreatmentProcedureStatus.COMPLETED
        ).id
        _ = billing_service.bill_repo.create(
            instance=factories.BillFactory.build(
                payor_type=PayorType.MEMBER, procedure_id=tp_id
            )
        )
        bill = factories.BillFactory.build(
            payor_type=PayorType.EMPLOYER, status=BillStatus.PAID, procedure_id=tp_id
        )
        bill = billing_service.bill_repo.create(instance=bill)
        for clinic_bill_status in pre_existing_clinic_bill_statuses:
            clinic_bill = factories.BillFactory.build(
                payor_type=PayorType.CLINIC,
                procedure_id=bill.procedure_id,
                status=clinic_bill_status,
            )
            _ = billing_service.bill_repo.create(instance=clinic_bill)
        tp_cost = 10000
        mocked_tp_dict = {
            "cost": tp_cost,
            "fertility_clinic_id": 10,
            "reimbursement_wallet_id": TEST_WALLET_ID,
        }
        with mock.patch(
            "direct_payment.billing.billing_service.get_treatment_procedure_as_dict_from_id",
            return_value=mocked_tp_dict,
        ), mock.patch(
            "direct_payment.billing.billing_service.BillingService.set_new_bill_to_processing",
        ) as set_new_bill_to_processing:
            with patch(
                "direct_payment.billing.billing_service.payments_customer_id",
            ) as _get_customer_id_from_payor_mock:
                with patch(
                    "common.base_triforce_client.BaseTriforceClient.make_service_request",
                ) as mock_make_request:
                    # fake a call to get the customer id
                    mocked_cust_uuid = uuid.uuid4()
                    _get_customer_id_from_payor_mock.return_value = mocked_cust_uuid
                    # create the transaction data
                    expected_called_transaction_data = {
                        "transaction_type": "transfer",
                        "amount": 12000,
                        "transfer": str(mocked_cust_uuid),
                        "fee": 0,
                    }
                    # fake the return to the PG server.
                    mock_response = create_mock_response_fixture(
                        transaction_data=expected_called_transaction_data,
                        uuid_param_str=str(uuid.uuid4()),
                        metadata={
                            "source_type": "TreatmentProcedure",
                            "source_id": str(bill.procedure_id),
                        },
                    )
                    mock_make_request.return_value = mock_response
                    res = from_employer_bill_create_clinic_bill_and_process(
                        emp_bill_id=bill.id
                    )
                    assert res == 0
                    bills = billing_service.get_bills_by_procedure_ids(
                        [bill.procedure_id]
                    )
                    bills = sorted(bills, key=lambda x: x.id)

                    assert len(bills) == 3 + len(pre_existing_clinic_bill_statuses)
                    employer_bill = None
                    clinic_bill = None
                    for bill in bills:
                        if bill.payor_type == PayorType.EMPLOYER:
                            employer_bill = bill
                        elif (
                            bill.payor_type == PayorType.CLINIC
                            and bill.status != BillStatus.CANCELLED
                        ):
                            clinic_bill = bill
                    assert employer_bill.payor_type == PayorType.EMPLOYER
                    assert clinic_bill.payor_type == PayorType.CLINIC

                    assert clinic_bill.procedure_id == employer_bill.procedure_id
                    assert (
                        clinic_bill.cost_breakdown_id == employer_bill.cost_breakdown_id
                    )
                    assert clinic_bill.label == employer_bill.label

                    assert clinic_bill.amount == mocked_tp_dict["cost"]
                    assert clinic_bill.payor_id == mocked_tp_dict["fertility_clinic_id"]

                    assert clinic_bill.payment_method == PaymentMethod.PAYMENT_GATEWAY
                    assert clinic_bill.payment_method_label is None
                    assert clinic_bill.last_calculated_fee == 0
                    set_new_bill_to_processing.assert_called_once()

    @pytest.mark.parametrize(
        argnames="input_employer_bill_status, input_employer_bill_payor_type, existing_clinic_bill_status, "
        "treatment_proc_data, exp_clinic_bill_amt",
        argvalues=(
            pytest.param(
                BillStatus.NEW,
                PayorType.EMPLOYER,
                None,
                {"cost": 1000, "fertility_clinic_id": 1},
                1000,
                id="1. New Employer Bill, no pre-existing clinic bill. clinic bill expected",
            ),
            pytest.param(
                BillStatus.FAILED,
                PayorType.EMPLOYER,
                None,
                {"cost": 2000, "fertility_clinic_id": 2},
                2000,
                id="2. FAILED Employer Bill, no pre-existing clinic bill. clinic bill expected",
            ),
            pytest.param(
                BillStatus.PAID,
                PayorType.EMPLOYER,
                None,
                {"cost": 3000, "fertility_clinic_id": 3},
                3000,
                id="3. PAID Employer Bill, no pre-existing clinic bill. clinic bill expected",
            ),
            pytest.param(
                BillStatus.PROCESSING,
                PayorType.EMPLOYER,
                None,
                {"cost": 4000, "fertility_clinic_id": 3},
                4000,
                id="4. PROCESSING Employer Bill, no pre-existing clinic bill. clinic bill expected",
            ),
            pytest.param(
                BillStatus.NEW,
                PayorType.EMPLOYER,
                BillStatus.FAILED,
                {"cost": 1000, "fertility_clinic_id": 1},
                None,
                id="5. New Employer Bill, pre-existing clinic bill. no clinic bill expected",
            ),
            pytest.param(
                BillStatus.FAILED,
                PayorType.EMPLOYER,
                BillStatus.NEW,
                {"cost": 2000, "fertility_clinic_id": 2},
                None,
                id="6. FAILED Employer Bill, pre-existing clinic bill. no clinic bill expected",
            ),
            pytest.param(
                BillStatus.PAID,
                PayorType.EMPLOYER,
                BillStatus.PROCESSING,
                {"cost": 3000, "fertility_clinic_id": 3},
                None,
                id="7. PAID Employer Bill, pre-existing clinic bill. no clinic bill expected",
            ),
            pytest.param(
                BillStatus.PROCESSING,
                PayorType.EMPLOYER,
                BillStatus.PAID,
                {"cost": 3000, "fertility_clinic_id": 3},
                None,
                id="8. Processing Employer Bill, pre-existing clinic bill. no clinic bill expected",
            ),
            pytest.param(
                BillStatus.CANCELLED,
                PayorType.EMPLOYER,
                None,
                {"cost": 3000, "fertility_clinic_id": 3},
                None,
                id="9. CANCELLED Employer Bill, no pre-existing clinic bill. no clinic bill expected",
            ),
            pytest.param(
                BillStatus.NEW,
                PayorType.MEMBER,
                None,
                {"cost": 3000, "fertility_clinic_id": 3},
                None,
                id="10. NEW Member Bill, no pre-existing clinic bill. no clinic bill expected",
            ),
            pytest.param(
                None,
                None,
                None,
                {"cost": 3000, "fertility_clinic_id": 3},
                None,
                id="10. No Input bill, no pre-existing clinic bill. no clinic bill expected",
            ),
        ),
    )
    def test_from_employer_bill_create_clinic_bill_with_billing_service(
        self,
        billing_service,
        input_employer_bill_status,
        input_employer_bill_payor_type,
        existing_clinic_bill_status,
        treatment_proc_data,
        exp_clinic_bill_amt,
    ):

        bill = (
            billing_service.bill_repo.create(
                instance=(
                    factories.BillFactory.build(
                        payor_type=input_employer_bill_payor_type,
                        status=input_employer_bill_status,
                    )
                )
            )
            if input_employer_bill_status
            else None
        )
        if existing_clinic_bill_status:
            _ = billing_service.bill_repo.create(
                instance=(
                    factories.BillFactory.build(
                        payor_type=PayorType.CLINIC,
                        status=existing_clinic_bill_status,
                        procedure_id=bill.procedure_id,
                    )
                )
            )
        with patch(
            "direct_payment.billing.billing_service.get_treatment_procedure_as_dict_from_id",
            return_value=treatment_proc_data,
        ), patch("direct_payment.billing.billing_service.payments_customer_id",), patch(
            "direct_payment.billing.lib.bill_creation_helpers.get_treatment_procedure_as_dict_from_id",
            return_value=treatment_proc_data,
        ):
            res = from_employer_bill_create_clinic_bill_with_billing_service(
                input_employer_bill=bill, billing_service=billing_service
            )
        if exp_clinic_bill_amt is None:
            assert res is None
        else:
            assert res.amount == exp_clinic_bill_amt


class TestCreateFullRefundBillsForPayor:
    def test_single_bill(self, billing_service, member, employer, clinic):
        tp_id = TreatmentProcedureFactory.create(
            status=TreatmentProcedureStatus.COMPLETED
        ).id
        bills = factories.BillFactory.create_batch(
            size=3,
            procedure_id=tp_id,
            payor_type=factory.Iterator(
                [PayorType.MEMBER, PayorType.EMPLOYER, PayorType.CLINIC]
            ),
            amount=factory.Iterator([10000, 10000, 10000]),
            status=BillStatus.PAID,
            payor_id=factory.Iterator([member.id, employer.id, clinic.id]),
        )
        for bill in bills:
            billing_service.bill_repo.create(instance=bill)
        for payor_type in list(PayorType):
            bills = billing_service.create_full_refund_bills_for_payor(
                procedure_id=tp_id, payor_type=payor_type
            )
            assert len(bills) == 1
            assert bills[0].amount == -10000

    def test_multiple_bills(self, billing_service, member):
        tp_id = TreatmentProcedureFactory.create(
            status=TreatmentProcedureStatus.COMPLETED
        ).id
        bills = factories.BillFactory.create_batch(
            size=2,
            procedure_id=tp_id,
            payor_type=factory.Iterator([PayorType.MEMBER, PayorType.MEMBER]),
            amount=factory.Iterator([10000, 10000]),
            status=BillStatus.PAID,
            payor_id=factory.Iterator([member.id, member.id]),
        )
        for bill in bills:
            billing_service.bill_repo.create(instance=bill)
        bills = billing_service.create_full_refund_bills_for_payor(
            procedure_id=tp_id, payor_type=PayorType.MEMBER
        )
        assert len(bills) == 2
        assert bills[0].amount == -10000
        assert bills[1].amount == -10000

    def test_partially_refunded_bills(self, billing_service, member):
        tp_id = TreatmentProcedureFactory.create(
            status=TreatmentProcedureStatus.COMPLETED
        ).id
        bills = factories.BillFactory.create_batch(
            size=2,
            procedure_id=tp_id,
            payor_type=factory.Iterator([PayorType.MEMBER, PayorType.MEMBER]),
            amount=factory.Iterator([10000, -5000]),
            status=BillStatus.PAID,
            payor_id=factory.Iterator([member.id, member.id]),
        )
        bills_with_id = []
        for bill in bills:
            bills_with_id.append(billing_service.bill_repo.create(instance=bill))

        records = factories.BillProcessingRecordFactory.create_batch(
            size=2,
            bill_id=factory.Iterator([bills_with_id[0].id, bills_with_id[1].id]),
            bill_status=factory.Iterator(
                [BillStatus.PAID.value, BillStatus.REFUNDED.value]
            ),
            body=factory.Iterator([{}, {"refund_bill": bills_with_id[0].id}]),
            processing_record_type="payment_gateway_request",
        )
        for record in records:
            billing_service.bill_processing_record_repo.create(instance=record)
        bills = billing_service.create_full_refund_bills_for_payor(
            procedure_id=tp_id, payor_type=PayorType.MEMBER
        )
        assert len(bills) == 1
        assert bills[0].amount == -5000
