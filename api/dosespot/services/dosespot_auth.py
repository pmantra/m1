from __future__ import annotations

import json
from base64 import b64encode
from datetime import datetime, timedelta
from hashlib import sha512
from os import urandom
from time import sleep

import requests

from common import stats
from dosespot.constants import (
    DOSESPOT_API_URL_V2,
    DOSESPOT_SUBSCRIPTION_KEY,
    MAX_RETRIES,
    RETRY_DELAY,
)
from utils.log import logger

log = logger(__name__)


class DoseSpotAuth:
    def __init__(self, clinic_key, clinic_id, user_id):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        self.clinic_key = clinic_key
        self.clinic_id = clinic_id
        self.user_id = user_id
        self.phrase = self._generate_phrase()
        self.token = None
        self.token_expires = None

    def create_encrypted_clinic_key(self):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        key = f"{self.phrase}{self.clinic_key}".encode("utf8")
        decoded_key = b64encode(sha512(key).digest()).decode("utf8").rstrip("=")
        return f"{self.phrase}{decoded_key}"

    def create_encrypted_user_id(self, user_id):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        user_id = str(user_id)
        phrase = self.phrase[:22]
        key = f"{user_id}{phrase}{self.clinic_key}".encode("utf8")
        final_key = b64encode(sha512(key).digest()).decode("utf8").rstrip("=")
        return final_key

    def _generate_phrase(self):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        random_bytes = urandom(64)
        token = b64encode(random_bytes).decode("utf8")
        phrase = token[:32]
        return phrase

    def create_token(self) -> str | None:
        token_url = DOSESPOT_API_URL_V2 + "connect/token"
        auth_headers = {
            "Content-Type": "application/x-www-form-urlencoded",
            "Subscription-Key": DOSESPOT_SUBSCRIPTION_KEY,
        }
        auth_data = {
            "grant_type": "password",
            "client_id": self.clinic_id,
            "client_secret": self.clinic_key,
            "username": self.user_id,
            "password": self.clinic_key,
            "scope": "api",
        }

        request_time = datetime.utcnow()
        res = requests.post(token_url, data=auth_data, headers=auth_headers)
        log.debug(
            "Attempted to create DoseSpot access token for User: (%s)", self.user_id
        )
        if res.status_code == 200:
            result = json.loads(res.text)
            # v2 response only has the token expires_in time, so we need to compute the token expire_at time
            expires_in = result["expires_in"]
            expires_at = request_time + timedelta(seconds=expires_in)
            self.token_expires = expires_at
            return result["access_token"]
        else:
            try:
                result = json.loads(res.text)

                log.error(
                    "Failed to create DoseSpot access token",
                    status_code=res.status_code,
                    result=result,
                    user_id=self.user_id,
                    clinic_id=self.clinic_id,
                )
                if "Clinic is not valid" in result["error_description"]:
                    stats.increment(
                        metric_name="api.dosespot.create_token.clinic_invalid",
                        pod_name=stats.PodNames.MPRACTICE_CORE,
                    )
                elif "Your account is inactive" in result["error_description"]:
                    stats.increment(
                        metric_name="api.dosespot.create_token.inactive_account",
                        pod_name=stats.PodNames.MPRACTICE_CORE,
                    )
                elif "Unknown user" in result["error_description"]:
                    stats.increment(
                        metric_name="api.dosespot.create_token.unknown_user",
                        pod_name=stats.PodNames.MPRACTICE_CORE,
                    )
                else:
                    stats.increment(
                        metric_name="api.dosespot.create_token.unknown_failure",
                        pod_name=stats.PodNames.MPRACTICE_CORE,
                    )
            except Exception as e:
                result = res.text or ""
                log.error(
                    "Failed to load DoseSpot response",
                    exception=e,
                    result=result,
                )
                stats.increment(
                    metric_name="api.dosespot.create_token.load_response_failed",
                    pod_name=stats.PodNames.MPRACTICE_CORE,
                )
            return None

    def get_token(self, attempts=0):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        if self.token is None or self.token_expires is None:
            log.debug("Refresh empty DoseSpot token.")
            self.token = self.create_token()
        elif self.token_expires <= datetime.now():
            log.debug("Refresh expired DoseSpot token.")
            self.token = self.create_token()

        attempts += 1
        if (
            self.token is None or self.token_expires is None
        ) and attempts < MAX_RETRIES:
            sleep(attempts * RETRY_DELAY)
            return self.get_token(attempts)
        else:
            return self.token
