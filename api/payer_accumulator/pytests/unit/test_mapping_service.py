from datetime import datetime
from unittest import mock

import pytest

from cost_breakdown.constants import ClaimType
from cost_breakdown.pytests.factories import (
    CostBreakdownFactory,
    ReimbursementRequestToCostBreakdownFactory,
)
from direct_payment.treatment_procedure.models.treatment_procedure import (
    TreatmentProcedureType,
)
from payer_accumulator import errors
from payer_accumulator.accumulation_mapping_service import AccumulationMappingService
from payer_accumulator.common import TreatmentAccumulationStatus
from payer_accumulator.errors import InvalidAccumulationMappingData
from payer_accumulator.models.accumulation_treatment_mapping import (
    AccumulationTreatmentMapping,
)
from payer_accumulator.pytests.factories import (
    AccumulationTreatmentMappingFactory,
    PayerFactory,
)
from wallet.models.constants import (
    ReimbursementRequestAutoProcessing,
    ReimbursementRequestState,
    ReimbursementRequestType,
)
from wallet.pytests.factories import ReimbursementRequestFactory
from wallet.repository.health_plan import HEALTH_PLAN_YOY_FLAG, NEW_BEHAVIOR


@pytest.fixture
def mapping_service(db):
    return AccumulationMappingService(session=db.session)


@pytest.fixture
def valid_wallet(
    rr_accumulation_wallet, add_employer_health_plan, add_member_health_plan, uhc_payer
):
    ehp = add_employer_health_plan(rr_accumulation_wallet, uhc_payer)
    add_member_health_plan(
        ehp,
        rr_accumulation_wallet,
        plan_start_at=datetime(year=2024, month=1, day=1),
        plan_end_at=datetime(year=2024, month=12, day=31),
    )
    return rr_accumulation_wallet


@pytest.fixture
def wallet_with_two_payers(
    valid_wallet, add_employer_health_plan, add_member_health_plan, cigna_payer
):
    ehp_cigna = add_employer_health_plan(valid_wallet, cigna_payer)
    add_member_health_plan(
        ehp_cigna,
        valid_wallet,
        plan_start_at=datetime(year=2025, month=1, day=1),
        plan_end_at=datetime(year=2025, month=12, day=31),
    )
    return valid_wallet


@pytest.fixture
def valid_reimbursement_request(valid_wallet):
    categories = (
        valid_wallet.reimbursement_organization_settings.allowed_reimbursement_categories
    )
    category = categories[0].reimbursement_request_category
    return ReimbursementRequestFactory.create(
        wallet=valid_wallet,
        category=category,
        person_receiving_service_id=valid_wallet.user_id,
        reimbursement_type=ReimbursementRequestType.MANUAL,
        state=ReimbursementRequestState.APPROVED,
        procedure_type=TreatmentProcedureType.MEDICAL.value,
        service_start_date=datetime(year=2024, month=2, day=2),
    )


@pytest.fixture
def health_plan_feature_flag(ff_test_data):
    ff_test_data.update(
        ff_test_data.flag(HEALTH_PLAN_YOY_FLAG).variations(NEW_BEHAVIOR)
    )


class TestReimbursementMappings:
    def test_no_auto_adjust(self, mapping_service, valid_reimbursement_request, db):
        mapping = mapping_service.create_valid_reimbursement_request_mapping(
            valid_reimbursement_request
        )
        db.session.add(mapping)
        db.session.commit()

        with pytest.raises(errors.AccumulationAdjustmentNeeded):
            # A second accumulation should be blocked
            mapping_service.create_valid_reimbursement_request_mapping(
                valid_reimbursement_request
            )

    def test_no_double_accumulation(self, mapping_service, valid_reimbursement_request):
        # given
        c_b = CostBreakdownFactory.create()
        ReimbursementRequestToCostBreakdownFactory.create(
            claim_type=ClaimType.EMPLOYER,
            reimbursement_request_id=valid_reimbursement_request.id,
            treatment_procedure_uuid=c_b.treatment_procedure_uuid,
            cost_breakdown_id=c_b.id,
        )

        # when / then
        with pytest.raises(errors.InvalidAccumulationMappingData) as e:
            mapping_service.create_valid_reimbursement_request_mapping(
                valid_reimbursement_request
            )
        assert (
            str(e.value)
            == "This Reimbursement Request is associated with a Treatment Procedure's Cost Breakdown. "
            "It should only be accumulated at the Treatment Procedure level."
        )

    def test_reimbursement_request_no_payer(
        self, mapping_service, rr_accumulation_wallet, valid_reimbursement_request
    ):
        # given
        ehp = valid_reimbursement_request.wallet.reimbursement_organization_settings.employer_health_plan[
            0
        ]
        ehp.benefits_payer_id = -1

        # when / then
        with pytest.raises(errors.InvalidAccumulationMappingData) as e:
            mapping_service.create_valid_reimbursement_request_mapping(
                valid_reimbursement_request
            )
        assert (
            str(e.value)
            == "No associated Payer found. Check Member and Employer health plan configurations."
        )
        assert e.value.expected_payer_id == -1

    def test_reimbursement_request_invalid_payer(
        self,
        mapping_service,
        rr_accumulation_wallet,
        add_employer_health_plan,
        add_member_health_plan,
    ):
        # given
        non_accumulations_payer = PayerFactory.create(
            payer_name="Blue Shield, Blue Cross", payer_code="blue_code"
        )
        ehp = add_employer_health_plan(rr_accumulation_wallet, non_accumulations_payer)
        add_member_health_plan(ehp, rr_accumulation_wallet)
        categories = (
            rr_accumulation_wallet.reimbursement_organization_settings.allowed_reimbursement_categories
        )
        category = categories[0].reimbursement_request_category
        reimbursement_request = ReimbursementRequestFactory.create(
            wallet=rr_accumulation_wallet,
            category=category,
            person_receiving_service_id=rr_accumulation_wallet.user_id,
            reimbursement_type=ReimbursementRequestType.MANUAL,
            state=ReimbursementRequestState.APPROVED,
            procedure_type=TreatmentProcedureType.MEDICAL.value,
        )

        # when / then
        with pytest.raises(errors.InvalidAccumulationMappingData) as e:
            mapping_service.create_valid_reimbursement_request_mapping(
                reimbursement_request
            )
        assert (
            str(e.value)
            == "The Associated Payer is not accumulation-report enabled. Check Member and Employer health plan configurations."
        )

    @pytest.mark.parametrize(
        "field,value,expected_message",
        [
            (
                "person_receiving_service_id",
                None,
                "Missing the Person Receiving Service ID for payer accumulation. "
                "This field is required for determining the associated member health plan.",
            ),
            (
                "reimbursement_type",
                ReimbursementRequestType.DIRECT_BILLING,
                "Invalid ReimbursementRequestType for payer accumulation. Must be MANUAL.",
            ),
            (
                "state",
                ReimbursementRequestState.NEW,
                "Invalid ReimbursementRequestState for payer accumulation. Must be one of APPROVED or DENIED.",
            ),
        ],
    )
    def test_invalid_fields(
        self,
        mapping_service,
        valid_reimbursement_request,
        field,
        value,
        expected_message,
    ):
        # given
        valid_reimbursement_request.__setattr__(field, value)

        # when / then
        with pytest.raises(errors.InvalidAccumulationMappingData) as e:
            mapping_service.create_valid_reimbursement_request_mapping(
                valid_reimbursement_request
            )
        assert str(e.value) == expected_message

    @pytest.mark.parametrize(
        "rx_integrated,procedure_type,expected_payer",
        [
            (False, TreatmentProcedureType.MEDICAL.value, "uhc_payer"),
            (False, TreatmentProcedureType.PHARMACY.value, "esi_payer"),
            (True, TreatmentProcedureType.MEDICAL.value, "uhc_payer"),
            (True, TreatmentProcedureType.PHARMACY.value, "uhc_payer"),
        ],
    )
    def test_create_mapping(
        self,
        mapping_service,
        valid_reimbursement_request,
        rx_integrated,
        procedure_type,
        expected_payer,
        request,
        uhc_payer,
        esi_payer,
        db,
    ):
        payer = request.getfixturevalue(expected_payer)
        ehp = valid_reimbursement_request.wallet.reimbursement_organization_settings.employer_health_plan[
            0
        ]
        ehp.rx_integrated = rx_integrated
        valid_reimbursement_request.procedure_type = procedure_type

        mapping = mapping_service.create_valid_reimbursement_request_mapping(
            valid_reimbursement_request
        )
        assert isinstance(mapping, AccumulationTreatmentMapping)
        assert mapping.reimbursement_request_id == valid_reimbursement_request.id
        assert mapping.treatment_accumulation_status == TreatmentAccumulationStatus.PAID
        assert mapping.payer_id == payer.id
        assert mapping.deductible is None
        assert mapping.oop_applied is None
        assert mapping.treatment_procedure_uuid is None
        assert not mapping.is_refund

    @pytest.mark.parametrize(
        "is_deductible_accumulation, amount, total_employer_responsibility, total_member_responsibility, state",
        [
            (False, 100, 100, 0, ReimbursementRequestState.DENIED),
            (False, 100, 100, 0, ReimbursementRequestState.PENDING),
            (True, 100, 25, 75, ReimbursementRequestState.APPROVED),
            (True, 100, 0, 100, ReimbursementRequestState.APPROVED),
        ],
        ids=[
            "No DA Accumulate",
            "No DA Do Not Accumulate",
            "DA Accumulate",
            "DA Do Not Accumulate",
        ],
    )
    def test_reimbursement_post_approval(
        self,
        mapping_service,
        rr_accumulation_wallet,
        is_deductible_accumulation,
        amount,
        total_employer_responsibility,
        total_member_responsibility,
        state,
    ):
        org_setting = rr_accumulation_wallet.reimbursement_organization_settings
        org_setting.deductible_accumulation_enabled = is_deductible_accumulation
        category = org_setting.allowed_reimbursement_categories[
            0
        ].reimbursement_request_category
        rr = ReimbursementRequestFactory.create(
            wallet=rr_accumulation_wallet,
            person_receiving_service_id=rr_accumulation_wallet.member.id,
            category=category,
            state=ReimbursementRequestState.NEW,
            amount=amount,
        )
        cb = CostBreakdownFactory.create(
            reimbursement_request_id=rr.id,
            total_employer_responsibility=total_employer_responsibility,
            total_member_responsibility=total_member_responsibility,
        )
        conditional = (
            mapping_service.should_accumulate_reimbursement_request_post_approval(
                reimbursement_request=rr, cost_breakdown=cb
            )
        )

        rr.state = state
        with mock.patch.object(
            mapping_service, "create_valid_reimbursement_request_mapping"
        ) as create_mapping:
            mapping_service.accumulate_reimbursement_request_post_approval(
                reimbursement_request=rr, cost_breakdown=cb
            )
        # these two functions should always agree on when a mapping is created
        assert conditional == (create_mapping.call_count == 1)

    @pytest.mark.parametrize(
        argnames="is_mapped, expected",
        argvalues=[
            (True, True),
            (False, False),
        ],
    )
    def test_update_status_to_accepted(self, mapping_service, is_mapped, expected):
        unique_id = "202410151234567890000001"
        if is_mapped:
            mapping = AccumulationTreatmentMappingFactory.create(
                payer_id=1,
                treatment_procedure_uuid="00000000-0000-0000-0000-000000000001",
                accumulation_unique_id=unique_id,
                accumulation_transaction_id="1",
                treatment_accumulation_status=TreatmentAccumulationStatus.SUBMITTED,
            )
        assert (
            mapping_service.update_status_to_accepted(unique_id, "A", "000") == expected
        )

        if is_mapped:
            updated_mapping = AccumulationTreatmentMapping.query.get(mapping.id)
            assert (
                updated_mapping.treatment_accumulation_status
                == TreatmentAccumulationStatus.ACCEPTED
            )
            assert updated_mapping.response_code == "000"

    @pytest.mark.parametrize(
        argnames="is_mapped, expected",
        argvalues=[
            (True, True),
            (False, False),
        ],
    )
    def test_update_status_to_rejected(self, mapping_service, is_mapped, expected):
        unique_id = "202410151234567890000001"
        if is_mapped:
            mapping = AccumulationTreatmentMappingFactory.create(
                payer_id=1,
                treatment_procedure_uuid="00000000-0000-0000-0000-000000000001",
                accumulation_unique_id=unique_id,
                accumulation_transaction_id="1",
                treatment_accumulation_status=TreatmentAccumulationStatus.SUBMITTED,
            )
        assert (
            mapping_service.update_status_to_rejected(unique_id, "R", "999") == expected
        )

        if is_mapped:
            updated_mapping = AccumulationTreatmentMapping.query.get(mapping.id)
            assert (
                updated_mapping.treatment_accumulation_status
                == TreatmentAccumulationStatus.REJECTED
            )
            assert updated_mapping.response_code == "999"

    def test_auto_processed_rx_adjust_allowed(
        self, mapping_service, valid_reimbursement_request, db
    ):
        existing_mapping = mapping_service.create_valid_reimbursement_request_mapping(
            valid_reimbursement_request
        )
        existing_mapping.treatment_accumulation_status = (
            TreatmentAccumulationStatus.REFUNDED
        )
        valid_reimbursement_request.auto_processed = (
            ReimbursementRequestAutoProcessing.RX
        )
        db.session.add(existing_mapping)
        db.session.commit()

        new_mapping = mapping_service.create_valid_reimbursement_request_mapping(
            valid_reimbursement_request
        )
        assert (
            new_mapping.reimbursement_request_id
            == existing_mapping.reimbursement_request_id
        )
        assert (
            new_mapping.treatment_accumulation_status
            == TreatmentAccumulationStatus.PAID
        )
        assert (
            existing_mapping.treatment_accumulation_status
            == TreatmentAccumulationStatus.REFUNDED
        )

    def test_auto_processed_rx_adjust_blocked(
        self, mapping_service, valid_reimbursement_request, db
    ):
        mapping = mapping_service.create_valid_reimbursement_request_mapping(
            valid_reimbursement_request
        )
        valid_reimbursement_request.auto_processed = (
            ReimbursementRequestAutoProcessing.RX
        )
        db.session.add(mapping)
        db.session.commit()

        with pytest.raises(errors.AccumulationAdjustmentNeeded):
            mapping_service.create_valid_reimbursement_request_mapping(
                valid_reimbursement_request
            )


class TestMappingServiceGetPayer:
    @pytest.mark.parametrize(
        "effective_date, expected_payer",
        [
            (datetime(year=2024, month=3, day=1), "uhc_payer"),
            (datetime(year=2025, month=3, day=1), "cigna_payer"),
        ],
    )
    def test_get_valid_payer(
        self,
        mapping_service,
        wallet_with_two_payers,
        effective_date,
        expected_payer,
        request,
        health_plan_feature_flag,
    ):
        expected_payer = request.getfixturevalue(expected_payer)
        payer = mapping_service.get_valid_payer(
            reimbursement_wallet_id=wallet_with_two_payers.id,
            user_id=wallet_with_two_payers.user_id,
            procedure_type=TreatmentProcedureType.MEDICAL,
            effective_date=effective_date,
        )
        assert payer == expected_payer

    def test_no_valid_payer(
        self, mapping_service, wallet_with_two_payers, health_plan_feature_flag
    ):
        with pytest.raises(InvalidAccumulationMappingData) as e:
            mapping_service.get_valid_payer(
                reimbursement_wallet_id=wallet_with_two_payers.id,
                user_id=wallet_with_two_payers.user_id,
                procedure_type=TreatmentProcedureType.MEDICAL,
                effective_date=datetime(year=2000, month=1, day=1),
            )
        assert (
            e.value.args[0]
            == "No Employer Health plan found for this user and this wallet on the given effective date."
        )
