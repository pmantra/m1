from operator import and_, or_
from typing import Dict, Iterator, Optional

import click

from geography.repository import SubdivisionRepository
from models.profiles import (
    PractitionerProfile,
    PractitionerSubdivision,
    State,
    practitioner_states,
)
from storage.connection import db
from utils.log import logger

log = logger(__name__)


def backfill_certified_subdivision_codes(batch_size: int = 1_000):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
    for batch in create_batch(batch_size=batch_size):
        log.debug("Updating mappings")
        db.session.bulk_save_objects(batch)


def get_subdivision_code(
    subdivision_repository: SubdivisionRepository,
    user_id: int,
    country_code: str,
    state: str,
) -> Optional[str]:
    if state == "ZZ":
        return "US-ZZ"

    if subdivision := subdivision_repository.get_by_country_code_and_state(
        country_code=country_code,
        state=state,
    ):
        return subdivision.code
    else:
        log.warning(
            f"Could not validate state with country code '{country_code}'",
            practitioner_id=user_id,
            country_code=country_code,
            state=state,
        )

        if country_code != "US":
            if subdivision := subdivision_repository.get_by_country_code_and_state(
                country_code="US",
                state=state,
            ):
                return subdivision.code
            else:
                log.warning(
                    "Tried to set the state with the country as 'US', but could still not validate the state.",
                    practitioner_id=user_id,
                    country_code="US",
                    state=state,
                )

    return  # type: ignore[return-value] # Return value expected


def create_batch(batch_size: int = 1_000) -> Iterator[Dict[int, str]]:
    log.debug("Fetching Practitioner certified states...")

    query = (
        db.session.query(
            practitioner_states.c.user_id,
            PractitionerProfile.country_code,
            practitioner_states.c.state_id,
            State.abbreviation,
        )
        .join(
            PractitionerProfile,
            PractitionerProfile.user_id == practitioner_states.c.user_id,
        )
        .join(State, practitioner_states.c.state_id == State.id)
        .order_by(practitioner_states.c.user_id)
    )

    log.debug("Building batch with country_code and subdivision_code data...")
    batch_num = 0
    batch = query.limit(batch_size).all()
    to_add = []

    subdivisions = SubdivisionRepository()

    while batch:
        last_row = (batch[-1].user_id, batch[-1].state_id)
        batch_num += 1

        for (
            user_id,
            country_code,
            state_id,  # noqa  B007  TODO:  Loop control variable 'state_id' not used within the loop body. If this is intended, start the name with an underscore.
            state,
        ) in batch:
            log_ = log.bind(practitioner_id=user_id)

            if subdivision_code := get_subdivision_code(
                subdivisions, user_id, country_code, state
            ):
                practitioner_subdivision = PractitionerSubdivision.query.filter_by(
                    practitioner_id=user_id,
                    subdivision_code=subdivision_code,
                ).one_or_none()

                if not practitioner_subdivision:
                    log_.info(
                        "Will set practitioner subdivision",
                        subdivision_code=subdivision_code,
                    )

                    practitioner_subdivision = PractitionerSubdivision(
                        practitioner_id=user_id,
                        subdivision_code=subdivision_code,
                    )
                    to_add.append(practitioner_subdivision)

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
                        practitioner_states.c.user_id == last_row[0],
                        practitioner_states.c.state_id > last_row[1],
                    ),
                    practitioner_states.c.user_id > last_row[0],
                )
            )
            .limit(batch_size)
            .all()
        )
    if to_add:
        yield to_add


def backfill(dry_run: bool = False, batch_size: int = 1_000):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
    log.info(
        "Running PractitionerSubdivision certified_subdivisions backfill.",
        dry_run=dry_run,
    )
    from app import create_app

    with create_app(task_instance=True).app_context():
        try:
            with db.session.no_autoflush:
                backfill_certified_subdivision_codes(batch_size=batch_size)
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
    help="The number of PractitionerProfiles to pull into memory at a time.",
)
def main(dry_run: bool = False, batch_size: int = 1_000):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
    backfill(dry_run=dry_run, batch_size=batch_size)


if __name__ == "__main__":
    main()
