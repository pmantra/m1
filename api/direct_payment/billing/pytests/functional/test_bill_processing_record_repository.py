import uuid
from datetime import datetime, timedelta

import pytest

from direct_payment.billing.models import BillStatus
from direct_payment.billing.pytests import factories
from direct_payment.billing.pytests.factories import BillFactory


@pytest.fixture
def bill(bill_repository):
    bill = factories.BillFactory.build(status=BillStatus.PROCESSING)
    return bill_repository.create(instance=bill)


@pytest.fixture
def raw_record(bill_processing_record_repository, bill):
    return factories.BillProcessingRecordFactory.build(
        processing_record_type="payment_gateway_request",
        bill_id=bill.id,
        bill_status=bill.status.value,
        body={
            "transaction_data": {
                "transaction_type": "charge",
                "customer_id": "a9a85fd4-5717-4562-b3fc-2c963f65afa6",
                "amount": 50000,
            },
            "metadata": {
                "payments_id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
                "source": "TreatmentProcedure",
                "source_id": "1243564576876",
            },
        },
    )


@pytest.fixture
def new_record(bill_processing_record_repository, raw_record):
    created = bill_processing_record_repository.create(instance=raw_record)
    return created


@pytest.fixture
def bill_processing_record_statuses():
    return [
        [BillStatus.PROCESSING, BillStatus.PAID],
        [BillStatus.PROCESSING],
        [BillStatus.NEW, BillStatus.PROCESSING, BillStatus.PAID],
        [BillStatus.NEW, BillStatus.PROCESSING, BillStatus.PAID, BillStatus.REFUNDED],
    ]


class TestBillProcessingRecordRepositoryBase:
    def test_create_bill_processing_record(
        self, bill_processing_record_repository, raw_record
    ):
        created = bill_processing_record_repository.create(instance=raw_record)
        assert created.id
        assert created.body == raw_record.body
        assert created.bill_id is not None
        assert created.bill_status == BillStatus.PROCESSING.value
        assert isinstance(created.transaction_id, uuid.UUID)
        assert created.created_at is not None

    def test_get_bill_processing_record(
        self, bill_processing_record_repository, new_record
    ):
        retrieved = bill_processing_record_repository.get(id=new_record.id)
        assert retrieved
        assert retrieved.id
        assert retrieved.body == new_record.body
        assert retrieved.bill_id is not None
        assert retrieved.bill_status == BillStatus.PROCESSING.value
        assert isinstance(retrieved.transaction_id, uuid.UUID)
        assert retrieved.created_at is not None

    def test_get_no_bill(self, bill_processing_record_repository):
        retrieved = bill_processing_record_repository.get(id=-1)
        assert retrieved is None


class TestBillProcessingRecordRepositoryCustomQueries:
    def test_get_bill_processing_attempt_count_none(
        self, bill_processing_record_repository, bill
    ):
        count = bill_processing_record_repository.get_bill_processing_attempt_count(
            bill
        )
        assert count == 0

    def test_get_bill_processing_attempt_count(
        self, bill_processing_record_repository, bill
    ):
        records = [
            # bills which count
            *factories.BillProcessingRecordFactory.build_batch(
                size=2,
                processing_record_type="payment_gateway_request",
                bill_id=bill.id,
            ),
            # bills which do not count
            factories.BillProcessingRecordFactory.build(
                processing_record_type="payment_gateway_response", bill_id=bill.id
            ),
            factories.BillProcessingRecordFactory.build(
                processing_record_type="payment_gateway_event", bill_id=bill.id
            ),
        ]
        for record in records:
            bill_processing_record_repository.create(instance=record)
        count = bill_processing_record_repository.get_bill_processing_attempt_count(
            bill
        )
        assert count == 2

    @pytest.mark.parametrize(
        ids=[
            "Filter includes one record",
            "Filter includes all records",
            "No filters",
            "No match",
        ],
        argnames="bills_to_include",
        argvalues=(
            ([0]),
            ([0, 1, 2]),
            ([]),
            ([4]),
        ),
    )
    def test_get_bill_processing_records(
        self,
        bill_repository,
        bill_processing_record_repository,
        bill_processing_record_statuses,
        bills_to_include,
    ):
        expected = {}
        inp_bill_ids = []
        bill_to_record_dict = self._generate_bill_to_record_dict(
            bill_repository,
            bill_processing_record_repository,
            bill_processing_record_statuses,
        )
        created_bills = [v["bill"] for v in bill_to_record_dict.values()]
        for index, bill in enumerate(created_bills):
            if not bills_to_include or index in bills_to_include:
                inp_bill_ids.append(bill.id)
                records = bill_to_record_dict[bill.id]["records"]
                for record in records:
                    expected[record.id] = record
        results = bill_processing_record_repository.get_bill_processing_records(
            inp_bill_ids
        )
        assert len(expected) == len(results)
        for res in results:
            exp = expected[res.id]
            assert exp.bill_id == exp.bill_id
            assert exp.processing_record_type == res.processing_record_type
            assert exp.bill_status == res.bill_status

    @pytest.mark.parametrize(
        ids=[
            "Last record in Paid state",
            "Multiple records in Paid state - Latest record picked from last bill",
            "No bills- nothing returned",
            "Last record in Refunding state - nothing returned",
            "Paid record - 2nd newest bill returned",
        ],
        argnames="bills_to_include, expected_last_rec_bill_index",
        argvalues=(
            ([0], 0),
            ([0, 1, 2], 2),
            ([], None),
            ([3], None),
            ([0, 2, 3], 2),
        ),
    )
    def test_get_latest_bill_processing_record_if_paid(
        self,
        bill_repository,
        bill_processing_record_repository,
        bill_processing_record_statuses,
        bills_to_include,
        expected_last_rec_bill_index,
    ):
        expected = None
        inp_bill_ids = []
        bill_to_record_dict = self._generate_bill_to_record_dict(
            bill_repository,
            bill_processing_record_repository,
            bill_processing_record_statuses,
        )
        created_bills = [v["bill"] for v in bill_to_record_dict.values()]
        for index, bill in enumerate(created_bills):
            if index in bills_to_include:
                inp_bill_ids.append(bill.id)
                if expected_last_rec_bill_index == index:
                    expected = bill_to_record_dict[bill.id]["records"][-1]
        res = (
            bill_processing_record_repository.get_latest_bill_processing_record_if_paid(
                inp_bill_ids
            )
        )
        assert expected == res

    @pytest.mark.parametrize(
        ids=[
            "One Bill. One input state.",
            "Two Bills, One input state",
            "Two Bills, Two input states",
        ],
        argnames="bill_processing_record_status_list, input_statuses, expected_last_rec_bill_index",
        argvalues=(
            (
                [
                    [BillStatus.NEW, BillStatus.PROCESSING, BillStatus.FAILED]
                ],  # records for Bill index 0
                [BillStatus.FAILED],
                0,
            ),
            (
                [
                    [BillStatus.NEW, BillStatus.FAILED],  # records for Bill index 1
                    [BillStatus.NEW],  # records for Bill index 1
                ],
                [BillStatus.NEW],
                1,
            ),
            (
                [
                    [BillStatus.NEW, BillStatus.PROCESSING],  # records for Bill index 0
                    [BillStatus.NEW, BillStatus.FAILED],  # records for Bill index 1
                ],
                [BillStatus.NEW, BillStatus.PROCESSING],
                0,
            ),
        ),
    )
    def test_get_latest_row_with_specified_statuses(
        self,
        bill_repository,
        bill_processing_record_repository,
        bill_processing_record_status_list,
        input_statuses,
        expected_last_rec_bill_index,
    ):

        bill_to_record_dict = self._generate_bill_to_record_dict(
            bill_repository,
            bill_processing_record_repository,
            bill_processing_record_status_list,
        )
        inp_bill_ids = list(bill_to_record_dict.keys())
        bill_id = inp_bill_ids[
            expected_last_rec_bill_index
        ]  # this is the bill whose last record we expect to return
        expected = bill_to_record_dict[bill_id]["records"][-1]

        res = bill_processing_record_repository.get_latest_row_with_specified_statuses(
            inp_bill_ids, input_statuses
        )

        assert expected == res

    @pytest.mark.parametrize(
        ids=[
            "1. 2 bills have head bprs that match the status filters",
            "2. 2 bills have head bprs that match the status filters",
            "3. 3 bills have head bprs that match the status filters",
            "4. No status filters match - everything gets filtered out",
        ],
        argnames="input_statuses, expected_bill_indices",
        argvalues=(
            ([BillStatus.FAILED, BillStatus.PROCESSING], [1, 2]),
            ([BillStatus.FAILED, BillStatus.PAID], [2, 3]),
            (
                [
                    BillStatus.NEW,
                    BillStatus.PROCESSING,
                    BillStatus.FAILED,
                    BillStatus.PAID,
                ],
                [1, 2, 3],
            ),
            ([], []),
        ),
    )
    def test_get_latest_records_with_specified_statuses_for_bill_ids(
        self,
        bill_repository,
        bill_processing_record_repository,
        input_statuses,
        expected_bill_indices,
    ):
        bill_processing_record_status_list = [
            [],  # no records for Bill 0 - NEW Bill
            [BillStatus.PROCESSING],  # records for Bill 1 - PROCESSING Bill
            [  # records for Bill 2 - FAILED Bill
                BillStatus.PROCESSING,
                BillStatus.FAILED,
            ],
            [  # records for Bill 3 - PAID Bill
                BillStatus.PROCESSING,
                BillStatus.PAID,
            ],
        ]

        bill_to_record_dict = self._generate_bill_to_record_dict(
            bill_repository,
            bill_processing_record_repository,
            bill_processing_record_status_list,
        )
        inp_bill_ids = list(bill_to_record_dict.keys())
        exp = {}
        for bill_index in expected_bill_indices:
            inp_bill_id = inp_bill_ids[bill_index]
            bpr = bill_to_record_dict[inp_bill_id]["records"][
                -1
            ]  # returning the head record
            exp[inp_bill_id] = bpr

        res = bill_processing_record_repository.get_latest_records_with_specified_statuses_for_bill_ids(
            inp_bill_ids, input_statuses
        )
        assert exp == res

    @pytest.mark.parametrize(
        ids=[
            "1. 1 bills has head paid/refunded bprs with transaction ids",
            "2. 2 bills have head paid/refunded bprs with transaction ids",
        ],
        argnames="bill_status_to_ids, expected_bills_ids",
        argvalues=(
            (
                {BillStatus.REFUNDED: (0, [False]), BillStatus.PAID: (2, [True, True])},
                [2],
            ),
            (
                {
                    BillStatus.REFUNDED: (3, [True, True]),
                    BillStatus.PAID: (4, [True, True]),
                },
                [3, 4],
            ),
        ),
    )
    def test_filter_bills_for_money_movement(
        self,
        bill_repository,
        bill_processing_record_repository,
        bill_status_to_ids,
        expected_bills_ids,
    ):
        bill_ids = []
        for status, ids in bill_status_to_ids.items():
            bill_ids.append(ids[0])
            bill = bill_repository.create(
                instance=BillFactory.build(status=status.value, id=ids[0])
            )
            created_at = datetime.now().replace(microsecond=0)
            for r_count, transaction_id in enumerate(ids[1]):
                created_at = created_at + timedelta(seconds=10)
                record = factories.BillProcessingRecordFactory.build(
                    bill_id=bill.id,
                    processing_record_type=f"test_{bill.id}_{r_count}",
                    bill_status=status.value,
                    created_at=created_at,
                    transaction_id=uuid.uuid4() if transaction_id else None,
                )
                bill_processing_record_repository.create(instance=record)
        results = bill_processing_record_repository.filter_bill_ids_for_money_movement(
            bill_ids=bill_ids
        )
        for result in results:
            assert result in expected_bills_ids

    @pytest.mark.parametrize(
        ids=[
            "One Bill. One input state.",
            "Two Bills, One input state",
            "Two Bills, Two input states",
        ],
        argnames="bill_processing_record_status_list, input_statuses",
        argvalues=(
            (
                [
                    [BillStatus.NEW, BillStatus.PROCESSING, BillStatus.FAILED]
                ],  # records for Bill index 0
                [BillStatus.CANCELLED],
            ),
            (
                [
                    [BillStatus.NEW, BillStatus.FAILED],  # records for Bill index 1
                    [BillStatus.NEW],  # records for Bill index 1
                ],
                [BillStatus.PROCESSING],
            ),
            (
                [
                    [BillStatus.NEW, BillStatus.PROCESSING],  # records for Bill index 0
                    [BillStatus.NEW, BillStatus.FAILED],  # records for Bill index 1
                ],
                [BillStatus.REFUNDED, BillStatus.CANCELLED],
            ),
        ),
    )
    def test_get_latest_row_with_specified_statuses_none_expected(
        self,
        bill_repository,
        bill_processing_record_repository,
        bill_processing_record_status_list,
        input_statuses,
    ):

        bill_to_record_dict = self._generate_bill_to_record_dict(
            bill_repository,
            bill_processing_record_repository,
            bill_processing_record_status_list,
        )
        inp_bill_ids = list(bill_to_record_dict.keys())

        res = bill_processing_record_repository.get_latest_row_with_specified_statuses(
            inp_bill_ids, input_statuses
        )

        assert res is None

    @staticmethod
    def _generate_bill_to_record_dict(
        bill_repository,
        bill_processing_record_repository,
        bill_processing_record_statuses,
    ) -> dict:
        to_return = {}
        for record_statuses in bill_processing_record_statuses:
            bill_status = record_statuses[-1] if record_statuses else BillStatus.NEW
            bill = BillFactory.build(status=bill_status)
            bill = bill_repository.create(instance=bill)
            to_return[bill.id] = {"bill": bill, "records": []}
            created_at = datetime.now().replace(microsecond=0)
            for r_count, status in enumerate(record_statuses):
                created_at = created_at + timedelta(seconds=10)
                record = factories.BillProcessingRecordFactory.build(
                    bill_id=bill.id,
                    processing_record_type=f"test_{bill.id}_{r_count}",
                    bill_status=status.value,
                    created_at=created_at,
                )
                record = bill_processing_record_repository.create(instance=record)
                to_return[bill.id]["records"].append(record)
        return to_return

    @pytest.mark.parametrize(
        ids=[
            "One bill, with one bill processing record, expect one bill returned",
            "One bill, with two bill processing record, expect one bill returned",
            "Two bills, with one bill processing record each, expect two bills returned",
            "Two bills, with two bill processing records each, expect two bills returned",
        ],
        argnames="bill_count, rows_per_bill_count, exp_bill_count",
        argvalues=((1, 1, 1), (1, 2, 1), (2, 1, 2), (2, 2, 2)),
    )
    def test_get_bill_ids_from_transaction_id(
        self,
        bill_repository,
        bill_processing_record_repository,
        bill_count,
        rows_per_bill_count,
        exp_bill_count,
    ):
        transaction_id = uuid.uuid4()
        exp = set()
        for _ in range(0, bill_count):
            # create the bill
            bill = BillFactory.build()
            bill = bill_repository.create(instance=bill)
            exp.add(bill.id)
            # create the records for the bill
            for r in range(0, rows_per_bill_count):
                record = factories.BillProcessingRecordFactory.build(
                    bill_id=bill.id,
                    processing_record_type=f"test_{bill.id}_{r}",
                    bill_status=bill.status.value,
                    transaction_id=transaction_id,
                )
                bill_processing_record_repository.create(instance=record)

        res = bill_processing_record_repository.get_bill_ids_from_transaction_id(
            transaction_id
        )
        assert len(res) == exp_bill_count
        assert set(res) == exp

    @pytest.mark.parametrize(
        argnames="bill_processing_record_status_list, input_statuses,input_bills_idx, expected_res_indices",
        ids=[
            "One bill created, one input bill, one input status, two bprs match",
            "Two bills created, one input bill, one input status, one bpr match",
            "Two bills created, two input bills, one input status, two bprs match",
            "Two bills created, two input bills, two input statuses, four bprs match",
        ],
        argvalues=(
            (
                [
                    [
                        BillStatus.PROCESSING,
                        BillStatus.PROCESSING,
                        BillStatus.FAILED,
                    ]  # records for Bill index 0
                ],
                [BillStatus.PROCESSING],  # Input search status(es)
                [0],  # input bill(s)
                {0: [0, 1]},  # expected bill index to bill processing record indices
            ),
            (
                [
                    [
                        BillStatus.PROCESSING,
                        BillStatus.FAILED,
                    ],  # records for Bill index 0
                    [BillStatus.PROCESSING],  # records for Bill index 1
                ],
                [BillStatus.PROCESSING],  # Input search status(es)
                [1],  # input bill(s)
                {1: [0]},  # expected bill index to bill processing record indices
            ),
            (
                [
                    [
                        BillStatus.PROCESSING,
                        BillStatus.FAILED,
                    ],  # records for Bill index 1
                    [BillStatus.FAILED],  # records for Bill index 1
                ],
                [BillStatus.FAILED],  # Input search status(es)
                [0, 1],  # input bill(s)
                {
                    0: [1],
                    1: [0],
                },  # expected bill index to bill processing record indices
            ),
            (
                [
                    [
                        BillStatus.PROCESSING,
                        BillStatus.FAILED,
                    ],  # records for Bill index 1
                    [
                        BillStatus.PROCESSING,
                        BillStatus.FAILED,
                        BillStatus.PROCESSING,
                        BillStatus.PAID,
                    ],  # records for Bill index 1
                ],
                [BillStatus.PROCESSING, BillStatus.PAID],  # Input search status(es)
                [0, 1],  # input bill(s)
                {
                    0: [0],
                    1: [0, 2, 3],
                },  # expected bill index to bill processing record indices
            ),
        ),
    )
    def test_get_all_records_with_specified_statuses_for_bill_ids(
        self,
        bill_repository,
        bill_processing_record_repository,
        bill_processing_record_status_list,
        input_statuses,
        input_bills_idx,
        expected_res_indices,
    ):

        bill_to_record_dict = self._generate_bill_to_record_dict(
            bill_repository,
            bill_processing_record_repository,
            bill_processing_record_status_list,
        )
        all_bill_ids = list(bill_to_record_dict.keys())
        bill_ids = [k for (i, k) in enumerate(all_bill_ids) if i in input_bills_idx]

        exp = {}
        for k, indices in expected_res_indices.items():
            key = all_bill_ids[k]
            exp[key] = []
            for i in indices:
                exp[key].append(bill_to_record_dict[key]["records"][i])

        res = bill_processing_record_repository.get_all_records_with_specified_statuses_for_bill_ids(
            bill_ids, input_statuses
        )

        for k, v in res.items():
            assert k in exp
            assert v == exp[k]
