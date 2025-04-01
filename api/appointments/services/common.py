from __future__ import annotations

import datetime
from typing import List

from flask_restful import abort
from sqlalchemy.orm.attributes import InstrumentedAttribute
from sqlalchemy.orm.exc import NoResultFound

from appointments.models.appointment import Appointment
from appointments.repository.appointment import AppointmentRepository
from authn.models.user import User
from authz.services.permission import only_member_or_practitioner
from common import stats
from models.products import Product
from models.tracks.client_track import TrackModifiers
from models.verticals_and_specialties import CX_VERTICAL_NAME, Vertical
from providers.service.provider import ProviderService
from storage.connection import db
from tracks.service import TrackSelectionService
from tracks.utils.common import get_active_member_track_modifiers
from utils.log import logger

log = logger(__name__)

OBFUSCATION_SECRET = 997948364


def get_platform(user_agent: str | None) -> str:
    if user_agent:
        if "Maven" in user_agent:
            return "iOS"
        elif "MPractice" in user_agent:
            return "iOS"
        elif "MAVEN_ANDROID" in user_agent:
            return "android"
        elif "Python" in user_agent:
            return "backend"
        else:
            return "web"
    else:
        return "NONE"


def obfuscate_appointment_id(appointment_id: int | InstrumentedAttribute) -> int:
    if isinstance(appointment_id, InstrumentedAttribute):
        # checking instance type here to maintain admin pytests, in a non-mocked scenario, the appointment id will always be of type int
        return appointment_id.op("^")(OBFUSCATION_SECRET)
    return appointment_id ^ OBFUSCATION_SECRET


def deobfuscate_appointment_id(obfuscated_id: int) -> int:
    clean = obfuscated_id ^ OBFUSCATION_SECRET
    return clean


def get_cleaned_appointment(
    appointment_id: int, user: User
) -> List[Appointment] | None:
    appointment_id = deobfuscate_appointment_id(appointment_id)
    appointment = AppointmentRepository(session=db.session).get_by_id(appointment_id)

    if not appointment:
        return None

    return only_member_or_practitioner(user, [appointment])


def round_to_nearest_minutes(
    date_time: datetime.datetime = datetime.datetime.utcnow(),  # noqa  B008  TODO:  Do not perform function calls in argument defaults.  The call is performed only once at function definition time. All calls to your function will reuse the result of that definition-time function call.  If this is intended, assign the function call to a module-level variable and use that variable as a default value.
    rounding_minutes: int = 10,
) -> datetime.datetime:
    # Round to to the nearest minute(s) like the client would
    date_time += datetime.timedelta(
        minutes=rounding_minutes - 1, seconds=59, microseconds=999999
    )
    return date_time.replace(
        minute=date_time.minute - (date_time.minute % rounding_minutes),
        second=0,
        microsecond=0,
    )


def check_intro_appointment_purpose(user, product):  # type: ignore[no-untyped-def] # Function is missing a type annotation
    """
    We will assign an 'introduction' purpose if the appt is the first time the
    member is meeting with a CA in their current track, as long as the current track is not
    a transition from a previous track.

    Transitions can be identified by looking at the previous_member_track_id field in the
    MemberTrack model. If the field is not empty, its a transition.
    """
    user_id = user.id
    product_id = product.id

    # Get the highest priority track - those are the ones for which intro appts are booked
    active_tracks = user.active_tracks
    if not active_tracks:
        log.warning(
            "User has no active tracks",
            user_id=user_id,
            product_id=product_id,
        )
        return
    track = TrackSelectionService().get_highest_priority_track(active_tracks)

    # If track has previous_member_track_id, it means that the member transitioned to this track, and hence, member is not booking an intro appt
    previous_member_track_id = track.previous_member_track_id  # type: ignore[union-attr] # Item "None" of "Optional[MemberTrack]" has no attribute "previous_member_track_id"
    if previous_member_track_id:
        log.info(
            "User's active track is a transition from another track, hence, appointment is not intro appointment",
            user_id=user_id,
            product_id=product_id,
            member_track_id=track.id,  # type: ignore[union-attr] # Item "None" of "Optional[MemberTrack]" has no attribute "id"
            previous_member_track_id=previous_member_track_id,
        )
        return

    # Consider if the member has had any CA appts since the track's activation date
    member_has_not_had_ca_appts_since_track_activation = (
        db.session.query(Appointment.id)
        .join(Product, Appointment.product_id == Product.id)
        .join(Vertical, Product.vertical_id == Vertical.id)
        .filter(
            Appointment.member_schedule_id == user.schedule.id,
            Appointment.scheduled_start >= track.activated_at,  # type: ignore[union-attr] # Item "None" of "Optional[MemberTrack]" has no attribute "activated_at"
            Appointment.cancelled_at.is_(None),
            Vertical.name == CX_VERTICAL_NAME,
        )
        .count()
        == 0
    )

    # Consider if the appointment is being booked with a CA
    practitioner_is_cx = product.practitioner.is_care_coordinator

    if (
        practitioner_is_cx
        and member_has_not_had_ca_appts_since_track_activation
        and TrackSelectionService().is_enterprise(user_id=user.id)
    ):
        if track and (track.name not in ("pregnancy", "postpartum", None)):
            _str = track.name.lower().replace("-", "_")
            purpose = f"introduction_{_str}"
        else:
            due_date = user.health_profile.due_date
            if (due_date is None) or (due_date < datetime.datetime.utcnow().date()):
                purpose = "introduction"  # could be introduction_postpartum
            else:
                purpose = "birth_needs_assessment"  # seems equivalent to introduction_pregnancy

        log.info(
            "Computed appointment purpose",
            user_id=user_id,
            product_id=product_id,
            purpose=purpose,
        )
        return purpose
    else:
        log.info(
            "Could not define appointment purpose",
            user_id=user_id,
            product_id=product_id,
            product_purpose=product.purpose,
        )
        return


def purpose_is_intro(purpose: str) -> bool:
    """
    This is also used by the Appointment model - Appointment.is_intro.
    Update Appointment.is_intro expression if you're updating this method.
    """

    if purpose and (
        "introduction_" in purpose
        or purpose
        in [
            "introduction",
            "birth_needs_assessment",
            "postpartum_needs_assessment",
        ]
    ):
        return True
    return False


def check_appointment_exists(appointment_id: int, user_id: int) -> None:
    """
    Using the incoming appointment id and user id, check if appointment exists - if not, abort with a 400 BAD REQUEST
    """

    try:
        appointment_id = deobfuscate_appointment_id(appointment_id)
        appointment = AppointmentRepository(session=db.session).get_by_id(
            appointment_id
        )
        if not appointment or user_id not in [
            appointment.member_id,
            appointment.practitioner_id,
        ]:
            raise NoResultFound
    except NoResultFound:
        log.error(
            "Appointment not found",
            appointment_id=appointment_id,
            user_id=user_id,
        )

        abort(400, message="Appointment not found")


def get_appointment_by_id(appointment_id: int) -> Appointment:
    return AppointmentRepository().get_by_id(appointment_id)


def can_member_book(user: User, product: Product) -> bool:
    active_tracks = user.active_tracks
    member_track_modifiers = get_active_member_track_modifiers(active_tracks)

    return ProviderService.provider_can_member_interact(
        provider=product.practitioner.practitioner_profile,
        modifiers=member_track_modifiers,
        client_track_ids=[track.client_track_id for track in active_tracks],
    )


def cancel_invalid_appointment_post_track_transition(
    user_id: int,
    member_track_modifiers: list[TrackModifiers],
    client_track_ids: list[int],
) -> None:

    if member_track_modifiers:
        pending_appointments = AppointmentRepository().get_by_member_id(
            member_id=user_id
        )

        if not pending_appointments:
            return None

        invalid_appointment_ids = []
        for appointment in pending_appointments:
            practitioner = appointment.product.practitioner
            # if an appointment is scheduled for a future date but the provider is not supported by the member's new track we should cancel the appointment
            if (
                appointment.scheduled_start >= datetime.datetime.utcnow()
                and not ProviderService.provider_can_member_interact(
                    provider=practitioner.practitioner_profile,
                    modifiers=member_track_modifiers,
                    client_track_ids=client_track_ids,
                )
            ):
                invalid_appointment_ids.append(appointment.id)

                # cancel the appointment from the provider side
                appointment.cancel(user_id=practitioner.id)

                stats.increment(
                    metric_name="api.appointments.services.common.cancel_invalid_appointment_post_track_transition",
                    pod_name=stats.PodNames.CARE_DISCOVERY,
                    tags=["reason:member_cannot_book_with_practitioner"],
                )

        if invalid_appointment_ids:
            log.info(
                "Cancelled existing appointments booked with unsupported providers",
                member_id=user_id,
                invalid_appointment_ids=invalid_appointment_ids,
            )
    return None
