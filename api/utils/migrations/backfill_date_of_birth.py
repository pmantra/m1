import datetime
from traceback import format_exc

import click

from health.models.health_profile import HealthProfile
from storage.connection import db
from utils.log import logger

log = logger(__name__)


def backfill_date_of_birth(is_dry_run: bool = True):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
    """
    There is a LOT of users. We'll batch them.
    There are 475,000 users in prod.
    We will have a future migration to remove the birthday from the
    HealthProfile.json field.
    """

    user_id_benchmarks = [(start, start + 1_000) for start in range(0, 500_000, 1_000)]
    count = 0
    for user_id_start, user_id_end in user_id_benchmarks:
        health_profiles = HealthProfile.query.filter(
            (HealthProfile.user_id >= user_id_start)
            & (HealthProfile.user_id < user_id_end),
            HealthProfile.date_of_birth == None,
        ).all()
        updates = []
        for health_profile in health_profiles:
            if health_profile.json and "birthday" in health_profile.json:
                birthday_str = health_profile.json["birthday"]
                try:
                    dob_as_date = datetime.datetime.strptime(
                        birthday_str, "%Y-%m-%d"
                    ).date()
                    health_profile.date_of_birth = dob_as_date
                    if not is_dry_run:
                        updates.append(health_profile)
                    count += 1
                except Exception:
                    print(f"user_id={health_profile.user_id}, {birthday_str=}")
                    print(format_exc())
        if not is_dry_run and updates:
            db.session.bulk_save_objects(updates)
            db.session.commit()
            print(
                f"Updated health_profiles for user_ids {user_id_start} to {user_id_end}"
            )
            print(f"Updated {len(updates)} profiles")
    print(f"Updated {count} health profiles.")


@click.option(
    "--dry-run",
    "-D",
    is_flag=True,
    help="Run the script but do not save the result in the database.",
)
def backfill(dry_run: bool = True):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
    from app import create_app

    with create_app(task_instance=True).app_context():
        try:
            backfill_date_of_birth(dry_run)
        except Exception as e:
            db.session.rollback()
            log.exception("Got an exception while backfilling.", exception=e)
            return

        if dry_run:
            log.info("Dry run requested. Rolling back changes.")
            db.session.rollback()
            return

        log.debug("Committing changes...")
        db.session.commit()
        log.debug("Finished.")


if __name__ == "__main__":
    backfill()
