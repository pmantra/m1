import dataclasses
from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch

import factory
import pytest
from maven import feature_flags

from cost_breakdown.models.cost_breakdown import (
    CalcConfigAudit,
    DeductibleAccumulationYTDInfo,
    ExtraAppliedAmount,
    HDHPAccumulationYTDInfo,
)
from cost_breakdown.models.rte import EligibilityInfo
from cost_breakdown.pytests.factories import CostBreakdownFactory
from direct_payment.treatment_procedure.models.treatment_procedure import (
    TreatmentProcedureStatus,
    TreatmentProcedureType,
)
from direct_payment.treatment_procedure.pytests.factories import (
    TreatmentProcedureFactory,
)
from payer_accumulator.common import TreatmentAccumulationStatus
from payer_accumulator.pytests.factories import AccumulationTreatmentMappingFactory
from pytests.factories import EnterpriseUserFactory
from wallet.models.constants import (
    FamilyPlanType,
    ReimbursementRequestState,
    WalletUserStatus,
    WalletUserType,
)
from wallet.pytests.factories import (
    MemberHealthPlanFactory,
    ReimbursementRequestFactory,
    ReimbursementWalletUsersFactory,
)
from wallet.repository.health_plan import (
    HEALTH_PLAN_YOY_FLAG,
    LOGGING_BEHAVIOR,
    NEW_BEHAVIOR,
)


@pytest.fixture(scope="function")
def eligibility_info():
    return EligibilityInfo(
        individual_deductible=20000,
        individual_deductible_remaining=10000,
        individual_oop=40000,
        individual_oop_remaining=20000,
    )


@pytest.fixture(scope="function")
def eligibility_info_family_plan():
    return EligibilityInfo(
        individual_deductible=20000,
        individual_deductible_remaining=10000,
        individual_oop=40000,
        individual_oop_remaining=20000,
        family_deductible=40000,
        family_deductible_remaining=20000,
        family_oop=80000,
        family_oop_remaining=40000,
    )


@pytest.fixture()
def enable_health_plan_feature(ff_test_data):
    ff_test_data.update(
        ff_test_data.flag(HEALTH_PLAN_YOY_FLAG).variations(NEW_BEHAVIOR)
    )


@pytest.fixture()
def enable_health_plan_logging_feature(ff_test_data):
    ff_test_data.update(
        ff_test_data.flag(HEALTH_PLAN_YOY_FLAG).variations(LOGGING_BEHAVIOR)
    )


@pytest.fixture(scope="function")
def member_health_plan(employer_health_plan, wallet, enterprise_user):
    plan = MemberHealthPlanFactory.create(
        employer_health_plan=employer_health_plan,
        is_subscriber=True,
        member_id=enterprise_user.id,
        reimbursement_wallet=wallet,
        plan_start_at=datetime(year=2024, month=1, day=1),
        plan_end_at=datetime(year=2025, month=1, day=1),
    )
    return plan


@pytest.fixture(scope="module")
def service_start_date():
    return datetime(year=2024, month=2, day=1)


class TestDeductibleAccumulationSequentialPayments:
    def test_treatment_scheduled_embedded(
        self,
        cost_breakdown_proc,
        member_health_plan,
        service_start_date,
    ):
        member_health_plan.employer_health_plan.ind_deductible_limit = 300_00
        member_health_plan.employer_health_plan.fam_deductible_limit = 600_00
        member_health_plan.employer_health_plan.ind_oop_max_limit = 3000_00
        member_health_plan.employer_health_plan.fam_oop_max_limit = 6000_00
        member_health_plan.employer_health_plan.is_deductible_embedded = True
        member_health_plan.employer_health_plan.is_oop_embedded = True
        member_health_plan.plan_type = FamilyPlanType.FAMILY
        cost_breakdown = CostBreakdownFactory.create(
            id=5,
            total_member_responsibility=4000_00,
            deductible=300_00,
            oop_applied=3000_00,
        )
        TreatmentProcedureFactory.create(
            cost_breakdown_id=cost_breakdown.id,
            member_id=member_health_plan.member_id,
            reimbursement_wallet_id=member_health_plan.reimbursement_wallet_id,
            status=TreatmentProcedureStatus.COMPLETED,
            created_at=datetime(2023, 1, 1),
            completed_date=datetime(2024, 1, 1),
            start_date=service_start_date,
        )
        current_treatment_procedure = TreatmentProcedureFactory.create(
            member_id=member_health_plan.member_id,
            reimbursement_wallet_id=member_health_plan.reimbursement_wallet_id,
            status=TreatmentProcedureStatus.COMPLETED,
            created_at=datetime(2023, 2, 1),
            completed_date=datetime(2024, 2, 1),
            start_date=service_start_date,
        )
        expected = cost_breakdown_proc.get_sequential_member_responsibility_for_deductible_accumulation(
            member_health_plan=member_health_plan,
            procedure_type=current_treatment_procedure.procedure_type,
            before_this_date=current_treatment_procedure.completed_date,
        )
        assert expected == DeductibleAccumulationYTDInfo(
            individual_deductible_applied=300_00,
            individual_oop_applied=3000_00,
            family_deductible_applied=300_00,
            family_oop_applied=3000_00,
        )
        assert cost_breakdown_proc.calc_config.sequential_cost_breakdown_ids == [5]

    def test_treatment_completed_picked_by_data_sourcer(
        self,
        cost_breakdown_proc,
        member_health_plan,
        service_start_date,
    ):
        cost_breakdown = CostBreakdownFactory.create(
            total_member_responsibility=10000, deductible=10000, oop_applied=10000
        )
        completed_treatment_procedure = TreatmentProcedureFactory.create(
            cost_breakdown_id=cost_breakdown.id,
            member_id=member_health_plan.member_id,
            reimbursement_wallet_id=member_health_plan.reimbursement_wallet_id,
            status=TreatmentProcedureStatus.COMPLETED,
            created_at=datetime(2023, 1, 1),
            completed_date=datetime(2024, 1, 1),
            start_date=service_start_date,
        )
        AccumulationTreatmentMappingFactory.create(
            treatment_procedure_uuid=completed_treatment_procedure.uuid,
            treatment_accumulation_status=TreatmentAccumulationStatus.PAID,
        )
        current_treatment_procedure = TreatmentProcedureFactory.create(
            member_id=member_health_plan.member_id,
            reimbursement_wallet_id=member_health_plan.reimbursement_wallet_id,
            status=TreatmentProcedureStatus.COMPLETED,
            created_at=datetime(2023, 2, 1),
            completed_date=datetime(2024, 2, 1),
            start_date=service_start_date,
        )
        expected = cost_breakdown_proc.get_sequential_member_responsibility_for_deductible_accumulation(
            member_health_plan=member_health_plan,
            procedure_type=current_treatment_procedure.procedure_type,
            before_this_date=current_treatment_procedure.completed_date,
        )

        assert expected.individual_deductible_applied == 10_000
        assert expected.individual_oop_applied == 10_000
        assert expected.family_deductible_applied == 10_000
        assert expected.family_oop_applied == 10_000

    def test_multiple_family_treatments(
        self,
        cost_breakdown_proc,
        employer_health_plan,
        wallet,
        service_start_date,
        member_health_plan,
    ):
        subscriber_wallet = member_health_plan.reimbursement_wallet
        dependent = EnterpriseUserFactory.create()
        ReimbursementWalletUsersFactory.create(
            user_id=dependent.id,
            reimbursement_wallet_id=subscriber_wallet.id,
            status=WalletUserStatus.ACTIVE,
            type=WalletUserType.DEPENDENT,
        )
        MemberHealthPlanFactory.create(
            reimbursement_wallet=subscriber_wallet,
            reimbursement_wallet_id=subscriber_wallet.id,
            employer_health_plan=employer_health_plan,
            plan_type=FamilyPlanType.FAMILY,
            is_subscriber=False,
            member_id=dependent.id,
            plan_start_at=datetime(year=2024, month=1, day=1),
            plan_end_at=datetime(year=2025, month=1, day=1),
        )

        cost_breakdown = CostBreakdownFactory.create(
            id=5,
            total_member_responsibility=100_00,
            deductible=100_00,
            oop_applied=100_00,
        )
        completed_treatment_procedure = TreatmentProcedureFactory.create(
            cost_breakdown_id=cost_breakdown.id,
            member_id=member_health_plan.member_id,
            reimbursement_wallet_id=subscriber_wallet.id,
            status=TreatmentProcedureStatus.COMPLETED,
            created_at=datetime(2023, 1, 1),
            start_date=service_start_date,
        )
        AccumulationTreatmentMappingFactory.create(
            treatment_procedure_uuid=completed_treatment_procedure.uuid,
            treatment_accumulation_status=TreatmentAccumulationStatus.PAID,
        )
        cost_breakdown_3 = CostBreakdownFactory.create(
            id=8,
            total_member_responsibility=100_00,
            deductible=100_00,
            oop_applied=100_00,
        )
        # diff family member tp picked up by data sourcer
        same_wallet_diff_member_completed_treatment_procedure = (
            TreatmentProcedureFactory.create(
                cost_breakdown_id=cost_breakdown_3.id,
                member_id=dependent.id,
                reimbursement_wallet_id=subscriber_wallet.id,
                status=TreatmentProcedureStatus.COMPLETED,
                created_at=datetime(2023, 1, 1),
                start_date=service_start_date,
            )
        )
        AccumulationTreatmentMappingFactory.create(
            treatment_procedure_uuid=same_wallet_diff_member_completed_treatment_procedure.uuid,
            treatment_accumulation_status=TreatmentAccumulationStatus.PAID,
        )

        cost_breakdown_1 = CostBreakdownFactory.create(
            id=6,
            total_member_responsibility=100_00,
            deductible=100_00,
            oop_applied=100_00,
        )
        # diff family member completed tp not picked up by data sourcer
        TreatmentProcedureFactory.create(
            cost_breakdown_id=cost_breakdown_1.id,
            member_id=dependent.id,
            reimbursement_wallet_id=subscriber_wallet.id,
            status=TreatmentProcedureStatus.COMPLETED,
            created_at=datetime(2023, 1, 1),
        )
        cost_breakdown_2 = CostBreakdownFactory.create(
            id=7,
            total_member_responsibility=100_00,
            deductible=100_00,
            oop_applied=100_00,
        )
        # diff family member scheduled tp not picked up by data sourcer
        TreatmentProcedureFactory.create(
            cost_breakdown_id=cost_breakdown_2.id,
            member_id=dependent.id,
            reimbursement_wallet_id=subscriber_wallet.id,
            status=TreatmentProcedureStatus.SCHEDULED,
            created_at=datetime(2023, 1, 1),
        )

        current_treatment_procedure = TreatmentProcedureFactory.create(
            member_id=member_health_plan.member_id,
            reimbursement_wallet_id=subscriber_wallet.id,
            status=TreatmentProcedureStatus.SCHEDULED,
            created_at=datetime(2023, 2, 1),
        )
        expected = cost_breakdown_proc.get_sequential_member_responsibility_for_deductible_accumulation(
            member_health_plan=member_health_plan,
            procedure_type=current_treatment_procedure.procedure_type,
            before_this_date=current_treatment_procedure.created_at,
            should_include_pending=True,
        )

        assert expected == DeductibleAccumulationYTDInfo(
            individual_deductible_applied=100_00,
            individual_oop_applied=100_00,
            family_deductible_applied=400_00,
            family_oop_applied=400_00,
        )
        assert [5, 6, 7, 8] == sorted(
            cost_breakdown_proc.calc_config.sequential_cost_breakdown_ids
        )

    def test_treatment_completed_but_not_picked_by_data_sourcer(
        self,
        cost_breakdown_proc,
        member_health_plan,
        service_start_date,
    ):
        cost_breakdown = CostBreakdownFactory.create(
            total_member_responsibility=10000, deductible=10000, oop_applied=10000
        )
        TreatmentProcedureFactory.create(
            cost_breakdown_id=cost_breakdown.id,
            member_id=member_health_plan.member_id,
            reimbursement_wallet_id=member_health_plan.reimbursement_wallet_id,
            status=TreatmentProcedureStatus.COMPLETED,
            created_at=datetime(2023, 1, 1),
            start_date=service_start_date,
        )
        current_treatment_procedure = TreatmentProcedureFactory.create(
            member_id=member_health_plan.member_id,
            reimbursement_wallet_id=member_health_plan.reimbursement_wallet_id,
            status=TreatmentProcedureStatus.SCHEDULED,
            created_at=datetime(2023, 2, 1),
            start_date=service_start_date,
        )
        expected = cost_breakdown_proc.get_sequential_member_responsibility_for_deductible_accumulation(
            member_health_plan=member_health_plan,
            procedure_type=current_treatment_procedure.procedure_type,
            before_this_date=current_treatment_procedure.created_at,
            should_include_pending=True,
        )

        assert expected.individual_deductible_applied == 10_000
        assert expected.individual_oop_applied == 10_000
        assert expected.family_deductible_applied == 10_000
        assert expected.family_oop_applied == 10_000

    def test_treatment_scheduled_and_completed(
        self,
        cost_breakdown_proc,
        member_health_plan,
        service_start_date,
    ):
        cost_breakdown = CostBreakdownFactory.create(
            total_member_responsibility=10000, deductible=10000, oop_applied=10000
        )
        TreatmentProcedureFactory.create(
            cost_breakdown_id=cost_breakdown.id,
            member_id=member_health_plan.member_id,
            reimbursement_wallet_id=member_health_plan.reimbursement_wallet_id,
            status=TreatmentProcedureStatus.SCHEDULED,
            created_at=datetime(2023, 1, 1),
            start_date=service_start_date,
        )
        completed_treatment_procedure = TreatmentProcedureFactory.create(
            cost_breakdown_id=cost_breakdown.id,
            member_id=member_health_plan.member_id,
            reimbursement_wallet_id=member_health_plan.reimbursement_wallet_id,
            status=TreatmentProcedureStatus.COMPLETED,
            created_at=datetime(2023, 1, 1),
            start_date=service_start_date,
        )
        AccumulationTreatmentMappingFactory.create(
            treatment_procedure_uuid=completed_treatment_procedure.uuid,
            treatment_accumulation_status=TreatmentAccumulationStatus.PAID,
        )
        current_treatment_procedure = TreatmentProcedureFactory.create(
            member_id=member_health_plan.member_id,
            reimbursement_wallet_id=member_health_plan.reimbursement_wallet_id,
            status=TreatmentProcedureStatus.SCHEDULED,
            created_at=datetime(2023, 2, 1),
        )
        expected = cost_breakdown_proc.get_sequential_member_responsibility_for_deductible_accumulation(
            member_health_plan=member_health_plan,
            procedure_type=current_treatment_procedure.procedure_type,
            before_this_date=current_treatment_procedure.created_at,
            should_include_pending=True,
        )

        assert expected.individual_deductible_applied == 20_000
        assert expected.individual_oop_applied == 20_000
        assert expected.family_deductible_applied == 20_000
        assert expected.family_oop_applied == 20_000

    def test_eligibility_info_exceed_limit(
        self,
        cost_breakdown_proc,
        member_health_plan,
        service_start_date,
    ):
        cost_breakdown = CostBreakdownFactory.create(
            total_member_responsibility=30000, deductible=30000, oop_applied=30000
        )
        TreatmentProcedureFactory.create(
            cost_breakdown_id=cost_breakdown.id,
            member_id=member_health_plan.member_id,
            reimbursement_wallet_id=member_health_plan.reimbursement_wallet_id,
            status=TreatmentProcedureStatus.COMPLETED,
            created_at=datetime(2023, 1, 1),
            completed_date=datetime(2024, 1, 1),
            start_date=service_start_date,
        )
        current_treatment_procedure = TreatmentProcedureFactory.create(
            member_id=member_health_plan.member_id,
            reimbursement_wallet_id=member_health_plan.reimbursement_wallet_id,
            status=TreatmentProcedureStatus.COMPLETED,
            created_at=datetime(2023, 2, 1),
            completed_date=datetime(2024, 2, 1),
            start_date=service_start_date,
        )
        expected = cost_breakdown_proc.get_sequential_member_responsibility_for_deductible_accumulation(
            member_health_plan=member_health_plan,
            procedure_type=current_treatment_procedure.procedure_type,
            before_this_date=current_treatment_procedure.completed_date,
        )

        assert expected.individual_deductible_applied == 30_000
        assert expected.individual_oop_applied == 30_000
        assert expected.family_deductible_applied == 30_000
        assert expected.family_oop_applied == 30_000

    def test_eligibility_info_rx_medical_separate(
        self,
        cost_breakdown_proc,
        member_health_plan_rx_not_included,
        service_start_date,
    ):
        cost_breakdown = CostBreakdownFactory.create(
            total_member_responsibility=10000, deductible=10000, oop_applied=10000
        )
        member_health_plan_rx_not_included.plan_start_at = datetime(
            year=2024, month=1, day=1
        )
        member_health_plan_rx_not_included.plan_end_at = datetime(
            year=2025, month=1, day=1
        )
        TreatmentProcedureFactory.create(
            cost_breakdown_id=cost_breakdown.id,
            member_id=member_health_plan_rx_not_included.member_id,
            reimbursement_wallet_id=member_health_plan_rx_not_included.reimbursement_wallet_id,
            status=TreatmentProcedureStatus.SCHEDULED,
            procedure_type=TreatmentProcedureType.PHARMACY,
            created_at=datetime(2023, 1, 1),
            start_date=service_start_date,
        )
        current_treatment_procedure = TreatmentProcedureFactory.create(
            member_id=member_health_plan_rx_not_included.member_id,
            reimbursement_wallet_id=member_health_plan_rx_not_included.reimbursement_wallet_id,
            status=TreatmentProcedureStatus.SCHEDULED,
            procedure_type=TreatmentProcedureType.PHARMACY,
            created_at=datetime(2023, 2, 1),
            start_date=service_start_date,
        )
        expected = cost_breakdown_proc.get_sequential_member_responsibility_for_deductible_accumulation(
            member_health_plan=member_health_plan_rx_not_included,
            procedure_type=current_treatment_procedure.procedure_type,
            before_this_date=current_treatment_procedure.created_at,
            should_include_pending=True,
        )

        assert expected == DeductibleAccumulationYTDInfo(
            individual_deductible_applied=10_000,
            individual_oop_applied=10_000,
            family_deductible_applied=10_000,
            family_oop_applied=10_000,
        )

    def test_rx_medical_separate_type_mismatch(
        self,
        cost_breakdown_proc,
        member_health_plan_rx_not_included,
        eligibility_info,
        service_start_date,
    ):
        member_health_plan_rx_not_included.plan_start_at = datetime(
            year=2024, month=1, day=1
        )
        member_health_plan_rx_not_included.plan_end_at = datetime(
            year=2025, month=1, day=1
        )

        cost_breakdown = CostBreakdownFactory.create(
            total_member_responsibility=10000, deductible=10000, oop_applied=10000
        )
        TreatmentProcedureFactory.create(
            cost_breakdown_id=cost_breakdown.id,
            member_id=member_health_plan_rx_not_included.member_id,
            status=TreatmentProcedureStatus.SCHEDULED,
            procedure_type=TreatmentProcedureType.PHARMACY,
            created_at=datetime(2023, 1, 1),
            start_date=service_start_date,
        )
        current_treatment_procedure = TreatmentProcedureFactory.create(
            member_id=member_health_plan_rx_not_included.member_id,
            status=TreatmentProcedureStatus.SCHEDULED,
            procedure_type=TreatmentProcedureType.MEDICAL,
            created_at=datetime(2023, 2, 1),
        )
        expected = cost_breakdown_proc.get_sequential_member_responsibility_for_deductible_accumulation(
            member_health_plan=member_health_plan_rx_not_included,
            procedure_type=current_treatment_procedure.procedure_type,
            before_this_date=current_treatment_procedure.created_at,
        )

        assert expected.individual_deductible_applied == 0
        assert expected.individual_oop_applied == 0
        assert expected.family_deductible_applied == 0
        assert expected.family_oop_applied == 0

    def test_embedded_plan(
        self,
        cost_breakdown_proc,
        member_health_plan_embedded_plan,
        eligibility_info_family_plan,
        service_start_date,
    ):
        member_health_plan_embedded_plan.plan_start_at = datetime(
            year=2024, month=1, day=1
        )
        member_health_plan_embedded_plan.plan_end_at = datetime(
            year=2025, month=1, day=1
        )

        cost_breakdown = CostBreakdownFactory.create(
            total_member_responsibility=10000, deductible=10000, oop_applied=10000
        )
        TreatmentProcedureFactory.create(
            cost_breakdown_id=cost_breakdown.id,
            member_id=member_health_plan_embedded_plan.member_id,
            reimbursement_wallet_id=member_health_plan_embedded_plan.reimbursement_wallet_id,
            status=TreatmentProcedureStatus.SCHEDULED,
            created_at=datetime(2023, 1, 1),
            start_date=service_start_date,
        )
        current_treatment_procedure = TreatmentProcedureFactory.create(
            member_id=member_health_plan_embedded_plan.member_id,
            reimbursement_wallet_id=member_health_plan_embedded_plan.reimbursement_wallet_id,
            status=TreatmentProcedureStatus.SCHEDULED,
            created_at=datetime(2023, 2, 1),
            start_date=service_start_date,
        )
        expected = cost_breakdown_proc.get_sequential_member_responsibility_for_deductible_accumulation(
            member_health_plan=member_health_plan_embedded_plan,
            procedure_type=current_treatment_procedure.procedure_type,
            before_this_date=current_treatment_procedure.created_at,
            should_include_pending=True,
        )

        assert expected.individual_deductible_applied == 10_000
        assert expected.individual_oop_applied == 10_000
        assert expected.family_deductible_applied == 10_000
        assert expected.family_oop_applied == 10_000

    def test_sequential_treatments_by_date(
        self,
        cost_breakdown_proc,
        member_health_plan,
        service_start_date,
    ):
        cost_breakdown = CostBreakdownFactory.create(
            total_member_responsibility=120_00, deductible=123_00, oop_applied=120_00
        )
        service_start_date = datetime.utcnow() - timedelta(days=5)

        # should show as it is, before the service start date
        TreatmentProcedureFactory.create(
            cost_breakdown_id=cost_breakdown.id,
            member_id=member_health_plan.member_id,
            reimbursement_wallet_id=member_health_plan.reimbursement_wallet_id,
            status=TreatmentProcedureStatus.SCHEDULED,
            procedure_type=TreatmentProcedureType.MEDICAL,
            created_at=service_start_date - timedelta(days=1),
            start_date=service_start_date,
        )
        # should not show, as it is after the service start date
        non_sequential_cost_breakdown = CostBreakdownFactory.create(
            total_member_responsibility=200_00, deductible=200_00, oop_applied=200_00
        )
        TreatmentProcedureFactory.create(
            cost_breakdown_id=non_sequential_cost_breakdown.id,
            member_id=member_health_plan.member_id,
            reimbursement_wallet_id=member_health_plan.reimbursement_wallet_id,
            status=TreatmentProcedureStatus.SCHEDULED,
            procedure_type=TreatmentProcedureType.MEDICAL,
            created_at=service_start_date + timedelta(days=1),
            start_date=service_start_date,
        )
        expected = cost_breakdown_proc.get_sequential_member_responsibility_for_deductible_accumulation(
            member_health_plan=member_health_plan,
            procedure_type=TreatmentProcedureType.MEDICAL,
            before_this_date=service_start_date,
            should_include_pending=True,
        )
        assert expected == DeductibleAccumulationYTDInfo(
            individual_deductible_applied=123_00,
            individual_oop_applied=120_00,
            family_deductible_applied=123_00,
            family_oop_applied=120_00,
        )

    def test_no_sequential_treatments(
        self,
        cost_breakdown_proc,
        member_health_plan,
        service_start_date,
    ):
        current_treatment_procedure = TreatmentProcedureFactory.create(
            member_id=member_health_plan.member_id,
            reimbursement_wallet_id=member_health_plan.reimbursement_wallet_id,
            status=TreatmentProcedureStatus.SCHEDULED,
            created_at=datetime(2023, 2, 1),
            start_date=service_start_date,
        )
        expected = cost_breakdown_proc.get_sequential_member_responsibility_for_deductible_accumulation(
            member_health_plan=member_health_plan,
            procedure_type=current_treatment_procedure.procedure_type,
            before_this_date=current_treatment_procedure.created_at,
        )
        assert expected == DeductibleAccumulationYTDInfo(
            individual_deductible_applied=0,
            individual_oop_applied=0,
            family_deductible_applied=0,
            family_oop_applied=0,
        )

    def test_sequential_treatments_and_reimbursement_requests(
        self,
        cost_breakdown_proc,
        member_health_plan,
        wallet_category,
        service_start_date,
        enable_health_plan_logging_feature,
    ):
        now = datetime.utcnow()
        (
            past_procedure_cost_breakdown,
            future_procedure_cost_breakdown,
        ) = CostBreakdownFactory.create_batch(
            size=2,
            deductible=120_00,
            oop_applied=150_00,
        )
        TreatmentProcedureFactory.create_batch(
            size=2,
            cost_breakdown_id=factory.Iterator(
                [past_procedure_cost_breakdown.id, future_procedure_cost_breakdown.id]
            ),
            member_id=member_health_plan.member_id,
            reimbursement_wallet_id=member_health_plan.reimbursement_wallet_id,
            status=TreatmentProcedureStatus.SCHEDULED,
            procedure_type=TreatmentProcedureType.MEDICAL,
            start_date=service_start_date,
            created_at=factory.Iterator(
                [
                    now - timedelta(days=1),
                    now + timedelta(days=1),
                ]
            ),
        )
        (
            past_reimbursement,
            current_reimbursement,
            future_reimbursement,
        ) = ReimbursementRequestFactory.create_batch(
            size=3,
            wallet=member_health_plan.reimbursement_wallet,
            person_receiving_service_id=member_health_plan.member_id,
            person_receiving_service_member_status="MEMBER",
            category=wallet_category,
            state=ReimbursementRequestState.NEW,
            service_start_date=service_start_date,
            procedure_type="MEDICAL",
        )
        (
            past_reimbursement_cost_breakdown,
            future_reimbursement_cost_breakdown,
        ) = CostBreakdownFactory.create_batch(
            size=2,
            wallet_id=member_health_plan.reimbursement_wallet_id,
            reimbursement_request_id=factory.Iterator(
                [past_reimbursement.id, future_reimbursement.id]
            ),
            deductible=102_00,
            oop_applied=103_00,
            created_at=factory.Iterator(
                [
                    now - timedelta(days=1),
                    now + timedelta(days=1),
                ]
            ),
        )
        # when
        responsibility = cost_breakdown_proc.get_sequential_member_responsibility_for_deductible_accumulation(
            member_health_plan=member_health_plan,
            procedure_type=TreatmentProcedureType.MEDICAL,
            before_this_date=now,
            should_include_pending=True,
        )

        # then
        assert responsibility.individual_oop_applied == (
            past_procedure_cost_breakdown.oop_applied
            + past_reimbursement_cost_breakdown.oop_applied
        )
        assert responsibility.individual_deductible_applied == (
            past_procedure_cost_breakdown.deductible
            + past_reimbursement_cost_breakdown.deductible
        )
        assert cost_breakdown_proc.calc_config.sequential_cost_breakdown_ids == [
            past_procedure_cost_breakdown.id,
            past_reimbursement_cost_breakdown.id,
        ]

    def test_sequential_treatments_and_reimbursement_requests_not_include_pending(
        self,
        cost_breakdown_proc,
        member_health_plan,
        wallet_category,
        service_start_date,
    ):
        now = datetime.utcnow()
        cost_breakdowns = CostBreakdownFactory.create_batch(
            size=2,
            deductible=120_00,
            oop_applied=150_00,
        )
        TreatmentProcedureFactory.create_batch(
            size=2,
            cost_breakdown_id=factory.Iterator(
                [cost_breakdowns[0].id, cost_breakdowns[1].id]
            ),
            member_id=member_health_plan.member_id,
            reimbursement_wallet_id=member_health_plan.reimbursement_wallet_id,
            status=factory.Iterator(
                [TreatmentProcedureStatus.SCHEDULED, TreatmentProcedureStatus.COMPLETED]
            ),
            procedure_type=TreatmentProcedureType.MEDICAL,
            completed_date=factory.Iterator([None, now - timedelta(days=1)]),
            start_date=service_start_date,
        )
        reimbursements = ReimbursementRequestFactory.create_batch(
            size=3,
            wallet=member_health_plan.reimbursement_wallet,
            person_receiving_service_id=member_health_plan.member_id,
            person_receiving_service_member_status="MEMBER",
            category=wallet_category,
            state=factory.Iterator(
                [
                    ReimbursementRequestState.APPROVED,
                    ReimbursementRequestState.NEW,
                    ReimbursementRequestState.PENDING,
                ]
            ),
            procedure_type="MEDICAL",
            service_start_date=service_start_date,
        )
        reimbursement_cost_breakdowns = CostBreakdownFactory.create_batch(
            size=3,
            wallet_id=member_health_plan.reimbursement_wallet_id,
            reimbursement_request_id=factory.Iterator(rr.id for rr in reimbursements),
            deductible=102_00,
            oop_applied=103_00,
            created_at=now - timedelta(days=1),
        )
        # when
        responsibility = cost_breakdown_proc.get_sequential_member_responsibility_for_deductible_accumulation(
            member_health_plan=member_health_plan,
            procedure_type=TreatmentProcedureType.MEDICAL,
            before_this_date=now,
        )

        # then
        assert responsibility.individual_oop_applied == (
            cost_breakdowns[1].oop_applied
            + reimbursement_cost_breakdowns[0].oop_applied
        )
        assert responsibility.individual_deductible_applied == (
            cost_breakdowns[1].deductible + reimbursement_cost_breakdowns[0].deductible
        )
        assert cost_breakdown_proc.calc_config.sequential_cost_breakdown_ids == [
            cost_breakdowns[1].id,
            reimbursement_cost_breakdowns[0].id,
        ]

    def test_multiple_family_treatments_health_plan(
        self,
        cost_breakdown_proc,
        wallet,
        member_health_plan,
        wallet_category,
        service_start_date,
        enable_health_plan_feature,
    ):
        # Subscriber health plan is fixture member health plan
        subscriber_wallet = member_health_plan.reimbursement_wallet
        dependent = EnterpriseUserFactory.create()
        ReimbursementWalletUsersFactory.create(
            user_id=dependent.id,
            reimbursement_wallet_id=subscriber_wallet.id,
            status=WalletUserStatus.ACTIVE,
            type=WalletUserType.DEPENDENT,
        )
        dependent_health_plan = MemberHealthPlanFactory.create(
            reimbursement_wallet=subscriber_wallet,
            reimbursement_wallet_id=subscriber_wallet.id,
            employer_health_plan=member_health_plan.employer_health_plan,
            plan_type=FamilyPlanType.FAMILY,
            is_subscriber=False,
            member_id=dependent.id,
            plan_start_at=datetime(year=2024, month=6, day=1),
            plan_end_at=None,
        )

        cost_breakdown_1, cost_breakdown_2 = CostBreakdownFactory.create_batch(
            size=2,
            total_member_responsibility=100_00,
            deductible=100_00,
            oop_applied=100_00,
        )
        # Subscriber procedures [one in valid health plan range, one not in valid health plan range]
        TreatmentProcedureFactory.create_batch(
            size=2,
            cost_breakdown_id=factory.Iterator(
                [cost_breakdown_1.id, cost_breakdown_2.id]
            ),
            member_id=member_health_plan.member_id,
            reimbursement_wallet_id=subscriber_wallet.id,
            status=TreatmentProcedureStatus.COMPLETED,
            created_at=datetime(2023, 1, 1),
            start_date=factory.Iterator(
                [
                    datetime(year=2024, month=2, day=1),
                    datetime(year=2023, month=2, day=1),
                ]
            ),
        )

        # Dependent reimbursements [one in valid dependent heath plan range, one not]
        rr_w_plan, rr_no_plan = ReimbursementRequestFactory.create_batch(
            size=2,
            wallet=member_health_plan.reimbursement_wallet,
            person_receiving_service_id=dependent.id,
            person_receiving_service_member_status="MEMBER",
            category=wallet_category,
            state=ReimbursementRequestState.APPROVED,
            procedure_type="MEDICAL",
            service_start_date=factory.Iterator(
                [
                    datetime(year=2024, month=7, day=1),
                    datetime(year=2023, month=2, day=1),
                ]
            ),
        )
        CostBreakdownFactory.create_batch(
            size=2,
            wallet_id=member_health_plan.reimbursement_wallet_id,
            reimbursement_request_id=factory.Iterator([rr_w_plan.id, rr_no_plan.id]),
            deductible=102_00,
            oop_applied=103_00,
            created_at=datetime(2023, 1, 1),
        )

        current_treatment_procedure = TreatmentProcedureFactory.create(
            member_id=dependent.id,
            reimbursement_wallet_id=subscriber_wallet.id,
            status=TreatmentProcedureStatus.SCHEDULED,
            created_at=datetime(2023, 2, 1),
            start_date=datetime(year=2024, month=9, day=1),
        )

        family_effective_date = member_health_plan.plan_start_at

        expected = cost_breakdown_proc.get_sequential_member_responsibility_for_deductible_accumulation(
            member_health_plan=dependent_health_plan,
            procedure_type=current_treatment_procedure.procedure_type,
            before_this_date=current_treatment_procedure.created_at,
            should_include_pending=True,
            family_effective_date=family_effective_date,
        )

        assert expected == DeductibleAccumulationYTDInfo(
            individual_deductible_applied=102_00,
            individual_oop_applied=103_00,
            family_deductible_applied=202_00,
            family_oop_applied=203_00,
        )

    def test_sequential_treatments_and_reimbursement_requests_individual(
        self,
        cost_breakdown_proc,
        wallet,
        member_health_plan,
        wallet_category,
        service_start_date,
        enable_health_plan_feature,
    ):
        subscriber_wallet = member_health_plan.reimbursement_wallet
        cost_breakdown_1, cost_breakdown_2 = CostBreakdownFactory.create_batch(
            size=2,
            total_member_responsibility=100_00,
            deductible=100_00,
            oop_applied=100_00,
        )
        # Subscriber procedures [one in valid health plan range, one not in valid health plan range]
        TreatmentProcedureFactory.create_batch(
            size=2,
            cost_breakdown_id=factory.Iterator(
                [cost_breakdown_1.id, cost_breakdown_2.id]
            ),
            member_id=member_health_plan.member_id,
            reimbursement_wallet_id=subscriber_wallet.id,
            status=TreatmentProcedureStatus.COMPLETED,
            created_at=datetime(2023, 1, 1),
            start_date=factory.Iterator(
                [
                    datetime(year=2024, month=2, day=1),
                    datetime(year=2023, month=2, day=1),
                ]
            ),
        )

        # Subscriber reimbursements [one in valid dependent heath plan range, one not]
        rr_w_plan, rr_no_plan = ReimbursementRequestFactory.create_batch(
            size=2,
            wallet=member_health_plan.reimbursement_wallet,
            person_receiving_service_id=member_health_plan.member_id,
            person_receiving_service_member_status="MEMBER",
            category=wallet_category,
            state=ReimbursementRequestState.APPROVED,
            procedure_type="MEDICAL",
            service_start_date=factory.Iterator(
                [
                    datetime(year=2024, month=7, day=1),
                    datetime(year=2023, month=2, day=1),
                ]
            ),
        )
        CostBreakdownFactory.create_batch(
            size=2,
            wallet_id=member_health_plan.reimbursement_wallet_id,
            reimbursement_request_id=factory.Iterator([rr_w_plan.id, rr_no_plan.id]),
            deductible=102_00,
            oop_applied=103_00,
            created_at=datetime(2023, 1, 1),
        )

        current_treatment_procedure = TreatmentProcedureFactory.create(
            member_id=member_health_plan.member_id,
            reimbursement_wallet_id=subscriber_wallet.id,
            status=TreatmentProcedureStatus.SCHEDULED,
            created_at=datetime(2023, 2, 1),
            start_date=datetime(year=2024, month=9, day=1),
        )

        family_effective_date = None

        expected = cost_breakdown_proc.get_sequential_member_responsibility_for_deductible_accumulation(
            member_health_plan=member_health_plan,
            procedure_type=current_treatment_procedure.procedure_type,
            before_this_date=current_treatment_procedure.created_at,
            should_include_pending=True,
            family_effective_date=family_effective_date,
        )

        assert expected == DeductibleAccumulationYTDInfo(
            individual_deductible_applied=202_00,
            individual_oop_applied=203_00,
            family_deductible_applied=202_00,
            family_oop_applied=203_00,
        )


class TestHDHPSequentialYTDSpend:
    def test_get_no_spend(
        self,
        cost_breakdown_proc,
        treatment_procedure,
        member_health_plan,
        service_start_date,
    ):
        treatment_procedure.start_date = service_start_date
        expected = cost_breakdown_proc.get_hdhp_non_alegeus_sequential_ytd_spend(
            member_id=member_health_plan.member_id,
            reimbursement_wallet_id=member_health_plan.reimbursement_wallet_id,
            before_this_date=treatment_procedure.created_at,
            member_health_plan=member_health_plan,
        )
        assert expected.sequential_member_responsibilities == 0
        assert expected.sequential_family_responsibilities == 0

    def test_get_spend(
        self,
        cost_breakdown_proc,
        member_health_plan,
        service_start_date,
    ):
        cost_breakdown = CostBreakdownFactory.create(total_member_responsibility=100_00)
        TreatmentProcedureFactory.create(
            cost_breakdown_id=cost_breakdown.id,
            member_id=member_health_plan.member_id,
            reimbursement_wallet_id=member_health_plan.reimbursement_wallet_id,
            status=TreatmentProcedureStatus.SCHEDULED,
            created_at=datetime(2023, 1, 1),
            start_date=service_start_date,
        )
        current_treatment_procedure = TreatmentProcedureFactory.create(
            member_id=member_health_plan.member_id,
            reimbursement_wallet_id=member_health_plan.reimbursement_wallet_id,
            status=TreatmentProcedureStatus.SCHEDULED,
            created_at=datetime(2023, 2, 1),
        )
        with patch(
            "cost_breakdown.cost_breakdown_processor.get_alegeus_hdhp_plan_year_to_date_spend",
            return_value=200_00,
        ):
            # when
            non_alegeus_expected = (
                cost_breakdown_proc.get_hdhp_non_alegeus_sequential_ytd_spend(
                    member_id=member_health_plan.member_id,
                    reimbursement_wallet_id=member_health_plan.reimbursement_wallet_id,
                    before_this_date=current_treatment_procedure.created_at,
                    member_health_plan=member_health_plan,
                    should_include_pending=True,
                )
            )
            alegeus_expected = (
                cost_breakdown_proc.get_hdhp_alegeus_sequential_ytd_spend(
                    member_health_plan=member_health_plan,
                )
            )

        # then
        expected = (
            alegeus_expected + non_alegeus_expected.sequential_member_responsibilities
        )
        assert expected == 300_00
        assert cost_breakdown_proc.calc_config.sequential_cost_breakdown_ids == [
            cost_breakdown.id
        ]

    def test_get_family_spend(
        self,
        cost_breakdown_proc,
        member_health_plan,
        service_start_date,
    ):
        # given
        second_member_health_plan = MemberHealthPlanFactory.create(
            reimbursement_wallet=member_health_plan.reimbursement_wallet,
            reimbursement_wallet_id=member_health_plan.reimbursement_wallet_id,
            employer_health_plan=member_health_plan.employer_health_plan,
        )
        price_per_cost_breakdown = 100_00
        cost_breakdowns = CostBreakdownFactory.create_batch(
            size=4, total_member_responsibility=price_per_cost_breakdown
        )
        # Two treatment procedures for each member in the family
        TreatmentProcedureFactory.create_batch(
            size=2,
            member_id=second_member_health_plan.member_id,
            reimbursement_wallet_id=member_health_plan.reimbursement_wallet_id,
            cost_breakdown_id=factory.Iterator(
                [c_b.id for c_b in cost_breakdowns[0:1]]
            ),
            status=TreatmentProcedureStatus.SCHEDULED,
            created_at=datetime(2023, 1, 1),
            start_date=service_start_date,
        )
        member_procedures = TreatmentProcedureFactory.create_batch(
            size=2,
            member_id=member_health_plan.member_id,
            reimbursement_wallet_id=member_health_plan.reimbursement_wallet_id,
            cost_breakdown_id=factory.Iterator(
                [c_b.id for c_b in cost_breakdowns[2:3]]
            ),
            status=TreatmentProcedureStatus.SCHEDULED,
            created_at=factory.Iterator([datetime(2023, 2, 1), datetime(2023, 3, 1)]),
            start_date=service_start_date,
        )
        current_treatment_procedure = member_procedures[-1]

        # when
        ytd_data = cost_breakdown_proc.get_hdhp_non_alegeus_sequential_ytd_spend(
            member_id=member_health_plan.member_id,
            reimbursement_wallet_id=member_health_plan.reimbursement_wallet_id,
            before_this_date=current_treatment_procedure.created_at,
            member_health_plan=member_health_plan,
            should_include_pending=True,
        )

        # then
        assert ytd_data.sequential_member_responsibilities == price_per_cost_breakdown
        assert (
            ytd_data.sequential_family_responsibilities == price_per_cost_breakdown * 3
        )

    def test_get_alegeus_exception(
        self,
        cost_breakdown_proc,
        member_health_plan,
    ):
        # TODO: this test literally just tests patch functionality.
        with patch(
            "cost_breakdown.cost_breakdown_processor.get_alegeus_hdhp_plan_year_to_date_spend",
        ) as mocked_alegeus_call, pytest.raises(ValueError):
            mocked_alegeus_call.side_effect = ValueError(
                "Missing account for HDHP plan"
            )
            cost_breakdown_proc.get_hdhp_alegeus_sequential_ytd_spend(
                member_health_plan=member_health_plan,
            )

    def test_treatment_and_reimbursement_request(
        self,
        cost_breakdown_proc,
        member_health_plan,
        wallet_category,
        service_start_date,
        enable_health_plan_logging_feature,
    ):
        (
            past_procedure_cost_breakdown,
            future_procedure_cost_breakdown,
        ) = CostBreakdownFactory.create_batch(
            size=2,
            total_member_responsibility=100_00,
        )
        TreatmentProcedureFactory.create_batch(
            size=2,
            cost_breakdown_id=factory.Iterator(
                [past_procedure_cost_breakdown.id, future_procedure_cost_breakdown.id]
            ),
            member_id=member_health_plan.member_id,
            reimbursement_wallet_id=member_health_plan.reimbursement_wallet_id,
            start_date=service_start_date,
            status=TreatmentProcedureStatus.SCHEDULED,
            procedure_type=TreatmentProcedureType.MEDICAL,
            created_at=factory.Iterator(
                [
                    service_start_date - timedelta(days=1),
                    service_start_date + timedelta(days=1),
                ]
            ),
        )
        (
            past_reimbursement,
            current_reimbursement,
            future_reimbursement,
        ) = ReimbursementRequestFactory.create_batch(
            size=3,
            wallet=member_health_plan.reimbursement_wallet,
            person_receiving_service_id=member_health_plan.member_id,
            person_receiving_service_member_status="MEMBER",
            category=wallet_category,
            state=ReimbursementRequestState.NEW,
            procedure_type="MEDICAL",
            service_start_date=factory.Iterator(
                [
                    service_start_date - timedelta(days=1),
                    service_start_date,
                    service_start_date + timedelta(days=1),
                ]
            ),
        )
        (
            past_reimbursement_cost_breakdown,
            future_reimbursement_cost_breakdown,
        ) = CostBreakdownFactory.create_batch(
            size=2,
            wallet_id=member_health_plan.reimbursement_wallet_id,
            reimbursement_request_id=factory.Iterator(
                [past_reimbursement.id, future_reimbursement.id]
            ),
            total_member_responsibility=151_00,
        )

        # when
        ytd_data = cost_breakdown_proc.get_hdhp_non_alegeus_sequential_ytd_spend(
            member_id=member_health_plan.member_id,
            reimbursement_wallet_id=member_health_plan.reimbursement_wallet_id,
            before_this_date=service_start_date,
            member_health_plan=member_health_plan,
            should_include_pending=True,
        )

        # then
        assert ytd_data.sequential_member_responsibilities == (
            past_reimbursement_cost_breakdown.total_member_responsibility
            + past_procedure_cost_breakdown.total_member_responsibility
        )
        assert cost_breakdown_proc.calc_config.sequential_cost_breakdown_ids == [
            past_procedure_cost_breakdown.id,
            past_reimbursement_cost_breakdown.id,
        ]

    def test_treatment_and_reimbursement_request_not_include_pending(
        self,
        cost_breakdown_proc,
        member_health_plan,
        wallet_category,
        service_start_date,
    ):
        now = datetime.utcnow()
        procedure_cost_breakdown = CostBreakdownFactory.create(
            total_member_responsibility=100_00,
        )
        TreatmentProcedureFactory.create(
            cost_breakdown_id=procedure_cost_breakdown.id,
            member_id=member_health_plan.member_id,
            reimbursement_wallet_id=member_health_plan.reimbursement_wallet_id,
            status=TreatmentProcedureStatus.SCHEDULED,
            procedure_type=TreatmentProcedureType.MEDICAL,
            created_at=now - timedelta(days=1),
            start_date=service_start_date,
        )
        reimbursements = ReimbursementRequestFactory.create_batch(
            size=3,
            wallet=member_health_plan.reimbursement_wallet,
            person_receiving_service_id=member_health_plan.member_id,
            person_receiving_service_member_status="MEMBER",
            category=wallet_category,
            state=factory.Iterator(
                [
                    ReimbursementRequestState.NEW,
                    ReimbursementRequestState.PENDING,
                    ReimbursementRequestState.DENIED,
                ]
            ),
            procedure_type="MEDICAL",
            service_start_date=service_start_date - timedelta(days=1),
            amount=151_00,
        )
        CostBreakdownFactory.create_batch(
            size=3,
            wallet_id=member_health_plan.reimbursement_wallet_id,
            reimbursement_request_id=factory.Iterator(rr.id for rr in reimbursements),
            total_member_responsibility=151_00,
        )

        # when
        ytd_data = cost_breakdown_proc.get_hdhp_non_alegeus_sequential_ytd_spend(
            member_id=member_health_plan.member_id,
            reimbursement_wallet_id=member_health_plan.reimbursement_wallet_id,
            before_this_date=now,
            member_health_plan=member_health_plan,
        )

        # then
        assert ytd_data.sequential_member_responsibilities == 0
        assert cost_breakdown_proc.calc_config.sequential_cost_breakdown_ids == []

    def test_extra_applied_amount(
        self, cost_breakdown_proc, member_health_plan, service_start_date
    ):
        cost_breakdowns = CostBreakdownFactory.create_batch(
            size=3, total_member_responsibility=10_000
        )
        tps = TreatmentProcedureFactory.create_batch(
            size=3,
            member_id=member_health_plan.member_id,
            reimbursement_wallet_id=member_health_plan.reimbursement_wallet_id,
            cost_breakdown_id=factory.Iterator([c_b.id for c_b in cost_breakdowns]),
            status=TreatmentProcedureStatus.SCHEDULED,
            created_at=datetime(2024, 1, 1),
            start_date=service_start_date,
        )
        current_treatment_procedure = TreatmentProcedureFactory.create(
            member_id=member_health_plan.member_id,
            reimbursement_wallet_id=member_health_plan.reimbursement_wallet_id,
            status=TreatmentProcedureStatus.SCHEDULED,
            created_at=datetime(2024, 2, 1),
            start_date=service_start_date,
        )
        cost_breakdown_proc.extra_applied_amount = ExtraAppliedAmount(
            assumed_paid_procedures=[tp.id for tp in tps[1:]],
            oop_applied=15_000,
        )
        ytd_spend = cost_breakdown_proc.get_hdhp_non_alegeus_sequential_ytd_spend(
            member_id=member_health_plan.member_id,
            reimbursement_wallet_id=member_health_plan.reimbursement_wallet_id,
            before_this_date=current_treatment_procedure.created_at,
            member_health_plan=member_health_plan,
            should_include_pending=True,
        )
        assert len(cost_breakdown_proc.calc_config.sequential_cost_breakdown_ids) == 1
        assert ytd_spend == HDHPAccumulationYTDInfo(
            sequential_member_responsibilities=25_000,
            sequential_family_responsibilities=25_000,
        )

    def test_treatment_and_reimbursement_request_health_plan_family_as_of(
        self,
        cost_breakdown_proc,
        member_health_plan,
        wallet_category,
        service_start_date,
        enable_health_plan_feature,
    ):
        subscriber_wallet = member_health_plan.reimbursement_wallet
        dependent = EnterpriseUserFactory.create()
        ReimbursementWalletUsersFactory.create(
            user_id=dependent.id,
            reimbursement_wallet_id=subscriber_wallet.id,
            status=WalletUserStatus.ACTIVE,
            type=WalletUserType.DEPENDENT,
        )
        dependent_health_plan = MemberHealthPlanFactory.create(
            reimbursement_wallet=subscriber_wallet,
            reimbursement_wallet_id=subscriber_wallet.id,
            employer_health_plan=member_health_plan.employer_health_plan,
            plan_type=FamilyPlanType.FAMILY,
            is_subscriber=False,
            member_id=dependent.id,
            plan_start_at=datetime(year=2024, month=6, day=1),
            plan_end_at=datetime(year=2025, month=1, day=1),
        )
        (
            health_plan_found_cb,
            health_plan_not_found_cb,
        ) = CostBreakdownFactory.create_batch(
            size=2,
            total_member_responsibility=100_00,
        )
        TreatmentProcedureFactory.create_batch(
            size=2,
            cost_breakdown_id=factory.Iterator(
                [health_plan_found_cb.id, health_plan_not_found_cb.id]
            ),
            member_id=member_health_plan.member_id,
            reimbursement_wallet_id=subscriber_wallet.id,
            start_date=factory.Iterator(
                [service_start_date, service_start_date + timedelta(days=600)]
            ),
            status=TreatmentProcedureStatus.SCHEDULED,
            procedure_type=TreatmentProcedureType.MEDICAL,
            created_at=service_start_date - timedelta(days=1),
        )
        rr_found_hp, rr_not_found_hp = ReimbursementRequestFactory.create_batch(
            size=2,
            wallet=subscriber_wallet,
            person_receiving_service_id=dependent.id,
            person_receiving_service_member_status="MEMBER",
            category=wallet_category,
            state=ReimbursementRequestState.NEW,
            procedure_type="MEDICAL",
            service_start_date=factory.Iterator(
                [
                    datetime(year=2024, month=6, day=2),
                    service_start_date - timedelta(days=365),
                ]
            ),
        )
        (
            found_reimbursement_cost_breakdown,
            not_found_reimbursement_cost_breakdown,
        ) = CostBreakdownFactory.create_batch(
            size=2,
            wallet_id=subscriber_wallet.id,
            reimbursement_request_id=factory.Iterator(
                [rr_found_hp.id, rr_not_found_hp.id]
            ),
            total_member_responsibility=151_00,
        )

        family_effective_date = member_health_plan.plan_start_at
        # when
        ytd_data = cost_breakdown_proc.get_hdhp_non_alegeus_sequential_ytd_spend(
            member_id=dependent_health_plan.member_id,
            reimbursement_wallet_id=dependent_health_plan.reimbursement_wallet_id,
            before_this_date=datetime(year=2024, month=7, day=2),
            member_health_plan=dependent_health_plan,
            should_include_pending=True,
            family_effective_date=family_effective_date,
        )

        # then
        assert ytd_data.sequential_member_responsibilities == (
            found_reimbursement_cost_breakdown.total_member_responsibility
        )
        assert ytd_data.sequential_family_responsibilities == (
            found_reimbursement_cost_breakdown.total_member_responsibility
            + health_plan_found_cb.total_member_responsibility
        )
        assert cost_breakdown_proc.calc_config.sequential_cost_breakdown_ids == [
            health_plan_found_cb.id,
            found_reimbursement_cost_breakdown.id,
        ]

    def test_treatment_and_reimbursement_request_health_plan_individual(
        self,
        cost_breakdown_proc,
        member_health_plan,
        wallet_category,
        service_start_date,
        enable_health_plan_feature,
    ):
        subscriber_wallet = member_health_plan.reimbursement_wallet
        dependent = EnterpriseUserFactory.create()
        ReimbursementWalletUsersFactory.create(
            user_id=dependent.id,
            reimbursement_wallet_id=subscriber_wallet.id,
            status=WalletUserStatus.ACTIVE,
            type=WalletUserType.DEPENDENT,
        )
        dependent_health_plan = MemberHealthPlanFactory.create(
            reimbursement_wallet=subscriber_wallet,
            reimbursement_wallet_id=subscriber_wallet.id,
            employer_health_plan=member_health_plan.employer_health_plan,
            plan_type=FamilyPlanType.FAMILY,
            is_subscriber=False,
            member_id=dependent.id,
            plan_start_at=datetime(year=2024, month=6, day=1),
            plan_end_at=datetime(year=2025, month=1, day=1),
        )
        (
            health_plan_found_cb,
            health_plan_not_found_cb,
        ) = CostBreakdownFactory.create_batch(
            size=2,
            total_member_responsibility=100_00,
        )
        TreatmentProcedureFactory.create_batch(
            size=2,
            cost_breakdown_id=factory.Iterator(
                [health_plan_found_cb.id, health_plan_not_found_cb.id]
            ),
            member_id=member_health_plan.member_id,
            reimbursement_wallet_id=subscriber_wallet.id,
            start_date=factory.Iterator(
                [service_start_date, service_start_date + timedelta(days=600)]
            ),
            status=TreatmentProcedureStatus.SCHEDULED,
            procedure_type=TreatmentProcedureType.MEDICAL,
            created_at=service_start_date - timedelta(days=1),
        )
        rr_found_hp, rr_not_found_hp = ReimbursementRequestFactory.create_batch(
            size=2,
            wallet=subscriber_wallet,
            person_receiving_service_id=dependent.id,
            person_receiving_service_member_status="MEMBER",
            category=wallet_category,
            state=ReimbursementRequestState.NEW,
            procedure_type="MEDICAL",
            service_start_date=factory.Iterator(
                [
                    datetime(year=2024, month=6, day=2),
                    service_start_date - timedelta(days=365),
                ]
            ),
        )
        (
            found_reimbursement_cost_breakdown,
            not_found_reimbursement_cost_breakdown,
        ) = CostBreakdownFactory.create_batch(
            size=2,
            wallet_id=subscriber_wallet.id,
            reimbursement_request_id=factory.Iterator(
                [rr_found_hp.id, rr_not_found_hp.id]
            ),
            total_member_responsibility=151_00,
        )
        # when
        # Setting the family_effective_date to None will filter by dependent health plan only
        ytd_data = cost_breakdown_proc.get_hdhp_non_alegeus_sequential_ytd_spend(
            member_id=dependent_health_plan.member_id,
            reimbursement_wallet_id=dependent_health_plan.reimbursement_wallet_id,
            before_this_date=datetime(year=2024, month=12, day=2),
            member_health_plan=dependent_health_plan,
            should_include_pending=True,
            family_effective_date=None,
        )

        # then
        assert ytd_data.sequential_member_responsibilities == (
            found_reimbursement_cost_breakdown.total_member_responsibility
        )
        assert ytd_data.sequential_family_responsibilities == (
            found_reimbursement_cost_breakdown.total_member_responsibility
        )
        assert cost_breakdown_proc.calc_config.sequential_cost_breakdown_ids == [
            found_reimbursement_cost_breakdown.id,
        ]


def test_store_cost_breakdown_to_db(
    cost_breakdown_proc, eligibility_info_family_plan, wallet
):
    cost_breakdown = CostBreakdownFactory.build(wallet_id=wallet.id)
    cost_breakdown.calc_config = dataclasses.asdict(
        CalcConfigAudit(
            eligibility_info=eligibility_info_family_plan,
            sequential_cost_breakdown_ids=[1, 2, 3, 4],
            trigger_object_status="SCHEDULED",
        )
    )
    cost_breakdown_proc._store_cost_breakdown_to_db(
        cost_breakdown=cost_breakdown, wallet=wallet
    )


class TestCostBreakdownProcessor:
    def test_build_data_service(self, cost_breakdown_proc, wallet, treatment_procedure):
        with feature_flags.test_data() as ff_test_data, patch.object(
            cost_breakdown_proc,
            "get_treatment_cost_sharing_category",
            return_value=MagicMock(name="CostSharingCategory"),
        ):
            ff_test_data.update(
                ff_test_data.flag(HEALTH_PLAN_YOY_FLAG).variations(NEW_BEHAVIOR)
            )
            available_categories = wallet.get_or_create_wallet_allowed_categories[0]
            category = available_categories.reimbursement_request_category
            treatment_procedure.reimbursement_request_category_id = category.id
            service = cost_breakdown_proc.cost_breakdown_service_from_data(
                cost=100_00,
                member_id=wallet.user_id,
                wallet=wallet,
                reimbursement_category=category,
                procedure_type=TreatmentProcedureType.MEDICAL,
                before_this_date=datetime(year=2024, month=1, day=1),
                asof_date=datetime(
                    year=2017, month=1, day=1
                ),  # I want NO member health plan
                global_procedure_id=-1,
                service_start_date=treatment_procedure.start_date,
            )
        assert service.member_health_plan is None
