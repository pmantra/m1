from time import sleep

from authn.domain import repository
from authn.services.integrations import idp
from tasks.queues import job
from utils.log import logger
from utils.service_owner_mapper import service_ns_team_mapper

BATCH_SIZE = 100
log = logger(__name__)


def backfill_user_auth_external_id(
    batch_size: int = BATCH_SIZE, dry_run: bool = True
) -> None:
    """Iterate through the entire User table in batches of <batch_size> to enqueue jobs to import user MFA to Auth0"""
    user_auth_repo = repository.UserAuthRepository()
    offset = 0
    batch = 1
    log.info(f"backfill_user_auth_external_id dry_run={dry_run}")
    while True:
        users_without_external_id = (
            user_auth_repo.get_all_without_user_auth_external_id(
                limit=batch_size, offset=offset
            )
        )
        if len(users_without_external_id) > 0:
            # Enqueue the batch of jobs to the ad_hoc queue
            service_ns_tag = "authentication"
            team_ns_tag = service_ns_team_mapper.get(service_ns_tag)
            start_backfill_user_auth_external_id.delay(
                users_without_external_id=users_without_external_id,
                batch=batch,
                dry_run=dry_run,
                service_ns=service_ns_tag,
                team_ns=team_ns_tag,
            )
            batch += 1
            offset += batch_size
        if len(users_without_external_id) < batch_size:
            # The last page we fetched was less than the limit, so we have exhausted our data set
            break


@job("ad_hoc")
def start_backfill_user_auth_external_id(  # type: ignore[no-untyped-def] # Function is missing a type annotation
    *, users_without_external_id, batch, dry_run=True
):
    """backfill user_auth table with empty external_id by copying their corresponding
    Auth0 id and insert it into the table.
    """
    if len(users_without_external_id) == 0:
        log.info("backfill_user_auth_external_id, no user to migrate")
        return

    management_client = idp.ManagementClient()
    log.info(
        f"backfill_user_auth_external_id starts batch={batch} migrating {len(users_without_external_id)} users"
    )
    if not dry_run:
        user_auth_repo = repository.UserAuthRepository()
        for user_id in users_without_external_id:
            try:
                res = management_client.query_users_by_user_id(user_id=user_id)
                if res is not None:
                    external_id = res.user_id
                    log.info(
                        f"backfill_user_auth_external_id find an Auth0 user {external_id} for {user_id}"
                    )
                    try:
                        user_auth_repo.update_by_user_id(
                            user_id=user_id, external_id=external_id
                        )
                        log.info(
                            f"backfill_user_auth_external_id updated user_auth user_id={user_id} external_id={external_id}"
                        )
                    except Exception as err:
                        log.warn(
                            f"backfill_user_auth_external_id, cannot update DB for id {user_id} {err}"
                        )
                else:
                    log.info(
                        f"backfill_user_auth_external_id cannot find an Auth0 user for {user_id}"
                    )
                sleep(0.5)
            except Exception as err:
                log.warn(
                    f"backfill_user_auth_external_id, cannot get Auth0 user for id {user_id} {err}"
                )

    log.info(
        f"backfill_user_auth_external_id finishes batch={batch} migrating {len(users_without_external_id)} users"
    )
