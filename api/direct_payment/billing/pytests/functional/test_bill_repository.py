import uuid
from datetime import date, datetime

import factory
import pytest

from direct_payment.billing.models import (
    BillErrorTypes,
    BillStatus,
    PaymentMethod,
    PayorType,
)
from direct_payment.billing.pytests import factories


@pytest.fixture
def new_bill(bill_repository):
    bill = factories.BillFactory.build()
    return bill_repository.create(instance=bill)


@pytest.fixture
def procedure_id():
    return 1


@pytest.fixture
def procedure_ids():
    return [1, 2]


@pytest.fixture
def several_bills(bill_repository, procedure_id, member_payor_id):
    created_bills = [
        factories.BillFactory.build(
            procedure_id=procedure_id,
            payor_type=PayorType.MEMBER,
            payor_id=member_payor_id,
            status=BillStatus.PAID,
        ),
        factories.BillFactory.build(
            procedure_id=procedure_id,
            payor_type=PayorType.MEMBER,
            payor_id=member_payor_id,
            status=BillStatus.CANCELLED,
        ),
        factories.BillFactory.build(
            procedure_id=procedure_id,
            payor_type=PayorType.EMPLOYER,
            payor_id=2,
            status=BillStatus.PAID,
        ),
        factories.BillFactory.build(
            procedure_id=procedure_id,
            payor_type=PayorType.CLINIC,
            payor_id=1,
            status=BillStatus.PAID,
        ),
        factories.BillFactory.build(
            procedure_id=2,
            payor_type=PayorType.MEMBER,
            payor_id=member_payor_id,
            status=BillStatus.PAID,
        ),
    ]
    res = []
    for bill in created_bills:
        res.append(bill_repository.create(instance=bill))
    return res


@pytest.fixture
def bills_created_at_specific_times(bill_repository):
    dt_fmt = "%d/%m/%Y %H:%M"
    created_bills = [
        factories.BillFactory.build(
            payor_type=PayorType.MEMBER,
            status=BillStatus.PAID,
            created_at=datetime.strptime("12/11/2018 00:00", dt_fmt),
        ),
        factories.BillFactory.build(
            payor_type=PayorType.MEMBER,
            status=BillStatus.NEW,
            created_at=datetime.strptime("13/11/2018 15:30", dt_fmt),
        ),
        factories.BillFactory.build(
            payor_type=PayorType.CLINIC,
            status=BillStatus.FAILED,
            created_at=datetime.strptime("15/11/2018 15:30", dt_fmt),
        ),
        factories.BillFactory.build(
            payor_type=PayorType.CLINIC,
            status=BillStatus.REFUNDED,
            created_at=datetime.strptime("19/11/2018 15:30", dt_fmt),
        ),
    ]
    to_return = [bill_repository.create(instance=bill) for bill in created_bills]
    return to_return


class TestBillRepositoryBase:
    def test_create_bill(self, bill_repository):
        bill = factories.BillFactory.build()
        created = bill_repository.create(instance=bill)
        assert created.id

    def test_get_bill(self, bill_repository, new_bill):
        retrieved = bill_repository.get(id=new_bill.id)
        assert retrieved
        assert retrieved.amount is not None
        assert retrieved.label is not None
        assert retrieved.payor_type == PayorType.MEMBER
        assert retrieved.payor_id is not None
        assert retrieved.procedure_id is not None
        assert retrieved.payment_method == PaymentMethod.PAYMENT_GATEWAY
        assert retrieved.status == BillStatus.NEW

    def test_get_no_bill(self, bill_repository):
        retrieved = bill_repository.get(id=-1)
        assert retrieved is None


class TestBillRepositoryByProcedure:
    def test_get_bills_by_multiple_procedures(
        self, bill_repository, several_bills, procedure_ids
    ):
        all_bills = bill_repository.get_by_procedure(procedure_ids=procedure_ids)
        assert len(all_bills) == 5

    def test_get_bills_by_procedure(self, bill_repository, several_bills, procedure_id):
        all_procedure_bills = bill_repository.get_by_procedure(
            procedure_ids=[procedure_id]
        )
        assert len(all_procedure_bills) == 4

    def test_get_estimates_by_procedure(
        self, bill_repository, several_bills_two_estimates
    ):
        procedure_ids = [
            b.procedure_id for b in several_bills_two_estimates if b.is_ephemeral
        ]
        all_procedure_estimates = bill_repository.get_by_procedure(
            procedure_ids=procedure_ids,
            is_ephemeral=True,
        )
        assert len(all_procedure_estimates) == len(procedure_ids)

    def test_get_bills_by_procedure_and_status(
        self, bill_repository, several_bills, procedure_id
    ):
        paid_bills = bill_repository.get_by_procedure(
            procedure_ids=[procedure_id], status=[BillStatus.PAID]
        )
        assert len(paid_bills) == 3

    def test_get_bills_by_procedure_status_and_exclude_clinic(
        self, bill_repository, several_bills, procedure_id
    ):
        no_clinic_bills = bill_repository.get_by_procedure(
            procedure_ids=[procedure_id],
            status=[BillStatus.PAID],
            exclude_payor_types=[PayorType.CLINIC],
        )
        assert len(no_clinic_bills) == 2

    def test_get_bills_by_procedure_and_specific_payor(
        self, bill_repository, several_bills, procedure_id, member_payor_id
    ):
        member_bills = bill_repository.get_by_procedure(
            procedure_ids=[procedure_id],
            payor_type=PayorType.MEMBER,
            payor_id=member_payor_id,
        )
        assert len(member_bills) == 2

    def test_get_bills_by_procedure_status_and_specific_payor(
        self, bill_repository, several_bills, procedure_id, member_payor_id
    ):
        paid_member_bills = bill_repository.get_by_procedure(
            procedure_ids=[procedure_id],
            payor_type=PayorType.MEMBER,
            payor_id=member_payor_id,
            status=[BillStatus.PAID],
        )
        assert len(paid_member_bills) == 1

    def test_get_bills_by_no_procedure(self, bill_repository, new_bill):
        all_procedure_bills = bill_repository.get_by_procedure(procedure_ids=[-1])
        assert all_procedure_bills == []


class TestBillRepositoryByPayor:
    def test_get_bills_by_payor(self, bill_repository, several_bills, member_payor_id):
        all_payor_bills = bill_repository.get_by_payor(
            payor_type=PayorType.MEMBER, payor_id=member_payor_id
        )
        assert len(all_payor_bills) == 3

    def test_get_bills_by_payor_and_status(
        self, bill_repository, several_bills, member_payor_id
    ):
        paid_payor_bills = bill_repository.get_by_payor(
            payor_type=PayorType.MEMBER,
            payor_id=member_payor_id,
            status=[BillStatus.PAID],
        )
        assert len(paid_payor_bills) == 2

    def test_get_bills_by_no_payor(self, bill_repository):
        all_payor_bills = bill_repository.get_by_payor(
            payor_type=PayorType.CLINIC, payor_id=-1
        )
        assert all_payor_bills == []

    def test_get_estimates_by_payor(
        self, bill_repository, several_bills_two_estimates, member_payor_id
    ):
        all_payor_estimates = bill_repository.get_estimates_by_payor(
            payor_type=PayorType.MEMBER, payor_id=member_payor_id
        )
        assert len(all_payor_estimates) == 2
        assert all_payor_estimates[0].procedure_id == 5
        assert all_payor_estimates[1].procedure_id == 4

    def test_get_member_estimates_by_procedure(
        self, bill_repository, several_bills_two_estimates
    ):
        assert (
            len(
                bill_repository.get_member_estimates_by_procedures(procedure_ids=[4, 5])
            )
            == 2
        )

    def test_get_procedure_ids_with_ephemeral_bills(
        self, bill_repository, several_bills_two_estimates
    ):
        res = bill_repository.get_procedure_ids_with_ephemeral_bills(
            procedure_ids=[4, 5, 6, 7, 8, 9]
        )
        assert [4, 5, 7] == sorted(res)

    def test_get_procedure_ids_with_non_ephemeral_bills(
        self, bill_repository, several_bills_two_estimates
    ):
        res = bill_repository.get_procedure_ids_with_non_ephemeral_bills(
            procedure_ids=[4, 5, 6, 7, 8, 9]
        )
        assert [6, 8, 9] == sorted(res)

    def test_get_procedure_ids_with_ephemeral_bills_no_procedures(
        self,
        bill_repository,
    ):
        assert (
            bill_repository.get_procedure_ids_with_ephemeral_bills(procedure_ids=[])
            == []
        )

    def test_get_procedure_ids_with_non_ephemeral_bills_no_procedures(
        self,
        bill_repository,
    ):
        assert (
            bill_repository.get_procedure_ids_with_non_ephemeral_bills(procedure_ids=[])
            == []
        )

    @pytest.mark.parametrize(
        argnames=" payor_types, statuses,  start_date, end_date, expected_bill_indices",
        argvalues=(
            (
                [PayorType.MEMBER],
                [BillStatus.PAID],
                date(2018, 11, 11),
                date(2018, 11, 15),
                [0],
            ),
            (
                [PayorType.MEMBER],
                [BillStatus.PAID, BillStatus.NEW],
                date(2018, 11, 11),
                date(2018, 11, 15),
                [0, 1],
            ),
            (
                [PayorType.MEMBER, PayorType.CLINIC],
                [BillStatus.FAILED, BillStatus.NEW],
                date(2018, 11, 11),
                date(2018, 11, 15),
                [1, 2],
            ),
            (
                [PayorType.MEMBER, PayorType.CLINIC],
                [BillStatus.FAILED, BillStatus.NEW],
                date(2019, 11, 11),
                date(2019, 11, 15),
                [],
            ),
            (
                [PayorType.EMPLOYER, PayorType.CLINIC],
                [BillStatus.CANCELLED, BillStatus.PROCESSING],
                date(2018, 11, 11),
                date(2018, 11, 15),
                [],
            ),
            (
                [PayorType.MEMBER, PayorType.CLINIC],
                [BillStatus.PAID],
                None,
                None,
                [0],
            ),
            (
                [PayorType.MEMBER],
                [BillStatus.PAID, BillStatus.NEW],
                date(2018, 11, 13),
                None,
                [1],
            ),
            (
                [PayorType.MEMBER],
                [BillStatus.PAID, BillStatus.NEW],
                None,
                date(2018, 11, 12),
                [0],
            ),
            (
                None,
                [BillStatus.NEW, BillStatus.FAILED],
                date(2018, 11, 11),
                date(2018, 11, 15),
                [1, 2],
            ),
            (
                [PayorType.MEMBER, PayorType.CLINIC],
                None,
                date(2018, 11, 11),
                date(2018, 11, 15),
                [0, 1, 2],
            ),
        ),
        ids=[
            "Single Payor Type, Single status, single row in date range",
            "Single Payor Type, Multiple statuses, all rows in date range",
            "Multiple Payor Type, Multiple statuses, 3 of 4 rows in date range, 2 of 4 with acceptable bill status",
            "Multiple Payor Type, Multiple statuses, none in date range",
            "Multiple Payor Type, Multiple statuses, some in date range, none in result",
            "Multiple Payor Type, Multiple statuses, no date range, one in result",
            "Multiple Payor Type, Multiple statuses, start date only, one in result",
            "Multiple Payor Type, Multiple statuses, end date only, one in result",
            "No Payor Types, Multiple statuses, three in date range, two in result",
            "Multiple Payor Types, No statuses, three in date range, three in result",
        ],
    )
    def test_get_by_payor_types_statuses_date_range(
        self,
        bill_repository,
        bills_created_at_specific_times,
        payor_types,
        statuses,
        start_date,
        end_date,
        expected_bill_indices,
    ):
        results = bill_repository.get_by_payor_types_statuses_date_range(
            payor_types, statuses, start_date, end_date
        )
        assert len(results) == len(expected_bill_indices)
        expected_dict = {}
        for expected_bill_index in expected_bill_indices:
            input_bill = bills_created_at_specific_times[expected_bill_index]
            expected_dict[input_bill.id] = input_bill

        for result in results:
            assert result.id in expected_dict
            expected = expected_dict[result.id]
            assert result.payor_type == expected.payor_type
            assert result.status == expected.status
            assert result.created_at == expected.created_at

    def test_get_by_payor_type_statuses_date_all_nones(self, bill_repository):
        with pytest.raises(ValueError):
            bill_repository.get_by_payor_types_statuses_date_range(
                None, None, None, None
            )

    @pytest.mark.parametrize(
        argnames="payor_types, statuses,  start_date_time, end_date_time, expected_bill_indices",
        argvalues=(
            (
                [PayorType.MEMBER],
                [BillStatus.PAID],
                datetime.strptime("11/11/2018 15:30", "%d/%m/%Y %H:%M"),
                datetime.strptime("15/11/2018 15:30", "%d/%m/%Y %H:%M"),
                [0],
            ),
            (
                [PayorType.MEMBER],
                [BillStatus.PAID, BillStatus.NEW],
                datetime.strptime("11/11/2018 15:30", "%d/%m/%Y %H:%M"),
                datetime.strptime("15/11/2018 15:30", "%d/%m/%Y %H:%M"),
                [0, 1],
            ),
            (
                [PayorType.MEMBER, PayorType.CLINIC],
                [BillStatus.PAID, BillStatus.FAILED],
                datetime.strptime("11/11/2018 15:30", "%d/%m/%Y %H:%M"),
                datetime.strptime("15/11/2018 15:30", "%d/%m/%Y %H:%M"),
                [0, 2],
            ),
            (
                [PayorType.MEMBER, PayorType.CLINIC],
                [BillStatus.PAID, BillStatus.FAILED],
                datetime.strptime("11/11/2011 15:30", "%d/%m/%Y %H:%M"),
                datetime.strptime("15/11/2011 15:30", "%d/%m/%Y %H:%M"),
                [],
            ),
            (
                [PayorType.EMPLOYER, PayorType.CLINIC],
                [BillStatus.CANCELLED, BillStatus.PROCESSING],
                datetime.strptime("11/11/2018 15:30", "%d/%m/%Y %H:%M"),
                datetime.strptime("15/11/2018 15:30", "%d/%m/%Y %H:%M"),
                [],
            ),
            (
                [PayorType.MEMBER, PayorType.CLINIC],
                [BillStatus.PAID],
                None,
                None,
                [0],
            ),
            (
                [PayorType.MEMBER],
                [BillStatus.PAID, BillStatus.NEW],
                datetime.strptime("13/11/2018 15:30", "%d/%m/%Y %H:%M"),
                None,
                [1],
            ),
            (
                [PayorType.MEMBER],
                [BillStatus.PAID, BillStatus.NEW],
                None,
                datetime.strptime("12/11/2018 15:30", "%d/%m/%Y %H:%M"),
                [0],
            ),
            (
                None,
                [BillStatus.NEW, BillStatus.FAILED],
                datetime.strptime("11/11/2018 15:30", "%d/%m/%Y %H:%M"),
                datetime.strptime("15/11/2018 15:30", "%d/%m/%Y %H:%M"),
                [1, 2],
            ),
            (
                [PayorType.MEMBER, PayorType.CLINIC],
                None,
                datetime.strptime("11/11/2018 15:30", "%d/%m/%Y %H:%M"),
                datetime.strptime("15/11/2018 15:30", "%d/%m/%Y %H:%M"),
                [0, 1, 2],
            ),
        ),
        ids=[
            "Single Payor Type, Single status, single row in date range",
            "Single Payor Type, Multiple statuses, all rows in date range",
            "Multiple Payor Type, Multiple statuses, 2 of 4 rows in date range",
            "Multiple Payor Type, Multiple statuses, none in date range",
            "Multiple Payor Type, Multiple statuses, some in date range, none in result",
            "Multiple Payor Type, Multiple statuses, no date range, one in result",
            "Multiple Payor Type, Multiple statuses, end date only, one in result",
            "Multiple Payor Type, Multiple statuses, start date only, one in result",
            "No Payor Types, Multiple statuses, three in date range, two in result",
            "Multiple Payor Types, No statuses, three in date range, three in result",
        ],
    )
    def test_get_by_payor_type_statuses_date_time_range(
        self,
        bill_repository,
        bills_created_at_specific_times,
        payor_types,
        statuses,
        start_date_time,
        end_date_time,
        expected_bill_indices,
    ):
        results = bill_repository.get_by_payor_type_statuses_date_time_range(
            payor_types, statuses, start_date_time, end_date_time
        )
        assert len(results) == len(expected_bill_indices)
        expected_dict = {}
        for expected_bill_index in expected_bill_indices:
            input_bill = bills_created_at_specific_times[expected_bill_index]
            expected_dict[input_bill.id] = input_bill

        for result in results:
            assert result.id in expected_dict
            expected = expected_dict[result.id]
            assert result.payor_type == expected.payor_type
            assert result.status == expected.status
            assert result.created_at == expected.created_at

    def test_get_by_payor_type_statuses_date_time_range_all_nones(
        self, bill_repository
    ):
        with pytest.raises(ValueError):
            bill_repository.get_by_payor_type_statuses_date_time_range(
                None, None, None, None
            )

    def test_get_all_member_bills_with_active_refunds(
        self,
        bill_repository,
    ):
        created_bills = [
            factories.BillFactory.build(
                payor_id=1,
                payor_type=PayorType.MEMBER,
                status=BillStatus.NEW,
                amount=10,
            ),
            factories.BillFactory.build(
                payor_id=1,
                payor_type=PayorType.MEMBER,
                status=BillStatus.PAID,
                amount=-20,
            ),
            factories.BillFactory.build(
                payor_id=1,
                payor_type=PayorType.MEMBER,
                status=BillStatus.NEW,
                amount=-30,
            ),
            factories.BillFactory.build(
                payor_id=2,
                payor_type=PayorType.MEMBER,
                status=BillStatus.PROCESSING,
                amount=-40,
            ),
            factories.BillFactory.build(
                payor_id=2,
                payor_type=PayorType.MEMBER,
                status=BillStatus.NEW,
                amount=50,
            ),
            factories.BillFactory.build(
                payor_id=2,
                payor_type=PayorType.MEMBER,
                status=BillStatus.FAILED,
                amount=-60,
            ),
            factories.BillFactory.build(
                payor_id=3,
                payor_type=PayorType.MEMBER,
                status=BillStatus.PAID,
                amount=-70,
            ),
            factories.BillFactory.build(
                payor_id=4,
                payor_type=PayorType.CLINIC,
                status=BillStatus.FAILED,
                amount=-70,
            ),
        ]
        for bill in created_bills:
            bill_repository.create(instance=bill)

        expected_payor_ids = {1, 2}
        results = bill_repository.get_all_payor_ids_with_active_refunds()
        assert expected_payor_ids == results

    @pytest.mark.parametrize(
        argnames="payor_id, payor_type, exclude_refunds, error_types, expected_indices",
        argvalues=(
            (
                1,
                PayorType.MEMBER,
                True,
                [
                    BillErrorTypes.CONTACT_CARD_ISSUER,
                    BillErrorTypes.PAYMENT_METHOD_HAS_EXPIRED,
                ],
                {1},
            ),
            (
                1,
                PayorType.MEMBER,
                False,
                [
                    BillErrorTypes.CONTACT_CARD_ISSUER,
                    BillErrorTypes.PAYMENT_METHOD_HAS_EXPIRED,
                ],
                {1, 2},
            ),
            (
                1,
                PayorType.MEMBER,
                False,
                [],
                {1, 2},
            ),
            (
                1,
                PayorType.MEMBER,
                False,
                [
                    BillErrorTypes.PAYMENT_METHOD_HAS_EXPIRED,
                ],
                {2},
            ),
            (
                3,
                PayorType.MEMBER,
                True,
                [
                    BillErrorTypes.CONTACT_CARD_ISSUER,
                    BillErrorTypes.INSUFFICIENT_FUNDS,
                    BillErrorTypes.OTHER_MAVEN,
                    BillErrorTypes.PAYMENT_METHOD_HAS_EXPIRED,
                    BillErrorTypes.PAYMENT_METHOD_HAS_EXPIRED,
                    BillErrorTypes.REQUIRES_AUTHENTICATE_PAYMENT,
                ],
                {},
            ),
            (
                1,
                PayorType.EMPLOYER,
                True,
                [
                    BillErrorTypes.CONTACT_CARD_ISSUER,
                    BillErrorTypes.PAYMENT_METHOD_HAS_EXPIRED,
                ],
                {1},
            ),
            (
                1,
                PayorType.CLINIC,
                False,
                [],
                {1, 2},
            ),
        ),
        ids=[
            "1. MEMBER BILL: One non-refund row found",
            "2. MEMBER BILL:One non-refund and one refund found",
            "3. MEMBER BILL:No rows match the error types",
            "4. MEMBER BILL:One refund row found",
            "5. MEMBER BILL:User has no failed bills",
            "6. EMPLOYER BILL: non-refund row found",
            "7. CLINIC BILL: Two rows found",
        ],
    )
    def test_get_failed_member_bill_by_payor_id_and_error_type(
        self,
        bill_repository,
        payor_id,
        payor_type,
        exclude_refunds,
        error_types,
        expected_indices,
    ):

        bills_to_create = [
            factories.BillFactory.build(
                payor_id=1,
                payor_type=payor_type,
                status=BillStatus.NEW,
                amount=1000,
            ),
            factories.BillFactory.build(
                payor_id=1,
                payor_type=payor_type,
                status=BillStatus.FAILED,
                amount=1000,
                error_type=BillErrorTypes.CONTACT_CARD_ISSUER.value,
            ),
            factories.BillFactory.build(
                payor_id=1,
                payor_type=payor_type,
                status=BillStatus.FAILED,
                amount=-2000,
                error_type=BillErrorTypes.PAYMENT_METHOD_HAS_EXPIRED.value,
            ),
            factories.BillFactory.build(
                payor_id=1,
                payor_type=payor_type,
                status=BillStatus.NEW,
                amount=-3000,
            ),
            factories.BillFactory.build(
                payor_id=2,
                payor_type=payor_type,
                status=BillStatus.PROCESSING,
                amount=-4000,
            ),
            factories.BillFactory.build(
                payor_id=3,
                payor_type=payor_type,
                status=BillStatus.PAID,
                amount=-7000,
            ),
        ]
        expected = set()
        for i, bill in enumerate(bills_to_create):
            bill = bill_repository.create(instance=bill)
            if i in expected_indices:
                expected.add(bill.id)
        results = {
            bill.id
            for bill in bill_repository.get_failed_bills_by_payor_id_type_and_error_types(
                payor_id, payor_type, exclude_refunds, error_types
            )
        }
        assert expected == results

    @pytest.mark.parametrize(
        argnames="inp_payor_id, inp_payor_type, inp_exclude_refunds, exp_indices",
        argvalues=(
            (1, PayorType.MEMBER, True, {0}),
            (1, PayorType.MEMBER, False, {0, 1}),
            (2, PayorType.MEMBER, True, {}),
            (1, PayorType.EMPLOYER, True, {3, 4}),
            (1, PayorType.EMPLOYER, False, {3, 4}),
            (3, PayorType.EMPLOYER, True, {}),
            (3, PayorType.CLINIC, True, {5, 6}),
            (4, PayorType.CLINIC, True, {}),
        ),
    )
    def test_get_new_bills_by_payor_id_and_type(
        self,
        billing_service,
        inp_payor_id,
        inp_payor_type,
        inp_exclude_refunds,
        exp_indices,
    ):
        bills_param = [
            (1, PayorType.MEMBER, 1000, BillStatus.NEW),
            (1, PayorType.MEMBER, -1000, BillStatus.NEW),
            (2, PayorType.MEMBER, 1500, BillStatus.FAILED),
            (1, PayorType.EMPLOYER, 2000, BillStatus.NEW),
            (1, PayorType.EMPLOYER, 3000, BillStatus.NEW),
            (3, PayorType.CLINIC, 15100, BillStatus.NEW),
            (3, PayorType.CLINIC, 15100, BillStatus.NEW),
            (4, PayorType.CLINIC, 15100, BillStatus.PAID),
        ]
        exp_bill_uuids = set()
        for i, (payor_id, payor_type, amount, status) in enumerate(bills_param):
            bill = factories.BillFactory.build(
                payor_id=payor_id,
                payor_type=payor_type,
                amount=amount,
                status=status,
            )
            bill = billing_service.bill_repo.create(instance=bill)
            if i in exp_indices:
                exp_bill_uuids.add(bill.uuid)
        res = billing_service.bill_repo.get_new_bills_by_payor_id_and_type(
            inp_payor_id, inp_payor_type, inp_exclude_refunds
        )
        res_uuids = {b.uuid for b in res}
        assert res_uuids == exp_bill_uuids

    @pytest.mark.parametrize(
        argnames="inp_payor_ids, inp_payor_type,  inp_start_date_time, inp_end_date_time, exp_indices",
        ids=[
            "1 NEW MEMBER bill found in range",
            "2 NEW MEMBER bills found in range",
            "no NEW MEMBER bills found in range",
            "2 NEW EMPLOYER bills found in range",
            "1 NEW EMPLOYER bill found in range",
        ],
        argvalues=(
            (
                [1],
                PayorType.MEMBER,
                datetime(2024, 1, 2, 10, 11, 30),
                datetime(2024, 1, 2, 10, 11, 30),
                {0},
            ),
            (
                [1],
                PayorType.MEMBER,
                datetime(2024, 1, 2, 10, 11, 30),
                datetime(2024, 3, 2, 10, 11, 30),
                {0, 1},
            ),
            (
                [2],
                PayorType.MEMBER,
                datetime(2024, 1, 2, 10, 11, 30),
                datetime(2024, 3, 2, 10, 11, 30),
                {},
            ),
            (
                [1],
                PayorType.EMPLOYER,
                datetime(2024, 1, 2, 10, 11, 30),
                datetime(2024, 3, 2, 10, 11, 30),
                {3, 4},
            ),
            (
                [1, 2],
                PayorType.EMPLOYER,
                datetime(2024, 1, 2, 10, 11, 30),
                datetime(2024, 3, 2, 10, 11, 30),
                {3, 4, 5},
            ),
        ),
    )
    def test_get_new_bills_by_payor_ids_and_type_in_date_time_range(
        self,
        billing_service,
        inp_payor_ids,
        inp_payor_type,
        inp_start_date_time,
        inp_end_date_time,
        exp_indices,
    ):
        bills_param = [
            (
                1,
                PayorType.MEMBER,
                1000,
                BillStatus.NEW,
                datetime(2024, 1, 2, 10, 11, 30),
            ),
            (
                1,
                PayorType.MEMBER,
                -1000,
                BillStatus.NEW,
                datetime(2024, 2, 2, 10, 11, 30),
            ),
            (
                2,
                PayorType.MEMBER,
                1500,
                BillStatus.FAILED,
                datetime(2024, 1, 2, 10, 11, 30),
            ),
            (
                1,
                PayorType.EMPLOYER,
                2000,
                BillStatus.NEW,
                datetime(2024, 1, 2, 10, 11, 30),
            ),
            (
                1,
                PayorType.EMPLOYER,
                3000,
                BillStatus.NEW,
                datetime(2024, 2, 2, 10, 11, 30),
            ),
            (
                2,
                PayorType.EMPLOYER,
                3000,
                BillStatus.NEW,
                datetime(2024, 2, 2, 10, 11, 30),
            ),
            (
                3,
                PayorType.CLINIC,
                15100,
                BillStatus.NEW,
                datetime(2024, 2, 2, 10, 11, 30),
            ),
            (
                3,
                PayorType.CLINIC,
                15100,
                BillStatus.NEW,
                datetime(2024, 3, 2, 10, 11, 30),
            ),
            (
                4,
                PayorType.CLINIC,
                15100,
                BillStatus.PAID,
                datetime(2024, 2, 2, 10, 11, 30),
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
        res = billing_service.bill_repo.get_new_bills_by_payor_ids_and_type_in_date_time_range(
            inp_payor_ids, inp_payor_type, inp_start_date_time, inp_end_date_time
        )
        res_uuids = {b.uuid for b in res}
        assert res_uuids == exp_bill_uuids

    def test_get_bills_by_procedure_id_and_payor_type(self, billing_service):
        bills_param = {
            1: {
                PayorType.MEMBER: (BillStatus.PAID, BillStatus.NEW),
                PayorType.EMPLOYER: (BillStatus.PAID, BillStatus.NEW),
                PayorType.CLINIC: (BillStatus.NEW,),
            },
            2: {
                PayorType.MEMBER: (
                    BillStatus.FAILED,
                    BillStatus.FAILED,
                ),
                PayorType.EMPLOYER: (BillStatus.NEW,),
            },
        }
        exp = []
        for proc_id, payload in bills_param.items():
            for payor_type, b_stats in payload.items():
                for b_stat in b_stats:
                    bill = billing_service.bill_repo.create(
                        instance=factories.BillFactory.build(
                            payor_type=payor_type, procedure_id=proc_id, status=b_stat
                        )
                    )
                    exp.append(bill)
        fn = billing_service.bill_repo.get_bills_by_procedure_id_payor_type_status
        assert fn(1, PayorType.MEMBER, [BillStatus.PAID]) == [exp[0]]
        assert fn(1, PayorType.MEMBER, [BillStatus.NEW]) == [exp[1]]
        assert fn(1, PayorType.MEMBER, [BillStatus.PAID, BillStatus.NEW]) == [
            exp[0],
            exp[1],
        ]
        assert fn(1, PayorType.MEMBER, []) == [exp[0], exp[1]]
        assert fn(1, PayorType.MEMBER, [BillStatus.FAILED]) == []
        assert fn(1, PayorType.EMPLOYER, [BillStatus.PAID]) == [exp[2]]
        assert fn(1, PayorType.EMPLOYER, [BillStatus.NEW]) == [exp[3]]
        assert fn(1, PayorType.CLINIC, [BillStatus.NEW]) == [exp[4]]
        assert fn(2, PayorType.MEMBER, [BillStatus.FAILED]) == [exp[5], exp[6]]
        assert fn(2, PayorType.EMPLOYER, [BillStatus.FAILED, BillStatus.NEW]) == [
            exp[7]
        ]
        assert fn(2, PayorType.CLINIC, [BillStatus.FAILED]) == []

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

        res = billing_service.bill_repo.get_money_movement_bills_by_procedure_id_payor_type(
            inp_proc_id,
            inp_payor_type,
            billing_service.bill_processing_record_repo.table,
        )
        assert exp == res

    @pytest.mark.parametrize(
        argnames="inp_proc_ids,inp_payor_type,inp_bills_to_build,current_year,exp_indices",
        ids=[
            "0. Only member bills that have money movement are returned",
            "1. No employer bills, nothing returned.",
            "2. Only member bills that have money movement are returned.",
            "3. Since there are no bills, nothing is returned.",
            "4. Since there are no member bills that have cash movement, nothing is returned.",
            "5. Since bills were created the previous year, nothing is returned",
        ],
        argvalues=(
            # 0. Only member bills that have money movement are returned. Employer bills, cancelled member bills. and
            # refunded member bills that were used to cancel bill are not returned.
            (
                [1, 2, 3, 4, 5, 6, 7],
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
                True,
                [0, 1, 5],
            ),
            # 1. Since there are no employer bills, none are returned.
            (
                [1, 2, 3, 4, 5, 6],
                PayorType.EMPLOYER,
                [
                    (PayorType.MEMBER, BillStatus.NEW, []),
                    (PayorType.MEMBER, BillStatus.PAID, [False, True]),
                    (PayorType.MEMBER, BillStatus.CANCELLED, []),
                    (PayorType.MEMBER, BillStatus.REFUNDED, []),
                    (PayorType.MEMBER, BillStatus.CANCELLED, [False, True]),
                    (PayorType.MEMBER, BillStatus.REFUNDED, [True, False]),
                ],
                True,
                [],
            ),
            # 2. Only member bills that have money movement are returned. Employer bills, cancelled member bills. and
            # refunded member bills that were used to cancel bill are not returned.
            (
                [1, 2, 3, 4, 5, 6],
                PayorType.MEMBER,
                [
                    (PayorType.MEMBER, BillStatus.NEW, []),
                    (PayorType.MEMBER, BillStatus.PAID, [False, True]),
                    (PayorType.MEMBER, BillStatus.CANCELLED, []),
                    (PayorType.MEMBER, BillStatus.REFUNDED, []),
                    (PayorType.MEMBER, BillStatus.CANCELLED, [False, True]),
                    (PayorType.EMPLOYER, BillStatus.REFUNDED, [True, False]),
                ],
                True,
                [0, 1],
            ),
            # 3. Since there are no bills, nothing is returned.
            ([7], PayorType.MEMBER, [], True, []),
            # 4. Since there are no member bills that have cash movement, nothing is returned.
            (
                [1, 2, 3],
                PayorType.MEMBER,
                [
                    (PayorType.MEMBER, BillStatus.CANCELLED, []),
                    (PayorType.MEMBER, BillStatus.REFUNDED, []),
                    (PayorType.MEMBER, BillStatus.CANCELLED, [False, True]),
                ],
                True,
                [],
            ),
            # 5. Since bills were created the previous year, nothing is returned.
            (
                [1, 2, 3],
                PayorType.MEMBER,
                [
                    (PayorType.MEMBER, BillStatus.CANCELLED, []),
                    (PayorType.MEMBER, BillStatus.REFUNDED, []),
                    (PayorType.MEMBER, BillStatus.CANCELLED, [False, True]),
                ],
                False,
                [],
            ),
        ),
    )
    def test_get_money_movement_bills_by_procedure_ids_payor_type_ytd(
        self,
        billing_service,
        inp_proc_ids,
        inp_payor_type,
        inp_bills_to_build,
        current_year,
        exp_indices,
    ):
        exp = []
        for i, (p_type, status, bpr_has_trans_id_list) in enumerate(inp_bills_to_build):
            if current_year:
                bill = billing_service.bill_repo.create(
                    instance=factories.BillFactory.build(
                        payor_type=p_type, procedure_id=inp_proc_ids[i], status=status
                    )
                )
            else:
                # set bills to be created last year
                current_year = datetime.utcnow()
                last_year = current_year.replace(year=current_year.year - 1)
                bill = billing_service.bill_repo.create(
                    instance=factories.BillFactory.build(
                        payor_type=p_type,
                        procedure_id=inp_proc_ids[i],
                        status=status,
                        created_at=last_year,
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

        res = billing_service.bill_repo.get_money_movement_bills_by_procedure_ids_payor_type_ytd(
            inp_proc_ids,
            inp_payor_type,
            billing_service.bill_processing_record_repo.table,
        )
        assert exp == res

    @pytest.mark.parametrize(
        argnames="pr_time, exp_bill_indices",
        argvalues=(
            (
                datetime(2024, 3, 10, 9, 30, 1),
                [3],
            ),
            (
                datetime(2024, 3, 11, 9, 30, 1),
                [3, 4],
            ),
            (
                datetime(2024, 3, 10, 8, 30, 1),
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
        bill_repository,
        new_member_bills_for_processing,
        pr_time,
        exp_bill_indices,
    ):
        exp_bill_ids = {new_member_bills_for_processing[i].id for i in exp_bill_indices}
        res = bill_repository.get_processable_new_member_bills(
            processing_time_threshhold=pr_time
        )
        assert {b.id for b in res} == exp_bill_ids


@pytest.fixture
def historic_bills(billing_service, member_payor_id):
    created_bills = factories.BillFactory.build_batch(
        size=6,
        payor_type=PayorType.MEMBER,
        payor_id=member_payor_id,
        status=factory.Iterator(
            [
                BillStatus.NEW,
                BillStatus.PROCESSING,
                BillStatus.FAILED,
                # historic bills
                BillStatus.PAID,  # with trans id
                BillStatus.REFUNDED,  # with trans id
                BillStatus.PAID,  # without trans id
                # cancelled bill and the refund that cancelled it should not show
                BillStatus.REFUNDED,
                BillStatus.CANCELLED,
            ]
        ),
    )
    # Different member should not show
    created_bills.append(
        factories.BillFactory.build(
            payor_type=PayorType.MEMBER,
            payor_id=1,
            status=BillStatus.PROCESSING,
        )
    )

    bills_with_trans = range(1, 5)
    to_return = []
    for i, bill in enumerate(created_bills):
        bill = billing_service.bill_repo.create(instance=bill)
        to_return.append(bill)
        billing_service.bill_processing_record_repo.create(
            instance=factories.BillProcessingRecordFactory.build(
                bill_id=bill.id,
                bill_status=bill.status.value,
                transaction_id=uuid.uuid4() if i in bills_with_trans else None,
                # these 2 fields do not matter
                processing_record_type="payment_gateway_request",
                body="",
            )
        )
    return to_return


class TestBillRepositoryHistoric:
    def test_get_historic_by_payor(
        self, bill_repository, historic_bills, member_payor_id
    ):
        bills = bill_repository.get_by_payor_with_historic(
            payor_type=PayorType.MEMBER,
            payor_id=member_payor_id,
            historic_limit=10,
        )
        assert len(bills) == 6
        assert sorted(bills, key=lambda x: x.id) == historic_bills[0:6]

    def test_get_historic_limit(self, bill_repository, historic_bills, member_payor_id):
        # limit cuts off one historical bill, but no upcoming bills
        limited_bills = bill_repository.get_by_payor_with_historic(
            payor_type=PayorType.MEMBER,
            payor_id=member_payor_id,
            historic_limit=1,
        )
        assert sorted(limited_bills, key=lambda x: x.id) == historic_bills[0:3] + [
            historic_bills[5]
        ]

    def test_get_historic_none(self, bill_repository, historic_bills):
        no_bills = bill_repository.get_by_payor_with_historic(
            payor_type=PayorType.MEMBER, payor_id=-1, historic_limit=10
        )
        assert no_bills == []

    def test_count_historic(self, bill_repository, historic_bills, member_payor_id):
        count = bill_repository.count_by_payor_with_historic(
            payor_type=PayorType.MEMBER, payor_id=member_payor_id
        )
        assert count == 3

    def test_count_historic_none(self, bill_repository, historic_bills):
        count = bill_repository.count_by_payor_with_historic(
            payor_type=PayorType.MEMBER, payor_id=-1
        )
        assert count == 0
