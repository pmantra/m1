import datetime
from unittest import mock

import factory
import pytest

from cost_breakdown.pytests.factories import CostBreakdownFactory
from direct_payment.billing import models
from direct_payment.billing.pytests import factories as billing_factories
from direct_payment.billing.pytests.conftest import (  # noqa: F401
    bill_repository,
    bill_user,
    bill_wallet,
)
from direct_payment.payments.http.payments_history import (
    PaymentHistoryResource,
    get_caption_label,
    get_display_date,
    get_subtitle_label,
)
from direct_payment.payments.models import PaymentRecord
from direct_payment.treatment_procedure.models.treatment_procedure import (
    TreatmentProcedureStatus,
)
from direct_payment.treatment_procedure.pytests import factories as procedure_factories


@pytest.fixture
def historic_pending_procedure(bill_wallet):  # noqa: F811
    return procedure_factories.TreatmentProcedureFactory.create(
        status=TreatmentProcedureStatus.SCHEDULED,
        reimbursement_wallet_id=bill_wallet.id,
    )


@pytest.fixture
def procedure(bill_wallet):  # noqa: F811
    return procedure_factories.TreatmentProcedureFactory.create(
        status=TreatmentProcedureStatus.SCHEDULED,
        reimbursement_wallet_id=bill_wallet.id,
    )


@pytest.fixture
def cost_breakdown():
    return CostBreakdownFactory.create(wallet_id=44444)


@pytest.fixture
def historic_bills(
    bill_repository,  # noqa: F811
    bill_wallet,  # noqa: F811
    procedure,
    cost_breakdown,
):
    bills = billing_factories.BillFactory.build_batch(
        size=3,
        status=factory.Iterator(
            [
                models.BillStatus.PROCESSING,
                models.BillStatus.FAILED,
                models.BillStatus.PAID,
            ]
        ),
        procedure_id=procedure.id,
        cost_breakdown_id=cost_breakdown.id,
        payor_type=models.PayorType.MEMBER,
        payor_id=bill_wallet.id,
        paid_at=factory.Iterator([None, None, datetime.datetime.now()]),
    )
    return [bill_repository.create(instance=bill) for bill in bills]


class TestPaymentHistory:
    def test_call_payments_history_success_empty(
        self, client, api_helpers, bill_wallet  # noqa: F811
    ):
        with mock.patch(
            "wallet.resources.common.WalletResourceMixin._wallet_or_404",
            return_value=bill_wallet,
        ):
            res = client.get(
                f"/api/v1/direct_payment/payments/reimbursement_wallet/{bill_wallet.id}",
                headers=api_helpers.json_headers(user=bill_wallet.employee_member),
            )
        assert res.status_code == 200

    def test_call_payments_history_success_refinement_flag_off(
        self,
        client,
        api_helpers,
        bill_wallet,  # noqa: F811
        historic_bills,
        historic_pending_procedure,
    ):
        with mock.patch(
            "wallet.resources.common.WalletResourceMixin._wallet_or_404",
            return_value=bill_wallet,
        ), mock.patch(
            "direct_payment.payments.http.payments_history.bool_variation",
            return_value=False,
        ):
            res = client.get(
                f"/api/v1/direct_payment/payments/reimbursement_wallet/{bill_wallet.id}",
                headers=api_helpers.json_headers(user=bill_wallet.employee_member),
            )
        assert res.status_code == 200
        assert len(res.json["upcoming"]) == 3
        assert [record["payment_status"] for record in res.json["upcoming"]] == [
            "FAILED",
            "PENDING",
            "PROCESSING",
        ]
        assert res.json["upcoming"][0]["payment_status"] == "FAILED"
        assert len(res.json["history"]["results"]) == 1
        assert [
            record["payment_status"] for record in res.json["history"]["results"]
        ] == ["PAID"]
        assert res.json["history"]["links"] == {"next": None, "prev": None}
        assert res.json["history"]["num_pages"] == 1
        assert res.json["history"]["count"] == 1
        pending_record = next(
            record
            for record in res.json["upcoming"]
            if record["payment_status"] == "PENDING"
        )
        assert pending_record["bill_uuid"] is None
        assert "subtitle_label" in pending_record
        assert "caption_label" not in pending_record

    def test_call_payments_history_success_refinement_flag_on(
        self,
        client,
        api_helpers,
        bill_wallet,  # noqa: F811
        historic_bills,
        historic_pending_procedure,
    ):
        with mock.patch(
            "wallet.resources.common.WalletResourceMixin._wallet_or_404",
            return_value=bill_wallet,
        ), mock.patch(
            "direct_payment.payments.http.payments_history.bool_variation",
            return_value=True,
        ):
            res = client.get(
                f"/api/v1/direct_payment/payments/reimbursement_wallet/{bill_wallet.id}",
                headers=api_helpers.json_headers(user=bill_wallet.employee_member),
            )
        assert res.status_code == 200
        assert len(res.json["upcoming"]) == 3
        assert [record["payment_status"] for record in res.json["upcoming"]] == [
            "FAILED",
            "PENDING",
            "PROCESSING",
        ]
        assert res.json["upcoming"][0]["payment_status"] == "FAILED"
        assert len(res.json["history"]["results"]) == 1
        assert [
            record["payment_status"] for record in res.json["history"]["results"]
        ] == ["PAID"]
        assert res.json["history"]["links"] == {"next": None, "prev": None}
        assert res.json["history"]["num_pages"] == 1
        assert res.json["history"]["count"] == 1
        pending_record = next(
            record
            for record in res.json["upcoming"]
            if record["payment_status"] == "PENDING"
        )
        assert pending_record["bill_uuid"] is None
        assert (
            pending_record["subtitle_label"] == "Calculating, please check back later."
        )
        assert pending_record["caption_label"] is None


class TestPaymentHistoryPagination:
    @pytest.mark.parametrize(
        "requested_page,limit,expected_offset",
        [
            (1, 10, 0),
            (2, 10, 10),
            (3, 10, 20),
            (5, 1, 4),
        ],
    )
    def test_offset_and_limit(self, requested_page, limit, expected_offset):
        resource = PaymentHistoryResource()
        resource.PAGINATION_LIMIT = limit
        data = resource._pagination_handler(requested_page, 0, 0)
        assert data.offset == expected_offset
        assert data.limit == limit

    @pytest.mark.parametrize(
        "pagination_count,limit,expected_page_count",
        [
            (1, 10, 1),
            (0, 10, 0),
            (30, 10, 3),
            (30, 2, 15),
        ],
    )
    def test_page_count(self, pagination_count, limit, expected_page_count):
        resource = PaymentHistoryResource()
        resource.PAGINATION_LIMIT = limit
        data = resource._pagination_handler(1, pagination_count, 0)
        assert data.num_pages == expected_page_count

    def test_no_page_links(self):
        resource = PaymentHistoryResource()
        resource.PAGINATION_LIMIT = 10
        data = resource._pagination_handler(1, 0, 0)
        assert data.next_link is None
        assert data.prev_link is None

    def test_next_page_link(self):
        resource = PaymentHistoryResource()
        resource.PAGINATION_LIMIT = 10
        data = resource._pagination_handler(
            page_number=1, pagination_count=100, wallet_id=1
        )
        assert (
            data.next_link == "/direct_payment/payments/reimbursement_wallet/1?page=2"
        )
        assert data.prev_link is None

    def test_prev_page_link(self):
        resource = PaymentHistoryResource()
        resource.PAGINATION_LIMIT = 10
        data = resource._pagination_handler(
            page_number=2, pagination_count=20, wallet_id=1
        )
        assert data.next_link is None
        assert (
            data.prev_link == "/direct_payment/payments/reimbursement_wallet/1?page=1"
        )

    def test_all_page_links(self):
        resource = PaymentHistoryResource()
        resource.PAGINATION_LIMIT = 10
        data = resource._pagination_handler(
            page_number=5, pagination_count=100, wallet_id=1
        )
        assert (
            data.next_link == "/direct_payment/payments/reimbursement_wallet/1?page=6"
        )
        assert (
            data.prev_link == "/direct_payment/payments/reimbursement_wallet/1?page=4"
        )


class TestPaymentHistoryUtils:
    @pytest.mark.parametrize(
        "cost_responsibility_type,computed_display_date,payment_status,expected_response",
        [
            ("shared", "Jan 1, 2050", "PAID", "Jan 1, 2050 | Billed to ***1234"),
            ("member_only", "Apr 4, 2053", "PAID", "Apr 4, 2053 | Billed to ***1234"),
            ("no_member", "Jan 3, 2025", "PAID", "Jan 3, 2025"),
            ("shared", "Aug 5, 2093", "PROCESSING", "Aug 5, 2093 | Billed to ***1234"),
            (
                "shared",
                "Aug 5, 2093",
                "PENDING",
                "Calculating, please check back later.",
            ),
            ("shared", "Aug 6, 2093", "FAILED", "Due Aug 6, 2093"),
            ("shared", "Dec 5, 2093", "REFUNDED", "Dec 5, 2093 | Returned to ***1234"),
            ("shared", "Jul 5, 2093", "NEW", "Due Jul 5, 2093 | Bill to ***1234"),
            ("shared", "Oct 31, 2093", "CANCELLED", "Oct 31, 2093"),
            ("shared", "Aug 5, 2095", "VOIDED", "Voided on Aug 5, 2095"),
            ("shared", "Aug 5, 2093", "impossible case", ""),
        ],
    )
    def test_get_subtitle_label(
        self,
        cost_responsibility_type,
        computed_display_date,
        payment_status,
        expected_response,
    ):
        record = PaymentRecord(
            label="hi",
            treatment_procedure_id=1,
            payment_status=payment_status,
            created_at=datetime.datetime(2013, 10, 2),
            bill_uuid="dud",
            payment_method_type=models.PaymentMethod.PAYMENT_GATEWAY,
            payment_method_display_label="1234",
            member_responsibility=3141592,
            total_cost=27181,
            cost_responsibility_type=cost_responsibility_type,
            due_at=datetime.datetime(2013, 10, 2),
            completed_at=datetime.datetime(2013, 10, 2),
            display_date="created_at",
        )
        result = get_subtitle_label(computed_display_date, record)
        assert result == expected_response

    @pytest.mark.parametrize(
        "display_date,expected_response",
        [
            ("created_at", "Jul 2, 2080"),
            ("due_at", "Jan 3, 2050"),
            ("completed_at", "Feb 4, 2050"),
            ("hello", ""),
        ],
    )
    def test_get_display_date(self, display_date, expected_response):
        record = PaymentRecord(
            label="hi",
            treatment_procedure_id=1,
            payment_status="PAID",
            created_at=datetime.datetime(2080, 7, 2),
            bill_uuid="dud",
            payment_method_type=models.PaymentMethod.PAYMENT_GATEWAY,
            payment_method_display_label="1234",
            member_responsibility=3141592,
            total_cost=27181,
            cost_responsibility_type="member_only",
            due_at=datetime.datetime(2050, 1, 3),
            completed_at=datetime.datetime(2050, 2, 4),
            display_date=display_date,
        )
        assert get_display_date(record) == expected_response

    def test_caption_label(self):
        payment_statuses = (
            "NEW",
            "PENDING",
            "PROCESSING",
            "FAILED",
            "PAID",
            "REFUNDED",
            "CANCELLED",
            "VOIDED",
        )
        cost_responsibility_types = ("shared", "no_member", "member_only")
        for payment_status in payment_statuses:
            if payment_status != "PAID":
                for cost_responsibility_type in cost_responsibility_types:
                    assert (
                        get_caption_label(payment_status, cost_responsibility_type)
                        is None
                    )
            else:
                for cost_responsibility_type in cost_responsibility_types:
                    result = get_caption_label(payment_status, cost_responsibility_type)
                    if cost_responsibility_type == "member_only":
                        assert result is None
                    elif cost_responsibility_type == "no_member":
                        assert result == "Full cost covered by Maven"
                    elif cost_responsibility_type == "shared":
                        assert result == "Remaining cost covered by Maven"
