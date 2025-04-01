class PharmacyException(Exception):
    ...


class ActionablePharmacyException(PharmacyException):
    def __init__(self, message: str):
        self.message = message

    def __repr__(self) -> str:
        return f"Need Ops Action: {self.message}"

    __str__ = __repr__


class NoReimbursementMethodError(ActionablePharmacyException):
    def __init__(self, message: str):
        super().__init__(message)


class AutoProcessedDirectPaymentException(PharmacyException):
    def __init__(self, message: str):
        super().__init__(message)
