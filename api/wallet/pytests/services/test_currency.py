from __future__ import annotations

import datetime
from decimal import Decimal
from unittest import mock

import pytest

from wallet.models.currency import Money
from wallet.models.reimbursement import ReimbursementRequest
from wallet.models.reimbursement_organization_settings import (
    ReimbursementOrgSettingCategoryAssociation,
)
from wallet.models.reimbursement_wallet import ReimbursementWallet
from wallet.pytests.factories import ReimbursementRequestFactory
from wallet.services.currency import (
    CurrencyService,
    InvalidAdjustmentRequest,
    InvalidCurrencyConversionRequest,
    InvalidExchangeRate,
)


class TestToDecimalAmount:
    @staticmethod
    @pytest.mark.parametrize(
        argnames=("amount", "minor_unit", "expected"),
        argvalues=[
            (10000, 2, Decimal("100")),
            (-10000, 2, Decimal("-100")),
            (10000, 0, Decimal("10000")),
            (10021, 2, Decimal("100.21")),
            (93, 2, Decimal(".93")),
            (123456, 3, Decimal("123.456")),
        ],
        ids=[
            "cents-to-dollars",
            "negative-cents-to-dollars",
            "minor-unit-of-zero",
            "cent-value-not-zero",
            "cents-only",
            "minor-unit-of-three",
        ],
    )
    def test_to_decimal_amount(
        currency_service: CurrencyService,
        amount: int,
        minor_unit: int,
        expected: Decimal,
    ):
        # Given an amount, minor_unit of the amount's currency

        # When
        decimal_amount: Decimal = currency_service._to_decimal_amount(
            amount=amount, minor_unit=minor_unit
        )

        # Then
        assert decimal_amount == expected

    @staticmethod
    def test_to_decimal_amount_invalid_minor_unit(currency_service: CurrencyService):
        # Given a negative minor unit
        minor_unit: int = -2

        # When - Then
        with pytest.raises(ValueError):
            currency_service._to_decimal_amount(amount=100, minor_unit=minor_unit)


class TestToMoney:
    @staticmethod
    def test_to_money_calls_get_minor_unit(currency_service: CurrencyService):
        # Given
        amount: int = 100
        currency_code: str = "USD"

        # When
        with mock.patch("wallet.services.currency.CurrencyService._to_decimal_amount"):
            currency_service.to_money(amount=amount, currency_code=currency_code)

        # Then
        currency_service.currency_code_repo.get_minor_unit.assert_called_once_with(
            currency_code=currency_code
        )

    @staticmethod
    def test_to_money_calls_to_decimal_amount(currency_service: CurrencyService):
        # Given
        amount: int = 200
        currency_code: str = "USD"
        minor_unit: int = 2
        decimal_amount: Decimal = Decimal("2.00")
        currency_service.currency_code_repo.get_minor_unit.return_value = minor_unit

        # When
        with mock.patch(
            "wallet.services.currency.CurrencyService._to_decimal_amount"
        ) as mock_to_decimal_amount:
            mock_to_decimal_amount.return_value = decimal_amount

            currency_service.to_money(amount=amount, currency_code=currency_code)

        # Then
        mock_to_decimal_amount.assert_called_once_with(
            amount=amount, minor_unit=minor_unit
        )

    @staticmethod
    def test_to_money_returns_money_dataclass(currency_service: CurrencyService):
        # Given
        amount: int = 200
        currency_code: str = "USD"
        minor_unit: int = 2
        decimal_amount: Decimal = Decimal("2.00")
        currency_service.currency_code_repo.get_minor_unit.return_value = minor_unit
        expected_money_amount: Money = Money(
            amount=decimal_amount, currency_code=currency_code
        )

        # When
        with mock.patch(
            "wallet.services.currency.CurrencyService._to_decimal_amount"
        ) as mock_to_decimal_amount:
            mock_to_decimal_amount.return_value = decimal_amount

            money_amount: Money = currency_service.to_money(
                amount=amount, currency_code=currency_code
            )

        # Then
        assert money_amount == expected_money_amount


class TestPrivateConvert:
    @staticmethod
    @pytest.mark.parametrize(
        argnames=(
            "source_amount",
            "source_minor_unit",
            "target_minor_unit",
            "rate",
            "expected_target_amount",
        ),
        argvalues=[
            (100, 2, 0, Decimal("153.40"), 153),
            (100, 2, 0, Decimal("153.50"), 154),
            (100, 0, 2, Decimal("0.0066"), 66),
            (100, 2, 2, Decimal("1.00"), 100),
            (100, 2, 2, Decimal("1.2234534"), 122),
            (100, 2, 2, Decimal("1.225"), 122),
            (100, 2, 2, Decimal("1.235"), 124),
            (100, 2, 2, Decimal("0.190424"), 19),
            (100, 2, 2, Decimal("0.195424"), 20),
        ],
    )
    def test_convert(
        currency_service: CurrencyService,
        source_amount: int,
        source_minor_unit: int,
        target_minor_unit: int,
        rate: Decimal,
        expected_target_amount: int,
    ):
        # Given

        # When
        amount: int = currency_service._convert(
            amount=source_amount,
            source_minor_unit=source_minor_unit,
            target_minor_unit=target_minor_unit,
            rate=rate,
        )

        # Then
        assert amount == expected_target_amount


class TestPublicConvert:
    @staticmethod
    def test_convert_calls_get_minor_unit_with_correct_params(
        currency_service: CurrencyService,
    ):
        # Given
        source_amount: int = 100
        source_currency_code: str = "USD"
        source_minor_unit: int = 2
        target_currency_code: str = "AUD"
        target_minor_unit: int = 2
        rate: Decimal = Decimal("2.00")
        currency_service.fx_rate_repo.get_rate.return_value = rate
        currency_service.currency_code_repo.get_minor_unit.side_effect = [
            source_minor_unit,
            target_minor_unit,
        ]

        expected_calls = [
            mock.call(source_currency_code),
            mock.call(target_currency_code),
        ]

        # When
        currency_service.convert(
            amount=source_amount,
            source_currency_code=source_currency_code,
            target_currency_code=target_currency_code,
            as_of_date=datetime.date(year=2024, month=3, day=1),
        )

        # Then
        currency_service.currency_code_repo.get_minor_unit.assert_has_calls(
            expected_calls
        )

    @staticmethod
    def test_convert_calls_get_rate_with_correct_params(
        currency_service: CurrencyService,
    ):
        # Given
        source_amount: int = 100
        source_currency_code: str = "USD"
        source_minor_unit: int = 2
        target_currency_code: str = "AUD"
        target_minor_unit: int = 2
        rate: Decimal = Decimal("2.00")
        currency_service.fx_rate_repo.get_rate.return_value = rate
        currency_service.currency_code_repo.get_minor_unit.side_effect = [
            source_minor_unit,
            target_minor_unit,
        ]
        as_of_date: datetime.date = datetime.date(year=2024, month=3, day=1)

        # When
        currency_service.convert(
            amount=source_amount,
            source_currency_code=source_currency_code,
            target_currency_code=target_currency_code,
            as_of_date=as_of_date,
        )

        # Then
        currency_service.fx_rate_repo.get_rate.assert_called_once_with(
            source_currency_code=source_currency_code,
            target_currency_code=target_currency_code,
            as_of_date=as_of_date,
        )

    @staticmethod
    def test_convert_calls_private_convert_with_correct_params(
        currency_service: CurrencyService,
    ):
        # Given
        source_amount: int = 100
        source_currency_code: str = "USD"
        source_minor_unit: int = 2
        target_currency_code: str = "AUD"
        target_minor_unit: int = 2
        rate: Decimal = Decimal("2.00")
        currency_service.fx_rate_repo.get_rate.return_value = rate
        currency_service.currency_code_repo.get_minor_unit.side_effect = [
            source_minor_unit,
            target_minor_unit,
        ]
        as_of_date: datetime.date = datetime.datetime(year=2024, month=3, day=1)

        # When
        with mock.patch(
            "wallet.services.currency.CurrencyService._convert"
        ) as mock_convert:
            currency_service.convert(
                amount=source_amount,
                source_currency_code=source_currency_code,
                target_currency_code=target_currency_code,
                as_of_date=as_of_date,
            )

        # Then
        mock_convert.assert_called_once_with(
            amount=source_amount,
            source_minor_unit=source_minor_unit,
            target_minor_unit=target_minor_unit,
            rate=rate,
        )

    @staticmethod
    def test_convert_custom_rate_is_provided(
        currency_service: CurrencyService,
    ):
        # Given
        source_amount: int = 100
        source_currency_code: str = "USD"
        source_minor_unit: int = 2
        target_currency_code: str = "AUD"
        target_minor_unit: int = 2
        custom_rate: Decimal = Decimal("2.00")

        currency_service.currency_code_repo.get_minor_unit.side_effect = [
            source_minor_unit,
            target_minor_unit,
        ]

        # When
        currency_service.convert(
            amount=source_amount,
            source_currency_code=source_currency_code,
            target_currency_code=target_currency_code,
            rate=custom_rate,
        )

        # Then
        currency_service.fx_rate_repo.get_rate.assert_not_called()

    @staticmethod
    @pytest.mark.parametrize(
        argnames="rate",
        argvalues=[Decimal("0"), Decimal("-1")],
    )
    def test_convert_rate_is_invalid_raises_exception(
        currency_service: CurrencyService, rate: Decimal
    ):
        # Given
        source_amount: int = 100
        source_currency_code: str = "USD"
        source_minor_unit: int = 2
        target_currency_code: str = "AUD"
        target_minor_unit: int = 2
        currency_service.fx_rate_repo.get_rate.return_value = rate

        currency_service.currency_code_repo.get_minor_unit.side_effect = [
            source_minor_unit,
            target_minor_unit,
        ]

        # When - Then
        with pytest.raises(InvalidExchangeRate):
            currency_service.convert(
                amount=source_amount,
                source_currency_code=source_currency_code,
                target_currency_code=target_currency_code,
            )

    @staticmethod
    def test_convert_returns_amount_and_rate(
        currency_service: CurrencyService,
    ):
        # Given
        source_amount: int = 100
        source_currency_code: str = "USD"
        source_minor_unit: int = 2
        target_currency_code: str = "AUD"
        target_minor_unit: int = 2
        expected_rate: Decimal = Decimal("2.00")
        currency_service.fx_rate_repo.get_rate.return_value = expected_rate
        currency_service.currency_code_repo.get_minor_unit.side_effect = [
            source_minor_unit,
            target_minor_unit,
        ]
        as_of_date: datetime.date = datetime.datetime(year=2024, month=3, day=1)
        expected_amount: int = 200

        # When
        amount, rate = currency_service.convert(
            amount=source_amount,
            source_currency_code=source_currency_code,
            target_currency_code=target_currency_code,
            as_of_date=as_of_date,
        )

        # Then
        assert (amount, rate) == (expected_amount, expected_rate)


class TestToMinorUnitAmount:
    @staticmethod
    @pytest.mark.parametrize(
        argnames=("amount", "minor_unit", "expected_minor_unit_amount"),
        argvalues=[
            (Decimal("1.00"), 2, 100),
            (Decimal("1.1234"), 2, 112),
            (Decimal("1.12"), 4, 11200),
            (Decimal("1.1350"), 2, 114),
            (Decimal("123.4345"), 0, 123),
        ],
        ids=[
            "no-rounding",
            "round-down",
            "pad-additional-zeroes",
            "round-up",
            "zero-minor-unit",
        ],
    )
    def test_to_minor_unit_amount(
        currency_service: CurrencyService,
        amount: Decimal,
        minor_unit: int,
        expected_minor_unit_amount: int,
    ):
        # Given parameters

        # When
        minor_unit_amount: int = currency_service._to_minor_unit_amount(
            amount=amount, minor_unit=minor_unit
        )

        # Then
        assert expected_minor_unit_amount == minor_unit_amount

    @staticmethod
    def test_to_minor_unit_amount_raises_exception_on_negative_minor_unit(
        currency_service: CurrencyService,
    ):
        # Given
        amount = Decimal("1.00")
        minor_unit: int = -3

        # When - Then
        with pytest.raises(ValueError, match="currency minor unit cannot be negative"):
            currency_service._to_minor_unit_amount(amount=amount, minor_unit=minor_unit)

    @staticmethod
    def test_to_minor_amount_calls_get_minor_unit(currency_service: CurrencyService):
        # Given
        money = Money(amount=Decimal("1.99"), currency_code="AUD")
        minor_unit: int = 2
        currency_service.currency_code_repo.get_minor_unit.return_value = minor_unit

        # When
        currency_service.to_minor_unit_amount(money=money)

        # Then
        currency_service.currency_code_repo.get_minor_unit.assert_called_with(
            currency_code=money.currency_code
        )

    @staticmethod
    def test_to_minor_amount_calls_private_to_minor_unit_amount(
        currency_service: CurrencyService,
    ):
        # Given
        money = Money(amount=Decimal("1.99"), currency_code="AUD")
        minor_unit: int = 2
        currency_service.currency_code_repo.get_minor_unit.return_value = minor_unit

        # When
        with mock.patch(
            "wallet.services.currency.CurrencyService._to_minor_unit_amount"
        ) as mock_to_minor_unit_amount:
            currency_service.to_minor_unit_amount(money=money)

        # Then
        mock_to_minor_unit_amount.assert_called_with(
            amount=money.amount, minor_unit=minor_unit
        )

    @staticmethod
    def test_to_minor_amount_returns_minor_unit_amount(
        currency_service: CurrencyService,
    ):
        # Given
        money = Money(amount=Decimal("1.99"), currency_code="AUD")
        minor_unit: int = 2
        currency_service.currency_code_repo.get_minor_unit.return_value = minor_unit
        expected_amount: int = 199

        # When
        amount: int = currency_service.to_minor_unit_amount(money=money)

        # Then
        assert amount == expected_amount

    @staticmethod
    def test_to_minor_amount_returns_int_type(currency_service: CurrencyService):
        # Given
        money = Money(amount=Decimal("1.99"), currency_code="AUD")
        minor_unit: int = 2
        currency_service.currency_code_repo.get_minor_unit.return_value = minor_unit

        # When
        amount: int = currency_service.to_minor_unit_amount(money=money)

        # Then
        assert isinstance(amount, int)


class TestProcessReimbursementRequest:
    @staticmethod
    def test_no_category_set_raises_exception(
        currency_service: CurrencyService,
    ):
        # Given
        amount = Money(amount=Decimal("1.00"), currency_code="AUD")
        request: ReimbursementRequest = ReimbursementRequest()

        # When - Then
        with pytest.raises(
            InvalidCurrencyConversionRequest,
            match="reimbursement_request_category_id is not set",
        ):
            currency_service.process_reimbursement_request(
                transaction=amount, request=request
            )

    @staticmethod
    def test_non_usd_benefit_currency_and_custom_rate_raises_exception(
        currency_service: CurrencyService, basic_qualified_wallet: ReimbursementWallet
    ):
        # Given
        amount = Money(amount=Decimal("1.00"), currency_code="GBP")
        category: ReimbursementOrgSettingCategoryAssociation = (
            basic_qualified_wallet.get_or_create_wallet_allowed_categories[0]
        )
        category.currency_code = "AUD"
        request: ReimbursementRequest = ReimbursementRequestFactory.create(
            reimbursement_wallet_id=basic_qualified_wallet.id,
            reimbursement_request_category_id=category.reimbursement_request_category.id,
        )
        custom_rate = Decimal("2.00")

        # When - Then
        with pytest.raises(
            InvalidCurrencyConversionRequest,
            match=f"Benefit currency of {category.currency_code} does not support usage of custom_rate",
        ):
            currency_service.process_reimbursement_request(
                transaction=amount,
                request=request,
                custom_rate=custom_rate,
            )

    @staticmethod
    def test_usd_benefit_currency_and_usd_transaction_with_custom_rate_raises_exception(
        currency_service: CurrencyService, basic_qualified_wallet: ReimbursementWallet
    ):
        # Given
        amount = Money(amount=Decimal("1.00"), currency_code="USD")
        category: ReimbursementOrgSettingCategoryAssociation = (
            basic_qualified_wallet.get_or_create_wallet_allowed_categories[0]
        )
        category.currency_code = "USD"
        request: ReimbursementRequest = ReimbursementRequestFactory.create(
            reimbursement_wallet_id=basic_qualified_wallet.id,
            reimbursement_request_category_id=category.reimbursement_request_category.id,
        )
        custom_rate = Decimal("2.00")

        # When - Then
        with pytest.raises(
            InvalidCurrencyConversionRequest,
            match="Custom rate is not supported when the transaction currency is already in USD",
        ):
            currency_service.process_reimbursement_request(
                transaction=amount,
                request=request,
                custom_rate=custom_rate,
            )

    @staticmethod
    def test_non_usd_transaction_with_direct_payment_enabled_raises_exception(
        currency_service: CurrencyService, direct_payment_wallet: ReimbursementWallet
    ):
        # Given
        amount = Money(amount=Decimal("1.00"), currency_code="AUD")
        category: ReimbursementOrgSettingCategoryAssociation = (
            direct_payment_wallet.get_or_create_wallet_allowed_categories[0]
        )
        category.currency_code = "USD"
        request: ReimbursementRequest = ReimbursementRequestFactory.create(
            reimbursement_wallet_id=direct_payment_wallet.id,
            reimbursement_request_category_id=category.reimbursement_request_category.id,
        )
        custom_rate = Decimal("2.00")

        # When - Then
        with pytest.raises(
            InvalidCurrencyConversionRequest,
            match="Direct payment enabled wallets do not support non-USD transactions",
        ):
            currency_service.process_reimbursement_request(
                transaction=amount,
                request=request,
                custom_rate=custom_rate,
            )

    @staticmethod
    @pytest.mark.parametrize(
        argnames=(
            "transaction_amount",
            "transaction_currency_code",
            "minor_unit_amount",
            "benefit_currency_code",
            "custom_rate",
        ),
        argvalues=[
            (Decimal("123.23"), "USD", 12323, "USD", None),
            (Decimal("123.23"), "GBP", 12323, "USD", Decimal("2.00")),
            (Decimal("10.00"), "AUD", 1000, "GBP", None),
            (Decimal("390.23"), "NZD", 39023, "NZD", None),
        ],
        ids=[
            "transaction-and-benefit-currency-code-in-USD",
            "transaction-in-GBP-benefit-currency-code-in-GBP-custom-rate",
            "transaction-and-benefit-currency-code-not-in-USD",
            "transaction-and-benefit-currency-code-same-not-in-USD",
        ],
    )
    def test_convert_has_correct_calls(
        currency_service: CurrencyService,
        basic_qualified_wallet: ReimbursementWallet,
        transaction_amount: Decimal,
        transaction_currency_code: str,
        minor_unit_amount: int,
        benefit_currency_code: str,
        custom_rate: Decimal | None,
    ):
        # Given
        as_of_date = datetime.datetime.fromisoformat("2024-03-12")
        category: ReimbursementOrgSettingCategoryAssociation = (
            basic_qualified_wallet.get_or_create_wallet_allowed_categories[0]
        )
        category.currency_code = benefit_currency_code
        expected_request: ReimbursementRequest = ReimbursementRequestFactory.create(
            transaction_amount=transaction_amount,
            transaction_currency_code=transaction_currency_code,
            reimbursement_wallet_id=basic_qualified_wallet.id,
            reimbursement_request_category_id=category.reimbursement_request_category.id,
            service_start_date=as_of_date,
        )
        amount = Money(
            amount=transaction_amount, currency_code=transaction_currency_code
        )
        expected_calls = [
            mock.call(
                amount=minor_unit_amount,
                source_currency_code=transaction_currency_code,
                target_currency_code="USD",
                rate=custom_rate,
                as_of_date=expected_request.created_at.date(),
            ),
            mock.call(
                amount=minor_unit_amount,
                source_currency_code=transaction_currency_code,
                target_currency_code=benefit_currency_code,
                rate=custom_rate,
                as_of_date=expected_request.created_at.date(),
            ),
        ]

        # When
        with mock.patch(
            "wallet.services.currency.CurrencyService.convert"
        ) as mock_convert, mock.patch(
            "wallet.services.currency.CurrencyService.to_minor_unit_amount"
        ) as mock_to_minor_unit_amount:
            mock_convert.return_value = (None, None)
            mock_to_minor_unit_amount.return_value = minor_unit_amount
            currency_service.process_reimbursement_request(
                transaction=amount,
                request=expected_request,
                custom_rate=custom_rate,
            )

        # Then
        mock_convert.assert_has_calls(calls=expected_calls)

    @staticmethod
    def test_process_reimbursement_request_uses_created_at_date_for_conversion(
        currency_service: CurrencyService, basic_qualified_wallet: ReimbursementWallet
    ):
        # Given
        service_start_datetime = datetime.datetime.fromisoformat("2024-03-01")
        created_at_datetime = datetime.datetime.fromisoformat("2024-05-01")

        expected_as_of_datetime = created_at_datetime

        category: ReimbursementOrgSettingCategoryAssociation = (
            basic_qualified_wallet.get_or_create_wallet_allowed_categories[0]
        )
        category.currency_code = "USD"
        expected_request: ReimbursementRequest = ReimbursementRequestFactory.create(
            reimbursement_wallet_id=basic_qualified_wallet.id,
            reimbursement_request_category_id=category.reimbursement_request_category.id,
            service_start_date=service_start_datetime,
        )
        expected_request.created_at = created_at_datetime

        amount = Money(amount=Decimal("100.00"), currency_code="GBP")
        expected_calls = [
            mock.call(
                amount=100_00,
                source_currency_code="GBP",
                target_currency_code="USD",
                rate=None,
                as_of_date=expected_as_of_datetime.date(),
            ),
            mock.call(
                amount=100_00,
                source_currency_code="GBP",
                target_currency_code="USD",
                rate=None,
                as_of_date=expected_as_of_datetime.date(),
            ),
        ]

        # When
        with mock.patch(
            "wallet.services.currency.CurrencyService.convert"
        ) as mock_convert, mock.patch(
            "wallet.services.currency.CurrencyService.to_minor_unit_amount"
        ) as mock_to_minor_unit_amount:
            mock_convert.return_value = (None, None)
            mock_to_minor_unit_amount.return_value = 100_00
            currency_service.process_reimbursement_request(
                transaction=amount, request=expected_request
            )

        # Then
        mock_convert.assert_has_calls(calls=expected_calls)

    @staticmethod
    def test_process_reimbursement_request_sets_correct_values(
        currency_service: CurrencyService,
        basic_qualified_wallet: ReimbursementWallet,
    ):
        # Given
        transaction_minor_unit_amount: int = 100
        transaction_decimal_amount = Decimal("1.00")
        transaction_currency_code: str = "GBP"
        amount = Money(
            amount=transaction_decimal_amount, currency_code=transaction_currency_code
        )
        benefit_currency_code: str = "AUD"
        category: ReimbursementOrgSettingCategoryAssociation = (
            basic_qualified_wallet.get_or_create_wallet_allowed_categories[0]
        )
        category.currency_code = benefit_currency_code
        expected_request: ReimbursementRequest = ReimbursementRequestFactory.create(
            transaction_amount=transaction_decimal_amount,
            transaction_currency_code=transaction_currency_code,
            reimbursement_wallet_id=basic_qualified_wallet.id,
            reimbursement_request_category_id=category.reimbursement_request_category.id,
            service_start_date=datetime.datetime(year=2024, month=3, day=1),
        )

        usd_amount: int = 200
        transaction_to_usd_rate: Decimal = Decimal("2.00")
        benefit_amount: int = 300
        transaction_to_benefit_rate: Decimal = Decimal("3.00")

        # When
        with mock.patch(
            "wallet.services.currency.CurrencyService.convert"
        ) as mock_convert, mock.patch(
            "wallet.services.currency.CurrencyService.to_minor_unit_amount"
        ) as mock_to_minor_unit_amount:
            mock_convert.side_effect = [
                (usd_amount, transaction_to_usd_rate),
                (benefit_amount, transaction_to_benefit_rate),
            ]
            mock_to_minor_unit_amount.return_value = transaction_minor_unit_amount
            currency_service.process_reimbursement_request(
                transaction=amount, request=expected_request
            )

        # Then
        assert (
            expected_request.transaction_amount,
            expected_request.transaction_currency_code,
            expected_request.benefit_currency_code,
            expected_request.usd_amount,
            expected_request.transaction_to_usd_rate,
            expected_request.amount,
            expected_request.transaction_to_benefit_rate,
        ) == (
            transaction_minor_unit_amount,
            transaction_currency_code,
            benefit_currency_code,
            usd_amount,
            transaction_to_usd_rate,
            benefit_amount,
            transaction_to_benefit_rate,
        )


class TestFormatAmountObj:
    @staticmethod
    def test_format_amount_obj_returns_correct_fields(
        currency_service: CurrencyService,
    ):
        # Given
        amount: int = 100
        currency_code: str = "USD"
        expected_keys = (
            "currency_code",
            "amount",
            "formatted_amount",
            "formatted_amount_truncated",
            "raw_amount",
        )

        # When
        with mock.patch(
            "wallet.services.currency.CurrencyService.to_money"
        ) as mock_to_money:
            mock_to_money.return_value = Money(
                amount=Decimal("1.00"), currency_code=currency_code
            )
            returned: dict = currency_service.format_amount_obj(
                amount=amount, currency_code=currency_code
            )

        # Then
        assert all(key in returned for key in expected_keys)

    @staticmethod
    def test_format_amount_obj_correct_default_values(
        currency_service: CurrencyService,
    ):
        # Given
        default_currency_code: str = "USD"
        default_amount: int = 0

        # When
        with mock.patch(
            "wallet.services.currency.CurrencyService.to_money"
        ) as mock_to_money:
            mock_to_money.return_value = Money(
                amount=Decimal("0"), currency_code=default_currency_code
            )
            currency_service.format_amount_obj(amount=None, currency_code=None)

        # Then
        mock_to_money.assert_called_with(
            amount=default_amount, currency_code=default_currency_code
        )


class TestProcessReimbursementRequestAdjustment:
    @staticmethod
    def test_legacy_usd_requests(currency_service: CurrencyService):
        # Given
        amount: int = 100000
        adjusted_amount: int = 123456
        request = ReimbursementRequest(benefit_currency_code=None, amount=amount)

        # When
        currency_service.process_reimbursement_request_adjustment(
            request=request, adjusted_usd_amount=adjusted_amount
        )

        # Then
        assert request.amount == adjusted_amount

    @staticmethod
    @pytest.mark.parametrize(
        argnames="null_field", argvalues=["amount", "usd_amount", "transaction_amount"]
    )
    def test_missing_amounts_raises_exception(
        currency_service: CurrencyService, null_field: str
    ):
        # Given
        amount_fields = ["amount", "usd_amount", "transaction_amount"]
        request = ReimbursementRequest(
            transaction_to_benefit_rate=Decimal("1.00"),
            transaction_to_usd_rate=Decimal("1.00"),
            benefit_currency_code="USD",
        )

        for field in amount_fields:
            if field == null_field:
                setattr(request, null_field, None)
            else:
                setattr(request, null_field, 10000)

        # When - Then
        with pytest.raises(
            InvalidAdjustmentRequest,
            match=f"ReimbursementRequest id={request.id} is missing necessary params for an amount adjustment",
        ):
            currency_service.process_reimbursement_request_adjustment(
                request=request, adjusted_usd_amount=10000
            )

    @staticmethod
    def test_no_adjustment_necessary(currency_service: CurrencyService):
        # Given
        amount = 2000
        expected_request = ReimbursementRequest(
            benefit_currency_code="USD",
            transaction_currency_code="GBP",
            amount=amount,
            usd_amount=amount,
            transaction_amount=1000,
            transaction_to_benefit_rate=Decimal("2.00"),
            transaction_to_usd_rate=Decimal("2.00"),
        )

        # When
        request = currency_service.process_reimbursement_request_adjustment(
            request=expected_request, adjusted_usd_amount=amount
        )

        # Then
        assert request == expected_request

    @staticmethod
    @pytest.mark.parametrize(
        argnames=(
            "benefit_currency_code",
            "transaction_currency_code",
            "amount",
            "transaction_amount",
            "usd_amount",
            "transaction_to_benefit_rate",
            "transaction_to_usd_rate",
            "adjusted_usd_amount",
            "expected_amount",
            "expected_transaction_amount",
        ),
        argvalues=[
            ("USD", "AUD", 100, 200, 100, Decimal("0.5"), Decimal("0.5"), 50, 50, 100),
            ("NZD", "GBP", 200, 100, 400, Decimal("0.5"), Decimal("4.0"), 200, 100, 50),
            ("USD", "USD", 100, 100, 100, Decimal("1.0"), Decimal("1.0"), 50, 50, 50),
        ],
    )
    def test_convert_has_correct_calls(
        currency_service: CurrencyService,
        benefit_currency_code: str,
        transaction_currency_code: str,
        amount: int,
        usd_amount: int,
        transaction_amount: int,
        transaction_to_benefit_rate: Decimal,
        transaction_to_usd_rate: Decimal,
        adjusted_usd_amount: int,
        expected_amount: int,
        expected_transaction_amount: int,
    ):
        # Given
        request = ReimbursementRequest(
            benefit_currency_code=benefit_currency_code,
            transaction_currency_code=transaction_currency_code,
            amount=amount,
            usd_amount=usd_amount,
            transaction_amount=transaction_amount,
            transaction_to_benefit_rate=transaction_to_benefit_rate,
            transaction_to_usd_rate=transaction_to_usd_rate,
        )
        expected_calls = [
            mock.call(
                currency_service,
                amount=adjusted_usd_amount,
                source_currency_code="USD",
                target_currency_code=transaction_currency_code,
                rate=1 / transaction_to_usd_rate,
            ),
            mock.call(
                currency_service,
                amount=expected_transaction_amount,
                source_currency_code=transaction_currency_code,
                target_currency_code=benefit_currency_code,
                rate=transaction_to_benefit_rate,
            ),
        ]

        # When
        with mock.patch(
            "wallet.services.currency.CurrencyService.convert", autospec=True
        ) as mock_convert:
            mock_convert.side_effect = [
                (expected_transaction_amount, mock.MagicMock),
                (expected_amount, mock.MagicMock),
            ]
            currency_service.process_reimbursement_request_adjustment(
                request=request, adjusted_usd_amount=adjusted_usd_amount
            )

        # Then
        mock_convert.assert_has_calls(expected_calls)

    @staticmethod
    @pytest.mark.parametrize(
        argnames=(
            "benefit_currency_code",
            "transaction_currency_code",
            "amount",
            "transaction_amount",
            "usd_amount",
            "transaction_to_benefit_rate",
            "transaction_to_usd_rate",
            "adjusted_usd_amount",
            "expected_amount",
            "expected_transaction_amount",
        ),
        argvalues=[
            ("USD", "AUD", 100, 200, 100, Decimal("0.5"), Decimal("0.5"), 50, 50, 100),
            ("NZD", "GBP", 200, 100, 400, Decimal("0.5"), Decimal("4.0"), 200, 100, 50),
            ("USD", "USD", 100, 100, 100, Decimal("1.0"), Decimal("1.0"), 50, 50, 50),
        ],
    )
    def test_convert_sets_correct_values(
        currency_service: CurrencyService,
        benefit_currency_code: str,
        transaction_currency_code: str,
        amount: int,
        usd_amount: int,
        transaction_amount: int,
        transaction_to_benefit_rate: Decimal,
        transaction_to_usd_rate: Decimal,
        adjusted_usd_amount: int,
        expected_amount: int,
        expected_transaction_amount: int,
    ):
        # Given
        request = ReimbursementRequest(
            benefit_currency_code=benefit_currency_code,
            transaction_currency_code=transaction_currency_code,
            amount=amount,
            usd_amount=usd_amount,
            transaction_amount=transaction_amount,
            transaction_to_benefit_rate=transaction_to_benefit_rate,
            transaction_to_usd_rate=transaction_to_usd_rate,
        )

        # When
        with mock.patch(
            "wallet.services.currency.CurrencyService.convert"
        ) as mock_convert:
            mock_convert.side_effect = [
                (expected_transaction_amount, mock.MagicMock),
                (expected_amount, mock.MagicMock),
            ]
            currency_service.process_reimbursement_request_adjustment(
                request=request, adjusted_usd_amount=adjusted_usd_amount
            )

        # Then
        assert (request.amount, request.transaction_amount, request.usd_amount) == (
            expected_amount,
            expected_transaction_amount,
            adjusted_usd_amount,
        )
