from types import MappingProxyType

from appointments.client.v2.http.appointment_video_timestamp import (
    AppointmentVideoTimestampResource,
)
from appointments.client.v2.http.authorize_payment import (
    AppointmentReservePaymentResource,
)
from appointments.client.v2.http.cancel_appointment import CancelAppointmentResource
from appointments.client.v2.http.cancel_payment import (
    AppointmentProcessPaymentForCancel,
)
from appointments.client.v2.http.complete_payment import (
    AppointmentCompletePaymentResource,
)
from appointments.client.v2.http.member_appointment import MemberAppointmentByIdResource
from appointments.client.v2.http.member_appointments import (
    MemberAppointmentsListResource,
)
from appointments.notes.resources.notes import AppointmentNotesResource
from appointments.resources.appointment import AppointmentResource
from appointments.resources.appointments import AppointmentsResource
from appointments.resources.availability_requests import (
    AvailabilityNotificationRequestResource,
    AvailabilityRequestResource,
)
from appointments.resources.booking import (
    BookingFlowCategoriesResource,
    BookingFlowSearchResource,
)
from appointments.resources.bookings_reply import BookingsReplyResource
from appointments.resources.cancellation_policy import CancellationPoliciesResource
from appointments.resources.heartbeat_connection import HeartbeatConnectionResource
from appointments.resources.needs import NeedsResource
from appointments.resources.overflow_report import OverflowReportResource
from appointments.resources.practitioners_availabilities import (
    PractitionerDatesAvailableResource,
    PractitionersAvailabilitiesResource,
)
from appointments.resources.product_availability import ProductAvailabilityResource
from appointments.resources.provider_profile import BookingFlowProviderProfileResource
from appointments.resources.provider_search import (
    MessageableProviderSearchResource,
    ProviderSearchResource,
)
from appointments.resources.providers_languages import ProvidersLanguagesResource
from appointments.resources.report_problem import ReportProblemResource
from appointments.resources.reschedule_appointment import RescheduleAppointmentResource
from appointments.resources.schedule_event import ScheduleEventResource
from appointments.resources.schedule_events import ScheduleEventsResource
from appointments.resources.schedule_recurring_block import (
    ScheduleRecurringBlockResource,
)
from appointments.resources.schedule_recurring_blocks import (
    ScheduleRecurringBlocksResource,
)
from appointments.resources.verticals_specialties import VerticalsSpecialtiesResource
from appointments.resources.video import (
    VideoSessionResource,
    VideoSessionResourceV2,
    VideoSessionTokenResource,
    VideoSessionTokenResourceV2,
)
from appointments.resources.video_connection import AppointmentConnectionResource
from appointments.resources.zoom_webhook import ZoomWebhookResource

_urls = MappingProxyType(
    {
        "/v1/practitioners/<int:practitioner_id>/schedules/events": ScheduleEventsResource,
        "/v1/practitioners/<int:practitioner_id>/schedules/events/<int:event_id>": ScheduleEventResource,
        "/v1/practitioners/<int:practitioner_id>/schedules/recurring_blocks": ScheduleRecurringBlocksResource,
        "/v1/practitioners/<int:practitioner_id>/schedules/recurring_blocks/<int:schedule_recurring_block_id>": ScheduleRecurringBlockResource,
        "/v1/appointments": AppointmentsResource,
        "/v1/appointments/<int:appointment_id>": AppointmentResource,
        "/v1/appointments/<int:appointment_id>/notes": AppointmentNotesResource,
        "/v1/appointments/<int:appointment_id>/reschedule": RescheduleAppointmentResource,
        "/v1/appointments/<int:appointment_api_id>/connection": AppointmentConnectionResource,
        "/v1/cancellation_policies": CancellationPoliciesResource,
        "/v1/overflow_report": OverflowReportResource,
        "/v1/availability_notification_request": AvailabilityNotificationRequestResource,
        "/v1/availability_request": AvailabilityRequestResource,
        "/v1/booking_flow/search": BookingFlowSearchResource,
        "/v1/booking_flow/categories": BookingFlowCategoriesResource,
        "/v1/needs": NeedsResource,
        "/v1/vendor/twilio/sms": BookingsReplyResource,
        "/v1/verticals-specialties": VerticalsSpecialtiesResource,
        "/v1/practitioners/availabilities": PractitionersAvailabilitiesResource,
        "/v1/practitioners/dates_available": PractitionerDatesAvailableResource,
        "/v1/products/<int:product_id>/availability": ProductAvailabilityResource,
        "/v1/providers/<int:provider_id>/profile": BookingFlowProviderProfileResource,
        "/v1/providers": ProviderSearchResource,
        "/v1/providers/languages": ProvidersLanguagesResource,
        "/v1/providers/messageable_providers": MessageableProviderSearchResource,
        "/v1/video/connection/<int:appointment_api_id>/heartbeat": HeartbeatConnectionResource,
        "/v1/video/report_problem": ReportProblemResource,
        "/v1/video/session": VideoSessionResource,
        "/v1/video/session/<string:session_id>/token": VideoSessionTokenResource,
        "/v1/_/vendor/zoom/webhook": ZoomWebhookResource,
        # v2
        "/v2/video/session": VideoSessionResourceV2,
        "/v2/video/session/<string:session_id>/token": VideoSessionTokenResourceV2,
        # new member/appointments/ endpoints
        "/v2/member/appointments": MemberAppointmentsListResource,
        "/v2/member/appointments/<int:appointment_id>": MemberAppointmentByIdResource,
        "/v2/appointments/<int:appointment_id>/cancel": CancelAppointmentResource,
        "/v2/appointments/<int:appointment_id>/video_timestamp": AppointmentVideoTimestampResource,
        "/v2/appointments/reserve_payment_or_credits": AppointmentReservePaymentResource,
        "/v2/appointments/complete_payment": AppointmentCompletePaymentResource,
        "/v2/appointments/process_payments_for_cancel": AppointmentProcessPaymentForCancel,
    },
)


def add_routes(api):  # type: ignore[no-untyped-def] # Function is missing a type annotation
    for url_path, view in _urls.items():
        api.add_resource(view, url_path)
    return api


def _fetch_url_mappings():  # type: ignore[no-untyped-def] # Function is missing a return type annotation
    for url_path, view in _urls.items():
        yield url_path, view, {},


def get_routes():  # type: ignore[no-untyped-def] # Function is missing a return type annotation
    yield from _fetch_url_mappings()


# fmt: off
def get_blueprints():  # type: ignore[no-untyped-def] # Function is missing a return type annotation
    ...
# fmt: on
