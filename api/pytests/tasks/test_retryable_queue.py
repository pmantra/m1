from rq.job import Job

from pytests.tasks import test_rq_utils
from tasks.queues import MavenWorker, retryable_job
from utils.cache import redis_client
from utils.log import logger

log = logger(__name__)


def backoff_fail_first_three(tries):
    # dummy implementation
    return 1


def no_backoff(tries):
    # dummy implementation
    return 0


def on_success_callback(job, connection, result, *args, **kwargs):
    # dummy callback
    job.func.job_cache["success_flag"] = True


def on_failure_callback(job, connection, _type, value, traceback):
    # dummy callback
    job.func.job_cache["success_flag"] = False
    # job won't retry after maximum configured retry times
    if job.retries_left and job.retries_left > 0:
        current_try = job.func.job_cache.get("total_retry_count", 0)
        job.func.job_cache["total_retry_count"] = current_try + 1


def on_stopped_callback(job, connection):
    # dummy callback
    job.func.job_cache["stopped_flag"] = True


@retryable_job("default", backoff_func=backoff_fail_first_three)
def retry_job_to_test():
    func_cache = getattr(retry_job_to_test, "job_cache", None)
    if func_cache:
        current_try = func_cache.get("try_count", 0)
        retry_job_to_test.job_cache["try_count"] = current_try + 1
        # fail the first 3 tries to simulate job logic
        if current_try < 3:
            raise Exception("Try Again!")
    return True


@retryable_job("default", backoff_func=no_backoff, retry_limit=6)
def failure_job_to_test():
    raise Exception("ARG! Something went wrong!")


def init_test_job(job_func, service_ns, team_ns, queue_name):
    # simulate real job logic sequence
    job_func.delay(
        service_ns=service_ns,
        team_ns=team_ns,
        test_helper=True,
        on_success=on_success_callback,
        on_failure=on_failure_callback,
        on_stopped=on_stopped_callback,
    )

    # prepare job parameters
    meta = {
        "service_ns": service_ns,
        "team_ns": team_ns,
        "original_on_success_callback": on_success_callback,
        "original_on_failure_callback": on_failure_callback,
        "original_on_stopped_callback": on_stopped_callback,
    }
    _job = Job.create(
        func=job_func,
        origin=queue_name,
        connection=redis_client(),
        meta=meta,
        on_success=job_func.job_cache["on_success"],
        on_failure=job_func.job_cache["on_failure"],
        on_stopped=job_func.job_cache["on_stopped"],
    )
    # hack to set retry parameters since the create method doesn't allow retry parameter
    # unfortunately this is also how it is implemented in rq package
    _job.retries_left = job_func.job_cache.get("retry").max
    _job.retry_intervals = job_func.job_cache.get("retry").intervals

    return _job


def test_retry_job_to_test_enqueue():
    assert getattr(retry_job_to_test, "job_cache", None) is None

    retry_job_to_test.delay(
        service_ns="misc", team_ns="core_services", test_helper=True
    )

    assert getattr(retry_job_to_test, "job_cache", None) is not None
    # it is set by the test_helper flag
    retry_func = retry_job_to_test.job_cache.get("retry")
    # the job will be tried 10 times (first try plus nine retries)
    assert retry_func.max == 9
    assert len(retry_func.intervals) == 9


def test_failure_job_to_test_enqueue():
    failure_job_to_test.delay(
        service_ns="misc", team_ns="core_services", test_helper=True
    )

    assert failure_job_to_test.job_cache is not None
    assert failure_job_to_test.job_cache.get("retry", None) is not None


def test_multiple_retry_success_logic(mock_queue):
    # make sure redis connectivity
    redis_url_updated = test_rq_utils.update_redis_url_env()

    # job parameter logic
    queue_name = "default"
    service_ns = "misc"
    team_ns = "core_services"

    _job = init_test_job(retry_job_to_test, service_ns, team_ns, queue_name)

    # validate job is created and no result before execution
    assert _job is not None

    # simulate the internal re-queue failed job logic until job retries_left is zero
    max_retry_cap = 0
    worker = MavenWorker(
        [queue_name],
        connection=redis_client(),
        log_job_description=False,
    )

    while _job.is_finished is False and max_retry_cap < 20:
        worker.perform_job(_job, mock_queue)
        max_retry_cap += 1

    if redis_url_updated:
        test_rq_utils.unset_redis_url_env()

    # validate the job logic has been executed successfully
    assert _job.is_finished is True
    assert _job.func.job_cache.get("success_flag") is True
    # should retry three times since we throw exceptions three times in the job logic
    assert _job.func.job_cache.get("total_retry_count") == 3


def test_multiple_retry_failure_logic(mock_queue):
    # make sure redis connectivity
    redis_url_updated = test_rq_utils.update_redis_url_env()

    # job parameter logic
    queue_name = "default"
    service_ns = "misc"
    team_ns = "core_services"

    _job = init_test_job(failure_job_to_test, service_ns, team_ns, queue_name)

    # validate job is created and no result before execution
    assert _job is not None

    # simulate the internal re-queue failed job logic until job retries_left is zero
    max_retry_cap = 0
    worker = MavenWorker(
        [queue_name],
        connection=redis_client(),
        log_job_description=False,
    )

    while _job.is_failed is False and max_retry_cap < 20:
        worker.perform_job(_job, mock_queue)
        max_retry_cap += 1

    if redis_url_updated:
        test_rq_utils.unset_redis_url_env()

    # validate the job logic has been executed successfully
    assert _job.is_failed is True
    # rq.worker logic always return this flag to be false when failed
    assert _job.is_finished is False
    assert _job.func.job_cache.get("success_flag") is False
    # should retry maximum times as defined since we throw exceptions all the time
    assert _job.func.job_cache.get("total_retry_count") == 5


def test_stopped_job_logic(mock_queue):
    # make sure redis connectivity
    redis_url_updated = test_rq_utils.update_redis_url_env()

    # job parameter logic
    queue_name = "default"
    service_ns = "misc"
    team_ns = "core_services"

    _job = init_test_job(retry_job_to_test, service_ns, team_ns, queue_name)

    # validate job is created and no result before execution
    assert _job is not None

    # simulate the internal re-queue failed job logic until job retries_left is zero
    worker = MavenWorker(
        [queue_name],
        connection=redis_client(),
        log_job_description=False,
    )

    worker._stopped_job_id = _job.id
    # RQ implementation for stopped callback is different from the other two callbacks
    _job.execute_stopped_callback(worker.death_penalty_class)

    if redis_url_updated:
        test_rq_utils.unset_redis_url_env()

    # validate the job logic has been executed successfully
    assert _job.func.job_cache.get("stopped_flag") is True
