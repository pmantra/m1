import json
import traceback

from flask import flash, redirect, request, url_for
from flask_admin import BaseView, expose
from maven import feature_flags
from sqlalchemy.orm import joinedload

from admin.common_cost_breakdown import CalculatorRTE, CostBreakdownExtras, RTEOverride
from admin.views.auth import AdminAuth
from admin.views.base import ViewExtras
from cost_breakdown.constants import AmountType, CostBreakdownType, Tier
from cost_breakdown.models.cost_breakdown import (
    CostBreakdown,
    ReimbursementRequestToCostBreakdown,
)
from cost_breakdown.utils.helpers import (
    get_cycle_based_wallet_balance_from_credit,
    is_plan_tiered,
)
from direct_payment.treatment_procedure.models.treatment_procedure import (
    TreatmentProcedureType,
)
from storage.connection import db
from utils.log import logger
from utils.payments import convert_dollars_to_cents
from wallet.models.constants import BenefitTypes, CostSharingCategory
from wallet.models.reimbursement import ReimbursementRequest
from wallet.models.reimbursement_wallet import MemberHealthPlan
from wallet.repository.health_plan import (
    HEALTH_PLAN_YOY_FLAG,
    OLD_BEHAVIOR,
    HealthPlanRepository,
)
from wallet.services.reimbursment_request_mmb import ReimbursementRequestMMBService

log = logger(__name__)


class ReimbursementRequestCalculatorView(
    AdminAuth, BaseView, ViewExtras, CostBreakdownExtras
):
    # Share Permissions with CostBreakdownRecalculationView
    read_permission = "read:direct-payment-cost-breakdown-recalculation"
    edit_permission = "edit:direct-payment-cost-breakdown-recalculation"
    create_permission = "create:direct-payment-cost-breakdown-recalculation"
    delete_permission = "delete:direct-payment-cost-breakdown-recalculation"

    @expose("/")
    def main(self):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        return redirect(url_for("reimbursementrequest"))

    def is_visible(self, *args):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        return False

    @expose("/submit", methods=("POST",))
    def submit_cost_breakdown_from_reimbursement_request(self):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        form_data = request.json if request.is_json else {}
        # Expected input
        reimbursement_request_id = form_data.get("reimbursement_request_id")
        overrides = form_data.get("overrides")
        rr_mmb_service = ReimbursementRequestMMBService()

        # Validate input
        try:
            reimbursement_request: ReimbursementRequest = (
                ReimbursementRequest.query.get(reimbursement_request_id)
            )
            if reimbursement_request is None:
                raise ValueError(
                    f"Reimbursement Request <{reimbursement_request_id}> not found for calculation."
                )

            user_id = reimbursement_request.person_receiving_service_id
            if user_id is None:
                raise ValueError(
                    "You must assign and save a user_id to the reimbursement request's person_receiving_service to calculate this cost breakdown."
                )

            procedure_type = reimbursement_request.procedure_type
            if procedure_type is None:
                raise ValueError(
                    "You must assign and save a procedure_type to the reimbursement request to calculate this cost breakdown."
                )

            cost_sharing_category = reimbursement_request.cost_sharing_category
            if cost_sharing_category is None:
                raise ValueError(
                    "You must assign and save a cost_sharing_category to the reimbursement request to calculate this cost breakdown."
                )

            if not rr_mmb_service.is_mmb(reimbursement_request):
                raise ValueError(
                    "This reimbursement request must be associated with a wallet and reimbursement organization settings with direct payments enabled."
                )

            benefit_type = reimbursement_request.wallet.category_benefit_type(
                request_category_id=reimbursement_request.reimbursement_request_category_id
            )
            if benefit_type == BenefitTypes.CYCLE:
                if reimbursement_request.cost_credit is None:
                    raise ValueError(
                        "You must assign and save a cost credit value to the reimbursement request "
                        "to calculate this cost breakdown, because it is on a cycle-based wallet."
                    )
                wallet_balance_override = get_cycle_based_wallet_balance_from_credit(
                    wallet=reimbursement_request.wallet,
                    category_id=reimbursement_request.reimbursement_request_category_id,
                    cost_credit=reimbursement_request.cost_credit,
                    cost=reimbursement_request.amount,
                )
                log.info(
                    "Wallet Balance Override",
                    wallet_balance_override=wallet_balance_override,
                )
            else:
                wallet_balance_override = None
                log.info("No Wallet Balance Override")

            eligibility_info_override = None
            tier_override = None
            if overrides and any(overrides.values()):
                if (
                    feature_flags.str_variation(
                        HEALTH_PLAN_YOY_FLAG, default=OLD_BEHAVIOR
                    )
                    != OLD_BEHAVIOR
                ):
                    health_plan_repo = HealthPlanRepository(db.session)
                    member_health_plan = (
                        health_plan_repo.get_member_plan_by_wallet_and_member_id(
                            member_id=user_id,
                            wallet_id=reimbursement_request.reimbursement_wallet_id,
                            effective_date=reimbursement_request.service_start_date,
                        )
                    )
                else:
                    member_health_plan = (
                        MemberHealthPlan.query.filter(
                            MemberHealthPlan.member_id == user_id,
                            MemberHealthPlan.reimbursement_wallet_id
                            == reimbursement_request.reimbursement_wallet_id,
                        )
                        .options(joinedload(MemberHealthPlan.employer_health_plan))
                        .one_or_none()
                    )
                if not member_health_plan:
                    raise ValueError(
                        f"Cannot override eligibility for a user without a member health plan. "
                        f"User: {reimbursement_request.person_receiving_service_id}, "
                        f"Wallet: {reimbursement_request.reimbursement_wallet_id}"
                    )
                # TODO: consistent form data names between calculator forms
                rte_override_data = RTEOverride(
                    ytd_ind_deductible=str(
                        overrides.get("ytd_individual_deductible", "")
                    ),
                    ytd_ind_oop=str(overrides.get("ytd_individual_oop", "")),
                    ytd_family_deductible=str(
                        overrides.get("ytd_family_deductible", "")
                    ),
                    ytd_family_oop=str(overrides.get("ytd_family_oop", "")),
                    hra_remaining=str(overrides.get("hra_remaining", "")),
                )
                tier_override = None
                if is_plan_tiered(ehp=member_health_plan.employer_health_plan):
                    tier_override_raw = overrides.get("tier")
                    if tier_override_raw:
                        tier_override = Tier(int(tier_override_raw))
                    else:
                        tier_override = Tier.SECONDARY
                if CalculatorRTE.should_override_rte_result(
                    member_health_plan=member_health_plan,
                    employer_health_plan=member_health_plan.employer_health_plan,
                    rte_override_data=rte_override_data,
                ):
                    eligibility_info_override = (
                        CalculatorRTE._eligibility_info_override(
                            member_health_plan=member_health_plan,
                            procedure_type=TreatmentProcedureType(procedure_type),
                            cost_sharing_category=CostSharingCategory(
                                cost_sharing_category
                            ),
                            rte_override_data=rte_override_data,
                            tier=tier_override,
                        )
                    )

            cost_breakdown_processor = self._new_cost_breakdown_processor()
            cost_breakdown_processor.calc_config = self.get_calc_config_audit()
        except Exception as e:
            log.error(
                "Invalid data for Reimbursement Request Calculator",
                error=e,
                traceback=traceback.format_exc(),
            )
            return {"error": str(e)}
        log.info(
            "Valid data for the Reimbursement Request Calculator",
            user_id=user_id,
            reimbursement_request_id=str(reimbursement_request_id),
            procedure_type=procedure_type,
            benefit_type=benefit_type,
            cost_sharing_category=cost_sharing_category,
            wallet_balance_override=wallet_balance_override,
            eligibility_info_override=eligibility_info_override,
            override_tier=tier_override,
        )

        # Add the non-blocking error message
        warning_message = None
        missing_rrs = rr_mmb_service.get_related_requests_missing_cost_breakdowns(
            reimbursement_request
        )
        if missing_rrs:
            messages = [
                f"Reimbursement Request ID: {rr.id} - "
                f"Expense Type(s): {', '.join([expense.value for expense in rr.category.expense_types])}"
                for rr in missing_rrs
            ]
            warning_message = (
                f"To return an accurate calculation, "
                f"these previous requests may need cost breakdowns: {''.join(messages)}"
            )
            log.error(
                warning_message, reimbursement_request_id=str(reimbursement_request_id)
            )

        # Process valid input
        params = dict(
            reimbursement_request=reimbursement_request,
            user_id=user_id,
            cost_sharing_category=cost_sharing_category,
            wallet_balance_override=wallet_balance_override,
            override_rte_result=eligibility_info_override,
            override_tier=tier_override,
        )
        try:
            cost_breakdown = (
                cost_breakdown_processor.get_cost_breakdown_for_reimbursement_request(
                    **params
                )
            )
            log.info(
                "Cost Breakdown calculated with the following details.",
                calc_config_audit=cost_breakdown.calc_config,
                reimbursement_request=reimbursement_request_id,
            )
        except Exception as e:
            log.error(
                "Failed to calculate a cost breakdown from params",
                params=params,
                error=str(e),
            )
            return {
                "error": f"Failed to calculate a cost breakdown from params: {params}. "
                f"Error: {str(e)} {traceback.format_exc()}"
            }

        formatted_cost_breakdown = self._format_cost_breakdown(
            initial_cost=reimbursement_request.amount,
            cost_breakdown=cost_breakdown,
        )
        log.info(
            "Successfully calculated a cost breakdown for a reimbursement request.",
            reimbursement_request_id=str(reimbursement_request_id),
        )
        return {"message": warning_message, "cost_breakdown": formatted_cost_breakdown}

    @expose("/save", methods=("POST",))
    def save_cost_breakdown_from_reimbursement_request(self):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        form_data = request.form if request.form else {}
        reimbursement_request_id = form_data.get("reimbursement_request_id")
        cost_breakdown_form_data: str = form_data.get("cost_breakdown", "")
        cost_breakdown_data = json.loads(cost_breakdown_form_data)
        # validate input
        try:
            reimbursement_request: ReimbursementRequest = (
                ReimbursementRequest.query.get(reimbursement_request_id)
            )
            if reimbursement_request is None:
                raise ValueError(
                    f"Reimbursement Request <{reimbursement_request_id}> not found for calculation."
                )

            if not cost_breakdown_data or not isinstance(cost_breakdown_data, dict):
                raise ValueError(
                    "You must first calculate valid cost breakdown data prior to saving."
                )

            existing_reimbursement_to_cost_breakdown: (
                ReimbursementRequestToCostBreakdown
            ) = ReimbursementRequestToCostBreakdown.query.filter_by(
                reimbursement_request_id=reimbursement_request_id
            ).one_or_none()

            if existing_reimbursement_to_cost_breakdown:
                raise ValueError(
                    f"Cannot create a cost breakdown for Reimbursement Request <{reimbursement_request_id}> because "
                    f"this reimbursement request was created by a cost breakdown."
                )

            cost_breakdown = self._create_cost_breakdown(
                reimbursement_request, cost_breakdown_data
            )

            # Note: person_receiving_service_id is(was?) not always a maven member id.
            # TODO: Check person_receiving_service_member_status as needed (low priority for internal tools)
            if not reimbursement_request.person_receiving_service_id:
                raise ValueError(
                    "person_receiving_service_id must be populated on reimbursement request to use calculator"
                )
            if (
                feature_flags.str_variation(HEALTH_PLAN_YOY_FLAG, default=OLD_BEHAVIOR)
                != OLD_BEHAVIOR
            ):
                health_plan_repo = HealthPlanRepository(db.session)
                member_health_plan = health_plan_repo.get_member_plan_by_wallet_and_member_id(
                    member_id=reimbursement_request.person_receiving_service_id,  # type: ignore[arg-type] # Argument "member_id" to "get_member_plan_by_wallet_and_member_id" of "HealthPlanRepository" has incompatible type "int | None"; expected "int"
                    wallet_id=reimbursement_request.reimbursement_wallet_id,
                    effective_date=reimbursement_request.service_start_date,
                )
            else:
                member_health_plan = (
                    MemberHealthPlan.query.filter(
                        MemberHealthPlan.member_id
                        == reimbursement_request.person_receiving_service_id,
                        MemberHealthPlan.reimbursement_wallet_id
                        == reimbursement_request.reimbursement_wallet_id,
                    )
                    .options(joinedload(MemberHealthPlan.employer_health_plan))
                    .one_or_none()
                )
            if not member_health_plan:
                raise ValueError("Missing a member health plan.")
        except Exception as e:
            log.error(
                "Invalid data when saving a cost breakdown from a reimbursement request.",
                error=str(e),
                reimbursement_request_id=reimbursement_request_id,
            )
            flash(str(e), category="error")
            return redirect(
                url_for("reimbursementrequest.edit_view", id=reimbursement_request_id)
            )
        log.info("Valid save data for the Reimbursement Request Calculator")
        try:
            self.update_reimbursement_request_on_cost_breakdown(
                member_id=reimbursement_request.person_receiving_service_id,
                reimbursement_request=reimbursement_request,
                cost_breakdown=cost_breakdown,
                member_health_plan=member_health_plan,
            )
        except Exception as e:
            log.error(
                "Exception handling reimbursement request and cost breakdown updates",
                reimbursement_request_id=str(reimbursement_request_id),
                cost_breakdown_id=str(cost_breakdown.id),
                error=f"{str(e)} {traceback.format_exc()}",
            )
        return redirect(
            url_for(
                "reimbursementrequest.edit_view",
                id=reimbursement_request.id,
            )
        )

    @staticmethod
    def _create_cost_breakdown(
        reimbursement_request: ReimbursementRequest, cost_breakdown_data: dict
    ) -> CostBreakdown:
        return CostBreakdown(
            wallet_id=reimbursement_request.reimbursement_wallet_id,
            member_id=reimbursement_request.person_receiving_service_id,
            reimbursement_request_id=reimbursement_request.id,
            total_member_responsibility=convert_dollars_to_cents(
                cost_breakdown_data["total_member_responsibility"]
            ),
            total_employer_responsibility=convert_dollars_to_cents(
                cost_breakdown_data["total_employer_responsibility"]
            ),
            beginning_wallet_balance=convert_dollars_to_cents(
                cost_breakdown_data["beginning_wallet_balance"]
            ),
            ending_wallet_balance=convert_dollars_to_cents(
                cost_breakdown_data["ending_wallet_balance"]
            ),
            deductible=convert_dollars_to_cents(cost_breakdown_data["deductible"]),
            deductible_remaining=convert_dollars_to_cents(
                cost_breakdown_data["deductible_remaining"]
            ),
            family_deductible_remaining=convert_dollars_to_cents(
                cost_breakdown_data["family_deductible_remaining"]
            ),
            coinsurance=convert_dollars_to_cents(cost_breakdown_data["coinsurance"]),
            copay=convert_dollars_to_cents(cost_breakdown_data["copay"]),
            oop_applied=convert_dollars_to_cents(cost_breakdown_data["oop_applied"]),
            oop_remaining=convert_dollars_to_cents(
                cost_breakdown_data["oop_remaining"]
            ),
            family_oop_remaining=convert_dollars_to_cents(
                cost_breakdown_data["family_oop_remaining"]
            ),
            overage_amount=convert_dollars_to_cents(
                cost_breakdown_data["overage_amount"]
            ),
            amount_type=AmountType(cost_breakdown_data["amount_type"]),
            cost_breakdown_type=CostBreakdownType(
                cost_breakdown_data["cost_breakdown_type"]
            ),
            rte_transaction_id=cost_breakdown_data["rte_transaction_id"],
            calc_config=cost_breakdown_data["calc_config"],
        )
