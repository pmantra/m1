from wallet.models.constants import WalletState
from wallet.models.reimbursement import (
    ReimbursementPlan,
    ReimbursementRequestCategory,
    ReimbursementWalletPlanHDHP,
)
from wallet.pytests.factories import ReimbursementWalletFactory


def test_reimbursement_plan_category_relationship__no_category():
    plan = ReimbursementPlan()
    assert plan.category is None


def test_reimbursement_plan_category_relationship__with_category():
    category = ReimbursementRequestCategory(label="TEST_CATEGORY")
    plan = ReimbursementPlan(category=category)
    assert plan.category is category


def test_reimbursement_plan_category_relationship__hdhp():
    wallet = ReimbursementWalletFactory.create(
        reimbursement_organization_settings__allowed_reimbursement_categories=[
            ("fertility", 99999, None)
        ],
        state=WalletState.QUALIFIED,
    )
    plan = ReimbursementPlan()
    hdhp_plan = ReimbursementWalletPlanHDHP(wallet=wallet, reimbursement_plan=plan)

    assert hdhp_plan.reimbursement_plan.category is None
