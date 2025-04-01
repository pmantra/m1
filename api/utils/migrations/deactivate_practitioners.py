"""
Script to deactivate multiple practitioners by id
- May need to break into digestable chunks (unknown drop from api on large number)

ex:
dry_run = True
from utils.migrations.deactivate_practitioners import deactivate_practitioners
prac_ids = [123,456,789]
deactivate_practitioners(prac_ids, dry_run)
"""

import uuid

from models.profiles import PractitionerProfile
from provider_matching.services.care_team_assignment import (
    remove_member_practitioner_associations,
)
from storage.connection import db
from utils.log import logger

log = logger(__name__)


def deactivate_practitioners(prac_ids, dry_run=True):  # type: ignore[no-untyped-def] # Function is missing a type annotation
    deactivated_ids = []
    pracs = (
        db.session.query(PractitionerProfile)
        .filter(PractitionerProfile.user_id.in_(prac_ids))
        .all()
    )
    for prac in pracs:
        log.info(f"Deactiving user id: {prac.user_id}")

        # Disable account
        prac.active = False
        prac.messaging_enabled = False
        prac.user.active = False

        # Set new api key if none (empty breaks login process if re-activing)
        if not prac.user.api_key:
            prac.user.api_key = str(uuid.uuid4())

        # Remove from any care teams
        remove_member_practitioner_associations(
            prac_to_remove=prac.user_id, remove_only_quiz_type=False
        )

        # Add to our list
        deactivated_ids.append(prac.user_id)

    # Log and complete
    log.info(f"Deactived Users: {deactivated_ids}")
    if dry_run:
        log.info("Dry Run Complete")
    else:
        db.session.commit()
