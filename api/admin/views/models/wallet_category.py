from __future__ import annotations

from typing import Type

import pycountry
from flask import flash, request
from flask_admin.form import BaseForm
from flask_admin.model.form import InlineFormAdmin
from wtforms import Form, fields, validators

from admin.common import Select2MultipleField
from admin.views.base import (
    AdminCategory,
    AdminViewT,
    ContainsFilter,
    CustomFormField,
    MavenAuditedView,
)
from models.enterprise import Organization
from storage.connection import RoutingSQLAlchemy, db
from utils.log import logger
from wallet.constants import SUPPORTED_BENEFIT_CURRENCIES
from wallet.models.constants import BenefitTypes, ReimbursementRequestExpenseTypes
from wallet.models.currency import Money
from wallet.models.reimbursement import (
    ReimbursementRequestCategory,
    ReimbursementRequestCategoryExpenseTypes,
)
from wallet.models.reimbursement_organization_settings import (
    ReimbursementOrganizationSettings,
    ReimbursementOrgSettingCategoryAssociation,
)
from wallet.services.currency import CurrencyService
from wallet.utils.currency import format_display_amount_with_currency_code

log = logger(__name__)


class ReimbursementRequestCategoryViewOrganizationFilter(ContainsFilter):
    def apply(self, query, value, alias=None):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        return (
            query.join(ReimbursementRequestCategory.allowed_reimbursement_organizations)
            .join(
                ReimbursementOrgSettingCategoryAssociation.reimbursement_organization_settings
            )
            .join(ReimbursementOrganizationSettings.organization)
            .filter(Organization.name.contains(value))
        )


class ReimbursementOrganizationSettingsFilter(ContainsFilter):
    def apply(self, query, value, alias=None):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        return (
            query.join(
                ReimbursementOrgSettingCategoryAssociation.reimbursement_organization_settings
            )
            .join(ReimbursementOrganizationSettings.organization)
            .filter(Organization.name.contains(value))
        )


class CategoryMaximumAmountForm(Form):
    is_unlimited = fields.BooleanField("Unlimited Benefit", default=False)
    amount = fields.DecimalField("Amount", validators=[validators.Optional()])
    # coerce lambda kwarg is a workaround for https://github.com/wtforms/wtforms/issues/289
    currency_code = fields.SelectField(
        "Currency",
        coerce=lambda x: None if x == "None" else x,
        choices=[(None, "Select benefit currency")]
        + [
            (c.alpha_3, f"{c.name} ({c.alpha_3})")
            for c in map(
                lambda cc: pycountry.currencies.get(alpha_3=cc),
                sorted(SUPPORTED_BENEFIT_CURRENCIES),
            )
        ],
        default=None,
    )

    def on_form_prefill(
        self,
        currency_service: CurrencyService,
        category: ReimbursementOrgSettingCategoryAssociation,
    ) -> None:
        self.is_unlimited.data = category.is_unlimited
        if (
            category.is_unlimited is False
            and category.reimbursement_request_category_maximum
            and category.currency_code
        ):
            money = currency_service.to_money(
                amount=category.reimbursement_request_category_maximum,
                currency_code=category.currency_code,
            )
            self.amount.places = currency_service.currency_code_repo.get_minor_unit(
                currency_code=money.currency_code
            )
            self.amount.data = money.amount
            self.currency_code.data = money.currency_code
        elif category.is_unlimited is True and category.currency_code:
            self.currency_code.data = category.currency_code

    def get_money_amount(self) -> Money:
        if self.is_unlimited.data is True:
            raise ValueError("get_money_amount can't be called for unlimited benefits")
        if self.amount.data is None:
            raise ValueError("'Amount' is required")
        if self.currency_code.data is None:
            raise ValueError("'Currency Code' is required")
        return Money(amount=self.amount.data, currency_code=self.currency_code.data)


def category_maximum_amount_formatter(view, context, model: ReimbursementOrgSettingCategoryAssociation, name) -> str:  # type: ignore[no-untyped-def] # Function is missing a type annotation for one or more arguments
    minor_unit_amount: int | None = model.reimbursement_request_category_maximum
    currency_code: str | None = model.currency_code
    is_unlimited: bool = model.is_unlimited

    if model.benefit_type == BenefitTypes.CURRENCY and is_unlimited is True:
        return "UNLIMITED"
    elif model.benefit_type == BenefitTypes.CURRENCY and is_unlimited is False:
        currency_service = CurrencyService()
        money_amount: Money = currency_service.to_money(
            amount=minor_unit_amount, currency_code=currency_code
        )
        return format_display_amount_with_currency_code(money=money_amount)
    else:
        return ""


class InlineOrgCategoryAssociation(InlineFormAdmin):
    form_extra_fields = {
        "category_maximum_form": CustomFormField(
            CategoryMaximumAmountForm,
            label="Currency Reimbursement Request Category Maximum",
        ),
    }

    form_excluded_columns = (
        "created_at",
        "modified_at",
        "reimbursement_request_category_maximum",
        "currency_code",
        "is_unlimited",
        "allowed_category_rules",
    )

    def on_model_change(self, form, model, is_created: bool):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        super().on_model_change(form, model, is_created)
        update_category_association_model_with_form(form, model)


class ReimbursementRequestCategoryForm(BaseForm):
    def validate(self, *args, **kwargs) -> bool:  # type: ignore[no-untyped-def] # Function is missing a type annotation
        is_valid = super().validate(*args, **kwargs)
        is_inline_valid = True
        for inline_form in self.allowed_reimbursement_organizations:
            if (
                validate_reimbursement_org_setting_category_association(
                    inline_form.reimbursement_organization_settings.data,
                    self,
                    inline_form.benefit_type.data,
                    inline_form.category_maximum_form.form.is_unlimited.data,
                    inline_form.num_cycles.data,
                    inline_form.category_maximum_form.form.currency_code.data,
                    inline_form.category_maximum_form.form.amount.data,
                    is_valid,
                )
                is False
            ):
                is_inline_valid = False
        return is_valid & is_inline_valid


class ReimbursementRequestCategoryView(MavenAuditedView):
    create_permission = "create:reimbursement-request-category"
    edit_permission = "edit:reimbursement-request-category"
    delete_permission = "delete:reimbursement-request-category"
    read_permission = "read:reimbursement-request-category"
    required_capability = "admin_wallet_tools"  # type: ignore[assignment] # Incompatible types in assignment (expression has type "str", base class "AdminAuth" defined the type as "None")

    form_base_class = ReimbursementRequestCategoryForm

    column_filters = [
        ReimbursementRequestCategoryViewOrganizationFilter(None, "Organizations"),
    ]
    column_list = (
        "id",
        "label",
        "reimbursement_plan_id",
        "reimbursement_plan.alegeus_plan_id",
        "organizations",
        "category_expense_types",
    )
    column_labels = {
        "reimbursement_plan.alegeus_plan_id": "Alegeus Plan Id (from Reimbursement Plan)",
    }
    column_formatters = {
        "organizations": (
            lambda v, c, m, p: (
                ", ".join(org.name for org in m.organizations) if m else None
            )
        ),
        "category_expense_types": (lambda v, c, m, p: m.expense_types),
    }
    form_columns = (
        "label",
        "short_label",
        "expenses",
        "reimbursement_plan",
        "allowed_reimbursement_organizations",
    )
    form_extra_fields = {
        "expenses": Select2MultipleField(
            label="Category Expense Types",
            choices=[
                (expense.value, expense) for expense in ReimbursementRequestExpenseTypes
            ],
        )
    }
    inline_models = [
        InlineOrgCategoryAssociation(ReimbursementOrgSettingCategoryAssociation)
    ]

    def on_form_prefill(self, form, id):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        super().on_form_prefill(form, id)
        e = self.get_one(id)
        form.expenses.process_formdata([t.value for t in e.expense_types])
        for inline_form in form.allowed_reimbursement_organizations:
            inline_form.form.category_maximum_form.on_form_prefill(
                currency_service=CurrencyService(),
                category=inline_form.object_data,
            )

    def on_model_change(self, form, model, is_created: bool):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        current_expenses = {e.name for e in model.expense_types}
        requested_expenses = set(request.form.getlist("expenses"))

        if len(current_expenses) < 1:
            model.category_expense_types = [
                ReimbursementRequestCategoryExpenseTypes(
                    expense_type=expense, reimbursement_request_category_id=model.id
                )
                for expense in requested_expenses  # supports selecting multiple category expense types
            ]
        else:
            # Removes or adds to the current list
            difference_expenses = current_expenses ^ requested_expenses
            for expense in difference_expenses:
                if expense not in current_expenses:
                    new_expense = ReimbursementRequestCategoryExpenseTypes(
                        expense_type=expense, reimbursement_request_category_id=model.id
                    )
                    model.category_expense_types.append(new_expense)
                else:
                    ReimbursementRequestCategoryExpenseTypes.query.filter_by(
                        expense_type=expense, reimbursement_request_category_id=model.id
                    ).delete()

        super().on_model_change(form, model, is_created)

    @classmethod
    def factory(  # type: ignore[no-untyped-def] # Function is missing a type annotation for one or more arguments
        cls: Type[AdminViewT],
        *,
        session: RoutingSQLAlchemy = None,  # type: ignore[assignment] # Incompatible default for argument "session" (default has type "None", argument has type "RoutingSQLAlchemy")
        category: AdminCategory = None,  # type: ignore[assignment] # Incompatible default for argument "category" (default has type "None", argument has type "AdminCategory")
        name: str = None,  # type: ignore[assignment] # Incompatible default for argument "name" (default has type "None", argument has type "str")
        endpoint: str = None,  # type: ignore[assignment] # Incompatible default for argument "endpoint" (default has type "None", argument has type "str")
        **kwargs,
    ) -> AdminViewT:
        return cls(  # type: ignore[call-arg] # Too many arguments for "object" #type: ignore[call-arg] # Unexpected keyword argument "category" for "object" #type: ignore[call-arg] # Unexpected keyword argument "name" for "object" #type: ignore[call-arg] # Unexpected keyword argument "endpoint" for "object"
            ReimbursementRequestCategory,
            session or db.session,
            category=category,
            name=name,
            endpoint=endpoint,
            **kwargs,
        )


class ReimbursementOrgSettingCategoryAssociationForm(BaseForm):
    def validate(self, *args, **kwargs) -> bool:  # type: ignore[no-untyped-def] # Function is missing a type annotation
        is_valid = super().validate(*args, **kwargs)
        return validate_reimbursement_org_setting_category_association(
            self.reimbursement_organization_settings.data,
            self.reimbursement_request_category.data,
            self.benefit_type.data,
            self.category_maximum_form.form.is_unlimited.data,
            self.num_cycles.data,
            self.category_maximum_form.form.currency_code.data,
            self.category_maximum_form.form.amount.data,
            is_valid,
        )


class ReimbursementOrgSettingCategoryAssociationView(MavenAuditedView):
    create_permission = "create:reimbursement-organization-category-association"
    edit_permission = "edit:reimbursement-organization-category-association"
    delete_permission = "delete:reimbursement-organization-category-association"
    read_permission = "read:reimbursement-organization-category-association"

    required_capability = "admin_wallet_tools"  # type: ignore[assignment] # Incompatible types in assignment (expression has type "str", base class "AdminAuth" defined the type as "None")

    form_base_class = ReimbursementOrgSettingCategoryAssociationForm

    column_list = (
        "id",
        "reimbursement_organization_settings",
        "reimbursement_request_category",
        "benefit_type",
        "currency_code",
        "reimbursement_request_category_maximum",
        "num_cycles",
    )

    column_labels = {
        "reimbursement_request_category_maximum": "Currency Reimbursement Request Category Maximum ($)",
        "num_cycles": "Cycle Reimbursement Request Category Maximum (Cycles)",
        "currency_code": "Benefit Currency",
    }

    column_descriptions = {
        "num_cycles": "(In Cycles. 1 Cycle = 12 Credits)",
        "currency_code": "The configured currency of this category (required for currency-based benefits)",
    }

    column_formatters = {
        "reimbursement_request_category_maximum": category_maximum_amount_formatter
    }

    column_filters = [
        ReimbursementOrganizationSettingsFilter(None, "Organizations"),
    ]

    form_extra_fields = {
        "category_maximum_form": CustomFormField(
            CategoryMaximumAmountForm,
            label="Currency Reimbursement Request Category Maximum",
        ),
    }

    form_create_rules = (
        "reimbursement_organization_settings",
        "reimbursement_request_category",
        "benefit_type",
        "category_maximum_form",
        "num_cycles",
    )

    form_edit_rules = (
        "reimbursement_organization_settings",
        "reimbursement_request_category",
        "benefit_type",
        "category_maximum_form",
        "num_cycles",
    )

    form_excluded_columns = ("created_at", "modified_at")

    def on_form_prefill(self, form, id):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        super().on_form_prefill(form=form, id=id)
        category: ReimbursementOrgSettingCategoryAssociation = self.get_one(id)
        currency_service = CurrencyService()
        category_maximum_form: CategoryMaximumAmountForm = form.category_maximum_form
        category_maximum_form.on_form_prefill(
            currency_service=currency_service, category=category
        )

    def on_model_change(self, form, model, is_created: bool):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        super().on_model_change(form, model, is_created)
        update_category_association_model_with_form(form, model)

    def get_delete_form(self):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        class DeleteForm(BaseForm):
            id = fields.HiddenField(validators=[validators.InputRequired()])
            url = fields.HiddenField()

        return DeleteForm

    def get_action_form(self):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        class ActionForm(BaseForm):
            action = fields.HiddenField()
            url = fields.HiddenField()

        return ActionForm

    @classmethod
    def factory(  # type: ignore[no-untyped-def] # Function is missing a type annotation for one or more arguments
        cls: Type[AdminViewT],
        *,
        session: RoutingSQLAlchemy = None,  # type: ignore[assignment] # Incompatible default for argument "session" (default has type "None", argument has type "RoutingSQLAlchemy")
        category: AdminCategory = None,  # type: ignore[assignment] # Incompatible default for argument "category" (default has type "None", argument has type "AdminCategory")
        name: str = None,  # type: ignore[assignment] # Incompatible default for argument "name" (default has type "None", argument has type "str")
        endpoint: str = None,  # type: ignore[assignment] # Incompatible default for argument "endpoint" (default has type "None", argument has type "str")
        **kwargs,
    ) -> AdminViewT:
        return cls(  # type: ignore[call-arg] # Too many arguments for "object" #type: ignore[call-arg] # Unexpected keyword argument "category" for "object" #type: ignore[call-arg] # Unexpected keyword argument "name" for "object" #type: ignore[call-arg] # Unexpected keyword argument "endpoint" for "object"
            ReimbursementOrgSettingCategoryAssociation,
            session or db.session,
            category=category,
            name=name,
            endpoint=endpoint,
            **kwargs,
        )


def validate_reimbursement_org_setting_category_association(
    reimbursement_organization_settings: ReimbursementOrganizationSettings | None,
    reimbursement_request_category: ReimbursementRequestCategory | None,
    benefit_type: str,
    is_unlimited: bool,
    num_cycles: int | None,
    currency_code: str | None,
    category_maximum_amount: int | None,
    is_valid: bool,
) -> bool:
    """
    Shared validation logic for ReimbursementOrgSettingCategoryAssociationForm and InlineOrgCategoryAssociation
    """
    if (ros := reimbursement_organization_settings) is None:
        flash("'Reimbursement Organization Settings' must be set")
        return False

    if reimbursement_request_category is None:
        flash("'Reimbursement Request Category' must be set")
        return False

    if benefit_type == BenefitTypes.CURRENCY.value:
        if num_cycles:
            flash(
                "Number of cycles cannot be set if benefit type is currency. "
                "Please use Cycle Benefit type to use this field."
            )
            return False

        if currency_code is None:
            flash("'Currency' must be set for currency-based benefits")
            return False

        if is_unlimited is False and category_maximum_amount is None:
            flash("'Amount' must be set for limited currency-based benefits")
            return False

        if is_unlimited is True and category_maximum_amount is not None:
            flash("'Amount' must not be set if benefits are unlimited")
            return False

    elif benefit_type == BenefitTypes.CYCLE.value:
        if (
            ros.debit_card_enabled
            or not ros.direct_payment_enabled
            or not ros.closed_network
        ):
            flash(
                "When setting benefit type to cycle, debit card cannot be enabled. Direct payment "
                "and closed network must be enabled",
                "error",
            )
            return False

        if num_cycles is None:
            flash("Number of cycles must be set if benefit type is cycle.")
            return False

        if is_unlimited is True:
            flash(
                "Unlimited Benefits can only be configured for currency-based benefits."
            )
            return False

    return is_valid


def update_category_association_model_with_form(
    form: ReimbursementOrgSettingCategoryAssociationForm,
    model: ReimbursementOrgSettingCategoryAssociation,
) -> ReimbursementOrgSettingCategoryAssociation:
    if model.benefit_type == BenefitTypes.CYCLE.value:
        model.reimbursement_request_category_maximum = None
        model.currency_code = None
        model.is_unlimited = False
    elif model.benefit_type == BenefitTypes.CURRENCY.value:
        if (is_unlimited := form.category_maximum_form.form.is_unlimited.data) is False:
            money_amount = form.category_maximum_form.get_money_amount()
            currency_service = CurrencyService()
            minor_unit_amount: int = currency_service.to_minor_unit_amount(
                money=money_amount
            )
            model.reimbursement_request_category_maximum = minor_unit_amount
            model.currency_code = money_amount.currency_code
            model.is_unlimited = is_unlimited
        else:
            model.reimbursement_request_category_maximum = None
            model.currency_code = form.category_maximum_form.form.currency_code.data
            model.is_unlimited = is_unlimited
    else:
        raise ValueError(f"Incompatible benefit type configured {model.benefit_type}")

    return model
