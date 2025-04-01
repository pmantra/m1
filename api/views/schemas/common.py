from __future__ import annotations

import datetime
import inspect
import os
import traceback
from collections import namedtuple
from functools import lru_cache
from traceback import format_exc
from typing import Any, Optional, Protocol

import ddtrace
import marshmallow_v1
import phonenumbers
import pymysql
import sqlalchemy
from flask import current_app
from flask_restful import abort
from httpproblem import Problem
from marshmallow_v1 import Schema, fields, utils
from marshmallow_v1.exceptions import (
    MarshallingError,
    UnmarshallingError,
    ValidationError,
)
from maven import feature_flags
from sqlalchemy.orm.exc import NoResultFound

import eligibility
from appointments.models.cancellation_policy import CancellationPolicy
from authn.domain.service import MFAService
from authn.models.user import User
from authz.models.roles import ROLES
from common import stats
from geography.repository import CountryRepository, SubdivisionRepository
from models.enterprise import Invite
from models.profiles import (
    Category,
    Certification,
    Language,
    MemberProfile,
    PractitionerProfile,
    State,
)
from models.verticals_and_specialties import Specialty, Vertical, is_cx_vertical_name
from providers.service.provider import ProviderService
from storage.connection import db
from tracks.utils.common import get_active_member_track_modifiers
from utils import flagr, security
from utils.data import normalize_phone_number, normalize_phone_number_old
from utils.flag_groups import DB_CONNECTION_RECOVERY_RELEASE
from utils.log import logger
from wallet.config import use_alegeus_for_reimbursements
from wallet.models.constants import WalletState, WalletUserStatus
from wallet.models.reimbursement_wallet import ReimbursementWallet
from wallet.models.reimbursement_wallet_user import ReimbursementWalletUsers

log = logger(__name__)

_other_user_field_exclusions = frozenset(
    [
        "address",
        "agreements",
        "faq_password",
        "phone_number",
        "state",
        "tel_number",
        "tel_region",
    ]
)

SPAN_TYPE: str = "web"
SERVICE: str = "marshmallow"

# Note: This applies to all schema definitions are using marshmallow_v1. Latest
# v3 has been shown (through local probe) to bubble exceptions as expected.
#
# During a call to `dump(SomeModel())` marshmallow visits each property. Those
# marked as a fields.Method("...") have instance level functions called to
# resolve the property value. Marshmallow_v1 explicitly ignores AttributeErrors
# during serialization. Additionally there is a non-trivial amount of business
# logic embedded in the schema resolution methods.
#
# The outcome of this is that exceptions due to improper field access are
# silently swallowed and null is returned to the client for that field. The
# client will likely not expect that field to be null and produce a degraded UX
# for the user.
#
# fields.Method("..., required=true") Marshmallow accepts a required flag that
# may be passed in the definition. If present, marshmallow will surface the
# AttributeError as a validation exception. From a cursory review of our code
# base, we are not consistently utilizing this flag.
#
# This is a DIRECT copy pasta of the marshmallow_v1 Method._serialize method
# that can be found here -> https://github.com/marshmallow-code/marshmallow/blob/1.2.6/marshmallow/fields.py#L1218

# Flag used to signal the forced raise
RAISE_ATTRIBUTE_ERRORS_FLAG = "RAISE_ATTRIBUTE_ERRORS"

# used when logging warnings during tests
serialization_warning_template = """
Encountered AttributeError during serialization

{exception}
{schema}
{schema_property}
{called_method}
{call_trace}
"""


# func that will be monkey patched over existing marshmallow_v1 Method._serialize
def _serialize(self, value, attr, obj):  # type: ignore[no-untyped-def] # Function is missing a type annotation
    try:
        with ddtrace.tracer.trace(name="marshmallow_v1._serialize", resource=attr):
            method = utils.callable_or_raise(
                getattr(self.parent, self.method_name, None)
            )
            # By convention marshmallow expects the first argument to be the
            # source object to extract the schema value from and if optionally
            # present the 2nd value is a context dictionary that may contain
            # arbitrary data. The get_func_args provided in marshmallow_v1
            # cannot support type hinting meaning we are restricted from using
            # it in all schema classes. This is a massive QOL issue as it blocks
            # our ability to catch developer mistakes at commit time with static
            # analysis. We resolve this limitation by monkey patching (below)
            # the get_func_args with a version that is more performant and can
            # accommodate type hinting.
            if len(utils.get_func_args(method)) > 2:
                if self.parent.context is None:
                    msg = "No context available for Method field {0!r}".format(attr)
                    raise MarshallingError(msg)
                return method(obj, self.parent.context)
            else:
                return method(obj)
    except AttributeError as e:
        # Aaron Jones 2024-10-24
        # This is where marshmallow_v1 swallows the exception.
        # It would be in our best interest to raise it instead.
        # Initially we will leave current behavior in place and emit metrics.
        # emit metrics so we can better understand the scope of undetected exceptions
        stats.increment(
            metric_name="mono.marshmallow_v1.attribute_error_during_serialization",
            tags=["attribute_name:" + attr],
            pod_name=stats.PodNames.CORE_SERVICES,
        )

        # To provide a more precise local developer experience we provide a
        # flag that can be set to raise the exception instead of ignoring it.
        # Initially this may be used ad-hoc. Within a fairly short time frame
        # we will globally enable this for test runners and require explicit
        # disabling for problematic areas.
        if getattr(marshmallow_v1.fields.Method, RAISE_ATTRIBUTE_ERRORS_FLAG, None):
            # defer warnings import to avoid pulling it in outside of tests
            import warnings

            warnings.warn(  # noqa  B028 TODO:  No explicit stacklevel keyword argument found. The warn method from
                # the warnings module uses a stacklevel of 1 by default. This will only show a stack trace for the
                # line on which the warn method is called. It is therefore recommended to use a stacklevel of 2 or
                # greater to provide more information to the user.
                serialization_warning_template.format(
                    exception=e,
                    schema=str(obj),
                    schema_property=attr,
                    called_method=str(self.method_name),
                    call_trace=traceback.format_exc(),
                )
            )
            raise e

        # default
        pass


# Explicitly override the marshmallow_v1 Method._serialize method directly so
# that version upgrades leave this monkey patch behind. We patch even in
# production to extract metrics on hidden exceptions.
marshmallow_v1.fields.Method._serialize = _serialize  # type: ignore[attr-defined]
marshmallow_v1.fields.Method._serialize = _serialize  # type: ignore[attr-defined]


# When adding type hints in schemas marshmallow_v1 fails to resolve function and
# method calls due to:
# ..../marshmallow_v1/utils.py:385: DeprecationWarning: inspect.getargspec() is deprecated since Python 3.0, use inspect.signature() or inspect.getfullargspec()
#   return inspect.getargspec(inspect.unwrap(func)).args
def _get_func_args(func):  # type: ignore[no-untyped-def] # Function is missing a type annotation
    """Return a tuple of argument names for a function."""
    # Note: a 3x perf gain can be achieved here by swapping inspect.unwrap() for
    # unwrapped = getattr(func, "__wrapped__", func)
    # This comes at the cost of only supporting 1 level of decorator depth.
    # Python devs expect to be able to decorate to an arbitrary depth so
    # encountering an issue here would be a surprise. Currently (12/2023) there
    # is no marshmallow_v1 schema with a decorator depth > 1 so the getattr
    # approach is currently able to succeed. We are intentionally not using it
    # to maintain existing developer implementation expectations.
    unwrapped = inspect.unwrap(func)
    return unwrapped.__code__.co_varnames[: unwrapped.__code__.co_argcount]


# monkey patch the marshmallow_v1 get_func_args method to use our override
marshmallow_v1.utils.get_func_args = _get_func_args


def should_attempt_dump_retry(
    schema_name: str = "",
    error_type: str = "",
) -> bool:
    """
    Returns true if we should attempt a single retry a failed schema dump.
    Defaults to False.
    """
    context_builder = feature_flags.Context.builder("schema_dump_retry_on_mysql_error")
    context_builder.set("schema_name", schema_name)
    context_builder.set("error_type", error_type)
    context = context_builder.build()

    return feature_flags.bool_variation(
        DB_CONNECTION_RECOVERY_RELEASE.RETRY_READ_ON_NETWORK_ERROR,
        context=context,
        default=False,
    )


def should_enable_can_member_interact() -> bool:
    return feature_flags.bool_variation(
        "kill-switch-messaging-channel-enable-can-member-interact",
        default=False,
    )


class MavenSchema(Schema):
    class Meta:
        strict = True

    # workaround until 'missing' kwarg is avail on fields.
    # https://github.com/marshmallow-code/marshmallow/issues/45
    @ddtrace.tracer.wrap(resource="maven_schema", service=SERVICE, span_type=SPAN_TYPE)
    def make_object(schema, in_data):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        if in_data is None:
            in_data = {}

        for name, field in schema.fields.items():
            if name not in in_data and field.metadata.get("missing"):
                in_data[name] = field.metadata["missing"]
        return in_data

    def dump(self, *args, **kwargs):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        with ddtrace.tracer.trace(
            name="marshmallow_v1.dump",
            resource=self.__class__.__name__,
            service=SERVICE,
            span_type=SPAN_TYPE,
        ):
            try:
                return super().dump(*args, **kwargs)
            except (
                sqlalchemy.exc.OperationalError,
                pymysql.err.InternalError,
                pymysql.err.OperationalError,
            ) as e:
                try:
                    # if the flag is off maintain current behavior
                    if not should_attempt_dump_retry(
                        schema_name=type(self).__name__,
                        error_type=type(e).__name__,
                    ):
                        raise e
                except Exception as feature_evaluation_exception:
                    log.exception(
                        "failed evaluating feature flag for schema dump retry",
                        exception=feature_evaluation_exception,
                    )
                    # if we fail to evaluate the feature flag, continue with
                    # existing behavior and raise the original exception
                    raise e

                # in the process of dumping a schema we can hit a pymysql error
                # that relates only to the connection or packet loss, attempt
                # one additional time. If the 2nd attempt throws any error then
                # allow it to raise.
                log.info(
                    "Caught pymysql error during schema dump, attempting one retry",
                    exception=e,
                    schema=f"{type(self)}",
                )
                # ensure we start the dump with a fresh connection
                db.session.rollback()
                return super().dump(*args, **kwargs)


class WithDefaultsSchema(MavenSchema):
    # Always use defaults if field not provided
    # https://github.com/marshmallow-code/marshmallow/issues/45
    @ddtrace.tracer.wrap(resource="with_defaults", service=SERVICE, span_type=SPAN_TYPE)
    def make_object(schema, in_data):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        for name, field in schema.fields.items():
            if name not in in_data:
                in_data[name] = field.default
        return super().make_object(in_data)


@MavenSchema.error_handler
@ddtrace.tracer.wrap(service=SERVICE, span_type=SPAN_TYPE)
def handle_errors(schema, errors, obj):  # type: ignore[no-untyped-def] # Function is missing a type annotation
    log.debug("MavenSchema Error: Schema=%s Object=%s Errors=%s", schema, obj, errors)
    abort(400, message=errors)


# Use this protocol to allow static analysis tools to properly determine the
# existence and type of class properties on mixins.
# fmt: off
class HasContextProtocol(Protocol):
    @property
    def context(self) -> dict:
        ...


# fmt: on


# ---- Request and Response Envelopes -----


class OrderDirectionField(fields.Field):
    @ddtrace.tracer.wrap(
        resource="order_direction_field", service=SERVICE, span_type=SPAN_TYPE
    )
    def _deserialize(self, value):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        if value is None:
            value = self.default

        value = value.lower()
        if value not in ("asc", "desc"):
            raise UnmarshallingError(f"{value} is not a valid order direction!")

        return value


@ddtrace.tracer.wrap(span_type=SPAN_TYPE)
def validate_offset(value):  # type: ignore[no-untyped-def] # Function is missing a type annotation
    if value is not None:
        if not isinstance(value, int):
            raise ValidationError("Offset must be an integer")
        if value < 0:
            raise ValidationError("Offset must be positive")


@ddtrace.tracer.wrap(span_type=SPAN_TYPE)
def validate_limit(value):  # type: ignore[no-untyped-def] # Function is missing a type annotation
    if value is not None:
        if not isinstance(value, int):
            raise ValidationError("Limit must be an integer")
        if value < 0:
            raise ValidationError("Limit must be positive")
        if value > 2000:
            raise ValidationError("Cannot be > 2000")


class PaginableArgsSchema(WithDefaultsSchema):
    offset = fields.Integer(default=0, required=False, validate=validate_offset)
    limit = fields.Integer(default=10, required=False, validate=validate_limit)
    order_direction = OrderDirectionField(default="desc", required=False)


class PaginationInfoSchema(PaginableArgsSchema):
    total = fields.Integer(required=False)


class PaginableOutputSchema(MavenSchema):
    pagination = fields.Nested(PaginationInfoSchema)
    meta = fields.Raw()
    data = fields.Raw()


# ---- Fields -----


class BooleanField(fields.Boolean):
    truthy = {True, "true", "True", "TRUE", 1, "1"}  # noqa: B033
    falsy = {False, "false", "False", "FALSE", 0, "0", None, "None"}  # noqa: B033


class BooleanDefaultNoneField(fields.Boolean):
    truthy = {True, "true", "True", "TRUE", 1, "1"}  # noqa: B033
    falsy = {False, "false", "False", "FALSE", 0, "0", None, "None"}  # noqa: B033

    def _deserialize(self, value):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        if value is None:
            return self.default
        else:
            return super()._deserialize(value)


class PrivacyOptionsField(fields.Field):
    @ddtrace.tracer.wrap(
        resource="privacy_option_field", service=SERVICE, span_type=SPAN_TYPE
    )
    def _deserialize(self, value):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        allowed = ["anonymous", "basic", "full_access"]
        if value is None or (value and value.lower() in allowed):
            return value
        raise ValidationError(f"{value} not an allowed privacy choice!")


class CancellationPolicyField(fields.Field):
    @ddtrace.tracer.wrap(
        resource="cancellation_policy_field",
        service=SERVICE,
        span_type=SPAN_TYPE,
    )
    def _deserialize(self, value):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        if not value:
            raise ValidationError("You must provide a cancellation policy!")

        try:
            policy = (
                db.session.query(CancellationPolicy)
                .filter(CancellationPolicy.name == value.lower())
                .one()
            )
        except NoResultFound:
            raise ValidationError(f"{value} is not a valid cancellation policy")
        else:
            return policy

    @ddtrace.tracer.wrap(
        resource="cancellation_policy_field",
        service=SERVICE,
        span_type=SPAN_TYPE,
    )
    def _serialize(self, value, attr, obj):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        if isinstance(value, str):
            # cached values are already processed
            return value
        else:
            return value.name


class ApplicationNameField(fields.Field):
    @ddtrace.tracer.wrap(
        resource="application_name_field",
        service=SERVICE,
        span_type=SPAN_TYPE,
    )
    def _deserialize(self, value):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        if "com.mavenclinic.Forum" in value:
            return "forum"
        elif "com.mavenclinic.Practitioner" in value:
            return "practitioner"
        elif "com.mavenclinic.Maven" in value:
            return "member"
        else:
            raise ValidationError(f"Bad User-Agent for application name: {value}")


class MavenDateTime(fields.DateTime):
    @ddtrace.tracer.wrap(
        resource="maven_date_time", service=SERVICE, span_type=SPAN_TYPE
    )
    def _deserialize(self, value):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        if value:
            value = super()._deserialize(value)
        else:
            value = None

        if value:
            if value.tzinfo is not None:
                raise ValidationError(
                    "Please send a datetime without a timezone offset!", self.name
                )

            return value.replace(microsecond=0)

    @ddtrace.tracer.wrap(
        resource="maven_date_time", service=SERVICE, span_type=SPAN_TYPE
    )
    def _serialize(self, value, attr, obj):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        if isinstance(value, datetime.datetime):
            value = value.replace(tzinfo=None, microsecond=0)
            return value.isoformat()
        elif isinstance(value, datetime.date):
            return value.isoformat()
        else:
            # cached values are already processed
            return value


@lru_cache(maxsize=32)
def _cached_normalize_number(phone_number):  # type: ignore[no-untyped-def] # Function is missing a type annotation
    if phone_number:
        try:
            return normalize_phone_number(phone_number, None)
        except ValidationError:
            log.warn(f"Could not normalize phone number from database: {phone_number}")
    return ("", None)


def get_normalized(obj):  # type: ignore[no-untyped-def] # Function is missing a type annotation
    phone_number = fields.utils.get_value("phone_number", obj)  # type: ignore[attr-defined] # Module has no attribute "utils"
    if phone_number is None:
        phone_number = fields.utils.get_value("tel_number", obj)  # type: ignore[attr-defined] # Module has no attribute "utils"
    return _cached_normalize_number(phone_number)


class PhoneNumber(fields.String):
    @ddtrace.tracer.wrap(
        resource="phone_number_field", service=SERVICE, span_type=SPAN_TYPE
    )
    def _serialize(self, value, attr, obj):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        _, num = get_normalized(obj)
        return normalize_phone_number_old(num, include_extension=True)


class TelRegion(fields.String):
    # Determine region from phone number
    @ddtrace.tracer.wrap(
        resource="tel_region_field", service=SERVICE, span_type=SPAN_TYPE
    )
    def serialize(self, attr, obj, accessor=None):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        _, num = get_normalized(obj)
        if num is None:
            return None
        return phonenumbers.region_code_for_number(num)


class TelNumber(fields.String):
    # Take the normalized form straight from the phone_number being serialized.
    @ddtrace.tracer.wrap(
        resource="tel_number_field", service=SERVICE, span_type=SPAN_TYPE
    )
    def serialize(self, attr, obj, accessor=None):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        tel_number, _ = get_normalized(obj)
        return tel_number


class TelNumberOrNone(TelNumber):
    @ddtrace.tracer.wrap(
        resource="tel_number_or_none_field",
        service=SERVICE,
        span_type=SPAN_TYPE,
    )
    def serialize(self, attr, obj, accessor=None):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        if isinstance(obj, PractitionerProfile):
            if any(is_cx_vertical_name(v.name) for v in obj.verticals):
                return None
        return super().serialize(attr, obj, accessor)


# ----- Custom Collection Fields -----


class CSVIntegerField(fields.Field):
    @ddtrace.tracer.wrap(
        resource="csv_field_field", service=SERVICE, span_type=SPAN_TYPE
    )
    def _deserialize(self, value):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        if not value:
            return []

        int_list = []

        for i in value.split(","):
            try:
                int_list.append(int(i))
            except ValueError:
                raise ValidationError(f"{i} not a valid int!")

        return int_list

    @ddtrace.tracer.wrap(resource="csv_field", service=SERVICE, span_type=SPAN_TYPE)
    def _serialize(self, value, attr, obj):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        try:
            return [int(i) for i in value]
        except ValueError:
            raise ValidationError(f"{value} not a valid int!")


class CSVStringField(fields.Field):
    @ddtrace.tracer.wrap(
        resource="csv_string_field", service=SERVICE, span_type=SPAN_TYPE
    )
    def _deserialize(self, value):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        str_list = []

        for i in value.split(","):
            try:
                str_list.append(str(i))
            except ValueError:
                raise ValidationError(f"{value} not a valid value!")

        return str_list

    @ddtrace.tracer.wrap(
        resource="csv_string_field", service=SERVICE, span_type=SPAN_TYPE
    )
    def _serialize(self, value, attr, obj):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        return ",".join(str(s) for s in value)


class _ArrayofAttr(fields.Field):
    cls = None
    array_attr = "id"
    capitalization = "upper"

    @ddtrace.tracer.wrap(
        resource="array_of_attr_field", service=SERVICE, span_type=SPAN_TYPE
    )
    def _deserialize(self, value):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        if not self.cls:
            raise NotImplementedError
        if not value:
            return []

        vals = []
        for v in value:
            # TODO: this should be taken out - it's here for compatibility
            # with flask-restful behavior for when this was migrated. Really
            # this should be a 400 error - an empty list is valid but an empty
            # string in the list should not be
            if not v or (v == " "):
                continue

            _value = v
            if self.capitalization and self.capitalization in ("upper", "lower"):
                _value = getattr(v, self.capitalization)()

            try:
                vals.append(
                    db.session.query(self.cls)
                    .filter((getattr(self.cls, self.array_attr) == _value))
                    .one()
                )
            except NoResultFound:
                raise ValidationError(f"{v} is not an allowed {self.cls.__name__}!")

        return vals

    @ddtrace.tracer.wrap(
        resource="array_of_attr_field", service=SERVICE, span_type=SPAN_TYPE
    )
    def _serialize(self, value, attr, obj):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        if not value:
            return []

        ret = []
        for _ in value:
            # cached values are already processed
            if isinstance(_, str):
                ret.append(_)
            else:
                ret.append(getattr(_, self.array_attr))

        return ret


class _AttrString(fields.Field):
    cls = None
    array_attr = "id"
    capitalization = "upper"
    allow_none = False
    allow_blank = False

    @ddtrace.tracer.wrap(
        resource="attr_string_field", service=SERVICE, span_type=SPAN_TYPE
    )
    def _deserialize(self, value):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        if value and self.capitalization and self.capitalization in ("upper", "lower"):
            value = getattr(value, self.capitalization)()

        if value is None and self.allow_none:
            return None
        if value == "" and self.allow_blank:
            return None

        try:
            return (
                db.session.query(self.cls)
                .filter((getattr(self.cls, self.array_attr) == value))
                .one()
            )
        except NoResultFound:
            raise ValidationError(f"{value} is not an allowed {self.cls.__name__}!")  # type: ignore[attr-defined] # "None" has no attribute "__name__"

    def _serialize(self, value, attr, obj):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        return getattr(value, self.array_attr)


# These appear to be flask restful fields which were refactored to marshmallow v1
# See: https://flask-restful.readthedocs.io/en/latest/fields.html
# See commit 85241ee569b61d2b80b85b1730668555db3e4247
# Thanks to Allon for the archeology
class ArrayofNames(_ArrayofAttr):
    array_attr = "name"
    capitalization = None  # type: ignore[assignment] # Incompatible types in assignment (expression has type "None", base class "_ArrayofAttr" defined the type as "str")


class AllowedLanguages(ArrayofNames):
    cls = Language  # type: ignore[assignment] # Incompatible types in assignment (expression has type "Type[Language]", base class "_ArrayofAttr" defined the type as "None")


class AllowedCategories(ArrayofNames):
    cls = Category  # type: ignore[assignment] # Incompatible types in assignment (expression has type "Type[Category]", base class "_ArrayofAttr" defined the type as "None")


class AllowedCertifications(ArrayofNames):
    cls = Certification  # type: ignore[assignment] # Incompatible types in assignment (expression has type "Type[Certification]", base class "_ArrayofAttr" defined the type as "None")


class AllowedSpecialties(ArrayofNames):
    cls = Specialty  # type: ignore[assignment] # Incompatible types in assignment (expression has type "Type[Specialty]", base class "_ArrayofAttr" defined the type as "None")


class AllowedVerticals(ArrayofNames):
    cls = Vertical  # type: ignore[assignment] # Incompatible types in assignment (expression has type "Type[Vertical]", base class "_ArrayofAttr" defined the type as "None")
    array_attr = "marketing_name"


class USAStatesCSVField(fields.Field):
    @ddtrace.tracer.wrap(
        resource="usa_states_csv_field", service=SERVICE, span_type=SPAN_TYPE
    )
    def _deserialize(self, value):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        states = []
        for abbr in value.split(","):
            try:
                state = (
                    db.session.query(State)
                    .filter(State.abbreviation == abbr.upper())
                    .one()
                )
            except NoResultFound:
                raise ValidationError(f"Invalid State! You entered {abbr}")
            else:
                states.append(state)

        return states

    def _serialize(self, value, attr, obj):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        try:
            return ",".join(str(s.abbreviation) for s in value)
        except Exception as e:
            log.exception(
                "failed serializing USAStatesCSVField value",
                exception=e,
            )
            raise e


class USAStatesListField(_ArrayofAttr):
    cls = State  # type: ignore[assignment] # Incompatible types in assignment (expression has type "Type[State]", base class "_ArrayofAttr" defined the type as "None")
    array_attr = "abbreviation"
    capitalization = "upper"


class USAStateStringField(_AttrString):
    cls = State  # type: ignore[assignment] # Incompatible types in assignment (expression has type "Type[State]", base class "_AttrString" defined the type as "None")
    array_attr = "abbreviation"
    capitalization = "upper"


class USAStateStringFieldAllowNone(USAStateStringField):
    allow_none = True
    allow_blank = True


# ---- Shared schemas for multiple views -----


class SessionMetaInfoSchema(MavenSchema):
    notes = fields.String()
    created_at = MavenDateTime()
    modified_at = MavenDateTime()
    draft = fields.Boolean(default=None)


class DoseSpotPharmacySchema(WithDefaultsSchema):
    # Note: Based on iOS field expectations
    PharmacyId = fields.String()
    Pharmacy = fields.String()
    State = fields.String()
    ZipCode = fields.String()
    PrimaryFax = fields.String()
    StoreName = fields.String()
    Address1 = fields.String()
    Address2 = fields.String()
    PrimaryPhone = fields.String()
    PrimaryPhoneType = fields.String()
    City = fields.String()
    IsPreferred = fields.Boolean()
    IsDefault = fields.Boolean()
    ServiceLevel = fields.Integer()


class VideoSchema(Schema):
    session_id = fields.String()
    member_token = fields.String()
    practitioner_token = fields.String()


class OrganizationSchema(MavenSchema):
    id = fields.Integer()
    name = fields.String()
    vertical_group_version = fields.String()
    bms_enabled = fields.Boolean()
    rx_enabled = fields.Boolean()
    education_only = fields.Boolean()
    display_name = fields.String()
    benefits_url = fields.String(default=None)


class PlanSchema(MavenSchema):
    id = fields.Integer()
    segment_days = fields.Integer()
    minimum_segments = fields.Integer()
    price_per_segment = fields.Decimal(as_string=True)
    is_recurring = fields.Boolean()
    active = fields.Method("get_active")
    description = fields.String()
    billing_description = fields.String()

    def get_active(self, plan, context):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        return True


@ddtrace.tracer.wrap(span_type=SPAN_TYPE)
def validate_address(schema, data):  # type: ignore[no-untyped-def] # Function is missing a type annotation
    state = data.get("state")
    country = data.get("country")
    if not country:
        return True

    countries = CountryRepository(session=db.session)
    validated_country = countries.get_by_name(name=country)
    if not validated_country:
        raise ValidationError(f"{country} is not a valid country code!")

    subdivisions = SubdivisionRepository()
    if (
        validated_country.alpha_2 == "US"
        and not subdivisions.get_by_country_code_and_state(
            country_code=validated_country.alpha_2,
            state=state,
        )
    ):
        raise ValidationError(f"{state} is not a valid US state")
    return True


class AddressSchema(MavenSchema):
    __validators__ = [validate_address]
    street_address = fields.String(required=True)
    zip_code = fields.String(required=True)
    city = fields.String(required=True)
    state = fields.String(required=True)
    country = fields.String(required=True)


@ddtrace.tracer.wrap(span_type=SPAN_TYPE)
def validate_phone_number(required):  # type: ignore[no-untyped-def] # Function is missing a type annotation
    def validate(schema, data):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        for f in ["tel_number", "tel_region"]:
            assert f in schema.fields, f"Missing required field for schema ({f})."

        # To support pre tel_number clients, new clients are required to provide *both* phone_number and tel_number.
        # Due to a pattern of getting a resource from the API, modifying the object, and sending it back,
        # old clients may be sending both fields, with only the old one modified. A difference between the old and
        # new field indicates that the old field should be respected. When the old field is removed from the schema,
        # clients will be able to transition fully and exclusively to "tel_number".
        #
        # 1) deploy this backend
        # 2) clients send same value for phone_number and tel_number
        # 3) wait for old clients to phase out of use (see log below)
        # 4) remove phone_number from schema
        # 5) remove phone_number from clients
        tel_number = data.get("tel_number", None)
        phone_number = data.get("phone_number", None)
        if tel_number == phone_number or phone_number is None:
            number = tel_number
        else:
            number = phone_number
            # When this stops showing up in the logs, we're ready for step 4.
            log.info("deprecated_phone_number")

        if not number:
            if required:
                raise ValidationError(
                    "Missing data for required field.", "phone_number"
                )
            return True

        region = data.get("tel_region", None)
        if "phone_number" in schema.fields:
            data["phone_number"], _ = normalize_phone_number(number, region)

        return True

    return validate


@ddtrace.tracer.wrap(span_type=SPAN_TYPE)
def validate_subdivision():  # type: ignore[no-untyped-def] # Function is missing a return type annotation
    def validate(schema, data):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        subdivisions = SubdivisionRepository()
        if subdivision := data.get("subdivision_code"):
            if subdivisions.get(subdivision_code=subdivision):
                return True
            raise ValidationError(f"'{subdivision}' is not a valid subdivision")

    return validate


@ddtrace.tracer.wrap(span_type=SPAN_TYPE)
def validate_country():  # type: ignore[no-untyped-def] # Function is missing a return type annotation
    def validate(schema, data):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        countries = CountryRepository(session=db.session)
        if country := data.get("country"):
            if countries.get_by_name(name=country):
                return True
            raise ValidationError(f"'{country}' is not a valid country")

    return validate


class MemberProfileSchema(MavenSchema):
    __validators__ = [validate_phone_number(required=False), validate_subdivision()]
    state = USAStateStringFieldAllowNone()
    country = fields.Method("get_country")
    phone_number = PhoneNumber()
    tel_region = TelRegion()
    tel_number = TelNumber()
    address = fields.Nested(AddressSchema)
    opted_in_notes_sharing = fields.Boolean(required=False)
    color_hex = fields.String()
    user_flags = fields.Method("get_current_risk_flags")
    can_book_cx = fields.Method("get_can_book_cx")
    has_care_plan = fields.Boolean()
    care_plan_id = fields.Integer(nullable=True, default=None)  # type: ignore[arg-type] # Argument "default" to "Integer" has incompatible type "None"; expected "int"
    subdivision_code = fields.String(required=False)

    def get_current_risk_flags(self, obj, context):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        if isinstance(obj, dict):
            return
        return [{"id": f.id} for f in obj.user.current_risk_flags()]

    @ddtrace.tracer.wrap()
    def get_can_book_cx(self, obj, context):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        return obj.user.is_enterprise

    def get_country(self, obj, context):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        if isinstance(obj, dict):
            return obj.get("country")

        return obj.country and obj.country.alpha_2


class AgreementsSchema(MavenSchema):
    subscription = BooleanField(default=False)


class V2VerticalGetSchema(Schema):
    ids = CSVIntegerField(required=False)


class V2VerticalSchema(Schema):
    id = fields.Integer()
    name = fields.String()
    pluralized_display_name = fields.String()
    description = fields.String()
    long_description = fields.String()
    can_prescribe = fields.Boolean()
    filter_by_state = fields.Boolean()


class PractitionerProfileSchema(MavenSchema):
    __validators__ = [
        validate_phone_number(required=False),
        validate_subdivision(),
        validate_country(),
    ]
    user_id = fields.Integer(required=False)
    certified_states = fields.Method("get_certified_states")
    years_experience = fields.Integer(required=False)
    certifications = AllowedCertifications(required=False)
    categories = AllowedCategories(required=False)
    specialties = AllowedSpecialties(required=False)
    verticals = AllowedVerticals(required=False)
    vertical_objects = fields.Method("get_vertical_objects")
    languages = AllowedLanguages(required=False)
    phone_number = PhoneNumber()
    tel_region = TelRegion()
    tel_number = TelNumberOrNone()
    cancellation_policy = CancellationPolicyField(required=False)
    awards = fields.String(required=False)
    work_experience = fields.String(required=False)
    education = fields.String(required=False)
    reference_quote = fields.String(required=False)
    state = USAStateStringFieldAllowNone(required=False)
    next_availability = MavenDateTime(required=False)
    agreements = fields.Nested(AgreementsSchema, required=False)
    address = fields.Nested(AddressSchema, required=False)
    can_prescribe = fields.Method("get_can_prescribe")
    can_prescribe_to_member = fields.Method("get_can_prescribe_to_member")
    messaging_enabled = fields.Boolean(required=False, default=False)
    response_time = fields.Integer(required=False, default=None)  # type: ignore[arg-type] # Argument "default" to "Integer" has incompatible type "None"; expected "int"
    rating = fields.Float(required=False, default=None)  # type: ignore[arg-type] # Argument "default" to "Float" has incompatible type "None"; expected "float"
    care_team_type = fields.Method("get_care_team_type")
    faq_password = fields.Method("get_faq_password")
    is_cx = fields.Method("get_is_cx")
    subdivision_code = fields.String(required=False)
    country = fields.Method("get_country")
    country_code = fields.String(required=False)
    certified_subdivision_codes = fields.Method("get_certified_subdivision_codes")
    can_member_interact = fields.Method("get_can_member_interact")

    def get_certified_subdivision_codes(self, obj, context):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        if isinstance(obj, dict):
            return obj.get("certified_subdivision_codes", [])

        if obj.verticals:
            subdivision_codes = []
            for vertical in obj.verticals:
                if vertical.filter_by_state:
                    subdivision_codes = obj.certified_subdivision_codes
                    break
        else:
            subdivision_codes = obj.certified_subdivision_codes

        return subdivision_codes

    def get_certified_states(self, obj, context):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        if isinstance(obj, dict):
            return obj.get("certified_states", [])

        if obj.verticals:
            states = []
            for vertical in obj.verticals:
                if vertical.filter_by_state:
                    states = obj.certified_states
                    break
        else:
            states = obj.certified_states
        try:
            return [state.abbreviation.upper() for state in states]
        except Exception as e:
            log.exception(
                "failed in get_certified_states",
                exception=e,
                states=states,
            )
            raise e

    def get_can_prescribe(self, obj, context):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        if isinstance(obj, dict):
            return obj.get("can_prescribe", False)

        return ProviderService().provider_enabled_for_prescribing(obj)

    def get_can_prescribe_to_member(self, obj, context):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        if isinstance(obj, dict):
            return obj.get("can_prescribe_to_member", False)

        user = context.get("user")
        try:
            if not user or not user.member_profile:
                return False
        except Exception as e:
            #  this is a temporary shim to introspect more information about the error
            log.exception(
                "exception when resolving can_prescribe_to_member",
                exception=e,
                user=user,
                trace=format_exc(),
            )
            raise e

        return ProviderService().provider_can_prescribe_in_state(
            obj,
            user.member_profile.prescribable_state,
        )

    def get_vertical_objects(self, obj, context):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        if isinstance(obj, dict):
            return obj.get("vertical_objects", [])

        schema = V2VerticalSchema()
        return schema.dump(obj.verticals, many=True).data

    def get_care_team_type(self, obj, context):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        if context.get("care_team"):
            if isinstance(obj, dict):
                ct_type = context["care_team"].get(obj["user_id"])
            else:
                ct_type = context["care_team"].get(obj.user_id)

            if ct_type:
                return ct_type.pop()

    def get_faq_password(self, obj, context):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        return os.environ.get("HELPDOCS_PASSWORD")

    def get_country(self, obj, context):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        if isinstance(obj, dict):
            return obj.get("country")

        if obj.country and obj.country_code != "US":
            return CountrySchema().dump(obj.country).data

    def get_is_cx(self, obj):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        if isinstance(obj, dict):
            return obj.get("is_cx")

        return obj.user.is_care_coordinator

    def get_can_member_interact(self, obj) -> bool:  # type: ignore[no-untyped-def] # Function is missing a type annotation

        if not should_enable_can_member_interact():
            return True

        if isinstance(obj, dict):
            return obj.get("can_member_interact", True)

        user = self.context.get("user")
        if not user:
            log.info(
                "Missing user when trying to see if member can interact",
            )
            return False
        # if user has no tracks (marketplace) ensure experience is the same as pre-doula
        if not user.active_tracks:
            return True

        active_tracks = user.active_tracks
        all_modifiers = get_active_member_track_modifiers(user.active_tracks)
        client_track_ids = [track.client_track_id for track in active_tracks]

        # return true for all non doula-only members or if member has any track that is doula_only
        # and if provider has any vertical that is doula_only_accessible
        return ProviderService().provider_can_member_interact(
            provider=obj, modifiers=all_modifiers, client_track_ids=client_track_ids
        )


class UserProfilesSchema(MavenSchema):
    practitioner = fields.Method("get_practitioner_profile")
    member = fields.Method("get_member_profile")

    def get_member_profile(  # type: ignore[no-untyped-def] # Function is missing a type annotation for one or more arguments
        self,
        profiles: dict[str, MemberProfile],
        context: dict[str, Any],
        # Allows the underlying member profile schema to be overridden
        # enabling the trimming of unused fields when nested.
        profile_schema=MemberProfileSchema,
    ) -> dict[str, Any]:
        mp = profiles.get(ROLES.member)
        if not mp:
            return {}

        context_user_id = context["user"].id if context.get("user") else None
        mp_user_id = mp.user_id if not isinstance(mp, dict) else None

        # default
        schema = profile_schema(only=["color_hex"])

        # overwrite on special cases
        if context_user_id and mp_user_id and context_user_id == mp_user_id:
            schema = profile_schema()
        elif context.get("appointment"):
            appt = context["appointment"]
            if appt.is_anonymous:
                schema = profile_schema(
                    only=["tel_region", "tel_number", "phone_number", "color_hex"]
                )
            elif appt.practitioner == context.get("user"):
                schema = profile_schema()

        return schema.dump(mp).data

    def get_practitioner_profile(  # type: ignore[no-untyped-def] # Function is missing a return type annotation #type: ignore[no-untyped-def] # Function is missing a type annotation for one or more arguments
        self,
        profiles: dict[str, PractitionerProfile],
        context: dict[str, Any],
        # Allows the underlying practitioner profile schema to be overridden
        # enabling the trimming of unused fields when nested.
        profile_schema=PractitionerProfileSchema,
    ):
        if not profiles.get(ROLES.practitioner):
            return {}

        profile = profiles[ROLES.practitioner]
        if isinstance(profile, dict):
            user_id = profile.get("user_id")
        else:
            user_id = profile.user_id

        context_user_id = None
        context_user = context.get("user")
        if context_user:
            context_user_id = context_user.id

        if context_user_id != user_id:
            schema = profile_schema(exclude=_other_user_field_exclusions)
        else:
            schema = profile_schema()
        schema.context["care_team"] = context.get("care_team")
        schema.context["user"] = context_user
        return schema.dump(profile).data


MockOrg = namedtuple(
    "MockOrg", ["id", "name", "vertical_group_version", "bms_enabled", "rx_enabled"]
)


class CountrySchema(MavenSchema):
    name = fields.Method("get_name")
    abbr = fields.Method("get_abbr")
    ext_info_link = fields.Method("get_ext_info_link")
    summary = fields.Method("get_summary")

    @ddtrace.tracer.wrap(resource="country", service=SERVICE, span_type=SPAN_TYPE)
    def get_name(self, obj, context):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        return obj and obj.name

    @ddtrace.tracer.wrap(resource="country", service=SERVICE, span_type=SPAN_TYPE)
    def get_abbr(self, obj, context):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        return obj and obj.alpha_2

    @ddtrace.tracer.wrap(resource="country", service=SERVICE, span_type=SPAN_TYPE)
    def get_ext_info_link(self, obj, context):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        countries = CountryRepository()
        if country_metadata := countries.get_metadata(country_code=obj.alpha_2):
            return country_metadata.ext_info_link

    @ddtrace.tracer.wrap(resource="country", service=SERVICE, span_type=SPAN_TYPE)
    def get_summary(self, obj, context):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        countries = CountryRepository()
        if country_metadata := countries.get_metadata(country_code=obj.alpha_2):
            return country_metadata.summary


class UserSchema(MavenSchema):
    id = fields.Integer()
    encoded_id = fields.Method("get_encoded_id")
    esp_id = fields.Method("get_esp_id")
    test_group = fields.String()
    first_name = fields.String()
    middle_name = fields.String()
    last_name = fields.String()
    name = fields.Method("get_name")
    email = fields.Method("get_email")
    username = fields.Method("get_username")
    role = fields.Method("get_role")
    avatar_url = fields.String()
    image_url = fields.Method("get_image_url")
    image_id = fields.Integer()
    profiles = fields.Method("get_profiles")
    organization = fields.Method("get_organization")
    subscription_plans = fields.Method("get_subscription_plans")
    care_coordinators = fields.Nested("UserSchema", many=True, exclude=("created_at",))
    country = fields.Method("get_country_info")
    created_at = MavenDateTime()

    def get_role(self, user, context):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        if isinstance(user, dict):
            return user.get("role", "")
        return user.role_name or ""

    def get_esp_id(self, user, context):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        if context.get("include_esp_id"):
            return user.esp_id

    def get_encoded_id(self, user, context):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        if user:
            user_id = user["id"] if isinstance(user, dict) else user.id
            context_user_id = context.get("user_id", None)
            if context_user_id is None:
                context_user_id = context.get("user") and context.get("user").id
            if user_id == context_user_id:
                return security.new_user_id_encoded_token(user_id)

    def get_email(self, user, context):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        if not context.get("user"):
            return

        context_user_id = context.get("user").id
        if isinstance(user, dict):
            # we are getting from the cache
            if (
                context_user_id == user.get("id")
                or self.context["user"].is_care_coordinator
            ):
                return user.get("email")
        else:
            if context_user_id == user.id or self.context["user"].is_care_coordinator:
                return user.email

    def get_name(self, user, context):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        if isinstance(user, dict):
            # we are getting from the cache
            return user.get("name")
        else:
            return user.full_name

    def get_image_url(self, user, context):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        if isinstance(user, dict):
            # we are getting from the cache
            return user.get("image_url")
        else:
            return user.avatar_url

    def get_profiles(  # type: ignore[no-untyped-def] # Function is missing a type annotation for one or more arguments
        self,
        user: User,
        context: dict[str, Any],
        # Allows the underlying member profiles schema to be overridden
        # enabling the trimming of unused fields when nested.
        profiles_schema=UserProfilesSchema,
    ) -> dict[str, Any] | None:
        if context.get("include_profile"):
            allowed = {ROLES.member, ROLES.practitioner}

            if isinstance(user, dict):
                # we are getting from the cache
                profile_keys = user["profiles"].keys()
            else:
                profile_keys = user.user_types

            schema = profiles_schema(only=profile_keys & allowed)
            schema.context["care_team"] = context.get("care_team")

            if context.get("user"):
                schema.context["user"] = context["user"]
            if context.get("appointment"):
                schema.context["appointment"] = context["appointment"]

            if isinstance(user, dict):
                # we are getting from the cache
                profiles = user["profiles"]
            else:
                profiles = user.profiles_map

            return schema.dump(profiles).data

        return None

    def get_organization(self, user, context):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        if not user:
            return

        if isinstance(user, dict):
            user = db.session.query(User).filter(User.id == user["id"]).one()

        # TODO: [multitrack] Can a user belong in more than one organization if they
        #  have multiple tracks? Probably no, so it may be safe to use active_tracks[0]
        member_track = user.current_member_track
        if not member_track:
            return

        # if the user is in an active member_track - we already know they belong to
        # a valid organization - no need to check e9y again, just return the org they belong to
        org = member_track.organization

        return OrganizationSchema().dump(org).data

    def get_subscription_plans(self, user, context) -> None:  # type: ignore[no-untyped-def] # Function is missing a type annotation
        # deprecated plan payer functionality
        return

    def get_country_info(self, user, context):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        """
        n.b.: if `country` is null, then it is defaulted to "US" for display on certain clients.
        """
        if (
            context.get("include_country_info")
            and user
            and user.country_code
            and not user.country_code == "US"
        ):
            return CountrySchema().dump(user.country).data

    def get_username(self, user, context):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        if not context.get("user"):
            return

        context_user_id = context.get("user").id
        if isinstance(user, dict):
            # we are getting from the cache
            if context_user_id == user.get("id"):
                return user.get("username")
        else:
            if context_user_id == user.id:
                return user.username


class BenefitResourceSchema(MavenSchema):
    title = fields.String(nullable=True)
    url = fields.String(nullable=True)


class WalletSchema(MavenSchema):
    organization_setting_id = fields.String()
    wallet_id = fields.String(default=None)  # type: ignore[arg-type] # Argument "default" to "String" has incompatible type "None"; expected "str"
    survey_url = fields.String(nullable=True, default=None)  # type: ignore[arg-type] # Argument "default" to "String" has incompatible type "None"; expected "str"
    state = fields.String(default=None)  # type: ignore[arg-type] # Argument "default" to "String" has incompatible type "None"; expected "str"
    channel_id = fields.Integer(default=None)  # type: ignore[arg-type] # Argument "default" to "Integer" has incompatible type "None"; expected "int"
    benefit_overview_resource = fields.Nested(
        BenefitResourceSchema, nullable=True, default=None
    )
    benefit_faq_resource = fields.Nested(BenefitResourceSchema)


class WalletEntitledOrEnrolledSchema(MavenSchema):
    eligible = fields.Nested(
        WalletSchema,
        many=True,
        only=[
            "wallet_id",
            "organization_setting_id",
            "survey_url",
            "state",
            "benefit_overview_resource",
            "benefit_faq_resource",
        ],
    )
    enrolled = fields.Nested(
        WalletSchema,
        many=True,
        only=[
            "wallet_id",
            "channel_id",
            "state",
            "benefit_overview_resource",
            "benefit_faq_resource",
        ],
    )


class UserMeSchema(UserSchema):
    wallet = fields.Method("get_wallets")
    pending_agreements = fields.Method("get_pending_user_agreements")
    all_pending_agreements = fields.Method("get_all_pending_agreements")
    flags = fields.Method("get_flagr_flags")
    bright_jwt = fields.String()  # deprecated
    active_tracks = fields.Nested("UserMeActiveTrackSchema", many=True)
    inactive_tracks = fields.Nested("UserMeInactiveTrackSchema", many=True)
    scheduled_tracks = fields.Nested("UserMeScheduledTrackSchema", many=True)
    has_available_tracks = fields.Method("get_whether_tracks_are_available")
    onboarding_state = fields.Method("get_user_onboarding_state")
    unclaimed_invite = fields.Method("get_unclaimed_invite")
    use_alegeus_for_reimbursements = fields.Method("get_use_alegeus_for_reimbursements")

    mfa_state = fields.Function(
        lambda obj: obj.mfa_state.value
    )  # return "disabled" instead of "MFAState.DISABLED"
    sms_phone_number = fields.String()
    date_of_birth = fields.Method("get_date_of_birth")
    mfa_enforcement_info = fields.Method("get_mfa_enforcement_info")

    def get_wallets(self, user: User, context):  # type: ignore[no-untyped-def] # Function is missing a return type annotation #type: ignore[no-untyped-def] # Function is missing a type annotation for one or more arguments
        automated_survey_url = get_survey_url_from_wallet()
        eligible = []
        enrolled = []
        if "organization_settings" in context:
            for settings in context["organization_settings"]:
                eligible.append(
                    {
                        "wallet_id": settings["wallet_id"],
                        "organization_setting_id": settings["id"],
                        "survey_url": automated_survey_url,
                        "benefit_overview_resource": settings[
                            "benefit_overview_resource"
                        ]
                        and {
                            "title": settings["benefit_overview_resource"]["title"],
                            "url": settings["benefit_overview_resource"]["url"],
                        },
                        "benefit_faq_resource": {
                            "title": settings["benefit_faq_resource"]["title"],
                            "url": settings["benefit_faq_resource"]["url"],
                        },
                        "state": None,
                    }
                )

        wallets_rwu_status_and_channels = (
            db.session.query(
                ReimbursementWallet,
                ReimbursementWalletUsers.status,
                ReimbursementWalletUsers.channel_id,
            )
            .join(
                ReimbursementWalletUsers,
                ReimbursementWalletUsers.reimbursement_wallet_id
                == ReimbursementWallet.id,
            )
            .filter(
                ReimbursementWalletUsers.user_id == user.id,
            )
            .all()
        )

        for wallet, status, channel_id in wallets_rwu_status_and_channels:
            is_denied_user: bool = status == WalletUserStatus.DENIED
            # TODO: how to handle expired wallets?
            if wallet.is_enrolled and not is_denied_user:
                enrolled.append(self.build_wallet(wallet, user, channel_id))
            elif wallet.is_disqualified or is_denied_user:
                eligible.append(self.build_wallet(wallet, user, channel_id))
        schema = WalletEntitledOrEnrolledSchema()
        return schema.dump({"eligible": eligible, "enrolled": enrolled}).data

    def build_wallet(
        self,
        wallet: ReimbursementWallet,
        user: User,
        channel_id: int | None,
    ) -> dict:
        return {
            "wallet_id": wallet.id,
            "channel_id": channel_id,
            "organization_setting_id": wallet.reimbursement_organization_settings_id,
            "survey_url": get_survey_url_from_wallet(),
            "state": get_wallet_state(wallet, user),
            "benefit_overview_resource": wallet.reimbursement_organization_settings.benefit_overview_resource
            and {
                "title": wallet.reimbursement_organization_settings.benefit_overview_resource.title,
                "url": wallet.reimbursement_organization_settings.benefit_overview_resource.custom_url,
            },
            "benefit_faq_resource": {
                "title": wallet.reimbursement_organization_settings.benefit_faq_resource.title,
                "url": wallet.reimbursement_organization_settings.benefit_faq_resource.content_url,
            },
        }

    def get_all_pending_agreements(self, user, context):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        """
        Get a list of info about the pending agreements for the User,
        including those that are specific to that User's organization.
        An agreement is pending if we do not have a corresponding AgreementAcceptance.
        @return: the name, display_name, and version of the agreements
        organized into Organization- and User-specific categories
        """
        return {
            "organization": self.get_pending_organization_agreements(user, context),
            "user": self.get_pending_user_agreements(user, context),
        }

    def get_pending_organization_agreements(self, user, context):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        """
        Get a list of info about the pending agreements for the User that are specific to that User's organization.
        An agreement is pending if we do not have a corresponding AgreementAcceptance.
        @return: list of dictionaries containing the name, display_name, and version of the agreement
        """
        verification_svc: eligibility.EnterpriseVerificationService = (
            eligibility.get_verification_service()
        )
        organization_ids = verification_svc.get_eligible_organization_ids_for_user(
            user_id=user.id
        )
        return [
            {
                "name": pending_agreement.name.value,
                "display_name": pending_agreement.display_name,
                "version": pending_agreement.version,
                "optional": pending_agreement.optional,
            }
            for pending_agreement in user.get_pending_organization_agreements(
                organization_ids
            )
        ]

    def get_pending_user_agreements(self, user, context):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        """
        Get a list of info about the pending agreements for the User that are not specific to that User's organization.
        An agreement is pending if we do not have a corresponding AgreementAcceptance.
        @return: list of dictionaries containing the name, display_name, and version of the agreement
        """
        return [
            {
                "name": pending_agreement.name.value,
                "display_name": pending_agreement.display_name,
                "version": pending_agreement.version,
                "optional": pending_agreement.optional,
            }
            for pending_agreement in user.pending_user_agreements
        ]

    def get_flagr_flags(self, user, context):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        return flagr.me_stubs()

    def get_whether_tracks_are_available(self, user, context):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        """
        This is deprecated.

        The field is no longer relevant to clients,
        but must remain to not break the expected response
        """
        return False

    def get_use_alegeus_for_reimbursements(self, user):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        return use_alegeus_for_reimbursements()

    def get_user_onboarding_state(self, user, context):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        if user.onboarding_state:
            return user.onboarding_state.state.value
        return None

    def get_unclaimed_invite(self, user, context):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        invite = (
            Invite.query.filter(
                Invite.created_by_user_id == user.id, Invite.claimed.is_(False)
            )
            .order_by(Invite.created_at.desc())
            .first()
        )
        if invite:
            return {
                "invite_id": invite.id,
                "type": invite.type.value,
                "email": invite.email,
            }
        return None

    def get_date_of_birth(self, user, context):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        if user.health_profile and user.health_profile.birthday:
            return user.health_profile.birthday.isoformat()
        return None

    def get_mfa_enforcement_info(self, user):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        (require_mfa, mfa_enforcement_reason) = MFAService().get_user_mfa_status(
            user_id=user.id
        )
        return {
            "require_mfa": require_mfa,
            "mfa_enforcement_reason": mfa_enforcement_reason.name,
        }


def get_wallet_state(
    wallet: ReimbursementWallet, user: ReimbursementWalletUsers
) -> Optional[str]:
    wallet_user_status = (
        db.session.query(ReimbursementWalletUsers.status).filter(
            ReimbursementWalletUsers.user_id == user.id,
            ReimbursementWalletUsers.reimbursement_wallet_id == wallet.id,
        )
    ).scalar()

    if wallet_user_status:
        # For PENDING wallet user status, allow PENDING wallet experience
        if wallet_user_status == WalletUserStatus.PENDING:
            return WalletState.PENDING.value
        elif wallet_user_status == WalletUserStatus.DENIED:
            # TODO confirm that we want to display DISQUALIFIED wallet view for Denied Users
            # For DENIED wallet user status, allow DISQUALIFIED wallet experience
            return WalletState.DISQUALIFIED.value

    # For ACTIVE wallet user status, fallback to wallet state
    return wallet.state.value  # type: ignore[attr-defined] # "str" has no attribute "value"


def get_survey_url_from_wallet() -> str:
    """Returns the survey_url for a wallet application."""
    base_url: str = current_app.config["BASE_URL"].rstrip("/")
    return f"{base_url}/app/wallet/apply"


class UserMeTrackSchema(MavenSchema):
    id = fields.Integer()
    name = fields.String()
    display_name = fields.String()
    scheduled_end = fields.Method("get_scheduled_end")

    def get_scheduled_end(self, track):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        return track.get_display_scheduled_end_date().isoformat()


class UserMeInactiveTrackSchema(UserMeTrackSchema):
    ended_at = fields.Method("get_ended_at")

    def get_ended_at(self, track):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        if track.ended_at:
            return track.ended_at.isoformat()
        return None


class UserMeScheduledTrackSchema(UserMeTrackSchema):
    start_date = fields.Method("get_start_date")

    def get_start_date(self, track):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        if track.start_date:
            return track.start_date.isoformat()
        return None


class UserMeActiveTrackSchema(UserMeTrackSchema):
    current_phase = fields.Method("get_current_phase")
    dashboard = fields.Method("get_dashboard")
    onboarding_assessment_id = fields.Method("get_onboarding_assessment_id")
    onboarding_assessment_slug = fields.Method("get_onboarding_assessment_slug")

    def get_current_phase(self, track):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        return track.current_phase.name

    def get_dashboard(self, track):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        return track.dashboard

    def get_onboarding_assessment_id(self, track):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        lifecycle = track.onboarding_assessment_lifecycle
        return (
            lifecycle and lifecycle.latest_assessment and lifecycle.latest_assessment.id
        )

    def get_onboarding_assessment_slug(self, track):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        # We use the slug for Contentful/HDC assessments. We use the id for legacy assessments.
        return track.onboarding_assessment_slug


class ProductSchema(Schema):
    id = fields.Integer()
    minutes = fields.Integer()
    price = fields.Decimal(as_string=True)
    practitioner = fields.Nested(
        UserSchema(context={"include_profile": True}, exclude=("created_at",))
    )
    vertical_id = fields.Integer()


@ddtrace.tracer.wrap(span_type=SPAN_TYPE)
def format_json_as_error(status, code, message, data=None, field=None):  # type: ignore[no-untyped-def] # Function is missing a type annotation
    # TODO: Refactor to only use the IETF RFC-7807 fields, instead of RFC+duplicate legacy fields
    problem = Problem(status=status, code=code, detail=message, message=message)
    error = problem.to_dict()
    if field:
        error["field"] = field
    return ({"data": data, "errors": [error]}, status)


@ddtrace.tracer.wrap(span_type=SPAN_TYPE)
def from_unmarshalling_error(e):  # type: ignore[no-untyped-def] # Function is missing a type annotation
    # TODO: Refactor to only use the IETF RFC-7807 fields, instead of RFC+duplicate legacy fields
    message = str(e).lstrip("['").rstrip("']")
    problem = Problem(
        status=400,
        message=message,
        detail=message,
        field=e.field_name,
        code="BAD_REQUEST",
    )
    return ({"data": None, "errors": [problem.to_dict()]}, 400)


@ddtrace.tracer.wrap(span_type=SPAN_TYPE)
def from_validation_error(e, many=False):  # type: ignore[no-untyped-def] # Function is missing a type annotation
    errors = []

    @ddtrace.tracer.wrap(span_type=SPAN_TYPE)
    def collect_field_errors(data_errors, field_prefix=""):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        if isinstance(data_errors, dict):
            for field_name, field_errors in data_errors.items():
                for message in field_errors:
                    # TODO: Refactor to only use the IETF RFC-7807 fields, instead of RFC+duplicate legacy fields
                    problem = Problem(
                        status=400,
                        message=message,
                        detail=message,
                        field=f"{field_prefix}{field_name}",
                        code="BAD_REQUEST",
                    )
                    errors.append(problem.to_dict())

    if many:
        for data_index, data_errors in e.normalized_messages().items():
            collect_field_errors(data_errors, f"{data_index}: ")
    else:
        collect_field_errors(e.normalized_messages())

    return {"data": None, "errors": errors}, 400


class RestrictedField(fields.Field):
    """
    Calls the parent's function `_restricted` and if it returns true, returns the default for the field otherwise deferrs serialization to the parent class
    """

    @ddtrace.tracer.wrap(
        resource="restricted_field", service=SERVICE, span_type=SPAN_TYPE
    )
    def serialize(self, attr, obj, accessor=None):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        if self.parent._restricted(attr, obj):
            return self.default
        return super().serialize(attr, obj, accessor)


class RestrictedString(fields.String, RestrictedField):
    pass


class RestrictedNested(fields.Nested, RestrictedField):
    pass


class RestrictableMavenSchema(MavenSchema):
    """
    Enforces the implementation of `_restricted` function that returns whether or not to apply restrictions to any `RestrictedField` impmenentations
    """

    def _restricted(self, attr, obj) -> bool:  # type: ignore[no-untyped-def] # Function is missing a type annotation for one or more arguments
        raise NotImplementedError("Must implement _restricted method")


class RestrictedUSOrganizationSchema(RestrictableMavenSchema):
    is_restricted = fields.Method("_is_restricted")
    organization = RestrictedNested(
        OrganizationSchema, only=("name", "US_restricted"), default=None
    )

    @ddtrace.tracer.wrap(
        resource="restricted_us_organization",
        service=SERVICE,
        span_type=SPAN_TYPE,
    )
    def _restricted(self, attr, obj):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        """
        If the current user is not in the US and the member's company has a US-only policy, restrict access to data
        """
        if hasattr(obj, "organization") and (obj.organization, "US_restricted"):
            return bool(
                obj.organization
                and obj.organization.US_restricted
                and (
                    not self.context["user"].country_code
                    or self.context["user"].country_code != "US"
                )
            )
        else:
            return None

    def _is_restricted(self, obj, context):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        return self._restricted("is_restricted", obj)
