from __future__ import annotations

import time

from authn.services.integrations import idp
from tasks.queues import job
from utils.log import logger

log = logger(__name__)

PAGE_SIZE = 100

enterprise_connections = {
    "dev": ["Maven-Okta", "saml-okta"],
    "qa1": ["Maven-Okta"],
    "qa2": [
        "Amazon",
        "Arkansas-BCBS",
        "CASTLIGHT",
        "Maven-Okta",
        "Optum-Mobile",
        "Optum-MSP",
        "Optum-Web",
        "PersonifyHealth",
        "Virgin-Pulse",
    ],
    "staging": ["Maven-Okta"],
    "prod": [
        "Arkansas-BCBS",
        "BonSecours",
        "CASTLIGHT",
        "Maven-OKTA-Test",
        "Optum-Mobile",
        "Optum-MSP",
        "Optum-Web",
        "PersonifyHealth",
        "Virgin-Pulse",
    ],
}

management_client = idp.ManagementClient()

# Backfill SSO users app_metadata original_email, first_name, last_name values from the Auth0 user object.

# Auth0 user query API has 1000 user return limitation. We query users with non app_metadata.original_email so
# that we can run the backfill as many times as we want.
@job("ad_hoc")
def backfill_sso_user(
    max_page: int = 10,
    dry_run: bool = True,
    env: str = "dev",
    verify_mode: bool = False,
) -> None:
    log.info("backfill_sso_user starts")
    connections = enterprise_connections[env]
    for connection in connections:
        log.info(f"backfill_sso_user query users from connection {connection}")
        if verify_mode:
            query_statement = f'identities.connection:"{connection}"'
        else:
            query_statement = f'identities.connection:"{connection}" AND (NOT _exists_:app_metadata.original_email)'
        query = {
            "q": query_statement,
            "fields": ["user_id", "app_metadata", "email", "first_name", "last_name"],
        }
        for i in range(max_page):
            users_in_page = management_client.search(
                query=query, page=i, per_page=PAGE_SIZE
            )
            log.info(
                f"backfill_sso_user processing {len(users_in_page)} users for {connection} page {i}"
            )
            if len(users_in_page) == 0:
                break
            process_users(users_in_page, connection, dry_run, verify_mode)
            log.info(
                f"backfill_sso_user complete {len(users_in_page)} users for {connection} page {i}"
            )


def process_users(auth0_users, connection, dry_run, verify_mode):  # type: ignore[no-untyped-def] # Function is missing a type annotation
    if not dry_run:
        for user in auth0_users:
            app_metadata = user.get("app_metadata", {})
            user_id = user.get("user_id")
            email = user.get("email", "")
            first_name = user.get("first_name", "")
            last_name = user.get("last_name", "")
            if verify_mode:
                if (
                    app_metadata["original_email"] != email
                    or app_metadata["original_first_name"] != first_name
                    or app_metadata["original_last_name"] != last_name
                ):
                    log.error(
                        f"back_fill_sso_user, verification failure {connection} {user_id}"
                    )
            else:
                app_metadata["original_email"] = email
                app_metadata["original_first_name"] = first_name
                app_metadata["original_last_name"] = last_name
                try:
                    management_client.update_user(
                        external_id=user_id, app_metadata=app_metadata
                    )
                except Exception as err:
                    log.error(
                        f"back_fill_sso_user, cannot backfill {connection} {user_id} {err}"
                    )
                # sleep to avoid throttling
                time.sleep(0.5)
    else:
        log.info("backfill_sso_user dry_run = True, skip processing")
