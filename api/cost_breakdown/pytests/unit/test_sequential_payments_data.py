import datetime

import factory
import pytest

from cost_breakdown.models.cost_breakdown import ExtraAppliedAmount
from cost_breakdown.pytests.factories import CostBreakdownFactory
from direct_payment.treatment_procedure.models.treatment_procedure import (
    TreatmentProcedureStatus,
)
from direct_payment.treatment_procedure.pytests.factories import (
    TreatmentProcedureFactory,
)
from payer_accumulator.common import TreatmentAccumulationStatus
from payer_accumulator.pytests.factories import AccumulationTreatmentMappingFactory
from pytests.factories import EnterpriseUserFactory, ReimbursementWalletUsersFactory
from wallet.models.constants import (
    FamilyPlanType,
    ReimbursementRequestState,
    WalletUserStatus,
    WalletUserType,
)
from wallet.pytests.factories import (
    MemberHealthPlanFactory,
    ReimbursementRequestFactory,
)
from wallet.repository.health_plan import HEALTH_PLAN_YOY_FLAG, NEW_BEHAVIOR


@pytest.fixture(scope="module")
def service_start_date():
    return datetime.datetime.utcnow() - datetime.timedelta(days=5)


@pytest.fixture(autouse=True)
def enable_health_plan_feature(ff_test_data):
    ff_test_data.update(
        ff_test_data.flag(HEALTH_PLAN_YOY_FLAG).variations(NEW_BEHAVIOR)
    )


class TestSequentialReimbursementRequestData:
    # _get_all_sequential_reimbursement_request_data used for deductible accumulation sequential data
    def test_no_data(
        self,
        ff_test_data,
        cost_breakdown_proc,
        member_health_plan_now,
    ):
        data = cost_breakdown_proc._get_all_sequential_reimbursement_request_data(
            member_health_plan=member_health_plan_now,
            before_this_date=datetime.datetime.utcnow(),
        )
        assert data == []

    def test_by_wallet(
        self,
        ff_test_data,
        cost_breakdown_proc,
        member_health_plan_now,
        wallet_category,
        wallet_deductible_accumulation,
        service_start_date,
    ):
        # With 1-n reimbursement requests
        valid_rr, invalid_rr = ReimbursementRequestFactory.create_batch(
            size=2,
            # we do return data associated with the given wallet
            # we do not return data associated with the wrong wallet
            wallet=factory.Iterator(
                [
                    member_health_plan_now.reimbursement_wallet,
                    wallet_deductible_accumulation,
                ]
            ),
            category=wallet_category,
            state=ReimbursementRequestState.APPROVED,
            service_start_date=service_start_date,
            person_receiving_service_id=member_health_plan_now.member_id,
        )
        CostBreakdownFactory.create_batch(
            size=2,
            wallet_id=factory.Iterator(
                [
                    member_health_plan_now.reimbursement_wallet.id,
                    wallet_deductible_accumulation.id,
                ]
            ),
            reimbursement_request_id=factory.Iterator([valid_rr.id, invalid_rr.id]),
            created_at=datetime.datetime.utcnow() - datetime.timedelta(days=1),
        )

        # when
        data = cost_breakdown_proc._get_all_sequential_reimbursement_request_data(
            member_health_plan=member_health_plan_now,
            before_this_date=datetime.datetime.utcnow(),
        )

        # then
        reimbursement_requests = [
            reimbursement_request for reimbursement_request, _ in data
        ]
        assert reimbursement_requests == [valid_rr]

    def test_by_has_a_cost_breakdown(
        self,
        ff_test_data,
        cost_breakdown_proc,
        member_health_plan_now,
        wallet_category,
        service_start_date,
    ):
        # must have a cost breakdown
        valid_rr, invalid_rr = ReimbursementRequestFactory.create_batch(
            size=2,
            wallet=member_health_plan_now.reimbursement_wallet,
            category=wallet_category,
            state=ReimbursementRequestState.APPROVED,
            service_start_date=service_start_date,
            person_receiving_service_id=member_health_plan_now.member_id,
        )
        old_c_b, new_c_b = CostBreakdownFactory.create_batch(
            size=2,
            # Making sure we handle multiple cost breakdowns for one reimbursement request here
            reimbursement_request_id=valid_rr.id,
            wallet_id=member_health_plan_now.reimbursement_wallet_id,
            created_at=factory.Iterator(
                [
                    # Making sure we return the most recent cost breakdown for the reimbursement request
                    datetime.datetime.utcnow() - datetime.timedelta(days=2),
                    datetime.datetime.utcnow() - datetime.timedelta(days=1),
                ]
            ),
        )

        # when
        data = cost_breakdown_proc._get_all_sequential_reimbursement_request_data(
            member_health_plan=member_health_plan_now,
            before_this_date=datetime.datetime.utcnow(),
        )

        # then
        reimbursement_requests = [
            reimbursement_request for reimbursement_request, _ in data
        ]
        cost_breakdowns = [cost_breakdown for _, cost_breakdown in data]
        assert reimbursement_requests == [valid_rr]
        assert new_c_b.created_at > old_c_b.created_at
        assert new_c_b.id > old_c_b.id
        assert cost_breakdowns == [new_c_b]

    def test_by_accumulation_status(
        self,
        ff_test_data,
        cost_breakdown_proc,
        member_health_plan_now,
        service_start_date,
        wallet_category,
    ):
        reimbursement_requests = ReimbursementRequestFactory.create_batch(
            size=5,
            wallet=member_health_plan_now.reimbursement_wallet,
            category=wallet_category,
            state=ReimbursementRequestState.APPROVED,
            service_start_date=service_start_date - datetime.timedelta(days=1),
        )
        CostBreakdownFactory.create_batch(
            size=5,
            wallet_id=member_health_plan_now.reimbursement_wallet.id,
            reimbursement_request_id=factory.Iterator(
                [rr.id for rr in reimbursement_requests]
            ),
        )
        mappings = AccumulationTreatmentMappingFactory.create_batch(
            size=5,
            reimbursement_request_id=factory.Iterator(
                [
                    reimbursement_request.id
                    for reimbursement_request in reimbursement_requests
                ]
            ),
            treatment_accumulation_status=factory.Iterator(
                [
                    TreatmentAccumulationStatus.PAID,
                    TreatmentAccumulationStatus.WAITING,
                    TreatmentAccumulationStatus.SUBMITTED,
                    TreatmentAccumulationStatus.ROW_ERROR,
                    TreatmentAccumulationStatus.REJECTED,
                ]
            ),
        )

        # when
        data = cost_breakdown_proc._get_all_sequential_reimbursement_request_data(
            member_health_plan=member_health_plan_now,
            before_this_date=service_start_date,
        )

        # then
        reimbursement_request_ids = [
            reimbursement_request.id for reimbursement_request, _ in data
        ]
        relevant_mappings = [
            mapping
            for mapping in mappings
            if mapping.reimbursement_request_id in reimbursement_request_ids
        ]
        # a SUBMITTED procedure should not be used in a calculation
        assert TreatmentAccumulationStatus.SUBMITTED not in [
            mapping.treatment_accumulation_status for mapping in relevant_mappings
        ]

    def test_by_state(
        self,
        ff_test_data,
        cost_breakdown_proc,
        member_health_plan_now,
        wallet_category,
        service_start_date,
    ):
        valid_requests = ReimbursementRequestFactory.create_batch(
            size=4,
            wallet=member_health_plan_now.reimbursement_wallet,
            category=wallet_category,
            service_start_date=service_start_date,
            person_receiving_service_id=member_health_plan_now.member_id,
            # always valid states
            state=factory.Iterator(
                [
                    ReimbursementRequestState.NEW,
                    ReimbursementRequestState.PENDING,
                    ReimbursementRequestState.APPROVED,
                    ReimbursementRequestState.REIMBURSED,
                ]
            ),
        )
        (
            valid_denied_request,
            invalid_denied_request,
        ) = ReimbursementRequestFactory.create_batch(
            size=2,
            wallet=member_health_plan_now.reimbursement_wallet,
            category=wallet_category,
            service_start_date=service_start_date,
            person_receiving_service_id=member_health_plan_now.member_id,
            # sometimes valid state
            state=ReimbursementRequestState.DENIED,
            amount=100_00,
        )
        invalid_request = ReimbursementRequestFactory.create(
            wallet=member_health_plan_now.reimbursement_wallet,
            category=wallet_category,
            service_start_date=service_start_date,
            person_receiving_service_id=member_health_plan_now.member_id,
            # example always invalid state
            state=ReimbursementRequestState.FAILED,
        )
        CostBreakdownFactory.create_batch(
            size=6,
            wallet_id=member_health_plan_now.reimbursement_wallet.id,
            reimbursement_request_id=factory.Iterator(
                [rr.id for rr in valid_requests]
                + [invalid_denied_request.id, invalid_request.id]
            ),
        )
        # Need to specify the cost breakdown state to make the valid denied request actually valid
        CostBreakdownFactory.create(
            wallet_id=member_health_plan_now.reimbursement_wallet.id,
            reimbursement_request_id=valid_denied_request.id,
            total_member_responsibility=valid_denied_request.amount,
            total_employer_responsibility=0,
            created_at=datetime.datetime.utcnow() - datetime.timedelta(days=1),
        )

        # when
        data = cost_breakdown_proc._get_all_sequential_reimbursement_request_data(
            member_health_plan=member_health_plan_now,
            before_this_date=datetime.datetime.utcnow(),
            should_include_pending=True,
        )

        # then
        reimbursement_requests = {
            reimbursement_request for reimbursement_request, _ in data
        }
        assert reimbursement_requests == set(valid_requests + [valid_denied_request])

    def test_by_state_not_include_pending(
        self,
        ff_test_data,
        cost_breakdown_proc,
        member_health_plan_now,
        wallet_category,
        service_start_date,
    ):
        valid_requests = ReimbursementRequestFactory.create_batch(
            size=4,
            wallet=member_health_plan_now.reimbursement_wallet,
            category=wallet_category,
            service_start_date=service_start_date,
            person_receiving_service_id=member_health_plan_now.member_id,
            # always valid states
            state=factory.Iterator(
                [
                    ReimbursementRequestState.NEW,
                    ReimbursementRequestState.PENDING,
                    ReimbursementRequestState.APPROVED,
                    ReimbursementRequestState.REIMBURSED,
                ]
            ),
        )
        (
            valid_denied_request,
            invalid_denied_request,
        ) = ReimbursementRequestFactory.create_batch(
            size=2,
            wallet=member_health_plan_now.reimbursement_wallet,
            category=wallet_category,
            service_start_date=service_start_date,
            person_receiving_service_id=member_health_plan_now.member_id,
            # sometimes valid state
            state=ReimbursementRequestState.DENIED,
            amount=100_00,
        )
        invalid_request = ReimbursementRequestFactory.create(
            wallet=member_health_plan_now.reimbursement_wallet,
            category=wallet_category,
            service_start_date=service_start_date,
            person_receiving_service_id=member_health_plan_now.member_id,
            # example always invalid state
            state=ReimbursementRequestState.FAILED,
        )
        CostBreakdownFactory.create_batch(
            size=6,
            wallet_id=member_health_plan_now.reimbursement_wallet.id,
            reimbursement_request_id=factory.Iterator(
                [rr.id for rr in valid_requests]
                + [invalid_denied_request.id, invalid_request.id]
            ),
        )
        # Need to specify the cost breakdown state to make the valid denied request actually valid
        CostBreakdownFactory.create(
            wallet_id=member_health_plan_now.reimbursement_wallet.id,
            reimbursement_request_id=valid_denied_request.id,
            total_member_responsibility=valid_denied_request.amount,
            total_employer_responsibility=0,
            created_at=datetime.datetime.utcnow() - datetime.timedelta(days=1),
        )

        # when
        data = cost_breakdown_proc._get_all_sequential_reimbursement_request_data(
            member_health_plan=member_health_plan_now,
            before_this_date=datetime.datetime.utcnow(),
            should_include_pending=False,
        )

        # then
        reimbursement_requests = {
            reimbursement_request for reimbursement_request, _ in data
        }
        assert reimbursement_requests == set(
            valid_requests[2:] + [valid_denied_request]
        )

    def test_by_member_health_plan_filter_by_asof_date(
        self,
        enable_health_plan_feature,
        cost_breakdown_proc,
        member_health_plan_now,
        wallet_category,
        service_start_date,
    ):
        valid_rr, invalid_rr = ReimbursementRequestFactory.create_batch(
            size=2,
            wallet=member_health_plan_now.reimbursement_wallet,
            category=wallet_category,
            state=ReimbursementRequestState.APPROVED,
            service_start_date=factory.Iterator(
                [
                    service_start_date,
                    datetime.datetime.utcnow() - datetime.timedelta(days=600),
                ]
            ),
            person_receiving_service_id=member_health_plan_now.member_id,
        )
        CostBreakdownFactory.create_batch(
            size=2,
            wallet_id=member_health_plan_now.reimbursement_wallet.id,
            reimbursement_request_id=factory.Iterator([valid_rr.id, invalid_rr.id]),
            created_at=datetime.datetime.utcnow() - datetime.timedelta(days=1),
        )

        # when
        data = cost_breakdown_proc._get_all_sequential_reimbursement_request_data(
            member_health_plan=member_health_plan_now,
            before_this_date=datetime.datetime.utcnow(),
            family_effective_date=None,
        )

        # then
        reimbursement_requests = [
            reimbursement_request for reimbursement_request, _ in data
        ]
        assert reimbursement_requests == [valid_rr]

    def test_by_member_health_plan_filter_by_family_asof_date(
        self,
        cost_breakdown_proc,
        employer_health_plan,
        member_health_plan_now,
        wallet_category,
        service_start_date,
        enable_health_plan_feature,
    ):
        subscriber_wallet = member_health_plan_now.reimbursement_wallet
        dependent = EnterpriseUserFactory.create()
        ReimbursementWalletUsersFactory.create(
            user_id=dependent.id,
            reimbursement_wallet_id=subscriber_wallet.id,
            status=WalletUserStatus.ACTIVE,
            type=WalletUserType.DEPENDENT,
        )
        # Created 30 days ago
        dependent_health_plan = MemberHealthPlanFactory.create(
            reimbursement_wallet=subscriber_wallet,
            reimbursement_wallet_id=subscriber_wallet.id,
            employer_health_plan=employer_health_plan,
            plan_type=FamilyPlanType.FAMILY,
            is_subscriber=False,
            member_id=dependent.id,
            plan_start_at=datetime.datetime.utcnow() - datetime.timedelta(days=30),
            plan_end_at=datetime.datetime.utcnow() + datetime.timedelta(days=395),
        )

        (
            valid_subscriber_rr,
            invalid_subscriber_rr,
            valid_dependent_rr,
            invalid_dependent_rr,
        ) = ReimbursementRequestFactory.create_batch(
            size=4,
            wallet=member_health_plan_now.reimbursement_wallet,
            category=wallet_category,
            state=ReimbursementRequestState.APPROVED,
            service_start_date=factory.Iterator(
                [
                    service_start_date - datetime.timedelta(days=60),
                    datetime.datetime.utcnow() - datetime.timedelta(days=600),
                    service_start_date,
                    datetime.datetime.utcnow() - datetime.timedelta(days=600),
                ]
            ),
            person_receiving_service_id=factory.Iterator(
                [
                    member_health_plan_now.member_id,
                    member_health_plan_now.member_id,
                    dependent_health_plan.member_id,
                    dependent_health_plan.member_id,
                ]
            ),
        )
        CostBreakdownFactory.create_batch(
            size=4,
            wallet_id=subscriber_wallet.id,
            reimbursement_request_id=factory.Iterator(
                [
                    valid_subscriber_rr.id,
                    invalid_subscriber_rr.id,
                    valid_dependent_rr.id,
                    invalid_dependent_rr.id,
                ]
            ),
            created_at=datetime.datetime.utcnow() - datetime.timedelta(days=10),
        )

        # when
        data = cost_breakdown_proc._get_all_sequential_reimbursement_request_data(
            member_health_plan=dependent_health_plan,
            before_this_date=datetime.datetime.utcnow(),
            family_effective_date=member_health_plan_now.plan_start_at,
        )

        # then

        reimbursement_requests = set(
            [reimbursement_request for reimbursement_request, _ in data]
        )
        assert {valid_subscriber_rr, valid_dependent_rr} == reimbursement_requests


class TestSequentialTreatmentProcedureData:
    # _get_ded_accumulation_sequential_treatment_procedure_data used for deductible accumulation sequential data
    def test_no_data(
        self,
        ff_test_data,
        cost_breakdown_proc,
        member_health_plan_now,
        service_start_date,
    ):
        data = cost_breakdown_proc._get_ded_accumulation_sequential_treatment_procedure_data(
            member_health_plan=member_health_plan_now,
            before_this_date=datetime.datetime.utcnow(),
            should_include_pending=True,
        )
        assert data == []

    def test_by_wallet(
        self,
        ff_test_data,
        cost_breakdown_proc,
        member_health_plan_now,
        service_start_date,
    ):
        cost_breakdowns = CostBreakdownFactory.create_batch(size=2)
        valid_procedure, invalid_procedure = TreatmentProcedureFactory.create_batch(
            size=2,
            member_id=member_health_plan_now.member_id,
            reimbursement_wallet_id=factory.Iterator(
                [
                    # we do return procedures associated with the given wallet
                    member_health_plan_now.reimbursement_wallet_id,
                    # we do not return procedures associated with a different wallet
                    member_health_plan_now.reimbursement_wallet_id + 1,
                ]
            ),
            cost_breakdown_id=factory.Iterator(
                [cost_breakdown.id for cost_breakdown in cost_breakdowns]
            ),
            status=TreatmentProcedureStatus.SCHEDULED,
            created_at=service_start_date - datetime.timedelta(days=1),
        )
        # when
        data = cost_breakdown_proc._get_ded_accumulation_sequential_treatment_procedure_data(
            member_health_plan=member_health_plan_now,
            before_this_date=service_start_date,
            should_include_pending=True,
        )

        # then
        procedures = [procedure for procedure, _ in data]
        assert valid_procedure in procedures
        assert invalid_procedure not in procedures

    def test_by_date(
        self,
        ff_test_data,
        cost_breakdown_proc,
        member_health_plan_now,
    ):
        cost_breakdowns = CostBreakdownFactory.create_batch(size=2)
        valid_procedure, invalid_procedure = TreatmentProcedureFactory.create_batch(
            size=2,
            member_id=member_health_plan_now.member_id,
            reimbursement_wallet_id=member_health_plan_now.reimbursement_wallet_id,
            cost_breakdown_id=factory.Iterator(
                [cost_breakdown.id for cost_breakdown in cost_breakdowns]
            ),
            status=TreatmentProcedureStatus.SCHEDULED,
            created_at=factory.Iterator(
                [
                    # we do return procedures before the given date
                    datetime.datetime.utcnow() - datetime.timedelta(days=1),
                    # we do not return procedures created after the given date
                    datetime.datetime.utcnow() + datetime.timedelta(days=1),
                ]
            ),
        )
        # when
        data = cost_breakdown_proc._get_ded_accumulation_sequential_treatment_procedure_data(
            member_health_plan=member_health_plan_now,
            before_this_date=datetime.datetime.utcnow(),
            should_include_pending=True,
        )

        # then
        procedures = [procedure for procedure, _ in data]
        assert valid_procedure in procedures
        assert invalid_procedure not in procedures

    def test_by_accumulation_status(
        self,
        ff_test_data,
        cost_breakdown_proc,
        member_health_plan_now,
    ):
        # given
        cost_breakdowns = CostBreakdownFactory.create_batch(size=5)
        treatment_procedures = TreatmentProcedureFactory.create_batch(
            size=5,
            member_id=member_health_plan_now.member_id,
            reimbursement_wallet_id=member_health_plan_now.reimbursement_wallet_id,
            cost_breakdown_id=factory.Iterator(
                [cost_breakdown.id for cost_breakdown in cost_breakdowns]
            ),
            status=TreatmentProcedureStatus.COMPLETED,
            created_at=datetime.datetime.utcnow() - datetime.timedelta(days=1),
        )
        mappings = AccumulationTreatmentMappingFactory.create_batch(
            size=5,
            treatment_procedure_uuid=factory.Iterator(
                [procedure.uuid for procedure in treatment_procedures]
            ),
            treatment_accumulation_status=factory.Iterator(
                [
                    TreatmentAccumulationStatus.PAID,
                    TreatmentAccumulationStatus.WAITING,
                    TreatmentAccumulationStatus.SUBMITTED,
                    TreatmentAccumulationStatus.ROW_ERROR,
                    TreatmentAccumulationStatus.REJECTED,
                ]
            ),
        )

        # when
        data = cost_breakdown_proc._get_ded_accumulation_sequential_treatment_procedure_data(
            member_health_plan=member_health_plan_now,
            before_this_date=datetime.datetime.utcnow(),
            should_include_pending=True,
        )

        # then
        assert len(data) == 4
        procedure_uuids = [procedure.uuid for procedure, _ in data]
        mapping_statuses = [
            mapping.treatment_accumulation_status
            for mapping in mappings
            if mapping.treatment_procedure_uuid in procedure_uuids
        ]
        # a SUBMITTED procedure should not be used in a calculation
        assert TreatmentAccumulationStatus.SUBMITTED not in mapping_statuses
        assert TreatmentAccumulationStatus.PAID in mapping_statuses
        assert TreatmentAccumulationStatus.WAITING in mapping_statuses
        assert TreatmentAccumulationStatus.ROW_ERROR in mapping_statuses
        assert TreatmentAccumulationStatus.REJECTED in mapping_statuses

    def test_by_procedure_status(
        self,
        ff_test_data,
        cost_breakdown_proc,
        member_health_plan_now,
    ):
        # given
        cost_breakdowns = CostBreakdownFactory.create_batch(size=3)
        TreatmentProcedureFactory.create_batch(
            size=3,
            member_id=member_health_plan_now.member_id,
            reimbursement_wallet_id=member_health_plan_now.reimbursement_wallet_id,
            cost_breakdown_id=factory.Iterator(
                [cost_breakdown.id for cost_breakdown in cost_breakdowns]
            ),
            status=factory.Iterator(
                [
                    TreatmentProcedureStatus.SCHEDULED,
                    TreatmentProcedureStatus.CANCELLED,
                    TreatmentProcedureStatus.COMPLETED,
                ]
            ),
            created_at=datetime.datetime.utcnow() - datetime.timedelta(days=1),
        )
        # when
        data = cost_breakdown_proc._get_ded_accumulation_sequential_treatment_procedure_data(
            member_health_plan=member_health_plan_now,
            before_this_date=datetime.datetime.utcnow(),
            should_include_pending=True,
        )

        # then
        assert len(data) == 2
        # CANCELLED should not be used in a calculation
        assert TreatmentProcedureStatus.CANCELLED not in [
            procedure.status for procedure, _ in data
        ]

    def test_extra_applied_amount(
        self,
        cost_breakdown_proc,
        member_health_plan_now,
    ):
        cost_breakdowns = CostBreakdownFactory.create_batch(size=3)
        procedures = TreatmentProcedureFactory.create_batch(
            size=3,
            member_id=member_health_plan_now.member_id,
            reimbursement_wallet_id=member_health_plan_now.reimbursement_wallet_id,
            cost_breakdown_id=factory.Iterator(
                [cost_breakdown.id for cost_breakdown in cost_breakdowns]
            ),
            status=factory.Iterator(
                [
                    TreatmentProcedureStatus.SCHEDULED,
                    TreatmentProcedureStatus.SCHEDULED,
                    TreatmentProcedureStatus.SCHEDULED,
                ]
            ),
            created_at=datetime.datetime.utcnow() - datetime.timedelta(days=1),
        )
        cost_breakdown_proc.extra_applied_amount = ExtraAppliedAmount(
            assumed_paid_procedures=[tp.id for tp in procedures[1:]]
        )
        data = cost_breakdown_proc._get_ded_accumulation_sequential_treatment_procedure_data(
            member_health_plan=member_health_plan_now,
            before_this_date=datetime.datetime.utcnow(),
            should_include_pending=True,
        )

        assert len(data) == 1

    def test_not_include_pending(
        self,
        ff_test_data,
        cost_breakdown_proc,
        member_health_plan_now,
    ):
        # given
        cost_breakdowns = CostBreakdownFactory.create_batch(size=3)
        TreatmentProcedureFactory.create_batch(
            size=3,
            member_id=member_health_plan_now.member_id,
            reimbursement_wallet_id=member_health_plan_now.reimbursement_wallet_id,
            cost_breakdown_id=factory.Iterator(
                [cost_breakdown.id for cost_breakdown in cost_breakdowns]
            ),
            status=factory.Iterator(
                [
                    TreatmentProcedureStatus.SCHEDULED,
                    TreatmentProcedureStatus.PARTIALLY_COMPLETED,
                    TreatmentProcedureStatus.COMPLETED,
                ]
            ),
            completed_date=factory.Iterator(
                [
                    None,
                    datetime.datetime.utcnow() - datetime.timedelta(days=1),
                    datetime.datetime.utcnow() - datetime.timedelta(days=2),
                ]
            ),
        )
        # when
        data = cost_breakdown_proc._get_ded_accumulation_sequential_treatment_procedure_data(
            member_health_plan=member_health_plan_now,
            before_this_date=datetime.datetime.utcnow(),
        )

        # then
        assert len(data) == 2
        # CANCELLED should not be used in a calculation
        assert TreatmentProcedureStatus.SCHEDULED not in [
            procedure.status for procedure, _ in data
        ]

    def test_by_member_health_plan_filter_by_individual_asof_date(
        self,
        enable_health_plan_feature,
        cost_breakdown_proc,
        member_health_plan_now,
        wallet_category,
        service_start_date,
    ):
        cost_breakdowns = CostBreakdownFactory.create_batch(size=2)
        valid_procedure, invalid_procedure = TreatmentProcedureFactory.create_batch(
            size=2,
            member_id=member_health_plan_now.member_id,
            reimbursement_wallet_id=member_health_plan_now.reimbursement_wallet_id,
            cost_breakdown_id=factory.Iterator(
                [cost_breakdown.id for cost_breakdown in cost_breakdowns]
            ),
            status=TreatmentProcedureStatus.SCHEDULED,
            created_at=service_start_date - datetime.timedelta(days=1),
            start_date=factory.Iterator(
                [
                    service_start_date,
                    datetime.datetime.utcnow() - datetime.timedelta(days=600),
                ]
            ),
        )
        # when
        data = cost_breakdown_proc._get_ded_accumulation_sequential_treatment_procedure_data(
            member_health_plan=member_health_plan_now,
            before_this_date=service_start_date,
            should_include_pending=True,
            family_effective_date=None,
        )

        # then
        procedures = [procedure for procedure, _ in data]
        assert valid_procedure in procedures
        assert invalid_procedure not in procedures

    def test_by_member_health_plan_filter_by_family_asof_date(
        self,
        cost_breakdown_proc,
        employer_health_plan,
        member_health_plan_now,
        wallet_category,
        service_start_date,
        enable_health_plan_feature,
    ):
        subscriber_wallet = member_health_plan_now.reimbursement_wallet
        dependent = EnterpriseUserFactory.create()
        ReimbursementWalletUsersFactory.create(
            user_id=dependent.id,
            reimbursement_wallet_id=subscriber_wallet.id,
            status=WalletUserStatus.ACTIVE,
            type=WalletUserType.DEPENDENT,
        )
        # Created 30 days ago
        dependent_health_plan = MemberHealthPlanFactory.create(
            reimbursement_wallet=subscriber_wallet,
            reimbursement_wallet_id=subscriber_wallet.id,
            employer_health_plan=employer_health_plan,
            plan_type=FamilyPlanType.FAMILY,
            is_subscriber=False,
            member_id=dependent.id,
            plan_start_at=datetime.datetime.utcnow() - datetime.timedelta(days=30),
            plan_end_at=datetime.datetime.utcnow() + datetime.timedelta(days=395),
        )

        cost_breakdowns = CostBreakdownFactory.create_batch(size=4)
        (
            valid_procedure_subscriber,
            invalid_procedure_subscriber,
            valid_procedure_dependent,
            invalid_procedure_dependent,
        ) = TreatmentProcedureFactory.create_batch(
            size=4,
            member_id=factory.Iterator(
                [
                    member_health_plan_now.member_id,
                    member_health_plan_now.member_id,
                    dependent_health_plan.member_id,
                    dependent_health_plan.member_id,
                ]
            ),
            reimbursement_wallet_id=member_health_plan_now.reimbursement_wallet_id,
            cost_breakdown_id=factory.Iterator(
                [cost_breakdown.id for cost_breakdown in cost_breakdowns]
            ),
            status=TreatmentProcedureStatus.COMPLETED,
            created_at=service_start_date - datetime.timedelta(days=90),
            start_date=factory.Iterator(
                [
                    service_start_date - datetime.timedelta(days=60),
                    datetime.datetime.utcnow() - datetime.timedelta(days=600),
                    service_start_date,
                    datetime.datetime.utcnow() - datetime.timedelta(days=600),
                ]
            ),
        )
        # when Passing in the family as of date includes the family procedures rather than filtering by the dependent
        # health plan
        data = cost_breakdown_proc._get_ded_accumulation_sequential_treatment_procedure_data(
            member_health_plan=dependent_health_plan,
            before_this_date=service_start_date,
            should_include_pending=True,
            family_effective_date=member_health_plan_now.plan_start_at,
        )

        # then
        procedures = set([procedure for procedure, _ in data])
        assert {valid_procedure_subscriber, valid_procedure_dependent} == procedures


class TestHDHPTreatmentProcedureData:
    # _get_scheduled_treatment_procedures_for_hdhp
    def test_no_data(self, cost_breakdown_proc, wallet, member_health_plan_now):
        data = cost_breakdown_proc._get_scheduled_treatment_procedures_for_hdhp(
            reimbursement_wallet_id=wallet.id,
            before_this_date=datetime.datetime.utcnow(),
            member_health_plan=member_health_plan_now,
        )
        assert data == []

    def test_no_cost_breakdown(
        self, cost_breakdown_proc, wallet, member_health_plan_now
    ):
        cost_breakdown = CostBreakdownFactory.create()
        (
            procedure_with_cost_breakdown,
            procedure_without_cost_breakdown,
        ) = TreatmentProcedureFactory.create_batch(
            size=2,
            reimbursement_wallet_id=wallet.id,
            status=TreatmentProcedureStatus.SCHEDULED,
            # Only return procedures with a joined cost breakdown id
            cost_breakdown_id=factory.Iterator([cost_breakdown.id, None]),
            created_at=datetime.datetime(2024, 1, 1),
        )

        # when
        data = cost_breakdown_proc._get_scheduled_treatment_procedures_for_hdhp(
            reimbursement_wallet_id=wallet.id,
            before_this_date=datetime.datetime(2024, 2, 1),
            member_health_plan=member_health_plan_now,
        )

        # then
        assert data == [(procedure_with_cost_breakdown, cost_breakdown)]

    def test_by_wallet(
        self,
        cost_breakdown_proc,
        wallet,
        wallet_deductible_accumulation,
        member_health_plan_now,
    ):
        cost_breakdowns = CostBreakdownFactory.create_batch(size=2)
        valid_procedure, invalid_procedure = TreatmentProcedureFactory.create_batch(
            size=2,
            # Only return procedures for the relevant wallet
            reimbursement_wallet_id=factory.Iterator(
                [wallet.id, wallet_deductible_accumulation.id]
            ),
            status=TreatmentProcedureStatus.SCHEDULED,
            cost_breakdown_id=factory.Iterator(
                [cost_breakdown.id for cost_breakdown in cost_breakdowns]
            ),
            created_at=datetime.datetime(2024, 1, 1),
        )

        # when
        data = cost_breakdown_proc._get_scheduled_treatment_procedures_for_hdhp(
            reimbursement_wallet_id=wallet.id,
            before_this_date=datetime.datetime(2024, 2, 1),
            member_health_plan=member_health_plan_now,
        )

        # then
        assert data == [(valid_procedure, cost_breakdowns[0])]

    def test_by_status(self, cost_breakdown_proc, wallet, member_health_plan_now):
        cost_breakdowns = CostBreakdownFactory.create_batch(size=2)
        valid_procedure, invalid_procedure = TreatmentProcedureFactory.create_batch(
            size=2,
            reimbursement_wallet_id=wallet.id,
            status=factory.Iterator(
                [TreatmentProcedureStatus.SCHEDULED, TreatmentProcedureStatus.COMPLETED]
            ),
            cost_breakdown_id=factory.Iterator(
                [cost_breakdown.id for cost_breakdown in cost_breakdowns]
            ),
            created_at=datetime.datetime(2024, 1, 1),
        )

        # when
        data = cost_breakdown_proc._get_scheduled_treatment_procedures_for_hdhp(
            reimbursement_wallet_id=wallet.id,
            before_this_date=datetime.datetime(2024, 2, 1),
            member_health_plan=member_health_plan_now,
        )

        # then
        assert data == [(valid_procedure, cost_breakdowns[0])]

    def test_by_member_health_plan_asof_date(
        self,
        cost_breakdown_proc,
        wallet,
        member_health_plan_now,
        enable_health_plan_feature,
    ):
        cost_breakdowns = CostBreakdownFactory.create_batch(size=2)
        valid_procedure, invalid_procedure = TreatmentProcedureFactory.create_batch(
            size=2,
            reimbursement_wallet_id=wallet.id,
            status=TreatmentProcedureStatus.SCHEDULED,
            cost_breakdown_id=factory.Iterator(
                [cost_breakdown.id for cost_breakdown in cost_breakdowns]
            ),
            created_at=datetime.datetime(2024, 1, 1),
            # Only return procedures for that fall within the member health plan dates
            start_date=factory.Iterator(
                [
                    datetime.datetime.utcnow(),
                    datetime.datetime.utcnow() - datetime.timedelta(days=600),
                ]
            ),
        )
        # when
        data = cost_breakdown_proc._get_scheduled_treatment_procedures_for_hdhp(
            reimbursement_wallet_id=wallet.id,
            before_this_date=datetime.datetime(2024, 2, 1),
            member_health_plan=member_health_plan_now,
            family_effective_date=None,
        )

        # then
        assert data == [(valid_procedure, cost_breakdowns[0])]

    def test_by_member_health_plan_family_asof_date(
        self,
        cost_breakdown_proc,
        wallet,
        member_health_plan_now,
        enable_health_plan_feature,
    ):
        cost_breakdowns = CostBreakdownFactory.create_batch(size=2)
        valid_procedure, invalid_procedure = TreatmentProcedureFactory.create_batch(
            size=2,
            reimbursement_wallet_id=wallet.id,
            status=TreatmentProcedureStatus.SCHEDULED,
            cost_breakdown_id=factory.Iterator(
                [cost_breakdown.id for cost_breakdown in cost_breakdowns]
            ),
            created_at=datetime.datetime(2024, 1, 1),
            # Only return procedures for that fall within the member health plan dates
            start_date=factory.Iterator(
                [
                    datetime.datetime.utcnow() - datetime.timedelta(days=60),
                    datetime.datetime.utcnow() - datetime.timedelta(days=600),
                ]
            ),
        )
        dependent = EnterpriseUserFactory.create()
        ReimbursementWalletUsersFactory.create(
            user_id=dependent.id,
            reimbursement_wallet_id=member_health_plan_now.reimbursement_wallet_id,
            status=WalletUserStatus.ACTIVE,
            type=WalletUserType.DEPENDENT,
        )
        # Created 30 days ago
        dependent_health_plan = MemberHealthPlanFactory.create(
            reimbursement_wallet=member_health_plan_now.reimbursement_wallet,
            reimbursement_wallet_id=member_health_plan_now.reimbursement_wallet_id,
            employer_health_plan=member_health_plan_now.employer_health_plan,
            plan_type=FamilyPlanType.FAMILY,
            is_subscriber=False,
            member_id=dependent.id,
            plan_start_at=datetime.datetime.utcnow() - datetime.timedelta(days=30),
            plan_end_at=datetime.datetime.utcnow() + datetime.timedelta(days=395),
        )
        dependent_cost_breakdowns = CostBreakdownFactory.create_batch(size=2)
        (
            dependent_valid_procedure,
            dependent_invalid_procedure,
        ) = TreatmentProcedureFactory.create_batch(
            size=2,
            reimbursement_wallet_id=wallet.id,
            status=TreatmentProcedureStatus.SCHEDULED,
            cost_breakdown_id=factory.Iterator(
                [cost_breakdown.id for cost_breakdown in dependent_cost_breakdowns]
            ),
            created_at=datetime.datetime(2024, 1, 1),
            # Only return procedures for that fall within the member health plan dates
            start_date=factory.Iterator(
                [
                    datetime.datetime.utcnow(),
                    datetime.datetime.utcnow() - datetime.timedelta(days=600),
                ]
            ),
        )
        # when
        data = cost_breakdown_proc._get_scheduled_treatment_procedures_for_hdhp(
            reimbursement_wallet_id=wallet.id,
            before_this_date=datetime.datetime(2024, 2, 1),
            member_health_plan=dependent_health_plan,
            family_effective_date=member_health_plan_now.plan_start_at,
        )

        # then
        procedures = set([procedure for procedure, _ in data])
        assert {valid_procedure, dependent_valid_procedure} == procedures


class TestHDHPReimbursementRequestData:
    # _get_scheduled_reimbursement_requests_for_hdhp
    def test_no_data(
        self, cost_breakdown_proc, wallet, service_start_date, member_health_plan_now
    ):
        data = cost_breakdown_proc._get_scheduled_reimbursement_requests_for_hdhp(
            reimbursement_wallet_id=wallet.id,
            before_this_date=service_start_date,
            member_health_plan=member_health_plan_now,
        )
        assert data == []

    def test_no_cost_breakdown(
        self,
        cost_breakdown_proc,
        wallet,
        wallet_category,
        service_start_date,
        member_health_plan_now,
    ):
        (
            valid_reimbursement_request,
            invalid_reimbursement_request,
        ) = ReimbursementRequestFactory.create_batch(
            size=2,
            wallet=wallet,
            category=wallet_category,
            state=ReimbursementRequestState.NEW,
            service_start_date=service_start_date - datetime.timedelta(days=1),
        )
        cost_breakdown = CostBreakdownFactory.create(
            reimbursement_request_id=valid_reimbursement_request.id
        )

        # when
        data = cost_breakdown_proc._get_scheduled_reimbursement_requests_for_hdhp(
            reimbursement_wallet_id=wallet.id,
            before_this_date=service_start_date,
            member_health_plan=member_health_plan_now,
            should_include_pending=True,
        )

        # then
        assert data == [(valid_reimbursement_request, cost_breakdown)]

    def test_by_wallet(
        self,
        cost_breakdown_proc,
        wallet,
        wallet_deductible_accumulation,
        wallet_category,
        service_start_date,
        member_health_plan_now,
    ):
        (
            valid_reimbursement_request,
            invalid_reimbursement_request,
        ) = ReimbursementRequestFactory.create_batch(
            size=2,
            wallet=factory.Iterator([wallet, wallet_deductible_accumulation]),
            category=wallet_category,
            state=ReimbursementRequestState.NEW,
            service_start_date=service_start_date - datetime.timedelta(days=1),
        )
        cost_breakdown, invalid_cost_breakdown = CostBreakdownFactory.create_batch(
            size=2,
            reimbursement_request_id=factory.Iterator(
                [valid_reimbursement_request.id, invalid_reimbursement_request.id]
            ),
        )

        # when
        data = cost_breakdown_proc._get_scheduled_reimbursement_requests_for_hdhp(
            reimbursement_wallet_id=wallet.id,
            before_this_date=service_start_date,
            member_health_plan=member_health_plan_now,
            should_include_pending=True,
        )

        # then
        assert data == [(valid_reimbursement_request, cost_breakdown)]

    def test_by_state(
        self,
        cost_breakdown_proc,
        wallet,
        wallet_category,
        service_start_date,
        member_health_plan_now,
    ):
        valid_reimbursement_requests = ReimbursementRequestFactory.create_batch(
            size=2,
            wallet=wallet,
            category=wallet_category,
            state=factory.Iterator(
                [ReimbursementRequestState.NEW, ReimbursementRequestState.PENDING]
            ),
            service_start_date=service_start_date - datetime.timedelta(days=1),
        )
        CostBreakdownFactory.create_batch(
            size=2,
            reimbursement_request_id=factory.Iterator(
                [
                    reimbursement_request.id
                    for reimbursement_request in valid_reimbursement_requests
                ]
            ),
        )
        denied_reimbursement_request = ReimbursementRequestFactory.create(
            wallet=wallet,
            category=wallet_category,
            state=ReimbursementRequestState.DENIED,
            service_start_date=service_start_date - datetime.timedelta(days=1),
            amount=100_00,
        )
        CostBreakdownFactory.create(
            reimbursement_request_id=denied_reimbursement_request.id,
            total_member_responsibility=denied_reimbursement_request.amount,
            total_employer_responsibility=0,
        )

        ReimbursementRequestFactory.create_batch(
            size=2,
            wallet=wallet,
            category=wallet_category,
            # invalid status reimbursement requests
            state=factory.Iterator(
                [
                    ReimbursementRequestState.APPROVED,
                    ReimbursementRequestState.NEEDS_RECEIPT,
                ]
            ),
            service_start_date=service_start_date - datetime.timedelta(days=1),
        )

        # when
        data = cost_breakdown_proc._get_scheduled_reimbursement_requests_for_hdhp(
            reimbursement_wallet_id=wallet.id,
            before_this_date=service_start_date,
            member_health_plan=member_health_plan_now,
            should_include_pending=True,
        )

        requests = {request for request, _ in data}
        assert requests == set(valid_reimbursement_requests)

    def test_by_date(
        self,
        cost_breakdown_proc,
        wallet,
        wallet_category,
        service_start_date,
        member_health_plan_now,
    ):
        past_rr, future_rr = ReimbursementRequestFactory.create_batch(
            size=2,
            wallet=wallet,
            category=wallet_category,
            state=ReimbursementRequestState.NEW,
            service_start_date=factory.Iterator(
                [
                    service_start_date - datetime.timedelta(hours=1),
                    service_start_date + datetime.timedelta(hours=1),
                ]
            ),
        )
        cost_breakdowns = CostBreakdownFactory.create_batch(
            size=2,
            wallet_id=wallet.id,
            reimbursement_request_id=factory.Iterator([past_rr.id, future_rr.id]),
        )

        # when
        data = cost_breakdown_proc._get_scheduled_reimbursement_requests_for_hdhp(
            reimbursement_wallet_id=wallet.id,
            before_this_date=service_start_date,
            member_health_plan=member_health_plan_now,
            should_include_pending=True,
        )

        assert past_rr.service_start_date < service_start_date
        assert data == [(past_rr, cost_breakdowns[0])]

    def test_by_member_health_plan_asof_date(
        self,
        cost_breakdown_proc,
        wallet,
        wallet_category,
        service_start_date,
        member_health_plan_now,
        enable_health_plan_feature,
    ):
        (
            valid_reimbursement_request,
            invalid_reimbursement_request,
        ) = ReimbursementRequestFactory.create_batch(
            size=2,
            wallet=wallet,
            category=wallet_category,
            state=ReimbursementRequestState.NEW,
            service_start_date=factory.Iterator(
                [
                    service_start_date - datetime.timedelta(days=1),
                    service_start_date - datetime.timedelta(days=600),
                ]
            ),
        )
        cost_breakdown, invalid_cost_breakdown = CostBreakdownFactory.create_batch(
            size=2,
            reimbursement_request_id=factory.Iterator(
                [valid_reimbursement_request.id, invalid_reimbursement_request.id]
            ),
        )
        # when
        data = cost_breakdown_proc._get_scheduled_reimbursement_requests_for_hdhp(
            reimbursement_wallet_id=wallet.id,
            before_this_date=service_start_date,
            member_health_plan=member_health_plan_now,
            should_include_pending=True,
            family_effective_date=None,
        )
        # then
        assert data == [(valid_reimbursement_request, cost_breakdown)]

    def test_by_member_health_plan_family_asof_date(
        self,
        cost_breakdown_proc,
        wallet,
        wallet_category,
        service_start_date,
        member_health_plan_now,
        enable_health_plan_feature,
    ):
        (
            valid_reimbursement_request,
            invalid_reimbursement_request,
        ) = ReimbursementRequestFactory.create_batch(
            size=2,
            wallet=wallet,
            category=wallet_category,
            state=ReimbursementRequestState.NEW,
            service_start_date=factory.Iterator(
                [
                    service_start_date - datetime.timedelta(days=60),
                    service_start_date - datetime.timedelta(days=600),
                ]
            ),
        )
        CostBreakdownFactory.create_batch(
            size=2,
            reimbursement_request_id=factory.Iterator(
                [valid_reimbursement_request.id, invalid_reimbursement_request.id]
            ),
        )

        dependent = EnterpriseUserFactory.create()
        ReimbursementWalletUsersFactory.create(
            user_id=dependent.id,
            reimbursement_wallet_id=member_health_plan_now.reimbursement_wallet_id,
            status=WalletUserStatus.ACTIVE,
            type=WalletUserType.DEPENDENT,
        )
        # Created 30 days ago
        dependent_health_plan = MemberHealthPlanFactory.create(
            reimbursement_wallet=member_health_plan_now.reimbursement_wallet,
            reimbursement_wallet_id=member_health_plan_now.reimbursement_wallet_id,
            employer_health_plan=member_health_plan_now.employer_health_plan,
            plan_type=FamilyPlanType.FAMILY,
            is_subscriber=False,
            member_id=dependent.id,
            plan_start_at=datetime.datetime.utcnow() - datetime.timedelta(days=30),
            plan_end_at=datetime.datetime.utcnow() + datetime.timedelta(days=395),
        )
        (
            valid_dependent_reimbursement_request,
            invalid_dependent_reimbursement_request,
        ) = ReimbursementRequestFactory.create_batch(
            size=2,
            wallet=wallet,
            category=wallet_category,
            state=ReimbursementRequestState.NEW,
            service_start_date=factory.Iterator(
                [
                    service_start_date - datetime.timedelta(days=1),
                    service_start_date - datetime.timedelta(days=600),
                ]
            ),
        )
        CostBreakdownFactory.create_batch(
            size=2,
            reimbursement_request_id=factory.Iterator(
                [
                    valid_dependent_reimbursement_request.id,
                    invalid_dependent_reimbursement_request.id,
                ]
            ),
        )
        # when
        data = cost_breakdown_proc._get_scheduled_reimbursement_requests_for_hdhp(
            reimbursement_wallet_id=wallet.id,
            before_this_date=service_start_date,
            member_health_plan=dependent_health_plan,
            should_include_pending=True,
            family_effective_date=member_health_plan_now.plan_start_at,
        )
        # then
        reimbursement_requests = set([rr for rr, _ in data])
        assert {
            valid_reimbursement_request,
            valid_dependent_reimbursement_request,
        } == reimbursement_requests
