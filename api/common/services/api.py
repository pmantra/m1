from __future__ import absolute_import, annotations

import hashlib
import itertools
import math
import re
import time
from functools import wraps
from importlib import import_module
from typing import Callable

import ddtrace
from flask import current_app, g, request
from flask_principal import Identity, PermissionDenied, identity_changed
from flask_restful import Api, Resource, abort
from httpproblem import Problem, problem
from marshmallow_v1 import ValidationError
from marshmallow_v1.exceptions import UnmarshallingError
from sqlalchemy.exc import TimeoutError as SATimeoutError
from sqlalchemy.orm.exc import NoResultFound

from authn.models.user import User
from authn.services.integrations.idp.token_validator import TokenValidator
from authz.services.block_list import BlockList, BlockListDenied
from common import stats
from common.services import ratelimiting
from members.utils.member_access import get_member_access_by_practitioner
from models.actions import audit
from models.profiles import MemberProfile
from providers.repository.provider import ProviderRepository
from storage.connection import db
from utils import security
from utils.log import logger
from utils.service_owner_mapper import USER_ID_TAG

log = logger(__name__)

IMPORTED_MODULES = (
    "authn.routes.api",
    "appointments.routes",
    "clinical_documentation.routes",
    "providers.routes",
    "bms.routes",
    "direct_payment.routes",
    "payments.routes",
    "wallet.routes",
    "messaging.routes",
    "braze.routes",
    "care_advocates.routes",
    "incentives.routes",
    "members.routes",
    "provider_matching.routes",
    "geography.routes",
    "preferences.routes",
    "learn.routes",
    "mpractice.routes",
    "personalization.routes",
)

VIEW_AS_API_ALLOW_LIST = (
    "/api/v1/users/me",
    "/api/v1/users/profiles/member",
    "/api/v1/reimbursement_wallet/dashboard",
    "/api/v1/reimbursement_wallet",
    "/api/v1/reimbursement_wallet/state",
    "/api/v1/reimbursement_wallet/[id]/users",
    "/api/v1/reimbursement_wallets/[id]/bank_account",
    "/api/v1/reimbursement_request",
    "/api/v1/reimbursement_request/state",
    "/api/v1/direct_payment/clinic/me",
    "/api/v1/direct_payment/clinic/fertility_clinic_users/[clinic_user_id]",
    "/api/v1/direct_payment/clinic/fertility_clinics/[clinic_id]",
    "/api/v1/direct_payment/clinic/fertility_clinics/[clinic_id]/procedures",
    "/api/v1/direct_payment/clinic/treatment_procedures",
    "/api/v1/direct_payment/treatment_procedure/[treatment_procedure_id]",
    "/api/v1/direct_payment/treatment_procedure/member/[member_id]",
    "/api/v1/direct_payment/payments/reimbursement_wallet/[wallet_id]",
    "/api/v1/direct_payment/payments/reimbursement_wallet/estimates/[wallet_id]",
    "/api/v1/direct_payment/payments/bill/[bill_uuid]/detail",
)

# Convert the VIEW_AS_API_ALLOW_LIST into regular expressions
view_as_pattern_list = [
    re.compile(re.sub(r"\[(.*?)\]", r"[^/]+", path)) for path in VIEW_AS_API_ALLOW_LIST
]


def is_path_allowed_view_as(path: str) -> bool:
    for pattern in view_as_pattern_list:
        if pattern.fullmatch(path):
            return True
    return False


# ---- Auth wrapper for AuthenticatedResource -----


def _get_user_from_token():  # type: ignore[no-untyped-def] # Function is missing a return type annotation
    bearer_header = request.headers.get("Authorization")
    if not bearer_header:
        return
    validator = TokenValidator()
    try:
        token_dict = validator.decode_token(bearer_header)
        user_id = token_dict["user_id"]
        return db.session.query(User).filter(User.id == user_id).one()
    except Exception:
        return


def _get_user(*, loader: Callable[[int], User] = None):  # type: ignore[no-untyped-def,assignment] # Function is missing a return type annotation #type: ignore[assignment] # Incompatible default for argument "loader" (default has type "None", argument has type "Callable[[int], User]")
    """Legacy authentication via the X-Maven-User-ID header"""
    user_id = request.headers.get(_USER_ID_HEADER)
    view_as = request.headers.get(_VIEW_AS_HEADER)

    if user_id:
        try:
            if loader:  # type: ignore[truthy-function] # Function "loader" could always be true in boolean context
                return loader(user_id)  # type: ignore[arg-type] # Argument 1 has incompatible type "str"; expected "int"
            if view_as:
                view_as_log = f"_get_user view as query: user_id {user_id} view_as {view_as} on {request.path}"
                if request.method == "GET" and is_path_allowed_view_as(request.path):
                    log.warning(f"Accepted, {view_as_log}")
                    user_id = int(view_as)
                else:
                    log.warning(f"Rejected, {view_as_log}")
            return db.session.query(User).filter(User.id == user_id).one()
        except NoResultFound:
            log.debug("No user for ID: %s", user_id)
    else:
        log.debug("No X-Maven-User-ID in request header.")


_USER_ID_HEADER = "X-Maven-User-ID"
_VIEW_AS_HEADER = "X-Maven-View-As"
_BEARER_HEADER = "Authorization"
_BLOCKED_PHONES_KEY = "user_blocked_phone_numbers"
_BLOCKED_LIST_SKIP_CHECK_WHEN_UNAVAILABLE = True
_REDIS_CLIENT_TIME_OUT = 2.0


def _get_phone_numbers(user):  # type: ignore[no-untyped-def] # Function is missing a type annotation
    """Return the users phone numbers from both the User or Member Profile"""
    numbers = [user.sms_phone_number]

    if user.member_profile:
        numbers.append(user.member_profile.phone_number)

    return ["".join(filter(str.isdigit, number)) for number in numbers if number]


def authenticate(func):  # type: ignore[no-untyped-def] # Function is missing a type annotation
    @wraps(func)
    def wrapper(*args, **kwargs):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        user_id = str(request.headers.get(_USER_ID_HEADER))
        user = None
        if (
            hasattr(func, "__self__")
            and hasattr(func.__self__, "user")
            and func.__self__.user
        ):
            if str(func.__self__.user.id) == user_id:
                user = func.__self__.user or _get_user_from_token()
            else:
                log.error(
                    f"[authenticate] mismatched user id, request_user_id {user_id}, stored {func.__self__.user.id}"
                )

        if user is None:
            user = _get_user() or _get_user_from_token()
            # further reduce the amount of queries and assign the user record here
            if hasattr(func, "__self__") and issubclass(
                type(func.__self__), HasUserResource
            ):
                func.__self__.set_user(user)
                # temp metric logic to gauge how often it happens
                resource_name = (
                    str(type(func.__self__)) if hasattr(func, "__self__") else "none"
                )
                func_name = func.__name__
                stats.increment(
                    metric_name="mono.assign_user_to_resource",
                    pod_name=stats.PodNames.CORE_SERVICES,
                    tags=[f"resource:{resource_name}", f"func:{func_name}"],
                )

        if user and user.is_active():
            prev_user_id = None
            current_user_id = user.id
            if hasattr(g, "request_stat_doc"):
                prev_user_id = g.request_stat_doc.get("user_id", None)
            if prev_user_id and prev_user_id == current_user_id:
                # temp log logic
                log.info("[authenticate] user is previously authenticated")
                # we take the short-cut here to avoid further expensive actions
                # temp metric logic to gauge how often it happens
                resource_name = (
                    str(type(func.__self__)) if hasattr(func, "__self__") else "none"
                )
                func_name = func.__name__
                stats.increment(
                    metric_name="mono.api_auth_skip",
                    pod_name=stats.PodNames.CORE_SERVICES,
                    tags=[f"resource:{resource_name}", f"func:{func_name}"],
                )

                identity_changed.send(
                    current_app._get_current_object(),
                    identity=Identity(current_user_id),
                )
                return func(*args, **kwargs)

            # The BlockList tracks phone_numbers, which tells us when a blocked phone number has been reused
            # If one of those re-used numbers is in our BlockList, we will abort and disable the User
            user_phone_numbers = _get_phone_numbers(user)
            BlockList(
                skip_if_unavailable=_BLOCKED_LIST_SKIP_CHECK_WHEN_UNAVAILABLE,
                timeout=_REDIS_CLIENT_TIME_OUT,
            ).validate_access(
                user_id=current_user_id,
                attribute="phone_number",
                check_values=user_phone_numbers,
            )

            root_span = ddtrace.tracer.current_root_span()
            if root_span:
                root_span.set_tags({USER_ID_TAG: current_user_id})
            cur_span = ddtrace.tracer.current_span()
            if cur_span and cur_span != root_span:
                cur_span.set_tags({USER_ID_TAG: current_user_id})
            g.current_user = user
            # start clean for the current request
            g.pop("user_role_identities", None)
            doc = {"user_id": current_user_id}
            g.request_stat_doc.update(doc)
            identity_changed.send(
                current_app._get_current_object(), identity=Identity(current_user_id)
            )
            return func(*args, **kwargs)
        else:
            log.debug("Bad or missing API KEY / JWT for auth.")
            abort(401, message="Unauthorized")

    return wrapper


# ---- Shared parts of Maven Base Views -----


class HasCacheKey:
    @property
    def cache_key(self):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        if not hasattr(self, "_cache_key"):
            path = request.path
            sorted_args = frozenset(sorted(request.args.items(), key=lambda x: x[1]))
            args = hashlib.md5(str(sorted_args).encode("utf8")).hexdigest()
            self._cache_key = path + args
        return self._cache_key


class HasUserResource(Resource):
    def audit(self, action_type, **body):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        if body.get("user_id"):
            user_id = body["user_id"]
        elif hasattr(self, "_user"):
            user_id = self.user.id
        else:
            user_id = None

        if "user_id" in body:
            del body["user_id"]

        try:
            audit(action_type, user_id, **body)
        except Exception as e:
            log.error("Exception: %s", e)
            log.warning("Could not audit: %s (%s), %s", action_type, user_id, body)

    def init_timer(self, timestamp=None):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        if hasattr(self, "_timer_start"):
            log.warning("ALREADY init'ed - overwriting!")
        self._timer_start = time.time()

    def timer(self, name, timestamp=None):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        if not hasattr(self, "_timer_start"):
            log.warning("Using an un-init'ed timer - init'ing now...")
            self.init_timer()

        timestamp = None or time.time()
        from_start = timestamp - self._timer_start

        log.info(
            "api_view_timer",
            **dict(
                timer_name=name,
                timestamp=timestamp,
                from_start=from_start,
                method=request.method,
                view_name=request.url_rule.endpoint.replace(".", "_"),  # type: ignore[union-attr] # Item "None" of "Optional[Rule]" has no attribute "endpoint"
                request_id=request.headers.get("X-Request-ID"),
            ),
        )

    @property
    def user(self):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        if not hasattr(self, "_user"):
            # Flask global var g may persist through unit test requests
            # to avoid failing tests call _get_user() on each request
            self._user = _get_user() or _get_user_from_token()
        return self._user

    def set_user(self, val):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        if not hasattr(self, "_user"):
            self._user = val
        elif self._user is None:
            self._user = val


# ---- Maven Base Classes for Views -----


class UnauthenticatedResource(HasUserResource, HasCacheKey):
    method_decorators = []


class AuthenticatedResource(HasUserResource, HasCacheKey):
    method_decorators = [authenticate]


class InternalServiceResource(UnauthenticatedResource):
    # Base class for Interal Apps calling Mono for use-cases that are not
    # member specific -- e.g. CarePlanService Cronjob fetching articles viewed for many users
    # Legacy implementation: Concrete class calls self._check_permissions() and
    # Caller must set "maven_service" identity to allow access
    # For external requests, the X-Maven-User-Identities gets replaced
    # with the logged-in user's identities, so an external user can never set this value
    def _check_permissions(self) -> None:
        identities = request.headers["X-Maven-User-Identities"]
        if "maven_service" not in identities:
            raise Problem(404)


class EnterpriseOrProviderResource(AuthenticatedResource):
    def _user_is_enterprise_or_provider_else_403(self) -> None:
        if not (self.user.is_enterprise or self.user.is_practitioner):
            raise Problem(403, detail="You do not have access to this resource")


class EnterpriseResource(AuthenticatedResource):
    def _user_is_enterprise_else_403(self):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        if not self.user.is_enterprise:
            raise Problem(403, detail="You do not have access to this resource")


class PermissionedUserResource(AuthenticatedResource):
    def _user_or_404(self, user_id):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        """
        Validate the user in the authentication context has the provided ID

        :param user_id: the id of the User object.
        :return: User object
        """
        if self.user is None:
            self._throw_invalid_user_id_error(user_id)

        if self.user.id != user_id:  # type: ignore[union-attr] # Item "None" of "Optional[Any]" has no attribute "id"
            log.debug(
                "Trying to edit private user data and unauthorized -- %s", user_id
            )
            self._throw_invalid_user_id_error(user_id)

        return self.user

    def _throw_invalid_user_id_error(self, user_id):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        abort(404, message=f"User {user_id} invalid.")


class PermissionedCareTeamResource(AuthenticatedResource):
    def target_user(self, target_user_id) -> User:  # type: ignore[no-untyped-def] # Function is missing a type annotation for one or more arguments
        if self.user is None:
            raise Problem(404, detail="Invalid Accessing User")
        if self.user.id == target_user_id:
            target_user = self.user
        else:
            target_user = (
                db.session.query(User).filter(User.id == target_user_id).first()
            )
        if not target_user:
            raise Problem(404, detail="Invalid Target User")
        self._user_has_access_to_user_or_403(self.user, target_user)
        return target_user

    def _user_has_access_to_user_or_403(self, accessing_user, target_user):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        """
        Check that the accessing user has permission to see the target user's data.

        :param accessing_user: the User accessing the view
        :param target_user: the User whose data is being supplied
        :return: User object, the user whose data is being supplied
        """
        if (
            accessing_user == target_user
            or accessing_user.is_care_coordinator
            or accessing_user.id
            in [prac_profile.user_id for prac_profile in target_user.care_team]
            or (
                accessing_user.is_practitioner
                and target_user.id
                in [
                    u.user_id
                    for u in get_member_access_by_practitioner(accessing_user.id).all()
                ]
            )
        ):
            return target_user
        else:
            self._throw_invalid_user_access_error()

    def _throw_invalid_user_access_error(self):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        raise Problem(
            403, detail="You do not have access to that target user's information."
        )

    def _user_id_has_access_to_member_id_or_403(  # type: ignore[return] # Missing return statement
        self, user_id: int, member_id: int
    ) -> bool:
        """
        Check that the accessing provider has permission to see the target member's data.

        :param user_id: the user_id of the user accessing the view
        :param member_id: the user_id of the member whose data is being supplied
        :return: bool, whether or not the provider can access the target member
        """
        provider = ProviderRepository().get_by_user_id(user_id=user_id)
        member = MemberProfile.query.filter(
            MemberProfile.user_id == member_id
        ).one_or_none()
        if (
            user_id == member_id
            or (provider is not None and provider.is_cx)
            or (
                member is not None
                and user_id in [prac.practitioner_id for prac in member.care_team]
            )
            or (
                provider is not None
                and member_id
                in [u.user_id for u in get_member_access_by_practitioner(user_id).all()]
            )
        ):
            return True
        else:
            self._throw_invalid_user_access_error()


class AuthenticatedViaTokenResource(HasUserResource, HasCacheKey):
    method_decorators = []

    @property
    def user_from_auth_or_token(self):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        if self.user:
            return self.user
        elif request.args.get("encoded_user_id"):
            decoded_id = security.check_user_id_encoded_token(
                request.args.get("encoded_user_id")
            )
            if not decoded_id:
                log.info("Bad encoded_user_id!")
                abort(400, message="Bad User Token for ID!")
            return User.query.get_or_404(decoded_id)


class ExceptionAwareApi(Api):
    def unauthorized(self, response):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        """Given a response, change it to ask for credentials"""

        realm = current_app.config.get("HTTP_BASIC_AUTH_REALM", "Maven")
        challenge = f'Maven realm="{realm}"'

        response.headers["WWW-Authenticate"] = challenge
        return response

    def handle_error(self, e):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        code = 500

        if isinstance(e, BlockListDenied):
            code = 401
            data = {
                "status_code": code,
                "message": "Unauthorized",
            }
        elif isinstance(e, PermissionDenied):
            code = 403
            data = {
                "status_code": code,
                "message": "Not authorized to perform that action!",
            }
        elif isinstance(e, (UnmarshallingError, ValidationError)):
            code = 400
            data = {"error": str(e), "status_code": code}
        elif isinstance(e, ratelimiting.RateLimitingError):
            code = 429
            data = {
                "message": (
                    "You have exceeded the maximum number of requests within the allowed timeframe. "
                    "Please try again later."
                ),
                "status_code": code,
            }
        elif isinstance(e, (TimeoutError, SATimeoutError)):
            code = 503
            data = {
                "message": f"Timed out on operation: {e}. Please try again later.",
                "status_code": code,
            }
        elif isinstance(e, Problem):
            problem = e.to_dict()
            return self.make_response({"errors": [problem]}, e.status)
        else:
            # Did not match a custom exception, continue normally
            e.data = self.update_data_with_http_problem(e.code, e.data, e)
            return super().handle_error(e)

        data = self.update_data_with_http_problem(code, data, e)
        return self.make_response(data, code)

    def update_data_with_http_problem(self, code, data, exception):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        try:
            if "errors" not in data and (data.get("message") or data.get("error")):
                content = data.get("message") or data.get("error")
                if isinstance(content, str):
                    data["errors"] = [problem(status=code, detail=content)]
                elif isinstance(content, object):
                    data["errors"] = [
                        problem(
                            status=code,
                            detail=(
                                ",".join(content[key])  # type: ignore[index] # Value of type "object" is not indexable
                                if isinstance(content[key], list)  # type: ignore[index] # Value of type "object" is not indexable
                                else content[key]  # type: ignore[index] # Value of type "object" is not indexable
                            ),
                            field=key,
                        )
                        for key in content.keys()  # type: ignore[attr-defined] # "object" has no attribute "keys"
                    ]
            else:
                raise ValueError("Unexpected Exception Structure")
        except ValueError:
            log.info(
                "Unexpected Exception Structure",
                exception=exception,
                trace=exception.__traceback__,
            )
        return data


def create_api(app):  # type: ignore[no-untyped-def] # Function is missing a type annotation
    # avoid circular imports with delayed import of urls
    from urls.v1 import add_routes as v1
    from urls.v2 import add_routes as v2

    api = ExceptionAwareApi(app, prefix="/api")

    for m in IMPORTED_MODULES:
        mod = import_module(m)
        api = mod.add_routes(api)
    api = v1(api)
    api = v2(api)
    return api


def chunk(iterable, size):  # type: ignore[no-untyped-def] # Function is missing a type annotation
    it = iter(iterable)
    item = list(itertools.islice(it, size))
    while item:
        yield item
        item = list(itertools.islice(it, size))


def even_chunks(iterable, target_size):  # type: ignore[no-untyped-def] # Function is missing a type annotation
    total_len = len(iterable)
    if total_len == 0:
        return []
    new_target_size = math.ceil(total_len / math.ceil(total_len / target_size))
    return chunk(iterable, new_target_size)
