import functools

from ddtrace import tracer
from ddtrace.filters import TraceFilter

from utils.log import logger

log = logger(__name__)

IGNORE_TRACE_TAG = "ignore_trace"


def ignore_trace():  # type: ignore[no-untyped-def] # Function is missing a return type annotation
    """
    Decorator for operations that should not be reported as a trace by ddtrace

    Example:
        @ignore_trace()
        def some_method():
            # No trace should be reported to Datadog for this method
    """

    def decorator(func):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        @functools.wraps(func)
        def wrapper(*args, **kwargs):  # type: ignore[no-untyped-def] # Function is missing a type annotation
            span = tracer.current_root_span()

            if span is not None:
                span.set_tag(IGNORE_TRACE_TAG, True)

            return func(*args, **kwargs)

        return wrapper

    return decorator


class IgnoreTraceFilter(TraceFilter):
    """
    Filter out traces from based on the existence of a specific tag in one of the spans
    """

    def process_trace(self, trace):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        for span in trace:
            if span.get_tag(IGNORE_TRACE_TAG) is not None:
                return None
        return trace
