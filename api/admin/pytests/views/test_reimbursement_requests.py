from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal
from unittest import mock
from unittest.mock import MagicMock
from uuid import UUID

import pytest
import wtforms

from admin.views.models.wallet import (
    ConvertedReimbursementRequestForm,
    CustomRateForm,
    ReimbursementRequestsView,
    TransactionAmountForm,
    benefit_amount_formatter,
    transaction_amount_formatter,
)
from common.document_mapper.models import (
    DocumentMappingFeedback,
    ReceiptExtractionDocumentMapping,
    ReceiptExtractionDocumentMappingWithFeedback,
)
from wallet.models.constants import (
    ReimbursementRequestExpenseTypes,
    ReimbursementRequestState,
)
from wallet.models.currency import Money
from wallet.models.reimbursement import ReimbursementRequest
from wallet.pytests.conftest import expense_subtypes  # noqa: F401
from wallet.pytests.factories import (
    ReimbursementRequestFactory,
    ReimbursementRequestSourceFactory,
    ReimbursementWalletFactory,
)
from wallet.services.currency import CurrencyService


@pytest.fixture(scope="function")
def mock_flash():
    with mock.patch("flask_admin.model.base.flash"):
        yield


class TestTransactionAmountForm:
    @staticmethod
    @pytest.mark.parametrize(
        argnames=("amount", "currency_code", "expected_is_valid"),
        argvalues=[
            (Decimal("1.00"), "USD", True),
            (None, "USD", False),
            (Decimal("1.00"), None, False),
            (None, None, False),
        ],
    )
    def test_required_fields(
        amount: Decimal, currency_code: str, expected_is_valid: bool
    ):
        # Given
        form = TransactionAmountForm()
        # Empty form
        form.amount.data = amount
        form.currency_code.data = currency_code

        # When
        is_valid: bool = form.validate()

        # Then
        assert is_valid == expected_is_valid

    @staticmethod
    def test_get_money_amount():
        # Given
        form = TransactionAmountForm()
        # Empty form
        amount = Decimal("1.00")
        currency_code: str = "USD"

        form.amount.data = amount
        form.currency_code.data = currency_code

        expected_money = Money(amount=amount, currency_code=currency_code)

        # When
        money: Money = form.get_money_amount()

        # Then
        assert money == expected_money

    @staticmethod
    @pytest.mark.parametrize(
        argnames=("form_input", "exception_string"),
        argvalues=[
            (
                {"amount": None, "currency_code": "USD"},
                "'Transaction Amount' is required",
            ),
            (
                {"amount": Decimal("1.00"), "currency_code": None},
                "'Transaction Currency Code' is required",
            ),
        ],
        ids=[
            "amount-is-null-currency-code-populated",
            "amount-is-populated-currency-code-is-null",
        ],
    )
    def test_get_money_amount_with_null_amount_raises_exception(
        form_input: dict, exception_string: str
    ):
        # Given
        form = TransactionAmountForm(**form_input)

        # When - Then
        with pytest.raises(ValueError, match=exception_string):
            form.get_money_amount()

    @staticmethod
    def test_on_form_prefill_request_without_transaction_amount_and_currency_code(
        currency_service: CurrencyService,
    ):
        """Test that the form properly handles the transactions persisted before the inception of transaction_amount"""
        # Given
        form = TransactionAmountForm()
        request = ReimbursementRequest(amount=100)
        expected_decimal_amount = Decimal("1.00")
        expected_currency_code = "USD"
        money_amount = Money(
            amount=expected_decimal_amount, currency_code=expected_currency_code
        )
        expected_form_values = (expected_decimal_amount, expected_currency_code)

        # When
        with mock.patch(
            "wallet.services.currency.CurrencyService.to_money"
        ) as mock_to_money:
            mock_to_money.return_value = money_amount

            form.on_form_prefill(
                currency_service=currency_service, reimbursement_request=request
            )

        # Then
        assert (form.amount.data, form.currency_code.data) == expected_form_values

    @staticmethod
    def test_on_form_prefill_request_without_transaction_amount_and_currency_code_calls_to_money(
        currency_service: CurrencyService,
    ):
        """Test that the right amount is used to call to_money with when transaction_amount doesn't exist"""
        # Given
        form = TransactionAmountForm()
        request = ReimbursementRequest(amount=100)
        expected_decimal_amount = Decimal("1.00")
        expected_currency_code = "USD"
        money_amount = Money(
            amount=expected_decimal_amount, currency_code=expected_currency_code
        )

        # When
        with mock.patch(
            "wallet.services.currency.CurrencyService.to_money"
        ) as mock_to_money:
            mock_to_money.return_value = money_amount

            form.on_form_prefill(
                currency_service=currency_service, reimbursement_request=request
            )

        # Then
        mock_to_money.assert_called_with(amount=request.amount, currency_code="USD")

    @staticmethod
    def test_on_form_prefill_request_with_transaction_amount_and_currency_code(
        currency_service: CurrencyService,
    ):
        """Test that the form properly handles the transactions persisted after the inception of transaction_amount"""
        # Given
        form = TransactionAmountForm()
        request = ReimbursementRequest(
            transaction_amount=100, transaction_currency_code="USD"
        )
        expected_decimal_amount = Decimal("1.00")
        expected_currency_code = "USD"
        money_amount = Money(
            amount=expected_decimal_amount, currency_code=expected_currency_code
        )
        expected_form_values = (expected_decimal_amount, expected_currency_code)

        # When
        with mock.patch(
            "wallet.services.currency.CurrencyService.to_money"
        ) as mock_to_money:
            mock_to_money.return_value = money_amount

            form.on_form_prefill(
                currency_service=currency_service, reimbursement_request=request
            )

        # Then
        assert (form.amount.data, form.currency_code.data) == expected_form_values

    @staticmethod
    def test_on_form_prefill_request_with_transaction_amount_and_currency_code_calls_to_money(
        currency_service: CurrencyService,
    ):
        """Test that the right amount is used to call to_money with when transaction_amount exists"""
        # Given
        form = TransactionAmountForm()
        request = ReimbursementRequest(
            transaction_amount=100, transaction_currency_code="USD"
        )
        expected_decimal_amount = Decimal("1.00")
        expected_currency_code = "USD"
        money_amount = Money(
            amount=expected_decimal_amount, currency_code=expected_currency_code
        )

        # When
        with mock.patch(
            "wallet.services.currency.CurrencyService.to_money"
        ) as mock_to_money:
            mock_to_money.return_value = money_amount

            form.on_form_prefill(
                currency_service=currency_service, reimbursement_request=request
            )

        # Then
        mock_to_money.assert_called_with(
            amount=request.transaction_amount,
            currency_code=request.transaction_currency_code,
        )


class TestCustomRateForm:
    @staticmethod
    @pytest.mark.parametrize(
        argnames=("use_custom_rate", "custom_rate", "expected_is_valid"),
        argvalues=[
            (False, None, True),
            (False, Decimal("1.00"), True),
            (True, None, False),
            (True, Decimal("1.00"), True),
        ],
    )
    def test_required_fields(
        use_custom_rate: bool, custom_rate: Decimal, expected_is_valid: bool
    ):
        # Given
        form = CustomRateForm()
        # Empty form
        form.use_custom_rate.data = use_custom_rate
        form.custom_rate.data = custom_rate

        # When
        with mock.patch("admin.views.models.wallet.flash"):
            is_valid: bool = form.validate()

        # Then
        assert is_valid == expected_is_valid

    @staticmethod
    @pytest.mark.parametrize(
        argnames=("use_custom_rate", "custom_rate"),
        argvalues=[
            (True, Decimal("2.23")),
            (False, None),
        ],
    )
    def test_on_form_prefill_use_custom_rate(
        use_custom_rate: bool, custom_rate: Decimal | None
    ):
        """Test that the form properly handles when use_custom_rate is True"""
        # Given
        form = CustomRateForm()

        request = ReimbursementRequest(
            use_custom_rate=use_custom_rate, transaction_to_usd_rate=custom_rate
        )

        # When
        form.on_form_prefill(reimbursement_request=request)

        # Then
        assert (form.use_custom_rate.data, form.custom_rate.data) == (
            use_custom_rate,
            custom_rate,
        )

    @staticmethod
    @pytest.mark.parametrize(
        argnames=("use_custom_rate", "custom_rate", "expected"),
        argvalues=[
            (True, Decimal("1.00"), Decimal("1.00")),
            (False, Decimal("1.00"), None),
            (False, None, None),
        ],
    )
    def test_get_custom_rate(
        use_custom_rate: bool, custom_rate: Decimal | None, expected: Decimal | None
    ):
        # Given
        form = CustomRateForm()
        form.use_custom_rate.data = use_custom_rate
        form.custom_rate.data = custom_rate

        # When
        custom_rate: Decimal | None = form.get_custom_rate()

        # Then
        assert custom_rate == expected


class TestConvertedReimbursementRequestForm:
    @staticmethod
    def test_all_fields_are_optional():
        # Given
        form = ConvertedReimbursementRequestForm()
        fields = [
            "transaction_amount_with_currency",
            "benefit_amount_with_currency",
            "usd_amount",
            "transaction_to_usd_rate",
            "transaction_to_benefit_rate",
        ]

        # Set all of the values to None
        for field_name in fields:
            field: wtforms.Field = getattr(form, field_name)
            field.data = None

        # When
        is_valid: bool = form.validate()

        # Then
        assert is_valid is True

    @staticmethod
    def test_on_form_prefill_has_transaction_field(currency_service: CurrencyService):
        # Given
        form = ConvertedReimbursementRequestForm()
        benefit_amount: int = 100
        transaction_amount: int = 200
        transaction_currency: str = "AUD"
        request = ReimbursementRequest(
            amount=benefit_amount,
            benefit_currency_code="USD",
            transaction_amount=transaction_amount,
            transaction_currency_code=transaction_currency,
        )
        expected_data: str = "show me the money"

        # When
        with mock.patch(
            "wallet.services.currency.CurrencyService.to_money"
        ), mock.patch(
            "admin.views.models.wallet.format_display_amount_with_full_currency_name"
        ) as mock_format:
            mock_format.return_value = expected_data
            form.on_form_prefill(
                currency_service=currency_service, reimbursement_request=request
            )

        # Then
        assert form.transaction_amount_with_currency.data == expected_data

    @staticmethod
    def test_on_form_prefill_has_benefit_amount_field(
        currency_service: CurrencyService,
    ):
        # Given
        form = ConvertedReimbursementRequestForm()
        benefit_amount: int = 100
        transaction_amount: int = 200
        benefit_currency: str = "AUD"
        request = ReimbursementRequest(
            amount=benefit_amount,
            benefit_currency_code=benefit_currency,
            transaction_amount=transaction_amount,
            transaction_currency_code="USD",
        )
        expected_data: str = "show me the money"

        # When
        with mock.patch(
            "wallet.services.currency.CurrencyService.to_money"
        ), mock.patch(
            "admin.views.models.wallet.format_display_amount_with_full_currency_name"
        ) as mock_format:
            mock_format.return_value = expected_data
            form.on_form_prefill(
                currency_service=currency_service, reimbursement_request=request
            )

        # Then
        assert form.benefit_amount_with_currency.data == expected_data

    @staticmethod
    def test_on_form_prefill_has_usd_amount_field(currency_service: CurrencyService):
        # Given
        form = ConvertedReimbursementRequestForm()
        benefit_amount: int = 200
        usd_amount: int = 100
        benefit_currency: str = "AUD"
        request = ReimbursementRequest(
            amount=benefit_amount,
            benefit_currency_code=benefit_currency,
            usd_amount=usd_amount,
        )
        expected_data: str = "show me the money"

        # When
        with mock.patch(
            "wallet.services.currency.CurrencyService.to_money"
        ), mock.patch(
            "admin.views.models.wallet.format_display_amount_with_full_currency_name"
        ) as mock_format:
            mock_format.return_value = expected_data
            form.on_form_prefill(
                currency_service=currency_service, reimbursement_request=request
            )

        # Then
        assert form.usd_amount.data == expected_data

    @staticmethod
    def test_on_form_prefill_has_fx_rate_fields(currency_service: CurrencyService):
        # Given
        form = ConvertedReimbursementRequestForm()
        benefit_amount: int = 200
        benefit_currency: str = "AUD"
        transaction_to_benefit_rate = Decimal("1.32")
        transaction_to_usd_rate = Decimal("0.23")
        request = ReimbursementRequest(
            amount=benefit_amount,
            benefit_currency_code=benefit_currency,
            transaction_to_benefit_rate=transaction_to_benefit_rate,
            transaction_to_usd_rate=transaction_to_usd_rate,
        )

        # When
        with mock.patch(
            "wallet.services.currency.CurrencyService.to_money"
        ), mock.patch(
            "admin.views.models.wallet.format_display_amount_with_full_currency_name"
        ):
            form.on_form_prefill(
                currency_service=currency_service, reimbursement_request=request
            )

        # Then
        assert (
            form.transaction_to_benefit_rate.data,
            form.transaction_to_usd_rate.data,
        ) == (transaction_to_benefit_rate, transaction_to_usd_rate)


class TestFormatters:
    @staticmethod
    def test_transaction_amount_formatter_calls_format_display_amount():
        # Given
        request = ReimbursementRequest(
            transaction_amount=100, transaction_currency_code="USD"
        )
        money_amount = Money(amount=Decimal("1.00"), currency_code="USD")
        view, context, name = MagicMock(), MagicMock(), MagicMock()

        # When
        with mock.patch(
            "wallet.services.currency.CurrencyService.to_money"
        ) as mock_to_money, mock.patch(
            "admin.views.models.wallet.format_display_amount_with_currency_code"
        ) as mock_format:
            mock_to_money.return_value = money_amount

            transaction_amount_formatter(
                view=view, context=context, model=request, name=name
            )

        # Then
        mock_format.assert_called_with(money=money_amount)

    @staticmethod
    @pytest.mark.parametrize(
        argnames=("amount", "currency_code"),
        argvalues=[(None, None), (1000, None), (None, "USD")],
    )
    def test_transaction_amount_formatter_returns_empty_string_when_input_is_missing(
        amount: str | None, currency_code: int | None
    ):
        # Given
        request = ReimbursementRequest(
            transaction_amount=amount, transaction_currency_code=currency_code
        )
        view, context, name = MagicMock(), MagicMock(), MagicMock()

        # When
        formatted: str = transaction_amount_formatter(
            view=view, context=context, model=request, name=name
        )

        # Then
        assert formatted == ""

    @staticmethod
    def test_benefit_amount_formatter_calls_format_display_amount():
        # Given
        request = ReimbursementRequest(amount=100, benefit_currency_code="USD")
        money_amount = Money(amount=Decimal("1.00"), currency_code="USD")
        view, context, name = MagicMock(), MagicMock(), MagicMock()

        # When
        with mock.patch(
            "wallet.services.currency.CurrencyService.to_money"
        ) as mock_to_money, mock.patch(
            "admin.views.models.wallet.format_display_amount_with_currency_code"
        ) as mock_format:
            mock_to_money.return_value = money_amount

            benefit_amount_formatter(
                view=view, context=context, model=request, name=name
            )

        # Then
        mock_format.assert_called_with(money=money_amount)

    @staticmethod
    def test_benefit_amount_formatter_returns_empty_string_when_input_is_missing():
        # Given
        request = ReimbursementRequest(amount=None, benefit_currency_code="USD")
        view, context, name = MagicMock(), MagicMock(), MagicMock()

        # When
        formatted: str = benefit_amount_formatter(
            view=view, context=context, model=request, name=name
        )

        # Then
        assert formatted == ""


class TestReimbursementRequestsForm:
    @staticmethod
    def test_validate_success(
        admin_app, session, mock_flash, mock_request_ctx, expense_subtypes  # noqa: F811
    ):
        wallet = ReimbursementWalletFactory.create()
        allowed_categories = wallet.get_or_create_wallet_allowed_categories
        category = allowed_categories[0].reimbursement_request_category
        with mock.patch(
            "flask_admin.actions.ActionsMixin.init_actions", return_value=False
        ):
            view = ReimbursementRequestsView(
                model=ReimbursementRequest, session=session
            )
            form = view.create_form()

            # Given

            # Field level validation
            form.transaction_amount_form.form.amount.data = 100_00
            form.transaction_amount_form.form.currency_code.data = "USD"
            form.category.raw_data = [str(category.id)]
            form.category.data = category
            form.wallet.raw_data = [str(wallet.id)]
            form.wallet.data = wallet
            form.label.raw_data = ["sample label"]
            form.label.data = "sample label"
            form.service_provider.raw_data = ["ivf clinic"]
            form.service_provider.data = "ivf clinic"
            form.state.raw_data = [ReimbursementRequestState.PENDING.value]
            form.state.data = ReimbursementRequestState.PENDING.value
            form.service_start_date.raw_data = ["2000-01-01 00:00:00"]
            form.service_start_date.data = ["2000-01-01 00:00:00"]

            # Form level validation in admin.views.models.wallet.ReimbursementRequestsForm.validate
            form.expense_type.data = ReimbursementRequestExpenseTypes.FERTILITY.name
            form.wallet_expense_subtype.data = expense_subtypes["FIVF"]

            assert form.validate() is True

    @staticmethod
    def test_validate_expense_type_required(
        admin_app, session, mock_flash, mock_request_ctx, expense_subtypes  # noqa: F811
    ):
        wallet = ReimbursementWalletFactory.create()
        allowed_categories = wallet.get_or_create_wallet_allowed_categories
        category = allowed_categories[0].reimbursement_request_category
        with mock.patch(
            "flask_admin.actions.ActionsMixin.init_actions", return_value=False
        ):
            view = ReimbursementRequestsView(
                model=ReimbursementRequest, session=session
            )
            form = view.create_form()

            # Given
            # expense_type is not populated
            form.expense_type.data = None

            # everything else is populated
            form.transaction_amount_form.form.amount.data = 100_00
            form.transaction_amount_form.form.currency_code.data = "USD"
            form.category.raw_data = [str(category.id)]
            form.category.data = category
            form.wallet.raw_data = [str(wallet.id)]
            form.wallet.data = wallet
            form.label.raw_data = ["sample label"]
            form.label.data = "sample label"
            form.service_provider.raw_data = ["ivf clinic"]
            form.service_provider.data = "ivf clinic"
            form.state.raw_data = [ReimbursementRequestState.PENDING.value]
            form.state.data = ReimbursementRequestState.PENDING.value
            form.service_start_date.raw_data = ["2000-01-01 00:00:00"]
            form.service_start_date.data = ["2000-01-01 00:00:00"]
            form.wallet_expense_subtype.data = expense_subtypes["FIVF"]

            assert form.validate() is False

    @staticmethod
    def test_validate_expense_subtype_optional(
        admin_app, session, mock_flash, mock_request_ctx, expense_subtypes  # noqa: F811
    ):
        wallet = ReimbursementWalletFactory.create()
        allowed_categories = wallet.get_or_create_wallet_allowed_categories
        category = allowed_categories[0].reimbursement_request_category
        with mock.patch(
            "flask_admin.actions.ActionsMixin.init_actions", return_value=False
        ):
            view = ReimbursementRequestsView(
                model=ReimbursementRequest, session=session
            )
            form = view.create_form()

            # Given
            # wallet_expense_subtype is not populated
            form.wallet_expense_subtype.data = None

            # everything else is populated
            form.transaction_amount_form.form.amount.data = 100_00
            form.transaction_amount_form.form.currency_code.data = "USD"
            form.category.raw_data = [str(category.id)]
            form.category.data = category
            form.wallet.raw_data = [str(wallet.id)]
            form.wallet.data = wallet
            form.label.raw_data = ["sample label"]
            form.label.data = "sample label"
            form.service_provider.raw_data = ["ivf clinic"]
            form.service_provider.data = "ivf clinic"
            form.state.raw_data = [ReimbursementRequestState.PENDING.value]
            form.state.data = ReimbursementRequestState.PENDING.value
            form.service_start_date.raw_data = ["2000-01-01 00:00:00"]
            form.service_start_date.data = ["2000-01-01 00:00:00"]
            form.expense_type.data = ReimbursementRequestExpenseTypes.FERTILITY.name

            assert form.validate() is True

    @staticmethod
    def test_validate_expense_subtype_mismatch(
        admin_app, session, mock_flash, mock_request_ctx, expense_subtypes  # noqa: F811
    ):
        wallet = ReimbursementWalletFactory.create()
        allowed_categories = wallet.get_or_create_wallet_allowed_categories
        category = allowed_categories[0].reimbursement_request_category
        with mock.patch(
            "flask_admin.actions.ActionsMixin.init_actions", return_value=False
        ):
            view = ReimbursementRequestsView(
                model=ReimbursementRequest, session=session
            )
            form = view.create_form()

            # Given
            # expense_type of expense_subtype does not match expense_type
            form.wallet_expense_subtype.data = expense_subtypes["FIVF"]
            form.expense_type.data = ReimbursementRequestExpenseTypes.ADOPTION.name

            # everything else is populated
            form.transaction_amount_form.form.amount.data = 100_00
            form.transaction_amount_form.form.currency_code.data = "USD"
            form.category.raw_data = [str(category.id)]
            form.category.data = category
            form.wallet.raw_data = [str(wallet.id)]
            form.wallet.data = wallet
            form.label.raw_data = ["sample label"]
            form.label.data = "sample label"
            form.service_provider.raw_data = ["ivf clinic"]
            form.service_provider.data = "ivf clinic"
            form.state.raw_data = [ReimbursementRequestState.PENDING.value]
            form.state.data = ReimbursementRequestState.PENDING.value
            form.service_start_date.raw_data = ["2000-01-01 00:00:00"]
            form.service_start_date.data = ["2000-01-01 00:00:00"]

            assert form.validate() is False


class TestReimbursementRequestValidations:
    def test_get_reimbursement_field_validations_success(self, session, wallet):
        document_mapping_uuid = UUID("12345678-1234-5678-1234-567812345678")
        category = (
            wallet.reimbursement_organization_settings.allowed_reimbursement_categories[
                0
            ].reimbursement_request_category
        )
        reimbursement_request = ReimbursementRequestFactory.create(
            wallet=wallet,
            category=category,
            state=ReimbursementRequestState.NEW,
            person_receiving_service="John Doe",
            service_provider="Test Provider",
            amount=10000,
            service_start_date=datetime.strptime("2024-01-15", "%Y-%m-%d"),
            sources=[
                ReimbursementRequestSourceFactory.create(
                    document_mapping_uuid=document_mapping_uuid,
                    reimbursement_wallet_id=wallet.id,
                )
            ],
        )
        mock_mapping = ReceiptExtractionDocumentMappingWithFeedback(
            document_mapping=ReceiptExtractionDocumentMapping(
                document_mapping_uuid=document_mapping_uuid,
                source_ids=[1],
                service_provider="Test Provider",
                patient_name="John Doe",
                payment_amount=10000,
                date_of_service="2024-01-15",
                service_evidence=True,
            ),
            feedback=None,
        )

        with mock.patch(
            "admin.views.models.wallet.DocumentMapperService.get_document_mapping",
            return_value=mock_mapping,
        ):
            with mock.patch(
                "flask_admin.actions.ActionsMixin.init_actions", return_value=False
            ):
                view = ReimbursementRequestsView(
                    model=ReimbursementRequest, session=session
                )
                result = view._get_reimbursement_field_validations(
                    reimbursement_request=reimbursement_request
                )

            assert result is not None
            assert result["fields"]["service_provider"]["status"] == "info"
            assert (
                "Provider name matches 'Test Provider'"
                in result["fields"]["service_provider"]["message"]
            )
            assert result["fields"]["transaction_amount_form"]["status"] == "info"
            assert (
                "Payment amount matches"
                in result["fields"]["transaction_amount_form"]["message"]
            )
            assert result["fields"]["person_receiving_service"]["status"] == "info"
            assert (
                "Patient name matches"
                in result["fields"]["person_receiving_service"]["message"]
            )
            assert result["fields"]["service_start_date"]["status"] == "info"
            assert (
                "Service date matches"
                in result["fields"]["service_start_date"]["message"]
            )
            assert result["fields"]["sources"]["status"] == "info"
            assert (
                "Service evidence found in sources"
                in result["fields"]["sources"]["message"]
            )

    def test_get_reimbursement_field_validations_mismatched_values(
        self, session, wallet
    ):
        document_mapping_uuid = UUID("12345678-1234-5678-1234-567812345678")
        category = (
            wallet.reimbursement_organization_settings.allowed_reimbursement_categories[
                0
            ].reimbursement_request_category
        )
        reimbursement_request = ReimbursementRequestFactory.create(
            wallet=wallet,
            category=category,
            state=ReimbursementRequestState.NEW,
            person_receiving_service="John Doe",
            service_provider="Test Provider",
            amount=10000,
            service_start_date=datetime.strptime("2024-01-15", "%Y-%m-%d"),
            sources=[
                ReimbursementRequestSourceFactory.create(
                    document_mapping_uuid=document_mapping_uuid,
                    reimbursement_wallet_id=wallet.id,
                )
            ],
        )
        mock_mapping = ReceiptExtractionDocumentMappingWithFeedback(
            document_mapping=ReceiptExtractionDocumentMapping(
                document_mapping_uuid=document_mapping_uuid,
                source_ids=[1],
                service_provider="Test Doctor",
                patient_name="John Downing",
                payment_amount=20000,
                date_of_service="2024-01-16",
                service_evidence=False,
            ),
            feedback=None,
        )

        with mock.patch(
            "admin.views.models.wallet.DocumentMapperService.get_document_mapping",
            return_value=mock_mapping,
        ):
            with mock.patch(
                "flask_admin.actions.ActionsMixin.init_actions", return_value=False
            ):
                view = ReimbursementRequestsView(
                    model=ReimbursementRequest, session=session
                )
                result = view._get_reimbursement_field_validations(
                    reimbursement_request=reimbursement_request
                )

            assert result is not None
            assert result["fields"]["service_provider"]["status"] == "warning"
            assert (
                "Provider name appears to be 'Test Doctor'"
                in result["fields"]["service_provider"]["message"]
            )
            assert result["fields"]["transaction_amount_form"]["status"] == "warning"
            assert (
                "Payment amount appears to be '$200.00' in the source document(s)"
                in result["fields"]["transaction_amount_form"]["message"]
            )
            assert result["fields"]["person_receiving_service"]["status"] == "warning"
            assert (
                "Patient name appears to be 'John Downing'"
                in result["fields"]["person_receiving_service"]["message"]
            )
            assert result["fields"]["service_start_date"]["status"] == "warning"
            assert (
                "Service date appears to be '2024-01-16'"
                in result["fields"]["service_start_date"]["message"]
            )
            assert result["fields"]["sources"]["status"] == "error"
            assert (
                "There does not appear to be service evidence in the sources"
                in result["fields"]["sources"]["message"]
            )

    def test_get_reimbursement_field_validations_missing_fields(self, session, wallet):
        document_mapping_uuid = UUID("12345678-1234-5678-1234-567812345678")
        category = (
            wallet.reimbursement_organization_settings.allowed_reimbursement_categories[
                0
            ].reimbursement_request_category
        )
        reimbursement_request = ReimbursementRequestFactory.create(
            wallet=wallet,
            category=category,
            state=ReimbursementRequestState.NEW,
            person_receiving_service="John Doe",
            service_provider="Test Provider",
            amount=10000,
            service_start_date=datetime.strptime("2024-01-15", "%Y-%m-%d"),
            sources=[
                ReimbursementRequestSourceFactory.create(
                    document_mapping_uuid=document_mapping_uuid,
                    reimbursement_wallet_id=wallet.id,
                )
            ],
        )
        mock_mapping = ReceiptExtractionDocumentMappingWithFeedback(
            document_mapping=ReceiptExtractionDocumentMapping(
                document_mapping_uuid=document_mapping_uuid,
                source_ids=[1],
                service_provider="",
                patient_name="",
                payment_amount=None,
                date_of_service="",
                service_evidence=False,
            ),
            feedback=None,
        )

        with mock.patch(
            "admin.views.models.wallet.DocumentMapperService.get_document_mapping",
            return_value=mock_mapping,
        ):
            with mock.patch(
                "flask_admin.actions.ActionsMixin.init_actions", return_value=False
            ):
                view = ReimbursementRequestsView(
                    model=ReimbursementRequest, session=session
                )
                result = view._get_reimbursement_field_validations(
                    reimbursement_request=reimbursement_request
                )

            assert result is not None
            assert result["fields"]["service_provider"]["status"] == "error"
            assert (
                "Provider name could not be found"
                in result["fields"]["service_provider"]["message"]
            )
            assert result["fields"]["transaction_amount_form"]["status"] == "error"
            assert (
                "Payment amount could not be found"
                in result["fields"]["transaction_amount_form"]["message"]
            )
            assert result["fields"]["person_receiving_service"]["status"] == "error"
            assert (
                "Patient name could not be found"
                in result["fields"]["person_receiving_service"]["message"]
            )
            assert result["fields"]["service_start_date"]["status"] == "error"
            assert (
                "Service date could not be found"
                in result["fields"]["service_start_date"]["message"]
            )
            assert result["fields"]["sources"]["status"] == "error"
            assert (
                "There does not appear to be service evidence in the sources"
                in result["fields"]["sources"]["message"]
            )

    def test_get_reimbursement_field_validations_multiple_mappings(
        self, session, wallet
    ):
        """Test error case when multiple document mappings are found"""
        category = (
            wallet.reimbursement_organization_settings.allowed_reimbursement_categories[
                0
            ].reimbursement_request_category
        )
        reimbursement_request = ReimbursementRequestFactory.create(
            wallet=wallet,
            category=category,
            state=ReimbursementRequestState.NEW,
            sources=[
                ReimbursementRequestSourceFactory.create(
                    reimbursement_wallet_id=wallet.id,
                    document_mapping_uuid=UUID("12345678-1234-5678-1234-567812345678"),
                ),
                ReimbursementRequestSourceFactory.create(
                    reimbursement_wallet_id=wallet.id,
                    document_mapping_uuid=UUID("12345678-1234-5678-1234-567812345679"),
                ),
            ],
        )

        with mock.patch(
            "flask_admin.actions.ActionsMixin.init_actions", return_value=False
        ):
            view = ReimbursementRequestsView(
                model=ReimbursementRequest, session=session
            )
            result = view._get_reimbursement_field_validations(
                reimbursement_request=reimbursement_request
            )

        assert result["fields"]["sources"]["status"] == "error"
        assert "AI Validations are stale" in result["fields"]["sources"]["message"]

    def test_get_reimbursement_field_validations_no_mapping(self, session, wallet):
        """Test case when document mapper returns no mapping"""
        category = (
            wallet.reimbursement_organization_settings.allowed_reimbursement_categories[
                0
            ].reimbursement_request_category
        )
        reimbursement_request = ReimbursementRequestFactory.create(
            wallet=wallet,
            category=category,
            state=ReimbursementRequestState.NEW,
            sources=[
                ReimbursementRequestSourceFactory.create(
                    reimbursement_wallet_id=wallet.id,
                    document_mapping_uuid=UUID("12345678-1234-5678-1234-567812345678"),
                ),
            ],
        )
        with mock.patch(
            "flask_admin.actions.ActionsMixin.init_actions", return_value=False
        ):
            view = ReimbursementRequestsView(
                model=ReimbursementRequest, session=session
            )
            result = view._get_reimbursement_field_validations(
                reimbursement_request=reimbursement_request
            )

        assert result["fields"]["sources"]["status"] == "error"
        assert (
            "No AI Validation returned - validations not shown"
            in result["fields"]["sources"]["message"]
        )

    def test_get_reimbursement_field_validations_no_sources(self, session, wallet):
        """Test case when no document sources are found"""
        category = (
            wallet.reimbursement_organization_settings.allowed_reimbursement_categories[
                0
            ].reimbursement_request_category
        )
        reimbursement_request = ReimbursementRequestFactory.create(
            wallet=wallet,
            category=category,
            state=ReimbursementRequestState.NEW,
        )

        with mock.patch(
            "flask_admin.actions.ActionsMixin.init_actions", return_value=False
        ):
            view = ReimbursementRequestsView(
                model=ReimbursementRequest, session=session
            )
            result = view._get_reimbursement_field_validations(
                reimbursement_request=reimbursement_request
            )

        assert result["fields"]["sources"]["status"] == "error"
        assert "No documents to validate" in result["fields"]["sources"]["message"]

    def test_get_reimbursement_field_validations_no_mappings_on_sources(
        self, session, wallet
    ):
        """Test case when document sources are found but document mapping uuid is None"""
        category = (
            wallet.reimbursement_organization_settings.allowed_reimbursement_categories[
                0
            ].reimbursement_request_category
        )
        reimbursement_request = ReimbursementRequestFactory.create(
            wallet=wallet,
            category=category,
            state=ReimbursementRequestState.NEW,
            sources=[
                ReimbursementRequestSourceFactory.create(
                    reimbursement_wallet_id=wallet.id,
                    document_mapping_uuid=None,
                )
            ],
        )

        with mock.patch(
            "flask_admin.actions.ActionsMixin.init_actions", return_value=False
        ):
            view = ReimbursementRequestsView(
                model=ReimbursementRequest, session=session
            )
            result = view._get_reimbursement_field_validations(
                reimbursement_request=reimbursement_request
            )

        assert result["fields"]["sources"]["status"] == "error"
        assert (
            "No AI validation exists on sources - Validation needs to be run"
            in result["fields"]["sources"]["message"]
        )

    def test_get_reimbursement_field_validations_with_feedback(self, session, wallet):
        document_mapping_uuid = UUID("12345678-1234-5678-1234-567812345678")
        category = (
            wallet.reimbursement_organization_settings.allowed_reimbursement_categories[
                0
            ].reimbursement_request_category
        )
        reimbursement_request = ReimbursementRequestFactory.create(
            wallet=wallet,
            category=category,
            state=ReimbursementRequestState.NEW,
            person_receiving_service="John Doe",
            service_provider="Test Provider",
            amount=10000,
            service_start_date=datetime.strptime("2024-01-15", "%Y-%m-%d"),
            sources=[
                ReimbursementRequestSourceFactory.create(
                    document_mapping_uuid=document_mapping_uuid,
                    reimbursement_wallet_id=wallet.id,
                )
            ],
        )

        # Create mock feedback
        mock_feedback = [
            DocumentMappingFeedback(
                uuid=UUID("87654321-4321-8765-4321-876543210987"),
                field_name="transaction_amount_form",
                previous_value="10000",
                feedback_accepted=True,
                updated_by="test@maven.com",
            ),
            DocumentMappingFeedback(
                uuid=UUID("11111111-2222-3333-4444-555555555555"),
                field_name="person_receiving_service",
                previous_value="John Doe",
                feedback_accepted=False,
                updated_by="test@maven.com",
            ),
        ]

        mock_mapping = ReceiptExtractionDocumentMappingWithFeedback(
            document_mapping=ReceiptExtractionDocumentMapping(
                document_mapping_uuid=document_mapping_uuid,
                source_ids=[1],
                service_provider="Test Provider",
                patient_name="John Doe",
                payment_amount=10000,
                date_of_service="2024-01-15",
                service_evidence=True,
            ),
            feedback=mock_feedback,
        )

        with mock.patch(
            "admin.views.models.wallet.DocumentMapperService.get_document_mapping",
            return_value=mock_mapping,
        ):
            with mock.patch(
                "flask_admin.actions.ActionsMixin.init_actions", return_value=False
            ):
                view = ReimbursementRequestsView(
                    model=ReimbursementRequest, session=session
                )
                result = view._get_reimbursement_field_validations(
                    reimbursement_request=reimbursement_request
                )

            assert result is not None
            # Check feedback is properly mapped using original field names
            assert (
                result["fields"]["transaction_amount_form"]["prior_feedback"] is True
            )  # payment_amount feedback
            assert (
                result["fields"]["person_receiving_service"]["prior_feedback"] is False
            )  # patient_name feedback
            # Fields without feedback should have prior_feedback as None
            assert result["fields"]["service_provider"]["prior_feedback"] is None
            assert result["fields"]["service_start_date"]["prior_feedback"] is None
            assert result["fields"]["sources"]["prior_feedback"] is None

    def test_get_reimbursement_field_validations_with_empty_feedback(
        self, session, wallet
    ):
        document_mapping_uuid = UUID("12345678-1234-5678-1234-567812345678")
        category = (
            wallet.reimbursement_organization_settings.allowed_reimbursement_categories[
                0
            ].reimbursement_request_category
        )
        reimbursement_request = ReimbursementRequestFactory.create(
            wallet=wallet,
            category=category,
            state=ReimbursementRequestState.NEW,
            person_receiving_service="John Doe",
            service_provider="Test Provider",
            amount=10000,
            service_start_date=datetime.strptime("2024-01-15", "%Y-%m-%d"),
            sources=[
                ReimbursementRequestSourceFactory.create(
                    document_mapping_uuid=document_mapping_uuid,
                    reimbursement_wallet_id=wallet.id,
                )
            ],
        )

        mock_mapping = ReceiptExtractionDocumentMappingWithFeedback(
            document_mapping=ReceiptExtractionDocumentMapping(
                document_mapping_uuid=document_mapping_uuid,
                source_ids=[1],
                service_provider="Test Provider",
                patient_name="John Doe",
                payment_amount=10000,
                date_of_service="2024-01-15",
                service_evidence=True,
            ),
            feedback=None,
        )

        with mock.patch(
            "admin.views.models.wallet.DocumentMapperService.get_document_mapping",
            return_value=mock_mapping,
        ):
            with mock.patch(
                "flask_admin.actions.ActionsMixin.init_actions", return_value=False
            ):
                view = ReimbursementRequestsView(
                    model=ReimbursementRequest, session=session
                )
                result = view._get_reimbursement_field_validations(
                    reimbursement_request=reimbursement_request
                )

            assert result is not None
            for field_validation in result["fields"].values():
                assert field_validation["prior_feedback"] is None

    def test_handle_document_mapper_feedback_success(
        self, admin_client, session, wallet
    ):
        """Test successful feedback submission"""
        document_mapping_uuid = UUID("12345678-1234-5678-1234-567812345678")
        test_data = {
            "document_mapping_uuid": str(document_mapping_uuid),
            "field_name": "service_provider",
            "is_correct": True,
            "field_value": "Test Provider",
        }

        with mock.patch(
            "admin.views.models.wallet.DocumentMapperService.create_feedback",
            return_value=DocumentMappingFeedback(
                uuid=UUID("87654321-4321-8765-4321-876543210987"),
                field_name="service_provider",
                previous_value="Test Provider",
                feedback_accepted=True,
                updated_by="placeholder@maven.com",
            ),
        ) as mock_create_feedback:
            response = admin_client.post(
                "/admin/reimbursementrequest/document_mapper_feedback",
                json=test_data,
                headers={"Content-Type": "application/json"},
            )
            assert response.status_code == 200
            assert response.get_json() == {"status": "success"}

            mock_create_feedback.assert_called_once_with(
                document_mapping_uuid=document_mapping_uuid,
                field_name="service_provider",
                updated_by=mock.ANY,
                previous_value="Test Provider",
                feedback_accepted=True,
            )

    def test_handle_document_mapper_feedback_failure(
        self, admin_client, session, wallet
    ):
        """Test feedback submission when document mapper service fails"""
        document_mapping_uuid = UUID("12345678-1234-5678-1234-567812345678")
        test_data = {
            "document_mapping_uuid": str(document_mapping_uuid),
            "field_name": "service_provider",
            "is_correct": True,
            "field_value": "Test Provider",
        }

        with mock.patch(
            "admin.views.models.wallet.DocumentMapperService.create_feedback",
            return_value=None,
        ):
            response = admin_client.post(
                "/admin/reimbursementrequest/document_mapper_feedback",
                json=test_data,
                headers={"Content-Type": "application/json"},
            )
            assert response.status_code == 400
            assert response.get_json() == {
                "status": "error",
                "message": "Failed to create feedback",
            }

    def test_handle_document_mapper_feedback_invalid_uuid(
        self, admin_client, session, wallet
    ):
        """Test feedback submission with invalid UUID"""
        test_data = {
            "document_mapping_uuid": "invalid-uuid",
            "field_name": "service_provider",
            "is_correct": True,
            "field_value": "Test Provider",
        }

        response = admin_client.post(
            "/admin/reimbursementrequest/document_mapper_feedback",
            json=test_data,
            headers={"Content-Type": "application/json"},
        )

        assert response.status_code == 500
        assert "status" in response.json
        assert response.json["status"] == "error"
        assert "message" in response.json

    def test_handle_document_mapper_feedback_missing_data(
        self, admin_client, session, wallet
    ):
        """Test feedback submission with missing required fields"""
        test_data = {
            "document_mapping_uuid": str(UUID("12345678-1234-5678-1234-567812345678")),
            # missing field_name
            "is_correct": True,
            "field_value": "Test Provider",
        }

        response = admin_client.post(
            "/admin/reimbursementrequest/document_mapper_feedback",
            json=test_data,
            headers={"Content-Type": "application/json"},
        )

        assert response.status_code == 500
        assert "status" in response.json
        assert response.json["status"] == "error"
        assert "message" in response.json

    def test_create_document_mapping_success(self, admin_client, session, wallet):
        """Test successful document mapping creation"""
        reimbursement_request_id = "123"

        with mock.patch(
            "admin.views.models.wallet.map_reimbursement_request_documents"
        ) as mock_map_documents:
            response = admin_client.post(
                f"/admin/reimbursementrequest/document_mapping?id={reimbursement_request_id}",
            )

            # Verify the response redirects to edit view
            assert response.status_code == 302
            assert (
                f"/admin/reimbursementrequest/edit/?id={reimbursement_request_id}"
                in response.location
            )

            # Verify mapping was triggered
            mock_map_documents.assert_called_once_with(
                reimbursement_request_id=reimbursement_request_id
            )

    def test_create_document_mapping_failure(self, admin_client, session, wallet):
        """Test document mapping creation when service fails"""
        reimbursement_request_id = "123"

        with mock.patch(
            "admin.views.models.wallet.map_reimbursement_request_documents",
            side_effect=Exception("Failed to create mapping"),
        ) as mock_map_documents:
            response = admin_client.post(
                f"/admin/reimbursementrequest/document_mapping?id={reimbursement_request_id}",
            )

            # Verify error response
            assert response.status_code == 500
            assert response.get_json() == {
                "status": "error",
                "message": "Failed to create mapping",
            }

            # Verify mapping was attempted
            mock_map_documents.assert_called_once_with(
                reimbursement_request_id=reimbursement_request_id
            )

    def test_create_document_mapping_missing_id(self, admin_client, session, wallet):
        """Test document mapping creation without request ID"""
        response = admin_client.post("/admin/reimbursementrequest/document_mapping")

        # Verify error response
        assert response.status_code == 400
        response_json = response.get_json()
        assert response_json["status"] == "error"
        assert response_json["message"] == "Reimbursement request ID is required"

    @pytest.mark.parametrize(
        "extracted_value, request_value, field_name, expected_status, expected_message_part",
        [
            # Case insensitivity and whitespace tests
            (
                "  PATRICIA BEARD  ",
                "Patricia Beard",
                "Provider name",
                "info",
                "matches",
            ),
            # Partial matching tests for provider names
            ("CCRM", "CCRM New York", "Provider name", "info", "matches"),
            ("CCRM New York", "CCRM", "Provider name", "info", "matches"),
            # Non-matching provider names
            ("Mayo Clinic", "CCRM", "Provider name", "warning", "appears to be"),
            # Different values for other fields
            ("John Smith", "Jane Doe", "Patient name", "warning", "appears to be"),
            # Missing extracted value
            ("", "Some Value", "Field name", "error", "could not be found"),
        ],
    )
    def test_get_field_validation_status_and_message_variations(
        self,
        session,
        extracted_value,
        request_value,
        field_name,
        expected_status,
        expected_message_part,
    ):
        """Test the helper function with various inputs using parameterization"""
        with mock.patch(
            "flask_admin.actions.ActionsMixin.init_actions", return_value=False
        ):
            view = ReimbursementRequestsView(
                model=ReimbursementRequest, session=session
            )

            result = view._get_field_validation_status_and_message(
                extracted_value, request_value, field_name
            )

            assert result["status"] == expected_status
            assert expected_message_part in result["message"]

    @pytest.mark.parametrize(
        "service_provider_extracted, service_provider_request, patient_name_extracted, patient_name_request",
        [
            # Case 1: Exact matches with case/whitespace differences
            ("TEST PROVIDER  ", "Test Provider", "  JOHN DOE", "John Doe"),
            # Case 2: Partial match for provider name
            ("CCRM", "CCRM New York", "John Doe", "John Doe"),
            # Case 3: Reverse partial match
            ("CCRM New York", "CCRM", "John Doe", "John Doe"),
        ],
    )
    def test_get_reimbursement_field_validations_matching_variations(
        self,
        session,
        wallet,
        service_provider_extracted,
        service_provider_request,
        patient_name_extracted,
        patient_name_request,
    ):
        """Test validation with different matching scenarios using parameterization"""
        category = (
            wallet.reimbursement_organization_settings.allowed_reimbursement_categories[
                0
            ].reimbursement_request_category
        )
        reimbursement_request = ReimbursementRequestFactory.create(
            wallet=wallet,
            category=category,
            state=ReimbursementRequestState.NEW,
            person_receiving_service=patient_name_request,
            service_provider=service_provider_request,
            amount=10000,
            service_start_date=datetime.strptime("2024-01-15", "%Y-%m-%d"),
            sources=[
                ReimbursementRequestSourceFactory.create(
                    reimbursement_wallet_id=wallet.id,
                )
            ],
        )

        mock_mapping = ReceiptExtractionDocumentMappingWithFeedback(
            document_mapping=ReceiptExtractionDocumentMapping(
                document_mapping_uuid=uuid.uuid4(),
                source_ids=[1],
                service_provider=service_provider_extracted,
                patient_name=patient_name_extracted,
                payment_amount=10000,
                date_of_service="2024-01-15",
                service_evidence=True,
            ),
            feedback=None,
        )

        with mock.patch(
            "admin.views.models.wallet.DocumentMapperService.get_document_mapping",
            return_value=mock_mapping,
        ):
            with mock.patch(
                "flask_admin.actions.ActionsMixin.init_actions", return_value=False
            ):
                view = ReimbursementRequestsView(
                    model=ReimbursementRequest, session=session
                )
                result = view._get_reimbursement_field_validations(
                    reimbursement_request=reimbursement_request
                )

            assert result is not None
            # Check provider name matching
            assert result["fields"]["service_provider"]["status"] == "info"
            assert (
                "Provider name matches"
                in result["fields"]["service_provider"]["message"]
            )

            # Patient name should always match
            assert result["fields"]["person_receiving_service"]["status"] == "info"
            assert (
                "Patient name matches"
                in result["fields"]["person_receiving_service"]["message"]
            )

    # Keep the numeric test separate since it needs a special format_value function
    def test_get_field_validation_status_and_message_numeric(self, session):
        """Test the helper function with numeric values"""
        with mock.patch(
            "flask_admin.actions.ActionsMixin.init_actions", return_value=False
        ):
            view = ReimbursementRequestsView(
                model=ReimbursementRequest, session=session
            )

            result = view._get_field_validation_status_and_message(
                10000, 10000, "Amount", format_value=lambda x: f"${x/100:.2f}"
            )
            assert result["status"] == "info"
            assert "Amount matches '$100.00'" in result["message"]
