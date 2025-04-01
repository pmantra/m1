from marshmallow_v1 import fields

from views.schemas.common import MavenSchema


class MoneyAmountSchema(MavenSchema):
    currency_code = fields.String()
    amount = fields.Integer()
    formatted_amount = fields.String()
    formatted_amount_truncated = fields.String()
    raw_amount = fields.String()
