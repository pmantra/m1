import tempfile
from datetime import date, datetime
from unittest import mock
from unittest.mock import Mock, PropertyMock, patch

import pytest
from google.cloud.storage import Bucket
from requests import Response

from common.global_procedures.procedure import ProcedureService
from cost_breakdown.constants import Tier
from cost_breakdown.pytests.factories import CostBreakdownFactory, RTETransactionFactory
from direct_payment.billing.billing_service import BillingService
from direct_payment.pharmacy.automated_reimbursement_request_service import (
    AutomatedReimbursementRequestService,
)
from direct_payment.pharmacy.constants import ENABLE_SMP_GCS_BUCKET_PROCESSING
from direct_payment.pharmacy.health_plan_ytd_service import (
    HealthPlanYearToDateSpendService,
)
from direct_payment.pharmacy.models.pharmacy_prescription import PrescriptionStatus
from direct_payment.pharmacy.pharmacy_prescription_service import (
    PharmacyPrescriptionService,
)
from direct_payment.pharmacy.pytests import factories
from direct_payment.pharmacy.pytests.factories import HealthPlanYearToDateSpendFactory
from direct_payment.pharmacy.repository.health_plan_ytd_spend import (
    HealthPlanYearToDateSpendRepository,
)
from direct_payment.pharmacy.repository.pharmacy_prescription import (
    PharmacyPrescriptionRepository,
)
from direct_payment.pharmacy.tasks.libs.pharmacy_file_handler import PharmacyFileHandler
from direct_payment.pharmacy.tasks.smp_cost_breakdown_audit import RxAudit
from direct_payment.treatment_procedure.models.treatment_procedure import (
    TreatmentProcedureStatus,
    TreatmentProcedureType,
)
from direct_payment.treatment_procedure.pytests.factories import (
    TreatmentProcedureFactory,
)
from eligibility import e9y
from eligibility.pytests.factories import DateRangeFactory
from pytests.factories import HealthProfileFactory, MemberProfileFactory
from storage.repository.base import BaseRepository
from wallet.models.constants import (
    CostSharingCategory,
    CostSharingType,
    CoverageType,
    FamilyPlanType,
    ReimbursementMethod,
    ReimbursementRequestAutoProcessing,
    ReimbursementRequestExpenseTypes,
    ReimbursementRequestType,
    WalletState,
    WalletUserStatus,
    WalletUserType,
)
from wallet.models.reimbursement_organization_settings import (
    EmployerHealthPlanCostSharing,
)
from wallet.pytests.conftest import SUPPORTED_CURRENCY_CODE_MINOR_UNIT
from wallet.pytests.factories import (
    CountryCurrencyCodeFactory,
    EmployerHealthPlanCoverageFactory,
    EmployerHealthPlanFactory,
    MemberHealthPlanFactory,
    ReimbursementAccountFactory,
    ReimbursementAccountTypeFactory,
    ReimbursementCycleCreditsFactory,
    ReimbursementCycleMemberCreditTransactionFactory,
    ReimbursementOrganizationSettingsFactory,
    ReimbursementPlanFactory,
    ReimbursementRequestCategoryExpenseTypesFactory,
    ReimbursementRequestCategoryFactory,
    ReimbursementRequestFactory,
    ReimbursementServiceCategoryFactory,
    ReimbursementWalletBenefitFactory,
    ReimbursementWalletFactory,
    ReimbursementWalletUsersFactory,
    WalletExpenseSubtypeFactory,
)


@pytest.fixture()
def expense_subtypes():
    rsc_adoption = ReimbursementServiceCategoryFactory(
        category="ADOPTION", name="Adoption"
    )
    rsc_fertility = ReimbursementServiceCategoryFactory(
        category="FERTILITY", name="Fertility"
    )
    rsc_preservation = ReimbursementServiceCategoryFactory(
        category="FERTRX", name="Fertility/Preservation"
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
        "FERTRX2": WalletExpenseSubtypeFactory(
            expense_type=ReimbursementRequestExpenseTypes.PRESERVATION,
            reimbursement_service_category=rsc_preservation,
            code="FERTRX",
            description="Fertility and preservation medication",
        ),
    }


@pytest.fixture(scope="function", autouse=True)
def supported_currency_codes():
    for currency_code, minor_unit in SUPPORTED_CURRENCY_CODE_MINOR_UNIT:
        CountryCurrencyCodeFactory.create(
            country_alpha_2=currency_code,
            currency_code=currency_code,
            minor_unit=minor_unit,
        )


@pytest.fixture
def pharmacy_prescription_repository(testdb):
    with patch.object(
        BaseRepository, "session", new_callable=PropertyMock
    ) as mock_session:
        mock_session.return_value = testdb.session
        yield PharmacyPrescriptionRepository(session=testdb.session)


@pytest.fixture
def pharmacy_prescription_service(testdb):
    with patch.object(
        BaseRepository, "session", new_callable=PropertyMock
    ) as mock_session:
        mock_session.return_value = testdb.session
        yield PharmacyPrescriptionService(session=testdb.session, is_in_uow=False)


@pytest.fixture
def procedure_service():
    return ProcedureService()


@pytest.fixture
def rx_audit():
    return RxAudit()


@pytest.fixture(scope="function")
def wallet(enterprise_user):
    enterprise_user.first_name = "Jane"
    enterprise_user.last_name = "Doe"
    enterprise_user.member_profile.country_code = "US"
    wallet = ReimbursementWalletFactory.create(
        member=enterprise_user, state=WalletState.QUALIFIED
    )
    wallet.reimbursement_organization_settings.direct_payment_enabled = True
    wallet.reimbursement_organization_settings.rx_direct_payment_enabled = True
    wallet.primary_expense_type = ReimbursementRequestExpenseTypes.FERTILITY
    category_association = (
        wallet.reimbursement_organization_settings.allowed_reimbursement_categories[0]
    )
    category_association.is_direct_payment_eligible = True
    request_category = category_association.reimbursement_request_category
    ReimbursementRequestCategoryExpenseTypesFactory.create(
        reimbursement_request_category=request_category,
        expense_type=ReimbursementRequestExpenseTypes.FERTILITY,
    )

    year = datetime.utcnow().year
    plan = ReimbursementPlanFactory.create(
        reimbursement_account_type=ReimbursementAccountTypeFactory.create(
            alegeus_account_type="HRA"
        ),
        alegeus_plan_id="FERTILITY",
        start_date=date(year=year, month=1, day=1),
        end_date=date(year=year, month=12, day=31),
        is_hdhp=False,
    )
    request_category.reimbursement_plan = plan

    account = ReimbursementAccountFactory.create(
        alegeus_account_type=ReimbursementAccountTypeFactory.create(
            alegeus_account_type="HRA"
        ),
        alegeus_flex_account_key="ALEGEUS_FLEX_ACCOUNT_KEY",
    )
    account.wallet = wallet
    account.plan = plan
    HealthProfileFactory.create(
        user=enterprise_user, birthday=datetime.strptime("2000-01-01", "%Y-%m-%d")
    )
    MemberProfileFactory.create(user=enterprise_user, country_code="US")
    ReimbursementWalletBenefitFactory.create(
        reimbursement_wallet=wallet, maven_benefit_id="12345"
    )
    wallet.reimbursement_method = ReimbursementMethod.PAYROLL
    wallet.reimbursement_organization_settings.organization.alegeus_employer_id = (
        "ABC234"
    )
    wallet.alegeus_id = "DEF567"
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
        state=WalletState.QUALIFIED,
        member=enterprise_user,
    )
    wallet.primary_expense_type = ReimbursementRequestExpenseTypes.FERTILITY
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
    year = datetime.utcnow().year
    request_category.reimbursement_plan = ReimbursementPlanFactory.create(
        reimbursement_account_type=ReimbursementAccountTypeFactory.create(
            alegeus_account_type="HRA1"
        ),
        alegeus_plan_id="FERTILITYHRA",
        start_date=date(year=year, month=1, day=1),
        end_date=date(year=year, month=12, day=31),
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
    ReimbursementWalletBenefitFactory.create(
        reimbursement_wallet=wallet, maven_benefit_id="12345"
    )

    return wallet


@pytest.fixture(scope="function")
def treatment_procedure():
    category = ReimbursementRequestCategoryFactory.create(label="fertility")
    return TreatmentProcedureFactory.create(reimbursement_request_category=category)


@pytest.fixture
def raw_prescription_data():
    return {
        "Rx Received Date": "8/1/2023",
        "NCPDP Number": "5710365",
        "First Name": "Brittany",
        "Last Name": "Fun",
        "Maven Benefit ID": "554691",
        "User Benefit ID": "M56789",
        "NDC#": "44087-1150-01",
        "Drug Name": "OVIDREL 250 MCG/0.5ML SUBCUTANEOUS INJECTABLE",
        "Drug Description": "OVIDREL 250 MCG/0.5ML SUBCUTANEOUS INJECTABLE",
        "Rx Quantity": "1",
        "Rx #": "12",
        "Order Number": "107",
        "Cash List Price": "0",
        "EMD Maven Coupons": "5.35",
        "SMP Maven Discounts": "53.5",
        "Other Savings": "1.1",
        "Amount Owed to SMP": "48.15",
        "SMP Patient ID": "7065817",
        "Prescribing Clinic": "Advanced Fertility Center Of Chicago",
        "Fill Number": "7065817-12",
        "Scheduled Ship Date": "8/1/2023",
        "Actual Ship Date": "8/2/2023",
        "Rx Canceled Date": "8/2/2023",
        "Filled Date": "8/2/2024",
        "Unique Identifier": "11225658-7065817-0",
        "Rx Adjusted": "N",
    }


@pytest.fixture
def new_prescription(
    pharmacy_prescription_repository,
    treatment_procedure,
    enterprise_user,
    raw_prescription_data,
    rx_reimbursement_request,
):
    def _new_prescription(
        status=PrescriptionStatus.SCHEDULED,
        treatment_procedure_id=treatment_procedure.id,
        reimbursement_request_id=rx_reimbursement_request.id,
        cost=1000,
        treatment_status=TreatmentProcedureStatus.SCHEDULED,
        unique_id=raw_prescription_data["Unique Identifier"],
    ):
        treatment_procedure.cost = cost
        treatment_procedure.status = treatment_status
        treatment_procedure.start_date = datetime(year=2025, month=1, day=5).date()
        prescription = factories.PharmacyPrescriptionFactory(
            treatment_procedure_id=treatment_procedure_id,
            reimbursement_request_id=reimbursement_request_id,
            user_id=enterprise_user.id,
            ndc_number="44087-1150-01",
            scheduled_json=raw_prescription_data,
            amount_owed=cost,
            status=status,
            rx_unique_id=unique_id,
        )
        return pharmacy_prescription_repository.create(instance=prescription)

    return _new_prescription


@pytest.fixture
def multiple_prescriptions(pharmacy_prescription_repository, enterprise_user, wallet):
    category = ReimbursementRequestCategoryFactory.create(label="fertility")
    cb_1 = CostBreakdownFactory.create(wallet_id=wallet.id)
    cb_2 = CostBreakdownFactory.create(wallet_id=wallet.id, id=cb_1.id + 1)
    cb_3 = CostBreakdownFactory.create(wallet_id=wallet.id, id=cb_1.id + 2)

    tp_1 = TreatmentProcedureFactory.create(
        reimbursement_request_category=category,
        cost_breakdown_id=cb_1.id,
        reimbursement_wallet_id=wallet.id,
        global_procedure_id="8af5df5d-ff8c-4158-8427-b2ad6679c58e",
        member_id=wallet.user_id,
        procedure_type=TreatmentProcedureType.PHARMACY,
        start_date=datetime(year=2025, month=1, day=5).date(),
    )
    tp_2 = TreatmentProcedureFactory.create(
        reimbursement_request_category=category,
        cost_breakdown_id=cb_2.id,
        reimbursement_wallet_id=wallet.id,
        global_procedure_id="8af5df5d-ff8c-4158-8427-b2ad6679c58e",
        member_id=wallet.user_id,
        procedure_type=TreatmentProcedureType.PHARMACY,
        start_date=datetime(year=2025, month=1, day=5).date(),
    )
    tp_3 = TreatmentProcedureFactory.create(
        reimbursement_request_category=category,
        cost_breakdown_id=cb_3.id,
        reimbursement_wallet_id=wallet.id,
        global_procedure_id="8af5df5d-ff8c-4158-8427-b2ad6679c58q",
        member_id=wallet.user_id,
        procedure_type=TreatmentProcedureType.PHARMACY,
        start_date=datetime(year=2025, month=1, day=5).date(),
    )

    user_id = enterprise_user.id

    created_prescriptions = [
        factories.PharmacyPrescriptionFactory(
            treatment_procedure_id=tp_1.id,
            user_id=user_id,
            rx_unique_id="test_1",
            status=PrescriptionStatus.SCHEDULED,
        ),
        factories.PharmacyPrescriptionFactory(
            treatment_procedure_id=tp_2.id,
            user_id=user_id,
            rx_unique_id="test_2",
            status=PrescriptionStatus.SHIPPED,
        ),
        factories.PharmacyPrescriptionFactory(
            treatment_procedure_id=tp_3.id,
            user_id=user_id,
            rx_unique_id="test_3",
            status=PrescriptionStatus.CANCELLED,
        ),
    ]
    res = []
    for prescription in created_prescriptions:
        res.append(pharmacy_prescription_repository.create(instance=prescription))
    return res


@pytest.fixture
def rx_integrated_cost_breakdown(
    pharmacy_prescription_repository, wallet, individual_member_health_plan
):
    expected_eligibility_info = {
        "individual_deductible": 25000,
        "individual_deductible_remaining": 0,
        "family_deductible": 50000,
        "family_deductible_remaining": 25000,
        "individual_oop": 150000,
        "individual_oop_remaining": 79309,
        "family_oop": 300000,
        "family_oop_remaining": 229309,
        "coinsurance": 0.0,
        "coinsurance_min": None,
        "coinsurance_max": None,
        "copay": 2000,
    }
    category = ReimbursementRequestCategoryFactory.create(label="fertility")
    rte = RTETransactionFactory.create(
        id=1,
        response=expected_eligibility_info,
        request={},
        response_code=200,
        member_health_plan_id=individual_member_health_plan.id,
    )
    cb_1 = CostBreakdownFactory.create(wallet_id=wallet.id, rte_transaction_id=rte.id)
    tp_1 = TreatmentProcedureFactory.create(
        reimbursement_request_category=category,
        cost_breakdown_id=cb_1.id,
        reimbursement_wallet_id=wallet.id,
        global_procedure_id="8af5df5d-ff8c-4158-8427-b2ad6679c58e",
        member_id=wallet.user_id,
        procedure_type=TreatmentProcedureType.PHARMACY,
        start_date=datetime(year=2025, month=1, day=5).date(),
    )
    prescription = factories.PharmacyPrescriptionFactory(
        treatment_procedure_id=tp_1.id,
        user_id=wallet.user_id,
        rx_unique_id="test_1",
        status=PrescriptionStatus.SCHEDULED,
    )
    pharmacy_prescription_repository.create(instance=prescription)
    return tp_1


@pytest.fixture
def rx_cost_breakdown_for_treatment_procedure(pharmacy_prescription_repository, wallet):
    category = ReimbursementRequestCategoryFactory.create(label="fertility")
    cb_1 = CostBreakdownFactory.create(
        wallet_id=wallet.id, beginning_wallet_balance=10, ending_wallet_balance=5
    )
    tp_1 = TreatmentProcedureFactory.create(
        reimbursement_request_category=category,
        cost_breakdown_id=cb_1.id,
        reimbursement_wallet_id=wallet.id,
        global_procedure_id="8af5df5d-ff8c-4158-8427-b2ad6679c58e",
        member_id=wallet.user_id,
        procedure_type=TreatmentProcedureType.PHARMACY,
        start_date=datetime(year=2025, month=1, day=5).date(),
    )
    prescription = factories.PharmacyPrescriptionFactory(
        treatment_procedure_id=tp_1.id,
        user_id=wallet.user_id,
        rx_unique_id="test_1",
        status=PrescriptionStatus.SCHEDULED,
    )
    pharmacy_prescription_repository.create(instance=prescription)
    return tp_1


@pytest.fixture()
def smp_scheduled_file():
    def _smp_scheduled_file(
        ncpdp="5710365",
        benefit_id="12345",
        ndc="44087-1150-01",
        date="09/01/2023",
        unique_identifier="7065817-12",
        rx_id="7065817",
        first_name="Jane",
        last_name="Doe",
        raw_data=None,
        rx_received_date="08/01/2023",
    ):
        f = tempfile.NamedTemporaryFile()
        if raw_data:
            data = raw_data
        else:
            data = (
                "Rx Received Date,NCPDP Number,First Name,Last Name,Maven Benefit ID,NDC#,Drug Name,Drug Description,"
                "Rx Quantity,Order Number,Cash List Price,EMD Maven Coupons,SMP Maven Discounts,Other Savings,"
                "Amount Owed to SMP,SMP Patient ID,Prescribing Clinic,Rx #,Fill Number,Unique Identifier,Scheduled "
                "Ship "
                f"Date\r\n{rx_received_date},{ncpdp},{first_name},{last_name},{benefit_id},{ndc},OVIDREL 250 MCG/0.5ML SUBCUTANEOUS "
                f"INJECTABLE,OVIDREL 250 MCG/0.5ML SUBCUTANEOUS INJECTABLE,1,{rx_id},107,0,5.35,53.5,48.15,567891,"
                f"Advanced Fertility Center Of Chicago,7065817,12,{unique_identifier},{date}"
            )
        f.write(bytes(data, encoding="utf-8"))
        f.seek(0)
        return f

    return _smp_scheduled_file


@pytest.fixture()
def smp_shipped_file():
    def _smp_shipped_file(
        ncpdp="5710365",
        benefit_id="12345",
        ndc="44087-1150-01",
        date="09/01/2023",
        unique_identifier="7065817-12",
        rx_id="7065817",
        first_name="Jane",
        last_name="Doe",
        rx_adjusted="N",
        ship_date="09/02/2023",
        cost="48.15",
        raw_data=None,
        rx_received_date="08/01/2023",
    ):
        f = tempfile.NamedTemporaryFile()
        f.name = "Maven_Rx_Shipped_2024201_063051.csv"
        if raw_data:
            data = raw_data
        else:
            data = (
                "Rx Received Date,NCPDP Number,First Name,Last Name,Maven Benefit ID,NDC#,Drug Name,Drug Description,"
                "Rx Quantity,Order Number,Cash List Price,EMD Maven Coupons,SMP Maven Discounts,Other Savings,"
                "Amount Owed to SMP,SMP Patient ID,Prescribing Clinic,Rx #,Fill Number,Unique Identifier,Scheduled "
                "Ship Date,Rx Adjusted,Actual Ship Date"
                f"\r\n{rx_received_date},{ncpdp},{first_name},{last_name},{benefit_id},{ndc},OVIDREL 250 MCG/0.5ML SUBCUTANEOUS "
                f"INJECTABLE,OVIDREL 250 MCG/0.5ML SUBCUTANEOUS INJECTABLE,1,{rx_id},107,0,5.35,53.5,{cost},567891,"
                f"Advanced Fertility Center Of Chicago,7065817,12,{unique_identifier},{date},{rx_adjusted},{ship_date}"
            )
        f.write(bytes(data, encoding="utf-8"))
        f.seek(0)
        return f

    return _smp_shipped_file


@pytest.fixture()
def smp_cancelled_file():
    def _smp_cancelled_file(
        ncpdp="5710365",
        benefit_id="12345",
        ndc="44087-1150-01",
        unique_identifier="7065817-12",
        rx_id="7065817",
        first_name="Jane",
        last_name="Doe",
        ship_date="09/02/2023",
        cost="48.15",
        cancelled_date="09/03/2023",
        raw_data=None,
    ):
        f = tempfile.NamedTemporaryFile()
        if raw_data:
            data = raw_data
        else:
            data = (
                "Rx Received Date,NCPDP Number,First Name,Last Name,Maven Benefit ID,NDC#,Drug Name,Drug Description,"
                "Rx Quantity,Order Number,Cash List Price,EMD Maven Coupons,SMP Maven Discounts,Other Savings,"
                "Amount Owed to SMP,SMP Patient ID,Prescribing Clinic,Rx #,Fill Number,Unique Identifier,Scheduled "
                "Ship Date,Rx Canceled Date"
                f"\r\n8/1/2023,{ncpdp},{first_name},{last_name},{benefit_id},{ndc},OVIDREL 250 MCG/0.5ML SUBCUTANEOUS "
                f"INJECTABLE,OVIDREL 250 MCG/0.5ML SUBCUTANEOUS INJECTABLE,1,{rx_id},107,0,5.35,53.5,{cost},567891,"
                f"Advanced Fertility Center Of Chicago,7065817,12,{unique_identifier},{ship_date},{cancelled_date}"
            )
        f.write(bytes(data, encoding="utf-8"))
        f.seek(0)
        return f

    return _smp_cancelled_file


@pytest.fixture()
def smp_reimbursement_file():
    def _smp_reimbursement_file(
        ncpdp="5710365",
        benefit_id="12345",
        ndc="44087-1150-01",
        date="09/01/2023",
        unique_identifier="7065817-12",
        rx_id="7065817",
        first_name="Jane",
        last_name="Doe",
        filled_date="09/02/2023",
        amount_paid="48.15",
        raw_data=None,
        rx_received_date="08/01/2023",
    ):
        f = tempfile.NamedTemporaryFile()
        f.name = "Maven_Rx_Reimbursement_2024201_063051.csv"
        if raw_data:
            data = raw_data
        else:
            data = (
                "Rx Received Date,NCPDP Number,First Name,Last Name,User Benefit ID,NDC#,Drug Name,Drug Description,"
                "Rx Quantity,Order Number,Amount Paid,SMP Patient ID,Prescribing Clinic,Rx #,Fill Number,"
                "Unique Identifier,Actual Ship Date,Filled Date"
                f"\r\n{rx_received_date},{ncpdp},{first_name},{last_name},{benefit_id},{ndc},OVIDREL 250 MCG/0.5ML SUBCUTANEOUS "
                f"INJECTABLE,OVIDREL 250 MCG/0.5ML SUBCUTANEOUS INJECTABLE,1,{rx_id},{amount_paid},999999,"
                f"Advanced Fertility Center Of Chicago,7065817,12,{unique_identifier},{date},{filled_date}"
            )
        f.write(bytes(data, encoding="utf-8"))
        f.seek(0)
        return f

    return _smp_reimbursement_file


@pytest.fixture
def health_plan_ytd_spend_repository(testdb):
    with patch.object(
        BaseRepository, "session", new_callable=PropertyMock
    ) as mock_session:
        mock_session.return_value = testdb.session
        yield HealthPlanYearToDateSpendRepository(session=testdb.session)


@pytest.fixture
def health_plan_ytd_spend_service(session):
    return HealthPlanYearToDateSpendService(session=session)


@pytest.fixture
def multiple_ytd_spends(health_plan_ytd_spend_repository):
    mocked_ytd_spends = [
        HealthPlanYearToDateSpendFactory.create(
            policy_id="policy1",
            first_name="paul",
            last_name="chris",
            year=2023,
            source="MAVEN",
            deductible_applied_amount=10_000,
            oop_applied_amount=10_000,
        ),
        HealthPlanYearToDateSpendFactory.create(
            policy_id="policy1",
            first_name="paul",
            last_name="chris",
            year=2023,
            source="MAVEN",
            deductible_applied_amount=15_000,
            oop_applied_amount=15_000,
        ),
        HealthPlanYearToDateSpendFactory.create(
            policy_id="policy1",
            first_name="paul",
            last_name="chris",
            year=2023,
            source="ESI",
            deductible_applied_amount=0,
            oop_applied_amount=0,
        ),
        HealthPlanYearToDateSpendFactory.create(
            policy_id="policy1",
            first_name="james",
            last_name="chris",
            year=2023,
            source="ESI",
            deductible_applied_amount=10_000,
            oop_applied_amount=10_000,
        ),
        HealthPlanYearToDateSpendFactory.create(
            policy_id="policy2",
            first_name="james",
            last_name="justin",
            year=2023,
            source="ESI",
            deductible_applied_amount=20_000,
            oop_applied_amount=20_000,
        ),
        HealthPlanYearToDateSpendFactory.create(
            policy_id="policy2",
            first_name="james",
            last_name="justin",
            year=2022,
            source="ESI",
            deductible_applied_amount=20_000,
            oop_applied_amount=20_000,
        ),
    ]
    records = [
        health_plan_ytd_spend_repository.create(instance=ytd_spend)
        for ytd_spend in mocked_ytd_spends
    ]
    yield records

    for record in records:
        health_plan_ytd_spend_repository.delete(id=record.id)


@pytest.fixture
def esi_ytd_spends():
    ytd_spends = [
        HealthPlanYearToDateSpendFactory.build(
            policy_id="policy1",
            first_name="paul",
            last_name="chris",
            year=2023,
            source="ESI",
            deductible_applied_amount=10_000,
            oop_applied_amount=10_000,
        ),
        HealthPlanYearToDateSpendFactory.build(
            policy_id="policy1",
            first_name="paul",
            last_name="chris",
            year=2023,
            source="ESI",
            deductible_applied_amount=-10_000,
            oop_applied_amount=-10_000,
        ),
        HealthPlanYearToDateSpendFactory.build(
            policy_id="policy2",
            first_name="qqq",
            last_name="spy",
            year=2023,
            source="ESI",
            deductible_applied_amount=0,
            oop_applied_amount=0,
        ),
        HealthPlanYearToDateSpendFactory.build(
            policy_id="policy2",
            first_name="qqq",
            last_name="spy",
            year=2023,
            source="ESI",
            deductible_applied_amount=5_000,
            oop_applied_amount=10_000,
        ),
    ]
    return ytd_spends


@pytest.fixture
def mock_storage_client():
    with mock.patch(
        "direct_payment.pharmacy.utils.gcs_handler.storage.Client",
        autospec=True,
        spec_set=True,
    ) as mock_storage:
        yield mock_storage


@pytest.fixture(scope="function")
def copay_cost_sharing():
    cost_sharing = [
        EmployerHealthPlanCostSharing(
            cost_sharing_type=CostSharingType.COPAY,
            cost_sharing_category=CostSharingCategory.GENERIC_PRESCRIPTIONS,
            absolute_amount=2000,
        ),
        EmployerHealthPlanCostSharing(
            cost_sharing_type=CostSharingType.COPAY,
            cost_sharing_category=CostSharingCategory.SPECIALTY_PRESCRIPTIONS,
            absolute_amount=4000,
        ),
    ]
    return cost_sharing


@pytest.fixture(scope="function")
def coinsurance_cost_sharing_with_min_max():
    cost_sharing = [
        EmployerHealthPlanCostSharing(
            cost_sharing_type=CostSharingType.COINSURANCE,
            cost_sharing_category=CostSharingCategory.GENERIC_PRESCRIPTIONS,
            percent=0.05,
        ),
        EmployerHealthPlanCostSharing(
            cost_sharing_type=CostSharingType.COINSURANCE_MAX,
            cost_sharing_category=CostSharingCategory.GENERIC_PRESCRIPTIONS,
            absolute_amount=20000,
        ),
        EmployerHealthPlanCostSharing(
            cost_sharing_type=CostSharingType.COINSURANCE_MIN,
            cost_sharing_category=CostSharingCategory.GENERIC_PRESCRIPTIONS,
            absolute_amount=10000,
        ),
        EmployerHealthPlanCostSharing(
            cost_sharing_type=CostSharingType.COINSURANCE,
            cost_sharing_category=CostSharingCategory.SPECIALTY_PRESCRIPTIONS,
            percent=0.1,
        ),
        EmployerHealthPlanCostSharing(
            cost_sharing_type=CostSharingType.COINSURANCE_MAX,
            cost_sharing_category=CostSharingCategory.SPECIALTY_PRESCRIPTIONS,
            absolute_amount=30000,
        ),
        EmployerHealthPlanCostSharing(
            cost_sharing_type=CostSharingType.COINSURANCE_MIN,
            cost_sharing_category=CostSharingCategory.SPECIALTY_PRESCRIPTIONS,
            absolute_amount=20000,
        ),
    ]
    return cost_sharing


@pytest.fixture(scope="function")
def individual_member_health_plan(wallet, coinsurance_cost_sharing_with_min_max):
    wallet.reimbursement_organization_settings.deductible_accumulation_enabled = True
    employer_health_plan = EmployerHealthPlanFactory.create(
        cost_sharings=coinsurance_cost_sharing_with_min_max,
        reimbursement_organization_settings=wallet.reimbursement_organization_settings,
        rx_integrated=False,
        coverage=[
            EmployerHealthPlanCoverageFactory.create(
                coverage_type=CoverageType.RX,
                individual_deductible=100000,
                individual_oop=200000,
                family_deductible=200000,
                family_oop=300000,
            ),
            EmployerHealthPlanCoverageFactory.create(
                coverage_type=CoverageType.MEDICAL,
                individual_deductible=100000,
                individual_oop=200000,
                family_deductible=200000,
                family_oop=300000,
            ),
        ],
    )
    return MemberHealthPlanFactory.create(
        reimbursement_wallet=wallet,
        employer_health_plan=employer_health_plan,
        is_subscriber=True,
        plan_start_at=datetime(year=2025, month=1, day=1),
        plan_end_at=datetime(year=2026, month=1, day=1),
    )


@pytest.fixture(scope="function")
def tiered_individual_member_health_plan(wallet, coinsurance_cost_sharing_with_min_max):
    wallet.reimbursement_organization_settings.deductible_accumulation_enabled = True
    employer_health_plan = EmployerHealthPlanFactory.create(
        cost_sharings=coinsurance_cost_sharing_with_min_max,
        reimbursement_organization_settings=wallet.reimbursement_organization_settings,
        rx_integrated=False,
        coverage=[
            EmployerHealthPlanCoverageFactory.create(
                coverage_type=CoverageType.RX,
                individual_deductible=100000,
                individual_oop=200000,
                family_deductible=200000,
                family_oop=300000,
                tier=Tier.PREMIUM,
            ),
            EmployerHealthPlanCoverageFactory.create(
                coverage_type=CoverageType.MEDICAL,
                individual_deductible=100000,
                individual_oop=200000,
                family_deductible=200000,
                family_oop=300000,
                tier=Tier.PREMIUM,
            ),
        ],
    )
    return MemberHealthPlanFactory.create(
        reimbursement_wallet=wallet,
        employer_health_plan=employer_health_plan,
        is_subscriber=True,
        plan_start_at=datetime(year=2025, month=1, day=1),
        plan_end_at=datetime(year=2026, month=1, day=1),
    )


@pytest.fixture(scope="function")
def family_member_health_plan(wallet, copay_cost_sharing):
    wallet.reimbursement_organization_settings.deductible_accumulation_enabled = True
    employer_health_plan = EmployerHealthPlanFactory.create(
        cost_sharings=copay_cost_sharing,
        reimbursement_organization_settings=wallet.reimbursement_organization_settings,
        rx_integrated=False,
        coverage=[
            EmployerHealthPlanCoverageFactory.create(
                coverage_type=CoverageType.RX,
                plan_type=FamilyPlanType.FAMILY,
                individual_deductible=100000,
                individual_oop=200000,
                family_deductible=200000,
                family_oop=300000,
            ),
            EmployerHealthPlanCoverageFactory.create(
                coverage_type=CoverageType.MEDICAL,
                plan_type=FamilyPlanType.FAMILY,
                individual_deductible=100000,
                individual_oop=200000,
                family_deductible=200000,
                family_oop=300000,
            ),
        ],
    )
    return MemberHealthPlanFactory.create(
        reimbursement_wallet=wallet,
        employer_health_plan=employer_health_plan,
        plan_type=FamilyPlanType.FAMILY,
        is_subscriber=True,
        plan_start_at=datetime(year=2025, month=1, day=1),
        plan_end_at=datetime(year=2026, month=1, day=1),
    )


@pytest.fixture
def billing_service(session):
    return BillingService(session=session, is_in_uow=True)


@pytest.fixture
def automated_reimbursement_request_service():
    return AutomatedReimbursementRequestService()


@pytest.fixture(scope="function")
def rx_reimbursement_request(wallet):
    category_association = (
        wallet.reimbursement_organization_settings.allowed_reimbursement_categories[0]
    )
    category_association.reimbursement_request_category_maximum = 10000
    category = category_association.reimbursement_request_category
    return ReimbursementRequestFactory.create(
        reimbursement_wallet_id=wallet.id,
        reimbursement_request_category_id=category.id,
        reimbursement_type=ReimbursementRequestType.MANUAL,
        procedure_type=TreatmentProcedureType.PHARMACY.value,
        cost_sharing_category=CostSharingCategory.GENERIC_PRESCRIPTIONS,
        person_receiving_service_id=wallet.user_id,
        expense_type=ReimbursementRequestExpenseTypes.FERTILITY,
        cost_credit=0,
        amount=5000,
        auto_processed=ReimbursementRequestAutoProcessing.RX,
    )


@pytest.fixture(scope="function")
def rx_cost_breakdown_for_reimbursement_request(
    pharmacy_prescription_repository, wallet, rx_reimbursement_request, new_prescription
):
    cost_breakdown = CostBreakdownFactory.create(
        wallet_id=wallet.id,
        beginning_wallet_balance=10,
        ending_wallet_balance=5,
        reimbursement_request_id=rx_reimbursement_request.id,
    )
    prescription = factories.PharmacyPrescriptionFactory(
        reimbursement_request_id=rx_reimbursement_request.id,
        user_id=wallet.user_id,
        rx_unique_id="test_1",
        status=PrescriptionStatus.SCHEDULED,
    )
    pharmacy_prescription_repository.create(instance=prescription)
    return cost_breakdown


@pytest.fixture
def mocked_auto_processed_claim_response():
    def _mocked_response(status_code, reimbursement_mode, amount, error_code="0"):
        mock_response = Response()
        mock_response.status_code = status_code
        payload = {
            "ReimbursementMode": reimbursement_mode,
            "PayProviderFlag": "No",
            "TrackingNumber": "TESTTRACKING",
            "TxnResponseList": [
                {"AcctTypeCde": "HRA", "DisbBal": 0.00, "TxnAmt": amount}
            ],
            "TxnAmtOrig": amount,
            "TxnApprovedAmt": amount,
            "ErrorCode": error_code,
        }
        mock_response.json = lambda: payload

        return mock_response

    return _mocked_response


@pytest.fixture(scope="function")
def qualified_wallet_eligibility_verification(wallet):
    date_range = DateRangeFactory()
    date_range.upper = datetime.utcnow().date()
    return e9y.EligibilityVerification(
        user_id=wallet.member.id,
        organization_id=wallet.reimbursement_organization_settings.organization_id,  # noqa: E501
        unique_corp_id="Abc212",
        dependent_id="ABC224",
        first_name="Test",
        last_name="User",
        date_of_birth=date.today(),
        email="test@mavenclinic.com",
        verified_at=datetime.utcnow(),
        created_at=datetime.utcnow(),
        verification_type="lookup",
        is_active=True,
        record={"employee_start_date": str(date.today())},
        effective_range=date_range,
    )


@pytest.fixture
def smp_gcs_ff_enabled(ff_test_data):
    def _mock(is_on: bool = True):
        ff_test_data.update(
            ff_test_data.flag(ENABLE_SMP_GCS_BUCKET_PROCESSING).variation_for_all(is_on)
        )

    return _mock


@pytest.fixture(autouse=True)
def mock_gcs_client():
    with patch("google.cloud.storage.Client") as MockClient:
        yield MockClient


@pytest.fixture
def mock_pharmacy_file_handler():
    mock_handler = Mock(spec=PharmacyFileHandler)
    mock_handler.outgoing_bucket = Mock(spec=Bucket)
    mock_handler.internal_bucket = Mock(spec=Bucket)
    return mock_handler
