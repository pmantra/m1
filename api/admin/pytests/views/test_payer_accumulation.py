import json

import pytest

from direct_payment.treatment_procedure.models.treatment_procedure import (
    TreatmentProcedureType,
)
from payer_accumulator.common import PayerName, TreatmentAccumulationStatus
from payer_accumulator.models.accumulation_treatment_mapping import (
    AccumulationTreatmentMapping,
)
from payer_accumulator.pytests.factories import (
    AccumulationTreatmentMappingFactory,
    PayerFactory,
)
from wallet.models.constants import (
    CostSharingCategory,
    ReimbursementRequestExpenseTypes,
    ReimbursementRequestState,
)
from wallet.pytests.factories import (
    EmployerHealthPlanFactory,
    MemberHealthPlanFactory,
    ReimbursementRequestFactory,
)
from wallet.pytests.fixtures import WalletTestHelper


@pytest.fixture
def test_payer():
    return PayerFactory.create(payer_name=PayerName.UHC, payer_code="uhc_code")


@pytest.fixture
def accumulation_wallet(test_payer):
    wallet_test_helper = WalletTestHelper()
    organization = wallet_test_helper.create_organization_with_wallet_enabled(
        reimbursement_organization_parameters={"direct_payment_enabled": True}
    )
    wallet_test_helper.add_lifetime_family_benefit(
        organization.reimbursement_organization_settings[0]
    )
    user = wallet_test_helper.create_user_for_organization(
        organization,
        member_profile_parameters={
            "country_code": "US",
            "subdivision_code": "US-NY",
        },
    )
    wallet = wallet_test_helper.create_pending_wallet(
        user,
        wallet_parameters={
            "primary_expense_type": ReimbursementRequestExpenseTypes.FERTILITY
        },
    )
    wallet_test_helper.qualify_wallet(wallet)

    ehp = EmployerHealthPlanFactory.create(
        reimbursement_organization_settings=wallet.reimbursement_organization_settings,
        benefits_payer_id=test_payer.id,
    )
    MemberHealthPlanFactory.create(
        employer_health_plan_id=ehp.id,
        employer_health_plan=ehp,
        reimbursement_wallet_id=wallet.id,
        reimbursement_wallet=wallet,
        member_id=wallet.member.id,
    )
    return wallet


@pytest.fixture
def accumulation_reimbursement_request(accumulation_wallet):
    category = accumulation_wallet.reimbursement_organization_settings.allowed_reimbursement_categories[
        0
    ].reimbursement_request_category
    reimbursement_request = ReimbursementRequestFactory.create(
        wallet=accumulation_wallet,
        category=category,
        state=ReimbursementRequestState.APPROVED,
        amount=100,
        person_receiving_service_id=accumulation_wallet.user_id,
        procedure_type=TreatmentProcedureType.MEDICAL.value,
        cost_sharing_category=CostSharingCategory.MEDICAL_CARE,
    )
    return reimbursement_request


@pytest.fixture
def accumulation_cost_breakdown_data():
    return {
        "amount_type": "INDIVIDUAL",
        "beginning_wallet_balance": 2500.00,
        "calc_config": None,
        "coinsurance": 0,
        "copay": 0,
        "cost": 2000.00,
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
        "total_employer_responsibility": 2000.00,
        "total_member_responsibility": 0,
    }


@pytest.mark.skip(reason="Flaky")
def test_accumulation_from_saved_reimbursement_cost_breakdown(
    admin_client,
    accumulation_reimbursement_request,
    accumulation_cost_breakdown_data,
    test_payer,
):
    assert AccumulationTreatmentMapping.query.count() == 0

    res = admin_client.post(
        "/admin/cost_breakdown_calculator/reimbursementrequest/save",
        data=json.dumps(
            {
                "reimbursement_request_id": accumulation_reimbursement_request.id,
                "cost_breakdown": accumulation_cost_breakdown_data,
            }
        ),
        headers={"Content-Type": "application/json"},
    )

    assert res.status_code == 200
    new_mapping: AccumulationTreatmentMapping = (
        AccumulationTreatmentMapping.query.filter(
            AccumulationTreatmentMapping.reimbursement_request_id
            == accumulation_reimbursement_request.id
        ).one()
    )
    assert new_mapping.payer_id == test_payer.id


@pytest.mark.skip(reason="Flaky")
def test_accumulation_from_saved_reimbursement_cost_breakdown_fails(
    admin_client,
    accumulation_reimbursement_request,
    accumulation_cost_breakdown_data,
    test_payer,
):
    AccumulationTreatmentMappingFactory.create(
        payer_id=test_payer.id,
        reimbursement_request_id=accumulation_reimbursement_request.id,
        treatment_accumulation_status=TreatmentAccumulationStatus.WAITING,
    )

    res = admin_client.post(
        "/admin/cost_breakdown_calculator/reimbursementrequest/save",
        data=json.dumps(
            {
                "reimbursement_request_id": accumulation_reimbursement_request.id,
                "cost_breakdown": accumulation_cost_breakdown_data,
            }
        ),
        headers={"Content-Type": "application/json"},
    )

    # then: the cost breakdown is saved, but a new mapping is not created
    assert res.status_code == 200
    assert AccumulationTreatmentMapping.query.count() == 1
