from unittest import mock

import pytest
from redis.exceptions import ConnectionError, TimeoutError

from utils import cache
from utils.cache import ResilientPipeline


class MySuperViewCache(cache.ViewCache):
    id_namespace = "super_view_cache"


@pytest.fixture
def view_cache():
    cache = MySuperViewCache(uri="super/view/")
    yield cache
    keys = cache.redis.keys(cache.id_namespace + "*")
    if keys:
        cache.redis.delete(*keys)


class TestInvalidateAll:
    @staticmethod
    def test_no_op(view_cache):
        # When
        invalidated = view_cache.invalidate_all()
        # Then
        assert invalidated == 0

    @staticmethod
    def test_atomic(view_cache, faker):
        # Given
        uris = [faker.swift11() for _ in range(16)]
        objects = [faker.bs()]
        for uri in uris:
            view_cache.redis.sadd(uri, *objects)
        view_cache.redis.sadd(view_cache.all_uris_key, *uris)
        # When
        invalidated = view_cache.invalidate_all()
        # Then
        assert invalidated == len(uris)

    @staticmethod
    def test_batched(view_cache, faker):
        # Given
        uris = [faker.swift11() for _ in range(16)]
        objects = [faker.bs()]
        for uri in uris:
            view_cache.redis.sadd(uri, *objects)
        view_cache.redis.sadd(view_cache.all_uris_key, *uris)
        view_cache.BATCH_SIZE = 10
        # When
        invalidated = view_cache.invalidate_all()
        # Then
        assert invalidated == len(uris)


class TestResilientRedis:
    @staticmethod
    @mock.patch("redis.Redis.execute_command")
    def test_normal_redis_operations_no_exception_handling(mock_redis_execute):
        # Given
        cache_key = "dummy_key"
        set_key = "dummy_set"
        mock_redis_execute.side_effect = [
            "ok",  # get
            1,  # delete
            True,  # expire
            "OK",  # set
            1,  # sadd
            True,  # sismember
        ]
        redis_client = cache.redis_client()

        value = redis_client.get(cache_key)
        assert value == "ok"

        deleted = redis_client.delete(cache_key)
        assert deleted == 1

        expired = redis_client.expire(cache_key, 3600)
        assert expired is True

        set_result = redis_client.set(cache_key, "new_value")
        assert set_result == "OK"

        added = redis_client.sadd(set_key, "member1")
        assert added == 1

        is_member = redis_client.sismember(set_key, "member1")
        assert is_member is True

        assert mock_redis_execute.call_count == 6

    @staticmethod
    @mock.patch("redis.client.Pipeline.execute")
    def test_redis_pipeline_operations_no_exception_handling(mock_pipeline_execute):
        # Given
        cache_key = "dummy_key"
        set_key = "dummy_set"
        mock_pipeline_execute.return_value = ["ok", 1, True, "OK", 1, True]

        redis_client = cache.redis_client()

        # When using pipeline
        pipeline = redis_client.pipeline()
        pipeline.get(cache_key)
        pipeline.delete(cache_key)
        pipeline.expire(cache_key, 3600)
        pipeline.set(cache_key, "new_value")
        pipeline.sadd(set_key, "member1")
        pipeline.sismember(set_key, "member1")
        results = pipeline.execute()

        # Then
        assert results == ["ok", 1, True, "OK", 1, True]
        assert mock_pipeline_execute.call_count == 1

    @staticmethod
    @mock.patch("redis.Redis.execute_command")
    def test_redis_operations_raise_without_exception_handling(mock_redis_execute):
        # Given
        cache_key = "dummy_key"
        set_key = "dummy_set"
        mock_redis_execute.side_effect = ConnectionError(
            "Error 111 connecting to redis:6379. Connection refused."
        )
        redis_client = cache.redis_client()

        with pytest.raises(
            ConnectionError,
            match="Error 111 connecting to redis:6379. Connection refused.",
        ):
            redis_client.get(cache_key)

        with pytest.raises(
            ConnectionError,
            match="Error 111 connecting to redis:6379. Connection refused.",
        ):
            redis_client.delete(cache_key)

        with pytest.raises(
            ConnectionError,
            match="Error 111 connecting to redis:6379. Connection refused.",
        ):
            redis_client.expire(cache_key, 3600)

        with pytest.raises(
            ConnectionError,
            match="Error 111 connecting to redis:6379. Connection refused.",
        ):
            redis_client.set(cache_key, "new_value")

        with pytest.raises(
            ConnectionError,
            match="Error 111 connecting to redis:6379. Connection refused.",
        ):
            redis_client.sadd(set_key, "member1")

        with pytest.raises(
            ConnectionError,
            match="Error 111 connecting to redis:6379. Connection refused.",
        ):
            redis_client.sismember(set_key, "member1")

    @staticmethod
    @mock.patch("redis.client.Pipeline.execute")
    def test_redis_pipeline_operations_raise_without_exception_handling(
        mock_pipeline_execute,
    ):
        # Given
        cache_key = "dummy_key"
        set_key = "dummy_set"
        mock_pipeline_execute.side_effect = ConnectionError(
            "Error 111 connecting to redis:6379. Connection refused."
        )
        redis_client = cache.redis_client()

        # When using pipeline
        pipeline = redis_client.pipeline()
        pipeline.get(cache_key)
        pipeline.delete(cache_key)
        pipeline.expire(cache_key, 3600)
        pipeline.set(cache_key, "new_value")
        pipeline.sadd(set_key, "member1")
        pipeline.sismember(set_key, "member1")

        # Then
        with pytest.raises(
            ConnectionError,
            match="Error 111 connecting to redis:6379. Connection refused.",
        ):
            pipeline.execute()

    @staticmethod
    @mock.patch("redis.Redis.execute_command")
    def test_resilient_client_normal_operations(mock_redis_execute):
        # Given
        cache_key = "dummy_key"
        set_key = "dummy_set"
        mock_redis_execute.side_effect = [
            "ok",  # get
            1,  # delete
            True,  # expire
            "OK",  # set
            1,  # sadd
            True,  # sismember
        ]
        redis_client = cache.redis_client(
            skip_on_fatal_exceptions=True, default_tags=["caller:unit_test"]
        )

        value = redis_client.get(cache_key)
        assert value == "ok"

        deleted = redis_client.delete(cache_key)
        assert deleted == 1

        expired = redis_client.expire(cache_key, 3600)
        assert expired is True

        set_result = redis_client.set(cache_key, "new_value")
        assert set_result == "OK"

        added = redis_client.sadd(set_key, "member1")
        assert added == 1

        is_member = redis_client.sismember(set_key, "member1")
        assert is_member is True

        assert mock_redis_execute.call_count == 6

    @staticmethod
    @mock.patch("redis.Redis.execute_command")
    def test_resilient_client_operations_no_raise(mock_redis_execute):
        cache_key = "dummy_key"
        set_key = "dummy_set"
        mock_redis_execute.side_effect = ConnectionError(
            "Error 111 connecting to redis:6379. Connection refused."
        )
        redis_client = cache.redis_client(
            skip_on_fatal_exceptions=True, default_tags=["caller:unit_test"]
        )

        value = redis_client.get(cache_key)
        assert value is None

        deleted = redis_client.delete(cache_key)
        assert deleted is None

        expired = redis_client.expire(cache_key, 3600)
        assert expired is None

        set_result = redis_client.set(cache_key, "new_value")
        assert set_result is None

        added = redis_client.sadd(set_key, "member1")
        assert added is None

        is_member = redis_client.sismember(set_key, "member1")
        assert is_member is None

        assert mock_redis_execute.call_count == 6

    @staticmethod
    @mock.patch("redis.client.Pipeline.execute")
    def test_redis_pipeline_operations_no_raise_exception(mock_pipeline_execute):
        # Given
        cache_key = "dummy_key"
        set_key = "dummy_set"
        mock_pipeline_execute.side_effect = ConnectionError(
            "Error 111 connecting to redis:6379. Connection refused."
        )
        redis_client = cache.redis_client(
            skip_on_fatal_exceptions=True, default_tags=["caller:unit_test"]
        )

        # When using pipeline
        pipeline = redis_client.pipeline()
        pipeline.get(cache_key)
        pipeline.delete(cache_key)
        pipeline.expire(cache_key, 3600)
        pipeline.set(cache_key, "new_value")
        pipeline.sadd(set_key, "member1")
        pipeline.sismember(set_key, "member1")

        # Then
        results = pipeline.execute()
        assert results == [None, None, None, None, None, None]

    @staticmethod
    @mock.patch("redis.Redis.execute_command")
    def test_resilient_client_raises_on_non_ignored_exceptions(mock_redis_execute):
        # Given
        cache_key = "dummy_key"
        set_key = "dummy_set"
        mock_redis_execute.side_effect = TimeoutError("Timeout")
        redis_client = cache.redis_client(
            skip_on_fatal_exceptions=True, default_tags=["caller:unit_test"]
        )

        with pytest.raises(TimeoutError, match="Timeout"):
            redis_client.get(cache_key)

        with pytest.raises(TimeoutError, match="Timeout"):
            redis_client.delete(cache_key)

        with pytest.raises(TimeoutError, match="Timeout"):
            redis_client.expire(cache_key, 3600)

        with pytest.raises(TimeoutError, match="Timeout"):
            redis_client.set(cache_key, "value")

        with pytest.raises(TimeoutError, match="Timeout"):
            redis_client.sadd(set_key, "member1")

        with pytest.raises(TimeoutError, match="Timeout"):
            redis_client.sismember(set_key, "member1")

        assert mock_redis_execute.call_count == 6

    @staticmethod
    @mock.patch("redis.client.Pipeline.execute")
    def test_redis_pipeline_operations_raise_non_ignored_exceptions(
        mock_pipeline_execute,
    ):
        # Given
        cache_key = "dummy_key"
        set_key = "dummy_set"
        mock_pipeline_execute.side_effect = TimeoutError("Timeout")
        redis_client = cache.redis_client(
            skip_on_fatal_exceptions=True, default_tags=["caller:unit_test"]
        )

        # When using pipeline
        pipeline = redis_client.pipeline()
        pipeline.get(cache_key)
        pipeline.delete(cache_key)
        pipeline.expire(cache_key, 3600)
        pipeline.set(cache_key, "new_value")
        pipeline.sadd(set_key, "member1")
        pipeline.sismember(set_key, "member1")

        # Then
        with pytest.raises(
            TimeoutError,
            match="Timeout",
        ):
            pipeline.execute()

    @staticmethod
    @mock.patch("redis.Redis.execute_command")
    def test_resilient_client_operations_no_raise_unbound_local_exception(
        mock_redis_execute,
    ):
        # Given
        cache_key = "dummy_key"
        set_key = "dummy_set"
        mock_redis_execute.side_effect = [
            UnboundLocalError("local variable 'result' referenced before assignment")
        ] * 6  # Set side effect for all 6 operations
        redis_client = cache.redis_client(
            skip_on_fatal_exceptions=True, default_tags=["caller:unit_test"]
        )

        value = redis_client.get(cache_key)
        assert value is None

        deleted = redis_client.delete(cache_key)
        assert deleted is None

        expired = redis_client.expire(cache_key, 3600)
        assert expired is None

        set_result = redis_client.set(cache_key, "new_value")
        assert set_result is None

        added = redis_client.sadd(set_key, "member1")
        assert added is None

        is_member = redis_client.sismember(set_key, "member1")
        assert is_member is None

        assert mock_redis_execute.call_count == 6

    @staticmethod
    @mock.patch("redis.client.Pipeline.execute")
    def test_redis_pipeline_operations_raise_non_unbound_local_exceptions(
        mock_pipeline_execute,
    ):
        # Given
        cache_key = "dummy_key"
        set_key = "dummy_set"
        mock_pipeline_execute.side_effect = UnboundLocalError(
            "local variable 'result' referenced before assignment"
        )
        redis_client = cache.redis_client(
            skip_on_fatal_exceptions=True, default_tags=["caller:unit_test"]
        )

        # When using pipeline
        pipeline = redis_client.pipeline()
        pipeline.get(cache_key)
        pipeline.delete(cache_key)
        pipeline.expire(cache_key, 3600)
        pipeline.set(cache_key, "new_value")
        pipeline.sadd(set_key, "member1")
        pipeline.sismember(set_key, "member1")

        # Then
        results = pipeline.execute()
        assert results == [None, None, None, None, None, None]

    @staticmethod
    @mock.patch("redis.Redis.execute_command")
    def test_resilient_client_operations_raise_unbound_local_exception_different_message(
        mock_redis_execute,
    ):
        # Given
        cache_key = "dummy_key"
        set_key = "dummy_set"
        mock_redis_execute.side_effect = [
            UnboundLocalError("dummy")
        ] * 6  # For all 6 operations
        redis_client = cache.redis_client(
            skip_on_fatal_exceptions=True, default_tags=["caller:unit_test"]
        )

        # When/Then
        with pytest.raises(UnboundLocalError, match="dummy"):
            redis_client.get(cache_key)

        with pytest.raises(UnboundLocalError, match="dummy"):
            redis_client.delete(cache_key)

        with pytest.raises(UnboundLocalError, match="dummy"):
            redis_client.expire(cache_key, 3600)

        with pytest.raises(UnboundLocalError, match="dummy"):
            redis_client.set(cache_key, "new_value")

        with pytest.raises(UnboundLocalError, match="dummy"):
            redis_client.sadd(set_key, "member1")

        with pytest.raises(UnboundLocalError, match="dummy"):
            redis_client.sismember(set_key, "member1")

        assert mock_redis_execute.call_count == 6

    @staticmethod
    @mock.patch("redis.client.Pipeline.execute")
    def test_redis_pipeline_operations_raise_non_unbound_local_different_message_exceptions(
        mock_pipeline_execute,
    ):
        # Given
        cache_key = "dummy_key"
        set_key = "dummy_set"
        mock_pipeline_execute.side_effect = UnboundLocalError("dummy")
        redis_client = cache.redis_client(
            skip_on_fatal_exceptions=True, default_tags=["caller:unit_test"]
        )

        # When using pipeline
        pipeline = redis_client.pipeline()
        pipeline.get(cache_key)
        pipeline.delete(cache_key)
        pipeline.expire(cache_key, 3600)
        pipeline.set(cache_key, "new_value")
        pipeline.sadd(set_key, "member1")
        pipeline.sismember(set_key, "member1")

        # Then
        with pytest.raises(UnboundLocalError, match="dummy"):
            pipeline.execute()

    def test_pipeline_returns_resilient_pipeline(self):
        redis_client = cache.redis_client()
        pipeline = redis_client.pipeline()
        assert isinstance(pipeline, ResilientPipeline)
