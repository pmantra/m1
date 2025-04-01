from appointments.repository.v2.member_appointments import (
    MemberAppointmentsListRepository,
)
from appointments.tasks.appointments import (
    appointment_completion,
    reserve_credits_if_unreserved,
)
from storage.connection import db
from tasks.queues import job
from utils.log import logger

log = logger(__name__)


@job
def resolve_appointment_pending_payments(num_days: int = 14) -> None:
    repo = MemberAppointmentsListRepository(db.session)
    appt_ids = repo.get_payment_pending_appointment_ids(num_days=num_days)
    if appt_ids:
        log.warning(
            "Appointments found in PAYMENT_PENDING state", appointment_ids=appt_ids
        )
        for appt_id in appt_ids:
            log.warning(
                "Completing appointment with nightly job", appointment_id=appt_id
            )
            reserve_credits_if_unreserved(appt_id)
            appointment_completion(appt_id)

    unresolved_appt_ids = repo.get_payment_pending_appointment_ids(num_days=num_days)
    if unresolved_appt_ids:
        log.warning(
            "Appointments still unresolved in PAYMENT_PENDING state after nightly job."
            " Appts with zero-cost products will be unresolved because no credits were assigned.",
            appointment_ids=unresolved_appt_ids,
        )
    else:
        log.info(
            "Successfully migrated all appointments to PAYMENT_RESOLVED",
            appointment_ids=appt_ids,
        )
