from marshmallow import fields

from direct_payment.payments.constants import EstimateText, PaymentText
from views.schemas.base import NestedWithDefaultV3
from views.schemas.common_v3 import (
    BooleanWithDefault,
    IntegerWithDefaultV3,
    MavenSchemaV3,
    StringWithDefaultV3,
)
from wallet.schemas.reimbursement_category_v3 import ReimbursementCategorySchemaV3
from wallet.schemas.reimbursement_wallet_debit_card import (
    ReimbursementWalletDebitCardSchemaV3,
)


def format_member_method(data):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
    if hasattr(data, "member_method"):
        return f"***{data.member_method}" if data.member_method else None
    return None


class ReimbursementWalletEmployeeSchemaV3(MavenSchemaV3):
    first_name = StringWithDefaultV3(default="")
    last_name = StringWithDefaultV3(default="")
    name = fields.Function(
        lambda obj: f"{obj['first_name'] or ''} {obj['last_name'] or ''}".strip()
    )


class ReimbursementWalletMemberSchemaV3(MavenSchemaV3):
    id = IntegerWithDefaultV3(default=0)
    first_name = StringWithDefaultV3(default="")
    last_name = StringWithDefaultV3(default="")
    name = fields.Function(
        lambda dependent: f"{dependent.get('first_name') or ''} {dependent.get('last_name') or ''}".strip()
    )


class ReimbursementWalletPaymentBlockSchemaV3(MavenSchemaV3):
    variant = StringWithDefaultV3(default=None, nullable=True)  # type: ignore[arg-type] # Argument "default" to "String" has incompatible type "None"; expected "str"
    show_benefit_amount = BooleanWithDefault(default=False)
    num_errors = IntegerWithDefaultV3(default=0)


class ReimbursementWalletEstimateSummarySchemaV3(MavenSchemaV3):
    estimate_text = StringWithDefaultV3(default=EstimateText.DEFAULT.value)
    total_estimates = IntegerWithDefaultV3(default=None)
    total_member_estimate = StringWithDefaultV3(default=None)  # type: ignore[arg-type] # Argument "default" to "String" has incompatible type "None"; expected "str"
    payment_text = StringWithDefaultV3(default=PaymentText.DEFAULT.value)
    estimate_bill_uuid = StringWithDefaultV3(default=None)  # type: ignore[arg-type] # Argument "default" to "String" has incompatible type "None"; expected "str"


class ReimbursementWalletTreatmentBlockSchemaV3(MavenSchemaV3):
    variant = StringWithDefaultV3(default=None, nullable=False)  # type: ignore[arg-type] # Argument "default" to "String" has incompatible type "None"; expected "str"
    clinic = StringWithDefaultV3(default="")
    clinic_location = StringWithDefaultV3(default="")


class ReimbursementWalletUpcomingPaymentSummarySchemaV3(MavenSchemaV3):
    total_member_amount = IntegerWithDefaultV3(default=None)  # type: ignore[arg-type] # Argument "default" to "Integer" has incompatible type "None"; expected "int"
    member_method = StringWithDefaultV3(default=None)  # type: ignore[arg-type] # Argument "default" to "String" has incompatible type "None"; expected "str"
    member_method_formatted = fields.Function(format_member_method)
    total_benefit_amount = IntegerWithDefaultV3(default=None)  # type: ignore[arg-type] # Argument "default" to "Integer" has incompatible type "None"; expected "int"
    benefit_remaining = IntegerWithDefaultV3(default=None)  # type: ignore[arg-type] # Argument "default" to "Integer" has incompatible type "None"; expected "int"
    procedure_title = StringWithDefaultV3(default="")


class ReimbursementWalletUpcomingPaymentSchemaV3(MavenSchemaV3):
    bill_uuid = StringWithDefaultV3(default=None)  # type: ignore[arg-type] # Argument "default" to "String" has incompatible type "None"; expected "str"
    member_amount = IntegerWithDefaultV3(default=None)  # type: ignore[arg-type] # Argument "default" to "Integer" has incompatible type "None"; expected "int"
    member_method = StringWithDefaultV3(default=None)  # type: ignore[arg-type] # Argument "default" to "String" has incompatible type "None"; expected "str"
    member_method_formatted = fields.Function(format_member_method)
    member_date = StringWithDefaultV3(default=None)  # type: ignore[arg-type] # Argument "default" to "String" has incompatible type "None"; expected "str"
    benefit_amount = IntegerWithDefaultV3(default=None)  # type: ignore[arg-type] # Argument "default" to "Integer" has incompatible type "None"; expected "int"
    benefit_date = StringWithDefaultV3(default=None)  # type: ignore[arg-type] # Argument "default" to "String" has incompatible type "None"; expected "str"
    benefit_remaining = IntegerWithDefaultV3(default=None)  # type: ignore[arg-type] # Argument "default" to "Integer" has incompatible type "None"; expected "int"
    error_type = StringWithDefaultV3(default=None)  # type: ignore[arg-type] # Argument "default" to "String" has incompatible type "None"; expected "str"
    procedure_id = IntegerWithDefaultV3(default=0)
    procedure_title = StringWithDefaultV3(default="")


class ReimbursementWalletUpcomingPaymentsSchemaV3(MavenSchemaV3):
    summary = NestedWithDefaultV3(
        ReimbursementWalletUpcomingPaymentSummarySchemaV3, nullable=True, default=None
    )
    payments = NestedWithDefaultV3(
        ReimbursementWalletUpcomingPaymentSchemaV3, many=True, default=[]
    )


class ReimbursementWalletReimbursementRequestBlockSchemaV3(MavenSchemaV3):
    title = StringWithDefaultV3(default=None)
    total = IntegerWithDefaultV3(default=None)
    reimbursement_text = StringWithDefaultV3(default=None)
    expected_reimbursement_amount = StringWithDefaultV3(default=None)
    original_claim_text = StringWithDefaultV3(default=None)
    original_claim_amount = StringWithDefaultV3(default=None)
    reimbursement_request_uuid = StringWithDefaultV3(default=None)
    details_text = StringWithDefaultV3(default=None)
    has_cost_breakdown_available = fields.Boolean()


class ReimbursementWalletPharmacySchemaV3(MavenSchemaV3):
    name = StringWithDefaultV3(default="")
    url = StringWithDefaultV3(default="")


class BenefitResourceSchemaV3(MavenSchemaV3):
    title = StringWithDefaultV3(default="")
    url = StringWithDefaultV3(attribute="content_url", default="")


class ReimbursementOrganizationSettingsSchemaV3(MavenSchemaV3):
    id = StringWithDefaultV3(default="")
    organization_id = IntegerWithDefaultV3(default=0)
    allowed_reimbursement_categories = fields.Method(
        "get_or_create_wallet_allowed_categories"
    )
    benefit_overview_resource = NestedWithDefaultV3(
        BenefitResourceSchemaV3, nullable=True, default=None
    )
    benefit_faq_resource = NestedWithDefaultV3(BenefitResourceSchemaV3)
    survey_url = StringWithDefaultV3(default="")
    reimbursement_request_maximum = IntegerWithDefaultV3(default=0)
    is_active = fields.Boolean()
    debit_card_enabled = fields.Boolean()
    direct_payment_enabled = fields.Boolean()

    def get_or_create_wallet_allowed_categories(  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        self, obj
    ):
        wallet = self.context.get("wallet")
        allowed_categories = (
            wallet.get_or_create_wallet_allowed_categories if wallet else []
        )
        schema = ReimbursementCategorySchemaV3(
            many=True, exclude=["direct_payment_eligible"]
        )
        return schema.dump(allowed_categories)


class ReimbursementWalletSchemaV3(MavenSchemaV3):
    id = StringWithDefaultV3(default="")
    reimbursement_organization_settings = fields.Method(
        "reimbursement_org_settings_context"
    )
    currency_code = StringWithDefaultV3(default="")
    state = fields.Function(
        lambda wallet: wallet.state.value
        if hasattr(wallet, "state") and hasattr(wallet.state, "value")
        else None
    )
    reimbursement_method = StringWithDefaultV3(required=True, default="")
    zendesk_ticket_id = IntegerWithDefaultV3(default=0)
    debit_card_eligible = BooleanWithDefault(default=None)
    reimbursement_wallet_debit_card = NestedWithDefaultV3(
        ReimbursementWalletDebitCardSchemaV3, default=None, attribute="debit_card"
    )
    hdhp_status = StringWithDefaultV3(default="")
    debit_banner = StringWithDefaultV3(default=None)  # type: ignore[arg-type] # Argument "default" to "String" has incompatible type "None"; expected "str"
    employee = NestedWithDefaultV3(ReimbursementWalletEmployeeSchemaV3, default=[])
    dependents = NestedWithDefaultV3(
        ReimbursementWalletMemberSchemaV3, many=True, default=[]
    )
    members = NestedWithDefaultV3(
        ReimbursementWalletMemberSchemaV3, many=True, default=[]
    )
    household = NestedWithDefaultV3(
        ReimbursementWalletMemberSchemaV3, many=True, default=[]
    )
    channel_id = fields.Integer(default=None)  # type: ignore[arg-type] # Argument "default" to "Integer" has incompatible type "None"; expected "int"
    benefit_id = fields.Function(
        lambda wallet: wallet.reimbursement_wallet_benefit.maven_benefit_id
        if hasattr(wallet, "reimbursement_wallet_benefit")
        and wallet.reimbursement_wallet_benefit
        and hasattr(wallet, "all_active_users")
        and wallet.all_active_users
        and any(
            user.member_profile.country_code == "US" for user in wallet.all_active_users
        )
        else None
    )
    payment_block = NestedWithDefaultV3(
        ReimbursementWalletPaymentBlockSchemaV3, default=None, nullable=True
    )
    estimate_block = NestedWithDefaultV3(
        ReimbursementWalletEstimateSummarySchemaV3, default=None
    )
    treatment_block = NestedWithDefaultV3(
        ReimbursementWalletTreatmentBlockSchemaV3, default=None, nullable=True
    )
    upcoming_payments = NestedWithDefaultV3(
        ReimbursementWalletUpcomingPaymentsSchemaV3, default=None, nullable=True
    )
    reimbursement_request_block = NestedWithDefaultV3(
        ReimbursementWalletReimbursementRequestBlockSchemaV3(),
        default=None,
        nullable=True,
    )
    payments_customer_id = StringWithDefaultV3(default=None)  # type: ignore[arg-type] # Argument "default" to "String" has incompatible type "None"; expected "str"
    pharmacy = NestedWithDefaultV3(ReimbursementWalletPharmacySchemaV3, default=None)

    def reimbursement_org_settings_context(self, obj):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        schema = ReimbursementOrganizationSettingsSchemaV3()
        schema.context["wallet"] = obj
        if hasattr(obj, "reimbursement_organization_settings"):
            return schema.dump(obj.reimbursement_organization_settings)
        return None


class ReimbursementWalletResponseSchemaV3(MavenSchemaV3):
    data = fields.Nested(ReimbursementWalletSchemaV3)
