from marshmallow import Schema, fields


class WalletBillingConsentSchema(Schema):
    consent_granted = fields.Boolean(required=True)
