from time import sleep
from typing import List

from authn.domain import repository
from authn.services.integrations import idp
from authn.services.integrations.idp.management_client import (
    build_mfa_enable_migration_payload,
)
from tasks.queues import job
from utils.cache import redis_client
from utils.log import logger
from utils.service_owner_mapper import service_ns_team_mapper

BATCH_SIZE = 500
RETRY_DELAY = 20
MAX_POLL_ATTEMPTS = 10
VALID_STATUSES = frozenset(("completed", "failed"))
MIGRATION_JOB_KEY = "migrate_mfa_to_auth0"
MIGRATION_JOB_TTL = 300

log = logger(__name__)


def enqueue_all_migrate_mfa_to_auth0(  # type: ignore[no-untyped-def] # Function is missing a return type annotation
    batch_size: int = BATCH_SIZE, user_ids: List[int] = None, dry_run: bool = True  # type: ignore[assignment] # Incompatible default for argument "user_ids" (default has type "None", argument has type "List[int]")
):
    """Iterate through the entire User table in batches of <batch_size> to enqueue jobs to import user MFA to Auth0"""
    user_repo = repository.UserRepository()
    offset = 0
    batch = 1
    while True:
        user_mfa_to_migrate = user_repo.get_users_mfa_enabled(
            limit=batch_size, user_ids=user_ids, offset=offset
        )
        if len(user_mfa_to_migrate) > 0:
            # Enqueue the batch of jobs to the ad_hoc queue
            log.info(f"migrate_user_mfa_to_auth0 batch={batch} dry_run={dry_run}")
            service_ns_tag = "authentication"
            team_ns_tag = service_ns_team_mapper.get(service_ns_tag)
            migrate_user_mfa_to_auth0.delay(
                user_mfa_to_migrate=user_mfa_to_migrate,
                dry_run=dry_run,
                service_ns=service_ns_tag,
                team_ns=team_ns_tag,
            )
            batch += 1
            offset += batch_size
        if len(user_mfa_to_migrate) < batch_size:
            # The last page we fetched was less than the limit, so we have exhausted our data set
            break


@job("ad_hoc")
def migrate_user_mfa_to_auth0(*, user_mfa_to_migrate, dry_run=True):  # type: ignore[no-untyped-def] # Function is missing a type annotation
    """Migrates users MFA to Auth0 in bulk via the Bulk Import API

    Auth0 limits concurrent bulk user import jobs to 2, so we cannot enqueue
    a ton of jobs without hitting rate limiting. Polling temporarily blocks the queue.
    """
    if len(user_mfa_to_migrate) == 0:
        log.info("migrate_user_mfa_to_auth0, no user to migrate")
        return

    management_client = idp.ManagementClient()

    # Caching the job ID because we have no way to fetch it programatically
    # This ensures that we don't hit our rate limit on the Auth0 API
    # If no job ID is found, go ahead and try the next import
    redis = redis_client(decode_responses=True)
    blocking_job_id = redis.get(MIGRATION_JOB_KEY)
    if blocking_job_id:
        if not poll_job(management_client, blocking_job_id):
            return

    log.info(
        f"migrate_user_mfa_to_auth0 dry_run={dry_run} start migrating {len(user_mfa_to_migrate)} users"
    )
    if not dry_run:
        # Build migration payload
        payload = list(
            map(
                lambda tuples: build_mfa_enable_migration_payload(*tuples),
                user_mfa_to_migrate,
            )
        )
        res = management_client.import_users(payload=payload)
        if res is not None:
            new_job_id = res["id"]
            log.info("Enqueued migrate_user_mfa_to_auth0 import job", job_id=new_job_id)
            redis.setex(MIGRATION_JOB_KEY, MIGRATION_JOB_TTL, new_job_id)


def poll_job(management_client, job_id: str) -> bool:  # type: ignore[no-untyped-def] # Function is missing a type annotation for one or more arguments
    """Poll the Auth0 jobs endpoint with incremental backoff"""
    poll_attempts = 1
    while poll_attempts <= MAX_POLL_ATTEMPTS:
        job = management_client.get_job(job_id)
        job_status = job["status"]
        log.info(f"migrate_user_mfa_to_auth0 job {job_id} status {job_status}")
        if job_status in VALID_STATUSES:
            return True
        sleep(2 * poll_attempts)
        poll_attempts += 1
    log.error(
        f"migrate_user_mfa_to_auth0 failed to get job {job_id} valid status after long polling"
    )
    return False
