from typing import Iterable


class NotificationBaseError(ValueError):
    def __init__(self, errors: Iterable[str]):
        self._errors = " ".join(errors)

    @property
    def message(self) -> str:
        return self._errors


class NotificationPayloadCreationError(NotificationBaseError):
    pass


class NotificationEventPayloadCreationError(NotificationBaseError):
    pass


class NotificationServiceError(NotificationBaseError):
    pass


class UserInferenceError(NotificationBaseError):
    pass


class PaymentGatewayMessageProcessingError(NotificationBaseError):
    pass
