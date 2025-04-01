import os

import requests

from utils.log import logger

log = logger(__name__)
INTERNAL_USER_ID = os.environ.get("API_INTERNAL_USER_ID", 1)
MAVEN_INTERNAL_API_URL = os.environ.get("MAVEN_INTERNAL_API_URL", "http://api")


class InternalAPIClient(object):
    def __init__(self, user_id=INTERNAL_USER_ID):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        assert user_id, "Need a user to call the API with"
        self.user_id = user_id

    def next_availible(self, vertical_ids):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        params = {"vertical_ids": vertical_ids}

        if not MAVEN_INTERNAL_API_URL:
            log.warn("Aborted: no internal api url configured.")
            return {}

        api_endpoint = MAVEN_INTERNAL_API_URL + "/api/v1/practitioners"

        try:
            res = requests.get(
                api_endpoint, params=params, headers={"X-Maven-User-ID": self.user_id}
            )
        except Exception as e:
            log.warning("Exception getting next_availible!")
            log.warning(e)
            return {}
        else:
            if res.status_code < 300:
                return res.json()
            else:
                log.debug("Error getting next_available! Got %s", res.text)
                return {}
