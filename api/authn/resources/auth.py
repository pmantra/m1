import json
import time
from urllib.parse import quote

from flask import redirect, request
from flask_restful import abort
from sqlalchemy.orm.exc import NoResultFound

import authn.domain.service
from authn.domain import model
from authn.domain.model import MFAData
from authn.domain.repository import user_auth
from authn.domain.service import (  # type: ignore[no-redef] # Name "authn" already defined (by an import)
    authn,
    mfa,
    user,
)
from authn.errors.idp.client_error import (
    REQUEST_TIMEOUT_ERROR,
    ClientError,
    DuplicateResourceError,
    IdentityClientError,
    RateLimitError,
    RequestsError,
)
from authn.models.user import MFAState
from authn.resources.user import UsersResource
from authn.services.integrations import mfa as mfa_integration
from authn.services.integrations.idp import (
    TokenExpiredError,
    TokenValidationError,
    TokenValidator,
)
from authn.services.integrations.mfa import (
    VerificationRequiredActions,
    decode_jwt,
    encode_jwt,
)
from authn.util.constants import (
    REFRESH_TOKEN_EXPIRE_AT_KEY,
    SECONDS_FIVE_MIN,
    SECONDS_SEVEN_DAYS,
)
from common import stats
from common.services import ratelimiting
from common.services.api import UnauthenticatedResource
from common.services.ratelimiting import (
    clear_rate_limit_redis,
    get_client_ip,
    get_email_or_client_ip,
    get_request_endpoint,
)
from configuration import get_idp_config
from storage.connection import db
from utils.log import logger

log = logger(__name__)

AUTH_METRICS_PREFIX = "api.authn.resources.auth"

UNAUTHORIZED = "Unauthorized"
INVALID_REVOCATION = "Could not revoke refresh token"
INVALID_REFRESH_TOKEN = "Unknown or invalid refresh token"
INVALID_CREDENTIALS = "Oh no! Those credentials didn't work."
INVALID_AUTHORIZATION_CODE = "Invalid authorization code"
USER_INACTIVE = "Your account is no longer active"
MFA_SEND_ERROR = "Error sending verification code via SMS, please try again"
TWILIO_SEND_ERROR = "Too many requests"
BAD_REQUEST_STATUS = 400
UNAUTHORIZED_STATUS = 401
FORBIDDEN_STATUS = 403
CONFLICT_STATUS = 409
TOO_MANY_REQUEST_STATUS = 429
UNIVERSAL_LOGIN_SIGN_IN_FLOW = "universal_login_sign_in_flow"
UNIVERSAL_LOGIN_SSO_LOGIN_FLOW = "universal_login_sso_login_flow"


class OauthTokenResource(UnauthenticatedResource):
    @ratelimiting.ratelimited(
        attempts=5,
        cooldown=(60 * 60),
        reset_on_success=True,
        scope=get_email_or_client_ip,
    )
    def post(self):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        """The /oauth/token endpoint supports multiple auth flows

        Authorization Code Flow
            Exchange an Authorization Code for Tokens

        Resource Owner Password Grant Flow
            Exchange an email and password for Tokens
        """
        data = request.json if request.is_json else None
        if not data:
            abort(400, message="Invalid request body. JSON expected.")
        forwarded_for = request.headers.get("X-Real-IP")
        validator = TokenValidator()
        auth_service = authn.AuthenticationService()  # type: ignore[attr-defined] # Module has no attribute "AuthenticationService"
        mfa_service = mfa.MFAService()

        code, redirect_uri, client_id, is_sso, is_universal_login = (
            data.get("code", None),
            data.get("redirect_uri", None),
            data.get("client_id", None),
            data.get("is_sso", False),
            data.get("is_universal_login", False),
        )
        if code is not None:
            ###########################
            # Authorization Code Flow #
            ###########################
            if is_universal_login is True or is_universal_login == "true":
                # The Authorization Code Flow will apply to universal login (web only) and sso.
                if code is not None:
                    if not redirect_uri or not client_id:
                        if not is_sso:
                            stats.increment(
                                metric_name=f"{AUTH_METRICS_PREFIX}.{UNIVERSAL_LOGIN_SIGN_IN_FLOW}",
                                pod_name=stats.PodNames.CORE_SERVICES,
                                tags=["code:400"],
                            )
                        else:
                            stats.increment(
                                metric_name=f"{AUTH_METRICS_PREFIX}.{UNIVERSAL_LOGIN_SSO_LOGIN_FLOW}",
                                pod_name=stats.PodNames.CORE_SERVICES,
                                tags=["code:400"],
                            )
                        abort(400, message="Invalid request")

                    result = self._authorization_code_flow(
                        code=code,
                        redirect_uri=str(redirect_uri),
                        auth_service=auth_service,
                        client_id=client_id,
                        forwarded_for=forwarded_for,  # type: ignore[arg-type] # Argument "forwarded_for" to "_authorization_code_flow" of "OauthTokenResource" has incompatible type "Optional[str]"; expected "str"
                        data=data,
                        is_sso=is_sso,
                    )
                    return result
            else:
                # We currently are only supporting the Authorization Code Flow for SSO purposes
                # which is why we return the token early here and do not prompt the user for MFA
                return self._legacy_authorization_code_flow(
                    code=code,
                    redirect_uri=redirect_uri,
                    forwarded_for=forwarded_for,  # type: ignore[arg-type] # Argument "forwarded_for" to "_legacy_authorization_code_flow" of "OauthTokenResource" has incompatible type "Optional[str]"; expected "str"
                    auth_service=auth_service,
                )

        ######################################
        # Resource Owner Password Grant Flow #
        ######################################
        metrics_name = "resource_password_login_flow"
        email, password, client_id = (
            data.get("email"),
            data.get("password"),
            data.get("client_id", None),
        )

        auth_repo = user_auth.UserAuthRepository(session=db.session, is_in_uow=True)
        user_service = user.UserService()

        # Validate user is active
        existing_user = self._get_active_user(email=email, user_service=user_service)

        # Update the IDP with the user's current identities
        # This is to support the legacy x-maven-user-identities header which some services rely on
        # We can do this before auth because we aren't accepting any user input to modify these roles
        try:
            auth_service.update_user_roles(user_id=existing_user.id, email=email)
        except IdentityClientError:
            category = get_request_endpoint()
            scope = get_email_or_client_ip()
            clear_rate_limit_redis(category, scope)
            stats.increment(
                metric_name=f"{AUTH_METRICS_PREFIX}.{metrics_name}",
                pod_name=stats.PodNames.CORE_SERVICES,
                tags=["code:400"],
            )
            abort(400, message="Something went wrong, please try again.")
        except (DuplicateResourceError, ClientError) as err:
            category = get_request_endpoint()
            scope = get_email_or_client_ip()
            clear_rate_limit_redis(category, scope)
            stats.increment(
                metric_name=f"{AUTH_METRICS_PREFIX}.update_user_role_in_password_login_flow",
                pod_name=stats.PodNames.CORE_SERVICES,
                tags=[f"code:{err.code}"],
            )
            abort(err.code, message=err.message)

        token = self._resource_owner_password_flow(
            email=email,
            password=password,
            forwarded_for=forwarded_for,  # type: ignore[arg-type] # Argument "forwarded_for" to "_resource_owner_password_flow" of "OauthTokenResource" has incompatible type "Optional[str]"; expected "str"
            auth_service=auth_service,
            client_id=client_id,
        )
        # Directly fetch the expire time from the access token and the expires_at is epoch time
        expires_at = validator.get_token_expires_at(token.get("access_token"))
        if expires_at:
            token["expires_at"] = expires_at
        # Currently the expiration time for refresh token is 7 days. We add 5 minutes as buffer
        refresh_token_expire_time = (
            int(time.time()) + SECONDS_SEVEN_DAYS - SECONDS_FIVE_MIN
        )
        token[REFRESH_TOKEN_EXPIRE_AT_KEY] = refresh_token_expire_time

        (require_mfa, enforcement_reason) = mfa_service.get_user_mfa_status(
            user_id=existing_user.id
        )
        log.info(f"User {existing_user.id} is require mfa: {require_mfa}")
        # When MFA is enabled, we do not return the access token. We return MFA data instead.
        if require_mfa:
            user_mfa = mfa_service.get(user_id=existing_user.id)
            if user_mfa is None or user_mfa.mfa_state != MFAState.ENABLED:
                stats.increment(
                    metric_name=f"{AUTH_METRICS_PREFIX}.require_mfa_enrollment",
                    pod_name=stats.PodNames.CORE_SERVICES,
                    tags=[f"enforcement_reason:{enforcement_reason.name.lower()}"],
                )
                # Store a refresh token for this user in their UserAuth record.
                # After MFA verification is completed, we can use the full scope refresh token
                # to get a full scope access token to be returned in the MFA verification endpoint.
                auth_repo.set_refresh_token(
                    user_id=existing_user.id, refresh_token=token.get("refresh_token")
                )
                db.session.commit()

                jwt = encode_jwt(VerificationRequiredActions.REQUIRE_MFA, existing_user)
                expires_at = decode_jwt(jwt)["exp"]
                return {
                    "access_token": jwt,
                    "expires_at": expires_at,
                    "mfa_enrollment_required": True,
                    "mfa_enforcement_reason": enforcement_reason.name,
                    "user_id": existing_user.id,
                }

            try:
                mfa_data = self._mfa_response_data(
                    user=existing_user,
                    refresh_token=token.get("refresh_token"),
                    mfa_service=mfa_service,
                    auth_repo=auth_repo,
                )
                mfa_data.enforcement_reason = enforcement_reason.name
                if mfa_data:
                    return {"mfa": mfa_data.__dict__}
            except mfa.UserMFAIntegrationError:
                return (
                    {"message": MFA_SEND_ERROR},
                    FORBIDDEN_STATUS,
                )
            except mfa.UserMFARateLimitError:
                return {"message": TWILIO_SEND_ERROR}, TOO_MANY_REQUEST_STATUS
        stats.increment(
            metric_name=f"{AUTH_METRICS_PREFIX}.{metrics_name}",
            pod_name=stats.PodNames.CORE_SERVICES,
            tags=["code:200"],
        )
        return {**token, "user_id": existing_user.id}

    @staticmethod
    def _legacy_authorization_code_flow(  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        code: str,
        redirect_uri: str,
        forwarded_for: str,
        auth_service: authn.AuthenticationService,  # type: ignore[name-defined] # Name "authn.AuthenticationService" is not defined
    ):
        """Exchange an authorization code for an access token"""
        token = None
        metrics_name = "legacy_sso_login_flow"
        try:
            token = auth_service.create_token(
                code=code, redirect_uri=redirect_uri, forwarded_for=forwarded_for
            )
        except (RateLimitError, RequestsError) as err:
            stats.increment(
                metric_name=f"{AUTH_METRICS_PREFIX}.{metrics_name}",
                pod_name=stats.PodNames.CORE_SERVICES,
                tags=[f"code:{err.code}"],
            )
            abort(err.code, message=err.message)
        except (DuplicateResourceError, ClientError) as err:
            category = get_request_endpoint()
            scope = get_email_or_client_ip()
            clear_rate_limit_redis(category, scope)
            stats.increment(
                metric_name=f"{AUTH_METRICS_PREFIX}.legacy_code_login_flow",
                pod_name=stats.PodNames.CORE_SERVICES,
                tags=[f"code:{err.code}"],
            )
            abort(err.code, message=err.message)

        if not token or not token.get("access_token"):
            stats.increment(
                metric_name=f"{AUTH_METRICS_PREFIX}.{metrics_name}",
                pod_name=stats.PodNames.CORE_SERVICES,
                tags=[f"code:{UNAUTHORIZED_STATUS}"],
            )
            abort(UNAUTHORIZED_STATUS, message=INVALID_AUTHORIZATION_CODE)
        stats.increment(
            metric_name=f"{AUTH_METRICS_PREFIX}.{metrics_name}",
            pod_name=stats.PodNames.CORE_SERVICES,
            tags=["code:200"],
        )
        validator = TokenValidator()
        decoded_token = validator.decode_token("bearer " + token.get("access_token"))  # type: ignore[union-attr] # Item "None" of "Optional[Any]" has no attribute "get"
        user_id: str = str(decoded_token.get("user_id"))
        if user_id:
            token["user_id"] = user_id  # type: ignore[index] # Unsupported target for indexed assignment ("Optional[Any]")
        expires_at = validator.get_token_expires_at(token.get("access_token"))  # type: ignore[union-attr] # Item "None" of "Optional[Any]" has no attribute "get"
        if expires_at:
            token["expires_at"] = expires_at  # type: ignore[index] # Unsupported target for indexed assignment ("Optional[Any]")
        # Currently the expiration time for refresh token is 7 days. We add 5 minutes as buffer
        refresh_token_expire_time = (
            int(time.time()) + SECONDS_SEVEN_DAYS - SECONDS_FIVE_MIN
        )
        token[REFRESH_TOKEN_EXPIRE_AT_KEY] = refresh_token_expire_time  # type: ignore[index] # Unsupported target for indexed assignment ("Optional[Any]")
        return token

    @staticmethod
    def _authorization_code_flow(  # type: ignore[no-untyped-def] # Function is missing a return type annotation #type: ignore[no-untyped-def] # Function is missing a type annotation for one or more arguments
        code: str,
        redirect_uri: str,
        client_id: str,
        forwarded_for: str,
        auth_service: authn.AuthenticationService,  # type: ignore[name-defined] # Name "authn.AuthenticationService" is not defined
        data=None,
        is_sso: bool = False,
    ):
        """Exchange an authorization code for an access token"""
        token = None
        metric_name = (
            UNIVERSAL_LOGIN_SSO_LOGIN_FLOW if is_sso else UNIVERSAL_LOGIN_SIGN_IN_FLOW
        )

        try:
            token = auth_service.create_token(
                code=code,
                redirect_uri=redirect_uri,
                client_id=client_id,
                forwarded_for=forwarded_for,
            )
            if not token or not token.get("access_token"):
                stats.increment(
                    metric_name=f"{AUTH_METRICS_PREFIX}.{metric_name}",
                    pod_name=stats.PodNames.CORE_SERVICES,
                    tags=[f"code:{UNAUTHORIZED_STATUS}"],
                )
                abort(UNAUTHORIZED_STATUS, message=INVALID_AUTHORIZATION_CODE)

            validator = TokenValidator()
            decoded_token = validator.decode_token(
                "bearer " + token.get("access_token")
            )
            external_id: str = str(decoded_token.get("sub"))
            user_id: str = str(decoded_token.get("user_id"))
            is_sign_up_flow = str(decoded_token.get("sign_up_flow"))
            if user_id:
                token["user_id"] = user_id
                log.info("User got token from the Auth0 successfully", user_id=user_id)
            expires_at = validator.get_token_expires_at(token.get("access_token"))
            if expires_at:
                token["expires_at"] = expires_at
            token["sign_up_flow"] = is_sign_up_flow
            # Currently the expiration time for refresh token is 7 days. We add 5 minutes as buffer
            refresh_token_expire_time = (
                int(time.time()) + SECONDS_SEVEN_DAYS - SECONDS_FIVE_MIN
            )
            token[REFRESH_TOKEN_EXPIRE_AT_KEY] = refresh_token_expire_time

            # If it is sso flow, we will return the token at this point.
            if is_sso:
                if user_id:
                    log.info("User is in the SSO login flow", user_id=user_id)
                stats.increment(
                    metric_name=f"{AUTH_METRICS_PREFIX}.{metric_name}",
                    pod_name=stats.PodNames.CORE_SERVICES,
                    tags=["code:200"],
                )
                return token

            if signup_user(
                external_id=external_id, auth_service=auth_service, data=data
            ):
                log.info("User is in the sign up flow", user_id=user_id)
                metric_name = "universal_login_sign_up_flow"
                # refresh the token to get a new token with updated user id and meta_data
                token = auth_service.refresh_token(
                    client_id=client_id, refresh_token=token.get("refresh_token")
                )
                token["flow"] = "signup"
                expires_at = validator.get_token_expires_at(token.get("access_token"))
                if expires_at:
                    token["expires_at"] = expires_at
                # Currently the expiration time for refresh token is 7 days. We add 5 minutes as buffer
                refresh_token_expire_time = (
                    int(time.time()) + SECONDS_SEVEN_DAYS - SECONDS_FIVE_MIN
                )
                token[REFRESH_TOKEN_EXPIRE_AT_KEY] = refresh_token_expire_time
        except (RateLimitError, RequestsError, IdentityClientError) as err:
            stats.increment(
                metric_name=f"{AUTH_METRICS_PREFIX}.{metric_name}",
                pod_name=stats.PodNames.CORE_SERVICES,
                tags=[f"code:{err.code}"],
            )
            category = get_request_endpoint()
            scope = get_email_or_client_ip()
            clear_rate_limit_redis(category, scope)
            abort(err.code, message=err.message)
        except (DuplicateResourceError, ClientError) as err:
            category = get_request_endpoint()
            scope = get_email_or_client_ip()
            clear_rate_limit_redis(category, scope)
            stats.increment(
                metric_name=f"{AUTH_METRICS_PREFIX}.code_login_flow",
                pod_name=stats.PodNames.CORE_SERVICES,
                tags=[f"code:{err.code}"],
            )
            abort(err.code, message=err.message)

        stats.increment(
            metric_name=f"{AUTH_METRICS_PREFIX}.{metric_name}",
            pod_name=stats.PodNames.CORE_SERVICES,
            tags=["code:200"],
        )
        return token

    @staticmethod
    def _get_active_user(email: str, user_service: user.UserService):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        existing_user = user_service.get_by_email(email=email)
        if existing_user is None:
            log.warning("User not found.")
            stats.increment(
                metric_name=f"{AUTH_METRICS_PREFIX}.password_login_flow",
                pod_name=stats.PodNames.CORE_SERVICES,
                tags=[f"code:{UNAUTHORIZED_STATUS}"],
            )
            abort(UNAUTHORIZED_STATUS, message=INVALID_CREDENTIALS)

        if not existing_user.active:
            log.warning(f"User [{existing_user.id}] is not active.")
            stats.increment(
                metric_name=f"{AUTH_METRICS_PREFIX}.password_login_flow",
                pod_name=stats.PodNames.CORE_SERVICES,
                tags=[f"code:{FORBIDDEN_STATUS}"],
            )
            abort(FORBIDDEN_STATUS, message=USER_INACTIVE)

        return existing_user

    @staticmethod
    def _resource_owner_password_flow(  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        email: str,
        password: str,
        forwarded_for: str,
        auth_service: authn.AuthenticationService,  # type: ignore[name-defined] # Name "authn.AuthenticationService" is not defined
        client_id: str = None,  # type: ignore[assignment] # Incompatible default for argument "client_id" (default has type "None", argument has type "str")
    ):
        """Exchange the resource owner's email and password for an access token"""
        if not email or not password:
            stats.increment(
                metric_name=f"{AUTH_METRICS_PREFIX}.password_login_flow",
                pod_name=stats.PodNames.CORE_SERVICES,
                tags=[f"code:{BAD_REQUEST_STATUS}"],
            )
            abort(BAD_REQUEST_STATUS, message=INVALID_CREDENTIALS)

        token = None
        try:
            token = auth_service.create_token(
                email=email,
                password=password,
                forwarded_for=forwarded_for,
                client_id=client_id,
            )
        except (RateLimitError, RequestsError) as err:
            if err.message == REQUEST_TIMEOUT_ERROR:
                category = get_request_endpoint()
                scope = get_email_or_client_ip()
                clear_rate_limit_redis(category, scope)
            stats.increment(
                metric_name=f"{AUTH_METRICS_PREFIX}.password_login_flow",
                pod_name=stats.PodNames.CORE_SERVICES,
                tags=[f"code:{err.code}"],
            )
            abort(err.code, message=err.message)
        except (DuplicateResourceError, ClientError) as err:
            category = get_request_endpoint()
            scope = get_email_or_client_ip()
            clear_rate_limit_redis(category, scope)
            stats.increment(
                metric_name=f"{AUTH_METRICS_PREFIX}.password_login_flow",
                pod_name=stats.PodNames.CORE_SERVICES,
                tags=[f"code:{err.code}"],
            )
            abort(err.code, message=err.message)

        if not token or not token.get("access_token"):
            stats.increment(
                metric_name=f"{AUTH_METRICS_PREFIX}.password_login_flow",
                pod_name=stats.PodNames.CORE_SERVICES,
                tags=[f"code:{UNAUTHORIZED_STATUS}"],
            )
            abort(UNAUTHORIZED_STATUS, message=INVALID_CREDENTIALS)
        return token

    @staticmethod
    def _mfa_response_data(
        user: model.User,
        refresh_token: str,
        mfa_service: mfa.MFAService,
        auth_repo: user_auth.UserAuthRepository,
    ) -> MFAData:
        mfa_config = mfa_service.get(user_id=user.id)  # type: ignore[arg-type] # Argument "user_id" to "get" of "MFAService" has incompatible type "Optional[int]"; expected "int"

        phone_number = mfa_config.sms_phone_number  # type: ignore[union-attr] # Item "None" of "Optional[UserMFA]" has no attribute "sms_phone_number"
        if phone_number is None:
            abort(
                CONFLICT_STATUS,
                message="User has MFA enabled but no phone number added.",
            )

        try:
            mfa_service.send_challenge(phone_number)  # type: ignore[arg-type] # Argument 1 to "send_challenge" of "MFAService" has incompatible type "Union[str, Any, None]"; expected "str"
        except (mfa.UserMFAIntegrationError, mfa.UserMFARateLimitError) as err:
            raise err

        # Store a refresh token for this user in their UserAuth record
        # When they verify MFA, we can refresh that token and return an access_token in the MFA verification endpoint
        auth_repo.set_refresh_token(user_id=user.id, refresh_token=refresh_token)  # type: ignore[arg-type] # Argument "user_id" to "set_refresh_token" of "UserAuthRepository" has incompatible type "Optional[int]"; expected "int"
        db.session.commit()

        encoded_jwt = mfa_integration.encode_jwt(
            mfa_integration.VerificationRequiredActions.LOGIN, user
        )
        message = mfa_integration.message_for_sms_code_sent(phone_number)  # type: ignore[arg-type] # Argument 1 to "message_for_sms_code_sent" has incompatible type "Union[str, Any, None]"; expected "str"
        last_four = phone_number[-4:]  # type: ignore[index] # Value of type "Union[str, Any, None]" is not indexable
        return MFAData(
            jwt=encoded_jwt, message=message, sms_phone_number_last_four=last_four
        )


class OauthRefreshTokenResource(UnauthenticatedResource):
    @ratelimiting.ratelimited(attempts=25, cooldown=(60 * 60), reset_on_success=True)
    def post(self):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        data = request.json if request.is_json else None
        client_id, refresh_token = data.get("client_id"), data.get("refresh_token")
        auth_service = authn.AuthenticationService()  # type: ignore[attr-defined] # Module has no attribute "AuthenticationService"

        if refresh_token is None:
            abort(FORBIDDEN_STATUS, message=INVALID_REFRESH_TOKEN)

        try:
            token = auth_service.refresh_token(
                client_id=client_id, refresh_token=refresh_token
            )
        except RequestsError as err:
            if err.message == REQUEST_TIMEOUT_ERROR:
                category = get_request_endpoint()
                scope = get_client_ip()
                clear_rate_limit_redis(category, scope)
            abort(err.code, message=err.message)
        except (DuplicateResourceError, ClientError) as err:
            category = get_request_endpoint()
            scope = get_email_or_client_ip()
            clear_rate_limit_redis(category, scope)
            stats.increment(
                metric_name=f"{AUTH_METRICS_PREFIX}.refresh_token",
                pod_name=stats.PodNames.CORE_SERVICES,
                tags=[f"code:{err.code}"],
            )
            abort(err.code, message=err.message)

        if not token or not token.get("access_token"):
            abort(FORBIDDEN_STATUS, message=INVALID_REFRESH_TOKEN)
        else:
            validator = TokenValidator()
            # Directly fetch the expire time from the access token and the expires_at is epoch time
            expires_at = validator.get_token_expires_at(token.get("access_token"))
            if expires_at:
                token["expires_at"] = expires_at
            return token


class OauthValidateTokenResource(UnauthenticatedResource):
    def post(self):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        token_dict = {}
        authenticated_user = None
        bearer_header = request.headers.get("Authorization")
        try:
            validator = TokenValidator()
            token_dict = validator.decode_token(bearer_header)  # type: ignore[arg-type] # Argument 1 to "decode_token" of "TokenValidator" has incompatible type "Optional[str]"; expected "str"
        except TokenExpiredError as err:
            log.warning(f"Token invalid: {err}")
            abort(UNAUTHORIZED_STATUS, message=str(err))
        except TokenValidationError as err:
            log.warning(f"Token invalid: {err}")
            abort(FORBIDDEN_STATUS, message=str(err))

        if "user_id" in token_dict:
            try:
                user_service = user.UserService()
                authenticated_user = user_service.get_user(
                    user_id=token_dict.get("user_id")  # type: ignore[arg-type] # Argument "user_id" to "get_user" of "UserService" has incompatible type "Optional[Any]"; expected "int"
                )
            except NoResultFound:
                log.warning(f"User not found: {token_dict.get('user_id')}")
                abort(FORBIDDEN_STATUS, message=UNAUTHORIZED)

        if (authenticated_user is None) or (not authenticated_user.active):
            abort(FORBIDDEN_STATUS, message=UNAUTHORIZED)

        # Get the identities from the claim to satisfy some legacy role-based authorization
        # Authenticator/Sessionizer add these identities to an X-Maven-User-Identities header
        identities = token_dict.get("identities") or []
        if len(identities) == 0:
            # If we failed to get identities from the claim we should check the database as a fallback
            # We can evaluate the ongoing need for this based on logging
            log.info(
                f"Identities missing in JWT claim for user {authenticated_user.id}"  # type: ignore[union-attr] # Item "None" of "Optional[User]" has no attribute "id"
            )
            user_service = user.UserService()
            identities = user_service.get_identities(user_id=authenticated_user.id)  # type: ignore[union-attr,arg-type] # Item "None" of "Optional[User]" has no attribute "id" #type: ignore[arg-type] # Argument "user_id" to "get_identities" of "UserService" has incompatible type "Union[int, None, Any]"; expected "int"

        return {"user_id": authenticated_user.id, "identities": identities}  # type: ignore[union-attr] # Item "None" of "Optional[User]" has no attribute "id"


class OauthRevokeTokenResource(UnauthenticatedResource):
    def post(self):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        data = request.json if request.is_json else None
        if not data:
            abort(400, message="Bad request")
        client_id, refresh_token = (
            data.get("client_id"),
            data.get("refresh_token"),
        )

        try:
            auth_service = authn.AuthenticationService()  # type: ignore[attr-defined] # Module has no attribute "AuthenticationService"
            auth_service.revoke_token(client_id=client_id, refresh_token=refresh_token)
        except IdentityClientError:
            abort(BAD_REQUEST_STATUS, message=INVALID_REVOCATION)
        except (DuplicateResourceError, ClientError) as err:
            category = get_request_endpoint()
            scope = get_email_or_client_ip()
            clear_rate_limit_redis(category, scope)
            stats.increment(
                metric_name=f"{AUTH_METRICS_PREFIX}.revoke_token",
                pod_name=stats.PodNames.CORE_SERVICES,
                tags=[f"code:{err.code}"],
            )
            abort(err.code, message=err.message)


class AuthorizationResource(UnauthenticatedResource):
    def get(self):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        state = request.args.to_dict()
        idp_config = get_idp_config()
        client_id = request.args.get("client_id")
        app_root_path = request.args.get("app_root_path") or "app"
        # The target_uri is for FE local development purpose
        target_base_uri = request.args.get("target_base_uri", None)
        qa_email = request.args.get("qa_email", None)
        redirect_uri = f"{idp_config.base_url}/{app_root_path}/oauth/callback"
        if not client_id:
            client_id = idp_config.web_client_id
        if target_base_uri:
            redirect_uri = f"{target_base_uri}/{app_root_path}/oauth/callback"
        domain = "https://" + idp_config.custom_domain
        audience = idp_config.audience
        if "screen_hint" in state and state["screen_hint"] == "signup":
            prompt = "screen_hint=signup"
        else:
            prompt = "prompt=login"
        url_to_auth0 = f"{domain}/authorize?response_type=code&client_id={client_id}&redirect_uri={redirect_uri}&scope=openid offline_access&audience={audience}&{prompt}"
        if qa_email:
            encoded_qa_email = quote(qa_email)
            url_to_auth0 += f"&login_hint={encoded_qa_email}"
        if state:
            state_str: str = json.dumps(state)
            log.info(f"state attach to url, content is {state_str}")
            url_to_auth0 = f"{url_to_auth0}&state={state_str}"
        if "ui_locales" in state:
            ui_locales = state["ui_locales"]
            url_to_auth0 = f"{url_to_auth0}&ui_locales={ui_locales}"
        log.info(f"URL to Auth0 is {url_to_auth0}")

        return redirect(url_to_auth0, code=302)


class LogoutResource(UnauthenticatedResource):
    def get(self):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        return_to = request.args.get("return_to")
        client_id = request.args.get("client_id")

        idp_config = get_idp_config()
        domain = "https://" + idp_config.custom_domain
        if not client_id:
            client_id = idp_config.web_client_id

        url = f"{domain}/v2/logout?client_id={client_id}"
        if return_to:
            url = f"{url}&returnTo={return_to}"
        log.info(f"url to auth0 is {url}")

        response = redirect(url, code=302)
        # Add CORS headers to the response
        log.info(f"base url is {idp_config.base_url}")
        response.headers["Access-Control-Allow-Origin"] = idp_config.base_url
        response.headers[
            "Access-Control-Allow-Methods"
        ] = "GET, POST, PUT, DELETE, OPTIONS"
        response.headers["Access-Control-Allow-Headers"] = "Content-Type, Authorization"

        return response


class SignupResource(UnauthenticatedResource):
    def post(self):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        log.info("processing a signup request.")
        data = request.json if request.is_json else None
        if not data:
            abort(BAD_REQUEST_STATUS, message="Invalid request body. JSON expected.")
        external_id: str = data.get("id")
        if not external_id:
            abort(BAD_REQUEST_STATUS, message="Invalid external_id for sign up.")

        auth_service = authn.AuthenticationService()  # type: ignore[attr-defined] # Module has no attribute "AuthenticationService"
        is_user_created = False
        try:
            log.info("processing a signup user.")
            is_user_created = signup_user(
                external_id=external_id, auth_service=auth_service, data=data
            )
        except Exception as err:
            log.info(f"Failed to signup user {external_id}: {err}")
            abort(BAD_REQUEST_STATUS, message=str(err))
        return {"is_sign_up": is_user_created, "status": "success"}


def signup_user(  # type: ignore[no-untyped-def] # Function is missing a return type annotation
    external_id: str, auth_service: authn.AuthenticationService, data: dict = None  # type: ignore[name-defined,assignment] # Name "authn.AuthenticationService" is not defined #type: ignore[assignment] # Incompatible default for argument "data" (default has type "None", argument has type "Dict[Any, Any]")
):
    # check if the external id is in our user auth table, if not, this is the universal login sign up flow
    # create the entry in Maven DB user and user_auth tables
    auth_user = auth_service.get_user_auth_by_external_id(external_id=external_id)
    if not auth_user:
        # universal signup flow
        log.info("Creating Maven user, user_auth and updating idp user meta_data.")
        idp_user = auth_service.get_idp_user_by_external_id(external_id=external_id)
        email = idp_user.email
        user_resource = UsersResource()

        # password is just a placeholder as the password was created in Auth0 already
        # source is hard coded for now.
        signup_data = {
            "email": email,
            "external_id": external_id,
            "agreements_accepted": True,
            "password": "mock_password",
            "source": "web",
            "subscription_agreed": False,
        }
        # update signup_data with any data that is passing from state from auth0
        # in the request body
        if data:
            signup_data.update(data)
        user_data = user_resource.signup_flow(signup_data, True)

        # Update the IDP with the user's current identities
        auth_service.update_user_roles(user_id=user_data.get("id"), email=email)
        return True
    else:
        # universal login flow, update user role to reach parity.
        auth_service.update_user_roles(user_id=auth_user.user_id)
        return False
