import uuid

import app
from models.enterprise import Organization
from storage.connection import db
from utils.log import logger

log = logger(__name__)


def main():  # type: ignore[no-untyped-def] # Function is missing a return type annotation
    for org in db.session.query(Organization):
        if org.org_employee_primary_key == "unique_corp_id":
            _populate_missing_ids(org)
    db.session.commit()


def _populate_missing_ids(org):  # type: ignore[no-untyped-def] # Function is missing a type annotation
    log.info(f"Checking for missing corp ids Org: {org}")
    for e in org.employees:
        if not e.unique_corp_id:
            log.info(f"Populating missing unique corp id for OE: {e}")
            e.unique_corp_id = str(uuid.uuid4())


if __name__ == "__main__":
    with app.create_app().app_context():
        main()
