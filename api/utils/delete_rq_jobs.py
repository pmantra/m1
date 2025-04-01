import time
from collections import defaultdict

from rq import Queue

from utils import log
from utils.cache import redis_client

logger = log.logger("rq-key-deleting")


def def_value() -> int:
    return 0


class DeleteRQJobs:
    """Given a queue name and a func name, delete all of the matching jobs in a queue

    Usage:
        dj = DeleteRQJobs(queue_name="high_mem", func_name="bq_etl.pubsub_bq.bulk_export.export_chunk", throttle=2)
        dj.delete_jobs()
    """

    def __init__(  # type: ignore[no-untyped-def] # Function is missing a type annotation
        self,
        *,
        redis=None,
        batch_size=1000,
        page_limit=20,
        throttle=None,
        queue=None,
        queue_name,
        func_name,
    ):
        self.redis = redis or redis_client()
        self.batch_size = batch_size
        self.page_limit = page_limit
        self.throttle = throttle
        self.queue = queue or Queue(connection=self.redis, name=queue_name)
        self.func_name = func_name

    def delete_jobs(self):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        deleted_count = 0
        logger.info("Beginning deleting RQ jobs")
        for jobs in self.get_all_jobs():
            with self.redis.pipeline() as pipeline:
                for job in jobs:
                    try:
                        job_func_name = job.func_name
                        if job_func_name == self.func_name:
                            job.delete(pipeline=pipeline, delete_dependents=True)
                            deleted_count += 1
                    except BaseException:  # noqa: B036
                        logger.warn(
                            f"Exception when getting func_name for job {str(job._func_name)}",
                            job=job,
                        )
                pipeline.execute()
        logger.info(f"End deleting RQ jobs, deleted {deleted_count}")

    def get_all_jobs(self):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        continue_scanning = True
        scans = 0
        while continue_scanning:
            jobs = self.get_jobs()
            yield jobs
            if len(jobs) == 0 or scans >= self.page_limit:
                continue_scanning = False
            scans += 1
            if self.throttle:
                logger.info(f"Sleeping for {self.throttle} seconds")
                time.sleep(self.throttle)

    def get_jobs(self):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        return self.queue.get_jobs(length=self.batch_size)

    def print_all_jobs(self, limit):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        jobs = self.queue.get_jobs(length=limit)
        result_dict = defaultdict(def_value)
        for job in jobs:
            try:
                job_name = job.func_name
                result_dict[job_name] = result_dict[job_name] + 1
            except BaseException:  # noqa:  B036
                logger.warn("Error in print_all_jobs", job=job)
        for job_name, job_count in result_dict.items():
            logger.info(f"{job_name}: {job_count}")
