from concurrent.futures import ThreadPoolExecutor

from ddtrace import tracer

# global threadpool. usage of this should respect the max_workers limit, and this limit should be
# raised if we are approaching it with max_workers concurrent requests
executor = ThreadPoolExecutor()


def run_async_in_threadpool(func, *args):  # type: ignore[no-untyped-def] # Function is missing a type annotation
    dd_context = tracer.current_trace_context()
    f = executor.submit(_run_async_wrapper, func, dd_context, *args)
    return f


def _run_async_wrapper(func, dd_context, *args):  # type: ignore[no-untyped-def] # Function is missing a type annotation
    # ties background to main thread in Datadog trace
    tracer.context_provider.activate(dd_context)
    func(*args)
    return
