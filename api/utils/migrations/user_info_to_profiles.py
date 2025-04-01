import click
from flask.cli import with_appcontext

from authn.models.user import User
from models.profiles import MemberProfile
from storage.connection import db


@click.command()
@with_appcontext
@click.option(
    "--limit",
    "-L",
    default=100,
    help="Number of records to process in each batch. Default is 100.",
)
@click.option(
    "--commit",
    "-C",
    is_flag=True,
    help="Run the script and save the result to the database.",
)
@click.option(
    "--unset",
    "-U",
    is_flag=True,
    help="Only update records where last_name on the MemberProfile is empty.",
)
def update_profiles(limit: int = 100, commit: bool = False, unset: bool = False):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
    """
    Set fields that were formally tracked on the user onto the profiles for that user

    Once Profiles become the source of truth for these fields, this migration should be deleted.
    """
    print(f"Getting users with flags\nlimit={limit}\ncommit={commit}\nunset={unset}")

    query = db.session.query(User)
    if unset:
        # Choosing MemberProfile here since all users have one
        query = query.join(MemberProfile).filter(MemberProfile.last_name.is_(None))

    users = query.limit(limit).all()

    print("****************")
    print(f"Number of users: {len(users)}")

    for user in users:
        mp = user.member_profile
        if mp:
            mp.first_name = user.first_name
            mp.last_name = user.last_name
            mp.middle_name = user.middle_name
            mp.zendesk_user_id = user.zendesk_user_id
            mp.esp_id = user.esp_id
            db.session.add(mp)
        pp = user.practitioner_profile
        if pp:
            pp.first_name = user.first_name
            pp.last_name = user.last_name
            pp.middle_name = user.middle_name
            pp.zendesk_user_id = user.zendesk_user_id
            pp.esp_id = user.esp_id
            db.session.add(pp)

    if commit:
        print("****************")
        print("Committing...")
        db.session.commit()

    print("****************")
    print("Complete!")


if __name__ == "__main__":
    update_profiles()
