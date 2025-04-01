from unittest.mock import patch

import pytest
from pymysql.err import OperationalError

from tasks.queues import MavenWorker, get_queue
from tasks.worker_utils import ensure_dependency_readiness
from utils.cache import redis_client


def dummy_job():
    pass


def test_ensure_worker_readiness():
    # Given

    # When

    # Then
    assert ensure_dependency_readiness()


def test_ensure_worker_readiness_with_retries():
    # Given
    retry_limit = 0

    # When
    with patch(
        "sqlalchemy.engine.Engine.connect",
        side_effect=OperationalError("cannot connect to DB"),
    ):
        # Then
        is_healthy = ensure_dependency_readiness(max_retry_limit=retry_limit)
        assert is_healthy is False


def test_do_status_detection_db_connection_good():
    queue = get_queue("test_do_status_detection_db_connection_good")
    queue.enqueue(dummy_job)
    worker = MavenWorker(
        [queue],
        connection=redis_client(),
        log_job_description=False,
        default_worker_ttl=300,
    )

    new_job, _ = worker.dequeue_job_and_maintain_ttl(None)

    res = worker.do_status_detection(new_job, job_name_check=False)
    assert res is True

    # Confirm no job left in the queue
    result = worker.dequeue_job_and_maintain_ttl(None)
    assert result is None


def test_do_status_detection_db_connection_good_enable_job_name_check():
    queue = get_queue(
        "test_do_status_detection_db_connection_good_enable_job_name_check"
    )
    queue.enqueue(dummy_job)
    worker = MavenWorker(
        [queue],
        connection=redis_client(),
        log_job_description=False,
        default_worker_ttl=300,
    )

    new_job, _ = worker.dequeue_job_and_maintain_ttl(None)

    res = worker.do_status_detection(new_job)
    assert res is False

    # Confirm no job left in the queue
    result = worker.dequeue_job_and_maintain_ttl(None)
    assert result is None


def test_do_status_detection_connection_failed():
    with patch(
        "sqlalchemy.engine.base.Engine.connect",
        side_effect=Exception(),
    ):
        queue = get_queue("test_do_status_detection_connection_failed")
        queue.enqueue(dummy_job)
        worker = MavenWorker(
            [queue],
            connection=redis_client(),
            log_job_description=False,
            default_worker_ttl=300,
        )

        new_job_one, _ = worker.dequeue_job_and_maintain_ttl(None)

        with pytest.raises(Exception) as e:
            worker.do_status_detection(new_job_one, job_name_check=False)
        assert "DB connection failed" in str(e.value)

        # Confirm the job is added back to the queue
        new_job_two, _ = worker.dequeue_job_and_maintain_ttl(None)
        assert new_job_one.id == new_job_two.id
        assert new_job_one.func_name == new_job_two.func_name


def test_do_status_detection_connection_lost():
    with patch(
        "sqlalchemy.engine.base.Connection.scalar",
        return_value=False,
    ):
        queue = get_queue("test_do_status_detection_connection_lost")
        queue.enqueue(dummy_job)
        worker = MavenWorker(
            [queue],
            connection=redis_client(),
            log_job_description=False,
            default_worker_ttl=300,
        )

        new_job_one, _ = worker.dequeue_job_and_maintain_ttl(None)

        with pytest.raises(Exception) as e:
            worker.do_status_detection(new_job_one, job_name_check=False)
        assert "DB connection failed" in str(e.value)

        # Confirm the job is added back to the queue
        new_job_two, _ = worker.dequeue_job_and_maintain_ttl(None)
        assert new_job_one.id == new_job_two.id
        assert new_job_one.func_name == new_job_two.func_name


def test_do_status_detection_worker_has_been_stopped():
    with patch(
        "tasks.queues.MavenWorker.is_stop_requested",
        return_value=True,
    ):
        queue = get_queue("test_do_status_detection_worker_has_been_stopped")
        queue.enqueue(dummy_job)
        worker = MavenWorker(
            [queue],
            connection=redis_client(),
            log_job_description=False,
            default_worker_ttl=300,
        )

        new_job_one, _ = worker.dequeue_job_and_maintain_ttl(None)

        with pytest.raises(Exception) as e:
            worker.do_status_detection(new_job_one, job_name_check=False)
        assert "Worker has been stopped" in str(e.value)

        # Confirm the job is added back to the queue
        new_job_two, _ = worker.dequeue_job_and_maintain_ttl(None)
        assert new_job_one.id == new_job_two.id
        assert new_job_one.func_name == new_job_two.func_name
