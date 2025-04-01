from typing import Tuple

from .base import AdminCategory, AdminViewT, AuthenticatedMenuLink
from .models.messaging import MessageView
from .models.questionnaires import RecordedAnswerSetView
from .models.schedules import (
    AppointmentMetaDataView,
    AppointmentView,
    AvailabilityNotificationView,
    PractitionerAckView,
)
from .models.users import AsyncEncounterSummaryView


def get_views() -> Tuple[AdminViewT, ...]:
    return (
        AppointmentView.factory(category=AdminCategory.BOOKINGS.value),  # type: ignore[arg-type] # Argument "category" to "factory" of "MavenAdminView" has incompatible type "str"; expected "Optional[AdminCategory]"
        AppointmentMetaDataView.factory(
            category=AdminCategory.BOOKINGS.value, name="Appointment Notes"  # type: ignore[arg-type] # Argument "category" to "factory" of "MavenAdminView" has incompatible type "str"; expected "Optional[AdminCategory]"
        ),
        AsyncEncounterSummaryView.factory(
            category=AdminCategory.BOOKINGS.value,  # type: ignore[arg-type] # Argument "category" to "factory" of "MavenAdminView" has incompatible type "str"; expected "Optional[AdminCategory]"
            name="Non-Appointment Encounters",
        ),
        RecordedAnswerSetView.factory(
            category=AdminCategory.BOOKINGS.value, name="Structured Notes"  # type: ignore[arg-type] # Argument "category" to "factory" of "MavenAdminView" has incompatible type "str"; expected "Optional[AdminCategory]"
        ),
        AvailabilityNotificationView.factory(category=AdminCategory.BOOKINGS.value),  # type: ignore[arg-type] # Argument "category" to "factory" of "MavenAdminView" has incompatible type "str"; expected "Optional[AdminCategory]"
        MessageView.factory(category=AdminCategory.BOOKINGS.value),  # type: ignore[arg-type] # Argument "category" to "factory" of "MavenAdminView" has incompatible type "str"; expected "Optional[AdminCategory]"
        PractitionerAckView.factory(category=AdminCategory.BOOKINGS.value),  # type: ignore[arg-type] # Argument "category" to "factory" of "MavenAdminView" has incompatible type "str"; expected "Optional[AdminCategory]"
    )


def get_links() -> Tuple[AuthenticatedMenuLink, ...]:
    return ()
