import datetime
from collections import defaultdict

from appointments.models.appointment import Appointment
from appointments.models.payments import FeeAccountingEntry, FeeAccountingEntryTypes
from models.profiles import PractitionerProfile
from storage.connection import db
from utils.log import logger

log = logger(__name__)


def set_opt_out_for_all():  # type: ignore[no-untyped-def] # Function is missing a return type annotation
    pracs = db.session.query(PractitionerProfile).all()

    for profile in pracs:
        log.debug("Setting optout for %s", profile.user)

        profile.malpractice_opt_out = True
        db.session.add(profile)

        log.debug("All set w/ %s", profile)

    db.session.commit()
    log.debug("All set!")


def migrate_sept_malpractice():  # type: ignore[no-untyped-def] # Function is missing a return type annotation
    now = datetime.datetime.utcnow()
    start_of_month = datetime.datetime(year=now.year, month=now.month, day=1)
    sept_appts = (
        db.session.query(Appointment)
        .filter(
            Appointment.cancelled_at == None,
            Appointment.scheduled_start >= start_of_month,
            Appointment.scheduled_start < now,
        )
        .all()
    )

    by_prac = defaultdict(list)
    for appt in sept_appts:
        by_prac[appt.product.practitioner.id].append(appt)

    for (
        prac_id,  # noqa  B007  TODO:  Loop control variable 'prac_id' not used within the loop body. If this is intended, start the name with an underscore.
        appt_list,
    ) in by_prac.items():
        first_appt = sorted(appt_list, key=lambda x: x.scheduled_start)[0]

        profile = first_appt.practitioner.practitioner_profile
        if profile.malpractice_opt_out:
            log.debug(
                "Not charging %s for malpractice (optout)", first_appt.practitioner
            )
            continue

        log.debug("Adding malpractice for %s", first_appt)
        fee = FeeAccountingEntry(
            amount=-10,
            practitioner=first_appt.practitioner,
            type=FeeAccountingEntryTypes.MALPRACTICE,
        )
        db.session.add(fee)
        log.debug("Added %s for %s", fee, first_appt)

    db.session.commit()
    log.info("All set!")
