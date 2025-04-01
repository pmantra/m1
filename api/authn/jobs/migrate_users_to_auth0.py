from time import sleep
from typing import List

from authn.domain import repository
from authn.services.integrations import idp
from tasks.queues import job
from utils.cache import redis_client
from utils.log import logger
from utils.service_owner_mapper import service_ns_team_mapper

BATCH_SIZE = 500
RETRY_DELAY = 20
MAX_POLL_ATTEMPTS = 10
VALID_STATUSES = frozenset(("completed", "failed"))
MIGRATION_JOB_KEY = "idp_migration_import_job"
MIGRATION_JOB_TTL = 300

log = logger(__name__)


def enqueue_all(batch_size: int = BATCH_SIZE, user_ids: List[int] = None):  # type: ignore[no-untyped-def,assignment] # Function is missing a return type annotation #type: ignore[assignment] # Incompatible default for argument "user_ids" (default has type "None", argument has type "List[int]")
    """Iterate through the entire User table in batches of <batch_size> to enqueue jobs to import users to Auth0"""
    user_repo = repository.UserRepository()
    offset = 0
    while True:
        user_ids_to_migrate = user_repo.get_all_without_auth(
            limit=batch_size, user_ids=user_ids, offset=offset
        )
        if len(user_ids_to_migrate) > 0:
            # Enqueue the batch of jobs to the ad_hoc queue
            service_ns_tag = "authentication"
            team_ns_tag = service_ns_team_mapper.get(service_ns_tag)
            migrate_users_to_auth0.delay(
                user_ids=user_ids_to_migrate,
                service_ns=service_ns_tag,
                team_ns=team_ns_tag,
            )
            offset += batch_size
        if len(user_ids_to_migrate) < batch_size:
            # The last page we fetched was less than the limit, so we have exhausted our data set
            break


@job("ad_hoc")
def migrate_users_to_auth0(*, user_ids: List[int]):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
    """Migrates users to Auth0 in bulk via the Bulk Import API

    Auth0 limits concurrent bulk user import jobs to 2, so we cannot enqueue
    a ton of jobs without hitting rate limiting. Polling temporarily blocks the queue.
    """
    if len(user_ids) == 0:
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

    user_repo = repository.UserRepository()
    users = user_repo.get_all_by_ids(ids=user_ids)
    if len(users) == 0:
        return

    # Build payload and filter out any with bad or missing passwords
    payload = [data for data in map(idp.import_helper.build_payload, users) if data]
    res = management_client.import_users(payload=payload)
    if res is not None:
        new_job_id = res["id"]
        log.info("Enqueued user import job", job_id=res["id"])

    # Update our database optimistically to mark users as migrated
    user_auth_repo = repository.UserAuthRepository()
    user_auth_repo.bulk_insert_user_auth(user_ids=user_ids)
    redis.setex(MIGRATION_JOB_KEY, MIGRATION_JOB_TTL, new_job_id)


def poll_job(management_client, job_id: str) -> bool:  # type: ignore[no-untyped-def] # Function is missing a type annotation for one or more arguments
    """Poll the Auth0 jobs endpoint with incremental backoff"""
    poll_attempts = 1
    while poll_attempts <= MAX_POLL_ATTEMPTS:
        job = management_client.get_job(job_id)
        if job["status"] in VALID_STATUSES:
            return True
        sleep(2 * poll_attempts)
        poll_attempts += 1
    return False
