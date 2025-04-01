import uuid
from unittest.mock import Mock, patch

import pytest
from requests import Response

from common.payments_gateway import (
    ChargePayload,
    PaymentsGatewayException,
    Transaction,
    TransactionPayload,
)
from direct_payment.billing import models


@pytest.fixture(autouse=True)
def payment_gateway_client():
    with patch("direct_payment.billing.billing_service.get_client") as get_client:
        get_client.return_value = Mock(
            create_transaction=Mock(
                return_value=Transaction(
                    transaction_id=uuid.uuid4(),
                    transaction_data={"transaction": "data"},
                    status="pending",
                    metadata={"source_id": "1", "source_type": "Type"},
                )
            ),
            create_charge_payload=Mock(
                return_value=TransactionPayload(
                    transaction_data=ChargePayload(
                        transaction_type="charge",
                        customer_id=str(uuid.uuid4()),
                        amount=0,
                        payment_method_id="",
                    ),
                    metadata={"source_id": "1", "source_type": "Type"},
                )
            ),
        )
        yield get_client


class TestBillEntityPermissions:
    def test_bill_not_found(self, client, api_helpers, bill_user):
        res = client.put(
            f"/api/v1/direct_payment/billing/bill/{uuid.uuid4()}",
            headers=api_helpers.json_headers(user=bill_user),
            json={"status": models.BillStatus.PROCESSING.value},
        )
        assert res.status_code == 404

    def test_user_blocked_from_bill(
        self, client, api_helpers, default_user, failed_bill
    ):
        res = client.put(
            f"/api/v1/direct_payment/billing/bill/{failed_bill.uuid}",
            headers=api_helpers.json_headers(user=default_user),
            json={"status": models.BillStatus.PROCESSING.value},
        )
        assert res.status_code == 403

    def test_user_has_access_to_bill(self, client, api_helpers, bill_user, failed_bill):
        res = client.put(
            f"/api/v1/direct_payment/billing/bill/{failed_bill.uuid}",
            headers=api_helpers.json_headers(user=bill_user),
            json={"status": models.BillStatus.PROCESSING.value},
        )
        assert res.status_code == 200

    def test_ops_has_access_to_bill(self, client, api_helpers, ops_user, failed_bill):
        res = client.put(
            f"/api/v1/direct_payment/billing/bill/{failed_bill.uuid}",
            headers=api_helpers.json_headers(user=ops_user),
            json={"status": models.BillStatus.PROCESSING.value},
        )
        assert res.status_code == 200


class TestBillManualRetry:
    def test_invalid_status_request(self, client, api_helpers, bill_user, failed_bill):
        res = client.put(
            f"/api/v1/direct_payment/billing/bill/{failed_bill.uuid}",
            headers=api_helpers.json_headers(user=bill_user),
            # Send the wrong status request
            json={"status": models.BillStatus.NEW.value},
        )
        assert res.status_code == 422

    def test_invalid_bill_status(self, client, api_helpers, bill_user, new_bill):
        # bill cannot change from NEW to PROCESSING via retry (in this MR, anyway)
        res = client.put(
            f"/api/v1/direct_payment/billing/bill/{new_bill.uuid}",
            headers=api_helpers.json_headers(user=bill_user),
            json={"status": models.BillStatus.PROCESSING.value},
        )
        assert res.status_code == 422

    def test_valid_bill_status_change(
        self, client, api_helpers, bill_user, failed_bill
    ):
        res = client.put(
            f"/api/v1/direct_payment/billing/bill/{failed_bill.uuid}",
            headers=api_helpers.json_headers(user=bill_user),
            json={"status": models.BillStatus.PROCESSING.value},
        )
        assert res.status_code == 200
        res_json = api_helpers.load_json(res)
        assert res_json["uuid"] == str(
            failed_bill.uuid
        ), f"Unexpected Bill id. Data: {res_json}"
        assert (
            res_json["status"] == models.BillStatus.PROCESSING.value
        ), f"Unexpected Bill status. Data: {res_json}"

    def test_no_payment_customer_id(
        self, client, api_helpers, bill_user, bill_wallet, failed_bill
    ):
        bill_wallet.payments_customer_id = None
        res = client.put(
            f"/api/v1/direct_payment/billing/bill/{failed_bill.uuid}",
            headers=api_helpers.json_headers(user=bill_user),
            json={"status": models.BillStatus.PROCESSING.value},
        )
        assert res.status_code == 400

    def test_gateway_exception(self, client, api_helpers, bill_user, failed_bill):
        with patch("direct_payment.billing.billing_service.get_client") as get_client:
            mock_response = Response()
            mock_response.status_code = 200
            mock_response.encoding = "application/json"
            mock_response._content = b"""
            {
              "status": 429,
              "title": "Rate Limit Payment Processor Error",
              "type": "rate_limit_payment_processor_error",
              "detail": "Please make your requests serially or at a lower rate.",
              "instance": "stripe:lock_timeout"
            }
            """
            raise_429 = PaymentsGatewayException(
                "Rate limit error.", code=429, response=mock_response
            )
            get_client.return_value = Mock(
                create_transaction=Mock(side_effect=raise_429),
                create_charge_payload=Mock(
                    return_value=TransactionPayload(
                        transaction_data=ChargePayload(
                            transaction_type="charge",
                            customer_id="fake-customer-id",
                            amount=0,
                            payment_method_id="",
                        ),
                        metadata={"source_id": "1", "source_type": "Type"},
                    )
                ),
            )

            # then
            res = client.put(
                f"/api/v1/direct_payment/billing/bill/{failed_bill.uuid}",
                headers=api_helpers.json_headers(user=bill_user),
                json={"status": models.BillStatus.PROCESSING.value},
            )
        assert res.status_code == 429
        res_json = api_helpers.load_json(res)
        assert res_json == {
            "errors": [
                {
                    "detail": "Rate limit error.",
                    "status": 429,
                    "title": "Too Many Requests",
                }
            ],
            "message": "Rate limit error.",
        }
