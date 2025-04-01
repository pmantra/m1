import datetime

import pytest

from authz.models.roles import ROLES, Role
from authz.services.permission import add_role_to_user
from direct_payment.clinic.models.user import AccountStatus
from direct_payment.clinic.pytests.factories import (
    FeeScheduleGlobalProceduresFactory,
    FertilityClinicFactory,
    FertilityClinicLocationFactory,
    FertilityClinicUserProfileFactory,
    FertilityClinicUserProfileFertilityClinicFactory,
)
from direct_payment.clinic.repository import clinic, clinic_location, user
from direct_payment.treatment_procedure.models.treatment_procedure import (
    TreatmentProcedureStatus,
)
from direct_payment.treatment_procedure.pytests.factories import (
    TreatmentProcedureFactory,
)
from pytests.common.global_procedures import factories
from pytests.common.global_procedures.factories import GlobalProcedureFactory
from pytests.factories import DefaultUserFactory
from storage.connection import db
from wallet.models.constants import (
    ReimbursementRequestExpenseTypes,
    WalletUserStatus,
    WalletUserType,
)
from wallet.pytests.conftest import (  # noqa: F401
    active_wallet_user,
    category_service,
    direct_payment_wallet_without_dp_category_access,
    pending_alegeus_wallet_hra,
    qualified_alegeus_wallet_hra,
    qualified_wallet,
    valid_alegeus_plan_hra,
)
from wallet.pytests.factories import (
    ReimbursementAccountTypeFactory,
    ReimbursementCycleCreditsFactory,
    ReimbursementCycleMemberCreditTransactionFactory,
    ReimbursementOrganizationSettingsFactory,
    ReimbursementPlanFactory,
    ReimbursementRequestCategoryExpenseTypesFactory,
    ReimbursementWalletFactory,
    ReimbursementWalletUsersFactory,
)

# Import of fixtures from other fixture scopes to avoid duplication
from wallet.pytests.fixtures import (  # noqa: F401
    direct_payment_wallet,
    unlimited_direct_payment_wallet,
    user_for_direct_payment_wallet,
    user_for_unlimited_direct_payment_wallet,
    wallet_test_helper,
)

NUMBER_OF_SCHEDULED_TREATMENT_PROCEDURES = 3
NUMBER_OF_COMPLETED_TREATMENT_PROCEDURES = 2


@pytest.fixture
def fertility_clinic_repository(session):
    return clinic.FertilityClinicRepository(session=session)


@pytest.fixture
def fertility_clinic_location_repository(session):
    return clinic_location.FertilityClinicLocationRepository(session=session)


@pytest.fixture
def fertility_clinic_user_repository(session):
    return user.FertilityClinicUserRepository(session=session)


@pytest.fixture
def fee_schedule_global_procedure(session):
    global_procedure = factories.GlobalProcedureFactory.create()
    fee_schedule_global_procedure = FeeScheduleGlobalProceduresFactory(
        cost=2995, global_procedure_id=global_procedure["id"]
    )
    return fee_schedule_global_procedure


@pytest.fixture
def active_fc_user(session):
    return FertilityClinicUserProfileFactory(status=AccountStatus.ACTIVE)


@pytest.fixture
def inactive_fc_user(session):
    return FertilityClinicUserProfileFactory(status=AccountStatus.INACTIVE)


@pytest.fixture
def suspended_fc_user(session):
    return FertilityClinicUserProfileFactory(status=AccountStatus.SUSPENDED)


@pytest.fixture
def fc_user(session, fertility_clinic):
    user = DefaultUserFactory.create()
    fc_profile = FertilityClinicUserProfileFactory.create(user_id=user.id)
    FertilityClinicUserProfileFertilityClinicFactory.create(
        fertility_clinic_id=fertility_clinic.id,
        fertility_clinic_user_profile_id=fc_profile.id,
    )
    return user


@pytest.fixture
def fc_billing_user(session, fc_user):
    role = Role.query.filter(
        Role.name == ROLES.fertility_clinic_billing_user
    ).one_or_none()
    if not role:
        db.session.add(Role(name=ROLES.fertility_clinic_billing_user))
        db.session.commit()
    add_role_to_user(fc_user, ROLES.fertility_clinic_billing_user)
    return fc_user


@pytest.fixture
def fertility_clinic(session):
    clinic = FertilityClinicFactory()
    return clinic


@pytest.fixture
def fertility_clinic_location(session, fertility_clinic):
    return FertilityClinicLocationFactory(fertility_clinic=fertility_clinic)


@pytest.fixture
def fertility_clinic_with_users(session, fertility_clinic):
    clinic = fertility_clinic
    for _ in range(3):
        user = DefaultUserFactory(email_prefix="clinic_user")
        fc_profile = FertilityClinicUserProfileFactory(user_id=user.id)
        FertilityClinicUserProfileFertilityClinicFactory.create(
            fertility_clinic_id=clinic.id,
            fertility_clinic_user_profile_id=fc_profile.id,
        )
    return clinic


@pytest.fixture
def global_procedure():
    return GlobalProcedureFactory.create(name="IVF", credits=5)


@pytest.fixture
def wallet_cycle_based(session, enterprise_user):
    org_settings = ReimbursementOrganizationSettingsFactory(
        organization_id=enterprise_user.organization.id,
        allowed_reimbursement_categories__cycle_based=True,
        direct_payment_enabled=True,
    )
    wallet = ReimbursementWalletFactory.create(
        reimbursement_organization_settings=org_settings, member=enterprise_user
    )
    wallet_user = ReimbursementWalletUsersFactory.create(
        user_id=enterprise_user.id,
        reimbursement_wallet_id=wallet.id,
        status=WalletUserStatus.ACTIVE,
        type=WalletUserType.EMPLOYEE,
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
        amount=60,
    )
    ReimbursementCycleMemberCreditTransactionFactory.create(
        reimbursement_cycle_credits_id=credits.id,
        amount=60,
        notes="Initial Fund",
    )
    return wallet


@pytest.fixture
def treatment_procedures_cycle_based(
    session,
    global_procedure,
    wallet_cycle_based,
    enterprise_user,
    fertility_clinic,
    fee_schedule_global_procedure,
):
    fee_schedule = fee_schedule_global_procedure.fee_schedule
    procedure_name = global_procedure["name"]
    enterprise_user.health_profile.birthday = datetime.date(1999, 1, 1)

    treatment_procedures = []
    for _ in range(NUMBER_OF_SCHEDULED_TREATMENT_PROCEDURES):
        tp = TreatmentProcedureFactory(
            member_id=enterprise_user.id,
            reimbursement_wallet_id=wallet_cycle_based.id,
            fee_schedule=fee_schedule,
            global_procedure_id=global_procedure["id"],
            procedure_name=procedure_name,
            cost=fee_schedule_global_procedure.cost,
            cost_credit=global_procedure["credits"],
            reimbursement_request_category=wallet_cycle_based.get_direct_payment_category,
            fertility_clinic=fertility_clinic,
            end_date=datetime.date(2024, 1, 10),
            start_date=datetime.date(2024, 1, 1),
        )
        treatment_procedures.append(tp)
    return treatment_procedures


@pytest.fixture
def treatment_procedures_with_completed_procedures(
    session,
    global_procedure,
    wallet_cycle_based,
    enterprise_user,
    fertility_clinic,
    fee_schedule_global_procedure,
    treatment_procedures_cycle_based,
):
    fee_schedule = fee_schedule_global_procedure.fee_schedule
    procedure_name = global_procedure["name"]

    completed_treatment_procedures = []
    for _ in range(NUMBER_OF_COMPLETED_TREATMENT_PROCEDURES):
        tp = TreatmentProcedureFactory(
            member_id=enterprise_user.id,
            reimbursement_wallet_id=wallet_cycle_based.id,
            fee_schedule=fee_schedule,
            global_procedure_id=global_procedure["id"],
            procedure_name=procedure_name,
            cost=fee_schedule_global_procedure.cost,
            cost_credit=global_procedure["credits"],
            reimbursement_request_category=wallet_cycle_based.get_direct_payment_category,
            fertility_clinic=fertility_clinic,
            status=TreatmentProcedureStatus.COMPLETED,
        )
        completed_treatment_procedures.append(tp)
    return [*completed_treatment_procedures, *treatment_procedures_cycle_based]


@pytest.fixture
def number_of_completed_treatment_procedures():
    return NUMBER_OF_COMPLETED_TREATMENT_PROCEDURES
