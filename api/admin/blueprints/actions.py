import csv
import datetime
import io
from decimal import Decimal

import flask_login as login
import stripe
from dateutil.parser import parse
from dateutil.relativedelta import relativedelta
from flask import (
    Blueprint,
    Response,
    abort,
    flash,
    jsonify,
    make_response,
    redirect,
    request,
    url_for,
)
from markupsafe import Markup
from pytz import timezone
from redis.lock import Lock
from sqlalchemy.orm import joinedload
from sqlalchemy.orm.exc import NoResultFound
from sqlalchemy.sql import and_, or_

from admin.common import SPEED_DATING_VERTICALS, _get_referer_path, https_url
from admin.process_stripe_csv import convert_rows
from appointments.models.appointment import Appointment
from appointments.models.constants import PRIVACY_CHOICES, ScheduleStates
from appointments.models.payments import (
    FeeAccountingEntry,
    FeeAccountingEntryTypes,
    Invoice,
)
from appointments.models.schedule import Schedule
from appointments.models.schedule_element import ScheduleElement
from appointments.models.schedule_event import ScheduleEvent
from appointments.services.common import (
    check_intro_appointment_purpose,
    purpose_is_intro,
)
from appointments.services.schedule import (
    BookingConflictException,
    managed_appointment_booking_availability,
    update_practitioner_profile_next_availability,
)
from appointments.tasks.appointment_notifications import (
    confirm_booking_email_to_member,
    notify_about_new_appointment,
)
from appointments.tasks.appointments import appointment_post_creation
from appointments.utils.booking import (
    AvailabilityCalculator,
    AvailabilityTools,
    TimeRange,
    is_in_date_ranges,
)
from appointments.utils.recurring_availability_utils import (
    check_conflicts_between_two_event_series,
)
from appointments.utils.redis_util import invalidate_appointment_cache
from audit_log.utils import (
    emit_audit_log_create,
    emit_audit_log_delete,
    emit_audit_log_read,
    emit_audit_log_update,
    emit_bulk_audit_log_create,
)
from authn.domain.repository import UserRepository
from authn.errors.idp.client_error import (
    ClientError,
    IdentityClientError,
    RequestsError,
)
from authn.models.user import User
from authn.resources.user import start_user_deletion
from bms.tasks.bms import process_bms_orders
from common.global_procedures.procedure import ProcedureService
from common.services.stripe import StripeConnectClient, StripeReimbursementHandler
from common.services.stripe_constants import PAYMENTS_STRIPE_API_KEY
from models.actions import audit
from models.enterprise import Invite
from models.gdpr import GDPRRequestSource
from models.products import Product
from models.profiles import Language, MemberProfile, PractitionerProfile
from models.tracks import (
    ChangeReason,
    TrackLifecycleError,
    initiate_transition,
    transition,
)
from models.tracks.lifecycle import add_track_closure_reason
from models.verticals_and_specialties import Vertical
from provider_matching.schemas.care_team_assignment import PractitionerReplacementSchema
from provider_matching.services.care_team_assignment import (
    REPLACE_PRAC_JOB_TIMEOUT,
    has_member_practitioner_association,
    is_an_active_available_practitioner,
    spin_off_replace_practitioner_in_care_teams_jobs,
)
from provider_matching.services.matching_engine import calculate_state_match_type
from providers.service.provider import ProviderService
from services.common import calculate_privilege_type
from storage.connection import db
from tasks.braze import update_bulk_messaging_attrs_in_braze
from tasks.marketing import repopulate_braze
from tasks.messaging import create_cx_message, send_to_zendesk
from tasks.notifications import notify_new_message
from tasks.payments import (
    PROVIDER_PAYMENTS_EMAIL,
    start_invoice_transfers_job,
    start_invoices,
)
from tracks.utils.common import get_active_member_track_modifiers
from utils import braze
from utils.cache import redis_client
from utils.data_management import gdpr_delete_user
from utils.exceptions import DeleteUserActionableError, ProgramLifecycleError
from utils.log import logger
from utils.passwords import encode_password, random_password
from wallet.models.reimbursement import ReimbursementRequest
from wallet.models.reimbursement_wallet_credit import ReimbursementCycleCredits
from wallet.services.reimbursement_qualifying_life_event import apply_qle_to_plan

URL_PREFIX = "actions"

log = logger(__name__)
actions = Blueprint(URL_PREFIX, __name__)


@actions.route("/payout_reimbursement", methods=["POST"])
@login.login_required
def payout_reimbursement():  # type: ignore[no-untyped-def] # Function is missing a return type annotation
    data = request.form

    log.info("Data from payout reimbursement attempt", data=data)

    if "reimbursement_request_id" not in data or "user_id" not in data:
        raise ValueError(
            "Missing input data necessary for sending a reimbursement payout."
        )
    reimbursement_request = ReimbursementRequest.query.get(
        data["reimbursement_request_id"]
    )
    if not reimbursement_request:
        raise ValueError("Reimbursement Request not found.")
    user = User.query.get(data["user_id"])
    if not user:
        raise ValueError("User not found.")
    try:
        StripeReimbursementHandler.create_reimbursement_payout(
            user=user, reimbursement_request=reimbursement_request
        )
    except ValueError as e:
        flash(str(e), category="error")
    return redirect("/admin/reimbursement_dashboard")


@actions.route("/repopulate_braze", methods=["POST"])
@login.login_required
def repopulate_braze_users():  # type: ignore[no-untyped-def] # Function is missing a return type annotation
    user_ids_file = request.files.get("user_ids_file")

    user_ids = []
    with io.StringIO(user_ids_file.read().decode()) as fp:  # type: ignore[union-attr] # Item "None" of "Optional[Any]" has no attribute "read"
        reader = csv.DictReader(fp)
        if reader.fieldnames != ["user_id"]:
            flash(
                "Invalid csv file, please only provide a file with 'user_id' header",
                category="error",
            )
            return redirect("/admin/marketing_tools")
        for row in reader:
            user_ids.append(row["user_id"])

    repopulate_braze.delay(user_ids)

    flash("Repopulating braze...", category="success")
    return redirect("/admin/marketing_tools")


@actions.route("/update_practitioner_bank_account", methods=["POST"])
@login.login_required
def update_practitioner_bank_account():  # type: ignore[no-untyped-def] # Function is missing a return type annotation
    practitioner_id = request.form.get("practitioner_id")
    routing_id = request.form.get("routing_id")
    account_id = request.form.get("account_id")

    try:
        practitioner = (
            db.session.query(PractitionerProfile)
            .filter(PractitionerProfile.user_id == int(practitioner_id))  # type: ignore[arg-type] # Argument 1 to "int" has incompatible type "Optional[Any]"; expected "Union[str, Buffer, SupportsInt, SupportsIndex, SupportsTrunc]"
            .one()
        )
    except Exception as exc:
        flash("Bad prac ID!")
        redirect(https_url("admin.index"))
        log.error(str(exc))

    bank_info = {
        "account_number": account_id,
        "routing_number": routing_id,
        "currency": "USD",
        "country": "US",
    }

    try:
        token = stripe.Token.create(bank_account=bank_info)
    except:  # noqa  B001  TODO:  Do not use bare `except:`, it also catches unexpected events like memory errors, interrupts, system exit, and so on.  Prefer `except Exception:`.  If you're sure what you're doing, be explicit and write `except BaseException:`.
        flash("Bad account info!")
        redirect(https_url("admin.index"))

    stripe_client = StripeConnectClient(api_key=PAYMENTS_STRIPE_API_KEY)
    account = stripe_client.set_bank_account_for_user(
        practitioner.user, token.id, overwrite_allowed=True
    )
    if account:
        flash("Set new bank account!")
    else:
        flash("Could not set bank account!")

    return redirect(https_url("admin.index"))


@actions.route("/set_practitioner_prescription_info", methods=["POST"])
@login.login_required
def set_practitioner_dosespot_info():  # type: ignore[no-untyped-def] # Function is missing a return type annotation
    admin_home_url = https_url("admin.index")
    practitioner_id = request.form.get("practitioner_id")
    prescribe_id = request.form.get("prescriber_id")
    clinic_id = request.form.get("clinic_id")
    clinic_key = request.form.get("clinic_key")

    if not all([practitioner_id, clinic_key, clinic_id, prescribe_id]):
        flash("Provide all data!")
        return redirect(admin_home_url)

    def valid_u32_int(field_name, value):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        try:
            value = int(value)
            if value > 0xFFFFFFFF:  # max unsigned 32bit int
                log.error("%s is overflowing an unsigned 32bit integer!", field_name)
                raise ValueError(f"Invalid {field_name}")
        except ValueError as e:
            log.error(e)
            flash(f"Invalid {field_name}", "error")
            return False

        return True

    if not valid_u32_int("clinic_id", clinic_id) or not valid_u32_int(
        "dosespot_prescriber_id", prescribe_id
    ):
        return redirect(admin_home_url)

    try:
        practitioner = db.session.query(User).filter(User.id == practitioner_id).one()
    except NoResultFound:
        flash("Bad practitioner ID!")
        return redirect(admin_home_url)

    profile = practitioner.practitioner_profile

    if "clinic_key" in (profile.dosespot or {}):
        flash("Practitioner already saved!")
        return redirect(https_url("admin.index"))

    old = profile.dosespot or {}
    old.update(
        {"clinic_key": clinic_key, "clinic_id": clinic_id, "user_id": int(prescribe_id)}  # type: ignore[arg-type] # Argument 1 to "int" has incompatible type "Optional[Any]"; expected "Union[str, Buffer, SupportsInt, SupportsIndex, SupportsTrunc]"
    )
    profile.dosespot = old

    db.session.add(practitioner)
    db.session.commit()

    flash(f"Saved DoseSpot info for {practitioner.email}!")
    return redirect(https_url("admin.index"))


@actions.route("/add_fee", methods=["POST"])
@login.login_required
def add_fee():  # type: ignore[no-untyped-def] # Function is missing a return type annotation
    fee_amount = request.form.get("fee_amount")
    practitioner_id = request.form.get("practitioner_id")
    appointment_id = request.form.get("appointment_id")
    audit_create = None
    audit_update = None

    practitioner = (
        db.session.query(PractitionerProfile)
        .filter(PractitionerProfile.user_id == practitioner_id)
        .first()
    )
    if practitioner is None:
        flash("Error: Practitioner ID not valid", category="error")
        return redirect("/admin/practitioner_tools")

    log.info(f"Adding fee for {practitioner.user_id} with amount: {fee_amount}")

    try:
        fee_amount = Decimal(fee_amount)  # type: ignore[arg-type] # Argument 1 to "Decimal" has incompatible type "Optional[Any]"; expected "Union[Decimal, float, str, Tuple[int, Sequence[int], int]]"
    except Exception as e:
        log.error(e)
        flash(f"Invalid fee amount: {fee_amount}", "error")
        return redirect("/admin/practitioner_tools")

    if fee_amount > 100:
        flash("Error: Fee is too high - add manually", category="error")
        return redirect("/admin/practitioner_tools")
    elif fee_amount < -100:
        flash("Error: Fee is too low - add manually", category="error")
        return redirect("/admin/practitioner_tools")

    if appointment_id:
        appointment = db.session.query(Appointment).get(appointment_id)
        if appointment is None:
            flash("Error: Appointment ID not valid", category="error")
            return redirect("/admin/practitioner_tools")
        elif (
            not appointment.practitioner
            or appointment.practitioner.id != practitioner.user_id
        ):
            flash(
                "Error: Appointment does not belong to practitioner", category="error"
            )
            return redirect("/admin/practitioner_tools")
        elif appointment and not appointment.requires_fee:
            flash(
                "Appointment doesn't require fee for internal reasons -- fee won't be paid, not creating fee."
            )
            return redirect("/admin/practitioner_tools")
        fee = FeeAccountingEntry(
            appointment=appointment,
            amount=fee_amount,
            practitioner_id=practitioner.user_id,
            type=FeeAccountingEntryTypes.APPOINTMENT,
        )
        audit_update = fee
    else:
        fee = FeeAccountingEntry(
            practitioner_id=practitioner.user_id,
            amount=fee_amount,
            type=FeeAccountingEntryTypes.APPOINTMENT,
        )
        audit_create = fee

    log.info(f"Added Fee via Admin: {fee}")
    db.session.add(fee)
    db.session.commit()
    if audit_update:
        emit_audit_log_update(audit_update)
    if audit_create:
        emit_audit_log_create(audit_create)

    flash(f"Added: {fee}")
    return redirect("/admin/practitioner_tools")


@actions.route("/set_promo_time_range", methods=["POST"])
@login.login_required
def set_promo_time_range():  # type: ignore[no-untyped-def] # Function is missing a return type annotation
    try:
        start_str, end_str = request.form.get("promo_time_range", "").split(" to ")
        start, end = parse(start_str), parse(end_str)
    except Exception:
        flash(
            "Invalid range, expected format: "
            "YYYY-MM-DD HH:mm:ss to YYYY-MM-DD HH:mm:ss",
            category="error",
        )
        return redirect("/admin/practitioner_tools")
    if end < start:
        flash(
            "Invalid range, expected format: "
            "YYYY-MM-DD HH:mm:ss to YYYY-MM-DD HH:mm:ss",
            category="error",
        )
        return redirect("/admin/practitioner_tools")
    for vertical in (
        db.session.query(Vertical)
        .filter(Vertical.name.in_(SPEED_DATING_VERTICALS))
        .all()
    ):
        vertical.promo_start = start
        vertical.promo_end = end
    db.session.commit()
    flash("success!")
    return redirect("/admin/practitioner_tools")


@actions.route("/set_recurring_availability", methods=["POST"])
@login.login_required
def set_recurring_availability():  # type: ignore[no-untyped-def] # Function is missing a return type annotation
    practitioner = db.session.query(PractitionerProfile).get(
        request.form.get("practitioner_id")
    )
    if practitioner is None:
        flash("Error: Practitioner ID not valid", category="error")
        return redirect("/admin/practitioner_tools")

    starts_at = parse(request.form.get("starts_at"))  # type: ignore[arg-type] # Argument 1 to "parse" has incompatible type "Optional[Any]"; expected "Union[bytes, str, IO[str], IO[Any]]"
    if starts_at < datetime.datetime.utcnow():
        flash("Error: starts_at must be in the future!", category="error")
        return redirect("/admin/practitioner_tools")

    until = parse(request.form.get("until"))  # type: ignore[arg-type] # Argument 1 to "parse" has incompatible type "Optional[Any]"; expected "Union[bytes, str, IO[str], IO[Any]]"

    # Check if we potentially cross a DST change within the time range. Note
    # that we won't necessarily know the user's time zone(?), so just choosing
    # US/Eastern should tell us generally if there is a DST change...
    for change in timezone("US/Eastern")._utc_transition_times:  # type: ignore[union-attr] # Item "_UTCclass" of "Union[_UTCclass, StaticTzInfo, DstTzInfo]" has no attribute "_utc_transition_times" #type: ignore[union-attr] # Item "StaticTzInfo" of "Union[_UTCclass, StaticTzInfo, DstTzInfo]" has no attribute "_utc_transition_times" #type: ignore[union-attr] # Item "DstTzInfo" of "Union[_UTCclass, StaticTzInfo, DstTzInfo]" has no attribute "_utc_transition_times"
        if starts_at <= change <= until:
            flash(
                f"Error: Time range crosses DST change (at: {change.isoformat()})",
                category="error",
            )
            return redirect("/admin/practitioner_tools")

    duration = int(request.form.get("duration"))  # type: ignore[arg-type] # Argument 1 to "int" has incompatible type "Optional[Any]"; expected "Union[str, Buffer, SupportsInt, SupportsIndex, SupportsTrunc]"
    schedule = practitioner.user.schedule
    days = [int(x) for x in request.form.getlist("week_days_index")]
    request_json = request.json if request.is_json else None

    e = ScheduleElement(
        frequency="WEEKLY",
        starts_at=starts_at,
        duration=duration,
        count=0,
        week_days_index=days,
    )

    new_recurring_blocks = e.occurrences(end_at=until)

    existing = (
        schedule.existing_events(starts_at, until)
        .filter(ScheduleEvent.state == ScheduleStates.available)
        .all()
    )

    existing_availability = [(x.starts_at, x.ends_at) for x in existing]

    schedule_conflict_exists = check_conflicts_between_two_event_series(
        existing_availability, new_recurring_blocks
    )

    if schedule_conflict_exists:
        audit("schedule_events_conflict", request_args=request_json)
        log.debug("Conflicts with %s", existing)
        flash(
            "Error: Conflict with existing availability!",
            category="error",
        )
        return redirect("/admin/practitioner_tools")

    for start_dt, end_dt in e.occurrences(end_at=until):
        audit_list = []
        new = ScheduleEvent(
            schedule=schedule, starts_at=start_dt, ends_at=end_dt, state="AVAILABLE"
        )
        db.session.add(new)
        audit_list.append(new)
        log.info(f"Added {new}")
    db.session.commit()
    emit_bulk_audit_log_create(audit_list)

    flash("success!")
    return redirect("/admin/practitioner_tools")


@actions.route("/update_member_bulk_messaging_settings", methods=["POST"])
@login.login_required
def update_member_bulk_messaging_settings():  # type: ignore[no-untyped-def] # Function is missing a return type annotation
    user_id = int(request.form.get("user_id"))  # type: ignore[arg-type] # Argument 1 to "int" has incompatible type "Optional[Any]"; expected "Union[str, Buffer, SupportsInt, SupportsIndex, SupportsTrunc]"
    member_profile = MemberProfile.query.filter(MemberProfile.user_id == user_id).one()

    for n in range(10):
        field_key = f"braze_pause_message_{n + 1}"
        pause_enabled = request.form.get(field_key)
        if pause_enabled:
            member_profile.json[field_key] = "yes"
        else:
            member_profile.json.pop(field_key, None)

    db.session.add(member_profile)
    emit_audit_log_update(member_profile)
    db.session.commit()

    flash("Saved bulk message settings. Updating Braze in the background.")

    update_bulk_messaging_attrs_in_braze.delay(member_profile.user.id)

    return redirect(f"/admin/memberprofile/edit/?id={user_id}")


@actions.route("/proactive_booking", methods=["POST"])
@login.login_required
def proactive_booking():  # type: ignore[no-untyped-def] # Function is missing a return type annotation
    """
    This whole endpoint is a hack and at some point we should refactor to
    either use the API to do the booking with that user's auth or we
    should refactor into common code.
    """
    user_id = int(request.form.get("user_id"))  # type: ignore[arg-type] # Argument 1 to "int" has incompatible type "Optional[Any]"; expected "Union[str, Buffer, SupportsInt, SupportsIndex, SupportsTrunc]"
    try:
        product_id = int(request.form.get("product_id"))  # type: ignore[arg-type] # Argument 1 to "int" has incompatible type "Optional[Any]"; expected "Union[str, Buffer, SupportsInt, SupportsIndex, SupportsTrunc]"
    except ValueError:
        flash(
            "Invalid product id. Did you paste the proactive booking string in the right field?"
        )
        return redirect(f"/admin/memberprofile/edit/?id={user_id}")

    request_purpose = request.form.get("purpose", "")

    if (
        request_purpose == "None"
    ):  # this would be the literal string "None", not a null value
        request_purpose = ""

    if request_purpose not in (
        "",
        "birth_needs_assessment",
        "birth_planning",
        "postpartum_needs_assessment",
        "introduction",
        "introduction_egg_freezing",
        "introduction_fertility",
        "introduction_menopause",
        "childbirth_ed",
        "pediatric_prenatal_consult",
        "postpartum_planning",
    ):
        flash(f"Bad purpose: {request_purpose}")
        return redirect(f"/admin/memberprofile/edit/?id={user_id}")

    try:
        scheduled_start = parse(request.form.get("scheduled_start"))  # type: ignore[arg-type] # Argument 1 to "parse" has incompatible type "Optional[Any]"; expected "Union[bytes, str, IO[str], IO[Any]]"
    except ValueError:
        flash(f"Bad start time format: {request.form.get('scheduled_start')}")
        return redirect(f"/admin/memberprofile/edit/?id={user_id}")

    if scheduled_start.tzinfo:
        flash("Error: Do not specify timezone in date", category="error")
        return redirect(f"/admin/memberprofile/edit/?id={user_id}")

    try:
        user = db.session.query(User).filter(User.id == user_id).one()
    except NoResultFound:
        flash("That user does not exist!")
        return redirect(f"/admin/memberprofile/edit/?id={user_id}")

    try:
        product = (
            db.session.query(Product)
            .filter(Product.id == product_id)
            .options(joinedload("practitioner"))
            .one()
        )
    except NoResultFound:
        flash("That product does not exist!")
        return redirect(f"/admin/memberprofile/edit/?id={user_id}")

    scheduled_end = scheduled_start + datetime.timedelta(minutes=product.minutes)

    profile = product.practitioner.practitioner_profile

    active_tracks = user.active_tracks

    # don't allow proactive booking for doula-only member and unsupported provider
    if not ProviderService.provider_can_member_interact(
        provider=profile,
        modifiers=get_active_member_track_modifiers(active_tracks),
        client_track_ids=[track.client_track_id for track in active_tracks],
    ):
        flash("This member isn't allowed to book with providers of this type.")
        return redirect(f"/admin/memberprofile/edit/?id={user_id}")

    log.info(
        "Proactive booking appointment for member",
        user_id=user_id,
        practitioner_id=profile.user_id,
        logged_in_user_id=login.current_user.id,
    )
    try:
        with managed_appointment_booking_availability(product, scheduled_start, user):
            cancellation_policy = (
                product.practitioner.practitioner_profile.default_cancellation_policy
            )

            # Match appt to schedule_event record
            try:
                event = ScheduleEvent.get_schedule_event_from_timestamp(
                    product.practitioner.schedule,
                    scheduled_start,
                )
            except Exception as error:
                # This shouldn't happen after the is_available check above
                # If it does, set event to None and log (allow to continue)
                event = None
                log.warning(
                    "Error matching appointment to schedule",
                    member_id=user_id,
                    product_id=product_id,
                    scheduled_start=scheduled_start,
                    error=str(error),
                )

            log.info(
                "Checking proactive booking appointment purpose against calculated purpose",
                user_id=user_id,
                product_id=product_id,
                request_purpose=request_purpose,
            )
            calculated_purpose = check_intro_appointment_purpose(user, product)
            if not request_purpose:
                purpose = calculated_purpose
                log.info(
                    "No purpose provided in proactive booking, so falling back to calculated purpose",
                    user_id=user_id,
                    product_id=product_id,
                    purpose=purpose,
                )
            else:
                request_purpose_is_intro = purpose_is_intro(request_purpose)
                calculated_purpose_is_intro = purpose_is_intro(calculated_purpose)
                if not request_purpose_is_intro and calculated_purpose_is_intro:
                    # if our calculated purpose is an intro but the admin input is not
                    # assume the calculated purpose is right
                    log.info(
                        "Proactive booking provided purpose was not an intro, but calculated purpose was. Using calculated purpose",
                        user_id=user_id,
                        product_id=product_id,
                        request_purpose=request_purpose,
                        calculated_purpose=calculated_purpose,
                    )
                    purpose = calculated_purpose
                elif request_purpose_is_intro and not calculated_purpose_is_intro:
                    # if our admin input is an intro but our calculated purpose
                    # is not an intro, throw an error and prevent the user from saving
                    log.warning(
                        "Proactive booking provided purpose is an intro, but calculated purpose was not an intro. Raising error and not saving appointment.",
                        user_id=user_id,
                        product_id=product_id,
                        request_purpose=request_purpose,
                        calculated_purpose=calculated_purpose,
                    )
                    flash(
                        "This appointment does not appear to be an intro appointment. The member may have had a previous CA appointment in their current track or a previous track. Please choose a different purpose or leave the field blank.",
                        category="error",
                    )
                    return redirect(f"/admin/memberprofile/edit/?id={user_id}")
                else:
                    purpose = request_purpose

            appointment = Appointment(
                schedule_event=event,
                scheduled_start=scheduled_start,
                scheduled_end=scheduled_end,
                product=product,
                purpose=(purpose or (product.purpose and product.purpose.value)),
                member_schedule=user.schedule,
                cancellation_policy=cancellation_policy,
                privacy=PRIVACY_CHOICES.basic,
                privilege_type=calculate_privilege_type(product.practitioner, user),
                state_match_type=calculate_state_match_type(
                    product.practitioner.practitioner_profile, user
                ),
                json={"admin_booked": True},
            )
            # flush the db session so we have an appt id for payment
            db.session.flush()

            paid = appointment.authorize_payment()
            log.info(
                "Proactive booking appointment created",
                appointment_id=appointment.id,
                user_id=user.id,
                practitioner_id=product.practitioner.id,
            )
            if paid is not None:
                db.session.add(appointment)
                db.session.commit()
                invalidate_appointment_cache(appointment=appointment)
                emit_audit_log_create(appointment)
                appointment_post_creation.delay(appointment.id)
                notify_about_new_appointment.delay(appointment.id)
                confirm_booking_email_to_member.delay(appointment.id)
                profile = product.practitioner.practitioner_profile
                update_practitioner_profile_next_availability(profile)

                flash(f"Appointment was booked!{appointment}")
                return redirect(f"/admin/memberprofile/edit/?id={user_id}")
            else:
                flash("Payment issue!")
                return redirect(f"/admin/memberprofile/edit/?id={user_id}")
    except BookingConflictException:
        # Recheck unavailable dates for better error messaging
        calculator = AvailabilityCalculator(
            practitioner_profile=product.practitioner.practitioner_profile,
            product=product,
        )
        if calculator.assignable_advocate is not None:
            member_has_had_ca_intro_appt = (
                AvailabilityTools.has_had_ca_intro_appointment(user)
            )
            unavailable_dates: list[
                TimeRange
            ] = calculator.assignable_advocate.unavailable_dates(
                scheduled_start,
                scheduled_end,
                member_has_had_ca_intro_appt,
                True,
            )
            if is_in_date_ranges(scheduled_start, unavailable_dates):
                flash(
                    f"No availability for {scheduled_start} due to the practitioner's max capacity"
                )
                return redirect(f"/admin/memberprofile/edit/?id={user_id}")

        flash(f"No availability for {scheduled_start}.")
        return redirect(f"/admin/memberprofile/edit/?id={user_id}")


@actions.route("/send_cx_message", methods=["POST"])
@login.login_required
def send_cx_message():  # type: ignore[no-untyped-def] # Function is missing a return type annotation
    user_id = request.form.get("user_id")
    message_text = request.form.get("message_text")
    redirect_path = _get_referer_path()
    if not (user_id and message_text):
        flash("Need User ID and message text")
        return redirect(redirect_path)

    user = User.query.get_or_404(user_id)
    message = create_cx_message(user, message=message_text, only_first=False)

    if message:
        db.session.commit()
        notify_new_message.delay(user.id, message.id)
        send_to_zendesk.delay(
            message.id,
            initial_cx_message=True,
            user_need_when_solving_ticket="customer-need-member-proactive-outreach-other",
            caller="send_cx_message",
        )
        emit_audit_log_create(message)
        flash("All set adding 1 Message!")
        return redirect(redirect_path)
    else:
        log.warning(f"Problem adding Message for {user}")
        flash("Could not send Message. Ask dev team for help!")
        return redirect(redirect_path)


@actions.route("/appointment_followup_info", methods=["POST"])
@login.login_required
def appointment_followup_info():  # type: ignore[no-untyped-def] # Function is missing a return type annotation
    redirect_path = _get_referer_path()
    user_id = request.form.get("user_id")
    note = request.form.get("member_profile_note")
    follow_up_reminder_send_time = request.form.get("follow_up_reminder_send_time")

    if not (note or follow_up_reminder_send_time):
        flash("Please provide a member profile note or follow up send time")
        return redirect(redirect_path)

    user = db.session.query(User).get(user_id)
    if not user:
        flash("User {} not found", category="error")
        return redirect(redirect_path)

    if follow_up_reminder_send_time:
        try:
            send_time = parse(follow_up_reminder_send_time)
        except Exception:
            flash(
                "Could not parse date for follow up reminder send time.",
                category="error",
            )
            return redirect(redirect_path)
        user.member_profile.follow_up_reminder_send_time = send_time

    if note:
        user.member_profile.note = note
        flash("Saved note to member profile")

    emit_audit_log_update(user.member_profile)

    db.session.commit()

    return redirect(redirect_path)


@actions.route("/delete_user_permanently", methods=["POST"])
@login.login_required
def delete_user_permanently():  # type: ignore[no-untyped-def] # Function is missing a return type annotation
    if not request.form.get("user_id"):
        flash("No user id provided in the form", category="info")
        return redirect("/admin/delete_user")

    date_str = request.form.get("date")

    if not date_str:
        flash("Please select the Requested Date.", category="info")
        return redirect("/admin/delete_user")

    # No expected value error as date is selected using the calendar widget, and it always returns `Y-%m-%d` format.
    requested_date = datetime.datetime.strptime(date_str, "%Y-%m-%d").date()
    user_id = int(request.form.get("user_id"))  # type: ignore[arg-type] # Argument 1 to "int" has incompatible type "Optional[Any]"; expected "Union[str, Buffer, SupportsInt, SupportsIndex, SupportsTrunc]"
    email = request.form.get("email").strip()  # type: ignore[union-attr] # Item "None" of "Optional[Any]" has no attribute "strip"
    url = request.form.get("url")
    delete_idp = bool(request.form.get("delete_idp", True))
    try:
        gdpr_delete_user(
            "YES_I_AM_SURE",
            login.current_user,
            user_id,
            email,
            requested_date,
            delete_idp=delete_idp,
        )
        db.session.commit()
        flash(
            Markup(f"User {user_id} - {email} permanently deleted!"),
            category="info",
        )
        return redirect("/admin/delete_user")
    except DeleteUserActionableError as ae:
        flash(str(ae), category="warning")
        return redirect(url)  # type: ignore[arg-type] # Argument 1 to "redirect" has incompatible type "Optional[Any]"; expected "str"
    except Exception as e:
        log.error(e)
        flash(
            f"(╯°□°)╯┅ ┻━┻ hop over & tap someone's shoulder at engineering: {e}",
            category="error",
        )
        return redirect(url)  # type: ignore[arg-type] # Argument 1 to "redirect" has incompatible type "Optional[Any]"; expected "str"


@actions.route("/start_delete_user_request", methods=["POST"])
@login.login_required
def start_delete_user_request():  # type: ignore[no-untyped-def] # Function is missing a return type annotation
    if not request.form.get("user_id"):
        flash("No user id provided in the form", category="info")
        return redirect("/admin/user/")

    user_id = int(request.form.get("user_id"))  # type: ignore[arg-type] # Argument 1 to "int" has incompatible type "Optional[Any]"; expected "Union[str, Buffer, SupportsInt, SupportsIndex, SupportsTrunc]"
    user = User.query.get(user_id)
    is_successful = start_user_deletion(user, GDPRRequestSource.ADMIN)
    if not is_successful:
        flash(
            "You had previously submitted a delete request for this user. You cannot submit a new delete request.",
            category="info",
        )

    emit_audit_log_delete(user)
    return redirect(f"/admin/user/edit/?id={user_id}")


@actions.route("/translate_stripe_csv", methods=["POST"])
@login.login_required
def translate_stripe_csv():  # type: ignore[no-untyped-def] # Function is missing a return type annotation
    if "content" not in request.files:
        abort(400)

    _csv = request.files["content"]
    with io.StringIO(_csv.stream.read().decode("utf-8"), newline=None) as stream:
        reader = csv.DictReader(stream)
        # save here so we can leave the file read context
        rows = [r for r in reader]

    report = io.StringIO()
    writer = csv.DictWriter(
        report, fieldnames=["date_time", "description", "amount"], extrasaction="ignore"
    )
    writer.writeheader()

    try:
        rows = convert_rows(rows)
    except (KeyError, ValueError) as e:
        log.error(e)
        flash(f"Error converting csv: {e}")
        return redirect("/admin/payment_tools")

    for row in rows:
        writer.writerow(row)

    report.seek(0)
    response = Response(report)

    filename = "stripe-csv.csv"
    response.headers["Content-Description"] = "File Transfer"
    response.headers["Cache-Control"] = "no-cache"
    response.headers["Content-Type"] = "text/csv"
    response.headers["Content-Disposition"] = f"attachment; filename={filename}"

    return response


@actions.route("/start_invoice_transfers", methods=["POST"])
@login.login_required
def start_invoice_transfers():  # type: ignore[no-untyped-def] # Function is missing a return type annotation
    data = request.form
    fee_hash = data.get("fee_hash", "")
    if fee_hash:
        start_invoice_transfers_job.delay(
            provided_fee_hash=fee_hash, team_ns="payments_platform", job_timeout=60 * 60
        )
        flash(
            "The Invoice Transfer job has been scheduled, a notification will be sent to {} when started and completed.",
            format(PROVIDER_PAYMENTS_EMAIL),
        )
    else:
        flash(
            "No fee hash code provided, please start transfers manually if required",
            category="error",
        )

    return redirect("/admin/payment_tools")


@actions.route("/restart_invoice_transfers", methods=["POST"])
@login.login_required
def restart_invoice_transfers():  # type: ignore[no-untyped-def] # Function is missing a return type annotation
    """
    Endpoint that kicks off similar process to the start_transfers admin action (but using the
    start_invoices job which is also doing the same thing but async), but automatically by grabbing
    invoice's to be processed instead of being manually selected
    """
    incomplete_invoices = (
        db.session.query(Invoice)
        .filter(
            Invoice.started_at.is_(None),
            Invoice.created_at >= datetime.datetime.utcnow() - relativedelta(months=1),
        )
        .all()
    )
    invoice_ids = [
        invoice.id
        for invoice in incomplete_invoices
        if invoice.value > 0 and invoice.practitioner is not None
    ]
    start_invoices.delay(
        team_ns="payments_platform",
        job_timeout=30 * 60,
        invoice_ids=invoice_ids,
    )

    return redirect("/admin/payment_tools")


@actions.route("/resend_invite", methods=["POST"])
@login.login_required
def resend_invite():  # type: ignore[no-untyped-def] # Function is missing a return type annotation
    redirect_path = _get_referer_path()

    invite = Invite.query.filter_by(id=request.form.get("invite_id")).one_or_none()
    braze.fileless_invite_requested(invite)

    return redirect(redirect_path)


@actions.route("/tracks/transition", methods=["POST"])
@login.login_required
def transition_track():  # type: ignore[no-untyped-def] # Function is missing a return type annotation
    from models.tracks import MemberTrack

    target = request.form.get("target")
    force_transition = bool(request.form.get("force_transition"))
    member_track_id = int(request.form.get("member_track_id"))  # type: ignore[arg-type] # Argument 1 to "int" has incompatible type "Optional[Any]"; expected "Union[str, Buffer, SupportsInt, SupportsIndex, SupportsTrunc]"
    member_track = MemberTrack.query.get(member_track_id)

    track = member_track
    try:
        user_id = str(login.current_user.id or "")
        if force_transition:
            track = transition(
                source=member_track,
                target=target,
                modified_by=user_id,
                change_reason=ChangeReason.ADMIN_FORCE_TRANSITION,
            )
            emit_audit_log_create(track)
        else:
            track = initiate_transition(
                track=member_track,
                target=target,
                modified_by=user_id,
                change_reason=ChangeReason.ADMIN_TRANSITION,
            )
            emit_audit_log_update(track)
        db.session.commit()
        closure_reason_id = int(request.form.get("closure_reason_id"))  # type: ignore[arg-type] # Argument 1 to "int" has incompatible type "Optional[Any]"; expected "Union[str, Buffer, SupportsInt, SupportsIndex, SupportsTrunc]"
        add_track_closure_reason(member_track, closure_reason_id)

    # TODO: [Track] Phase 3 - drop ProgramLifecycleError.
    except (TrackLifecycleError, ProgramLifecycleError) as e:
        db.session.rollback()
        flash(str(e))

    # Show CAs a confirmation that the multi-step transition has been initiated.
    # The member must compelte the assessment before CAs see the new track in Admin.
    if not force_transition:
        flash(
            "Transition was successful! Once the member completes the in-app assessment, "
            + "the track transition will be reflected in Admin."
        )

    return redirect(url_for("membertrack.edit_view", id=track.id))


@actions.route("/reimbursement_wallet/qle", methods=["POST"])
@login.login_required
def add_qle():  # type: ignore[no-untyped-def] # Function is missing a return type annotation
    from wallet.models.reimbursement import ReimbursementPlan

    redirect_path = _get_referer_path()
    data = request.form

    plan_id = data["plan_id"]
    plan = ReimbursementPlan.query.get(plan_id)

    amount = data["amount"]
    effective_date = data["effective_date"]
    effective_date = datetime.datetime.strptime(effective_date, "%Y-%m-%d")

    flash_messages = apply_qle_to_plan(plan, amount, effective_date)
    if flash_messages:
        for flash_message in flash_messages:
            flash(
                message=flash_message.message,
                category=flash_message.category.value,
            )

    return redirect(redirect_path)


class PracReplacementEndpointMessage(str):
    MISSING_PRAC_ID = "Did not provide practitioner_id"
    INVALID_PRAC_ID = "Invalid Practitioner ID"
    MISSING_REMOVE_ONLY_QUIZ_TYPE = "Did not provider remove_only_quiz_type value"
    PRAC_TO_REPLACE_IN_NEW_PRACS = "Practitioner to be replaced is present in list of active potential new practitioners (Update Care Teams list)"
    PRAC_NOT_PRESENT_IN_ANY_CARE_TEAM = "Practitioner not present in any care teams"
    PRAC_NOT_PRESENT_IN_ANY_CARE_TEAM_AS_QUIZ = (
        "Practitioner not present in any care teams as type quiz"
    )
    ANOTHER_JOB_RUNNING_FOR_SAME_PRAC = (
        "Another replace practitioner job is running for this practitioner"
    )
    PRAC_IS_CARE_ADVOCATE = "Practitioner to be replaced is a care advocate"


@actions.route("/replace_practitioner/", methods=["POST"])
@login.login_required
def replace_practitioner():  # type: ignore[no-untyped-def] # Function is missing a return type annotation
    practitioner_id = request.form.get("practitioner_id")
    if not practitioner_id:
        log.warn(PracReplacementEndpointMessage.MISSING_PRAC_ID)
        return make_response(
            jsonify({"error": PracReplacementEndpointMessage.MISSING_PRAC_ID}), 400
        )

    prac_to_replace = PractitionerProfile.query.get(practitioner_id)
    if not prac_to_replace:
        log.warn(
            PracReplacementEndpointMessage.INVALID_PRAC_ID,
            practitioner_id=practitioner_id,
        )
        return make_response(
            jsonify({"error": PracReplacementEndpointMessage.INVALID_PRAC_ID}), 400
        )

    if prac_to_replace.is_cx:
        log.warn(
            PracReplacementEndpointMessage.PRAC_IS_CARE_ADVOCATE,
            practitioner_id=practitioner_id,
        )
        return make_response(
            jsonify({"error": PracReplacementEndpointMessage.PRAC_IS_CARE_ADVOCATE}),
            400,
        )

    if is_an_active_available_practitioner(prac_id=prac_to_replace.user_id):
        log.warn(
            PracReplacementEndpointMessage.PRAC_TO_REPLACE_IN_NEW_PRACS,
            prac_to_replace_id=prac_to_replace.user_id,
        )
        return make_response(
            jsonify(
                {"error": PracReplacementEndpointMessage.PRAC_TO_REPLACE_IN_NEW_PRACS}
            ),
            400,
        )

    """
    Get remove_only_quiz_type from body of request, and validate its a boolean
    remove_only_quiz_type: True if we only want to replace the practitioner when they are type QUIZ
                           False if we want to replace practitioner regardless of type
    """
    remove_only_quiz_type = request.form.get("remove_only_quiz_type")
    schema = PractitionerReplacementSchema()
    quiz_type_schema = schema.load(
        {"remove_only_quiz_type": remove_only_quiz_type}
    ).data
    remove_only_quiz_type = quiz_type_schema.get("remove_only_quiz_type")

    # Check if another job is already working with this practitioner
    # If lock is available, grab it. If not, report to user that job in progress.
    redis = redis_client()
    lock_name = f"{practitioner_id}_replace_practitioner_in_progress"
    lock = Lock(
        redis=redis,
        name=lock_name,
        timeout=REPLACE_PRAC_JOB_TIMEOUT,
    )
    if lock.locked():
        log.warn(
            PracReplacementEndpointMessage.ANOTHER_JOB_RUNNING_FOR_SAME_PRAC,
            practitioner_id=practitioner_id,
        )
        return make_response(
            jsonify(
                {
                    "error": PracReplacementEndpointMessage.ANOTHER_JOB_RUNNING_FOR_SAME_PRAC
                }
            ),
            500,
        )
    lock.acquire(blocking=False, token=str(practitioner_id))
    log.info(
        "Got lock for replace practitioner process", practitioner_id=practitioner_id
    )

    if not has_member_practitioner_association(practitioner_id, remove_only_quiz_type):
        if lock.locked():
            lock.do_release(expected_token=str(practitioner_id))
            log.info("Lock released", lock_token=str(practitioner_id))
        else:
            log.error(
                "Trying to release a lock that is not locked",
                lock_token=str(practitioner_id),
                practitioner_id=practitioner_id,
            )

        if remove_only_quiz_type:
            return make_response(
                jsonify(
                    {
                        "error": PracReplacementEndpointMessage.PRAC_NOT_PRESENT_IN_ANY_CARE_TEAM_AS_QUIZ
                    }
                ),
                400,
            )
        else:
            return make_response(
                jsonify(
                    {
                        "error": PracReplacementEndpointMessage.PRAC_NOT_PRESENT_IN_ANY_CARE_TEAM
                    }
                ),
                400,
            )

    log.info(
        "Kicking off job to replace practitioner.",
        prac_to_replace=prac_to_replace.user_id,
        remove_only_quiz_type=remove_only_quiz_type,
    )

    job_ids = spin_off_replace_practitioner_in_care_teams_jobs(
        prac_to_replace_id=prac_to_replace.user_id,
        remove_only_quiz_type=remove_only_quiz_type,
        to_email=login.current_user.email,
    )
    if job_ids:
        response = make_response(
            jsonify({"message": "Success", "job_ids": job_ids}),
            200,
        )
        return response
    else:
        if lock.locked():
            lock.do_release(expected_token=str(practitioner_id))
            log.info("Lock released", lock_token=str(practitioner_id))
        else:
            log.error(
                "Trying to release a lock that is not locked",
                lock_token=str(practitioner_id),
                practitioner_id=practitioner_id,
            )

        return make_response(
            jsonify(
                {
                    "error": "Error during call to spin off replace practitioner in care teams jobs"
                }
            ),
            400,
        )


@actions.route("/list_all_practitioners/", methods=["GET"])
@login.login_required
def list_practitioners():  # type: ignore[no-untyped-def] # Function is missing a return type annotation
    practitioners = db.session.query(PractitionerProfile).all()

    practitioners = [
        {
            "name": p.user.full_name if p.user else "",
            "id": p.user_id,
        }
        for p in practitioners
    ]

    return {"practitioners": practitioners}


@actions.route("/process_bms_orders/", methods=(["POST"]))
@login.login_required
def process_downloaded_bms_orders():  # type: ignore[no-untyped-def] # Function is missing a return type annotation
    process_bms_orders.delay()
    flash("Processing BMS orders triggered.", category="success")
    return redirect("/admin/bmsorder")


@actions.route("/register_user", methods=(["POST"]))
@login.login_required
def register_user():  # type: ignore[no-untyped-def] # Function is missing a return type annotation
    first_name = request.form.get("first_name")
    last_name = request.form.get("last_name")
    email = request.form.get("email")
    language = request.form.get("language")

    users = UserRepository()
    existing_user = users.get_by_email(email=email)
    if existing_user:
        flash("User with this email already exists", category="error")
        return redirect("/admin/enterprise_setup")

    try:
        log.info(
            "Registering new user",
            created_by=login.current_user.id,
        )
        user = User(
            first_name=first_name,
            last_name=last_name,
            email=email,
        )
        user.password = encode_password(random_password())
        db.session.add(user)

        with db.session.no_autoflush:
            # Imports moved here to avoid circular import in Data Admin
            from authn.resources import user as user_resources
            from health.domain import add_profile

            lang = Language.query.get(int(language))  # type: ignore[arg-type] # Argument 1 to "int" has incompatible type "Optional[Any]"; expected "Union[str, Buffer, SupportsInt, SupportsIndex, SupportsTrunc]"

            add_profile.add_profile_to_user(user, **vars(user))
            user_resources.post_user_create_steps(
                user, agreements_accepted=True, language=lang
            )
            try:
                user_resources.create_idp_user(user)
            except (RequestsError, ClientError, IdentityClientError) as err:
                log.error(f"Failed to create idp user: {err}")
                db.session.rollback()
                abort(400, "Invalid credentials")

        db.session.commit()
        flash(f"Successfully registered new user ({user})!", category="success")

    except Exception as e:
        db.session.rollback()
        log.exception("Unable to register new user", exception=e)
        flash(str(e), category="error")

    return redirect("/admin/enterprise_setup")


@actions.route("/reimbursement_cycle_member_credit_transactions/new", methods=["POST"])
@login.login_required
def add_reimbursement_cycle_credit_transaction():  # type: ignore[no-untyped-def] # Function is missing a return type annotation
    redirect_path = _get_referer_path()
    data = request.form

    # get form data
    amount = data["amount"] or None
    reimbursement_cycle_credits_id = data["reimbursement_cycle_credits_id"]
    reimbursement_request_id = data["reimbursement_request_id"] or None
    global_procedures_id = data["global_procedures_id"] or None
    notes = data["notes"] or None

    # Get amount or calculate it
    global_procedure = None
    if global_procedures_id and not amount:
        procedure_service_client = ProcedureService(internal=True)
        global_procedure = procedure_service_client.get_procedure_by_id(
            procedure_id=global_procedures_id
        )

    if amount:
        try:
            amount = int(amount)
        except (ValueError, TypeError):
            amount = None
    elif global_procedure:
        amount = global_procedure["credits"] * -1  # type: ignore[typeddict-item] # TypedDict "PartialProcedure" has no key "credits"

    # Fetch credit balance
    credits = ReimbursementCycleCredits.query.get(reimbursement_cycle_credits_id)

    if not (amount or reimbursement_cycle_credits_id or credits):
        flash(
            "Cannot create new transaction -- missing amount or invalid global_procedures_id"
        )
        return redirect(redirect_path)

    try:
        credits.edit_credit_balance(
            amount,
            reimbursement_request_id=reimbursement_request_id,
            global_procedures_id=global_procedures_id,
            notes=notes,
        )
    except ValueError as e:
        flash(
            "Invalid input, please check that IDs are valid if included, or amount is valid for the remaining balance: "
            f"{e}"
        )
    return redirect(redirect_path)


@actions.route("/get_affected_appointments", methods=["POST"])
@login.login_required
def get_affected_appointments():  # type: ignore[no-untyped-def] # Function is missing a return type annotation
    # get form data
    data = request.form
    start_datetime = data.get("start_datetime")
    end_datetime = data.get("end_datetime")
    start_datetime = datetime.datetime.strptime(start_datetime, "%Y-%m-%d %H:%M:%S")  # type: ignore[arg-type] # Argument 1 to "strptime" of "datetime" has incompatible type "Optional[Any]"; expected "str"
    end_datetime = datetime.datetime.strptime(end_datetime, "%Y-%m-%d %H:%M:%S")  # type: ignore[arg-type] # Argument 1 to "strptime" of "datetime" has incompatible type "Optional[Any]"; expected "str"

    # Get the start and end time and fetch appointment metadata
    appointment_data = []
    for a in (
        Appointment.query.filter(
            Appointment.scheduled_start >= start_datetime,
            Appointment.scheduled_start <= end_datetime,
        )
        .join(Schedule, Appointment.member_schedule_id == Schedule.id)
        .filter(
            or_(
                and_(
                    Appointment.cancelled_at >= start_datetime,
                    Appointment.cancelled_by_user_id == Schedule.user_id,
                ),
                Appointment.cancelled_at == None,
            )
        )
        .all()
    ):
        emit_audit_log_read(a)
        if a.ended_at and a.started_at:
            # to get the duration in minutes
            duration = round((a.ended_at - a.started_at).total_seconds() / 60)
            appointment_length_variance = round(duration / a.product.minutes * 100)
        else:
            duration = None
            appointment_length_variance = None
        appointment_data.append(
            [
                a.member_schedule.user_id,
                a.member.esp_id,
                a.scheduled_start,
                a.state if a.state else None,
                a.cancelled_at,
                a.started_at if a.started_at else None,
                a.ended_at if a.ended_at else None,
                duration,
                a.product.minutes,
                appointment_length_variance,
                a.id,
                a.practitioner.email,
                [
                    vertical.name
                    for vertical in a.practitioner.practitioner_profile.verticals
                ],
            ]
        )

    # Create a csv and download
    with open("affected_appointment_data.csv", "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(
            [
                "Member ID",
                "Member ESP ID",
                "Start time (UTC)",
                "Appointment Status",
                "Cancelled At",
                "Started At",
                "Ended At",
                "Actual Duration (minutes)",
                "Initial Appointment Length (minutes)",
                "Difference Actual vs Initial Appointment Length (%)",
                "Appointment ID",
                "Provider Email",
                "Provider Verticals",
            ]
        )
        writer.writerows(appointment_data)

    with open("affected_appointment_data.csv", "r") as f:
        content = f.read()
    return Response(content, mimetype="text/csv")
