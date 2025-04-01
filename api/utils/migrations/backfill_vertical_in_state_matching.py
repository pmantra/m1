from operator import and_, or_
from typing import Dict, Iterator

import click

from geography.repository import SubdivisionRepository
from models.profiles import State
from provider_matching.models.in_state_matching import (
    VerticalInStateMatching,
    VerticalInStateMatchState,
)
from storage.connection import db
from utils.log import logger

log = logger(__name__)


def backfill_vertical_in_state_matching(batch_size: int = 1_000):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
    for batch in create_batch(batch_size=batch_size):
        log.debug("Updating mappings")
        db.session.bulk_save_objects(batch)


def create_batch(batch_size: int = 1_000) -> Iterator[Dict[int, str]]:
    log.debug("Fetching data from vertical_in_state_match_state...")

    query = (
        db.session.query(
            VerticalInStateMatchState.vertical_id,
            VerticalInStateMatchState.state_id,
            State.abbreviation,
        )
        .join(State, VerticalInStateMatchState.state_id == State.id)
        .order_by(VerticalInStateMatchState.vertical_id, State.id)
    )

    log.debug("Building batch...")
    batch_num = 0
    batch = query.limit(batch_size).all()
    to_add = []

    subdivisions = SubdivisionRepository()

    while batch:
        last_row = (batch[-1].vertical_id, batch[-1].state_id)
        batch_num += 1

        for vertical_id, state_id, state in batch:
            if subdivision := subdivisions.get_by_country_code_and_state(
                country_code="US", state=state
            ):
                existing = VerticalInStateMatching.query.filter_by(
                    vertical_id=vertical_id,
                    subdivision_code=subdivision.code,
                ).one_or_none()

                if not existing:
                    log.info(
                        "Will create new row",
                        vertical_id=vertical_id,
                        subdivision_code=subdivision.code,
                    )

                    new_row = VerticalInStateMatching(
                        vertical_id=vertical_id,
                        subdivision_code=subdivision.code,
                    )
                    to_add.append(new_row)

            else:
                log.warning(
                    "Could not find appropriate subdivision_code for state",
                    vertical_id=vertical_id,
                    state_id=state_id,
                    state=state,
                )

        if len(to_add) >= batch_size:
            yield to_add
            to_add = []
        else:
            log.info("Still building batch...", batch=batch_num, size=len(batch))

        # Pull in the next batch
        batch = (
            query.filter(
                or_(
                    and_(
                        VerticalInStateMatchState.vertical_id == last_row[0],
                        VerticalInStateMatchState.state_id > last_row[1],
                    ),
                    VerticalInStateMatchState.vertical_id > last_row[0],
                )
            )
            .limit(batch_size)
            .all()
        )
    if to_add:
        yield to_add


def backfill(dry_run: bool = False, batch_size: int = 1_000):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
    log.info(
        "Running vertical_in_state_matching backfill...",
        dry_run=dry_run,
    )
    from app import create_app

    with create_app(task_instance=True).app_context():
        try:
            with db.session.no_autoflush:
                backfill_vertical_in_state_matching(batch_size=batch_size)
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

        len_old_table = VerticalInStateMatchState.query.count()
        len_new_table = VerticalInStateMatching.query.count()
        assert len_old_table == len_new_table, "Tables are not the same shape!"


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
    help="The number of rows to pull into memory at a time.",
)
def main(dry_run: bool = False, batch_size: int = 1_000):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
    backfill(dry_run=dry_run, batch_size=batch_size)


if __name__ == "__main__":
    main()
