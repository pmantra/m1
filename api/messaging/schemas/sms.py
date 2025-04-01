from marshmallow import ValidationError
from marshmallow import fields as v3_fields
from marshmallow import validates_schema
from marshmallow.validate import OneOf
from marshmallow_v1 import fields

from utils.data import normalize_phone_number
from views.schemas.common import (
    MavenSchema,
    PhoneNumber,
    TelNumber,
    TelRegion,
    validate_phone_number,
)
from views.schemas.common_v3 import (
    MavenSchemaV3,
    V3PhoneNumber,
    V3TelNumber,
    V3TelRegion,
)

SMS_TEMPLATES = {
    "default": "Here's a link to download the Maven app: http://m.onelink.me/d8de6de2",
    "sms1": "Here's a link to download the Maven app: https://mvn.app.link/KwFhr32T7N",
    "no_url": "Links not supported. Please visit the app store to download the Maven app.",
}


class SMSSchema(MavenSchema):
    __validators__ = [validate_phone_number(required=True)]
    phone_number = PhoneNumber()
    tel_number = TelNumber()
    tel_region = TelRegion()
    template = fields.Select(SMS_TEMPLATES, required=True)


class InternalSMSSchema(MavenSchemaV3):
    user_id = v3_fields.Integer(required=True)


class SMSSchemaV3(MavenSchemaV3):
    # __validators__ = [validate_phone_number(required=True)]
    phone_number = V3PhoneNumber()
    tel_number = V3TelNumber()
    tel_region = V3TelRegion()
    template = v3_fields.String(
        validate=OneOf(list(SMS_TEMPLATES.keys())), required=True
    )

    @validates_schema(skip_on_field_errors=False)
    def validate_fn(self, data, **kwargs):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        for f in ["tel_number", "tel_region"]:
            assert f in self.fields, f"Missing required field for schema ({f})."

        tel_number = data.get("tel_number", None)
        phone_number = data.get("phone_number", None)
        if tel_number == phone_number or phone_number is None:
            number = tel_number
        else:
            number = phone_number

        if not number:
            if True:
                raise ValidationError(
                    "Missing data for required field.", "phone_number"
                )
            return True

        region = data.get("tel_region", None)
        if "phone_number" in self.fields:
            data["phone_number"], _ = normalize_phone_number(number, region)

        return True
