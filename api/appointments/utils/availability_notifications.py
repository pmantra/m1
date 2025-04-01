from __future__ import annotations

from datetime import datetime

from appointments.services.schedule import update_practitioner_profile_next_availability
from appointments.tasks.availability_notifications import notify_about_availability
from models.profiles import PractitionerProfile
from utils.log import logger
from utils.service_owner_mapper import service_ns_team_mapper
from utils.slack import notify_bookings_channel

log = logger(__name__)


def update_next_availability_and_alert_about_availability(  # type: ignore[no-untyped-def] # Function is missing a return type annotation
    practitioner_profile: PractitionerProfile,
    user_full_name: str,
    starts_at: datetime,
    ends_at: datetime,
    until: datetime = None,  # type: ignore[assignment] # Incompatible default for argument "until" (default has type "None", argument has type "datetime")
    recurring: bool = False,
):
    """
    Shared post adding availability functionality for scheduling individual availability and recurring
    availability.

    Updates practitioner's next availability, alerts in slack of their profile is set to,
    and kicks off async job to notify member if they have an alert set for availability on
    that provider.
    """
    update_practitioner_profile_next_availability(practitioner_profile)

    if practitioner_profile.alert_about_availability:
        try:
            if recurring:
                message = f"<!channel>: {user_full_name} set recurring availability from {starts_at} to {ends_at} until {until}"
            else:
                message = f"<!channel>: {user_full_name} set availability from {starts_at} to {ends_at}"

            notify_bookings_channel(message)
        except ValueError as e:
            log.warning("Invalid input value", exception=e)
        except Exception as e:
            log.warning("Unknown exception type: %s", e)

    service_ns_tag = "provider_availability"
    team_ns_tag = service_ns_team_mapper.get(service_ns_tag)
    notify_about_availability.delay(
        practitioner_profile.user_id, service_ns=service_ns_tag, team_ns=team_ns_tag
    )
