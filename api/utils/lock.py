import functools
from typing import Callable

from httpproblem import Problem
from redset.exceptions import LockTimeout

from utils import cache
from utils.log import logger

log = logger(__name__)


def prevent_concurrent_requests(key: Callable):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
    """
    Decorator for endpoints that are unable to be processed in parallel.
    When the decorated method is called, a RedisLock is created with a
    certain key, and other requests to the endpoint with the same key
    will be rejected with a 409 CONFLICT error.

    The method takes a KEY lambda that turns the method's arguments into
    the key that should be used. Often this should make use of the current
    user ID, so that the method is only locked against requests from the
    same user.

    Example:
        @prevent_concurrent_requests(lambda self: f"some_method:{self.user.id}")
        def some_method(self):
            # This code can only be called once per user at a time
    """

    def decorator(func):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        func_name = getattr(func, "__qualname__", func.__name__)

        @functools.wraps(func)
        def wrapper(*args, **kwargs):  # type: ignore[no-untyped-def] # Function is missing a type annotation
            current_key = key(*args, **kwargs)
            log_kwargs = {"method": func_name, "key": current_key}
            # Try attaching user_id to logs
            # (for Flask endpoints the user is often self.user)
            if (
                args
                and getattr(args[0], "user", None)
                and getattr(args[0].user, "id", None)
            ):
                log_kwargs["user_id"] = args[0].user.id

            try:
                log.info("Acquiring lock for request", **log_kwargs)
                with cache.RedisLock(current_key, timeout=0):
                    result = func(*args, **kwargs)
                    log.info("Releasing lock for request", **log_kwargs)
                    return result
            except LockTimeout:
                log.info("Rejecting concurrent request", **log_kwargs)
                raise Problem(
                    409, detail="Concurrent requests to this endpoint are not allowed."
                )

        return wrapper

    return decorator
