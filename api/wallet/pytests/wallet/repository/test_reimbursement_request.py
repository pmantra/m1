from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from random import randint
from uuid import uuid4

import pytest

from cost_breakdown.constants import ClaimType
from cost_breakdown.pytests.factories import (
    CostBreakdownFactory,
    ReimbursementRequestToCostBreakdownFactory,
)
from direct_payment.billing.pytests import factories as billing_factories  # noqa: F401
from direct_payment.payments.pytests.test_payments_helper import (  # noqa: F401
    CURRENT_TIME,
    wallet_cycle_based,
)
from direct_payment.treatment_procedure.pytests import factories as procedure_factories
from storage.connection import db
from wallet.models.constants import (
    ReimbursementRequestExpenseTypes,
    ReimbursementRequestState,
    ReimbursementRequestType,
)
from wallet.models.models import ReimbursementPostRequest
from wallet.models.reimbursement import (
    ReimbursementRequest,
    ReimbursementRequestCategory,
)
from wallet.models.reimbursement_organization_settings import (
    ReimbursementOrgSettingCategoryAssociation,
)
from wallet.models.reimbursement_wallet import ReimbursementWallet
from wallet.models.reimbursement_wallet_credit import ReimbursementCycleCredits
from wallet.pytests import factories
from wallet.repository.reimbursement_request import ReimbursementRequestRepository
from wallet.services.reimbursement_request import ReimbursementRequestService


@pytest.fixture
def reimbursement_request_repository(session) -> ReimbursementRequestRepository:
    return ReimbursementRequestRepository(session)


@pytest.fixture
def add_reimbursement_request(qualified_wallet: ReimbursementWallet):
    fertility_category: ReimbursementRequestCategory = (
        factories.ReimbursementRequestCategoryFactory.create(label="fertility")
    )
    maternity_category: ReimbursementRequestCategory = (
        factories.ReimbursementRequestCategoryFactory.create(label="maternity")
    )
    fertility_category_association: ReimbursementOrgSettingCategoryAssociation = factories.ReimbursementOrgSettingCategoryAssociationFactory.create(
        reimbursement_organization_settings=qualified_wallet.reimbursement_organization_settings,
        reimbursement_request_category=fertility_category,
        reimbursement_request_category_maximum=5000,
        currency_code="USD",
    )
    maternity_category_association: ReimbursementOrgSettingCategoryAssociation = factories.ReimbursementOrgSettingCategoryAssociationFactory.create(
        reimbursement_organization_settings=qualified_wallet.reimbursement_organization_settings,
        reimbursement_request_category=maternity_category,
        reimbursement_request_category_maximum=5000,
        currency_code="USD",
    )
    category_mapping = {
        "fertility": fertility_category_association,
        "maternity": maternity_category_association,
    }

    def _add(
        state: ReimbursementRequestState,
        category_label: str,
        reimbursement_type: ReimbursementRequestType | None = None,
        age_in_days: int = 0,
    ):
        category = category_mapping.get(category_label)
        request = factories.ReimbursementRequestFactory.create(
            amount=199999,
            benefit_currency_code=category.currency_code,
            reimbursement_wallet_id=qualified_wallet.id,
            reimbursement_request_category_id=category.reimbursement_request_category_id,
            state=state,
            reimbursement_type=reimbursement_type,
        )
        if age_in_days > 0:
            request.created_at = datetime.now(timezone.utc) - timedelta(
                days=age_in_days
            )
        return request

    return _add


class TestCreateReimbursementRequest:
    def test_create_reimbursement_request_success(
        self, db, reimbursement_request_data, reimbursement_request_repository
    ):
        post_request = ReimbursementPostRequest.from_request(reimbursement_request_data)
        new_reimbursement_request = (
            ReimbursementRequestService.get_reimbursement_request_from_post_request(
                post_request
            )
        )
        reimbursement_request_repository.create_reimbursement_request(
            new_reimbursement_request
        )

        # ensures the reimbursement request was created by loading it back
        (
            db.session.query(ReimbursementRequest)
            .filter(ReimbursementRequest.id == new_reimbursement_request.id)
            .one()
        )


class TestGetAllReimbursementRequestsForWalletAndCategory:
    @staticmethod
    def test_no_reimbursements_returned(
        reimbursement_request_repository,
        qualified_wallet: ReimbursementWallet,
    ):
        # Given
        category_association = qualified_wallet.get_or_create_wallet_allowed_categories[
            0
        ]

        # When
        reimbursements = reimbursement_request_repository.get_all_reimbursement_requests_for_wallet_and_category(
            wallet_id=qualified_wallet.id,
            category_id=category_association.reimbursement_request_category_id,
        )

        # Then
        assert not reimbursements

    @staticmethod
    def test_reimbursements_returned_for_correct_category(
        reimbursement_request_repository,
        add_reimbursement_request,
        qualified_wallet: ReimbursementWallet,
    ):
        # Given
        reimbursement_fertility = add_reimbursement_request(
            state=ReimbursementRequestState.REIMBURSED, category_label="fertility"
        )
        _ = add_reimbursement_request(
            state=ReimbursementRequestState.REIMBURSED, category_label="maternity"
        )

        # When
        reimbursements = reimbursement_request_repository.get_all_reimbursement_requests_for_wallet_and_category(
            wallet_id=qualified_wallet.id,
            category_id=reimbursement_fertility.reimbursement_request_category_id,
        )

        # Then
        assert len(reimbursements) == 1
        assert reimbursements[0] == reimbursement_fertility

    @staticmethod
    def test_reimbursements_returned_for_correct_wallet(
        reimbursement_request_repository,
        add_reimbursement_request,
        qualified_wallet: ReimbursementWallet,
    ):
        # Given
        reimbursement_fertility = add_reimbursement_request(
            state=ReimbursementRequestState.REIMBURSED, category_label="fertility"
        )
        _ = add_reimbursement_request(
            state=ReimbursementRequestState.REIMBURSED, category_label="maternity"
        )

        # When
        reimbursements = reimbursement_request_repository.get_all_reimbursement_requests_for_wallet_and_category(
            wallet_id=qualified_wallet.id + 1,
            category_id=reimbursement_fertility.reimbursement_request_category_id,
        )

        # Then
        assert not reimbursements


class TestGetReimbursementRequestsForWallet:
    @staticmethod
    @pytest.mark.parametrize(
        argnames=("state", "reimbursement_type", "age_in_days", "is_returned"),
        argvalues=[
            (ReimbursementRequestState.NEW, None, 0, True),
            (
                ReimbursementRequestState.NEW,
                ReimbursementRequestType.DIRECT_BILLING,
                0,
                False,
            ),
            (
                ReimbursementRequestState.NEW,
                ReimbursementRequestType.DEBIT_CARD,
                0,
                True,
            ),
            (ReimbursementRequestState.NEW, None, 61, False),
            (ReimbursementRequestState.PENDING, None, 0, True),
            (
                ReimbursementRequestState.PENDING,
                ReimbursementRequestType.DIRECT_BILLING,
                0,
                False,
            ),
            (
                ReimbursementRequestState.PENDING,
                ReimbursementRequestType.DEBIT_CARD,
                0,
                True,
            ),
            (ReimbursementRequestState.PENDING, None, 61, True),
            (ReimbursementRequestState.APPROVED, None, 0, True),
            (
                ReimbursementRequestState.APPROVED,
                ReimbursementRequestType.DIRECT_BILLING,
                0,
                False,
            ),
            (
                ReimbursementRequestState.APPROVED,
                ReimbursementRequestType.DEBIT_CARD,
                0,
                True,
            ),
            (ReimbursementRequestState.APPROVED, None, 61, True),
            (ReimbursementRequestState.REIMBURSED, None, 0, True),
            (
                ReimbursementRequestState.REIMBURSED,
                ReimbursementRequestType.DIRECT_BILLING,
                0,
                False,
            ),
            (
                ReimbursementRequestState.REIMBURSED,
                ReimbursementRequestType.DEBIT_CARD,
                0,
                True,
            ),
            (ReimbursementRequestState.REIMBURSED, None, 61, True),
            (ReimbursementRequestState.DENIED, None, 0, True),
            (
                ReimbursementRequestState.DENIED,
                ReimbursementRequestType.DIRECT_BILLING,
                0,
                False,
            ),
            (
                ReimbursementRequestState.DENIED,
                ReimbursementRequestType.DEBIT_CARD,
                0,
                True,
            ),
            (ReimbursementRequestState.DENIED, None, 61, True),
            (ReimbursementRequestState.NEEDS_RECEIPT, None, 0, True),
            (
                ReimbursementRequestState.NEEDS_RECEIPT,
                ReimbursementRequestType.DIRECT_BILLING,
                0,
                False,
            ),
            (
                ReimbursementRequestState.NEEDS_RECEIPT,
                ReimbursementRequestType.DEBIT_CARD,
                0,
                True,
            ),
            (ReimbursementRequestState.NEEDS_RECEIPT, None, 61, True),
            (ReimbursementRequestState.RECEIPT_SUBMITTED, None, 0, True),
            (
                ReimbursementRequestState.RECEIPT_SUBMITTED,
                ReimbursementRequestType.DIRECT_BILLING,
                0,
                False,
            ),
            (
                ReimbursementRequestState.RECEIPT_SUBMITTED,
                ReimbursementRequestType.DEBIT_CARD,
                0,
                True,
            ),
            (ReimbursementRequestState.RECEIPT_SUBMITTED, None, 61, True),
            (ReimbursementRequestState.INSUFFICIENT_RECEIPT, None, 0, True),
            (
                ReimbursementRequestState.INSUFFICIENT_RECEIPT,
                ReimbursementRequestType.DIRECT_BILLING,
                0,
                False,
            ),
            (
                ReimbursementRequestState.INSUFFICIENT_RECEIPT,
                ReimbursementRequestType.DEBIT_CARD,
                0,
                True,
            ),
            (ReimbursementRequestState.INSUFFICIENT_RECEIPT, None, 61, True),
            (ReimbursementRequestState.INELIGIBLE_EXPENSE, None, 0, True),
            (
                ReimbursementRequestState.INELIGIBLE_EXPENSE,
                ReimbursementRequestType.DIRECT_BILLING,
                0,
                False,
            ),
            (
                ReimbursementRequestState.INELIGIBLE_EXPENSE,
                ReimbursementRequestType.DEBIT_CARD,
                0,
                True,
            ),
            (ReimbursementRequestState.INELIGIBLE_EXPENSE, None, 61, True),
            (ReimbursementRequestState.RESOLVED, None, 0, True),
            (
                ReimbursementRequestState.RESOLVED,
                ReimbursementRequestType.DIRECT_BILLING,
                0,
                False,
            ),
            (
                ReimbursementRequestState.RESOLVED,
                ReimbursementRequestType.DEBIT_CARD,
                0,
                True,
            ),
            (ReimbursementRequestState.RESOLVED, None, 61, True),
            (ReimbursementRequestState.REFUNDED, None, 0, True),
            (
                ReimbursementRequestState.REFUNDED,
                ReimbursementRequestType.DIRECT_BILLING,
                0,
                False,
            ),
            (
                ReimbursementRequestState.REFUNDED,
                ReimbursementRequestType.DEBIT_CARD,
                0,
                True,
            ),
            (ReimbursementRequestState.REFUNDED, None, 61, True),
            (ReimbursementRequestState.FAILED, None, 0, False),
            (ReimbursementRequestState.PENDING_MEMBER_INPUT, None, 0, False),
        ],
    )
    def test_get_reimbursement_request_for_wallet(
        reimbursement_request_repository,
        add_reimbursement_request,
        qualified_wallet: ReimbursementWallet,
        state: ReimbursementRequestState,
        reimbursement_type: ReimbursementRequestType,
        age_in_days: int,
        is_returned: bool,
    ):
        # Given
        add_reimbursement_request(
            state, "fertility", reimbursement_type, age_in_days=age_in_days
        )

        # When
        requests = (
            reimbursement_request_repository.get_reimbursement_requests_for_wallet(
                wallet_id=qualified_wallet.id
            )
        )

        # Then
        assert len(requests) == is_returned

    @staticmethod
    def test_get_reimbursement_request_for_wallet_with_category(
        reimbursement_request_repository,
        add_reimbursement_request,
        qualified_wallet: ReimbursementWallet,
    ):
        # Given
        fertility_request = add_reimbursement_request(
            state=ReimbursementRequestState.NEW, category_label="fertility"
        )
        _ = add_reimbursement_request(
            state=ReimbursementRequestState.NEW, category_label="maternity"
        )

        # When
        requests = (
            reimbursement_request_repository.get_reimbursement_requests_for_wallet(
                wallet_id=qualified_wallet.id, category="fertility"
            )
        )

        # Then
        assert len(requests) == 1 and requests[0] == fertility_request

    @staticmethod
    def test_get_reimbursement_request_for_wallet_ordering(
        reimbursement_request_repository,
        add_reimbursement_request,
        qualified_wallet: ReimbursementWallet,
    ):
        # Given
        fertility_request_1 = add_reimbursement_request(
            state=ReimbursementRequestState.NEW,
            category_label="fertility",
        )
        fertility_request_1.created_at = datetime.now(timezone.utc) - timedelta(days=10)
        fertility_request_2 = add_reimbursement_request(
            state=ReimbursementRequestState.NEW,
            category_label="fertility",
        )
        fertility_request_2.created_at = datetime.now(timezone.utc) - timedelta(days=1)
        fertility_request_3 = add_reimbursement_request(
            state=ReimbursementRequestState.NEW,
            category_label="fertility",
        )
        fertility_request_3.created_at = datetime.now(timezone.utc) - timedelta(days=5)

        # When
        requests = (
            reimbursement_request_repository.get_reimbursement_requests_for_wallet(
                wallet_id=qualified_wallet.id, category="fertility"
            )
        )

        # Then
        assert (fertility_request_1, fertility_request_2, fertility_request_3) == (
            requests[2],
            requests[0],
            requests[1],
        )

    @staticmethod
    def test_get_num_credits_by_cost_breakdown_id__no_id_present(
        reimbursement_request_repository,
    ):
        assert (
            reimbursement_request_repository.get_num_credits_by_cost_breakdown_id(
                randint(0, 1_000_000_000)
            )
            is None
        )

    @staticmethod
    def test_get_num_credits_by_cost_breakdown_id__cost_breakdown_id_present(
        reimbursement_request_repository: ReimbursementRequestRepository,
        wallet_cycle_based: ReimbursementWallet,  # noqa: F811
    ):
        # Create a cost
        wallet_category_association = wallet_cycle_based.reimbursement_organization_settings.allowed_reimbursement_categories[
            0
        ]
        category = wallet_category_association.reimbursement_request_category
        reimbursement_request = factories.ReimbursementRequestFactory.create(
            wallet=wallet_cycle_based, category=category, amount=750000
        )
        procedure = procedure_factories.TreatmentProcedureFactory.create(
            cost=2000,
            created_at=CURRENT_TIME,
            uuid=uuid4(),
        )
        cost_breakdown = CostBreakdownFactory.create(
            deductible=0,  # will show regardless of value
            coinsurance=0,
            copay=0,
            overage_amount=0,  # to test the filter
            total_member_responsibility=1000,
            total_employer_responsibility=1000,
        )
        cycle_credits_id = (
            db.session.query(ReimbursementCycleCredits.id)
            .filter(
                ReimbursementCycleCredits.reimbursement_wallet_id
                == wallet_cycle_based.id
            )
            .scalar()
        )
        assert cycle_credits_id is not None

        expected_number_credits_used = randint(1, 1_000_000_000)
        factories.ReimbursementCycleMemberCreditTransactionFactory.create(
            reimbursement_cycle_credits_id=cycle_credits_id,
            amount=expected_number_credits_used,
            reimbursement_request_id=reimbursement_request.id,
        )

        ReimbursementRequestToCostBreakdownFactory.create(
            reimbursement_request_id=reimbursement_request.id,
            cost_breakdown_id=cost_breakdown.id,
            treatment_procedure_uuid=procedure.uuid,
        )

        assert (
            reimbursement_request_repository.get_num_credits_by_cost_breakdown_id(
                cost_breakdown.id
            )
            == expected_number_credits_used
        )

    @staticmethod
    def test_get_reimbursement_requests_for_wallet_rr_block_filter_states(
        qualified_wallet: ReimbursementWallet,
        add_reimbursement_request,
        reimbursement_request_repository,
    ):
        valid_states = [
            ReimbursementRequestState.NEW,
            ReimbursementRequestState.PENDING,
            ReimbursementRequestState.APPROVED,
            ReimbursementRequestState.NEEDS_RECEIPT,
            ReimbursementRequestState.RECEIPT_SUBMITTED,
            ReimbursementRequestState.INSUFFICIENT_RECEIPT,
        ]
        invalid_states = [
            ReimbursementRequestState.REIMBURSED,
            ReimbursementRequestState.DENIED,
            ReimbursementRequestState.FAILED,
            ReimbursementRequestState.INELIGIBLE_EXPENSE,
            ReimbursementRequestState.RESOLVED,
            ReimbursementRequestState.REFUNDED,
            ReimbursementRequestState.PENDING_MEMBER_INPUT,
        ]

        for state in valid_states + invalid_states:
            add_reimbursement_request(
                state=state,
                category_label="fertility",
                reimbursement_type=ReimbursementRequestType.MANUAL,
            )

        add_reimbursement_request(
            state=ReimbursementRequestState.NEW,
            category_label="fertility",
            age_in_days=61,
            reimbursement_type=ReimbursementRequestType.MANUAL,
        )

        add_reimbursement_request(
            state=ReimbursementRequestState.NEW,
            category_label="fertility",
            reimbursement_type=ReimbursementRequestType.DIRECT_BILLING,
        )

        filtered_requests = reimbursement_request_repository.get_reimbursement_requests_for_wallet_rr_block(
            qualified_wallet.id, ["fertility"]
        )

        assert len(filtered_requests) == len(valid_states)

        for request in filtered_requests:
            assert request.state in valid_states
            assert request.reimbursement_type != ReimbursementRequestType.DIRECT_BILLING
            if request.state == ReimbursementRequestState.NEW:
                assert request.created_at >= datetime.today() - timedelta(days=60)

    @staticmethod
    def test_get_reimbursement_requests_for_wallet_rr_block_filter_states_no_results(
        qualified_wallet: ReimbursementWallet,
        add_reimbursement_request,
        reimbursement_request_repository,
    ):
        for state in [
            ReimbursementRequestState.REIMBURSED,
            ReimbursementRequestState.DENIED,
            ReimbursementRequestState.FAILED,
        ]:
            add_reimbursement_request(state=state, category_label="fertility")

        filtered_requests = reimbursement_request_repository.get_reimbursement_requests_for_wallet_rr_block(
            qualified_wallet.id, ["fertility"]
        )

        assert len(filtered_requests) == 0

    @staticmethod
    @pytest.mark.parametrize(
        "category_filter,expected_count,excluded_label",
        [
            (["fertility"], 6, "maternity"),
            (["maternity"], 6, "fertility"),
            (["adoption"], 0, None),
            ([], 0, None),
        ],
    )
    def test_get_reimbursement_requests_for_wallet_rr_block_filter_category_labels(
        qualified_wallet: ReimbursementWallet,
        add_reimbursement_request,
        reimbursement_request_repository,
        category_filter,
        expected_count,
        excluded_label,
    ):
        valid_states = [
            ReimbursementRequestState.NEW,
            ReimbursementRequestState.PENDING,
            ReimbursementRequestState.APPROVED,
            ReimbursementRequestState.NEEDS_RECEIPT,
            ReimbursementRequestState.RECEIPT_SUBMITTED,
            ReimbursementRequestState.INSUFFICIENT_RECEIPT,
        ]

        for state in valid_states:
            add_reimbursement_request(
                state=state,
                category_label="fertility",
            )
            add_reimbursement_request(
                state=state,
                category_label="maternity",
            )

        filtered_requests = reimbursement_request_repository.get_reimbursement_requests_for_wallet_rr_block(
            qualified_wallet.id, category_filter
        )

        assert len(filtered_requests) == expected_count

        for request in filtered_requests:
            assert request.category.label in category_filter
            if excluded_label:
                assert request.category.label != excluded_label

    @staticmethod
    def test_get_cost_breakdowns_for_reimbursement_requests(
        qualified_wallet,
        reimbursement_request_repository,
        add_reimbursement_request,
    ):

        add_reimbursement_request(
            state=ReimbursementRequestState.NEW, category_label="fertility"
        )
        add_reimbursement_request(
            state=ReimbursementRequestState.NEW, category_label="fertility"
        )
        add_reimbursement_request(
            state=ReimbursementRequestState.NEW, category_label="fertility"
        )
        reimbursement_requests = (
            reimbursement_request_repository.get_reimbursement_requests_for_wallet(
                wallet_id=qualified_wallet.id
            )
        )
        total_cost_breakdowns = 0
        for rr in reimbursement_requests:
            CostBreakdownFactory.create(
                wallet_id=qualified_wallet.id,
                reimbursement_request_id=rr.id,
                total_member_responsibility=25000,
                created_at=date.today(),
            )
            total_cost_breakdowns += 1
            CostBreakdownFactory.create(
                wallet_id=qualified_wallet.id,
                reimbursement_request_id=rr.id,
                total_member_responsibility=777700,
                created_at=date.today() - timedelta(days=2),
            )
            total_cost_breakdowns += 1

        cost_breakdowns = reimbursement_request_repository.get_cost_breakdowns_for_reimbursement_requests(
            reimbursement_requests=reimbursement_requests
        )

        assert len(cost_breakdowns) == total_cost_breakdowns
        for cb in cost_breakdowns:
            assert cb.reimbursement_request_id in [
                rr.id for rr in reimbursement_requests
            ]

    @staticmethod
    def test_get_reimbursement_request_by_id_found(
        reimbursement_request_repository, add_reimbursement_request
    ):
        rr = add_reimbursement_request(
            state=ReimbursementRequestState.NEW, category_label="fertility"
        )

        result = reimbursement_request_repository.get_reimbursement_request_by_id(rr.id)
        assert result == rr

    @staticmethod
    def test_get_reimbursement_request_by_id_not_found(
        reimbursement_request_repository, add_reimbursement_request
    ):
        add_reimbursement_request(
            state=ReimbursementRequestState.NEW, category_label="fertility"
        )
        not_found_id = randint(1, 1000)
        result = reimbursement_request_repository.get_reimbursement_request_by_id(
            not_found_id
        )
        assert result is None

    @staticmethod
    @pytest.mark.parametrize(
        argnames=("state", "expected"),
        argvalues=[
            (ReimbursementRequestState.NEW, True),
            (ReimbursementRequestState.PENDING, True),
            (ReimbursementRequestState.APPROVED, False),
            (ReimbursementRequestState.REIMBURSED, False),
            (ReimbursementRequestState.DENIED, False),
            (ReimbursementRequestState.FAILED, False),
            (ReimbursementRequestState.NEEDS_RECEIPT, True),
            (ReimbursementRequestState.RECEIPT_SUBMITTED, True),
            (ReimbursementRequestState.INSUFFICIENT_RECEIPT, True),
            (ReimbursementRequestState.INELIGIBLE_EXPENSE, True),
            (ReimbursementRequestState.PENDING_MEMBER_INPUT, True),
            (ReimbursementRequestState.RESOLVED, True),
            (ReimbursementRequestState.REFUNDED, True),
        ],
    )
    def test_wallet_has_unresolved_reimbursements(
        reimbursement_request_repository,
        qualified_wallet,
        add_reimbursement_request,
        state: ReimbursementRequestState,
        expected: bool,
    ):
        # Given
        add_reimbursement_request(state=state, category_label="fertility")

        # When
        has_unresolved: bool = (
            reimbursement_request_repository.wallet_has_unresolved_reimbursements(
                wallet_id=qualified_wallet.id
            )
        )

        # Then
        assert has_unresolved == expected

    @staticmethod
    def test_get_employer_cb_mapping(
        reimbursement_request_repository,
        qualified_wallet,
        add_reimbursement_request,
    ):
        # Given
        reimbursement = add_reimbursement_request(
            state=ReimbursementRequestState.REIMBURSED, category_label="fertility"
        )
        cb = CostBreakdownFactory.create(wallet_id=qualified_wallet.id)
        ReimbursementRequestToCostBreakdownFactory.create(
            reimbursement_request_id=reimbursement.id,
            treatment_procedure_uuid=cb.treatment_procedure_uuid,
            cost_breakdown_id=cb.id,
            claim_type=ClaimType.EMPLOYER,
        )

        # When
        mapping = reimbursement_request_repository.get_employer_cb_mapping(
            reimbursement_request_id=reimbursement.id
        )

        # Then
        assert mapping
        assert mapping.treatment_procedure_uuid == cb.treatment_procedure_uuid

    @staticmethod
    def test_get_employer_cb_mapping_not_found(
        reimbursement_request_repository,
        qualified_wallet,
        add_reimbursement_request,
    ):
        # Given
        reimbursement = add_reimbursement_request(
            state=ReimbursementRequestState.REIMBURSED, category_label="fertility"
        )

        # When
        mapping = reimbursement_request_repository.get_employer_cb_mapping(
            reimbursement_request_id=reimbursement.id
        )

        # Then
        assert not mapping

    @staticmethod
    @pytest.mark.parametrize(
        argnames=("state", "expected"),
        argvalues=[
            (ReimbursementRequestState.NEW, False),
            (ReimbursementRequestState.PENDING, False),
            (ReimbursementRequestState.APPROVED, True),
            (ReimbursementRequestState.REIMBURSED, True),
            (ReimbursementRequestState.DENIED, False),
            (ReimbursementRequestState.FAILED, False),
            (ReimbursementRequestState.NEEDS_RECEIPT, False),
            (ReimbursementRequestState.RECEIPT_SUBMITTED, False),
            (ReimbursementRequestState.INSUFFICIENT_RECEIPT, False),
            (ReimbursementRequestState.INELIGIBLE_EXPENSE, False),
            (ReimbursementRequestState.PENDING_MEMBER_INPUT, False),
            (ReimbursementRequestState.RESOLVED, False),
            (ReimbursementRequestState.REFUNDED, False),
        ],
    )
    def test_get_reimbursed_reimbursements_filter_correct_state(
        reimbursement_request_repository,
        qualified_wallet,
        add_reimbursement_request,
        state: ReimbursementRequestState,
        expected: bool,
    ):
        # Given
        request: ReimbursementRequest = add_reimbursement_request(
            state=state, category_label="fertility"
        )

        # When
        reimbursed: list[
            ReimbursementRequest
        ] = reimbursement_request_repository.get_reimbursed_reimbursements(
            wallet_id=qualified_wallet.id,
            category_id=request.reimbursement_request_category_id,
        )

        # Then
        assert bool(reimbursed) is expected

    @staticmethod
    @pytest.mark.parametrize(
        argnames=("created_at", "start_date", "end_date", "expected"),
        argvalues=[
            (
                datetime(year=2000, month=6, day=1),
                date(year=2000, month=1, day=1),
                date(year=2000, month=12, day=31),
                True,
            ),
            (
                datetime(year=2000, month=6, day=1),
                None,
                date(year=2000, month=12, day=31),
                True,
            ),
            (
                datetime(year=2000, month=6, day=1),
                date(year=2000, month=1, day=1),
                None,
                True,
            ),
            (
                datetime(year=2000, month=6, day=1),
                date(year=2000, month=6, day=1),
                date(year=2000, month=12, day=31),
                True,
            ),
            (
                datetime(year=2000, month=6, day=1),
                date(year=2000, month=1, day=1),
                date(year=2000, month=6, day=1),
                False,
            ),
        ],
    )
    def test_get_reimbursed_reimbursements_filter_date_range(
        reimbursement_request_repository,
        qualified_wallet,
        add_reimbursement_request,
        created_at: datetime,
        start_date: date | None,
        end_date: date | None,
        expected: bool,
    ):
        # Given
        request: ReimbursementRequest = add_reimbursement_request(
            state=ReimbursementRequestState.REIMBURSED, category_label="fertility"
        )
        request.created_at = created_at

        # When
        reimbursed: list[
            ReimbursementRequest
        ] = reimbursement_request_repository.get_reimbursed_reimbursements(
            wallet_id=qualified_wallet.id,
            category_id=request.reimbursement_request_category_id,
            start_date=start_date,
            end_date=end_date,
        )

        # Then
        assert bool(reimbursed) is expected


class TestPendingReimbursementsForWallet:
    @staticmethod
    def test_no_reimbursements_returned(
        reimbursement_request_repository,
        qualified_wallet: ReimbursementWallet,
    ):
        # Given
        category_association = qualified_wallet.get_or_create_wallet_allowed_categories[
            0
        ]

        # When
        reimbursements = reimbursement_request_repository.get_pending_reimbursements(
            wallet_id=qualified_wallet.id,
            category_id=category_association.reimbursement_request_category_id,
        )

        # Then
        assert not reimbursements

    @staticmethod
    def test_reimbursements_returned_for_correct_category(
        reimbursement_request_repository,
        add_reimbursement_request,
        qualified_wallet: ReimbursementWallet,
    ):
        # Given
        reimbursement_fertility = add_reimbursement_request(
            state=ReimbursementRequestState.PENDING, category_label="fertility"
        )
        _ = add_reimbursement_request(
            state=ReimbursementRequestState.PENDING, category_label="maternity"
        )

        # When
        reimbursements = reimbursement_request_repository.get_pending_reimbursements(
            wallet_id=qualified_wallet.id,
            category_id=reimbursement_fertility.reimbursement_request_category_id,
        )

        # Then
        assert len(reimbursements) == 1
        assert reimbursements[0] == reimbursement_fertility

    @staticmethod
    def test_reimbursements_returned_for_correct_wallet(
        reimbursement_request_repository,
        add_reimbursement_request,
        qualified_wallet: ReimbursementWallet,
    ):
        # Given
        reimbursement_fertility = add_reimbursement_request(
            state=ReimbursementRequestState.PENDING, category_label="fertility"
        )
        _ = add_reimbursement_request(
            state=ReimbursementRequestState.PENDING, category_label="maternity"
        )

        # When
        reimbursements = reimbursement_request_repository.get_pending_reimbursements(
            wallet_id=qualified_wallet.id + 1,
            category_id=reimbursement_fertility.reimbursement_request_category_id,
        )

        # Then
        assert not reimbursements


class TestGetExpenseSubtype:
    @staticmethod
    def test_get_expense_subtype(reimbursement_request_repository, expense_subtypes):
        # Given
        expense_subtype_code = "FERTRX"

        # When
        expense_subtype = reimbursement_request_repository.get_expense_subtype(
            expense_type=ReimbursementRequestExpenseTypes.FERTILITY,
            code=expense_subtype_code,
        )

        # Then
        assert expense_subtype == expense_subtypes[expense_subtype_code]

    @staticmethod
    def test_get_expense_subtype_not_found(
        reimbursement_request_repository, expense_subtypes
    ):
        # Given
        expense_subtype_code = "gobbledygook"

        # When
        expense_subtype = reimbursement_request_repository.get_expense_subtype(
            expense_type=ReimbursementRequestExpenseTypes.FERTILITY,
            code=expense_subtype_code,
        )

        # Then
        assert not expense_subtype
