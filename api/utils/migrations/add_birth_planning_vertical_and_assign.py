"""
add_birth_planning_vertical_and_assign.py

Create a new vertical with the name "Birth planning" and assign it to
the providers with the ids provided in a comma-separated list.

Usage:
    add_birth_planning_vertical_and_assign.py [--force] (--user_ids=<user_ids>)

Options:
  --user_ids=<user_ids>         Provide a comma-separated list of practitioner ids
  --force                       Actually commit the changes
"""
from docopt import docopt

from app import create_app
from authn.models.user import User
from models.verticals_and_specialties import BIRTH_PLANNING_VERTICAL_NAME, Vertical
from storage.connection import db


def add_birth_planning_vertical_and_assign(force=False, user_id_str=""):  # type: ignore[no-untyped-def] # Function is missing a type annotation
    user_ids = [int(id_str.strip()) for id_str in user_id_str.split(",")]
    users = User.query.filter(User.id.in_(user_ids)).all()

    bp_vert = Vertical.query.filter_by(name=BIRTH_PLANNING_VERTICAL_NAME).one_or_none()
    if not bp_vert:
        print("****************")
        print("Adding birth planning vertical!")
        print("****************")
        bp_vert = Vertical(
            name=BIRTH_PLANNING_VERTICAL_NAME,
            display_name="Birth Planning Specialist",
            pluralized_display_name="Birth Planning Specialists",
            products=[{"minutes": 75, "price": 122, "purpose": "birth_planning"}],
        )
        if force:
            db.session.add(bp_vert)
            db.session.commit()
        else:
            bp_vert.id = 9999

    print("****************")
    print("Assigning birth planning vertical to providers!")
    print("****************")
    for user in users:
        user.practitioner_profile.verticals.append(bp_vert)
        db.session.add(user)
    if force:
        db.session.commit()
    else:
        print("****************")
        print("...But not committing.")
        print("****************")
        db.session.rollback()


if __name__ == "__main__":
    args = docopt(__doc__)
    with create_app().app_context():
        add_birth_planning_vertical_and_assign(
            force=args["--force"], user_id_str=args["--user_ids"]
        )
