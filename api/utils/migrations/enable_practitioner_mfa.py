import click

from authn.models.user import MFAState, User
from models.profiles import PractitionerProfile
from storage.connection import db
from utils.data import normalize_phone_number
from utils.log import logger

log = logger(__name__)


def batch_enable_practitioner_mfa(batch_size: int = 100):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
    for practitioner_batch in create_batch(limit=batch_size):
        log.info("Processing new batch")
        db.session.bulk_save_objects(practitioner_batch)


def create_batch(limit: int = 100):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
    query = PractitionerProfile.query.join(User).filter(
        (
            (PractitionerProfile.phone_number != None)
            & (PractitionerProfile.phone_number != "")
        )
        | ((User.sms_phone_number != None) & (User.sms_phone_number != "")),
        PractitionerProfile.active == True,
        User.mfa_state != MFAState.ENABLED,
    )

    log.info("Building batch of providers to enable MFA")
    batch_num = 0
    practitioner_batch = query.limit(limit).all()
    to_add = []

    while practitioner_batch:
        last_row = practitioner_batch[-1].user_id
        batch_num += 1

        for prac in practitioner_batch:
            to_add.append(set_tel_number_to_sms_phone_number_and_enable_mfa(prac))

        if len(to_add) >= limit:
            yield to_add
            to_add = []

        # Pull in the next batch
        practitioner_batch = (
            query.filter(PractitionerProfile.user_id > last_row).limit(limit).all()
        )

    if to_add:
        yield to_add


def set_tel_number_to_sms_phone_number_and_enable_mfa(prac):  # type: ignore[no-untyped-def] # Function is missing a type annotation
    # Do not overwrite an existing sms_phone_number
    number_to_normalize = prac.user.sms_phone_number
    if prac.user.sms_phone_number is None:
        number_to_normalize = prac.phone_number
    try:
        phone_number, _ = normalize_phone_number(number_to_normalize, None)
        prac.user.sms_phone_number = phone_number
    except Exception as e:
        # If the phone number cannot be normalized, store it as is
        prac.user.sms_phone_number = number_to_normalize
        log.exception(
            f"Storing non-normalized phone number for practitioner {str(prac.user_id)}",
            exception=e,
        )
    # Enable MFA
    prac.user.mfa_state = MFAState.ENABLED
    log.info("Enabling MFA for practitioner %s", prac.user_id)
    # If the phone number can't be validated, log an exception and move on
    return prac


@click.command()
@click.option(
    "--dry_run",
    "-d",
    is_flag=True,
    help="Run the script but do not save the result in the database.",
)
@click.option(
    "--batch_size",
    "-b",
    default=1_000,
    help="The number of PractitionerProfile to pull into memory at a time.",
)
def backfill(dry_run: bool = False, batch_size: int = 100):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
    log.info("Running enable MFA for all practitioners backfill.", dry_run=dry_run)
    from app import create_app

    with create_app(task_instance=True).app_context():
        try:
            batch_enable_practitioner_mfa(batch_size=batch_size)
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
