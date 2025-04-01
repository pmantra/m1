from __future__ import annotations

from dataclasses import dataclass

from marshmallow_v1 import fields

from direct_payment.payments.constants import EstimateText, PaymentText
from views.schemas.common import MavenSchema
from wallet.models.constants import WalletState
from wallet.models.reimbursement_organization_settings import (
    ReimbursementOrganizationSettings,
)
from wallet.models.reimbursement_wallet import ReimbursementWallet
from wallet.schemas.reimbursement_category import ReimbursementCategorySchema
from wallet.schemas.reimbursement_wallet_debit_card import (
    ReimbursementWalletDebitCardSchema,
)


def format_member_method(  # type: ignore[no-untyped-def] # Function is missing a return type annotation
    data: ReimbursementWalletUpcomingPaymentSchema
    | ReimbursementWalletUpcomingPaymentSummarySchema,
):
    return f"***{data.member_method}" if data.member_method else None


class BenefitResourceSchema(MavenSchema):
    title = fields.String()
    url = fields.String(attribute="content_url")


class ReimbursementOrganizationSettingsSchema(MavenSchema):
    id = fields.String()
    organization_id = fields.Integer()
    allowed_reimbursement_categories = fields.Method(
        "get_or_create_wallet_allowed_categories"
    )
    benefit_overview_resource = fields.Nested(
        BenefitResourceSchema, nullable=True, default=None
    )
    benefit_faq_resource = fields.Nested(BenefitResourceSchema)
    survey_url = fields.String()
    reimbursement_request_maximum = fields.Integer()
    is_active = fields.Boolean()
    debit_card_enabled = fields.Boolean()
    direct_payment_enabled = fields.Boolean()

    def get_or_create_wallet_allowed_categories(  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        self, obj: ReimbursementOrganizationSettings
    ):
        wallet = self.context.get("wallet")
        allowed_categories = (
            wallet.get_or_create_wallet_allowed_categories if wallet else []
        )
        schema = ReimbursementCategorySchema(
            many=True, exclude=["direct_payment_eligible"]
        )
        return schema.dump(allowed_categories).data


class ReimbursementWalletEmployeeSchema(MavenSchema):
    first_name = fields.String()
    last_name = fields.String()
    name = fields.Function(
        lambda obj: f"{obj['first_name'] or ''} {obj['last_name'] or ''}".strip()
    )


class ReimbursementWalletMemberSchema(MavenSchema):
    id = fields.Integer()
    first_name = fields.String()
    last_name = fields.String()
    name = fields.Function(
        lambda dependent: f"{dependent.get('first_name') or ''} {dependent.get('last_name') or ''}".strip()
    )


class ReimbursementWalletPharmacySchema(MavenSchema):
    name = fields.String()
    url = fields.String()


class ReimbursementWalletPaymentBlockSchema(MavenSchema):
    variant = fields.String(default=None, nullable=True)  # type: ignore[arg-type] # Argument "default" to "String" has incompatible type "None"; expected "str"
    show_benefit_amount = fields.Boolean(default=False)
    num_errors = fields.Integer(default=0)


class ReimbursementWalletTreatmentBlockSchema(MavenSchema):
    variant = fields.String(default=None, nullable=False)  # type: ignore[arg-type] # Argument "default" to "String" has incompatible type "None"; expected "str"
    clinic = fields.String()
    clinic_location = fields.String()


class ReimbursementWalletUpcomingPaymentSummarySchema(MavenSchema):
    total_member_amount = fields.Integer(default=None)  # type: ignore[arg-type] # Argument "default" to "Integer" has incompatible type "None"; expected "int"
    member_method = fields.String(default=None)  # type: ignore[arg-type] # Argument "default" to "String" has incompatible type "None"; expected "str"
    member_method_formatted = fields.Function(format_member_method)
    total_benefit_amount = fields.Integer(default=None)  # type: ignore[arg-type] # Argument "default" to "Integer" has incompatible type "None"; expected "int"
    benefit_remaining = fields.Integer(default=None)  # type: ignore[arg-type] # Argument "default" to "Integer" has incompatible type "None"; expected "int"
    procedure_title = fields.String()


class ReimbursementWalletEstimateSummarySchema(MavenSchema):
    estimate_text = fields.String(default=EstimateText.DEFAULT.value)
    total_estimates = fields.Integer(default=None)
    total_member_estimate = fields.String(default=None)  # type: ignore[arg-type] # Argument "default" to "String" has incompatible type "None"; expected "str"
    payment_text = fields.String(default=PaymentText.DEFAULT.value)
    estimate_bill_uuid = fields.String(default=None)  # type: ignore[arg-type] # Argument "default" to "String" has incompatible type "None"; expected "str"


class ReimbursementWalletUpcomingPaymentSchema(MavenSchema):
    bill_uuid = fields.String(default=None)  # type: ignore[arg-type] # Argument "default" to "String" has incompatible type "None"; expected "str"
    member_amount = fields.Integer(default=None)  # type: ignore[arg-type] # Argument "default" to "Integer" has incompatible type "None"; expected "int"
    member_method = fields.String(default=None)  # type: ignore[arg-type] # Argument "default" to "String" has incompatible type "None"; expected "str"
    member_method_formatted = fields.Function(format_member_method)
    member_date = fields.String(default=None)  # type: ignore[arg-type] # Argument "default" to "String" has incompatible type "None"; expected "str"
    benefit_amount = fields.Integer(default=None)  # type: ignore[arg-type] # Argument "default" to "Integer" has incompatible type "None"; expected "int"
    benefit_date = fields.String(default=None)  # type: ignore[arg-type] # Argument "default" to "String" has incompatible type "None"; expected "str"
    benefit_remaining = fields.Integer(default=None)  # type: ignore[arg-type] # Argument "default" to "Integer" has incompatible type "None"; expected "int"
    error_type = fields.String(default=None)  # type: ignore[arg-type] # Argument "default" to "String" has incompatible type "None"; expected "str"
    procedure_id = fields.Integer()
    procedure_title = fields.String()


class ReimbursementWalletUpcomingPaymentsSchema(MavenSchema):
    summary = fields.Nested(
        ReimbursementWalletUpcomingPaymentSummarySchema, nullable=True, default=None
    )
    payments = fields.Nested(ReimbursementWalletUpcomingPaymentSchema, many=True)


class ReimbursementWalletReimbursementRequestBlockSchema(MavenSchema):
    title = fields.String(default=None)
    total = fields.Integer(default=None)
    reimbursement_text = fields.String(default=None)
    expected_reimbursement_amount = fields.String(default=None)
    original_claim_text = fields.String(default=None)
    original_claim_amount = fields.String(default=None)
    reimbursement_request_uuid = fields.String(default=None)
    details_text = fields.String(default=None)
    has_cost_breakdown_available = fields.Boolean()


class ReimbursementWalletSchema(MavenSchema):
    id = fields.String()
    reimbursement_organization_settings = fields.Method(
        "reimbursement_org_settings_context"
    )
    currency_code = fields.String()
    state = fields.Function(lambda wallet: wallet.state.value)
    reimbursement_method = fields.String(required=True)
    zendesk_ticket_id = fields.Integer()
    debit_card_eligible = fields.Boolean()
    reimbursement_wallet_debit_card = fields.Nested(
        ReimbursementWalletDebitCardSchema, default=None, attribute="debit_card"
    )
    hdhp_status = fields.String()
    debit_banner = fields.String(default=None)  # type: ignore[arg-type] # Argument "default" to "String" has incompatible type "None"; expected "str"
    employee = fields.Nested(ReimbursementWalletEmployeeSchema)
    dependents = fields.Nested(ReimbursementWalletMemberSchema, many=True)
    members = fields.Nested(ReimbursementWalletMemberSchema, many=True)
    household = fields.Nested(ReimbursementWalletMemberSchema, many=True)
    channel_id = fields.Integer(default=None)  # type: ignore[arg-type] # Argument "default" to "Integer" has incompatible type "None"; expected "int"
    benefit_id = fields.Function(
        lambda wallet: wallet.reimbursement_wallet_benefit.maven_benefit_id
        if wallet.reimbursement_wallet_benefit
        and wallet.all_active_users
        and any(
            user.member_profile.country_code == "US" for user in wallet.all_active_users
        )
        else None
    )
    payment_block = fields.Nested(
        ReimbursementWalletPaymentBlockSchema, default=None, nullable=True
    )
    estimate_block = fields.Nested(
        ReimbursementWalletEstimateSummarySchema, default=None, nullable=True
    )
    treatment_block = fields.Nested(
        ReimbursementWalletTreatmentBlockSchema, default=None, nullable=True
    )
    upcoming_payments = fields.Nested(
        ReimbursementWalletUpcomingPaymentsSchema, default=None, nullable=True
    )
    reimbursement_request_block = fields.Nested(
        ReimbursementWalletReimbursementRequestBlockSchema, default=None, nullable=True
    )
    payments_customer_id = fields.String(default=None)  # type: ignore[arg-type] # Argument "default" to "String" has incompatible type "None"; expected "str"
    pharmacy = fields.Nested(ReimbursementWalletPharmacySchema, default=None)

    def reimbursement_org_settings_context(self, obj: ReimbursementWallet):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        schema = ReimbursementOrganizationSettingsSchema()
        schema.context["wallet"] = obj
        return schema.dump(obj.reimbursement_organization_settings).data


class ReimbursementWalletGETResponseSchema(MavenSchema):
    data = fields.Nested(ReimbursementWalletSchema, many=True)


@dataclass(frozen=True)
class ReimbursementWalletPOSTRequest:
    __slots__ = ("reimbursement_organization_settings_id", "initial_wallet_state")
    reimbursement_organization_settings_id: str
    initial_wallet_state: WalletState

    @staticmethod
    def from_request(request: dict) -> ReimbursementWalletPOSTRequest:
        initial_state_str = request.get("initial_wallet_state", None)
        initial_wallet_state = WalletState.PENDING
        if (
            initial_state_str is not None
            and initial_state_str.strip().lower()
            == WalletState.DISQUALIFIED.value.lower()
        ):
            initial_wallet_state = WalletState.DISQUALIFIED
        return ReimbursementWalletPOSTRequest(
            reimbursement_organization_settings_id=str(
                request["reimbursement_organization_settings_id"]
            ),
            initial_wallet_state=initial_wallet_state,
        )


class ReimbursementWalletResponseSchema(MavenSchema):
    data = fields.Nested(ReimbursementWalletSchema)


class ReimbursementWalletPUTRequestSchema(MavenSchema):
    reimbursement_organization_settings_id = fields.String()
    state = fields.String()
