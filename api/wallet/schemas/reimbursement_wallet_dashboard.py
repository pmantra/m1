from marshmallow import Schema, fields


class ReimbursementWalletDashboardCardSchema(Schema):
    title = fields.String()
    body = fields.String()
    img_url = fields.String()
    link_text = fields.String()
    link_url = fields.String()


class ReimbursementWalletDashboardSchema(Schema):
    data = fields.Nested(ReimbursementWalletDashboardCardSchema, many=True)
    show_apply_for_wallet = fields.Boolean()
    show_prompt_to_ask_for_invitation = fields.Boolean()
