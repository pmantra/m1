from __future__ import annotations

from typing import Iterable


class InvalidBillStatusChange(ValueError):
    pass


class MissingPaymentGatewayInformation(ValueError):
    pass


class MissingLinkedChargeInformation(ValueError):
    pass


class InvalidInputBillStatus(ValueError):
    pass


class InvalidRefundBillCreationError(ValueError):
    pass


class InvalidRefundBillPayerType(ValueError):
    pass


class PaymentsGatewaySetupError(ValueError):
    pass


class BillingServicePGMessageProcessingError(ValueError):
    def __init__(self, errors: Iterable[str]):
        self._errors = " ".join(errors)

    @property
    def message(self) -> str:
        return self._errors


class InvalidEphemeralBillOperationError(ValueError):
    pass


class InvalidBillTreatmentProcedureCancelledError(ValueError):
    pass
