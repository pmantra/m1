"""
Backfill the module and phase tables with the appropriate values to transition from 'STATIC' to 'WEEKLY' for menopause.

Usage:
    backfill_phases_for_menopause.py
"""

from docopt import docopt

from app import create_app
from models.programs import Module, Phase, PhaseLogic
from storage.connection import db
from utils.log import logger

log = logger(__name__)


def backfill_phases_for_menopause():  # type: ignore[no-untyped-def] # Function is missing a return type annotation

    module_row = Module.query.filter_by(name="menopause").first()
    if module_row.phase_logic == PhaseLogic.STATIC:
        module_row.phase_logic = PhaseLogic.WEEKLY
        log.info("Updated phase_logic value in Module table from 'STATIC' to 'WEEKLY'")

    phase_menopause_row = Phase.query.filter_by(name="menopause").first()
    if phase_menopause_row is not None:
        phase_menopause_row.name = "week-1"
        phase_menopause_row.frontend_name = "Week 1"

    phase_menopause_transition_row = Phase.query.filter_by(
        name="menopause transition"
    ).first()
    if phase_menopause_transition_row is not None:
        phase_menopause_transition_row.name = "menopause-end"

    if phase_menopause_row is not None:
        phase_menopause_and_week_rows = Phase.query.filter(
            (Phase.module_id == phase_menopause_row.module_id)
            & (Phase.name.like("week%"))
        ).all()
        if len(phase_menopause_and_week_rows) != 52:
            log.info(
                f"Creating weekly phases in Phase table since there is {len(phase_menopause_and_week_rows)} "
                f"row(s) for Menopause"
            )
            for i in range(2, 53):
                new_phase_row = Phase(
                    module_id=phase_menopause_row.id,
                    module=module_row,
                    name=f"week-{i}",
                    frontend_name=f"Week {i}",
                    onboarding_assessment_lifecycle_id=None,
                    is_transitional=False,
                    json={},
                    is_entry=True,
                    auto_transition_module_id=None,
                )
                db.session.add(new_phase_row)
            log.info("Added 51 rows to Phase table")
            db.session.commit()
    else:
        log.info("Backfill has already been run or the criteria has not been met.")
    log.info("Done running the backfill for Module and Phase tables")


if __name__ == "__main__":
    args = docopt(__doc__)
    with create_app().app_context():
        backfill_phases_for_menopause()
