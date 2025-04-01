from __future__ import annotations

import datetime
from typing import TYPE_CHECKING, Dict, List, Optional
from urllib.parse import quote

import configuration
from appointments.models import appointment as appointment_models
from authn.models.user import User
from bms.constants import BMSProductNames
from bms.models.bms import BMSOrder, BMSProduct, BMSShipment
from braze import client, format_dt
from direct_payment.clinic.resources.constants import FERTILITY_CLINIC_PORTAL_BASE_URL
from geography.repository import CountryRepository
from messaging.models.messaging import Message
from models.enterprise import Organization
from models.questionnaires import Question, RecordedAnswer
from models.tracks.track import TrackName
from models.zoom import Webinar
from storage.connection import db
from utils import braze, security
from utils.braze import ConnectedEvent, fertility_clinic_user
from utils.log import logger
from utils.rotatable_token import BRAZE_ATTACHMENT_TOKEN
from wallet.models.constants import MemberType, ReimbursementRequestState

if TYPE_CHECKING:
    from wallet.models.reimbursement_wallet import ReimbursementWallet

log = logger(__name__)


GCAL_DATE_FORMAT = "%Y%m%dT%H%M00Z"
NEW_FERTILITY_USER_PASSWORD_SET_EXP_IN_SECONDS = 60 * 60 * 168
# 8 hour expiration for MMB password reset is temporary for initial launch.
# TBD when we revert: BEX-1898
FERTILITY_USER_RESET_PASSWORD_EXP_IN_SECONDS = 60 * 60 * 8
RESOLUTION_SURVEY_OID = "first_touch_resolution"
SATISFACTION_SURVEY_OID = "satisfaction"


def member_new_message(user: User, message: Message) -> None:
    log.info(
        "Sending member braze notification about new message",
        user_id=user.id,
        message_id=message.id,
    )
    braze.send_event(
        user,
        "member_new_message",
        {
            "channel_id": message.channel_id,
            "practitioner_id": message.channel.practitioner.id,
            "practitioner_name": message.channel.practitioner.full_name,
            "practitioner_image": message.channel.practitioner.avatar_url,
            "practitioner_type": ", ".join(
                v.name
                for v in message.channel.practitioner.practitioner_profile.verticals
            ),
        },
    )


def member_new_wallet_message(user: User, message: Message) -> None:
    log.info(
        "Sending member braze notification about new wallet message",
        user_id=user.id,
        message_id=message.id,
    )
    braze.send_event(
        user,
        "member_new_wallet_message",
        {"channel_id": message.channel_id, "practitioner_name": "Maven Wallet"},
    )


@ConnectedEvent.password_reset()
def password_reset(user: User) -> Dict[str, client.RawBrazeString]:
    return _get_password_set_url(user)


@ConnectedEvent.new_user_registration(
    exp=NEW_FERTILITY_USER_PASSWORD_SET_EXP_IN_SECONDS
)
def new_user_password_set(user: User) -> Dict[str, client.RawBrazeString]:
    return _get_password_set_url(
        user, True, NEW_FERTILITY_USER_PASSWORD_SET_EXP_IN_SECONDS
    )


@ConnectedEvent.existing_fertility_user_password_reset(
    exp=FERTILITY_USER_RESET_PASSWORD_EXP_IN_SECONDS
)
def existing_fertility_user_password_reset(
    user: User,
) -> Dict[str, client.RawBrazeString]:
    return _get_password_set_url(
        user, False, FERTILITY_USER_RESET_PASSWORD_EXP_IN_SECONDS
    )


def _get_password_set_url(
    user: User,
    new_user: bool = False,
    exp: int = security.DEFAULT_EMAIL_SIGNING_TIMEOUT,
) -> Dict[str, client.RawBrazeString]:
    config = configuration.get_api_config()
    email = user.email
    token = security.new_password_reset_token(email, exp)
    route = "reset_password"
    if new_user:
        route = "activate-account"
    base_uri = config.common.base_url
    if fertility_clinic_user(user.id):
        base_uri = FERTILITY_CLINIC_PORTAL_BASE_URL  # type: ignore[assignment] # Incompatible types in assignment (expression has type "Optional[str]", variable has type "str")

    url = f"{base_uri}/{route}/{quote(email, safe='')}/{quote(token, safe='')}"
    return {"password_reset_url": client.RawBrazeString(url)}


def password_updated(user: User) -> None:
    braze.send_event(user, "password_updated")


def appointment_booked_member(appointment: appointment_models.Appointment) -> None:
    appointment_id = appointment.id
    practitioner = appointment.practitioner
    practitioner_profile = practitioner.practitioner_profile  # type: ignore[union-attr] # Item "None" of "Optional[User]" has no attribute "practitioner_profile"
    member = appointment.member
    member_id = member.id

    # Grab the organization this user is associated with - avoid circular import
    from tracks import service as tracks_svc

    track_svc = tracks_svc.TrackSelectionService()
    organization = track_svc.get_organization_for_user(user_id=member_id)

    log.info(
        "Sending member braze notification about appointment booked",
        user_id=member_id,
        appointment_id=appointment_id,
        organization_id=(organization and organization.id),
    )

    braze.send_event(
        appointment.member,
        "appointment_booked_member",
        {
            "appointment_id": appointment.api_id,
            "practitioner_id": practitioner.id,  # type: ignore[union-attr] # Item "None" of "Optional[User]" has no attribute "id"
            "practitioner_name": practitioner.full_name,  # type: ignore[union-attr] # Item "None" of "Optional[User]" has no attribute "full_name"
            "practitioner_image": practitioner.avatar_url,  # type: ignore[union-attr] # Item "None" of "Optional[User]" has no attribute "avatar_url"
            "practitioner_type": ", ".join(
                v.name for v in practitioner_profile.verticals
            ),
            "scheduled_start_time": format_dt(appointment.scheduled_start),
            "booked_at": format_dt(appointment.created_at),
            "has_pre_session_note": bool(appointment.client_notes),
            "health_binder_fields_completed": all(
                (
                    member.health_profile.height,
                    member.health_profile.weight,
                )
            ),
            "user_country": (member.country and member.country.name),
            "user_organization": (organization and organization.name),
            "appointment_purpose": appointment.purpose,
            "anonymous_appointment": appointment.is_anonymous,
            "prescription_available": appointment.rx_enabled
            and practitioner_profile.dosespot != {},
            "gcal_link": _gcal_link(appointment),
            "ical_link": _ical_link(appointment),
        },
    )


def appointment_booked_practitioner(
    appointment: appointment_models.Appointment,
) -> None:
    appointment_id = appointment.id
    member = appointment.member
    member_id = member.id
    member_country = member.country
    country_metadata = member_country and CountryRepository().get_metadata(
        country_code=member_country.alpha_2
    )

    # Grab the organization this user is associated with - avoid circular import
    from tracks import service as tracks_svc

    track_svc = tracks_svc.TrackSelectionService()
    organization = track_svc.get_organization_for_user(user_id=member_id)

    log.info(
        "Sending practitioner braze notification about appointment booked",
        user_id=member_id,
        appointment_id=appointment_id,
        organization_id=(organization and organization.id),
        practitioner_id=(appointment and appointment.practitioner_id),
    )

    braze.send_event(
        appointment.practitioner,  # type: ignore[arg-type] # Argument 1 to "send_event" has incompatible type "Optional[User]"; expected "User"
        "appointment_booked_practitioner",
        {
            "appointment_id": appointment.api_id,
            "anonymous_appointment": appointment.is_anonymous,
            "member_name": member.full_name,
            "has_pre_session_note": bool(appointment.client_notes),
            "scheduled_start_time": format_dt(appointment.scheduled_start),
            "booked_at": format_dt(appointment.created_at),
            "user_country": (member_country and member_country.name),
            "country_summary": (country_metadata and country_metadata.summary),
            "user_organization": (organization and organization.name),
            "appointment_purpose": appointment.purpose,
            "gcal_link": _gcal_link(appointment),
            "ical_link": _ical_link(appointment),
        },
    )


def appointment_rescheduled_practitioner(
    appointment: appointment_models.Appointment,
) -> None:
    country_metadata = appointment.member.country and CountryRepository().get_metadata(
        country_code=appointment.member.country.alpha_2
    )
    # Grab the organization this user is associated with - avoid circular import
    from tracks import service as tracks_svc

    track_svc = tracks_svc.TrackSelectionService()
    member_id = appointment.member.id
    organization = track_svc.get_organization_for_user(user_id=member_id)
    log.info(
        "Sending practitioner braze notification about appointment rescheduled",
        user_id=member_id,
        appointment_id=appointment.id,
        practitioner_id=(appointment and appointment.practitioner_id),
    )
    braze.send_event(
        appointment.practitioner,  # type: ignore[arg-type] # Argument 1 to "send_event" has incompatible type "Optional[User]"; expected "User"
        "appointment_rescheduled_practitioner",
        {
            "appointment_id": appointment.api_id,
            "anonymous_appointment": appointment.is_anonymous,
            "member_name": appointment.member.full_name,
            "has_pre_session_note": bool(appointment.client_notes),
            "scheduled_start_time": format_dt(appointment.scheduled_start),
            "booked_at": format_dt(appointment.created_at),
            "user_country": (
                appointment.member.country and appointment.member.country.name
            ),
            "country_summary": (country_metadata and country_metadata.summary),
            "user_organization": (organization and organization.name),
            "appointment_purpose": appointment.purpose,
            "prescription_available": appointment.rx_enabled,
            "gcal_link": _gcal_link(appointment),
            "ical_link": _ical_link(appointment),
        },
    )


def _ical_link(appointment: appointment_models.Appointment) -> str:
    config = configuration.get_api_config()
    return f"{config.common.base_url}/api/v1/braze_attachment?token={BRAZE_ATTACHMENT_TOKEN.encode(dict(appointment_id=appointment.id), exp=604800)}"


def _gcal_link(appointment: appointment_models.Appointment) -> str:
    return (
        "https://www.google.com/calendar/render?action=TEMPLATE&text=Maven Appointment&dates="
        f"{appointment.scheduled_start.strftime(GCAL_DATE_FORMAT)}/"
        f"{appointment.scheduled_end.strftime(GCAL_DATE_FORMAT)}"
        "&sf=true&output=xml"
    )


def zoom_webinar_followup(user: User, event_name: str, webinar: Webinar) -> None:
    braze.send_event(
        user,
        event_name,
        {
            "webinar_id": webinar.id,
            "webinar_start_time": format_dt(webinar.start_time),
            "webinar_timezone": webinar.timezone,
            "webinar_topic": webinar.topic,
        },
    )


def appointment_canceled_prac_to_member(
    appointment: appointment_models.Appointment, note: Optional[str]
) -> None:
    practitioner_id = appointment.practitioner.id if appointment.practitioner else None
    log.info(
        "Sending member appointment cancellation, appointment cancelled by practitioner",
        user_id=appointment.member.id,
        appointment_id=appointment.id,
        practitioner_id=practitioner_id,
    )
    braze.send_event(
        appointment.member,
        "appointment_canceled_prac_to_member",
        {
            "appointment_id": appointment.api_id,
            "practitioner_id": practitioner_id,  # type: ignore[union-attr] # Item "None" of "Optional[User]" has no attribute "id"
            "practitioner_name": appointment.practitioner.full_name,  # type: ignore[union-attr] # Item "None" of "Optional[User]" has no attribute "full_name"
            "practitioner_vertical_id": appointment.product.vertical_id,
            "practitioner_image": appointment.practitioner.avatar_url,  # type: ignore[union-attr] # Item "None" of "Optional[User]" has no attribute "avatar_url"
            "scheduled_start_time": format_dt(appointment.scheduled_start),
            "scheduled_end_time": format_dt(appointment.scheduled_end),
            "appointment_started": bool(
                appointment.member_started_at and appointment.practitioner_started_at
            ),
            "cancellation_note": note,
        },
    )


def appointment_reminder_member(
    appointment: appointment_models.Appointment, event_name: str
) -> None:
    # Grab the organization this user is associated with - avoid circular import
    from tracks import service as tracks_svc

    track_svc = tracks_svc.TrackSelectionService()
    user_id = appointment.member.id
    organization = track_svc.get_organization_for_user(user_id=user_id)
    log.info(
        "Sending member braze notification for appointment reminder",
        user_id=user_id,
        appointment_id=appointment.id,
    )
    braze.send_event(
        appointment.member,
        event_name,
        {
            "appointment_id": appointment.api_id,
            "practitioner_id": appointment.practitioner.id,  # type: ignore[union-attr] # Item "None" of "Optional[User]" has no attribute "id"
            "practitioner_name": appointment.practitioner.full_name,  # type: ignore[union-attr] # Item "None" of "Optional[User]" has no attribute "full_name"
            "practitioner_image": appointment.practitioner.avatar_url,  # type: ignore[union-attr] # Item "None" of "Optional[User]" has no attribute "avatar_url"
            "practitioner_type": ", ".join(
                v.name for v in appointment.practitioner.practitioner_profile.verticals  # type: ignore[union-attr] # Item "None" of "Optional[User]" has no attribute "practitioner_profile"
            ),
            "scheduled_start_time": format_dt(appointment.scheduled_start),
            "booked_at": format_dt(appointment.created_at),
            "has_pre_session_note": bool(appointment.client_notes),
            "health_binder_fields_completed": all(
                (
                    appointment.member.health_profile.height,
                    appointment.member.health_profile.weight,
                )
            ),
            "user_country": (
                appointment.member.country and appointment.member.country.name
            ),
            "user_organization": (organization and organization.name),
            "appointment_purpose": appointment.purpose,
            "anonymous_appointment": appointment.is_anonymous,
            "prescription_available": appointment.rx_enabled
            and appointment.practitioner.practitioner_profile.dosespot != {},  # type: ignore[union-attr] # Item "None" of "Optional[User]" has no attribute "practitioner_profile"
        },
    )


def appointment_canceled_member_to_member(
    appointment: appointment_models.Appointment,
) -> None:
    practitioner_id = appointment.practitioner.id if appointment.practitioner else None
    is_intro_app = appointment.is_intro
    log.info(
        "Sending member appointment cancellation, appointment cancelled by member",
        user_id=appointment.member.id,
        appointment_id=appointment.id,
        practitioner_id=practitioner_id,
        is_intro_appointment=is_intro_app,
    )
    more_than_3_hours = (
        datetime.datetime.utcnow() + datetime.timedelta(hours=3)
    ) < appointment.scheduled_start
    braze.send_event(
        appointment.member,
        "appointment_canceled_member_to_member",
        {
            "appointment_id": appointment.api_id,
            "is_intro_appointment": is_intro_app,
            "practitioner_id": practitioner_id,  # type: ignore[union-attr] # Item "None" of "Optional[User]" has no attribute "id"
            "practitioner_name": appointment.practitioner.full_name,  # type: ignore[union-attr] # Item "None" of "Optional[User]" has no attribute "full_name"
            "practitioner_vertical_id": appointment.product.vertical_id,
            "practitioner_image": appointment.practitioner.avatar_url,  # type: ignore[union-attr] # Item "None" of "Optional[User]" has no attribute "avatar_url"
            "practitioner_type": ", ".join(
                v.name for v in appointment.practitioner.practitioner_profile.verticals  # type: ignore[union-attr] # Item "None" of "Optional[User]" has no attribute "practitioner_profile"
            ),
            "more_than_3_hours": more_than_3_hours,
        },
    )


def appointment_canceled_member_to_practitioner(  # type: ignore[no-untyped-def] # Function is missing a type annotation for one or more arguments
    appointment: appointment_models.Appointment, payment_amount, note
) -> None:
    log.info(
        "Sending practitioner appointment cancellation, appointment cancelled by member",
        user_id=appointment.member.id,
        appointment_id=appointment.id,
        practitioner_id=(
            appointment.practitioner.id if appointment.practitioner else None
        ),
    )
    braze.send_event(
        appointment.practitioner,  # type: ignore[arg-type] # Argument 1 to "send_event" has incompatible type "Optional[User]"; expected "User"
        "appointment_canceled_member_to_practitioner",
        {
            "appointment_id": appointment.api_id,
            "member_name": appointment.member.full_name,
            "scheduled_start_time": format_dt(appointment.scheduled_start),
            "payment_amount": f"{payment_amount:.2f}",
            "cancellation_note": note,
        },
    )


def _get_appointment_question_recorded_answers(
    question_oids: List[str], user_id: int, appointment_id: int
) -> str:
    return (
        db.session.query(RecordedAnswer)
        .join(Question, RecordedAnswer.question_id == Question.id)
        .filter(
            Question.oid.in_(question_oids),
            RecordedAnswer.user_id == user_id,
            RecordedAnswer.appointment_id == appointment_id,
        )
        .all()
    )


def appointment_complete(appointment: appointment_models.Appointment) -> None:
    if appointment.practitioner.is_care_coordinator:  # type: ignore[union-attr] # Item "None" of "Optional[User]" has no attribute "is_care_coordinator"
        counter_key = "ca_appointments_completed_count"
    else:
        counter_key = "non_ca_appointments_completed_count"

    need_id = None
    if appointment.need:
        need_id = appointment.need.id

    member_id = appointment.member.id
    appointment_id = appointment.id
    responses = _get_appointment_question_recorded_answers(
        [RESOLUTION_SURVEY_OID, SATISFACTION_SURVEY_OID],
        member_id,
        appointment_id,
    )

    rating_response = None
    resolution_response = None
    for response in responses:
        if response.question.oid == RESOLUTION_SURVEY_OID:  # type: ignore[attr-defined] # "str" has no attribute "question"
            resolution_response = response.answer.text  # type: ignore[attr-defined] # "str" has no attribute "answer"
        if response.question.oid == SATISFACTION_SURVEY_OID:  # type: ignore[attr-defined] # "str" has no attribute "question"
            rating_response = response.answer.text  # type: ignore[attr-defined] # "str" has no attribute "answer"
    log.info(
        "Sending member appointment complete notification",
        user_id=member_id,
        appointment_id=appointment_id,
    )
    braze.send_event(
        appointment.member,
        "appointment_complete",
        event_data={
            "appointment_id": appointment.api_id,
            "appointment_need_id": need_id,
            "appointment_purpose": appointment.purpose,
            "appointment_rating": rating_response,
            "appointment_resolution_response": resolution_response,
            "practitioner_id": appointment.practitioner.id,  # type: ignore[union-attr] # Item "None" of "Optional[User]" has no attribute "id"
            "practitioner_name": appointment.practitioner.full_name,  # type: ignore[union-attr] # Item "None" of "Optional[User]" has no attribute "full_name"
            "practitioner_vertical_id": appointment.product.vertical_id,
            "practitioner_image": appointment.practitioner.avatar_url,  # type: ignore[union-attr] # Item "None" of "Optional[User]" has no attribute "avatar_url"
            "scheduled_start_time": format_dt(appointment.scheduled_start),
            "practitioner_type": ", ".join(
                v.name for v in appointment.practitioner.practitioner_profile.verticals  # type: ignore[union-attr] # Item "None" of "Optional[User]" has no attribute "practitioner_profile"
            ),
        },
        user_attributes={counter_key: {"inc": 1}},
    )


def _no_show_event(
    appointment: appointment_models.Appointment, user: User, event_name: str
) -> None:
    log.info(
        "Sending no show event notification",
        user_id=user.id,
        appointment_id=appointment.id,
        event_name=event_name,
    )
    braze.send_event(
        user,
        event_name,
        {
            "appointment_id": appointment.api_id,
            "practitioner_id": appointment.practitioner.id,  # type: ignore[union-attr] # Item "None" of "Optional[User]" has no attribute "id"
            "practitioner_name": appointment.practitioner.full_name,  # type: ignore[union-attr] # Item "None" of "Optional[User]" has no attribute "full_name"
            "practitioner_vertical_id": appointment.product.vertical_id,
            "practitioner_image": appointment.practitioner.avatar_url,  # type: ignore[union-attr] # Item "None" of "Optional[User]" has no attribute "avatar_url"
            "practitioner_type": ", ".join(
                v.name for v in appointment.practitioner.practitioner_profile.verticals  # type: ignore[union-attr] # Item "None" of "Optional[User]" has no attribute "practitioner_profile"
            ),
        },
    )


def appointment_no_show_member_to_member(
    appointment: appointment_models.Appointment,
) -> None:
    _no_show_event(
        appointment, appointment.member, "appointment_no_show_member_to_member"
    )


def appointment_no_show_prac_to_member(
    appointment: appointment_models.Appointment,
) -> None:
    _no_show_event(
        appointment, appointment.member, "appointment_no_show_prac_to_member"
    )


def appointment_no_show_prac_to_prac(
    appointment: appointment_models.Appointment,
) -> None:
    _no_show_event(
        appointment, appointment.practitioner, "appointment_no_show_prac_to_prac"  # type: ignore[arg-type] # Argument 2 to "_no_show_event" has incompatible type "Optional[User]"; expected "User"
    )


def appointment_no_show_member_to_prac(
    appointment: appointment_models.Appointment,
) -> None:
    _no_show_event(
        appointment, appointment.practitioner, "appointment_no_show_member_to_prac"  # type: ignore[arg-type] # Argument 2 to "_no_show_event" has incompatible type "Optional[User]"; expected "User"
    )


def prescription_sent(  # type: ignore[no-untyped-def] # Function is missing a type annotation for one or more arguments
    appointment: appointment_models.Appointment,
    pharmacy_name,
    pharmacy_phone_number,
    time_sent,
) -> None:
    log.info(
        "Sending member braze notification for prescription sent",
        user_id=appointment.member.id,
        appointment_id=appointment.id,
    )
    braze.send_event(
        appointment.member,
        "prescription_sent",
        {
            "appointment_id": appointment.api_id,
            "practitioner_id": appointment.practitioner.id,  # type: ignore[union-attr] # Item "None" of "Optional[User]" has no attribute "id"
            "practitioner_name": appointment.practitioner.full_name,  # type: ignore[union-attr] # Item "None" of "Optional[User]" has no attribute "full_name"
            "practitioner_vertical_id": appointment.product.vertical_id,
            "pharmacy_name": pharmacy_name,
            "pharmacy_phone_number": pharmacy_phone_number,
            "time_sent": format_dt(time_sent),
        },
    )


def birth_plan_posted(appointment: appointment_models.Appointment) -> None:
    log.info(
        "Sending member braze notification for birth plan posted",
        user_id=appointment.member.id,
        appointment_id=appointment.id,
    )
    braze.send_event(
        appointment.member,
        "birth_plan_posted",
        {
            "time_posted": format_dt(datetime.datetime.utcnow()),
            "practitioner_id": appointment.practitioner.id,  # type: ignore[union-attr] # Item "None" of "Optional[User]" has no attribute "id"
            "practitioner_name": appointment.practitioner.full_name,  # type: ignore[union-attr] # Item "None" of "Optional[User]" has no attribute "full_name"
            "practitioner_vertical_id": appointment.product.vertical_id,
            "practitioner_type": ", ".join(
                v.name for v in appointment.practitioner.practitioner_profile.verticals  # type: ignore[union-attr] # Item "None" of "Optional[User]" has no attribute "practitioner_profile"
            ),
            "practitioner_image": appointment.practitioner.avatar_url,  # type: ignore[union-attr] # Item "None" of "Optional[User]" has no attribute "avatar_url"
        },
    )


def post_session_note_added(appointment: appointment_models.Appointment) -> None:
    log.info(
        "Sending member braze notification for post appointment note",
        user_id=appointment.member.id,
        appointment_id=appointment.id,
    )
    braze.send_event(
        appointment.member,
        "post_session_note_added",
        {
            "appointment_id": appointment.api_id,
            "practitioner_id": appointment.practitioner.id,  # type: ignore[union-attr] # Item "None" of "Optional[User]" has no attribute "id"
            "practitioner_name": appointment.practitioner.full_name,  # type: ignore[union-attr] # Item "None" of "Optional[User]" has no attribute "full_name"
            "practitioner_image": appointment.practitioner.avatar_url,  # type: ignore[union-attr] # Item "None" of "Optional[User]" has no attribute "avatar_url"
            "practitioner_type": ", ".join(
                v.name for v in appointment.practitioner.practitioner_profile.verticals  # type: ignore[union-attr] # Item "None" of "Optional[User]" has no attribute "practitioner_profile"
            ),
        },
    )


def appointment_overflow(appointment: appointment_models.Appointment) -> None:
    braze.send_event(
        appointment.practitioner,  # type: ignore[arg-type] # Argument 1 to "send_event" has incompatible type "Optional[User]"; expected "User"
        "appointment_overflow",
        {
            "appointment_id": appointment.api_id,
            "scheduled_start": format_dt(appointment.scheduled_start),
            "launch_time": format_dt(appointment.practitioner_started_at),
            "scheduled_end": format_dt(appointment.scheduled_end),
            "member_id": appointment.member.id,
            "member_name": appointment.member.full_name,
            "token": security.new_overflowing_appointment_token(appointment.id),
        },
    )


def appointment_canceled_member_third_time(
    appointment: appointment_models.Appointment,
) -> None:
    log.info(
        "Sending member braze notification for appointment canceled third time",
        user_id=appointment.member.id,
        appointment_id=appointment.id,
    )
    braze.send_event(
        appointment.member,
        "appointment_canceled_member_third_time",
        {
            "appointment_id": appointment.api_id,
            "practitioner_id": appointment.practitioner.id,  # type: ignore[union-attr] # Item "None" of "Optional[User]" has no attribute "id"
            "practitioner_name": appointment.practitioner.full_name,  # type: ignore[union-attr] # Item "None" of "Optional[User]" has no attribute "full_name"
            "practitioner_vertical_id": appointment.product.vertical_id,
            "practitioner_image": appointment.practitioner.avatar_url,  # type: ignore[union-attr] # Item "None" of "Optional[User]" has no attribute "avatar_url"
            "practitioner_type": ", ".join(
                v.name for v in appointment.practitioner.practitioner_profile.verticals  # type: ignore[union-attr] # Item "None" of "Optional[User]" has no attribute "practitioner_profile"
            ),
            "member_name": appointment.member.full_name,
            "scheduled_start_time": format_dt(appointment.scheduled_start),
        },
    )


def bms_order_received(user: User) -> None:
    braze.send_event(user, "bms_order_received")


def bms_travel_end_date(user: User, travel_end_date) -> None:  # type: ignore[no-untyped-def] # Function is missing a type annotation for one or more arguments
    braze.send_event(
        user, "bms_travel_end_date", {"travel_end_date": format_dt(travel_end_date)}
    )


def user_org_disassociation(user: User, organization: Organization) -> None:
    braze.send_event(
        user,
        "user_org_disassociation",
        {"organization_name": organization.marketing_name},
    )


def practitioner_availability_request(practitioner: User, request) -> None:  # type: ignore[no-untyped-def] # Function is missing a type annotation for one or more arguments
    log.info(
        "Sending practitioner availability request notification",
        user_id=practitioner.id,
        request_id=request.id,
    )
    braze.send_event(
        practitioner,
        "practitioner_availability_request",
        {"request_note": request.note, "request_id": request.id},
    )


def practitioner_set_availability(member: User, practitioner: User) -> None:
    braze.send_event(
        member,
        "practitioner_set_availability",
        {
            "practitioner_id": practitioner.id,
            "practitioner_name": practitioner.full_name,
            "practitioner_image": practitioner.avatar_url,
            "practitioner_type": ", ".join(
                v.name for v in practitioner.practitioner_profile.verticals
            ),
            "next_availability": format_dt(
                practitioner.practitioner_profile.next_availability
            ),
        },
    )


def notify_upcoming_availability(practitioner: User, starts_in_minutes) -> None:  # type: ignore[no-untyped-def] # Function is missing a type annotation for one or more arguments
    braze.send_event(
        practitioner,
        "notify_upcoming_availability",
        {"starts_in_minutes": starts_in_minutes},
    )


def user_added_pharmacy(practitioner: User, member_name: str) -> None:
    braze.send_event(practitioner, "user_added_pharmacy", {"member_name": member_name})


def practitioner_dosespot_link(practitioner: User, ds_link: str) -> None:
    braze.send_event(practitioner, "practitioner_dosespot_link", {"link_url": ds_link})


def practitioner_invoice_payment(practitioner: User, amount, payment_date) -> None:  # type: ignore[no-untyped-def] # Function is missing a type annotation for one or more arguments
    braze.send_event(
        practitioner,
        "practitioner_invoice_payment",
        {
            "practitioner_id": practitioner.id,
            "practitioner_name": practitioner.full_name,
            "payment_amount": f"{amount:.2f}",
            "payment_date": format_dt(payment_date),
        },
    )


def mfa_enabled(user: User) -> None:
    braze.send_event(
        user,
        "mfa_enabled",
        {
            "sms_phone_number_last_four": user.sms_phone_number
            and user.sms_phone_number[-4:]
        },
    )


def mfa_disabled(user: User) -> None:
    braze.send_event(user, "mfa_disabled")


def track_renewal(
    user: User,
    track: TrackName,
    start_date: datetime.date,
) -> None:
    braze.send_event(
        user,
        "track_renewal",
        {
            "track": TrackName(track).value,
            "start_date": format_dt(start_date),
        },
    )


def track_auto_renewal(
    user: User,
    track: TrackName,
    start_date: datetime.date,
) -> None:
    braze.send_event(
        user,
        "track_auto_renewal",
        {
            "track": TrackName(track).value,
            "start_date": format_dt(start_date),
        },
    )


def fertility_status(user: User, status: str) -> None:
    braze.send_event(
        user=user,
        event_name="fertility_treatment_status",
        user_attributes={"fertility_treatment_status": status},
    )


def prior_c_section_status(user: User, status: bool) -> None:
    braze.send_event(
        user=user,
        event_name="prior_c_section_status",
        user_attributes={"prior_c_section": status},
    )


def biological_sex(user: User, biological_sex: str) -> None:
    braze.send_event(
        user=user,
        event_name="biological_sex",
        user_attributes={"biological_sex": biological_sex},
    )


def send_bms_tracking_email(
    shipments: List[BMSShipment], product: BMSProduct, order: BMSOrder
) -> None:
    if product.name == BMSProductNames.BMS_PUMP_AND_CARRY.value:
        bms_carry_order_sent(order, shipments[0].tracking_numbers)
    elif product.name == BMSProductNames.BMS_PUMP_AND_CHECK.value:
        bms_check_order_sent(order, shipments[0].tracking_numbers)
    elif (
        product.name == BMSProductNames.BMS_PUMP_AND_POST.value and len(shipments) == 2
    ):
        # When a member requests Pump & Post the first shipment will always be to the hotel followed by the
        # second shipment to the members home.
        to_hotel_shipment = shipments[0]
        to_home_shipment = shipments[1]

        hotel_tracking_num = to_hotel_shipment.tracking_numbers
        home_tracking_nums = to_home_shipment.tracking_numbers

        bms_post_orders_sent(order, hotel_tracking_num, home_tracking_nums)


def bms_carry_order_sent(order, tracking_num) -> None:  # type: ignore[no-untyped-def] # Function is missing a type annotation for one or more arguments
    braze.send_event(
        order.user,
        "bms_carry_order_sent",
        {
            "tracking_num": tracking_num,
            "order_id": order.id,
        },
    )


def bms_check_order_sent(order, tracking_num) -> None:  # type: ignore[no-untyped-def] # Function is missing a type annotation for one or more arguments
    braze.send_event(
        order.user,
        "bms_check_order_sent",
        {
            "tracking_num": tracking_num,
            "order_id": order.id,
        },
    )


def bms_post_orders_sent(order, to_hotel_tracking_num, to_home_tracking_nums) -> None:  # type: ignore[no-untyped-def] # Function is missing a type annotation for one or more arguments
    braze.send_event(
        order.user,
        "bms_post_orders_sent",
        {
            "tracking_num": to_hotel_tracking_num,
            "return_home_tracking_nums": to_home_tracking_nums,
            "order_id": order.id,
        },
    )


def notify_post_author_of_reply(user: User, post_id: int) -> None:
    braze.send_event(user, "reply_to_post_author", {"post_id": post_id})


def notify_post_participant_of_reply(user: User, post_id: int) -> None:
    braze.send_event(user, "reply_to_post_participant", {"post_id": post_id})


def debit_card_lost_stolen(debit_card) -> None:  # type: ignore[no-untyped-def] # Function is missing a type annotation for one or more arguments
    user = debit_card.reimbursement_wallet.member
    braze.send_event(user, "debit_card_lost_stolen", {})


def debit_card_temp_inactive(debit_card) -> None:  # type: ignore[no-untyped-def] # Function is missing a type annotation for one or more arguments
    user = debit_card.reimbursement_wallet.member
    braze.send_event(user, "debit_card_temp_inactive", {})


def debit_card_mailed(user: User) -> None:
    braze.send_event(user, "debit_card_mailed", {})


def debit_card_transaction_denied(reimbursement_request) -> None:  # type: ignore[no-untyped-def] # Function is missing a type annotation for one or more arguments
    user = reimbursement_request.wallet.member
    braze.send_event(
        user,
        "debit_card_transaction_denied",
        {},
    )


def debit_card_transaction_needs_receipt(  # type: ignore[no-untyped-def] # Function is missing a type annotation for one or more arguments
    reimbursement_request, amount, date: datetime.date
) -> None:
    user = reimbursement_request.wallet.member
    braze.send_event(
        user,
        "debit_card_transaction_needs_receipt",
        {
            "transaction_date": date.strftime("%m/%d/%Y"),
            "transaction_amount": f"{amount:.2f}",
        },
    )


def debit_card_transaction_approved(  # type: ignore[no-untyped-def] # Function is missing a type annotation for one or more arguments
    reimbursement_request, amount, date: datetime.date
) -> None:
    user = reimbursement_request.wallet.member
    braze.send_event(
        user,
        "debit_card_transaction_approved",
        {
            "transaction_date": date.strftime("%m/%d/%Y"),
            "transaction_amount": f"{amount:.2f}",
        },
    )


def debit_card_transaction_insufficient_docs(  # type: ignore[no-untyped-def] # Function is missing a type annotation for one or more arguments
    reimbursement_request, amount, date: datetime.date
) -> None:
    user = reimbursement_request.wallet.member
    braze.send_event(
        user,
        "debit_card_transaction_insufficient_docs",
        {
            "transaction_date": date.strftime("%m/%d/%Y"),
            "transaction_amount": f"{amount:.2f}",
        },
    )


def wallet_state_qualified(wallet) -> None:  # type: ignore[no-untyped-def] # Function is missing a type annotation for one or more arguments
    for wallet_user in wallet.all_active_users:
        braze.send_event(
            user=wallet_user,
            event_name="wallet_state_qualified",
        )


def mmb_wallet_qualified(wallet, event_data) -> None:  # type: ignore[no-untyped-def] # Function is missing a type annotation for one or more arguments
    for wallet_user in wallet.all_active_users:
        braze.send_event(
            user=wallet_user, event_name="mmb_wallet_qualified", event_data=event_data
        )


def mmb_wallet_qualified_not_shareable(wallet, event_data: dict) -> None:  # type: ignore[no-untyped-def] # Function is missing a type annotation for one or more arguments
    for wallet_user in wallet.all_active_users:
        if wallet_user.member_benefit:
            benefit_id = wallet_user.member_benefit.benefit_id
        else:
            log.error(
                "Could not send mmb_wallet_qualified_not_shareable event - no benefit_id found for user",
                user_id=wallet_user.id,
            )
            continue
        braze.send_event(
            user=wallet_user,
            event_name="mmb_wallet_qualified_not_shareable",
            event_data={
                "benefit_id": benefit_id,
                **event_data,
            },
        )


def mmb_wallet_qualified_and_shareable(wallet, event_data: dict) -> None:  # type: ignore[no-untyped-def] # Function is missing a type annotation for one or more arguments
    for wallet_user in wallet.all_active_users:
        if wallet_user.member_benefit:
            benefit_id = wallet_user.member_benefit.benefit_id
        else:
            log.error(
                "Could not send mmb_wallet_qualified_and_shareable event - no benefit_id found for user",
                user_id=wallet_user.id,
            )
            continue
        braze.send_event(
            user=wallet_user,
            event_name="mmb_wallet_qualified_and_shareable",
            event_data={"benefit_id": benefit_id, **event_data},
        )


def wallet_state_disqualified(wallet) -> None:  # type: ignore[no-untyped-def] # Function is missing a type annotation for one or more arguments
    for wallet_user in wallet.all_active_users:
        braze.send_event(
            user=wallet_user,
            event_name="wallet_state_disqualified",
        )


def wallet_reimbursement_state_declined(wallet):  # type: ignore[no-untyped-def] # Function is missing a type annotation
    for wallet_user in wallet.all_active_users:
        braze.send_event(
            user=wallet_user, event_name="wallet_reimbursement_state_declined"
        )


def wallet_reimbursement_state_declined_erisa(wallet):  # type: ignore[no-untyped-def] # Function is missing a type annotation
    for wallet_user in wallet.all_active_users:
        braze.send_event(
            user=wallet_user, event_name="wallet_reimbursement_state_declined_erisa"
        )


def wallet_reimbursement_state_appeal_declined_erisa(wallet):  # type: ignore[no-untyped-def] # Function is missing a type annotation
    for wallet_user in wallet.all_active_users:
        braze.send_event(
            user=wallet_user,
            event_name="wallet_reimbursement_state_appeal_declined_erisa",
        )


def wallet_reimbursement_state_approved(wallet):  # type: ignore[no-untyped-def] # Function is missing a type annotation
    for wallet_user in wallet.all_active_users:
        braze.send_event(
            user=wallet_user, event_name="wallet_reimbursement_state_approved"
        )


def wallet_reimbursement_state_appeal_approved_erisa(wallet):  # type: ignore[no-untyped-def] # Function is missing a type annotation
    for wallet_user in wallet.all_active_users:
        braze.send_event(
            user=wallet_user,
            event_name="wallet_reimbursement_state_appeal_approved_erisa",
        )


def wallet_reimbursement_state_reimbursed(wallet):  # type: ignore[no-untyped-def] # Function is missing a type annotation
    for wallet_user in wallet.all_active_users:
        braze.send_event(
            user=wallet_user, event_name="wallet_reimbursement_state_reimbursed"
        )


def alegeus_claim_submitted(wallet):  # type: ignore[no-untyped-def] # Function is missing a type annotation
    for wallet_user in wallet.all_active_users:
        braze.send_event(user=wallet_user, event_name="alegeus_claim_submitted")


def alegeus_claim_attachments_submitted(wallet):  # type: ignore[no-untyped-def] # Function is missing a type annotation
    for wallet_user in wallet.all_active_users:
        braze.send_event(
            user=wallet_user,
            event_name="alegeus_claim_attachments_submitted",
        )


def alegeus_card_transaction_attachments_submitted(wallet):  # type: ignore[no-untyped-def] # Function is missing a type annotation
    for wallet_user in wallet.all_active_users:
        braze.send_event(
            user=wallet_user,
            event_name="alegeus_card_transaction_attachments_submitted",
        )


def reimbursement_request_created_new(
    wallet: ReimbursementWallet, member_type: MemberType
) -> None:
    for wallet_user in wallet.all_active_users:
        braze.send_event(
            user=wallet_user,
            event_name="reimbursement_request_created_new",
            event_data={
                "member_type": member_type.value,
                "prev_state": None,
                "new_state": ReimbursementRequestState.NEW.value,
            },
        )


def reimbursement_request_updated_new_to_pending(
    wallet: ReimbursementWallet, member_type: MemberType
) -> None:
    for wallet_user in wallet.all_active_users:
        braze.send_event(
            user=wallet_user,
            event_name="reimbursement_request_updated_new_to_pending",
            event_data={
                "member_type": member_type.value,
                "prev_state": ReimbursementRequestState.NEW.value,
                "new_state": ReimbursementRequestState.PENDING.value,
            },
        )
