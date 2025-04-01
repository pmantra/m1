import click
from flask.cli import with_appcontext

from authn.models.user import User
from storage.connection import db


@click.command()
@with_appcontext
@click.option(
    "--dry-run", "-D", is_flag=True, help="Run the script but do not save the result."
)
def main(dry_run: bool = True):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
    practioners_without_country = (
        db.session.query(User)
        .filter(User.country_code.is_(None), User.practitioner_profile.has())  # type: ignore[attr-defined] # "Callable[[User], Optional[str]]" has no attribute "is_"
        .all()
    )

    print("****************")
    print("Ids of practitioners without country: ")
    for prac in practioners_without_country:
        print(prac.id)
    print("****************")

    for practitioner in practioners_without_country:
        practitioner.country_code = "US"
        db.session.add(practitioner)

    if not dry_run:
        db.session.commit()


if __name__ == "__main__":
    main()
