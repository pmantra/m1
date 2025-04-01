from app import create_app
from authn.models.user import User
from braze import client
from storage.connection import db
from utils.log import logger
from utils.query import paginate

log = logger(__name__)


def disable_braze_click_tracking_for_all_users():  # type: ignore[no-untyped-def] # Function is missing a return type annotation
    log.info("Disable braze click tracking")
    braze_batch_size = 75

    braze_client = client.BrazeClient()
    for users in paginate(
        db.session.query(User), User.esp_id, size=braze_batch_size, chunk=True
    ):
        braze_user_attributes = [
            client.BrazeUserAttributes(
                external_id=u.esp_id,
                attributes={"email_click_tracking_disabled": True},
            )
            for u in users
            if u.esp_id
        ]
        braze_client.track_users(user_attributes=braze_user_attributes)

    log.info("Disable braze click tracking completed")


if __name__ == "__main__":
    with create_app().app_context():
        disable_braze_click_tracking_for_all_users()
