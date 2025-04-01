import pytest

from wallet.models.constants import FamilyPlanType
from wallet.models.reimbursement_wallet import MemberHealthPlan
from wallet.pytests.factories import EmployerHealthPlanFactory, MemberHealthPlanFactory


@pytest.mark.parametrize(
    "plan_type",
    [pytest.param(FamilyPlanType.EMPLOYEE_PLUS), pytest.param(FamilyPlanType.FAMILY)],
)
def test_member_health_plan_family_plans(
    plan_type,
    db,
    basic_qualified_wallet,
):
    employee_plus_mhp = MemberHealthPlanFactory.create(
        reimbursement_wallet=basic_qualified_wallet,
        employer_health_plan=EmployerHealthPlanFactory.create(
            reimbursement_organization_settings=basic_qualified_wallet.reimbursement_organization_settings
        ),
        plan_type=plan_type,
    )
    assert employee_plus_mhp.is_family_plan is True
    employee_plus_mhp_from_query = (
        db.session.query(MemberHealthPlan)
        .filter(
            MemberHealthPlan.is_family_plan, MemberHealthPlan.id == employee_plus_mhp.id
        )
        .one()
    )
    assert employee_plus_mhp_from_query.plan_type == plan_type
    assert employee_plus_mhp_from_query.is_family_plan is True


@pytest.mark.parametrize(
    "plan_type",
    [
        pytest.param(FamilyPlanType.INDIVIDUAL),
        pytest.param(FamilyPlanType.UNDETERMINED),
    ],
)
def test_member_health_plan_non_family_plans(
    plan_type,
    db,
    basic_qualified_wallet,
):
    employee_plus_mhp = MemberHealthPlanFactory.create(
        reimbursement_wallet=basic_qualified_wallet,
        employer_health_plan=EmployerHealthPlanFactory.create(
            reimbursement_organization_settings=basic_qualified_wallet.reimbursement_organization_settings
        ),
        plan_type=plan_type,
    )
    assert employee_plus_mhp.is_family_plan is False
    employee_plus_mhp_from_query = (
        db.session.query(MemberHealthPlan)
        .filter(
            MemberHealthPlan.is_family_plan == False,
            MemberHealthPlan.id == employee_plus_mhp.id,
        )
        .one()
    )
    assert employee_plus_mhp_from_query.plan_type == plan_type
    assert employee_plus_mhp_from_query.is_family_plan is False
