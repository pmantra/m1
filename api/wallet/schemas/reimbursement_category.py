from marshmallow_v1 import fields

from views.schemas.common import MavenDateTime, MavenSchema
from wallet.schemas.currency import MoneyAmountSchema


class ReimbursementCategorySchema(MavenSchema):
    id = fields.String(attribute="reimbursement_request_category_id")
    label = fields.String()
    is_unlimited = fields.Boolean(default=False)
    reimbursement_request_category_maximum = fields.Integer()
    reimbursement_request_category_maximum_amount = fields.Nested(MoneyAmountSchema)
    title = fields.String()
    subtitle = fields.String()
    benefit_type = fields.Method("get_category_benefit_type")
    is_fertility_category = fields.Boolean(default=False)
    direct_payment_eligible = fields.Boolean(default=False)
    # credit_maximum will default to 0 if the benefit_type is CURRENCY
    credit_maximum = fields.Integer()
    credits_remaining = fields.Integer()

    def get_category_benefit_type(self, obj):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        if type(obj) is dict:
            return obj.get("benefit_type")
        if hasattr(obj, "benefit_type"):
            return obj.benefit_type.value
        return None


class ReimbursementRequestCategoryContainerSchema(MavenSchema):
    category = fields.Nested(ReimbursementCategorySchema)
    plan_type = fields.String()
    plan_start = MavenDateTime()
    plan_end = MavenDateTime()
    spent = fields.Integer()
    spent_amount = fields.Nested(MoneyAmountSchema)
    remaining_amount = fields.Nested(MoneyAmountSchema)


class ExpenseTypesFormOptionsSchema(MavenSchema):
    name = fields.String()
    label = fields.String()


class ExpenseTypesSubtypesSchema(MavenSchema):
    id = fields.String()
    label = fields.String()


class ReimbursementRequestExpenseTypesSchema(MavenSchema):
    label = fields.String()
    currency_code = fields.String(default=None)
    form_options = fields.Nested(ExpenseTypesFormOptionsSchema, many=True)
    is_fertility_expense = fields.Boolean(default=False)
    subtypes = fields.Nested(ExpenseTypesSubtypesSchema, many=True)
