"""
get_resource_ids.py

Fetch resource ids from the DB based on their URL slugs. Outputs a csv file
named 'resource_tags.csv' which can be used with the bulk resource tagging tool

Usage:
  get_resource_ids.py <file_path>

Options:
  -h --help     Show this screen.

"""

import csv

from docopt import docopt

from admin.app import (  # type: ignore[attr-defined] # Module "admin.app" has no attribute "RESOURCE_TAG_CSV_FIELD_NAMES"
    RESOURCE_TAG_CSV_FIELD_NAMES,
)
from app import create_app
from models.marketing import Resource
from storage.connection import db
from utils.log import logger

log = logger(__name__)

OUTPUT_FILE_PATH = "resource_tags.csv"


def get_resource_ids(file_path):  # type: ignore[no-untyped-def] # Function is missing a type annotation
    with open(file_path) as fp:
        rows = []
        for row in csv.DictReader(fp):
            rows.append(_get_resource_info(row))

    with open(OUTPUT_FILE_PATH, "w") as fp:
        writer = csv.DictWriter(fp, RESOURCE_TAG_CSV_FIELD_NAMES)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def _get_resource_info(row):  # type: ignore[no-untyped-def] # Function is missing a type annotation
    resource = db.session.query(Resource).filter(Resource.slug == row["URL slug"]).one()
    return {
        "resource_id": resource.id,
        "module_name": row["Module name"],
        "phase_name": row["Phase name"],
        "content_type": resource.content_type,
        "tag_display_names": row["Tag name"],
    }


if __name__ == "__main__":
    with create_app().app_context():
        get_resource_ids(docopt(__doc__)["<file_path>"])
