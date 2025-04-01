from unittest.mock import MagicMock, Mock, patch

import pytest

from appointments.utils.flask_redis_ext import (
    APPOINTMENT_REDIS,
    FlaskRedis,
    cache_response,
)


@pytest.fixture
def app_with_redis(app, monkeypatch):
    mock_redis_client = Mock()
    redis_extension = FlaskRedis(app)
    monkeypatch.setattr("redis.Redis.get", mock_redis_client.get)
    monkeypatch.setattr("redis.Redis.setex", mock_redis_client.setex)
    redis_extension._redis_clients[APPOINTMENT_REDIS] = mock_redis_client
    return app


@pytest.fixture
def redis_extension(app):
    redis_extension = FlaskRedis(app)
    redis_extension._redis_clients[APPOINTMENT_REDIS] = Mock()
    return redis_extension


class TestCache:
    def test_cache_hit_decorator(self, app_with_redis, monkeypatch):
        monkeypatch.setattr("json.loads", lambda x: {"data": "cached"})
        monkeypatch.setattr("json.dumps", lambda x: '{"data": "cached"}')
        with app_with_redis.app_context():

            @cache_response(
                cache_key_func=lambda x: "test:123", experiment_enabled=lambda: True
            )
            def fetch(data_id):
                return {"data": "not cached"}

        response = fetch(123)
        assert response == {"data": "cached"}

    def test_cache_miss_and_set(self, app_with_redis, monkeypatch):
        redis_client = app_with_redis.extensions["redis"].get_client(
            name="appointment_redis"
        )
        redis_client.get.return_value = None
        monkeypatch.setattr("json.dumps", lambda x: '{"data": "fresh"}')

        with app_with_redis.app_context():

            @cache_response(
                cache_key_func=lambda x: "test:123", experiment_enabled=lambda: True
            )
            def fetch(data_id):
                return {"data": "fresh"}

            resp = fetch(123)
            assert resp == {"data": "fresh"}
            assert redis_client.setex.called

    def test_redis_get_exception(self, app_with_redis, logs):
        redis_client = app_with_redis.extensions["redis"].get_client(
            name="appointment_redis"
        )
        redis_client.get.side_effect = Exception("redis connection error")

        @cache_response(
            cache_key_func=lambda x: "test:456", experiment_enabled=lambda: True
        )
        def fetch(data_id):
            return {"data": "fresh data"}

        fetch(456)
        event = next((r for r in logs if "redis connection error" in r["event"]), None)
        assert event is not None

    def test_decorated_function_exception(self, monkeypatch, logs):
        monkeypatch.setattr("redis.Redis.get", MagicMock(return_value=None))
        error_msg = "Error within decorated function"

        @cache_response(
            cache_key_func=lambda x: "test:123", experiment_enabled=lambda: True
        )
        def error_prone_function(data_id):
            raise ValueError(error_msg)

        with pytest.raises(ValueError):
            error_prone_function(123)

        event = next((r for r in logs if error_msg in r["event"]), None)
        assert event is not None

    def test_register_script(self, redis_extension):
        with patch("redis.Redis") as mock_redis:
            mock_redis = redis_extension.get_client("appointment_redis")
            mock_redis.script_load.return_value = "sha1-hash"
            sha1 = redis_extension.register_lua_script(
                "return redis.call('ping')", "test_script", "appointment_redis"
            )
            assert sha1 == "sha1-hash"
            mock_redis.script_load.assert_called_once_with("return redis.call('ping')")

    def test_execute_script(self, redis_extension):
        with patch("redis.Redis") as mock_redis:
            redis_extension._redis_clients["default"] = mock_redis
            mock_redis.evalsha.return_value = "PONG"
            redis_extension._script_hashes["default"]["test"] = "sha1-hash"
            result = redis_extension.execute_script(
                "test", keys=["keys"], args=["value"], client_name="default"
            )
            assert result == "PONG"
            mock_redis.evalsha.assert_called_once_with("sha1-hash", 1, "keys", "value")
