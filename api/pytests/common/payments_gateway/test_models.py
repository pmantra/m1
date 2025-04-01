import pytest

from common.payments_gateway import (
    ChargePayload,
    Customer,
    CustomerSetupStatus,
    PaymentGatewayEventMessage,
    RefundPayload,
    Transaction,
    TransactionFee,
    TransactionPayload,
    TransferPayload,
)
from direct_payment.billing.errors import BillingServicePGMessageProcessingError


def test_customer__create_from_dict():
    c = Customer.create_from_dict(
        {
            "customer_id": 12345,
            "customer_setup_status": "succeeded",
            "payment_method_types": ["card"],
            "payment_methods": [
                {"payment_method_type": "card", "last4": "0000", "brand": "visa"}
            ],
        }
    )

    assert c.customer_id == 12345
    assert c.customer_setup_status == CustomerSetupStatus.SUCCEEDED
    assert len(c.payment_method_types) == 1
    assert c.payment_method_types[0] == "card"
    assert len(c.payment_methods) == 1
    payment_method = c.payment_methods[0]
    assert payment_method.last4 == "0000"
    assert payment_method.payment_method_type == "card"
    assert payment_method.brand == "visa"


@pytest.mark.parametrize(
    "payload",
    [
        ChargePayload(
            transaction_type="charge",
            customer_id="test",
            amount=1000,
            payment_method_id="",
        ),
        TransferPayload(
            transaction_type="transfer",
            recipient_id="test",
            amount=1000,
            description="test_description",
        ),
        RefundPayload(
            transaction_type="charge_refund",
            transaction_id="test",
            amount=1000,
        ),
    ],
)
def test_transaction_payload_to_request_data(payload):
    example_charge = TransactionPayload(
        transaction_data=payload,
        metadata={"source_id": "1", "source_type": "Type"},
    )
    request_data = example_charge.as_dict()
    assert isinstance(request_data["transaction_data"], dict)
    assert (
        request_data["transaction_data"]["transaction_type"] == payload.transaction_type
    )
    assert request_data["metadata"]["source_id"] == "1"


def test_transaction__create_from_dict():
    transaction = Transaction.create_from_dict(
        {
            "transaction_id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
            "transaction_data": {
                "transaction_type": "charge",
                "customer_id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
                "amount": 5000,
            },
            "status": "completed",
            "metadata": {
                "payments_id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
                "source_type": "treatment_plan",
                "source_id": "1243564576876",
            },
        }
    )

    assert str(transaction.transaction_id) == "3fa85f64-5717-4562-b3fc-2c963f66afa6"
    assert transaction.status == "completed"


def test_transaction_fee__create_from_dict():
    fee = TransactionFee.create_from_dict(
        {
            "transaction_data": {
                "description": None,
                "transaction_type": "charge",
                "amount": 500,
                "fee": 15,
                "customer_id": "07dd8ea5-f168-47fb-8d4d-b7dff194fa45",
            }
        }
    )

    assert fee.transaction_data["fee"] == 15


@pytest.mark.parametrize(
    argnames="inp, exp",
    argvalues=[
        (
            None,
            {"input_dict cannot be None"},
        ),
        (
            {},
            {
                "The event_type key is missing from the message.",
                "The message_payload key is missing from the message.",
            },
        ),
        (
            {
                "event_type": "a_bad_value",
                "message_payload": [],
                "error_payload": [],
            },
            {
                "Received unsupported event_type a_bad_value from payment gateway.",
                "The message_payload does not implement Mapping.",
                "The error_payload does not implement Mapping.",
            },
        ),
        (
            {"event_type": "billing_event", "message_payload": {}},
            {
                "The message_payload is empty.",
            },
        ),
        (
            {"event_type": "billing_event", "message_payload": None},
            {
                "The message_payload is None.",
            },
        ),
        (
            {
                "event_type": "billing_event",
                "message_payload": {"a": "B"},
                "bad_key": "bad_value",
            },
            {"TypeError", "__init__() got an unexpected keyword argument 'bad_key'"},
        ),
        (
            {
                "event_type": "billing_event",
                "message_payload": {"a": "B"},
                "error_payload": None,
            },
            {
                "The error_payload is None.",
            },
        ),
    ],
)
def test_payment_gateway_message_create_from_dict_errors(inp, exp):
    with pytest.raises(BillingServicePGMessageProcessingError) as ex_info:
        PaymentGatewayEventMessage.create_from_dict(inp)
    assert set(ex_info.value.args[0]) == exp


@pytest.mark.parametrize(
    argnames="inp",
    argvalues=[
        {
            "event_type": "billing_event",
            "message_payload": {"a": "b"},
        },
        {
            "event_type": "billing_event",
            "message_payload": {"a": "b"},
            "error_payload": {"b": "c"},
        },
    ],
)
def test_payment_gateway_message_create_from_dict(inp):

    # with pytest.raises(BillingServicePGMessageProcessingError) as ex_info:
    res = PaymentGatewayEventMessage.create_from_dict(inp)
    assert res.event_type == inp["event_type"]
    assert res.message_payload == inp["message_payload"]
    assert res.error_payload == inp.get("error_payload", {})
