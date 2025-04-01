from marshmallow import fields

from views.schemas.base import NestedWithDefaultV3
from views.schemas.common_v3 import (
    BooleanWithDefault,
    IntegerWithDefaultV3,
    MavenDateTime,
    MavenSchemaV3,
    StringWithDefaultV3,
)
from wallet.schemas.currency_v3 import MoneyAmountSchemaV3
from wallet.schemas.reimbursement import ReimbursementRequestSourceSchemaV3
from wallet.schemas.reimbursement_category_v3 import (
    ReimbursementCategorySchemaV3,
    ReimbursementRequestCategoryContainerSchemaV3,
    ReimbursementRequestExpenseTypesSchemaV3,
)


class ReimbursementRequestCostShareDetailsSchemaV3(MavenSchemaV3):
    reimbursement_amount = StringWithDefaultV3(
        required=False, allow_none=True, default=None
    )
    reimbursement_expected_message = StringWithDefaultV3(
        required=False, allow_none=True, default=None
    )
    original_claim_amount = StringWithDefaultV3(
        required=False, allow_none=True, default=None
    )


class ReimbursementRequestSchemaV3(MavenSchemaV3):
    id = StringWithDefaultV3(default="")
    label = fields.Function(
        # handle test cases where request is not a ReimbursementRequest object
        lambda request: request.formatted_label
        if hasattr(request, "formatted_label")
        else ""
    )
    service_provider = StringWithDefaultV3(default="")
    person_receiving_service = StringWithDefaultV3(default="")
    employee_name = StringWithDefaultV3(default="")
    description = StringWithDefaultV3(default="")
    amount = IntegerWithDefaultV3(default=0)
    benefit_amount = NestedWithDefaultV3(MoneyAmountSchemaV3, default=[])
    state = fields.Function(
        lambda request: request.state.value
        if hasattr(request, "state") and hasattr(request.state, "value")
        else None
    )
    state_description = StringWithDefaultV3(default="")
    category = NestedWithDefaultV3(
        ReimbursementCategorySchemaV3(
            exclude=(
                "reimbursement_request_category_maximum",
                "reimbursement_request_category_maximum_amount",
                "direct_payment_eligible",
                "credit_maximum",
                "credits_remaining",
                "is_fertility_category",
                "is_unlimited",
            )
        ),
        default=[],
    )
    source = NestedWithDefaultV3(
        ReimbursementRequestSourceSchemaV3, attribute="first_source", default=[]
    )
    sources = NestedWithDefaultV3(
        ReimbursementRequestSourceSchemaV3, many=True, default=[]
    )
    service_start_date = MavenDateTime()
    service_end_date = MavenDateTime()
    created_at = MavenDateTime()
    taxation_status = StringWithDefaultV3(default="")
    reimbursement_type = fields.Function(
        lambda request: request.reimbursement_type.name
        if hasattr(request, "reimbursement_type")
        and hasattr(request.reimbursement_type, "name")
        else None
    )
    cost_share_details = NestedWithDefaultV3(
        ReimbursementRequestCostShareDetailsSchemaV3, allow_null=True, default=[]
    )


class ReimbursementRequestSummarySchemaV3(MavenSchemaV3):
    reimbursement_request_maximum = IntegerWithDefaultV3(default=0)
    reimbursement_spent = IntegerWithDefaultV3(default=0)
    currency_code = StringWithDefaultV3(default="")
    wallet_shareable = BooleanWithDefault(default=False)
    category_breakdown = NestedWithDefaultV3(
        ReimbursementRequestCategoryContainerSchemaV3, many=True, default=[]
    )
    expense_types = NestedWithDefaultV3(
        ReimbursementRequestExpenseTypesSchemaV3, many=True, default=[]
    )


class ReimbursementRequestDataSchemaV3(MavenSchemaV3):
    summary = NestedWithDefaultV3(ReimbursementRequestSummarySchemaV3, default=[])
    reimbursement_requests = NestedWithDefaultV3(
        ReimbursementRequestSchemaV3, many=True, default=[]
    )


class ReimbursementRequestMetaSchemaV3(MavenSchemaV3):
    reimbursement_wallet_id = StringWithDefaultV3(default="")
    category = StringWithDefaultV3(default="")


class ReimbursementRequestResponseSchemaV3(MavenSchemaV3):
    meta = NestedWithDefaultV3(
        # TODO: the exclude does not work in V1, so removed it
        # ReimbursementRequestMetaSchemaV3(exclude=["category"]), default=[]
        ReimbursementRequestMetaSchemaV3(),
        default=[],
    )
    data = NestedWithDefaultV3(ReimbursementRequestDataSchemaV3, default=[])


class ReimbursementRequestWithCategoryResponseSchemaV3(MavenSchemaV3):
    meta = NestedWithDefaultV3(ReimbursementRequestMetaSchemaV3(), default=[])
    data = NestedWithDefaultV3(ReimbursementRequestDataSchemaV3, default=[])
