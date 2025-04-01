from marshmallow import ValidationError, fields

from views.schemas.base import (
    BooleanWithDefault,
    IntegerWithDefaultV3,
    MavenSchemaV3,
    StringWithDefaultV3,
)


def validate_zip(value: str) -> None:
    if len(value) > 10:
        raise ValidationError(f"Bad zip_code: {value}")

    try:
        int(value)
    except ValueError:
        raise ValidationError(f"Bad zip_code: {value}")


class PharmacySearchRequestSchemaV3(MavenSchemaV3):
    zip_code = StringWithDefaultV3(
        validate=validate_zip, required=False, dump_default=None
    )
    pharmacy_name = StringWithDefaultV3(required=False, dump_default=None)
    page_number = IntegerWithDefaultV3(required=False, dump_default=None)


class DoseSpotPharmacySchemaV3(MavenSchemaV3):
    PharmacyId = StringWithDefaultV3(required=True, dump_default="")
    StoreName = StringWithDefaultV3(required=True, dump_default="")
    Address1 = StringWithDefaultV3(required=True, dump_default="")
    Address2 = StringWithDefaultV3(required=False, dump_default="")
    City = StringWithDefaultV3(required=True, dump_default="")
    State = StringWithDefaultV3(required=True, dump_default="")
    ZipCode = StringWithDefaultV3(required=True, dump_default="")
    PrimaryPhone = StringWithDefaultV3(required=True, dump_default="")
    PrimaryPhoneType = StringWithDefaultV3(required=True, dump_default="")
    PrimaryFax = StringWithDefaultV3(required=True, dump_default="")


class PaginationSchemaV3(MavenSchemaV3):
    current_page = IntegerWithDefaultV3(required=True, dump_default=0)
    total_pages = IntegerWithDefaultV3(required=True, dump_default=0)
    page_size = IntegerWithDefaultV3(required=True, dump_default=0)
    has_previous = BooleanWithDefault(required=True, dump_default=False)
    has_next = BooleanWithDefault(required=True, dump_default=False)


class PharmacySearchResponseSchemaV3(MavenSchemaV3):
    data = fields.Nested(DoseSpotPharmacySchemaV3, many=True, required=True)
    pagination = fields.Nested(PaginationSchemaV3, required=True)
