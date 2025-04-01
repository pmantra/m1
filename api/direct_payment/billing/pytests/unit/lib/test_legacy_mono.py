import datetime
import uuid
from unittest.mock import PropertyMock, patch

import pytest

from direct_payment.billing.lib.legacy_mono import (
    get_benefit_id_from_wallet_id,
    get_clinic_locations_as_dicts_from_treatment_procedure_id,
    get_first_and_last_name_from_user_id,
    get_org_invoicing_settings_as_dict_from_ros_id,
    get_organisation_id_from_ros_id,
    get_payor,
    get_payor_id_from_payments_customer_or_recipient_id,
    get_treatment_procedure_ids_with_status_since_bill_timing_change,
    get_treatment_procedures_as_dicts_from_ids,
    payments_customer_id,
)
from direct_payment.billing.models import PayorType
from direct_payment.clinic.pytests.factories import (
    FeeScheduleFactory,
    FeeScheduleGlobalProceduresFactory,
    FertilityClinicFactory,
    FertilityClinicLocationFactory,
)
from direct_payment.invoicing.pytests.factories import (
    OrganizationInvoicingSettingsFactory,
)
from direct_payment.invoicing.repository.organization_invoicing_settings import (
    OrganizationInvoicingSettingsRepository,
)
from direct_payment.treatment_procedure.models.treatment_procedure import (
    TreatmentProcedureStatus,
)
from direct_payment.treatment_procedure.pytests.factories import (
    TreatmentProcedureFactory,
)
from direct_payment.treatment_procedure.repository.treatment_procedure import (
    TreatmentProcedureRepository,
)
from pytests.factories import OrganizationFactory, ResourceFactory
from storage import connection
from wallet.models.reimbursement_wallet import ReimbursementWallet
from wallet.pytests.factories import (
    ReimbursementOrganizationSettingsFactory,
    ReimbursementRequestCategoryFactory,
    ReimbursementWalletBenefitFactory,
)

A_REIMB_ORG_ID = 6789012
A_CLINIC_ID = 226789012


@pytest.fixture()
def payor_type(request):
    return request.param


@pytest.fixture
def payor(payor_type, bill_wallet):
    if payor_type == PayorType.MEMBER:
        return bill_wallet
    if payor_type == PayorType.EMPLOYER:
        return ReimbursementOrganizationSettingsFactory.create(organization_id=1)
    if payor_type == PayorType.CLINIC:
        return FertilityClinicFactory.create()
    return


class TestLegacyMono:
    @pytest.mark.parametrize(
        "payor_type",
        [PayorType.MEMBER, PayorType.EMPLOYER, PayorType.CLINIC],
        indirect=True,
    )
    def test_get_payor(self, payor_type, payor):
        res = get_payor(payor_type, payor.id)
        assert res == payor

    def test_payments_customer_id_found_member(self, bill_wallet):
        res = payments_customer_id(bill_wallet.id, PayorType.MEMBER)
        assert res == uuid.UUID(bill_wallet.payments_customer_id)

    def test_payments_customer_id_not_found_member(self, bill_wallet):
        res = payments_customer_id(bill_wallet.id + 1, PayorType.MEMBER)
        assert res is None

    @pytest.mark.parametrize(
        "exp_payments_customer_id, inp_org_id",
        [
            (str(uuid.uuid4()), A_REIMB_ORG_ID),
            (None, A_REIMB_ORG_ID),
            (None, 9999999),
        ],
        ids=[
            "1. Found match and a payment id",
            "2. Found match but payment id is None",
            "3. Didnt find match",
        ],
    )
    def test_payments_customer_id_employer(
        self, reimbursement_org, exp_payments_customer_id, inp_org_id
    ):
        _ = reimbursement_org(exp_payments_customer_id)
        res = payments_customer_id(inp_org_id, PayorType.EMPLOYER)
        if res:
            res = str(res)
        assert res == exp_payments_customer_id

    @pytest.mark.parametrize(
        "exp_payments_recipient_id, inp_clinic_id",
        [
            (str(uuid.uuid4()), A_CLINIC_ID),
            (None, A_CLINIC_ID),
            (None, 9999999),
        ],
        ids=[
            "1. Found match and a payment recipient id",
            "2. Found match but payment recipient id is None",
            "3. Didnt find match",
        ],
    )
    def test_payments_customer_id_clinic(
        self, fertility_clinic_recipient, exp_payments_recipient_id, inp_clinic_id
    ):
        fertility_clinic_recipient(exp_payments_recipient_id)
        res = payments_customer_id(inp_clinic_id, PayorType.CLINIC)
        if res:
            res = str(res)
        assert res == exp_payments_recipient_id

    @pytest.mark.parametrize(
        "payor_type",
        [PayorType.MEMBER, PayorType.CLINIC, PayorType.EMPLOYER],
    )
    def test_get_payor_id_from_payments_customer_or_recipient_id(
        self,
        bill_wallet,
        reimbursement_org,
        fertility_clinic_recipient,
        payor_type,
    ):
        org = reimbursement_org(A_REIMB_ORG_ID)
        clinic = fertility_clinic_recipient(A_CLINIC_ID)
        inp_uuid = None
        exp_id = None
        if payor_type == PayorType.MEMBER:
            exp_id = bill_wallet.id
            inp_uuid = bill_wallet.payments_customer_id
        elif payor_type == PayorType.EMPLOYER:
            exp_id = org.id
            inp_uuid = org.payments_customer_id
        elif payor_type == PayorType.CLINIC:
            exp_id = clinic.id
            inp_uuid = clinic.payments_recipient_id
        res = get_payor_id_from_payments_customer_or_recipient_id(inp_uuid)
        assert res == (exp_id, payor_type)

    @pytest.mark.parametrize(
        "payor_type",
        [PayorType.MEMBER, PayorType.CLINIC, PayorType.EMPLOYER],
    )
    def test_get_payor_id_from_payments_customer_or_recipient_id_not_found(
        self,
        bill_wallet,
        reimbursement_org,
        fertility_clinic_recipient,
        payor_type,
    ):
        _ = reimbursement_org(A_REIMB_ORG_ID)
        _ = fertility_clinic_recipient(A_CLINIC_ID)
        inp_uuid = str(uuid.uuid4())
        with pytest.raises(ValueError):
            _ = get_payor_id_from_payments_customer_or_recipient_id(inp_uuid)

    def test_get_benefit_id_from_wallet_id(self, bill_wallet):
        benefit = ReimbursementWalletBenefitFactory.create()
        bill_wallet.reimbursement_wallet_benefit = benefit
        res = get_benefit_id_from_wallet_id(bill_wallet.id)
        assert res == benefit.maven_benefit_id

    def test_get_benefit_id_from_wallet_id_failed(self, bill_wallet):
        benefit = ReimbursementWalletBenefitFactory.create()
        bill_wallet.reimbursement_wallet_benefit = benefit
        res = get_benefit_id_from_wallet_id(bill_wallet.id + 1)
        assert res is None

    def test_get_user_first_and_last_name_from_id(self, bill_user):
        res = get_first_and_last_name_from_user_id(bill_user.id)
        assert res == (bill_user.first_name, bill_user.last_name)

    def test_get_first_and_last_name_from_id_failed(self):
        res = get_first_and_last_name_from_user_id(0)
        assert res == ("", "")

    def test_get_treatment_procedure_ids_with_status_since_bill_timing_change(
        self, bill_wallet
    ):
        tp_repo = TreatmentProcedureRepository()
        scheduled_after = TreatmentProcedureFactory.create_batch(3)
        scheduled_after_ids = []
        completed_after = TreatmentProcedureFactory.create_batch(3)
        completed_after_ids = []
        scheduled_before = TreatmentProcedureFactory.create()
        fee_schedule = FeeScheduleFactory.create()
        FeeScheduleGlobalProceduresFactory.create(
            fee_schedule=fee_schedule,
            global_procedure_id=scheduled_before.global_procedure_id,
            cost=10000,
        )
        cat = ReimbursementRequestCategoryFactory.create(
            label="category",
        )
        with patch.object(
            ReimbursementWallet,
            "get_direct_payment_category",
            new=PropertyMock(return_value=cat),
        ):
            scheduled_before_id = (
                tp_repo.create(
                    member_id=scheduled_before.member_id,
                    reimbursement_wallet_id=bill_wallet.id,
                    status=TreatmentProcedureStatus.SCHEDULED,
                    reimbursement_request_category_id=cat.id,
                    fee_schedule_id=fee_schedule.id,
                    global_procedure_id=scheduled_before.global_procedure_id,
                    global_procedure_name=scheduled_before.procedure_name,
                    global_procedure_credits=scheduled_before.cost_credit,
                    fertility_clinic_id=scheduled_before.fertility_clinic_id,
                    fertility_clinic_location_id=scheduled_before.fertility_clinic_location_id,
                    start_date=scheduled_before.start_date,
                )
            ).id
            scheduled_before_tp = tp_repo.get_treatments_by_ids(
                treatment_procedure_ids=[scheduled_before_id]
            )[0]
            scheduled_before_tp.created_at = datetime.datetime.strptime(
                "24/06/2024 12:30", "%d/%m/%Y %H:%M"
            )
            tp_repo.session.add(scheduled_before_tp)
            completed_before_id = (
                tp_repo.create(
                    member_id=scheduled_before.member_id,
                    reimbursement_wallet_id=bill_wallet.id,
                    status=TreatmentProcedureStatus.COMPLETED,
                    reimbursement_request_category_id=cat.id,
                    fee_schedule_id=fee_schedule.id,
                    global_procedure_id=scheduled_before.global_procedure_id,
                    global_procedure_name=scheduled_before.procedure_name,
                    global_procedure_credits=scheduled_before.cost_credit,
                    fertility_clinic_id=scheduled_before.fertility_clinic_id,
                    fertility_clinic_location_id=scheduled_before.fertility_clinic_location_id,
                    start_date=scheduled_before.start_date,
                )
            ).id
            completed_before_tp = tp_repo.get_treatments_by_ids(
                treatment_procedure_ids=[completed_before_id]
            )[0]
            completed_before_tp.created_at = datetime.datetime.strptime(
                "24/06/2024 12:30", "%d/%m/%Y %H:%M"
            )
            tp_repo.session.add(completed_before_tp)
            tp_repo.session.commit()
            for tp in scheduled_after:
                tp = tp_repo.create(
                    member_id=tp.member_id,
                    reimbursement_wallet_id=bill_wallet.id,
                    status=TreatmentProcedureStatus.SCHEDULED,
                    reimbursement_request_category_id=cat.id,
                    fee_schedule_id=fee_schedule.id,
                    global_procedure_id=tp.global_procedure_id,
                    global_procedure_name=tp.procedure_name,
                    global_procedure_credits=tp.cost_credit,
                    fertility_clinic_id=tp.fertility_clinic_id,
                    fertility_clinic_location_id=tp.fertility_clinic_location_id,
                    start_date=tp.start_date,
                )
                scheduled_after_ids.append(tp.id)
            for tp in completed_after:
                tp = tp_repo.create(
                    member_id=tp.member_id,
                    reimbursement_wallet_id=bill_wallet.id,
                    status=TreatmentProcedureStatus.COMPLETED,
                    reimbursement_request_category_id=cat.id,
                    fee_schedule_id=fee_schedule.id,
                    global_procedure_id=tp.global_procedure_id,
                    global_procedure_name=tp.procedure_name,
                    global_procedure_credits=tp.cost_credit,
                    fertility_clinic_id=tp.fertility_clinic_id,
                    fertility_clinic_location_id=tp.fertility_clinic_location_id,
                    start_date=tp.start_date,
                )
                completed_after_ids.append(tp.id)
        scheduled_res = (
            get_treatment_procedure_ids_with_status_since_bill_timing_change(
                statuses=["SCHEDULED"]
            )
        )
        for id in scheduled_after_ids:
            assert id in scheduled_res
        assert scheduled_before_id not in scheduled_res
        completed_res = (
            get_treatment_procedure_ids_with_status_since_bill_timing_change(
                statuses=["COMPLETED"]
            )
        )
        for id in completed_after_ids:
            assert id in completed_res
        assert completed_before_id not in completed_res

    def test_get_clinic_locations_as_dicts_from_treatment_procedure_id(
        self, bill_wallet
    ):
        clinic = FertilityClinicFactory()
        clinic_location = FertilityClinicLocationFactory.create(
            fertility_clinic_id=clinic.id, fertility_clinic=clinic
        )
        TreatmentProcedureFactory.create()
        tp = TreatmentProcedureFactory.create(
            fertility_clinic_location_id=clinic_location.id,
        )
        result = get_clinic_locations_as_dicts_from_treatment_procedure_id(
            treatment_procedure_id=tp.id
        )
        assert result["city"] == "New York City"

    def test_get_treatment_procedures_as_dicts_from_ids(self, bill_wallet):
        tp_repo = TreatmentProcedureRepository()
        tps = TreatmentProcedureFactory.create_batch(5)
        tp_ids = []
        cat = ReimbursementRequestCategoryFactory.create(
            label="category",
        )
        with patch.object(
            ReimbursementWallet,
            "get_direct_payment_category",
            new=PropertyMock(return_value=cat),
        ):
            for tp in tps:
                fee_schedule = FeeScheduleFactory.create()
                FeeScheduleGlobalProceduresFactory.create(
                    fee_schedule=fee_schedule,
                    global_procedure_id=tp.global_procedure_id,
                    cost=10000,
                )
                tp = tp_repo.create(
                    member_id=tp.member_id,
                    reimbursement_wallet_id=bill_wallet.id,
                    reimbursement_request_category_id=cat.id,
                    fee_schedule_id=fee_schedule.id,
                    global_procedure_id=tp.global_procedure_id,
                    global_procedure_name=tp.procedure_name,
                    global_procedure_credits=tp.cost_credit,
                    fertility_clinic_id=tp.fertility_clinic_id,
                    fertility_clinic_location_id=tp.fertility_clinic_location_id,
                    start_date=tp.start_date,
                )
                tp_ids.append(tp.id)
        assert (
            get_treatment_procedures_as_dicts_from_ids([]) == {}
        ), "Empty input, empty output expected"
        assert (
            get_treatment_procedures_as_dicts_from_ids(None) == {}
        ), "None input, empty output expected"
        assert (
            get_treatment_procedures_as_dicts_from_ids(set()) == {}
        ), "Empty input, empty output expected"
        assert set(get_treatment_procedures_as_dicts_from_ids(tp_ids).keys()) == set(
            tp_ids
        ), "Keys provided in input must match output if the TPS are found"
        inp1 = [tp_ids[0], tp_ids[1], sum(tp_ids)]
        res1 = get_treatment_procedures_as_dicts_from_ids(inp1).keys()
        assert set(res1) != set(inp1), "Input without matching TP is missing from O/P"
        assert set(res1) == {
            tp_ids[0],
            tp_ids[1],
        }, "Output only contains TPs that are found"

    def test_get_organization_invoicing_settings_dict_by_reimbursement_organization_settings_id(
        self,
    ):
        ois_repo = OrganizationInvoicingSettingsRepository(
            session=connection.db.session, is_in_uow=True
        )
        org = OrganizationFactory.create()
        ois1 = OrganizationInvoicingSettingsFactory.build(
            organization_id=org.id, uuid=uuid.uuid4()
        )
        ois2 = OrganizationInvoicingSettingsFactory.build(
            organization_id=OrganizationFactory.create().id, uuid=uuid.uuid4()
        )  # junk ois - org id guaranteed to not match the real one
        exp = ois_repo.create(instance=ois1)
        _ = ois_repo.create(instance=ois2)
        ros = ReimbursementOrganizationSettingsFactory.create(organization_id=org.id)
        res = get_org_invoicing_settings_as_dict_from_ros_id(ros_id=ros.id)
        assert res
        assert res["id"] == exp.id
        assert res["uuid"] == exp.uuid
        assert res["organization_id"] == exp.organization_id

    def test_get_organization_invoicing_settings_dict_by_reimbursement_organization_settings_id_not_found(
        self,
    ):
        ois_repo = OrganizationInvoicingSettingsRepository(
            session=connection.db.session, is_in_uow=True
        )
        org = OrganizationFactory.create()
        ois1 = OrganizationInvoicingSettingsFactory.build(
            organization_id=org.id, uuid=uuid.uuid4()
        )
        ois2 = OrganizationInvoicingSettingsFactory.build(
            organization_id=OrganizationFactory.create().id, uuid=uuid.uuid4()
        )  # junk ois - org id guaranteed to not match the real one
        _ = ois_repo.create(instance=ois1)
        _ = ois_repo.create(instance=ois2)
        # Create an ROS guaranteed to not belong to these orgs
        ros = ReimbursementOrganizationSettingsFactory.create(
            organization_id=ois1.organization_id + ois2.organization_id
        )
        res = get_org_invoicing_settings_as_dict_from_ros_id(ros_id=ros.id)
        assert not res

    def test_get_organisation_id_from_ros_id(self):
        exp = 101
        ros = ReimbursementOrganizationSettingsFactory.create(organization_id=exp)
        res = get_organisation_id_from_ros_id(ros.id)
        assert res == exp


@pytest.fixture
def fertility_clinic_recipient():
    def fn(exp_payments_recipient_id):
        to_ret = FertilityClinicFactory(
            id=A_CLINIC_ID, payments_recipient_id=exp_payments_recipient_id
        )
        return to_ret

    return fn


@pytest.fixture
def reimbursement_org():
    def fn(exp_payments_customer_id):
        OrganizationFactory.create(id=123456012)
        resource = ResourceFactory(id=5432123)
        org_id = A_REIMB_ORG_ID
        to_ret = ReimbursementOrganizationSettingsFactory(
            id=org_id,
            organization_id=1,
            benefit_faq_resource_id=resource.id,
            survey_url="fake_url",
            payments_customer_id=exp_payments_customer_id,
        )
        return to_ret

    return fn
