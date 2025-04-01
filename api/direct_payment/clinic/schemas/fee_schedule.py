from marshmallow import Schema, fields


class FeeScheduleGlobalProceduresSchema(Schema):
    id = fields.Integer(required=True)
    reimbursement_wallet_global_procedures_id = fields.Integer(required=True)
    cost = fields.Integer(required=True)


class FeeScheduleSchema(Schema):
    id = fields.Integer(required=True)
    name = fields.String(required=True)
    fee_schedule_global_procedures = fields.Nested(FeeScheduleGlobalProceduresSchema)
