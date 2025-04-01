import datetime

from appointments.models.availability_notification_request import (
    AvailabilityNotificationRequest,
)
from appointments.utils.availability_requests import (
    get_member_availability_from_message,
)
from common import stats
from messaging.models.messaging import Channel, Message
from messaging.services.zendesk import send_general_ticket_to_zendesk
from storage.connection import db
from tasks.queues import job
from utils.log import logger

log = logger(__name__)


@job
def find_stale_request_availability_messages() -> None:
    """
    Finds availability requests that haven't been responded to in 48 hours
    """
    try:
        now = datetime.datetime.now()

        results = (
            db.session.query(Channel, AvailabilityNotificationRequest)
            .join(Channel.messages)
            .join(
                AvailabilityNotificationRequest,
                AvailabilityNotificationRequest.id
                == Message.availability_notification_request_id,
            )
            .filter(
                Message.created_at >= now - datetime.timedelta(days=2, hours=1),
                Message.created_at <= now - datetime.timedelta(days=2),
            )
            .all()
        )

        num_stale = 0
        for result in results:
            channel = result[0]
            messages = channel.messages
            avail_req = result[1]

            # Check the channel for a practitioner response
            passed_avail_req = False
            prac_responded = False
            member_availability_str = ""
            for message in messages:
                # Fast foward the channel until we get to the notification request
                if not passed_avail_req:
                    if message.availability_notification_request_id == avail_req.id:
                        passed_avail_req = True
                        member_availability_str = get_member_availability_from_message(
                            message.body
                        )
                    continue

                # Check the rest of the messages for a response from the practitioner
                if message.user_id == avail_req.practitioner_id:
                    prac_responded = True
                    break

            if not prac_responded:
                create_zendesk_ticket(
                    avail_req.id,
                    f"{avail_req.practitioner.first_name} {avail_req.practitioner.last_name}",
                    avail_req.member,
                    member_availability_str,
                )
                num_stale += 1

        stats.increment(
            metric_name="api.appointments.tasks.availability_requests.zendesk_tickets_created",
            pod_name=stats.PodNames.TEST_POD,
            metric_value=num_stale,
            tags=[],
        )
        log.info(f"Found {num_stale} stale availability requests!")
        log.info("Done finding stale availabilities requests!")

    except Exception as e:
        log.exception(
            "Failed to find stale request availability messages",
            exception=e,
        )


def create_zendesk_ticket(avail_req_id, prac_name, member, member_availability_str):  # type: ignore[no-untyped-def] # Function is missing a type annotation
    content = (
        "An availability request has not been responded to in 48 hours. Please respond to the member within 24 hours.\n"
        f"Reference ID: {avail_req_id}\n"
        f"Provider: {prac_name}\n"
        f"Member ID: {member.id}\n"
        f"Member availability: {member_availability_str}"
    )
    send_general_ticket_to_zendesk(
        user=member,
        ticket_subject="An availability request has not been responded to in 48 hours",
        content=content,
        tags=["request_availability"],
    )
    # Needed for send_general_ticket_to_zendesk to persist zendesk user
    db.session.commit()
