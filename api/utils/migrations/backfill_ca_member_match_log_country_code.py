from __future__ import annotations

import dataclasses

import click

from geography import repository
from storage.connection import db
from utils.log import logger

log = logger(__name__)


def backfill_in_batches(batch: list[UpdateDataRow], batch_size: int = 1_000):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
    session = db.session().using_bind("default")

    inserts = [dataclasses.asdict(insert_) for insert_ in batch]

    batch_num = 0
    start_idx = 0
    num_inserts = len(inserts)
    for _ in range(start_idx, num_inserts, batch_size):
        batch_num += 1
        end_idx = min(start_idx + batch_size, num_inserts)
        batch_inserts = inserts[start_idx:end_idx]
        num_batch_inserts = len(batch_inserts)

        log.info(
            "Updating rows",
            batch_num=batch_num,
            num_rows=num_batch_inserts,
            start_idx=start_idx,
            end_idx=end_idx,
        )
        session.execute(
            """
            SET @@local.net_read_timeout=360;
            INSERT INTO `ca_member_match_log` (id, user_id, country_code)
            VALUES (:id, :user_id, :country_code)
            ON DUPLICATE KEY UPDATE
                `id`=VALUES(`id`),
                `user_id`=VALUES(`user_id`),
                `country_code`=VALUES(`country_code`)
            """,
            params=batch_inserts,
        )
        log.info(
            "Inserted rows",
            batch_num=batch_num,
            num_rows=num_batch_inserts,
            start_idx=start_idx,
            end_idx=end_idx,
        )

        start_idx = end_idx


def find_rows_to_udpate():  # type: ignore[no-untyped-def] # Function is missing a return type annotation
    log.info("Fetching CA Member Match Logs with missing country_code data...")

    query = """
    SELECT mml.id, mml.user_id, c.abbr, mml.country_code
    FROM ca_member_match_log mml
    LEFT JOIN country c ON mml.country_id = c.id
    WHERE mml.country_id IS NOT NULL AND mml.country_code IS NULL;
    """

    session = db.session().using_bind("default")

    countries = repository.CountryRepository(session=session)

    to_update = []
    for id_, user_id, country, country_code in session.execute(query):
        # no country_code, set to country abbr
        if country and not country_code:
            if country_ := countries.get(country_code=country):
                new_country_code = country_.alpha_2

                to_update.append(
                    UpdateDataRow(
                        id=id_,
                        user_id=user_id,
                        country_code=new_country_code,
                    )
                )

    return to_update


def backfill_country(batch_size: int = 1_000):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
    rows_to_update = find_rows_to_udpate()
    backfill_in_batches(rows_to_update, batch_size=batch_size)


def backfill(dry_run: bool = False, batch_size: int = 1_000):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
    log.info(
        "Running country backfill.",
        dry_run=dry_run,
    )
    from app import create_app

    with create_app(task_instance=True).app_context():
        try:
            with db.session.no_autoflush:
                backfill_country(batch_size=batch_size)
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
    help="The number of rows to update at a time.",
)
def main(dry_run: bool = False, batch_size: int = 1_000):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
    backfill(dry_run=dry_run, batch_size=batch_size)


@dataclasses.dataclass
class UpdateDataRow:
    id: int
    user_id: str
    country_code: str


if __name__ == "__main__":
    main()
