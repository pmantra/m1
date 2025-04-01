import ddtrace
import requests
from auth0 import exceptions
from maven.data_access import errors

from authn.errors.idp.client_error import RateLimitError, process_auth0_err
from configuration import get_idp_config
from utils.log import logger

from .token_client import TokenClient

SCOPE = "offline_access profile openid email"
REALM = "Username-Password-Authentication"

log = logger(__name__)


class AuthenticationClient:
    def __init__(self, domain=None, audience=None, client_id=None, client_secret=None, config=None):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        idp_config = get_idp_config()
        self.domain = domain or idp_config.domain
        self.audience = audience or idp_config.audience
        self.client_id = client_id or idp_config.auth_client_id
        self.client_secret = client_secret or idp_config.auth_client_secret
        self.client_secret_dict = idp_config.client_secret_dict
        self.config = idp_config.errors

    @errors.handle
    def token_client(self, client_id: str = None):  # type: ignore[no-untyped-def,assignment] # Function is missing a return type annotation #type: ignore[assignment] # Incompatible default for argument "client_id" (default has type "None", argument has type "str") #type: ignore[assignment] # Incompatible default for argument "client_id" (default has type "None", argument has type "str")
        # this approach is for thread safety purposes
        try:
            if not client_id:
                # we use the default auth client
                client_id = self.client_id
                client_secret = self.client_secret
            else:
                client_secret = self.client_secret_dict[client_id]
            client = TokenClient(
                domain=self.domain,
                client_id=client_id,
                client_secret=client_secret,
                audience=self.audience,
            )

            return client
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
    def create_token(  # type: ignore[return] # Missing return statement
        self,
        *,
        username: str = None,  # type: ignore[assignment] # Incompatible default for argument "username" (default has type "None", argument has type "str")
        password: str = None,  # type: ignore[assignment] # Incompatible default for argument "password" (default has type "None", argument has type "str")
        code: str = None,  # type: ignore[assignment] # Incompatible default for argument "code" (default has type "None", argument has type "str")
        redirect_uri: str = None,  # type: ignore[assignment] # Incompatible default for argument "redirect_uri" (default has type "None", argument has type "str")
        forwarded_for: str = None,  # type: ignore[assignment] # Incompatible default for argument "forwarded_for" (default has type "None", argument has type "str")
        client_id: str = None,  # type: ignore[assignment] # Incompatible default for argument "client_id" (default has type "None", argument has type "str")
    ) -> str:
        try:
            if code:
                return self.token_client(client_id=client_id).authorization_code(
                    code=code,
                    redirect_uri=redirect_uri,
                )
            return self.token_client(client_id=client_id).login(
                username=username,
                password=password,
                realm=REALM,
                scope=SCOPE,
                forwarded_for=forwarded_for,
            )
        except exceptions.RateLimitError as err:
            raise RateLimitError() from err
        except (
            requests.ConnectionError,
            requests.ReadTimeout,
        ) as err:
            log.warning(f"Time out, need to retry with error type {type(err)}")
            raise errors.TransientRepositoryError(
                "Request to Auth0 is timeout", error=err
            )
        except exceptions.Auth0Error as err:
            process_auth0_err(err)

    @ddtrace.tracer.wrap()
    @errors.handle
    def refresh_token(self, *, refresh_token: str, client_id: str = None) -> str:  # type: ignore[return,assignment] # Missing return statement # Incompatible default for argument "client_id" (default has type "None", argument has type "str")
        try:
            return self.token_client(client_id=client_id).refresh_token(
                refresh_token=refresh_token
            )
        except (
            requests.ConnectionError,
            requests.ReadTimeout,
        ) as err:
            log.warning(f"Time out, need to retry with error type {type(err)}")
            raise errors.TransientRepositoryError(
                "Request to Auth0 is timeout", error=err
            )
        except exceptions.Auth0Error as err:
            process_auth0_err(err)

    @ddtrace.tracer.wrap()
    @errors.handle
    def revoke_token(self, *, refresh_token: str, client_id: str = None) -> str:  # type: ignore[return,assignment] # Missing return statement #type: ignore[assignment] # Incompatible default for argument "client_id" (default has type "None", argument has type "str") #type: ignore[assignment] # Incompatible default for argument "client_id" (default has type "None", argument has type "str")
        try:
            self.token_client(client_id=client_id).revoke_token(
                refresh_token=refresh_token
            )
        except (
            requests.ConnectionError,
            requests.ReadTimeout,
        ) as err:
            log.warning(f"Time out, need to retry with error type {type(err)}")
            raise errors.TransientRepositoryError(
                "Request to Auth0 is timeout", error=err
            )
        except exceptions.Auth0Error as err:
            process_auth0_err(err)
