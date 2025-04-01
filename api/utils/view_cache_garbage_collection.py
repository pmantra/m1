import redis

from utils.cache import redis_client
from utils.log import logger

log = logger(__name__)


def gc_view_caches() -> None:
    # this utility is created for manually garbage collection all the Redis memory space taken by
    # the ViewCache implementations to fix the memory leak issues
    # this should be run during off-peak hours to avoid service disruptions and monitor related metrics closely
    new_client = redis_client()
    try:
        stop_migration_ttl = 2 * 60 * 60
        stop_migration_key = "view_caches_stop_gc_process"
        # in another console, set this to be 1 will stop the GC run if something happens during the process
        new_client.setex(stop_migration_key, stop_migration_ttl, 0)

        gc_run(
            new_client,
            all_uris_key="posts_PostsViewCache_all_uris",
            match_pattern="posts_view_cache_*",
            stop_migration_key=stop_migration_key,
        )
        # re-enable this if we want to clean up CategoriesViewCache as well
        # gc_run(
        #     new_client,
        #     all_uris_key="categories_CategoriesViewCache_all_uris",
        #     match_pattern="categories_view_cache_*",
        #     stop_migration_key=stop_migration_key,
        # )
    except Exception as ex:
        log.error(f"[gc_view_caches] encountered exception when running gc run {ex}")
        return
    log.info("[gc_view_caches] gc job is finished successfully")


def gc_run(
    new_client: redis.Redis,
    all_uris_key: str,
    match_pattern: str,
    stop_migration_key: str,
) -> None:
    # step 1: clean up id cache
    batch_size = 50
    cursor = 0
    continue_scanning = True
    count = 0
    while continue_scanning:
        cursor, keys = new_client.scan(cursor, match_pattern, batch_size)
        if len(keys) > 0:
            count += len(keys)
            with new_client.pipeline(transaction=False) as new_pipe:
                for key in keys:
                    new_pipe.delete(key)
                new_pipe.execute()
        stop_migration_val = int(new_client.get(stop_migration_key))  # type: ignore
        if stop_migration_val == 1 or cursor == 0:
            continue_scanning = False

    # step 2: delete the all_uris set
    stop_migration_val = int(new_client.get(stop_migration_key))  # type: ignore
    if stop_migration_val == 0:
        new_client.delete(all_uris_key)
        count += 1

    log.info(f"[gc_run] gc run has cleaned up {count} redis keys")
