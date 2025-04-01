import json
from contextlib import nullcontext as does_not_raise
from datetime import timedelta
from json import JSONDecodeError

import pytest
import redis

from caching.redis import RedisTTLCache

NAMESPACE = "namespace"
TTL_IN_SECONDS = 123


@pytest.fixture()
def fake_ttl_cache(mock_redis_client):
    return RedisTTLCache(NAMESPACE, TTL_IN_SECONDS, mock_redis_client)


def test_ttl_cache_add_calls_setex(mock_redis_client, fake_ttl_cache):
    value = {"a": "b"}

    fake_ttl_cache.add("key", value)

    mock_redis_client.setex.assert_called_with(
        "namespace:key",
        timedelta(seconds=TTL_IN_SECONDS),
        value=json.dumps(value).encode("utf-8"),
    )


def test_ttl_cache_get_deserializes_value(mock_redis_client, fake_ttl_cache):
    value = {"a": "b", "c": {"d": 123}}

    mock_redis_client.get.return_value = json.dumps(value).encode("utf-8")

    result = fake_ttl_cache.get("key")

    mock_redis_client.get.assert_called_with("namespace:key")

    assert result == value


@pytest.mark.parametrize(
    argnames="exception_to_raise",
    argvalues=[
        (redis.RedisError()),
        (Exception()),
    ],
)
def test_ttl_cache_add_suppresses_exceptions(
    mock_redis_client, fake_ttl_cache, exception_to_raise
):
    mock_redis_client.setex.side_effect = exception_to_raise

    with does_not_raise():
        fake_ttl_cache.add("key", {"a": "b"})


@pytest.mark.parametrize(
    argnames="exception_to_raise",
    argvalues=[
        (redis.RedisError()),
        (JSONDecodeError(msg="Fake Error", doc="Fake Doc", pos=0)),
        (Exception()),
    ],
)
def test_ttl_cache_get_suppresses_exceptions(
    mock_redis_client, fake_ttl_cache, exception_to_raise
):
    mock_redis_client.get.side_effect = exception_to_raise

    with does_not_raise():
        result = fake_ttl_cache.get("key")

    assert result is None
