import datetime

import factory
import pytest

from cost_breakdown.pytests.factories import CostBreakdownFactory
from pytests.db_util import enable_db_performance_warnings
from wallet.models.constants import (
    ReimbursementRequestExpenseTypes,
    ReimbursementRequestState,
    ReimbursementRequestType,
    WalletState,
)
from wallet.pytests.factories import (
    ReimbursementRequestCategoryExpenseTypesFactory,
    ReimbursementRequestFactory,
    ReimbursementWalletFactory,
)
from wallet.services.reimbursment_request_mmb import ReimbursementRequestMMBService
from wallet.utils.admin_helpers import FlashMessage, FlashMessageCategory


@pytest.fixture
def mmb_service():
    return ReimbursementRequestMMBService()


@pytest.fixture(scope="function")
def reimbursement_request(qualified_direct_payment_enabled_wallet):
    wallet = qualified_direct_payment_enabled_wallet
    org_setting = wallet.reimbursement_organization_settings
    category = org_setting.allowed_reimbursement_categories[
        0
    ].reimbursement_request_category
    reimbursement_request = ReimbursementRequestFactory.create(
        amount=100_00,
        reimbursement_wallet_id=wallet.id,
        wallet=wallet,
        category=category,
        state=ReimbursementRequestState.NEW,
        reimbursement_type=ReimbursementRequestType.MANUAL,
        service_start_date=datetime.date.today() - datetime.timedelta(days=2),
    )
    return reimbursement_request


class TestMMBService:
    @pytest.mark.parametrize("direct_payment_enabled", [True, False])
    def test_is_mmb(self, mmb_service, reimbursement_request, direct_payment_enabled):
        reimbursement_request.wallet.reimbursement_organization_settings.direct_payment_enabled = (
            direct_payment_enabled
        )
        is_mmb = mmb_service.is_mmb(reimbursement_request)
        assert is_mmb == direct_payment_enabled

    def test_get_related_requests_missing_cost_breakdowns_empty(
        self, mmb_service, reimbursement_request
    ):
        assert (
            mmb_service.get_related_requests_missing_cost_breakdowns(
                reimbursement_request
            )
            == []
        )

    def test_get_related_requests_missing_cost_breakdowns(
        self, mmb_service, reimbursement_request
    ):
        # RR with cost breakdown
        with_id = ReimbursementRequestFactory.create(
            reimbursement_wallet_id=reimbursement_request.reimbursement_wallet_id,
            wallet=reimbursement_request.wallet,
            category=reimbursement_request.category,
            reimbursement_type=ReimbursementRequestType.MANUAL,
            service_start_date=reimbursement_request.service_start_date
            - datetime.timedelta(days=1),
        )
        CostBreakdownFactory.create(reimbursement_request_id=with_id.id)
        # RRs without cost breakdowns
        # on the wrong wallet
        wallet = ReimbursementWalletFactory.create(state=WalletState.QUALIFIED)
        ReimbursementRequestFactory.create(
            reimbursement_wallet_id=wallet.id,
            wallet=wallet,
            category=reimbursement_request.category,
            reimbursement_type=ReimbursementRequestType.MANUAL,
            service_start_date=reimbursement_request.service_start_date
            - datetime.timedelta(days=1),
        )
        # not manual
        ReimbursementRequestFactory.create(
            reimbursement_wallet_id=reimbursement_request.reimbursement_wallet_id,
            wallet=reimbursement_request.wallet,
            category=reimbursement_request.category,
            reimbursement_type=ReimbursementRequestType.DIRECT_BILLING,
            service_start_date=reimbursement_request.service_start_date
            - datetime.timedelta(days=1),
        )
        # after our current start date
        ReimbursementRequestFactory.create(
            reimbursement_wallet_id=reimbursement_request.reimbursement_wallet_id,
            wallet=reimbursement_request.wallet,
            category=reimbursement_request.category,
            reimbursement_type=ReimbursementRequestType.DIRECT_BILLING,
            service_start_date=reimbursement_request.service_start_date
            + datetime.timedelta(days=1),
        )
        # valid due to lack of cost breakdown
        valid_request = ReimbursementRequestFactory.create(
            # on the right wallet
            reimbursement_wallet_id=reimbursement_request.reimbursement_wallet_id,
            wallet=reimbursement_request.wallet,
            category=reimbursement_request.category,
            # is manual
            reimbursement_type=ReimbursementRequestType.MANUAL,
            # before the current start date
            service_start_date=reimbursement_request.service_start_date
            - datetime.timedelta(days=1),
        )
        assert mmb_service.get_related_requests_missing_cost_breakdowns(
            reimbursement_request
        ) == [valid_request]

    def test_get_related_requests_missing_cost_breakdowns_performance(
        self, mmb_service, reimbursement_request, db
    ):
        # valid due to lack of cost breakdown
        request = ReimbursementRequestFactory.create(
            # on the right wallet
            reimbursement_wallet_id=reimbursement_request.reimbursement_wallet_id,
            wallet=reimbursement_request.wallet,
            category=reimbursement_request.category,
            # is manual
            reimbursement_type=ReimbursementRequestType.MANUAL,
            # before the current start date
            service_start_date=reimbursement_request.service_start_date
            - datetime.timedelta(days=1),
        )
        ReimbursementRequestCategoryExpenseTypesFactory.create_batch(
            size=2,
            reimbursement_request_category_id=reimbursement_request.reimbursement_request_category_id,
            expense_type=factory.Iterator(
                [
                    ReimbursementRequestExpenseTypes.FERTILITY,
                    ReimbursementRequestExpenseTypes.PRESERVATION,
                ]
            ),
        )
        missing_rrs = mmb_service.get_related_requests_missing_cost_breakdowns(
            reimbursement_request
        )

        # confirm the joined loads in get_related... are working
        with enable_db_performance_warnings(
            database=db,
            failure_threshold=1,
        ):
            messages = [
                f"Reimbursement Request ID: {rr.id} - Expense Type(s): {', '.join([expense.value for expense in rr.category.expense_types])}"
                for rr in missing_rrs
            ]
        assert len(messages) == 1
        assert (
            messages[0]
            == f"Reimbursement Request ID: {request.id} - Expense Type(s): FERTILITY, PRESERVATION"
        )

    @pytest.mark.parametrize(
        "is_deductible_accumulation,total_member_responsibility,total_employer_responsibility,"
        "expected_amount,expected_state",
        [
            # member responsibility == amount
            (False, 100, 0, 100, "PENDING"),
            (True, 100, 0, 100, "DENIED"),
            # divided responsibility
            (False, 25, 75, 100, "PENDING"),
            (True, 25, 75, 75, "PENDING"),
            # employer responsibility == amount
            (False, 0, 100, 100, "PENDING"),
            (True, 0, 100, 100, "PENDING"),
        ],
        ids=[
            "memb_resp_not_da",
            "memb_resp_da",
            "divided_resp_not_da",
            "divided_resp_da",
            "employer_resp_not_da",
            "employer_resp_da",
        ],
    )
    def test_update_request_for_cost_breakdown(
        self,
        qualified_wallet,
        mmb_service,
        is_deductible_accumulation,
        total_member_responsibility,
        total_employer_responsibility,
        expected_amount,
        expected_state,
    ):
        org_setting = qualified_wallet.reimbursement_organization_settings
        org_setting.deductible_accumulation_enabled = is_deductible_accumulation
        category = org_setting.allowed_reimbursement_categories[
            0
        ].reimbursement_request_category
        reimbursement_request = ReimbursementRequestFactory.create(
            wallet=qualified_wallet,
            category=category,
            state=ReimbursementRequestState.NEW,
            amount=100,
            transaction_amount=100,
        )
        cost_breakdown = CostBreakdownFactory.create(
            total_employer_responsibility=total_employer_responsibility,
            total_member_responsibility=total_member_responsibility,
        )

        updated_rr = mmb_service.update_request_for_cost_breakdown(
            reimbursement_request, cost_breakdown
        )

        assert updated_rr.amount == expected_amount
        assert updated_rr.transaction_amount == expected_amount
        assert updated_rr.state == ReimbursementRequestState(expected_state)

    @pytest.mark.parametrize(
        "messages",
        [
            [],
            [
                FlashMessage(message="Test", category=FlashMessageCategory.INFO),
                FlashMessage(message=None, category=FlashMessageCategory.ERROR),
                FlashMessage(message="Test", category=None),
            ],
            None,
        ],
    )
    def test_handle_messages_for_state_change(self, mmb_service, messages):
        res = ReimbursementRequestMMBService.handle_messages_for_state_change(messages)
        assert isinstance(res, str)
