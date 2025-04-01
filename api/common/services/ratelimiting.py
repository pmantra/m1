from __future__ import annotations

import dataclasses
import functools
import os
from typing import Callable, TypeVar

import flask
import redis

from utils import cache, log

_T = TypeVar("_T", bound=Callable)
logger = log.logger(__name__)


# THIS PACKAGE WILL SOON BE DEPRECATED. DO NOT CALL NEW INSTANCES OF THIS PACKAGE
#
# PLEASE SEE https://www.notion.so/mavenclinic/Cloud-Armor-Rate-Limiting-11515ef5a6478097a0dcca70efd9076c FOR OUR NEW RATE LIMITING SYSTEM.


# region: functional api


def ratelimited(
    view: _T = None,  # type: ignore[assignment] # Incompatible default for argument "view" (default has type "None", argument has type "_T")
    *,
    limit: RateLimitManager = None,  # type: ignore[assignment] # Incompatible default for argument "limit" (default has type "None", argument has type "RateLimitManager")
    attempts: int = 30_000,
    cooldown: int = 300,
    send_x_headers: bool = True,
    reset_on_success: bool = False,
    scope: Callable[[], str] = None,  # type: ignore[assignment] # Incompatible default for argument "scope" (default has type "None", argument has type "Callable[[], str]")
    category: Callable[[], str] = None,  # type: ignore[assignment] # Incompatible default for argument "category" (default has type "None", argument has type "Callable[[], str]")
) -> _T:
    """A decorator which will track the current state of a rate-limit for a function."""

    def ratelimit_decorator(caller: Callable):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        manager = limit or ratelimit(
            attempts=attempts,
            cooldown=cooldown,
            send_x_headers=send_x_headers,
            reset_on_success=reset_on_success,
            scope=scope,
            category=category,
        )
        caller.ratelimit = manager  # type: ignore[attr-defined] # "Callable[..., Any]" has no attribute "ratelimit"

        @functools.wraps(caller)
        def ratelimit_wrapper(*args, **kwargs):  # type: ignore[no-untyped-def] # Function is missing a type annotation
            current_manager = None
            if flask.g:
                current_manager = flask.g.get("rate_limit_manager", None)
                if current_manager is None:
                    current_manager = limit or ratelimit(
                        attempts=attempts,
                        cooldown=cooldown,
                        send_x_headers=send_x_headers,
                        reset_on_success=reset_on_success,
                        scope=scope,
                        category=category,
                    )
                    flask.g.rate_limit_manager = current_manager
            current_manager = current_manager or manager
            with current_manager:
                result = caller(*args, **kwargs)
                return result

        return ratelimit_wrapper

    return ratelimit_decorator(view) if view else ratelimit_decorator


def ratelimit(
    *,
    # Default of 100r/1s
    attempts: int = 30_000,
    cooldown: int = 300,
    send_x_headers: bool = True,
    reset_on_success: bool = False,
    category: Callable[[], str] = None,  # type: ignore[assignment] # Incompatible default for argument "category" (default has type "None", argument has type "Callable[[], str]")
    scope: Callable[[], str] = None,  # type: ignore[assignment] # Incompatible default for argument "scope" (default has type "None", argument has type "Callable[[], str]")
) -> RateLimitManager:
    """Get a rate-limit with the defined policy.

    Args:
        attempts: (defaults 30_000)
            The number of attempts to allow before raising an error.
        cooldown: (defaults 300)
            How many seconds a client must wait until trying again.
        send_x_headers: (defaults True)
            Whether to report the current status back to the client.
        reset_on_success: (defaults False)
            Whether to clear any tracked attempts on a successful result.
        category: (optional)
            A callable which will return the top-level category.
            This is used for scoping the rate limit.
            Defaults to looking up the endpoint of the current request.
        scope: (optional)
            A callable which will look up the fine-grained scope of this limit.
            This is used for scoping the rate limit.
            Defaults to looking up the client IP address.
    """
    scope = scope or get_client_ip  # type: ignore[truthy-function] # Function "scope" could always be true in boolean context
    category = category or get_request_endpoint  # type: ignore[truthy-function] # Function "category" could always be true in boolean context
    multiplier = int(os.environ.get("RATE_LIMIT_MULTIPLIER", 1))
    policy = RateLimitPolicy(
        attempts=attempts * multiplier,
        cooldown=cooldown,
        send_x_headers=send_x_headers,
        reset_on_success=reset_on_success,
    )
    manager = RateLimitManager(policy=policy, scope=scope, category=category)
    return manager


# endregion
# region: core interface


class RateLimitManager:
    """Core logic for managing the state of a pre-configured rate-limit policy."""

    def __init__(
        self,
        policy: RateLimitPolicy,
        scope: Callable[[], str] = None,  # type: ignore[assignment] # Incompatible default for argument "scope" (default has type "None", argument has type "Callable[[], str]")
        category: Callable[[], str] = None,  # type: ignore[assignment] # Incompatible default for argument "category" (default has type "None", argument has type "Callable[[], str]")
    ):
        self.policy = policy
        self.scope = scope or get_client_ip  # type: ignore[truthy-function] # Function "scope" could always be true in boolean context
        self.category = category or get_request_endpoint  # type: ignore[truthy-function] # Function "category" could always be true in boolean context
        self.redis = cache.redis_client()

    def __enter__(self):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        key = self.key()
        status = self._dummy_status(key=key)
        try:
            status = self.incr(key=key)
        except redis.RedisError as e:
            logger.warning("Failed to set rate-limit.", key=key, error=repr(e))

        set_ratelimit_status(status)
        return status

    def __exit__(self, exc_type, exc_val, exc_tb):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        if self.policy.reset_on_success and exc_type is None:
            key = self.key()
            status = self._dummy_status(key=key)
            try:
                status = self.clear(key=key)
            except redis.RedisError as e:
                logger.warning("Failed to reset rate-limit.", key=key, error=repr(e))
            except RateLimitingError as e:
                status = e.status
                raise
            finally:
                set_ratelimit_status(status)

    def _dummy_status(self, key: str = None) -> RateLimitStatus:  # type: ignore[assignment] # Incompatible default for argument "key" (default has type "None", argument has type "str")
        key = key or self.key()
        return RateLimitStatus(
            remaining=self.policy.attempts,
            limit=self.policy.attempts,
            reset=0,
            send_x_headers=self.policy.send_x_headers,
            key=key,
        )

    def key(self) -> str:
        """Generate a key in the cache for this rate-limit."""
        category, scope = self.category(), self.scope()
        return f"rate-limit/{category}/{scope}"

    def clear(self, *, key: str = None) -> RateLimitStatus:  # type: ignore[assignment] # Incompatible default for argument "key" (default has type "None", argument has type "str")
        """Clear any rate-limits at `key`."""
        key = key or self.key()
        self.redis.delete(key)
        return self._dummy_status(key=key)

    def ttl(self, *, key: str = None) -> int:  # type: ignore[assignment] # Incompatible default for argument "key" (default has type "None", argument has type "str")
        """Get the current ttl at `key`."""
        key = key or self.key()
        return self.redis.ttl(key)

    def extend(self, *, key: str = None) -> int:  # type: ignore[assignment] # Incompatible default for argument "key" (default has type "None", argument has type "str")
        """Reset the cooldown period at the defined key."""
        key = key or self.key()
        touched = self.redis.touch(key)
        if touched == 0:
            return self.set(key=key)
        return self.ttl(key=key)

    def set(self, *, key: str = None, count: int = 0, ttl: int = None) -> int:  # type: ignore[assignment] # Incompatible default for argument "key" (default has type "None", argument has type "str") #type: ignore[assignment] # Incompatible default for argument "ttl" (default has type "None", argument has type "int")
        """Manually set the current number of attempts at key."""
        key = key or self.key()
        if ttl is None:
            ttl = self.policy.cooldown
        self.redis.setex(name=key, time=ttl, value=count)
        return ttl

    def incr(self, key: str = None, n: int = 1) -> RateLimitStatus:  # type: ignore[assignment] # Incompatible default for argument "key" (default has type "None", argument has type "str")
        """Increase the number of attempts by `n`."""
        key = key or self.key()
        exists = self.redis.exists(key)
        if not exists:
            ttl = self.set(key=key, count=n)
            return self.status(key=key, attempts=n, ttl=ttl)

        attempts = int(self.redis.incrby(key, amount=n))
        # Avoids an edge case where incrementing an expired key will leave it without a ttl
        # We just performed INCRBY, so ensure that there is a TTL still applied to the key
        # Read: https://redis.io/commands/incr
        ttl = self.redis.ttl(key)
        if ttl < 0:
            self.redis.expire(key, self.policy.cooldown)

        return self.status(key=key, attempts=attempts, ttl=ttl)

    def status(  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        self,
        *,
        key: str = None,  # type: ignore[assignment] # Incompatible default for argument "key" (default has type "None", argument has type "str")
        attempts: int = None,  # type: ignore[assignment] # Incompatible default for argument "attempts" (default has type "None", argument has type "int")
        ttl: int = None,  # type: ignore[assignment] # Incompatible default for argument "ttl" (default has type "None", argument has type "int")
        raises: bool = True,
    ):
        """Get the current rate-limit status for `key`."""
        key = key or self.key()
        attempts, ttl = self._get_attempts_and_ttl(key=key, attempts=attempts, ttl=ttl)
        ttl = self.policy.cooldown if ttl is None else ttl
        remaining = self.policy.attempts - attempts
        status = RateLimitStatus(
            remaining=remaining,
            limit=self.policy.attempts,
            reset=ttl,
            send_x_headers=self.policy.send_x_headers,
            key=key,
        )
        if remaining < 0 and raises is True:
            raise RateLimitingError(
                "Too many attempts.",
                policy=self.policy,
                status=status,
            )
        return status

    def _get_attempts_and_ttl(self, *, key: str, attempts: int | None, ttl: int | None):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        has_attempts = attempts is not None
        has_ttl = ttl is not None
        truth = (has_attempts, has_ttl)
        # If we already have them, short-circuit
        if truth == (True, True):
            return attempts, ttl
        # If we have neither, fetch them both in one round-trip
        if truth == (False, False):
            with self.redis.pipeline(transaction=False) as pipe:
                attempts, ttl = pipe.get(key).ttl(key).execute()
            attempts = int(attempts) if attempts else 0
            # -1 indicates the key exists, but has no TTL
            # -2 indicates there is no key.
            # In either case, we just default to the cooldown policy.
            ttl = self.policy.cooldown if ttl < 0 else ttl
            return attempts, ttl
        # If we need the attempts, fetch that
        if truth == (False, True):
            attempts = self.redis.get(key)
            attempts = int(attempts) if attempts else 0
            return attempts, ttl

        # If we need the TTL, fetch that
        # if truth == (True, False):
        ttl = self.redis.ttl(key)
        ttl = self.policy.cooldown if ttl < 0 else ttl
        return attempts, ttl


# endregion
# region: data-model


# endregion
# region: data-model


@dataclasses.dataclass
class RateLimitPolicy:
    attempts: int
    cooldown: int
    send_x_headers: bool = True
    reset_on_success: bool = False


@dataclasses.dataclass
class RateLimitStatus:
    remaining: int
    limit: int
    reset: int
    key: str
    send_x_headers: bool = True


class RateLimitingError(Exception):
    def __init__(self, msg: str, policy: RateLimitPolicy, status: RateLimitStatus):
        self.policy = policy
        self.status = status
        super().__init__(msg)


# endregion
# region: flask helpers


def set_ratelimit_status(status: RateLimitStatus):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
    try:
        setattr(  # noqa  B010  TODO:  Do not call setattr with a constant attribute value, it is not any safer than normal property access.
            flask.g, "_view_rate_limit", status
        )
    except RuntimeError:
        logger.warning(
            "Couldn't set the current rate-limit status on the global scope.",
            **dataclasses.asdict(status),
        )


def get_ratelimit_status() -> RateLimitStatus | None:  # type: ignore[return] # Missing return statement
    try:
        return getattr(flask.g, "_view_rate_limit", None)
    except RuntimeError:
        logger.warning(
            "Couldn't fetch the current rate-limit status from the global scope.",
        )


def get_client_ip() -> str:
    """Return the source IP of the client making the request (i.e. end user)."""

    # Try the X-Real-IP first. This gets set by our nginx.
    real_ip = flask.request.headers.get("X-Real-IP")
    if real_ip:
        return real_ip

    # Fallback to X-Forwarded-For if needed (this should happen very rarely).
    # This can be a single IP or a comma-separated list where the first value
    # is client IP. Note that clients can spoof this, so we prefer X-Real-IP.
    forwarded_for = flask.request.headers.get("X-Forwarded-For", "")
    return forwarded_for.split(",")[0]


def get_email_or_client_ip() -> str:
    if flask.request.is_json:
        email = flask.request.json.get("email")
        if email:
            from hashlib import sha256

            return sha256(email.encode("utf-8")).hexdigest()

    return get_client_ip()


def get_request_endpoint() -> str:
    """Get the endpoint for the current request."""
    return flask.request.endpoint  # type: ignore[return-value] # Incompatible return value type (got "Optional[str]", expected "str")


def inject_x_rate_headers(response: flask.Response) -> flask.Response:
    """Inject the current status of the associated rate-limit configuration."""
    limit = get_ratelimit_status()
    if limit and limit.send_x_headers:
        h = response.headers
        h.add("X-RateLimit-Remaining", str(limit.remaining))
        h.add("X-RateLimit-Limit", str(limit.limit))
        h.add("X-RateLimit-Reset", str(limit.reset))
    return response


def clear_rate_limit_redis(category: str, scope: str) -> None:
    """Clear redis rate limit key based on category and scope"""
    redis_client = cache.redis_client()
    key = f"rate-limit/{category}/{scope}"
    logger.warning("Cleaning cache key.", key=key)

    try:
        redis_client.delete(key)
    except redis.RedisError as e:
        logger.warning("Failed to reset rate-limit.", key=key, error=repr(e))


# endregion
