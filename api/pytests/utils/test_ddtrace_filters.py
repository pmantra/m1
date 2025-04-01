from ddtrace import Span, tracer

from utils.ddtrace_filters import IGNORE_TRACE_TAG, IgnoreTraceFilter, ignore_trace


def test_filters_on_matching_tag():
    span = Span(name="name")
    span.set_tag(IGNORE_TRACE_TAG, True)

    trace = IgnoreTraceFilter().process_trace([span])

    assert trace is None


def test_no_match():
    span = Span(name="name")

    trace = IgnoreTraceFilter().process_trace([span])

    assert trace is not None


def test_ignore_trace_should_drop_trace():
    with tracer.trace("test_span") as span:
        assert tracer.current_span() is span

        should_not_be_traced()

        trace = IgnoreTraceFilter().process_trace([span])

        assert trace is None


def test_it_should_not_drop_trace():
    with tracer.trace("test_span") as span:
        assert tracer.current_span() is span

        should_be_traced()

        trace = IgnoreTraceFilter().process_trace([span])

        assert trace is not None


@ignore_trace()
def should_not_be_traced():
    return True


def should_be_traced():
    return True
