import datetime
from datetime import date
from decimal import Decimal
from typing import List
from unittest.mock import patch

import factory
import pytest
from maven import feature_flags

from cost_breakdown.constants import ClaimType
from cost_breakdown.errors import WalletBalanceReimbursementsException
from cost_breakdown.models.cost_breakdown import ReimbursementRequestToCostBreakdown
from cost_breakdown.pytests.factories import (
    CostBreakdownFactory,
    ReimbursementRequestToCostBreakdownFactory,
)
from cost_breakdown.wallet_balance_reimbursements import (
    _generate_direct_billing_reimbursement_request,
    add_back_balance,
    deduct_balance,
)
from direct_payment.clinic.pytests.factories import FertilityClinicFactory
from direct_payment.treatment_procedure.models.treatment_procedure import (
    TreatmentProcedureStatus,
)
from direct_payment.treatment_procedure.pytests.factories import (
    TreatmentProcedureFactory,
)
from wallet.models.constants import (
    FamilyPlanType,
    ReimbursementRequestState,
    ReimbursementRequestType,
    WalletState,
)
from wallet.models.reimbursement import ReimbursementRequest
from wallet.models.reimbursement_wallet_user import ReimbursementWalletUsers
from wallet.pytests.factories import (
    EmployerHealthPlanFactory,
    MemberHealthPlanFactory,
    ReimbursementRequestFactory,
)
from wallet.repository.health_plan import HEALTH_PLAN_YOY_FLAG, NEW_BEHAVIOR


@pytest.fixture()
def enable_new_health_plan_behavior():
    with feature_flags.test_data() as ff_test_data:
        ff_test_data.update(
            ff_test_data.flag(HEALTH_PLAN_YOY_FLAG).variations(NEW_BEHAVIOR)
        )
        yield ff_test_data


@pytest.mark.parametrize(
    "responsibilities, hra_applied, expected_amount,expected_balance_change",
    [
        ([10], 0, 10, 10),
        ([10], 1, 9, 9),
        ([10, 30], 0, 20, 30),
        ([10, 30, 20], 0, -10, 20),
    ],
)
def test_deduct_balance_employer(
    wallet,
    wallet_category,
    responsibilities,
    hra_applied,
    expected_amount,
    expected_balance_change,
):
    treatment_procedure = TreatmentProcedureFactory.create(
        member_id=wallet.user_id,
        reimbursement_request_category=wallet_category,
        start_date=date.today(),
        status=TreatmentProcedureStatus.COMPLETED,
    )
    cost_breakdowns = CostBreakdownFactory.create_batch(
        size=len(responsibilities),
        treatment_procedure_uuid=treatment_procedure.uuid,
        wallet_id=wallet.id,
        member_id=wallet.user_id,
        total_employer_responsibility=factory.Iterator(responsibilities),
        hra_applied=hra_applied,
    )
    initial_balance = wallet.available_currency_amount_by_category[
        treatment_procedure.reimbursement_request_category_id
    ]

    for cost_breakdown in cost_breakdowns:
        with patch(
            "cost_breakdown.wallet_balance_reimbursements._create_direct_payment_claim"
        ):
            success = deduct_balance(treatment_procedure, cost_breakdown, wallet)
            assert success

            # one mapping per cost breakdown
            rr_c_b_mappings: List[
                ReimbursementRequestToCostBreakdown
            ] = ReimbursementRequestToCostBreakdown.query.filter(
                ReimbursementRequestToCostBreakdown.cost_breakdown_id
                == cost_breakdown.id
            ).all()
            assert len(rr_c_b_mappings) == 1
            rr_c_b_mapping = rr_c_b_mappings[0]
            assert (
                cost_breakdown.treatment_procedure_uuid
                == rr_c_b_mapping.treatment_procedure_uuid
            )
            assert cost_breakdown.id == rr_c_b_mapping.cost_breakdown_id
            assert ClaimType.EMPLOYER == rr_c_b_mapping.claim_type

    # pops disable primitive_threaded_cached_property on the available_currency_amount_by_category property
    wallet.__dict__.pop("approved_amount_by_category")
    wallet.__dict__.pop("available_currency_amount_by_category")
    wallet.__dict__.pop("approved_amounts")
    current_balance = wallet.available_currency_amount_by_category[
        treatment_procedure.reimbursement_request_category_id
    ]

    # check on the last reimbursement request
    reimbursement_request: ReimbursementRequest = ReimbursementRequest.query.get(
        rr_c_b_mapping.reimbursement_request_id
    )
    assert reimbursement_request.amount == expected_amount
    assert (
        reimbursement_request.reimbursement_type
        == ReimbursementRequestType.DIRECT_BILLING
    )
    assert reimbursement_request.state == ReimbursementRequestState.APPROVED
    assert (initial_balance - expected_balance_change) == current_balance


def test_deduct_balance_with_incomplete_treatment_procedure(
    cost_breakdown, wallet, wallet_category
):
    treatment_procedure = TreatmentProcedureFactory.create(
        member_id=wallet.user_id,
        reimbursement_request_category=wallet_category,
        start_date=date.today(),
        status=TreatmentProcedureStatus.SCHEDULED,
    )
    previous_balance = wallet.available_currency_amount_by_category[
        treatment_procedure.reimbursement_request_category_id
    ]
    cost_breakdown.total_employer_responsibility = 1

    success = deduct_balance(treatment_procedure, cost_breakdown, wallet)
    wallet.__dict__.pop("approved_amount_by_category")
    wallet.__dict__.pop("available_currency_amount_by_category")
    wallet.__dict__.pop("approved_amounts")
    current_balance = wallet.available_currency_amount_by_category[
        treatment_procedure.reimbursement_request_category_id
    ]

    reimbursement_request_cost_breakdown_mappings: List[
        ReimbursementRequestToCostBreakdown
    ] = ReimbursementRequestToCostBreakdown.query.filter(
        ReimbursementRequestToCostBreakdown.cost_breakdown_id == cost_breakdown.id
    ).all()

    assert len(reimbursement_request_cost_breakdown_mappings) == 0
    assert previous_balance == current_balance
    assert success


def test_deduct_balance_cycle(
    treatment_procedure, cost_breakdown, wallet_cycle_based, global_procedure
):
    wallet_cycle_based.state = WalletState.QUALIFIED
    with patch(
        "common.global_procedures.procedure.ProcedureService.get_procedure_by_id",
        return_value=global_procedure,
    ):
        # Given
        request_category = wallet_cycle_based.reimbursement_organization_settings.allowed_reimbursement_categories[
            0
        ].reimbursement_request_category
        wallet_user = ReimbursementWalletUsers.query.filter(
            ReimbursementWalletUsers.reimbursement_wallet_id == wallet_cycle_based.id
        ).one()
        treatment_procedure = TreatmentProcedureFactory.create(
            member_id=wallet_user.user_id,
            fertility_clinic=FertilityClinicFactory(),
            reimbursement_request_category=request_category,
            start_date=date.today(),
            status=TreatmentProcedureStatus.COMPLETED,
            cost=global_procedure["credits"],
            cost_credit=5,
        )
        cost_breakdown.total_employer_responsibility = 1
        previous_balance = wallet_cycle_based.available_credit_amount_by_category[
            treatment_procedure.reimbursement_request_category_id
        ]

        # When
        success = deduct_balance(
            treatment_procedure, cost_breakdown, wallet_cycle_based
        )

        # Then
        wallet_cycle_based.__dict__.pop("available_credit_amount_by_category")
        current_balance = wallet_cycle_based.available_credit_amount_by_category[
            treatment_procedure.reimbursement_request_category_id
        ]

        reimbursement_request_cost_breakdown_mappings: List[
            ReimbursementRequestToCostBreakdown
        ] = ReimbursementRequestToCostBreakdown.query.filter(
            ReimbursementRequestToCostBreakdown.cost_breakdown_id == cost_breakdown.id
        ).all()

        assert len(reimbursement_request_cost_breakdown_mappings) == 1
        reimbursement_request_cost_breakdown_mapping = (
            reimbursement_request_cost_breakdown_mappings[0]
        )

        assert (
            cost_breakdown.treatment_procedure_uuid
            == reimbursement_request_cost_breakdown_mapping.treatment_procedure_uuid
        )
        assert (
            cost_breakdown.id
            == reimbursement_request_cost_breakdown_mapping.cost_breakdown_id
        )
        assert (
            ClaimType.EMPLOYER
            == reimbursement_request_cost_breakdown_mapping.claim_type
        )

        assert (previous_balance - treatment_procedure.cost_credit) == current_balance
        assert success


def test_deduct_balance_cycle_zero(
    treatment_procedure, cost_breakdown, wallet_cycle_based, global_procedure
):
    wallet_cycle_based.state = WalletState.QUALIFIED
    with patch(
        "common.global_procedures.procedure.ProcedureService.get_procedure_by_id",
        return_value=global_procedure,
    ):
        # Given
        request_category = wallet_cycle_based.reimbursement_organization_settings.allowed_reimbursement_categories[
            0
        ].reimbursement_request_category
        wallet_user = ReimbursementWalletUsers.query.filter(
            ReimbursementWalletUsers.reimbursement_wallet_id == wallet_cycle_based.id
        ).one()
        treatment_procedure = TreatmentProcedureFactory.create(
            member_id=wallet_user.user_id,
            fertility_clinic=FertilityClinicFactory(),
            reimbursement_request_category=request_category,
            start_date=date.today(),
            status=TreatmentProcedureStatus.COMPLETED,
            cost=global_procedure["credits"],
            cost_credit=0,
        )
        cost_breakdown.total_employer_responsibility = 1
        previous_balance = wallet_cycle_based.available_credit_amount_by_category[
            treatment_procedure.reimbursement_request_category_id
        ]

        # When
        success = deduct_balance(
            treatment_procedure, cost_breakdown, wallet_cycle_based
        )

        # Then
        wallet_cycle_based.__dict__.pop("available_credit_amount_by_category")
        current_balance = wallet_cycle_based.available_credit_amount_by_category[
            treatment_procedure.reimbursement_request_category_id
        ]

        assert previous_balance == current_balance
        assert success


@pytest.mark.parametrize(
    argnames="ros__deductible_accumulation_enabled,"
    "ehp__is_hdhp,"
    "cb__employer_responsibility,"
    "cb__member_responsibility,"
    "cb__deductible,"
    "expected_number_of_reimbursement_requests_and_claims",
    argvalues=[
        pytest.param(
            True,
            True,
            4_000_00,
            6_000_00,
            6_000_00,
            1,
            id="DA w/ HDHP, Benefit spend, Deductible spend => 1 RR",
        ),
        pytest.param(
            True,
            True,
            0,
            10_000_00,
            6_000_00,
            0,
            id="DA w/ HDHP, No Benefit spend, Deductible spend => 0 RR",
        ),
        pytest.param(
            True,
            False,
            4_000_00,
            6_000_00,
            6_000_00,
            1,
            id="DA w/o HDHP, Benefit spend, Deductible spend => 1 RR",
        ),
        pytest.param(
            True,
            False,
            0,
            10_000_00,
            6_000_00,
            0,
            id="DA w/o HDHP, No Benefit spend, Deductible spend => 0 RR",
        ),
        pytest.param(
            False,
            True,
            4_000_00,
            6_000_00,
            6_000_00,
            2,
            id="Non-DA w/ HDHP, Benefit spend, Deductible spend => 2 RR",
        ),
        pytest.param(
            False,
            True,
            0,
            10_000_00,
            6_000_00,
            1,
            id="Non-DA w/ HDHP, No Benefit spend, Deductible spend => 1 RR",
        ),
        pytest.param(
            False,
            True,
            4_000_00,
            6_000_00,
            0,
            1,
            id="Non-DA w/ HDHP, Benefit spend, No Deductible spend => 1 RR",
        ),
        pytest.param(
            False,
            True,
            0,
            10_000_00,
            0,
            0,
            id="Non-DA w/ HDHP, No Benefit spend, No Deductible spend => 0 RR",
        ),
        pytest.param(
            False,
            False,
            4_000_00,
            6_000_00,
            6_000_00,
            1,
            id="Non-DA w/o HDHP, Benefit spend, Deductible spend => 1 RR",
        ),
        pytest.param(
            False,
            False,
            0,
            10_000_00,
            6_000_00,
            0,
            id="Non-DA w/o HDHP, No Benefit spend, Deductible spend => 0 RR",
        ),
        pytest.param(
            False,
            False,
            4_000_00,
            6_000_00,
            0,
            1,
            id="Non-DA w/o HDHP, Benefit spend, No Deductible spend => 1 RR",
        ),
        pytest.param(
            False,
            False,
            0,
            10_000_00,
            0,
            0,
            id="Non-DA w/o HDHP, No Benefit spend, No Deductible spend => 0 RR",
        ),
    ],
)
def test_deduct_balance__reimbursement_requests_and_claims(
    direct_payment_wallet,
    employer_health_plan_cost_sharing,
    ros__deductible_accumulation_enabled,
    ehp__is_hdhp,
    cb__employer_responsibility,
    cb__member_responsibility,
    cb__deductible,
    expected_number_of_reimbursement_requests_and_claims,
    enable_new_health_plan_behavior,
):
    wallet = direct_payment_wallet
    wallet.reimbursement_organization_settings.deductible_accumulation_enabled = (
        ros__deductible_accumulation_enabled
    )

    employer_health_plan = EmployerHealthPlanFactory.create(
        reimbursement_organization_settings=wallet.reimbursement_organization_settings,
        cost_sharings=employer_health_plan_cost_sharing,
        is_hdhp=ehp__is_hdhp,
    )

    MemberHealthPlanFactory.create(
        reimbursement_wallet=wallet,
        employer_health_plan=employer_health_plan,
        plan_type=FamilyPlanType.INDIVIDUAL,
        is_subscriber=True,
        plan_start_at=datetime.datetime(year=2020, month=1, day=1),
    )

    category = (
        wallet.reimbursement_organization_settings.allowed_reimbursement_categories[
            0
        ].reimbursement_request_category
    )

    treatment_procedure = TreatmentProcedureFactory.create(
        member_id=wallet.user_id,
        reimbursement_wallet_id=wallet.id,
        reimbursement_request_category=category,
        cost=10_000_00,
        status=TreatmentProcedureStatus.COMPLETED,
        start_date=datetime.date(year=2024, month=1, day=1),
    )

    cost_breakdown = CostBreakdownFactory.create(
        treatment_procedure_uuid=treatment_procedure.uuid,
        wallet_id=wallet.id,
        total_member_responsibility=cb__member_responsibility,
        total_employer_responsibility=cb__employer_responsibility,
        deductible=cb__deductible,
    )

    with patch(
        "cost_breakdown.wallet_balance_reimbursements.create_direct_payment_claim_in_alegeus"
    ) as mock_create_claim:
        deduct_balance(treatment_procedure, cost_breakdown, wallet)
        reimbursement_requests = (
            ReimbursementRequest.query.filter(ReimbursementRequest.wallet == wallet)
            .filter(ReimbursementRequest.category == category)
            .filter(
                ReimbursementRequest.reimbursement_type
                == ReimbursementRequestType.DIRECT_BILLING
            )
            .all()
        )

        assert (
            len(reimbursement_requests)
            == expected_number_of_reimbursement_requests_and_claims
        )
        assert (
            mock_create_claim.call_count
            == expected_number_of_reimbursement_requests_and_claims
        )


def test_deduct_balance_negative_claim_handling(direct_payment_wallet):
    # https://mavenclinic.atlassian.net/browse/PAY-5391
    # given
    employer_health_plan = EmployerHealthPlanFactory.create(
        reimbursement_organization_settings=direct_payment_wallet.reimbursement_organization_settings,
        cost_sharings=[],
        is_hdhp=True,
    )
    MemberHealthPlanFactory.create(
        reimbursement_wallet=direct_payment_wallet,
        employer_health_plan=employer_health_plan,
        plan_start_at=datetime.datetime(year=2020, month=1, day=1),
    )
    category_association = (
        direct_payment_wallet.get_or_create_wallet_allowed_categories[0]
    )
    direct_payment_wallet.reimbursement_organization_settings.deductible_accumulation_enabled = (
        False
    )
    treatment_procedure = TreatmentProcedureFactory.create(
        status=TreatmentProcedureStatus.COMPLETED,
        member_id=direct_payment_wallet.user_id,
        reimbursement_request_category=category_association.reimbursement_request_category,
    )
    cost_breakdown = CostBreakdownFactory.create(
        treatment_procedure_uuid=treatment_procedure.uuid,
        deductible=0,
        total_employer_responsibility=0,
    )
    previous_cost_breakdown = CostBreakdownFactory.create(
        treatment_procedure_uuid=treatment_procedure.uuid,
        deductible=1835,
        total_employer_responsibility=0,
    )

    # when
    with patch(
        "cost_breakdown.wallet_balance_reimbursements._get_previous_cost_breakdown_with_reimbursement_requests",
        return_value=(previous_cost_breakdown, True),
    ), patch(
        "cost_breakdown.wallet_balance_reimbursements._create_direct_payment_claim"
    ) as create_claim:
        deduct_balance(
            cost_breakdown=cost_breakdown,
            treatment_procedure=treatment_procedure,
            wallet=direct_payment_wallet,
        )

    # then
    created_reimbursement_request = (
        ReimbursementRequest.query.join(
            ReimbursementRequestToCostBreakdown,
            ReimbursementRequestToCostBreakdown.reimbursement_request_id
            == ReimbursementRequest.id,
        )
        .filter(
            ReimbursementRequestToCostBreakdown.cost_breakdown_id == cost_breakdown.id,
        )
        .one()
    )
    assert created_reimbursement_request.amount == -1835
    # negative amount claims not submitted to alegeus
    assert create_claim.call_count == 0


def test_generate_direct_billing_reimbursement_request_populates_currency_fields(
    user_for_direct_payment_wallet, direct_payment_wallet
):
    # Given
    category_association = (
        direct_payment_wallet.get_or_create_wallet_allowed_categories[0]
    )
    treatment_procedure = TreatmentProcedureFactory.create(
        status=TreatmentProcedureStatus.COMPLETED,
        member_id=user_for_direct_payment_wallet.id,
        reimbursement_request_category=category_association.reimbursement_request_category,
    )
    clinic = FertilityClinicFactory()
    state = ReimbursementRequestState.APPROVED
    amount = 12345
    expected_rate = Decimal("1.00")

    # When
    generated: ReimbursementRequest = _generate_direct_billing_reimbursement_request(
        treatment_procedure=treatment_procedure,
        clinic=clinic,
        member=user_for_direct_payment_wallet,
        wallet=direct_payment_wallet,
        amount=amount,
        state=state,
    )

    # Then
    assert (
        generated.amount,
        generated.transaction_amount,
        generated.usd_amount,
        generated.benefit_currency_code,
        generated.transaction_currency_code,
        generated.transaction_to_benefit_rate,
        generated.transaction_to_usd_rate,
    ) == (amount, amount, amount, "USD", "USD", expected_rate, expected_rate)


class TestAddBackBalance:
    def test_procedure_not_completed(
        self, user_for_direct_payment_wallet, direct_payment_wallet
    ):
        # Given
        treatment_procedure = TreatmentProcedureFactory.create(
            status=TreatmentProcedureStatus.SCHEDULED,
            member_id=user_for_direct_payment_wallet.id,
        )
        with pytest.raises(WalletBalanceReimbursementsException):
            add_back_balance(treatment_procedure)

    def test_reimbursement_request_success(self, direct_payment_wallet):
        category = direct_payment_wallet.reimbursement_organization_settings.allowed_reimbursement_categories[
            0
        ].reimbursement_request_category
        reimbursement_requests = ReimbursementRequestFactory.create_batch(
            size=2,
            wallet=direct_payment_wallet,
            category=category,
            amount=factory.Iterator([4000, 75000]),
            transaction_amount=factory.Iterator([4000, 75000]),
            usd_amount=factory.Iterator([4000, 75000]),
            state=ReimbursementRequestState.APPROVED,
        )
        cb = CostBreakdownFactory.create()
        treatment_procedure = TreatmentProcedureFactory.create(
            status=TreatmentProcedureStatus.COMPLETED,
            cost_breakdown_id=cb.id,
            reimbursement_wallet_id=direct_payment_wallet.id,
        )
        ReimbursementRequestToCostBreakdownFactory.create_batch(
            size=2,
            claim_type=factory.Iterator(
                [ClaimType.EMPLOYEE_DEDUCTIBLE, ClaimType.EMPLOYER]
            ),
            treatment_procedure_uuid=treatment_procedure.uuid,
            reimbursement_request_id=factory.Iterator(
                [reimbursement_requests[0].id, reimbursement_requests[1].id]
            ),
            cost_breakdown_id=cb.id,
        )
        add_back_balance(treatment_procedure)
        reimbursement_requests = ReimbursementRequest.query.all()
        assert sum(rr.amount for rr in reimbursement_requests) == 0
        rr_to_cbs = ReimbursementRequestToCostBreakdown.query.all()
        assert len(rr_to_cbs) == 4

    def test_already_refunded(self, direct_payment_wallet):
        category = direct_payment_wallet.reimbursement_organization_settings.allowed_reimbursement_categories[
            0
        ].reimbursement_request_category
        reimbursement_requests = ReimbursementRequestFactory.create_batch(
            size=4,
            wallet=direct_payment_wallet,
            category=category,
            amount=factory.Iterator([4000, 75000, -4000, -75000]),
            transaction_amount=factory.Iterator([4000, 75000, -4000, -75000]),
            usd_amount=factory.Iterator([4000, 75000, -4000, -75000]),
            state=ReimbursementRequestState.APPROVED,
        )
        cb = CostBreakdownFactory.create()
        treatment_procedure = TreatmentProcedureFactory.create(
            status=TreatmentProcedureStatus.COMPLETED,
            cost_breakdown_id=cb.id,
            reimbursement_wallet_id=direct_payment_wallet.id,
        )
        ReimbursementRequestToCostBreakdownFactory.create_batch(
            size=4,
            claim_type=factory.Iterator(
                [ClaimType.EMPLOYEE_DEDUCTIBLE, ClaimType.EMPLOYER]
            ),
            treatment_procedure_uuid=treatment_procedure.uuid,
            reimbursement_request_id=factory.Iterator(
                [rr.id for rr in reimbursement_requests]
            ),
            cost_breakdown_id=cb.id,
        )
        with pytest.raises(WalletBalanceReimbursementsException):
            add_back_balance(treatment_procedure)
