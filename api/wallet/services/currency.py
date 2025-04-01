from __future__ import annotations

import datetime
from decimal import ROUND_HALF_UP, Context, Decimal
from typing import Tuple

import ddtrace

from utils.log import logger
from wallet.models.currency import Money
from wallet.models.reimbursement import ReimbursementRequest
from wallet.models.reimbursement_organization_settings import (
    ReimbursementOrgSettingCategoryAssociation,
)
from wallet.repository.currency_code import CurrencyCodeRepository
from wallet.repository.currency_fx_rate import (
    CurrencyFxRateRepository,
    InvalidExchangeRate,
)
from wallet.utils.currency import (
    format_display_amount,
    format_raw_amount,
    format_truncated_amount,
)

log = logger(__name__)

# Decimal.Context() to use for calculations with, 28 precision is the default
ctx: Context = Context(prec=28, rounding=ROUND_HALF_UP)
DEFAULT_CURRENCY_CODE: str = "USD"


class CurrencyService:
    def __init__(
        self,
        currency_code_repo: CurrencyCodeRepository | None = None,
        currency_fx_rate_repo: CurrencyFxRateRepository | None = None,
    ):
        self.currency_code_repo: CurrencyCodeRepository = (
            currency_code_repo or CurrencyCodeRepository()
        )
        self.fx_rate_repo: CurrencyFxRateRepository = (
            currency_fx_rate_repo or CurrencyFxRateRepository()
        )

    @staticmethod
    @ddtrace.tracer.wrap()
    def _convert(
        amount: int,
        source_minor_unit: int,
        target_minor_unit: int,
        rate: Decimal,
    ) -> int:
        """
        Private staticmethod to do the math in a currency conversion

        Args:
            amount: amount in minor currency unit of source currency
            source_minor_unit: minor unit of the source currency
            target_minor_unit: minor unit of the target currency
            rate: conversion rate

        Returns:
            amount in minor currency unit of target currency
        """
        target_amount: Decimal = ctx.multiply(amount, rate)
        factor: Decimal = ctx.power(ctx.radix(), target_minor_unit - source_minor_unit)
        minor_unit_amount: Decimal = ctx.multiply(target_amount, factor)
        return int(round(minor_unit_amount, 0))

    @staticmethod
    @ddtrace.tracer.wrap()
    def _to_decimal_amount(amount: int, minor_unit: int) -> Decimal:
        """
        Convert from currency minor unit amount to a decimal representation.

        Args:
            amount: Integer amount in minor units
            minor_unit: ISO 4217 currency minor unit of the input amount

        Returns:
            Decimal representation of the amount
        """
        if minor_unit < 0:
            raise ValueError("currency minor unit cannot be negative")

        return ctx.divide(Decimal(amount), ctx.power(ctx.radix(), minor_unit))

    @staticmethod
    @ddtrace.tracer.wrap()
    def _to_minor_unit_amount(amount: Decimal, minor_unit: int) -> int:
        """
        Convert from decimal to currency minor unit amount

        Args:
            amount: Decimal amount
            minor_unit: ISO 4217 currency minor unit of the input amount

        Returns:
            integer currency minor unit representation of the amount
        """
        if minor_unit < 0:
            raise ValueError("currency minor unit cannot be negative")

        return int(round(ctx.multiply(amount, ctx.power(ctx.radix(), minor_unit)), 0))

    @ddtrace.tracer.wrap()
    def to_money(self, amount: int, currency_code: str) -> Money:
        """
        Convert a minor unit currency integer along with a currency_code to a Money obj

        Args:
            amount: minor unit integer amount
            currency_code: ISO 4217 currency code:

        Returns:
            Money class $$$, contains a decimal representation and currency code
        """
        minor_unit: int = self.currency_code_repo.get_minor_unit(
            currency_code=currency_code
        )
        decimal_amount: Decimal = CurrencyService._to_decimal_amount(
            amount=amount, minor_unit=minor_unit
        )
        return Money(amount=decimal_amount, currency_code=currency_code)

    @ddtrace.tracer.wrap()
    def to_minor_unit_amount(self, money: Money) -> int:
        """
        Convert a Money obj to minor unit currency integer

        Args:
            Money class $$$, contains a decimal representation and currency code

        Returns:
            amount: minor unit integer amount
        """
        minor_unit: int = self.currency_code_repo.get_minor_unit(
            currency_code=money.currency_code
        )
        minor_unit_amount: int = CurrencyService._to_minor_unit_amount(
            amount=money.amount, minor_unit=minor_unit
        )
        return minor_unit_amount

    @ddtrace.tracer.wrap()
    def convert(
        self,
        amount: int,
        source_currency_code: str,
        target_currency_code: str,
        rate: Decimal | None = None,
        as_of_date: datetime.date | None = None,
    ) -> Tuple[int, Decimal]:
        """
        Public method for currency conversion between minor unit amounts
        Args:
            amount: amount in minor currency unit of source currency
            source_currency_code: ISO 4217 currency code of source currency
            target_currency_code: ISO 4217 currency code of target currency
            rate: Optional exchange rate to use
            as_of_date: Determines the valid FX rate that is used at this point in time, defaults to current date

        Returns:
            Tuple[amount, rate] - the minor unit amount and the FX rate used to perform the conversion
        """
        if as_of_date is None:
            as_of_date = datetime.date.today()

        # Use a custom rate that is passed in
        if rate is None:
            rate = self.fx_rate_repo.get_rate(
                source_currency_code=source_currency_code,
                target_currency_code=target_currency_code,
                as_of_date=as_of_date,
            )

        if rate <= Decimal("0"):
            raise InvalidExchangeRate("Exchange rate cannot be less than or equal to 0")

        source_minor_unit: int = self.currency_code_repo.get_minor_unit(
            source_currency_code
        )
        target_minor_unit: int = self.currency_code_repo.get_minor_unit(
            target_currency_code
        )

        return (
            CurrencyService._convert(
                amount=amount,
                source_minor_unit=source_minor_unit,
                target_minor_unit=target_minor_unit,
                rate=rate,
            ),
            rate,
        )

    def format_amount_obj(
        self,
        amount: int | None = None,
        currency_code: str | None = None,
    ) -> dict:
        # if amount is None, assume 0
        amount = int(amount or 0)
        currency_code = str(currency_code or DEFAULT_CURRENCY_CODE)

        money: Money = self.to_money(amount=amount, currency_code=currency_code)

        return {
            "currency_code": currency_code.upper(),
            "amount": amount,
            "formatted_amount": format_display_amount(money=money),
            "formatted_amount_truncated": format_truncated_amount(money=money),
            "raw_amount": format_raw_amount(money=money),
        }

    @ddtrace.tracer.wrap()
    def process_reimbursement_request(
        self,
        *,
        transaction: Money,
        request: ReimbursementRequest,
        custom_rate: Decimal | None = None,
    ) -> ReimbursementRequest:
        """
        Args:
            transaction: Money representation of the transaction
            request: An instance of ReimbursementRequest
            custom_rate: If not supplied, will use standard rates

        Returns:
            ReimbursementRequest - enriched with converted amounts in benefit currency and USD
        """
        if not request.category:
            raise InvalidCurrencyConversionRequest(
                "reimbursement_request_category_id is not set"
            )

        if not request.wallet:
            raise InvalidCurrencyConversionRequest("reimbursement_wallet_id is not set")

        # Fetch the category association based on the request category and wallet
        category_association: ReimbursementOrgSettingCategoryAssociation | None = (
            request.category.get_category_association(
                reimbursement_wallet=request.wallet
            )
        )
        direct_payment_enabled: bool = request.category.is_direct_payment_eligible(
            reimbursement_wallet=request.wallet
        )

        if not category_association:
            raise InvalidCurrencyConversionRequest(
                "Can't find category association for wallet and reimbursement request"
            )

        benefit_currency_code: str = (
            category_association.currency_code or DEFAULT_CURRENCY_CODE
        )

        # Only support usage of custom rates if benefit currency is USD
        if custom_rate is not None and benefit_currency_code != DEFAULT_CURRENCY_CODE:
            raise InvalidCurrencyConversionRequest(
                f"Benefit currency of {benefit_currency_code} does not support usage of custom_rate"
            )

        # Don't allow custom rate calculation if the transaction_currency is also USD
        if (
            custom_rate is not None
            and transaction.currency_code == DEFAULT_CURRENCY_CODE
        ):
            raise InvalidCurrencyConversionRequest(
                "Custom rate is not supported when the transaction currency is already in USD"
            )

        # Don't allow direct_payment_enabled wallets to have non-USD transactions
        if (
            direct_payment_enabled is True
            and transaction.currency_code != DEFAULT_CURRENCY_CODE
        ):
            raise InvalidCurrencyConversionRequest(
                "Direct payment enabled wallets do not support non-USD transactions"
            )

        # Set use_custom_rate appropriately
        request.use_custom_rate = False if custom_rate is None else True

        usd_amount: int
        transaction_to_usd_rate: Decimal
        benefit_amount: int
        transaction_to_benefit_rate: Decimal

        transaction_amount: int = self.to_minor_unit_amount(money=transaction)
        # Use submission date to determine conversion fx rate
        as_of_date: datetime.date = request.created_at.date()

        usd_amount, transaction_to_usd_rate = self.convert(
            amount=transaction_amount,
            source_currency_code=transaction.currency_code,
            target_currency_code=DEFAULT_CURRENCY_CODE,
            rate=custom_rate,
            as_of_date=as_of_date,
        )
        benefit_amount, transaction_to_benefit_rate = self.convert(
            amount=transaction_amount,
            source_currency_code=transaction.currency_code,
            target_currency_code=benefit_currency_code,
            rate=custom_rate,
            as_of_date=as_of_date,
        )

        # Set the original transaction_amount and transaction_currency_code
        request.transaction_amount = transaction_amount
        request.transaction_currency_code = transaction.currency_code

        # Set the converted values back on the original ReimbursementRequest
        request.usd_amount = usd_amount
        request.transaction_to_usd_rate = transaction_to_usd_rate

        # Set the benefit amount
        request.amount = benefit_amount
        request.benefit_currency_code = benefit_currency_code
        request.transaction_to_benefit_rate = transaction_to_benefit_rate

        return request

    def process_reimbursement_request_adjustment(
        self, *, request: ReimbursementRequest, adjusted_usd_amount: int
    ) -> ReimbursementRequest:
        # Handle older legacy requests where benefit_currency_code is None
        if request.benefit_currency_code is None:
            request.amount = adjusted_usd_amount
            return request

        # TODO: Make sure we update this when we backfill this data
        if None in (
            request.amount,
            request.usd_amount,
            request.transaction_amount,
            request.transaction_to_usd_rate,
            request.transaction_to_benefit_rate,
        ):
            log.error(
                "Invalid request passed to process_reimbursement_request_adjustment",
                reimbursement_request_id=str(request.id),
            )
            raise InvalidAdjustmentRequest(
                f"ReimbursementRequest id={request.id} is missing necessary params for an amount adjustment"
            )

        if request.usd_amount == adjusted_usd_amount:
            log.info(
                "process_reimbursement_request_adjustment - No adjustments necessary since adjusted_usd_amount == usd_amount",
                reimbursement_request_id=str(request.id),
            )
            return request

        # For logging purposes
        original_usd_amount: int = request.usd_amount  # type: ignore[assignment] # Incompatible types in assignment (expression has type "Optional[int]", variable has type "int")
        original_amount: int = request.amount
        original_transaction_amount: int = request.transaction_amount  # type: ignore[assignment] # Incompatible types in assignment (expression has type "Optional[int]", variable has type "int")

        # Convert new usd_amount (USD) -> transaction_amount (transaction_currency_code)
        usd_to_transaction_rate = ctx.divide(1, request.transaction_to_usd_rate)
        adjusted_transaction_amount, _ = self.convert(
            amount=adjusted_usd_amount,
            source_currency_code=DEFAULT_CURRENCY_CODE,
            target_currency_code=request.transaction_currency_code,
            rate=usd_to_transaction_rate,
        )

        # Then, convert new transaction_amount (transaction_currency_code) -> amount (benefit_currency_code)
        adjusted_benefit_amount, _ = self.convert(
            amount=adjusted_transaction_amount,
            source_currency_code=request.transaction_currency_code,
            target_currency_code=request.benefit_currency_code,
            rate=request.transaction_to_benefit_rate,
        )

        # Set the converted amounts
        request.transaction_amount = adjusted_transaction_amount
        request.amount = adjusted_benefit_amount
        request.usd_amount = adjusted_usd_amount

        log.info(
            "Successfully adjusted ReimbursementRequest with new amount via process_reimbursement_request_adjustment",
            reimbursement_request_id=str(request.id),
            original_usd_amount=str(original_usd_amount),
            original_amount=str(original_amount),
            original_transaction_amount=str(original_transaction_amount),
            usd_to_transaction_rate=str(usd_to_transaction_rate),
            transaction_to_benefit_rate=str(request.transaction_to_benefit_rate),
            adjusted_usd_amount=str(request.usd_amount),
            adjusted_amount=str(request.amount),
            adjusted_transaction_amount=str(request.transaction_amount),
        )

        return request


class InvalidAdjustmentRequest(Exception):
    pass


class InvalidCurrencyConversionRequest(Exception):
    pass
