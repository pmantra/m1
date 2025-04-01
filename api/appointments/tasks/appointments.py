from __future__ import annotations

import datetime

import ddtrace
from pymysql import DatabaseError
from redset.locks import LockTimeout
from sqlalchemy.exc import SQLAlchemyError
from stripe.error import StripeError

import configuration
from appointments.models.appointment import MAX_MEMBER_CANCELLATIONS, Appointment
from appointments.models.appointment_meta_data import AppointmentMetaData
from appointments.models.constants import APPOINTMENT_STATES
from appointments.models.practitioner_appointment import PractitionerAppointmentAck
from appointments.repository.appointment import AppointmentRepository
from care_plans.activities_completed.care_plan_activity_util import CarePlanActivityUtil
from care_plans.care_plans_service import CarePlansService
from common import stats
from dosespot.constants import (
    DOSESPOT_GLOBAL_CLINIC_ID_V2,
    DOSESPOT_GLOBAL_CLINIC_KEY_V2,
)
from dosespot.resources.dosespot_api import DoseSpotAPI
from incentives.services.incentive_organization import IncentiveOrganizationService

# DO NOT REMOVE BELOW 2 LINES. SQLALCHEMY NEEDS IT FOR MAPPER INSTANTIATION
from l10n.utils import message_with_enforced_locale
from messaging.models.messaging import Channel, Message, MessageBilling  # noqa: F401
from messaging.services.zendesk import PostSessionZendeskTicket
from models.actions import audit
from models.products import Product
from models.profiles import PractitionerProfile
from models.referrals import ReferralCode, ReferralCodeUse  # noqa: F401
from payments.services.appointment_payments import AppointmentPaymentsService
from providers.service.provider import ProviderService
from storage.connection import db
from tasks.helpers import get_appointment
from tasks.queues import job, retryable_job
from tracks import service as tracks_svc
from utils import braze, braze_events
from utils.braze import appointment_rescheduled_member
from utils.cache import RedisLock
from utils.log import logger

log = logger(__name__)

MEMBER_DISCONNECT_TIMES = "member_disconnect_times"
PRACTITIONER_DISCONNECT_TIMES = "practitioner_disconnect_times"


class Error(Exception):
    pass


@retryable_job("priority", retry_limit=3, traced_parameters=("appointment_id",))
def send_post_appointment_message(
    appointment_id: int, appointment_metadata_id: int
) -> Message | None:
    log.info(
        "Start add message in send_post_appointment_message",
        appointment_id=appointment_id,
        appointment_metadata_id=appointment_metadata_id,
    )

    appointment = Appointment.query.get(appointment_id)
    post_session = AppointmentMetaData.query.get(appointment_metadata_id)
    if post_session.draft:
        return  # type: ignore[return-value]

    config = configuration.get_api_config()
    channel = Channel.get_or_create_channel(
        appointment.practitioner, [appointment.member]
    )

    message_body = message_with_enforced_locale(
        user=appointment.member, text_key="member_post_appointment_note_message"
    ).format(
        member_first_name=appointment.member.first_name,
        post_session_content=post_session.content,
        base_url=config.common.base_url,
    )

    message = Message(user=appointment.practitioner, channel=channel, body=message_body)
    post_session.message = message
    db.session.add(post_session)
    db.session.commit()

    log.info(
        "Successfully add message in send_post_appointment_message",
        appointment_id=appointment_id,
        appointment_metadata_id=appointment_metadata_id,
        channel_id=channel.id,
    )

    braze_events.post_session_note_added(appointment)
    pszt = PostSessionZendeskTicket(
        appointment.practitioner,
        message,
        user_need_when_solving_ticket="customer-need-member-proactive-outreach-post-appointment-note",
    )
    pszt.update_zendesk()

    return message


@job("priority", traced_parameters=("appointment_id",))
def appointment_post_creation(appointment_id: int) -> Appointment | None:  # type: ignore[return]
    metric_name = "api.appointments.tasks.appointments.post_create_async_tasks"
    try:
        appointment: Appointment = get_appointment(appointment_id)
        if appointment:
            log.info(
                "Started post-creation tasks for appointment",
                appointment_id=appointment.id,
            )

            if (
                appointment.practitioner is None
                or appointment.practitioner.practitioner_profile is None
            ):
                raise AttributeError("Appointment missing practitioner")
            profile = appointment.practitioner.practitioner_profile
            if ProviderService().enabled_for_prescribing(appointment.practitioner_id):
                validate_appointment_pharmacy(appointment)

            # Add practitioner to member care team
            appointment.member.add_care_team_via_appointment(appointment)

            # the 555 number is a dummy to pass validation on the model so that
            # we can still make a ack record even when a practitioner has no
            # phone number. this will require manual ack in admin to avoid the
            # no-show notification
            ack = PractitionerAppointmentAck(
                appointment=appointment,
                phone_number=(profile.phone_number or "+12125555555"),
                ack_by=(appointment.scheduled_start - datetime.timedelta(minutes=10)),
                warn_by=(appointment.scheduled_start - datetime.timedelta(minutes=90)),
            )
            db.session.add(ack)
            db.session.commit()

            braze.update_appointment_attrs(appointment.member)
            stats.increment(
                metric_name=metric_name,
                pod_name=stats.PodNames.MPRACTICE_CORE,
                tags=["success:true"],
            )
            log.info(
                "Finished post-creation tasks for appointment",
                appointment_id=appointment.id,
            )
            return appointment
    except DatabaseError as e:
        stats.increment(
            metric_name=metric_name,
            pod_name=stats.PodNames.MPRACTICE_CORE,
            tags=["error:true", "error_cause:failed_post_creation"],
        )
        log.error(
            "Database error in appointment_post_creation for appointment",
            appointment_id=appointment_id,
            error=e,
        )
    except Exception as e:
        stats.increment(
            metric_name=metric_name,
            pod_name=stats.PodNames.MPRACTICE_CORE,
            tags=["error:true", "error_cause:failed_post_creation"],
        )
        log.exception(
            "Failed appointment_post_creation for appointment",
            appointment_id=appointment_id,
            exception=e,
        )


def validate_appointment_pharmacy(appointment: Appointment) -> None:
    mp = appointment.member.member_profile
    pharmacy_info = mp.get_prescription_info()

    if pharmacy_info.get("pharmacy_id"):
        if (
            appointment.practitioner is None
            or appointment.practitioner.practitioner_profile is None
        ):
            raise AttributeError("Appointment missing practitioner")
        profile = appointment.practitioner.practitioner_profile
        dosespot = DoseSpotAPI(
            clinic_id=DOSESPOT_GLOBAL_CLINIC_ID_V2,
            clinic_key=DOSESPOT_GLOBAL_CLINIC_KEY_V2,
            user_id=profile.dosespot["user_id"],
            maven_user_id=appointment.practitioner.id,
        )
        pharmacy = dosespot.validate_pharmacy(pharmacy_info["pharmacy_id"])
        if pharmacy.get("PharmacyId"):
            pass
        else:
            mp.set_prescription_info(pharmacy_id=None)
            db.session.add(mp)
            db.session.commit()


@job
def complete_overdue_appointments() -> None:
    """
    Completes overdue appointments.
    """
    appointments = (
        db.session.query(Appointment)
        .filter(
            Appointment.cancelled_at == None,
            Appointment.practitioner_started_at != None,
            Appointment.member_started_at != None,
            (Appointment.practitioner_ended_at == None)
            | (Appointment.member_ended_at == None),
            (
                Appointment.scheduled_end
                <= datetime.datetime.utcnow() - datetime.timedelta(hours=12)
            ),
        )
        .all()
    )

    log.info(f"Got {len(appointments)} overdue appointments to complete")
    for appointment in appointments:
        complete_overdue_appointment.delay(appointment.id, team_ns="virtual_care")


@job(traced_parameters=("appointment_id",))
def complete_overdue_appointment(appointment_id: int) -> None:
    """
    Completes an overdue appointment.
    """
    metric_name = "api.appointments.tasks.appointments.complete_overdue_appointment"

    log.info(
        "Attempting to process overdue appointment . . .",
        appointment_id=appointment_id,
    )

    appointment = get_appointment(appointment_id)
    if not appointment:
        log.warning(
            "Unable to process overdue appointment - invalid appointment id",
            appointment_id=appointment_id,
        )
        return

    # if member disconnected data exists and member_ended_at is None, set the member_ended_at
    if (
        disconnect_times := appointment.json.get(MEMBER_DISCONNECT_TIMES, None)
    ) and not appointment.member_ended_at:
        log.info(
            "Processing overdue appointment - setting disconnected at time as member ended at time",
            appointment_id=appointment_id,
        )
        appointment.member_ended_at = max(disconnect_times)
        db.session.add(appointment)
        db.session.commit()

    # if practitioner disconnected data exists and practitioner_ended_at is None, set the practitioner_ended_at
    if (
        disconnect_times := appointment.json.get(PRACTITIONER_DISCONNECT_TIMES, None)
    ) and not appointment.practitioner_ended_at:
        log.info(
            "Processing overdue appointment - setting disconnected at time as practitioner ended at time",
            appointment_id=appointment_id,
        )
        appointment.practitioner_ended_at = max(disconnect_times)
        db.session.add(appointment)
        db.session.commit()

    try:
        now = datetime.datetime.utcnow()
        if not appointment.member_ended_at:
            appointment.member_ended_at = now
        if not appointment.practitioner_ended_at:
            appointment.practitioner_ended_at = now

        appointment.json["system_completion"] = {
            "user": "member",
            "time": str(now),
        }
        db.session.add(appointment)
        db.session.commit()

        appointment_completion.delay(appointment.id)

        stats.increment(
            metric_name=metric_name,
            tags=["success:true"],
            pod_name=stats.PodNames.VIRTUAL_CARE,
        )
        log.info(
            "Completed overdue appointment",
            appointment_id=appointment_id,
        )
    except Exception as e:
        log.error(
            "Error completing overdue appointment",
            error=e.__class__.__name__,
            exception=e,
            appointment_id=appointment_id,
        )
        stats.increment(
            metric_name=metric_name,
            tags=["success:false"],
            pod_name=stats.PodNames.VIRTUAL_CARE,
        )


@ddtrace.tracer.wrap()
def reserve_credits_if_unreserved(
    appointment_id: int,
) -> None:
    appointment = get_appointment(appointment_id)
    track_svc = tracks_svc.TrackSelectionService()
    is_enterprise_member = track_svc.is_enterprise(user_id=appointment.member_id)
    if not is_enterprise_member:
        return
    log.info(
        "Checking credit reserves for enterprise member", appointment_id=appointment_id
    )
    appt_payments_svc = AppointmentPaymentsService(session=db.session)
    reserved_credits = appt_payments_svc.get_credits_reserved_for_appointment(
        appointment_id
    )
    if not reserved_credits:
        log.info(
            "No credits reserved for enterprise member appointment. Reserving fresh credits now",
            appointment_id=appointment_id,
        )
        appt_payments_svc.reserve_credits(
            appointment_id=appointment.id,
            product_id=appointment.product_id,
            member_id=appointment.member_id,
            scheduled_start=appointment.scheduled_start,
        )
        db.session.commit()


@job(team_ns="care_discovery", traced_parameters=("appointment_id",))
def appointment_completion(
    appointment_id: int,
    user_id: int | None = None,
) -> None:
    """
    Should be idempotent until we put a flag in place.

    The lock here is used so that the view for PUT of an appointment (where
    this task is originated from by a user action) cannot delay one of these if
    it is already in progress. the key for the lock is also used there to see
    if we can obtain it, and then delay if so...

    user_id: When this job is invoked as a scheduled cron job, the value will be None. When this job is invoked
    via the PUT /appointments/{id} endpoint, this value should be the member id or the practitioner id.
    """
    log.info("Attempting to complete appointment", appointment_id=appointment_id)

    try:
        with RedisLock(
            f"appointment_completion_{appointment_id}", timeout=0, expires=45
        ):
            _appointment_completion(
                appointment_id,
                user_id=user_id,
            )

    except LockTimeout as e:
        log.info(
            "Failed to acquire lock for appointment_completion job",
            appointment_id=appointment_id,
            error=e,
        )


def _appointment_completion(  # type: ignore[no-untyped-def] # Function is missing a return type annotation
    appointment_id: int,
    user_id: int | None = None,
) -> None:
    """
    Completes appointment activities such as payments, sending pubsub messages, updating practitioner rating.

    user_id: When this function is invoked as part of a scheduled cron job, the value will be None. When this
    function is invoked via the PUT /appointments/{id} endpoint, this value should be the member id or the practitioner id.
    """
    try:
        appointment = get_appointment(appointment_id)
        if (
            appointment.practitioner is None
            or appointment.practitioner.practitioner_profile is None
        ):
            raise AttributeError("Appointment missing practitioner")

        if not appointment:
            log.warning(
                "Unable to complete appointment - invalid appointment id",
                appointment_id=appointment_id,
            )
            return

        log.info("Going to complete appointment", appointment_id=appointment_id)
        audit("appointment_completion", appointment_id=appointment.id, user_id=user_id)  # type: ignore[arg-type] # Argument "user_id" to "audit" has incompatible type "Optional[int]"; expected "int"
        # send the care plan meet activity message
        # removed logic to try to avoid sending duplicate messages per discussion with care management
        # sending duplicate messages is an idempotent activity
        CarePlansService.send_appointment_completed(appointment, "mono_appt")

        # Resolve appointment payment
        if appointment.state == Appointment.states.payment_pending:
            # Collect any money owed for marketplace appointment
            from payments.services.appointment_payments import (
                AppointmentPaymentsService,
            )

            try:
                state, result = AppointmentPaymentsService(db.session).complete_payment(
                    appointment_id=appointment_id,
                    product_price=appointment.product.price,
                )
            except StripeError as ex:
                state, result = (False, ex.json_body.get("error", {}).get("message"))

            if appointment.payment and (state is False or result is None):
                stats.increment(
                    metric_name="api.appointments.tasks.appointments.appointment_completion.failed_capture",
                    pod_name=stats.PodNames.CARE_DISCOVERY,
                    tags=[
                        "error:true",
                        "error_cause:invalid_payment",
                    ],
                )
                user = appointment.member
                body = f"""
User: {user}
Stripe Customer Id: [{user.member_profile.stripe_customer_id}]
Charge Result: {result}
Practitioner: {appointment.practitioner}
Appointment: {appointment}
"""
                log.error(
                    "Failed to complete payment for appointment",
                    appointment_id=appointment_id,
                    error=body,
                )
            elif result:
                # We collected fees here, commit the PaymentAccountingEntry
                log.info(
                    "Collected fees successfully. Commit the PaymentAccountingEntry",
                    appointment_id=appointment_id,
                )
                db.session.commit()

            if not appointment.fees:
                profile = appointment.practitioner.practitioner_profile
                if not appointment.requires_fee:
                    prac_active_contract = profile.active_contract
                    if prac_active_contract:
                        is_staff_check = not profile.active_contract.emits_fees
                    else:
                        log.warning(
                            "Falling back to using is_staff",
                            appointment_id=appointment_id,
                            practitioner_id=profile.user_id,
                        )
                        is_staff_check = profile.is_staff

                    if is_staff_check:  # Rename after is_staff is deprecated
                        # TODO: does this needs to be deprecated? staff_cost?
                        log.info(
                            "Calculating staff cost for appointment",
                            appointment_id=appointment_id,
                        )
                        appointment.staff_cost = profile.loaded_cost(
                            minutes=appointment.product.minutes
                        )
                        db.session.add(appointment)
                else:
                    appointment.collect_practitioner_fees()
                    appointment.collect_malpractice_fee()
                db.session.commit()
            else:
                log.info(
                    "Appointment already has fees, not collecting!",
                    appointment_id=appointment.id,
                )

            send_appointment_receipt.delay(appointment_id, team_ns="virtual_care")
            update_practitioner_rating.delay(
                appointment.practitioner.id, team_ns="virtual_care"
            )
            log.info(
                "Finished completion task for appointment",
                appointment_id=appointment_id,
            )
            used_code = appointment.user_recent_code
            if used_code:
                code = (
                    db.session.query(ReferralCode)
                    .filter(ReferralCode.code == used_code)
                    .one_or_none()
                )
                if code is None:
                    log.warning(
                        "Referral code not found for appointment",
                        appointment_id=appointment_id,
                    )

        elif appointment.state == Appointment.states.payment_resolved:
            log.info(
                "Payment already resolved for appointment",
                appointment_id=appointment_id,
            )
        else:
            log.warning(
                "Cannot collect payment for an appointment that isn't pending",
                appointment_id=appointment_id,
            )

        # Update user in braze
        braze.update_appointment_attrs(appointment.member)

        # If appt is intro appt, attempt to mark appt incentive as earned
        if appointment.is_intro:
            log.info(
                "Appointment being completed is intro appt, will check if an incentive was earned",
                appointment_id=appointment_id,
            )
            IncentiveOrganizationService().attempt_to_set_intro_appt_incentive_as_earned(
                appointment
            )

    except SQLAlchemyError as e:
        stats.increment(
            metric_name="api.appointments.tasks.appointments.appointment_completion.sql_alchemy_error",
            pod_name=stats.PodNames.TEST_POD,
            tags=[
                "error:true",
                "error_cause:sql_alchemy_error",
            ],
        )
        log.warning(
            "Database error while completing appointment",
            error=e.__class__.__name__,
            exception=e,
            appointment_id=appointment_id,
        )
    except Exception as e:
        log.warning(
            "Error completing appointment",
            error=e.__class__.__name__,
            exception=e,
            appointment_id=appointment_id,
        )


@job(traced_parameters=("appointment_id",))
def send_appointment_receipt(appointment_id: int) -> None:
    appointment = get_appointment(appointment_id)
    if appointment:
        if not appointment.state == APPOINTMENT_STATES.payment_resolved:
            log.warning(
                "Not sending receipt for appointment - payment is not resolved",
                appointment_id=appointment_id,
            )
            return
        braze_events.appointment_complete(appointment)


@job(traced_parameters=("user_id",))
def update_practitioner_rating(user_id: int) -> None:
    """Calculate new average based on existing average.
    @see http://math.stackexchange.com/a/957376/
    """
    profile = PractitionerProfile.query.get(user_id)

    rated_appts = (
        db.session.query(Appointment)
        .join(Product)
        .filter(Appointment.json.contains("ratings"), Product.user_id == user_id)
        .all()
    )

    appt_ratings = [a.rating for a in rated_appts if a.rating]
    if not appt_ratings:
        log.info("No ratings to be updated for %s", profile)
        return

    new_avg = sum(appt_ratings) / len(appt_ratings)

    profile.rating = new_avg
    db.session.add(profile)
    db.session.commit()
    log.info("Rating for %s has been updated to %s", profile, new_avg)


# ---- CX automation -----


@job
def cancel_practitioner_no_shows() -> None:
    """
    Cancels appointments as practitioner no-shows.
    """
    appointments = (
        db.session.query(Appointment)
        .filter(
            Appointment.scheduled_start
            >= (datetime.datetime.utcnow() - datetime.timedelta(hours=3)),
            Appointment.scheduled_end
            <= (datetime.datetime.utcnow() - datetime.timedelta(minutes=30)),
            Appointment.practitioner_started_at == None,
            Appointment.member_started_at != None,
            Appointment.cancelled_at == None,
            Appointment.phone_call_at == None,
        )
        .all()
    )

    log.info(f"Got {len(appointments)} practitioner no-show appointments to cancel")
    for appointment in appointments:
        cancel_practitioner_no_show.delay(appointment.id, team_ns="virtual_care")


@job(traced_parameters=("appointment_id",))
def cancel_practitioner_no_show(appointment_id: int) -> None:
    """
    Cancels appointment as a practitioner no-show.
    """
    metric_name = "api.appointments.tasks.appointments.cancel_practitioner_no_show"

    log.info(
        "Attempting to process appointment as cancel practitioner no-show . . .",
        appointment_id=appointment_id,
    )

    appointment = get_appointment(appointment_id)
    if not appointment:
        log.warning(
            "Unable to process cancel practitioner no-show - invalid appointment id",
            appointment_id=appointment_id,
        )
        return

    # verify appointment should be cancelled as practitioner no-show
    if appointment.practitioner_started_at:
        log.info(
            "Unable to process cancel practitioner no-show - started at value exists",
            appointment_id=appointment_id,
        )
        return
    if appointment.cancelled_at:
        log.info(
            "Unable to process cancel practitioner no-show - appointment already cancelled",
            appointment_id=appointment_id,
        )
        return

    # if practitioner disconnected data exists and practitioner_started_at is None, set the practitioner_started_at
    # and return so we do not erroneously cancel the appointment
    if (
        disconnect_times := appointment.json.get(PRACTITIONER_DISCONNECT_TIMES, None)
    ) and not appointment.practitioner_started_at:
        log.info(
            "Processing cancel practitioner no-show - attempting to set disconnected at time as started at time",
            appointment_id=appointment_id,
        )
        appointment.practitioner_started_at = min(disconnect_times)
        db.session.add(appointment)
        db.session.commit()
        return

    try:
        log.info(
            "Going to cancel appointment as practitioner no-show",
            appointment_id=appointment_id,
        )

        if appointment.practitioner is None:
            raise AttributeError("Appointment missing practitioner")

        appointment.cancel(appointment.practitioner.id, admin_initiated=True)
        db.session.add(appointment)
        db.session.commit()

        if appointment.state == APPOINTMENT_STATES.cancelled:
            braze_events.appointment_no_show_prac_to_member(appointment)
            braze_events.appointment_no_show_prac_to_prac(appointment)
            braze.update_appointment_attrs(appointment.member)
            stats.increment(
                metric_name=metric_name,
                tags=["success:true"],
                pod_name=stats.PodNames.VIRTUAL_CARE,
            )
            log.info(
                "Processed cancel practitioner no-show appointment",
                appointment_id=appointment_id,
            )
        else:
            log.warning(
                "Cancel practitioner no-show appointment - appointment did not end up in cancelled state",
                appointment_id=appointment_id,
                appointment_state=appointment.state,
            )
            stats.increment(
                metric_name=metric_name,
                tags=["success:false"],
                pod_name=stats.PodNames.VIRTUAL_CARE,
            )
    except Exception as e:
        log.error(
            "Error cancelling practitioner no-show appointment",
            error=e.__class__.__name__,
            exception=e,
            appointment_id=appointment_id,
        )
        stats.increment(
            metric_name=metric_name,
            tags=["success:false"],
            pod_name=stats.PodNames.VIRTUAL_CARE,
        )


@job
def cancel_member_no_shows() -> None:
    """
    Cancels appointments as member no-shows.
    """
    appointments = (
        db.session.query(Appointment)
        .filter(
            Appointment.scheduled_start
            >= (datetime.datetime.utcnow() - datetime.timedelta(hours=3)),
            Appointment.scheduled_end
            <= (datetime.datetime.utcnow() - datetime.timedelta(minutes=30)),
            Appointment.member_started_at == None,
            Appointment.practitioner_started_at != None,
            Appointment.cancelled_at == None,
            Appointment.member_ended_at == None,
        )
        .all()
    )

    log.info(f"Got {len(appointments)} member no-show appointments to cancel")
    for appointment in appointments:
        cancel_member_no_show.delay(appointment.id, team_ns="virtual_care")


@job(traced_parameters=("appointment_id",))
def cancel_member_no_show(appointment_id: int) -> None:
    """
    Cancels appointment as a member no-show.
    """
    metric_name = "api.appointments.tasks.appointments.cancel_member_no_show"

    log.info(
        "Attempting to process appointment as cancel member no-show . . .",
        appointment_id=appointment_id,
    )

    appointment = get_appointment(appointment_id)
    if not appointment:
        log.warning(
            "Unable to process cancel member no-show - invalid appointment id",
            appointment_id=appointment_id,
        )
        return

    # verify appointment should be cancelled as member no-show
    if appointment.member_started_at:
        log.info(
            "Unable to process cancel member no-show - started at value exists",
            appointment_id=appointment_id,
        )
        return
    if appointment.scheduled_end > datetime.datetime.utcnow():
        log.info(
            "Unable to process cancel member no-show - appointment scheduled to end later",
            appointment_id=appointment_id,
        )
        return
    if appointment.cancelled_at:
        log.info(
            "Unable to process cancel member no-show - appointment already cancelled",
            appointment_id=appointment_id,
        )
        return

    mp = appointment.member.member_profile
    if mp.json.get("payment_collection_failed"):
        log.info(
            "Unable to process cancel member no-show - payment collection already failed",
            appointment_id=appointment_id,
        )
        return

    # if member disconnected data exists and member_started_at is None, set the member_started_at
    # and return so we do not erroneously cancel the appointment
    if (
        disconnect_times := appointment.json.get(MEMBER_DISCONNECT_TIMES, None)
    ) and not appointment.member_started_at:
        log.info(
            "Processing cancel member no-show - attempting to set disconnected at time as started at time",
            appointment_id=appointment_id,
        )
        appointment.member_started_at = min(disconnect_times)
        db.session.add(appointment)
        db.session.commit()
        return

    try:
        log.info(
            "Going to cancel appointment as member no-show",
            appointment_id=appointment_id,
        )
        appointment.cancel(appointment.member.id, admin_initiated=True)
        db.session.add(appointment)
        db.session.commit()
        braze.update_appointment_attrs(appointment.member)

        if appointment.state == APPOINTMENT_STATES.cancelled:
            braze_events.appointment_no_show_member_to_member(appointment)
            braze_events.appointment_no_show_member_to_prac(appointment)
            stats.increment(
                metric_name=metric_name,
                tags=["success:true"],
                pod_name=stats.PodNames.VIRTUAL_CARE,
            )
            log.info(
                "Processed cancel member no-show appointment",
                appointment_id=appointment_id,
            )
        else:
            log.warning(
                "Cancel member no-show appointment - appointment did not end up in cancelled state",
                appointment_id=appointment_id,
                appointment_state=appointment.state,
            )
            stats.increment(
                metric_name=metric_name,
                tags=["success:false"],
                pod_name=stats.PodNames.VIRTUAL_CARE,
            )
    except Exception as e:
        log.error(
            "Error cancelling member no-show appointment",
            error=e.__class__.__name__,
            exception=e,
            appointment_id=appointment_id,
        )
        stats.increment(
            metric_name=metric_name,
            tags=["success:false"],
            pod_name=stats.PodNames.VIRTUAL_CARE,
        )


@job
def check_on_overflowing_appointments() -> None:
    """
    Check on overflowing appointments.
    """
    appointments = (
        db.session.query(Appointment)
        .filter(
            Appointment.scheduled_start
            >= (datetime.datetime.utcnow() - datetime.timedelta(hours=12)),
            Appointment.scheduled_end
            <= (datetime.datetime.utcnow() - datetime.timedelta(minutes=30)),
            Appointment.member_started_at != None,
            Appointment.practitioner_started_at != None,
            (
                (Appointment.member_ended_at == None)
                | (Appointment.practitioner_ended_at == None)
            ),
        )
        .all()
    )

    log.info(f"Got {len(appointments)} overflowing appointments to check")
    for appointment in appointments:
        check_on_overflowing_appointment.delay(appointment.id, team_ns="virtual_care")


@job(traced_parameters=("appointment_id",))
def check_on_overflowing_appointment(appointment_id: int) -> None:
    """
    Checks on an overflowing appointment.
    """
    metric_name = "api.appointments.tasks.appointments.check_on_overflowing_appointment"

    log.info(
        "Attempting to process check on overflowing appointment . . .",
        appointment_id=appointment_id,
    )

    appointment = get_appointment(appointment_id)
    if not appointment:
        log.warning(
            "Unable to process check on overflowing appointment - invalid appointment id",
            appointment_id=appointment_id,
        )
        return

    # if member disconnected data exists and member_ended_at is None, set the member_ended_at
    if (
        disconnect_times := appointment.json.get(MEMBER_DISCONNECT_TIMES, None)
    ) and not appointment.member_ended_at:
        log.info(
            "Processing check on overflow appointment - attempting to set disconnected at time as member ended at",
            appointment_id=appointment_id,
        )
        appointment.member_ended_at = max(disconnect_times)
        db.session.add(appointment)
        db.session.commit()

    # if practitioner disconnected data exists and practitioner_ended_at is None, set the practitioner_ended_at
    if (
        disconnect_times := appointment.json.get(PRACTITIONER_DISCONNECT_TIMES, None)
    ) and not appointment.practitioner_ended_at:
        log.info(
            "Processing check on overflow appointment - attempting to set disconnected at time as practitioner ended at",
            appointment_id=appointment_id,
        )
        appointment.practitioner_ended_at = max(disconnect_times)
        db.session.add(appointment)
        db.session.commit()

    # check to see if both x_ended_at values exist, if so, complete the appointment as an overdue
    if appointment.member_ended_at and appointment.practitioner_ended_at:
        log.info(
            "Unable to process check on overflow appointment - both ended at values exist, completing as an overdue appointment",
            appointment_id=appointment_id,
        )
        complete_overdue_appointment.delay(appointment.id, team_ns="virtual_care")
        return

    try:
        if not appointment.json.get("practitoner_overflow_checked"):
            log.info(
                "Sending overflow check for appointment", appointment_id=appointment_id
            )
            braze_events.appointment_overflow(appointment)
            appointment.json["practitoner_overflow_checked"] = True
            db.session.add(appointment)
            db.session.commit()
            log.info(
                "Initial overflow check complete for appointment",
                appointment_id=appointment_id,
            )
        elif (
            (appointment.json.get("practitoner_responded_overflow") is None)
            and (appointment.json.get("practitoner_overflow_checked_again") is None)
            and (
                appointment.scheduled_end
                < (datetime.datetime.utcnow() - datetime.timedelta(minutes=120))
            )
        ):
            log.info(
                "Re-sending overflow check for appointment",
                appointment_id=appointment_id,
            )
            braze_events.appointment_overflow(appointment)
            appointment.json["practitoner_overflow_checked_again"] = True
            db.session.add(appointment)
            db.session.commit()
            log.info(
                "Re-send overflow check complete for appointment",
                appointment_id=appointment_id,
            )
        else:
            log.info(
                "Already checked overflow for appointment",
                appointment_id=appointment_id,
                pracitioner_responded_overflow=appointment.json.get(
                    "practitoner_responded_overflow"
                ),
            )

        stats.increment(
            metric_name=metric_name,
            tags=["success:true"],
            pod_name=stats.PodNames.VIRTUAL_CARE,
        )
        log.info(
            "Processed check for overflow appointment", appointment_id=appointment_id
        )
    except Exception as e:
        log.error(
            "Error checking for overflow appointment",
            error=e.__class__.__name__,
            exception=e,
            appointment_id=appointment_id,
        )
        stats.increment(
            metric_name=metric_name,
            tags=["success:false"],
            pod_name=stats.PodNames.VIRTUAL_CARE,
        )


@job("priority", traced_parameters=("appointment_id",))
def update_member_cancellations(
    appointment_id: int, admin_initiated: bool = False
) -> None:
    """
    Updates the number of member initiated cancellations if member cancels
    within 24 hours of appointment scheduled start time.

    Initiates additional member cancellation activities for repeat offenders.

    Per product management: Repeat offenders are those members who cancel an appointment
    within 24 hrs of scheduled start time or who cancel via a no-show cancellation.
    """
    metric_name = "api.appointments.tasks.appointments.update_member_cancellations"

    log.info(
        "Attempting to process update member cancellations . . .",
        appointment_id=appointment_id,
    )

    appointment = get_appointment(appointment_id)
    if not appointment:
        log.warning(
            "Unable to process update member cancellations - invalid appointment id",
            appointment_id=appointment_id,
        )
        return

    # if appointment starts >= 24 hours from now and the cancellation was not admin initiated, do nothing
    if (
        appointment.scheduled_start
        >= datetime.datetime.utcnow() + datetime.timedelta(hours=24)
    ) and not admin_initiated:
        log.info(
            "Unable to process update member cancellations - appointment scheduled to start later",
            appointment_id=appointment_id,
        )
        return

    profile = appointment.member.profile
    notified_member = profile.get_repeat_offender()

    # if member was already notified, do nothing
    if notified_member:
        log.info(
            "Unable to process update member cancellations - member was already notified",
            appointment_id=appointment_id,
        )
        return

    try:
        try:
            profile.add_or_update_cancellations()
            db.session.add(profile)
            db.session.commit()
        except Exception as e:
            log.warning(
                "Error while attempting to update member profile cancellations",
                error=e.__class__.__name__,
                exception=e,
                appointment_id=appointment.id,
            )
            raise Error("Unable to update member profile cancellations")

        cancellations = profile.get_cancellations()

        if (
            cancellations
            and cancellations >= MAX_MEMBER_CANCELLATIONS
            and not notified_member
        ):
            braze_events.appointment_canceled_member_third_time(appointment)
            # update profile, set member notified
            profile.set_repeat_offender()
            db.session.add(profile)
            db.session.commit()

        stats.increment(
            metric_name=metric_name,
            tags=["success:true"],
            pod_name=stats.PodNames.VIRTUAL_CARE,
        )
        log.info(
            "Processed update member cancellations for appointment",
            appointment_id=appointment_id,
        )
    except Exception as e:
        log.error(
            "Error updating member cancellations",
            error=e.__class__.__name__,
            exception=e,
            appointment_id=appointment_id,
        )
        stats.increment(
            metric_name=metric_name,
            tags=["success:false"],
            pod_name=stats.PodNames.VIRTUAL_CARE,
        )


@ddtrace.tracer.wrap()
@job("priority", traced_parameters=("appointment_id",))
def appointment_post_reschedule_async_tasks(appointment_id: int) -> None:
    metric_name = "api.appointments.tasks.appointments.post_reschedule_async_tasks"
    try:
        appointment = get_appointment(appointment_id)
        if appointment:
            log.info(
                "Started post-reschedule async tasks for the appointment",
                appointment_id=appointment.id,
            )

            # Update the PractitionerAppointmentAck record with the new timestamp for
            # sending alerts and notifications
            practitioner_apt_ack = (
                db.session.query(PractitionerAppointmentAck)
                .filter(PractitionerAppointmentAck.appointment_id == appointment.id)
                .one()
            )
            if practitioner_apt_ack:
                practitioner_apt_ack.ack_by = (
                    appointment.scheduled_start - datetime.timedelta(minutes=10)
                )
                practitioner_apt_ack.warn_by = (
                    appointment.scheduled_start - datetime.timedelta(minutes=90)
                )
                # Clear the past records
                practitioner_apt_ack.is_acked = False
                practitioner_apt_ack.is_alerted = False
                practitioner_apt_ack.is_warned = False

                db.session.add(practitioner_apt_ack)
                db.session.commit()

            # Send practitioner a braze email event
            braze_events.appointment_rescheduled_practitioner(appointment)

            appointment_rescheduled_member(appointment=appointment)

            # braze.track_user(appointment.member)
            stats.increment(
                metric_name=metric_name,
                pod_name=stats.PodNames.VIRTUAL_CARE,
                tags=["success:true"],
            )
            log.info(
                "Finished post-reschedule tasks for appointment",
                appointment_id=appointment.id,
            )
    except DatabaseError as e:
        stats.increment(
            metric_name=metric_name,
            pod_name=stats.PodNames.VIRTUAL_CARE,
            tags=["error:true", "error_cause:failed_post_reschedule"],
        )
        log.error(
            "Database error in appointment_post_reschedule_async_tasks.",
            appointment_id=appointment_id,
            error=e,
        )
    except Exception as e:
        stats.increment(
            metric_name=metric_name,
            pod_name=stats.PodNames.VIRTUAL_CARE,
            tags=["error:true", "error_cause:failed_post_reschedule"],
        )
        log.exception(
            "Failed appointment_post_reschedule_async_tasks.",
            appointment_id=appointment_id,
            exception=e,
        )


@ddtrace.tracer.wrap()
@job("priority")
def send_appointment_completion_event() -> int:
    """
    Triggers the call to CPS to complete a meet activity when a member has completed an appointment
    """
    look_back_time = 8  # configured value help set the range in which we want to consider an appointments `scheduled_end_time`;
    # currently cron runs every 4 hours, and we want to look back 2n hours, which is 8

    log.info(f"Retrieving list of appointments within the last {look_back_time} hours")

    # get appointments that have a `scheduled_end_time` timestamp that is within the range of 2n hours ago and the time
    # that the cron is executed

    current_time = datetime.datetime.utcnow()
    time_delta = datetime.timedelta(hours=look_back_time)
    start_time = current_time - time_delta

    upcoming_appointment_args = {
        "scheduled_end_range": (start_time, current_time),
        "limit": 5,
        "offset": 0,
    }

    all_appointments = []

    while True:
        # query Appointment table based on arguments dict
        pagination, appointments = AppointmentRepository().get_appointments_paginated(
            upcoming_appointment_args
        )

        # extend list of appointments to return for final count
        all_appointments.extend(appointments)

        log.info(
            f"Attempting to process {len(appointments)} appointments",
            appointment_ids_to_member_ids=[
                (appointment.id, appointment.member_id) for appointment in appointments  # type: ignore[union-attr]
            ],
        )

        # Iterate through paginated appointments and trigger meet conditions if conditions are met
        for appointment in appointments:
            if not appointment:
                raise AttributeError("Missing appointment")

            if CarePlanActivityUtil.is_completed(appointment):
                CarePlansService.send_appointment_completed(
                    appointment, "mono_appt_cron"
                )

        if len(appointments) < upcoming_appointment_args["limit"]:
            break

        upcoming_appointment_args["offset"] += upcoming_appointment_args["limit"]

    return len(all_appointments)
