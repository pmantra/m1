import json
import time

import jwt
import requests
from requests.adapters import HTTPAdapter

from utils.cache import redis_client
from utils.log import logger

log = logger(__name__)


def _load_credentials():  # type: ignore[no-untyped-def] # Function is missing a return type annotation
    try:
        with open("/google-svc-accounts/user-file.json") as credentials_file:
            credentials = json.load(credentials_file)
            return credentials["client_email"], credentials["private_key"]
    except FileNotFoundError as e:
        log.warning(
            "The user files service account has not been mounted into this environment.",
            exception=repr(e),
        )
        return None, None


CLOUD_STORAGE_SERVICE_ACCOUNT, CLOUD_STORAGE_KEY = _load_credentials()


def upload_file(  # type: ignore[no-untyped-def] # Function is missing a type annotation
    name,
    bucket,
    file_body,
    content_type="text/plain",
    bearer_token=None,
    auth_cache_key=None,
    acl="authenticatedRead",
):

    """
    allowed acl:
        https://developers.google.com/storage/docs/json_api/v1/objects/insert

    This function is only safe to use on objects of 5 MB or smaller. It will
    not automatically retry if it fails.

    Args:
        name (string) name of the object
        bucket (string) name of the bucket
        file_body (file-like object) should be able to be used as the payload
            of a requests.Session HTTP request.

    """

    session = _session_with_auth(auth_cache_key)
    google_cloud_storage_api = (
        f"https://www.googleapis.com/upload/storage/v1/b/{bucket}/o"
    )

    params = {"uploadType": "media", "predefinedAcl": acl, "name": name}
    headers = {"Content-Type": content_type}

    res = session.post(
        google_cloud_storage_api, params=params, headers=headers, data=file_body
    )

    if res.status_code == 200:
        log.info("Uploaded %s to %s", name, bucket)
    else:
        log.warning("Upload of %s to %s failed!", name, bucket)

        redis = redis_client(
            skip_on_fatal_exceptions=True, default_tags=["caller:storage"]
        )
        redis.delete(auth_cache_key)


def delete_file(name, bucket, auth_cache_key=None):  # type: ignore[no-untyped-def] # Function is missing a type annotation
    session = _session_with_auth(auth_cache_key)
    res = session.delete(f"https://www.googleapis.com/storage/v1/b/{bucket}/o/{name}")

    if res.status_code == 200:
        log.info("Deleted %s from %s", name, bucket)
    else:
        log.warning("Failed to delete %s from %s", name, bucket)


def _session_with_auth(  # type: ignore[no-untyped-def] # Function is missing a type annotation
    cache_key, scope=("https://www.googleapis.com/auth/devstorage.read_write")
):
    auth = GoogleCloudAPIAuthorizer(scope, cache_key=cache_key)
    bearer_token = auth.bearer_token

    log.debug("Got bearer token")

    # The max_retries below applies only to failed connections and timeouts,
    # never to requests where the server returns a response
    # http://docs.python-requests.org/en/latest/api
    session = requests.Session()
    session.mount("https://www.googleapis.com", HTTPAdapter(max_retries=5))

    session.headers.update({"Authorization": f"Bearer {bearer_token}"})
    return session


class GoogleCloudAPIAuthorizer(object):
    def __init__(  # type: ignore[no-untyped-def] # Function is missing a type annotation
        self,
        scope,
        service_account_email=CLOUD_STORAGE_SERVICE_ACCOUNT,
        private_key=CLOUD_STORAGE_KEY,
        validity_seconds=3600,
        cache_key=None,
    ):
        """
        scope can be a space-delimited list from the choices at:
            https://developers.google.com/storage/docs/json_api/
                v1/how-tos/authorizing
        """
        self.redis = redis_client(
            skip_on_fatal_exceptions=True, default_tags=["caller:storage"]
        )
        self.cache_key = cache_key

        self.service_account_email = service_account_email
        self.private_key = private_key
        self.scope = scope
        self.validity_seconds = int(max(validity_seconds, 3600))

    @property
    def bearer_token(self):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        if self.cache_key:
            bearer_token = self.redis.get(self.cache_key)
            if bearer_token:
                bearer_token = bearer_token.decode("utf-8")
                log.debug("Got bearer_token from cache.")

        if not bearer_token:
            bearer_token = self.new_bearer_token()
            log.debug("Got new bearer_token")

            if self.cache_key:
                self.redis.set(self.cache_key, bearer_token)
                self.redis.expire(self.cache_key, 3600)
                log.debug("Cached bearer_token")

        return bearer_token

    def new_bearer_token(self):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        now = int(time.time())
        claim_url = "https://accounts.google.com/o/oauth2/token"

        header = {"alg": "RS256", "typ": "JWT"}
        claims = {
            "iss": self.service_account_email,
            "scope": self.scope,
            "aud": "https://accounts.google.com/o/oauth2/token",
            "exp": now + self.validity_seconds,
            "iat": now,
        }
        body = {
            "grant_type": "urn:ietf:params:oauth:grant-type:jwt-bearer",
            "assertion": jwt.encode(claims, self.private_key, "RS256", headers=header),
        }
        res = requests.post(claim_url, data=body)

        if res.status_code == 200:
            return res.json()["access_token"]
        else:
            log.info("Problem getting new token for Google APIs!")
            log.debug("%s", res.content)
