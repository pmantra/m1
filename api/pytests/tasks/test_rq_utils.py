import os

from tasks.queues import MavenWorker, job
from utils.cache import redis_client


def create_maven_worker_and_perform_job(queues, job, queue):
    worker = MavenWorker(
        queues,
        connection=redis_client(),
        log_job_description=False,
    )
    worker.perform_job(job, queue)


def update_redis_url_env() -> bool:
    # make sure redis connectivity
    redis_url = os.environ.get("REDIS_URL", None)
    if redis_url is None:
        os.environ["REDIS_URL"] = "redis://mono-redis:6379/0"

    # return true if redis url is updated
    return redis_url is None


def unset_redis_url_env():
    os.environ.pop("REDIS_URL", None)


# add a simple wrapper similar to this around your real job implementations and do validations if there is a need
@job
def create_dummy_rq_job_for_owner_logic(application_name="forum", **kwargs):
    service_ns = kwargs.get("service_ns", None)
    team_ns = kwargs.get("team_ns", None)

    # application_name should be updated to be the one passed in from the job
    assert application_name == "post"

    # both should have been removed in the worker logic
    assert service_ns is None
    assert team_ns is None

    # added to facilitate test logic validation
    return True
