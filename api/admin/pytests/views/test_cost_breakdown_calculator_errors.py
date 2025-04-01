import datetime
from unittest import mock

import pytest
from flask import Response

from admin.user_facing_errors import ErrorMessageImprover
from cost_breakdown import errors
from cost_breakdown.models.rte import TieredRTEErrorData
from cost_breakdown.pytests.factories import RTETransactionFactory
from direct_payment.treatment_procedure.models.treatment_procedure import (
    TreatmentProcedureType,
)
from direct_payment.treatment_procedure.pytests.factories import (
    TreatmentProcedureFactory,
)
from wallet.models.constants import FamilyPlanType
from wallet.pytests.factories import (
    EmployerHealthPlanFactory,
    MemberHealthPlanFactory,
    ReimbursementRequestCategoryFactory,
    ReimbursementRequestFactory,
)


@pytest.fixture(scope="function")
def procedure(enterprise_user, wallet):
    category = ReimbursementRequestCategoryFactory.create(label="fertility")
    return TreatmentProcedureFactory.create(
        member_id=enterprise_user.id,
        reimbursement_wallet_id=wallet.id,
        reimbursement_request_category=category,
        procedure_type=TreatmentProcedureType.MEDICAL,
        start_date=datetime.date(year=2025, month=1, day=5),
    )


@pytest.fixture(scope="function")
def get_cost_breakdown_result(admin_client, procedure):
    def get_result(exception: Exception) -> Response:
        with mock.patch(
            "cost_breakdown.cost_breakdown_processor.CostBreakdownProcessor.get_cost_breakdown_for_treatment_procedure",
            side_effect=exception,
        ):
            res = admin_client.post(
                "/admin/cost_breakdown_calculator/submit",
                data={
                    "treatment_ids": f"{procedure.id}",
                    "ind_deductible": "",
                    "ind_oop": "",
                    "family_deductible": "",
                    "family_oop": "",
                    "hra_remaining": "",
                },
                headers={"Content-Type": "multipart/form-data"},
            )
        return res

    return get_result


class TestErrorMessageImprover:
    def test_tier_coverage_error(self, get_cost_breakdown_result):
        plan = EmployerHealthPlanFactory.create()
        exception = errors.TieredRTEError(
            message="Test Message",
            tier=None,
            errors=[
                TieredRTEErrorData("Test Error", 1, 2),
                TieredRTEErrorData("Test Error 2", 100, None),
            ],
            plan=plan,
        )

        # when
        res = get_cost_breakdown_result(exception)

        # then
        assert res.status_code == 400
        assert res.json["error"] == (
            "This calculation has a coverage error. "
            "The tiered coverage expects a Test Error of 1, however PVerify is returning a Test Error of 2. "
            "The tiered coverage expects a Test Error 2 of 100, however PVerify is returning a Test Error 2 of None. "
            "Please check the member is assigned to the correct employer health plan "
            f"<a href='/admin/employerhealthplan/edit/?id={plan.id}'>&lt;[name:{plan.name}] [id:{plan.id}]&gt;</a>"
            ", and the employer health plan has the correct limit configurations."
        )

    def test_deductible_oop_error(self, get_cost_breakdown_result, procedure):
        plan = MemberHealthPlanFactory.create(plan_type=FamilyPlanType.INDIVIDUAL)
        rte = RTETransactionFactory.create()
        exception = errors.NoIndividualDeductibleOopRemaining(
            plan=plan, rte_transaction=rte, message="Test Message"
        )

        # when
        res = get_cost_breakdown_result(exception)

        # then
        assert res.status_code == 400
        assert res.json["error"] == (
            f"This user's health plan "
            f"<a href='/admin/memberhealthplan/edit/?id={plan.id}'>&lt;MemberHealthPlan {plan.id}&gt;</a> "
            f"has no remaining INDIVIDUAL deductible or out-of-pocket maximum according to Pverify: "
            f"<a href='/admin/rtetransaction/edit/?id={rte.id}'>&lt;RTETransaction {rte.id}&gt;</a>. "
            f"Please send this to Payment Ops who can check historical data and pverify or contact the member for an "
            f"accurate explanation of benefits for this "
            f"<a href='/admin/treatmentprocedure/edit/?id={procedure.id}'>&lt;TreatmentProcedure {procedure.id}&gt;</a>."
        )

    def test_deductible_oop_error_multi_select(self, admin_client):
        plan = MemberHealthPlanFactory.create(plan_type=FamilyPlanType.INDIVIDUAL)
        rte = RTETransactionFactory.create()
        exception = errors.NoIndividualDeductibleOopRemaining(
            plan=plan, rte_transaction=rte, message="Test Message"
        )

        with mock.patch(
            "admin.views.models.cost_breakdown.CostBreakdownRecalculationView._validate_user",
            side_effect=exception,
        ):
            res = admin_client.post(
                "/admin/cost_breakdown_calculator/multipleprocedures/submit",
                json={
                    "userId": "-1",
                    "individualDeductible": "",
                    "individualOop": "",
                    "familyDeductible": "",
                    "familyOop": "",
                    "hraRemaining": "",
                    "procedures": [
                        {
                            "type": "medical",
                            "procedure": {"id": "gp_id", "name": "Test"},
                            "clinic_location": {"id": "-1"},
                            "start_date": "0000-00-00",
                        }
                    ],
                },
                headers={"Content-Type": "application/json"},
            )

        assert res.status_code == 400
        assert res.json["error"] == (
            f"This user's health plan "
            f"<a href='/admin/memberhealthplan/edit/?id={plan.id}'>&lt;MemberHealthPlan {plan.id}&gt;</a> "
            f"has no remaining INDIVIDUAL deductible or out-of-pocket maximum according to Pverify: "
            f"<a href='/admin/rtetransaction/edit/?id={rte.id}'>&lt;RTETransaction {rte.id}&gt;</a>. "
            f"Please send this to Payment Ops who can check historical data and pverify or contact the member for an "
            f"accurate explanation of benefits for this procedure."
        )

    @pytest.mark.parametrize(
        "http_status, message",
        [
            (408, "The request to Pverify timed out."),
            (401, "The request to Pverify failed authorization."),
            (500, "The request to Pverify failed with an unexpected error."),
        ],
    )
    def test_pverify_http_error(self, get_cost_breakdown_result, http_status, message):
        # given
        exception = errors.PverifyHttpCallError(
            http_status=http_status, message="Test Message"
        )

        # when
        res = get_cost_breakdown_result(exception)

        # then
        assert res.status_code == 400
        assert res.json["error"].startswith(message)

    def test_pverify_failed_error(self, get_cost_breakdown_result):
        # given
        rte = RTETransactionFactory.create()
        error = "Oh no, an error."
        exception = errors.PverifyProcessFailedError(
            message="Test Message", error=error, rte_transaction=rte
        )

        # when
        res = get_cost_breakdown_result(exception)

        # then
        assert res.status_code == 400
        assert res.json["error"] == (
            f"Pverify has returned the following error: {error} for RTE transaction "
            f"<a href='/admin/rtetransaction/edit/?id={rte.id}'>&lt;RTETransaction {rte.id}&gt;</a>."
        )

    def test_pverify_inactive_error(self, get_cost_breakdown_result):
        plan = MemberHealthPlanFactory.create()
        exception = errors.PverifyPlanInactiveError(plan=plan, message="Test Message")

        # when
        res = get_cost_breakdown_result(exception)

        # then
        assert res.status_code == 400
        assert res.json["error"] == (
            "Pverify has indicated that this user’s plan "
            f"<a href='/admin/memberhealthplan/edit/?id={plan.id}'>&lt;MemberHealthPlan {plan.id}&gt;</a>"
            " is inactive. This user may be on COBRA. "
            "Please reach out to Payment Ops for a manual override using the member's last known RTE data."
        )

    def test_submit_with_error(self, admin_client, procedure):
        with mock.patch(
            "cost_breakdown.cost_breakdown_processor.CostBreakdownProcessor.get_cost_breakdown_for_treatment_procedure",
            side_effect=errors.NoCostSharingCategory("Mock Error"),
        ):
            res = admin_client.post(
                "/admin/cost_breakdown_calculator/submit",
                data={
                    "treatment_ids": f"{procedure.id}",
                    "ind_deductible": "",
                    "ind_oop": "",
                    "family_deductible": "",
                    "family_oop": "",
                    "hra_remaining": "",
                },
                headers={"Content-Type": "multipart/form-data"},
            )

        assert res.status_code == 400
        assert (
            res.json["error"]
            == f"<a href='/admin/treatmentprocedure/edit/?id={procedure.id}'>&lt;TreatmentProcedure {procedure.id}&gt;</a> is missing a Global Procedure Id."
        )

    def test_error_message_is_dynamic(self, wallet):
        category = (
            wallet.reimbursement_organization_settings.allowed_reimbursement_categories[
                0
            ].reimbursement_request_category
        )
        reimbursement_request = ReimbursementRequestFactory.create(
            wallet=wallet, category=category
        )
        treatment_procedure = TreatmentProcedureFactory.create()

        error_message_improver = ErrorMessageImprover()
        exception = errors.NoCostSharingCategory("Test Message")

        error_message_improver.procedure = treatment_procedure
        procedure_message = error_message_improver.get_error_message(
            error=exception, formatter=str
        )

        error_message_improver.procedure = reimbursement_request
        reimbursement_message = error_message_improver.get_error_message(
            error=exception, formatter=str
        )

        error_message_improver.procedure = None
        none_message = error_message_improver.get_error_message(
            error=exception, formatter=str
        )

        assert {procedure_message, reimbursement_message, none_message} == {
            "An unexpected error has occurred. Please reach out to @payments-platform-oncall "
            "and provide the following message: Need Ops Action: Test Message",
            f"{treatment_procedure} is missing a Global Procedure Id.",
            f"{reimbursement_request} is missing a Cost Sharing Category",
        }

    def test_unspecified_message(self):
        error_message_improver = ErrorMessageImprover()
        expected_message = "I am a Test Message"
        exception = TypeError(expected_message)
        result = error_message_improver.get_error_message(
            error=exception, formatter=str
        )
        assert result == (
            "An unexpected error has occurred. Please reach out to @payments-platform-oncall "
            f"and provide the following message: {expected_message}"
        )
