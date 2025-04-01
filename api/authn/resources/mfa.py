import time
from dataclasses import asdict, dataclass

import jwt
from auth0 import TokenValidationError
from flask import make_response, request
from flask_restful import abort
from marshmallow import Schema, ValidationError, fields, validate

from authn.domain.repository import user_auth
from authn.domain.service import AuthenticationService, authn, mfa
from authn.errors.idp.client_error import (
    ClientError,
    DuplicateResourceError,
    RateLimitError,
    RequestsError,
)
from authn.models.user import MFAState, User
from authn.resources.auth import FORBIDDEN_STATUS, UNAUTHORIZED, UNAUTHORIZED_STATUS
from authn.resources.user import UserApiKeySchema
from authn.services.integrations import idp
from authn.services.integrations.idp import TokenExpiredError, TokenValidator
from authn.services.integrations.mfa import (
    VerificationRequiredActionNames,
    VerificationRequiredActions,
    decode_jwt,
    encode_jwt,
    message_for_sms_code_sent,
)
from authn.util.constants import (
    REFRESH_TOKEN_EXPIRE_AT_KEY,
    SECONDS_FIVE_MIN,
    SECONDS_SEVEN_DAYS,
)
from common import stats
from common.services import ratelimiting
from common.services.api import AuthenticatedResource, UnauthenticatedResource
from common.services.ratelimiting import (
    clear_rate_limit_redis,
    get_email_or_client_ip,
    get_request_endpoint,
)
from models.actions import ACTIONS, audit
from storage.connection import db
from utils import braze_events
from utils.log import logger

log = logger(__name__)

# This must match the selected option in the Twilio console. (Default is 6)
MFA_TOKEN_LENGTH = 6
MFA_METRICS_PREFIX = "api.authn.resources.mfa"


class MFAVerificationSchema(Schema):
    """
    Schema used for all requests to the /mfa/verify endpoint.
    """

    mfa_token = fields.String(
        required=True,
        validate=[validate.Length(equal=MFA_TOKEN_LENGTH), lambda x: x.isdigit()],
    )
    jwt = fields.String(required=True)


class MFAEnrollmentSchema(Schema):
    """
    Schema used for requests to the /mfa/enroll endpoint.
    """

    # not using PhoneNumber because serialization has logic about phone_number and tel_number
    # that not only aren't useful here, but actually don't work because field name is different
    sms_phone_number = fields.String()


class MFAForceEnrollmentSchema(Schema):
    """
    Schema used for requests to the /mfa/force_enroll endpoint.
    """

    jwt = fields.String(required=True)

    # not using PhoneNumber because serialization has logic about phone_number and tel_number
    # that not only aren't useful here, but actually don't work because field name is different
    sms_phone_number = fields.String()


def _refresh_auth_token(user_id: int) -> dict:
    if not user_id:
        return  # type: ignore[return-value] # Return value expected

    auth_service = authn.AuthenticationService()
    auth_repo = user_auth.UserAuthRepository()

    user_auth_instance = auth_repo.get_by_user_id(user_id=user_id)
    if not user_auth_instance or not user_auth_instance.refresh_token:
        return  # type: ignore[return-value] # Return value expected

    tokens = auth_service.refresh_token(refresh_token=user_auth_instance.refresh_token)
    if not tokens:
        abort(FORBIDDEN_STATUS, message=UNAUTHORIZED)

    return tokens  # type: ignore[return-value] # Incompatible return value type (got "Optional[Dict[Any, Any]]", expected "Dict[Any, Any]")


def _handle_get_api_key(user):  # type: ignore[no-untyped-def] # Function is missing a type annotation
    """
    This function must be called after MFA verification has been successfully completed.
    Returns a Response that can be returned from a view function.

    @param user: instance of the User model
    """

    audit(ACTIONS.login, user.id)
    log.info(
        f"User {user.id} authenticated with MFA; returning new api key.",
        user_id=user.id,
    )

    schema = UserApiKeySchema()
    data = schema.dump(user).data
    schema.validate(data)

    oauth_tokens = _refresh_auth_token(user.id)

    if oauth_tokens:
        # To get expires time of the token and include to the response
        validator = TokenValidator()
        expires_at = validator.get_token_expires_at(oauth_tokens.get("access_token"))  # type: ignore[arg-type] # Argument 1 to "get_token_expires_at" of "TokenValidator" has incompatible type "Optional[Any]"; expected "str"
        if expires_at:
            oauth_tokens["expires_at"] = expires_at
        # Currently the expiration time for refresh token is 7 days. We add 5 minutes as buffer
        refresh_token_expire_time = (
            int(time.time()) + SECONDS_SEVEN_DAYS - SECONDS_FIVE_MIN
        )
        oauth_tokens[REFRESH_TOKEN_EXPIRE_AT_KEY] = refresh_token_expire_time

    data["oauth_tokens"] = oauth_tokens

    resp = make_response(data)
    resp.headers["x-user-id"] = user.id
    resp.headers["x-user-api-key"] = user.api_key_with_ttl
    resp.headers["x-user-identities"] = user.identities
    return resp


def _handle_enable_mfa(user):  # type: ignore[no-untyped-def] # Function is missing a type annotation
    """
    This function must be called after MFA verification has been successfully completed.
    Returns a Response that can be returned from a view function.

    @param user: instance of the User model
    """

    if user.mfa_state == MFAState.DISABLED:
        abort(400, message="User has not enabled MFA for this account.")
    elif user.mfa_state == MFAState.ENABLED:
        abort(400, message="MFA has already been set up for this account.")

    user.mfa_state = MFAState.ENABLED

    # Update Auth0 user MFA status and phone number
    management_client = idp.ManagementClient()
    auth_service = AuthenticationService()
    user_auth_entry = auth_service.user_auth.get_by_user_id(user_id=user.id)
    external_id = user_auth_entry.external_id
    log.info("In resource name and start update user mfa")
    management_client.update_user_mfa(
        external_id=external_id,
        enable_mfa=True,
        phone_number=user.sms_phone_number,
        email=user.email,
        user_id=str(user.id),
    )

    db.session.commit()

    braze_events.mfa_enabled(user)
    log.info(f"Successfully enabled MFA for user {user.id}.")

    return make_response({"message": "MFA has been enabled for this account."}, 200)


def _handle_disable_mfa(user):  # type: ignore[no-untyped-def] # Function is missing a type annotation
    """
    This function must be called after MFA verification has been successfully completed.
    Returns a Response that can be returned from a view function.

    @param user: instance of the User model
    """

    user.mfa_state = MFAState.DISABLED

    # Update Auth0 user MFA status
    management_client = idp.ManagementClient()
    auth_service = AuthenticationService()
    user_auth_entry = auth_service.user_auth.get_by_user_id(user_id=user.id)
    external_id = user_auth_entry.external_id
    management_client.update_user_mfa(
        external_id=external_id, enable_mfa=False, user_id=str(user.id)
    )

    db.session.commit()

    braze_events.mfa_disabled(user)
    log.info(f"Successfully disabled MFA for user {user.id}.")

    return make_response({"message": "MFA has been disabled for this account."}, 200)


def _handle_require_mfa(user):  # type: ignore[no-untyped-def] # Function is missing a type annotation
    _handle_enable_mfa(user)
    return _handle_get_api_key(user)


# This needs to be defined after the handler functions so they're defined.
# These actions require MFA verification, and the function is called only AFTER
# ensuring the user has successfully entered the correct verification code.
# A handler function takes a User as an argument and returns a Response.
JWT_ACTION_TO_HANDLER = {
    VerificationRequiredActions.LOGIN: _handle_get_api_key,
    VerificationRequiredActions.ENABLE_MFA: _handle_enable_mfa,
    VerificationRequiredActions.DISABLE_MFA: _handle_disable_mfa,
    VerificationRequiredActions.REQUIRE_MFA: _handle_require_mfa,
}


class JWTSchema(Schema):
    action = fields.String(
        validate=validate.OneOf(VerificationRequiredActionNames), required=True
    )
    user_id = fields.Integer(required=True)
    expiry = fields.Integer(required=True, data_key="exp")
    subject = fields.String(data_key="sub")


def _send_mfa_challenge(user, phone_number, require_resend=False):  # type: ignore[no-untyped-def] # Function is missing a type annotation
    mfa_service = mfa.MFAService()
    try:
        mfa_service.begin_enable(user, phone_number, require_resend)
    except (mfa.UserMFAConfigurationError, mfa.UserMFAIntegrationError) as err:
        abort(make_response({"message": str(err)}, 400))
    except mfa.UserMFARateLimitError as err:
        abort(make_response({"message": str(err)}, 429))


def _mfa_enroll(args, user, action):  # type: ignore[no-untyped-def] # Function is missing a type annotation
    phone_number = args.get("sms_phone_number") or ""
    if not phone_number:
        return make_response(
            {"message": "Invalid phone number. Please fix and try again."}, 400
        )

    _send_mfa_challenge(user, phone_number)

    db.session.commit()

    message = message_for_sms_code_sent(phone_number)
    encoded_jwt = encode_jwt(action, user)
    return {"message": message, "jwt": encoded_jwt}, 200


class MFAEnrollmentResource(AuthenticatedResource):
    def post(self):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        log.info("MFA enrollment request received!")
        schema = MFAEnrollmentSchema()
        args = schema.load(request.json if request.is_json else {})
        return _mfa_enroll(args, self.user, VerificationRequiredActions.ENABLE_MFA)


class MFAForceEnrollmentResource(UnauthenticatedResource):
    def post(self):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        log.info("MFA force enrollment request received!")
        request_json = request.json if request.is_json else None
        if not request_json:
            abort(400, message="Missing payload")

        schema = MFAForceEnrollmentSchema()
        try:
            args = schema.load(request_json)
        except ValidationError as e:
            return {"message": e.messages}, 400

        jwt_payload = self._get_jwt_payload(args["jwt"])
        user = self._validate_jwt_payload_and_get_user(
            jwt_payload, VerificationRequiredActions.REQUIRE_MFA, self.user
        )
        return _mfa_enroll(args, user, VerificationRequiredActions.REQUIRE_MFA)

    @staticmethod
    def _get_jwt_payload(encoded_jwt):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        try:
            decoded = decode_jwt(encoded_jwt)
        except jwt.ExpiredSignatureError:
            log.error("JWT signature is expired.")
            abort(
                403,
                message="Signature has expired. Please request a new key before trying again.",
            )
        except Exception as e:
            log.exception(
                "Error decoding JWT during MFA login verification", exception=e
            )
            abort(403, message="Invalid JWT.")

        try:
            return JWTSchema().load(decoded)
        except ValidationError:
            abort(403, message="Invalid JWT.")

    @staticmethod
    def _validate_jwt_payload_and_get_user(jwt_data, expected_action, expected_user):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        if not jwt_data:
            abort(400, message="Bad request, missing JWT")
        action = jwt_data.get("action")
        # expected_action won't be None, because it should be enum value in VerificationRequiredActions
        if not action or action != expected_action.value:
            abort(403, message="Invalid action in JWT")

        user_id = jwt_data.get("user_id")
        if expected_user:
            # There is a valid API-KEY header, but its user doesn't match the user from the JWT.
            # Something went wrong, so reject the request to be safe.
            if expected_user.id != user_id:
                abort(403, message="Authentication header and signature do not match!")

            user = expected_user
        else:
            user = db.session.query(User).get(user_id)

        # something went wrong, jwt was valid but user doesn't exist
        if user is None:
            log.error("JWT contained user_id that does not exist", user_id=user_id)
            abort(403)

        return user


class MFACancellationResource(AuthenticatedResource):
    def post(self):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        log.info("MFA disable request received")

        user = self.user
        mfa_service = mfa.MFAService()

        # Practioners are not allowed to disable MFA
        if user.is_practitioner:
            return make_response(
                {"message": "MFA can not be disabled for this account."}, 403
            )

        if mfa_service.begin_disable(user) is None:
            return make_response(
                {"message": "MFA is not enabled for this account."}, 200
            )

        db.session.commit()

        message = message_for_sms_code_sent(user.sms_phone_number)
        encoded_jwt = encode_jwt(VerificationRequiredActions.DISABLE_MFA, user)
        resp = make_response(
            {"jwt": encoded_jwt, "action": "mfa_token_needed", "message": message}, 200
        )

        return resp


class MFAResendCodeResource(UnauthenticatedResource):
    @ratelimiting.ratelimited(attempts=10, cooldown=60 * 10, reset_on_success=True)
    def post(self):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        log.info("MFA resend code request received")

        # There are a couple of instances in which a user might request a resend/new code:
        # 1) they are logged in, trying to turn on MFA, and need to verify their number
        # 2) they have MFA enabled, are trying to log in, and need a verification code

        user = None

        # case 1: we have already gotten the user from the API-KEY header
        if self.user is not None:
            user = self.user

        # case 2: the client sent a jwt that we need to decode
        request_json = request.get_json(force=True)
        encoded_jwt = request_json and request_json.get("jwt")
        if encoded_jwt:
            try:
                decoded = decode_jwt(encoded_jwt)
            except jwt.ExpiredSignatureError:
                return make_response(
                    {
                        "message": "Signature has expired. Please request a new key before trying again."
                    },
                    403,
                )
            except Exception as e:
                log.exception(
                    "Error decoding JWT during MFA login verification", exception=e
                )
                abort(403, message="Invalid JWT.")

            try:
                decoded_payload = JWTSchema().load(decoded)
            except ValidationError:
                abort(403, message="Invalid JWT.")

            user_id = decoded_payload.get("user_id")
            if user_id:
                user = db.session.query(User).get(user_id)
            if user is None:
                log.error("JWT contained user_id that does not exist", user_id=user_id)
                # something went wrong, jwt was valid but user doesn't exist
                abort(403)

        # neither the API-KEY header or jwt was present
        if user is None:
            abort(403)

        phone_number = user.sms_phone_number  # type: ignore[union-attr] # Item "None" of "Optional[Any]" has no attribute "sms_phone_number"
        if not phone_number:
            abort(
                make_response(
                    {"message": "Must have a phone number stored to receive MFA code"},
                    400,
                )
            )

        # Finally, actually send the code
        _send_mfa_challenge(user, phone_number, True)

        message = message_for_sms_code_sent(phone_number)
        return {"message": message}, 200


# This is an UnauthenticatedResource because one place we do MFA verification
# is when a user is trying to log in, and they are not authenticated yet.
class MFAVerificationResource(UnauthenticatedResource):
    @ratelimiting.ratelimited(attempts=2, cooldown=60, reset_on_success=True)
    def post(self):  # type: ignore[no-untyped-def] # Function is missing a return type annotation

        # marshmallow_v1 doesn't return a validation error on schema.load(None)
        request_json = request.json if request.is_json else None
        if not request_json:
            abort(400, message="Missing payload")

        schema = MFAVerificationSchema()
        try:
            args = schema.load(request_json)
        except ValidationError as e:
            return {"message": e.messages}, 400

        try:
            decoded = decode_jwt(args["jwt"])
        except jwt.ExpiredSignatureError:
            return make_response(
                {
                    "message": "Signature has expired. Please request a new key before trying again."
                },
                403,
            )
        except Exception as e:
            log.exception(
                "Error decoding JWT during MFA login verification", exception=e
            )
            abort(403, message="Invalid JWT.")

        try:
            jwt_data = JWTSchema().load(decoded)
        except ValidationError:
            return {"message": "Invalid JWT."}, 403

        user_id = jwt_data.get("user_id")
        log.info(f"MFA verification request received for user {user_id}")
        if self.user:
            # There is a valid API-KEY header, but its user doesn't match the user from the JWT.
            # Something went wrong, so reject the request to be safe.
            if self.user.id != user_id:
                abort(403, message="Authentication header and signature do not match!")

            user = self.user
        else:
            user = db.session.query(User).get(user_id)

        # something went wrong, jwt was valid but user doesn't exist
        if user is None:
            log.error(
                f"JWT contained user id {user_id} that does not exist", user_id=user_id
            )
            abort(403)

        action = jwt_data.get("action")
        token = args["mfa_token"]
        try:
            mfa_service = mfa.MFAService()
            mfa_service.process_challenge_response(user, action, token)
        except mfa.UserMFAVerificationError:
            return make_response({"message": "Invalid or incorrect token."}, 403)

        # dispatch handler for the actual action the user wanted to perform that required verification first
        try:
            handler = JWT_ACTION_TO_HANDLER.get(VerificationRequiredActions(action))

            return handler(user)
        except (RateLimitError, RequestsError) as err:
            stats.increment(
                metric_name=f"{MFA_METRICS_PREFIX}.{action}",
                pod_name=stats.PodNames.CORE_SERVICES,
                tags=[f"code:{err.code}"],
            )
            abort(err.code, message=err.message)
        except (DuplicateResourceError, ClientError) as err:
            category = get_request_endpoint()
            scope = get_email_or_client_ip()
            clear_rate_limit_redis(category, scope)
            stats.increment(
                metric_name=f"{MFA_METRICS_PREFIX}.{action}",
                pod_name=stats.PodNames.CORE_SERVICES,
                tags=[f"code:{err.code}"],
            )
            abort(err.code, message=err.message)


@dataclass
class MFAEnforcement:
    require_mfa: bool
    mfa_enforcement_reason: str


class MFAEnforcementResource(AuthenticatedResource):
    def get(self):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        mfa_service = mfa.MFAService()
        try:
            (require_mfa, mfa_enforcement_reason) = mfa_service.get_user_mfa_status(
                user_id=self.user.id
            )
        except (RateLimitError, RequestsError) as err:
            stats.increment(
                metric_name=f"{MFA_METRICS_PREFIX}.enforce_mfa",
                pod_name=stats.PodNames.CORE_SERVICES,
                tags=[f"code:{err.code}"],
            )
            abort(err.code, message=err.message)
        except (DuplicateResourceError, ClientError) as err:
            category = get_request_endpoint()
            scope = get_email_or_client_ip()
            clear_rate_limit_redis(category, scope)
            stats.increment(
                metric_name=f"{MFA_METRICS_PREFIX}.enforce_mfa",
                pod_name=stats.PodNames.CORE_SERVICES,
                tags=[f"code:{err.code}"],
            )
            abort(err.code, message=err.message)

        enforcement = MFAEnforcement(
            require_mfa=require_mfa, mfa_enforcement_reason=mfa_enforcement_reason.name
        )

        return asdict(enforcement)


class MFACompanyDataResource(AuthenticatedResource):
    def post(self):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        decoded_token = None

        try:
            bearer_token = request.headers.get("Authorization")
            validator = TokenValidator()
            decoded_token = validator.decode_token(bearer_token)  # type: ignore[arg-type] # Argument 1 to "decode_token" of "TokenValidator" has incompatible type "Optional[str]"; expected "str"
        except TokenExpiredError as err:
            log.warning(f"Token invalid: {err}")
            abort(UNAUTHORIZED_STATUS, message=str(err))
        except TokenValidationError as err:
            log.warning(f"Token invalid: {err}")
            abort(FORBIDDEN_STATUS, message=str(err))

        external_id = decoded_token.get("sub", None)  # type: ignore[union-attr] # Item "None" of "Optional[Dict[Any, Any]]" has no attribute "get"
        user_id = decoded_token.get("user_id", None)  # type: ignore[union-attr] # Item "None" of "Optional[Dict[Any, Any]]" has no attribute "get"

        if not user_id or not external_id:
            log.error("user id or external id is None")
            abort(400, message="Bad request")

        external_id_str: str = str(external_id)
        user_id_str: str = str(user_id)

        mfa_service = mfa.MFAService()
        management_client = idp.ManagementClient()
        # sync company mfa data to maven db and Auth0
        log.info(f"Checking company mfa status for user id {user_id_str}")
        org_id = mfa_service.get_org_id_by_user_id(user_id=int(user_id_str))
        # When org_id existing, the user can have company level mfa requirement. Otherwise, won't check
        try:
            if org_id:
                org_mfa_required = mfa_service.is_mfa_required_for_org(org_id=org_id)
                # Sync data to Auth0 for company mfa information
                management_client.update_company_enforce_mfa(
                    external_id=external_id_str, company_enforce_mfa=org_mfa_required
                )
                log.info(
                    f"Successfully sync company mfa {org_mfa_required} to Auth0 for user {user_id_str}"
                )
                idp_sms_phone_number = management_client.get_user_mfa_sms_phone_number(
                    external_id=external_id_str
                )
                if org_mfa_required:
                    # Sync data to Maven DB only when org mfa is required
                    if user_id_str and idp_sms_phone_number:
                        try:
                            mfa_service.update_mfa_status_and_sms_phone_number(
                                user_id=int(user_id_str),
                                sms_phone_number=idp_sms_phone_number,
                                is_enable=True,
                            )
                            log.info(
                                f"Successfully enable MFA in Maven DB for user {user_id_str} due to company mfa required"
                            )
                        except Exception as e:
                            log.error(
                                f"Failed to update the user's MFA status and sms_phone_number in maven db: {e}"
                            )
                    else:
                        log.warning(
                            f"Failed fetch sms phone number for user {user_id_str}"
                        )
        except (DuplicateResourceError, ClientError) as err:
            category = get_request_endpoint()
            scope = get_email_or_client_ip()
            clear_rate_limit_redis(category, scope)
            stats.increment(
                metric_name=f"{MFA_METRICS_PREFIX}.company_mfa_sync",
                pod_name=stats.PodNames.CORE_SERVICES,
                tags=[f"code:{err.code}"],
            )
            abort(err.code, message=err.message)

        return "", 200
