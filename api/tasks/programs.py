from models.enterprise import Organization
from models.programs import Module
from storage.connection import db
from tasks.queues import job
from utils.log import logger

log = logger(__name__)


@job(team_ns="enrollments")
def update_organization_approved_modules():  # type: ignore[no-untyped-def] # Function is missing a return type annotation
    # This job is needed to keep "live" ClientTracks in sync with organization_approved_modules,
    # which is used in Programs Lifecycle code. The Growth team also looks at the Allowed Modules
    # field on the Admin Organization page to verify which tracks are actually visible to members.
    # We can delete this job once we've moved off both those use cases.

    organizations = Organization.query.all()
    for org in organizations:
        log.info("Refreshing org allowed modules for org.", org_id=org.id)
        org.allowed_modules = Module.query.filter(
            Module.name.in_([ct.name for ct in org.allowed_tracks])
        ).all()

    db.session.commit()
