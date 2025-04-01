import redis

from utils.cache import redis_client
from utils.log import logger

log = logger(__name__)


def migration_wrapper():  # type: ignore[no-untyped-def] # Function is missing a return type annotation
    legacy_client = redis_client("redis")
    new_client = redis_client()
    try:
        # this is a placeholder, other methods will be called here during the api shell script run as well
        appointment_connection_state_migration(legacy_client, new_client)
    except Exception as ex:
        log.error(
            f"[migration_wrapper] encountered exception when running default redis migration {ex}"
        )
        return
    log.info("[migration_wrapper] migration job is finished successfully")


def categories_view_cache_migration(
    legacy_client: redis.Redis, new_client: redis.Redis
):
    # double check if the match pattern is correct
    # /models/profiles.py
    ttl = 24 * 60 * 60
    all_uris_key = "categories_CategoriesViewCache_all_uris"
    all_keys = legacy_client.smembers(all_uris_key)
    for key in all_keys:
        val = legacy_client.get(key)
        if val:
            new_client.setex(key, ttl, val)  # type: ignore[arg-type]
        # keep set content the same for migration
        new_client.sadd(all_uris_key, key)

    # now the id key logic
    match_pattern = "categories_view_cache_*"
    batch_size = 100
    cursor = 0
    continue_scanning = True
    count = 0
    while continue_scanning:
        cursor, keys = legacy_client.scan(cursor, match_pattern, batch_size)
        if len(keys) > 0:
            count += len(keys)
            with legacy_client.pipeline(transaction=False) as legacy_pipe:
                for key in keys:
                    legacy_pipe.smembers(key)
                fields = legacy_pipe.execute()
                keys_to_fields = dict(zip(keys, fields))

            if len(keys_to_fields) > 0:
                with new_client.pipeline(transaction=False) as new_pipe:
                    for key, uris in keys_to_fields.items():
                        for uri in uris:
                            new_pipe.sadd(key, uri)
                    new_pipe.execute()
        if cursor == 0:
            continue_scanning = False

    log.info(f"[categories_view_cache_migration] id key count={count}")

    # theoretically direct switch should work based on the logic, no need to run the following in general
    # from models.profiles import CategoriesViewCache
    #
    # # for clean up
    # cache = CategoriesViewCache()
    # cache.invalidate_all()
    # cache set logic in CategoriesResource.get() implementation

    log.info(
        "[categories_view_cache_migration] migration job is finished successfully."
    )


def posts_view_cache_migration(legacy_client: redis.Redis, new_client: redis.Redis):
    # double check if the match pattern is correct
    # /models/forum.py
    ttl = 24 * 60 * 60
    all_uris_key = "posts_PostsViewCache_all_uris"
    all_keys = legacy_client.smembers(all_uris_key)
    for key in all_keys:
        val = legacy_client.get(key)
        if val:
            new_client.setex(key, ttl, val)  # type: ignore[arg-type]
        # keep the cached content the same even if val is None
        new_client.sadd(all_uris_key, key)

    # now the id key logic
    match_pattern = "posts_view_cache_*"
    batch_size = 100
    cursor = 0
    continue_scanning = True
    count = 0
    while continue_scanning:
        cursor, keys = legacy_client.scan(cursor, match_pattern, batch_size)
        if len(keys) > 0:
            count += len(keys)
            with legacy_client.pipeline(transaction=False) as legacy_pipe:
                for key in keys:
                    legacy_pipe.smembers(key)
                fields = legacy_pipe.execute()
                keys_to_fields = dict(zip(keys, fields))

            if len(keys_to_fields) > 0:
                with new_client.pipeline(transaction=False) as new_pipe:
                    for key, uris in keys_to_fields.items():
                        for uri in uris:
                            new_pipe.sadd(key, uri)
                    new_pipe.execute()
        if cursor == 0:
            continue_scanning = False

    log.info(f"[posts_view_cache_migration] id key count={count}")

    # theoretically direct switch should work based on the logic, no need to run the following in general
    # from models.forum import PostsViewCache
    #
    # cache = PostsViewCache()
    # cache.invalidate_all()

    log.info("[posts_view_cache_migration] migration job is finished successfully.")


def user_posts_migration(legacy_client: redis.Redis, new_client: redis.Redis):
    # this needs to be done in off-peak hours after view_cache migration switch (RQ jobs)
    # step 1: update_personalized_caches.delay(team_ns='content_and_community')
    # after step 1, bookmark data should already be taken care of
    # only need to migrate votes data
    match_pattern = "forum_cache_user_*_has_voted"
    batch_size = 100
    cursor = 0
    continue_scanning = True
    while continue_scanning:
        cursor, keys = legacy_client.scan(cursor, match_pattern, batch_size)
        # insert into memory store for the kv pairs
        if len(keys) > 0:
            with legacy_client.pipeline(transaction=False) as legacy_pipe:
                for key in keys:
                    legacy_pipe.smembers(key)
                fields = legacy_pipe.execute()
                keys_to_fields = dict(zip(keys, fields))

            if len(keys_to_fields) > 0:
                with new_client.pipeline(transaction=False) as new_pipe:
                    for key, post_ids in keys_to_fields.items():
                        for post_id in post_ids:
                            new_pipe.sadd(key, post_id)
                        expire_seconds = 24 * 60 * 60  # 24-hrs
                        new_pipe.expire(key, expire_seconds)

                    new_pipe.execute()

        # redis SCAN will return a cursor of 0 once the full iteration has been completed
        if cursor == 0:
            continue_scanning = False

    log.info("[user_posts_migration] migration job is finished successfully.")


def cost_breakdown_migration(legacy_client: redis.Redis, new_client: redis.Redis):
    match_pattern = "cost_breakdown_rq:*"
    batch_size = 100
    cursor = 0
    continue_scanning = True
    while continue_scanning:
        cursor, keys = legacy_client.scan(cursor, match_pattern, batch_size)
        # insert into memory store for the kv pairs
        if len(keys) > 0:
            with legacy_client.pipeline(transaction=False) as legacy_pipe:
                for key in keys:
                    legacy_pipe.lrange(key, 0, -1)
                fields = legacy_pipe.execute()
                keys_to_fields = dict(zip(keys, fields))

            if len(keys_to_fields) > 0:
                with new_client.pipeline(transaction=False) as new_pipe:
                    for key, pending_job_ids in keys_to_fields.items():
                        for pending_job_id in pending_job_ids:
                            new_pipe.lpush(key, pending_job_id)
                        expire_seconds = 600  # 10 minutes
                        new_pipe.expire(key, expire_seconds)

                    new_pipe.execute()

        # redis SCAN will return a cursor of 0 once the full iteration has been completed
        if cursor == 0:
            continue_scanning = False

    log.info("[cost_breakdown_migration] migration job is finished successfully.")


def zendesk_migration():
    from messaging.services.zendesk import MAVEN_TO_ZENDESK_RECONCILIATION_LIST_KEY

    legacy_client = redis_client("redis")
    new_client = redis_client()
    message_ids = legacy_client.smembers(MAVEN_TO_ZENDESK_RECONCILIATION_LIST_KEY)
    for message_id in message_ids:
        new_client.sadd(MAVEN_TO_ZENDESK_RECONCILIATION_LIST_KEY, message_id)
    log.info(
        f"[zendesk_migration] migration job is finished successfully with {len(message_ids)} items migrated"
    )


def block_list_migration():  # type: ignore[no-untyped-def] # Function is missing a return type annotation
    from authz.services.block_list import BlockableAttributes, BlockList

    legacy_block_list = BlockList()
    new_block_list = BlockList(migration_purpose=True)
    for attribute in BlockableAttributes:
        values = legacy_block_list.get_block_list(attribute)
        if values:
            for value in values:
                new_block_list.block_attribute(attribute, value)

    log.info("[block_list_migration] migration job is finished successfully")


def appointment_connection_state_migration(
    legacy_client: redis.Redis, new_client: redis.Redis
):
    from appointments.repository.appointment_connection_state import (
        SESSION_ID_LOOKUP_TTL_SECONDS,
        STATE_DATA_TTL_SECONDS,
    )

    # state, lock, session_lookup: api/appointments/repository/appointment_connection_state.py
    appointment_state_dict = {
        "appointment_connection_state:state:*": STATE_DATA_TTL_SECONDS,
        # "appointment_connection_state:lock:*": STATE_LOCK_EXPIRY_SECONDS,
        "appointment_connection_state:session_lookup:*": SESSION_ID_LOOKUP_TTL_SECONDS,
    }
    for key, ttl in appointment_state_dict.items():
        _appointment_connection_state_migration(
            legacy_client, new_client, match_pattern=key, ttl=ttl  # type: ignore
        )


def _appointment_connection_state_migration(
    legacy_client: redis.Redis,
    new_client: redis.Redis,
    match_pattern: str,
    ttl: int,
):
    batch_size = 100
    cursor = 0
    continue_scanning = True
    while continue_scanning:
        cursor, keys = legacy_client.scan(cursor, match_pattern, batch_size)
        # insert into memory store for the kv pairs
        if len(keys) > 0:
            with legacy_client.pipeline(transaction=False) as legacy_pipe:
                for key in keys:
                    legacy_pipe.get(key)
                fields = legacy_pipe.execute()
                keys_to_fields = dict(zip(keys, fields))

            if len(keys_to_fields) > 0:
                with new_client.pipeline(transaction=False) as new_pipe:
                    for key, val in keys_to_fields.items():
                        # check the original logic and keep the logic the same
                        new_pipe.setex(name=key, time=ttl, value=val)  # type: ignore
                    new_pipe.execute()

        # redis SCAN will return a cursor of 0 once the full iteration has been completed
        if cursor == 0:
            continue_scanning = False

    log.info(
        f"[appointment_connection_state_migration] migration job is finished successfully for {match_pattern}"
    )
