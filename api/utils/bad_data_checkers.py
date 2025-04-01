import datetime

from sqlalchemy import func

from appointments.models.appointment import Appointment
from appointments.models.payments import FeeAccountingEntry, PaymentAccountingEntry
from appointments.models.schedule import Schedule
from authn.models.user import User
from authz.models.roles import ROLES, Role
from common.stats import PodNames, increment
from messaging.models.messaging import Message
from models.products import Product
from models.profiles import MemberProfile, PractitionerProfile, RoleProfile
from storage.connection import db
from tasks.queues import job
from utils.log import logger
from utils.mail import alert_admin

log = logger(__name__)

member_care_pod_email = "pod-member-care@mavenclinic.com"
core_services_pod_email = "core-services@mavenclinic.com"
backend_email = "backend@mavenclinic.com"


@job
def half_hourly():  # type: ignore[no-untyped-def] # Function is missing a return type annotation
    from app import create_app

    app = create_app()

    with app.app_context():
        find_appointments_that_should_be_over()
        find_appointments_with_captured_payments_no_fees()


@job
def hourly() -> None:
    # TODO: given that the tasks runned inside hourly are owned by different pods, it would be nice to break this into different cron jobs
    from app import create_app

    app = create_app()

    with app.app_context():
        find_cancelled_appointments_that_has_uncaptured_and_uncancelled_payments()
        find_appointments_that_has_ended_but_uncaptured_payments()
        find_appointments_that_has_more_than_one_practitioner_fee()
        find_appointments_missing_reminders()


@job
def daily() -> None:
    from app import create_app

    app = create_app()

    with app.app_context():
        find_appointments_with_no_event()
        find_appointments_with_missing_start_or_end_data()
        find_members_with_no_stripe_id()
        find_practitioners_without_products()
        find_practitioners_with_duplicate_products()
        find_users_with_no_profiles()
        find_users_with_no_schedule()
        find_users_with_staff_profile_without_staff_email()


def find_appointments_with_no_event():  # type: ignore[no-untyped-def] # Function is missing a return type annotation
    now = datetime.datetime.utcnow()

    bad = (
        db.session.query(Appointment)
        .filter(
            Appointment.scheduled_end >= now,
            Appointment.schedule_event_id == None,
            Appointment.cancelled_at == None,
        )
        .all()
    )

    txt = ""
    for appt in bad:
        if not appt.json.get("admin_booked"):
            txt += f"{appt} has no event\n"

    if txt:
        subj = f"Uncancelled appointments with no events. {now}"
        increment(
            metric_name="api.utils.bad_data_checkers.find_appointments_with_no_event.uncancelled_appointment",
            pod_name=PodNames.TEST_POD,
            tags=[
                "error:true",
                "error_cause:uncancelled_appointment",
            ],
        )
        log.warning(
            f"{subj}\n{txt}",
        )


def find_practitioners_without_products():  # type: ignore[no-untyped-def] # Function is missing a return type annotation
    now = datetime.datetime.utcnow()
    product_info = (
        db.session.query(Product.user_id, func.count(Product.id).label("product_count"))
        .filter(Product.is_active == True)
        .group_by(Product.user_id)
        .subquery()
    )

    a = (
        db.session.query(PractitionerProfile.user_id, product_info.c.product_count)
        .outerjoin(
            product_info, (PractitionerProfile.user_id == product_info.c.user_id)
        )
        .order_by(product_info.c.product_count.asc())
        .all()
    )

    txt = ""
    for row in a:
        if (row[1] is None) or row[1] < 2:
            user = db.session.query(User).filter(User.id == row[0]).first()
            if not user:
                log.debug("No user in no products: %s", row)
                continue

            txt += (
                "Practitioner %s has too few products (%s)" % (user.email, row[1])
            ) + "\n"

    subj = f"Practitioners that should have products, but don't. {now}"
    if txt:
        alert_admin(txt, subject=subj, alert_emails=[member_care_pod_email])


def find_practitioners_with_duplicate_products():  # type: ignore[no-untyped-def] # Function is missing a return type annotation
    bad = (
        db.session.query(
            Product.user_id,
            func.count(Product.id),
            Product.vertical_id,
            Product.minutes,
        )
        .filter(Product.is_active == True)
        .group_by(Product.user_id, Product.vertical_id, Product.minutes)
        .having(func.count(Product.id) > 1)
        .all()
    )

    for row in bad:
        user_id = row[0]
        count = row[1]
        vertical_id = row[2]
        minutes = row[3]

        log.warning(
            "Practitioner has duplicate products with different pricing",
            user_id=user_id,
            count=count,
            vertical_id=vertical_id,
            minutes=minutes,
        )


def find_appointments_with_captured_payments_no_fees():  # type: ignore[no-untyped-def] # Function is missing a return type annotation
    now = datetime.datetime.utcnow()
    m30 = now - datetime.timedelta(minutes=30)

    # Get payments that occurred in last 30 minutes and were not cancelled
    pymts = (
        db.session.query(PaymentAccountingEntry)
        .filter(
            (
                (PaymentAccountingEntry.captured_at >= m30)
                & (PaymentAccountingEntry.captured_at <= now)
                & (PaymentAccountingEntry.cancelled_at == None)
            )
        )
        .all()
    )

    bad = []
    for pymt in pymts:
        if (
            not db.session.query(FeeAccountingEntry)
            .filter((FeeAccountingEntry.appointment_id == pymt.appointment_id))
            .first()
        ):
            # If Member already failed payment, no fee is expected
            member_profile = pymt.appointment.member.member_profile
            if member_profile and member_profile.json.get("payment_collection_failed"):
                continue

            if not pymt.appointment.requires_fee:
                continue

            bad.append(pymt)

    for p in bad:
        # Log monitored by https://app.datadoghq.com/monitors/114519814
        log.warning(
            "Appointment should have a fee associated.", appointment_id=p.appointment.id
        )


def find_appointments_that_should_be_over():  # type: ignore[no-untyped-def] # Function is missing a return type annotation
    now = datetime.datetime.utcnow()
    m30 = now - datetime.timedelta(minutes=30)
    overflow_appts = (
        db.session.query(Appointment)
        .filter(
            (Appointment.cancelled_at == None)
            & ((Appointment.scheduled_end >= m30) & (Appointment.scheduled_end <= now))
            & (
                (Appointment.practitioner_ended_at == None)
                | (Appointment.member_ended_at == None)
            )
            & (
                (Appointment.practitioner_started_at == None)
                | (Appointment.member_started_at == None)
            )
        )
        .all()
    )

    text_builder = []
    for a in overflow_appts:
        if a.member.is_enterprise:
            text_builder.append(" (Enterprise)")
        text_builder.append(f"{a} should have ended!\n")
        increment(
            metric_name="api.utils.bad_data_checkers.appointment_that_should_be_over",
            pod_name=PodNames.MPRACTICE_CORE,
        )

    text = "".join(text_builder)
    if text:
        subj = f"Appointments that should have ended @ {now}"
        log.warning(f"{subj}\n{text}")


def find_appointments_with_missing_start_or_end_data():  # type: ignore[no-untyped-def] # Function is missing a return type annotation
    now = datetime.datetime.utcnow()
    h24 = now - datetime.timedelta(hours=24)
    missing_practitioner_end_appts = (
        db.session.query(Appointment)
        .filter(
            ((Appointment.scheduled_end >= h24) & (Appointment.scheduled_end <= now))
            & (Appointment.cancelled_at == None)
            & (Appointment.practitioner_started_at != None)
            & (Appointment.practitioner_ended_at == None)
        )
        .all()
    )

    missing_member_end_appts = (
        db.session.query(Appointment)
        .filter(
            ((Appointment.scheduled_end >= h24) & (Appointment.scheduled_end <= now))
            & (Appointment.cancelled_at == None)
            & (Appointment.member_started_at != None)
            & (Appointment.member_ended_at == None)
        )
        .all()
    )

    missing_practitioner_start_appts = (
        db.session.query(Appointment)
        .filter(
            ((Appointment.scheduled_end >= h24) & (Appointment.scheduled_end <= now))
            & (Appointment.cancelled_at == None)
            & (Appointment.practitioner_started_at == None)
            & (Appointment.practitioner_ended_at != None)
        )
        .all()
    )

    missing_member_start_appts = (
        db.session.query(Appointment)
        .filter(
            ((Appointment.scheduled_end >= h24) & (Appointment.scheduled_end <= now))
            & (Appointment.cancelled_at == None)
            & (Appointment.member_started_at == None)
            & (Appointment.member_ended_at != None)
        )
        .all()
    )

    text_builder = []
    for appointment in (
        missing_practitioner_end_appts
        + missing_member_end_appts
        + missing_practitioner_start_appts
        + missing_member_start_appts
    ):
        if appointment.member.is_enterprise:
            text_builder.append(" (Enterprise)")
        text_builder.append(f"{appointment} should have ended!\n")
        increment(
            metric_name="api.utils.bad_data_checkers.appointment_with_missing_start_or_end_data",
            pod_name=PodNames.MPRACTICE_CORE,
        )

    subj = f"Appointments missing start or end data @ {now}"
    if text_builder:
        log.warning(f"{subj}\n{''.join(text_builder)}")


def find_cancelled_appointments_that_has_uncaptured_and_uncancelled_payments() -> None:
    appts = (
        db.session.query(Appointment, PaymentAccountingEntry)
        .filter(
            (Appointment.id == PaymentAccountingEntry.appointment_id)
            & (Appointment.cancelled_at.isnot(None))
            & (PaymentAccountingEntry.captured_at.is_(None))
            & (PaymentAccountingEntry.cancelled_at.is_(None))
        )
        .all()
    )

    for a in appts:
        log.warning(
            "Cancelled appointment has uncaptured or uncancelled payment",
            appointment_id=a.id,
        )


def find_appointments_that_has_ended_but_uncaptured_payments():  # type: ignore[no-untyped-def] # Function is missing a return type annotation
    now = datetime.datetime.utcnow()
    appts = (
        db.session.query(Appointment, PaymentAccountingEntry)
        .filter(
            (Appointment.id == PaymentAccountingEntry.appointment_id)
            & (
                (Appointment.member_ended_at < now)
                & (Appointment.practitioner_ended_at < now)
            )
            & (PaymentAccountingEntry.captured_at.is_(None))
            & (PaymentAccountingEntry.cancelled_at.is_(None))
        )
        .all()
    )

    for a in appts:
        log.warning(
            "Ended appointment has uncaptured payment",
            appointment_id=a.id,
        )


def find_appointments_that_has_more_than_one_practitioner_fee():  # type: ignore[no-untyped-def] # Function is missing a return type annotation
    now = datetime.datetime.utcnow()
    one_hour_ago = now - datetime.timedelta(hours=1)
    appt_and_fee_counts = (
        db.session.query(
            Appointment, func.count(FeeAccountingEntry.id).label("fee_count")
        )
        .outerjoin(FeeAccountingEntry)
        .filter(
            Appointment.member_ended_at < now,
            Appointment.practitioner_ended_at < now,
            Appointment.created_at > one_hour_ago,
        )
        .group_by(FeeAccountingEntry.id)
        .having(func.count(FeeAccountingEntry.id) > 1)
        .all()
    )

    for row in appt_and_fee_counts:
        log.warning(
            "Appointment has fees for more than one provider",
            appointment_id=row.Appointment,
            fee_count=row.fee_count,
        )


def find_users_with_no_profiles():  # type: ignore[no-untyped-def] # Function is missing a return type annotation
    now = datetime.datetime.utcnow()
    users = (
        db.session.query(User)
        .outerjoin(MemberProfile)
        .filter(MemberProfile.user_id.is_(None))
        .all()
    )

    txt = ""
    for user in users:
        txt += ("%s has no member profile" % user) + "\n"

    subj = "Users who have no member profiles %s" % now
    if txt:
        alert_admin(txt, subject=subj, alert_emails=[core_services_pod_email])


def find_users_with_staff_profile_without_staff_email():  # type: ignore[no-untyped-def] # Function is missing a return type annotation
    now = datetime.datetime.utcnow()
    users = (
        db.session.query(User)
        .join(RoleProfile)
        .outerjoin(Role)
        .filter((Role.name == ROLES.staff) & ~(User.email.like("%@mavenclinic.com")))
        .all()
    )

    txt = ""
    for user in users:
        txt += (
            "%s has staff access but without mavenclinic.com email address" % user
        ) + "\n"

    subj = f"Staff users without staff email addresses {now}"
    if txt:
        alert_admin(txt, subject=subj, alert_emails=[core_services_pod_email])


def find_members_with_no_stripe_id():  # type: ignore[no-untyped-def] # Function is missing a return type annotation
    now = datetime.datetime.utcnow()
    thirty_mins_ago = now - datetime.timedelta(minutes=30)

    bad = (
        db.session.query(MemberProfile)
        .join(User)
        .filter(
            MemberProfile.stripe_customer_id.is_(None),
            User.created_at < thirty_mins_ago,
        )
        .all()
    )

    txt = ""
    for profile in bad:
        txt += f"Member ID {profile.user_id} has no stripe ID!\n"

    if txt:
        txt += (
            "\n\n -- most likely the post-creation task for the users "
            "should be re-run..."
        )

    subj = "Members without stripe customer IDs."
    if txt:
        alert_admin(
            txt,
            subject=subj,
            alert_emails=[core_services_pod_email],
            production_only=True,
        )


def find_users_with_no_schedule():  # type: ignore[no-untyped-def] # Function is missing a return type annotation
    now = datetime.datetime.utcnow()

    bad = (
        db.session.query(User)
        .outerjoin(Schedule)
        .filter(Schedule.user_id == None)
        .all()
    )

    txt = ""
    for user in bad:
        if user.email == "zach+adminacct@mavenclinic.com":
            continue

        txt += f"{user} has no schedule!\n"

    if txt:
        txt += (
            "\n\n -- most likely the post-creation task for the user "
            "should be re-run..."
        )

    subj = f"Users without schedules @ {now}"
    if txt:
        alert_admin(
            txt,
            subject=subj,
            alert_emails=[core_services_pod_email],
            production_only=True,
        )


def find_messages_with_no_fee():  # type: ignore[no-untyped-def] # Function is missing a return type annotation
    now = datetime.datetime.utcnow()
    bad = (
        db.session.query(Message)
        .outerjoin(FeeAccountingEntry)
        .filter(
            FeeAccountingEntry.message_id.is_(None),
            Message.created_at < now - datetime.timedelta(hours=12),
        )
        .all()
    )

    for purchase in bad:
        log.warning(
            "Message Billing without fees",
            purchase=purchase,
        )


def find_invalid_fees():  # type: ignore[no-untyped-def] # Function is missing a return type annotation
    fees_without_a_product = (
        db.session.query(FeeAccountingEntry)
        .filter(
            FeeAccountingEntry.appointment_id.is_(None),
            FeeAccountingEntry.message_id.is_(None),
        )
        .all()
    )

    for fee in fees_without_a_product:
        log.warning(
            "FeeAccountingEntry with no appointment id or message id",
            fee=fee.id,
        )

        increment(
            metric_name="api.utils.bad_data_checkers.invalid_fees",
            pod_name=PodNames.PAYMENTS_POD,
            tags=["error:true", "status:invalid_feeds"],
        )

    fees_with_two_products = db.session.query(FeeAccountingEntry).filter(
        FeeAccountingEntry.appointment_id.isnot(None),
        FeeAccountingEntry.message_id.isnot(None),
    )

    for fee in fees_with_two_products:
        log.warning(
            "FeeAccountingEntry with two products",
            fee=fee.id,
        )

        increment(
            metric_name="api.utils.bad_data_checkers.invalid_fees",
            pod_name=PodNames.PAYMENTS_POD,
            tags=["error:true", "status:invalid_feeds"],
        )


def find_appointments_missing_reminders():  # type: ignore[no-untyped-def] # Function is missing a return type annotation
    now = datetime.datetime.utcnow()
    appointments = (
        db.session.query(Appointment)
        .filter(
            Appointment.scheduled_start < now + datetime.timedelta(hours=2),
            Appointment.created_at < now - datetime.timedelta(hours=13),
            Appointment.cancelled_at.is_(None),
            Appointment.reminder_sent_at.is_(None),
        )
        .all()
    )

    if not appointments:
        return

    subject = "Appointments missing reminders"
    txt = f"Appointment ids: {','.join(str(a.id) for a in appointments)}"

    alert_admin(txt, subject=subject, alert_emails=[member_care_pod_email])
