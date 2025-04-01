from uuid import uuid4

from sqlalchemy import text

from health.models.health_profile import HealthProfile
from storage.connection import db
from utils.log import logger

log = logger(__name__)


def add_missing_child_id_in_health_profiles():  # type: ignore[no-untyped-def] # Function is missing a return type annotation
    results = (
        db.session.query(HealthProfile).filter(text("json LIKE '%\"children\"%'")).all()
    )

    num_changed = 0
    num_skipped = 0
    log.debug("There are a total of %s health profiles with children.", len(results))
    for profile in results:
        changed = False
        children = profile.json.get("children") or []
        log.debug("Existing %s in %s", children, profile)

        for child in children:
            if not child.get("id"):
                child["id"] = str(uuid4())
                changed = True

        if changed:
            log.debug("With ids %s", children)
            profile.json["children"] = children
            num_changed += 1
        else:
            log.debug("Not changed. Skipping...")
            num_skipped += 1

    db.session.commit()
    log.debug("All set. %s changed, %s skipped.", num_changed, num_skipped)
