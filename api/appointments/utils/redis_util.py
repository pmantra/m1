"""
This script is intended for handling adhoc, inconsistent issues related to appointment redis cache with
handy functions directly interact with appointment redis cache

It's expected that user accessing to the api-shell and perform functions

Example usage:

```python
from appointments.utils.redis_util import *

namespace = "appointment"
entries = list_entries(namespace)

```

"""
import logging

from appointments.utils.flask_redis_ext import (
    APPOINTMENT_REDIS,
    CACHE_RESPONSE_FAILURES,
    INVALIDATE_RESPONSE_FAILURES,
    delete_keys_and_tags,
    flask_redis,
)
from common import stats

logger = logging.getLogger(__name__)


def get_cached_value_by_key(cache_key, redis_client=None, redis_name=APPOINTMENT_REDIS):  # type: ignore[no-untyped-def] # Function is missing a type annotation
    if not redis_client:
        redis_client = flask_redis.get_client(redis_name)
    try:
        return redis_client.get(cache_key)
    except Exception as e:
        logger.warning(f"Got exception {e} while retrieve from cache", key=cache_key)  # type: ignore[call-arg] # Unexpected keyword argument "key" for "warning" of "Logger"
        stats.increment(
            metric_name=CACHE_RESPONSE_FAILURES,
            tags=["namespace:appointment_details", "reason:REDIS_GET_EXCEPTION"],
            pod_name=stats.PodNames.CARE_DISCOVERY,
        )


def invalidate_cache(tags, redis_name=APPOINTMENT_REDIS):  # type: ignore[no-untyped-def] # Function is missing a type annotation
    try:
        delete_keys_and_tags(
            redis_name=redis_name,
            tags=tags,
            namespace="appointment_details",
            pod_name=stats.PodNames.CARE_DISCOVERY,
        )
    except Exception as e:
        logger.error(f"Got exception {e} during invalidate tags", exc_info=True)
        stats.increment(
            metric_name=INVALIDATE_RESPONSE_FAILURES,
            tags=[
                "namespace:appointment_details",
                "reason:INVALIDATE_FAILURE",
                "source:TASKS",
            ],
            pod_name=stats.PodNames.CARE_DISCOVERY,
        )


def invalidate_appointment_cache(appointment, redis_client=None):  # type: ignore[no-untyped-def] # Function is missing a type annotation
    if not redis_client:
        try:
            redis_client = flask_redis.get_client(APPOINTMENT_REDIS)
        except KeyError:
            logger.error(f"Redis client {APPOINTMENT_REDIS} not found.")
            stats.increment(
                metric_name=CACHE_RESPONSE_FAILURES,
                tags=["reason:CLIENT_NAME_NOT_FOUND", "namespace:appointment_details"],
                pod_name=stats.PodNames.CARE_DISCOVERY,
            )
            return
    tags = [
        f"appointment_data:{appointment.id}",
        f"user_appointments:{appointment.member_id}",
        f"user_appointments:{appointment.practitioner_id}",
    ]
    invalidate_cache(tags=tags)


def cache_key_exists(cache_key, redis_name=APPOINTMENT_REDIS):  # type: ignore[no-untyped-def] # Function is missing a type annotation
    """
    Check if a given cache key exists or not
    Args:
        cache_key: formatted cache key
        redis_name: the named redis client, default to appointment redis
    Returns: True if key exists in namespace, False otherwise
    """
    value = get_cached_value_by_key(cache_key, redis_name=redis_name)
    return True if value else False


def list_entries(namespace, redis_name=APPOINTMENT_REDIS):  # type: ignore[no-untyped-def] # Function is missing a type annotation
    """
    list out key, value pairs under the provided namespace
    Args:
        namespace: cache key namespace, e.g. appointment_detail
        redis_name: the named redis client, default to appointment redis

    Returns: list of entries

    """
    client = flask_redis.get_client(redis_name)
    result = []
    for item in client.scan_iter(match=f"{namespace}:*", count=500):
        result.append(item)
    return result
