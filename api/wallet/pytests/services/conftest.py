from __future__ import annotations

from datetime import date, datetime, timedelta
from unittest import mock
from unittest.mock import MagicMock

import pytest

from common.wallet_historical_spend import WalletHistoricalSpendClient
from cost_breakdown.pytests.factories import CostBreakdownFactory
from eligibility import e9y
from pytests import factories
from wallet.constants import INTERNAL_TRUST_WHS_URL
from wallet.models.constants import (
    EligibilityLossRule,
    FertilityProgramTypes,
    ReimbursementRequestState,
    WalletState,
    WalletUserStatus,
)
from wallet.models.models import MemberBenefitProfile, OrganizationWalletSettings
from wallet.models.reimbursement_organization_settings import (
    ReimbursementOrganizationSettings,
)
from wallet.models.reimbursement_wallet import ReimbursementWallet
from wallet.pytests.factories import (
    MemberWalletSummaryFactory,
    ReimbursementRequestCategoryFactory,
    ReimbursementRequestFactory,
)
from wallet.services.currency import CurrencyService
from wallet.services.wallet_historical_spend import WalletHistoricalSpendService

BENEFIT_ID = "M909093203"


@pytest.fixture(scope="function")
def marketplace_member_benefit_profile(default_user):
    default_user.health_profile.date_of_birth = datetime(year=1993, month=5, day=1)
    factories.MemberProfileFactory.create(user_id=default_user.id)
    return MemberBenefitProfile(
        benefit_id="M909093203",
        first_name=default_user.first_name,
        last_name=default_user.last_name,
        date_of_birth=default_user.health_profile.date_of_birth,
        user_id=default_user.id,
        phone=default_user.member_profile.phone_number,
        email=default_user.email,
    )


@pytest.fixture(scope="function")
def enterprise_member_benefit_profile(enterprise_user):
    enterprise_user.health_profile.date_of_birth = datetime(year=1993, month=5, day=1)
    return MemberBenefitProfile(
        benefit_id=BENEFIT_ID,
        first_name=enterprise_user.first_name,
        last_name=enterprise_user.last_name,
        date_of_birth=enterprise_user.health_profile.date_of_birth,
        user_id=enterprise_user.id,
        phone=enterprise_user.member_profile.phone_number,
        email=enterprise_user.email,
    )


@pytest.fixture(scope="function")
def org_wallet_settings_enterprise(enterprise_user):
    return OrganizationWalletSettings(
        organization_id=enterprise_user.organization.id,
        organization_name=enterprise_user.organization.name,
        org_settings_id=None,
    )


@pytest.fixture(scope="function")
def org_wallet_settings_reimbursement(enterprise_user):
    return OrganizationWalletSettings(
        fertility_program_type=FertilityProgramTypes.CARVE_OUT,
        organization_id=enterprise_user.organization.id,
        organization_name=enterprise_user.organization.name,
        direct_payment_enabled=False,
        org_settings_id=1,
    )


@pytest.fixture(scope="function")
def org_wallet_settings_direct_payment(enterprise_user):
    return OrganizationWalletSettings(
        fertility_program_type=FertilityProgramTypes.CARVE_OUT,
        organization_id=enterprise_user.organization.id,
        organization_name=enterprise_user.organization.name,
        direct_payment_enabled=True,
        org_settings_id=1,
    )


@pytest.fixture(scope="function")
def disqualified_member_wallet_summary_reimbursement():
    return MemberWalletSummaryFactory.create(
        wallet_state=WalletState.DISQUALIFIED,
        wallet_user_status=WalletUserStatus.DENIED,
        direct_payment_enabled=False,
    )


@pytest.fixture(scope="function")
def active_member_wallet_summary_reimbursement():
    return MemberWalletSummaryFactory.create(
        wallet_state=WalletState.QUALIFIED,
        wallet_user_status=WalletUserStatus.ACTIVE,
        direct_payment_enabled=False,
        is_shareable=False,
    )


@pytest.fixture(scope="function")
def active_member_wallet_summary_direct_payment():
    return MemberWalletSummaryFactory.create(
        wallet_state=WalletState.QUALIFIED,
        wallet_user_status=WalletUserStatus.ACTIVE,
        direct_payment_enabled=True,
        is_shareable=True,
    )


@pytest.fixture(scope="function")
def active_clinic_portal_member_wallet_summary_reimbursement():
    return MemberWalletSummaryFactory.create(
        wallet_state=WalletState.QUALIFIED,
        wallet_user_status=WalletUserStatus.ACTIVE,
        direct_payment_enabled=False,
    )


@pytest.fixture(scope="function")
def active_clinic_portal_member_wallet_summary_direct_payment_without_dp_category_access(
    direct_payment_wallet_without_dp_category_access,
):
    return MemberWalletSummaryFactory.create(
        wallet=direct_payment_wallet_without_dp_category_access,
        wallet_state=WalletState.QUALIFIED,
        wallet_user_status=WalletUserStatus.ACTIVE,
        direct_payment_enabled=True,
    )


@pytest.fixture(scope="function")
def active_clinic_portal_member_wallet_summary_direct_payment(direct_payment_wallet):
    return MemberWalletSummaryFactory.create(
        wallet=direct_payment_wallet,
        wallet_state=WalletState.QUALIFIED,
        wallet_user_status=WalletUserStatus.ACTIVE,
        direct_payment_enabled=True,
    )


@pytest.fixture
def reimbursement_requests(qualified_alegeus_wallet_hdhp_single):
    category = ReimbursementRequestCategoryFactory.create(label="fertility")
    rr_1 = ReimbursementRequestFactory.create(
        wallet=qualified_alegeus_wallet_hdhp_single,
        category=category,
        amount=100000,
        state=ReimbursementRequestState.NEW,
    )
    rr_2 = ReimbursementRequestFactory.create(
        wallet=qualified_alegeus_wallet_hdhp_single,
        category=category,
        amount=50000,
        state=ReimbursementRequestState.NEW,
    )
    rr_3 = ReimbursementRequestFactory.create(
        wallet=qualified_alegeus_wallet_hdhp_single,
        category=category,
        amount=7705,
        state=ReimbursementRequestState.NEW,
    )
    return [rr_1, rr_2, rr_3]


@pytest.fixture
def cost_breakdowns(qualified_alegeus_wallet_hdhp_single, reimbursement_requests):
    for rr in reimbursement_requests:
        CostBreakdownFactory.create(
            wallet_id=qualified_alegeus_wallet_hdhp_single.id,
            reimbursement_request_id=rr.id,
            total_member_responsibility=25000,
            created_at=date.today(),
        )
        CostBreakdownFactory.create(
            wallet_id=qualified_alegeus_wallet_hdhp_single.id,
            reimbursement_request_id=rr.id,
            total_member_responsibility=777700,
            created_at=date.today() - timedelta(days=2),
        )
        CostBreakdownFactory.create(
            wallet_id=qualified_alegeus_wallet_hdhp_single.id,
            reimbursement_request_id=rr.id,
            total_member_responsibility=888800,
            created_at=date.today() - timedelta(days=5),
        )


@pytest.fixture(scope="function")
def mock_wallet():
    wallet = MagicMock(spec=ReimbursementWallet)
    wallet.id = 1
    wallet.state = WalletState.QUALIFIED
    wallet.reimbursement_organization_settings_id = 1
    wallet.reimbursement_organization_settings = MagicMock(
        spec=ReimbursementOrganizationSettings
    )
    wallet.reimbursement_organization_settings.run_out_days = 90
    wallet.reimbursement_organization_settings.eligibility_loss_rule = (
        EligibilityLossRule.TERMINATION_DATE
    )
    wallet.employee_member = MagicMock()
    wallet.employee_member.id = 100
    return wallet


@pytest.fixture(scope="function")
def mock_eligibility_record():
    record = MagicMock()
    record.effective_range.upper = date.today() + timedelta(days=30)
    record.organization_id = 1
    record.user_id = 1
    record.record = {"some_key": "some_value"}
    return record


@pytest.fixture
def mock_currency_code_repository():
    with mock.patch(
        "wallet.repository.currency_code.CurrencyCodeRepository",
        spec_set=True,
        autospec=True,
    ) as m:
        yield m.return_value


@pytest.fixture
def mock_currency_fx_rate_repository():
    with mock.patch(
        "wallet.repository.currency_fx_rate.CurrencyFxRateRepository",
        spec_set=True,
        autospec=True,
    ) as m:
        yield m.return_value


@pytest.fixture
def currency_service(mock_currency_code_repository, mock_currency_fx_rate_repository):
    return CurrencyService(
        currency_code_repo=mock_currency_code_repository,
        currency_fx_rate_repo=mock_currency_fx_rate_repository,
    )


@pytest.fixture
def historical_spend_service():
    whs_client = WalletHistoricalSpendClient(base_url=INTERNAL_TRUST_WHS_URL)
    historical_spend_service = WalletHistoricalSpendService(whs_client=whs_client)
    return historical_spend_service


@pytest.fixture(scope="function")
def eligibility_verification():
    def _eligibility_verification(first_name="John", last_name="Doe", dob=None):
        dob = dob if dob else date.today()
        return e9y.EligibilityVerification(
            user_id=1,
            organization_id=1,
            unique_corp_id="Abc212",
            dependent_id="ABC224",
            first_name=first_name,
            last_name=last_name,
            date_of_birth=dob,
            email="test@mavenclinic.com",
            verified_at=datetime.utcnow(),
            created_at=datetime.utcnow(),
            verification_type="lookup",
            is_active=True,
            record={
                "employee_start_date": str(date.today()),
                "subscriber_id": "sub_123",
            },
            effective_range=None,
        )

    return _eligibility_verification
