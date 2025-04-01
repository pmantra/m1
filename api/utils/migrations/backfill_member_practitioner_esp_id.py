"""
backfill_member_practitioner_esp_id.py

Backfills esp_id from user on their member or practitioner profile esp_id

Usage:
    backfill_member_practitioner_esp_id.py [--force]

Options:
  --force                       Actually commit the changes
"""
import click

from authn.models.user import User
from storage.connection import db
from utils.log import logger

log = logger(__name__)


def update_esp_id(force=False):  # type: ignore[no-untyped-def] # Function is missing a type annotation
    # determine if user is a member or practitioner and backfills esp_id on the appropriate profile
    log.info("Backfilling esp_id on member and practitioner profile")

    users = db.session.query(User).filter(User.esp_id.isnot(None))

    log.info(f"{users.count()} users with esp_id")

    member_result = db.session.execute(
        """
        UPDATE member_profile
        JOIN user ON user.id=member_profile.user_id
        SET member_profile.esp_id=user.esp_id
        WHERE user.esp_id IS NOT NULL;
        """
    )

    log.debug(
        f"""
        Backfilling {member_result.rowcount} rows in member_profile with esp_id
        from user.esp_id when it exists
        """
    )

    practitioner_result = db.session.execute(
        """
        UPDATE practitioner_profile
        JOIN user ON user.id=practitioner_profile.user_id
        SET practitioner_profile.esp_id=user.esp_id
        WHERE user.esp_id IS NOT NULL;
        """
    )

    log.debug(
        f"""
        Backfilling {practitioner_result.rowcount} rows in practitioner_profile with esp_id
        from user.esp_id when it exists
        """
    )


@click.option(
    "--dry-run",
    "-D",
    is_flag=True,
    help="Run the script but do not save the result in the database.",
)
def backfill(dry_run: bool = False):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
    from app import create_app

    with create_app(task_instance=True).app_context():
        try:
            update_esp_id()
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
