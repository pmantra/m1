from __future__ import annotations

import datetime
from unittest import mock

import pytest

from authn.models.user import User
from direct_payment.treatment_procedure.models.treatment_procedure import (
    TreatmentProcedureType,
)
from direct_payment.treatment_procedure.pytests.factories import (
    TreatmentProcedureFactory,
)
from payer_accumulator.models.payer_list import PayerName
from payer_accumulator.pytests.factories import PayerFactory
from wallet.models.constants import ReimbursementRequestExpenseTypes, WalletState
from wallet.pytests import factories
from wallet.pytests.conftest import SUPPORTED_CURRENCY_CODE_MINOR_UNIT
from wallet.pytests.factories import (
    EmployerHealthPlanFactory,
    MemberHealthPlanFactory,
    ReimbursementAccountTypeFactory,
    ReimbursementCycleCreditsFactory,
    ReimbursementCycleMemberCreditTransactionFactory,
    ReimbursementOrganizationSettingsFactory,
    ReimbursementPlanFactory,
    ReimbursementRequestCategoryExpenseTypesFactory,
    ReimbursementRequestCategoryFactory,
    ReimbursementWalletFactory,
    ReimbursementWalletUsersFactory,
)
from wallet.services.currency import CurrencyService


@pytest.fixture(autouse=True)
def admin_auth(admin_app):
    admin_app.app.config["LOGIN_DISABLED"] = True
    # Skip all rbac + auth
    with mock.patch(
        "admin.views.auth.AdminAuth.is_accessible", return_value=True
    ) as mock_login, mock.patch(
        "flask_login.current_user",
        autospec=User,
        is_authenticated=True,
        id=-1,
        email="not.a@email.com",
    ):
        yield mock_login


@pytest.fixture(scope="function", autouse=True)
def supported_currency_codes():
    for currency_code, minor_unit in SUPPORTED_CURRENCY_CODE_MINOR_UNIT:
        factories.CountryCurrencyCodeFactory.create(
            country_alpha_2=currency_code,
            currency_code=currency_code,
            minor_unit=minor_unit,
        )


@pytest.fixture()
def mock_currency_code_repository():
    with mock.patch(
        "wallet.repository.currency_code.CurrencyCodeRepository",
        spec_set=True,
        autospec=True,
    ) as m:
        yield m.return_value


@pytest.fixture()
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


@pytest.fixture(scope="function")
def wallet(enterprise_user):
    wallet = ReimbursementWalletFactory.create(
        state=WalletState.QUALIFIED, member=enterprise_user
    )
    ReimbursementWalletUsersFactory.create(
        user_id=enterprise_user.id,
        reimbursement_wallet_id=wallet.id,
    )
    wallet.reimbursement_organization_settings.direct_payment_enabled = True
    wallet.member.member_profile.country_code = "US"
    category_association = (
        wallet.reimbursement_organization_settings.allowed_reimbursement_categories[0]
    )
    category_association.is_direct_payment_eligible = True
    request_category = category_association.reimbursement_request_category
    ReimbursementRequestCategoryExpenseTypesFactory.create(
        reimbursement_request_category=request_category,
        expense_type=ReimbursementRequestExpenseTypes.FERTILITY,
    )
    year = datetime.datetime.now().year  # noqa
    ReimbursementPlanFactory.create(
        category=request_category,
        start_date=datetime.datetime(year, 1, 1).date(),
        end_date=datetime.datetime(year, 12, 31).date(),
    )
    return wallet


@pytest.fixture
def health_plans_for_wallet(wallet):
    emp = EmployerHealthPlanFactory.create(
        name="Test Plan",
        reimbursement_organization_settings=wallet.reimbursement_organization_settings,
    )
    mhp = MemberHealthPlanFactory.create(
        employer_health_plan=emp,
        reimbursement_wallet=wallet,
        plan_start_at=datetime.datetime(year=2020, month=1, day=1),
    )
    PayerFactory.create(id=1, payer_name=PayerName.UHC, payer_code="uhc_code")
    return mhp


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
def rx_procedure(enterprise_user):
    category = ReimbursementRequestCategoryFactory.create(label="fertility")
    return TreatmentProcedureFactory.create(
        member_id=enterprise_user.id,
        reimbursement_request_category=category,
        procedure_type=TreatmentProcedureType.PHARMACY,
    )
