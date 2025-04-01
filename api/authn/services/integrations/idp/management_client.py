from __future__ import annotations

import dataclasses
import functools
import io
import json

import ddtrace
import requests
from auth0 import exceptions, management
from flask import g
from maven import feature_flags
from maven.data_access import errors

from authn.errors.idp.client_error import ClientError, process_auth0_err
from authn.util.constants import ENABLE_MFA
from common import stats
from configuration import get_idp_config
from utils.log import logger

from .models import AppMetadata, IDPIdentity, IDPUser
from .token_client import TokenClient

IDP_BASE_METRIC_NAME = "authn_idp_client_error"

log = logger(__name__)


class ManagementClient:
    def __init__(  # type: ignore[no-untyped-def] # Function is missing a type annotation
        self, domain=None, client_id=None, client_secret=None, connection_id=None
    ):
        idp_config = get_idp_config()
        self.domain = domain or idp_config.domain
        self.client_id = client_id or idp_config.mgmt_client_id
        self.client_secret = client_secret or idp_config.mgmt_client_secret
        self.connection_id = connection_id or idp_config.base_connection_id
        self.connection_name = idp_config.base_connection_name

        # If we do not have a domain value, we consider the entire client disabled
        # This should only occur in test and local environments where an IDP tenant was not provisioned
        self.client_disabled = not self.domain
        self.config = idp_config.errors

    @property
    def token_client(self):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        # this approach is for thread safety purpose
        client = None
        inited = False
        if g:
            client = g.get("management_token_client", None)
        if client is None:
            client = TokenClient(
                domain=self.domain,
                client_id=self.client_id,
                client_secret=self.client_secret,
            )
            inited = True
        if inited and g:
            g.management_token_client = client
        return client

    @ddtrace.tracer.wrap()
    @errors.handle
    def get_job(self, job_id: str):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        try:
            return self.management_api.jobs.get(job_id)
        except exceptions.Auth0Error as err:
            process_auth0_err(err)
        except (
            requests.ConnectionError,
            requests.ReadTimeout,
        ) as err:
            log.warning(f"Time out, need to retry with error type {type(err)}")
            raise errors.TransientRepositoryError(
                "Request to Auth0 is timeout", error=err
            )

    @ddtrace.tracer.wrap()
    @errors.handle
    def send_verification_email(self, external_id: str):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        try:
            request_body = {
                "user_id": external_id,
            }
            return self.management_api.jobs.send_verification_email(request_body)
        except exceptions.Auth0Error as err:
            log.error(f"Auth0 send_verification_email call failed with {err}")
            process_auth0_err(err)
        except (
            requests.ConnectionError,
            requests.ReadTimeout,
        ) as err:
            log.warning(f"Time out, need to retry with error type {type(err)}")
            raise errors.TransientRepositoryError(
                "Request to Auth0 is timeout", error=err
            )

    @ddtrace.tracer.wrap()
    @errors.handle
    def get_user(self, external_id: str) -> IDPUser:  # type: ignore[return] # Missing return statement
        try:
            user = self.management_api.users.get(external_id)
            if user:
                return self._deserialize_user(user)
        except exceptions.Auth0Error as err:
            log.error("Failed to get the user from IDP by idp user id")
            process_auth0_err(err)
        except (
            requests.ConnectionError,
            requests.ReadTimeout,
        ) as err:
            log.warning(f"Time out, need to retry with error type {type(err)}")
            raise errors.TransientRepositoryError(
                "Request to Auth0 is timeout", error=err
            )

    @ddtrace.tracer.wrap()
    @errors.handle
    def get_user_mfa_sms_phone_number(self, external_id: str) -> str | None:  # type: ignore[return] # Missing return statement
        try:
            guardian_enrollments = self.management_api.users.get_guardian_enrollments(
                external_id
            )
            if guardian_enrollments:
                return guardian_enrollments[0].get("phone_number")
            else:
                log.warning("No guardian_enrollments found.")
                return None
        except exceptions.Auth0Error as err:
            log.error("Failed get user mfa sms phone number from IDP")
            process_auth0_err(err)
        except (
            requests.ConnectionError,
            requests.ReadTimeout,
        ) as err:
            log.warning(f"Time out, need to retry with error type {type(err)}")
            log.warning("Failed get user mfa sms phone number from IDP")
            raise errors.TransientRepositoryError(
                "Request to Auth0 is timeout", error=err
            )

    @ddtrace.tracer.wrap()
    @errors.handle
    def create_user(self, email: str, password: str, user_id: int) -> IDPUser | None:  # type: ignore[return] # Missing return statement
        if self.client_disabled:
            return None

        try:
            user = {
                "email": email,
                "name": email,
                "email_verified": True,
                "password": password,
                "connection": self.connection_name,
                "app_metadata": {"maven_user_id": user_id},
            }
            user = self.management_api.users.create(user)
            return self._deserialize_user(user)
        except exceptions.Auth0Error as err:
            log.error("Failed create user in IDP for Maven user_id", user_id=user_id)
            self._track_idp_error(action="create_user", error=err)
            process_auth0_err(err)
        except (requests.ConnectionError, requests.ReadTimeout) as err:
            log.warning(f"Time out, need to retry with error type {type(err)}")
            log.warning("Failed create user in IDP for Maven user_id", user_id=user_id)

            raise errors.TransientRepositoryError(
                "Got a transient error connecting to Auth0.", error=err
            )

    @ddtrace.tracer.wrap()
    @errors.handle
    def update_user(  # type: ignore[no-untyped-def] # Function is missing a return type annotation #type: ignore[no-untyped-def] # Function is missing a type annotation for one or more arguments
        self, external_id: str, connection_name: str | None = None, **attrs
    ):
        try:
            data = {k: v for k, v in attrs.items()}
            # If email or password are updated, then connection is required
            if "email" in data or "password" in data:
                data["connection"] = connection_name or self.connection_name
            if "email" in attrs:
                data["name"] = data["email"]
                data["email_verified"] = True
            user = self.management_api.users.update(id=external_id, body=data)
            return self._deserialize_user(user)
        except (
            requests.ConnectionError,
            requests.ReadTimeout,
        ) as err:
            log.warning("Failed update user in IDP")
            log.warning(f"Time out, need to retry with error type {type(err)}")
            raise errors.TransientRepositoryError(
                "Got a transient error connecting to Auth0.", error=err
            )
        except exceptions.Auth0Error as err:
            log.error("Failed update user in IDP")
            self._track_idp_error(action="update_user", error=err)
            process_auth0_err(err)

    @ddtrace.tracer.wrap()
    @errors.handle
    def user_access_control(self, external_id: str, is_active: bool):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        try:
            self.management_api.users.update(
                id=external_id, body={"blocked": not is_active}
            )
        except (
            requests.ConnectionError,
            requests.ReadTimeout,
        ) as err:
            log.warning("Failed update idp user block status")
            log.warning(f"Time out, need to retry with error type {type(err)}")
            raise errors.TransientRepositoryError(
                "Got a transient error connecting to Auth0.", error=err
            )
        except exceptions.Auth0Error as err:
            log.error("Failed update idp user block status")
            self._track_idp_error(action="update_user_block_status", error=err)
            process_auth0_err(err)

    @errors.handle
    def update_user_mfa(  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        self,
        user_id: str,
        external_id: str,
        enable_mfa: bool,
        phone_number: str = None,  # type: ignore[assignment] # Incompatible default for argument "phone_number" (default has type "None", argument has type "str")
        email: str = None,  # type: ignore[assignment] # Incompatible default for argument "email" (default has type "None", argument has type "str")
    ):
        try:
            log.info(
                f"update_user_mfa for Auth0 user {external_id} enable_mfa {enable_mfa} user_id {user_id}"
            )
            if enable_mfa:
                if phone_number and email:
                    payload = [
                        build_mfa_enable_migration_payload(
                            email=email,
                            external_id=external_id,
                            phone_number=phone_number,
                            user_id=user_id,
                        )
                    ]
                    # the import_users API is the only way to update a user's MFA phone number.
                    res = self.import_users(payload=payload)
                    if res is not None:
                        new_job_id = res["id"]
                        log.info("Enqueued user enable mfa job", job_id=new_job_id)
                    else:
                        log.error("no response from enable mfa job")
                else:
                    raise ClientError(
                        code=400,
                        message="Must include phone number and email when enable MFA.",
                    )
            else:
                app_metadata = {ENABLE_MFA: enable_mfa}
                self.update_user(external_id=external_id, app_metadata=app_metadata)
        except (
            requests.ConnectionError,
            requests.ReadTimeout,
        ) as err:
            log.warning(
                f"update_user_mfa failed in IDP, target mfa status:{enable_mfa}, {err}",
                user_id=user_id,
            )
            log.warning(f"Time out, need to retry with error type {type(err)}")
            raise errors.TransientRepositoryError(
                "Got a transient error connecting to Auth0.", error=err
            )
        except exceptions.Auth0Error as err:
            log.error(
                f"update_user_mfa failed in IDP, target mfa status:{enable_mfa}, {err}",
                user_id=user_id,
            )
            self._track_idp_error(action="update_user_mfa", error=err)
            process_auth0_err(err)

    @ddtrace.tracer.wrap()
    def update_company_enforce_mfa(self, external_id: str, company_enforce_mfa: bool):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        log.info(
            f"update_company_enforce_mfa for user to company_enforce_mfa {company_enforce_mfa}"
        )
        app_metadata = {"company_enforce_mfa": company_enforce_mfa}
        user = self.update_user(external_id=external_id, app_metadata=app_metadata)
        return user

    @ddtrace.tracer.wrap()
    @errors.handle
    def delete_user(self, external_id: str):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        try:
            self.management_api.users.delete(id=external_id)
        except (
            requests.ConnectionError,
            requests.ReadTimeout,
        ) as err:
            log.warning("Failed delete user in IDP")
            log.warning(f"Time out, need to retry error type {type(err)}")
            raise errors.TransientRepositoryError(
                "Got a transient error connecting to Auth0.", error=err
            )
        except exceptions.Auth0Error as err:
            log.error("Failed delete user in IDP")
            self._track_idp_error(action="delete_user", error=err)
            process_auth0_err(err)

    @ddtrace.tracer.wrap()
    @errors.handle
    def search(self, query=None, page: int = 0, per_page: int = 25):  # type: ignore[no-untyped-def] # Function is missing a return type annotation #type: ignore[no-untyped-def] # Function is missing a type annotation for one or more arguments
        """Finds a user in the IDP"""
        if query is None:
            return
        data = {k: v for k, v in query.items()}
        try:
            res = self.management_api.users.list(**data, page=page, per_page=per_page)
            if "users" in res:
                return res["users"]
            else:
                return []
        except (
            requests.ConnectionError,
            requests.ReadTimeout,
        ) as err:
            log.warning(f"Time out, need to retry with error type {type(err)}")
            raise errors.TransientRepositoryError(
                "Got a transient error connecting to Auth0.", error=err
            )
        except exceptions.Auth0Error as err:
            log.error("Failed in search user in IDP")
            process_auth0_err(err)

    @ddtrace.tracer.wrap()
    @errors.handle
    def search_by_email(self, email: str = None) -> IDPUser | None:  # type: ignore[return,assignment] # Missing return statement #type: ignore[assignment] # Incompatible default for argument "email" (default has type "None", argument has type "str") #type: ignore[assignment] # Incompatible default for argument "email" (default has type "None", argument has type "str")
        """
        Finds a user in the IDP by email address, or return None

        Only searches within the Username & Password connection type,
        ignoring SAML and other identities
        """
        if self.client_disabled:
            log.warning("Domain is disabled.")
            return None

        if email is None:
            log.warning("Email is missing.")
            return None

        query = {
            "q": f"email:{email} AND identities.connection:{self.connection_name}",
            "fields": ["email", "user_id"],
        }
        try:
            res = self.management_api.users.list(**query)
            if "users" in res and len(res["users"]) == 1:
                user = res["users"][0]
                return self._deserialize_user(user)
        except (
            requests.ConnectionError,
            requests.ReadTimeout,
        ) as err:
            log.warning("Failed to find the user in IDP by email")
            log.warning(f"Time out, need to retry with error type {type(err)}")
            raise errors.TransientRepositoryError(
                "Got a transient error connecting to Auth0.", error=err
            )
        except exceptions.Auth0Error as err:
            log.error("Failed to find the user in IDP by email")
            process_auth0_err(err)

    @ddtrace.tracer.wrap()
    @errors.handle
    def query_users_by_user_id(self, user_id: int) -> IDPUser | None:  # type: ignore[return] # Missing return statement
        query = f"app_metadata.maven_user_id:{user_id}"
        try:
            res = self.management_api.users.list(q=query, search_engine="v3")
            if "users" in res and len(res["users"]) == 1:
                user = res["users"][0]
                return self._deserialize_user(user)
            else:
                log.error(
                    f"backfill_user_auth_external_id find multiple Auth0 users for {user_id}"
                )
                return None
        except (
            requests.ConnectionError,
            requests.ReadTimeout,
        ) as err:
            log.warning("Failed to find user in IDP by user_id", user_id=user_id)
            log.warning(f"Time out, need to retry with error type {type(err)}")
            raise errors.TransientRepositoryError(
                "Got a transient error connecting to Auth0.", error=err
            )
        except exceptions.Auth0Error as err:
            log.error("Failed to find user in IDP by user_id", user_id=user_id)
            process_auth0_err(err)

    @ddtrace.tracer.wrap()
    def import_users(  # type: ignore[no-untyped-def] # Function is missing a return type annotation #type: ignore[no-untyped-def] # Function is missing a type annotation for one or more arguments
        self, payload, upsert: bool = True, send_completion_email: bool = False
    ):
        stream = io.StringIO()
        json.dump(payload, stream)
        stream.seek(0)
        log.info(
            f"In import users, the upsert is {upsert} and send completion email is {send_completion_email}"
        )
        return self.management_api.jobs.import_users(
            self.connection_id,
            stream,
            upsert=upsert,
            send_completion_email=send_completion_email,
        )

    @functools.cached_property
    @errors.handle
    def management_api(self):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        try:
            return management.Auth0(self.domain, self.token_client.management_token())
        except (
            requests.ConnectionError,
            requests.ReadTimeout,
        ) as err:
            log.warning("Failed to init the management api")
            log.warning(f"Time out, need to retry with error type {type(err)}")
            raise errors.TransientRepositoryError(
                "Got a transient error connecting to Auth0.", error=err
            )
        except exceptions.Auth0Error as err:
            log.error("Failed to init the management api")
            process_auth0_err(err)

    def _track_idp_error(self, action: str, error):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        log.error(
            f"Failed to {action} in IDP with {type(error)}, code: [{error.status_code}], message: [{error.message}]"
        )
        stats.increment(
            metric_name=f"{IDP_BASE_METRIC_NAME}.{action}",
            pod_name=stats.PodNames.CORE_SERVICES,
            tags=[
                f"status_code:{error.status_code}",
            ],
        )

    def _deserialize_user(self, user: dict) -> IDPUser:
        idp_user_fields = dataclasses.fields(IDPUser)

        user_data = self._extract_data(idp_user_fields, user)  # type: ignore[arg-type] # Argument 1 to "_extract_data" of "ManagementClient" has incompatible type "Tuple[Field[Any], ...]"; expected "List[Field[Any]]"
        idp_user = IDPUser(**user_data)

        identities = self._deserialize_identities(idp_user.identities)  # type: ignore[arg-type] # Argument 1 to "_deserialize_identities" of "ManagementClient" has incompatible type "List[IDPIdentity]"; expected "List[Dict[Any, Any]]"
        idp_user.identities = identities

        app_metadata = self._deserialize_app_metadata(idp_user.app_metadata)  # type: ignore[arg-type] # Argument 1 to "_deserialize_app_metadata" of "ManagementClient" has incompatible type "AppMetadata"; expected "Dict[Any, Any]"
        idp_user.app_metadata = app_metadata  # type: ignore[assignment] # Incompatible types in assignment (expression has type "Optional[AppMetadata]", variable has type "AppMetadata")

        return idp_user

    def _deserialize_app_metadata(self, app_metadata: dict) -> AppMetadata | None:
        if app_metadata is None:
            return None
        app_metadata_fields = dataclasses.fields(AppMetadata)

        return AppMetadata(**self._extract_data(app_metadata_fields, app_metadata))  # type: ignore[arg-type] # Argument 1 to "_extract_data" of "ManagementClient" has incompatible type "Tuple[Field[Any], ...]"; expected "List[Field[Any]]"

    def _deserialize_identities(self, identities: list[dict]) -> list[IDPIdentity]:
        if identities is None:
            return []

        idp_ident_fields = dataclasses.fields(IDPIdentity)

        return [
            IDPIdentity(**self._extract_data(idp_ident_fields, identity))  # type: ignore[arg-type] # Argument 1 to "_extract_data" of "ManagementClient" has incompatible type "Tuple[Field[Any], ...]"; expected "List[Field[Any]]"
            for identity in identities
        ]

    def _extract_data(self, fields: list[dataclasses.Field], data: dict):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        return {field.name: data[field.name] for field in fields if field.name in data}


def build_mfa_enable_migration_payload(
    email: str, external_id: str, phone_number: str, user_id: str
) -> dict | None:
    is_fix_auth0_app_metadata_override_flag_on = feature_flags.bool_variation(
        "fix-auth-0-app-metadata-override-flag",
        feature_flags.Context.create("fix-auth-0-app-metadata-override-flag"),
        default=False,
    )

    if is_fix_auth0_app_metadata_override_flag_on:
        return {
            "email": email,
            "user_id": external_id,
            "mfa_factors": [{"phone": {"value": phone_number}}],
            "app_metadata": {"enable_mfa": True, "maven_user_id": int(user_id)},
        }
    else:
        return {
            "email": email,
            "user_id": external_id,
            "mfa_factors": [{"phone": {"value": phone_number}}],
            "app_metadata": {"enable_mfa": True},
        }
