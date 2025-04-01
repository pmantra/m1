import pytest

from data_admin.makers.health_plans import (
    EmployerHealthPlanMaker,
    MemberHealthPlanMaker,
)
from payer_accumulator.common import PayerName
from payer_accumulator.pytests.factories import PayerFactory
from pytests.factories import EnterpriseUserFactory
from wallet.models.constants import WalletState
from wallet.pytests.factories import (
    EmployerHealthPlanFactory,
    ReimbursementOrganizationSettingsFactory,
    ReimbursementWalletFactory,
)


def test_employer_health_plan__successful():
    # Given
    employer_health_plan_spec = {
        "user_email": "test+staff@mavenclinic.com",
        "start_date": "2023-01-01",
        "end_date": "2023-12-30",
        "payer": "UHC",
        "ind_deductible_limit": 100000,
        "ind_oop_max_limit": 200000,
        "fam_deductible_limit": 200000,
        "fam_oop_max_limit": 500000,
        "carrier_number": "12345",
        "is_deductible_embedded": True,
        "is_oop_embedded": False,
    }
    enterprise_user = EnterpriseUserFactory.create(email="test+staff@mavenclinic.com")
    ReimbursementWalletFactory.create(member=enterprise_user)
    PayerFactory.create(payer_name=PayerName.UHC)

    # When
    emp_health_plan = EmployerHealthPlanMaker().create_object_and_flush(
        spec=employer_health_plan_spec
    )
    # Then
    assert emp_health_plan


def test_employer_health_plan__fails_with_missing_required_param():
    # Given
    employer_health_plan_spec = {
        "start_date": "2023-01-01",
        "end_date": "2023-12-30",
        "ind_deductible_limit": 100000,
        "ind_oop_max_limit": 200000,
        "fam_deductible_limit": 200000,
        "fam_oop_max_limit": 500000,
        "carrier_number": "12345",
        "is_deductible_embedded": True,
        "is_oop_embedded": False,
    }
    # When / Then
    with pytest.raises(ValueError) as error_msg:
        EmployerHealthPlanMaker().create_object_and_flush(
            spec=employer_health_plan_spec
        )
    assert str(error_msg.value) == "Missing param(s): ['payer']"


def test_member_health_plan__successful():
    # Given
    enterprise_user = EnterpriseUserFactory.create(email="test+staff@mavenclinic.com")
    member_health_plan_spec = {
        "user_email": "test+staff@mavenclinic.com",
        "employer_health_plan_id": "123456",
        "member_id": f"{enterprise_user.id}",
        "subscriber_insurance_id": "999888",
        "subscriber_first_name": "sub-first-name",
        "subscriber_last_name": "sub-last-name",
        "subscriber_date_of_birth": "1980-12-01",
        "patient_first_name": "patient-first-name",
        "patient_last_name": "patient-last-name",
        "patient_date_of_birth": "1980-12-01",
        "patient_sex": "female",
        "patient_relationship": "cardholder",
    }
    wallet = ReimbursementWalletFactory.create(
        member=enterprise_user, state=WalletState.QUALIFIED
    )
    org_settings = ReimbursementOrganizationSettingsFactory.create(
        organization_id=1,
        deductible_accumulation_enabled=True,
    )
    employer_health_plan = EmployerHealthPlanFactory.create(
        id=123456, reimbursement_organization_settings=org_settings
    )
    # When
    member_health_plan = MemberHealthPlanMaker().create_object_and_flush(
        spec=member_health_plan_spec
    )
    # Then
    assert member_health_plan
    assert member_health_plan.plan_start_at.date() == employer_health_plan.start_date
    assert member_health_plan.plan_end_at.date() == employer_health_plan.end_date
    assert member_health_plan.member_id == enterprise_user.id
    assert member_health_plan.reimbursement_wallet_id == wallet.id


def test_member_health_plan__fails_with_missing_required_param():
    # Given
    member_health_plan_spec = {
        "member_id": "999888",
        "subscriber_insurance_id": "999888",
        "subscriber_first_name": "sub-first-name",
        "subscriber_last_name": "sub-last-name",
        "subscriber_date_of_birth": "1980-12-01",
        "patient_first_name": "patient-first-name",
        "patient_last_name": "patient-last-name",
        "patient_date_of_birth": "1980-12-01",
        "patient_sex": "female",
        "patient_relationship": "cardholder",
    }
    # When
    with pytest.raises(ValueError) as error_msg:
        MemberHealthPlanMaker().create_object_and_flush(spec=member_health_plan_spec)
    # Then
    assert str(error_msg.value) == "Missing param(s): ['user_email']"
