from dateutil.relativedelta import relativedelta

from models.profiles import PractitionerProfile
from storage.connection import db


def populate_experience_started():  # type: ignore[no-untyped-def] # Function is missing a return type annotation
    print("Fetching practitioner profiles...")
    profiles = (
        db.session.query(PractitionerProfile)
        .filter(PractitionerProfile.experience_started.is_(None))
        .all()
    )
    for profile in profiles:
        _set_experience_started(profile, _fetch_experience(profile.user_id))


def _set_experience_started(profile, years_experience):  # type: ignore[no-untyped-def] # Function is missing a type annotation
    if not years_experience:
        print(
            "Years experience not set for user id {}, skipping.".format(profile.user_id)
        )
        return
    print(
        "Found {} years of experience for user id: {}".format(
            years_experience, profile.user_id
        )
    )
    experience_started = profile.created_at - relativedelta(years=years_experience)
    print("Setting experience started to {}".format(experience_started))
    profile.experience_started = experience_started
    db.session.commit()


def _fetch_experience(user_id):  # type: ignore[no-untyped-def] # Function is missing a type annotation
    return db.session.execute(
        "SELECT years_experience FROM practitioner_profile " "WHERE user_id = :id",
        {"id": user_id},
    ).scalar()
