from __future__ import annotations

import json
import traceback
from datetime import datetime, timezone
from decimal import Decimal
from typing import List, Optional, Tuple, Type

from flask import get_flashed_messages, jsonify, request
from flask_admin import BaseView, expose
from flask_admin.contrib.sqla.filters import BooleanEqualFilter
from flask_admin.model.helpers import get_mdict_item_or_list
from maven import feature_flags
from sqlalchemy import func
from sqlalchemy.orm import joinedload

from admin.common import format_column_link, format_column_search_link
from admin.common_cost_breakdown import (
    CalculatorRTE,
    CostBreakdownExtras,
    CostBreakdownPreviewRow,
    RTEOverride,
)
from admin.user_facing_errors import ErrorMessageImprover
from admin.views.auth import AdminAuth
from admin.views.base import (
    AdminCategory,
    AdminViewT,
    AmountDisplayCentsInDollarsField,
    MavenAuditedView,
    ViewExtras,
    cents_to_dollars_formatter,
)
from authn.models.user import User
from common.global_procedures.procedure import ProcedureService
from cost_breakdown.constants import AmountType, CostBreakdownType, Tier
from cost_breakdown.errors import CostBreakdownCalculatorValidationError
from cost_breakdown.models.cost_breakdown import (
    CostBreakdown,
    CostBreakdownData,
    CostBreakdownIrsMinimumDeductible,
    ExtraAppliedAmount,
)
from cost_breakdown.models.rte import EligibilityInfo, RTETransaction
from cost_breakdown.tasks.calculate_cost_breakdown import deduct_balance
from cost_breakdown.utils.helpers import (
    get_effective_date_from_cost_breakdown,
    is_plan_tiered,
)
from direct_payment.billing.repository import BillRepository
from direct_payment.billing.tasks.rq_job_create_bill import (
    create_member_and_employer_bill,
    create_member_bill,
)
from direct_payment.clinic.models.clinic import FertilityClinicLocation
from direct_payment.clinic.models.fee_schedule import FeeScheduleGlobalProcedures
from direct_payment.treatment_procedure.models.treatment_procedure import (
    TreatmentProcedure,
    TreatmentProcedureStatus,
    TreatmentProcedureType,
)
from direct_payment.treatment_procedure.utils.procedure_utils import (
    get_currency_balance_from_credit_wallet_balance,
)
from storage.connection import RoutingSQLAlchemy, db
from utils.log import logger
from utils.payments import convert_cents_to_dollars, convert_dollars_to_cents
from wallet.models.constants import BenefitTypes, ReimbursementRequestState
from wallet.models.reimbursement import ReimbursementRequest
from wallet.models.reimbursement_organization_settings import EmployerHealthPlan
from wallet.models.reimbursement_wallet import MemberHealthPlan, ReimbursementWallet
from wallet.repository.health_plan import (
    HEALTH_PLAN_YOY_FLAG,
    OLD_BEHAVIOR,
    HealthPlanRepository,
)
from wallet.utils.annual_questionnaire.utils import check_if_wallet_is_fdc_hdhp

log = logger(__name__)


class CostBreakdownView(MavenAuditedView):
    required_capability = "admin_wallet_tools"  # type: ignore[assignment] # Incompatible types in assignment (expression has type "str", base class "AdminAuth" defined the type as "None")

    read_permission = "read:direct-payment-cost-breakdown"

    column_list = (
        "id",
        "uuid",
        "treatment_procedure_uuid",
        "wallet_id",
        "member_id",
        "reimbursement_request_id",
        "total_member_responsibility",
        "total_employer_responsibility",
        "is_unlimited",
        "beginning_wallet_balance",
        "ending_wallet_balance",
        "deductible",
        "oop_applied",
        "hra_applied",
        "coinsurance",
        "copay",
        "overage_amount",
        "calc_config",
        "cost_breakdown_type",
        "amount_type",
        "rte_transaction.response",
        "rte_transaction.member_health_plan_id",
        "deductible_remaining",
        "oop_remaining",
        "family_deductible_remaining",
        "family_oop_remaining",
        "created_at",
    )
    column_filters = (
        "id",
        "treatment_procedure_uuid",
        "member_id",
        "wallet_id",
        "reimbursement_request_id",
        "rte_transaction.member_health_plan_id",
    )
    column_labels = {
        "rte_transaction.response": "RTE response",
        "rte_transaction.member_health_plan_id": "Member Health Plan ID",
        "is_unlimited": "Unlimited Coverage",
    }
    column_formatters = {
        # watch out for the fragility of search params like "flt2_9".
        "treatment_procedure_uuid": lambda v, c, model, n: format_column_search_link(
            "treatmentprocedure.index_view",
            "flt2_9",
            model.treatment_procedure_uuid,
            model.treatment_procedure_uuid,
        ),
        "wallet_id": lambda v, c, model, n: format_column_link(
            "reimbursementwallet.edit_view", model.wallet_id, str(model.wallet_id)
        ),
        "member_id": lambda v, c, model, n: format_column_link(
            "user.edit_view", model.member_id, str(model.member_id)
        ),
        "reimbursement_request_id": lambda v, c, model, n: format_column_link(
            "reimbursementrequest.edit_view",
            model.reimbursement_request_id,
            str(model.reimbursement_request_id),
        ),
        "rte_transaction.member_health_plan_id": lambda v, c, model, n: format_column_link(
            "memberhealthplan.edit_view",
            (
                model.rte_transaction.member_health_plan_id
                if model.rte_transaction
                else None
            ),
            (
                str(model.rte_transaction.member_health_plan_id)  # type: ignore[arg-type] # Argument 3 to "format_column_link" has incompatible type "Optional[str]"; expected "str"
                if model.rte_transaction
                else None
            ),
        ),
        "total_member_responsibility": cents_to_dollars_formatter,
        "total_employer_responsibility": cents_to_dollars_formatter,
        "beginning_wallet_balance": cents_to_dollars_formatter,
        "ending_wallet_balance": cents_to_dollars_formatter,
        "deductible": cents_to_dollars_formatter,
        "coinsurance": cents_to_dollars_formatter,
        "copay": cents_to_dollars_formatter,
        "overage_amount": cents_to_dollars_formatter,
        # only in detail view
        "oop_applied": cents_to_dollars_formatter,
        "hra_applied": cents_to_dollars_formatter,
        "oop_remaining": cents_to_dollars_formatter,
        "deductible_remaining": cents_to_dollars_formatter,
        "family_deductible_remaining": cents_to_dollars_formatter,
        "family_oop_remaining": cents_to_dollars_formatter,
    }

    def get_query(self):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        return super().get_query().options(joinedload(self.model.rte_transaction))

    details_template = "cost_breakdown_detail_view.html"

    @expose("/details/", methods=["GET"])
    def details_view(self):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        cb_id = get_mdict_item_or_list(request.args, "id")
        cb = super().get_one(id=cb_id)

        wallet_id = cb.wallet_id
        member_id = cb.member_id

        if (
            feature_flags.str_variation(HEALTH_PLAN_YOY_FLAG, default=OLD_BEHAVIOR)
            != OLD_BEHAVIOR
        ):
            health_plan_repo = HealthPlanRepository(db.session)
            effective_date = get_effective_date_from_cost_breakdown(cb)
            employer_health_plan = (
                health_plan_repo.get_employer_plan_by_wallet_and_member_id(
                    member_id=member_id,
                    wallet_id=wallet_id,
                    effective_date=effective_date,
                )
            )
        else:
            employer_health_plan = (
                EmployerHealthPlan.query.join(MemberHealthPlan)
                .filter(
                    MemberHealthPlan.reimbursement_wallet_id == wallet_id,
                    MemberHealthPlan.member_id == member_id,
                )
                .one_or_none()
            )

        self._template_args["employer_health_plan"] = employer_health_plan
        details_view = super().details_view()
        return details_view

    can_view_details = True
    column_default_sort = ("id", True)

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
            CostBreakdown,
            session or db.session,
            category=category,
            name=name,
            endpoint=endpoint,
            **kwargs,
        )


class CostBreakdownRecalculationView(
    AdminAuth, BaseView, ViewExtras, CostBreakdownExtras
):
    read_permission = "read:direct-payment-cost-breakdown-recalculation"
    edit_permission = "edit:direct-payment-cost-breakdown-recalculation"
    create_permission = "create:direct-payment-cost-breakdown-recalculation"
    delete_permission = "delete:direct-payment-cost-breakdown-recalculation"

    @expose("/")
    def index(self):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        return self.render("cost_breakdown_recalculation.html")

    @expose("/submit", methods=("POST",))
    def submit_cost_breakdown(self):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        cost_breakdown_processor = self._new_cost_breakdown_processor()
        error_improver = ErrorMessageImprover()
        form = request.form

        # expected input
        treatment_ids = form.get("treatment_ids")
        # TODO: consistent form data names between calculator forms
        to_cents = lambda string: int(Decimal(string) * 100)
        ytd_ind_oop = str(form.get("ind_oop", ""))
        ytd_family_oop = str(form.get("family_oop", ""))
        ind_oop_limit = str(form.get("ind_oop_limit", ""))
        family_oop_limit = str(form.get("family_oop_limit", ""))
        rte_override_data = RTEOverride(
            ytd_ind_deductible=str(form.get("ind_deductible", "")),
            ytd_ind_oop=ytd_ind_oop,
            ytd_family_deductible=str(form.get("family_deductible", "")),
            ytd_family_oop=ytd_family_oop,
            hra_remaining=str(form.get("hra_remaining", "")),
            ind_oop_remaining=str(to_cents(ind_oop_limit) - to_cents(ytd_ind_oop))
            if ind_oop_limit != "" and ytd_ind_oop != ""
            else "",
            family_oop_remaining=str(
                to_cents(family_oop_limit) - to_cents(ytd_family_oop)
            )
            if family_oop_limit != "" and ytd_family_oop != ""
            else "",
        )

        try:
            # validate input (functions from CostBreakdownExtras, raise ValueError)
            treatment_procedures = self._validate_treatment_procedures(treatment_ids)
            user = self._validate_user_for_procedures(treatment_procedures)
            wallet = self._validate_wallet_for_procedures(treatment_procedures, user)
            all_dates = [
                datetime.fromordinal(procedure.start_date.toordinal())
                for procedure in treatment_procedures
                if procedure.start_date is not None
            ]
            member_health_plan = self._validate_health_plan(
                start_dates=all_dates, user=user, wallet=wallet
            )
            should_override_rte_result = CalculatorRTE.validate_rte_override(
                member_health_plan, rte_override_data
            )
        except ValueError as e:
            return self._return_formatted_error(
                exception=e, error_improver=error_improver
            )

        try:
            # get cost breakdown for one or multiple treatment procedures
            cost_breakdowns: List[CostBreakdown] = []
            extra_applied_amount: ExtraAppliedAmount = ExtraAppliedAmount()
            extra_applied_amount.assumed_paid_procedures = []

            for treatment_procedure in treatment_procedures:
                # Set current procedure on the error message improver
                error_improver.procedure = treatment_procedure
                eligibility_info_override = None
                if should_override_rte_result:
                    # construct the mock-real-time-eligibility data
                    eligibility_info_override = CalculatorRTE.get_eligibility_info_override(
                        cost_breakdown_processor,
                        treatment_procedure,
                        member_health_plan,  # type: ignore[arg-type] # Argument "member_health_plan" has incompatible type "MemberHealthPlan | None"; # it's validated by should_override_rte_result
                        rte_override_data,
                    )

                wallet_balance = None
                benefit_type = wallet.category_benefit_type(
                    request_category_id=treatment_procedure.reimbursement_request_category_id
                )

                try:
                    if benefit_type == BenefitTypes.CYCLE:
                        # Convert a credit balance to a dollar balance to do temporary calculations with dollars
                        try:
                            wallet_balance = (
                                get_currency_balance_from_credit_wallet_balance(
                                    treatment_procedure=treatment_procedure
                                )
                            )
                        except TypeError as e:
                            raise ValueError(
                                "Cycle wallet balance failed. Make sure there is a cost credit value saved."
                            ) from e

                    # used for multi-procedure calcs
                    cost_breakdown_processor.extra_applied_amount = extra_applied_amount

                    # audit data
                    cost_breakdown_processor.calc_config = self.get_calc_config_audit(
                        extra_applied_amount=extra_applied_amount
                    )

                    # Get the actual cost breakdown!
                    cost_breakdown = cost_breakdown_processor.get_cost_breakdown_for_treatment_procedure(
                        wallet=wallet,
                        treatment_procedure=treatment_procedure,
                        store_to_db=False,
                        override_rte_result=eligibility_info_override,
                        wallet_balance=wallet_balance,
                    )
                    cost_breakdowns.append(cost_breakdown)
                    extra_applied_amount.oop_applied += cost_breakdown.oop_applied
                    extra_applied_amount.assumed_paid_procedures.append(
                        treatment_procedure.id
                    )
                except Exception as e:
                    return self._return_formatted_error(
                        exception=e, error_improver=error_improver
                    )
        except Exception as e:
            return self._return_formatted_error(
                exception=e, error_improver=error_improver
            )
        return self._format_submit_cost_breakdowns(
            treatment_procedures=treatment_procedures,
            cost_breakdowns=cost_breakdowns,
            member_health_plan=member_health_plan,
        )

    def _format_submit_cost_breakdowns(
        self,
        treatment_procedures: List[TreatmentProcedure],
        cost_breakdowns: List[CostBreakdown],
        member_health_plan: Optional[MemberHealthPlan],
    ) -> dict:
        if member_health_plan:
            plan_dict = {
                "member_id": member_health_plan.member_id,
                "plan_name": member_health_plan.employer_health_plan.name,
                "rx_integrated": member_health_plan.employer_health_plan.rx_integrated,
                "is_family_plan": member_health_plan.is_family_plan,
                "member_health_plan_id": str(member_health_plan.id),
            }
        else:
            plan_dict = {}
        return {
            "plan": plan_dict,
            "breakdowns": [
                {
                    **self._format_cost_breakdown(
                        initial_cost=tp.cost, cost_breakdown=cb
                    ),
                    **{
                        "treatment_id": tp.id,
                        "treatment_uuid": tp.uuid,
                        "treatment_type": tp.procedure_type.value,  # type: ignore[attr-defined] # "str" has no attribute "value"
                        "treatment_cost_credit": tp.cost_credit,
                    },
                }
                for tp, cb in zip(treatment_procedures, cost_breakdowns)
            ],
        }

    @expose("/confirm", methods=("POST",))
    def confirm_cost_breakdown(self):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        data = json.loads(request.data.decode())
        error_improver = ErrorMessageImprover()
        dollars_to_cents = lambda dollar: int(Decimal(dollar) * 100) if dollar else 0

        cost_breakdown_rows: List[CostBreakdown] = []
        cost_breakdowns = data["breakdowns"]
        to_return = []
        for cost_breakdown in cost_breakdowns:
            treatment_uuid = cost_breakdown["treatment_uuid"]
            treatment_procedure = TreatmentProcedure.query.filter(
                TreatmentProcedure.uuid == treatment_uuid
            ).one_or_none()
            error_improver.procedure = treatment_procedure
            if not treatment_procedure:
                return {"error": "Invalid treatment procedure id"}
            wallet_id = treatment_procedure.reimbursement_wallet_id
            wallet = ReimbursementWallet.query.get(wallet_id)
            try:
                cost_breakdown_row = CostBreakdown(
                    treatment_procedure_uuid=treatment_uuid,
                    wallet_id=wallet_id,
                    member_id=treatment_procedure.member_id,
                    total_member_responsibility=dollars_to_cents(
                        cost_breakdown["total_member_responsibility"]
                    ),
                    total_employer_responsibility=dollars_to_cents(
                        cost_breakdown["total_employer_responsibility"]
                    ),
                    is_unlimited=cost_breakdown["is_unlimited"],
                    beginning_wallet_balance=dollars_to_cents(
                        cost_breakdown["beginning_wallet_balance"]
                    ),
                    ending_wallet_balance=dollars_to_cents(
                        cost_breakdown["ending_wallet_balance"]
                    ),
                    deductible=dollars_to_cents(cost_breakdown["deductible"]),
                    deductible_remaining=dollars_to_cents(
                        cost_breakdown["deductible_remaining"]
                    ),
                    family_deductible_remaining=dollars_to_cents(
                        cost_breakdown["family_deductible_remaining"]
                    ),
                    coinsurance=dollars_to_cents(cost_breakdown["coinsurance"]),
                    copay=dollars_to_cents(cost_breakdown["copay"]),
                    oop_applied=dollars_to_cents(cost_breakdown["oop_applied"]),
                    hra_applied=cost_breakdown["hra_applied"],
                    oop_remaining=dollars_to_cents(cost_breakdown["oop_remaining"]),
                    family_oop_remaining=dollars_to_cents(
                        cost_breakdown["family_oop_remaining"]
                    ),
                    overage_amount=dollars_to_cents(cost_breakdown["overage_amount"]),
                    amount_type=(
                        AmountType(cost_breakdown["amount_type"])
                        if cost_breakdown["amount_type"]
                        else None
                    ),
                    cost_breakdown_type=(
                        CostBreakdownType(cost_breakdown["cost_breakdown_type"])
                        if cost_breakdown["cost_breakdown_type"]
                        else None
                    ),
                    rte_transaction_id=cost_breakdown["rte_transaction_id"],
                    calc_config=cost_breakdown["calc_config"],
                )
                db.session.add(cost_breakdown_row)
                db.session.commit()

                treatment_procedure.cost_breakdown_id = cost_breakdown_row.id
                db.session.add(treatment_procedure)
                db.session.commit()

                cost_breakdown_rows.append(cost_breakdown_row)

                # also trigger bill creation
                if treatment_procedure.status in [
                    TreatmentProcedureStatus.COMPLETED,
                    TreatmentProcedureStatus.PARTIALLY_COMPLETED,
                ]:
                    create_member_and_employer_bill(
                        treatment_procedure_id=treatment_procedure.id,
                        cost_breakdown_id=cost_breakdown_row.id,
                        wallet_id=wallet_id,
                        treatment_procedure_status=treatment_procedure.status,
                    )
                else:
                    create_member_bill(
                        treatment_procedure_id=treatment_procedure.id,
                        cost_breakdown_id=cost_breakdown_row.id,
                        wallet_id=wallet_id,
                        treatment_procedure_status=treatment_procedure.status,
                    )
                deduct_balance(
                    treatment_procedure=treatment_procedure,
                    cost_breakdown=cost_breakdown_row,
                    wallet=wallet,
                )
            except Exception as e:
                return self._return_formatted_error(
                    exception=e, error_improver=error_improver
                )
            bill_repo = BillRepository(session=db.session)
            bills = bill_repo.get_by_cost_breakdown_ids([cost_breakdown_row.id])
            to_return.extend(
                {
                    "cost_breakdown_uuid": cost_breakdown_row.uuid,
                    "bill_id": bill.id,
                    "bill_amount": convert_cents_to_dollars(bill.amount),
                    "bill_payer_type": bill.payor_type.value,
                    "treatment_id": bill.procedure_id,
                }
                for bill in bills
            )
        return {"bills": to_return}

    @expose("/procedurelist", methods=("GET",))
    def get_procedure_list(self):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        procedure_client = ProcedureService(internal=True)
        valid_global_procedures = procedure_client.list_all_procedures(
            headers=request.headers  # type: ignore[arg-type] # Argument "headers" to "list_all_procedures" of "ProcedureService" has incompatible type "EnvironHeaders"; expected "Optional[Mapping[str, str]]"
        )
        # Sort global procedures alphabetically by name
        valid_global_procedures = sorted(
            valid_global_procedures, key=lambda gp: gp["name"]  # type: ignore[typeddict-item] # TypedDict "PartialProcedure" has no key "name"
        )
        valid_global_procedures = [
            (gp["id"], gp["name"]) for gp in valid_global_procedures  # type: ignore[typeddict-item] # TypedDict "PartialProcedure" has no key "id" #type: ignore[typeddict-item] # TypedDict "PartialProcedure" has no key "name"
        ]
        return jsonify(valid_global_procedures)

    @expose("/cliniclocationlist", methods=("GET",))
    def get_clinic_list(self):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        clinic_locations = FertilityClinicLocation.query.all()
        return jsonify(
            [
                (clinic_location.id, clinic_location.name)
                for clinic_location in clinic_locations
            ]
        )

    @expose("/multipleprocedures/submit", methods=("POST",))
    def submit_multiple_procedures(self):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        form_data = request.json if request.is_json else {}
        error_improver = ErrorMessageImprover()
        user_id = int(form_data.get("userId"))
        procedures: List[dict] = form_data.get("procedures")
        ind_oop_limit = str(form_data.get("individualOopLimit", ""))
        family_oop_limit = str(form_data.get("familyOopLimit", ""))
        ytd_ind_oop = str(form_data.get("individualOop", ""))
        ytd_family_oop = str(form_data.get("familyOop", ""))
        # TODO: consistent form data names between calculator forms
        to_cents = lambda string: int(Decimal(string) * 100)
        rte_override_data = RTEOverride(
            ytd_ind_deductible=str(form_data.get("individualDeductible", "")),
            ytd_ind_oop=ytd_ind_oop,
            ytd_family_deductible=str(form_data.get("familyDeductible", "")),
            ytd_family_oop=ytd_family_oop,
            hra_remaining=str(form_data.get("hraRemaining", "")),
            ind_oop_remaining=str(to_cents(ind_oop_limit) - to_cents(ytd_ind_oop))
            if ind_oop_limit != "" and ytd_ind_oop != ""
            else "",
            family_oop_remaining=str(
                to_cents(family_oop_limit) - to_cents(ytd_family_oop)
            )
            if family_oop_limit != "" and ytd_family_oop != ""
            else "",
        )
        try:
            member = self._validate_user(user_id)
            wallet = self._validate_wallet(member.id)

            direct_payment_category = wallet.get_direct_payment_category
            if not direct_payment_category:
                raise CostBreakdownCalculatorValidationError(
                    "Could not find wallet direct payment category"
                )
            benefit_type = wallet.category_benefit_type(
                request_category_id=direct_payment_category.id
            )

            expected_start_dates: List[str] = [
                procedure.get("start_date")
                for procedure in procedures
                if procedure.get("start_date") != ""
            ]
            if len(expected_start_dates) != len(procedures):
                log.error("Missing Expected Dates", dates=expected_start_dates)
                raise ValueError(
                    "Missing start dates. Please provide a start date for all procedures."
                )
            try:
                procedure_start_dates: List[datetime] = [
                    datetime.strptime(date, "%Y-%m-%d") for date in expected_start_dates
                ]
            except ValueError:
                log.error("Invalid Expected Dates", dates=expected_start_dates)
                raise CostBreakdownCalculatorValidationError(
                    "Invalid start dates provided for one or more procedures."
                )
            member_health_plan = self._validate_health_plan(
                start_dates=procedure_start_dates, user=member, wallet=wallet
            )

            should_override_rte_result = CalculatorRTE.validate_rte_override(
                member_health_plan, rte_override_data
            )
            # End validation here

            extra_applied_amount = self._get_extra_applied_amount(
                member=member,
                benefit_type=benefit_type,  # type: ignore[arg-type] # Argument "benefit_type" has incompatible type "BenefitTypes | None"; expected "BenefitTypes"
            )

            cost_breakdown_rows: List[CostBreakdownPreviewRow] = []
            hra_applied = 0
            cost_breakdown_processor = self._new_cost_breakdown_processor()
            cost_breakdown_processor.calc_config = self.get_calc_config_audit(
                extra_applied_amount=extra_applied_amount, should_include_pending=True
            )
            for procedure in procedures:
                given_procedure_type = procedure.get("type")
                effective_start_date = (
                    datetime.strptime(procedure.get("start_date"), "%Y-%m-%d")  # type: ignore[arg-type] # already validated string further up
                    if procedure.get("start_date")
                    else datetime.now()  # noqa # comparison of naive and non-naive datetimes
                )
                # no real treatment procedures here, so we pass a descriptive string
                global_procedure_name: str = procedure.get(
                    "procedure", {"name": ""}
                ).get("name")
                error_improver.procedure = f"global procedure {global_procedure_name}"
                global_procedure_id = procedure.get("procedure").get("id")  # type: ignore[union-attr] # Item "None" of "Optional[Any]" has no attribute "get"
                global_procedure = cost_breakdown_processor.procedure_service_client.get_procedure_by_id(
                    procedure_id=global_procedure_id, headers=request.headers  # type: ignore[arg-type] # Argument "headers" to "get_procedure_by_id" of "ProcedureService" has incompatible type "EnvironHeaders"; expected "Optional[Mapping[str, str]]"
                )
                start_date = procedure.get(
                    "start_date",
                    datetime.now(),  # noqa necessary for naive datetime comparison
                )
                if isinstance(start_date, str):
                    try:
                        start_date = datetime.strptime(start_date, "%Y-%m-%d")
                    except ValueError:
                        start_date = datetime.now(timezone.utc)

                params = dict(
                    member_id=user_id,
                    wallet=wallet,
                    reimbursement_category=direct_payment_category,
                    global_procedure_id=global_procedure_id,
                    # before this date == created at / completed at, which we are currently not entering
                    before_this_date=datetime.now(timezone.utc),
                    asof_date=start_date,
                    service_start_date=start_date.date(),
                )
                if given_procedure_type == "medical":
                    if procedure.get("cost"):
                        cost = convert_dollars_to_cents(procedure.get("cost"))
                    else:
                        clinic_location_id = int(
                            procedure.get("clinic_location").get("id")  # type: ignore[union-attr] # Item "None" of "Optional[Any]" has no attribute "get"
                        )
                        clinic_location = FertilityClinicLocation.query.get(
                            clinic_location_id
                        )
                        clinic = clinic_location.fertility_clinic
                        fee_schedule_gp = FeeScheduleGlobalProcedures.query.filter(
                            FeeScheduleGlobalProcedures.global_procedure_id
                            == global_procedure_id,
                            FeeScheduleGlobalProcedures.fee_schedule_id
                            == clinic.fee_schedule_id,
                        ).one_or_none()
                        cost = fee_schedule_gp.cost
                    procedure_type = TreatmentProcedureType.MEDICAL
                    params.update(procedure_type=TreatmentProcedureType.MEDICAL)
                    params.update(cost=cost)
                elif given_procedure_type == "pharmacy":
                    procedure_type = TreatmentProcedureType.PHARMACY
                    cost = convert_dollars_to_cents(procedure.get("cost"))
                    params.update(procedure_type=TreatmentProcedureType.PHARMACY)
                    params.update(cost=cost)
                else:
                    raise CostBreakdownCalculatorValidationError(
                        "Invalid procedure type"
                    )

                if benefit_type == BenefitTypes.CYCLE:
                    # if it's cycle based wallet, find wallet balance in currency,
                    # if credit balance is smaller than procedure credit, then wallet balance is prorated amount of the cost,
                    # if credit balance is equal or greater than procedure credit, then wallet balance is tp cost.
                    credit_balance = wallet.available_credit_amount_by_category
                    category_credit_balance = credit_balance.get(
                        direct_payment_category.id
                    )
                    if not global_procedure["credits"]:  # type: ignore[index,typeddict-item] # Value of type "Union[GlobalProcedure, PartialProcedure, None]" is not indexable #type: ignore[typeddict-item] # TypedDict "PartialProcedure" has no key "credits"
                        prorated_amount = 1
                    else:
                        prorated_amount = min(  # type: ignore[assignment]
                            category_credit_balance / global_procedure["credits"], 1  # type: ignore[index,typeddict-item] # Value of type "Union[GlobalProcedure, PartialProcedure, None]" is not indexable #type: ignore[typeddict-item] # TypedDict "PartialProcedure" has no key "credits"
                        )
                    wallet_balance = prorated_amount * cost
                    params.update(wallet_balance_override=wallet_balance)

                cost_breakdown_processor.extra_applied_amount = extra_applied_amount
                tier_override_raw = procedure.get("tier")
                tier = Tier(int(tier_override_raw)) if tier_override_raw else None
                if member_health_plan:
                    if (
                        is_plan_tiered(ehp=member_health_plan.employer_health_plan)
                        and not tier
                    ):
                        clinic_location = None
                        if procedure_type == TreatmentProcedureType.MEDICAL:
                            clinic_location_id = int(
                                procedure.get("clinic_location").get("id")  # type: ignore[union-attr] # Item "None" of "Optional[Any]" has no attribute "get"
                            )
                            clinic_location = FertilityClinicLocation.query.get(
                                clinic_location_id
                            )
                        tier = CalculatorRTE._get_treatment_procedure_calculation_tier(
                            employer_health_plan=member_health_plan.employer_health_plan,
                            treatment_procedure_type=procedure_type,
                            fertility_clinic_location=clinic_location,
                            start_date=effective_start_date.date(),  # noqa
                        )
                params.update(tier=tier)

                if not member_health_plan:
                    fdc_hdhp_check = check_if_wallet_is_fdc_hdhp(
                        wallet=wallet,
                        user_id=user_id,
                        effective_date=effective_start_date,
                    )
                    params.update(fdc_hdhp_check=fdc_hdhp_check)

                data_service = cost_breakdown_processor.cost_breakdown_data_service_from_treatment_procedure(
                    **params
                )
                if member_health_plan and should_override_rte_result:
                    cost_sharing_category = CalculatorRTE._cost_sharing_from_procedure(
                        cost_breakdown_processor=cost_breakdown_processor,
                        global_procedure_id=global_procedure_id,
                    )
                    employer_health_plan: EmployerHealthPlan = (
                        member_health_plan.employer_health_plan
                    )
                    if employer_health_plan.is_hdhp:
                        eligibility_info_override = EligibilityInfo(
                            individual_oop=to_cents(rte_override_data.ytd_ind_oop)
                            if rte_override_data.ytd_ind_oop
                            else None,
                            individual_oop_remaining=to_cents(
                                rte_override_data.ind_oop_remaining
                            )
                            if rte_override_data.ind_oop_remaining
                            else None,
                            family_oop=to_cents(rte_override_data.ytd_family_oop)
                            if rte_override_data.ytd_family_oop
                            else None,
                            family_oop_remaining=to_cents(
                                rte_override_data.family_oop_remaining
                            )
                            if rte_override_data.family_oop_remaining
                            else None,
                        )
                    else:
                        eligibility_info_override = (
                            CalculatorRTE._eligibility_info_override(
                                member_health_plan=member_health_plan,
                                procedure_type=procedure_type,
                                cost_sharing_category=cost_sharing_category,
                                rte_override_data=rte_override_data,
                                tier=tier,
                            )
                        )
                    data_service.override_rte_result = eligibility_info_override
                cost_breakdown_data: CostBreakdownData = (
                    data_service.get_cost_breakdown_data()
                )

                cost_breakdown_row = CostBreakdownPreviewRow(
                    member_id=str(user_id),
                    total_member_responsibility=cost_breakdown_data.total_member_responsibility,
                    total_employer_responsibility=cost_breakdown_data.total_employer_responsibility,
                    is_unlimited=cost_breakdown_data.is_unlimited,
                    beginning_wallet_balance=cost_breakdown_data.beginning_wallet_balance,
                    ending_wallet_balance=cost_breakdown_data.ending_wallet_balance,
                    deductible=cost_breakdown_data.deductible,
                    oop_applied=cost_breakdown_data.oop_applied,
                    deductible_remaining=cost_breakdown_data.deductible_remaining,
                    oop_remaining=cost_breakdown_data.oop_remaining,
                    family_deductible_remaining=cost_breakdown_data.family_deductible_remaining,
                    family_oop_remaining=cost_breakdown_data.family_oop_remaining,
                    coinsurance=cost_breakdown_data.coinsurance,
                    copay=cost_breakdown_data.copay,
                    cost=cost,
                    amount_type=cost_breakdown_data.amount_type,
                    cost_breakdown_type=cost_breakdown_data.cost_breakdown_type,
                    hra_applied=cost_breakdown_data.hra_applied,
                    overage_amount=cost_breakdown_data.overage_amount,
                    procedure_name=global_procedure["name"],  # type: ignore[index,typeddict-item] # Value of type "Union[GlobalProcedure, PartialProcedure, None]" is not indexable #type: ignore[typeddict-item] # TypedDict "PartialProcedure" has no key "name"
                    cost_sharing_category=global_procedure["cost_sharing_category"],  # type: ignore[index,typeddict-item] # Value of type "Union[GlobalProcedure, PartialProcedure, None]" is not indexable #type: ignore[typeddict-item] # TypedDict "PartialProcedure" has no key "cost_sharing_category"
                    procedure_type=procedure_type.value,
                )

                cost_breakdown_rows.append(cost_breakdown_row)
                extra_applied_amount.oop_applied += cost_breakdown_data.oop_applied
                # beginning wallet balance of cycle based wallet is always treatment cost
                if benefit_type == BenefitTypes.CURRENCY:
                    extra_applied_amount.wallet_balance_applied += (
                        cost_breakdown_data.total_employer_responsibility
                    )

                # override initial hra here for loop purposes
                rte_override_data.hra_remaining = str(
                    max(
                        CalculatorRTE.convert_string_to_int(
                            rte_override_data.hra_remaining
                        )
                        - hra_applied,
                        0,
                    )
                )
        except Exception as e:
            return self._return_formatted_error(
                exception=e, error_improver=error_improver
            )
        return self._format_cost_breakdown_results(
            cost_breakdown_rows, member_health_plan
        )

    @staticmethod
    def _get_extra_applied_amount(
        member: User, benefit_type: BenefitTypes | None
    ) -> ExtraAppliedAmount:
        """
        For currency wallet, we deduct all previous scheduled treatment procedures' employer responsibility
        from the wallet balance to get the real "available balance".
        For cycle based wallet, we always use treatment cost as beginning wallet balance.
        """
        if benefit_type == BenefitTypes.CURRENCY:
            scheduled_wallet_balance_applied = (
                db.session.query(
                    func.coalesce(
                        func.sum(CostBreakdown.total_employer_responsibility), 0
                    )
                )
                .join(
                    TreatmentProcedure,
                    TreatmentProcedure.cost_breakdown_id == CostBreakdown.id,
                )
                .filter(
                    TreatmentProcedure.status == TreatmentProcedureStatus.SCHEDULED,
                    TreatmentProcedure.member_id == member.id,
                )
                .scalar()
            )

            extra_applied_amount: ExtraAppliedAmount = ExtraAppliedAmount(
                wallet_balance_applied=scheduled_wallet_balance_applied,
            )
        else:
            extra_applied_amount = ExtraAppliedAmount()
        return extra_applied_amount

    @expose("/linkreimbursement", methods=("POST",))
    def link_reimbursement(self):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        try:
            data = request.get_json()
            # Extract data from request
            reimbursement_id = str(data.get("reimbursementRequestId"))
            member_id = str(data.get("memberId"))
            total_member_responsibility = data.get("memberResponsibility")
            total_employer_responsibility = data.get("employerResponsibility")
            is_unlimited = data.get("isUnlimited")
            beginning_wallet_balance = data.get("beginningWalletBalance")
            ending_wallet_balance = data.get("endingWalletBalance")
            deductible = data.get("deductible")
            oop_applied = data.get("oopApplied")
            copay = data.get("copay")
            coinsurance = data.get("coinsurance")
            hra_applied = data.get("hraApplied")
            overage_amount = data.get("overageAmount")
            amount_type = data.get("amountType")
            cost_breakdown_type = data.get("costBreakdownType")
            deductible_remaining = data.get("deductibleRemaining")
            oop_remaining = data.get("oopRemaining")
            family_deductible_remaining = data.get("familyDeductibleRemaining")
            family_oop_remaining = data.get("familyOopRemaining")
            description = data.get("description")
            # Validate required fields
            missing_fields = [
                field
                for field, value in {
                    "reimbursement_id": reimbursement_id,
                    "total_employer_responsibility": total_employer_responsibility,
                    "total_member_responsibility": total_member_responsibility,
                    "deductible": deductible,
                    "oop_applied": oop_applied,
                }.items()
                if value is None
            ]
            if missing_fields:
                return {"message": "Missing required fields"}, 400

            # Find the reimbursement request
            reimbursement = db.session.query(ReimbursementRequest).get(
                int(reimbursement_id)
            )
            if not reimbursement:
                return {"error": "Invalid reimbursement ID"}, 404
            if reimbursement.state != ReimbursementRequestState.NEW:
                return {"error": "Reimbursement Request is not in a NEW state"}, 400
            if (
                feature_flags.str_variation(HEALTH_PLAN_YOY_FLAG, default=OLD_BEHAVIOR)
                != OLD_BEHAVIOR
            ):
                health_plan_repo = HealthPlanRepository(db.session)
                member_health_plan = (
                    health_plan_repo.get_member_plan_by_wallet_and_member_id(
                        member_id=int(member_id),
                        wallet_id=reimbursement.reimbursement_wallet_id,
                        effective_date=reimbursement.service_start_date,
                    )
                )
            else:
                member_health_plan = (
                    MemberHealthPlan.query.filter(  # noqa
                        MemberHealthPlan.member_id == int(member_id),
                        MemberHealthPlan.reimbursement_wallet_id
                        == reimbursement.reimbursement_wallet_id,
                    )
                    .options(joinedload(MemberHealthPlan.employer_health_plan))
                    .one_or_none()
                )
            if not member_health_plan:
                raise CostBreakdownCalculatorValidationError(
                    "Missing a member health plan."
                )
            # Link the cost breakdown to the reimbursement request
            dollars_to_cents = (
                lambda dollar: int(Decimal(dollar) * 100) if dollar else 0
            )
            cost_breakdown_row = CostBreakdown(
                reimbursement_request_id=int(reimbursement_id),
                wallet_id=reimbursement.reimbursement_wallet_id,
                member_id=int(member_id),
                is_unlimited=is_unlimited,
                total_member_responsibility=dollars_to_cents(
                    total_member_responsibility
                ),
                total_employer_responsibility=dollars_to_cents(
                    total_employer_responsibility
                ),
                beginning_wallet_balance=dollars_to_cents(beginning_wallet_balance),
                ending_wallet_balance=dollars_to_cents(ending_wallet_balance),
                deductible=dollars_to_cents(deductible),
                oop_applied=dollars_to_cents(oop_applied),
                coinsurance=dollars_to_cents(coinsurance),
                copay=dollars_to_cents(copay),
                hra_applied=dollars_to_cents(hra_applied),
                overage_amount=dollars_to_cents(overage_amount),
                amount_type=(AmountType(amount_type) if amount_type else None),
                cost_breakdown_type=(
                    CostBreakdownType(cost_breakdown_type)
                    if cost_breakdown_type
                    else None
                ),
                deductible_remaining=dollars_to_cents(deductible_remaining),
                oop_remaining=dollars_to_cents(oop_remaining),
                family_deductible_remaining=dollars_to_cents(
                    family_deductible_remaining
                ),
                family_oop_remaining=dollars_to_cents(family_oop_remaining),
            )
            # Save changes
            self.update_reimbursement_request_on_cost_breakdown(
                member_id=int(member_id),
                reimbursement_request=reimbursement,
                cost_breakdown=cost_breakdown_row,
                member_health_plan=member_health_plan,
                cost_breakdown_description=description,
            )
            messages = get_flashed_messages(with_categories=True)
            return {
                "message": "Successfully linked cost breakdown to reimbursement request",
                "flash_messages": messages,
                "status": "success",
            }, 200

        except Exception:
            log.error(
                "Error:linking cost breakdown to reimbursement request",
                exception=traceback.format_exc(),
            )
            messages = get_flashed_messages(with_categories=True)
            return {
                "error": "Failed to link cost breakdown to reimbursement request",
                "flash_messages": messages,
                "status": "error",
            }, 500

    @expose("/check_existing/<int:reimbursement_id>", methods=("GET",))
    def check_existing_breakdown(self, reimbursement_id):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        try:
            existing = (
                db.session.query(CostBreakdown)
                .filter(CostBreakdown.reimbursement_request_id == reimbursement_id)
                .first()
            )
            return {"exists": existing is not None}, 200
        except Exception:
            log.error(
                "Error checking existing cost breakdown",
                exception=traceback.format_exc(),
            )
            return {"error": "Failed to check existing breakdown"}, 500

    def _format_cost_breakdown_results(
        self,
        cost_breakdown_rows: List[CostBreakdownPreviewRow],
        member_health_plan: Optional[MemberHealthPlan],
    ) -> dict:
        cents_to_dollars = lambda cents: Decimal(cents) / 100 if cents else 0

        total_cost: int = 0
        total_deductible: int = 0
        total_oop_applied: int = 0
        total_coinsurance: int = 0
        total_copay: int = 0
        total_not_covered: int = 0
        total_hra_applied: int = 0
        total_member_responsibility: int = 0
        total_employer_responsibility: int = 0
        deductible_remaining = cents_to_dollars(
            cost_breakdown_rows[-1].deductible_remaining
        )
        oop_remaining = cents_to_dollars(cost_breakdown_rows[-1].oop_remaining)
        family_deductible_remaining = cents_to_dollars(
            cost_breakdown_rows[-1].family_deductible_remaining
        )
        family_oop_remaining = cents_to_dollars(
            cost_breakdown_rows[-1].family_oop_remaining
        )
        for cbr in cost_breakdown_rows:
            total_cost += cbr.cost
            total_deductible += cbr.deductible
            total_oop_applied += cbr.oop_applied
            total_coinsurance += cbr.coinsurance
            total_copay += cbr.copay
            total_not_covered += cbr.overage_amount
            total_member_responsibility += cbr.total_member_responsibility
            total_employer_responsibility += cbr.total_employer_responsibility
            total_hra_applied += cbr.hra_applied
        res = {
            "plan": {
                "name": (
                    member_health_plan.employer_health_plan.name
                    if member_health_plan
                    else "N/A"
                ),
                "rxIntegrated": (
                    member_health_plan.employer_health_plan.rx_integrated
                    if member_health_plan
                    else "N/A"
                ),
                "memberId": str(cost_breakdown_rows[0].member_id),
            },
            "total": {
                "cost": cents_to_dollars(total_cost),
                "deductible": cents_to_dollars(total_deductible),
                "oopApplied": cents_to_dollars(total_oop_applied),
                "coinsurance": cents_to_dollars(total_coinsurance),
                "copay": cents_to_dollars(total_copay),
                "notCovered": cents_to_dollars(total_not_covered),
                "hraApplied": cents_to_dollars(total_hra_applied),
                "memberResponsibility": cents_to_dollars(total_member_responsibility),
                "employerResponsibility": cents_to_dollars(
                    total_employer_responsibility
                ),
                "beginningWalletBalance": cents_to_dollars(
                    cost_breakdown_rows[0].beginning_wallet_balance
                ),
                "endingWalletBalance": cents_to_dollars(
                    cost_breakdown_rows[-1].ending_wallet_balance
                ),
                "deductibleRemaining": deductible_remaining,
                "oopRemaining": oop_remaining,
                "familyDeductibleRemaining": family_deductible_remaining,
                "familyOopRemaining": family_oop_remaining,
                "amountType": cost_breakdown_rows[0].amount_type.value,
                "costBreakdownType": cost_breakdown_rows[0].cost_breakdown_type.value,
            },
            "breakdowns": [
                {
                    "memberResponsibility": cents_to_dollars(
                        cbr.total_member_responsibility
                    ),
                    "employerResponsibility": cents_to_dollars(
                        cbr.total_employer_responsibility
                    ),
                    "deductible": cents_to_dollars(cbr.deductible),
                    "oopApplied": cents_to_dollars(cbr.oop_applied),
                    "cost": cents_to_dollars(cbr.cost),
                    "procedureName": cbr.procedure_name,
                    "procedureType": cbr.procedure_type,
                    "costSharingCategory": cbr.cost_sharing_category,
                    "coinsurance": cents_to_dollars(cbr.coinsurance),
                    "copay": cents_to_dollars(cbr.copay),
                    "overageAmount": cents_to_dollars(cbr.overage_amount),
                    "hraApplied": cents_to_dollars(cbr.hra_applied),
                }
                for cbr in cost_breakdown_rows
            ],
        }
        return res

    def _return_formatted_error(
        self, exception: Exception, error_improver: ErrorMessageImprover
    ) -> Tuple[dict, int]:
        error_message = error_improver.get_error_message(
            error=exception, formatter=ErrorMessageImprover.format_as_admin_url
        )
        log.error(
            "The Cost Breakdown Calculator returned an error.",
            error_message=error_message,
            exception=traceback.format_exc(),
        )
        return {"error": error_message}, 400


class CostBreakdownIRSMinimumDeductibleView(MavenAuditedView):
    required_capability = "admin_wallet_tools"  # type: ignore[assignment] # Incompatible types in assignment (expression has type "str", base class "AdminAuth" defined the type as "None")

    read_permission = "read:irs-minimum-deductible"
    edit_permission = "edit:irs-minimum-deductible"
    create_permission = "create:irs-minimum-deductible"
    delete_permission = "delete:irs-minimum-deductible"

    # year is the primary key, id should not be used here
    column_default_sort = ("year", True)
    column_list = (
        "year",
        "individual_amount",
        "family_amount",
    )
    form_columns = (
        "year",
        "individual_amount",
        "family_amount",
    )
    column_labels = {
        "individual_amount": "Individual Amount ($)",
        "family_amount": "Family Amount ($)",
    }
    column_formatters = {
        "individual_amount": cents_to_dollars_formatter,
        "family_amount": cents_to_dollars_formatter,
    }
    form_overrides = {
        "individual_amount": AmountDisplayCentsInDollarsField,
        "family_amount": AmountDisplayCentsInDollarsField,
    }

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
            CostBreakdownIrsMinimumDeductible,
            session or db.session,
            category=category,
            name=name,
            endpoint=endpoint,
            **kwargs,
        )


class RTEwithErrorFilter(BooleanEqualFilter):
    def apply(self, query, value, alias=None):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        if value == "1":
            return query.filter(RTETransaction.error_message != None)
        else:
            return query.filter(RTETransaction.error_message == None)


class RTETransactionView(MavenAuditedView):
    read_permission = "read:rte-transaction"
    column_list = (
        "id",
        "member_health_plan_id",
        "response_code",
        "request",
        "response",
        "plan_active_status",
        "error_message",
        "trigger_source",
        "time",
    )
    can_view_details = True
    column_default_sort = ("id", True)
    column_filters = (
        "id",
        "member_health_plan_id",
        "response_code",
        RTEwithErrorFilter(None, "Has RTE Error"),
    )

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
            RTETransaction,
            session or db.session,
            category=category,
            name=name,
            endpoint=endpoint,
            **kwargs,
        )
