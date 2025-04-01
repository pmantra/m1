from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from traceback import format_exc
from typing import TypedDict

from flask import make_response, request
from flask.views import MethodView
from flask_restful import abort
from marshmallow import fields as ma_fields
from marshmallow import fields as v3_fields
from marshmallow_v1 import Schema, ValidationError, fields
from maven.feature_flags import bool_variation
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext import baked
from sqlalchemy.orm import noload
from sqlalchemy.orm.exc import NoResultFound

from appointments.models.schedule import Schedule
from authn.domain import model, service
from authn.domain.model import MFAData
from authn.domain.repository import user_auth
from authn.domain.service import authn, get_user_service
from authn.domain.service import mfa as mfa_service
from authn.domain.service.user import PasswordStrengthCheckerMixIn, UserService
from authn.errors.idp.client_error import (
    ClientError,
    DuplicateResourceError,
    IdentityClientError,
    RateLimitError,
    RequestsError,
)
from authn.errors.local.error import PasswordStrengthCheckError
from authn.models.user import MFAState, User
from authn.services.integrations import mfa, twilio
from authn.util.constants import (
    CLIENT_ERROR_MESSAGE,
    SERVER_ERROR_MESSAGE,
    SSO_USER_DATA_STORAGE,
    USER_METRICS_PREFIX,
)
from care_advocates.models.assignable_advocates import AssignableAdvocate
from common import stats
from common.services import ratelimiting
from common.services.api import (
    AuthenticatedResource,
    InternalServiceResource,
    PermissionedUserResource,
    UnauthenticatedResource,
)
from common.services.ratelimiting import (
    clear_rate_limit_redis,
    get_email_or_client_ip,
    get_request_endpoint,
)
from health.domain.add_profile import add_profile_to_user
from models.actions import ACTIONS, audit
from models.advertising import AutomaticCodeApplication, UserInstallAttribution
from models.enterprise import OnboardingState
from models.gdpr import GDPRRequestSource, GDPRRequestStatus, GDPRUserRequest
from models.profiles import Agreement, AgreementAcceptance
from models.referrals import ReferralCode
from models.tracks import ChangeReason
from storage.connection import db
from tasks.braze import sync_practitioner_with_braze
from tasks.forum import invalidate_posts_cache_for_user
from tasks.users import (
    send_existing_fertility_user_password_reset,
    send_password_changed,
    send_password_reset,
    user_post_creation,
)
from utils import security
from utils.braze import fertility_clinic_user
from utils.data_management import delete_user, gdpr_delete_user
from utils.exceptions import DeleteUserActionableError
from utils.flag_groups import (
    USER_DELETE_RESOURCE_MARSHMALLOW_V3_MIGRATION,
    USER_GET_RESOURCE_MARSHMALLOW_V3_MIGRATION,
    USER_POST_RESOURCE_MARSHMALLOW_V3_MIGRATION,
    USER_PUT_RESOURCE_MARSHMALLOW_V3_MIGRATION,
)
from utils.gdpr_backup_data import GDPRDataRestore
from utils.launchdarkly import idp_user_context
from utils.log import logger
from utils.marshmallow_experiment import marshmallow_experiment_enabled
from utils.member_tracks import terminate_track
from utils.onboarding_state import update_onboarding_state
from utils.passwords import check_password_strength as check_password
from utils.passwords import encode_password
from utils.service_owner_mapper import service_ns_team_mapper
from utils.slack_v2 import notify_gdpr_delete_user_request_channel
from views.schemas.base import PaginableOutputSchemaV3, SchemaV3, UserSchemaV3
from views.schemas.common import (
    BooleanField,
    MavenSchema,
    PaginableOutputSchema,
    UserSchema,
    WithDefaultsSchema,
)

log = logger(__name__)


class SignUpArgs(MavenSchema):
    first_name = fields.String(required=False)
    middle_name = fields.String(required=False)
    last_name = fields.String(required=False)
    email = fields.Email(required=True)
    username = fields.String(required=False)
    password = fields.String(required=True)
    image_id = fields.Integer(required=False)
    external_id = fields.String(required=False)

    plan_invite_id = fields.String(required=False)
    referral_code = fields.String(required=False)

    # the platform where user signs up (used for welcome email)
    source = fields.String(required=False)
    install_campaign = fields.String(required=False)
    install_content = fields.String(required=False)
    install_source = fields.String(required=False)
    install_ad_unit = fields.String(required=False)
    http_page_referrer = fields.String(required=False)

    agreements_accepted = fields.Boolean(required=False)


class DeleteUserRequestSchema(Schema):
    email = fields.Email(required=True)
    requested_date = fields.Date(required=True)
    delete_idp = fields.Boolean(required=False)


class DeleteUserRequestSchemaV3(SchemaV3):
    email = v3_fields.Email(required=True)
    requested_date = v3_fields.Date(required=True)
    delete_idp = v3_fields.Boolean(required=False)


def _attribute_install(user, args):  # type: ignore[no-untyped-def] # Function is missing a type annotation
    campaign = args.get("install_campaign")
    content = args.get("install_content")
    source = args.get("install_source")
    ad_unit = args.get("install_ad_unit")
    http_page_referrer = args.get("http_page_referrer")

    to_attribute = any([campaign, content, source, ad_unit, http_page_referrer])
    if to_attribute:
        install_data = {
            "install_campaign": campaign,
            "install_content": content,
            "media_source": source,
            "install_ad_unit": ad_unit,
            "http_page_referrer": http_page_referrer,
            "registered_on_web": True,
        }

        new = UserInstallAttribution(user=user, json=install_data)
        db.session.add(new)
        db.session.commit()
    else:
        log.debug("No data to attribute for %s", user)


def _apply_code_if_needed(user, args):  # type: ignore[no-untyped-def] # Function is missing a type annotation
    if not args.get("install_campaign"):
        log.debug("Skipping auto code application due to blank install campaign")
        return

    _needed = (
        db.session.query(AutomaticCodeApplication)
        .filter(
            AutomaticCodeApplication.install_campaign == args.get("install_campaign")
        )
        .first()
    )
    if _needed:
        log.debug("Going to claim code: %s", _needed.code)
        _needed.code.use(user)
        log.info("Claimed code on signup: %s", _needed.code)


def _apply_referral_code(user, referral_code):  # type: ignore[no-untyped-def] # Function is missing a type annotation
    try:
        code = (
            db.session.query(ReferralCode)
            .filter(ReferralCode.code == referral_code)
            .one()
        )
    except NoResultFound:
        log.warning("Cannot find a code for: %s", referral_code)
        return
    else:
        log.debug("Using code %s for %s", code, user)
        code.use(user)
        log.debug("All set applying %s...", code)


class UsersResource(UnauthenticatedResource):
    @ratelimiting.ratelimited(attempts=100, cooldown=(60 * 10), reset_on_success=True)
    def post(self):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        request_json = request.json if request.is_json else None
        if not request_json:
            abort(400, message="We only accept JSON data!")
        try:
            return self.signup_flow(request_json)
        except (RateLimitError, RequestsError) as err:
            stats.increment(
                metric_name=f"{USER_METRICS_PREFIX}.signup_user",
                pod_name=stats.PodNames.CORE_SERVICES,
                tags=[f"code:{err.code}"],
            )
            abort(err.code, message=err.message)
        except (DuplicateResourceError, ClientError) as err:
            category = get_request_endpoint()
            scope = get_email_or_client_ip()
            clear_rate_limit_redis(category, scope)
            stats.increment(
                metric_name=f"{USER_METRICS_PREFIX}.signup_user",
                pod_name=stats.PodNames.CORE_SERVICES,
                tags=[f"code:{err.code}"],
            )
            abort(err.code, message=err.message)

    def signup_flow(self, json, is_universal_login=False):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        signup_schema = SignUpArgs()
        args = signup_schema.load(json)
        session = db.session
        user = self._user_if_new(
            args=args.data, session=session, is_universal_login=is_universal_login
        )
        # launch darkly flag
        experiment_enabled = marshmallow_experiment_enabled(
            USER_POST_RESOURCE_MARSHMALLOW_V3_MIGRATION,
            self.user.esp_id if self.user else None,
            self.user.email if self.user else None,
            default=False,
        )
        if user:
            source = args.data.get("source", "ios")
            log.debug("Create user from source.", source=source)

            agreements_acceptance = args.data.get("agreements_accepted", False)

            referral_code = args.data.get("referral_code")
            if referral_code:
                _apply_referral_code(user, referral_code)

            log.debug("Going to apply code if needed")
            _apply_code_if_needed(user, args.data)
            log.info("Finished applying code")

            log.debug("Going to attribute install for user")
            _attribute_install(user, args.data)
            log.debug("Finished attributing install")

            post_user_create_steps(user, agreements_acceptance)
            db.session.commit()

            if experiment_enabled:
                schema = UserSchemaV3(
                    context={
                        "user": user,
                    },
                    exclude=("created_at",),
                )
                return schema.dump(user)
            else:
                schema = UserSchema(exclude=("created_at",))
                schema.context["user"] = user
                return schema.dump(user).data

    def _user_if_new(  # type: ignore[no-untyped-def] # Function is missing a type annotation for one or more arguments
        self, args: dict, session: db.Session, is_universal_login=False  # type: ignore[name-defined] # Name "db.Session" is not defined
    ) -> User | None:
        log.debug("Will create user if it doesnt exist")
        # This will 500 if the role isn't in the DB
        user_info = self._parse_user_create_args(args)

        user_service = get_user_service(session=session)

        return user_service.create_maven_user(
            email=user_info.email,
            password=user_info.password,
            first_name=user_info.first_name,  # type: ignore[arg-type] # Argument "first_name" to "create_maven_user" of "UserService" has incompatible type "Optional[str]"; expected "str"
            last_name=user_info.last_name,  # type: ignore[arg-type] # Argument "last_name" to "create_maven_user" of "UserService" has incompatible type "Optional[str]"; expected "str"
            middle_name=user_info.middle_name,  # type: ignore[arg-type] # Argument "middle_name" to "create_maven_user" of "UserService" has incompatible type "Optional[str]"; expected "str"
            username=user_info.username,  # type: ignore[arg-type] # Argument "username" to "create_maven_user" of "UserService" has incompatible type "Optional[str]"; expected "str"
            image_id=user_info.image_id,  # type: ignore[arg-type] # Argument "image_id" to "create_maven_user" of "UserService" has incompatible type "Optional[str]"; expected "str"
            session=session,
            external_id=user_info.external_id,  # type: ignore[arg-type] # Argument "external_id" to "create_maven_user" of "UserService" has incompatible type "Optional[str]"; expected "str"
            is_universal_login=is_universal_login,
        )

    def _parse_user_create_args(self, args: dict) -> UserCreateArgs:
        return UserCreateArgs(
            email=args["email"].strip(),
            password=args["password"],
            first_name=args["first_name"].strip() if "first_name" in args else None,
            last_name=args["last_name"].strip() if "last_name" in args else None,
            middle_name=args["middle_name"].strip() if "middle_name" in args else None,
            username=args["username"].strip() if "username" in args else None,
            image_id=args.get("image_id"),
            external_id=args["external_id"].strip() if "external_id" in args else None,
        )

    CLIENT_ERROR_MESSAGE = (
        "There was an error creating your account, "
        "please make sure you are using a secure password "
        "and that you don't already have an account registered with the same email address or username."
    )

    SERVER_ERROR_MESSAGE = (
        "There was an error creating your account, please try again. "
        "Contact the support team if the error persists."
    )


bakery = baked.bakery()  # type: ignore[call-arg,func-returns-value] # Missing positional argument "initial_fn" in call to "__call__" of "Bakery" #type: ignore[func-returns-value] # Function does not return a value (it only ever returns None)


@dataclass
class UserCreateArgs:
    email: str
    password: str
    first_name: str | None = None
    middle_name: str | None = None
    last_name: str | None = None
    username: str | None = None
    image_id: str | None = None
    external_id: str | None = None


MAX_RETRY_ATTEMPTS = 2


def post_user_create_steps(user: User, agreements_accepted=False, language=None):  # type: ignore[no-untyped-def] # Function is missing a return type annotation #type: ignore[no-untyped-def] # Function is missing a type annotation for one or more arguments
    db.session.flush()
    audit(ACTIONS.user_added, user.id)
    log.info("Saved new user %s", user)

    schedule = Schedule(name=f"Schedule for {user.full_name}", user=user)
    db.session.add(schedule)

    acceptances = []
    if agreements_accepted:
        acceptances = [
            AgreementAcceptance(user=user, agreement=a)
            for a in Agreement.latest_agreements(user, language=language)
            if a.accept_on_registration
        ]
        db.session.add_all(acceptances)

    update_onboarding_state(user, OnboardingState.USER_CREATED)

    AssignableAdvocate.add_care_coordinator_for_member(user)
    db.session.flush()

    service_ns_tag = "authentication"
    team_ns_tag = service_ns_team_mapper.get(service_ns_tag)
    user_post_creation.delay(user.id, service_ns=service_ns_tag, team_ns=team_ns_tag)

    for acceptance in acceptances:
        acceptance.audit_creation()


def create_idp_user(user: User, plain_password: str = None):  # type: ignore[no-untyped-def,assignment] # Function is missing a return type annotation #type: ignore[assignment] # Incompatible default for argument "plain_password" (default has type "None", argument has type "str")
    """
    Create the user in Auth0
    We want this to occur synchronously so that a subsequent auth attempt will use this new record
    For API user creation, we need to pass the plaintext password to the IDP User Creation call
    For SAML user creation, we don't have a password,
    so setting it to whatever is already hashed in the `user.password` works
    """
    user_password = user.password
    if plain_password:
        user_password = plain_password
    auth_service = authn.get_auth_service(email=user.email)

    try:
        auth_service.create_auth_user(
            email=user.email, password=user_password, user_id=user.id
        )
    except DuplicateResourceError:
        # A user might have been created in IDP in a previously failed attempt.
        # If so, we need to update the IDs stored in IDP and the user_auth table.
        log.info(f"IDP user already exists when creating user {user.id}")
        try:
            auth_service.update_idp_user_and_user_auth_table(
                user.id, user.email, user.password
            )
        except IdentityClientError as err:
            category = get_request_endpoint()
            scope = get_email_or_client_ip()
            clear_rate_limit_redis(category, scope)
            abort(err.code, message="Something went wrong, please try again.")
        except (DuplicateResourceError, ClientError) as err:
            category = get_request_endpoint()
            scope = get_email_or_client_ip()
            clear_rate_limit_redis(category, scope)
            abort(err.code, message=err.message)


def create_user_auth_update_idp_user(user: User, external_id: str):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
    auth_service = authn.get_auth_service(email=user.email)
    log.info(f"create user_auth and update IDP user {user.id} {external_id}")
    auth_service.create_user_auth_update_idp_user(user.id, external_id)


class MFAVerificationNeededSchema(MavenSchema):
    jwt = fields.String(required=True)
    message = fields.String(required=True)
    sms_phone_number_last_four = fields.String(required=True)


class UserApiKeySchema(MavenSchema):
    id = fields.Integer(default=None)  # type: ignore[arg-type] # Argument "default" to "Integer" has incompatible type "None"; expected "int"
    api_key = fields.String(attribute="api_key_with_ttl", default=None)  # type: ignore[arg-type] # Argument "default" to "String" has incompatible type "None"; expected "str"
    api_key_ttl = fields.Integer(default=None)  # type: ignore[arg-type] # Argument "default" to "Integer" has incompatible type "None"; expected "int"
    mfa = fields.Nested(MFAVerificationNeededSchema, default=None)
    identities = fields.List(fields.String())


@UserApiKeySchema.validator
def validate_api_key(schema, data):  # type: ignore[no-untyped-def] # Function is missing a type annotation
    """
    It is recommended to call UserApiKeySchema().validate before returning.
    Marshmallow does not validate during serialization due to performance,
    but since we're checking a few specific fields (i.e. no reflection),
    hopefully the performance hit is relatively small.

    Our contract with API clients is that for a status_code 200 response,
    either the API key and user ID will be set and 'mfa' will be null
    OR the fields inside 'mfa' will be set. We can't guarantee the order
    in which each client checks for null fields, so validate just in case
    to make sure we're not accidentally returning all null or all populated.
    """

    api_fields = ["api_key_ttl", "api_key_with_ttl", "id"]
    has_api_fields = all(data.get(f) is not None for f in api_fields)

    mfa_fields = ["jwt", "message", "sms_phone_number_last_four"]
    has_mfa = bool(data.get("mfa"))
    has_mfa_fields = has_mfa and all(
        data.get("mfa").get(f) is not None for f in mfa_fields
    )

    return (has_api_fields and not has_mfa) or (has_mfa_fields and not has_api_fields)


_WRONG_COMBO = "Looks like the wrong email and password combination. Please try again."
_NOT_ACTIVE = "Your account is no longer active."


class ApiKeyResource(UnauthenticatedResource):
    def __init__(self) -> None:
        self.mfa_service = mfa_service.MFAService()

    def get_post_request(self, request: dict) -> dict[str, str]:
        result = {
            "password": str(request["password"]),
            "email": str(request["email"]),
        }
        # this is here for legacy compat reasons, it is ignored in the view
        if "apple_ifa" in request:
            result["apple_ifa"] = str(request["apple_ifa"])
        return result

    @ratelimiting.ratelimited(
        attempts=6, cooldown=((60 * 60) * 3), reset_on_success=True
    )
    def post(self, user_id=None):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        request_json = request.json if request.is_json else None
        if not request_json:
            abort(400, message="Invalid request body. JSON expected.")

        args = self.get_post_request(request_json)
        user: User = (
            db.session.query(User)
            .filter(User.email == args["email"])
            .options(
                noload("roles"),
            )
            .one_or_none()
        )

        def audit_unauthorized():  # type: ignore[no-untyped-def] # Function is missing a return type annotation
            self.audit(
                "api_key_unauthorized",
                request_ip=request.headers.get("X-Real-IP"),
                request_user_agent=request.headers.get("User-Agent"),
                request_id=request.headers.get("X-Request-ID"),
                user_id=user.id if user else None,
                user_email=user.email if user else args["email"],
            )

        def send_authn_error(error_cause: str):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
            stats.increment(
                metric_name=f"{USER_METRICS_PREFIX}.api_key_resource.unauthenticated",
                pod_name=stats.PodNames.ENROLLMENTS,
                tags=["error:true", f"error_cause:{error_cause}"],
            )

        # NOTE: Returning early when email does not match a user provides a
        #       timing attack. It allows an unauthorized client to test
        #       whether a user exists for a given email.
        #
        #       The effectiveness of this attack is lessened by rate limiting.
        #
        #       A future solution could be to call check password with
        #       constant values, eliminating the timing difference.
        if user is None:
            log.info("No user found matching the given email.")
            audit_unauthorized()
            send_authn_error("no_user_found_matching_email")
            abort(403, message=_WRONG_COMBO)

        auth_service = authn.AuthenticationService()
        if not auth_service.check_password(
            hashed_password=user.password,
            email=args["email"],
            plaintext_password=args["password"],
            user_id=user.id,
            forwarded_for=request.headers.get("X-Real-IP"),  # type: ignore[arg-type] # Argument "forwarded_for" to "check_password" of "AuthenticationService" has incompatible type "Optional[str]"; expected "str"
        ):
            log.info("Password did not match given user email.", user_id=user.id)
            audit_unauthorized()
            send_authn_error("password_not_matching_email")
            abort(403, message=_WRONG_COMBO)

        if not user.is_active():
            log.warning(
                "Inactive user is not allowed to issue an api key.", user_id=user.id
            )
            audit_unauthorized()
            send_authn_error("inactive_user")
            abort(403, message=_NOT_ACTIVE)

        # When the user has opted into Multi-Factor Authentication, we will send them
        # a verification code after they successfully enter their username/password.
        # The client will then supply the returned jwt along with the code from the user
        # to complete the additional verification step and receive the API key.
        #
        # As of 09/26/2023, ApiKeyResource (/api_key) is only used by MPractice iOS app.
        # Since enforcing MFA for practitioners is still under discussion,
        # no MFA enforcement logic is added to the /api_key endpoint
        # as part of https://mavenclinic.atlassian.net/browse/CPCS-1837
        if user.mfa_state.value == MFAState.ENABLED.value:  # type: ignore[attr-defined] # "str" has no attribute "value"
            phone_number = user.sms_phone_number
            if phone_number is None:
                send_authn_error("mfa_enabled_but_missing_phone_number")
                abort(409, message="User has MFA enabled but no phone number added.")

            try:
                twilio.request_otp_via_sms(phone_number)
            except twilio.TwilioRateLimitException:
                send_authn_error("rate_limited")
                return (
                    {
                        "message": "You have reached the rate limit. Please try again in a few minutes."
                    },
                    429,
                )
            except twilio.TwilioApiException:
                send_authn_error("error_sending_verification_code")
                abort(
                    403,
                    message="Error sending verification code via SMS, please try again.",
                )

            encoded_jwt = mfa.encode_jwt(mfa.VerificationRequiredActions.LOGIN, user)
            message = mfa.message_for_sms_code_sent(phone_number)  # type: ignore[arg-type] # Argument 1 to "message_for_sms_code_sent" has incompatible type "Optional[str]"; expected "str"
            last_four = phone_number.rsplit("-", maxsplit=1)[-1]  # type: ignore[union-attr] # Item "None" of "Optional[str]" has no attribute "rsplit"
            # HACK to return a consistent schema from this view / route
            # with null api key fields but a fully populated 'mfa' object
            mfa_data = MFAData(
                jwt=encoded_jwt,
                message=message,
                sms_phone_number_last_four=last_four,
            )

            try:
                # Store a refresh token for this user in their UserAuth record
                # When they verify MFA, we can refresh that token and return an access_token in the MFA verification endpoint
                token = auth_service.create_token(
                    email=args["email"],
                    password=args["password"],
                    forwarded_for=request.headers.get("X-Real-IP"),
                )
            except (RateLimitError, RequestsError) as err:
                abort(err.code, message=err.message)

            auth_repo = user_auth.UserAuthRepository(session=db.session, is_in_uow=True)
            auth_repo.set_refresh_token(
                user_id=user.id, refresh_token=token.get("refresh_token")  # type: ignore[union-attr,arg-type] # Item "None" of "Optional[Dict[Any, Any]]" has no attribute "get" #type: ignore[arg-type] # Argument "refresh_token" to "set_refresh_token" of "UserAuthRepository" has incompatible type "Optional[Any]"; expected "str"
            )
            db.session.commit()
            return self._send_response(user, {"mfa": mfa_data.__dict__})

        db.session.commit()
        audit(ACTIONS.login, user.id)
        log.info("User authenticated; returning new api key.", user_id=user.id)

        return self._send_response(user)

    def _send_response(self, user: User, body: dict = None):  # type: ignore[no-untyped-def,assignment] # Function is missing a return type annotation #type: ignore[assignment] # Incompatible default for argument "body" (default has type "None", argument has type "Dict[Any, Any]")
        schema = UserApiKeySchema()
        body = body or user
        data = schema.dump(body).data
        schema.validate(data)
        resp = make_response(data)
        resp.headers["x-user-id"] = user.id
        resp.headers["x-user-api-key"] = user.api_key_with_ttl
        resp.headers["x-user-identities"] = user.identities
        return resp


class UserGetArgs(WithDefaultsSchema):
    include_profile = BooleanField(default=False)
    include_attachments = BooleanField(default=False)


class UserEditArgs(UserSchema):
    old_password = fields.String(required=False)
    new_password = fields.String(required=False)
    first_name = fields.String(required=False)
    middle_name = fields.String(required=False)
    last_name = fields.String(required=False)
    username = fields.String(required=False)  # type: ignore[assignment] # Incompatible types in assignment (expression has type "String", base class "UserSchema" defined the type as "Method")

    class Meta:
        exclude = ("id", "avatar_url", "role", "name")


class UserResource(PermissionedUserResource, PasswordStrengthCheckerMixIn):
    def get_request(self, request_args: dict) -> dict:
        result = {}
        if not request_args:
            return result
        result["include_profile"] = bool(request_args.get("include_profile", False))
        result["include_attachments"] = bool(
            request_args.get("include_attachments", False)
        )
        return result

    def get(self, user_id: int):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        # launch darkly flag
        experiment_enabled = marshmallow_experiment_enabled(
            USER_GET_RESOURCE_MARSHMALLOW_V3_MIGRATION,
            self.user.esp_id,
            self.user.email,
            default=False,
        )
        query_args_schema = UserGetArgs()
        args = query_args_schema.load(request.args).data

        try:
            python_args = self.get_request(request.args)
            if args == python_args:
                log.info("FM - UserResource GET identical")
            else:
                log.info(
                    "FM - UserResource GET difference",
                    args=str(args),
                    python_args=str(python_args),
                )
        except Exception:
            log.info("FM - UserResource GET error", traces=format_exc())

        user = self._user_or_404(user_id)

        if experiment_enabled:
            schema = UserSchemaV3(
                context={
                    "include_profile": args["include_profile"],
                    "user": self.user,
                    "include_esp_id": True,
                },
                exclude=("created_at",),
            )
            return schema.dump(user)
        else:
            schema = UserSchema(exclude=("created_at",))
            schema.context["user"] = self.user
            schema.context["include_esp_id"] = True
            schema.context["include_profile"] = args["include_profile"]
            return schema.dump(user).data

    def put(self, user_id):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        # launch darkly flag
        experiment_enabled = marshmallow_experiment_enabled(
            USER_PUT_RESOURCE_MARSHMALLOW_V3_MIGRATION,
            self.user.esp_id,
            self.user.email,
            default=False,
        )
        user = self._user_or_404(user_id)

        schema = UserEditArgs(exclude=("created_at",))
        request_json = request.json if request.is_json else None
        args = schema.load(request_json).data
        log.debug("Editing User %s", user)

        auth_service = authn.AuthenticationService()
        email_mfa_ff = bool_variation("auth0-email-mfa", default=False)

        if not email_mfa_ff and args.get("email") and args["email"] != user.email:
            abort(403, message="Changing email is not supported!")

        old_email = user.email
        new_email = args.get("email")
        if args.get("first_name"):
            user.first_name = args["first_name"].strip()
        if args.get("last_name"):
            user.last_name = args["last_name"].strip()
        if args.get("image_id"):
            user.image_id = args.get("image_id")
        if args.get("username") is not None:
            if (
                args.get("username")
                and user.username != args.get("username")
                and User.query.filter(User.username == args["username"]).first()
            ):
                abort(400, message="Username already taken!")
            log.info(f"Setting from username {user.username} to {args.get('username')}")
            if not args.get("username"):
                user.username = None
            else:
                user.username = args.get("username").strip()
        if args.get("old_password") and args.get("new_password"):
            if args["old_password"] == args["new_password"]:
                abort(
                    400,
                    message="New password must be different from the current password",
                )
            try:
                self.check_password_strength(args["new_password"])
            except PasswordStrengthCheckError as e:
                abort(400, message=str(e))
            if auth_service.check_password(
                hashed_password=user.password,
                email=user.email,
                plaintext_password=args["old_password"],
                user_id=user.id,
                forwarded_for=request.headers.get("X-Real-IP"),  # type: ignore[arg-type] # Argument "forwarded_for" to "check_password" of "AuthenticationService" has incompatible type "Optional[str]"; expected "str"
            ):
                idp_user = None
                try:
                    idp_user = auth_service.update_password(
                        user_id=user.id, email=user.email, password=args["new_password"]
                    )
                except (RateLimitError, RequestsError) as err:
                    stats.increment(
                        metric_name=f"{USER_METRICS_PREFIX}.update_user",
                        pod_name=stats.PodNames.CORE_SERVICES,
                        tags=[f"code:{err.code}"],
                    )
                    abort(err.code, message=err.message)
                except (DuplicateResourceError, ClientError) as err:
                    category = get_request_endpoint()
                    scope = get_email_or_client_ip()
                    clear_rate_limit_redis(category, scope)
                    stats.increment(
                        metric_name=f"{USER_METRICS_PREFIX}.update_user",
                        pod_name=stats.PodNames.CORE_SERVICES,
                        tags=[f"code:{err.code}"],
                    )
                    abort(err.code, message=err.message)
                if not idp_user:
                    abort(400, message="Something went wrong, please try again.")

                user.password = encode_password(args["new_password"])
                audit(
                    ACTIONS.password_changed,
                    user.id,
                    ip_addr=request.headers.get("X-Real-IP"),
                )
                user.rotate_api_key()

                service_ns_tag = "authentication"
                team_ns_tag = service_ns_team_mapper.get(service_ns_tag)
                send_password_changed.delay(
                    user.id, service_ns=service_ns_tag, team_ns=team_ns_tag
                )
            else:
                abort(400, message="Bad old_password!")

        if user.middle_name != args.get("middle_name", "").strip():
            user.middle_name = args.get("middle_name", "").strip()
        db.session.add(user)

        if old_email and new_email and old_email != new_email:
            UserService().validate_email(email=new_email)
            try:
                log.info("Updating user email", user_id=str(user.id))
                user.email = new_email
                db.session.commit()
                result = auth_service.update_email(
                    user_id=user.id, email=old_email, new_email=user.email
                )
                if not result:
                    raise IdentityClientError(
                        code=400, message="Auth0 could not update to the email"
                    )
                log.info(
                    "Successfully updated user email",
                    user_id=str(user.id),
                    old_email=old_email[:3],
                    new_email=user.email[:3],
                )
            except Exception as e:
                db.session.rollback()
                log.warning(
                    "Could not update to the email", user_id=str(user.id), error=e
                )
                abort(
                    400,
                    message="Could not update to the email, it might be already registered!",
                )
        else:
            db.session.commit()

        service_ns_tag = "authentication"
        team_ns_tag = service_ns_team_mapper.get(service_ns_tag)

        invalidate_posts_cache_for_user.delay(
            user.id,
            service_ns="community_forum",
            team_ns=service_ns_team_mapper.get("community_forum"),
        )

        if user.is_practitioner:
            sync_practitioner_with_braze.delay(
                user.id, service_ns=service_ns_tag, team_ns=team_ns_tag
            )

        if experiment_enabled:
            schema = UserSchemaV3(  # type: ignore[assignment]
                context={
                    "user": self.user,
                },
                exclude=("created_at",),
            )
            return schema.dump(user)
        else:
            schema = UserSchema(exclude=("created_at",))
            schema.context["user"] = self.user
            return schema.dump(user).data

    def delete(self, user_id):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        """
        Delete a user.
        """
        if request.args.get("flag") == "gdpr" or request.args.get("flag") == "gdpr_v2":
            # launch darkly flag
            experiment_enabled = marshmallow_experiment_enabled(
                USER_DELETE_RESOURCE_MARSHMALLOW_V3_MIGRATION,
                self.user.esp_id if self.user else None,
                self.user.email if self.user else None,
                default=False,
            )
            # This route is the same as the data admin feature that which care advocates have access too
            request_json = request.json if request.is_json else None

            schema = (
                DeleteUserRequestSchemaV3()
                if experiment_enabled
                else DeleteUserRequestSchema()
            )

            args = (
                schema.load(request_json)  # type: ignore
                if experiment_enabled
                else schema.load(request_json).data  # type: ignore
            )

            email = args.get("email")
            delete_idp = bool(args.get("delete_idp", False))

            # this should be an admin user with delete.gdpr_user perms
            current_user = self.user

            try:
                if request.args.get("flag") == "gdpr":
                    delete_user("YES_I_AM_SURE", current_user, user_id, email)
                elif request.args.get("flag") == "gdpr_v2":
                    requested_date = args.get("requested_date")
                    if not requested_date:
                        return {
                            "error": "requested_date missing or value is not provided."
                        }, 400

                    gdpr_delete_user(
                        "YES_I_AM_SURE",
                        current_user,
                        user_id,
                        email,
                        requested_date,
                        delete_idp,
                    )
                db.session.commit()
                return "", 204
            except DeleteUserActionableError as ae:
                db.session.rollback()
                log.error(ae)
                return {"error": ae.args[0]}, 400
            except Exception as e:
                db.session.rollback()
                log.error(e)
                return {"error": e.args[0]}, 500
        else:
            # legacy code remains
            user = self._user_or_404(user_id)
            try:
                week_ago_date = datetime.utcnow() - timedelta(days=7)
                for track in user.active_tracks:
                    terminate_track(
                        member_track_id=track.id,
                        revoke_billing=track.created_at > week_ago_date,
                        user_id=self.user.id,
                        change_reason=ChangeReason.API_USER_DELETE,
                    )
                log.info("%s is de-activating user %s", self.user, user)
                auth_service = authn.AuthenticationService()
                auth_service.user_access_control(user_id=user_id, is_active=False)
                log.info(f"Deactivate user {user_id} in Auth0 complete")
                user.active = False
                db.session.add(user)
                db.session.commit()
                log.info(f"Deactivate user {user_id} in MavenDB complete")
            except Exception as e:
                db.session.rollback()
                log.exception(
                    "Got an exception while terminating member tracks.", exception=e
                )
                abort(
                    400,
                    message="Something went wrong when deactivating your account, please try again.",
                )
            return "", 204


class UsersSchema(PaginableOutputSchema):
    data = fields.Method("get_data")  # type: ignore[assignment] # Incompatible types in assignment (expression has type "Method", base class "PaginableOutputSchema" defined the type as "Raw")

    def get_data(self, obj, context):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        schema = UserSchema(
            context={
                "include_profile": True,
                "user": context.get("user"),
                "include_country_info": context.get("include_country_info"),
            },
            exclude=("created_at",),
        )
        return schema.dump(obj["data"], many=True).data


class UsersSchemaV3(PaginableOutputSchemaV3):
    data = ma_fields.Method("get_data")  # type: ignore[assignment] # Incompatible types in assignment (expression has type "Method", base class "PaginableOutputSchema" defined the type as "Raw")

    def get_data(self, obj):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        schema = UserSchemaV3(
            context={
                "include_profile": True,
                "user": self.context.get("user"),
                "include_country_info": self.context.get("include_country_info"),
            },
            exclude=("created_at",),
        )
        return schema.dump(obj["data"], many=True)


def start_user_deletion(user: User, source: GDPRRequestSource):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
    delete_request = GDPRUserRequest.query.filter_by(user_id=user.id).one_or_none()
    if not delete_request:
        delete_request = GDPRUserRequest(
            user_id=user.id,
            user_email=user.email,
            status=GDPRRequestStatus.PENDING,
            source=source,
        )
        db.session.add(delete_request)
        db.session.commit()
        notification_body = (
            f"The following user made a request to be deleted. "
            f"User ID: {user.id}, First Name: {user.first_name}, "
            f"Last Name: {user.last_name}, Email: {user.email}, "
            f"esp_id: {'Not Available' if user.esp_id is None else user.esp_id}, "
            f"Status: {GDPRRequestStatus.PENDING}, Source: {source}"
        )
        notify_gdpr_delete_user_request_channel(
            notification_title="Start user deletion",
            notification_body=notification_body,
        )
        return True
    else:
        log.warning("A user request already exists!")
        return False


class UserRestore(MethodView):
    def post(self, user_id: int) -> tuple[str, int]:
        user_data_restore = GDPRDataRestore()

        result = user_data_restore.restore_data(user_id)
        if result:
            return "", 204
        else:
            return "Something went wrong", 409


class UserVerificationEmailResource(AuthenticatedResource):
    def post(self):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        auth_service = authn.AuthenticationService()
        try:
            auth_service.send_verification_email(user_id=self.user.id)
            return "OK", 200
        except Exception as e:
            log.exception(
                "Got an exception while sending verification email.",
                exception=e,
                user_id=self.user.id,
            )
            abort(
                400,
                message="Could not send the verification email. Please try again later.",
            )


class GDPRResource(PermissionedUserResource):
    def post(self, user_id: int) -> tuple[str, int]:
        user = self._user_or_404(user_id)
        is_successful = start_user_deletion(user=user, source=GDPRRequestSource.MEMBER)
        if is_successful:
            return "", 204
        else:
            return "Duplicate delete request is made", 409


class PasswordResetRequest(TypedDict):
    """Class to handle PasswordResetResource POST requests."""

    token: str
    password: str


class PasswordResetResource(UnauthenticatedResource, PasswordStrengthCheckerMixIn):
    @ratelimiting.ratelimited(attempts=5, cooldown=(60 * 10))
    def get(self, email: str):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        user = User.query.filter(User.email == email).one_or_none()
        if not user:
            stats.increment(
                metric_name=f"{USER_METRICS_PREFIX}.password_reset_resource",
                pod_name=stats.PodNames.ENROLLMENTS,
                tags=["error:true", "error_cause:unknown_email"],
            )
        else:
            log.info("Sending password reset E-Mail")
            if fertility_clinic_user(user.id):
                service_ns_tag = "clinic_portal"
                team_ns_tag = service_ns_team_mapper.get(service_ns_tag)
                send_existing_fertility_user_password_reset.delay(
                    user.id, service_ns=service_ns_tag, team_ns=team_ns_tag
                )
            else:
                service_ns_tag = "login"
                team_ns_tag = service_ns_team_mapper.get(service_ns_tag)
                send_password_reset.delay(
                    user.id, service_ns=service_ns_tag, team_ns=team_ns_tag
                )
        return "", 204

    @ratelimiting.ratelimited(attempts=5, cooldown=(60 * 10))
    def post(self, email: str):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        to_use = {}
        request_json = request.json if request.is_json else None
        if request_json:
            to_use.update(request_json)
        if request.form:
            to_use.update(request.form)

        if not to_use:
            abort(400, message="Password to be set is not provided.")

        args = PasswordResetRequest(
            token=str(to_use["token"]), password=str(to_use["password"])
        )

        if not security.check_password_reset_token(email, args["token"]):
            log.warning("Invalid password reset token")
            abort(403, message="Bad PW Reset Token!")

        log.debug("Resetting PW for %s", email)
        user = db.session.query(User).filter(User.email == email).one()
        try:
            self.check_password_strength(args["password"])
        except PasswordStrengthCheckError as e:
            abort(400, message=str(e))
        if not user:
            log.warning("User is not exist.")
            abort(400, message="Bad request payload.")

        auth_service = authn.AuthenticationService()
        idp_user = None
        try:
            idp_user = auth_service.update_password(
                user_id=user.id, email=user.email, password=args["password"]
            )
        except (RateLimitError, RequestsError) as err:
            stats.increment(
                metric_name=f"{USER_METRICS_PREFIX}.reset_password",
                pod_name=stats.PodNames.CORE_SERVICES,
                tags=[f"code:{err.code}"],
            )
            abort(err.code, message=err.message)
        except (DuplicateResourceError, ClientError) as err:
            category = get_request_endpoint()
            scope = get_email_or_client_ip()
            clear_rate_limit_redis(category, scope)
            stats.increment(
                metric_name=f"{USER_METRICS_PREFIX}.reset_password",
                pod_name=stats.PodNames.CORE_SERVICES,
                tags=[f"code:{err.code}"],
            )
            abort(err.code, message=err.message)
        if not idp_user:
            abort(400, message="Something went wrong, please try again.")
        user.password = encode_password(args["password"])
        user.rotate_api_key()
        db.session.add(user)
        db.session.commit()
        audit(ACTIONS.password_reset, user.id, ip_addr=request.headers.get("X-Real-IP"))

        service_ns_tag = "login"
        team_ns_tag = service_ns_team_mapper.get(service_ns_tag)
        send_password_changed.delay(
            user.id, service_ns=service_ns_tag, team_ns=team_ns_tag
        )

        log.info("Resetting PW")
        return "", 204


class ConfirmEmailArgs(MavenSchema):
    token = fields.String(required=True)


class ConfirmEmailResource(UnauthenticatedResource):
    def make_get_request(request: dict) -> dict:
        return {"token": str(request["token"])}

    @ratelimiting.ratelimited(attempts=2, cooldown=(60 * 10))
    def get(self, email):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        schema = ConfirmEmailArgs()
        args = schema.load(request.args).data
        try:
            python_args = self.make_get_request(request.args)  # type: ignore[call-arg] # Too many arguments for "make_get_request" of "ConfirmEmailResource"
            if python_args == args:
                log.info("FM - ConfirmEmailResource identical")
            else:
                log.info("FM - ConfirmEmailResource discrepancy")
        except Exception:
            log.info("FM - ConfirmEmailResource exception", exc_info=True)

        token = args["token"]
        if not security.check_confirm_email_token(email, token):
            abort(403, message="Not Authorized!")

        user = db.session.query(User).filter(User.email == email).one()

        if not user.email_confirmed:
            user.email_confirmed = True
            db.session.add(user)
            db.session.commit()
            return "", 204
        else:
            log.info("E-Mail already confirmed for user: %s", user)
            return abort(409, message="Already confirmed!")


class PasswordStrengthScoreResource(
    UnauthenticatedResource, PasswordStrengthCheckerMixIn
):
    def post_request(self, request_json: dict) -> dict:
        if not request_json:
            return {}
        result = {"password": str(request_json["password"])}
        for field in ("first_name", "last_name", "email", "username"):
            if field in request_json:
                result[field] = str(request_json[field])
        return result

    @ratelimiting.ratelimited(attempts=20, cooldown=2)
    def post(self):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        args = self.post_request(request.json if request.is_json else None)
        pw = args.get("password", "")
        if not pw:
            abort(400, message="password cannot be empty.")
        try:
            return check_password(pw)
        except (RateLimitError, RequestsError) as err:
            stats.increment(
                metric_name=f"{USER_METRICS_PREFIX}.password_score",
                pod_name=stats.PodNames.CORE_SERVICES,
                tags=[f"code:{err.code}"],
            )
            abort(err.code, message=err.message)
        except (DuplicateResourceError, ClientError) as err:
            category = get_request_endpoint()
            scope = get_email_or_client_ip()
            clear_rate_limit_redis(category, scope)
            stats.increment(
                metric_name=f"{USER_METRICS_PREFIX}.password_score",
                pod_name=stats.PodNames.CORE_SERVICES,
                tags=[f"code:{err.code}"],
            )
            abort(err.code, message=err.message)


class SsoUserRelinkResource(AuthenticatedResource):
    @ratelimiting.ratelimited(attempts=100, cooldown=(60 * 10), reset_on_success=True)
    def post(self):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        payload = request.json if request.is_json else None
        if not payload:
            log.error("Sso relink request missing payload.")
            abort(400, message="Bad request payload.")
        try:
            args = post_request(payload)
        except KeyError as e:
            return {"message": str(e)}, 400

        user_id = args["user_id"]
        encoded_external_id = args["external_id"]

        if not user_id or not encoded_external_id:
            log.error("Request payload is invalid.")
            abort(400, message="Bad request payload.")
        sso_service = service.SSOService()

        external_id = sso_service.decode_external_id(encoded_external_id)

        idp_user, provider, connection_name = sso_service.retrieval_idp_user(
            external_id=external_id
        )
        log.info(f"SSO User is going to relink to user {user_id}")
        if not idp_user.external_user_id:
            log.info(f"external_user_id is null for user {external_id}")
            abort(400, message=CLIENT_ERROR_MESSAGE)

        # Check whether the user is existing in the table
        identity = sso_service.fetch_identity_by_idp_and_external_user_id(
            idp_id=provider.id, external_user_id=idp_user.external_user_id
        )
        if identity:
            # This branch should not enter. Because the relink logic only applies to the new sso user.
            # If enter this branch, it means the user already has the record in the user external identity table, which
            # means the user is not a new user.
            # Currently, the FE is working on a fix. https://mavenclinic.atlassian.net/browse/EPEN-2941
            log.warning(
                f"Going to create identity for user {user_id} in {connection_name} while the identity existed in table"
            )
            stats.increment(
                metric_name="api.authn.resources.user.sso_relink_insert_dup_key",
                pod_name=stats.PodNames.CORE_SERVICES,
            )
        else:
            # Create record in user external identity table
            enable_user_data_storage = bool_variation(
                SSO_USER_DATA_STORAGE,
                idp_user_context(idp_user),
                default=False,
            )
            if enable_user_data_storage:
                identity = model.UserExternalIdentity(
                    user_id=user_id,
                    identity_provider_id=provider.id,
                    external_user_id=idp_user.external_user_id,
                    external_organization_id=idp_user.organization_external_id,
                    reporting_id=idp_user.rewards_id,
                    unique_corp_id=idp_user.employee_id,
                    sso_email=idp_user.email,
                    sso_user_first_name=idp_user.first_name,
                    sso_user_last_name=idp_user.last_name,
                    auth0_user_id=idp_user.user_id,
                )
            else:
                identity = model.UserExternalIdentity(
                    user_id=user_id,
                    identity_provider_id=provider.id,
                    external_user_id=idp_user.external_user_id,
                    external_organization_id=idp_user.organization_external_id,
                    reporting_id=idp_user.rewards_id,
                    unique_corp_id=idp_user.employee_id,
                )
            created = sso_service.identities.create(instance=identity)
            if not created:
                log.error(f"Failed create user_external_identity for user {user_id}")
                raise Exception
            log.info(f"Success created user_external_identity for user {user_id}")

        return "", 200


def post_request(request_json: dict) -> dict:
    if not request_json:
        return {}
    return {
        "user_id": str(request_json["user_id"]),
        "external_id": str(request_json["external_id"]),
    }


class PostUserCreationResource(InternalServiceResource):
    """
    This class is used to trigger the post maven user creation work
    """

    @ratelimiting.ratelimited(attempts=100, cooldown=(60 * 10), reset_on_success=True)
    def post(self):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        payload = request.json if request.is_json else None

        if not payload:
            log.error("post user request missing payload.")
            abort(400, message="Bad request payload.")
        try:
            signup_schema = SignUpArgs()
            args = signup_schema.load(payload)
        except KeyError as e:
            return {"message": str(e)}, 400
        user_id = args["user_id"]
        session = db.session
        user_service = get_user_service(session=session)
        # Phase 1: When the user is created in the authn-api database, the mono sync_user_data internal
        # endpoint will be called to create the user in mono. Then we fetch the user from the mono.
        # Phase 2: When the dependency component fetches the user id information from the authn-api,
        # the mono will call authn-api service to fetch the user information.
        try_times = 3
        while try_times > 0:
            user = User.query.filter(User.id == user_id).one()
            if user:
                # user is synced from the authn-api to the mono db
                break
            else:
                try_times -= 1
        if try_times == 0:
            log.error(
                "User data is not synced from the authn-api to the mono db via CDC."
            )
            abort(500, message=SERVER_ERROR_MESSAGE)

        try:
            add_profile_to_user(user, **vars(user))
            # NOTE session is not passed into add_profile_to_user
            db.session.commit()
            log.info("Added profile to user", user_id=user_id)
            user = user_service.sync_practitioner_info(user)
            db.session.commit()
            log.info("Synced practitioner info to user", user_id=user_id)
        except IntegrityError:
            abort(409, message=CLIENT_ERROR_MESSAGE)

        # Assign a benefit ID to the user
        try:
            from wallet.repository.member_benefit import MemberBenefitRepository
            from wallet.services.member_benefit import MemberBenefitService

            repo = MemberBenefitRepository(session=session)
            member_benefit_service = MemberBenefitService(member_benefit_repo=repo)
            member_benefit_service.add_for_user(user_id=user.id)
        except Exception as e:
            session.rollback()
            log.exception(
                "Failed to generate benefit ID:", user_id=str(user.id), error=e
            )
        else:
            session.commit()
            log.info("Successfully generated benefit ID", user_id=str(user.id))
        # end create_maven_user function

        # process the signup args
        agreements_acceptance = True

        # It could always None and the enrollment job maybe is related to this
        referral_code = args.data.get("referral_code")
        if referral_code:
            _apply_referral_code(user, referral_code)
        # This could also be never execute
        log.debug("Going to apply code if needed")
        _apply_code_if_needed(user, args.data)
        log.info("Finished applying code")
        # This could never execute
        log.debug("Going to attribute install for user")
        _attribute_install(user, args.data)
        log.debug("Finished attributing install")

        user_service.post_user_create_steps_v2(user, agreements_acceptance)
        db.session.commit()

        experiment_enabled = marshmallow_experiment_enabled(
            USER_POST_RESOURCE_MARSHMALLOW_V3_MIGRATION,
            self.user.esp_id if self.user else None,
            self.user.email if self.user else None,
            default=False,
        )

        if experiment_enabled:
            schema = UserSchemaV3(
                context={
                    "user": user,
                },
                exclude=("created_at",),
            )
            return schema.dump(user)
        else:
            schema = UserSchema(exclude=("created_at",))
            schema.context["user"] = user
            return schema.dump(user).data


class GetIdentitiesResource(InternalServiceResource):
    @ratelimiting.ratelimited(attempts=100, cooldown=(60 * 10), reset_on_success=True)
    def get(self, user_id: int):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        session = db.session
        user = session.query(User).filter(User.id == user_id).one_or_none()
        if not user:
            log.warn(f"user {user_id} is not existed.")
            abort(401, message="unauthorized")

        user_service = get_user_service(session=session)

        identities = user_service.get_identities(user_id=user_id)

        return make_response({"identities": identities}, 200)


class GetOrgIdResource(InternalServiceResource):
    @ratelimiting.ratelimited(attempts=100, cooldown=(60 * 10), reset_on_success=True)
    def get(self, user_id: int):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        user = db.session.query(User).filter(User.id == user_id).one_or_none()
        if not user:
            log.warn(f"user {user_id} is not existed.")
            abort(401, message="unauthorized")

        mfa_svc = mfa_service.MFAService()
        org_id = mfa_svc.get_org_id_by_user_id(user_id=user_id)

        return make_response({"org_id": org_id}, 200)


class SyncUserDataRequestSchema(MavenSchema):
    id = fields.Integer(required=True)
    esp_id = fields.String(required=True)
    email = fields.Email(required=True)
    username = fields.String(required=False)
    first_name = fields.String(required=False)
    middle_name = fields.String(required=False)
    last_name = fields.String(required=False)
    active = fields.Boolean(required=True)
    email_confirmed = fields.Boolean(required=True)
    mfa_state = fields.String(required=True)
    sms_phone_number = fields.String(required=False)
    zendesk_user_id = fields.Integer(required=False)
    password = fields.String(required=True)


class SyncUserDataResource(InternalServiceResource):
    def _send_metrics(self, status: str) -> None:
        stats.increment(
            metric_name=f"{USER_METRICS_PREFIX}.{self.__class__.__name__}",
            pod_name=stats.PodNames.CORE_SERVICES,
            tags=[f"status:{status}"],
        )

    @ratelimiting.ratelimited(attempts=100, cooldown=(60 * 10), reset_on_success=True)
    def post(self):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        data = None
        try:
            signup_schema = SyncUserDataRequestSchema()
            args = signup_schema.load(request.json if request.is_json else {})
            if not args:
                log.error("args is None")
                self._send_metrics("failure")
                abort(400, message="Bad request payload.")
            data = args.data
        except ValidationError:
            self._send_metrics("failure")
            abort(400, message="Bad request payload.")
        if not data:
            log.error("data is None")
            self._send_metrics("failure")
            abort(400, message="Bad request payload.")
        else:
            session = db.session
            user = User(
                id=data.get("id"),
                esp_id=data.get("esp_id"),
                email=data.get("email"),
                username=data.get("username", None),
                first_name=data.get("first_name", None),
                middle_name=data.get("middle_name", None),
                last_name=data.get("last_name", None),
                active=data.get("active"),
                email_confirmed=data.get("email_confirmed"),
                mfa_state=data.get("mfa_state"),
                sms_phone_number=data.get("sms_phone_number", None),
                zendesk_user_id=data.get("zendesk_user_id", None),
                password=data.get("password"),
            )
            session.add(user)
            session.commit()
            self._send_metrics("success")

            return "", 200
