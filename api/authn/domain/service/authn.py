from __future__ import annotations

import datetime
import os
import re
import secrets
from typing import Optional

import requests
from flask import g
from redis import lock
from werkzeug import security

from activity.models import UserActivityType
from activity.service import UserActivityService
from authn.domain import model, repository, service
from authn.domain.model import UserAuth
from authn.errors.idp.client_error import (
    REQUEST_TIMEOUT_ERROR,
    UNAUTHORIZED_STATUS,
    ClientError,
    DuplicateResourceError,
    IdentityClientError,
    RateLimitError,
    RequestsError,
)
from authn.services.integrations import idp
from authn.services.integrations.idp import IDPUser
from storage.connection import db
from utils.cache import redis_client
from utils.log import logger

log = logger(__name__)

# These are copied over from the User model,
# and will be short lived here just during our migration to Auth0
SALT_LENGTH = 12
HASH_FUNCTION = "sha256"
COST_FACTOR = 10000


def get_auth_service(*, email: str = None) -> AuthenticationService:  # type: ignore[assignment] # Incompatible default for argument "email" (default has type "None", argument has type "str")
    if _is_e2e_test_context(email):
        return E2EAuthenticationService()
    else:
        return AuthenticationService()


def _is_e2e_test_context(email: str = None) -> bool:  # type: ignore[assignment] # Incompatible default for argument "email" (default has type "None", argument has type "str")
    """Determines whether this service is being accessed for AuthN during an e2e test run"""
    if email is None or email == "":
        return False

    test_pool_enabled = os.getenv("AUTH_TEST_POOL_ENABLED") in ["True", "true"]
    test_email_regex = os.getenv("AUTH_TEST_POOL_EMAIL")
    if not (test_email_regex and test_pool_enabled):
        return False

    test_email_match = re.match(test_email_regex, email)
    return test_pool_enabled and test_email_match  # type: ignore[return-value] # Incompatible return value type (got "Optional[Match[str]]", expected "bool")


class AuthenticationService:
    """
    This service handles checking whether the user has been migrated
    to Auth0 and routes to the appropriate authentication logic based on that
    """

    def __init__(  # type: ignore[no-untyped-def] # Function is missing a type annotation for one or more arguments
        self,
        auth_client=None,
        management_client=None,
        user_auth=None,
        org_auth_repo=None,
        user_service=None,
        user_activity_service=None,
        is_in_uow: bool = False,
    ):
        self._auth_client = auth_client
        self._management_client = management_client
        self.user_auth = user_auth or repository.UserAuthRepository(
            session=db.session if is_in_uow else None,
            is_in_uow=is_in_uow,
        )
        self.org_auth_repo = org_auth_repo or repository.OrganizationAuthRepository(
            session=db.session if is_in_uow else None,
            is_in_uow=is_in_uow,
        )
        self.user_service = user_service or service.UserService(is_in_uow=is_in_uow)
        self.user_activity_service = user_activity_service or UserActivityService()

    def insert_user_auth_data_from_authn_api(self, data: dict) -> None:
        """
        This function is ONLY used for the data sync from the authn_api service
        """
        data["modified_at"] = data["updated_at"]
        data.pop("updated_at")
        instance = model.UserAuth(**data)
        user_auth = self.user_auth.create(instance=instance)
        if not user_auth:
            log.error(
                "Failed create user auth from the authn-api", user_id=data.get("id")
            )

    def update_user_auth_data_from_authn_api(self, data: dict) -> None:
        """
        This function is ONLY used for the data sync from the authn_api service
        """
        data["modified_at"] = data["updated_at"]
        data.pop("updated_at")
        instance = model.UserAuth(**data)
        user_auth = self.user_auth.update(instance=instance)
        if not user_auth:
            log.error(
                "Failed update user auth from the authn-api", user_id=data.get("id")
            )

    def insert_org_auth_data_from_authn_api(self, data: dict) -> None:
        """
        This function is ONLY used for the data sync from the authn_api service
        """
        data["modified_at"] = data["updated_at"]
        data.pop("updated_at")
        instance = model.OrganizationAuth(**data)
        org_auth = self.org_auth_repo.create(instance=instance)
        if not org_auth:
            log.error(
                "Failed create org auth from the authn-api", user_id=data.get("id")
            )

    def update_org_auth_data_from_authn_api(self, data: dict) -> None:
        """
        This function is ONLY used for the data sync from the authn_api service
        """
        data["modified_at"] = data["updated_at"]
        data.pop("updated_at")
        instance = model.OrganizationAuth(**data)
        org_auth = self.org_auth_repo.update(instance=instance)
        if not org_auth:
            log.error(
                "Failed update org auth from the authn-api", user_id=data.get("id")
            )

    @property
    def auth_client(self):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        if self._auth_client is not None:
            return self._auth_client

        client = None
        inited = False
        if g:
            client = g.get("authn_auth_client", None)
        if client is None:
            client = idp.AuthenticationClient()
            inited = True
        if inited and g:
            g.authn_auth_client = client
        return client

    @property
    def management_client(self):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        if self._management_client is not None:
            return self._management_client

        client = None
        inited = False
        if g:
            client = g.get("authn_management_client", None)
        if client is None:
            client = idp.ManagementClient()
            inited = True
        if inited and g:
            g.authn_management_client = client
        return client

    def create_token(
        self,
        *,
        email: str | None = None,
        password: str | None = None,
        code: str | None = None,
        redirect_uri: str | None = None,
        forwarded_for: str | None = None,
        client_id: str | None = None,
    ) -> dict | None:
        try:
            token = self.auth_client.create_token(
                username=email,
                password=password,
                code=code,
                redirect_uri=redirect_uri,
                forwarded_for=forwarded_for,
                client_id=client_id,
            )
            if token:
                if user := self.user_service.get_by_email(email=email):  # type: ignore[arg-type] # Argument "email" to "get_by_email" of "UserService" has incompatible type "Optional[str]"; expected "str"
                    self.user_activity_service.create(
                        user_id=user.id,
                        activity_type=UserActivityType.LAST_LOGIN,
                        activity_date=datetime.datetime.utcnow(),
                    )
            return token
        except IdentityClientError:
            return None
        except requests.ReadTimeout as err:
            log.error(f"ReadTimeout when calling Auth0 create_token: {err}")
            raise RequestsError(UNAUTHORIZED_STATUS, REQUEST_TIMEOUT_ERROR)

    def refresh_token(
        self, *, refresh_token: str, client_id: str = None  # type: ignore[assignment] # Incompatible default for argument "client_id" (default has type "None", argument has type "str")
    ) -> dict | None:
        try:
            return self.auth_client.refresh_token(
                refresh_token=refresh_token, client_id=client_id
            )
        except IdentityClientError:
            return None
        except requests.ReadTimeout as err:
            log.error(f"ReadTimeout when calling Auth0 refresh_token: {err}")
            raise RequestsError(UNAUTHORIZED_STATUS, REQUEST_TIMEOUT_ERROR)

    def revoke_token(self, *, refresh_token: str, client_id: str = None) -> dict | None:  # type: ignore[assignment] # Incompatible default for argument "client_id" (default has type "None", argument has type "str")
        return self.auth_client.revoke_token(
            refresh_token=refresh_token, client_id=client_id
        )

    def check_password(
        self,
        *,
        hashed_password: str,
        email: str,
        plaintext_password: str,
        user_id: int = None,  # type: ignore[assignment] # Incompatible default for argument "user_id" (default has type "None", argument has type "int")
        forwarded_for: str = None,  # type: ignore[assignment] # Incompatible default for argument "forwarded_for" (default has type "None", argument has type "str")
    ) -> bool:
        """Checks a user password against either the IDP (if configured) or our own database"""
        user_auth = self._get_user_auth(user_id)
        if user_auth is not None:
            self._set_auth_external_id(user_auth=user_auth, email=email)
            try:
                token = self.create_token(
                    email=email,
                    password=plaintext_password,
                    forwarded_for=forwarded_for,
                )
                # If we successfuly auth against the IDP, just return True
                if token is not None:
                    log.info("Success create the access token", user_id=user_id)
                    return True
            except (
                RateLimitError,
                ClientError,
                IdentityClientError,
                requests.ReadTimeout,
            ):
                log.error("Failed to get the token", user_id=user_id)
                return False
        else:
            log.error("User unable to login due to missing UserAuth", user_id=user_id)
            # For environments without the IDP enabled, we check the database password
            return security.check_password_hash(hashed_password, plaintext_password)

        return False

    def update_password(
        self, *, user_id: int = None, email: str = None, password: str  # type: ignore[assignment] # Incompatible default for argument "user_id" (default has type "None", argument has type "int") #type: ignore[assignment] # Incompatible default for argument "email" (default has type "None", argument has type "str")
    ) -> IDPUser | None:
        """Performs an update call to the IDP to update the password"""
        user_auth = self._get_user_auth(user_id)
        if user_auth is not None:
            # _set_auth_external_id will create user if the there is no Auth0 user.
            self._set_auth_external_id(user_auth=user_auth, email=email)

            return self.management_client.update_user(
                user_auth.external_id, password=password
            )
        else:
            # If a user was not migrated to the IDP previously or if the UserAuth object was ever removed
            # We will create the UserAuth record and link the user now
            # Check if a record exists in the IDP, and create or update accordingly
            idp_user = self.management_client.search_by_email(email=email)
            if idp_user is None:
                return self.create_auth_user(  # type: ignore[return-value] # Incompatible return value type (got "Optional[UserAuth]", expected "Optional[IDPUser]")
                    email=email, password=password, user_id=user_id
                )
            else:
                idp_user = self.management_client.update_user(
                    idp_user.user_id, password=password
                )
                # The UserAuth object didn't exist before or was somehow removed
                # Set that here now to associate the user with their IDP record
                user_auth = model.UserAuth(
                    user_id=user_id, external_id=idp_user.user_id
                )
                self.user_auth.create(instance=user_auth)
                return idp_user

    def send_verification_email(self, *, user_id: int) -> None:
        """Sends verification email for the user based on their external_id"""
        user_auth = self._get_user_auth(user_id)
        if user_auth is not None:
            self.management_client.send_verification_email(
                external_id=user_auth.external_id
            )
        else:
            log.warning(
                "Could not find Auth0 user on send_verification_email",
                user_id=str(user_id),
            )

    def update_email(
        self, *, user_id: int = None, email: str = None, new_email: str  # type: ignore[assignment] # Incompatible default for argument "user_id" (default has type "None", argument has type "int") #type: ignore[assignment] # Incompatible default for argument "email" (default has type "None", argument has type "str")
    ) -> bool:
        """Updates the users email address in the IDP"""
        user_auth = self._get_user_auth(user_id)
        if user_auth is not None:
            self._set_auth_external_id(user_auth=user_auth, email=email)
            try:
                self.management_client.update_user(
                    user_auth.external_id, email=new_email
                )
            except IdentityClientError as err:
                log.info(f"Failed to update email for user_id {user_id}: {err}")
                return False
        # if user_auth is None, it means the user never successfully created the Auth0 user.
        return True

    def update_metadata(
        self,
        *,
        user_id: Optional[int] = None,
        email: Optional[str] = None,
        app_metadata: Optional[dict] = None,
    ) -> None:
        """Updates the user's app_metadata in the IDP"""
        # Sending app_metadata as None or an empty dict will clear that data on the Auth0 user profile
        # We need to be very explicit about what we are sending to Auth0 for this metadata
        log.info(f"Start uploading the user {user_id} identities to Auth0.")
        if not app_metadata:
            return

        user_auth = self._get_user_auth(user_id)
        if user_auth is None:
            log.info(f"Failed to find UserAuth record for user_id {user_id}")
            return

        self._set_auth_external_id(user_auth=user_auth, email=email)
        try:
            self.management_client.update_user(
                user_auth.external_id, app_metadata=app_metadata
            )
        except IdentityClientError as err:
            log.warning(f"Failed to set metadata for user_id {user_id}: {err}")
            raise err

    def create_auth_user(
        self, *, email: str, password: str, user_id: int
    ) -> model.UserAuth | None:
        """Creates a user in the IDP and a corresponding UserAuth record"""
        try:
            idp_user = self.management_client.create_user(
                email=email, password=password, user_id=user_id
            )
            if idp_user is not None:
                # After successful creation in the IDP, create the UserAuth record
                user_auth = model.UserAuth(
                    user_id=user_id, external_id=idp_user.user_id
                )
                self.user_auth.create(instance=user_auth)
            return idp_user
        except RequestsError as err:
            log.error(
                f"Failed to create user in request error for user_id {user_id}: {err}"
            )
            raise err
        except DuplicateResourceError:
            log.error(f"User already exists in IdP for user_id {user_id}")
            return self.management_client.search_by_email(email=email)
        except (ClientError, IdentityClientError) as err:
            log.error(f"Failed to create user in IDP for user_id {user_id}: {err}")
            raise err

    def get_idp_user_by_external_id(self, *, external_id: str) -> IDPUser:
        # get the auth0 user by external_id
        try:
            idp_user = self.management_client.get_user(external_id=external_id)
            return idp_user
        except IdentityClientError as err:
            log.warning(
                f"Failed to get user in IDP for external_id {external_id}: {err}"
            )
            raise err

    def get_user_auth_by_external_id(self, *, external_id: str):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        # query user_auth table by external_id
        return self.user_auth.get_by_external_id(external_id=external_id)

    def delete_user(self, *, user_id: id = None):  # type: ignore[no-untyped-def,valid-type] # Function is missing a return type annotation #type: ignore[valid-type] # Function "builtins.id" is not valid as a type
        """Performs an update call to the IDP to update the password"""
        user_auth = self._get_user_auth(user_id)
        if user_auth is not None and user_auth.external_id is not None:
            self.management_client.delete_user(external_id=user_auth.external_id)

    def update_user_roles(self, user_id: int, email: str | None = None) -> None:
        """Set the user's roles (member, practitioner, etc.) in the IDP"""
        identities = self.user_service.get_identities(user_id=user_id)
        app_metadata = {"maven_user_identities": identities}
        self.update_metadata(user_id=user_id, email=email, app_metadata=app_metadata)

    def update_idp_user_and_user_auth_table(
        self, user_id: int, email: str, password: str
    ) -> None:
        """
        Update the maven_user_id in the IDP user's app_metadata and the IDP user's password.
        Update the user_auth table if the user is missing.

        Parameters
        ----------
        user_id: int
            The internal user ID stored in the user table
        email: str
            The email of the user
        password: str
            The password of the user

        Raises
        ------
        IdentityClientError
            If failed to get the IDP user by email or update the IDP user's app_metadata
        """
        # Get the IDP user and update its password and maven_user_id
        try:
            idp_user = self.management_client.search_by_email(email)
            self.management_client.update_user(
                idp_user.user_id,
                password=password,
                app_metadata={"maven_user_id": user_id},
            )
        except IdentityClientError as e:
            log.error(
                f"Failed to get IDP user by email or update password/app_metadata for user_id {user_id}: {e}"
            )
            raise e

        # Update the user_auth table if the user is missing
        user_auth = self._get_user_auth(user_id)
        if user_auth is None:
            user_auth = UserAuth(user_id=user_id, external_id=idp_user.user_id)
            self.user_auth.create(instance=user_auth)

    def user_access_control(self, user_id: int, is_active: bool) -> None:
        """Block user in Auth0"""
        log.info(f"Setting user {user_id} access to Auth0 to {is_active}")
        user_auth = self._get_user_auth(user_id)
        if user_auth is not None and user_auth.external_id is not None:
            self.management_client.user_access_control(
                external_id=user_auth.external_id, is_active=is_active
            )
        else:
            log.info(f"Failed to set user {user_id} access to Auth0 to {is_active}.")

    def update_user_mfa(
        self,
        user_id: int,
        enable_mfa: bool,
        phone_number: str | None = None,
        email: str | None = None,
    ) -> None:
        log.info(f"update_user_mfa to Auth0 to {enable_mfa} for user {user_id}")
        user_auth = self._get_user_auth(user_id)
        if user_auth is not None and user_auth.external_id is not None:
            self.management_client.update_user_mfa(
                external_id=user_auth.external_id,
                enable_mfa=enable_mfa,
                phone_number=phone_number,
                email=email,
                user_id=str(user_id),
            )
        else:
            log.info(
                f"Failed to update_user_mfa user {user_id} to Auth0 to {enable_mfa}."
            )

    def create_user_auth_update_idp_user(self, user_id: int, external_id: str) -> None:
        """
        Create the user_auth table and update the maven_user_id in the IDP user's app_metadata

        Parameters
        ----------
        user_id: int
            The internal user ID stored in the user table
        external_id: str
            The id of the external idp user

        Raises
        ------
        IdentityClientError
            If failed to update the IDP user's app_metadata
        """

        user_auth = UserAuth(user_id=user_id, external_id=external_id)
        self.user_auth.create(instance=user_auth)

        # update the IDP user maven_user_id
        try:
            self.management_client.update_user(
                external_id=external_id,
                app_metadata={"maven_user_id": user_id},
            )
        except IdentityClientError as e:
            log.error(
                f"Failed to update app_metadata for user_id {user_id} external_id {external_id}: {e}"
            )
            raise e

    def get_user_auth_by_time_range(
        self, end: datetime.date, start: datetime.date | None = None
    ) -> list[model.UserAuth]:
        if start and end <= start:
            log.error(f"{end} time is less or equal to {start} time")
            return []
        return self.user_auth.get_all_by_time_range(end=end, start=start)

    def get_org_auth_by_time_range(
        self, end: datetime.date, start: datetime.date | None = None
    ) -> list[model.OrganizationAuth]:
        if start and end <= start:
            log.error(f"{end} time is less or equal to {start} time")
            return []
        return self.org_auth_repo.get_all_by_time_range(before=end, after=start)

    def _get_user_auth(self, user_id: Optional[int] = None) -> model.UserAuth | None:
        if user_id is None:
            return None
        return self.user_auth.get_by_user_id(user_id=user_id)

    def get_user_auth_by_id(self, user_auth_id: int) -> model.UserAuth | None:
        return self.user_auth.get(id=user_auth_id)

    def get_org_auth_by_id(self, org_auth_id: int) -> model.OrganizationAuth | None:
        return self.org_auth_repo.get(id=org_auth_id)

    def _set_auth_external_id(
        self, user_auth: Optional[model.UserAuth] = None, email: Optional[str] = None
    ) -> None:
        if user_auth is None:
            return
        # If we already have the external ID set, we don't need to check again
        if user_auth.external_id is not None:
            # It is possible that the user auth table has external id but Auth0 doesn't have the user mapped to it.
            # Ticket: https://mavenclinic.atlassian.net/browse/CPCS-2425
            log.info(
                f"User {user_auth.user_id} contains external id {user_auth.external_id}"
            )
            existing_idp_user = self.management_client.get_user(
                external_id=user_auth.external_id
            )
            if existing_idp_user:
                return
        log.info(
            f"User {user_auth.user_id} has external id {user_auth.external_id} but doesn't have real Auth0 user mapping to it."
        )
        idp_user = self.management_client.search_by_email(email=email)
        # Make sure the user was actually migrated correctly. If they were not, migrate them now
        if idp_user is None:
            # The most likely cause of a prior failure to migrate to the IDP is a malformed password in our database
            # Specifically, SSO users had their passwords initialized as empty strings
            # We randomize that here to work around that rather than sending that old password to the IDP again
            # This may mean the user needs to subsequently reset their password
            log.info(f"User {user_auth.user_id} doesn't have Auth0 user, creating now.")
            password = secrets.token_urlsafe(32)
            user_id = user_auth.user_id
            try:
                idp_user = self.management_client.create_user(
                    email=email, password=password, user_id=user_id
                )
            except RequestsError as err:
                log.error(
                    f"Failed to create user in request error for user_id {user_id}: {err}"
                )
            except DuplicateResourceError:
                log.error(f"User already exists in IdP for user_id {user_id}")
            except (ClientError, IdentityClientError) as err:
                log.error(f"Failed to create user in IDP for user_id {user_id}: {err}")

        # Finally, update the UserAuth record with their external ID
        if idp_user is not None:
            user_auth.external_id = idp_user.user_id
            self.user_auth.update(instance=user_auth)
            log.info(
                f"Successfully created Auth0 user for user {user_auth.user_id} and update user auth table."
            )
        else:
            self._remove_user_auth(user_auth.user_id)
            log.info(
                f"Failed created Auth0 user for user {user_auth.user_id} and remove user auth table."
            )

    def _remove_user_auth(self, user_id: int = None) -> int:  # type: ignore[assignment] # Incompatible default for argument "user_id" (default has type "None", argument has type "int")
        log.info(f"Deleting user_auth object for user_id {user_id}")
        if user_id is None:
            return 0
        return self.user_auth.delete_by_user_id(user_id=user_id)


class E2EAuthenticationService(AuthenticationService):
    """
    An Authentication Service specifically for end to end test runs

    This helps us control the volume of test users created and authenticated in our IDP
    """

    # 100 is the maximum query set by Auth0: https://auth0.com/docs/manage-users/user-search/view-search-results-by-page
    PAGE_SIZE = 100
    MAX_PAGE = 5

    def create_auth_user(  # type: ignore[return] # Missing return statement
        self, *, email: str, password: str, user_id: int
    ) -> model.UserAuth:
        """Fetch test users from the IdP and use them in e2e test."""
        try:
            # Find users in our test user pool (e.g. "test-pool-user-9@mavenclinic.com")
            # Sort by least recently logged in, so we re-use those users first
            query = {
                "q": "_exists_:app_metadata.test_pool_identifier AND (NOT _exists_:blocked OR blocked:false)",
                "fields": ["user_id", "app_metadata"],
                "sort": "last_login:1",
            }
            users = []
            for i in range(self.MAX_PAGE):
                users_in_page = self.management_client.search(
                    query=query, page=i, per_page=self.PAGE_SIZE
                )
                log.info(
                    f"Finished fetching {i+1} page and get {len(users_in_page)} users"
                )
                users.extend(users_in_page)
            log.info(f"The total number of users fetched is {len(users)}")
            redis = redis_client()
            for user in users:
                pool_identifier = user.get("app_metadata", {}).get(
                    "test_pool_identifier"
                )
                if self._checkout_user(redis=redis, lock_identifier=pool_identifier):
                    idp_id = user.get("user_id")
                    return self._update_user_credentials(
                        idp_id=idp_id, email=email, password=password, user_id=user_id
                    )
            raise AuthenticationServiceError(
                f"Test user pool ({len(users)} users) exhausted, please contact core-services-team to increase."
            )
        except IdentityClientError as err:
            log.info(f"Failed to create test IDP user {err}")

    def _checkout_user(self, redis, lock_identifier: str) -> bool:  # type: ignore[no-untyped-def] # Function is missing a type annotation for one or more arguments
        """Attempts to acquire a distributed lock on a given key"""
        lock_name = f"auth0-user-lock-{lock_identifier}"
        pool_lock = lock.Lock(redis=redis, name=lock_name, timeout=300)
        # Check if another e2e test is using this user already
        return not pool_lock.locked() and pool_lock.acquire(blocking=False)

    def _update_user_credentials(  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        self, idp_id: str, email: str, password: str, user_id: int
    ):
        """Updates user in Auth0 to have the email, password of the newly created user

        This permits logging in as this new user after the update,
        but must be done in two separate calls per Auth0 requirements
        """
        # Fails setting the password if done in a single call
        # Change the email for the Auth0 User
        self.management_client.update_user(
            external_id=idp_id, email=email, app_metadata={"maven_user_id": user_id}
        )
        # Set the password for that user
        self.management_client.update_user(external_id=idp_id, password=password)

        # Find the existing UserAuth record for the Auth0 User and remap it to the new user or create a new UserAuth
        user_auth = self.user_auth.get_by_external_id(external_id=idp_id)
        if user_auth:
            user_auth.user_id = user_id
            user_auth.refresh_token = None
            return self.user_auth.update(instance=user_auth)
        else:
            user_auth = model.UserAuth(user_id=user_id, external_id=idp_id)
            return self.user_auth.create(instance=user_auth)


class AuthenticationServiceError(Exception):
    ...
