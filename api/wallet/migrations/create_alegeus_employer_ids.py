import secrets

from app import create_app
from models.enterprise import Organization, OrganizationType
from storage.connection import db
from utils.log import logger

log = logger(__name__)


def _get_new_id():  # type: ignore[no-untyped-def] # Function is missing a return type annotation
    return "MVN" + secrets.token_hex(4)


def create_alegeus_employer_id():  # type: ignore[no-untyped-def] # Function is missing a return type annotation
    count = 0
    try:
        organizations = (
            db.session.query(Organization)
            .filter(
                Organization.internal_type != OrganizationType.TEST,
                Organization.internal_type != OrganizationType.DEMO_OR_VIP,
                Organization.alegeus_employer_id.is_(None),
            )
            .all()
        )

        for organization in organizations:
            try:
                organization.alegeus_employer_id = _get_new_id()
                db.session.add(organization)
                count += 1
            except Exception as e:
                log.info(f"There was an error assigning the alegeus_employer_id {e}")

        db.session.commit()

        log.info(f"{count} alegeus employer ids were successfully created.")

    except Exception as e:
        log.info(f"There was an error retrieving the organizations {e}")


if __name__ == "__main__":
    with create_app().app_context():
        create_alegeus_employer_id()
