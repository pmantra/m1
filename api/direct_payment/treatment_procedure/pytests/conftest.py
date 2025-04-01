import datetime

import pytest

from direct_payment.clinic.pytests.factories import (
    FeeScheduleGlobalProceduresFactory,
    FertilityClinicFactory,
    FertilityClinicLocationFactory,
    FertilityClinicUserProfileFactory,
    FertilityClinicUserProfileFertilityClinicFactory,
)
from direct_payment.treatment_procedure.pytests.factories import (
    QuestionnaireGlobalProcedureFactory,
    TreatmentProcedureFactory,
)
from direct_payment.treatment_procedure.repository.treatment_procedure import (
    TreatmentProcedureRepository,
)
from direct_payment.treatment_procedure.repository.treatment_procedure_questionnaire import (
    TreatmentProcedureQuestionnaireRepository,
)
from eligibility.pytests import factories as eligibility_factories
from models.questionnaires import (
    SINGLE_EMBRYO_TRANSFER_QUESTIONNAIRE_OID,
    QuestionTypes,
)
from pytests.common.global_procedures import factories
from pytests.common.global_procedures.factories import GlobalProcedureFactory
from pytests.factories import DefaultUserFactory, QuestionnaireFactory
from wallet.models.constants import (
    ReimbursementRequestExpenseTypes,
    WalletState,
    WalletUserStatus,
    WalletUserType,
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


@pytest.fixture
def global_procedure():
    return GlobalProcedureFactory.create(name="IVF", credits=5)


@pytest.fixture
def diagnostic_global_procedure():
    return GlobalProcedureFactory.create(name="IVF", credits=5, is_diagnostic=True)


@pytest.fixture
def partial_global_procedure():
    return GlobalProcedureFactory.create(
        name="PARTIAL DIAGNOSTIC", credits=1, is_partial=True
    )


@pytest.fixture
def treatment_procedure_repository(session):
    return TreatmentProcedureRepository(session=session)


@pytest.fixture
def wallet(session, enterprise_user):
    wallet = ReimbursementWalletFactory.create(
        member=enterprise_user, state=WalletState.QUALIFIED
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
    year = datetime.datetime.now().year
    ReimbursementPlanFactory.create(
        category=request_category,
        start_date=datetime.datetime(year, 1, 1).date(),
        end_date=datetime.datetime(year, 12, 31).date(),
    )
    return wallet


@pytest.fixture
def wallet_cycle_based(session, enterprise_user):
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
def treatment_procedure(session, global_procedure, wallet):
    member_id = wallet.member.id
    global_procedure = factories.GlobalProcedureFactory.create()
    fee_schedule_global_procedures = FeeScheduleGlobalProceduresFactory.create(
        cost=34, global_procedure_id=global_procedure["id"]
    )
    fee_schedule = fee_schedule_global_procedures.fee_schedule
    procedure_name = global_procedure["name"]
    category = (
        wallet.reimbursement_organization_settings.allowed_reimbursement_categories[
            0
        ].reimbursement_request_category
    )

    return TreatmentProcedureFactory.create(
        member_id=member_id,
        reimbursement_wallet_id=wallet.id,
        reimbursement_request_category=category,
        fee_schedule=fee_schedule,
        global_procedure_id=global_procedure["id"],
        procedure_name=procedure_name,
        cost=fee_schedule_global_procedures.cost,
    )


@pytest.fixture
def treatment_procedure_cycle_based(
    session, global_procedure, wallet_cycle_based, enterprise_user
):
    fee_schedule_global_procedures = FeeScheduleGlobalProceduresFactory(
        cost=50_000, global_procedure_id=global_procedure["id"]
    )
    fee_schedule = fee_schedule_global_procedures.fee_schedule
    procedure_name = global_procedure["name"]

    return TreatmentProcedureFactory(
        member_id=enterprise_user.id,
        reimbursement_wallet_id=wallet_cycle_based.id,
        fee_schedule=fee_schedule,
        global_procedure_id=global_procedure["id"],
        procedure_name=procedure_name,
        cost=fee_schedule_global_procedures.cost,
        cost_credit=global_procedure["credits"],
        reimbursement_request_category=wallet_cycle_based.get_direct_payment_category,
    )


@pytest.fixture
def e9y_member_currency(treatment_procedure):
    eligibility_factories.WalletEnablementFactory.create(
        member_id=treatment_procedure.member_id,
    )


@pytest.fixture
def e9y_member_cycle(treatment_procedure_cycle_based):
    eligibility_factories.WalletEnablementFactory.create(
        member_id=treatment_procedure_cycle_based.member_id,
    )


@pytest.fixture
def e9y_member_wallet(enterprise_user):
    eligibility_factories.WalletEnablementFactory.create(
        member_id=enterprise_user.id,
    )


@pytest.fixture
def fertility_clinic(session):
    clinic = FertilityClinicFactory.create()
    return clinic


@pytest.fixture
def fertility_clinic_location(session, fertility_clinic):
    return FertilityClinicLocationFactory(fertility_clinic=fertility_clinic)


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
def treatment_procedure_questionnaire_repository(session):
    return TreatmentProcedureQuestionnaireRepository(session)


@pytest.fixture
def questionnaire_global_procedures():
    questionnaire_global_procedures = [
        QuestionnaireGlobalProcedureFactory.create(),
        QuestionnaireGlobalProcedureFactory.create(),
        QuestionnaireGlobalProcedureFactory.create(),
        QuestionnaireGlobalProcedureFactory.create(),
    ]
    firstEntry = questionnaire_global_procedures[0]
    questionnaire_global_procedures[2].questionnaire_id = firstEntry.questionnaire_id
    questionnaire_global_procedures[
        3
    ].global_procedure_id = firstEntry.global_procedure_id

    return questionnaire_global_procedures


@pytest.fixture
def treatment_procedure_recorded_answer_set_questionnaire():
    questionnaire = QuestionnaireFactory.create(
        oid=SINGLE_EMBRYO_TRANSFER_QUESTIONNAIRE_OID
    )
    questions = questionnaire.question_sets[0].questions

    radio_question = next(q for q in questions if q.type == QuestionTypes.RADIO)
    questions = [
        {
            "question_id": radio_question.id,
            "answer_id": radio_question.answers[0].id,
        },
    ]

    return {"questionnaire_id": questionnaire.id, "questions": questions}
