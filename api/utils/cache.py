from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from typing import Any, List
from urllib import parse

import ddtrace
import redis
from redset.locks import Lock

from common import stats
from utils.log import logger

log = logger(__name__)
trace_wrapper = ddtrace.tracer.wrap(span_type=ddtrace.ext.SpanTypes.CACHE)

# ======= Default Redis DB Name Constants ==================
DEFAULT_REDIS_AUTH_STRING = os.environ.get("DEFAULT_CACHE_REDIS_AUTH_STRING", None)
DEFAULT_REDIS_HOST = os.environ.get("DEFAULT_CACHE_REDIS_HOST", None)
DEFAULT_REDIS_PORT = os.environ.get("DEFAULT_CACHE_REDIS_PORT", "6379")
DEFAULT_REDIS_PROXY_HOST = os.environ.get("DEFAULT_REDIS_PROXY_HOST", None)
DEFAULT_REDIS_PROXY_PORT = os.environ.get("DEFAULT_REDIS_PROXY_PORT", "6379")
DEFAULT_REDIS_CERT_FILE_PATH = os.environ.get(
    "DEFAULT_CACHE_REDIS_CERT_FILE_PATH", None
)
# ==================================================


def redis_client(
    redis_host: str | None = None,
    redis_port: int | None = None,
    redis_db: int | None = None,
    redis_url: str | None = None,
    decode_responses: bool = False,
    socket_timeout: float | None = None,
    skip_on_fatal_exceptions: bool = False,
    default_tags: List[str] | None = None,
    ignored_exceptions: List[Exception] | None = None,
    via_redis_proxy: bool = False,
) -> redis.Redis:
    if via_redis_proxy:
        if DEFAULT_REDIS_PROXY_HOST is None:
            raise Exception(
                "DEFAULT_REDIS_PROXY_HOST is not set when using redis proxy to connect to redis"
            )

        return ResilientRedis(
            host=DEFAULT_REDIS_PROXY_HOST,
            port=DEFAULT_REDIS_PROXY_PORT,
            db=0,
            decode_responses=None,
            socket_timeout=None,
            skip_on_fatal_exceptions=False,
            default_tags=None,
            ignored_exceptions=None,
        )

    if redis_host is None and redis_url is None and DEFAULT_REDIS_HOST is not None:
        return ResilientRedis(
            host=DEFAULT_REDIS_HOST,
            port=DEFAULT_REDIS_PORT,
            password=DEFAULT_REDIS_AUTH_STRING,
            ssl_ca_certs=DEFAULT_REDIS_CERT_FILE_PATH,
            ssl=True if DEFAULT_REDIS_CERT_FILE_PATH else False,
            db=0,
            decode_responses=decode_responses,
            socket_timeout=socket_timeout,
            skip_on_fatal_exceptions=skip_on_fatal_exceptions,
            default_tags=default_tags,
            ignored_exceptions=ignored_exceptions,
        )
    else:
        if redis_host is None and redis_url is None and DEFAULT_REDIS_HOST is None:
            log.warning("[redis_client] default redis MemoryStore is not configured")

        if redis_url is None:
            # mainly for unit test purposes going forward
            # before the self-hosted redis instance is removed, we can connect to it using redis_client("redis") call
            redis_url = os.environ.get("REDIS_URL", "redis://redis:6379/0")

        redis_url: parse.ParseResult = parse.urlparse(redis_url)  # type: ignore[no-redef] # Name "redis_url" already defined on line 32

        hostport: list[str] = redis_url.netloc.split(":", maxsplit=1)  # type: ignore[attr-defined] # "str" has no attribute "netloc"
        host: str = redis_host or str(hostport[0])
        port: int = redis_port or int(hostport[1])
        db: int = redis_db or int(redis_url.path.rsplit("/", maxsplit=1)[1])  # type: ignore[attr-defined] # "str" has no attribute "path"

        return ResilientRedis(
            host=host,
            port=port,
            db=db,
            decode_responses=decode_responses,
            socket_timeout=socket_timeout,
            skip_on_fatal_exceptions=skip_on_fatal_exceptions,
            default_tags=default_tags,
            ignored_exceptions=ignored_exceptions,
        )


class ResilientRedis(redis.Redis):
    def __init__(self, **kwargs):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        default_tags = kwargs.pop("default_tags", None)
        self._default_tags = [] if default_tags is None else [*default_tags]
        self._skip_on_fatal_exceptions = kwargs.pop("skip_on_fatal_exceptions", False)
        # for now, only default to ignore Redis connectivity exception
        ignored_exceptions = kwargs.pop("ignored_exceptions", None)
        self._ignored_exceptions = tuple(
            set(
                # UnboundLocalError emitted from ddtrace trace_utils_redis.py
                # the fix is in ddtrace 2.9.0. We can remove the UnboundLocalError from the list after the upgrade
                (
                    redis.exceptions.ConnectionError,
                    UnboundLocalError,
                )
                + tuple(ignored_exceptions if ignored_exceptions else [])
            )
        )
        super().__init__(**kwargs)

    def execute_command(self, *args, **options):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        try:
            return super().execute_command(*args, **options)
        except self._ignored_exceptions as ex:
            log.error(
                "Redis client encountered an issue when executing the command",
                exception=ex,
            )
            stats.increment(
                "mono.redis.error",
                pod_name=stats.PodNames.CORE_SERVICES,
                tags=[f"error:{type(ex).__name__}", *self._default_tags],
            )
            if self._skip_on_fatal_exceptions:
                # UnboundLocalError emitted from ddtrace trace_utils_redis.py
                # the fix is in ddtrace 2.9.0. We can remove the UnboundLocalError from the list after the upgrade
                if not isinstance(
                    ex, UnboundLocalError
                ) or "local variable 'result' referenced before assignment" in str(ex):
                    return None
            raise ex

    def pipeline(
        self, transaction: bool = True, shard_hint: Any = None
    ) -> ResilientPipeline:
        return ResilientPipeline(
            self.connection_pool,
            self.response_callbacks,
            transaction,
            shard_hint,
            skip_on_fatal_exceptions=self._skip_on_fatal_exceptions,
            ignored_exceptions=self._ignored_exceptions,
            default_tags=self._default_tags,
        )


class ResilientPipeline(redis.client.Pipeline):
    def __init__(self, *args, **kwargs):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        self._skip_on_fatal_exceptions = kwargs.pop("skip_on_fatal_exceptions", False)
        self._ignored_exceptions = kwargs.pop("ignored_exceptions", ())
        self._default_tags = kwargs.pop("default_tags", [])
        super().__init__(*args, **kwargs)

    def execute(self, raise_on_error: bool = True):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        try:
            return super().execute(raise_on_error)
        except self._ignored_exceptions as ex:
            log.error(
                "Redis pipeline encountered an issue when executing commands",
                exception=ex,
            )
            stats.increment(
                "mono.redis.pipeline.error",
                pod_name=stats.PodNames.CORE_SERVICES,
                tags=[f"error:{type(ex).__name__}", *self._default_tags],
            )
            if self._skip_on_fatal_exceptions:
                if not isinstance(
                    ex, UnboundLocalError
                ) or "local variable 'result' referenced before assignment" in str(ex):
                    return [None] * len(self.command_stack)
            raise ex


class RedisLock(Lock):
    def __init__(self, key, **kwargs):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        if "timeout" in kwargs and kwargs["timeout"] == 0:
            # This is a fix for a bug on the redset library
            # https://github.com/percolate/redset/issues/11
            kwargs["timeout"] = 0.1

        super().__init__(
            redis_client(),
            key,
            **kwargs,
        )


class ViewCache(object):
    ttl = 24 * 60 * 60
    id_attr = "id"
    id_namespace = None
    batch_size = 10_000

    def __init__(self, uri=None):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        self.id_namespace = self.id_namespace or self.__class__.__name__

        self.uri = uri
        self.redis = redis_client(
            skip_on_fatal_exceptions=True,
            default_tags=["caller:view_cache"],
        )

        self.all_uris_key = f"{self.id_namespace}_{self.__class__.__name__}_all_uris"

        self.invalidate_all_time_key = f"{self.id_namespace}:invalidate_all:time"

    @property
    def key(self):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        """
        Required for cache R/W operations but optional for invalidation operations
        """
        assert self.uri, "Need a URI to get a key!"
        return self.uri

    @trace_wrapper
    def get(self):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        log.debug("Getting: %s", self.key)
        res = self.redis.get(self.key)

        if res:
            return json.loads(res.decode("utf8"))

    @trace_wrapper
    def set(self, res):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        """
        res is an api response
        """
        pipeline = self.redis.pipeline()

        if isinstance(res, list):
            ids_present = [_.get(self.id_attr) for _ in res]
        elif "data" in res.keys() and "pagination" in res.keys():
            ids_present = [_.get(self.id_attr) for _ in res["data"]]
        else:
            ids_present = [res.get(self.id_attr)]

        for id in ids_present:
            pipeline.sadd(self._id_key(id), self.uri)

        log.debug("Setting %s for main key: %s", self.key, self.ttl)
        pipeline.setex(self.key, self.ttl, json.dumps(res))
        pipeline.sadd(self.all_uris_key, self.key)

        ret = pipeline.execute()
        return ret

    @trace_wrapper
    def invalidate_id(self, id):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        log.debug("Invalidating ID: %s", id)
        return self.invalidate_ids([id])

    @trace_wrapper
    def invalidate_ids(self, ids):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        log.debug("Invalidating IDs: %s", ids)
        pipeline = self.redis.pipeline()

        for id in ids:
            pipeline.smembers(self._id_key(id))

        # fetch individual uris so that we remove level 2 cache
        to_invalidate = []
        for members in pipeline.execute():
            if members:
                for member in members:
                    to_invalidate.append(member.decode("utf8"))

        # remove object id sets (level 1 ache)
        pipeline = self.redis.pipeline()
        if ids:
            pipeline.delete(*[self._id_key(id) for id in ids])
        if to_invalidate:
            pipeline.delete(*[uri for uri in to_invalidate])

        res = pipeline.execute()
        log.debug("Delete results: %s", res)
        return to_invalidate

    @trace_wrapper
    def invalidate_path_prefix(self, path):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        pattern = path + "*"
        pipeline = self.redis.pipeline()

        keys_to_delete = [
            key for key in self.redis.scan_iter(match=pattern, count=self.batch_size)
        ]
        if keys_to_delete:
            pipeline.delete(*keys_to_delete)
            pipeline.srem(self.all_uris_key, *keys_to_delete)

        return pipeline.execute()

    @trace_wrapper
    def invalidate_all(self) -> int:
        keys = [*self.all_uris()]
        numkeys = len(keys)
        # No-op, don't waste my time.
        if numkeys == 0:
            delete_count = 0
        # If it's significantly higher than our batch size, batch it.
        elif numkeys > (self.BATCH_SIZE + (self.BATCH_SIZE // 5)):
            with self.redis.pipeline(transaction=False) as pipe:
                for i in range(0, len(keys), self.BATCH_SIZE):
                    batch = keys[i : i + self.BATCH_SIZE]
                    pipe.delete(*batch)
                out = pipe.execute()
                delete_count = sum(out)
        else:
            # Otherwise, just do an atomic delete.
            delete_count = self.redis.delete(*keys)

        self.redis.set(
            self.invalidate_all_time_key, datetime.now(timezone.utc).isoformat()
        )
        return delete_count

    BATCH_SIZE = int(os.environ.get("CACHE_CLEAR_BATCH_SIZE", 500_000))

    @trace_wrapper
    def all_uris(self):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        return self.redis.smembers(self.all_uris_key)

    def _id_key(self, id):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        return f"{self.id_namespace}_view_cache_{id}"

    @property
    def last_invalidated_all(self) -> datetime:  # type: ignore[return] # Missing return statement
        try:
            value = self.redis.get(self.invalidate_all_time_key)
            if value:
                return datetime.fromisoformat(value.decode("utf8"))
        except Exception:
            log.error(
                f"Error getting redis value from key [{self.invalidate_all_time_key}]",
                exc_info=True,
            )
