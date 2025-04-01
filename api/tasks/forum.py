import time

from redset.exceptions import LockTimeout
from sqlalchemy.orm.exc import NoResultFound

from authn.models.user import User

# DO NOT REMOVE BELOW 2 LINES. SQLALCHEMY NEEDS IT FOR MAPPER INSTANTIATION
from messaging.models.messaging import MessageBilling  # noqa: F401
from models.forum import (
    Post,
    PostsViewCache,
    UserPersonalizedPostsCache,
    Vote,
    user_bookmarks,
)
from models.referrals import ReferralCodeUse  # noqa: F401
from storage.connection import db
from tasks.queues import job
from utils.cache import RedisLock
from utils.log import logger

log = logger(__name__)


@job("high_mem")
def invalidate_posts_cache(ids=None, update_time=120):  # type: ignore[no-untyped-def] # Function is missing a type annotation
    start = time.time()

    try:
        with RedisLock("forum_cache_invalidate_all", timeout=1, expires=update_time):
            invalidated = PostsViewCache().invalidate_all()
            # TODO - fill the cache with a request to the endpoints

    except LockTimeout:
        log.info("Already warming up in forum cache all...")
        return

    log.info(
        f"Invalidated posts cache for {invalidated} endpoints in {time.time() - start}"
    )


@job(traced_parameters=("user_id",))
def invalidate_posts_cache_for_user(user_id):  # type: ignore[no-untyped-def] # Function is missing a type annotation
    cache = PostsViewCache()

    try:
        with RedisLock(f"forum_cache_invalidate_all_user_{user_id}", timeout=2):
            posts = db.session.query(Post).filter(Post.author_id == user_id).all()

            if posts:
                post_ids = [p.id for p in posts]
                invalidated = cache.invalidate_ids(post_ids)
                log.info(
                    "invalidate_posts_cache_for_user: %s endpoints for %s",
                    len(invalidated),
                    user_id,
                )

    except LockTimeout:
        log.debug(
            f"Could not get lock on invalidate_posts_cache_for_user: {user_id}, returning"
        )


@job("high_mem")
def update_personalized_caches():  # type: ignore[no-untyped-def] # Function is missing a return type annotation
    log.debug("Updating personalized forum caches for all users.")

    try:
        with RedisLock("forum_cache_update_personalized_caches", timeout=2):
            _update_personalized_caches()
            log.debug("update_personalized_caches updated!")
    except LockTimeout:
        log.info("Could not get lock on update_personalized_caches")


@job(traced_parameters=("user_id",))
def update_personalized_cache(user_id):  # type: ignore[no-untyped-def] # Function is missing a type annotation

    try:
        user = db.session.query(User).filter(User.id == int(user_id)).one()
    except NoResultFound:
        log.info("Cannot cache personalized for bad user: %s", user_id)
        return

    try:
        key = f"forum_cache_update_personalized_caches_user_{user.id}"
        with RedisLock(key, timeout=2):
            log.debug("Updating personalized forum caches for %s", user)
            cache = UserPersonalizedPostsCache(user)
            cache.update_personalized()
            log.info("update_personalized_cache done for %s", user.id)

    except LockTimeout:
        log.debug(
            f"Could not get lock on update_personalized_cache: {user_id}, returning"
        )


def _update_personalized_caches():  # type: ignore[no-untyped-def] # Function is missing a return type annotation
    votes_data = db.session.query(Vote.user_id).filter().distinct().all()
    bookmarks_data = (
        db.session.query(user_bookmarks.c.user_id).filter().distinct().all()
    )

    votes_data = [r[0] for r in votes_data]
    bookmarks_data = [r[0] for r in bookmarks_data]

    log.debug("Updating votes for user IDs: %s", votes_data)
    log.debug("Updating bookmarks for user IDs: %s", bookmarks_data)
    _all = set(votes_data + bookmarks_data)
    for _user_id in _all:
        update_personalized_cache.delay(_user_id, team_ns="content_and_community")

    log.info(
        (
            "update_personalized_caches done for %s bookmark_users, "
            "%s vote_users, %s total_users"
        ),
        len(bookmarks_data),
        len(votes_data),
        len(_all),
    )


@job(team_ns="content_and_community", service_ns="community_forum")
def send_braze_events_for_post_reply(post_id: int, replier_id: int) -> None:
    post = db.session.query(Post).filter(Post.id == post_id).first()
    post.notify_author_and_other_participants(replier_id)
