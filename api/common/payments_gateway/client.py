from __future__ import annotations

import uuid
from dataclasses import asdict
from typing import Mapping, Optional

from requests import Response

from common.base_triforce_client import BaseTriforceClient
from common.payments_gateway import models
from utils.log import logger

log = logger(__name__)

# Headers
CONTENT_TYPE = "application/json"

SERVICE_NAME = "payments-gateway"


class PaymentsGatewayClient(BaseTriforceClient):
    def __init__(
        self,
        *,
        base_url: str,
        headers: Optional[dict[str, str]] = None,
        internal: bool = False,
    ) -> None:
        super().__init__(
            base_url=base_url,
            headers=headers,
            service_name=SERVICE_NAME,
            internal=internal,
            log=log,
        )

    # Customers
    def create_customer(
        self,
        address: models.Address | None = None,
        email: str | None = None,
        name: str | None = None,
        phone: str | None = None,
        metadata: dict | None = None,
        headers: Mapping[str, str] | None = None,
    ) -> models.Customer:
        data = {}
        if address:
            data["address"] = asdict(address)
        if email:
            data["email"] = email  # type: ignore[assignment] # Incompatible types in assignment (expression has type "str", target has type "Dict[str, Any]")
        if name:
            data["name"] = name  # type: ignore[assignment] # Incompatible types in assignment (expression has type "str", target has type "Dict[str, Any]")
        if phone:
            data["phone"] = phone  # type: ignore[assignment] # Incompatible types in assignment (expression has type "str", target has type "Dict[str, Any]")
        if metadata:
            data["metadata"] = metadata

        response = self.make_service_request(
            "customer", data=data, method="POST", extra_headers=headers  # type: ignore[arg-type] # Argument "extra_headers" to "make_request" of "HttpTransport" has incompatible type "Optional[Mapping[str, str]]"; expected "Optional[Dict[Any, Any]]"
        )

        if response.status_code == 200:
            try:
                return models.Customer.create_from_dict(response.json())
            except Exception as e:
                log.exception("Failed to create Customer object", error=e)
                raise PaymentsGatewayException("Client error", 500, response=response)

        log.error("Failed to create customer", response=response)
        raise PaymentsGatewayException(
            response.text, response.status_code, response=response
        )

    def get_customer(
        self, customer_id: str, headers: Mapping[str, str] = None  # type: ignore[assignment] # Incompatible default for argument "headers" (default has type "None", argument has type "Mapping[str, str]")
    ) -> models.Customer:
        response = self.make_service_request(
            f"customer/{customer_id}", method="GET", extra_headers=headers  # type: ignore[arg-type] # Argument "extra_headers" to "make_request" of "HttpTransport" has incompatible type "Optional[Mapping[str, str]]"; expected "Optional[Dict[Any, Any]]"
        )
        if response.status_code == 200:
            try:
                return models.Customer.create_from_dict(response.json())
            except Exception as e:
                log.exception("Failed to create Customer object", error=e)
                raise PaymentsGatewayException("Client error", 500, response=response)
        log.error(
            "Failed to retrieve customer", requested_id=customer_id, response=response
        )
        raise PaymentsGatewayException(
            response.text, response.status_code, response=response
        )

    # Recipients
    def add_bank_account(
        self,
        customer_id: str,
        name: str,
        account_type: str,
        account_holder_type: str,
        account_number: str,
        routing_number: str,
        headers: Mapping[str, str] = None,  # type: ignore[assignment] # Incompatible default for argument "headers" (default has type "None", argument has type "Mapping[str, str]")
    ) -> None:
        data = {
            "payment_method": {
                "payment_method_type": "us_bank_account",
                "account_type": account_type,
                "account_holder_type": account_holder_type,
                "account_number": account_number,
                "routing_number": routing_number,
            },
            "name": name,
        }

        url = f"customer/{customer_id}/payment_method"
        response = self.make_service_request(
            url, data=data, method="POST", extra_headers=headers  # type: ignore[arg-type] # Argument "extra_headers" to "make_request" of "HttpTransport" has incompatible type "Optional[Mapping[str, str]]"; expected "Optional[Dict[Any, Any]]"
        )

        if response.status_code != 200:
            log.error("Failed to add bank account", response=response)
            raise PaymentsGatewayException(
                response.text or "", response.status_code, response=response
            )

    # Reconciliation
    def get_reconciliation_by_recipient(  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        self, recipient_id: str, start_time: int, end_time: int
    ):
        payload = {"start_time": start_time, "end_time": end_time}
        url = f"recipient/{recipient_id}/reconciliation"
        response = self.make_service_request(url, params=payload, method="GET")

        if response.status_code != 200:
            log.error(
                f"Failed to get reconciliation for recipient: {recipient_id}",
                response=response,
            )
            raise PaymentsGatewayException(
                response.text or "", response.status_code, response=response
            )
        return response

    # Transactions
    @staticmethod
    def create_charge_payload(
        amount: int, customer_id: uuid.UUID, metadata: dict, payment_method_id: str
    ) -> models.TransactionPayload:
        transaction_data = models.ChargePayload(
            transaction_type="charge",
            customer_id=str(customer_id),
            amount=amount,
            payment_method_id=payment_method_id,
        )
        data = models.TransactionPayload(
            transaction_data=transaction_data, metadata=metadata
        )
        return data

    @staticmethod
    def create_transfer_payload(
        amount: int, recipient_id: uuid.UUID, metadata: dict, description: str
    ) -> models.TransactionPayload:
        transaction_data = models.TransferPayload(
            transaction_type="transfer",
            recipient_id=str(recipient_id),
            amount=amount,
            description=description,
        )
        data = models.TransactionPayload(
            transaction_data=transaction_data, metadata=metadata
        )
        return data

    @staticmethod
    def create_refund_payload(
        amount: int, transaction_id: uuid.UUID, metadata: dict
    ) -> models.TransactionPayload:
        transaction_data = models.RefundPayload(
            transaction_type="charge_refund",
            transaction_id=str(transaction_id),
            amount=amount,
        )
        data = models.TransactionPayload(
            transaction_data=transaction_data, metadata=metadata
        )
        return data

    @staticmethod
    def create_transfer_reverse_payload(
        amount: int, transaction_id: uuid.UUID, metadata: dict
    ) -> models.TransactionPayload:
        transaction_data = models.TransferReversePayload(
            transaction_type="transfer_reverse",
            transaction_id=str(transaction_id),
            amount=amount,
        )
        data = models.TransactionPayload(
            transaction_data=transaction_data, metadata=metadata
        )
        return data

    def create_transaction(
        self,
        transaction_payload: models.TransactionPayload,
        headers: Mapping[str, str] = None,  # type: ignore[assignment] # Incompatible default for argument "headers" (default has type "None", argument has type "Mapping[str, str]")
    ) -> models.Transaction:
        response = self.make_service_request(
            "transaction",
            data=transaction_payload.as_dict(),
            method="POST",
            extra_headers=headers,  # type: ignore[arg-type] # Argument "extra_headers" to "make_request" of "HttpTransport" has incompatible type "Optional[Mapping[str, str]]"; expected "Optional[Dict[Any, Any]]"
        )

        if response.status_code == 200:
            try:
                return models.Transaction.create_from_dict(response.json())
            except Exception as e:
                log.exception("Failed to create Transaction object", error=e)
                raise PaymentsGatewayException(
                    message="Client error", code=500, response=response
                )

        raise PaymentsGatewayException(
            message=response.text, code=response.status_code, response=response
        )


class PaymentsGatewayException(Exception):
    __slots__ = ("code", "response", "message")

    def __init__(self, message: str, code: int, response: Response = None):  # type: ignore[assignment] # Incompatible default for argument "response" (default has type "None", argument has type "Response")
        super().__init__(message)
        self.message = message
        self.code = code
        self.response = response
