from marshmallow import Schema, fields


class FHIRPharmacyInfoSchema(Schema):
    Address1 = fields.String()
    Address2 = fields.String(default=None, allow_none=True)
    City = fields.String()
    Pharmacy = fields.String(default=None, allow_none=True)
    PharmacyId = fields.String()
    PrimaryFax = fields.String(default=None, allow_none=True)
    PrimaryPhone = fields.String()
    PrimaryPhoneType = fields.String(default=None, allow_none=True)
    State = fields.String()
    StoreName = fields.String()
    ZipCode = fields.String()
