from datetime import date, datetime, timedelta
from decimal import Decimal
from unittest import mock
from unittest.mock import patch

import factory
import pytest

from cost_breakdown.pytests.factories import CostBreakdownFactory
from wallet.models.constants import (
    MemberType,
    ReimbursementRequestAutoProcessing,
    ReimbursementRequestExpenseTypes,
    ReimbursementRequestState,
)
from wallet.models.models import ReimbursementPostRequest
from wallet.models.reimbursement import ReimbursementRequest
from wallet.models.reimbursement_wallet import ReimbursementWallet
from wallet.pytests.factories import (
    ReimbursementRequestCategoryFactory,
    ReimbursementRequestExchangeRatesFactory,
    ReimbursementRequestFactory,
    ReimbursementRequestSourceFactory,
)
from wallet.services.reimbursement_request import (
    ReimbursementRequestService,
    create_appeal,
)


@pytest.fixture
def reimbursement_request_service(session):
    return ReimbursementRequestService(session)


@pytest.fixture
def exchange_rates():
    rates = [
        ("AUD", "USD", date(2024, 1, 1), Decimal("1.50")),
        ("GBP", "USD", date(2024, 1, 1), Decimal("0.50")),
        ("JPY", "USD", date(2024, 1, 1), Decimal("0.0068")),
    ]

    ReimbursementRequestExchangeRatesFactory.create_batch(
        size=len(rates),
        source_currency=factory.Iterator(rates, getter=lambda r: r[0]),
        target_currency=factory.Iterator(rates, getter=lambda r: r[1]),
        trading_date=factory.Iterator(rates, getter=lambda r: r[2]),
        exchange_rate=factory.Iterator(rates, getter=lambda r: r[3]),
    )


@pytest.fixture
def category():
    return ReimbursementRequestCategoryFactory.create(label="fertility")


@pytest.fixture
def reimbursement_request_and_cost_breakdown():
    def create_rr_and_cb(
        wallet,
        category,
        rr_amount,
        rr_state=ReimbursementRequestState.NEW,
        rr_category_id="",
        rr_person_receiving_service_id="",
        rr_cost_credit=None,
        total_member_responsibility=0,
        total_employer_responsibility=0,
        copay=0,
        coinsurance=0,
        deductible=0,
        overage_amount=0,
        hra_applied=0,
        should_create_cost_breakdown=True,
        rr_created_at=None,
        cb_created_at=None,
    ):
        if rr_created_at is None:
            rr_created_at = date.today()
        if cb_created_at is None:
            cb_created_at = date.today()

        rr = ReimbursementRequestFactory.create(
            wallet=wallet,
            category=category,
            amount=rr_amount,
            state=rr_state,
            created_at=rr_created_at,
            reimbursement_request_category_id=rr_category_id,
            person_receiving_service_id=rr_person_receiving_service_id,
            cost_credit=rr_cost_credit,
        )
        cost_breakdown = None
        if should_create_cost_breakdown:
            cost_breakdown = CostBreakdownFactory.create(
                wallet_id=wallet.id,
                reimbursement_request_id=rr.id,
                total_member_responsibility=total_member_responsibility,
                copay=copay,
                coinsurance=coinsurance,
                deductible=deductible,
                overage_amount=overage_amount,
                hra_applied=hra_applied,
                total_employer_responsibility=total_employer_responsibility,
                created_at=cb_created_at,
            )

        return rr, cost_breakdown

    return create_rr_and_cb


def test_create_appeal__success(denied_reimbursement_request):
    messages, success, appeal_id = create_appeal(denied_reimbursement_request)

    assert success

    appeal = ReimbursementRequest.query.get(appeal_id)

    assert denied_reimbursement_request.id != appeal.id
    assert denied_reimbursement_request.id == appeal.appeal_of
    assert len(denied_reimbursement_request.sources) == len(appeal.sources)
    assert (
        denied_reimbursement_request.sources[0].user_asset_id
        == appeal.sources[0].user_asset_id
    )
    assert (
        denied_reimbursement_request.reimbursement_wallet_id
        == appeal.reimbursement_wallet_id
    )
    assert (
        denied_reimbursement_request.reimbursement_request_category_id
        == appeal.reimbursement_request_category_id
    )
    assert denied_reimbursement_request.amount == appeal.amount
    assert (
        messages[0].message == "Successfully created reimbursement request for appeal."
    )


def test_create_appeal__invalid_not_denied(valid_reimbursement_request):
    messages, success, appeal_id = create_appeal(valid_reimbursement_request)

    assert success is False
    assert appeal_id is None
    assert messages[0].message == "Cannot appeal a non-denied reimbursement request."


def test_create_appeal__invalid_is_appeal(denied_reimbursement_request):
    messages, success, appeal_id = create_appeal(denied_reimbursement_request)

    assert success

    # appeal the appeal
    appeal = ReimbursementRequest.query.get(appeal_id)
    appeal.state = ReimbursementRequestState.DENIED
    messages, success, appeal_appeal_id = create_appeal(appeal)

    assert success is False
    assert appeal_appeal_id is None
    assert (
        messages[0].message
        == "Cannot appeal a reimbursement request that is an appeal."
    )


def test_create_appeal__failure_create_request(denied_reimbursement_request):
    with patch("wallet.services.reimbursement_request.db.session.flush") as mock_flush:
        mock_flush.side_effect = Exception

        messages, success, appeal_id = create_appeal(denied_reimbursement_request)

        assert success is False
        assert appeal_id is None
        assert messages[0].message == "Unable to create Reimbursement Request record."


def test_create_appeal_auto_processed_rz__success(denied_reimbursement_request):
    denied_reimbursement_request.auto_processed = ReimbursementRequestAutoProcessing.RX
    messages, success, appeal_id = create_appeal(denied_reimbursement_request)

    assert success

    appeal = ReimbursementRequest.query.get(appeal_id)

    assert denied_reimbursement_request.id != appeal.id
    assert denied_reimbursement_request.id == appeal.appeal_of
    assert (
        denied_reimbursement_request.auto_processed
        == ReimbursementRequestAutoProcessing.RX
    )
    assert appeal.auto_processed is None
    assert (
        messages[0].message == "Successfully created reimbursement request for appeal."
    )


class TestReimbursementRequestService:
    def test_create_reimbursement_request_success(
        self,
        db,
        enterprise_user,
        reimbursement_request_data,
        reimbursement_request_service,
    ):
        del reimbursement_request_data["expense_subtype_id"]

        with patch(
            "wallet.services.reimbursement_request.add_reimbursement_request_comment"
        ) as mock_reimbursement_request_comment:
            new_reimbursement_request = (
                reimbursement_request_service.create_reimbursement_request(
                    ReimbursementPostRequest.from_request(reimbursement_request_data),
                    enterprise_user,
                )
            )

            mock_reimbursement_request_comment.assert_called_once()

        reimbursement_request = (
            db.session.query(ReimbursementRequest)
            .filter(ReimbursementRequest.id == new_reimbursement_request.id)
            .one()
        )

        assert reimbursement_request.amount == reimbursement_request_data["amount"]
        assert reimbursement_request.state == ReimbursementRequestState.NEW
        assert reimbursement_request.label == reimbursement_request_data["description"]
        assert (
            reimbursement_request.description
            == reimbursement_request_data["description"]
        )
        assert (
            reimbursement_request.person_receiving_service_id
            == reimbursement_request_data["person_receiving_service_id"]
        )
        assert (
            reimbursement_request.person_receiving_service
            == reimbursement_request_data["person_receiving_service_name"]
        )
        assert len(reimbursement_request.sources) == 2
        assert (
            reimbursement_request.sources[0].source_id
            == reimbursement_request_data["sources"][0]["source_id"]
        )
        assert (
            reimbursement_request.sources[1].source_id
            == reimbursement_request_data["sources"][1]["source_id"]
        )

    def test_create_reimbursement_request_success_subtype(
        self,
        db,
        enterprise_user,
        reimbursement_request_data,
        reimbursement_request_service,
    ):
        with patch(
            "wallet.services.reimbursement_request.add_reimbursement_request_comment"
        ) as mock_reimbursement_request_comment:
            new_reimbursement_request = (
                reimbursement_request_service.create_reimbursement_request(
                    ReimbursementPostRequest.from_request(reimbursement_request_data),
                    enterprise_user,
                )
            )

            mock_reimbursement_request_comment.assert_called_once()

        reimbursement_request = (
            db.session.query(ReimbursementRequest)
            .filter(ReimbursementRequest.id == new_reimbursement_request.id)
            .one()
        )

        assert reimbursement_request.wallet_expense_subtype_id == int(
            reimbursement_request_data["expense_subtype_id"]
        )
        assert reimbursement_request.description == ""

    def test_create_reimbursement_request_populates_currency_amounts(
        self,
        db,
        enterprise_user,
        reimbursement_request_data,
        reimbursement_request_service,
    ):
        # Given fixtures

        # When
        with patch(
            "wallet.services.reimbursement_request.add_reimbursement_request_comment"
        ):
            new_reimbursement_request = (
                reimbursement_request_service.create_reimbursement_request(
                    ReimbursementPostRequest.from_request(reimbursement_request_data),
                    enterprise_user,
                )
            )

        reimbursement_request: ReimbursementRequest = (
            db.session.query(ReimbursementRequest)
            .filter(ReimbursementRequest.id == new_reimbursement_request.id)
            .one()
        )

        # Then
        assert (
            reimbursement_request.amount,
            reimbursement_request.transaction_amount,
            reimbursement_request.usd_amount,
            reimbursement_request.transaction_currency_code,
            reimbursement_request.benefit_currency_code,
            reimbursement_request.transaction_to_benefit_rate,
            reimbursement_request.transaction_to_usd_rate,
        ) == (
            reimbursement_request_data["amount"],
            reimbursement_request_data["amount"],
            reimbursement_request_data["amount"],
            "USD",
            "USD",
            Decimal("1.0"),
            Decimal("1.0"),
        )

    @pytest.mark.parametrize(
        argnames=("currency_code", "exception_string"),
        argvalues=[
            ("", "currency_code can't be empty string"),
            ("      ", "currency_code can't be empty string"),
            (None, "currency_code can't be None"),
        ],
    )
    def test_from_request_validates_currency_code(
        self,
        db,
        enterprise_user,
        reimbursement_request_data,
        reimbursement_request_service,
        currency_code,
        exception_string,
    ):
        # Given
        reimbursement_request_data["currency_code"] = currency_code

        # When - Then
        with pytest.raises(ValueError, match=exception_string):
            ReimbursementPostRequest.from_request(reimbursement_request_data)

    def test_create_reimbursement_request_populates_currency_amounts_legacy_usd_default(
        self,
        db,
        enterprise_user,
        reimbursement_request_data,
        reimbursement_request_service,
    ):
        # Given
        del reimbursement_request_data["currency_code"]

        # When
        with patch(
            "wallet.services.reimbursement_request.add_reimbursement_request_comment"
        ):
            new_reimbursement_request = (
                reimbursement_request_service.create_reimbursement_request(
                    ReimbursementPostRequest.from_request(reimbursement_request_data),
                    enterprise_user,
                )
            )

        reimbursement_request: ReimbursementRequest = (
            db.session.query(ReimbursementRequest)
            .filter(ReimbursementRequest.id == new_reimbursement_request.id)
            .one()
        )

        # Then
        assert (
            reimbursement_request.amount,
            reimbursement_request.transaction_amount,
            reimbursement_request.usd_amount,
            reimbursement_request.transaction_currency_code,
            reimbursement_request.benefit_currency_code,
            reimbursement_request.transaction_to_benefit_rate,
            reimbursement_request.transaction_to_usd_rate,
        ) == (
            reimbursement_request_data["amount"],
            reimbursement_request_data["amount"],
            reimbursement_request_data["amount"],
            "USD",
            "USD",
            Decimal("1.0"),
            Decimal("1.0"),
        )

    @pytest.mark.parametrize(
        argnames=(
            "benefit_currency",
            "transaction_currency",
            "transaction_amount",
            "expected_benefit_amount",
        ),
        argvalues=[
            ("USD", "AUD", 1000, 1500),
            ("USD", "USD", 1000, 1000),
            ("USD", "JPY", 1000, 680),
            ("GBP", "AUD", 1000, 3000),
        ],
    )
    def test_create_reimbursement_request_success_non_usd_transaction(
        self,
        db,
        enterprise_user,
        qualified_alegeus_wallet_hdhp_family: ReimbursementWallet,
        reimbursement_request_data,
        reimbursement_request_service,
        exchange_rates,
        benefit_currency,
        transaction_currency,
        transaction_amount,
        expected_benefit_amount,
    ):
        # Given
        category = qualified_alegeus_wallet_hdhp_family.get_or_create_wallet_allowed_categories[
            0
        ]
        category.currency_code = benefit_currency
        reimbursement_request_data["amount"] = transaction_amount
        reimbursement_request_data["currency_code"] = transaction_currency

        with patch(
            "wallet.services.reimbursement_request.add_reimbursement_request_comment"
        ):
            new_reimbursement_request = (
                reimbursement_request_service.create_reimbursement_request(
                    ReimbursementPostRequest.from_request(reimbursement_request_data),
                    enterprise_user,
                )
            )

        reimbursement_request = (
            db.session.query(ReimbursementRequest)
            .filter(ReimbursementRequest.id == new_reimbursement_request.id)
            .one()
        )

        assert (
            reimbursement_request.amount,
            reimbursement_request.benefit_currency_code,
        ) == (expected_benefit_amount, benefit_currency)

    def test_create_reimbursement_request_invalid_wallet(
        self,
        reimbursement_request_data,
        reimbursement_request_service,
        qualified_alegeus_wallet_hdhp_family,
        enterprise_user,
    ):
        reimbursement_request_data["person_receiving_service_id"] = "2"
        with pytest.raises(ValueError, match=r".*not associated with the wallet.*"):
            reimbursement_request_service.create_reimbursement_request(
                ReimbursementPostRequest.from_request(reimbursement_request_data),
                enterprise_user,
            )

    @pytest.mark.parametrize("invalid_amount", [0, 10000001])
    def test_create_reimbursement_request_invalid_amount(
        self,
        invalid_amount,
        reimbursement_request_data,
        reimbursement_request_service,
        enterprise_user,
    ):
        reimbursement_request_data["amount"] = invalid_amount
        with pytest.raises(
            ValueError, match=r"Amount must be between \$0 and \$100,000 in USD"
        ):
            reimbursement_request_service.create_reimbursement_request(
                ReimbursementPostRequest.from_request(reimbursement_request_data),
                enterprise_user,
            )

    @pytest.mark.parametrize("invalid_source", [[], [{"source_id": "test"}] * 21])
    def test_create_reimbursement_request_invalid_sources(
        self,
        invalid_source,
        reimbursement_request_data,
        reimbursement_request_service,
        enterprise_user,
    ):
        reimbursement_request_data["sources"] = invalid_source
        with pytest.raises(
            ValueError, match="Attachment size must be between 1 and 20"
        ):
            reimbursement_request_service.create_reimbursement_request(
                ReimbursementPostRequest.from_request(reimbursement_request_data),
                enterprise_user,
            )

    def test_create_reimbursement_request_source_already_exists(
        self, reimbursement_request_data, reimbursement_request_service, enterprise_user
    ):
        example_source_data = reimbursement_request_data["sources"][-1]
        ReimbursementRequestSourceFactory.create(
            user_asset_id=example_source_data["source_id"],
            reimbursement_wallet_id=reimbursement_request_data["wallet_id"],
        )
        with pytest.raises(
            ValueError,
            match="1 of these documents are already uploaded to this account",
        ), patch(
            "wallet.services.reimbursement_request.add_reimbursement_request_comment"
        ):
            reimbursement_request_service.create_reimbursement_request(
                ReimbursementPostRequest.from_request(reimbursement_request_data),
                enterprise_user,
            )

    def test_create_reimbursement_request_invalid_service_date(
        self, reimbursement_request_data, reimbursement_request_service, enterprise_user
    ):
        reimbursement_request_data["service_start_date"] = (
            datetime.today() + timedelta(days=1)
        ).strftime("%Y-%m-%d")
        with pytest.raises(ValueError, match=r".*Service date is in the future.*"):
            reimbursement_request_service.create_reimbursement_request(
                ReimbursementPostRequest.from_request(reimbursement_request_data),
                enterprise_user,
            )

    def test_create_reimbursement_request_submitter_not_in_wallet(
        self, reimbursement_request_data, reimbursement_request_service, enterprise_user
    ):
        with pytest.raises(
            ValueError, match="Submitter is not an active user on the wallet"
        ):
            enterprise_user.id = 1
            reimbursement_request_service.create_reimbursement_request(
                ReimbursementPostRequest.from_request(reimbursement_request_data),
                enterprise_user,
            )

    def test_create_reimbursement_request_expense_subtype_without_type(
        self,
        reimbursement_request_data,
        reimbursement_request_service,
        enterprise_user,
        expense_subtypes,
    ):
        reimbursement_request_data["expense_type"] = None
        with pytest.raises(
            ValueError, match="Expense Subtype requires a valid Expense Type"
        ):
            reimbursement_request_service.create_reimbursement_request(
                ReimbursementPostRequest.from_request(reimbursement_request_data),
                enterprise_user,
            )

    def test_create_reimbursement_request_expense_type_subtype_mismatch(
        self,
        reimbursement_request_data,
        reimbursement_request_service,
        enterprise_user,
        expense_subtypes,
    ):
        reimbursement_request_data["expense_type"] = "Fertility"
        reimbursement_request_data["expense_subtype_id"] = str(
            expense_subtypes["ALF"].id
        )

        with patch(
            "wallet.services.reimbursement_request.add_reimbursement_request_comment"
        ) as mock_reimbursement_request_comment, pytest.raises(
            ValueError, match="Expense Subtype is not valid for this Expense Type"
        ):
            reimbursement_request_service.create_reimbursement_request(
                ReimbursementPostRequest.from_request(reimbursement_request_data),
                enterprise_user,
            )

            mock_reimbursement_request_comment.assert_called_once()

    def test_get_available_currencies(self, reimbursement_request_service):
        # Given
        mock_repo_return_value = [
            {"currency_code": "USD", "minor_unit": 2},
            {"currency_code": "GBP", "minor_unit": 2},
        ]

        # When
        with mock.patch(
            "wallet.repository.currency_fx_rate.CurrencyFxRateRepository.get_available_currency_and_minor_units"
        ) as mock_get_available_currency_and_minor_units:
            mock_get_available_currency_and_minor_units.return_value = (
                mock_repo_return_value
            )
            available_currencies = (
                reimbursement_request_service.get_available_currencies()
            )

        # Then
        assert available_currencies == [
            {"currency_code": "GBP", "minor_unit": 2, "display_name": "Pound Sterling"},
            {"currency_code": "USD", "minor_unit": 2, "display_name": "US Dollar"},
        ]

    def test_get_available_currencies_is_sorted(self, reimbursement_request_service):
        # Given
        mock_repo_return_value = [
            {"currency_code": "USD", "minor_unit": 2},
            {"currency_code": "AUD", "minor_unit": 2},
            {"currency_code": "NZD", "minor_unit": 2},
        ]

        # When
        with mock.patch(
            "wallet.repository.currency_fx_rate.CurrencyFxRateRepository.get_available_currency_and_minor_units"
        ) as mock_get_available_currency_and_minor_units:
            mock_get_available_currency_and_minor_units.return_value = (
                mock_repo_return_value
            )
            available_currencies = (
                reimbursement_request_service.get_available_currencies()
            )

        # Then
        assert available_currencies == [
            {
                "currency_code": "AUD",
                "minor_unit": 2,
                "display_name": "Australian Dollar",
            },
            {
                "currency_code": "NZD",
                "minor_unit": 2,
                "display_name": "New Zealand Dollar",
            },
            {"currency_code": "USD", "minor_unit": 2, "display_name": "US Dollar"},
        ]

    def test_get_available_currencies_exception(self, reimbursement_request_service):
        # Given
        mock_repo_return_value = [{"currency_code": "USD", "minor_unit": 2}]

        # When
        with mock.patch(
            "wallet.repository.currency_fx_rate.CurrencyFxRateRepository.get_available_currency_and_minor_units"
        ) as mock_get_available_currency_and_minor_units, mock.patch(
            "pycountry.currencies.get"
        ) as mock_get:
            mock_get_available_currency_and_minor_units.return_value = (
                mock_repo_return_value
            )
            mock_get.side_effect = Exception("Some exception thrown by pycountry")
            available_currencies = (
                reimbursement_request_service.get_available_currencies()
            )

        # Then
        assert available_currencies == [
            {"currency_code": "USD", "minor_unit": 2, "display_name": "USD"}
        ]

    def test_create_reimbursement_request_success_document_mapping(
        self,
        db,
        enterprise_user,
        reimbursement_request_data,
        reimbursement_request_service,
    ):
        document_mapping_uuid = factory.Faker("uuid4")
        reimbursement_request_data["document_mapping_uuid"] = document_mapping_uuid
        with patch(
            "wallet.services.reimbursement_request.add_reimbursement_request_comment"
        ) as mock_reimbursement_request_comment:
            new_reimbursement_request = (
                reimbursement_request_service.create_reimbursement_request(
                    ReimbursementPostRequest.from_request(reimbursement_request_data),
                    enterprise_user,
                )
            )

            mock_reimbursement_request_comment.assert_called_once()

        reimbursement_request = (
            db.session.query(ReimbursementRequest)
            .filter(ReimbursementRequest.id == new_reimbursement_request.id)
            .one()
        )
        assert (
            reimbursement_request.sources[0].source_id
            == reimbursement_request_data["sources"][0]["source_id"]
        )
        assert (
            reimbursement_request.sources[0].document_mapping_uuid
            == document_mapping_uuid
        )
        assert (
            reimbursement_request.sources[1].source_id
            == reimbursement_request_data["sources"][1]["source_id"]
        )
        assert (
            reimbursement_request.sources[1].document_mapping_uuid
            == document_mapping_uuid
        )

    def test_create_reimbursement_request_success_cost_share_breakdown_enabled(
        self,
        enterprise_user,
        reimbursement_request_data,
        reimbursement_request_service,
        patch_braze_send_event,
    ):
        with patch(
            "wallet.services.reimbursement_request.add_reimbursement_request_comment"
        ) as mock_reimbursement_request_comment, patch(
            "wallet.services.reimbursement_request.ReimbursementRequestService.is_cost_share_breakdown_applicable",
            return_value=True,
        ):

            reimbursement_request_service.create_reimbursement_request(
                ReimbursementPostRequest.from_request(reimbursement_request_data),
                enterprise_user,
            )

            mock_reimbursement_request_comment.assert_called_once()

        patch_braze_send_event.assert_called_once_with(
            user=enterprise_user,
            event_name="reimbursement_request_created_new",
            event_data={
                "member_type": MemberType.MAVEN_GOLD.value,
                "prev_state": None,
                "new_state": ReimbursementRequestState.NEW.value,
            },
        )

    def test_create_reimbursement_request_success_cost_share_breakdown_disabled(
        self,
        enterprise_user,
        reimbursement_request_data,
        reimbursement_request_service,
        patch_braze_send_event,
    ):
        with patch(
            "wallet.services.reimbursement_request.add_reimbursement_request_comment"
        ) as mock_reimbursement_request_comment, patch(
            "wallet.services.reimbursement_request.ReimbursementRequestService.is_cost_share_breakdown_applicable",
            return_value=False,
        ):

            reimbursement_request_service.create_reimbursement_request(
                ReimbursementPostRequest.from_request(reimbursement_request_data),
                enterprise_user,
            )

            mock_reimbursement_request_comment.assert_called_once()

        patch_braze_send_event.assert_not_called()

    def test_get_latest_cost_breakdowns_by_reimbursement_request(
        self, reimbursement_request_service, reimbursement_requests, cost_breakdowns
    ):
        latest_cost_breakdowns_by_rr = reimbursement_request_service.get_latest_cost_breakdowns_by_reimbursement_request(
            reimbursement_requests=reimbursement_requests
        )
        assert len(latest_cost_breakdowns_by_rr) == len(reimbursement_requests)
        for rr in reimbursement_requests:
            latest_cb = latest_cost_breakdowns_by_rr[rr.id]
            assert latest_cb.created_at.date() == date.today()
            assert latest_cb.total_member_responsibility == 25000

    def test_get_latest_cost_breakdowns_by_reimbursement_request_empty_input(
        self,
        reimbursement_request_service,
    ):

        latest_cost_breakdowns_by_rr = reimbursement_request_service.get_latest_cost_breakdowns_by_reimbursement_request(
            reimbursement_requests=[]
        )
        assert latest_cost_breakdowns_by_rr == {}

    def test_get_latest_cost_breakdowns(
        self, reimbursement_request_service, reimbursement_requests, cost_breakdowns
    ):
        latest_cost_breakdowns = (
            reimbursement_request_service.get_latest_cost_breakdowns(
                reimbursement_requests=reimbursement_requests
            )
        )

        assert len(latest_cost_breakdowns) == len(reimbursement_requests)

        for cb in latest_cost_breakdowns:
            assert cb.created_at.date() == date.today()

    def test_get_latest_cost_breakdowns_empty_input(
        self, reimbursement_request_service
    ):
        latest_cost_breakdowns = (
            reimbursement_request_service.get_latest_cost_breakdowns(
                reimbursement_requests=[]
            )
        )
        assert latest_cost_breakdowns == []

    @pytest.mark.parametrize(
        argnames=(
            "country_code",
            "subdivision_code",
            "direct_payment_enabled",
            "deductible_accumulation_enabled",
            "expected_value",
        ),
        argvalues=[
            ("FR", "", True, True, False),
            ("US", "US-NY", True, False, False),
            ("US", "US-NY", False, True, False),
            ("US", "US-NY", True, True, True),
        ],
    )
    def test_is_cost_share_breakdown_applicable(
        self,
        reimbursement_request_service,
        qualified_alegeus_wallet_hdhp_single,
        country_code,
        subdivision_code,
        direct_payment_enabled,
        deductible_accumulation_enabled,
        expected_value,
        ff_test_data,
    ):
        enterprise_user = qualified_alegeus_wallet_hdhp_single.employee_member
        enterprise_user.profile.country_code = country_code
        enterprise_user.profile.subdivision_code = subdivision_code
        qualified_alegeus_wallet_hdhp_single.primary_expense_type = (
            ReimbursementRequestExpenseTypes.FERTILITY
        )
        qualified_alegeus_wallet_hdhp_single.reimbursement_organization_settings.direct_payment_enabled = (
            direct_payment_enabled
        )
        qualified_alegeus_wallet_hdhp_single.reimbursement_organization_settings.deductible_accumulation_enabled = (
            deductible_accumulation_enabled
        )
        is_cost_share_breakdown_applicable = (
            reimbursement_request_service.is_cost_share_breakdown_applicable(
                wallet=qualified_alegeus_wallet_hdhp_single
            )
        )
        assert is_cost_share_breakdown_applicable is expected_value

    def test_add_cost_share_details(
        self,
        reimbursement_request_service,
        reimbursement_requests,
        qualified_alegeus_wallet_hdhp_single,
        category,
    ):
        rr_properties = [
            {"state": ReimbursementRequestState.NEW, "amount": 1000},
            {"state": ReimbursementRequestState.PENDING, "amount": 30000},
            {"state": ReimbursementRequestState.REFUNDED, "amount": 250099},
        ]
        for curr, rr in enumerate(reimbursement_requests):
            rr.state = rr_properties[curr]["state"]
            rr.amount = rr_properties[curr]["amount"]

        # add cost breakdowns for some reimbursement requests

        CostBreakdownFactory.create(
            wallet_id=qualified_alegeus_wallet_hdhp_single.id,
            reimbursement_request_id=reimbursement_requests[1].id,
            total_member_responsibility=10000,
            total_employer_responsibility=20000,
            created_at=date.today(),
        )
        CostBreakdownFactory.create(
            wallet_id=qualified_alegeus_wallet_hdhp_single.id,
            reimbursement_request_id=reimbursement_requests[2].id,
            total_member_responsibility=20000,
            total_employer_responsibility=230099,
            created_at=date.today(),
        )

        ineligible_expense_reimbursement = ReimbursementRequestFactory.create(
            wallet=qualified_alegeus_wallet_hdhp_single,
            category=category,
            amount=7705,
            state=ReimbursementRequestState.DENIED,
        )

        denied_reimbursement = ReimbursementRequestFactory.create(
            wallet=qualified_alegeus_wallet_hdhp_single,
            category=category,
            amount=10000,
            state=ReimbursementRequestState.INELIGIBLE_EXPENSE,
        )

        CostBreakdownFactory.create(
            wallet_id=qualified_alegeus_wallet_hdhp_single.id,
            reimbursement_request_id=ineligible_expense_reimbursement.id,
            total_member_responsibility=15000,
            total_employer_responsibility=230099,
            created_at=date.today(),
        )

        all_requests = reimbursement_requests + [
            ineligible_expense_reimbursement,
            denied_reimbursement,
        ]

        reimbursement_request_service.add_cost_share_details(all_requests)

        assert all_requests[0].cost_share_details == {
            "original_claim_amount": "$10.00",
            "reimbursement_amount": None,
            "reimbursement_expected_message": "Your expenses have been received. Family building services can be subject to coinsurance, copay, and deductible. If you have financial responsibility towards this claim, our care team will calculate this when they review your claim. It will be deducted from the amount reimbursed to you.",
        }

        assert all_requests[1].cost_share_details == {
            "original_claim_amount": "$300.00",
            "reimbursement_amount": "$200.00",
            "reimbursement_expected_message": None,
        }

        assert all_requests[2].cost_share_details == {
            "original_claim_amount": "$2,500.99",
            "reimbursement_amount": "$2,300.99",
            "reimbursement_expected_message": None,
        }

        assert all_requests[3].cost_share_details == {
            "original_claim_amount": "$2,450.99",
            "reimbursement_amount": "$0.00",
            "reimbursement_expected_message": None,
        }

        assert all_requests[4].cost_share_details is None

    def test_get_reimbursement_request_with_cost_breakdown_details_no_cost_breakdown(
        self,
        reimbursement_request_service,
        qualified_alegeus_wallet_hdhp_single,
        category,
        reimbursement_request_and_cost_breakdown,
    ):

        rr, _ = reimbursement_request_and_cost_breakdown(
            wallet=qualified_alegeus_wallet_hdhp_single,
            category=category,
            rr_amount=7705,
            should_create_cost_breakdown=False,
        )

        result = reimbursement_request_service.get_reimbursement_request_with_cost_breakdown_details(
            rr
        )

        assert result["cost_breakdown_details"]["reimbursement_breakdown"] is None
        assert result["cost_breakdown_details"]["credits_details"] is None
        assert result["cost_breakdown_details"]["refund_explanation"] is None
        assert (
            result["cost_breakdown_details"]["member_responsibility_breakdown"] is None
        )
        assert result["original_claim_amount"] == "$77.05"
        assert result["id"] == str(rr.id)
        assert result["created_at_date_formatted"] == date.today().strftime("%B %d, %Y")

    def test_get_reimbursement_request_with_cost_breakdown_details_with_cost_breakdown(
        self,
        reimbursement_request_service,
        qualified_alegeus_wallet_hdhp_single,
        category,
        reimbursement_request_and_cost_breakdown,
    ):
        rr, _ = reimbursement_request_and_cost_breakdown(
            wallet=qualified_alegeus_wallet_hdhp_single,
            category=category,
            rr_amount=90000,
            rr_created_at=date.today() - timedelta(days=15),
            total_member_responsibility=50000,
            copay=15000,
            coinsurance=10000,
            deductible=20000,
            overage_amount=5000,
            hra_applied=5000,
            total_employer_responsibility=40000,
        )

        # creating two cost breakdowns to ensure we use latest for calculations
        CostBreakdownFactory.create(
            wallet_id=qualified_alegeus_wallet_hdhp_single.id,
            reimbursement_request_id=rr.id,
            total_member_responsibility=90000,
            total_employer_responsibility=0,
            created_at=date.today() - timedelta(days=10),
        )

        expected_items = [
            {"label": "Deductible", "cost": "$200.00"},
            {"label": "Coinsurance", "cost": "$100.00"},
            {"label": "Copay", "cost": "$150.00"},
            {"label": "Not covered", "cost": "$50.00"},
            {"label": "HRA applied", "cost": "-$50.00"},
        ]

        result = reimbursement_request_service.get_reimbursement_request_with_cost_breakdown_details(
            rr
        )

        assert result["cost_breakdown_details"]["reimbursement_breakdown"] is not None
        assert (
            result["cost_breakdown_details"]["reimbursement_breakdown"]["title"]
            == "Expected reimbursement"
        )
        assert (
            result["cost_breakdown_details"]["reimbursement_breakdown"]["total_cost"]
            == "$400.00"
        )
        assert result["original_claim_amount"] == "$900.00"
        assert (
            result["cost_breakdown_details"]["member_responsibility_breakdown"][
                "total_cost"
            ]
            == "$500.00"
        )
        assert (
            result["cost_breakdown_details"]["member_responsibility_breakdown"]["items"]
            == expected_items
        )
        assert result["id"] == str(rr.id)
        assert result["created_at_date_formatted"] == date.today().strftime("%B %d, %Y")
        assert result["cost_breakdown_details"]["refund_explanation"] is not None

    def test_get_reimbursement_request_with_cost_breakdown_details_with_cost_breakdown_no_service_end_date(
        self,
        reimbursement_request_service,
        qualified_alegeus_wallet_hdhp_single,
        category,
        reimbursement_request_and_cost_breakdown,
    ):
        rr, _ = reimbursement_request_and_cost_breakdown(
            wallet=qualified_alegeus_wallet_hdhp_single,
            category=category,
            rr_amount=90000,
            rr_created_at=date.today() - timedelta(days=15),
            total_member_responsibility=50000,
            copay=15000,
            coinsurance=10000,
            deductible=20000,
            overage_amount=5000,
            total_employer_responsibility=40000,
        )
        rr.service_end_date = None

        # creating two cost breakdowns to ensure we use latest for calculations
        CostBreakdownFactory.create(
            wallet_id=qualified_alegeus_wallet_hdhp_single.id,
            reimbursement_request_id=rr.id,
            total_member_responsibility=90000,
            total_employer_responsibility=0,
            created_at=date.today() - timedelta(days=10),
        )

        # When
        result = reimbursement_request_service.get_reimbursement_request_with_cost_breakdown_details(
            rr
        )

        # Then
        assert result["service_end_date"] is None

    def test_get_reimbursement_request_with_cost_breakdown_details_with_cost_breakdown_reimbursed(
        self,
        reimbursement_request_service,
        qualified_alegeus_wallet_hdhp_single,
        category,
        reimbursement_request_and_cost_breakdown,
    ):

        rr, _ = reimbursement_request_and_cost_breakdown(
            wallet=qualified_alegeus_wallet_hdhp_single,
            category=category,
            rr_amount=90000,
            rr_state=ReimbursementRequestState.REIMBURSED,
            total_member_responsibility=50000,
            copay=15000,
            coinsurance=10000,
            deductible=20000,
            overage_amount=5000,
            total_employer_responsibility=40000,
        )

        result = reimbursement_request_service.get_reimbursement_request_with_cost_breakdown_details(
            rr
        )

        assert result["cost_breakdown_details"]["reimbursement_breakdown"] is not None
        assert (
            result["cost_breakdown_details"]["reimbursement_breakdown"]["title"]
            == "Reimbursement"
        )
        assert (
            result["cost_breakdown_details"]["reimbursement_breakdown"]["total_cost"]
            == "$400.00"
        )
        assert result["original_claim_amount"] == "$900.00"
        assert (
            result["cost_breakdown_details"]["member_responsibility_breakdown"][
                "total_cost"
            ]
            == "$500.00"
        )

    def test_get_reimbursement_request_with_cost_breakdown_details_with_no_cost_breakdown_reimbursed(
        self,
        reimbursement_request_service,
        qualified_alegeus_wallet_hdhp_single,
        category,
        reimbursement_request_and_cost_breakdown,
    ):
        rr, _ = reimbursement_request_and_cost_breakdown(
            wallet=qualified_alegeus_wallet_hdhp_single,
            category=category,
            rr_amount=90000,
            rr_state=ReimbursementRequestState.REIMBURSED,
            should_create_cost_breakdown=False,
        )

        result = reimbursement_request_service.get_reimbursement_request_with_cost_breakdown_details(
            rr
        )

        assert result["cost_breakdown_details"]["reimbursement_breakdown"] is not None
        assert (
            result["cost_breakdown_details"]["reimbursement_breakdown"]["title"]
            == "Reimbursement"
        )
        assert (
            result["cost_breakdown_details"]["reimbursement_breakdown"]["total_cost"]
            == "$900.00"
        )
        assert result["original_claim_amount"] == "$900.00"
        assert result["cost_breakdown_details"]["refund_explanation"] is None

    def test_get_reimbursement_request_with_cost_breakdown_details_cycle_based_wallet_with_credits(
        self,
        reimbursement_request_service,
        wallet_cycle_based,
        reimbursement_request_and_cost_breakdown,
    ):
        assoc_category = wallet_cycle_based.reimbursement_organization_settings.allowed_reimbursement_categories[
            0
        ]
        category = assoc_category.reimbursement_request_category

        credits_used = 1

        rr, _ = reimbursement_request_and_cost_breakdown(
            wallet=wallet_cycle_based,
            category=category,
            rr_amount=100,
            rr_state=ReimbursementRequestState.APPROVED,
            rr_category_id=category.id,
            rr_person_receiving_service_id=wallet_cycle_based.user_id,
            rr_cost_credit=credits_used,
            total_member_responsibility=50000,
            copay=15000,
            coinsurance=10000,
            deductible=20000,
            overage_amount=5000,
            total_employer_responsibility=40000,
        )

        result = reimbursement_request_service.get_reimbursement_request_with_cost_breakdown_details(
            rr
        )

        credits_details = result["cost_breakdown_details"]["credits_details"]
        assert credits_details["credits_used_formatted"] == "1 credit"
        assert credits_details["credits_used"] == credits_used

    @pytest.mark.parametrize(
        argnames=(
            "has_cost_breakdown",
            "rr_state",
            "expected_title",
            "expected_reimbursement_amount",
        ),
        argvalues=[
            (
                True,
                ReimbursementRequestState.PENDING,
                "Expected reimbursement",
                "$50.00",
            ),
            (True, ReimbursementRequestState.REIMBURSED, "Reimbursement", "$50.00"),
            (True, ReimbursementRequestState.DENIED, "Reimbursement", "$0.00"),
            (False, ReimbursementRequestState.PENDING, None, None),
            (False, ReimbursementRequestState.REIMBURSED, "Reimbursement", "$100.00"),
            (False, ReimbursementRequestState.DENIED, "Reimbursement", "$0.00"),
        ],
    )
    def test__create_reimbursement_breakdown_obj(
        self,
        reimbursement_request_service,
        qualified_alegeus_wallet_hdhp_single,
        category,
        has_cost_breakdown,
        rr_state,
        expected_title,
        expected_reimbursement_amount,
        reimbursement_request_and_cost_breakdown,
    ):
        (
            reimbursement_request,
            cost_breakdown,
        ) = reimbursement_request_and_cost_breakdown(
            wallet=qualified_alegeus_wallet_hdhp_single,
            category=category,
            rr_amount=10000,
            rr_state=rr_state,
            should_create_cost_breakdown=has_cost_breakdown,
            total_member_responsibility=5000,
            copay=5000,
            coinsurance=0,
            deductible=0,
            overage_amount=0,
            total_employer_responsibility=5000,
        )

        result = reimbursement_request_service._create_reimbursement_breakdown_obj(
            reimbursement_request, cost_breakdown
        )
        if expected_title is not None:
            assert result["title"] == expected_title
            assert result["total_cost"] == expected_reimbursement_amount
        else:
            assert result is None

    @pytest.mark.parametrize(
        argnames=("has_cost_breakdown"),
        argvalues=[(True), (False)],
    )
    def test__create_member_responsibility_breakdown_obj(
        self,
        reimbursement_request_service,
        category,
        qualified_alegeus_wallet_hdhp_single,
        has_cost_breakdown,
        reimbursement_request_and_cost_breakdown,
    ):
        _, cost_breakdown = reimbursement_request_and_cost_breakdown(
            wallet=qualified_alegeus_wallet_hdhp_single,
            category=category,
            rr_amount=60000,
            rr_state=ReimbursementRequestState.APPROVED,
            should_create_cost_breakdown=has_cost_breakdown,
            total_member_responsibility=30000,
            copay=10000,
            coinsurance=10000,
            deductible=5000,
            overage_amount=5000,
            hra_applied=5000,
            total_employer_responsibility=30000,
        )

        result = (
            reimbursement_request_service._create_member_responsibility_breakdown_obj(
                cost_breakdown
            )
        )

        if has_cost_breakdown:
            assert result is not None
            assert result["total_cost"] == "$300.00"
            expected_items = [
                {"label": "Deductible", "cost": "$50.00"},
                {"label": "Coinsurance", "cost": "$100.00"},
                {"label": "Copay", "cost": "$100.00"},
                {"label": "Not covered", "cost": "$50.00"},
                {"label": "HRA applied", "cost": "-$50.00"},
            ]
            assert result["items"] == expected_items
        else:
            assert result is None

    @pytest.mark.parametrize(
        argnames=("has_cost_breakdown", "is_cycle_based_wallet", "credits_used"),
        argvalues=[
            (True, True, 1),
            (True, True, 2),
            (True, False, None),
            (False, False, None),
            (False, True, None),
        ],
    )
    def test__create_credits_details_obj(
        self,
        reimbursement_request_service,
        qualified_alegeus_wallet_hdhp_single,
        category,
        has_cost_breakdown,
        is_cycle_based_wallet,
        credits_used,
        reimbursement_request_and_cost_breakdown,
    ):

        (
            reimbursement_request,
            cost_breakdown,
        ) = reimbursement_request_and_cost_breakdown(
            wallet=qualified_alegeus_wallet_hdhp_single,
            category=category,
            rr_amount=60000,
            rr_cost_credit=credits_used,
            rr_state=ReimbursementRequestState.APPROVED,
            total_member_responsibility=0,
            copay=0,
            coinsurance=0,
            deductible=0,
            overage_amount=0,
            total_employer_responsibility=10000,
            should_create_cost_breakdown=has_cost_breakdown,
        )

        result = reimbursement_request_service._create_credits_details_obj(
            bool(cost_breakdown), is_cycle_based_wallet, reimbursement_request
        )

        if has_cost_breakdown and is_cycle_based_wallet:
            assert result is not None
            assert result["credits_used"] == credits_used

            if credits_used == 1:
                assert result["credits_used_formatted"] == f"{credits_used} credit"
            else:
                assert result["credits_used_formatted"] == f"{credits_used} credits"
        else:
            assert result is None

    @pytest.mark.parametrize(
        argnames=("has_cost_breakdown", "employer_responsibility", "rr_amount"),
        argvalues=[
            (True, 100, 100),
            (True, 60, 100),
            (True, 160, 100),
            (False, 100, 100),
        ],
    )
    def test__create_refund_explanation_obj(
        self,
        reimbursement_request_service,
        qualified_alegeus_wallet_hdhp_single,
        category,
        has_cost_breakdown,
        employer_responsibility,
        rr_amount,
        reimbursement_request_and_cost_breakdown,
    ):

        _, cost_breakdown = reimbursement_request_and_cost_breakdown(
            wallet=qualified_alegeus_wallet_hdhp_single,
            category=category,
            rr_amount=rr_amount,
            rr_state=ReimbursementRequestState.PENDING_MEMBER_INPUT,
            total_employer_responsibility=employer_responsibility,
            should_create_cost_breakdown=has_cost_breakdown,
        )

        result = reimbursement_request_service._create_refund_explanation_obj(
            cost_breakdown, rr_amount
        )

        if has_cost_breakdown and employer_responsibility < rr_amount:
            assert result is not None
            assert result["label"] == "Why do I only receive a partial refund?"
            assert len(result["content"]) == 2
        else:
            assert result is None
