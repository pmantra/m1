import datetime
import json
from unittest.mock import call, patch

import pytest

from admin.views.models.reimbursement_request_calculator import (
    ReimbursementRequestCalculatorView,
)
from cost_breakdown.constants import ClaimType, Tier
from cost_breakdown.models.cost_breakdown import CostBreakdown
from cost_breakdown.pytests.factories import (
    CostBreakdownFactory,
    ReimbursementRequestToCostBreakdownFactory,
)
from direct_payment.treatment_procedure.models.treatment_procedure import (
    TreatmentProcedureStatus,
    TreatmentProcedureType,
)
from direct_payment.treatment_procedure.pytests.factories import (
    TreatmentProcedureFactory,
)
from payer_accumulator.models.accumulation_treatment_mapping import (
    AccumulationTreatmentMapping,
)
from pytests.common.global_procedures.factories import GlobalProcedureFactory
from utils.log import logger
from utils.payments import convert_cents_to_dollars
from wallet.models.constants import (
    BenefitTypes,
    CostSharingCategory,
    CostSharingType,
    MemberType,
    ReimbursementRequestAutoProcessing,
    ReimbursementRequestExpenseTypes,
    ReimbursementRequestState,
    ReimbursementRequestType,
    WalletUserMemberStatus,
)
from wallet.models.reimbursement import ReimbursementRequest
from wallet.models.reimbursement_organization_settings import (
    EmployerHealthPlanCostSharing,
)
from wallet.pytests.factories import (
    EmployerHealthPlanCoverageFactory,
    EmployerHealthPlanFactory,
    MemberHealthPlanFactory,
    ReimbursementRequestFactory,
)
from wallet.repository.health_plan import HEALTH_PLAN_YOY_FLAG, NEW_BEHAVIOR

log = logger(__name__)


@pytest.fixture()
def enable_health_plan_repo(ff_test_data):
    ff_test_data.update(
        ff_test_data.flag(HEALTH_PLAN_YOY_FLAG).variations(NEW_BEHAVIOR)
    )


class TestRequestCalculatorSubmit:
    def test_cost_breakdown_from_reimbursement_request(self, admin_client, wallet):
        category = (
            wallet.reimbursement_organization_settings.allowed_reimbursement_categories[
                0
            ].reimbursement_request_category
        )
        reimbursement_request = ReimbursementRequestFactory.create(
            wallet=wallet,
            category=category,
            state=ReimbursementRequestState.APPROVED,
            amount=100,
            person_receiving_service_id=1,
            procedure_type=TreatmentProcedureType.MEDICAL.value,
            cost_sharing_category=CostSharingCategory.MEDICAL_CARE,
        )
        with patch(
            "cost_breakdown.cost_breakdown_processor.CostBreakdownProcessor.get_cost_breakdown_for_reimbursement_request",
            side_effect=Exception("Expected Error"),
        ) as service_creation_call:
            res = admin_client.post(
                "/admin/reimbursement_request_calculator/submit",
                data=json.dumps({"reimbursement_request_id": reimbursement_request.id}),
                headers={"Content-Type": "application/json"},
            )
        assert res.status_code == 200
        assert "Failed to calculate a cost breakdown from params" in res.json["error"]
        assert service_creation_call.call_args.kwargs == {
            "reimbursement_request": reimbursement_request,
            "user_id": reimbursement_request.person_receiving_service_id,
            "cost_sharing_category": CostSharingCategory.MEDICAL_CARE,
            "wallet_balance_override": None,
            "override_rte_result": None,
            "override_tier": None,
        }

    def test_cost_breakdown_from_reimbursement_request_cycle_wallet(
        self, admin_client, wallet_cycle_based
    ):
        assoc_category = wallet_cycle_based.reimbursement_organization_settings.allowed_reimbursement_categories[
            0
        ]
        assert assoc_category.benefit_type == BenefitTypes.CYCLE
        category = assoc_category.reimbursement_request_category
        reimbursement_request = ReimbursementRequestFactory.create(
            wallet=wallet_cycle_based,
            category=category,
            reimbursement_request_category_id=category.id,
            state=ReimbursementRequestState.APPROVED,
            amount=100,
            person_receiving_service_id=wallet_cycle_based.user_id,
            procedure_type=TreatmentProcedureType.MEDICAL.value,
            cost_sharing_category=CostSharingCategory.MEDICAL_CARE,
            cost_credit=1,
        )
        with patch(
            "cost_breakdown.cost_breakdown_processor.CostBreakdownProcessor.get_cost_breakdown_for_reimbursement_request"
        ) as service_creation_call, patch.object(
            ReimbursementRequestCalculatorView,
            "_format_cost_breakdown",
            return_value={},
        ):
            res = admin_client.post(
                "/admin/reimbursement_request_calculator/submit",
                data=json.dumps({"reimbursement_request_id": reimbursement_request.id}),
                headers={"Content-Type": "application/json"},
            )

        assert res.status_code == 200
        assert service_creation_call.call_args.kwargs == {
            "reimbursement_request": reimbursement_request,
            "user_id": reimbursement_request.person_receiving_service_id,
            "cost_sharing_category": CostSharingCategory.MEDICAL_CARE,
            "wallet_balance_override": 100,
            "override_rte_result": None,
            "override_tier": None,
        }

    @pytest.mark.parametrize(
        "rr_data,form_data,error_message",
        [
            ({}, {}, "Reimbursement Request <None> not found for calculation."),
            (
                {"id": 1234},
                {"reimbursement_request_id": 1234},
                "You must assign and save a user_id to the reimbursement request's person_receiving_service to calculate this cost breakdown.",
            ),
            (
                {"id": 1234, "person_receiving_service_id": 1},
                {"reimbursement_request_id": 1234},
                "You must assign and save a procedure_type to the reimbursement request to calculate this cost breakdown.",
            ),
            (
                {
                    "id": 1234,
                    "person_receiving_service_id": 1,
                    "procedure_type": TreatmentProcedureType.MEDICAL.value,
                },
                {"reimbursement_request_id": 1234},
                "You must assign and save a cost_sharing_category to the reimbursement request to calculate this cost breakdown.",
            ),
        ],
    )
    def test_save_reimbursement_request_cost_breakdown_validation_errors(
        self, admin_client, wallet_cycle_based, rr_data, form_data, error_message
    ):
        category = wallet_cycle_based.reimbursement_organization_settings.allowed_reimbursement_categories[
            0
        ].reimbursement_request_category
        ReimbursementRequestFactory.create(
            wallet=wallet_cycle_based,
            category=category,
            state=ReimbursementRequestState.APPROVED,
            amount=100,
            **rr_data,
        )
        res = admin_client.post(
            "/admin/reimbursement_request_calculator/submit",
            data=json.dumps(form_data),
            headers={"Content-Type": "application/json"},
        )
        assert res.status_code == 200
        assert res.json["error"] == error_message

    def test_reimbursement_request_calculate_with_overrides(
        self, admin_client, wallet, enable_health_plan_repo
    ):
        user = wallet.member
        org_setting = wallet.reimbursement_organization_settings
        org_setting.deductible_accumulation_enabled = False
        category = org_setting.allowed_reimbursement_categories[
            0
        ].reimbursement_request_category
        employer_health_plan = EmployerHealthPlanFactory.create(
            reimbursement_organization_settings=org_setting,
            coverage=[
                EmployerHealthPlanCoverageFactory.create(
                    individual_deductible=200000,
                    individual_oop=400_000,
                    family_deductible=None,
                    family_oop=None,
                    tier=Tier.PREMIUM,
                ),
            ],
            cost_sharings=[
                EmployerHealthPlanCostSharing(
                    cost_sharing_type=CostSharingType.COPAY,
                    cost_sharing_category=CostSharingCategory.MEDICAL_CARE,
                    absolute_amount=2000,
                )
            ],
        )
        MemberHealthPlanFactory.create(
            reimbursement_wallet=wallet,
            reimbursement_wallet_id=wallet.id,
            employer_health_plan=employer_health_plan,
            employer_health_plan_id=employer_health_plan.id,
            member_id=user.id,
            plan_start_at=datetime.datetime(year=2024, month=1, day=1),
        )
        reimbursement_request = ReimbursementRequestFactory.create(
            wallet=wallet,
            reimbursement_wallet_id=wallet.id,
            category=category,
            state=ReimbursementRequestState.APPROVED,
            amount=100,
            person_receiving_service_id=user.id,
            procedure_type=TreatmentProcedureType.MEDICAL.value,
            cost_sharing_category=CostSharingCategory.MEDICAL_CARE,
            service_start_date=datetime.datetime.now(datetime.timezone.utc),
        )
        res = admin_client.post(
            "/admin/reimbursement_request_calculator/submit",
            data=json.dumps(
                {
                    "reimbursement_request_id": reimbursement_request.id,
                    "overrides": {
                        "ytd_individual_deductible": "2000",
                        "ytd_individual_oop": "2000",
                        "ytd_family_deductible": "",
                        "ytd_family_oop": "",
                        "hra_remaining": "",
                        "tier": "1",
                    },
                }
            ),
            headers={"Content-Type": "application/json"},
        )
        assert res.status_code == 200
        cost_breakdown_data = res.json["cost_breakdown"]
        assert cost_breakdown_data["cost"] == "1"
        assert cost_breakdown_data["total_member_responsibility"] == 0
        assert cost_breakdown_data["total_employer_responsibility"] == "1"
        calc_config = json.loads(cost_breakdown_data["calc_config"])
        assert calc_config["tier"] == 1
        assert calc_config["eligibility_info"] == {
            "individual_deductible": 200000,
            "individual_deductible_remaining": 0,
            "family_deductible": None,
            "family_deductible_remaining": None,
            "individual_oop": 400000,
            "individual_oop_remaining": 200000,
            "family_oop": None,
            "family_oop_remaining": None,
            "hra_remaining": None,
            "coinsurance": None,
            "coinsurance_min": None,
            "coinsurance_max": None,
            "copay": None,
            "max_oop_per_covered_individual": None,
            "is_deductible_embedded": False,  # will be changed in part 2 MR
            "is_oop_embedded": False,  # will be changed in part 2 MR
            "ignore_deductible": False,
        }
        assert res.json["message"] is None


class TestRequestCalculatorSave:
    def test_save_reimbursement_request_cost_breakdown_existing_many_relationship(
        self,
        admin_client,
        enterprise_user,
        wallet,
        rx_procedure,
    ):
        category = (
            wallet.reimbursement_organization_settings.allowed_reimbursement_categories[
                0
            ].reimbursement_request_category
        )
        reimbursement_request = ReimbursementRequestFactory.create(
            wallet=wallet, category=category, amount=750000
        )
        cb = CostBreakdownFactory.create()
        form_data = {
            "reimbursement_request_id": reimbursement_request.id,
            "cost_breakdown": json.dumps({"test_data": True}),
        }
        ReimbursementRequestToCostBreakdownFactory.create(
            claim_type=ClaimType.EMPLOYER,
            treatment_procedure_uuid=rx_procedure.uuid,
            reimbursement_request_id=reimbursement_request.id,
            cost_breakdown_id=cb.id,
        )

        with patch(
            "admin.views.models.reimbursement_request_calculator.flash"
        ) as flash:
            res = admin_client.post(
                "/admin/reimbursement_request_calculator/save",
                data=form_data,
                headers={"Content-Type": "application/x-www-form-urlencoded"},
            )
        assert res.status_code == 302
        assert (
            res.location
            == f"/admin/reimbursementrequest/edit/?id={reimbursement_request.id}"
        )
        assert flash.call_args == call(
            f"Cannot create a cost breakdown for Reimbursement Request <{reimbursement_request.id}> because "
            "this reimbursement request was created by a cost breakdown.",
            category="error",
        )

    def test_save_reimbursement_request_cost_breakdown_bad_data(
        self,
        admin_client,
        enterprise_user,
        wallet,
    ):
        rr_data = {
            "id": 1234,
            "person_receiving_service_id": enterprise_user.id,
            "procedure_type": TreatmentProcedureType.MEDICAL.value,
            "cost_sharing_category": CostSharingCategory.MEDICAL_CARE,
        }
        category = (
            wallet.reimbursement_organization_settings.allowed_reimbursement_categories[
                0
            ].reimbursement_request_category
        )
        reimbursement_request = ReimbursementRequestFactory.create(
            wallet=wallet,
            category=category,
            state=ReimbursementRequestState.APPROVED,
            amount=100,
            **rr_data,
        )

        cb_form_data = {
            "amount_type": "FAMILY",
            "beginning_wallet_balance": 1922.35,
            "calc_config": None,
            "coinsurance": 0,
            "copay": 0,
            "cost": 1922.35,
            "cost_breakdown_type": None,
            "deductible": 0,
            "deductible_remaining": 0,
            "ending_wallet_balance": 0,
            "family_deductible_remaining": 0,
            "family_oop_remaining": 0,
            "oop_applied": 0,
            "oop_remaining": 0,
            "overage_amount": 0,
            "rte_transaction_id": None,
            "total_employer_responsibility": 1922.35,
            "total_member_responsibility": 0,
        }
        form_data = {
            "reimbursement_request_id": reimbursement_request.id,
            "cost_breakdown": json.dumps(cb_form_data),
        }

        with patch(
            "admin.views.models.reimbursement_request_calculator.flash"
        ) as flash:
            res = admin_client.post(
                "/admin/reimbursement_request_calculator/save",
                data=form_data,
                headers={"Content-Type": "application/x-www-form-urlencoded"},
            )
        assert res.status_code == 302
        assert (
            res.location
            == f"/admin/reimbursementrequest/edit/?id={reimbursement_request.id}"
        )
        assert flash.call_args == call(
            "None is not a valid CostBreakdownType",
            category="error",
        )

    @pytest.mark.parametrize(
        "is_deductible_accumulation,total_member_responsibility,total_employer_responsibility,"
        "expected_amount,expected_state,mapping_count,flash_count",
        [
            # member responsibility == amount
            (False, 100, 0, 100, "PENDING", 0, 1),
            (True, 100, 0, 100, "DENIED", 1, 2),
            # divided responsibility
            (False, 25, 75, 100, "PENDING", 0, 1),
            (True, 25, 75, 75, "PENDING", 0, 2),
            # employer responsibility == amount
            (False, 0, 100, 100, "PENDING", 0, 1),
            (True, 0, 100, 100, "PENDING", 0, 1),
        ],
        ids=[
            "memb_resp_not_da",
            "memb_resp_da",
            "divided_resp_not_da",
            "divided_resp_da",
            "employer_resp_not_da",
            "employer_resp_da",
        ],
    )
    def test_save_reimbursement_request_cost_breakdown_saves(
        self,
        admin_client,
        wallet,
        health_plans_for_wallet,
        is_deductible_accumulation,
        total_member_responsibility,
        total_employer_responsibility,
        expected_amount,
        expected_state,
        mapping_count,
        flash_count,
        enable_health_plan_repo,
    ):
        org_setting = wallet.reimbursement_organization_settings
        org_setting.deductible_accumulation_enabled = is_deductible_accumulation
        category = org_setting.allowed_reimbursement_categories[
            0
        ].reimbursement_request_category
        reimbursement_request = ReimbursementRequestFactory.create(
            wallet=wallet,
            person_receiving_service_id=wallet.member.id,
            category=category,
            state=ReimbursementRequestState.NEW,
            procedure_type=TreatmentProcedureType.MEDICAL.value,
            cost_sharing_category=CostSharingCategory.MEDICAL_CARE,
            amount=100_00,
            description="",
            service_start_date=datetime.datetime.now(datetime.timezone.utc),
        )
        fake_calc_config = json.dumps(
            {
                "health_plan_configuration": {"is_family_plan": True},
                "trigger_object_status": "SCHEDULED",
            }
        )
        cb_form_data = {
            "amount_type": "FAMILY",
            "beginning_wallet_balance": 1922.35,
            "calc_config": fake_calc_config,
            "coinsurance": 0,
            "copay": 0,
            "cost": 100.0,
            "cost_breakdown_type": "FIRST_DOLLAR_COVERAGE",
            "deductible": 0,
            "deductible_remaining": 0,
            "ending_wallet_balance": 0,
            "family_deductible_remaining": 0,
            "family_oop_remaining": 0,
            "oop_applied": 0,
            "oop_remaining": 0,
            "overage_amount": 0,
            "rte_transaction_id": None,
            "total_employer_responsibility": total_employer_responsibility,
            "total_member_responsibility": total_member_responsibility,
        }
        form_data = {
            "reimbursement_request_id": reimbursement_request.id,
            "cost_breakdown": json.dumps(cb_form_data),
        }

        with patch(
            "payer_accumulator.accumulation_mapping_service.AccumulationMappingService.create_valid_reimbursement_request_mapping"
        ) as mapping_call, patch("admin.common_cost_breakdown.flash") as flash:
            mapping_call.return_value = None
            res = admin_client.post(
                "/admin/reimbursement_request_calculator/save",
                data=form_data,
                headers={"Content-Type": "application/x-www-form-urlencoded"},
            )
        assert res.status_code == 302
        assert (
            res.location
            == f"/admin/reimbursementrequest/edit/?id={reimbursement_request.id}"
        )
        reimbursement_request = ReimbursementRequest.query.filter(
            ReimbursementRequest.id == reimbursement_request.id
        ).one()
        assert convert_cents_to_dollars(reimbursement_request.amount) == expected_amount
        assert reimbursement_request.state == ReimbursementRequestState(expected_state)
        assert reimbursement_request.description.__contains__("Test Plan")
        assert (
            reimbursement_request.person_receiving_service_member_status
            == WalletUserMemberStatus.MEMBER
        )
        cost_breakdown = CostBreakdown.query.filter(
            CostBreakdown.reimbursement_request_id == reimbursement_request.id
        ).one()
        assert cost_breakdown.calc_config == fake_calc_config
        assert mapping_call.call_count == mapping_count

        assert flash.call_count == flash_count
        main_message = flash.call_args_list[0].args[0]
        assert f"Cost Breakdown <{cost_breakdown.id}> saved!" in main_message

    @pytest.mark.parametrize(
        "is_deductible_accumulation,total_member_responsibility,total_employer_responsibility,"
        "expected_amount,expected_state,claims_calls,flash_count,accumulations",
        [
            # member responsibility == amount
            (False, 100, 0, 100, "DENIED", 1, 2, 0),
            (True, 100, 0, 100, "DENIED", 0, 2, 1),
            # divided responsibility
            (False, 25, 75, 75, "APPROVED", 2, 2, 0),
            (True, 25, 75, 75, "APPROVED", 1, 2, 1),
            # employer responsibility == amount
            (False, 0, 100, 100, "APPROVED", 1, 2, 0),
            (True, 0, 100, 100, "APPROVED", 1, 2, 0),
        ],
        ids=[
            "memb_resp_not_da",
            "memb_resp_da",
            "divided_resp_not_da",
            "divided_resp_da",
            "employer_resp_not_da",
            "employer_resp_da",
        ],
    )
    def test_save_reimbursement_request_cost_breakdown_saves_auto_processed_rx(
        self,
        admin_client,
        wallet,
        health_plans_for_wallet,
        is_deductible_accumulation,
        total_member_responsibility,
        total_employer_responsibility,
        expected_amount,
        expected_state,
        claims_calls,
        flash_count,
        accumulations,
        enable_health_plan_repo,
    ):
        org_setting = wallet.reimbursement_organization_settings
        org_setting.deductible_accumulation_enabled = is_deductible_accumulation
        # if DA enabled it doesn't check this. Adding this for when DA is not enabled
        health_plans_for_wallet.employer_health_plan.is_hdhp = True

        category = org_setting.allowed_reimbursement_categories[
            0
        ].reimbursement_request_category
        reimbursement_request = ReimbursementRequestFactory.create(
            reimbursement_wallet_id=wallet.id,
            reimbursement_request_category_id=category.id,
            reimbursement_type=ReimbursementRequestType.MANUAL,
            procedure_type=TreatmentProcedureType.PHARMACY.value,
            cost_sharing_category=CostSharingCategory.GENERIC_PRESCRIPTIONS,
            person_receiving_service_id=wallet.user_id,
            expense_type=ReimbursementRequestExpenseTypes.FERTILITY,
            cost_credit=0,
            amount=100_00,
            auto_processed=ReimbursementRequestAutoProcessing.RX,
            person_receiving_service_member_status=WalletUserMemberStatus.MEMBER,
        )
        fake_calc_config = json.dumps(
            {
                "health_plan_configuration": {"is_family_plan": True},
                "trigger_object_status": "SCHEDULED",
            }
        )
        cb_form_data = {
            "amount_type": "FAMILY",
            "beginning_wallet_balance": 1922.35,
            "calc_config": fake_calc_config,
            "coinsurance": 0,
            "copay": 0,
            "cost": 100.0,
            "cost_breakdown_type": "FIRST_DOLLAR_COVERAGE",
            "deductible": total_member_responsibility,
            "deductible_remaining": 0,
            "ending_wallet_balance": 0,
            "family_deductible_remaining": 0,
            "family_oop_remaining": 0,
            "oop_applied": 0,
            "oop_remaining": 0,
            "overage_amount": 0,
            "rte_transaction_id": None,
            "total_employer_responsibility": total_employer_responsibility,
            "total_member_responsibility": total_member_responsibility,
        }
        form_data = {
            "reimbursement_request_id": reimbursement_request.id,
            "cost_breakdown": json.dumps(cb_form_data),
        }
        with patch(
            "direct_payment.pharmacy.automated_reimbursement_request_service"
            ".create_auto_processed_claim_in_alegeus",
            return_value=True,
        ) as submit_claims_to_alegeus, patch(
            "admin.common_cost_breakdown.flash"
        ) as flash, patch(
            "wallet.services.reimbursement_request_state_change"
            ".use_alegeus_for_reimbursements",
            return_value=True,
        ), patch(
            "braze.client.BrazeClient._make_request"
        ) as mock_send_event:
            res = admin_client.post(
                "/admin/reimbursement_request_calculator/save",
                data=form_data,
                headers={"Content-Type": "application/x-www-form-urlencoded"},
            )
        assert res.status_code == 302
        assert (
            res.location
            == f"/admin/reimbursementrequest/edit/?id={reimbursement_request.id}"
        )
        rr = ReimbursementRequest.query.filter(
            ReimbursementRequest.id == reimbursement_request.id
        ).one()
        assert convert_cents_to_dollars(rr.amount) == expected_amount
        assert rr.state == ReimbursementRequestState(expected_state)

        cost_breakdown = CostBreakdown.query.filter(
            CostBreakdown.reimbursement_request_id == reimbursement_request.id
        ).one()
        assert cost_breakdown.calc_config == fake_calc_config

        assert flash.call_count == flash_count
        main_message = flash.call_args_list[0].args[0]
        assert f"Cost Breakdown <{cost_breakdown.id}> saved!" in main_message
        assert submit_claims_to_alegeus.call_count == claims_calls

        accumulation_mapping = AccumulationTreatmentMapping.query.filter_by(
            reimbursement_request_id=reimbursement_request.id
        ).all()
        assert len(accumulation_mapping) == accumulations
        assert mock_send_event.call_count == 1

    @pytest.mark.parametrize(
        "is_deductible_accumulation,total_member_responsibility,total_employer_responsibility,"
        "expected_amount,expected_state,mapping_count,flash_count, is_cost_share_breakdown_enabled, is_auto_processed_rx",
        [
            (False, 25, 75, 100, "PENDING", 0, 1, False, False),
            (True, 25, 75, 75, "PENDING", 0, 2, True, False),
            (True, 0, 100, 100, "PENDING", 0, 1, True, True),
        ],
        ids=[
            "cost_share_enabled_false_skips_braze_event",
            "cost_share_enabled_true_sends_braze_event",
            "cost_share_enabled_and_auto_processed_rx_skips_braze_event",
        ],
    )
    def test_save_reimbursement_request_cost_breakdown_saves_cost_share_breakdown_braze_event(
        self,
        admin_client,
        patch_braze_send_event,
        wallet,
        health_plans_for_wallet,
        is_deductible_accumulation,
        total_member_responsibility,
        total_employer_responsibility,
        expected_amount,
        expected_state,
        mapping_count,
        flash_count,
        is_cost_share_breakdown_enabled,
        is_auto_processed_rx,
        enable_health_plan_repo,
    ):
        org_setting = wallet.reimbursement_organization_settings
        org_setting.deductible_accumulation_enabled = is_deductible_accumulation
        category = org_setting.allowed_reimbursement_categories[
            0
        ].reimbursement_request_category
        wallet_user = wallet.reimbursement_wallet_users[0].member

        reimbursement_request = ReimbursementRequestFactory.create(
            wallet=wallet,
            person_receiving_service_id=wallet_user.id,
            category=category,
            state=ReimbursementRequestState.NEW,
            procedure_type=TreatmentProcedureType.MEDICAL.value,
            cost_sharing_category=CostSharingCategory.MEDICAL_CARE,
            amount=100_00,
            description="",
            auto_processed=(
                ReimbursementRequestAutoProcessing.RX if is_auto_processed_rx else None
            ),
        )
        fake_calc_config = json.dumps(
            {
                "health_plan_configuration": {"is_family_plan": True},
                "trigger_object_status": "SCHEDULED",
            }
        )
        cb_form_data = {
            "amount_type": "FAMILY",
            "beginning_wallet_balance": 1922.35,
            "calc_config": fake_calc_config,
            "coinsurance": 0,
            "copay": 0,
            "cost": 100.0,
            "cost_breakdown_type": "FIRST_DOLLAR_COVERAGE",
            "deductible": 0,
            "deductible_remaining": 0,
            "ending_wallet_balance": 0,
            "family_deductible_remaining": 0,
            "family_oop_remaining": 0,
            "oop_applied": 0,
            "oop_remaining": 0,
            "overage_amount": 0,
            "rte_transaction_id": None,
            "total_employer_responsibility": total_employer_responsibility,
            "total_member_responsibility": total_member_responsibility,
        }
        form_data = {
            "reimbursement_request_id": reimbursement_request.id,
            "cost_breakdown": json.dumps(cb_form_data),
        }

        with patch(
            "payer_accumulator.accumulation_mapping_service.AccumulationMappingService.create_valid_reimbursement_request_mapping"
        ) as mapping_call, patch("admin.common_cost_breakdown.flash") as flash, patch(
            "wallet.services.reimbursement_request.ReimbursementRequestService.is_cost_share_breakdown_applicable",
            return_value=is_cost_share_breakdown_enabled,
        ):
            mapping_call.return_value = None
            res = admin_client.post(
                "/admin/reimbursement_request_calculator/save",
                data=form_data,
                headers={"Content-Type": "application/x-www-form-urlencoded"},
            )
        assert res.status_code == 302
        assert (
            res.location
            == f"/admin/reimbursementrequest/edit/?id={reimbursement_request.id}"
        )

        assert convert_cents_to_dollars(reimbursement_request.amount) == expected_amount
        assert reimbursement_request.state == ReimbursementRequestState(expected_state)
        assert (
            reimbursement_request.person_receiving_service_member_status
            == WalletUserMemberStatus.MEMBER
        )
        if not is_auto_processed_rx:
            assert reimbursement_request.description.__contains__("Test Plan")

        cost_breakdown = CostBreakdown.query.filter(
            CostBreakdown.reimbursement_request_id == reimbursement_request.id
        ).one()

        assert flash.call_count == flash_count
        main_message = flash.call_args_list[0].args[0]
        assert f"Cost Breakdown <{cost_breakdown.id}> saved!" in main_message

        if is_cost_share_breakdown_enabled and not is_auto_processed_rx:
            patch_braze_send_event.assert_called_once_with(
                user=wallet_user,
                event_name="reimbursement_request_updated_new_to_pending",
                event_data={
                    "member_type": MemberType.MAVEN_GOLD.value,
                    "prev_state": ReimbursementRequestState.NEW.value,
                    "new_state": ReimbursementRequestState.PENDING.value,
                },
            )
        else:
            patch_braze_send_event.assert_not_called()


class TestCalculatorInteractions:
    def test_state_across_view(
        self,
        admin_client,
        wallet,
        session,
        enable_health_plan_repo,
    ):
        user = wallet.member
        org_settings = wallet.reimbursement_organization_settings
        org_settings.first_dollar_coverage = True
        category = org_settings.allowed_reimbursement_categories[
            0
        ].reimbursement_request_category
        reimbursement_request = ReimbursementRequestFactory.create(
            wallet=wallet,
            reimbursement_wallet_id=wallet.id,
            category=category,
            state=ReimbursementRequestState.APPROVED,
            amount=100,
            person_receiving_service_id=user.id,
            procedure_type=TreatmentProcedureType.MEDICAL.value,
            cost_sharing_category=CostSharingCategory.MEDICAL_CARE,
            service_start_date=datetime.datetime(2024, 2, 2, 0, 0, 0),
        )
        # add extra amount
        extra_amount_cb = CostBreakdownFactory.create(
            total_employer_responsibility=1000
        )
        TreatmentProcedureFactory.create(
            member_id=user.id,
            cost=1000,
            status=TreatmentProcedureStatus.SCHEDULED,
            cost_breakdown_id=extra_amount_cb.id,
            start_date=datetime.date(2024, 2, 2),
        )

        log.info("First call to the reimbursement request calculator")
        res = admin_client.post(
            "/admin/reimbursement_request_calculator/submit",
            data=json.dumps({"reimbursement_request_id": reimbursement_request.id}),
            headers={"Content-Type": "application/json"},
        )
        assert res.status_code == 200
        assert res.json["cost_breakdown"]["cost"] == "1"
        assert res.json["cost_breakdown"]["total_employer_responsibility"] == "1"
        assert res.json["cost_breakdown"]["beginning_wallet_balance"] == "49"
        assert res.json["cost_breakdown"]["ending_wallet_balance"] == "48"

        log.info("First call to the multi-procedure calculator")
        with patch(
            "common.global_procedures.procedure.ProcedureService.get_procedure_by_id",
            return_value=GlobalProcedureFactory.create(id="test_gp", name="Test"),
        ):
            res_multi = admin_client.post(
                "/admin/cost_breakdown_calculator/multipleprocedures/submit",
                json={
                    "userId": str(user.id),
                    "individualDeductible": "",
                    "individualOop": "",
                    "familyDeductible": "",
                    "familyOop": "",
                    "hraRemaining": "",
                    "procedures": [
                        {
                            "type": "medical",
                            "procedure": {"id": "test_gp", "name": "IVF"},
                            "clinic": {"id": 1},
                            "cost": "26",
                            "start_date": "2024-02-02",
                        }
                    ],
                },
                headers={"Content-Type": "application/json"},
            )
        assert res_multi.status_code == 200
        assert res_multi.json["total"]["beginningWalletBalance"] == "39"
        assert res_multi.json["total"]["endingWalletBalance"] == "13"

        log.info("Second call to the reimbursement request calculator")
        res = admin_client.post(
            "/admin/reimbursement_request_calculator/submit",
            data=json.dumps({"reimbursement_request_id": reimbursement_request.id}),
            headers={"Content-Type": "application/json"},
        )
        # confirming that no extra_applied_amount state is carried over to the reimbursement request calculator
        assert res.json["cost_breakdown"]["beginning_wallet_balance"] == "49"
        assert res.json["cost_breakdown"]["ending_wallet_balance"] == "48"
