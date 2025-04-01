from __future__ import annotations

import dataclasses
from time import sleep

from authn.domain.model import UserExternalIdentity
from authn.domain.service import get_auth_service, get_sso_service
from authn.util.constants import SSO_VALIDATION_METRICS_PREFIX
from common import stats
from tasks.queues import job
from utils.log import logger

log = logger(__name__)

BATCH_SIZE = 100

METRICS_NAME = "data_backfill_job"
FAILED_REASON_1 = "auth0 user not found"
FAILED_REASON_2 = "dup data with the same external user_id and connection"
FAILED_REASON_3 = "database update failed"
FAILED_REASON_4 = (
    "missing record in user external identity based on maven user id and connection"
)


def migrate_auth0_sso_user_metadata_to_maven(
    connection_name: str,
    user_id: int | None = None,
    batch_size: int = BATCH_SIZE,
    dryrun: bool = True,
) -> None:
    log.info(
        f"Start migrating the auth0 sso user metadata to maven for connection {connection_name} with dryrun is {dryrun}"
    )
    sso_service = get_sso_service()
    # Get all the existing users from the maven database for one connection
    maven_user_ids_set = set()
    if user_id:
        maven_user_ids_set.add(user_id)
    else:
        sso_users = sso_service.retrieval_users_per_connection_from_maven(
            connection_name=connection_name
        )
        for sso_user in sso_users:
            maven_user_ids_set.add(sso_user.user_id)
    maven_user_ids = list(maven_user_ids_set)
    log.info(
        f"Going to update {len(maven_user_ids)} records with unique maven user id in the user external identity table"
    )

    sliced_candidates = [
        maven_user_ids[i : i + batch_size]
        for i in range(0, len(maven_user_ids), batch_size)
    ]

    for candidates in sliced_candidates:
        sync_data_from_auth0.delay(
            candidates=candidates, connection_name=connection_name, dryrun=dryrun
        )


@job("ad_hoc")
def sync_data_from_auth0(
    candidates: list[int], connection_name: str, dryrun: bool = True
) -> None:
    authn_service = get_auth_service()
    sso_service = get_sso_service()
    failed_updated_record = []
    success_updated_record = []

    for maven_user_id in candidates:
        # For each user, query the Auth0 data based on the maven user id and the connection
        # We can't query the user_external_id because it is not support in Auth0 side.
        query = {
            "q": f"app_metadata.maven_user_id:{maven_user_id} AND identities.connection:{connection_name}",
            "fields": [
                "user_id",
                "email",
                "first_name",
                "last_name",
                "external_user_id",
                "identities.connection",
            ],
        }
        auth0_users = authn_service.management_client.search(query=query)
        # Void throttling
        sleep(0.5)
        # The identities could be multiple due to relinking feature
        maven_identities = sso_service.fetch_identities(user_id=maven_user_id)

        if len(auth0_users) == 0:
            # The auth0 user should be only 1
            log.error(
                f"The query auth0 user based on {maven_user_id} "
                f"and connection {connection_name} return empty auth0 user"
            )
            for maven_identity in maven_identities:
                failed_updated_record.append((maven_identity.id, FAILED_REASON_1))
                stats.increment(
                    metric_name=f"{SSO_VALIDATION_METRICS_PREFIX}.{METRICS_NAME}",
                    pod_name=stats.PodNames.CORE_SERVICES,
                    tags=[f"reason:{FAILED_REASON_1.replace(' ', '-')}"],
                )
            continue
        else:
            if not dryrun:
                for auth0_user in auth0_users:
                    # Write the user metadata to the user_external_identity database
                    sso_user: UserExternalIdentity | None = None
                    dup_maven_identities_list = []
                    for maven_identity in maven_identities:
                        # to double-check there is exactly 1 match in the maven identities and the auth0 users
                        if (
                            auth0_user.get("external_user_id")
                            == maven_identity.external_user_id
                            and auth0_user.get("identities")[0].get("connection")
                            == connection_name
                        ):
                            if not sso_user:
                                sso_user = maven_identity
                            else:
                                dup_maven_identities_list.append(sso_user.id)
                                failed_updated_record.append(
                                    (
                                        sso_user.id,
                                        FAILED_REASON_2,
                                    )
                                )
                                stats.increment(
                                    metric_name=f"{SSO_VALIDATION_METRICS_PREFIX}.{METRICS_NAME}",
                                    pod_name=stats.PodNames.CORE_SERVICES,
                                    tags=[
                                        f"reason:{FAILED_REASON_2.replace(' ', '-')}"
                                    ],
                                )
                    if len(dup_maven_identities_list) > 0:
                        # It should not happen
                        log.error(
                            f"Duplicate external_user_id in the {connection_name} with ids: {dup_maven_identities_list}"
                        )
                        continue
                    if not sso_user:
                        # This should not happen, because we took the Maven DB as the source of truth
                        log.error(
                            f"Missing user external identity record from the auth0 user {auth0_user.get('user_id')}",
                            data_classification="confidential",
                            auth_related="true",
                        )
                        stats.increment(
                            metric_name=f"{SSO_VALIDATION_METRICS_PREFIX}.{METRICS_NAME}",
                            pod_name=stats.PodNames.CORE_SERVICES,
                            tags=[f"reason:{FAILED_REASON_4.replace(' ', '-')}"],
                        )
                        continue

                    log.info(
                        f"Start writing data to the database for id {sso_user.id}.",
                        user_external_identity_id=sso_user.id,
                        data_classification="confidential",
                        auth_related="true",
                    )
                    try:
                        sso_user = dataclasses.replace(
                            sso_user,
                            sso_email=auth0_user.get("email", ""),
                            auth0_user_id=auth0_user.get("user_id"),
                            sso_user_first_name=auth0_user.get("first_name", ""),
                            sso_user_last_name=auth0_user.get("last_name", ""),
                        )
                        updated = sso_service.identities.update(instance=sso_user)
                        success_updated_record.append(updated.id)
                        log.info(
                            f"Successful update user external identity entry with id {updated.id}",
                            user_external_identity_id=sso_user.id,
                            data_classification="confidential",
                            auth_related="true",
                        )
                    except Exception as e:
                        failed_updated_record.append((sso_user.id, FAILED_REASON_3))
                        stats.increment(
                            metric_name=f"{SSO_VALIDATION_METRICS_PREFIX}.{METRICS_NAME}",
                            pod_name=stats.PodNames.CORE_SERVICES,
                            tags=[f"reason:{FAILED_REASON_3.replace(' ', '-')}"],
                        )
                        log.error(
                            f"Failed update User external identity entry with id {sso_user.id} with [{e}]",
                            user_external_identity_id=sso_user.id,
                            data_classification="confidential",
                            auth_related="true",
                        )
            else:
                log.info("It is dryrun, we won't write any data to the database.")

    log.info(
        f"Success updated {len(success_updated_record)} records and failed updated {len(failed_updated_record)} in total entries {len(candidates)}"
    )
    log.info(f"Failed updated identities are {failed_updated_record}")
