from __future__ import annotations

import ddtrace.ext
import sqlalchemy.orm
from cachetools import func

from storage import connection
from utils.log import logger

log = logger(__name__)
trace_wrapper = ddtrace.tracer.wrap(span_type=ddtrace.ext.SpanTypes.SQL)


class CurrencyCodeRepository:
    def __init__(self, session: sqlalchemy.orm.scoping.ScopedSession = None):  # type: ignore[assignment] # Incompatible default for argument "session" (default has type "None", argument has type "scoped_session")
        self.session = session or connection.db.session

    @trace_wrapper
    @func.ttl_cache(maxsize=500, ttl=60 * 60)
    def get_minor_unit(self, currency_code: str) -> int:
        """
        Get the minor unit for the input currency_code

        Args:
            currency_code: iso 4217 currency code

        Returns:
            iso 4217 minor unit
        """
        if currency_code is None:
            raise ValueError("currency_code can't be None")
        if currency_code.strip() == "":
            raise ValueError("currency_code can't be empty string")

        query = """
            SELECT 
                minor_unit
            FROM country_currency_code
            WHERE currency_code = :currency_code
            LIMIT 1;
        """

        minor_unit: int | None = self.session.scalar(
            query,
            {
                "currency_code": currency_code.strip().upper(),
            },
        )

        if minor_unit is None:
            raise MissingCurrencyCode(
                f"Currency code is not configured: {currency_code}"
            )

        return minor_unit


class MissingCurrencyCode(Exception):
    pass
