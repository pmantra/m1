from datetime import date, datetime, time, timedelta
from typing import List

import pytz
from flask import request
from flask_restful import abort
from maven import feature_flags
from sqlalchemy.orm import contains_eager
from sqlalchemy.orm.exc import NoResultFound

from appointments.models.availability_notification_request import (
    AvailabilityNotificationRequest,
)
from appointments.models.availability_request_member_times import (
    AvailabilityRequestMemberTimes,
)
from appointments.schemas.availability_request import (
    AvailabilityNotificationRequestPOSTSchema,
)
from authn.models.user import User
from common.services.api import AuthenticatedResource
from messaging.models.messaging import Channel, Message
from messaging.services.zendesk import send_general_ticket_to_zendesk
from models.profiles import PractitionerProfile
from providers.service.provider import ProviderService
from storage.connection import db
from tasks.notifications import notify_new_message
from utils import braze_events
from utils.log import logger

log = logger(__name__)


class AvailabilityNotificationRequestResource(AuthenticatedResource):
    """
    As of Aug 2024 this is still in use on Android and Web. Any changes to AvailabilityRequestResource should also be made here.
    Soon to be deprecated availability request endpoint which additionally stores member requested times and creates a channel for communication between member and provider
    """

    def post(self):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        request_json = request.json if request.is_json else None
        args = AvailabilityNotificationRequestPOSTSchema().load(request_json).data

        practitioner = _get_practitioner(args)

        if feature_flags.bool_variation(
            "release-turn-off-request-availability-by-contract-type",
            default=False,
        ):
            _verify_contract_type(practitioner)

        _verify_request_limit(self.user, args)

        _verify_phone_number(self.user.member_profile)

        _verify_member_timezone(args)

        _verify_availability(args)

        availabilities = args["availabilities"]

        availabilities = _validate_member_times(availabilities)

        new_request = AvailabilityNotificationRequest(
            member_id=self.user.id,
            practitioner_id=args["practitioner_id"],
            member_timezone=args["member_timezone"],
        )

        db.session.add(new_request)
        db.session.commit()

        member_times = []
        for a in availabilities:
            member_times.append(
                AvailabilityRequestMemberTimes(
                    availability_notification_request_id=new_request.id,
                    start_time=time.fromisoformat(a["start_time"]),
                    end_time=time.fromisoformat(a["end_time"]),
                    start_date=date.fromisoformat(a["start_date"]),
                    end_date=date.fromisoformat(a["end_date"]),
                )
            )

        db.session.add_all(member_times)

        braze_events.practitioner_availability_request(practitioner, new_request)

        message, channel = _create_request_message(
            new_request,
            self.user,
            practitioner,
            member_times,
            True,
        )

        db.session.commit()

        log.info(f"Successfully created availability request: {new_request}")
        response = {"message_id": message.id, "channel_id": channel.id}
        return response, 201


class AvailabilityRequestResource(AuthenticatedResource):
    """
    Any changes to this resource should also be made to AvailabilityNotificationRequestResource, until AvailabilityNotificationRequestResource is completely deprecated.
    Availability request endpoint which additionally stores member requested times and creates a channel for communication between member and provider
    """

    def post(self):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        request_json = request.json if request.is_json else None
        args = AvailabilityNotificationRequestPOSTSchema().load(request_json).data

        practitioner = _get_practitioner(args)

        if feature_flags.bool_variation(
            "release-turn-off-request-availability-by-contract-type",
            default=False,
        ):
            _verify_contract_type(practitioner)

        _verify_request_limit(self.user, args)

        _verify_phone_number(self.user.member_profile)

        _verify_member_timezone(args)

        _verify_availability(args)

        availabilities = args["availabilities"]

        availabilities = _validate_member_times(availabilities)

        new_request = AvailabilityNotificationRequest(
            member_id=self.user.id,
            practitioner_id=args["practitioner_id"],
            member_timezone=args["member_timezone"],
        )

        db.session.add(new_request)
        db.session.commit()

        member_times = []
        for a in availabilities:
            member_times.append(
                AvailabilityRequestMemberTimes(
                    availability_notification_request_id=new_request.id,
                    start_time=time.fromisoformat(a["start_time"]),
                    end_time=time.fromisoformat(a["end_time"]),
                    start_date=date.fromisoformat(a["start_date"]),
                    end_date=date.fromisoformat(a["end_date"]),
                )
            )

        db.session.add_all(member_times)

        braze_events.practitioner_availability_request(practitioner, new_request)

        if practitioner.practitioner_profile.is_cx:
            message_body = _create_availability_request_message_body(
                new_request.id,
                practitioner.first_name,
                member_times,
                new_request.member_timezone,
            )
            send_general_ticket_to_zendesk(
                user=self.user,
                ticket_subject="An availability request has been made",
                content=message_body,
                tags=["request_availability"],
            )

            # Needed for send_general_ticket_to_zendesk to persist zendesk user
            db.session.commit()

            return {"message_id": None, "channel_id": None}, 201

        else:
            message, channel = _create_request_message(
                new_request,
                self.user,
                practitioner,
                member_times,
                True,
            )

            log.info(f"Successfully created availability request: {new_request}")
            db.session.commit()
            notify_new_message.delay(practitioner.id, message.id)

            response = {
                "message_id": message.id,
                "channel_id": channel.id,
            }
            return response, 201


def _create_request_message(  # type: ignore[no-untyped-def] # Function is missing a return type annotation
    availability_request: AvailabilityNotificationRequest,
    member: User,
    practitioner: User,
    member_times: List[AvailabilityRequestMemberTimes],
    commit_db: bool = False,
):
    availability_notification_request_id = availability_request.id

    channel = Channel.get_or_create_channel(member, [practitioner])

    message_body = _create_availability_request_message_body(
        availability_request.id,
        practitioner.first_name,  # type: ignore[arg-type] # Argument 2 to "_create_availability_request_message_body" has incompatible type "Optional[str]"; expected "str"
        member_times,
        availability_request.member_timezone,
    )

    message = Message(
        user=None,
        channel=channel,
        body=message_body,
        availability_notification_request_id=availability_notification_request_id,
    )

    db.session.add(message)
    if commit_db:
        db.session.commit()

    return message, channel


def _create_availability_request_message_body(
    availability_request_id: int,
    practitioner_name: str,
    member_times: List,
    member_tz: str,
) -> str:
    availability_times_string = ""

    for member_time in member_times:
        for _time in member_time.separate_by_day():
            # start_date and end_date should be the same
            start_datetime = datetime.combine(_time.start_date, _time.start_time)
            end_datetime = datetime.combine(_time.start_date, _time.end_time)
            tz = pytz.timezone(member_tz)
            tz_offset = tz.localize(start_datetime).utcoffset()
            tz_str = tz.localize(start_datetime, is_dst=None).tzname()
            start_date_str = start_datetime.strftime("%b %d")
            start_time_str = (start_datetime + tz_offset).strftime("%I:%M%p")
            end_time_str = (end_datetime + tz_offset).strftime("%I:%M%p")
            availability_times_string += (
                f"{start_date_str}, {start_time_str}-{end_time_str}, {tz_str}\n"
            )

    message_body = (
        f"Hi {practitioner_name},\n\n You have an appointment request!\n\n"
        "The member’s availability is as follows (in order of preference):\n\n"
        f"{availability_times_string}\n"
        "If any of these dates/times work for you, please open the corresponding availability. "
        "To coordinate a new time, you can reply directly to this message.\n\n"
        "Need help? Reach out to providersupport@mavenclinic.com\n\n"
        "Thank you!\n\n"
        f"Reference ID: {availability_request_id}"
    )

    return message_body


def _get_practitioner(args):  # type: ignore[no-untyped-def] # Function is missing a type annotation
    try:
        practitioner_id = args.get("practitioner_id")

        return (
            db.session.query(User)
            .filter(User.id == practitioner_id)
            .join(
                PractitionerProfile,
                PractitionerProfile.user_id == practitioner_id,
            )
            .options(contains_eager("practitioner_profile"))
            .one()
        )
    except NoResultFound:
        abort(400, message="Invalid Practitioner ID")


def _get_request_count(user, practitioner_id):  # type: ignore[no-untyped-def] # Function is missing a type annotation
    return (
        db.session.query(AvailabilityNotificationRequest)
        .filter(
            AvailabilityNotificationRequest.member_id == user.id,
            AvailabilityNotificationRequest.practitioner_id == practitioner_id,
            AvailabilityNotificationRequest.notified_at.is_(None),
            AvailabilityNotificationRequest.cancelled_at.is_(None),
            AvailabilityNotificationRequest.created_at
            >= datetime.utcnow() - timedelta(hours=24),
        )
        .count()
    )


def _verify_contract_type(practitioner: User) -> None:
    if not ProviderService().provider_contract_can_accept_availability_requests(
        practitioner.practitioner_profile
    ):
        abort(
            400, message="Provider contract type does not allow availability requests"
        )


def _verify_request_limit(user, args):  # type: ignore[no-untyped-def] # Function is missing a type annotation
    if _get_request_count(user, args["practitioner_id"]) >= 5:
        abort(400, message="Daily availability request limit reached")


def _verify_unique_request(user, args):  # type: ignore[no-untyped-def] # Function is missing a type annotation
    if _get_request_count(user, args["practitioner_id"]) >= 1:
        abort(409, message="Already requested!")


def _verify_phone_number(member_profile):  # type: ignore[no-untyped-def] # Function is missing a type annotation
    if not member_profile.phone_number:
        abort(400, message="Set a phone number to notify with")


def _verify_member_timezone(args):  # type: ignore[no-untyped-def] # Function is missing a type annotation
    if args["member_timezone"] not in pytz.all_timezones:
        abort(400, message="A valid member timezone is required")


def _verify_availability(args):  # type: ignore[no-untyped-def] # Function is missing a type annotation
    if len(args["availabilities"]) < 1:
        abort(400, message="Member must provide at least one available time")


def _validate_member_times(times):  # type: ignore[no-untyped-def] # Function is missing a type annotation
    for t in times:
        all_keys = t.keys()

        # set the end_date equal to the start_date if it was not provided
        if "end_date" not in all_keys or not t["end_date"]:
            t["end_date"] = t["start_date"]

        # validate there are no null values provided
        for k in all_keys:
            if not t[k]:
                abort(400, message="Available times are missing values")

        try:
            start_time = time.fromisoformat(t["start_time"])
            time.fromisoformat(t["end_time"])
            start_date = date.fromisoformat(t["start_date"])
            end_date = date.fromisoformat(t["end_date"])
        except ValueError as e:
            log.error(e)
            abort(400, message="dates and times must be in ISO")

        # validate the times available are within 7 days from now (plus 1 day extra padding for timezones)
        if end_date > (datetime.utcnow() + timedelta(days=8)).date():
            abort(
                400, message="Available times provided must be within the next 7 days"
            )

        # validate the times provided are in the future or one day in the past
        if (start_date < (datetime.utcnow() - timedelta(days=1)).date()) or (
            start_date == (datetime.utcnow() - timedelta(days=1)).date()
            and start_time < datetime.utcnow().time()
        ):
            abort(400, message="Available times provided cannot be in the past")

    return times
