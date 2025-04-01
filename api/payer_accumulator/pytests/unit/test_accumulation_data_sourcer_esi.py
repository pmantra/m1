import datetime

import pytest as pytest
from maven import feature_flags

from direct_payment.treatment_procedure.models.treatment_procedure import (
    TreatmentProcedureStatus,
    TreatmentProcedureType,
)
from direct_payment.treatment_procedure.pytests.factories import (
    TreatmentProcedureFactory,
)
from payer_accumulator.accumulation_data_sourcer_esi import AccumulationDataSourcerESI
from payer_accumulator.common import PayerName
from payer_accumulator.models.accumulation_treatment_mapping import (
    AccumulationTreatmentMapping,
)
from payer_accumulator.pytests.factories import PayerFactory
from wallet.pytests.factories import (
    EmployerHealthPlanFactory,
    MemberHealthPlanFactory,
    ReimbursementOrganizationSettingsFactory,
    ReimbursementWalletFactory,
)
from wallet.repository.health_plan import (
    HEALTH_PLAN_YOY_FLAG,
    NEW_BEHAVIOR,
    OLD_BEHAVIOR,
)


@pytest.fixture
def ESI_payer():
    return PayerFactory.create(payer_name=PayerName.ESI)


@pytest.fixture
def non_esi_payer():
    return PayerFactory.create(payer_name=PayerName.AETNA)


@pytest.fixture
def valid_esi_ehp(non_esi_payer):
    org_settings = ReimbursementOrganizationSettingsFactory.create(
        deductible_accumulation_enabled=True,
    )
    ehp = EmployerHealthPlanFactory.create(
        name="Valid ESI EHP",
        reimbursement_org_settings_id=org_settings.id,
        reimbursement_organization_settings=org_settings,
        benefits_payer_id=non_esi_payer.id,
        rx_integrated=False,
    )
    return ehp


@pytest.fixture
def invalid_esi_ehp(non_esi_payer):
    org_settings = ReimbursementOrganizationSettingsFactory.create(
        deductible_accumulation_enabled=True,
    )
    ehp = EmployerHealthPlanFactory.create(
        name="Invalid ESI EHP",
        reimbursement_org_settings_id=org_settings.id,
        reimbursement_organization_settings=org_settings,
        benefits_payer_id=non_esi_payer.id,
        rx_integrated=True,  # Invalid for ESI
    )
    return ehp


@pytest.fixture
def invalid_esi_ehp_non_da(non_esi_payer):
    org_settings = ReimbursementOrganizationSettingsFactory.create(
        deductible_accumulation_enabled=False,  # Invalid for ESI
    )
    ehp = EmployerHealthPlanFactory.create(
        reimbursement_org_settings_id=org_settings.id,
        reimbursement_organization_settings=org_settings,
        benefits_payer_id=non_esi_payer.id,
        rx_integrated=False,  # Invalid for ESI
    )
    return ehp


@pytest.fixture
def invalid_esi_ehp_with_esi(ESI_payer):
    org_settings = ReimbursementOrganizationSettingsFactory.create(
        deductible_accumulation_enabled=False,  # Invalid for ESI
    )
    ehp = EmployerHealthPlanFactory.create(
        reimbursement_org_settings_id=org_settings.id,
        reimbursement_organization_settings=org_settings,
        benefits_payer_id=ESI_payer.id,
        rx_integrated=True,  # Not really a valid setting, I think?
    )
    return ehp


@pytest.fixture
def valid_esi_wallet(valid_esi_ehp):
    valid_wallet = ReimbursementWalletFactory.create(
        reimbursement_organization_settings_id=valid_esi_ehp.reimbursement_org_settings_id,
    )
    MemberHealthPlanFactory.create(
        member_id=valid_wallet.user_id,
        employer_health_plan_id=valid_esi_ehp.id,
        employer_health_plan=valid_esi_ehp,
        reimbursement_wallet=valid_wallet,
        reimbursement_wallet_id=valid_wallet.id,
        plan_start_at=datetime.datetime(2020, 1, 1),
    )
    return valid_wallet


@pytest.fixture
def invalid_esi_wallet(invalid_esi_ehp):
    invalid_wallet = ReimbursementWalletFactory.create(
        reimbursement_organization_settings_id=invalid_esi_ehp.reimbursement_org_settings_id,
    )
    MemberHealthPlanFactory.create(
        member_id=invalid_wallet.user_id,
        employer_health_plan_id=invalid_esi_ehp.id,
        employer_health_plan=invalid_esi_ehp,
        reimbursement_wallet=invalid_wallet,
        reimbursement_wallet_id=invalid_wallet.id,
        plan_start_at=datetime.datetime(2020, 1, 1),
    )
    return invalid_wallet


@pytest.fixture(scope="function")
def accumulation_data_sourcer_esi(session, ESI_payer):
    return AccumulationDataSourcerESI(session)


def test_accumulation_employer_health_plans(
    accumulation_data_sourcer_esi,
    valid_esi_ehp,
    invalid_esi_ehp,
    invalid_esi_ehp_non_da,
    invalid_esi_ehp_with_esi,
):
    ehps = accumulation_data_sourcer_esi._accumulation_employer_health_plans
    assert len(ehps) == 1
    assert ehps == [valid_esi_ehp]
    assert invalid_esi_ehp not in ehps
    assert invalid_esi_ehp_non_da not in ehps
    assert (
        invalid_esi_ehp_with_esi not in ehps
    )  # The ESI payer is irrelevant to the ESI query!


@pytest.mark.parametrize(
    argnames="feature_flag_variation", argvalues=[OLD_BEHAVIOR, NEW_BEHAVIOR]
)
def test_get_medical_accumulation_wallet_ids(
    accumulation_data_sourcer_esi,
    feature_flag_variation,
    ff_test_data,
    valid_esi_wallet,
    invalid_esi_wallet,
):
    with feature_flags.test_data() as ff_test_data:
        ff_test_data.update(
            ff_test_data.flag(HEALTH_PLAN_YOY_FLAG).variations(feature_flag_variation)
        )
        (
            medical_ids,
            rx_ids,
        ) = accumulation_data_sourcer_esi._get_medical_and_rx_accumulation_wallet_ids()
    assert medical_ids is None
    assert rx_ids == [valid_esi_wallet.id]
    assert invalid_esi_wallet.id not in rx_ids


def test_esi_accumulation_with_procedures(
    accumulation_data_sourcer_esi, ff_test_data, valid_esi_wallet
):
    valid_tp = TreatmentProcedureFactory.create(
        reimbursement_wallet_id=valid_esi_wallet.id,
        procedure_type=TreatmentProcedureType.PHARMACY,
        status=TreatmentProcedureStatus.COMPLETED,
        start_date=datetime.date(2024, 1, 1),
        member_id=valid_esi_wallet.user_id,
    )

    with feature_flags.test_data() as ff_test_data:
        ff_test_data.update(
            ff_test_data.flag(HEALTH_PLAN_YOY_FLAG).variations(NEW_BEHAVIOR)
        )
        accumulation_data_sourcer_esi._insert_new_data_for_generation()

    mapping = AccumulationTreatmentMapping.query.filter(
        AccumulationTreatmentMapping.treatment_procedure_uuid == valid_tp.uuid
    ).first()
    assert mapping is not None
