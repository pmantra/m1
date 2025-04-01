from datetime import date, datetime, timedelta
from unittest.mock import Mock, patch

import pytest

from cost_breakdown.pytests.factories import CostBreakdownFactory
from direct_payment.billing import models
from direct_payment.billing.pytests.factories import BillFactory
from direct_payment.treatment_procedure.models.treatment_procedure import (
    TreatmentProcedureStatus,
    TreatmentProcedureType,
)
from direct_payment.treatment_procedure.pytests import factories
from direct_payment.treatment_procedure.pytests.factories import (
    TreatmentProcedureFactory,
)
from payer_accumulator.accumulation_data_sourcer import AccumulationDataSourcer
from payer_accumulator.common import PayerName, TreatmentAccumulationStatus
from payer_accumulator.file_generators import AccumulationFileGeneratorUHC
from payer_accumulator.models.payer_list import Payer
from payer_accumulator.pytests.factories import (
    AccumulationTreatmentMappingFactory,
    PayerFactory,
)
from pytests.freezegun import freeze_time
from wallet.models.constants import (
    MemberHealthPlanPatientRelationship,
    MemberHealthPlanPatientSex,
    ReimbursementRequestExpenseTypes,
    WalletState,
)
from wallet.pytests.factories import (
    EmployerHealthPlanFactory,
    MemberHealthPlanFactory,
    ReimbursementOrganizationSettingsFactory,
    ReimbursementRequestCategoryFactory,
    ReimbursementRequestFactory,
    ReimbursementWalletFactory,
)
from wallet.pytests.fixtures import WalletTestHelper
from wallet.repository.health_plan import HEALTH_PLAN_YOY_FLAG, NEW_BEHAVIOR


@pytest.fixture(scope="function")
def aetna_payer():
    return PayerFactory.create(payer_name=PayerName.AETNA)


@pytest.fixture(scope="function")
def anthem_payer():
    return PayerFactory.create(payer_name=PayerName.ANTHEM)


@pytest.fixture(scope="function")
def bcbs_ma_payer():
    return PayerFactory.create(payer_name=PayerName.BCBS_MA)


@pytest.fixture(scope="function")
def cigna_payer():
    return PayerFactory.create(payer_name=PayerName.Cigna)


@pytest.fixture(scope="function")
def credence_payer():
    return PayerFactory.create(payer_name=PayerName.CREDENCE)


@pytest.fixture(scope="function")
def luminare_payer():
    return PayerFactory.create(payer_name=PayerName.LUMINARE)


@pytest.fixture(scope="function")
def premera_payer():
    return PayerFactory.create(payer_name=PayerName.PREMERA)


@pytest.fixture(scope="function")
def surest_payer():
    return PayerFactory.create(id=1, payer_name=PayerName.SUREST, payer_code="00002")


@pytest.fixture(scope="function")
def uhc_payer():
    return PayerFactory.create(id=123456, payer_name=PayerName.UHC, payer_code="00192")


@pytest.fixture(scope="function")
def esi_payer():
    return PayerFactory.create(id=654321, payer_name=PayerName.ESI, payer_code="00001")


@pytest.fixture(scope="function")
@freeze_time("2023-10-24 13:20:09")
def uhc_file_generator(uhc_payer):
    accumulation_file_generator_uhc = AccumulationFileGeneratorUHC()
    return accumulation_file_generator_uhc


@pytest.fixture(scope="function")
def accumulation_data_sourcer(uhc_payer, session):
    return AccumulationDataSourcer(PayerName.UHC, session)


TP_UUID_2 = "29d597db-d657-4ba8-953e-c5999abf2cb5"
TP_UUID_3 = "6def363f-fccc-40c5-995f-5c8f16108500"
TP_UUID_4 = "b72711d4-f53d-45b3-b8ec-0097fdae4e37"
TP_UUID_5 = "9b2e178d-aaf7-47db-8ae7-d56c8efe8da2"
TP_UUID_6 = "d86e84fb-4297-4b98-952a-f1f3635f5af6"


@pytest.fixture(scope="function")
def treatment_procedures():
    dt_fmt = "%d/%m/%Y %H:%M"
    date_fmt = "%d/%m/%Y"
    procedures = [
        factories.TreatmentProcedureFactory.create(
            id=2,
            cost_breakdown_id=2,
            uuid=TP_UUID_2,
            status=TreatmentProcedureStatus.COMPLETED,
            reimbursement_wallet_id=3,
            start_date=datetime.strptime("15/01/2018", date_fmt),
            end_date=datetime.strptime("15/11/2018", date_fmt),
            completed_date=datetime.strptime("15/11/2018 15:30", dt_fmt),
            procedure_type=TreatmentProcedureType.MEDICAL,
        ),
        factories.TreatmentProcedureFactory.create(
            id=3,
            cost_breakdown_id=2,
            uuid=TP_UUID_3,
            status=TreatmentProcedureStatus.COMPLETED,
            reimbursement_wallet_id=3,
            start_date=datetime.strptime("15/01/2018", date_fmt),
            end_date=datetime.strptime("15/11/2018", date_fmt),
            completed_date=datetime.strptime("15/11/2018 16:30", dt_fmt),
            procedure_type=TreatmentProcedureType.MEDICAL,
        ),
        factories.TreatmentProcedureFactory.create(
            id=4,
            cost_breakdown_id=2,
            uuid=TP_UUID_4,
            status=TreatmentProcedureStatus.COMPLETED,
            reimbursement_wallet_id=3,
            start_date=datetime.strptime("15/01/2018", date_fmt),
            end_date=datetime.strptime("15/11/2018", date_fmt),
            completed_date=datetime.strptime("15/11/2018 15:30", dt_fmt),
            procedure_type=TreatmentProcedureType.MEDICAL,
        ),
        factories.TreatmentProcedureFactory.create(
            id=5,
            cost_breakdown_id=2,
            uuid=TP_UUID_5,
            status=TreatmentProcedureStatus.COMPLETED,
            reimbursement_wallet_id=3,
            start_date=datetime.strptime("15/01/2018", date_fmt),
            end_date=datetime.strptime("15/11/2018", date_fmt),
            completed_date=datetime.strptime("15/11/2018 18:30", dt_fmt),
            procedure_type=TreatmentProcedureType.MEDICAL,
        ),
        factories.TreatmentProcedureFactory.create(
            id=6,
            cost_breakdown_id=2,
            uuid=TP_UUID_6,
            status=TreatmentProcedureStatus.COMPLETED,
            reimbursement_wallet_id=7,
            start_date=datetime.strptime("15/01/2018", date_fmt),
            end_date=datetime.strptime("15/11/2018", date_fmt),
            completed_date=datetime.strptime("15/11/2018 18:30", dt_fmt),
            procedure_type=TreatmentProcedureType.PHARMACY,
        ),
    ]
    return procedures


@pytest.fixture(scope="function")
def latest_treatment_procedure_to_bills():
    dt_fmt = "%d/%m/%Y %H:%M"
    tp_to_bills = {
        2: [
            BillFactory.build(
                payor_id=1,
                amount=5000,
                payor_type=models.PayorType.MEMBER,
                status=models.BillStatus.PAID,
                created_at=datetime.strptime("12/11/2018 00:00", dt_fmt),
            ),
            BillFactory.build(
                payor_id=1,
                amount=5000,
                payor_type=models.PayorType.MEMBER,
                status=models.BillStatus.PAID,
                created_at=datetime.strptime("12/11/2018 00:00", dt_fmt),
            ),
        ],
        3: [
            BillFactory.build(
                payor_id=1,
                amount=15000,
                payor_type=models.PayorType.MEMBER,
                status=models.BillStatus.PAID,
                created_at=datetime.strptime("12/11/2018 00:00", dt_fmt),
            ),
            BillFactory.build(
                payor_id=1,
                amount=-5000,
                payor_type=models.PayorType.MEMBER,
                status=models.BillStatus.REFUNDED,
                created_at=datetime.strptime("12/11/2018 00:00", dt_fmt),
            ),
        ],
        4: [],
        5: [
            BillFactory.build(
                payor_id=1,
                amount=5000,
                payor_type=models.PayorType.MEMBER,
                status=models.BillStatus.PAID,
                created_at=datetime.strptime("12/11/2018 00:00", dt_fmt),
            )
        ],
        6: [
            BillFactory.build(
                payor_id=1,
                amount=5000,
                payor_type=models.PayorType.MEMBER,
                status=models.BillStatus.PAID,
                created_at=datetime.strptime("12/11/2018 00:00", dt_fmt),
            )
        ],
    }
    return tp_to_bills


@pytest.fixture(scope="function")
def waiting_treatment_procedure_to_bills():
    dt_fmt = "%d/%m/%Y %H:%M"
    tp_to_bills = {
        2: [
            BillFactory.build(
                payor_id=1,
                amount=5000,
                payor_type=models.PayorType.MEMBER,
                status=models.BillStatus.PAID,
                created_at=datetime.strptime("12/11/2018 00:00", dt_fmt),
            ),
            BillFactory.build(
                payor_id=1,
                amount=5000,
                payor_type=models.PayorType.MEMBER,
                status=models.BillStatus.PAID,
                created_at=datetime.strptime("12/11/2018 00:00", dt_fmt),
            ),
        ],
        5: [
            BillFactory.build(
                payor_id=1,
                amount=5000,
                payor_type=models.PayorType.MEMBER,
                status=models.BillStatus.PAID,
                created_at=datetime.strptime("12/11/2018 00:00", dt_fmt),
            )
        ],
    }
    return tp_to_bills


@pytest.fixture(scope="function")
def cost_breakdown_mr_200():
    return CostBreakdownFactory.create(
        treatment_procedure_uuid=TP_UUID_2,
        wallet_id=3,
        id=3,
        total_member_responsibility=20000,
        deductible=20000,
        oop_applied=20000,
        created_at=datetime.strptime("12/10/2018 00:00", "%d/%m/%Y %H:%M"),
    )


@pytest.fixture(scope="function")
def cost_breakdown_mr_100():
    return CostBreakdownFactory.create(
        treatment_procedure_uuid=TP_UUID_2,
        wallet_id=3,
        id=2,
        total_member_responsibility=10000,
        deductible=10000,
        oop_applied=10000,
        hra_applied=5000,
        created_at=datetime.strptime("12/11/2018 00:00", "%d/%m/%Y %H:%M"),
    )


@pytest.fixture(scope="function")
def cost_breakdown_mr_150():
    return CostBreakdownFactory.create(
        treatment_procedure_uuid=TP_UUID_2,
        wallet_id=3,
        id=4,
        total_member_responsibility=15000,
        deductible=15000,
        oop_applied=15000,
        created_at=datetime.strptime("12/12/2018 00:00", "%d/%m/%Y %H:%M"),
    )


@pytest.fixture(scope="function")
def employer_health_plan(uhc_payer):
    org_settings = ReimbursementOrganizationSettingsFactory.create(
        id=1,
        organization_id=1,
        deductible_accumulation_enabled=True,
    )
    ehp = EmployerHealthPlanFactory.create(
        id=1,
        reimbursement_org_settings_id=1,
        reimbursement_organization_settings=org_settings,
        start_date=date(2024, 1, 1),
        end_date=date(2099, 1, 1),
        ind_deductible_limit=200_000,
        ind_oop_max_limit=400_000,
        fam_deductible_limit=400_000,
        fam_oop_max_limit=600_000,
        benefits_payer_id=uhc_payer.id,
        rx_integrated=False,
    )
    return ehp


@pytest.fixture(scope="function")
def employer_health_plan2(uhc_payer):
    org_settings2 = ReimbursementOrganizationSettingsFactory.create(
        id=2,
        organization_id=2,
        deductible_accumulation_enabled=True,
    )
    ehp = EmployerHealthPlanFactory.create(
        id=2,
        reimbursement_org_settings_id=2,
        reimbursement_organization_settings=org_settings2,
        start_date=date(2024, 1, 1),
        end_date=date(2099, 1, 1),
        ind_deductible_limit=200_000,
        ind_oop_max_limit=400_000,
        fam_deductible_limit=400_000,
        fam_oop_max_limit=600_000,
        benefits_payer_id=uhc_payer.id,
        rx_integrated=True,
    )
    return ehp


@pytest.fixture(scope="function")
def employer_health_plan3(uhc_payer):
    org_settings3 = ReimbursementOrganizationSettingsFactory.create(
        id=3,
        organization_id=3,
        deductible_accumulation_enabled=False,
    )
    ehp = EmployerHealthPlanFactory.create(
        id=3,
        reimbursement_org_settings_id=3,
        reimbursement_organization_settings=org_settings3,
        start_date=date(2010, 1, 1),
        end_date=date(2010, 1, 1),
        ind_deductible_limit=200_000,
        ind_oop_max_limit=400_000,
        fam_deductible_limit=400_000,
        fam_oop_max_limit=600_000,
        benefits_payer_id=uhc_payer.id,
        rx_integrated=False,
    )
    return ehp


@pytest.fixture(scope="function")
def member_health_plans(employer_health_plan, employer_health_plan2):
    mhps = [
        MemberHealthPlanFactory.create(
            employer_health_plan_id=1,
            reimbursement_wallet=ReimbursementWalletFactory.create(
                id=5, state=WalletState.QUALIFIED
            ),
            employer_health_plan=employer_health_plan,
            reimbursement_wallet_id=5,
            is_subscriber=True,
            patient_sex=MemberHealthPlanPatientSex.FEMALE,
            patient_relationship=MemberHealthPlanPatientRelationship.CARDHOLDER,
            member_id=1,
            subscriber_insurance_id="u1234567801",
        ),
        MemberHealthPlanFactory.create(
            reimbursement_wallet_id=6,
            reimbursement_wallet=ReimbursementWalletFactory.create(
                id=6, state=WalletState.QUALIFIED
            ),
            employer_health_plan=employer_health_plan,
            employer_health_plan_id=1,
            is_subscriber=True,
            patient_sex=MemberHealthPlanPatientSex.MALE,
            patient_relationship=MemberHealthPlanPatientRelationship.SPOUSE,
            subscriber_insurance_id="U1234567802",
        ),
        MemberHealthPlanFactory.create(
            reimbursement_wallet_id=7,
            reimbursement_wallet=ReimbursementWalletFactory.create(
                id=7, state=WalletState.QUALIFIED
            ),
            employer_health_plan=employer_health_plan2,
            employer_health_plan_id=2,
            is_subscriber=True,
            patient_sex=MemberHealthPlanPatientSex.UNKNOWN,
            patient_relationship=MemberHealthPlanPatientRelationship.CHILD,
            subscriber_insurance_id="U1234567802",
        ),
    ]
    return mhps


@pytest.fixture(scope="function")
def accumulation_treatment_mappings():
    atm = [
        # case where treatment procedure is waiting and will remain waiting after querying billing
        AccumulationTreatmentMappingFactory.create(
            treatment_procedure_uuid=TP_UUID_5,
            completed_at=datetime.strptime("15/11/2018 14:30", "%d/%m/%Y %H:%M"),
            treatment_accumulation_status=TreatmentAccumulationStatus.WAITING,
        ),
        # case where treatment procedure is waiting and will be marked paid after querying billing
        AccumulationTreatmentMappingFactory.create(
            treatment_procedure_uuid=TP_UUID_2,
            completed_at=datetime.strptime("15/11/2019 14:30", "%d/%m/%Y %H:%M"),
            treatment_accumulation_status=TreatmentAccumulationStatus.WAITING,
        ),
        # case where treatment procedure is paid and won't be picked up for querying, but will be used as tp cutoff
        AccumulationTreatmentMappingFactory.create(
            treatment_procedure_uuid=TP_UUID_3,
            completed_at=datetime.strptime("15/11/2019 14:33", "%d/%m/%Y %H:%M"),
            treatment_accumulation_status=TreatmentAccumulationStatus.PAID,
        ),
        # case where treatment procedure will not be picked up for the payer we are processing
        AccumulationTreatmentMappingFactory.create(
            payer_id=9123,
            completed_at=datetime.strptime("15/11/2019 14:35", "%d/%m/%Y %H:%M"),
            treatment_accumulation_status=TreatmentAccumulationStatus.WAITING,
        ),
    ]
    return atm


@pytest.fixture()
def make_new_procedure_for_report_row():
    def make_procedure(payer: Payer, cost_breakdown_deductible: int):
        wallet = ReimbursementWalletFactory.create(state=WalletState.QUALIFIED)
        ehp = EmployerHealthPlanFactory.create(
            benefits_payer_id=payer.id,
            reimbursement_organization_settings=wallet.reimbursement_organization_settings,
        )
        MemberHealthPlanFactory.create(
            employer_health_plan_id=ehp.id,
            employer_health_plan=ehp,
            reimbursement_wallet_id=wallet.id,
            reimbursement_wallet=wallet,
            member_id=wallet.member.id,
            patient_sex=MemberHealthPlanPatientSex.UNKNOWN,
            patient_relationship=MemberHealthPlanPatientRelationship.OTHER,
        )
        new_procedure = TreatmentProcedureFactory.create(
            member_id=wallet.member.id,
            reimbursement_wallet_id=wallet.id,
            end_date=datetime.now() + timedelta(days=7),
        )
        cb = CostBreakdownFactory.create(
            treatment_procedure_uuid=new_procedure.uuid,
            wallet_id=wallet.id,
            deductible=cost_breakdown_deductible,
        )
        new_procedure.cost_breakdown_id = cb.id
        return new_procedure

    return make_procedure


@pytest.fixture()
def make_treatment_procedure_equivalent_to_reimbursement_request():
    def make_procedure(
        reimbursement_request,
        record_type,
        deductible_apply_amount,
        oop_apply_amount,
    ):
        wallet = reimbursement_request.wallet
        new_procedure = TreatmentProcedureFactory.create(
            member_id=wallet.member.id,
            reimbursement_wallet_id=wallet.id,
            end_date=reimbursement_request.service_end_date,
            start_date=reimbursement_request.service_start_date,
            procedure_type=record_type,
        )
        cb = CostBreakdownFactory.create(
            treatment_procedure_uuid=new_procedure.uuid,
            wallet_id=wallet.id,
            deductible=deductible_apply_amount,
            oop_applied=oop_apply_amount,
        )
        new_procedure.cost_breakdown_id = cb.id
        return new_procedure, cb

    return make_procedure


@pytest.fixture()
def make_new_reimbursement_request_for_report_row():
    def make_reimbursement_request(payer=None):
        payer_id = payer.id if payer else 1
        wallet = ReimbursementWalletFactory.create(state=WalletState.QUALIFIED)
        ehp = EmployerHealthPlanFactory.create(
            reimbursement_organization_settings=wallet.reimbursement_organization_settings,
            benefits_payer_id=payer_id,
        )
        MemberHealthPlanFactory.create(
            employer_health_plan_id=ehp.id,
            employer_health_plan=ehp,
            reimbursement_wallet_id=wallet.id,
            reimbursement_wallet=wallet,
            member_id=wallet.member.id,
            patient_sex=MemberHealthPlanPatientSex.MALE,
            patient_relationship=MemberHealthPlanPatientRelationship.OTHER,
            subscriber_insurance_id="U1234567801",
        )
        category = ReimbursementRequestCategoryFactory.create(label="fertility")
        reimbursement_request = ReimbursementRequestFactory.create(
            reimbursement_wallet_id=wallet.id,
            reimbursement_request_category_id=category.id,
            person_receiving_service_id=wallet.member.id,
        )
        return reimbursement_request

    return make_reimbursement_request


@pytest.fixture
def add_employer_health_plan():
    def add_ehp(wallet, payer, **kwargs):
        return EmployerHealthPlanFactory.create(
            reimbursement_organization_settings=wallet.reimbursement_organization_settings,
            benefits_payer_id=payer.id,
            **kwargs,
        )

    return add_ehp


@pytest.fixture
def add_member_health_plan():
    def add_mhp(employer_health_plan, wallet, user=None, **kwargs):
        return MemberHealthPlanFactory.create(
            employer_health_plan_id=employer_health_plan.id,
            employer_health_plan=employer_health_plan,
            reimbursement_wallet_id=wallet.id,
            reimbursement_wallet=wallet,
            member_id=user if user else wallet.member.id,
            **kwargs,
        )

    return add_mhp


@pytest.fixture(autouse=True)
def historical_spend_client():
    with patch(
        "wallet.services.wallet_historical_spend.wallet_historical_spend.get_client"
    ) as get_client:
        get_client.return_value = Mock(
            get_historic_spend_records=Mock(return_value=[]),
        )
        yield get_client


@pytest.fixture
def rr_accumulation_wallet(
    uhc_payer, add_employer_health_plan, add_member_health_plan, historical_spend_client
):
    wallet_test_helper = WalletTestHelper()
    organization = wallet_test_helper.create_organization_with_wallet_enabled(
        reimbursement_organization_parameters={"direct_payment_enabled": True}
    )
    wallet_test_helper.add_lifetime_family_benefit(
        organization.reimbursement_organization_settings[0]
    )
    user = wallet_test_helper.create_user_for_organization(
        organization,
        member_profile_parameters={
            "country_code": "US",
            "subdivision_code": "US-NY",
        },
    )
    wallet = wallet_test_helper.create_pending_wallet(
        user,
        wallet_parameters={
            "primary_expense_type": ReimbursementRequestExpenseTypes.FERTILITY
        },
    )
    wallet_test_helper.qualify_wallet(wallet)
    return wallet


@pytest.fixture()
def mhp_yoy_feature_flag_enabled(ff_test_data):
    ff_test_data.update(
        ff_test_data.flag(HEALTH_PLAN_YOY_FLAG).variations(NEW_BEHAVIOR)
    )
