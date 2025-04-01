from __future__ import annotations

import base64
import contextlib
import functools
import json
import os
from urllib.parse import urlparse

import ddtrace.ext
import flask
import sqlalchemy.orm
from flask import make_response, request
from flask_restful import abort
from google.cloud import storage
from marshmallow import Schema, ValidationError, fields
from maven import feature_flags
from sqlalchemy.ext import baked

from authn.domain import service
from authn.domain.model import IdentityProvider, UserExternalIdentity
from authn.domain.service import IDPAssertion, authn, get_user_service
from authn.domain.service.user import PasswordStrengthCheckerMixIn
from authn.errors.idp.client_error import (
    ClientError,
    DuplicateResourceError,
    IdentityClientError,
    RateLimitError,
    RequestsError,
)
from authn.errors.local.error import PasswordStrengthCheckError
from authn.models import user as legacy_user
from authn.services.integrations import saml
from authn.services.integrations.idp import (
    IDPUser,
    TokenValidationError,
    TokenValidator,
)
from authn.util.constants import (
    CLIENT_ERROR_MESSAGE,
    SERVER_ERROR_MESSAGE,
    SSO_METRICS_PREFIX,
    SSO_USER_DATA_STORAGE,
)
from common import stats
from common.services.api import PermissionedUserResource, UnauthenticatedResource
from common.services.ratelimiting import (
    clear_rate_limit_redis,
    get_email_or_client_ip,
    get_request_endpoint,
)
from configuration import get_idp_config
from storage import connection
from storage.connection import db
from utils.json import SafeJSONEncoder
from utils.launchdarkly import idp_user_context
from utils.log import logger
from utils.passwords import encode_password

log = logger(__name__)


# region: saml sso entrypoint


class SAMLCompleteResource(UnauthenticatedResource):
    _USER_ID_HEADER = "X-User-Id"
    _BEARER_HEADER = "Authorization"
    _UTF8 = "utf-8"

    def __init__(self) -> None:
        self.session = connection.db.session

    def post(self):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        # Despite this being an UnauthenticatedResource,
        # we handle SAML as a special case dependent on JWT validation
        bearer_header = request.headers.get(self._BEARER_HEADER)
        if bearer_header is None:
            abort(403, message="Missing Bearer Token")
        token_dict = None
        try:
            validator = TokenValidator()
            token_dict = validator.decode_token(bearer_header)  # type: ignore[arg-type] # Argument 1 to "decode_token" of "TokenValidator" has incompatible type "Optional[str]"; expected "str"
        except TokenValidationError:
            abort(403, message="Invalid JWT")

        if not token_dict and "sub" not in token_dict:
            abort(400, message="Could not validate claims in JWT")
        saml_user_data = None
        identity = None
        is_new = None
        external_id = None

        try:
            external_id = token_dict["sub"]  # type: ignore[index] # Value of type "Optional[Dict[Any, Any]]" is not indexable
            if not external_id:
                abort(400, message="Invalid request.")
            sso_service = service.SSOService(session=self.session)
            is_new, identity, saml_user_data = sso_service.handle_sso_login(
                external_id=external_id, token_data=token_dict
            )
        except service.SSOLoginError:
            abort(403, message="Failed to authenticate user with the provided identity")

        self.session.commit()
        encoded_external_id = base64.b64encode(external_id.encode(self._UTF8)).decode(  # type: ignore[union-attr] # Item "None" of "Optional[Any]" has no attribute "encode"
            self._UTF8
        )
        log.info(f"The request is for new user: {is_new}")

        if not saml_user_data:
            log.error("missing saml_user_data")
            abort(400, message="Invalid request")

        # The email and first name is from the SAML request. Based on the standard template, they should not be None
        # We set the default value as empty string for safety purpose.
        resp = make_response(
            {
                "is_new": is_new,
                "connection_name": saml_user_data.get("idp_connection_name"),  # type: ignore[union-attr] # Item "None" of "Optional[Any]" has no attribute "get"
                "email": saml_user_data.get("email", ""),  # type: ignore[union-attr] # Item "None" of "Optional[Any]" has no attribute "get"
                "first_name": saml_user_data.get("first_name", ""),  # type: ignore[union-attr] # Item "None" of "Optional[Any]" has no attribute "get"
                "external_id": encoded_external_id,
            }
        )
        if is_new:
            log.info(f"Returning the sso request for new user, is_new is {is_new}")
            return resp

        if not identity:
            log.error("missing identity")
            abort(400, message="Invalid request")

        resp.headers[self._USER_ID_HEADER] = identity.user_id  # type: ignore[union-attr] # Item "None" of "Optional[Any]" has no attribute "user_id"
        log.info(f"Returning the sso request for existing user {identity.user_id}")  # type: ignore[union-attr] # Item "None" of "Optional[Any]" has no attribute "user_id"
        return resp


class SAMLRedirectResource(UnauthenticatedResource):
    def post(self):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        idp_config = get_idp_config()
        # For SSO, we still use the legacy domain.
        # We may plan to move it the custom domain in the future, but it is not high priority work so far.
        # Will track the task here: https://mavenclinic.atlassian.net/browse/CPCS-2867
        domain = "https://" + idp_config.domain

        is_universal_login_sso_on = feature_flags.bool_variation(
            "universal-login-sso-flow",
            feature_flags.Context.create("universal-login-sso-flow"),
            default=False,
        )
        client_id = None
        if is_universal_login_sso_on:
            client_id = idp_config.web_client_id
        else:
            client_id = idp_config.auth_client_id
        redirect_uri = idp_config.base_url + "/app/saml/callback"
        audience = idp_config.audience
        state = {"client_id": client_id}
        state_str: str = json.dumps(state)

        url_to_auth0 = f"{domain}/authorize?response_type=code&client_id={client_id}&redirect_uri={redirect_uri}&scope=openid offline_access&audience={audience}&prompt=none&state={state_str}"

        log.info(f"state attach to url, content is {state_str}")

        return flask.redirect(url_to_auth0, code=302)


class SAMLConsumerResource(UnauthenticatedResource):
    """The core entrypoint for our SAML integrations."""

    def __init__(self) -> None:
        self.session = connection.db.session
        self.service = service.get_sso_service(session=self.session)

    def post(self):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        # Parse the incoming request.
        saml_request = self._parse_request()
        with self._handle_saml_errors(saml_request):
            # Create/Update/Locate our internal identity mapping.
            is_new, identity = self.service.execute_assertion(saml_request)
            # Redirect the user.
            location = self._get_redirect_location(is_new=is_new)
            resp = flask.redirect(location, code=302)
            resp.headers[self.USER_ID_HEADER] = identity.user_id
            # Save any changes.
            self.session.commit()
            return resp

    USER_ID_HEADER = "X-User-Id"

    @staticmethod
    def _parse_request() -> saml.SAMLRequestBody:
        url_data = urlparse(flask.request.url)
        return {
            "https": "on",
            "http_host": flask.request.host,
            "server_port": url_data.port,
            "script_name": flask.request.path.rstrip("/"),
            "get_data": flask.request.args.copy(),
            "post_data": flask.request.form.copy(),
        }

    @contextlib.contextmanager
    def _handle_saml_errors(self, request: saml.SAMLRequestBody):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        try:
            yield
        except saml.SAMLTranslationError as e:
            metric = "sso.assertion_translation_error"
            subject = e.auth_object.get_nameid()  # type: ignore[union-attr] # Item "None" of "Optional[Any]" has no attribute "get_nameid"
            assertion_id = e.auth_object.get_last_assertion_id()  # type: ignore[union-attr] # Item "None" of "Optional[Any]" has no attribute "get_last_assertion_id"
            tags = [
                f"sso.auth.subject:{subject}",
                f"sso.auth.assertion_id:{assertion_id}",
            ]
            for attr in e.auth_object.get_attributes():  # type: ignore[union-attr] # Item "None" of "Optional[Any]" has no attribute "get_attributes"
                tags.append(f"sso.auth.attributes:{attr}")
            self._report_error(
                e,
                *tags,
                message="Failed to parse SAML Assertion.",
                metric=metric,
                status_code=self._get_status_code(e),
                request=request,
                subject=subject,
                assertion_id=assertion_id,
            )
        except saml.SAMLVerificationError as e:
            metric = "sso.assertion_verification_error"
            tags = []
            for idp, err_detail in e.auth_errors.items():
                tags.extend(
                    (
                        f"sso.error.{idp}.message:{err_detail['message']}",
                        f"sso.error.{idp}.reason:{err_detail['reason']}",
                        *(
                            f"sso.error.{idp}.codes:{code}"
                            for code in err_detail["codes"]
                        ),
                    )
                )
            self._report_error(
                e,
                *tags,
                message="Failed SAML Verification.",
                metric=metric,
                status_code=self._get_status_code(e),
                request=request,
                **e.auth_errors,  # type: ignore[arg-type] # Argument 7 to "_report_error" of "SAMLConsumerResource" has incompatible type "**Dict[str, _AuthErrorDetail]"; expected "bool"
            )
        except service.SSOIdentityError as e:
            metric = "sso.identity_error"
            tags = [
                *self._get_assertion_tags(e.assertion),
                f"sso.identity.external_organization_id:{e.identity.external_organization_id}",
                f"sso.identity.identity_provider_id:{e.identity.identity_provider_id}",
                f"sso.identity.unique_corp_id:{e.identity.unique_corp_id}",
                f"sso.identity.external_user_id:{e.identity.external_user_id}",
                f"sso.identity.reporting_id:{e.identity.reporting_id}",
                f"sso.identity.user_id:{e.identity.user_id}",
                f"sso.identity_provider.name:{e.provider.name}",
            ]
            self._report_error(
                e,
                *tags,
                message="The given SAML assertion couldn't be consolidated with the located identity.",
                metric=metric,
                status_code=self._get_status_code(e),
                request=request,
                add_tags_to_error_detail=True,
            )

    @classmethod
    def _get_status_code(cls, err: Exception) -> int:
        if err.__class__ in cls._ERROR_TYPE_TO_STATUS_CODE:
            return cls._ERROR_TYPE_TO_STATUS_CODE[err.__class__]
        return 500

    _ERROR_TYPE_TO_STATUS_CODE: dict[type[Exception], int] = {
        saml.error.SAMLTranslationError: 400,
        saml.error.SAMLVerificationError: 401,
        service.SSOIdentityError: 409,
    }

    @staticmethod
    def _get_assertion_tags(assertion: IDPAssertion) -> tuple[str, ...]:
        return (
            f"sso.assertion.subject:{assertion.subject}",
            f"sso.assertion.employee_id:{assertion.employee_id}",
            f"sso.assertion.rewards_id:{assertion.rewards_id}",
            f"sso.assertion.organization_external_id:{assertion.organization_external_id}",
        )

    def _report_error(  # type: ignore[no-untyped-def] # Function is missing a return type annotation #type: ignore[no-untyped-def] # Function is missing a type annotation for one or more arguments
        self,
        error: BaseException,
        *tags,
        message: str,
        metric: str,
        status_code: int,
        request: saml.SAMLRequestBody,
        add_tags_to_error_detail: bool = False,
        **error_detail,
    ):
        span = ddtrace.tracer.current_root_span()
        self._log_to_saml_bucket(str(span.trace_id), request=request)
        tags_to_send = [*tags]
        if isinstance(error, saml.SAMLIntegrationError):
            tags_to_send.extend(
                (
                    f"sso.is_strict:{error.configuration.strict}",
                    f"sso.is_debug:{error.configuration.debug}",
                    f"sso.issuer:{error.configuration.entity_id}",
                )
            )
        context = {}
        for tag in tags_to_send:
            key, value = tag.split(":", 1)
            context.setdefault(key, []).append(value)
            span.set_tag(key, value)
        context = {k: v[0] if len(v) == 1 else v for k, v in context.items()}
        if add_tags_to_error_detail:
            error_detail.update(context)
        stats.increment(
            metric_name=metric,
            pod_name="core_services",  # type: ignore[arg-type] # Argument "pod_name" to "increment" has incompatible type "str"; expected "PodNames"
            tags=tags_to_send,
        )
        log.error(message, **context)
        error = {  # type: ignore[assignment] # Incompatible types in assignment (expression has type "Dict[str, Collection[str]]", variable has type "BaseException")
            "message": str(error),
            "code": metric,
            "detail": error_detail,
        }
        abort(status_code, message=message, error=error)

    def _log_to_saml_bucket(self, trace_id: str, request: saml.SAMLRequestBody):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        bucket_name = os.environ.get("SAML_BUCKET")
        if bucket_name:
            client = self._gcp_client()
            bucket = client.get_bucket(bucket_name)
            blob = bucket.blob(trace_id)
            blob.upload_from_string(
                json.dumps(request, cls=SafeJSONEncoder, ensure_ascii=False, indent=2)
            )

    @staticmethod
    @functools.lru_cache(maxsize=1)
    def _gcp_client():  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        return storage.Client.from_service_account_json(
            "/google-saml-svc-accounts/saml-file.json"
        )

    @ddtrace.tracer.wrap(span_type=ddtrace.ext.SpanTypes.WEB)
    def _get_redirect_location(self, *, is_new: bool) -> str:
        return self.SET_PASSWORD_PAGE if is_new else self.DASHBOARD_PAGE

    SET_PASSWORD_PAGE = "/app/onboarding/sso"
    DASHBOARD_PAGE = "/dashboard"


# endregion
# region: post sso user setup


bakery = baked.bakery()  # type: ignore[call-arg,func-returns-value] # Missing positional argument "initial_fn" in call to "__call__" of "Bakery" #type: ignore[func-returns-value] # Function does not return a value (it only ever returns None)


class UserSetupSchema(Schema):
    password = fields.Str(required=True)
    email = fields.Email(required=True)


class UserSetupResource(PermissionedUserResource, PasswordStrengthCheckerMixIn):
    """
    This endpoint was created as a separate user update endpoint as we are not
    allowing user email changes in any other endpoints

    For additional context, this endpoint is only used for SAML onboarding on the
    “account set up” page, immediately upon getting redirected after the SAML
    handshake.
    """

    schema = UserSetupSchema()

    def put(self, user_id):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        user = self._user_or_404(user_id)

        try:
            args = self.schema.load(flask.request.json if flask.request.is_json else {})
        except ValidationError as e:
            abort(400, message=e.messages)

        password, new_email = args["password"], args["email"]

        if new_email:
            new_email = new_email.strip()

        try:
            self.check_password_strength(password)
        except PasswordStrengthCheckError as e:
            abort(400, message={"password": e.errors})

        owning_id = _user_id_owning_email(connection.db.session, new_email)
        if owning_id and owning_id != user_id:
            abort(400, message={"email": "Email address is already in use."})

        auth_service = authn.AuthenticationService(is_in_uow=True)
        try:
            idp_user = auth_service.update_password(
                user_id=user.id, email=user.email, password=password
            )
            if not idp_user:
                abort(400, message="There is something wrong happen. Please try again.")

            user.password = encode_password(password)
            if new_email != user.email:
                # Ensure we also update the user in the IDP
                result = auth_service.update_email(
                    user_id=user.id, email=user.email, new_email=new_email
                )
                if not result:
                    abort(400, message="Something went wrong, please try again.")
                user.email = new_email

            connection.db.session.commit()
            return "", 204
        except (RateLimitError, RequestsError) as err:
            stats.increment(
                metric_name=f"{SSO_METRICS_PREFIX}.password_score",
                pod_name=stats.PodNames.CORE_SERVICES,
                tags=[f"code:{err.code}"],
            )
            abort(err.code, message=err.message)
        except (DuplicateResourceError, ClientError) as err:
            category = get_request_endpoint()
            scope = get_email_or_client_ip()
            clear_rate_limit_redis(category, scope)
            stats.increment(
                metric_name=f"{SSO_METRICS_PREFIX}.password_score",
                pod_name=stats.PodNames.CORE_SERVICES,
                tags=[f"code:{err.code}"],
            )
            abort(err.code, message=err.message)


class SSOUserCreationSchema(Schema):
    password = fields.Str(required=True)
    email = fields.Email(required=True)
    external_id = fields.Str(required=True)


class SsoUserCreationResource(UnauthenticatedResource):
    schema = SSOUserCreationSchema()

    def post(self):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        try:
            args: dict = self.schema.load(
                flask.request.json if flask.request.is_json else {}
            )
        except ValidationError as e:
            abort(400, message=e.messages)

        email = args["email"]  # type: ignore[index] # Value of type "Optional[Any]" is not indexable
        password: str = args["password"]
        encoded_external_id: str = args["external_id"]

        local_session = db.session
        user_service = get_user_service(session=local_session)
        sso_service = service.SSOService(users=user_service, session=local_session)

        external_id = sso_service.decode_external_id(encoded_external_id)
        idp_user, provider, connection_name = sso_service.retrieval_idp_user(
            external_id=external_id
        )

        if idp_user.external_user_id is None:
            log.error(
                f"idp user doesn't have external_user_id for external_id {external_id}"
            )
            abort(400, message=CLIENT_ERROR_MESSAGE)

        # create maven user account
        user = self._create_user_account(
            idp_user=idp_user,
            email=email,
            password=password,
            session=local_session,
            user_service=user_service,
        )

        # update saml user account app_metadata on Auth0 to include the user id
        try:
            sso_service.update_external_user_id_link(
                external_id=external_id,
                user_id=user.id,
                connection_name=connection_name,
                idp_user=idp_user,
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

        self._create_user_external_identity(
            user_id=user.id,
            idp_user=idp_user,
            provider=provider,
            sso_service=sso_service,
        )

        # _create_user_account function has checked the user won't be None.
        return make_response({"user_id": user.id})

    def _create_user_external_identity(  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        self,
        user_id: int,
        idp_user: IDPUser,
        provider: IdentityProvider,
        sso_service: service.SSOService,
    ):
        if user_id is None or idp_user.external_user_id is None or provider.id is None:
            log.error(
                f"The table not null fields contain null value. user_id is {user_id}, provider id is {provider.id}"
            )
            abort(500, message=SERVER_ERROR_MESSAGE)
        # query before create
        result = sso_service.identities.get_by_idp_and_external_user_id(
            idp_id=provider.id, external_user_id=idp_user.external_user_id
        )
        enable_user_data_storage = feature_flags.bool_variation(
            SSO_USER_DATA_STORAGE,
            idp_user_context(idp_user),
            default=False,
        )
        if result:
            # this branch should not enter, because new user won't have user external identity record
            log.error(
                f"user external identity is already existed for user {result.user_id}"
            )
            stats.increment(
                metric_name="api.authn.resources.sso.new_user_identity_already_exist",
                pod_name=stats.PodNames.CORE_SERVICES,
            )
            abort(500, message=SERVER_ERROR_MESSAGE)
        else:
            if enable_user_data_storage:
                identity = UserExternalIdentity(
                    user_id=user_id,
                    identity_provider_id=provider.id,  # type: ignore[arg-type] # Argument "identity_provider_id" to "UserExternalIdentity" has incompatible type "Optional[int]"; expected "int"
                    external_user_id=idp_user.external_user_id,
                    external_organization_id=idp_user.organization_external_id,
                    reporting_id=idp_user.rewards_id,
                    unique_corp_id=idp_user.employee_id,
                    sso_email=idp_user.email,
                    auth0_user_id=idp_user.user_id,
                    sso_user_first_name=idp_user.first_name,
                    sso_user_last_name=idp_user.last_name,
                )
            else:
                identity = UserExternalIdentity(
                    user_id=user_id,
                    identity_provider_id=provider.id,  # type: ignore[arg-type] # Argument "identity_provider_id" to "UserExternalIdentity" has incompatible type "Optional[int]"; expected "int"
                    external_user_id=idp_user.external_user_id,
                    external_organization_id=idp_user.organization_external_id,
                    reporting_id=idp_user.rewards_id,
                    unique_corp_id=idp_user.employee_id,
                )
            sso_service.identities.create(instance=identity)
            log.info(f"Successful created user external identity for user {user_id}")

    def _create_user_account(  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        self,
        idp_user: IDPUser,
        email: str,
        password: str,
        session: db.Session,  # type: ignore[name-defined] # Name "db.Session" is not defined
        user_service: service.UserService,
    ):
        if not idp_user:
            log.error("failed to get idp user.")
            abort(500, message=SERVER_ERROR_MESSAGE)

        # create user in maven and auth0
        user = user_service.create_maven_user(
            email=email,
            password=password,
            first_name=idp_user.first_name,
            last_name=idp_user.last_name,
            session=session,
        )
        if not user:
            log.error(
                f"Create user failed in sso onboarding with external_id {idp_user.user_id}"
            )
            abort(500, message=SERVER_ERROR_MESSAGE)
        user_service.post_user_create_steps_v2(user=user, agreements_accepted=True)  # type: ignore[arg-type] # Argument "user" to "post_user_create_steps_v2" of "UserService" has incompatible type "Optional[User]"; expected "User"

        return user


def _user_id_owning_email(
    session: sqlalchemy.orm.scoped_session, email: str
) -> int | None:
    q = bakery(
        lambda sesh: (
            sesh.query(legacy_user.User.id).filter(
                legacy_user.User.email == sqlalchemy.bindparam("email")
            )
        )
    )
    return q(session()).params(email=email).scalar()


# endregion
