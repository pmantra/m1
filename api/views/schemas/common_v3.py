from __future__ import annotations

import datetime
from typing import Optional

import ddtrace
import phonenumbers
from marshmallow import Schema, ValidationError, fields

from geography.repository import CountryRepository
from utils.data import normalize_phone_number_old
from utils.log import logger
from views.schemas.base import NestedWithDefaultV3  # noqa: F401
from views.schemas.base import (
    BooleanWithDefault,
    DecimalWithDefaultV3,
    IntegerWithDefaultV3,
    MavenSchemaV3,
    SchemaV3,
    StringWithDefaultV3,
    UserSchemaV3,
)
from views.schemas.common import (
    SPAN_TYPE,
    USAStateStringFieldAllowNone,
    get_normalized,
    validate_address,
    validate_limit,
    validate_offset,
    validate_phone_number,
    validate_subdivision,
)

log = logger(__name__)

TRUTHY = frozenset((True, "true", "True", "TRUE", 1, "1"))
FALSY = frozenset((False, "false", "False", "FALSE", 0, "0", None, "None"))
SERVICE: str = "marshmallow"


# adding this to prevent circular imports
def validate_practitioner_order(value):  # type: ignore[no-untyped-def] # Function is missing a type annotation
    if value == "next_availability":
        return value
    else:
        raise ValidationError("Invalid practitioner order_by!")


class MavenDateTime(fields.DateTime):
    def _deserialize(self, value, attr, data, **kwargs):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        try:
            value = super()._deserialize(value, attr, data, **kwargs)
            if value.tzinfo is not None:
                raise ValidationError(
                    "Please send a datetime without a timezone offset!", self.name  # type: ignore[arg-type] # Argument 2 to "ValidationError" has incompatible type "None"; expected "str"
                )
            return value.replace(microsecond=0)
        except ValidationError:
            # check if we need to validate a date instead
            date_value = fields.Date()._deserialize(value, attr, data, **kwargs)
            return date_value

    def _serialize(self, value, attr, obj, **kwargs):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        if isinstance(value, datetime.datetime):
            value = value.replace(tzinfo=None, microsecond=0)
            return value.isoformat()
        elif isinstance(value, datetime.date):
            return value.isoformat()
        else:
            # cached values are already processed
            return value


class ImageSchemaMixin:
    image = fields.Method("get_image_info")

    def get_image_info(self, obj):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        if obj.image:
            urls = {
                "original": obj.image.asset_url(None, None),
                "hero": obj.image.asset_url(428, 760, smart=False),
                "thumbnail": obj.image.asset_url(90, 120, smart=False),
            }
            for image_size in self.context.get("image_sizes", []):  # type: ignore[attr-defined] # "ImageSchemaMixin" has no attribute "context"
                urls[image_size] = obj.image.asset_url(
                    *reversed(image_size.split("x")), smart=False
                )
            return urls


class V3BooleanField(fields.Boolean):
    truthy = TRUTHY  # type: ignore[assignment] # Incompatible types in assignment (expression has type "FrozenSet[object]", base class "Boolean" defined the type as "Set[object]")
    falsy = FALSY  # type: ignore[assignment] # Incompatible types in assignment (expression has type "FrozenSet[object]", base class "Boolean" defined the type as "Set[object]")


class V3AddressSchema(Schema):
    __validators__ = [validate_address]
    street_address = fields.String(required=True)
    zip_code = fields.String(required=True)
    city = fields.String(required=True)
    state = fields.String(required=True)
    country = fields.String(required=True)


class V3PhoneNumber(fields.String):
    @ddtrace.tracer.wrap(
        resource="phone_number_field", service=SERVICE, span_type=SPAN_TYPE
    )
    def _serialize(self, value, attr, obj):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        _, num = get_normalized(obj)
        return normalize_phone_number_old(num, include_extension=True)


class V3TelRegion(fields.String):
    # Determine region from phone number
    def serialize(self, attr, obj, accessor=None, **kwargs):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        _, num = get_normalized(obj)
        if num is None:
            return None
        return phonenumbers.region_code_for_number(num)


class V3TelNumber(fields.String):
    # Take the normalized form straight from the phone_number being serialized.
    def serialize(self, attr, obj, accessor=None, **kwargs):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        tel_number, _ = get_normalized(obj)
        return tel_number


class OrderDirectionField(fields.Field):
    def _deserialize(self, value, attr, obj, **kwargs):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        if value is None:
            value = self.default

        value = value.lower()
        if value not in ("asc", "desc"):
            raise ValidationError(
                f"Order direction '{value}' is not a valid order direction"
            )

        return value

    def _serialize(self, value, attr, obj, **kwargs):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        if value is None:
            value = self.default

        value = value.lower()
        if value not in ("asc", "desc"):
            raise ValidationError(
                f"Order direction '{value}' is not a valid order direction"
            )

        return value


class CSVIntegerField(fields.Field):
    def _deserialize(self, value, attr, obj, **kwargs):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        if not value:
            return []

        int_list = []

        for i in value.split(","):
            try:
                int_list.append(int(i))
            except ValueError:
                raise ValidationError(f"Value '{i}' is not a valid integer")

        return int_list

    def _serialize(self, value, attr, obj, **kwargs):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        try:
            if value:
                return [int(i) for i in value]
            else:
                return None
        except ValueError:
            raise ValidationError(f"Value '{value}' is not a valid integer")


class PrivacyOptionsField(fields.Field):
    @ddtrace.tracer.wrap(
        resource="privacy_option_field", service=SERVICE, span_type=SPAN_TYPE
    )
    def _deserialize(self, value, attr, obj, **kwargs):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        allowed = ["anonymous", "basic", "full_access"]
        if value is None or (value and value.lower() in allowed):
            return value
        raise ValidationError(f"{value} not an allowed privacy choice!")


class CSVStringField(fields.Field):
    def __init__(self, max_size: Optional[int] = None, **kwargs):  # type: ignore[no-untyped-def] # Function is missing a type annotation for one or more arguments
        self.__max_size = max_size
        super().__init__(**kwargs)

    def _deserialize(self, value, attr, obj, **kwargs):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        str_list = []
        split_value = value.split(",")

        if self.__max_size and len(split_value) > self.__max_size:
            raise ValidationError(
                f"{attr} must have between 1 and {self.__max_size} values, inclusive."
            )

        for i in value.split(","):
            try:
                str_list.append(str(i))
            except ValueError:
                raise ValidationError("%s not a valid value!", i)

        return str_list

    def _serialize(self, value, attr, obj, **kwargs):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        if not value:
            return None
        return ",".join(str(s) for s in value)


@ddtrace.tracer.wrap(span_type=SPAN_TYPE)
def validate_image_sizes(values):  # type: ignore[no-untyped-def] # Function is missing a type annotation
    for value in values:
        parts = value.split("x")
        if len(parts) != 2:
            raise ValidationError("Invalid image size")
        try:
            width, height = int(parts[0]), int(parts[1])
        except ValueError:
            raise ValidationError("Invalid image size")
        if width < 1 or height < 1:
            raise ValidationError("Invalid image size")


class ImageSizesMixin:
    image_sizes = CSVStringField(validate=validate_image_sizes)


class PaginableArgsSchemaV3(MavenSchemaV3):
    offset = IntegerWithDefaultV3(
        dump_default=0,
        load_default=0,
        required=False,
        validate=validate_offset,
        default=0,
    )
    limit = IntegerWithDefaultV3(
        dump_default=10,
        load_default=10,
        required=False,
        validate=validate_limit,
        default=10,
    )
    order_direction = OrderDirectionField(
        dump_default="desc", load_default="desc", required=False
    )


class PaginationInfoSchemaV3(PaginableArgsSchemaV3):
    total = IntegerWithDefaultV3(required=False, default=0)


class PaginableOutputSchemaV3(MavenSchemaV3):
    pagination = fields.Nested(PaginationInfoSchemaV3)
    meta = fields.Raw()
    data = fields.Raw()


class PractitionerGetSchema(PaginableArgsSchemaV3):
    user_ids = CSVIntegerField(required=False)
    verticals = CSVStringField(required=False)
    vertical_ids = CSVIntegerField(required=False)
    specialties = CSVStringField(required=False)
    specialty_ids = CSVIntegerField(required=False)
    needs = CSVStringField(required=False)
    need_ids = CSVIntegerField(required=False)
    can_prescribe = fields.Boolean(required=False)
    product_minutes = fields.Integer(required=False)
    only_free = fields.Boolean(required=False)
    available_in_next_hours = fields.Integer(required=False)
    availability_scope_in_days = fields.Integer(required=False)
    bypass_availability = fields.Boolean(required=False)

    order_by = fields.String(
        validate=validate_practitioner_order,
        default="next_availability",
        required=False,
    )
    type = fields.String(required=False)

    limit = IntegerWithDefaultV3(default=20, required=False)


class OrganizationEmployeeDataSchema(MavenSchemaV3):
    employee_first_name = fields.String(dump_default="", load_default="")
    employee_last_name = fields.String(dump_default="", load_default="")
    address_1 = fields.String(dump_default="", load_default="")
    address_2 = fields.String(dump_default="", load_default="")
    city = fields.String(dump_default="", load_default="")
    state = fields.String(dump_default="", load_default="")
    zip_code = fields.String(dump_default="", load_default="")
    country = fields.String(dump_default="", load_default="")


class SessionMetaInfoSchemaV3(MavenSchemaV3):
    notes = StringWithDefaultV3(dump_default="", load_default="")
    created_at = MavenDateTime()
    modified_at = MavenDateTime()
    draft = fields.Boolean(default=None)


class AddressSchemaV3(MavenSchemaV3):
    __validators__ = [validate_address]
    street_address = StringWithDefaultV3(required=True, default="")
    zip_code = StringWithDefaultV3(required=True, default="")
    city = StringWithDefaultV3(required=True, default="")
    state = StringWithDefaultV3(required=True, default="")
    country = StringWithDefaultV3(required=True, default="")


class AgreementsSchemaV3(MavenSchemaV3):
    subscription = BooleanWithDefault(default=False)


class CountrySchemaV3(MavenSchemaV3):
    name = fields.Method("get_name")
    abbr = fields.Method("get_abbr")
    ext_info_link = fields.Method("get_ext_info_link")
    summary = fields.Method("get_summary")

    @ddtrace.tracer.wrap(resource="country", service=SERVICE, span_type=SPAN_TYPE)
    def get_name(self, obj):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        if hasattr(obj, "name"):
            return obj and obj.name
        return None

    @ddtrace.tracer.wrap(resource="country", service=SERVICE, span_type=SPAN_TYPE)
    def get_abbr(self, obj):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        if hasattr(obj, "alpha_2"):
            return obj and obj.alpha_2
        return None

    @ddtrace.tracer.wrap(resource="country", service=SERVICE, span_type=SPAN_TYPE)
    def get_ext_info_link(self, obj):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        if hasattr(obj, "alpha2"):
            countries = CountryRepository()
            if country_metadata := countries.get_metadata(country_code=obj.alpha_2):
                return country_metadata.ext_info_link

    @ddtrace.tracer.wrap(resource="country", service=SERVICE, span_type=SPAN_TYPE)
    def get_summary(self, obj):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        if hasattr(obj, "alpha2"):
            countries = CountryRepository()
            if country_metadata := countries.get_metadata(country_code=obj.alpha_2):
                return country_metadata.summary


class MemberProfileSchemaV3(MavenSchemaV3):
    __validators__ = [validate_phone_number(required=False), validate_subdivision()]
    state = USAStateStringFieldAllowNone()
    country = fields.Method("get_country")
    phone_number = V3PhoneNumber()
    tel_region = V3TelRegion()
    tel_number = V3TelNumber()
    address = fields.Nested(AddressSchemaV3)
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


class OrganizationSchemaV3(MavenSchemaV3):
    id = IntegerWithDefaultV3(default=0)
    name = StringWithDefaultV3(default="")
    vertical_group_version = StringWithDefaultV3(default="")
    bms_enabled = fields.Boolean()
    rx_enabled = fields.Boolean()
    education_only = fields.Boolean()
    display_name = StringWithDefaultV3(default="")
    benefits_url = StringWithDefaultV3(default=None)
    US_restricted = fields.String(required=False)


class ProductSchemaV3(SchemaV3):
    id = IntegerWithDefaultV3(default=0)
    minutes = IntegerWithDefaultV3(default=0)
    price = DecimalWithDefaultV3(as_string=True, default="0")
    practitioner = fields.Nested(
        UserSchemaV3(context={"include_profile": True}, exclude=("created_at",))
    )
    vertical_id = IntegerWithDefaultV3(default=0)


class VideoSchemaV3(SchemaV3):
    session_id = StringWithDefaultV3(default="")
    member_token = StringWithDefaultV3(default="")
    practitioner_token = StringWithDefaultV3(default="")


class BooleanField(fields.Boolean):
    truthy = {True, "true", "True", "TRUE", 1, "1"}  # noqa: B033
    falsy = {False, "false", "False", "FALSE", 0, "0", None, "None"}  # noqa: B033


class DoseSpotPharmacySchemaV3(MavenSchemaV3):
    # Note: Based on iOS field expectations
    PharmacyId = StringWithDefaultV3(dump_default="", load_default="")
    Pharmacy = StringWithDefaultV3(dump_default="", load_default="")
    State = StringWithDefaultV3(dump_default="", load_default="")
    ZipCode = StringWithDefaultV3(dump_default="", load_default="")
    PrimaryFax = StringWithDefaultV3(dump_default="", load_default="")
    StoreName = StringWithDefaultV3(dump_default="", load_default="")
    Address1 = StringWithDefaultV3(dump_default="", load_default="")
    Address2 = StringWithDefaultV3(dump_default="", load_default="")
    PrimaryPhone = StringWithDefaultV3(dump_default="", load_default="")
    PrimaryPhoneType = StringWithDefaultV3(dump_default="", load_default="")
    City = StringWithDefaultV3(dump_default="", load_default="")
    IsPreferred = fields.Boolean(dump_default=False, load_default=False)
    IsDefault = fields.Boolean(dump_default=False, load_default=False)
    ServiceLevel = IntegerWithDefaultV3(dump_default=0, load_default=0)


class RestrictedFieldV3(fields.Field):
    """
    Calls the parent's function `_restricted` and if it returns true, returns the default for the field otherwise deferrs serialization to the parent class
    """

    @ddtrace.tracer.wrap(
        resource="restricted_field", service=SERVICE, span_type=SPAN_TYPE
    )
    def serialize(self, attr, obj, accessor=None):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        if self.parent._restricted(attr, obj):  # type: ignore[attr-defined]
            return self.default
        return super().serialize(attr, obj, accessor)


class RestrictedStringV3(fields.String, RestrictedFieldV3):
    pass


class RestrictedNestedV3(fields.Nested, RestrictedFieldV3):
    pass


class RestrictableMavenSchemaV3(MavenSchemaV3):
    """
    Enforces the implementation of `_restricted` function that returns whether or not to apply restrictions to any `RestrictedField` impmenentations
    """

    def _restricted(self, attr, obj) -> bool:  # type: ignore[no-untyped-def] # Function is missing a type annotation for one or more arguments
        raise NotImplementedError("Must implement _restricted method")


class RestrictedUSOrganizationSchemaV3(RestrictableMavenSchemaV3):
    is_restricted = fields.Method("_is_restricted")
    organization = RestrictedNestedV3(
        OrganizationSchemaV3, only=("name", "US_restricted"), default=None
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

    def _is_restricted(self, obj):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        return self._restricted("is_restricted", obj)
