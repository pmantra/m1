from __future__ import annotations

import datetime
import tempfile
from typing import Optional
from unittest.mock import patch

import factory
import pytest
import stripe
from requests import Response

from authn.models.user import User
from common.wallet_historical_spend import LedgerEntry
from direct_payment.treatment_procedure.models.treatment_procedure import (
    TreatmentProcedureType,
)
from eligibility import e9y
from eligibility.pytests import factories as eligibility_factories
from eligibility.pytests.factories import DateRangeFactory
from payer_accumulator.models.payer_list import PayerName
from payer_accumulator.pytests.factories import PayerFactory
from wallet.alegeus_api import AlegeusApi
from wallet.constants import NUM_CREDITS_PER_CYCLE
from wallet.models.constants import (
    AlegeusCoverageTier,
    BenefitTypes,
    CategoryRuleAccessLevel,
    CategoryRuleAccessSource,
    CostSharingCategory,
    ReimbursementMethod,
    ReimbursementRequestAutoProcessing,
    ReimbursementRequestExpenseTypes,
    ReimbursementRequestState,
    ReimbursementRequestType,
    WalletState,
    WalletUserStatus,
    WalletUserType,
)
from wallet.models.reimbursement import ReimbursementRequestCategory
from wallet.models.reimbursement_organization_settings import (
    ReimbursementOrgSettingCategoryAssociation,
)
from wallet.models.reimbursement_wallet import ReimbursementWallet
from wallet.models.reimbursement_wallet_dashboard import (
    ReimbursementWalletDashboardType,
)
from wallet.models.reimbursement_wallet_user import ReimbursementWalletUsers
from wallet.pytests.factories import (
    AnnualInsuranceQuestionnaireResponseFactory,
    CountryCurrencyCodeFactory,
    EmployerHealthPlanFactory,
    MemberHealthPlanFactory,
    ReimbursementAccountFactory,
    ReimbursementAccountTypeFactory,
    ReimbursementClaimFactory,
    ReimbursementCycleCreditsFactory,
    ReimbursementCycleMemberCreditTransactionFactory,
    ReimbursementOrganizationSettingsFactory,
    ReimbursementOrgSettingCategoryAssociationFactory,
    ReimbursementOrgSettingsAllowedCategoryRuleFactory,
    ReimbursementPlanFactory,
    ReimbursementRequestCategoryExpenseTypesFactory,
    ReimbursementRequestCategoryFactory,
    ReimbursementRequestFactory,
    ReimbursementRequestSourceFactory,
    ReimbursementRequestSourceRequestsFactory,
    ReimbursementServiceCategoryFactory,
    ReimbursementTransactionFactory,
    ReimbursementWalletAllowedCategorySettingsFactory,
    ReimbursementWalletCategoryRuleEvaluationFailureFactory,
    ReimbursementWalletCategoryRuleEvaluationResultFactory,
    ReimbursementWalletDashboardCardFactory,
    ReimbursementWalletDashboardCardsFactory,
    ReimbursementWalletDashboardFactory,
    ReimbursementWalletDebitCardFactory,
    ReimbursementWalletFactory,
    ReimbursementWalletNonMemberDependentFactory,
    ReimbursementWalletPlanHDHPFactory,
    ReimbursementWalletUsersFactory,
    WalletExpenseSubtypeFactory,
    WalletUserAssetFactory,
)

# import the new-style wallet fixtures
from wallet.pytests.fixtures import *  # noqa: F403,F401
from wallet.pytests.wallet.models.test_reimbursement_wallet import REIMBURSED_AMOUNT
from wallet.services.reimbursement_category_activation_visibility import (
    CategoryActivationService,
)
from wallet.services.reimbusement_wallet_dashboard import DASHBOARD_CARD_LINK_URL_TEXT

SUPPORTED_CURRENCY_CODE_MINOR_UNIT = [
    ("USD", 2),
    ("AUD", 2),
    ("NZD", 2),
    ("GBP", 2),
    ("JPY", 0),
]


@pytest.fixture()
def wallet_org_settings(enterprise_user):
    return ReimbursementOrganizationSettingsFactory.create(
        organization_id=enterprise_user.organization.id
    )


@pytest.fixture(scope="function")
def enterprise_user_asset(enterprise_user):
    return WalletUserAssetFactory.create(user=enterprise_user)


@pytest.fixture(scope="function")
def enterprise_user_assets(enterprise_user):
    return WalletUserAssetFactory.create_batch(size=3, user=enterprise_user)


@pytest.fixture(scope="function")
def make_enterprise_user_assets():
    def _make_enterprise_user_assets(size, enterprise_user):
        return WalletUserAssetFactory.create_batch(size=size, user=enterprise_user)

    return _make_enterprise_user_assets


@pytest.fixture(scope="function")
def qualified_wallet(enterprise_user):
    wallet = ReimbursementWalletFactory.create(
        member=enterprise_user, state=WalletState.QUALIFIED
    )
    return wallet


@pytest.fixture(scope="function")
def active_wallet_user(enterprise_user, qualified_wallet):
    wallet_user = ReimbursementWalletUsersFactory.create(
        user_id=enterprise_user.id,
        reimbursement_wallet_id=qualified_wallet.id,
        zendesk_ticket_id=1234,
    )
    return wallet_user


@pytest.fixture(scope="function")
def qualified_alegeus_wallet_hdhp_single(
    qualified_wallet, valid_alegeus_plan_hdhp, active_wallet_user
):
    qualified_wallet.reimbursement_organization_settings.organization.alegeus_employer_id = (
        "123"
    )
    qualified_wallet.alegeus_id = "456"

    # Configure Reimbursement Plan for wallet through an HDHP
    ReimbursementWalletPlanHDHPFactory.create(
        reimbursement_plan=valid_alegeus_plan_hdhp,
        wallet=qualified_wallet,
        alegeus_coverage_tier=AlegeusCoverageTier.SINGLE,
    )

    return qualified_wallet


@pytest.fixture(scope="function")
def qualified_alegeus_wallet_hdhp_family(enterprise_user, valid_alegeus_plan_hdhp):
    wallet = ReimbursementWalletFactory.create(
        member=enterprise_user, state=WalletState.QUALIFIED
    )
    wallet.reimbursement_organization_settings.organization.alegeus_employer_id = "123"
    wallet.alegeus_id = "456"
    ReimbursementWalletUsersFactory.create(
        user_id=enterprise_user.id,
        reimbursement_wallet_id=wallet.id,
    )

    # Configure Reimbursement Plan for wallet through an HDHP
    ReimbursementWalletPlanHDHPFactory.create(
        reimbursement_plan=valid_alegeus_plan_hdhp,
        wallet=wallet,
        alegeus_coverage_tier=AlegeusCoverageTier.FAMILY,
    )

    # This shouldn't be done here. It should be done in the ROS factory. Sadly, that's called by default within
    # the wallet factory.
    ReimbursementRequestCategoryExpenseTypesFactory.create(
        reimbursement_request_category_id=wallet.reimbursement_organization_settings.allowed_reimbursement_categories[
            0
        ].reimbursement_request_category_id,
        expense_type=ReimbursementRequestExpenseTypes.FERTILITY,
    )

    return wallet


@pytest.fixture(scope="function")
def qualified_alegeus_wallet_with_two_hdhp_plans(
    enterprise_user, valid_alegeus_plan_hdhp, valid_next_year_alegeus_plan_hdhp
):
    wallet = ReimbursementWalletFactory.create(
        member=enterprise_user, state=WalletState.QUALIFIED
    )
    wallet.reimbursement_organization_settings.organization.alegeus_employer_id = "123"
    wallet.alegeus_id = "456"
    ReimbursementWalletUsersFactory.create(
        user_id=enterprise_user.id,
        reimbursement_wallet_id=wallet.id,
    )

    # Configure Reimbursement Plan for wallet through an HDHP
    ReimbursementWalletPlanHDHPFactory.create(
        reimbursement_plan=valid_alegeus_plan_hdhp,
        wallet=wallet,
        alegeus_coverage_tier=AlegeusCoverageTier.FAMILY,
    )
    ReimbursementWalletPlanHDHPFactory.create(
        reimbursement_plan=valid_next_year_alegeus_plan_hdhp,
        wallet=wallet,
        alegeus_coverage_tier=AlegeusCoverageTier.FAMILY,
    )

    return wallet


@pytest.fixture(scope="function")
def pending_alegeus_wallet_hra(enterprise_user, valid_alegeus_plan_hra):
    wallet = ReimbursementWalletFactory.create(
        member=enterprise_user,
        state=WalletState.PENDING,
        reimbursement_organization_settings__allowed_reimbursement_categories__no_categories=True,
    )
    wallet.reimbursement_organization_settings.organization.alegeus_employer_id = "123"
    wallet.alegeus_id = "456"
    wallet.member.member_profile.phone_number = "+1-201-555-0123"
    ReimbursementWalletUsersFactory.create(
        user_id=enterprise_user.id,
        reimbursement_wallet_id=wallet.id,
    )

    # Configure Reimbursement Plan for wallet
    org_settings = wallet.reimbursement_organization_settings

    # Fertility category
    fertility_category = ReimbursementRequestCategoryFactory.create(
        label="fertility", reimbursement_plan=valid_alegeus_plan_hra
    )
    ReimbursementOrgSettingCategoryAssociationFactory.create(
        reimbursement_organization_settings=org_settings,
        reimbursement_request_category=fertility_category,
        reimbursement_request_category_maximum=5000,
    )

    # Adoption category
    adoption_category = ReimbursementRequestCategoryFactory.create(
        label="adoption", reimbursement_plan=valid_alegeus_plan_hra
    )
    ReimbursementOrgSettingCategoryAssociationFactory.create(
        reimbursement_organization_settings=org_settings,
        reimbursement_request_category=adoption_category,
        reimbursement_request_category_maximum=5000,
    )

    return wallet


@pytest.fixture(scope="function")
def pending_alegeus_wallet_hra_without_rwu(enterprise_user, valid_alegeus_plan_hra):
    wallet = ReimbursementWalletFactory.create(
        member=enterprise_user, state=WalletState.PENDING
    )
    wallet.reimbursement_organization_settings.organization.alegeus_employer_id = "123"
    wallet.alegeus_id = "456"

    wallet.member.member_profile.phone_number = "+1-201-555-0123"

    # Configure Reimbursement Plan for wallet
    org_settings = wallet.reimbursement_organization_settings
    category = ReimbursementRequestCategoryFactory.create(
        label="fertility", reimbursement_plan=valid_alegeus_plan_hra
    )
    category_association = ReimbursementOrgSettingCategoryAssociationFactory.create(
        reimbursement_organization_settings=org_settings,
        reimbursement_request_category=category,
        reimbursement_request_category_maximum=5000,
    )
    ReimbursementWalletAllowedCategorySettingsFactory.create(
        reimbursement_organization_settings_allowed_category_id=category_association.id,
        reimbursement_wallet_id=wallet.id,
        access_level=CategoryRuleAccessLevel.FULL_ACCESS,
        access_level_source=CategoryRuleAccessSource.NO_RULES,
    )

    return wallet


@pytest.fixture()
def qualified_alegeus_wallet_hra_cycle_based_categories(
    enterprise_user, valid_alegeus_plan_hra
):
    """
    Creates a wallet with 2 cycle-based categories.
    """
    wallet = ReimbursementWalletFactory.create(
        member=enterprise_user, state=WalletState.QUALIFIED
    )
    wallet.reimbursement_organization_settings.organization.alegeus_employer_id = "123"
    wallet.alegeus_id = "456"

    wallet.member.member_profile.phone_number = "+1-201-555-0123"

    # Configure Reimbursement Plan for wallet
    org_settings = wallet.reimbursement_organization_settings
    category1 = ReimbursementRequestCategoryFactory.create(
        label="fertility", reimbursement_plan=valid_alegeus_plan_hra
    )
    category2 = ReimbursementRequestCategoryFactory.create(
        label="happiness", reimbursement_plan=valid_alegeus_plan_hra
    )
    category3 = ReimbursementRequestCategoryFactory.create(
        label="shouldNotBeInTheComputation", reimbursement_plan=valid_alegeus_plan_hra
    )
    category_association = ReimbursementOrgSettingCategoryAssociationFactory.create(
        benefit_type=BenefitTypes.CYCLE,
        reimbursement_organization_settings=org_settings,
        reimbursement_request_category=category1,
        reimbursement_request_category_maximum=0,
        num_cycles=2,
    )
    ReimbursementWalletAllowedCategorySettingsFactory.create(
        reimbursement_organization_settings_allowed_category_id=category_association.id,
        reimbursement_wallet_id=wallet.id,
        access_level=CategoryRuleAccessLevel.FULL_ACCESS,
        access_level_source=CategoryRuleAccessSource.NO_RULES,
    )
    category_association2 = ReimbursementOrgSettingCategoryAssociationFactory.create(
        benefit_type=BenefitTypes.CYCLE,
        reimbursement_organization_settings=org_settings,
        reimbursement_request_category=category2,
        reimbursement_request_category_maximum=0,
        num_cycles=3,
    )
    ReimbursementWalletAllowedCategorySettingsFactory.create(
        reimbursement_organization_settings_allowed_category_id=category_association2.id,
        reimbursement_wallet_id=wallet.id,
        access_level=CategoryRuleAccessLevel.FULL_ACCESS,
        access_level_source=CategoryRuleAccessSource.NO_RULES,
    )
    # This one should not impact cycle-based categories
    category_association3 = ReimbursementOrgSettingCategoryAssociationFactory.create(
        benefit_type=BenefitTypes.CURRENCY,
        reimbursement_organization_settings=org_settings,
        reimbursement_request_category=category3,
        reimbursement_request_category_maximum=23223,
        # Inconsistent num_cycles for CURRENCY-based categories,
        # But we're doing this to make sure it does not change any
        # cycle-based calculations.
        num_cycles=2,
    )
    ReimbursementWalletAllowedCategorySettingsFactory.create(
        reimbursement_organization_settings_allowed_category_id=category_association3.id,
        reimbursement_wallet_id=wallet.id,
        access_level=CategoryRuleAccessLevel.FULL_ACCESS,
        access_level_source=CategoryRuleAccessSource.NO_RULES,
    )
    return wallet


@pytest.fixture()
def cycle_benefits_wallet(enterprise_user):
    n_cycles = 3
    labels_with_max_and_currency_code = [
        ("label_1", None, None),
        ("label_2", None, None),
    ]
    wallet = ReimbursementWalletFactory.create(
        member=enterprise_user,
        reimbursement_organization_settings__allowed_reimbursement_categories=labels_with_max_and_currency_code,
        state=WalletState.QUALIFIED,
    )

    for (
        allowed_category
    ) in wallet.reimbursement_organization_settings.allowed_reimbursement_categories:
        allowed_category.benefit_type = BenefitTypes.CYCLE
        allowed_category.num_cycles = n_cycles
        category = allowed_category.reimbursement_request_category
        rr = ReimbursementRequestFactory.create(
            wallet=wallet,
            category=category,
            amount=123,
            state=ReimbursementRequestState.APPROVED,
        )

        credits = ReimbursementCycleCreditsFactory.create(
            reimbursement_wallet_id=wallet.id,
            reimbursement_organization_settings_allowed_category_id=allowed_category.id,
            amount=n_cycles * NUM_CREDITS_PER_CYCLE,
        )

        ReimbursementCycleMemberCreditTransactionFactory.create(
            reimbursement_cycle_credits_id=credits.id,
            amount=-n_cycles * NUM_CREDITS_PER_CYCLE,
            notes="Initial Fund",
            reimbursement_request_id=rr.id,
        )

    return wallet


@pytest.fixture(scope="function")
def qualified_alegeus_wallet_hra(pending_alegeus_wallet_hra):
    wallet = pending_alegeus_wallet_hra
    wallet.state = WalletState.QUALIFIED

    return wallet


@pytest.fixture(scope="function")
def qualified_verification_hra(qualified_alegeus_wallet_hra):
    verification = eligibility_factories.VerificationFactory.create(
        user_id=qualified_alegeus_wallet_hra.member.id,
        organization_id=qualified_alegeus_wallet_hra.reimbursement_organization_settings.organization_id,
        record={},
        verified_at=qualified_alegeus_wallet_hra.created_at,
        created_at=datetime.datetime.utcnow(),
        verification_type="MOCKED_VERIFICATION_TYPE",
        is_active=True,
    )
    return verification


@pytest.fixture(scope="function")
def qualified_direct_payment_enabled_wallet(qualified_alegeus_wallet_hra):
    wallet = qualified_alegeus_wallet_hra
    wallet.reimbursement_organization_settings.direct_payment_enabled = True

    return wallet


@pytest.fixture(scope="function")
def valid_alegeus_plan_hdhp():
    plan = ReimbursementPlanFactory.create(
        reimbursement_account_type=ReimbursementAccountTypeFactory.create(
            alegeus_account_type="DTR"
        ),
        alegeus_plan_id="HDHP",
        start_date=datetime.date(year=2020, month=1, day=3),
        end_date=datetime.date(year=2199, month=12, day=31),
        is_hdhp=True,
    )
    return plan


@pytest.fixture(scope="function")
def valid_next_year_alegeus_plan_hdhp():
    next_year = datetime.datetime.utcnow().year + 1
    plan = ReimbursementPlanFactory.create(
        reimbursement_account_type=ReimbursementAccountTypeFactory.create(
            alegeus_account_type="DTR"
        ),
        alegeus_plan_id="HDHP2",
        start_date=datetime.date(year=next_year, month=1, day=3),
        end_date=datetime.date(year=2200, month=12, day=31),
        is_hdhp=True,
    )
    return plan


@pytest.fixture(scope="function")
def current_hdhp_plan():
    year = datetime.datetime.utcnow().year
    plan = ReimbursementPlanFactory.create(
        reimbursement_account_type=ReimbursementAccountTypeFactory.create(
            alegeus_account_type="DTR"
        ),
        alegeus_plan_id="HDHP",
        start_date=datetime.date(year=year, month=1, day=1),
        end_date=datetime.date(year=year, month=12, day=31),
        is_hdhp=True,
    )
    return plan


@pytest.fixture(scope="function")
def valid_alegeus_plan_hra():
    plan = ReimbursementPlanFactory.create(
        reimbursement_account_type=ReimbursementAccountTypeFactory.create(
            alegeus_account_type="HRA"
        ),
        alegeus_plan_id="FAMILYFUND",
        start_date=datetime.date(year=2020, month=1, day=3),
        end_date=datetime.date(year=2199, month=12, day=31),
        is_hdhp=False,
    )
    return plan


@pytest.fixture(scope="function")
def valid_alegeus_account_hra():
    account = ReimbursementAccountFactory.create(
        alegeus_account_type=ReimbursementAccountTypeFactory.create(
            alegeus_account_type="HRA"
        ),
        alegeus_flex_account_key="ALEGEUS_FLEX_ACCOUNT_KEY",
    )
    return account


@pytest.fixture(scope="function")
def valid_alegeus_account_hdhp():
    account = ReimbursementAccountFactory.create(
        alegeus_account_type=ReimbursementAccountTypeFactory.create(
            alegeus_account_type="DTR"
        ),
        alegeus_flex_account_key="ALEGEUS_FLEX_ACCOUNT_KEY",
    )
    return account


@pytest.fixture(scope="function")
def valid_reimbursement_request(
    qualified_alegeus_wallet_hdhp_single, enterprise_user_asset
):
    source = ReimbursementRequestSourceFactory.create(
        user_asset=enterprise_user_asset, wallet=qualified_alegeus_wallet_hdhp_single
    )

    category = ReimbursementRequestCategoryFactory.create(label="fertility")

    reimbursement_request = ReimbursementRequestFactory.create(
        wallet=qualified_alegeus_wallet_hdhp_single,
        category=category,
        service_start_date=datetime.datetime.utcnow(),
        amount=100_000,
        state=ReimbursementRequestState.PENDING,
        person_receiving_service="Jane Doe",
        description="new reimbursement request",
    )

    ReimbursementRequestSourceRequestsFactory.create(
        request=reimbursement_request, source=source
    )

    return reimbursement_request


@pytest.fixture(scope="function")
def denied_reimbursement_request(valid_reimbursement_request):
    valid_reimbursement_request.state = ReimbursementRequestState.DENIED
    return valid_reimbursement_request


@pytest.fixture(scope="function")
def qualified_alegeus_wallet_with_dependents(
    qualified_alegeus_wallet_hdhp_family, factories
):
    dependent_1 = factories.OrganizationEmployeeDependentFactory.create(
        reimbursement_wallet_id=qualified_alegeus_wallet_hdhp_family.id,
    )
    dependent_1.create_alegeus_dependent_id()
    dependent_2 = factories.OrganizationEmployeeDependentFactory.create(
        reimbursement_wallet_id=qualified_alegeus_wallet_hdhp_family.id,
    )
    dependent_2.create_alegeus_dependent_id()
    return qualified_alegeus_wallet_hdhp_family


@pytest.fixture(autouse=True, scope="module")
def patch_configure_wallet_in_alegeus(request):
    marks = [m.name for m in request.node.own_markers]
    if "disable_auto_patch_configure_wallet" in marks:
        return
    with patch(
        "wallet.utils.alegeus.enrollments.enroll_wallet.configure_wallet_in_alegeus"
    ) as p:
        return p


@pytest.fixture(scope="function")
def wallet_with_approved_direct_billing_request_no_claim(
    qualified_alegeus_wallet_hdhp_single,
    valid_alegeus_plan_hdhp,
    valid_alegeus_account_hdhp,
    make_enterprise_user_assets,
    enterprise_user,
):
    valid_alegeus_account_hdhp.wallet = qualified_alegeus_wallet_hdhp_single
    valid_alegeus_account_hdhp.plan = valid_alegeus_plan_hdhp

    category = ReimbursementRequestCategoryFactory.create(label="fertility")
    category.reimbursement_plan = valid_alegeus_plan_hdhp

    request_amount = 10000

    ReimbursementRequestFactory.create(
        wallet=qualified_alegeus_wallet_hdhp_single,
        category=category,
        state=ReimbursementRequestState.APPROVED,
        reimbursement_type=ReimbursementRequestType.DIRECT_BILLING,
        amount=request_amount,
        service_start_date=datetime.datetime.utcnow(),
    )
    return qualified_alegeus_wallet_hdhp_single


@pytest.fixture(scope="function")
def wallet_with_pending_requests_no_claims(
    qualified_alegeus_wallet_hdhp_single,
    valid_alegeus_plan_hdhp,
    valid_alegeus_account_hdhp,
    make_enterprise_user_assets,
    enterprise_user,
):
    """
    Use this fixture to simulate requests that haven't been sent to alegeus yet
        but are ready.
    Upon sending to Alegeus, new ReimbursementClaims should be created
        and tied to the ReimbursementRequests.
    """
    all_user_assets = make_enterprise_user_assets(6, enterprise_user)
    valid_alegeus_account_hdhp.wallet = qualified_alegeus_wallet_hdhp_single
    valid_alegeus_account_hdhp.plan = valid_alegeus_plan_hdhp

    category = ReimbursementRequestCategoryFactory.create(label="fertility")
    category.reimbursement_plan = valid_alegeus_plan_hdhp

    request_amount = 10000

    request_1 = ReimbursementRequestFactory.create(
        wallet=qualified_alegeus_wallet_hdhp_single,
        category=category,
        state=ReimbursementRequestState.PENDING,
        amount=request_amount,
        service_start_date=datetime.datetime.utcnow(),
    )
    source_1a = ReimbursementRequestSourceFactory.create(
        user_asset=all_user_assets[0], wallet=qualified_alegeus_wallet_hdhp_single
    )
    ReimbursementRequestSourceRequestsFactory.create(
        request=request_1, source=source_1a
    )
    source_1b = ReimbursementRequestSourceFactory.create(
        user_asset=all_user_assets[1], wallet=qualified_alegeus_wallet_hdhp_single
    )
    ReimbursementRequestSourceRequestsFactory.create(
        request=request_1, source=source_1b
    )

    request_2 = ReimbursementRequestFactory.create(
        wallet=qualified_alegeus_wallet_hdhp_single,
        category=category,
        state=ReimbursementRequestState.PENDING,
        amount=request_amount,
        service_start_date=datetime.datetime.utcnow(),
    )
    source_2a = ReimbursementRequestSourceFactory.create(
        user_asset=all_user_assets[2], wallet=qualified_alegeus_wallet_hdhp_single
    )
    ReimbursementRequestSourceRequestsFactory.create(
        request=request_2, source=source_2a
    )
    source_2b = ReimbursementRequestSourceFactory.create(
        user_asset=all_user_assets[3], wallet=qualified_alegeus_wallet_hdhp_single
    )
    ReimbursementRequestSourceRequestsFactory.create(
        request=request_2, source=source_2b
    )

    request_3 = ReimbursementRequestFactory.create(
        wallet=qualified_alegeus_wallet_hdhp_single,
        category=category,
        state=ReimbursementRequestState.APPROVED,
        amount=request_amount,
        service_start_date=datetime.datetime.utcnow(),
    )

    source_3a = ReimbursementRequestSourceFactory.create(
        user_asset=all_user_assets[4], wallet=qualified_alegeus_wallet_hdhp_single
    )
    ReimbursementRequestSourceRequestsFactory.create(
        request=request_3, source=source_3a
    )
    source_3b = ReimbursementRequestSourceFactory.create(
        user_asset=all_user_assets[5], wallet=qualified_alegeus_wallet_hdhp_single
    )
    ReimbursementRequestSourceRequestsFactory.create(
        request=request_3, source=source_3b
    )

    return qualified_alegeus_wallet_hdhp_single


@pytest.fixture(scope="function")
def wallet_with_pending_currency_specific_request_no_claims(
    request,
    qualified_alegeus_wallet_hdhp_single,
    valid_alegeus_plan_hdhp,
    valid_alegeus_account_hdhp,
    make_enterprise_user_assets,
    enterprise_user,
):
    """
    Use this fixture to simulate currency specific requests that haven't been sent to alegeus yet
        but are ready.
    Upon sending to Alegeus, new ReimbursementClaims should be created
        and tied to the ReimbursementRequests.
    """
    all_user_assets = make_enterprise_user_assets(6, enterprise_user)
    valid_alegeus_account_hdhp.wallet = qualified_alegeus_wallet_hdhp_single
    valid_alegeus_account_hdhp.plan = valid_alegeus_plan_hdhp
    category = ReimbursementRequestCategoryFactory.create(label="fertility")
    category.reimbursement_plan = valid_alegeus_plan_hdhp

    amount: int
    usd_amount: int
    benefit_currency_code: str | None

    (amount, usd_amount, benefit_currency_code) = request.param

    request = ReimbursementRequestFactory.create(
        wallet=qualified_alegeus_wallet_hdhp_single,
        category=category,
        state=ReimbursementRequestState.PENDING,
        usd_amount=usd_amount,
        amount=amount,
        benefit_currency_code=benefit_currency_code,
        service_start_date=datetime.datetime.utcnow(),
    )
    source = ReimbursementRequestSourceFactory.create(
        user_asset=all_user_assets[0], wallet=qualified_alegeus_wallet_hdhp_single
    )
    ReimbursementRequestSourceRequestsFactory.create(request=request, source=source)

    return qualified_alegeus_wallet_hdhp_single


@pytest.fixture(scope="function")
def wallet_with_pending_requests_with_claims_and_attachments(
    wallet_with_pending_requests_no_claims,
):
    """
    Use this fixture to simulate requests that have already been sent to alegeus
        and are still pending.
    ReimbursementClaims are tied to ReimbursementRequests.
    """
    requests = wallet_with_pending_requests_no_claims.reimbursement_requests
    claim_amount = 100

    request_1 = requests[0]
    ReimbursementClaimFactory.create(
        alegeus_claim_id="123abc",
        alegeus_claim_key=1,
        status="pending",
        reimbursement_request=request_1,
        amount=claim_amount,
    )

    request_2 = requests[1]
    ReimbursementClaimFactory.create(
        alegeus_claim_id="456def",
        status="pending",
        reimbursement_request=request_2,
        amount=claim_amount,
    )

    request_3 = requests[2]
    ReimbursementClaimFactory.create(
        alegeus_claim_id="789ghi",
        status="approved",
        reimbursement_request=request_3,
        amount=claim_amount,
    )

    return wallet_with_pending_requests_no_claims


@pytest.fixture(scope="function")
def wallet_with_pending_requests_with_transactions_and_attachments(
    wallet_with_pending_requests_no_claims,
):
    """
    Use this fixture to simulate requests with debit card transactions, some with uploaded attachments.
    """

    ReimbursementWalletDebitCardFactory(
        reimbursement_wallet_id=wallet_with_pending_requests_no_claims.id,
    )
    requests = wallet_with_pending_requests_no_claims.reimbursement_requests
    claim_amount = 100

    request_1 = requests[0]
    request_1.state = ReimbursementRequestState.NEEDS_RECEIPT
    request_1.reimbursement_type = ReimbursementRequestType.DEBIT_CARD
    ReimbursementTransactionFactory.create(
        status="Insufficient documentation",
        reimbursement_request=request_1,
        amount=claim_amount,
    )

    request_2 = requests[1]
    request_2.reimbursement_type = ReimbursementRequestType.DEBIT_CARD
    ReimbursementTransactionFactory.create(
        status="Pending",
        reimbursement_request=request_2,
        amount=claim_amount + 1,
    )

    request_3 = requests[2]
    request_3.reimbursement_type = ReimbursementRequestType.DEBIT_CARD
    ReimbursementTransactionFactory.create(
        status="New",
        reimbursement_request=request_3,
        amount=claim_amount + 2,
    )
    return wallet_with_pending_requests_no_claims


@pytest.fixture(scope="function")
def stripe_event():
    def _stripe_event(reimbursement_request_id, event_type, amount):
        return stripe.Event.construct_from(
            {
                "data": {
                    "object": {
                        "amount": amount,
                        "client_secret": (
                            "pi_1ITvI7KEGJDOxFwycCCqVb3h_secret"
                            "_XZVxG9Mh9cL62HAAMz53eH3MB"
                        ),
                        "confirmation_method": "automatic",
                        "currency": "usd",
                        "id": "pi_1ITvI7KEGJDOxFwycCCqVb3h",
                        "metadata": {
                            "reimbursement_request_id": reimbursement_request_id,
                            "user_id": "fake-user",
                        },
                        "object": "payout",
                        "payment_method_types": ["bank_account"],
                    }
                },
                "id": "evt_1ITvI9KEGJDOxFwy6Bf0gX7Y",
                "object": "event",
                "request": {"id": "req_UQhVFWWTxEwID6", "idempotency_key": ""},
                "type": event_type,
            },
            "stripe_event",
        )

    return _stripe_event


@pytest.fixture(scope="function")
def qualified_wallet_enablement_hdhp_single(qualified_alegeus_wallet_hdhp_single):
    return e9y.WalletEnablement(
        eligibility_date=datetime.date.today(),
        member_id=qualified_alegeus_wallet_hdhp_single.member.id,
        organization_id=qualified_alegeus_wallet_hdhp_single.reimbursement_organization_settings.organization_id,
        # noqa: E501
        enabled=True,
    )


@pytest.fixture(scope="function")
def qualified_wallet_enablement_hdhp_family(qualified_alegeus_wallet_hdhp_family):
    return e9y.WalletEnablement(
        eligibility_date=datetime.date.today(),
        member_id=qualified_alegeus_wallet_hdhp_family.member.id,
        organization_id=qualified_alegeus_wallet_hdhp_family.reimbursement_organization_settings.organization_id,
        # noqa: E501
        enabled=True,
    )


@pytest.fixture(scope="function")
def qualified_wallet_enablement_hra(qualified_alegeus_wallet_hra):
    return e9y.WalletEnablement(
        eligibility_date=datetime.date.today(),
        member_id=qualified_alegeus_wallet_hra.member.id,
        organization_id=qualified_alegeus_wallet_hra.reimbursement_organization_settings.organization_id,  # noqa: E501
        enabled=True,
    )


@pytest.fixture(scope="function")
def qualified_wallet_eligibility_verification(qualified_alegeus_wallet_hra):
    date_range = DateRangeFactory()
    date_range.upper = datetime.datetime.utcnow().date()
    return e9y.EligibilityVerification(
        user_id=qualified_alegeus_wallet_hra.member.id,
        organization_id=qualified_alegeus_wallet_hra.reimbursement_organization_settings.organization_id,  # noqa: E501
        unique_corp_id="Abc212",
        dependent_id="ABC224",
        first_name="Test",
        last_name="User",
        date_of_birth=datetime.date.today(),
        email="test@mavenclinic.com",
        verified_at=datetime.datetime.utcnow(),
        created_at=datetime.datetime.utcnow(),
        verification_type="lookup",
        is_active=True,
        record={"employee_start_date": str(datetime.date.today())},
        effective_range=date_range,
    )


@pytest.fixture()
def wallet_debitcardinator():
    """
    Use the method provided by this fixture to add a debit card to your wallet.
    """

    def _add_debit_card_to_wallet(wallet: ReimbursementWallet, **kwargs):
        wallet.debit_card = ReimbursementWalletDebitCardFactory(
            reimbursement_wallet_id=wallet.id,
            **kwargs,
        )

    return _add_debit_card_to_wallet


@pytest.fixture(scope="function")
def alegeus_api():
    return AlegeusApi()


@pytest.fixture()
def post_card_issue_response():
    def _post_card_issue_response(wallet):
        response = {
            "CardIssueCde": 2,
            "CardLast4Digits": "0205",
            "CardProxyNumber": "1100054003980205",
            "CardStatusCode": 1,
            "DependentId": None,
            "EmployeeId": wallet.alegeus_id,
            "FirstName": wallet.member.first_name,
            "LastName": wallet.member.last_name,
            "MailedDate": "",
            "MiddleInitial": "",
            "NamePrefix": "",
        }
        return response

    return _post_card_issue_response


@pytest.fixture()
def get_card_details_response():
    def _get_card_details_response(wallet):
        response = {
            "ActivationDate": "",
            "CardDesignID": "PAYMENT",
            "CardEffectiveDate": "20220712",
            "CardExpireDate": "20270831",
            "CardLast4Digits": "0205",
            "CardProxyNumber": "1100054003980205",
            "CardStatusCode": 1,
            "CardStatusReasonCode": 17,
            "CreationDate": "20220712",
            "DependentID": "",
            "EmployeeId": wallet.alegeus_id,
            "EmployerID": "MVNEF475482",
            "IssueDate": "20220712",
            "IssuedBy": "CARDAGENT",
            "LastUpdatedDateTime": "/Date(1657640202460-0500)/",
            "MailedDate": "",
            "PINMailedDate": "",
            "PINMailerAddress": "160 Varick St, New York, NY  10013",
            "PINMailerRequestDate": "",
            "PickDate": 0,
            "PrimaryCard": True,
            "ShipmentTrackingNumber": "",
            "ShippingAddress": "160 Varick St, New York, NY  10013",
            "ThermalFrontLogoID": "",
            "UserDefinedField": "",
            "ReissueCard": False,
        }

        return response

    return _get_card_details_response


@pytest.fixture()
def put_debit_card_update_status_response():
    def _put_debit_card_update_status_response(wallet, status=5):
        response = {
            "CardIssueCde": 2,
            "CardLast4Digits": "0205",
            "CardProxyNumber": "1100054003980205",
            "CardStatusCode": status,
            "DependentId": None,
            "EmployeeId": wallet.alegeus_id,
            "FirstName": "Tester",
            "LastName": "Debit Wallet",
            "MailedDate": "",
            "MiddleInitial": "",
            "NamePrefix": "",
        }
        return response

    return _put_debit_card_update_status_response


@pytest.fixture()
def get_employee_activity_response():
    def _get_employee_activity_response(
        start_date="/Date(1660712400000-0500)/",
        status_code=16,
        has_receipts=True,
    ):
        response = [
            {
                "AccountsPaidAmount": 0.0000,
                "Actions": 5,
                "AllowedAmount": 0,
                "Amount": 150.0000,
                "BilledAmount": 0,
                "CardTransactionDetails": {
                    "AccountTypeCode": "HRA",
                    "ApprovedAmount": 0.0000,
                    "BalanceDueAmount": 150.0000,
                    "DenialReason": "",
                    "IneligibleAmount": 150.0000,
                    "IneligibleReason": "0006 - Insufficient substantiation of claim received.  Documentation must contain date of service, provider, patient, services rendered and amount.",
                    "MerchantName": "MEDICALTESTING",
                    "MerchantType": "In-Vitro and N-Vitro Diagnostics",
                    "PostedAmount": 150.0000,
                    "CustomDescription": "FAMILYFUND",
                },
                "CheckNumber": None,
                "ClaimAdjudicationDetails": None,
                "ClaimId": "",
                "ClaimKey": -1,
                "Claimant": "Jane Doe",
                "CoveredAmount": 0,
                "Date": "/Date(1663758848047-0500)/",
                "DeductibleAmount": 0,
                "DenialReason": None,
                "Description": "CARD - POST",
                "DisplayStatus": "Paid",
                "ExcludedReason": None,
                "ExpenseKey": 0,
                "ExpensesDetails": None,
                "HasReceipts": has_receipts,
                "OffsetAmount": 0.0000,
                "OutOfPocketAmount": 0,
                "PaidToProvider": False,
                "PatientAccountNumber": "",
                "PatientName": "",
                "PendedComment": None,
                "PendedReason": None,
                "Provider": "",
                "ProviderId": "",
                "ProviderKey": 0,
                "ReceiptsDetails": [],
                "ReimbursementDate": None,
                "ReimbursementDetails": None,
                "ReimbursementMethod": None,
                "RemainingResponsibilityAmount": 150.0000,
                "RenderingProvider": "",
                "ResponsibilityAmount": 150.0000,
                "SeqNumber": 1,
                "ServiceCategoryCode": "",
                "ServiceCategoryName": "",
                "ServiceEndDate": "/Date(1663736400000-0500)/",
                "ServiceStartDate": start_date,
                "SettlementDate": "20220921",
                "Status": "Ineligible Purchase",
                "StatusCode": status_code,
                "StatusWithAmount": "$150.0000 Ineligible Purchase",
                "TrackingNumber": "",
                "TransactionKey": "1250000411-20220817-16154520",
                "Type": "CARD TRANSACTION",
                "TypeCode": 2,
                "CustomDescription": "FAMILYFUND",
                "PostTaxAmt": 0.0000,
                "PreTaxAmt": 0.0000,
                "TaxYear": "    ",
                "AcctTypeCode": "HRA",
                "BalanceDue": 150.0000,
                "FlexAcctKey": 155,
                "HSABillPayInfo": None,
                "HSATransactionDetail": None,
                "RepaymentInitiatedDate": None,
                "RepaymentStatus": 1,
            },
        ]
        return response

    return _get_employee_activity_response


@pytest.fixture()
def en_record():
    def _en_record(status_code="AUP2"):
        line = [
            "EN",
            "50002878",
            "20220818",
            "T01676",
            "MVN67AE99BD",
            "456",
            "FERTHRA2021",
            "HRA",
            "20210101",
            "21991231",
            "1.50",
            "20220818093006",
            "000000",
            "",
            "",
            "",
            "",
            "",
            "",
            "1250000411-20220817-16154520",
            "12",
            "20220818101733",
            "cele_beta",
            status_code,
            "",
            "",
            "0",
            "1100054003980205",
        ]
        return line

    return _en_record


@pytest.fixture()
def ek_record():
    return [
        "EK",
        "50003156",
        "T01676",
        "MVNIMPORT",
        "HDHPANNUAL",
        "456",
        "HRA",
        "20220101",
        "20221231",
        "258369147HRA",
        "1100054076452725",
        "",
        "",
        "2835",
        "2835",
        "",
        "5.25",
        "5.25",
        "5.25",
        "5.25",
        "12",
        "AUP3",
        "",
        "20220908143558",
        "20220908143558",
        "20220908",
        "20220908144442",
        "20220908",
        "144442",
        "5.25",
        "1250003156-20220908-14355875",
    ]


@pytest.fixture()
def em_record():
    def _em_record(status=5):
        return (
            f'EM,T01676,MVND9857963,456,,20221013,20280131,20221013,101550,1100054058115420,0,{status},3,"160 '
            'Varick St,New York, NY  10013",20221013,20220919,20221013,20221013,tracking-number-123'
        )

    return _em_record


@pytest.fixture()
def export_file():
    f = tempfile.TemporaryFile()
    f.write(
        b"EK,50015430,T01676,MVNIMPORT,HDHPANNUAL,456,HRA,20220101,20221231,369147258HRA,1100054073677275,,,"
        b"2835,2835,,40.00,40.00,40.00,0.00,12,AUPI,,20220913073448,20220913000000,20220913,20220913073936,"
        b"20220913,073936,0.00,1250000411-20220817-16154520\r\n "
        b"EN,50002878,20220818,T01676,MVN67AE99BD,456,FERTHRA2021,HRA,20210101,21991231,1.50,20220818093006,"
        b"000000,,,,,,,1250002878-20220818-09300641,12,20220818101733,cele_beta,AUP2,,,0,1100054003980205\r\n "
        b'EM,T01676,MVNTEST,456,,20220823,20280131,20220823,112433,1100054071243581,0,5,3,"1601 Trapelo Rd,'
        b'North Bldg. Ste 301,Waltham, MA  02451",20220823,,20220823,20220823,Hybrid Carryover,,Test\r\n'
    )
    f.seek(0)
    return f


@pytest.fixture()
def employer_config_results_file_no_error():
    f = tempfile.TemporaryFile()
    f.write(
        b"RA, MAVEN_IU_4_2.mbi, 20230301, 2, 0, 1, Maven_Conversion_Results\r\n"
        b"RU, 0, T01676, MVNfd12c803, MVNLOCAL2023, HRA, 20230101, 20231231,"
    )
    f.seek(0)
    return f


@pytest.fixture()
def employer_config_results_file_error():
    f = tempfile.TemporaryFile()
    f.write(
        b"RA, MAVEN_IU_4_2.mbi, 20230301, 2, 1, 1, Maven_Conversion_Results\r\n"
        b"RU, 111004, T01676, MVNfd12c803, MVNLOCAL2023, HRA, 20230101, 20231231,"
    )
    f.seek(0)
    return f


@pytest.fixture(autouse=True, scope="function")
def wallet_dashboard():
    none_dashboard = ReimbursementWalletDashboardFactory.create(
        type=ReimbursementWalletDashboardType.NONE
    )
    pending_dashboard = ReimbursementWalletDashboardFactory.create(
        type=ReimbursementWalletDashboardType.PENDING
    )
    disqualified_dashboard = ReimbursementWalletDashboardFactory.create(
        type=ReimbursementWalletDashboardType.DISQUALIFIED
    )

    generic_card = ReimbursementWalletDashboardCardFactory.create(
        title="Generic Card", link_url=DASHBOARD_CARD_LINK_URL_TEXT
    )
    debit_card = ReimbursementWalletDashboardCardFactory.create(
        title="Debit Card", require_debit_eligible=True
    )
    pending_card = ReimbursementWalletDashboardCardFactory.create(title="Pending Card")
    disqualified_card = ReimbursementWalletDashboardCardFactory.create(
        title="Disqualified Card"
    )

    ReimbursementWalletDashboardCardsFactory.create(
        dashboard=none_dashboard, card=generic_card, order=10
    )
    ReimbursementWalletDashboardCardsFactory.create(
        dashboard=none_dashboard, card=debit_card, order=20
    )
    ReimbursementWalletDashboardCardsFactory.create(
        dashboard=pending_dashboard, card=pending_card, order=10
    )
    ReimbursementWalletDashboardCardsFactory.create(
        dashboard=pending_dashboard, card=generic_card, order=20
    )
    ReimbursementWalletDashboardCardsFactory.create(
        dashboard=pending_dashboard, card=debit_card, order=30
    )
    ReimbursementWalletDashboardCardsFactory.create(
        dashboard=disqualified_dashboard, card=disqualified_card, order=10
    )
    ReimbursementWalletDashboardCardsFactory.create(
        dashboard=disqualified_dashboard, card=generic_card, order=20
    )
    ReimbursementWalletDashboardCardsFactory.create(
        dashboard=disqualified_dashboard, card=debit_card, order=30
    )


@pytest.fixture()
def create_multi_member_wallet_and_users(factories):
    def create_enterprise_multi_member_user(user_types):
        to_return_users = []
        to_return_wallet = None
        for user_type in user_types:
            user = factories.EnterpriseUserFactory.create()
            user.organization_employee.json = {"wallet_enabled": True}
            user.profile.country_code = "US"
            if not to_return_wallet:
                to_return_wallet = ReimbursementWalletFactory.create(
                    member=user, state=WalletState.QUALIFIED
                )

            ReimbursementWalletUsersFactory.create(
                user_id=user.id,
                reimbursement_wallet_id=to_return_wallet.id,
                type=user_type,
                status=WalletUserStatus.ACTIVE,
                channel_id=None,
                zendesk_ticket_id=None,
                alegeus_dependent_id="",
            )
            to_return_users.append(user)
        return to_return_wallet, to_return_users

    return create_enterprise_multi_member_user


@pytest.fixture(scope="function")
def questionnaire_wallet_user(enterprise_user) -> ReimbursementWalletUsers:
    wallet = ReimbursementWalletFactory.create(
        state=WalletState.QUALIFIED,
        reimbursement_organization_settings__allowed_reimbursement_categories=[
            ("fertility", 5000, None),
            ("other", 3000, None),
        ],
        reimbursement_method=ReimbursementMethod.PAYROLL,
    )
    return ReimbursementWalletUsersFactory.create(
        user_id=enterprise_user.id,
        reimbursement_wallet_id=wallet.id,
    )


@pytest.fixture(scope="function")
def annual_insurance_questionnaire_response():
    def fn(
        wallet_id,
        submitting_user_id,
        questionnaire_id="long_2024",
        user_response_json='{"key": "value"}',
        sync_status=None,
        sync_attempt_at=None,
        survey_year=2024,
    ):
        return AnnualInsuranceQuestionnaireResponseFactory(
            wallet_id=wallet_id,
            questionnaire_id=questionnaire_id,
            user_response_json=user_response_json,
            submitting_user_id=submitting_user_id,
            sync_status=sync_status,
            sync_attempt_at=sync_attempt_at,
            survey_year=survey_year,
        )

    return fn


@pytest.fixture(scope="function")
def wallet_for_events(enterprise_user):
    def fn(categories, is_direct_payment_eligible, allowed_members):
        wallet = ReimbursementWalletFactory.create(
            member=enterprise_user,
            state=WalletState.QUALIFIED,
            reimbursement_organization_settings__allowed_reimbursement_categories=[
                categories
            ],
        )
        ReimbursementWalletUsersFactory.create(
            reimbursement_wallet_id=wallet.id,
            user_id=enterprise_user.id,
            status=WalletUserStatus.ACTIVE,
            type=WalletUserType.EMPLOYEE,
        )
        org_settings = wallet.reimbursement_organization_settings
        org_settings.direct_payment_enabled = is_direct_payment_eligible
        org_settings.allowed_members = allowed_members
        wallet.member.member_profile.country_code = "US"
        category_association = org_settings.allowed_reimbursement_categories[0]
        category_association.is_direct_payment_eligible = is_direct_payment_eligible
        request_category = category_association.reimbursement_request_category
        ReimbursementRequestCategoryExpenseTypesFactory.create(
            reimbursement_request_category=request_category,
            expense_type=ReimbursementRequestExpenseTypes.FERTILITY,
        )
        # if is_direct_payment_eligible:
        ReimbursementPlanFactory.create(
            category=request_category,
            start_date=datetime.datetime(datetime.datetime.now().year, 1, 1).date(),
            end_date=datetime.datetime(datetime.datetime.now().year, 12, 31).date(),
        )
        ReimbursementWalletAllowedCategorySettingsFactory.create(
            reimbursement_organization_settings_allowed_category_id=category_association.id,
            reimbursement_wallet_id=wallet.id,
            access_level=CategoryRuleAccessLevel.FULL_ACCESS,
            access_level_source=CategoryRuleAccessSource.NO_RULES,
        )
        return wallet

    return fn


# Deprecated. Use reimbursement_request_data_generator instead to get predictable results.
@pytest.fixture
def reimbursement_request_data(
    qualified_alegeus_wallet_hdhp_family,
    enterprise_user,
    valid_alegeus_plan_hra,
    reimbursement_request_data_generator,
):
    return reimbursement_request_data_generator(
        qualified_alegeus_wallet_hdhp_family,
        enterprise_user,
    )


@pytest.fixture
def reimbursement_request_data_generator(make_enterprise_user_assets, expense_subtypes):
    def _reimbursement_request_data_generator(wallet: ReimbursementWallet, user: User):
        assets = make_enterprise_user_assets(2, user)

        category_association: ReimbursementOrgSettingCategoryAssociation = (
            wallet.get_or_create_wallet_allowed_categories[0]
        )

        category = category_association.reimbursement_request_category

        ReimbursementWalletNonMemberDependentFactory.create(
            id=12345,
            reimbursement_wallet_id=wallet.id,
        )

        return {
            "category_id": category.id,
            "service_provider": "NYU Langone Fertility Center",
            "description": "Fertility expenses",
            "service_start_date": "2024-01-25",
            "person_receiving_service_id": user.id,
            "person_receiving_service_name": "Amelia",
            "amount": 4000,
            "currency_code": "USD",
            "wallet_id": wallet.id,
            "sources": [
                {
                    "source_id": assets[0].id,
                },
                {
                    "source_id": assets[1].id,
                },
            ],
            "submitter_user_id": user.id,
            "expense_type": "Fertility",
            "expense_subtype_id": str(expense_subtypes["FIVF"].id),
        }
        pass

    return _reimbursement_request_data_generator


@pytest.fixture(scope="function", autouse=True)
def supported_currency_codes():
    for currency_code, minor_unit in SUPPORTED_CURRENCY_CODE_MINOR_UNIT:
        CountryCurrencyCodeFactory.create(
            country_alpha_2=currency_code,
            currency_code=currency_code,
            minor_unit=minor_unit,
        )


@pytest.fixture
def category_associations_with_rules_and_settings(
    valid_alegeus_plan_hra, qualified_wallet
):
    org_settings = qualified_wallet.reimbursement_organization_settings
    category_2: ReimbursementRequestCategory = (
        ReimbursementRequestCategoryFactory.create(
            label="Preservation", reimbursement_plan=valid_alegeus_plan_hra
        )
    )
    allowed_category_2: ReimbursementOrgSettingCategoryAssociation = (
        ReimbursementOrgSettingCategoryAssociationFactory.create(
            reimbursement_organization_settings_id=org_settings.id,
            reimbursement_organization_settings=org_settings,
            reimbursement_request_category=category_2,
            reimbursement_request_category_id=category_2.id,
            benefit_type=BenefitTypes.CYCLE,
            num_cycles=2,
        )
    )
    allowed_ids = [ac.id for ac in org_settings.allowed_reimbursement_categories]

    ReimbursementWalletAllowedCategorySettingsFactory.create_batch(
        size=2,
        reimbursement_organization_settings_allowed_category_id=factory.Iterator(
            allowed_ids
        ),
        reimbursement_wallet_id=qualified_wallet.id,
        access_level=CategoryRuleAccessLevel.FULL_ACCESS,
        access_level_source=CategoryRuleAccessSource.RULES,
    )

    rule = ReimbursementOrgSettingsAllowedCategoryRuleFactory.create(
        reimbursement_organization_settings_allowed_category_id=allowed_category_2.id
    )
    allowed_category_2.reimbursement_org_settings_allowed_category_rule = rule
    return allowed_category_2


@pytest.fixture
def category_association_with_rule(valid_alegeus_plan_hra, qualified_wallet):
    org_settings = qualified_wallet.reimbursement_organization_settings
    category: ReimbursementRequestCategory = ReimbursementRequestCategoryFactory.create(
        label="Preservation", reimbursement_plan=valid_alegeus_plan_hra
    )
    allowed_category: ReimbursementOrgSettingCategoryAssociation = (
        ReimbursementOrgSettingCategoryAssociationFactory.create(
            reimbursement_organization_settings_id=org_settings.id,
            reimbursement_organization_settings=org_settings,
            reimbursement_request_category=category,
            reimbursement_request_category_id=category.id,
            benefit_type=BenefitTypes.CYCLE,
            num_cycles=2,
        )
    )
    rule = ReimbursementOrgSettingsAllowedCategoryRuleFactory.create(
        reimbursement_organization_settings_allowed_category_id=allowed_category.id,
        rule_name="TENURE_ONE_CALENDAR_YEAR",
    )
    allowed_category.reimbursement_org_settings_allowed_category_rule = rule
    return allowed_category, rule


@pytest.fixture
def category_associations_with_a_rule(valid_alegeus_plan_hra, qualified_wallet):
    org_settings = qualified_wallet.reimbursement_organization_settings
    to_return = []
    for label in ["Preservation", "Adoption"]:
        category: ReimbursementRequestCategory = (
            ReimbursementRequestCategoryFactory.create(
                label=label, reimbursement_plan=valid_alegeus_plan_hra
            )
        )
        allowed_category: ReimbursementOrgSettingCategoryAssociation = (
            ReimbursementOrgSettingCategoryAssociationFactory.create(
                reimbursement_organization_settings_id=org_settings.id,
                reimbursement_organization_settings=org_settings,
                reimbursement_request_category=category,
                reimbursement_request_category_id=category.id,
                benefit_type=BenefitTypes.CYCLE,
                num_cycles=2,
            )
        )
        rule = ReimbursementOrgSettingsAllowedCategoryRuleFactory.create(
            reimbursement_organization_settings_allowed_category_id=allowed_category.id,
            rule_name="TENURE_ONE_CALENDAR_YEAR",
        )
        allowed_category.reimbursement_org_settings_allowed_category_rule = rule
        to_return.append(
            (
                allowed_category,
                rule,
            )
        )
    return to_return


@pytest.fixture
def category_association_with_setting(valid_alegeus_plan_hra, qualified_wallet):
    org_settings = qualified_wallet.reimbursement_organization_settings
    category: ReimbursementRequestCategory = ReimbursementRequestCategoryFactory.create(
        label="Preservation", reimbursement_plan=valid_alegeus_plan_hra
    )
    allowed_category: ReimbursementOrgSettingCategoryAssociation = (
        ReimbursementOrgSettingCategoryAssociationFactory.create(
            reimbursement_organization_settings_id=org_settings.id,
            reimbursement_organization_settings=org_settings,
            reimbursement_request_category=category,
            reimbursement_request_category_id=category.id,
            benefit_type=BenefitTypes.CYCLE,
            num_cycles=2,
        )
    )
    setting = ReimbursementWalletAllowedCategorySettingsFactory.create(
        reimbursement_organization_settings_allowed_category_id=allowed_category.id,
        reimbursement_wallet_id=qualified_wallet.id,
        access_level=CategoryRuleAccessLevel.FULL_ACCESS,
        access_level_source=CategoryRuleAccessSource.NO_RULES,
    )
    return allowed_category, setting


@pytest.fixture
def category_service(session):
    service = CategoryActivationService(session=session)
    return service


@pytest.fixture(scope="function")
def wallet_cycle_based(enterprise_user):
    org_settings = ReimbursementOrganizationSettingsFactory(
        organization_id=enterprise_user.organization.id,
        allowed_reimbursement_categories__cycle_based=True,
        direct_payment_enabled=True,
    )

    wallet = ReimbursementWalletFactory.create(
        reimbursement_organization_settings=org_settings,
        member=enterprise_user,
        state=WalletState.QUALIFIED,
    )
    wallet_user = ReimbursementWalletUsersFactory.create(
        user_id=enterprise_user.id,
        reimbursement_wallet_id=wallet.id,
    )
    wallet_user.member.member_profile.country_code = "US"
    category_association = (
        wallet.reimbursement_organization_settings.allowed_reimbursement_categories[0]
    )
    category_association.is_direct_payment_eligible = True
    request_category = category_association.reimbursement_request_category
    ReimbursementRequestCategoryExpenseTypesFactory.create(
        reimbursement_request_category=request_category,
        expense_type=ReimbursementRequestExpenseTypes.FERTILITY,
    )
    year = datetime.datetime.utcnow().year
    request_category.reimbursement_plan = ReimbursementPlanFactory.create(
        reimbursement_account_type=ReimbursementAccountTypeFactory.create(
            alegeus_account_type="HRA"
        ),
        alegeus_plan_id="FERTILITY",
        start_date=datetime.date(year=year, month=1, day=1),
        end_date=datetime.date(year=year, month=12, day=31),
        is_hdhp=False,
    )

    credits = ReimbursementCycleCreditsFactory.create(
        reimbursement_wallet_id=wallet.id,
        reimbursement_organization_settings_allowed_category_id=category_association.id,
        amount=12,
    )
    ReimbursementCycleMemberCreditTransactionFactory.create(
        reimbursement_cycle_credits_id=credits.id,
        amount=12,
        notes="Initial Fund",
    )
    return wallet


@pytest.fixture(scope="function")
def rx_reimbursement_request(
    qualified_direct_payment_enabled_wallet,
    valid_alegeus_plan_hra,
    valid_alegeus_account_hra,
):
    valid_alegeus_account_hra.wallet = qualified_direct_payment_enabled_wallet
    valid_alegeus_account_hra.plan = valid_alegeus_plan_hra
    category_association = qualified_direct_payment_enabled_wallet.reimbursement_organization_settings.allowed_reimbursement_categories[
        0
    ]
    category_association.reimbursement_request_category_maximum = 10000
    category = category_association.reimbursement_request_category
    category.reimbursement_plan = valid_alegeus_plan_hra
    return ReimbursementRequestFactory.create(
        reimbursement_wallet_id=qualified_direct_payment_enabled_wallet.id,
        reimbursement_request_category_id=category.id,
        reimbursement_type=ReimbursementRequestType.MANUAL,
        procedure_type=TreatmentProcedureType.PHARMACY.value,
        cost_sharing_category=CostSharingCategory.GENERIC_PRESCRIPTIONS,
        person_receiving_service_id=qualified_direct_payment_enabled_wallet.user_id,
        person_receiving_service=qualified_direct_payment_enabled_wallet.member.full_name,
        person_receiving_service_member_status="MEMBER",
        expense_type=ReimbursementRequestExpenseTypes.FERTILITY,
        cost_credit=0,
        amount=5000,
        auto_processed=ReimbursementRequestAutoProcessing.RX,
    )


@pytest.fixture
def member_health_plan_for_wallet(qualified_direct_payment_enabled_wallet):
    emp = EmployerHealthPlanFactory.create(
        name="Test Plan",
        reimbursement_organization_settings=qualified_direct_payment_enabled_wallet.reimbursement_organization_settings,
    )
    mhp = MemberHealthPlanFactory.create(
        employer_health_plan=emp,
        reimbursement_wallet=qualified_direct_payment_enabled_wallet,
    )
    PayerFactory.create(id=1, payer_name=PayerName.UHC, payer_code="uhc_code")
    return mhp


@pytest.fixture(scope="function")
def qualified_wallet_eligibility_verification_record(enterprise_user):
    date_range = DateRangeFactory()
    date_range.upper = datetime.datetime.utcnow().date()
    return e9y.EligibilityVerification(
        user_id=enterprise_user.id,
        organization_id=enterprise_user.organization.id,  # noqa: E501
        unique_corp_id="Abc212",
        dependent_id="ABC224",
        first_name="Test",
        last_name="User",
        date_of_birth=datetime.date.today(),
        email="test@mavenclinic.com",
        verified_at=datetime.datetime.utcnow(),
        created_at=datetime.datetime.utcnow(),
        verification_type="lookup",
        is_active=True,
        record={"employee_start_date": str(datetime.date.today())},
        effective_range=date_range,
    )


@pytest.fixture()
def two_category_wallet(enterprise_user):
    labels_with_max_and_currency_code = [
        ("label_1", 5000, "USD"),
        ("label_2", 10_000, "USD"),
    ]
    return ReimbursementWalletFactory.create(
        member=enterprise_user,
        reimbursement_organization_settings__allowed_reimbursement_categories=labels_with_max_and_currency_code,
        state=WalletState.QUALIFIED,
    )


@pytest.fixture()
def two_category_wallet_with_active_plans(two_category_wallet):
    today = datetime.date.today()

    for (
        category_assoc
    ) in (
        two_category_wallet.reimbursement_organization_settings.allowed_reimbursement_categories
    ):
        category = category_assoc.reimbursement_request_category
        ReimbursementPlanFactory.create(
            category=category,
            start_date=today - datetime.timedelta(days=2),
            end_date=today + datetime.timedelta(days=2),
        )

        ReimbursementRequestFactory.create(
            wallet=two_category_wallet,
            category=category,
            amount=REIMBURSED_AMOUNT,
            state=ReimbursementRequestState.REIMBURSED,
        )

        ReimbursementRequestFactory.create(
            wallet=two_category_wallet,
            category=category,
            amount=REIMBURSED_AMOUNT,
            state=ReimbursementRequestState.APPROVED,
        )

    return two_category_wallet


@pytest.fixture()
def two_category_wallet_with_active_plans_no_reimbursement_requests(
    two_category_wallet,
):
    today = datetime.date.today()
    for (
        category_assoc
    ) in (
        two_category_wallet.reimbursement_organization_settings.allowed_reimbursement_categories
    ):
        category = category_assoc.reimbursement_request_category
        ReimbursementPlanFactory.create(
            category=category,
            start_date=today - datetime.timedelta(days=2),
            end_date=today + datetime.timedelta(days=2),
        )
    return two_category_wallet


@pytest.fixture()
def two_category_wallet_with_inactive_plans(two_category_wallet):
    today = datetime.date.today()

    for (
        category_assoc
    ) in (
        two_category_wallet.reimbursement_organization_settings.allowed_reimbursement_categories
    ):
        category = category_assoc.reimbursement_request_category
        ReimbursementPlanFactory.create(
            category=category,
            start_date=today - datetime.timedelta(days=4),
            end_date=today - datetime.timedelta(days=2),
        )

        ReimbursementRequestFactory.create(
            wallet=two_category_wallet,
            category=category,
            amount=REIMBURSED_AMOUNT,
            state=ReimbursementRequestState.REIMBURSED,
        )

        ReimbursementRequestFactory.create(
            wallet=two_category_wallet,
            category=category,
            amount=REIMBURSED_AMOUNT,
            state=ReimbursementRequestState.APPROVED,
        )

    return two_category_wallet


@pytest.fixture()
def two_category_wallet_with_active_and_inactive_plans(two_category_wallet):
    today = datetime.date.today()

    inactive_plan = ReimbursementPlanFactory.create(
        start_date=today - datetime.timedelta(days=4),
        end_date=today - datetime.timedelta(days=2),
    )
    active_plan = ReimbursementPlanFactory.create(
        start_date=today - datetime.timedelta(days=2),
        end_date=today + datetime.timedelta(days=2),
    )
    plans = [inactive_plan, active_plan]

    for i, category_assoc in enumerate(
        two_category_wallet.reimbursement_organization_settings.allowed_reimbursement_categories
    ):
        category = category_assoc.reimbursement_request_category
        plan = plans[i]
        plan.category = category

        ReimbursementRequestFactory.create(
            wallet=two_category_wallet,
            category=category,
            amount=REIMBURSED_AMOUNT,
            state=ReimbursementRequestState.REIMBURSED,
        )

        ReimbursementRequestFactory.create(
            wallet=two_category_wallet,
            category=category,
            amount=REIMBURSED_AMOUNT,
            state=ReimbursementRequestState.APPROVED,
        )

    return two_category_wallet


@pytest.fixture(scope="function")
def direct_payment_wallet_without_dp_category_access(
    session, category_service, direct_payment_wallet
):
    allowed_categories = (
        direct_payment_wallet.reimbursement_organization_settings.allowed_reimbursement_categories
    )
    settings = category_service.rules_repo.get_all_category_settings_from_wallet(
        wallet_id=direct_payment_wallet.id
    )
    settings[0].access_level = CategoryRuleAccessLevel.NO_ACCESS
    direct_payment_wallet._cached_get_direct_payment_category = None
    direct_payment_wallet._cached_get_allowed_categories = None
    session.commit()

    result = ReimbursementWalletCategoryRuleEvaluationResultFactory.create(
        reimbursement_organization_settings_allowed_category_id=allowed_categories[
            0
        ].id,
        reimbursement_wallet_id=direct_payment_wallet.id,
        evaluation_result=False,
        executed_category_rule=None,
        failed_category_rule=None,
    )
    ReimbursementWalletCategoryRuleEvaluationFailureFactory.create(
        evaluation_result_id=result.id,
        rule_name="AMAZON_PROGENY_TOC_PERIOD",
    )
    return direct_payment_wallet


@pytest.fixture()
def expense_subtypes():
    rsc_adoption = ReimbursementServiceCategoryFactory(
        category="ADOPTION", name="Adoption"
    )
    rsc_fertility = ReimbursementServiceCategoryFactory(
        category="FERTILITY", name="Fertility"
    )
    rsc_preservation = ReimbursementServiceCategoryFactory(
        category="PRESERVATION", name="Preservation"
    )
    rsc_surrogacy = ReimbursementServiceCategoryFactory(
        category="SURROGACY", name="Surrogacy"
    )
    return {
        "ALF": WalletExpenseSubtypeFactory(
            expense_type=ReimbursementRequestExpenseTypes.ADOPTION,
            reimbursement_service_category=rsc_adoption,
            code="ALF",
            description="Legal fees",
        ),
        "APF": WalletExpenseSubtypeFactory(
            expense_type=ReimbursementRequestExpenseTypes.ADOPTION,
            reimbursement_service_category=rsc_adoption,
            code="APF",
            description="Agency fees",
        ),
        "FT": WalletExpenseSubtypeFactory(
            expense_type=ReimbursementRequestExpenseTypes.FERTILITY,
            reimbursement_service_category=rsc_fertility,
            code="FT",
            description="Fertility testing",
        ),
        "FERTRX": WalletExpenseSubtypeFactory(
            expense_type=ReimbursementRequestExpenseTypes.FERTILITY,
            reimbursement_service_category=rsc_fertility,
            code="FERTRX",
            description="Fertility medication",
        ),
        "FIVF": WalletExpenseSubtypeFactory(
            expense_type=ReimbursementRequestExpenseTypes.FERTILITY,
            reimbursement_service_category=rsc_fertility,
            code="FIVF",
            description="IVF (with fresh transfer)",
        ),
        "FRTTRAVEL": WalletExpenseSubtypeFactory(
            expense_type=ReimbursementRequestExpenseTypes.FERTILITY,
            reimbursement_service_category=rsc_fertility,
            code="FRTTRAVEL",
            description="Fertility Travel",
            visible=False,
        ),
        "FERTRX2": WalletExpenseSubtypeFactory(
            expense_type=ReimbursementRequestExpenseTypes.PRESERVATION,
            reimbursement_service_category=rsc_preservation,
            code="FERTRX",
            description="Fertility and preservation medication",
        ),
        "PRSEGG": WalletExpenseSubtypeFactory(
            expense_type=ReimbursementRequestExpenseTypes.PRESERVATION,
            reimbursement_service_category=rsc_preservation,
            code="PRSEGG",
            description="Egg Freezing-IVF-IUI",
        ),
        "SGCC": WalletExpenseSubtypeFactory(
            expense_type=ReimbursementRequestExpenseTypes.SURROGACY,
            reimbursement_service_category=rsc_surrogacy,
            code="SGCC",
            description="Surrogacy-Gestational Carrier Costs",
        ),
    }


@pytest.fixture
def make_mocked_alegeus_direct_claim_response():
    def _make_mocked_response(
        status_code,
        error_code: Optional[int],
        txn_amt_orig: Optional[float],
        txn_approved_amt: Optional[float],
    ):
        mock_response = Response()
        mock_response.status_code = status_code
        payload = {
            "ReimbursementMode": "None",
            "PayProviderFlag": "No",
            "TrackingNumber": "DPNOPAYTEST8",
            "TxnResponseList": [
                {"AcctTypeCde": "HRA", "DisbBal": 0.00, "TxnAmt": 13.80}
            ],
        }
        if error_code is not None:
            payload["ErrorCode"] = error_code
        if txn_amt_orig is not None:
            payload["TxnAmtOrig"] = txn_amt_orig
        if txn_approved_amt is not None:
            payload["TxnApprovedAmt"] = txn_approved_amt
        mock_response.json = lambda: payload

        return mock_response

    return _make_mocked_response


@pytest.fixture
def mock_ledger_entry():
    return LedgerEntry(
        id="3fa85f64-5717-4562-b3fc-2c963f66afa6",
        configuration_id="3fa85f64-5717-4562-b3fc-2c963f66afa6",
        reimbursement_organization_settings_id="12324452543",
        employee_id="321",
        first_name="John",
        last_name="Doe",
        date_of_birth="1980-01-01",
        calculated_spend=90071,
        calculated_cycles=5,
        historical_spend=90072,
        historical_cycles_used=3,
        category="fertility",
        balance_id="3fa85f64-5717-4562-b3fc-2c963f66afa6",
        file_id="3fa85f64-5717-4562-b3fc-2c963f66afa6",
        most_recent_auth_date=datetime.date(2024, 12, 4),
        created_at=datetime.datetime(2024, 12, 4),
        service_date="2024-12-04",
        adjustment_id=None,
        dependent_first_name="",
        dependent_last_name="",
        dependent_date_of_birth=None,
        dependent_id=None,
        subscriber_id="sub_123",
    )


@pytest.fixture
def mock_ledger_entry_adoption():
    return LedgerEntry(
        id="3fa85f64-5717-4562-b3fc-2c963f66afa6",
        configuration_id="3fa85f64-5717-4562-b3fc-2c963f66afa6",
        reimbursement_organization_settings_id="12324452543",
        employee_id="321",
        first_name="John",
        last_name="Doe",
        date_of_birth="1980-01-01",
        calculated_spend=30000,
        calculated_cycles=2,
        historical_spend=90072,
        historical_cycles_used=3,
        category="adoption",
        balance_id="3fa85f64-5717-4562-b3fc-2c963f66afa6",
        file_id="3fa85f64-5717-4562-b3fc-2c963f66afa6",
        most_recent_auth_date=datetime.date(2024, 12, 4),
        created_at=datetime.datetime(2024, 12, 4),
        service_date="2024-12-04",
        adjustment_id=None,
        dependent_first_name="",
        dependent_last_name="",
        dependent_date_of_birth=None,
        dependent_id=None,
        subscriber_id="sub_123",
    )
