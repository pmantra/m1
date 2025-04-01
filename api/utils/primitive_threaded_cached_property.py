import functools
from datetime import date, datetime
from traceback import format_exc
from typing import Callable, TypeVar

from cached_property import threaded_cached_property
from maven.feature_flags import bool_variation
from typing_extensions import ParamSpec

from utils.log import logger

log = logger(__name__)


# feature flag to enable/disable the primitive_threaded_cached_property
FEATURE_FLAG_PRIMITIVE_THREADED_CACHED_PROPERTY = (
    "feature_flag_primitive_threaded_cached_property"
)


def should_raise_on_non_primitive() -> bool:
    """
    Returns True if failed evaluations should raise an error, False if they
    should not.
    """
    return bool_variation(
        FEATURE_FLAG_PRIMITIVE_THREADED_CACHED_PROPERTY,
        # disable hard fails by default
        default=False,
    )


# returns True if the value type matches what we consider a primitive type.
# primitive types are values that can be safely accessed across threads.
def is_primitive(value) -> bool:  # type: ignore[no-untyped-def] # Function is missing a type annotation for one or more arguments
    # a dict where all keys and values are primitives is safe to cache
    if isinstance(value, dict):
        for k, v in value.items():
            if not is_primitive(k) or not is_primitive(v):
                return False
        return True

    return isinstance(
        value,
        (
            int,
            float,
            str,
            bool,
            date,
            datetime,
            type(None),
        ),
    )


error_message_template = """
threaded_cached_property may only be used on primitive types, not {value_type}."
lists, dicts, collection, and other complex types are not allowed because we
have chosen not to recursively validate primitive types for performance reasons.
It is critical to not cache live ORM objects because their connection usage is
not thread-safe when lazy loading properties.
"""

# param type for wrap target of primitive_threaded_cached_property
P = ParamSpec("P")
# return type for wrap target of primitive_threaded_cached_property
R = TypeVar("R")


def primitive_threaded_cached_property(func: Callable[P, R]) -> R:
    """
    A decorator that wraps the threaded_cached_property decorator to add a check
    that the return value is a primitive type. This is to prevent accidental
    caching of non thread-safe values.
    """

    @functools.wraps(func)
    def wrapper(*func_args, **func_kwargs):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        retval = func(*func_args, **func_kwargs)

        if not is_primitive(retval):
            err_msg = error_message_template.format(value_type=type(retval))
            if should_raise_on_non_primitive():
                raise ValueError(err_msg)
            else:
                log.warning(
                    err_msg,
                    trace=format_exc(),
                )

        return retval

    return threaded_cached_property(wrapper)
