from marshmallow import fields as v3_fields
from marshmallow_v1 import fields

from views.schemas.base import (
    BooleanWithDefault,
    IntegerWithDefaultV3,
    MavenSchemaV3,
    NestedWithDefaultV3,
    StringWithDefaultV3,
)
from views.schemas.common import MavenSchema
from wallet.models.constants import CardStatusReasonText


class ReimbursementWalletDebitCardSchema(MavenSchema):
    id = fields.Integer()
    reimbursement_wallet_id = fields.Integer()
    card_proxy_number = fields.String()
    card_last_4_digits = fields.String()
    card_status = fields.Function(lambda request: request.card_status.value)
    card_status_reason = fields.Function(
        lambda request: request.card_status_reason.value
    )
    card_status_reason_text = fields.Function(
        lambda request: CardStatusReasonText[request.card_status_reason]
    )
    created_date = fields.Date()
    issued_date = fields.Date()
    shipped_date = fields.Date()
    shipping_tracking_number = fields.String()


class ReimbursementWalletDebitCardSchemaV3(MavenSchemaV3):
    id = IntegerWithDefaultV3(default=0)
    reimbursement_wallet_id = IntegerWithDefaultV3(default=0)
    card_proxy_number = StringWithDefaultV3(default="")
    card_last_4_digits = StringWithDefaultV3(default="")
    card_status = v3_fields.Function(
        lambda request: request.card_status.value
        if hasattr(request, "card_status")
        else None
    )
    card_status_reason = v3_fields.Function(
        lambda request: request.card_status_reason.value
        if hasattr(request, "card_status_reason")
        else None
    )
    card_status_reason_text = v3_fields.Function(
        lambda request: CardStatusReasonText[request.card_status_reason]
        if hasattr(request, "card_status_reason")
        else None
    )
    created_date = v3_fields.Date()
    issued_date = v3_fields.Date()
    shipped_date = v3_fields.Date()
    shipping_tracking_number = StringWithDefaultV3(default="")


class ReimbursementWalletDebitCardResponseSchema(MavenSchema):
    data = fields.Nested(ReimbursementWalletDebitCardSchema)


class ReimbursementWalletDebitCardResponseSchemaV3(MavenSchemaV3):
    data = NestedWithDefaultV3(ReimbursementWalletDebitCardSchemaV3, default=[])


class ReimbursementWalletDebitCardPOSTRequestSchema(MavenSchema):
    sms_opt_in = fields.Boolean(default=False)


class ReimbursementWalletDebitCardPOSTRequestSchemaV3(MavenSchemaV3):
    sms_opt_in = BooleanWithDefault(default=False)
