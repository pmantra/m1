import itertools
import pathlib
import sys
from csv import DictReader
from typing import Iterable, Mapping

import click
from sqlalchemy import and_
from sqlalchemy.sql import case

from models.enterprise import Organization, OrganizationEmployee
from utils import log

logger = log.logger(__name__)


def chunks(iterable: Iterable, size: int) -> Iterable[Iterable]:
    """Yield successive n-sized chunks."""
    it = iter(iterable)
    item = [*itertools.islice(it, size)]
    while item:
        yield item
        item = [*itertools.islice(it, size)]


def get_mapping(path: pathlib.Path) -> DictReader:
    logger.info("Fetching corp-id mapping from file.", file=str(path))
    mapping = DictReader(path.open())
    logger.info("Fetched mapping from file.", file=str(path))
    return mapping


DUPE_TAIL = "+DUPE"


def remap_corp_ids(  # type: ignore[no-untyped-def] # Function is missing a return type annotation
    org_id: int,
    mapping: Iterable[Mapping[str, str]],
    *,
    dry_run: bool = False,
    chunk_size: int = 1_000,
):
    from storage.connection import db

    log = logger.bind(organization_id=org_id)
    log.info("Start re-mapping corp-ids for org.")
    q = db.session.query(Organization.id).filter(Organization.id == org_id)
    org_exists = db.session.query(q.exists()).scalar()
    if not org_exists:
        raise ValueError(f"Selected Organization doesn't exist: {org_id}")

    table = OrganizationEmployee.__table__
    tmp_ids = set()
    new_ids = set()
    entries = []
    for m in mapping:
        tmp_ids.add(m["old_corp_id"])
        new_ids.add(m["new_corp_id"])
        entries.append(m)
    overlap = new_ids & tmp_ids
    tmp_mappings = []
    with db.session.begin_nested():
        for i, chunk in enumerate(chunks(entries, size=chunk_size), start=1):
            whens = []
            old_ids = []
            log.debug("Generating case statement for update chunk.", chunk=i)
            for m in chunk:
                old, new = m["old_corp_id"], m["new_corp_id"]
                # If we have an overlap, we need to do a temporary migration
                #   OFF the collision.
                if new in overlap:
                    tmp = new + DUPE_TAIL
                    tmp_mappings.append({"tmp_corp_id": tmp, "new_corp_id": new})
                    new = tmp
                whens.append((table.c.unique_corp_id == old, new))
                old_ids.append(old)
            log.debug("Done creating case statement.", entries=len(whens))
            log.info("Building query for re-mapping in db.", entries=len(whens))
            stmt = (
                table.update()
                .values(unique_corp_id=case(whens))
                .where(
                    and_(
                        table.c.unique_corp_id.in_(old_ids),
                        (table.c.organization_id == org_id),
                    )
                )
            )
            if dry_run:
                log.info("Dry-run. Not running update.")
                continue
            db.session.execute(stmt)
        # If there were overlapping re-mappings, we created a temporary migration.
        #   NOW we update to the final value.
        if tmp_mappings:
            whens = []
            tmp_ids = []  # type: ignore[assignment] # Incompatible types in assignment (expression has type "List[Never]", variable has type "Set[str]")
            for tm in tmp_mappings:
                tmp, new = tm["tmp_corp_id"], tm["new_corp_id"]
                whens.append((table.c.unique_corp_id == tmp, new))
                tmp_ids.append(tmp)  # type: ignore[attr-defined] # "Set[str]" has no attribute "append"

            stmt = (
                table.update()
                .values(unique_corp_id=case(whens))
                .where(
                    and_(
                        table.c.unique_corp_id.in_(tmp_ids),
                        (table.c.organization_id == org_id),
                    )
                )
            )
            if dry_run:
                log.info("Dry-run. Not running update.")
            else:
                db.session.execute(stmt)

    try:
        db.session.commit()
        log.info("Done re-mapping corp-ids for org.")
    except BaseException:
        db.session.rollback()
        raise


@click.command()
@click.option(
    "--org-id",
    "-o",
    type=int,
    required=True,
    prompt="Organization ID",
    help="The ID of the Organization whose members should be updated.",
)
@click.option(
    "--file",
    "-f",
    type=click.Path(exists=True, dir_okay=False, resolve_path=True),
    required=True,
    prompt="Path to CSV file",
    help="A path to a CSV which contains the mapping from `old_corp_id->new_corp_id`.",
)
@click.option(
    "--dry-run",
    "-D",
    is_flag=True,
    help="Run the script but do not save the result in the database.",
)
@click.option(
    "--chunk-size", "-c", default=1_000, help="The max size for an individual DB write."
)
def main(org_id: int, file: str, dry_run: bool = False, chunk_size: int = 1_000):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
    from app import create_app

    app = create_app(task_instance=True)
    with app.app_context():
        try:
            mapping = get_mapping(pathlib.Path(file))
            remap_corp_ids(org_id, mapping, dry_run=dry_run, chunk_size=chunk_size)
        except ValueError as e:
            ue = click.UsageError(str(e))
            ue.show()
            sys.exit(ue.exit_code)


if __name__ == "__main__":
    main()
