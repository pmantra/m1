from __future__ import annotations

import dataclasses
import datetime
import os
from traceback import format_exc

import ddtrace
import phonenumbers
from marshmallow import (
    Schema,
    ValidationError,
    fields,
    pre_dump,
    pre_load,
    validate,
    validates_schema,
)
from marshmallow.utils import EXCLUDE
from marshmallow.utils import _iso8601_datetime_re as ISO_DATEFORMAT
from sqlalchemy.orm.exc import NoResultFound

from appointments.models.cancellation_policy import CancellationPolicy
from authn.models.user import User
from authz.models.roles import ROLES
from geography import CountryRepository, SubdivisionRepository
from models.profiles import (
    Category,
    Certification,
    Language,
    PractitionerProfile,
    State,
)
from models.verticals_and_specialties import Specialty, Vertical, is_cx_vertical_name
from providers.service.provider import ProviderService
from storage.connection import db
from tracks.utils.common import get_active_member_track_modifiers
from utils import security
from utils.data import normalize_phone_number, normalize_phone_number_old
from utils.log import logger
from views.schemas.common import (
    _other_user_field_exclusions,
    get_normalized,
    should_enable_can_member_interact,
)

log = logger(__name__)

SERVICE: str = "marshmallow"
SPAN_TYPE: str = "web"


# ============================ Fields definition =======================================
class MavenDateTimeV3(fields.NaiveDateTime):
    @ddtrace.tracer.wrap(
        resource="maven_date_time", service=SERVICE, span_type=SPAN_TYPE
    )
    def _deserialize(self, value, attr, data, **kwargs):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        # N.B Marshmallow v3 has removed the dependency on python-dateutil doing string parsing
        # instead, it's adopting django isoformat regex check.
        # Since our request datetime could be in `YYYY-MM-DD` but missing the `Thh:mm:ss` format, here
        # we expand to the full format
        if not ISO_DATEFORMAT.match(value):
            try:
                value = datetime.datetime.strptime(value, "%Y-%m-%d").isoformat()
            except ValueError:
                raise ValidationError(f"Invalid date time with {value}")

        value = super()._deserialize(value, attr, data, **kwargs)
        return value.replace(microsecond=0)

    @ddtrace.tracer.wrap(
        resource="maven_date_time", service=SERVICE, span_type=SPAN_TYPE
    )
    def _serialize(self, value, attr, obj, **kwargs):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        if isinstance(value, datetime.datetime):
            value = value.replace(tzinfo=None, microsecond=0)
        return super()._serialize(value, attr, obj, **kwargs)


class DataTimeWithDefaultV3(fields.DateTime):
    def _serialize(self, value, attr, obj, **kwargs):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        """override to keep v1 behavior"""
        if value is None:
            return None
        result = super()._serialize(value, attr, obj, **kwargs)
        dt = datetime.datetime.fromisoformat(result)
        return dt.astimezone(datetime.timezone.utc).isoformat()


class StringWithDefaultV3(fields.String):
    """
    This is purely for backwards compatibility with v1. Since the change for
    https://github.com/marshmallow-code/marshmallow/issues/199 merged, the default value has changed for fields
    like String, Integer.
    Although Field provide dump_default parameter for pass-in default value, it won't work with sqlalchemy model
    attributes value is None (get_value return None instead of missing_ which is used for check later to use
    load_default)
    """

    def _serialize(self, value, attr, obj, **kwargs):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        if value is None:
            return self.default
        return super()._serialize(value, attr, obj, **kwargs)


class IntegerWithDefaultV3(fields.Integer):
    def _serialize(self, value, attr, obj, **kwargs):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        if value is None:
            return self.default
        return super()._serialize(value, attr, obj, **kwargs)


class DecimalWithDefaultV3(fields.Decimal):
    def _serialize(self, value, attr, obj, **kwargs):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        if value is None:
            return self.default
        return super()._serialize(value, attr, obj, **kwargs)


class RawWithDefaultV3(fields.Raw):
    def _serialize(self, value, attr, obj, **kwargs):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        if value is None:
            return self.default
        return super()._serialize(value, attr, obj, **kwargs)


class FloatWithDefaultV3(fields.Float):
    def _serialize(self, value, attr, obj, **kwargs):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        if value is None:
            return str(self.default) if self.as_string else self.default
        return super()._serialize(value, attr, obj, **kwargs)


class DecimalWithDefault(fields.Decimal):
    def _serialize(self, value, attr, obj, **kwargs):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        if value is None:
            return str(self.default) if self.as_string else self.default
        return super()._serialize(value, attr, obj, **kwargs)


class PhoneNumberV3(fields.String):
    def _serialize(self, value, attr, obj, **kwarg):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        _, num = get_normalized(obj)
        return normalize_phone_number_old(num, include_extension=True)


class TelNumberV3(fields.String):
    def serialize(self, attr, obj, accessor=None, **kwargs):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        tel_number, _ = get_normalized(obj)
        return tel_number


class TelRegionV3(fields.String):
    def serialize(self, attr, obj, accessor=None, **kwargs):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        _, num = get_normalized(obj)
        if num is None:
            return None
        return phonenumbers.region_code_for_number(num)


class BooleanWithDefault(fields.Boolean):
    truthy = {True, "true", "True", "TRUE", 1, "1"}  # noqa: B033
    falsy = {False, "false", "False", "FALSE", 0, "0", None, "None"}  # noqa: B033

    def _serialize(self, value, attr, obj, **kwargs):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        if value is None:
            return self.default
        return super()._serialize(value, attr, obj, **kwargs)


class ListWithDefaultV3(fields.List):
    """
    A custom field used to achieve backwards compatibility with fields.List() in marshmallow V1
    """

    def _serialize(self, value, attr, obj, **kwargs):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        if value is None:
            return self.default
        return super()._serialize(value, attr, obj, **kwargs)


class NestedWithDefaultV3(fields.Nested):
    """
    A custom field used to achieve backwards compatibility with fields.Nested(many=True) in marshmallow V1
    """

    def serialize(self, attr, obj, accessor=None, **kwargs):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        value = super().serialize(attr, obj, accessor, **kwargs)
        if value is None:
            return self.dump_default  # type: ignore[attr-defined] # "NestedWithDefaultV3" has no attribute "dump_default"
        return value


class _AttrStringV3(fields.Field):
    cls = None
    array_attr = "id"
    capitalization = "upper"
    allow_none = False
    allow_blank = False

    def _deserialize(self, value, attr, data, **kwargs):  # type: ignore[no-untyped-def] # Function is missing a type annotation
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

    def _serialize(self, value, attr, obj, **kwargs):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        if value:
            return getattr(value, self.array_attr)


class _ArrayofAttrV3(fields.Field):
    cls = None
    array_attr = "id"
    capitalization = "upper"

    def _deserialize(self, value, attr, data, **kwargs):  # type: ignore[no-untyped-def] # Function is missing a type annotation
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

    def _serialize(self, value, attr, obj, **kwargs):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        # N.B. This is for backwards compatibility with both serialize sqlalchemy objects and JSON objects
        # return value here for cases that value == [] and value == None
        if not value:
            return value

        ret = []
        for _ in value:
            # cached values are already processed
            if isinstance(_, str):
                ret.append(_)
            else:
                ret.append(getattr(_, self.array_attr))

        return ret


class ArrayofNamesV3(_ArrayofAttrV3):
    array_attr = "name"
    capitalization = None  # type: ignore[assignment] # Incompatible types in assignment (expression has type "None", base class "_ArrayofAttrV3" defined the type as "str")


class AllowedCertificationsV3(ArrayofNamesV3):
    cls = Certification  # type: ignore[assignment] # Incompatible types in assignment (expression has type "Type[Certification]", base class "_ArrayofAttrV3" defined the type as "None")


class AllowedCategoriesV3(ArrayofNamesV3):
    cls = Category  # type: ignore[assignment] # Incompatible types in assignment (expression has type "Type[Category]", base class "_ArrayofAttrV3" defined the type as "None")


class AllowedSpecialtiesV3(ArrayofNamesV3):
    cls = Specialty  # type: ignore[assignment] # Incompatible types in assignment (expression has type "Type[Specialty]", base class "_ArrayofAttrV3" defined the type as "None")


class AllowedVerticalsV3(ArrayofNamesV3):
    cls = Vertical  # type: ignore[assignment] # Incompatible types in assignment (expression has type "Type[Vertical]", base class "_ArrayofAttrV3" defined the type as "None")
    array_attr = "marketing_name"


class AllowedLanguagesV3(ArrayofNamesV3):
    cls = Language  # type: ignore[assignment] # Incompatible types in assignment (expression has type "Type[Language]", base class "_ArrayofAttrV3" defined the type as "None")


class USAStatesListFieldV3(_ArrayofAttrV3):
    cls = State  # type: ignore[assignment] # Incompatible types in assignment (expression has type "Type[State]", base class "_ArrayofAttrV3" defined the type as "None")
    array_attr = "abbreviation"
    capitalization = "upper"


class USAStateStringFieldV3(_AttrStringV3):
    cls = State  # type: ignore[assignment] # Incompatible types in assignment (expression has type "Type[State]", base class "_AttrStringV3" defined the type as "None")
    array_attr = "abbreviation"
    capitalization = "upper"


class USAStateStringFieldAllowNoneV3(USAStateStringFieldV3):
    allow_none = True
    allow_blank = True


class CSVIntegerFieldV3(fields.Field):
    def _deserialize(self, value, attr, data, **kwargs):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        if not value:
            return self.load_default  # type: ignore[attr-defined] # "CSVIntegerFieldV3" has no attribute "load_default"

        int_list = []

        for i in value.split(","):
            try:
                int_list.append(int(i))
            except ValueError:
                raise ValidationError(f"{i} not a valid int!")

        return int_list

    def _serialize(self, value, attr, obj, **kwargs):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        # This is to achieve backwards compatibility with V1's behaviro is that if value is None, return None, otherwise empty []
        if value is not None:
            try:
                return [int(i) for i in value]
            except ValueError:
                raise ValidationError(f"{value} not a valid int!")
        else:
            return None


class CSVStringFieldV3(fields.Field):
    def _deserialize(self, value, attr, data, **kwargs):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        str_list = []

        if not value:
            return str_list
        for i in value.split(","):
            try:
                str_list.append(str(i))
            except ValueError:
                raise ValidationError(f"{value} not a valid value!")

        return str_list

    def _serialize(self, value, attr, obj, **kwargs):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        if value is None:
            return value
        return ",".join(str(s) for s in value)


class CancellationPolicyFieldV3(fields.Field):
    def _deserialize(self, value, attr, data, **kwargs):  # type: ignore[no-untyped-def] # Function is missing a type annotation
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

    def _serialize(self, value, attr, obj, **kwargs):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        if value is None:
            return None
        if isinstance(value, str):
            # cached values are already processed
            return value
        else:
            return value.name


class TelNumberOrNoneV3(TelNumberV3):
    def serialize(self, attr, obj, accessor=None, **kwargs):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        if isinstance(obj, PractitionerProfile):
            if any(is_cx_vertical_name(v.name) for v in obj.verticals):
                return None
        return super().serialize(attr, obj, accessor=accessor, **kwargs)


class OrderDirectionFieldV3(StringWithDefaultV3):
    def _deserialize(self, value, attr, data, **kwargs):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        if value is None:
            value = self.load_default  # type: ignore[attr-defined] # "OrderDirectionFieldV3" has no attribute "load_default"

        value = value.lower()
        if value not in ("asc", "desc"):
            raise ValidationError(f"{value} is not a valid order direction!")

        return value


# ============================ Deserialize Validator =======================================
def validate_geo_info(country, state, subdivision_code):  # type: ignore[no-untyped-def] # Function is missing a type annotation
    subdivisions = SubdivisionRepository()
    if country:
        if validated_country := subdivisions.countries.get_by_name(name=country):
            if not validated_country:
                raise ValidationError(f"{country} is not a valid country code!")
            if state and (
                validated_country.alpha_2 == "US"
                and not subdivisions.get_by_country_code_and_state(
                    country_code=validated_country.alpha_2, state=state
                )
            ):
                raise ValidationError(f"{state} is not a valid US state")

    if subdivision_code:
        if validated_subdivision := subdivisions.get(subdivision_code=subdivision_code):
            if not validated_subdivision:
                raise ValidationError(
                    f"'{subdivision_code}' is not a valid subdivision"
                )


# ============================ Schema definition =======================================


class SchemaV3(Schema):
    """
    This class is added purely for v1 backward compatibility.

    Quite a lot of the v1 schema definitions inherit directly from marshmallow_v1.Schema and this is to preserve
    the v1 behavior after migration. All v1 schema directly inherited from marshmallow_v1.Schema should inherit
    from this class in the respective v3 schema.
    """

    class Meta:
        # https://stackoverflow.com/questions/60866234/unknown-field-after-updating-to-3-5-0-marshmallow
        # In v3., marshmallow changed the default behavior from EXCLUDE to RAISE
        # https://marshmallow.readthedocs.io/en/stable/quickstart.html#handling-unknown-fields.
        # this is to stick to the old behavior
        unknown = EXCLUDE


class MavenSchemaV3(SchemaV3):
    def dump(self, obj, *args, **kwargs):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        with ddtrace.tracer.trace(
            name="marshmallow.dump",
            resource=self.__class__.__name__,
            service=SERVICE,
            span_type=SPAN_TYPE,
        ):
            return super().dump(obj, *args, **kwargs)

    def load(self, data, *args, **kwargs):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        with ddtrace.tracer.trace(
            name="marshmallow.load",
            resource=self.__class__.__name__,
            service=SERVICE,
            span_type=SPAN_TYPE,
        ):
            return super().load(data, *args, **kwargs)


class OrganizationSchemaV3(MavenSchemaV3):
    id = fields.Integer()
    name = StringWithDefaultV3(dump_default="")
    vertical_group_version = StringWithDefaultV3(dump_default="")
    bms_enabled = fields.Boolean()
    rx_enabled = fields.Boolean()
    education_only = fields.Boolean()
    display_name = StringWithDefaultV3(dump_default="")
    benefits_url = fields.String(default=None)


class PlanSchemaV3(MavenSchemaV3):
    id = IntegerWithDefaultV3(dump_default=0)
    segment_days = IntegerWithDefaultV3(dump_default=0)
    minimum_segments = IntegerWithDefaultV3(dump_default=0)
    price_per_segment = DecimalWithDefault(as_string=True, dump_default=0)
    is_recurring = fields.Boolean()
    active = fields.Constant(True)
    description = StringWithDefaultV3(dump_default="")
    billing_description = StringWithDefaultV3(dump_default="")


class AgreementsSchemaV3(MavenSchemaV3):
    subscription = BooleanWithDefault(dump_default=False)


class PaginableArgsSchemaV3(MavenSchemaV3):
    @pre_load(pass_many=False)
    def normalize_none_to_missing(self, data, **kwargs):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        for k, v in data.items():
            if v is None and not self.fields[k].allow_none:  # type: ignore[has-type] # Cannot determine type of "allow_none"
                data[k] = self.fields[k].load_default  # type: ignore[attr-defined] # "Field" has no attribute "load_default"

        return data

    offset = IntegerWithDefaultV3(
        dump_default=0,
        load_default=0,
        required=False,
        validate=validate.Range(min=0, min_inclusive=True),
    )
    limit = IntegerWithDefaultV3(
        dump_default=10,
        load_default=10,
        required=False,
        validate=validate.Range(
            min=0, min_inclusive=True, max=2000, max_inclusive=True
        ),
    )
    order_direction = OrderDirectionFieldV3(
        load_default="desc", dump_default="desc", required=False
    )


class PaginationInfoSchemaV3(PaginableArgsSchemaV3):
    total = IntegerWithDefaultV3(dump_default=0, required=False)


class PaginableOutputSchemaV3(MavenSchemaV3):
    pagination = fields.Nested(PaginationInfoSchemaV3)
    meta = RawWithDefaultV3(dump_default=None)
    data = RawWithDefaultV3(dump_default=None)


# N.B Purely for having minimum change to make this work
# Country is a fronzen dataclass which is immutable, here create a
# mutable version to make serialization easier
@dataclasses.dataclass()
class Country:
    alpha_2: str
    alpha_3: str
    name: str
    common_name: str | None = None
    official_name: str | None = None


class CountrySchemaV3(MavenSchemaV3):
    name = fields.Method(serialize="get_name")
    abbr = fields.Method(serialize="get_abbr")
    ext_info_link = fields.Method(serialize="get_ext_info_link")
    summary = fields.Method(serialize="get_summary")

    @pre_dump
    def prepare(self, obj, many, **kwargs):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        obj = Country(**dataclasses.asdict(obj))
        database_operation_fields = ("ext_info_link", "summary")
        for f in database_operation_fields:
            if self.only and f not in self.only or self.exclude and f in self.exclude:
                continue
            else:
                countries = CountryRepository()
                if country_metadata := countries.get_metadata(country_code=obj.alpha_2):
                    setattr(obj, f, getattr(country_metadata, f))
                else:
                    setattr(obj, f, None)

        return obj

    @staticmethod
    def get_name(obj):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        return obj and obj.name

    @staticmethod
    def get_abbr(obj):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        return obj and obj.alpha_2

    @staticmethod
    def get_ext_info_link(obj):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        return obj.ext_info_link

    @staticmethod
    def get_summary(obj):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        return obj.summary


class AddressSchemaV3(MavenSchemaV3):
    street_address = StringWithDefaultV3(dump_default="", required=True)
    zip_code = StringWithDefaultV3(dump_default="", required=True)
    city = StringWithDefaultV3(dump_default="", required=True)
    state = StringWithDefaultV3(dump_default="", required=True)
    country = StringWithDefaultV3(dump_default="", required=True)

    @validates_schema
    def validate_address(self, data, **kwargs):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        state = data.get("state")
        country = data.get("country")
        if not country:
            return
        validate_geo_info(country=country, state=state, subdivision_code=None)


class V2VerticalGetSchemaV3(MavenSchemaV3):
    @pre_load(pass_many=False)
    def normalize_none_to_missing(self, data, **kwargs):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        if "ids" in data and data["ids"] is None:
            data["ids"] = self.fields["ids"].load_default  # type: ignore[attr-defined] # "Field" has no attribute "load_default"
        return data

    ids = CSVIntegerFieldV3(required=False, load_default=[])


class V2VerticalSchemaV3(MavenSchemaV3):
    id = IntegerWithDefaultV3(dump_default=0)
    name = StringWithDefaultV3(dump_default="")
    pluralized_display_name = StringWithDefaultV3(dump_default="")
    description = StringWithDefaultV3(dump_default="")
    long_description = StringWithDefaultV3(dump_default="")
    can_prescribe = fields.Boolean()
    filter_by_state = fields.Boolean()


class MemberProfileSchemaV3(MavenSchemaV3):
    state = USAStateStringFieldAllowNoneV3()
    country = fields.Method(
        serialize="get_country", deserialize="load_value", allow_none=True
    )
    phone_number = PhoneNumberV3()
    tel_region = TelRegionV3(required=False, allow_none=True)
    tel_number = TelNumberV3()
    address = fields.Nested(AddressSchemaV3)
    opted_in_notes_sharing = fields.Boolean(required=False)
    color_hex = StringWithDefaultV3(dump_default="")
    user_flags = fields.Method(serialize="get_risk_flags", deserialize="load_value")
    can_book_cx = fields.Method(serialize="get_can_book_cx", deserialize="load_value")
    has_care_plan = fields.Boolean()
    care_plan_id = fields.Integer(
        nullable=True, default=None, required=False, allow_none=True
    )
    subdivision_code = StringWithDefaultV3(dump_default="", required=False)

    @validates_schema
    def validate_subdivision(self, data, **kwargs):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        validate_geo_info(
            country=None, state=None, subdivision_code=data.get("subdivision_code")
        )

    @pre_load
    def update_phone_number(self, data, **kwargs):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        tel_number = data.get("tel_number", None)
        phone_number = data.get("phone_number", None)
        if tel_number == phone_number or phone_number is None:
            number = tel_number
        else:
            number = phone_number
        region = data.get("tel_region", None)
        if "phone_number" in self.fields and number:
            data["phone_number"], _ = normalize_phone_number(number, region)
        return data

    @staticmethod
    def get_risk_flags(obj):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        if isinstance(obj, dict):
            return
        # Marshmallow v3 no longer swallow Attribute error in fields.Method/fields.Function like
        # marshmallow v1 does, user need to check if obj is valid
        try:
            user: User = obj.user
            return [{"id": f.id} for f in user.current_risk_flags()]
        except Exception:
            pass

    @staticmethod
    def get_can_book_cx(obj):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        if isinstance(obj, dict):
            return
        # Marshmallow v3 no longer swallow Attribute error in fields.Method/fields.Function like
        # marshmallow v1 does, user need to check if obj is valid
        if hasattr(obj.user, "is_enterprise"):
            return obj.user.is_enterprise

    @staticmethod
    def get_country(obj):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        if isinstance(obj, dict):
            return obj.get("country")
        if hasattr(obj, "country"):
            return obj.country and obj.country.alpha_2

    @staticmethod
    def load_value(value):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        return value


class PractitionerProfileSchemaV3(MavenSchemaV3):
    user_id = IntegerWithDefaultV3(dump_default=0, required=False)
    certified_states = fields.Method(serialize="get_certified_states")
    years_experience = IntegerWithDefaultV3(dump_default=0, required=False)
    certifications = AllowedCertificationsV3(required=False)
    categories = AllowedCategoriesV3(required=False)
    specialties = AllowedSpecialtiesV3(required=False)
    verticals = AllowedVerticalsV3(required=False)
    vertical_objects = fields.Method(serialize="get_vertical_objects")
    languages = AllowedLanguagesV3(required=False)
    phone_number = PhoneNumberV3()
    tel_region = TelRegionV3(required=True)
    tel_number = TelNumberOrNoneV3()
    cancellation_policy = CancellationPolicyFieldV3(required=False, allow_none=True)
    awards = StringWithDefaultV3(dump_default="", required=False)
    work_experience = StringWithDefaultV3(dump_default="", required=False)
    education = StringWithDefaultV3(dump_default="", required=False)
    reference_quote = StringWithDefaultV3(dump_default="", required=False)
    state = USAStateStringFieldAllowNoneV3(required=False)
    next_availability = MavenDateTimeV3(required=False)
    agreements = fields.Nested(AgreementsSchemaV3, required=False)
    address = fields.Nested(AddressSchemaV3, required=False)
    can_prescribe = fields.Method(serialize="get_can_prescribe")
    can_prescribe_to_member = fields.Method(serialize="get_can_prescribe_to_member")
    messaging_enabled = BooleanWithDefault(required=False, dump_default=False)
    response_time = fields.Integer(required=False, default=None)
    rating = fields.Float(required=False, default=None)
    care_team_type = fields.Method(serialize="get_care_team_type")
    faq_password = fields.Constant(os.environ.get("HELPDOCS_PASSWORD"))
    is_cx = fields.Method(serialize="get_is_cx")
    subdivision_code = StringWithDefaultV3(dump_default="", required=False)
    country = fields.Method(serialize="get_country")
    country_code = StringWithDefaultV3(dump_default="", required=False)
    certified_subdivision_codes = fields.Method(
        serialize="get_certified_subdivision_codes"
    )
    can_request_availability = fields.Method(serialize="get_can_request_availability")
    can_member_interact = fields.Method(serialize="get_can_member_interact")

    @validates_schema
    def validate_country_and_subdivision(self, data, **kwargs):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        validate_geo_info(
            country=data.get("country"),
            state=None,
            subdivision_code=data.get("subdivision_code"),
        )

    @pre_load
    def update_phone_number(self, data, **kwargs):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        tel_number = data.get("tel_number", None)
        phone_number = data.get("phone_number", None)
        if tel_number == phone_number or phone_number is None:
            number = tel_number
        else:
            number = phone_number
        region = data.get("tel_region", None)
        if "phone_numer" in self.fields:
            data["phone_number"], _ = normalize_phone_number(number, region)

    @staticmethod
    def get_certified_subdivision_codes(obj):  # type: ignore[no-untyped-def] # Function is missing a type annotation
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

    @staticmethod
    def get_certified_states(obj):  # type: ignore[no-untyped-def] # Function is missing a type annotation
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

        return [state.abbreviation.upper() for state in states]

    @staticmethod
    def get_can_prescribe(obj):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        if isinstance(obj, dict):
            return obj.get("can_prescribe", False)

        return ProviderService().provider_enabled_for_prescribing(obj)

    def get_can_prescribe_to_member(self, obj):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        if isinstance(obj, dict):
            return obj.get("can_prescribe_to_member", False)

        user = self.context.get("user")
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

    def get_vertical_objects(self, obj):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        if isinstance(obj, dict):
            return obj.get("vertical_objects", [])

        localize_provider_fields = self.context.get("localize_provider_fields")
        if localize_provider_fields:
            from l10n.db_strings.schema import TranslatedV2VerticalSchemaV3

            schema = TranslatedV2VerticalSchemaV3()  # type: ignore[assignment]
            schema.context = {
                "localize_provider_fields": True,
                "user": self.context.get("user"),
            }
        else:
            schema = V2VerticalSchemaV3()  # type: ignore[assignment]
        return schema.dump(obj.verticals, many=True)

    def get_care_team_type(self, obj):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        if self.context.get("care_team"):
            if isinstance(obj, dict):
                ct_type = self.context["care_team"].get(obj["user_id"])
            else:
                ct_type = self.context["care_team"].get(obj.user_id)

            if ct_type:
                return ct_type.pop()

    @staticmethod
    def get_country(obj):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        if isinstance(obj, dict):
            return obj.get("country")

        if obj.country and obj.country_code != "US":
            return CountrySchemaV3().dump(obj.country)

    @staticmethod
    def get_is_cx(obj):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        if isinstance(obj, dict):
            return obj.get("is_cx")

        return obj.user.is_care_coordinator

    @staticmethod
    def get_can_request_availability(obj):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        if isinstance(obj, dict):
            return obj.get("can_accept_availability_requests")

        return ProviderService().provider_contract_can_accept_availability_requests(obj)

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
        all_modifiers = get_active_member_track_modifiers(active_tracks)
        client_track_ids = [track.client_track_id for track in active_tracks]

        # return true for all non doula-only members or if member has any track that is doula_only
        # and if provider has any vertical that is doula_only_accessible
        return ProviderService().provider_can_member_interact(
            provider=obj,
            modifiers=all_modifiers,
            client_track_ids=client_track_ids,
        )


class UserProfilesSchemaV3(MavenSchemaV3):
    practitioner = fields.Method(serialize="get_practitioner_profile", dump_default={})
    member = fields.Method(serialize="get_member_profile", dump_default={})

    def get_member_profile(  # type: ignore[no-untyped-def] # Function is missing a type annotation
        self,
        profiles,
        # Allows the underlying member profile schema to be overridden
        # enabling the trimming of unused fields when nested.
        profile_schema=MemberProfileSchemaV3,
    ):
        mp = profiles.get(ROLES.member)
        if not mp:
            return {}

        context_user_id = self.context["user"].id if self.context.get("user") else None
        mp_user_id = mp.user_id if not isinstance(mp, dict) else None

        # default
        schema = profile_schema(only=["color_hex"])

        # overwrite on special cases
        if context_user_id and mp_user_id and context_user_id == mp_user_id:
            schema = profile_schema()
        elif self.context.get("appointment"):
            appt = self.context["appointment"]
            if appt.is_anonymous:
                schema = profile_schema(
                    only=["tel_region", "tel_number", "phone_number", "color_hex"]
                )
            elif appt.practitioner == self.context.get("user"):
                schema = profile_schema()

        return schema.dump(mp)

    def get_practitioner_profile(  # type: ignore[no-untyped-def] # Function is missing a type annotation
        self,
        profiles,
        # Allows the underlying practitioner profile schema to be overridden
        # enabling the trimming of unused fields when nested.
        profile_schema=PractitionerProfileSchemaV3,
    ):
        if not profiles.get(ROLES.practitioner):
            return {}

        profile = profiles[ROLES.practitioner]
        if isinstance(profile, dict):
            user_id = profile.get("user_id")
        else:
            user_id = profile.user_id

        context_user_id = None
        context_user = self.context.get("user")

        context_localize_provider = self.context.get("localize_provider_fields")
        if context_localize_provider:
            from l10n.db_strings.schema import TranslatedPractitionerProfileSchemaV3

            profile_schema = TranslatedPractitionerProfileSchemaV3

        if context_user:
            context_user_id = context_user.id

        if context_user_id != user_id:
            schema = profile_schema(exclude=_other_user_field_exclusions)
        else:
            schema = profile_schema()

        schema.context["care_team"] = self.context.get("care_team")
        schema.context["user"] = context_user
        schema.context["localize_provider_fields"] = self.context.get(
            "localize_provider_fields"
        )
        return schema.dump(profile)


class UserSchemaV3(MavenSchemaV3):
    id = IntegerWithDefaultV3(default=0)
    encoded_id = fields.Method(serialize="serialize_encoded_id")
    esp_id = fields.Method(serialize="get_esp_id")
    test_group = StringWithDefaultV3(dump_default="")
    first_name = StringWithDefaultV3(dump_default="")
    middle_name = StringWithDefaultV3(dump_default="")
    last_name = StringWithDefaultV3(dump_default="")
    name = fields.Method(serialize="get_name")
    email = fields.Method(serialize="get_email")
    username = fields.Method(serialize="get_username")
    role = fields.Method(serialize="serialize_role")
    avatar_url = StringWithDefaultV3(dump_default="")
    image_url = fields.Method(serialize="get_image_url")
    image_id = IntegerWithDefaultV3(dump_default=0)
    profiles = fields.Method(serialize="get_profiles")
    organization = fields.Method(serialize="get_organization")
    subscription_plans = fields.Method(serialize="get_subscription_plans")
    care_coordinators = NestedWithDefaultV3(
        "self", many=True, exclude=("created_at",), dump_default=[], default=[]
    )
    country = fields.Method("get_country_info")
    created_at = MavenDateTimeV3()

    @staticmethod
    def serialize_role(user):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        if isinstance(user, dict):
            return user.get("role", "")
        return user.role_name or ""

    def get_esp_id(self, user):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        if self.context.get("include_esp_id"):
            return user.esp_id

    def get_context_user_id(self):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        if self.context.get("user_id", None):
            return self.context.get("user_id", None)
        elif self.context.get("user"):
            return self.context.get("user").id  # type: ignore[union-attr] # Item "None" of "Optional[Any]" has no attribute "id"
        else:
            return None

    def serialize_encoded_id(self, user):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        user_id = user["id"] if isinstance(user, dict) else user.id
        context_user_id = self.get_context_user_id()
        if user_id == context_user_id:
            return security.new_user_id_encoded_token(user_id)

    def get_email(self, user):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        if not self.context.get("user"):
            return

        context_user_id = self.context.get("user").id  # type: ignore[union-attr] # Item "None" of "Optional[Any]" has no attribute "id"
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

    @staticmethod
    def get_name(user):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        if isinstance(user, dict):
            return user.get("name")
        return user.full_name

    @staticmethod
    def get_image_url(user):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        if isinstance(user, dict):
            return user.get("image_url")
        return user.avatar_url

    def get_profiles(  # type: ignore[no-untyped-def] # Function is missing a type annotation
        self,
        user,
        # Allows the underlying member profiles schema to be overridden
        # enabling the trimming of unused fields when nested.
        profiles_schema=UserProfilesSchemaV3,
    ):
        if self.context.get("include_profile"):
            allowed = {ROLES.member, ROLES.practitioner}

            if isinstance(user, dict):
                # we are getting from the cache
                profile_keys = user["profiles"].keys()
            else:
                profile_keys = user.user_types

            only = profile_keys & allowed

            schema = profiles_schema(only=only)
            schema.context["care_team"] = self.context.get("care_team")

            if self.context.get("user"):
                schema.context["user"] = self.context["user"]
            if self.context.get("appointment"):
                schema.context["appointment"] = self.context["appointment"]
            if self.context.get("localize_provider_fields"):
                schema.context["localize_provider_fields"] = self.context[
                    "localize_provider_fields"
                ]

            if isinstance(user, dict):
                # we are getting from the cache
                profiles = user["profiles"]
            else:
                profiles = user.profiles_map

            if not profiles:
                if not only:
                    return {"member": {}, "practitioner": {}}
                elif only == {ROLES.member}:
                    return {"member": {}}
                elif only == {ROLES.practitioner}:
                    return {"practitioner": {}}
            else:
                result = schema.dump(profiles)
                if result == {"member": {}, "practitioner": {}} or not result:
                    return {"member": {}, "practitioner": {}}
                else:
                    return result

        return None

    @staticmethod
    def get_organization(user):  # type: ignore[no-untyped-def] # Function is missing a type annotation
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

        return OrganizationSchemaV3().dump(org)

    @staticmethod
    def get_subscription_plans(user) -> None:  # type: ignore[no-untyped-def] # Function is missing a type annotation
        # Deprecated PlanPayer functionality
        return

    def get_country_info(self, user):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        """
        n.b.: if `country` is null, then it is defaulted to "US" for display on certain clients.
        """
        if (
            self.context.get("include_country_info")
            and user
            and user.country_code
            and not user.country_code == "US"
        ):
            return CountrySchemaV3().dump(user.country)

    def get_username(self, user):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        if not self.context.get("user"):
            return

        context_user_id = self.context.get("user").id  # type: ignore[union-attr] # Item "None" of "Optional[Any]" has no attribute "id"
        if isinstance(user, dict):
            # we are getting from the cache
            if context_user_id == user.get("id"):
                return user.get("username")
        else:
            if context_user_id == user.id:
                return user.username


class UserRoleFieldV3(fields.Field):
    @ddtrace.tracer.wrap(
        resource="user_role_field", service=SERVICE, span_type=SPAN_TYPE
    )
    def _deserialize(self, value: str) -> str:
        value = value.lower()
        roles = [v for k, v in ROLES.__dict__.items() if not k.startswith("_")]

        if value in roles:
            return value
        else:
            raise ValidationError(f"Invalid role: {value}")
