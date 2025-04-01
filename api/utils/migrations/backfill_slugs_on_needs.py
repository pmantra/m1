from __future__ import absolute_import

import csv
import dataclasses
from typing import List

import click

from providers.repository.need import NeedRepository
from storage.connection import db
from utils.log import logger

log = logger(__name__)


def print_header(header_text):  # type: ignore[no-untyped-def] # Function is missing a type annotation
    log.info("\n=================================================")
    log.info(f"{header_text}\n=================================================\n")


@dataclasses.dataclass
class NeedRow:
    id: int
    slug: str


def is_row_data_valid(row) -> bool:
    try:
        NeedRow(id=int(row["id"]), slug=row["slug"])
        return True
    except Exception:
        return False


def add_slugs_to_needs(filename) -> List[NeedRow]:  # type: ignore[return] # Missing return statement #type: ignore[no-untyped-def] # Function is missing a type annotation for one or more arguments
    total_csv_rows = 0
    need_data = []

    # Read and validate CSV data
    with open(filename) as csvfile:
        reader = csv.DictReader(csvfile)
        for row in reader:
            total_csv_rows += 1

            if is_row_data_valid(row):
                log.info(f"Reading row: {row}")
                need_data.append(NeedRow(id=int(row["id"]), slug=row["slug"]))
            else:
                log.info(
                    f"Invalid data for need: {row}.\nThe following fields are required for every row: {list(NeedRow.__annotations__)}"
                )

    total_rows_updated = 0
    for row in need_data:  # type: ignore[assignment] # Incompatible types in assignment (expression has type "NeedRow", variable has type "Dict[Union[str, Any], Union[str, Any]]")
        NeedRepository(db.session).add_slug_to_need(need_id=row.id, slug=row.slug)  # type: ignore[attr-defined] # "Dict[Union[str, Any], Union[str, Any]]" has no attribute "id" #type: ignore[attr-defined] # "Dict[Union[str, Any], Union[str, Any]]" has no attribute "slug"
        total_rows_updated += 1

    log.info(
        f"\nNumber of rows in CSV: {total_csv_rows}.\nNumber of rows updated: {total_rows_updated}"
    )


def backfill_slugs_on_needs(file, dry_run):  # type: ignore[no-untyped-def] # Function is missing a type annotation
    try:
        print_header("Starting to update Needs by adding slugs")
        add_slugs_to_needs(file)
    except Exception as e:
        db.session.rollback()
        log.info("Got an exception while backfilling.", exception=e)  # noqa
        return

    if dry_run:
        log.info("Dry run requested. Rolling back changes.")  # noqa
        db.session.rollback()
        return

    log.info("Committing changes...")  # noqa
    db.session.commit()
    log.info("Finished.")  # noqa


@click.command()
@click.option(
    "--file",
    "-f",
    required=True,
    prompt="Path to CSV file",
    help="A path to a CSV which contains the Need data",
)
@click.option(
    "--dry-run",
    "-D",
    is_flag=True,
    help="Run the script but do not save the result in the database.",
)
def backfill(file: str, dry_run: bool = False):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
    from app import create_app

    with create_app(task_instance=True).app_context():
        backfill_slugs_on_needs(file, dry_run)


if __name__ == "__main__":
    backfill()
