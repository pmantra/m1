import json
import uuid
from unittest.mock import patch

import pytest
from requests import Response

from common import payments_gateway


@pytest.fixture
def mock_response():
    mock_response = Response()
    mock_response.status_code = 200
    mock_response.encoding = "application/json"
    return mock_response


@pytest.fixture
def create_payment_gateway_error_response():
    def create_error_response(status_code, body):
        mock_response = Response()
        mock_response.status_code = status_code
        mock_response.encoding = "application/json"
        mock_response._content = json.dumps(body).encode("utf-8")
        return mock_response

    return create_error_response


@pytest.fixture
def raw_customer_response(mock_response):
    mock_response._content = b"""
    {
      "customer_id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
      "customer_setup_status": "succeeded",
      "payment_method_types": [
        "us_bank_account",
        "card"
      ],
      "payment_methods": [
        {
          "payment_method_type": "us_bank_account",
          "last4": "4242",
          "brand": "visa"
        }
      ]
    }
    """
    return mock_response


@pytest.fixture
def gateway_429_error_response(create_payment_gateway_error_response):
    return create_payment_gateway_error_response(
        status_code=429,
        body={
            "status": 429,
            "title": "Rate Limit Payment Processor Error",
            "type": "rate_limit_payment_processor_error",
            "detail": "Please make your requests serially or at a lower rate.",
            "instance": "stripe:lock_timeout",
        },
    )


def test_make_request__success():
    mock_response = Response()
    mock_response.status_code = 200
    mock_response.json = lambda: {}

    with patch("common.base_http_client.requests.request") as mock_request:
        mock_request.return_value = mock_response

        client = payments_gateway.get_client("http://www.example.com")
        response = client.make_service_request("/foo")

    assert mock_request.call_args.kwargs["url"] == "http://www.example.com/foo"
    assert response is mock_response


def test_make_request__exception():
    with patch("common.base_http_client.requests.request") as mock_request:
        mock_request.side_effect = Exception("fubar")

        client = payments_gateway.get_client("http://www.example.com")
        response = client.make_service_request("/foo")
    assert response.status_code == 400


def test_create_customer__success(raw_customer_response):
    with patch("common.base_http_client.requests.request") as mock_request:
        mock_request.return_value = raw_customer_response

        client = payments_gateway.get_client()
        customer = client.create_customer()

        assert customer.customer_id == "3fa85f64-5717-4562-b3fc-2c963f66afa6"


def test_create_customer__invalid_data(mock_response):
    mock_response._content = b"""
    {
        "foo": "bar"
    }
    """

    with patch(
        "common.base_http_client.requests.request"
    ) as mock_request, pytest.raises(payments_gateway.PaymentsGatewayException) as e:
        mock_request.return_value = mock_response

        client = payments_gateway.get_client()
        client.create_customer()

    assert e.value.code == 500


def test_create_customer__request_exception():
    with patch(
        "common.base_http_client.requests.request"
    ) as mock_request, pytest.raises(payments_gateway.PaymentsGatewayException) as e:
        mock_request.side_effect = Exception("fubar")

        client = payments_gateway.get_client()
        client.create_customer()

    assert e.value.code == 400


class TestPaymentGatewayGetCustomer:
    def test_get_customer__success(self, raw_customer_response):
        with patch("common.base_http_client.requests.request") as mock_request:
            mock_request.return_value = raw_customer_response

            client = payments_gateway.get_client()
            customer = client.get_customer("3fa85f64-5717-4562-b3fc-2c963f66afa6")

            assert customer.customer_id == "3fa85f64-5717-4562-b3fc-2c963f66afa6"

    def test_get_customer__invalid_data(self, mock_response):
        mock_response._content = b"""
        {
            "foo": "bar"
        }
        """

        with patch(
            "common.base_http_client.requests.request"
        ) as mock_request, pytest.raises(
            payments_gateway.PaymentsGatewayException
        ) as e:
            mock_request.return_value = mock_response

            client = payments_gateway.get_client()
            client.get_customer("foo")

        assert e.value.code == 500

    def test_get_customer__failure(self, mock_response):
        with patch(
            "common.base_http_client.requests.request"
        ) as mock_request, pytest.raises(
            payments_gateway.PaymentsGatewayException
        ) as e:
            mock_request.side_effect = Exception("fubar")

            client = payments_gateway.get_client()
            client.get_customer("foo")

        assert e.value.code == 400


@pytest.fixture
def charge_transaction_payload():
    client = payments_gateway.get_client()
    transaction_data = client.create_charge_payload(
        amount=50000,
        customer_id=uuid.UUID("a9a85fd4-5717-4562-b3fc-2c963f65afa6"),
        metadata={
            "source": "TreatmentProcedure",
            "source_id": "1243564576876",
        },
        payment_method_id="",
    )
    return transaction_data


class TestPaymentGatewayTransaction:
    def test_create_charge__success(self, mock_response, charge_transaction_payload):
        mock_response._content = b"""
        {
          "transaction_id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
          "transaction_data": {
            "transaction_type": "charge",
            "customer_id": "a9a85fd4-5717-4562-b3fc-2c963f65afa6",
            "amount": 50000
          },
          "status": "pending",
          "metadata": {
            "payments_id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
            "source_type": "TreatmentProcedure",
            "source_id": "1243564576876"
          }
        }
        """

        with patch("common.base_http_client.requests.request") as mock_request:
            mock_request.return_value = mock_response

            client = payments_gateway.get_client()
            transaction = client.create_transaction(charge_transaction_payload)

        assert transaction.transaction_id == "3fa85f64-5717-4562-b3fc-2c963f66afa6"
        assert transaction.status == "pending"

    def test_create_transfer__success(self, mock_response):
        mock_response._content = b"""
        {
          "transaction_id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
          "transaction_data": {
            "transaction_type": "transfer",
            "recipient_id": "a9a85fd4-5717-4562-b3fc-2c963f65afa6",
            "amount": 50000
          },
          "status": "pending",
          "metadata": {
            "payments_id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
            "source_type": "TreatmentProcedure",
            "source_id": "1243564576876"
          }
        }
        """
        with patch("common.base_http_client.requests.request") as mock_request:
            mock_request.return_value = mock_response

            client = payments_gateway.get_client()
            transaction_data = client.create_transfer_payload(
                amount=50000,
                recipient_id=uuid.UUID("a9a85fd4-5717-4562-b3fc-2c963f65afa6"),
                metadata={
                    "source_type": "TreatmentProcedure",
                    "source_id": "1243564576876",
                },
                description="description",
            )
            transaction = client.create_transaction(transaction_data)

        assert transaction.transaction_id == "3fa85f64-5717-4562-b3fc-2c963f66afa6"
        assert transaction.status == "pending"

    def test_create_refund__success(self, mock_response):
        mock_response._content = b"""
        {
          "transaction_id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
          "transaction_data": {
            "transaction_type": "refund",
            "transaction_id": "a9a85fd4-5717-4562-b3fc-2c963f65afa6",
            "amount": 50000
          },
          "status": "pending",
          "metadata": {
            "payments_id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
            "source_type": "TreatmentProcedure",
            "source_id": "1243564576876"
          }
        }
        """
        with patch("common.base_http_client.requests.request") as mock_request:
            mock_request.return_value = mock_response

            client = payments_gateway.get_client()
            transaction_data = client.create_refund_payload(
                amount=50000,
                transaction_id=uuid.UUID("a9a85fd4-5717-4562-b3fc-2c963f65afa6"),
                metadata={
                    "source_type": "TreatmentProcedure",
                    "source_id": "1243564576876",
                },
            )
            transaction = client.create_transaction(transaction_data)

        assert transaction.transaction_id == "3fa85f64-5717-4562-b3fc-2c963f66afa6"
        assert transaction.status == "pending"

    def test_create_reverse_transfer__success(self, mock_response):
        mock_response._content = b"""
        {
            "transaction_id": "83a46aff-a036-4358-bf49-b4c6f5e91819",
            "transaction_data": {
                "fee": 0,
                "amount": 2000000,
                "description": null,
                "transaction_id": "16c857c6-2054-410c-8470-10ab6234b51e",
                "transaction_type": "transfer_reverse"
            },
            "status": "pending",
            "metadata": {
                "source_id": "1243564576876",
                "source_type": "TreatmentProcedure"
            }
        }
        """
        with patch("common.base_http_client.requests.request") as mock_request:
            mock_request.return_value = mock_response

            client = payments_gateway.get_client()
            transaction_data = client.create_transfer_reverse_payload(
                amount=2000000,
                transaction_id=uuid.UUID("16c857c6-2054-410c-8470-10ab6234b51e"),
                metadata={
                    "source_type": "TreatmentProcedure",
                    "source_id": "1243564576876",
                },
            )
            transaction = client.create_transaction(transaction_data)

        assert transaction.transaction_id == "83a46aff-a036-4358-bf49-b4c6f5e91819"
        assert transaction.status == "pending"

    def test_create_transaction__invalid_data(self, mock_response):
        mock_response._content = b"""{"test": "foo"}"""

        with patch(
            "common.base_http_client.requests.request"
        ) as mock_request, pytest.raises(
            payments_gateway.PaymentsGatewayException
        ) as e:
            mock_request.return_value = mock_response

            client = payments_gateway.get_client()
            transaction_data = client.create_charge_payload(
                amount=50000,
                customer_id=uuid.UUID("a9a85fd4-5717-4562-b3fc-2c963f65afa6"),
                metadata={
                    "source_type": "TreatmentProcedure",
                    "source_id": "1243564576876",
                },
                payment_method_id="",
            )
            client.create_transaction(transaction_data)
        assert e.value.code == 500

    def test_create_transaction__request_exception(self, charge_transaction_payload):
        with patch(
            "common.base_http_client.requests.request"
        ) as mock_request, pytest.raises(
            payments_gateway.PaymentsGatewayException
        ) as e:
            mock_request.side_effect = Exception("problem")
            client = payments_gateway.get_client()
            client.create_transaction(charge_transaction_payload)
        assert e.value.code == 400

    def test_make_request__gateway_returns_error(
        self, gateway_429_error_response, charge_transaction_payload
    ):
        with patch(
            "common.base_http_client.requests.request"
        ) as mock_request, pytest.raises(
            payments_gateway.PaymentsGatewayException
        ) as e:
            mock_request.return_value = gateway_429_error_response
            client = payments_gateway.get_client()
            client.create_transaction(charge_transaction_payload)

        assert e.value.code == 429
        assert (
            e.value.message
            == '{"status": 429, "title": "Rate Limit Payment Processor Error", "type": '
            '"rate_limit_payment_processor_error", "detail": "Please make your requests '
            'serially or at a lower rate.", "instance": "stripe:lock_timeout"}'
        )
        assert e.value.response == gateway_429_error_response
