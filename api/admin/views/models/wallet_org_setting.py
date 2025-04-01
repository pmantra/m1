from __future__ import annotations

import datetime
import io
from typing import Type

from flask import Response, flash, request, send_file
from flask_admin import expose
from flask_admin.actions import action
from flask_admin.contrib.sqla import form
from flask_admin.form import BaseForm
from wtforms import IntegerField, SelectField, fields, validators
from wtforms.validators import NumberRange

from admin.views.base import (
    AdminCategory,
    AdminViewT,
    MavenAuditedView,
    ReadOnlyFieldRule,
)
from admin.views.models.clinic import GlobalProcedureSelectField
from storage.connection import RoutingSQLAlchemy, db
from utils.csv_helpers import dict_to_csv
from utils.log import logger
from wallet.models.constants import BenefitTypes, EligibilityLossRule, WalletState
from wallet.models.reimbursement_organization_settings import (
    ReimbursementOrganizationSettings,
    ReimbursementOrgSettingCategoryAssociation,
    ReimbursementOrgSettingDxRequiredProcedures,
    ReimbursementOrgSettingExcludedProcedures,
    ReimbursementOrgSettingsExpenseType,
)
from wallet.models.reimbursement_wallet import ReimbursementWallet
from wallet.repository.reimbursement_wallet import ReimbursementWalletRepository
from wallet.services.reimbursement_wallet import ReimbursementWalletService
from wallet.utils.admin_helpers import org_setting_expense_type_config_form_data

log = logger(__name__)


class ReimbursementOrganizationSettingsForm(BaseForm):
    def validate(self, *args, **kwargs):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        is_valid = super().validate(*args, **kwargs)
        # Get the field values from the form
        direct_payment_enabled = self.direct_payment_enabled.data
        deductible_accumulation_enabled = self.deductible_accumulation_enabled.data
        debit_card_enabled = self.debit_card_enabled.data
        closed_network = self.closed_network.data
        allowed_reimbursement_categories = (
            self.allowed_reimbursement_categories.data
            if self.allowed_reimbursement_categories.data
            else None
        )

        # Validate run_out_days and eligibility_loss_rule
        run_out_days = self.run_out_days.data

        if run_out_days is not None and run_out_days < 0:
            flash("Run out days must be a non-negative integer.", "error")
            return False

        cycles_enabled = self._is_cycles_enabled(allowed_reimbursement_categories)

        try:
            self._debit_card_validations(
                direct_payment_enabled,
                deductible_accumulation_enabled,
                debit_card_enabled,
                cycles_enabled,
            )
            self._cycles_enabled_validations(
                direct_payment_enabled, closed_network, cycles_enabled
            )
        except ValueError as error:
            flash(message=str(error), category="error")
            return
        return is_valid

    @staticmethod
    def _is_cycles_enabled(allowed_reimbursement_categories) -> bool:  # type: ignore[no-untyped-def] # Function is missing a type annotation for one or more arguments
        if allowed_reimbursement_categories:
            current_or_future_plan = False
            cycles_enabled = False

            for category_assoc in allowed_reimbursement_categories:
                category = category_assoc.reimbursement_request_category
                plan = category.reimbursement_plan
                if plan and plan.start_date <= datetime.date.today() <= plan.end_date:
                    current_or_future_plan = True

                if category_assoc.benefit_type == BenefitTypes.CYCLE:
                    cycles_enabled = True

                if current_or_future_plan and cycles_enabled:
                    return True

        return False

    @staticmethod
    def _cycles_enabled_validations(
        direct_payment_enabled: bool, closed_network: bool, cycles_enabled: bool
    ) -> None:
        if cycles_enabled and not direct_payment_enabled:
            raise ValueError("If direct payment is disabled, cycles cannot be enabled.")

        if cycles_enabled and not closed_network:
            raise ValueError("If closed network is disabled, cycles cannot be enabled.")

    @staticmethod
    def _debit_card_validations(  # type: ignore[no-untyped-def] # Function is missing a type annotation
        direct_payment_enabled,
        deductible_accumulation_enabled,
        debit_card_enabled,
        cycles_enabled,
    ):
        if debit_card_enabled and direct_payment_enabled:
            raise ValueError(
                "Debit card and direct payment cannot be enabled together."
            )

        if debit_card_enabled and deductible_accumulation_enabled:
            raise ValueError(
                "Debit card and deductible accumulation cannot be enabled together."
            )

        if debit_card_enabled and cycles_enabled:
            raise ValueError(
                "Debit card and cycles cannot be enabled together. Org has an allowed category that has "
                "the benefit type of cycle."
            )


class ReimbursementOrganizationSettingsView(MavenAuditedView):
    create_permission = "create:reimbursement-organization-settings"
    edit_permission = "edit:reimbursement-organization-settings"
    delete_permission = "delete:reimbursement-organization-settings"
    read_permission = "read:reimbursement-organization-settings"

    required_capability = "admin_wallet_tools"  # type: ignore[assignment] # Incompatible types in assignment (expression has type "str", base class "AdminAuth" defined the type as "None")
    form_base_class = ReimbursementOrganizationSettingsForm
    edit_template = "reimbursement_org_settings_edit_template.html"
    column_list = (
        "id",
        "organization",
        "name",
        "allowed_reimbursement_categories",
        "benefit_overview_resource",
        "benefit_faq_resource",
        "started_at",
        "ended_at",
        "is_active",
        "taxation_status",
        "debit_card_enabled",
        "run_out_days",
        "eligibility_loss_rule",
    )
    column_filters = ["id", "organization.id", "organization.name", "taxation_status"]
    column_sortable_list = ("started_at", "ended_at", "taxation_status")
    form_excluded_columns = ("reimbursement_wallets", "created_at", "modified_at")
    form_overrides = {
        "run_out_days": IntegerField,
        "eligibility_loss_rule": SelectField,
        "required_tenure_days": IntegerField,
    }
    form_args = {
        "started_at": {"validators": (validators.DataRequired(),)},
        "run_out_days": {
            "validators": [validators.Optional(), NumberRange(min=0)],
            "description": "Number of days for run-out period (can be left empty)",
        },
        "eligibility_loss_rule": {
            "choices": [(rule.name, rule.value) for rule in EligibilityLossRule],
            "coerce": lambda name: EligibilityLossRule[name] if name else None,
        },
        "required_tenure_days": {
            "validators": [validators.Optional(), NumberRange(min=0)],
            "description": "Number of days an org requires members to be tenured for",
        },
    }

    def _contains_cycle_categories(request, form):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        if "allowed_reimbursement_categories" in form:
            categories = form.allowed_reimbursement_categories.data
            for category in categories:
                if (
                    isinstance(category, ReimbursementOrgSettingCategoryAssociation)
                    and category.benefit_type == BenefitTypes.CYCLE
                ):
                    return "Has Cycle Based Categories"
        return "No Cycle Based Categories"

    def on_form_prefill(self, form, id):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        super().on_form_prefill(form, id)
        if self.reimbursement_organization_setting_has_linked_wallet(id):
            # Add the disabled flag to the flags collection of the field, and add it as validation attribute to the
            # widget (which is a member variable of field).
            # The __call__ function of the base select class is invoked with kwargs. The __call__ function adds any
            # flags and their values on the containing field to the kwargs if the widget's validation attributes contain
            # the field name. These kwargs are then used to generate the html tag.
            form.allowed_members.flags.disabled = True
            form.allowed_members.widget.validation_attrs.append("disabled")

    form_rules = (
        "organization",
        "name",
        "benefit_overview_resource",
        "benefit_faq_resource",
        "survey_url",
        "required_track",
        "started_at",
        "ended_at",
        "debit_card_enabled",
        "direct_payment_enabled",
        "rx_direct_payment_enabled",
        "deductible_accumulation_enabled",
        "closed_network",
        "fertility_program_type",
        "fertility_allows_taxable",
        "payments_customer_id",
        "allowed_members",
        "excluded_procedures",
        "dx_required_procedures",
        "run_out_days",
        "eligibility_loss_rule",
        ReadOnlyFieldRule(
            "Credit based reimbursement request categories?", _contains_cycle_categories
        ),
        "required_tenure_days",
        "first_dollar_coverage",
        "expense_types",
        "allowed_reimbursement_categories",
    )
    inline_models = (
        (
            ReimbursementOrgSettingsExpenseType,
            {
                "form_columns": [
                    "id",
                    "expense_type",
                    "taxation_status",
                    "reimbursement_method",
                ]
            },
        ),
        (
            ReimbursementOrgSettingExcludedProcedures,
            {
                "form_excluded_columns": (
                    "reimbursement_organization_settings_id",
                    "modified_at",
                    "created_at",
                ),
                "form_columns": [
                    "id",
                    "global_procedure_id",
                ],
                "form_label": "Excluded Global Procedure",
                "column_labels": dict(
                    global_procedure_id="Global Procedure",
                ),
                "form_overrides": {
                    "global_procedure_id": GlobalProcedureSelectField,
                },
            },
        ),
        (
            ReimbursementOrgSettingDxRequiredProcedures,
            {
                "form_excluded_columns": (
                    "reimbursement_organization_settings_id",
                    "modified_at",
                    "created_at",
                ),
                "form_columns": [
                    "id",
                    "global_procedure_id",
                ],
                "form_label": "DX-Required Global Procedure",
                "column_labels": dict(
                    global_procedure_id="Global Procedure",
                ),
                "form_overrides": {
                    "global_procedure_id": GlobalProcedureSelectField,
                },
            },
        ),
    )

    @staticmethod
    def reimbursement_organization_setting_has_linked_wallet(id_: str) -> bool:
        return (
            id_  # type: ignore[return-value] # Incompatible return value type (got "Union[str, Literal[False], Any]", expected "bool")
            and id_.isdigit()
            and db.session.query(
                db.session.query(ReimbursementWallet.id)
                .filter(
                    ReimbursementWallet.reimbursement_organization_settings_id
                    == int(id_)
                )
                .exists()
            ).scalar()
        )

    @expose("/edit/", methods=("GET", "POST"))
    def edit_view(self):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        org_settings_id = request.args.get("id")
        org_settings = self.get_one(org_settings_id)
        self._template_args["run_out_days"] = org_settings.run_out_days
        self._template_args[
            "eligibility_loss_rule"
        ] = org_settings.eligibility_loss_rule
        ros_expense_types = ReimbursementOrgSettingsExpenseType.query.filter_by(
            reimbursement_organization_settings_id=org_settings_id
        ).all()
        reimbursement_categories = org_settings.allowed_reimbursement_categories
        form_data, errors = org_setting_expense_type_config_form_data(
            reimbursement_categories, ros_expense_types
        )
        self._template_args["form_data"] = form_data
        self._template_args["errors"] = errors
        return super().edit_view()

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

    @action(
        "bulk_expire_wallets",
        "Expire all wallets",
        "Are you sure you want to set all (QUALIFIED and RUNOUT) wallets to EXPIRED for this ROS?",
    )
    def bulk_expire_wallets(self, ids: list[str]) -> Response | None:
        if len(ids) > 1:
            flash(
                message="This action can only be performed against a single ROS",
                category="error",
            )
            return None
        wallet_repo = ReimbursementWalletRepository(session=db.session)
        wallet_service = ReimbursementWalletService(wallet_repo=wallet_repo)

        try:
            expired_metdata: list[dict] = wallet_service.expire_wallets_for_ros(
                ros_id=int(ids[0]),
                wallet_states={WalletState.QUALIFIED, WalletState.RUNOUT},
            )
            in_mem_buffer: io.BytesIO = dict_to_csv(dicts=expired_metdata)
        except Exception as e:
            log.exception(
                "Exception encountered while expiring wallets", ros_id=ids[0], exc=e
            )
            db.session.rollback()
            flash(
                message=f"Error while attempting to expire wallets for ROS: {ids[0]}",
                category="error",
            )
            return None
        else:
            db.session.commit()
            filename: str = (
                f"expired_wallets_{datetime.datetime.utcnow().isoformat()}.csv"
            )
            flash(
                message=f"Successfully expired {len(expired_metdata)} wallets for ROS: {ids[0]}",
                category="info",
            )
            flash(
                message=f"Downloading CSV of impacted wallets: {filename}",
                category="info",
            )

        return send_file(
            in_mem_buffer,
            mimetype="text/csv",
            as_attachment=True,
            download_name=filename,  # type: ignore[call-arg] # Unexpected keyword argument "download_name" for "send_file"
        )

    def scaffold_form(self):  # type: ignore[no-untyped-def]
        """
        Create form from the model.
        """
        converter = self.model_form_converter(self.session, self)
        form_class = form.get_form(
            self.model,
            converter,
            base_class=self.form_base_class,
            only=self.form_columns,
            exclude=self.form_excluded_columns,
            field_args=self.form_args,
            hidden_pk=True,
            ignore_hidden=self.ignore_hidden,
            extra_fields=self.form_extra_fields,
        )

        if self.inline_models:
            form_class = self.scaffold_inline_form_models(form_class)

        return form_class

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
            ReimbursementOrganizationSettings,
            session or db.session,
            category=category,
            name=name,
            endpoint=endpoint,
            **kwargs,
        )
