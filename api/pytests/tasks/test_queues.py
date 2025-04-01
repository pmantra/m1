from unittest.mock import MagicMock, patch

from pymysql.err import OperationalError
from redis.exceptions import RedisError
from rq.job import Job

from common import stats
from pytests.tasks import test_rq_utils
from tasks.queues import (
    GENERIC_EXCEPTION_SCHEDULING_FN_ERROR_COUNT,
    REDIS_EXCEPTION_SCHEDULING_FN_ERROR_COUNT,
    MavenWorker,
    schedule_fn,
)
from utils.cache import redis_client


def test_perform_job_owner_logic(mock_queue):
    # make sure redis connectivity
    redis_url_updated = test_rq_utils.update_redis_url_env()

    # prepare the job logic
    queue_name = "default"
    # explicit call the delay method to simulate the logic
    test_rq_utils.create_dummy_rq_job_for_owner_logic.delay(
        service_ns="misc",
        team_ns="core_services",
        test_helper=True,
    )
    kwargs = {
        "application_name": "post",
        "failure_ttl": 1,
    }
    _job = Job.create(
        func=test_rq_utils.create_dummy_rq_job_for_owner_logic,
        kwargs=kwargs,
        origin=queue_name,
        connection=redis_client(),
    )

    # validate job is created and no result before execution
    assert _job is not None
    assert _job.return_value() is None
    assert _job.is_started is False

    test_rq_utils.create_maven_worker_and_perform_job(
        [queue_name], job=_job, queue=mock_queue
    )

    if redis_url_updated:
        test_rq_utils.unset_redis_url_env()

    # validate the job logic has been executed successfully
    assert _job.return_value() is True
    assert _job.is_finished is True


def test_prune_devices_owner_logic(mock_queue):
    from tasks.notifications import prune_devices

    # make sure redis connectivity
    redis_url_updated = test_rq_utils.update_redis_url_env()

    # prepare the job logic
    queue_name = "default"
    # explicit call the delay method to simulate the logic
    prune_devices.delay(
        service_ns="misc",
        team_ns="core_services",
        test_helper=True,
    )
    kwargs = {
        "application_name": "member",
    }
    _job = Job.create(
        func=prune_devices,
        kwargs=kwargs,
        origin=queue_name,
        connection=redis_client(),
    )

    # validate job is created and no result before execution
    assert _job is not None
    assert _job.is_started is False

    test_rq_utils.create_maven_worker_and_perform_job(
        [queue_name], job=_job, queue=mock_queue
    )

    if redis_url_updated:
        test_rq_utils.unset_redis_url_env()

    # validate the job logic has been executed successfully
    assert _job.is_finished is True


def test_worker_check_for_suspension(monkeypatch):
    monkeypatch.setattr("tasks.queues._MAX_HEALTH_PROBE_RETRY", 0)
    with patch(
        "sqlalchemy.engine.Engine.connect",
        side_effect=OperationalError("cannot connect to DB"),
    ):
        # make sure redis connectivity
        redis_url_updated = test_rq_utils.update_redis_url_env()

        worker = MavenWorker(
            ["default"],
            connection=redis_client(),
            log_job_description=False,
        )

        assert worker._shutdown_requested_date is None
        worker.check_for_suspension(burst=False)

        if redis_url_updated:
            test_rq_utils.unset_redis_url_env()

        assert worker._shutdown_requested_date is not None


def test_schedule_fn__happy_path():
    # Given a function and arbitrary args
    fn = MagicMock(__name__="fn")
    non_keyword_arg = "non_keyword_arg"
    keyword_args = {"keyword_1": "keyword_1_val", "keyword_2": "keyword_2_val"}

    # When calling schedule_fn for the function and the args
    schedule_fn(fn, non_keyword_arg, **keyword_args)

    # Assert .delay was called
    fn.delay.assert_called_once_with(non_keyword_arg, **keyword_args)


@patch("tasks.queues.stats.increment")
def test_schedule_fn__redis_exception(mock_stats_increment):
    # Given the .delay will raise a RedisError
    fn = MagicMock(__name__="fn")
    fn.delay = MagicMock()
    fn.delay.side_effect = RedisError()

    non_keyword_arg = "non_keyword_arg"
    keyword_args = {
        "keyword_1": "keyword_1_val",
        "keyword_2": "keyword_2_val",
        "team_ns": "best_team",
    }

    # When calling schedule_fn for the function and the args
    schedule_fn(fn, non_keyword_arg, **keyword_args)

    # Assert .delay was called
    fn.delay.assert_called_once_with(non_keyword_arg, **keyword_args)
    # And we increase redis exception metric

    mock_stats_increment.assert_called_once_with(
        REDIS_EXCEPTION_SCHEDULING_FN_ERROR_COUNT,
        pod_name=stats.PodNames.CORE_SERVICES,
        tags=[
            "team:best_team" "fn:fn",
        ],
    )


@patch("tasks.queues.stats.increment")
def test_schedule_fn__generic_exception(mock_stats_increment):
    # Given the .delay will raise a generic Exception
    fn = MagicMock(__name__="fn")
    fn.delay = MagicMock()
    fn.delay.side_effect = Exception()

    non_keyword_arg = "non_keyword_arg"
    keyword_args = {
        "keyword_1": "keyword_1_val",
        "keyword_2": "keyword_2_val",
        "team_ns": "best_team",
    }

    # When calling schedule_fn for the function and the args
    schedule_fn(fn, non_keyword_arg, **keyword_args)

    # Assert .delay was called
    fn.delay.assert_called_once_with(non_keyword_arg, **keyword_args)
    # And we increase generic exception metric

    mock_stats_increment.assert_called_once_with(
        GENERIC_EXCEPTION_SCHEDULING_FN_ERROR_COUNT,
        pod_name=stats.PodNames.CORE_SERVICES,
        tags=[
            "team:best_team" "fn:fn",
        ],
    )
