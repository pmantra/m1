from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Dict, Tuple

import ddtrace.ext
import sqlalchemy.orm

from storage import connection
from utils.log import logger

log = logger(__name__)
trace_wrapper = ddtrace.tracer.wrap(span_type=ddtrace.ext.SpanTypes.SQL)


class CurrencyFxRateRepository:
    def __init__(self, session: sqlalchemy.orm.scoping.ScopedSession = None):  # type: ignore[assignment] # Incompatible default for argument "session" (default has type "None", argument has type "scoped_session")
        self.session = session or connection.db.session

    @trace_wrapper
    def get_direct_rate(
        self,
        source_currency_code: str,
        target_currency_code: str,
        as_of_date: date,
    ) -> Decimal:
        """
        Get a single exchange rate as stored in the DB, fallback to calculating the inverse.

        Args:
            source_currency_code: iso 4217 currency code
            target_currency_code: iso 4217 currency code
            as_of_date: the effective date for the rate

        Returns:
            exchange rate
        """
        if source_currency_code == target_currency_code:
            return Decimal("1.0")

        query = """
            (
                SELECT 
                    exchange_rate,
                    source_currency,
                    target_currency
                FROM reimbursement_request_exchange_rates
                WHERE (
                    source_currency=:source_currency_code
                    AND 
                    target_currency=:target_currency_code
                )
                AND trading_date <= :as_of_date
                ORDER BY trading_date DESC
                LIMIT 1
            )
            UNION
            (
                SELECT 
                    exchange_rate,
                    source_currency,
                    target_currency
                FROM reimbursement_request_exchange_rates
                WHERE (
                    source_currency=:target_currency_code
                    AND 
                    target_currency=:source_currency_code
                )
                AND trading_date <= :as_of_date
                ORDER BY trading_date DESC
                LIMIT 1
            );
        """

        rates = self.session.execute(
            query,
            {
                "source_currency_code": source_currency_code.upper(),
                "target_currency_code": target_currency_code.upper(),
                "as_of_date": str(as_of_date),
            },
        )

        # Create a lookup table of the fetched rates
        # if duplicated we should always have the latest populated
        rate_lookup: Dict[Tuple[str, str], Decimal] = {
            (rate["source_currency"], rate["target_currency"]): rate["exchange_rate"]
            for rate in rates
        }

        rate_pair: Tuple[str, str] = (source_currency_code, target_currency_code)
        use_inverse: bool = False
        # Try to look for the direct rate first
        if (rate := rate_lookup.get(rate_pair)) is not None:
            pass
        # Fall back to using the inverse rate
        elif (rate := rate_lookup.get(rate_pair[::-1])) is not None:
            use_inverse = True
        else:
            raise MissingExchangeRate(
                f"No rate found for {source_currency_code} to {target_currency_code} for {str(as_of_date.year)}"
            )

        if rate <= Decimal("0"):
            raise InvalidExchangeRate(f"Rate fetched is not valid: {str(rate)}")

        return 1 / rate if use_inverse else rate

    @trace_wrapper
    def get_rate(
        self,
        source_currency_code: str,
        target_currency_code: str,
        as_of_date: date,
    ) -> Decimal:
        """
        Get a single exchange rate as stored in the DB, fallback to trying to use an intermediate rate (USD).

        Args:
            source_currency_code: iso 4217 currency code
            target_currency_code: iso 4217 currency code
            as_of_date: the effective date for the rate

        Returns:
            exchange rate
        """
        try:
            rate: Decimal = self.get_direct_rate(
                source_currency_code=source_currency_code,
                target_currency_code=target_currency_code,
                as_of_date=as_of_date,
            )
        except MissingExchangeRate:
            # try via an intermediary currency, USD
            source_to_inter_rate: Decimal = self.get_direct_rate(
                source_currency_code=source_currency_code,
                target_currency_code="USD",
                as_of_date=as_of_date,
            )
            inter_to_target_rate: Decimal = self.get_direct_rate(
                source_currency_code="USD",
                target_currency_code=target_currency_code,
                as_of_date=as_of_date,
            )
            calculated_rate: Decimal = source_to_inter_rate * inter_to_target_rate
            log.info(
                f"Direct rate not found for {source_currency_code} -> {target_currency_code}, using USD intermediate rate",
                calculated_rate=str(calculated_rate),
                source_currency_code=source_currency_code,
                target_currency_code=target_currency_code,
            )
            return calculated_rate
        else:
            return rate

    @trace_wrapper
    def get_available_currency_and_minor_units(self) -> list[dict]:
        """
        Fetch a list of currency code and minor units based on the stored exchange rates

        Returns: List of currency codes and minor units that are stored
        """
        query = """
            SELECT DISTINCT
                all_currencies.currency_code,
                ccc.minor_unit
            FROM (
                SELECT target_currency as currency_code
                FROM reimbursement_request_exchange_rates
                    UNION
                SELECT source_currency as currency_code
                FROM reimbursement_request_exchange_rates
            ) as all_currencies
            INNER JOIN country_currency_code ccc
            ON ccc.currency_code = all_currencies.currency_code;
        """

        rates = self.session.execute(query)

        return [
            dict(currency_code=rate["currency_code"], minor_unit=rate["minor_unit"])
            for rate in rates
        ]


class BaseExchangeRateException(Exception):
    pass


class MissingExchangeRate(BaseExchangeRateException):
    pass


class InvalidExchangeRate(BaseExchangeRateException):
    pass
