import redis

from airflow.utils import with_app_context
from utils.cache import redis_client
from utils.log import logger

log = logger(__name__)


@with_app_context(team_ns="core_services", service_ns="gdpr_deletion")
def memorystore_connection_test_job() -> None:
    client = redis_client(via_redis_proxy=True)
    _print_values(client)


def _print_values(client: redis.Redis) -> None:
    all_uris_key = "posts_PostsViewCache_all_uris"
    all_keys = client.smembers(all_uris_key)
    log.info(f"number of keys: {len(all_keys)}")

    with client.pipeline(transaction=False) as pipe:
        for key in all_keys:
            pipe.smembers(key)
        fields = pipe.execute()
        keys_to_fields = dict(zip(all_keys, fields))
        log.info(f"Result of pipeline: {keys_to_fields}")

    for key in all_keys:
        try:
            value = client.get(key)
            if value:
                log.info(f"Value for key '{key}': {value}")
            else:
                log.info(f"Key '{key}' does not exist.")
        except Exception as e:
            log.error(f"Error getting key '{key}': {e}")
            raise e
