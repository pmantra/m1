from __future__ import annotations

import datetime
from typing import Type

from flask import flash, redirect, request
from flask_admin import expose
from flask_admin.contrib.sqla.filters import BooleanEqualFilter
from flask_admin.form import BaseForm
from maven import feature_flags
from sqlalchemy import func, or_
from sqlalchemy.orm import aliased

from admin.common import format_column_link
from admin.views.base import (
    AdminCategory,
    AdminViewT,
    AmountDisplayCentsInDollarsField,
    IsFilter,
    MavenAuditedView,
    cents_to_dollars_formatter,
)
from admin.views.models.clinic import GlobalProcedureSelectField
from authn.models.user import User
from cost_breakdown.wallet_balance_reimbursements import add_back_balance
from direct_payment.billing.billing_admin import BillingAdminService
from direct_payment.billing.billing_service import BillingService
from direct_payment.billing.constants import INTERNAL_TRUST_PAYMENT_GATEWAY_URL
from direct_payment.treatment_procedure.models.treatment_procedure import (
    TreatmentProcedure,
)
from direct_payment.treatment_procedure.repository.treatment_procedures_needing_questionnaires_repository import (
    TreatmentProceduresNeedingQuestionnairesRepository,
)
from payer_accumulator.accumulation_data_sourcer import AccumulationDataSourcer
from payer_accumulator.models.payer_list import Payer
from storage.connection import db
from storage.connector import RoutingSQLAlchemy
from wallet.models.member_benefit import MemberBenefit
from wallet.models.reimbursement_wallet import MemberHealthPlan
from wallet.models.reimbursement_wallet_benefit import ReimbursementWalletBenefit
from wallet.repository.health_plan import (
    HEALTH_PLAN_YOY_FLAG,
    OLD_BEHAVIOR,
    HealthPlanRepository,
)


class ProcedureWalletUserEmailFilter(IsFilter):
    def apply(self, query, value, alias=None):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        UserEmailAliased = aliased(User)
        return query.join(
            UserEmailAliased, TreatmentProcedure.member_id == UserEmailAliased.id
        ).filter(
            UserEmailAliased.email == value,
        )


class ProcedureWalletUserFirstNameFilter(IsFilter):
    def apply(self, query, value):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        UserFirstNameAliased = aliased(User)
        return query.join(
            UserFirstNameAliased,
            TreatmentProcedure.member_id == UserFirstNameAliased.id,
        ).filter(
            UserFirstNameAliased.first_name == value,
        )


class ProcedureWalletUserLastNameFilter(IsFilter):
    def apply(self, query, value):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        UserLastNameAliased = aliased(User)
        return query.join(
            UserLastNameAliased, TreatmentProcedure.member_id == UserLastNameAliased.id
        ).filter(
            UserLastNameAliased.last_name == value,
        )


class ProcedureWalletUserBenefitIdFilter(IsFilter):
    def apply(self, query, value):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        return (
            query.join(
                ReimbursementWalletBenefit,
                TreatmentProcedure.reimbursement_wallet_id
                == ReimbursementWalletBenefit.reimbursement_wallet_id,
            )
            .join(MemberBenefit, TreatmentProcedure.member_id == MemberBenefit.user_id)
            .filter(
                or_(
                    ReimbursementWalletBenefit.maven_benefit_id == value,
                    func.lower(MemberBenefit.benefit_id) == func.lower(value),
                )
            )
        )


def benefit_id_formatter(view, context, model, name) -> str | None:  # type: ignore[no-untyped-def] # Function is missing a type annotation
    return model.member_benefit and model.member_benefit.benefit_id


class MissingCostBreakdownFilter(BooleanEqualFilter):
    def apply(self, query, value, alias=None):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        if value == "1":
            return query.filter(TreatmentProcedure.cost_breakdown_id == None)
        else:
            return query.filter(TreatmentProcedure.cost_breakdown_id != None)


class TreatmentProcedureView(MavenAuditedView):
    required_capability = "admin_wallet_tools"  # type: ignore[assignment] # Incompatible types in assignment (expression has type "str", base class "AdminAuth" defined the type as "None")

    read_permission = "read:direct-payment-procedure"
    edit_permission = "edit:direct-payment-procedure"
    create_permission = "create:direct-payment-procedure"
    delete_permission = "delete:direct-payment-procedure"
    can_view_details = True

    column_default_sort = ("id", True)
    column_list = (
        "id",
        "procedure_name",
        "user.first_name",
        "user.last_name",
        "benefit_id",
        "fertility_clinic.name",
        "fertility_clinic_location.name",
        "member_id",
        "uuid",
        "reimbursement_wallet_id",
        "reimbursement_request_category_id",
        "fee_schedule_id",
        "global_procedure_id",
        "start_date",
        "end_date",
        "cost",
        "status",
        "cost_breakdown_id",
        "cancellation_reason",
        "cancelled_date",
        "completed_date",
    )
    column_labels = {
        "uuid": "Treatment Procedure UUID",
        "benefit_id": "Maven Benefit ID",
        "global_procedure_id": "Global Procedure",
        "user.first_name": "First Name",
        "user.last_name": "Last Name",
        "cost": "Cost ($)",
        "fertility_clinic.name": "Fertility Clinic Name",
        "fertility_clinic_location.name": "Fertility Clinic Location Name",
    }
    column_formatters = {
        "cost": cents_to_dollars_formatter,
        "member_id": lambda v, c, model, n: format_column_link(
            "user.details_view", model.member_id, str(model.member_id)
        ),
        "reimbursement_wallet_id": lambda v, c, model, n: format_column_link(
            "reimbursementwallet.details_view",
            model.reimbursement_wallet_id,
            str(model.reimbursement_wallet_id),
        ),
        "cost_breakdown_id": lambda v, c, model, n: format_column_link(
            "costbreakdown.details_view",
            model.cost_breakdown_id,
            str(model.cost_breakdown_id),
        ),
        "benefit_id": benefit_id_formatter,
    }
    column_filters = (
        "id",
        "uuid",
        "member_id",
        "reimbursement_wallet_id",
        "procedure_name",
        "cost_breakdown_id",
        "procedure_type",
        "status",
        ProcedureWalletUserBenefitIdFilter(None, "Benefit Id"),
        ProcedureWalletUserEmailFilter(None, "Member Email"),
        ProcedureWalletUserFirstNameFilter(None, "Member First Name"),
        ProcedureWalletUserLastNameFilter(None, "Member Last Name"),
        "fertility_clinic.name",
        "fertility_clinic_location.name",
        MissingCostBreakdownFilter(None, "Missing Cost Breakdown"),
    )

    form_columns = (
        "member_id",
        "reimbursement_wallet_id",
        "reimbursement_request_category_id",
        "fee_schedule_id",
        "global_procedure_id",
        "fertility_clinic_id",
        "fertility_clinic_location_id",
        "start_date",
        "end_date",
        "procedure_name",
        "cost",
        "status",
        "cancellation_reason",
        "cost_breakdown_id",
        "cancelled_date",
        "completed_date",
    )
    form_overrides = {
        "global_procedure_id": GlobalProcedureSelectField,
        "cost": AmountDisplayCentsInDollarsField,
    }
    details_template = "treatment_procedure_detail_template.html"

    def after_model_change(
        self,
        form: BaseForm,
        model: TreatmentProcedure,
        is_created: bool,
    ) -> None:
        if is_created:
            # If we create a new TreatmentProcedure, then we must add a row to the
            # treatment_procedures_needing_questionnaires table.
            TreatmentProceduresNeedingQuestionnairesRepository().create_tpnq_from_treatment_procedure_id(
                treatment_procedure_id=model.id
            )

    @expose("/refund_all_bills", methods=["POST"])
    def refund_all_bills(self):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        procedure_id = int(request.form.get("procedure_id"))  # type: ignore[arg-type] # Argument 1 to "int" has incompatible type "Optional[Any]"; expected "Union[str, Buffer, SupportsInt, SupportsIndex, SupportsTrunc]"

        svc = BillingService(
            session=db.session,
            # configured for internal trust
            payment_gateway_base_url=INTERNAL_TRUST_PAYMENT_GATEWAY_URL,
        )
        admin_svc = BillingAdminService()
        try:
            bills = admin_svc.create_clinic_reverse_transfer_bills_for_procedure(
                svc=svc, procedure_id=procedure_id
            )
            flash(
                f"Created and processed clinic reverse transfer bill {[(bill.id, bill.amount) for bill in bills]}, "
                "member and employer refund bills will be auto-created and processed after clinic bill processed",
                "success",
            )
        except Exception as e:
            flash(
                f"unable to create clinic reverse transfer bills, error {str(e)}",
                "error",
            )
        return redirect(self.get_url(".details_view", id=procedure_id))

    @expose("/revert_payer_accumulation", methods=["POST"])
    def revert_payer_accumulation(self):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        procedure_id = int(request.form.get("procedure_id"))  # type: ignore[arg-type] # Argument 1 to "int" has incompatible type "Optional[Any]"; expected "Union[str, Buffer, SupportsInt, SupportsIndex, SupportsTrunc]"
        procedure = TreatmentProcedure.query.get(procedure_id)

        if (
            feature_flags.str_variation(HEALTH_PLAN_YOY_FLAG, default=OLD_BEHAVIOR)
            != OLD_BEHAVIOR
        ):
            health_plan_repo = HealthPlanRepository(db.session)
            member_health_plan = (
                health_plan_repo.get_member_plan_by_wallet_and_member_id(
                    member_id=procedure.member_id,
                    wallet_id=procedure.reimbursement_wallet_id,
                    effective_date=datetime.datetime.fromordinal(
                        procedure.start_date.toordinal()
                    ),
                )
            )
        else:
            member_health_plan = MemberHealthPlan.query.filter(
                MemberHealthPlan.member_id == procedure.member_id
            ).one_or_none()

        if (
            not member_health_plan
            or not member_health_plan.employer_health_plan.reimbursement_organization_settings.deductible_accumulation_enabled
        ):
            flash("Member plan is not a deductible accumulation plan!", "error")
            return redirect(self.get_url(".details_view", id=procedure_id))

        payor = Payer.query.get(
            member_health_plan.employer_health_plan.benefits_payer_id
        )
        if not payor:
            flash("Invalid payer configured in member's employer health plan!", "error")
            return redirect(self.get_url(".details_view", id=procedure_id))

        payor_name = payor.payer_name

        data_sourcer = AccumulationDataSourcer(
            payer_name=payor_name, session=self.session
        )
        try:
            mapping = data_sourcer.revert_treatment_accumulation(procedure)
            if not mapping:
                flash(
                    "Revert Success! Treatment accumulation not sent to payer yet, updated all existing"
                    " mappings to skip status",
                    "success",
                )
            else:
                flash(
                    f"Revert Success! Successfully created a reverse request to payer accumulation, "
                    f"<id: {mapping.id}, deductible: {mapping.deductible}, oop_applied: {mapping.oop_applied}>"
                    "success",
                )
        except Exception as e:
            flash(
                f"Unable to revert payer accumulation, error {str(e)}",
                "error",
            )
        return redirect(self.get_url(".details_view", id=procedure_id))

    @expose("/add_back_wallet_balance", methods=["POST"])
    def add_back_wallet_balance(self):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        procedure_id = request.form.get("procedure_id")
        if not procedure_id:
            flash("No procedure id provided!", "error")
            return redirect(self.get_url(".details_view", id=procedure_id))

        procedure_id = int(procedure_id)
        procedure = TreatmentProcedure.query.get(procedure_id)

        try:
            add_back_balance(procedure)
            flash(
                "Revert Wallet Balance Success!" "success",
            )
        except Exception as e:
            flash(
                f"Revert Wallet Balance Failed, error {str(e)}" "error",
            )
        return redirect(self.get_url(".details_view", id=procedure_id))

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
        return cls(
            # type: ignore[call-arg] # Too many arguments for "object" #type: ignore[call-arg] # Unexpected keyword argument "category" for "object" #type: ignore[call-arg] # Unexpected keyword argument "name" for "object" #type: ignore[call-arg] # Unexpected keyword argument "endpoint" for "object"
            TreatmentProcedure,
            session or db.session,
            category=category,
            name=name,
            endpoint=endpoint,
            **kwargs,
        )
