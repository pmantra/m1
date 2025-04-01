"""
Create a new vertical with the name "Birth planning" and assign it to
the providers with the ids provided in a comma-separated list.

Usage:
    add_pregnancy_options_track.py (--remove)

Options:
  --remove                       remove the rows (downgrade the data migration)
"""

from docopt import docopt

from app import create_app
from models.enterprise import organization_approved_modules
from models.programs import Module, Phase
from storage.connection import db


def add_pregnancy_options_track(remove=False):  # type: ignore[no-untyped-def] # Function is missing a type annotation
    if remove:
        downgrade()
    else:
        upgrade()


def upgrade():  # type: ignore[no-untyped-def] # Function is missing a return type annotation
    # Insert a hard-coded row into Module table
    module_row = Module(
        name="pregnancy_options",
        frontend_name="Pregnancy Options",
        allow_phase_browsing=False,
        days_in_transition=14,
        duration=365,
        json=None,
        is_maternity=True,
        partner_module_id=None,
        intro_message_text_copy_id=None,
        phase_logic="STATIC",
        program_length_logic="DURATION",
        onboarding_as_partner=False,
        onboarding_display_label=None,
        onboarding_display_order=None,
        restrict_booking_verticals=False,
    )
    db.session.add(module_row)
    db.session.commit()
    print(f"Newly created module_row id: {module_row.id}")
    # Insert 2 hard-coded rows into Phase table that has the same foreign key to module_row
    phase_row_one = Phase(
        module_id=module_row.id,
        module=module_row,
        name="pregnancy_options",
        frontend_name=None,
        onboarding_assessment_lifecycle_id=None,
        is_transitional=False,
        json={},
        is_entry=True,
        auto_transition_module_id=None,
    )
    phase_row_two = Phase(
        module_id=module_row.id,
        module=module_row,
        name="pregnancy_options transition",
        frontend_name=None,
        onboarding_assessment_lifecycle_id=None,
        is_transitional=True,
        json={},
        is_entry=False,
        auto_transition_module_id=None,
    )
    db.session.add(phase_row_one)
    db.session.add(phase_row_two)
    db.session.commit()


def downgrade():  # type: ignore[no-untyped-def] # Function is missing a return type annotation
    module_row = Module.query.filter_by(name="pregnancy_options").one_or_none()
    org_mods = db.session.query(organization_approved_modules).filter_by(
        module_id=module_row.id
    )
    # Delete the org_mods with this module id.
    for org_mod in org_mods:
        db.session.delete(org_mod)
    # Delete the 2 phase rows that foreign-key reference the module row first and then delete the module row finally.
    is_phase_row_two_deleted = Phase.query.filter_by(
        name="Pregnancy_options transition"
    ).delete()
    print(f"is_phase_row_two_deleted: {is_phase_row_two_deleted}")
    is_phase_row_one_deleted = Phase.query.filter_by(name="Pregnancy_options").delete()
    print(f"is_phase_row_one_deleted: {is_phase_row_one_deleted}")
    is_module_row_deleted = Module.query.filter_by(name="pregnancy_options").delete()
    print(f"is_module_row_deleted: {is_module_row_deleted}")
    db.session.commit()


if __name__ == "__main__":
    args = docopt(__doc__)
    with create_app().app_context():
        add_pregnancy_options_track(remove=args["--remove"])
