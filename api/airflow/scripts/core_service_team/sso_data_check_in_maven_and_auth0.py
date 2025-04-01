import os
from concurrent.futures import ThreadPoolExecutor, as_completed
from enum import Enum
from time import sleep

from airflow.utils import with_app_context
from authn.domain.model import UserExternalIdentity
from authn.domain.service import get_auth_service, get_sso_service
from authn.services.integrations.idp import IDPUser
from authn.util.constants import SSO_VALIDATION_METRICS_PREFIX
from common import stats
from utils.log import logger

log = logger(__name__)


class CheckStatus(Enum):
    IDENTICAL = 1
    FAILURE_WITH_AUTH0_REQUEST = 2
    FAILURE_WITH_AUTH0_USER_NOT_FOUND = 3
    FAILURE_WITH_DB_DATA_DIFF = 4
    VALUE_MISSING_IN_MAVEN_DB = 5


def compare_data(db_record: UserExternalIdentity, auth_record: IDPUser) -> bool:
    return (
        db_record.sso_email == auth_record.email
        and db_record.auth0_user_id == auth_record.user_id
        and db_record.sso_user_first_name == auth_record.first_name
        and db_record.sso_user_last_name == auth_record.last_name
    )


connection_map = {
    "maven-clinic-qa1": ["Maven-Okta"],
    "maven-clinic-qa2": [
        "Arkansas-BCBS",
        "CASTLIGHT",
        "Maven-Okta",
        "Optum-MSP",
        "Optum-Web",
        "PersonifyHealth",
        "VIRGIN_PULSE",
    ],
    "maven-clinic-staging": ["Maven-Okta"],
    "maven-clinic-prod": [
        "Arkansas-BCBS",
        "BonSecours",
        "CASTLIGHT",
        "Maven-OKTA-Test",
        "Optum-MSP",
        "Optum-Web",
        "PersonifyHealth",
        "VIRGIN_PULSE",
    ],
}


def send_metrics(status: str) -> None:
    stats.increment(
        metric_name=f"{SSO_VALIDATION_METRICS_PREFIX}.check_data_consistency",
        pod_name=stats.PodNames.CORE_SERVICES,
        tags=[f"status:{status}"],
    )


def check_data_on_auth0(local_data: UserExternalIdentity) -> tuple[int, CheckStatus]:
    if not local_data or not local_data.id:
        log.error("Missing record or record id for user external identity data")
        send_metrics(status=CheckStatus.VALUE_MISSING_IN_MAVEN_DB.name)

        return -1, CheckStatus.VALUE_MISSING_IN_MAVEN_DB

    authn_service = get_auth_service()
    # sleep before calling auth0 to avoid throttling
    sleep(0.5)
    try:
        if local_data.auth0_user_id:
            idp_user: IDPUser = authn_service.get_idp_user_by_external_id(
                external_id=local_data.auth0_user_id
            )
        else:
            log.error("Missing auth0_user_id in record.", identity_id=local_data.id)
            send_metrics(status=CheckStatus.VALUE_MISSING_IN_MAVEN_DB.name)

            return local_data.id, CheckStatus.VALUE_MISSING_IN_MAVEN_DB
    except Exception as e:
        # We catch the error and continue processing the rest records
        log.error(
            f"Failed to query data from the Auth0, {e}",
            data_classification="confidential",
            auth_related="true",
        )
        send_metrics(status=CheckStatus.FAILURE_WITH_AUTH0_REQUEST.name)

        return local_data.id, CheckStatus.FAILURE_WITH_AUTH0_REQUEST
    if not idp_user:
        log.error(
            f"Failed to find the user {local_data.external_user_id}",
            identity_id=local_data.id,
            data_classification="confidential",
            auth_related="true",
        )
        send_metrics(status=CheckStatus.FAILURE_WITH_AUTH0_REQUEST.name)

        return local_data.id, CheckStatus.FAILURE_WITH_AUTH0_USER_NOT_FOUND
    else:
        if compare_data(db_record=local_data, auth_record=idp_user):
            send_metrics(status=CheckStatus.IDENTICAL.name)

            return local_data.id, CheckStatus.IDENTICAL
        else:
            send_metrics(status=CheckStatus.FAILURE_WITH_DB_DATA_DIFF.name)
            log.warning(
                f"Data attributes mismatch between the database and the Auth0, auth0 user id <{idp_user.user_id}>",
                identity_id=local_data.id,
                data_classification="confidential",
                auth_related="true",
            )

            return local_data.id, CheckStatus.FAILURE_WITH_DB_DATA_DIFF


@with_app_context(team_ns="core_services", service_ns="authentication")
def data_compare_job() -> None:
    sso_service = get_sso_service()
    env = os.environ.get("CLOUD_PROJECT", "DEV")
    log.info(f"Starting data consistency check on {env}")
    pending_check_idps_name = connection_map.get(env.lower(), [])
    log.info(f"pending checked idps list {pending_check_idps_name}")
    all_user_external_identities = []
    for idp_name in pending_check_idps_name:
        idp_record = sso_service.idps.get_by_name(name=idp_name)
        if not idp_record:
            log.error(f"Record of the idp {idp_name} is missing in identity provider")
            continue
        idp_id = idp_record.id
        all_user_external_identities.extend(
            sso_service.identities.get_by_idp_id(idp_id=idp_id)
        )

    log.info(f"all identities size is {len(all_user_external_identities)}")
    results: list[tuple[int, CheckStatus]] = []
    with ThreadPoolExecutor(max_workers=10) as worker:
        future_to_record = {
            worker.submit(check_data_on_auth0, record): record
            for record in all_user_external_identities
        }

        for future in as_completed(future_to_record):
            record_id, check_result = future.result()
            results.append((record_id, check_result))

    check_pass_count = 0
    check_fail_count = 0
    for result in results:
        if result[1] != CheckStatus.IDENTICAL:
            check_fail_count += 1
        else:
            check_pass_count += 1
    log.info(
        f"Complete data consistency check. Pass: {check_pass_count}, Fail: {check_fail_count}, Total: {len(results)}"
    )
