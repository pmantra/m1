import click

from models.tracks import MemberTrack
from storage.connection import db
from utils.log import logger

log = logger(__name__)


def backfill_in_batches(batch_size: int = 1_000):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
    for batch in create_batch(batch_size=batch_size):
        log.info("Setting `start_date` value")
        session = db.session().using_bind("default")
        session.execute(
            """
            UPDATE member_track
            SET start_date = DATE(created_at)
            WHERE id IN :ids AND start_date != DATE(created_at);
            """,
            params={"ids": batch},
        )


def create_batch(batch_size: int = 1_000):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
    log.info("Fetching MemberTracks...")

    query = db.session.query(MemberTrack.id).filter(
        MemberTrack.start_date != MemberTrack.created_at
    )

    log.info("Building batch MemberTrack data...")
    batch_num = 0
    batch = query.limit(batch_size).all()
    to_add = []

    while batch:
        last_id = batch[-1].id
        batch_num += 1

        to_add = [mt_id[0] for mt_id in batch]

        if len(to_add) >= batch_size:
            yield to_add
            to_add = []
        else:
            log.info("Still building batch...", batch=batch_num, size=len(batch))

        # Pull in the next batch
        batch = query.filter(MemberTrack.id > last_id).limit(batch_size).all()

    if to_add:
        yield to_add


def backfill(dry_run: bool = False, batch_size: int = 1_000):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
    log.info(
        "Running MemberTrack start_date backfill.",
        dry_run=dry_run,
    )
    from app import create_app

    with create_app(task_instance=True).app_context():
        try:
            with db.session.no_autoflush:
                backfill_in_batches(batch_size=batch_size)
        except Exception as e:
            db.session.rollback()
            log.exception("Got an exception while backfilling.", exception=e)
            return

        if dry_run:
            log.info("Dry run requested. Rolling back changes.")
            db.session.rollback()
            return

        log.info("Committing changes...")
        db.session.commit()
        log.info("Finished.")


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
    help="The number of MemberTracks to pull into memory at a time.",
)
def main(dry_run: bool = False, batch_size: int = 1_000):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
    backfill(dry_run=dry_run, batch_size=batch_size)


if __name__ == "__main__":
    main()
