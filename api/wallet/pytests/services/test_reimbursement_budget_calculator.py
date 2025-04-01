from datetime import datetime

import factory
import pytest

from wallet.models.constants import PlanType, ReimbursementRequestState, WalletState
from wallet.pytests.factories import (
    ReimbursementOrgSettingCategoryAssociationFactory,
    ReimbursementPlanFactory,
    ReimbursementRequestCategoryFactory,
    ReimbursementRequestFactory,
    ReimbursementWalletFactory,
)


@pytest.fixture()
def category_association_plan_lifetime(enterprise_user, wallet_org_settings):
    return ReimbursementOrgSettingCategoryAssociationFactory.create(
        reimbursement_request_category_maximum=1000,
        reimbursement_organization_settings=wallet_org_settings,
        reimbursement_request_category=factory.SubFactory(
            ReimbursementRequestCategoryFactory,
            label="fertility",
            reimbursement_plan=factory.SubFactory(
                ReimbursementPlanFactory,
                alegeus_plan_id="FAMILYFUND",
                plan_type=PlanType.LIFETIME.value,
                start_date=datetime.now().date().replace(month=1, day=1),
                end_date=datetime.now().date().replace(month=12, day=31, year=2199),
                is_hdhp=False,
            ),
        ),
    )


@pytest.fixture()
def category_association_plan_lifetime_hdhp(enterprise_user, wallet_org_settings):
    return ReimbursementOrgSettingCategoryAssociationFactory.create(
        reimbursement_request_category_maximum=1000,
        reimbursement_organization_settings=wallet_org_settings,
        reimbursement_request_category=factory.SubFactory(
            ReimbursementRequestCategoryFactory,
            label="fertility",
            reimbursement_plan=factory.SubFactory(
                ReimbursementPlanFactory,
                alegeus_plan_id="FAMILYFUND2",
                plan_type=PlanType.LIFETIME.value,
                start_date=datetime.now().date().replace(month=1, day=1),
                end_date=datetime.now().date().replace(month=12, day=31, year=2199),
                is_hdhp=True,
            ),
        ),
    )


@pytest.fixture()
def category_association_plan_annual(enterprise_user, wallet_org_settings):
    return ReimbursementOrgSettingCategoryAssociationFactory.create(
        reimbursement_request_category_maximum=1000,
        reimbursement_organization_settings=wallet_org_settings,
        reimbursement_request_category=factory.SubFactory(
            ReimbursementRequestCategoryFactory,
            label="fertility",
            reimbursement_plan=factory.SubFactory(
                ReimbursementPlanFactory,
                alegeus_plan_id="FAMILYFUND3",
                plan_type=PlanType.ANNUAL.value,
                start_date=datetime.now().date().replace(month=1, day=1),
                end_date=datetime.now().date().replace(month=12, day=31),
                is_hdhp=False,
            ),
        ),
    )


@pytest.fixture()
def category_association_plan_annual_expired(enterprise_user, wallet_org_settings):
    return ReimbursementOrgSettingCategoryAssociationFactory.create(
        reimbursement_request_category_maximum=1000,
        reimbursement_organization_settings=wallet_org_settings,
        reimbursement_request_category=factory.SubFactory(
            ReimbursementRequestCategoryFactory,
            label="fertility",
            reimbursement_plan=factory.SubFactory(
                ReimbursementPlanFactory,
                alegeus_plan_id="FAMILYFUND4",
                plan_type=PlanType.ANNUAL.value,
                start_date=datetime.now().date().replace(month=1, day=1, year=2020),
                end_date=datetime.now().date().replace(month=12, day=31, year=2020),
                is_hdhp=False,
            ),
        ),
    )


@pytest.fixture()
def category_wallet(
    enterprise_user,
    wallet_org_settings,
    category_association_plan_lifetime,
    category_association_plan_lifetime_hdhp,
    category_association_plan_annual,
    category_association_plan_annual_expired,
):
    wallet = ReimbursementWalletFactory.create(
        reimbursement_organization_settings=wallet_org_settings,
        state=WalletState.QUALIFIED,
    )

    return wallet


@pytest.fixture()
def reimbursement_for_plan_lifetime(
    category_wallet, category_association_plan_lifetime
):
    return ReimbursementRequestFactory.create(
        amount=250,
        wallet=category_wallet,
        category=category_association_plan_lifetime.reimbursement_request_category,
        state=ReimbursementRequestState.REIMBURSED,
    )


@pytest.fixture()
def reimbursement_for_plan_lifetime_hdhp(
    category_wallet, category_association_plan_lifetime_hdhp
):
    return ReimbursementRequestFactory.create(
        amount=250,
        wallet=category_wallet,
        category=category_association_plan_lifetime_hdhp.reimbursement_request_category,
        state=ReimbursementRequestState.REIMBURSED,
    )


@pytest.fixture()
def reimbursement_for_plan_annual(category_wallet, category_association_plan_annual):
    return ReimbursementRequestFactory.create(
        amount=250,
        wallet=category_wallet,
        category=category_association_plan_annual.reimbursement_request_category,
        state=ReimbursementRequestState.REIMBURSED,
    )


@pytest.fixture()
def reimbursement_for_plan_annual_expired(
    category_wallet, category_association_plan_annual_expired
):
    return ReimbursementRequestFactory.create(
        amount=250,
        wallet=category_wallet,
        category=category_association_plan_annual_expired.reimbursement_request_category,
        state=ReimbursementRequestState.REIMBURSED,
    )
