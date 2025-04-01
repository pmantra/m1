#!/usr/bin/env python3
"""
migrate_unlimited_programs.py

Set scheduled end on active, unlimited programs in duration logic modules.

Usage:
  migrate_unlimited_programs.py [--force]

Options:
  --force       Perform the migration, rather than doing a dry run.
  -h --help     Show this screen.
"""
from collections import defaultdict
from datetime import date, timedelta
from sys import path

from docopt import docopt

path.insert(0, "/api")
try:
    from app import create_app
    from models.programs import CareProgram, Module, ProgramLengthLogic
    from storage.connection import db
    from utils.log import logger
except ImportError:
    raise
log = logger(__name__)


# There is a set of users curated by the cx team that should, at present, keep their unlimited care programs.
USERS_TO_KEEP_UNLIMITED = (
    91526,
    147197,
    156806,
    158653,
    106382,
    116661,
    107613,
    126805,
)


def migrate(force):  # type: ignore[no-untyped-def] # Function is missing a type annotation

    today = date.today()
    mm = {m.name: m for m in Module.query}

    m_pp = defaultdict(list)
    query = CareProgram.query.filter(
        CareProgram.scheduled_end.is_(None),
        CareProgram.ended_at.is_(None),
        CareProgram.user_id.notin_(USERS_TO_KEEP_UNLIMITED),
    )
    for p in query:
        m = p.current_module
        if not m:
            continue
        if m.program_length_logic == ProgramLengthLogic.DURATION:
            m_pp[p.current_module.name].append(p)

    for name, pp in m_pp.items():
        m = mm[name]
        duration = m.duration
        days_in_transition = m.days_in_transition
        log.info(
            "Transitioning %d active programs in module %s from having no scheduled end "
            "to having a %d day duration and a %d day transition.",
            len(pp),
            name,
            duration,
            days_in_transition,
        )

        scheduled_length = timedelta(days=duration + days_in_transition)
        earliest_allowed_scheduled_end = today + timedelta(days=days_in_transition)
        for p in pp:
            program_start_date = p.module_started_at(m.name).date()
            hypothetical_scheduled_end = program_start_date + scheduled_length
            adjusted_scheduled_end = max(
                earliest_allowed_scheduled_end, hypothetical_scheduled_end
            )
            if force:
                p.scheduled_end = adjusted_scheduled_end
            log.info(
                "Program %s (started on %s) adjusted to %s.",
                p,
                program_start_date,
                adjusted_scheduled_end,
            )

    log.info("All done.")
    if force:
        db.session.commit()


if __name__ == "__main__":
    args = docopt(__doc__)
    with create_app().app_context():
        migrate(force=args["--force"])
