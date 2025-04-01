from datetime import date
from decimal import Decimal
from unittest import mock

import factory
import pytest

from wallet.models.reimbursement_wallet import ReimbursementWallet
from wallet.pytests.factories import ReimbursementRequestExchangeRatesFactory

AVAILABLE_FX_RATES = [
    ("USD", "JPY", date(2024, 1, 1), Decimal("1.04")),
    ("AUD", "GBP", date(2024, 1, 1), Decimal("2.00")),
]


@pytest.fixture
def exchange_rates():
    ReimbursementRequestExchangeRatesFactory.create_batch(
        size=len(AVAILABLE_FX_RATES),
        source_currency=factory.Iterator(AVAILABLE_FX_RATES, getter=lambda fx: fx[0]),
        target_currency=factory.Iterator(AVAILABLE_FX_RATES, getter=lambda fx: fx[1]),
        trading_date=factory.Iterator(AVAILABLE_FX_RATES, getter=lambda fx: fx[2]),
        exchange_rate=factory.Iterator(AVAILABLE_FX_RATES, getter=lambda fx: fx[3]),
    )


class TestReimbursementWalletAvailableCurrencies:
    @staticmethod
    def test_available_currency(
        client,
        enterprise_user,
        api_helpers,
        exchange_rates,
        basic_qualified_wallet: ReimbursementWallet,
    ):
        # Given

        # When
        res = client.get(
            "/api/v1/reimbursement_wallet/available_currencies",
            headers=api_helpers.json_headers(enterprise_user),
        )
        content = api_helpers.load_json(res)

        # Then
        assert len(content) and res.status_code == 200

    @staticmethod
    def test_available_currency_exception(
        client,
        enterprise_user,
        api_helpers,
        exchange_rates,
        basic_qualified_wallet: ReimbursementWallet,
    ):
        # Given

        # When
        with mock.patch(
            "wallet.services.reimbursement_request.ReimbursementRequestService.get_available_currencies"
        ) as mock_get_available_currencies:
            mock_get_available_currencies.side_effect = Exception("An exception")
            res = client.get(
                "/api/v1/reimbursement_wallet/available_currencies",
                headers=api_helpers.json_headers(enterprise_user),
            )

        # Then
        assert res.status_code == 500
