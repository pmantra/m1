from app import create_app
from authn.models.user import User
from utils import braze
from utils.log import logger

log = logger(__name__)

BATCH_SIZE = 75  # (braze limit for bulk add)


def add_all_users_to_braze():  # type: ignore[no-untyped-def] # Function is missing a return type annotation
    users = User.query.all()  # ~180k users, ~2400 75 user chunks
    offset = 0
    user_chunk = users[offset : offset + BATCH_SIZE]
    while user_chunk:
        # apparently no rate limit here, but maybe add a sleep to be safe?
        # https://www.braze.com/docs/api/basics/#api-limits
        log.info(f"adding user chunk to braze, offset at {offset}")
        braze.bulk_track_users(user_chunk)
        offset += BATCH_SIZE
        user_chunk = users[offset : offset + BATCH_SIZE]


if __name__ == "__main__":
    with create_app().app_context():
        add_all_users_to_braze()
