import os
import time
from unittest import mock

import flask
import flask_restful
import pytest

from common.services import ratelimiting
from common.services.api import ExceptionAwareApi


@pytest.fixture
def mock_config():
    with mock.patch.dict(os.environ, RATE_LIMIT_MULTIPLIER="1"):
        yield


@pytest.fixture
def ratelimit(mock_config) -> ratelimiting.RateLimitManager:
    manager = ratelimiting.RateLimitManager(
        policy=ratelimiting.RateLimitPolicy(
            attempts=1,
            cooldown=1,
        ),
        scope=lambda: "scope",
        category=lambda: "category",
    )
    yield manager
    manager.redis.flushdb()


@pytest.fixture
def lockout(mock_config) -> ratelimiting.RateLimitManager:
    manager = ratelimiting.RateLimitManager(
        policy=ratelimiting.RateLimitPolicy(
            attempts=1,
            cooldown=1,
            reset_on_success=True,
        ),
        scope=lambda: "scope",
        category=lambda: "category",
    )
    yield manager
    manager.redis.flushdb()


class TestStandardRateLimiting:
    @staticmethod
    def test_set(ratelimit):
        # When
        ttl = ratelimit.set()
        count = int(ratelimit.redis.get(ratelimit.key()))
        # Then
        assert (ttl, count) == (ratelimit.policy.cooldown, 0)

    @staticmethod
    def test_set_override_key(ratelimit, faker):
        # Given
        key = faker.swift11()
        # When
        ttl = ratelimit.set(key=key)
        count = int(ratelimit.redis.get(key))
        # Then
        assert (ttl, count) == (ratelimit.policy.cooldown, 0)

    @staticmethod
    def test_set_override_ttl(ratelimit):
        # Given
        expected_ttl = 10
        # When
        ttl = ratelimit.set(ttl=expected_ttl)
        count = int(ratelimit.redis.get(ratelimit.key()))
        # Then
        assert (ttl, count) == (expected_ttl, 0)

    @staticmethod
    def test_extend(ratelimit):
        # Given
        given_ttl = ratelimit.set()
        work_time = 0.01
        # When
        time.sleep(work_time)
        ttl = ratelimit.extend()
        # Then
        assert given_ttl >= ttl > given_ttl - work_time

    @staticmethod
    def test_incr(ratelimit):
        # Given
        ratelimit.set()
        expected_remaining = ratelimit.policy.attempts - 1
        # When
        status = ratelimit.incr()
        # Then
        assert status.remaining == expected_remaining

    @staticmethod
    def test_incr_no_initial_value(ratelimit):
        # Given
        expected_remaining = ratelimit.policy.attempts - 1
        # When
        status = ratelimit.incr()
        # Then
        assert status.remaining == expected_remaining

    @staticmethod
    def test_incr_expired_key(ratelimit):
        # Given
        key = "test-key-1"
        ratelimit.redis.setex(name=key, time=1, value=100)
        # When
        time.sleep(1.1)
        ratelimit.incr(key=key)
        # Then
        assert ratelimit.redis.ttl(key) > 0

    @staticmethod
    def test_clear(ratelimit):
        # Given
        ratelimit.set()
        ratelimit.incr()
        # When
        ratelimit.clear()
        status = ratelimit.status()
        # Then
        assert status.remaining == ratelimit.policy.attempts

    @staticmethod
    def test_status_over_limit_raises(ratelimit):
        # Given
        ratelimit.set(count=ratelimit.policy.attempts + 1)
        # When/Then
        with pytest.raises(ratelimiting.RateLimitingError):
            ratelimit.status()

    @staticmethod
    def test_context_manager(ratelimit):
        # Given
        expected_remaining = ratelimit.policy.attempts - 1
        # When
        with ratelimit:
            pass

        status = ratelimit.status()
        # Then
        assert status.remaining == expected_remaining


class TestLockoutRateLimiting:
    @staticmethod
    def test_context_manager_on_success(lockout):
        # Given
        expected_remaining = lockout.policy.attempts
        # When
        with lockout:
            pass

        status = lockout.status()
        # Then
        assert status.remaining == expected_remaining

    @staticmethod
    def test_context_manager_on_error(lockout):
        # Given
        expected_remaining = lockout.policy.attempts - 1
        # When
        try:
            with lockout:
                raise Exception("BOOM")
        except Exception:
            pass

        status = lockout.status()
        # Then
        assert status.remaining == expected_remaining


class TestFlaskHelpers:
    @staticmethod
    @pytest.fixture
    def mock_flask():
        with mock.patch.object(ratelimiting, "flask") as f:
            yield f

    @staticmethod
    @pytest.fixture
    def mock_request(mock_flask):
        mock_flask.request.headers = {}
        return mock_flask.request

    @staticmethod
    @pytest.fixture
    def mock_g(mock_flask):
        return mock_flask.g

    @staticmethod
    @pytest.mark.parametrize(
        argnames="header", argvalues=["X-Real-IP", "X-Forwarded-For"]
    )
    def test_get_client_ip(
        faker,
        mock_request,
        header,
    ):
        # Given
        expected_ip_address = faker.ipv4()
        mock_request.headers[header] = expected_ip_address
        # When
        client_ip = ratelimiting.get_client_ip()
        # Then
        assert client_ip == expected_ip_address

    @staticmethod
    def test_get_request_endpoint(faker, mock_request):
        # Given
        expected_endpoint = faker.uri_path()
        mock_request.endpoint = expected_endpoint
        # When
        request_endpoint = ratelimiting.get_request_endpoint()
        # Then
        assert request_endpoint == expected_endpoint

    @staticmethod
    def test_get_set_ratelimit_status(mock_g):
        # Given
        expected_status = ratelimiting.RateLimitStatus(
            remaining=10,
            limit=10,
            reset=0,
            send_x_headers=True,
            key="key",
        )
        # When
        ratelimiting.set_ratelimit_status(expected_status)
        status = ratelimiting.get_ratelimit_status()
        # Then
        assert status == expected_status


class TestFunctionalAPI:
    @staticmethod
    def decorated_function(faker, ratelimit):
        # When
        @ratelimiting.ratelimited(limit=ratelimit)
        def myfunc():
            return faker.bs()

        # Then
        assert myfunc.ratelimit is ratelimit

    @staticmethod
    def decorated_function_call_under_limit(faker, ratelimit):
        # Given
        @ratelimiting.ratelimited(limit=ratelimit)
        def myfunc():
            return faker.bs()

        expected_remaining = ratelimit.policy.attempts - 1
        # When
        myfunc()
        status = myfunc.ratelimit.status()
        # Then
        assert status.remaining == expected_remaining

    @staticmethod
    def decorated_function_call_over_limit(faker, ratelimit):
        # Given
        @ratelimiting.ratelimited(limit=ratelimit)
        def myfunc():
            return faker.bs()

        # When/Then
        with pytest.raises(ratelimiting.RateLimitingError):
            for _ in range(ratelimit.policy.attempts + 1):
                myfunc()


class TestRatelimitedEndpoint:
    @staticmethod
    @pytest.fixture
    def api(ratelimit, faker):
        app = flask.Flask("ratelimit-test")
        app.after_request(ratelimiting.inject_x_rate_headers)

        class BSResource(flask_restful.Resource):
            @ratelimiting.ratelimited(limit=ratelimit)
            def get(self):
                return {"bs": faker.bs()}

        api = ExceptionAwareApi(app)
        api.add_resource(BSResource, "/bs")

        with api.app.app_context():
            yield api

    @staticmethod
    @pytest.fixture
    def client(api):
        with api.app.test_client() as client:
            yield client

    @staticmethod
    def test_successful(client, ratelimit):
        # Given
        expected_response_code = 200
        expected_response_headers = {
            "X-RateLimit-Remaining": str(ratelimit.policy.attempts - 1),
            "X-RateLimit-Limit": str(ratelimit.policy.attempts),
            "X-RateLimit-Reset": str(ratelimit.policy.cooldown),
        }
        # When
        response: flask.Response = client.get("/bs")
        headers = {h: response.headers.get(h) for h in expected_response_headers}
        # Then
        assert response.status_code == expected_response_code
        assert headers == expected_response_headers

    @staticmethod
    def test_ratelimited(client, ratelimit):
        # Given
        expected_response_code = 429
        expected_response_headers = {
            "X-RateLimit-Remaining": "0",
            "X-RateLimit-Limit": str(ratelimit.policy.attempts),
            "X-RateLimit-Reset": str(ratelimit.policy.cooldown),
        }
        tries = ratelimit.policy.attempts
        # When
        response: flask.Response = client.get("/bs")
        headers = {h: response.headers.get(h) for h in expected_response_headers}
        for _ in range(tries):
            response = client.get("/bs")
            headers = {h: response.headers.get(h) for h in expected_response_headers}

        # Then
        assert response.status_code == expected_response_code
        assert headers == expected_response_headers
