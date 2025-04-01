from marshmallow import Schema, fields


class ReimbursementWalletUpcomingTransactionRequestSchema(Schema):
    offset = fields.Integer()


class UpcomingTransactionSchema(Schema):
    bill_uuid = fields.String()
    procedure_uuid = fields.String(required=True)
    procedure_name = fields.String(required=True)
    procedure_details = fields.String(required=True)
    maven_responsibility = fields.String(required=True)
    status = fields.String(required=True)


class ReimbursementWalletUpcomingTransactionResponseSchema(Schema):
    balance_after_upcoming_transactions = fields.String(required=True)
    limit = fields.Integer(required=True)
    offset = fields.Integer(required=True)
    total = fields.Integer(required=True)
    upcoming = fields.Nested(UpcomingTransactionSchema, many=True)
