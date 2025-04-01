from __future__ import annotations


class AppointmentNotFoundException(Exception):
    def __init__(self, appointment_id: int | None):
        if appointment_id:
            self.appointment_id = appointment_id
            self.message = f"Appointment with id {appointment_id} not found"
        else:
            self.message = "Appointment not found"


class AppointmentJSONError(Exception):
    message = "Invalid appointment json field"


class ProviderNotFoundException(Exception):
    message = "Associated provider not found for appointment"


class MemberNotFoundException(Exception):
    message = "Associated member not found for appointment"


class AppointmentAlreadyCancelledException(Exception):
    message = "The appointment is already cancelled."


class AppointmentCancelledByUserIdNotFoundException(Exception):
    message = "Can't find appointment's cancelled_by_user_id"


class AppointmentNotInCancellableStateException(Exception):
    message = "Appointment must be in a cancellable state"


class ErrorFetchingCancellationPolicy(Exception):
    def __init__(self, product_id: int, appointment_id: int):
        self.message = f"Error fetching cancellation policy for appointment {appointment_id} with product id {product_id}, got None."


class ProductNotFoundException(Exception):
    def __init__(self, product_id: int):
        self.message = f"Error fetching product with product id {product_id}, got None."


class QueryError(Exception):
    message = "Error loading sql query."


class QueryNotFoundError(Exception):
    ...


class MissingQueryError(Exception):
    ...


class SearchApiError(Exception):
    ...


class SearchApiRequestsError(SearchApiError):
    ...
