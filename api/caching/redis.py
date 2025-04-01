from datetime import timedelta
from functools import wraps
from json import JSONDecodeError
from typing import List, Optional, Type, TypeVar

import ddtrace
import redis
from rq.serializers import DefaultSerializer, JSONSerializer

from common import stats
from utils.cache import redis_client
from utils.log import logger

log = logger(__name__)
span = ddtrace.tracer.wrap(span_type="cache")


def get_redis_client() -> redis.Redis:
    return redis_client()


T = TypeVar("T")
K = TypeVar("K")

METRIC_PREFIX = "api.redis_ttl_cache"
_DEFAULT_REDUCED_SAMPLE_RATE = 0.1


class RedisTTLCache:
    def __init__(
        self,
        namespace: str,
        ttl_in_seconds: int,
        client: redis.Redis = None,  # type: ignore[assignment] # Incompatible default for argument "client" (default has type "None", argument has type "Redis[Any]")
        serializer: Optional[
            Type[DefaultSerializer]
        ] = JSONSerializer(),  # noqa  B008  TODO:  Do not perform function calls in argument defaults.  The call is performed only once at function definition time. All calls to your function will reuse the result of that definition-time function call.  If this is intended, assign the function call to a module-level variable and use that variable as a default value.
        pod_name: stats.PodNames = stats.PodNames.TEST_POD,
    ):
        self._namespace = namespace
        self._ttl_in_seconds = ttl_in_seconds
        self._client = client
        self._serializer = serializer
        self.pod_name = pod_name

    def get_client(self):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        if self._client is None:
            self._client = get_redis_client()

        return self._client

    @span
    def add(self, key: K, value: T):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        """
        Add a value to the cache with the given key. Note that the value must
        be serializable as JSON.

        raises TypeError if value is not serializable
        """
        try:
            self._increment_metric("add", sample_rate=_DEFAULT_REDUCED_SAMPLE_RATE)
            serialized = self._serializer.dumps(value)  # type: ignore[union-attr] # Item "None" of "Optional[Type[Any]]" has no attribute "dumps"
            self.get_client().setex(
                self._get_namespaced_key(key),
                timedelta(seconds=self._ttl_in_seconds),
                value=serialized,
            )
        except TypeError as e:
            log.error("Error encoding value", exception=e, key=key)
            self._increment_metric("add.error", tags=["error_type:serialization"])
            raise e
        except redis.RedisError as e:
            log.error("Error storing value in redis", exception=e, key=key)
            self._increment_metric("add.error", tags=["error_type:redis"])
        except Exception as e:
            log.error("Error storing value in redis", exception=e, key=key)
            self._increment_metric("add.error", tags=["error_type:other"])

    @span
    def get(self, key: K) -> T:  # type: ignore[return,type-var] # Missing return statement #type: ignore[type-var] # A function returning TypeVar should receive at least one argument containing the same TypeVar #type: ignore[type-var] # A function returning TypeVar should receive at least one argument containing the same TypeVar
        try:
            self._increment_metric("get", sample_rate=_DEFAULT_REDUCED_SAMPLE_RATE)
            value = self.get_client().get(self._get_namespaced_key(key))

            if value is not None:
                self._increment_metric("get.hit")
                return self._serializer.loads(value)  # type: ignore[union-attr] # Item "None" of "Optional[Type[Any]]" has no attribute "loads"
        except redis.RedisError as e:
            log.error("Error retrieving value from redis", exception=e, key=key)
            self._increment_metric("get.error", tags=["error_type:redis"])
        except JSONDecodeError as e:
            log.error("Error decoding cached value", exception=e, key=key)
            self._increment_metric("get.error", tags=["error_type:deserialization"])
        except Exception as e:
            log.error("Error retrieving value from redis", exception=e, key=key)
            self._increment_metric("get.error", tags=["error_type:other"])

    def _get_namespaced_key(self, key: K):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        return f"{self._namespace}:{key}"

    def _increment_metric(  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        self, metric_suffix: str, tags: List[str] = None, sample_rate: float = 1  # type: ignore[assignment] # Incompatible default for argument "tags" (default has type "None", argument has type "List[str]")
    ):
        namespace_tag = f"namespace:{self._namespace}"
        if tags is None:
            tags = [namespace_tag]
        else:
            tags.append(namespace_tag)

        metric_name = f"{METRIC_PREFIX}.{metric_suffix}"
        stats.increment(
            metric_name=metric_name,
            pod_name=self.pod_name,
            tags=tags,
            sample_rate=sample_rate,
        )


class RedisTTLCacheManager:
    def ttl_cache(  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        self,
        namespace: str,
        ttl_in_seconds: int,
        pod_name: stats.PodNames = stats.PodNames.TEST_POD,
    ):
        """
        Cache the result of a function call in Redis with a given TTL

        The wrapped function must have just one positional string argument
        (to be used as part of the cache key)

        Addtionally, the return value of the function must be serializable as JSON
        (e.g. string, number, boolean, dict, list of objects with primitive data types)

        Examples:
            >>> @redis_cache_manager.ttl_cache(namespace="expensive_operation", ttl_in_seconds=60)
            >>> def get_expensive_operation_result(input_value: str)
            >>>     # Something expensive
            >>>     return 123
        """

        def decorator(func):  # type: ignore[no-untyped-def] # Function is missing a type annotation
            @wraps(func)
            def wrapper(*args, **kwargs):  # type: ignore[no-untyped-def] # Function is missing a type annotation
                if len(args) != 1 or not isinstance(args[0], str):
                    log.warning(
                        "redis_ttl_cache must wrap method with one str argument"
                    )
                    return func(*args, **kwargs)

                key = args[0]

                cache = RedisTTLCache(
                    namespace=namespace,
                    ttl_in_seconds=ttl_in_seconds,
                    pod_name=pod_name,
                )
                cached = cache.get(key)

                if cached is not None:
                    return cached

                value = func(*args, **kwargs)
                cache.add(key, value)

                return value

            return wrapper

        return decorator


redis_cache_manager = RedisTTLCacheManager()
