"""
resolve_payment_auth_failure_appointments.py

Collects all appointments after 2020-8-26 with no appointment_post_generation
and prints a list of future appointments for CAs to resolve
and sets past appointments to Cancelled by Member

Usage:
  resolve_payment_auth_failure_appointments.py [--live]

Options:
  --live        Applies changes instead of just describing them.
  -h --help     Show this screen.

"""
from docopt import docopt

from app import create_app
from appointments.models.appointment import Appointment
from storage.connection import db
from utils.log import logger

log = logger(__name__)


def get_problem_appts():  # type: ignore[no-untyped-def] # Function is missing a return type annotation
    """
    Look for user-booked appts where appointment_post_creation did not run, so there's no video info
    """
    potential_problem_appt_ids = [
        a[0]
        for a in db.session.execute(
            "select id from appointment where video = '{}' and created_at >= '2020-08-26';"
        ).fetchall()
    ]
    problem_appointments = [
        a
        for a in Appointment.query.filter(
            Appointment.id.in_(potential_problem_appt_ids)
        ).all()
        if not a.admin_booked
    ]
    return problem_appointments


def resolve_problem_appts(problem_appointments, live_run=False):  # type: ignore[no-untyped-def] # Function is missing a type annotation
    """
    Sort and cancel appointments with payment auth errors based on appointment state.

    :param problem_appointments:
    :param live_run:
    :return:
    """
    for appt in problem_appointments:
        pending_appts = []
        scheduled_appts = []
        if appt.state == Appointment.states.payment_pending:
            pending_appts.append(appt)
        else:
            scheduled_appts.append(appt)

        for upcoming_appointment in scheduled_appts:
            log.info(
                f"Scheduled Problem Appointment: [{upcoming_appointment}] for User [{upcoming_appointment.member.id}]"
            )

        for appointment in pending_appts:
            log.debug(f"Payment Pending Problem appointment: {appointment}")

            user = appointment.member
            if not appointment.member.is_member:
                log.debug(
                    "Appointment member was not 'member' type user",
                    user=user,
                    appointment=appointment,
                )
                continue

            if live_run:
                log.debug(f"Cancelling problem appointment: {appointment}")

                appointment.cancel(
                    user_id=appointment.member.id,
                    cancelled_note="Cancelled as this appointment was created by a bug.",
                    admin_initiated=True,
                )

                db.session.add(appointment)
                db.session.commit()

                log.debug(f"Cancelled problem appointment: {appointment}")
            else:
                log.debug("No action taken during test run.")


if __name__ == "__main__":
    with create_app().app_context():
        appointments = get_problem_appts()
        resolve_problem_appts(appointments, live_run=(docopt(__doc__)["--live"]))
