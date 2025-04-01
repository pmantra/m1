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


class ReimbursementCategorySchemaV3(MavenSchemaV3):
    id = StringWithDefaultV3(attribute="reimbursement_request_category_id", default="")
    label = StringWithDefaultV3(default="")
    reimbursement_request_category_maximum = IntegerWithDefaultV3(default=0)
    reimbursement_request_category_maximum_amount = fields.Nested(MoneyAmountSchemaV3)
    is_unlimited = BooleanWithDefault(default=False)
    title = StringWithDefaultV3(default="")
    subtitle = StringWithDefaultV3(default="")
    benefit_type = fields.Method("get_category_benefit_type")
    is_fertility_category = BooleanWithDefault(default=False)
    direct_payment_eligible = BooleanWithDefault(default=False)
    # credit_maximum will default to 0 if the benefit_type is CURRENCY
    credit_maximum = IntegerWithDefaultV3(default=0)
    credits_remaining = IntegerWithDefaultV3(default=0)

    def get_category_benefit_type(self, obj):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        if type(obj) is dict:
            return obj.get("benefit_type")
        if hasattr(obj, "benefit_type"):
            return obj.benefit_type.value
        return None


class ReimbursementRequestCategoryContainerSchemaV3(MavenSchemaV3):
    category = NestedWithDefaultV3(ReimbursementCategorySchemaV3, default=[])
    plan_type = StringWithDefaultV3(default="")
    plan_start = MavenDateTime()
    plan_end = MavenDateTime()
    spent = IntegerWithDefaultV3(default=0)
    spent_amount = NestedWithDefaultV3(MoneyAmountSchemaV3, default=[])
    remaining_amount = NestedWithDefaultV3(MoneyAmountSchemaV3, default=[])


class ExpenseTypesFormOptionsSchemaV3(MavenSchemaV3):
    name = StringWithDefaultV3(default="")
    label = StringWithDefaultV3(default="")


class ExpenseTypesSubtypesSchemaV3(MavenSchemaV3):
    id = StringWithDefaultV3(default="")
    label = StringWithDefaultV3(default="")


class ReimbursementRequestExpenseTypesSchemaV3(MavenSchemaV3):
    label = StringWithDefaultV3(default="")
    currency_code = StringWithDefaultV3(default=None)
    form_options = NestedWithDefaultV3(
        ExpenseTypesFormOptionsSchemaV3, many=True, default=[]
    )
    is_fertility_expense = BooleanWithDefault(default=False)
    subtypes = NestedWithDefaultV3(ExpenseTypesSubtypesSchemaV3, many=True, default=[])
