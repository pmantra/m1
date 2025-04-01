from models.programs import Module, Phase
from storage.connection import db


def run(module_name, week_count, dry_run=True):  # type: ignore[no-untyped-def] # Function is missing a type annotation
    """
    Create N weekly phases that look like:
         name: "week-1", frontend_name: "Week 1"

    This script updates phases that already exists, so it can be run again on
    the same module. However, if you run it with a LOWER week_count than before,
    it will not delete phases that are outside that range.
    """
    module = db.session.query(Module).filter(Module.name == module_name).first()

    if not module:
        raise ValueError(f"Module not found: {module}")

    for i in range(0, week_count):
        phase_name = f"week-{i+1}"
        # Check if phase with this name already exists. If it does, update it instead
        # of creating a new one
        existing_phase = next(
            (phase for phase in module.phases if phase.name == phase_name), None
        )
        if existing_phase:
            phase = existing_phase
        else:
            phase = Phase(
                module=module, is_transitional=False, is_entry=False, name=phase_name
            )
        phase.frontend_name = f"Week {i+1}"
        db.session.add(phase)
        verb = "Updating" if existing_phase else "Creating"
        print(f"{verb} phase: name={phase.name}\tfrontend_name={phase.frontend_name}")

    if dry_run:
        print("Dry run, not saving.")
        db.session.rollback()
    else:
        print("Saving...")
        db.session.commit()
        print("Done.")
