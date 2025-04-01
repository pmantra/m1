import traceback
from resource import struct_rusage

from rq.job import Job

from tasks.owner_utils import inject_owner_count_metric
from utils.log import logger
from utils.service_owner_mapper import (
    CALLER_TAG,
    SERVICE_NS_TAG,
    TEAM_NS_TAG,
    TRACKING_ID,
)

logger = logger(__name__)


def on_success_callback_wrapper(job, connection, result, *args, **kwargs):  # type: ignore[no-untyped-def] # Function is missing a type annotation
    """on_success_callback_wrapper wraps the standard callback logic and call user defined callback logic

    Args:
        job: executed job object (task)
        connection: active connection object
        result: job execution result, if any

    Notes that the RQ worker implementation wraps the callback functions so any emitted exceptions will be swallowed
    and the default callback timeout is 60 seconds.

    """
    defined, job_func_name = get_job_func_name(job)
    job_cache = job.meta or {}
    job_tracking_id = job_cache.get(TRACKING_ID)
    inject_owner_count_metric(
        metric_name="mono.rq_tasks.job_success",
        func=job.func if defined else None,
        tags=job_cache.get("default_tags", []),
        service_ns=job_cache.get(SERVICE_NS_TAG, None),
        team_ns=job_cache.get(TEAM_NS_TAG, None),
        caller=job_cache.get(CALLER_TAG, None),
        job_func_name=job_func_name,
    )

    original_on_success_callback = job_cache.get("original_on_success_callback", None)
    if original_on_success_callback is not None:
        original_on_success_callback(job, connection, result, *args, **kwargs)

    logger.info(  # type: ignore[attr-defined] # "Callable[[str, KwArg(Any)], Any]" has no attribute "info"
        "Job run has succeeded",
        job_name=job_func_name,
        job_id=job.id,
        job_tracking_id=job_tracking_id,
    )


def on_failure_callback_wrapper(job, connection, _type, value, _traceback):  # type: ignore[no-untyped-def] # Function is missing a type annotation
    """on_failure_callback_wrapper wraps the standard callback logic and call user defined callback logic

    Args:
        job: executed job object (task)
        connection: active connection object
        _type: exception type
        value: the actual exception
        traceback: stack trace info for the exception

    Notes that the RQ worker implementation wraps the callback functions so the emitted exceptions will be swallowed
    and the default callback timeout is 60 seconds.

    """
    defined, job_func_name = get_job_func_name(job)
    job_cache = job.meta or {}
    default_tags = job_cache.get("default_tags", [])
    service_ns = job_cache.get(SERVICE_NS_TAG, None)
    team_ns = job_cache.get(TEAM_NS_TAG, None)
    caller = job_cache.get(CALLER_TAG, None)
    job_tracking_id = job_cache.get(TRACKING_ID)
    exc_tb_info = traceback.format_tb(_traceback)
    if job.retries_left and job.retries_left > 0:
        try_count = len(job.retry_intervals) - job.retries_left
        inject_owner_count_metric(
            metric_name="mono.rq_tasks.job_retry",
            func=job.func if defined else None,
            tags=default_tags + [f"try_count:{try_count}"],
            service_ns=service_ns,
            team_ns=team_ns,
            caller=caller,
            job_func_name=job_func_name,
        )
        # add the log line
        logger.warning(  # type: ignore[attr-defined] # "Callable[[str, KwArg(Any)], Any]" has no attribute "warning"
            f"Retrying job failed for attempt {try_count}, exception type {_type}, traceback {exc_tb_info}",
            job_name=job_func_name,
            job_id=job.id,
            job_tracking_id=job_tracking_id,
            try_count=try_count,
            exception=value,
        )
    else:
        inject_owner_count_metric(
            metric_name="mono.rq_tasks.job_failure",
            func=job.func if defined else None,
            tags=default_tags,
            service_ns=service_ns,
            team_ns=team_ns,
            caller=caller,
            job_func_name=job_func_name,
        )
        # log the exception
        logger.error(  # type: ignore[attr-defined] # "Callable[[str, KwArg(Any)], Any]" has no attribute "error"
            f"Job run has failed with {value}, exception type {_type}, traceback {exc_tb_info}",
            exception=value,
            job_name=job_func_name,
            job_id=job.id,
            job_tracking_id=job_tracking_id,
        )

    original_on_failure_callback = job_cache.get("original_on_failure_callback", None)
    if original_on_failure_callback is not None:
        original_on_failure_callback(job, connection, _type, value, traceback)


def on_stopped_callback_wrapper(job, connection):  # type: ignore[no-untyped-def] # Function is missing a type annotation
    """on_stopped_callback_wrapper wraps the standard callback logic and call user defined callback logic

    Args:
        job: executed job object (task)
        connection: active connection object

    Notes that the RQ worker implementation wraps the callback functions so any emitted exceptions will be swallowed
    and the default callback timeout is 60 seconds.

    """
    defined, job_func_name = get_job_func_name(job)
    job_cache = job.meta or {}
    job_tracking_id = job_cache.get(TRACKING_ID)
    inject_owner_count_metric(
        metric_name="mono.rq_tasks.job_stopped",
        func=job.func if defined else None,
        tags=job_cache.get("default_tags", []),
        service_ns=job_cache.get(SERVICE_NS_TAG, None),
        team_ns=job_cache.get(TEAM_NS_TAG, None),
        caller=job_cache.get(CALLER_TAG, None),
        job_func_name=job_func_name,
    )
    # log the exception
    logger.error(  # type: ignore[attr-defined] # "Callable[[str, KwArg(Any)], Any]" has no attribute "error"
        "Job run has been stopped",
        job_name=job_func_name,
        job_id=job.id,
        job_tracking_id=job_tracking_id,
    )

    original_on_stopped_callback = job_cache.get("original_on_stopped_callback", None)
    if original_on_stopped_callback is not None:
        original_on_stopped_callback(job, connection)


def on_work_horse_killed_handler(
    job: Job, retpid: int, ret_val: int, rusage: struct_rusage
) -> None:
    defined, job_func_name = get_job_func_name(job)
    job_cache = job.meta or {}
    job_tracking_id = job_cache.get(TRACKING_ID)
    inject_owner_count_metric(
        metric_name="mono.rq_tasks.work_horse_killed",
        func=job.func if defined else None,
        tags=job_cache.get("default_tags", []),
        service_ns=job_cache.get(SERVICE_NS_TAG, None),
        team_ns=job_cache.get(TEAM_NS_TAG, None),
        caller=job_cache.get(CALLER_TAG, None),
        job_func_name=job_func_name,
    )
    # log the exception
    logger.error(  # type: ignore[attr-defined] # "Callable[[str, KwArg(Any)], Any]" has no attribute "error"
        f"RQ job run has been terminated due to work horse killed issue, ret_pid {retpid}, "
        f"ret_val {ret_val}, rusage {rusage}",
        job_name=job_func_name,
        job_id=job.id,
        job_tracking_id=job_tracking_id,
    )


def get_job_func_name(job: Job) -> tuple[bool, str]:
    func_name = "undefined"
    defined = False
    try:
        func_name = job.func_name
        defined = True
    except Exception as e:
        # in most cases, this indicates a bigger serializer issue for job data
        # this needs to be investigated
        logger.error(  # type: ignore[attr-defined] # "Callable[[str, KwArg(Any)], Any]" has no attribute "error"
            f"RQ worker has issues to retrieve job name for job with exception {e}",
            job_id=job.id,
        )
    return defined, func_name
