from __future__ import annotations

import copy
import dataclasses
import uuid
from dataclasses import dataclass
from enum import Enum
from typing import Dict, Literal, Mapping

from direct_payment.billing.errors import BillingServicePGMessageProcessingError


@dataclass
class Address:
    __slots__ = ("city", "country", "line1", "line2", "post_code", "state")
    city: str
    country: str
    line1: str
    line2: str
    post_code: str
    state: str


class CustomerSetupStatus(str, Enum):
    SUCCEEDED = "succeeded"
    PROCESSING = "processing"
    REQUIRES_ACTION = "requires_action"
    REQUIRES_CONFIRMATION = "requires_confirmation"
    REQUIRES_PAYMENT_METHOD = "requires_payment_method"


@dataclass
class Customer:
    __slots__ = (
        "customer_id",
        "customer_setup_status",
        "payment_method_types",
        "payment_methods",
    )

    customer_id: str
    customer_setup_status: CustomerSetupStatus
    payment_method_types: list[str]
    payment_methods: list[PaymentMethod]

    @staticmethod
    def create_from_dict(input_dict: dict) -> Customer:
        return Customer(
            customer_id=input_dict["customer_id"],
            customer_setup_status=CustomerSetupStatus(
                input_dict["customer_setup_status"]
            ),
            payment_method_types=input_dict["payment_method_types"] or [],
            payment_methods=[
                PaymentMethod(
                    payment_method_type=method["payment_method_type"],
                    last4=method["last4"],
                    brand=method["brand"],
                    payment_method_id=method.get("payment_method_id", ""),
                    card_funding=method.get("card_funding", None),
                )
                for method in input_dict["payment_methods"]
            ]
            if "payment_methods" in input_dict
            else [],
        )


@dataclass
class PaymentMethod:
    __slots__ = (
        "payment_method_type",
        "last4",
        "brand",
        "payment_method_id",
        "card_funding",
    )

    payment_method_type: str
    last4: str
    brand: str
    payment_method_id: str
    card_funding: str | None


@dataclass(frozen=True)
class ChargePayload:
    __slots__ = ("transaction_type", "amount", "customer_id", "payment_method_id")

    transaction_type: Literal["charge"]
    amount: int
    customer_id: str
    payment_method_id: str


@dataclass(frozen=True)
class TransferPayload:
    __slots__ = ("transaction_type", "amount", "recipient_id", "description")

    transaction_type: Literal["transfer"]
    amount: int
    recipient_id: str
    description: str


@dataclass(frozen=True)
class TransferReversePayload:
    __slots__ = ("transaction_type", "amount", "transaction_id")

    transaction_type: Literal["transfer_reverse"]
    amount: int
    transaction_id: str


@dataclass(frozen=True)
class RefundPayload:
    __slots__ = ("transaction_type", "amount", "transaction_id")

    transaction_type: Literal["charge_refund"]
    amount: int
    transaction_id: str


@dataclass(frozen=True)
class TransactionPayload:
    __slots__ = ("transaction_data", "metadata")
    transaction_data: ChargePayload | TransferPayload | RefundPayload | TransferReversePayload
    metadata: dict

    def as_dict(self) -> dict:
        return dataclasses.asdict(self)


TransactionStatusT = Literal["completed", "failed", "pending", "processing"]
EventTypeT = Literal[
    "billing_event", "payment_method_attach_event", "payment_method_detach_event"
]


@dataclass(frozen=True)
class Transaction:
    __slots__ = ("transaction_id", "transaction_data", "status", "metadata")
    transaction_id: uuid.UUID
    transaction_data: dict
    status: TransactionStatusT
    metadata: dict

    @classmethod
    def create_from_dict(cls, input_dict: dict) -> Transaction:
        if "transaction_id" not in input_dict:
            raise KeyError("input_dict must contain transaction_id key.")
        new_dict = copy.deepcopy(input_dict)
        new_dict["transaction_id"] = uuid.UUID(input_dict["transaction_id"])
        return Transaction(**input_dict)

    def __post_init__(self) -> None:
        required_metadata_fields = [("source_id", str), ("source_type", str)]
        for field_name, field_type in required_metadata_fields:
            # Quick hack for validation error
            if field_name not in self.metadata or not isinstance(
                self.metadata[field_name], field_type
            ):
                raise TypeError(
                    "Metadata must include source_id and source_type strings."
                )


@dataclass(frozen=True)
class TransactionFee:
    __slots__ = ("transaction_data",)
    transaction_data: ChargePayload | TransferPayload | RefundPayload

    @staticmethod
    def create_from_dict(input_dict: dict) -> TransactionFee:
        return TransactionFee(**input_dict)

    def as_dict(self) -> dict:
        return dataclasses.asdict(self)


@dataclass(frozen=True)
class PaymentGatewayEventMessage:
    __slots__ = ("event_type", "message_payload", "error_payload")
    event_type: EventTypeT
    message_payload: Dict
    error_payload: Dict

    @classmethod
    def create_from_dict(cls, input_dict: dict) -> PaymentGatewayEventMessage:
        PaymentGatewayEventMessage._validate_input_dict(input_dict)
        try:
            if "error_payload" not in input_dict:
                input_dict = {**input_dict, **{"error_payload": {}}}
            return PaymentGatewayEventMessage(**input_dict)
        except TypeError as ex:
            raise (
                BillingServicePGMessageProcessingError(["TypeError"] + list(ex.args))
            )

    @staticmethod
    def _validate_input_dict(input_dict: dict) -> None:
        error_messages = []
        if input_dict is None:
            raise BillingServicePGMessageProcessingError(["input_dict cannot be None"])

        if "event_type" not in input_dict:
            error_messages.append("The event_type key is missing from the message.")
        else:
            event_type = input_dict["event_type"]
            if event_type not in [
                "billing_event",
                "payment_method_attach_event",
                "payment_method_detach_event",
            ]:
                error_messages.append(
                    f"Received unsupported event_type {event_type} from payment gateway."
                )
        # a populate message payload is mandatory
        if "message_payload" not in input_dict:
            error_messages.append(
                "The message_payload key is missing from the message."
            )
        else:
            if mp_validation := PaymentGatewayEventMessage._validate_payload(
                input_dict, "message_payload", False
            ):
                error_messages.append(mp_validation)

        # if an error payload is present it cannot be none or not a map.
        if "error_payload" in input_dict:
            if ep_validation := PaymentGatewayEventMessage._validate_payload(
                input_dict, "error_payload", True
            ):
                error_messages.append(ep_validation)

        if error_messages:
            raise BillingServicePGMessageProcessingError(error_messages)

    @staticmethod
    def _validate_payload(input_dict: dict, payload_key: str, allow_empty: bool) -> str:
        to_return = ""
        message_payload = input_dict[payload_key]
        if message_payload is None:
            to_return = f"The {payload_key} is None."
        elif not isinstance(message_payload, Mapping):
            to_return = f"The {payload_key} does not implement Mapping."
        elif not allow_empty and not message_payload:
            to_return = f"The {payload_key} is empty."
        return to_return
