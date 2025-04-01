from __future__ import annotations

from marshmallow import fields, pre_load, validates_schema
from marshmallow.utils import _iso8601_datetime_re as ISO_DATEFORMAT
from marshmallow.utils import from_iso_datetime

from views.schemas.base import (
    BooleanWithDefault,
    MavenSchemaV3,
    PhoneNumberV3,
    StringWithDefaultV3,
    TelNumberV3,
    TelRegionV3,
)
from views.schemas.common import validate_phone_number


class CreateInviteSchemaV3(MavenSchemaV3):
    id = StringWithDefaultV3(dump_default="")
    email = fields.Email(required=True)
    name = StringWithDefaultV3(required=True, dump_default="")
    date_of_birth = fields.Date(required=True)
    phone_number = PhoneNumberV3()
    tel_number = TelNumberV3()
    tel_region = TelRegionV3()
    due_date = fields.Date()
    last_child_birthday = fields.Date()
    claimed = BooleanWithDefault(dump_default=None)

    @pre_load
    def preprocess_date(self, data, **kwargs):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        for k, v in data.items():
            if isinstance(self.fields[k], fields.Date):
                if ISO_DATEFORMAT.match(v):
                    # N.B. Python version below 3.11 doesn't support direct load string contain timezone
                    # info into a datetime obj, hence here we use the utils from marshamllow
                    data[k] = from_iso_datetime(v).date().isoformat()
        return data

    @validates_schema
    def validates_phone_number_wrapper(self, data, **kwargs):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        validator = validate_phone_number(required=False)
        return validator(self, data)
