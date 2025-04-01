from rq.job import Job

from pytests.tasks import test_rq_utils
from tasks.job_callbacks import on_work_horse_killed_handler
from tasks.queues import MavenWorker
from utils.cache import redis_client


def create_dummy_test_job():
    return True


def test_on_work_horse_killed_handler(mock_queue):
    # make sure redis connectivity
    redis_url_updated = test_rq_utils.update_redis_url_env()

    # prepare the job logic
    queue_name = "priority"
    _job = Job.create(
        func=create_dummy_test_job,
        timeout=1,
        origin=queue_name,
        connection=redis_client(),
    )

    # validate job is created and no result before execution
    assert _job is not None
    assert _job.return_value() is None
    assert _job.is_started is False

    worker = MavenWorker(
        [queue_name],
        connection=redis_client(),
        log_job_description=False,
        job_monitoring_interval=1,
        work_horse_killed_handler=on_work_horse_killed_handler,
    )
    assert worker.state == "starting"
    # trigger the work horse killed logic
    worker.handle_work_horse_killed(_job, 1, 1, ("cpu", "memory"))

    if redis_url_updated:
        test_rq_utils.unset_redis_url_env()

    assert _job.is_finished is False
