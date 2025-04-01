"""
 Flask redis extension for interacting with redis cache
"""

from __future__ import annotations

import dataclasses
import json
import os
import random
from collections import defaultdict
from functools import wraps

import flask
from redis import ConnectionPool, SSLConnection, StrictRedis

from common import stats
from utils.log import logger

log = logger(__name__)

# ======= Metric Related Constants ===============
CACHE_RESPONSE_FAILURES = "cache_response_failures"
INVALIDATE_RESPONSE_FAILURES = "invalidate_response_failures"
CACHE_HIT_STATS = "cache_hit_stats"
CACHE_MISS_STATS = "cache_miss_stats"
CACHE_UPDATE_STATS = "cache_update_stats"
CACHE_SCRIPTS_STATS = "cache_scripts_stats"
# =================================================

# ======= Redis DB Name Constants ==================
APPOINTMENT_REDIS = "appointment_redis"
APPOINTMENT_DEFAULT_TTL = 12 * 60 * 60  # 12 hours

# ==================================================


# ====== Script related ============================
INVALIDATE_WITH_TAG_SCRIPT = "invalidate_with_tags_script"
LUA_SCRIPT = """
 local tag = KEYS[1]
 local keys = redis.call('smembers', tag)
 if #keys > 0 then
     redis.call('del', unpack(keys))
 end
 redis.call('del', tag)
 """
# ==================================================


@dataclasses.dataclass
class RedisConfig:
    host: str = "localhost"
    port: int = 6479
    db: int = 0
    password: str | None = None
    ssl_ca_certs: str | None = None
    ssl: bool = False
    max_connections: int = 10
    # timeout in seconds
    socket_timeout: float | None = None
    socket_connect_timeout: float | None = None
    # represent scripts related to a given redis client, scripts are compiled along with
    # the client initialize time and use for address atomic and performance usage
    scripts: dict[str, str] | None = None


def redis_config() -> dict:
    appointments_redis_auth_string = os.environ.get("APPOINTMENTS_REDIS_AUTH_STRING")
    appointments_redis_host = os.environ.get("APPOINTMENTS_REDIS_HOST", "localhost")
    appointments_redis_port = os.environ.get("APPOINTMENTS_REDIS_PORT", "6479")
    appointments_redis_cert_file_path = os.environ.get(
        "APPOINTMENTS_REDIS_CERT_FILE_PATH"
    )
    appointments_redis_db = int(os.environ.get("APPOINTMENTS_REDIS_DB", 0))
    return {
        APPOINTMENT_REDIS: RedisConfig(
            host=appointments_redis_host,
            port=int(appointments_redis_port),
            password=appointments_redis_auth_string,
            ssl_ca_certs=appointments_redis_cert_file_path,
            ssl=True if appointments_redis_cert_file_path else False,
            db=appointments_redis_db,
            max_connections=10,
            socket_timeout=5.0,
            socket_connect_timeout=5.0,
            scripts={INVALIDATE_WITH_TAG_SCRIPT: LUA_SCRIPT},
        )
    }


class FlaskRedis:
    def __init__(self, app=None, **kwargs):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        self._redis_clients = {}
        self._script_hashes = defaultdict(dict)
        if app is not None:
            self.init_app(app, **kwargs)

    def init_app(self, app, **configurations):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        for name, config in configurations.items():
            pool_kwargs = dict(
                host=config.host,
                port=config.port,
                db=config.db,
                password=config.password,
                socket_timeout=config.socket_timeout,
                socket_connect_timeout=config.socket_connect_timeout,
                max_connections=config.max_connections,
            )
            if config.ssl:
                pool_kwargs.update(
                    connection_class=SSLConnection,
                    ssl_cert_reqs="required",
                    ssl_ca_certs=config.ssl_ca_certs,
                )
            connection_pool = ConnectionPool(**pool_kwargs)
            client = StrictRedis(connection_pool=connection_pool, decode_responses=True)
            self._redis_clients[name] = client
            # each client has a script hash dict
            self._script_hashes[name] = {}
            if config.scripts:
                for script_name, script in config.scripts.items():
                    self.register_lua_script(script, script_name, name)
        if not hasattr(app, "extensions"):
            app.extensions = {}
        app.extensions["redis"] = self

    def get_client(self, name):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        return self._redis_clients.get(name)

    def register_lua_script(self, script, script_name, client_name):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        client = self.get_client(client_name)
        try:
            sha1 = client.script_load(script)
            self._script_hashes[client_name][script_name] = sha1
            return sha1
        except Exception as e:
            log.debug(
                f"Got exception {e} when register {script_name=} for {client_name}"
            )
            stats.increment(
                metric_name=CACHE_SCRIPTS_STATS,
                tags=[f"client:{client_name}", "reason:REGISTER_FAILURE"],
                pod_name=stats.PodNames.CARE_DISCOVERY,
            )
            return None

    def execute_script(self, script_name, client_name, keys, args):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        client = self.get_client(client_name)
        scripts = self._script_hashes.get(client_name, {})
        sha1 = scripts.get(script_name)
        if not sha1:
            stats.increment(
                metric_name=CACHE_SCRIPTS_STATS,
                tags=[f"client:{client_name}", "reason:EXECUTION_FAILURE"],
                pod_name=stats.PodNames.CARE_DISCOVERY,
            )
            raise ValueError(
                f"No script registered under {script_name=} for {client_name=}"
            )
        return client.evalsha(sha1, len(keys), *keys, *args)


# Global flask_redis instance for flask app initialization, for app within flask context,
# use: flask_redis.get_client(foo) to retrieve dedicated redis client for foo
flask_redis = FlaskRedis()


def get_cache_key(cache_key_func, *args, **kwargs):  # type: ignore[no-untyped-def] # Function is missing a type annotation
    if (
        args
        and hasattr(args[0], "redis_cache_key")
        and callable(args[0].redis_cache_key)
    ):
        return args[0].redis_cache_key(*args, **kwargs)
    elif cache_key_func and callable(cache_key_func):
        return cache_key_func(*args, **kwargs)
    else:
        return None


def get_invalidate_func(invalidate_cache_func, *args, **kwargs):  # type: ignore[no-untyped-def] # Function is missing a type annotation
    if (
        args
        and hasattr(args[0], "invalidate_cache_func")
        and callable(args[0].invalidate_cache_func)
    ):
        return args[0].invalidate_cache_func
    elif invalidate_cache_func and callable(invalidate_cache_func):
        return invalidate_cache_func
    else:
        return None


def get_experiment_func(experiment_func, *args, **kwargs):  # type: ignore[no-untyped-def] # Function is missing a type annotation
    if (
        args
        and hasattr(args[0], "experiment_enabled")
        and callable(args[0].experiment_enabled)
    ):
        return args[0].experiment_enabled(*args, **kwargs)
    elif experiment_func and callable(experiment_func):
        return experiment_func()
    else:
        return None


def get_tag_keys(tag_key_func, *args, **kwargs):  # type: ignore[no-untyped-def] # Function is missing a type annotation
    if args and hasattr(args[0], "redis_tags") and callable(args[0].redis_tags):
        return args[0].redis_tags(*args, **kwargs)
    elif tag_key_func and callable(tag_key_func):
        return tag_key_func(*args, **kwargs)
    else:
        return None


def update_cache_by_key(redis_client, ttl, cache_key, resp, namespace, pod_name):  # type: ignore[no-untyped-def] # Function is missing a type annotation
    jitter_percent = random.uniform(-0.1, 0.1)
    ttl_with_jitter = int(ttl + (ttl * jitter_percent))
    try:
        redis_client.setex(cache_key, ttl_with_jitter, json.dumps(resp).encode("utf-8"))
        stats.increment(
            metric_name=CACHE_UPDATE_STATS,
            tags=[f"namespace:{namespace}"],
            pod_name=pod_name,
        )
    except Exception as e:
        log.warning(f"Failed to update cache response: {e}")
        stats.increment(
            metric_name=CACHE_RESPONSE_FAILURES,
            tags=[f"namespace:{namespace}", "reason:UPDATE_CACHE_FAILED"],
            pod_name=pod_name,
        )


def delete_keys_and_tags(redis_name, tags, namespace, pod_name):  # type: ignore[no-untyped-def] # Function is missing a type annotation
    if not tags:
        return
    try:
        for tag in tags:
            flask_redis.execute_script(
                script_name=INVALIDATE_WITH_TAG_SCRIPT,
                keys=[tag],
                client_name=redis_name,
                args=[],
            )
    except Exception as e:
        log.error(f"Got error {e} when delete tags {tags}")
        stats.increment(
            metric_name=INVALIDATE_RESPONSE_FAILURES,
            tags=[
                f"namespace:{namespace}",
                "reason:INVALIDATE_FAILURE",
            ],
            pod_name=pod_name,
        )


def cache_response(  # type: ignore[no-untyped-def] # Function is missing a type annotation
    cache_key_func=None,
    ttl=APPOINTMENT_DEFAULT_TTL,
    redis_name=APPOINTMENT_REDIS,
    pod_name=stats.PodNames.CARE_DISCOVERY,
    namespace=None,
    experiment_enabled=False,
    tags_func=None,
):
    """
    A redis backed cache decorator for flask resource usage.

    Example:

        class Foo(AuthenticatedResource):
           def redis_cache_key(self, *args, **kwargs):
               return f"{foo_resource}:{self.user.id}

           @cache_response(redis_name=bar_cache)
           def get(self, foo_id):
              ....

    redis_cache_key will be used to generate the cache key based on client implementation
    Args:
        tags_func: function to retrieve tags associated with the key
        cache_key_func: function to generate cache key
        ttl: base time to live for the entries inside redis cache, default to 2hrs, eventual ttl applied to cache
             entries will be in +-10% range of base ttl
        redis_name: the correct redis_client registered at flask app level
        For observability purpose:
        pod_name: owner team
        namespace: redis namespace name
        experiment_enabled: A bool or callable to determine whether experiment is enabled for the decorator user

    Returns: cached response in json format if there's cache hit, otherwise perform
             normal function call and cache the result

    """

    def decorator(f):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        @wraps(f)
        def decorated_function(*args, **kwargs):  # type: ignore[no-untyped-def] # Function is missing a type annotation
            enabled = get_experiment_func(experiment_enabled, *args, **kwargs)
            if not enabled:
                return f(*args, **kwargs)
            try:
                redis_client = flask.current_app.extensions["redis"].get_client(
                    name=redis_name
                )
            except KeyError:
                log.error(f"Redis client {redis_name} not found.")
                stats.increment(
                    metric_name=CACHE_RESPONSE_FAILURES,
                    tags=["reason:CLIENT_NAME_NOT_FOUND", f"namespace:{namespace}"],
                    pod_name=pod_name,
                )
                return f(*args, **kwargs)

            cache_key = get_cache_key(cache_key_func, *args, **kwargs)
            tags = get_tag_keys(tags_func, *args, **kwargs)
            if not cache_key:
                log.error(
                    "Resource does not have a cache_key function, no cache_key function found either"
                )
                stats.increment(
                    metric_name=CACHE_RESPONSE_FAILURES,
                    tags=[
                        f"namespace:{namespace}",
                        "reason: CACHE_KEY_FUNC_MISSING",
                    ],
                    pod_name=pod_name,
                )
                return f(*args, **kwargs)
            try:
                cached_resp = redis_client.get(cache_key)
                if cached_resp:
                    stats.increment(
                        metric_name=CACHE_HIT_STATS,
                        tags=[f"namespace:{namespace}"],
                        pod_name=pod_name,
                    )
                    return json.loads(cached_resp)
            except Exception as e:
                log.warning(
                    f"Got exception {e} while retrieve from cache", key=cache_key
                )
                stats.increment(
                    metric_name=CACHE_RESPONSE_FAILURES,
                    tags=[f"namespace:{namespace}", "reason:REDIS_GET_EXCEPTION"],
                    pod_name=pod_name,
                )

            stats.increment(
                metric_name=CACHE_MISS_STATS,
                tags=[f"namespace:{namespace}"],
                pod_name=pod_name,
            )
            try:
                resp = f(*args, **kwargs)
            except Exception as e:
                log.error(f"Error executing decorated function: {e}")
                stats.increment(
                    metric_name=CACHE_RESPONSE_FAILURES,
                    tags=[f"namespace:{namespace}", "reason:DECORATED_EXCEPTION"],
                    pod_name=pod_name,
                )
                raise e
            # We don't need to cache errors
            update_cache_by_key(redis_client, ttl, cache_key, resp, namespace, pod_name)
            # Adding tags if there are any
            if tags:
                for tag in tags:
                    try:
                        redis_client.sadd(tag, cache_key)
                    except Exception as e:
                        log.error(
                            f"Error {e} occurred when adding {cache_key} to {tag}"
                        )
                        stats.increment(
                            metric_name=CACHE_RESPONSE_FAILURES,
                            tags=[
                                f"namespace:{namespace}",
                                "reason:UPDATE_TAGS_FAILURE",
                            ],
                            pod_name=pod_name,
                        )
            return resp

        return decorated_function

    return decorator


def invalidate_cache(  # type: ignore[no-untyped-def] # Function is missing a type annotation
    cache_key_func=None,
    redis_name=APPOINTMENT_REDIS,
    invalidate_func=None,
    pod_name=stats.PodNames.CARE_DISCOVERY,
    namespace=None,
    experiment_enabled=False,
    tags_func=None,
):
    """
    Decorator for invalidate cache entries

    Example:
        class Foo(AuthenticatedResource):
           def invalidate_cache_func(self, *args, **kwargs):
               customized invalidate logic goes here

           @invalidate_cache(redis_name=APPOINTMENT_REDIS, namespace="appointments")
           def put(self, foo_id):

    If invalidate_cache_func is defined, this decorator will use it as the invalidate func, if not
    it will try to use the same cache_key_func defined for cache_response and the invalidate func will
    simply be redis.delete(cache_key)
    Args:
        tags_func: function to get tags associated with a given key
        cache_key_func: cache key generate function
        redis_name: redis client name
        invalidate_func: function to invalidate cache
        metric related parameters
        pod_name: owner team
        namespace: redis namespace
        experiment_enabled: Bool or Callable for client to do experiment switch

    Returns: result from decorated function

    """

    def decorator(f):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        @wraps(f)
        def wrapped(*args, **kwargs):  # type: ignore[no-untyped-def] # Function is missing a type annotation
            enabled = get_experiment_func(experiment_enabled, *args, **kwargs)
            if not enabled:
                return f(*args, **kwargs)
            result = f(*args, **kwargs)
            try:
                redis_client = flask.current_app.extensions["redis"].get_client(
                    name=redis_name
                )
            except KeyError:
                log.error(f"Redis client {redis_name} not found.")
                stats.increment(
                    metric_name=INVALIDATE_RESPONSE_FAILURES,
                    tags=["reason:CLIENT_NAME_NOT_FOUND", f"namespace:{namespace}"],
                    pod_name=pod_name,
                )
                return result
            invalidate_cache_func = get_invalidate_func(
                invalidate_func, *args, **kwargs
            )
            tags = get_tag_keys(tags_func, *args, **kwargs)

            # If client define custom invalidate function, use it otherwise fallback to invalidate the cache
            # using the same cache_key as cache decorator
            if invalidate_cache_func:
                if tags:
                    delete_keys_and_tags(
                        redis_name, tags, namespace=namespace, pod_name=pod_name
                    )
                else:
                    invalidate_cache_func(redis_client, *args, **kwargs)
            else:
                cache_key = get_cache_key(cache_key_func, *args, **kwargs)
                if not cache_key:
                    log.error(
                        "Resource does not have a cache_key function, no cache_key function found either"
                    )
                    stats.increment(
                        metric_name=INVALIDATE_RESPONSE_FAILURES,
                        tags=[
                            f"namespace:{namespace}",
                            "reason: CACHE_KEY_FUNC_MISSING",
                        ],
                        pod_name=pod_name,
                    )
                    return result
                if tags:
                    delete_keys_and_tags(
                        redis_name, tags, namespace=namespace, pod_name=pod_name
                    )
                else:
                    try:
                        redis_client.delete(cache_key)
                    except Exception as e:
                        log.error(
                            f"Failed to invalidate {cache_key} due to {e}",
                            exc_info=True,
                        )
                        stats.increment(
                            metric_name=INVALIDATE_RESPONSE_FAILURES,
                            tags=[
                                f"namespace:{namespace}",
                                "reason:INVALIDATE_FAILURE",
                            ],
                            pod_name=pod_name,
                        )
            return result

        return wrapped

    return decorator


def update_cache(  # type: ignore[no-untyped-def] # Function is missing a type annotation
    cache_key_func=None,
    ttl=APPOINTMENT_DEFAULT_TTL,
    redis_name=APPOINTMENT_REDIS,
    pod_name=stats.PodNames.CARE_DISCOVERY,
    namespace=None,
    experiment_enabled=False,
):
    """
    Decorator for update cache entries with value based on the decorated function

    Example:
        class Foo(AuthenticatedResource):
           def redis_cache_key(self, *args, **kwargs):
               return f"{foo_resource}:{self.user.id}

           @update_cache(redis_name=APPOINTMENT_REDIS, namespace="appointments")
           def put(self, foo_id):
    Args:
        cache_key_func: cache key generate function
        redis_name: redis client name
        metric related parameters
        pod_name: owner team
        namespace: redis namespace
        experiment_enabled: Bool or Callable for client to do experiment switch

    Returns: result from decorated function

    """

    def decorator(f):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        @wraps(f)
        def wrapped(*args, **kwargs):  # type: ignore[no-untyped-def] # Function is missing a type annotation
            enabled = get_experiment_func(experiment_enabled, *args, **kwargs)
            if not enabled:
                return f(*args, **kwargs)
            result = f(*args, **kwargs)
            try:
                redis_client = flask.current_app.extensions["redis"].get_client(
                    name=redis_name
                )
            except KeyError:
                log.error(f"Redis client {redis_name} not found.")
                stats.increment(
                    metric_name=INVALIDATE_RESPONSE_FAILURES,
                    tags=["reason:CLIENT_NAME_NOT_FOUND", f"namespace:{namespace}"],
                    pod_name=pod_name,
                )
                return result

            cache_key = get_cache_key(cache_key_func, *args, **kwargs)
            if not cache_key:
                log.error(
                    "Resource does not have a cache_key function, no cache_key function found either"
                )
                stats.increment(
                    metric_name=INVALIDATE_RESPONSE_FAILURES,
                    tags=[
                        f"namespace:{namespace}",
                        "reason: CACHE_KEY_FUNC_MISSING",
                    ],
                    pod_name=pod_name,
                )
                return result
            update_cache_by_key(
                redis_client, ttl, cache_key, result, namespace, pod_name
            )
            return result

        return wrapped

    return decorator
