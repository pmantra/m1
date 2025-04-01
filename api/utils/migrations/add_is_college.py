from authn.models.user import User
from utils.log import logger
from utils.mailchimp import add_group_to_email

log = logger(__name__)


def migrate_all_users():  # type: ignore[no-untyped-def] # Function is missing a return type annotation
    for user in User.query.all():
        log.debug("Tagging %s", user)

        if user.health_profile.json.get("is_college"):
            log.debug("%s is college...", user)

            add_group_to_email(user.email, "is_college", grouping_name="User Segments")
