from decimal import Decimal
from unittest import mock

import pytest

from cost_breakdown import errors
from cost_breakdown.cost_breakdown_processor import CostBreakdownProcessor
from cost_breakdown.models.rte import EligibilityInfo
from direct_payment.treatment_procedure.models.treatment_procedure import (
    TreatmentProcedureType,
)
from direct_payment.treatment_procedure.pytests.factories import (
    TreatmentProcedureFactory,
)
from pytests.factories import OrganizationFactory
from wallet.models.constants import CostSharingCategory
from wallet.pytests.factories import EmployerHealthPlanFactory, MemberHealthPlanFactory

"""
# NoCostSharingFoundError for procedure 4c35139e-d83c-420e-8727-c3369903de42
from cost_breakdown.cost_breakdown_processor import TreatmentProcedure, ReimbursementWallet, MemberHealthPlan
procedure = TreatmentProcedure.query.get(756)
plan = MemberHealthPlan.query.get(1319726684299540975)
This appears to be a normal configuration issue and not a logic issue.
"""


def test_no_cost_sharing_found():
    # given
    organization = OrganizationFactory.create()
    employer_health_plan = EmployerHealthPlanFactory.create(
        fam_deductible_limit=400000,
        fam_oop_max_limit=800000,
        ind_deductible_limit=300000,
        ind_oop_max_limit=600000,
        cost_sharings=[],
        rx_integrated=True,
        is_hdhp=True,
        is_deductible_embedded=False,
        is_oop_embedded=False,
        reimbursement_organization_settings__organization_id=organization.id,
        reimbursement_organization_settings__deductible_accumulation_enabled=True,
    )
    member_health_plan = MemberHealthPlanFactory.create(
        employer_health_plan=employer_health_plan,
        reimbursement_wallet__reimbursement_organization_settings=employer_health_plan.reimbursement_organization_settings,
    )
    member_health_plan.member_id = member_health_plan.reimbursement_wallet.user_id
    procedure = TreatmentProcedureFactory.create(
        member_id=member_health_plan.reimbursement_wallet.user_id,
        cost=1200_00,
        procedure_type=TreatmentProcedureType.MEDICAL,
        reimbursement_wallet_id=member_health_plan.reimbursement_wallet.id,
    )
    initial_wallet_balance = 200_000_00

    expected_e9y_info = EligibilityInfo(
        individual_deductible=25000,
        individual_deductible_remaining=0,
        family_deductible=50000,
        family_deductible_remaining=25000,
        individual_oop=150000,
        individual_oop_remaining=79309,
        family_oop=300000,
        family_oop_remaining=229309,
        coinsurance=Decimal(0.0),
        coinsurance_min=None,
        coinsurance_max=None,
        copay=2000,
    )

    # when / then
    with pytest.raises(errors.NoCostSharingFoundError):
        with mock.patch(
            "cost_breakdown.cost_breakdown_processor.CostBreakdownProcessor.get_treatment_cost_sharing_category",
            return_value=CostSharingCategory.CONSULTATION,
        ), mock.patch(
            "cost_breakdown.rte.pverify_api.PverifyAPI.get_real_time_eligibility_data",
        ), mock.patch(
            "cost_breakdown.rte.rte_processor.RTEProcessor._get_deductible_oop",
            return_value=expected_e9y_info,
        ):
            processor = CostBreakdownProcessor()
            processor.get_cost_breakdown_for_treatment_procedure(
                wallet=member_health_plan.reimbursement_wallet,
                treatment_procedure=procedure,
                wallet_balance=initial_wallet_balance,
            )
