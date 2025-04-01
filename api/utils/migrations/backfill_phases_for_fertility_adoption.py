from sqlalchemy import and_

from app import create_app
from models.programs import Module, Phase
from storage.connection import db
from utils.log import logger

log = logger(__name__)


def add_weekly_track_phases(track_name, week_start, week_end):  # type: ignore[no-untyped-def] # Function is missing a type annotation
    module_row: Module = (
        db.session.query(Module).filter(Module.name == track_name).first()
    )

    for i in range(week_start, week_end + 1):
        week_name = f"week-{i}"
        week_already_in_db = (
            db.session.query(Phase)
            .filter(and_(Phase.module_id == module_row.id, Phase.name == week_name))
            .first()
        )
        if not week_already_in_db:
            new_phase_row = Phase(
                module_id=module_row.id,
                module=module_row,
                name=week_name,
                frontend_name=f"Week {i}",
                onboarding_assessment_lifecycle_id=None,
                is_transitional=False,
                json={},
                is_entry=i == 1,  # only an entry if first week?
                auto_transition_module_id=None,
            )
            db.session.add(new_phase_row)
    log.info(
        f"Added (or validated) {week_start}-{week_end} week rows to Phase table for module/track {track_name}"
    )
    db.session.commit()


if __name__ == "__main__":
    with create_app().app_context():
        add_weekly_track_phases("fertility", 32, 52)
        add_weekly_track_phases("adoption", 1, 104)
