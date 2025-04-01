"""Helpers for integrating the Verification Service with a frontend client."""

from __future__ import annotations

import contextlib
import datetime
import json
from typing import Any, Callable, List, Type, TypedDict, TypeVar

import ddtrace.ext
import httpproblem
from sqlalchemy.exc import OperationalError
from structlog import contextvars
from werkzeug import exceptions

from eligibility import service
from eligibility.e9y import model as e9y_model
from utils import log as logging

__all__ = (
    "verify_member",
    "verify_members",
    "handle_verification_errors",
    "ClientVerificationParameters",
)


logger = logging.logger(__name__)


@ddtrace.tracer.wrap()
def verify_member(
    *,
    user_id: int,
    client_params: ClientVerificationParameters,
    svc: service.EnterpriseVerificationService = None,  # type: ignore[assignment] # Incompatible default for argument "svc" (default has type "None", argument has type "EnterpriseVerificationService")
    commit: bool = True,
) -> e9y_model.EligibilityVerification:
    """Run enterprise verification and associate to a user, if necessary.

    Keyword Args:
        user_id:
            The user ID on which to run verification.
        client_params:
            A bundle of parameters from the upstream client.
            See: `ClientVerificationParameters`.
    """
    svc = svc or service.get_verification_service()
    verification_type = get_verification_type(params=client_params)
    params = parse_parameters(params=client_params, verification_type=verification_type)  # type: ignore[arg-type] # Argument "verification_type" to "parse_parameters" has incompatible type "Optional[Literal[`standard`, `alternate`, `client_specific`, `multistep`, `fileless`, `lookup`, `sso`]]"; expected "Literal[`standard`, `alternate`, `client_specific`, `multistep`, `fileless`, `lookup`, `sso`]"
    given_param_names = [k for k, v in params.items() if v is not None]
    # If we haven't located any params from the request,
    #   default to an un-bounded lookup.
    # This is a valid use-case for multi-track enrollment,
    #   which relies upon a call to the /features endpoint when checking for the
    #   available tracks for a user.
    #   They do not send any identifying flag in the request, currently.
    if not given_param_names and verification_type != "sso":
        verification_type = "lookup"
    elif given_param_names and not verification_type:
        verification_type = "alternate"

    context = dict(
        user_id=user_id,
        params=given_param_names,
        verification_type=verification_type,
    )
    contextvars.bind_contextvars(**context)
    root_span = ddtrace.tracer.current_root_span()
    if root_span:
        for param in given_param_names:
            root_span.set_tag("params", str(param))
        root_span.set_tag("maven.user_id", user_id)
        root_span.set_tag("verification_type", verification_type)

    # Call eligibility verification service here
    try:
        logger.info("Getting verification for user.")

        verification: e9y_model.EligibilityVerification | None

        verification = svc.get_enterprise_association(
            user_id=user_id,
            verification_type=verification_type,
            **params,
        )
        logger.info(
            "Got verification for user.",
            organization_id=verification.organization_id
            if verification is not None
            else None,
            eligibility_member_id=verification.eligibility_member_id
            if verification is not None
            else None,
            verification_id=verification.verification_id
            if verification is not None
            else None,
        )

        if root_span:
            root_span.set_tag(
                "organization_id",
                verification.organization_id if verification is not None else None,
            )

        # commit the changes if any
        if commit and svc.session.is_active:
            svc.session.commit()

        return verification  # type: ignore[return-value] # Incompatible return value type (got "Optional[EligibilityVerification]", expected "EligibilityVerification")
    except service.EnterpriseVerificationError as e:
        logger.info("Failed to verify user.")
        # rollback changes when exceptions happen
        svc.session.rollback()
        raise e
    except OperationalError as e:
        logger.info(f"Encountered errors when committing the changes: {e}")
        # rollback changes when exceptions happen
        svc.session.rollback()
        raise
    finally:
        contextvars.unbind_contextvars(*context)


@ddtrace.tracer.wrap()
def verify_members(
    *,
    user_id: int,
    client_params: ClientVerificationParameters,
    svc: service.EnterpriseVerificationService = None,  # type: ignore[assignment] # Incompatible default for argument "svc" (default has type "None", argument has type "EnterpriseVerificationService")
    commit: bool = True,
) -> List[e9y_model.EligibilityVerification]:
    """Run enterprise verification and associate to a user, if necessary.
    This method replaces verify_member to search all member records for a user
    and create corresponding verification and association records for them

        Keyword Args:
            user_id:
                The user ID on which to run verification.
            client_params:
                A bundle of parameters from the upstream client.
                See: `ClientVerificationParameters`.
    """
    svc = svc or service.get_verification_service()
    verification_type = get_verification_type(params=client_params)
    params = parse_parameters(
        params=client_params, verification_type=verification_type  # type: ignore[arg-type] # Argument "verification_type" to "parse_parameters" has incompatible type "Optional[Literal[`standard`, `alternate`, `client_specific`, `multistep`, `fileless`, `lookup`, `sso`]]"; expected "Literal[`standard`, `alternate`, `client_specific`, `multistep`, `fileless`, `lookup`, `sso`]"
    )
    given_param_names = [k for k, v in params.items() if v is not None]
    # If we haven't located any params from the request,
    #   default to an un-bounded lookup.
    # This is a valid use-case for multi-track enrollment,
    #   which relies upon a call to the /features endpoint when checking for the
    #   available tracks for a user.
    #   They do not send any identifying flag in the request, currently.
    if not given_param_names and verification_type != "sso":
        verification_type = "lookup"
    elif given_param_names and not verification_type:
        verification_type = "alternate"

    context = dict(
        user_id=user_id,
        params=given_param_names,
        verification_type=verification_type,
    )
    contextvars.bind_contextvars(**context)
    root_span = ddtrace.tracer.current_root_span()
    if root_span:
        for param in given_param_names:
            root_span.set_tag("params", str(param))
        root_span.set_tag("maven.user_id", user_id)
        root_span.set_tag("verification_type", verification_type)

    # Call eligibility verification service here
    try:
        logger.info("Getting enterprise associations for user.")

        verifications = svc.get_enterprise_associations(
            user_id=user_id,
            verification_type=verification_type,
            **params,
        )

        # check if organization_id was passed as input
        # if so we should apply filter and only return matching verifications
        input_organization_id = params.get("organization_id")
        if input_organization_id and verifications:
            verifications = apply_filter(input_organization_id, verifications)

        # For logging purposes, extract association info from verification_association_list
        organization_ids = set()
        eligibility_member_ids = set()
        association_ids = []

        if verifications:
            # If we only have verification objects, use their properties
            organization_ids = set(
                v.organization_id for v in verifications if v is not None
            )
            eligibility_member_ids = set(
                v.eligibility_member_id
                for v in verifications
                if v is not None and hasattr(v, "eligibility_member_id")
            )
            # No association_ids to extract from verification objects

        logger.info(
            "Got association(s) for user.",
            organization_ids=organization_ids,
            eligibility_member_ids=eligibility_member_ids,
            association_ids=association_ids,
        )

        if root_span:
            root_span.set_tag(
                "organization_ids",
                organization_ids,
            )

        # commit the changes if any
        if commit and svc.session.is_active:
            svc.session.commit()

        return verifications
    except service.EnterpriseVerificationError as e:
        logger.info("Failed to verify user.")
        # rollback changes when exceptions happen
        svc.session.rollback()
        raise e
    except OperationalError as e:
        logger.info(f"Encountered errors when committing the changes: {e}")
        # rollback changes when exceptions happen
        svc.session.rollback()
        raise
    finally:
        contextvars.unbind_contextvars(*context)


def apply_filter(
    organization_id: int,
    verifications: List[e9y_model.EligibilityVerification],
) -> List[e9y_model.EligibilityVerification]:
    if len(verifications) <= 1:
        return verifications
    return [
        verification
        for verification in verifications
        if verification.organization_id == organization_id
    ]


@contextlib.contextmanager
def handle_verification_errors():  # type: ignore[no-untyped-def] # Function is missing a return type annotation
    try:
        yield
    except Exception as error:
        raise get_http_error(error) from error


def get_http_error(error: Exception):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
    if not isinstance(error, service.EnterpriseVerificationError):
        return error

    error_cls: Type = exceptions.BadRequest
    code = "BAD_REQUEST"
    error_context = dict(verification_type=error.verification_type)
    data = None

    if isinstance(error, service.EnterpriseVerificationQueryError):
        error_cls = exceptions.BadRequest
        error_context["required_params"] = [*error.required_params]  # type: ignore[assignment] # Incompatible types in assignment (expression has type "List[str]", target has type "str")

    elif isinstance(error, service.EnterpriseVerificationConfigurationError):
        error_cls = exceptions.Conflict
        code = f"{error.settings.eligibility_type}_ELIGIBILITY_ENABLED"
        data = error.settings._asdict()

    elif isinstance(error, service.EnterpriseVerificationConflictError):
        error_cls = exceptions.Conflict
        code = "EMPLOYEE_CLAIMED"
        error_context.update(  # type: ignore[call-overload] # No overload variant of "update" of "MutableMapping" matches argument types "int", "Optional[int]", "Optional[int]"
            given_user_id=error.given_user_id,
            employee_id=error.employee_id,
            claiming_user_id=error.claiming_user_id,
        )

    elif isinstance(error, service.EnterpriseVerificationFailedError):
        error_cls = exceptions.NotFound
        code = "EMPLOYEE_NOT_FOUND"
        if error.verification_type == "multistep":
            code = f"HEALTHPLAN_{code}"

    errors = [
        httpproblem.problem(
            status=error_cls.code,
            code=code,
            message=str(error),
            detail=f"Verification Type: {error.verification_type}",
            data=error_context,
        )
    ]
    http_error = error_cls(
        str(error),
    )
    http_error.data = {"data": data, "errors": errors}
    return http_error


def parse_parameters(
    params: ClientVerificationParameters,
    *,
    verification_type: service.VerificationTypeT,
) -> ServiceVerificationParameters:
    date_of_birth = _maybe_type(
        key="date_of_birth",
        data=params,
        loader=_to_date,
    )
    dependent_date_of_birth = _maybe_type(
        key="own_date_of_birth",
        data=params,
        loader=_to_date,
    )
    corp_id = (
        params.get("subscriber_id") or None
        if verification_type == "multistep"
        else params.get("unique_corp_id") or None
    )
    organization_id = _maybe_type(
        key="organization_id",
        data=params,
        loader=int,
    )
    is_employee = _maybe_type(
        key="is_employee", data=params, loader=lambda v: bool(json.loads(v))
    )
    eligibility_member_id = _maybe_type(
        key="eligibility_member_id",
        data=params,
        loader=int,
    )
    return {
        "date_of_birth": date_of_birth,
        "dependent_date_of_birth": dependent_date_of_birth,
        "company_email": params.get("company_email") or None,
        "work_state": params.get("work_state") or None,
        "first_name": params.get("first_name") or None,
        "last_name": params.get("last_name") or None,
        "unique_corp_id": corp_id,
        "organization_id": organization_id,
        "is_employee": is_employee,
        "eligibility_member_id": eligibility_member_id,
        "verification_creator": params.get("verification_creator") or None,
        "zendesk_id": params.get("zendesk_id") or None,
        "employee_first_name": params.get("employee_first_name") or None,
        "employee_last_name": params.get("employee_last_name") or None,
        "verification_type_v2": params.get("verification_type_v2") or None,
    }


def _to_date(
    string: str | datetime.datetime | datetime.date | None,
) -> datetime.date | None:
    if isinstance(string, datetime.datetime):
        return string.date()
    if isinstance(string, datetime.date):
        return string
    if isinstance(string, str):
        try:
            return datetime.datetime.fromisoformat(string).date()
        except ValueError:
            logger.warning("Invalid date input")
    return None


def _maybe_type(
    *,
    key: str,
    data: dict[str, Any] | ClientVerificationParameters,
    loader: type[T] | Callable[[Any], T],
) -> T | None:
    value = data.get(key)
    if value is None:
        return None
    if value == "":
        return None
    try:
        return loader(value)  # type: ignore[call-arg] # Too many arguments for "object"
    except (TypeError, ValueError):
        logger.warning("Failed to parse given value.", param=key)
        return None


T = TypeVar("T")


def get_verification_type(
    params: ClientVerificationParameters,
) -> service.VerificationTypeT | None:
    if "verification_type" in params:
        return params["verification_type"]

    if params.get("fileless", False):
        return "fileless"

    if params.get("external_identity", False):
        return "sso"

    if params.get("healthplan", False):
        return "multistep"

    if params.get("standard", False):
        return "standard"

    if params.get("alternate", False):
        return "alternate"

    if {"organization_id", "unique_corp_id"}.issubset(params.keys()):
        return "client_specific"

    return None


class ClientVerificationParameters(TypedDict, total=False):
    date_of_birth: datetime.date
    """The date of birth of the primary account.

    Used with: standard, alternate, client-specific
    """
    own_date_of_birth: datetime.date
    """The date of birth of the dependent, if provided.

    Used with: standard, alternate, client-specific
    """
    company_email: str
    """An email associated to the target organization.

    Used with: standard
    """
    work_state: str
    """The state which a member works in.

    Used with: alternate
    """
    first_name: str
    """The first name of the member.

    Used with: alternate
    """
    last_name: str
    """The last name of the member.

    Used with: alternate
    """
    unique_corp_id: str
    """A unique ID associated to the primary account.

    Used with: client-specific.
    """
    is_employee: bool
    """Whether this query is for a primary or dependent.

    Used with: client-specific
    """
    organization_id: int
    """The specific organization to query.

    Used with: client-specific
    """
    subscriber_id: str
    """The unique ID associated to the primary account.

    Used with: health plans (e.g., multi-step)
    """
    external_identity: bool
    """A flag indicating we should use an external identity for verification."""
    fileless: bool
    """A flag indicating we should use fileless verification logic."""
    healthplan: bool
    """A flag indicating we should use multi-step verification with & subscriber_id."""
    standard: bool
    """A flag indicating we should use standard verification."""
    alternate: bool
    """A flag indicating we should use alternate verification."""
    verification_type: service.VerificationTypeT
    """Override all flags and run a specific verification type."""
    eligibility_member_id: int
    """Override all flags and lookup a member by eligibility ID."""
    verification_creator: str = None
    """Keep track of the user who generated this manual verification"""
    zendesk_id: str | None = None
    """The identifier for the zendesk ticket a user was manually verified with"""
    employee_first_name: str | None = None
    employee_last_name: str | None = None
    verification_type_v2: str | None = None
    """Identifies the verification type in simplified verification flow"""


class ServiceVerificationParameters(TypedDict):
    date_of_birth: datetime.date | None
    dependent_date_of_birth: datetime.date | None
    company_email: str | None
    work_state: str | None
    first_name: str | None
    last_name: str | None
    unique_corp_id: str | None
    organization_id: int | None
    is_employee: bool | None
    eligibility_member_id: int | None
    verification_creator: str | None
    zendesk_id: str | None
    employee_first_name: str | None
    employee_last_name: str | None
    verification_type_v2: str | None
