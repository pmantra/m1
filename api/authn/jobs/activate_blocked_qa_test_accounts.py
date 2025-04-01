from __future__ import annotations

import time

from authn.domain.service import AuthenticationService
from authn.services.integrations import idp
from tasks.queues import job
from utils.log import logger

log = logger(__name__)

PAGE_SIZE = 100


@job("ad_hoc")
def activate_blocked_test_accounts(
    max_page: int = 0, dry_run: bool = True, user_id: int | None = None
) -> None:
    query = {
        "q": "_exists_:app_metadata.test_pool_identifier AND blocked:true",
        "fields": ["app_metadata"],
        "sort": "last_login:1",
    }
    users = []
    management_client = idp.ManagementClient()
    authn_service = AuthenticationService()
    for i in range(max_page):
        users_in_page = management_client.search(
            query=query, page=i, per_page=PAGE_SIZE
        )
        log.info(f"Finished fetching {i + 1} page and get {len(users_in_page)} users")
        users.extend(users_in_page)
    log.info(f"Will activate {len(users)} test accounts")

    if not dry_run:
        if user_id:
            log.info(f"Activating {user_id} on Auth0")
            authn_service.user_access_control(user_id=user_id, is_active=True)
        else:
            for user in users:
                user_id = user.get("app_metadata", {}).get("maven_user_id")
                if user_id:
                    authn_service.user_access_control(user_id=user_id, is_active=True)
                    # sleep for avoid throttling
                    time.sleep(1)
