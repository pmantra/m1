"""
Create the menopause track in the Module table.

Usage:
    add_menopause_track.py (--remove)

Options:
 --remove           remove the row (downgrade the data migration)
"""


from docopt import docopt

from app import create_app
from models.enterprise import organization_approved_modules
from models.programs import Module, Phase
from storage.connection import db


def add_menopause_track(remove=False):  # type: ignore[no-untyped-def] # Function is missing a type annotation
    if remove:
        downgrade_phase_table()
        downgrade_module_table()
    else:
        upgrade_module_table()
        upgrade_phase_table()


def upgrade_module_table():  # type: ignore[no-untyped-def] # Function is missing a return type annotation
    module_row = Module(
        name="menopause",
        frontend_name="Menopause",
        allow_phase_browsing=False,
        days_in_transition=14,
        duration=365,
        json=None,
        is_maternity=False,
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


def downgrade_module_table():  # type: ignore[no-untyped-def] # Function is missing a return type annotation
    module_row = Module.query.filter_by(name="menopause").first()
    org_mods = db.session.query(organization_approved_modules).filter_by(
        module_id=module_row.id
    )
    for org_mod in org_mods:
        db.session.delete(org_mod)
    print(f"Deleted {org_mods.count()} organization modules for menopause track")
    is_module_row_deleted = Module.query.filter_by(name="menopause").delete()
    print(f"is_module_row_deleted: {is_module_row_deleted}")
    db.session.commit()


def upgrade_phase_table():  # type: ignore[no-untyped-def] # Function is missing a return type annotation
    module_row = Module.query.filter_by(name="menopause").first()
    phase_row_one = Phase(
        module_id=module_row.id,
        module=module_row,
        name="menopause",
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
        name="menopause transition",
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


def downgrade_phase_table():  # type: ignore[no-untyped-def] # Function is missing a return type annotation
    module_row = Module.query.filter_by(name="menopause").first()
    phases = Phase.query.filter_by(module_id=module_row.id)
    for phase in phases:
        db.session.delete(phase)
    print(f"Deleted {phases.count()} phases for menopause track")


if __name__ == "__main__":
    args = docopt(__doc__)
    with create_app().app_context():
        add_menopause_track(remove=args["--remove"])
