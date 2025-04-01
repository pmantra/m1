from marshmallow import fields

from views.schemas.base import MavenSchemaV3


class MemberRiskFlagsPostRequestV3(MavenSchemaV3):
    risk_flag_name = fields.String(required=True)
    modified_reason = fields.String(required=False)


class MemberRiskFlagsPostResponseV3(MavenSchemaV3):
    risk_flag_name = fields.String(required=True)
    created_risk = fields.Boolean(default=False)
    ended_risk = fields.Boolean(default=False)
    confirmed_risk = fields.Boolean(default=False)
