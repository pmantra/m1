import datetime
from unittest import mock

import pytest
from maven.feature_flags import test_data

from cost_breakdown.pytests.factories import CostBreakdownFactory
from direct_payment.billing.models import BillStatus, PayorType
from direct_payment.billing.pytests import factories
from direct_payment.clinic.pytests.factories import FertilityClinicLocationFactory
from direct_payment.payments.estimates_helper import (
    ESTIMATED_BOILERPLATE,
    EstimateMissingCriticalDataException,
    EstimatesHelper,
)
from direct_payment.payments.models import (
    EstimateBreakdown,
    EstimateDetail,
    EstimateSummaryForReimbursementWallet,
    LabelCost,
)
from direct_payment.treatment_procedure.models.treatment_procedure import (
    TreatmentProcedureStatus,
)
from direct_payment.treatment_procedure.pytests.factories import (
    TreatmentProcedureFactory,
)

# TODO @Rajneesh Remove the mocks from this test


@pytest.fixture(scope="function")
def estimates_helper(session):
    return EstimatesHelper(session=session)


@pytest.fixture(scope="function")
def estimates_bills():
    bills = [
        factories.BillFactory.build(
            procedure_id=4,
            amount=20000,
            cost_breakdown_id=2,
            payor_type=PayorType.MEMBER,
            payor_id=5,
            status=BillStatus.NEW,
            processing_scheduled_at_or_after=None,
            created_at=datetime.datetime.strptime("12/15/2018 00:00", "%m/%d/%Y %H:%M"),
            payment_method_label="4242",
        ),
        factories.BillFactory.build(
            procedure_id=5,
            amount=2000,
            cost_breakdown_id=3,
            payor_type=PayorType.MEMBER,
            payor_id=5,
            status=BillStatus.NEW,
            processing_scheduled_at_or_after=None,
            created_at=datetime.datetime.strptime("12/11/2018 00:00", "%m/%d/%Y %H:%M"),
            payment_method_label="4242",
        ),
        factories.BillFactory.build(
            uuid="40ec6e28-3c66-4880-b7cc-0b30a67e90b4",
            procedure_id=5,
            amount=8000,
            cost_breakdown_id=3,
            payor_type=PayorType.MEMBER,
            payor_id=5,
            status=BillStatus.NEW,
            processing_scheduled_at_or_after=None,
            created_at=datetime.datetime.strptime("12/10/2018 00:00", "%m/%d/%Y %H:%M"),
            payment_method_label="4242",
        ),
        factories.BillFactory.build(
            procedure_id=6,
            amount=2000,
            cost_breakdown_id=4,
            payor_type=PayorType.MEMBER,
            payor_id=6,
            status=BillStatus.NEW,
            processing_scheduled_at_or_after=None,
            created_at=datetime.datetime.strptime("12/11/2018 00:00", "%m/%d/%Y %H:%M"),
            payment_method_label="4242",
        ),
    ]
    return bills


@pytest.fixture(scope="function")
def estimates_tps():
    return [
        TreatmentProcedureFactory.create(
            id=4,
            cost_breakdown_id=2,
            status=TreatmentProcedureStatus.SCHEDULED,
            reimbursement_wallet_id=3,
            procedure_name="Fresh IVF",
            cost=100000,
            cost_credit=0,
        ),
        TreatmentProcedureFactory.create(
            id=5,
            cost_breakdown_id=3,
            status=TreatmentProcedureStatus.SCHEDULED,
            reimbursement_wallet_id=3,
            procedure_name="Frozen IVF",
            cost=200000,
            cost_credit=1,
        ),
        TreatmentProcedureFactory.create(
            id=6,
            cost_breakdown_id=4,
            status=TreatmentProcedureStatus.SCHEDULED,
            reimbursement_wallet_id=3,
            procedure_name="Frozen IVF",
            cost=200000,
            cost_credit=1,
        ),
    ]


@pytest.fixture(scope="function")
def estimates_clinic_location():
    return FertilityClinicLocationFactory.build(
        name="Maven Fertility",
        city="Brooklyn",
        subdivision_code="US-NY",
    )


@pytest.fixture(scope="function")
def estimates_cost_breakdowns():
    return [
        CostBreakdownFactory.create(
            id=2,
            total_member_responsibility=20000,
            deductible=10000,
            total_employer_responsibility=80000,
            coinsurance=0,
            copay=3000,
        ),
        CostBreakdownFactory.create(
            id=3,
            total_member_responsibility=10000,
            deductible=10000,
            total_employer_responsibility=1000,
            coinsurance=2000,
            copay=0,
        ),
        CostBreakdownFactory.create(
            id=4,
            total_member_responsibility=10000,
            deductible=10000,
            total_employer_responsibility=190000,
            coinsurance=0,
            copay=0,
        ),
    ]


def test_get_estimate_detail_by_uuid(
    estimates_helper,
    estimates_bills,
    estimates_tps,
    estimates_cost_breakdowns,
    estimates_clinic_location,
):
    expected = EstimateDetail(
        procedure_id=4,
        bill_uuid=str(estimates_bills[0].uuid),
        procedure_title="Fresh IVF",
        clinic="Maven Fertility",
        clinic_location="Brooklyn, NY",
        estimate_creation_date="Dec 15, 2018",
        estimate_creation_date_raw=estimates_bills[0].created_at,
        estimated_member_responsibility="$200.00",
        estimated_total_cost="$1,000.00",
        estimated_boilerplate=ESTIMATED_BOILERPLATE,
        credits_used=None,
        responsibility_breakdown=EstimateBreakdown(
            title="Your estimated responsibility",
            total_cost="$200.00",
            items=[
                LabelCost(label="Deductible", cost="$100.00"),
                LabelCost(label="Coinsurance", cost="$0.00"),
                LabelCost(label="Copay", cost="$30.00"),
            ],
        ),
        covered_breakdown=EstimateBreakdown(
            title="Covered amount",
            total_cost="$800.00",
            items=[
                LabelCost(label="Maven Benefit", cost="$800.00"),
            ],
        ),
    )
    with mock.patch(
        "direct_payment.billing.billing_service.BillingService.get_bill_by_uuid",
        return_value=estimates_bills[0],
    ), mock.patch(
        "direct_payment.clinic.repository.clinic_location.FertilityClinicLocationRepository.get",
        return_value=estimates_clinic_location,
    ):
        assert (
            estimates_helper.get_estimate_detail_by_uuid(bill_uuid="1232421")
            == expected
        )


def test_get_estimate_detail_by_uuid__employee_only(
    estimates_helper,
    estimates_bills,
    estimates_tps,
    estimates_cost_breakdowns,
    estimates_clinic_location,
):
    cb = CostBreakdownFactory.create(
        total_member_responsibility=120000,
        deductible=120000,
        total_employer_responsibility=0,
        coinsurance=0,
        copay=0,
    )
    tp = TreatmentProcedureFactory.create(
        cost_breakdown_id=cb.id,
        status=TreatmentProcedureStatus.SCHEDULED,
        reimbursement_wallet_id=3,
        procedure_name="IUI",
        cost=120000,
        cost_credit=1,
    )
    bill = factories.BillFactory.build(
        procedure_id=tp.id,
        amount=120000,
        cost_breakdown_id=cb.id,
        payor_type=PayorType.MEMBER,
        payor_id=6,
        status=BillStatus.NEW,
        processing_scheduled_at_or_after=None,
        created_at=datetime.datetime.strptime("12/15/2018 00:00", "%m/%d/%Y %H:%M"),
        payment_method_label="4242",
    )

    expected = EstimateDetail(
        procedure_id=tp.id,
        bill_uuid=str(bill.uuid),
        procedure_title="IUI",
        clinic="Maven Fertility",
        clinic_location="Brooklyn, NY",
        estimate_creation_date="Dec 15, 2018",
        estimate_creation_date_raw=bill.created_at,
        estimated_member_responsibility="$1,200.00",
        estimated_total_cost="$1,200.00",
        estimated_boilerplate=ESTIMATED_BOILERPLATE,
        credits_used=None,
        responsibility_breakdown=EstimateBreakdown(
            title="Your estimated responsibility",
            total_cost="$1,200.00",
            items=[
                LabelCost(label="Deductible", cost="$1,200.00"),
                LabelCost(label="Coinsurance", cost="$0.00"),
                LabelCost(label="Copay", cost="$0.00"),
            ],
        ),
        covered_breakdown=EstimateBreakdown(
            title="Covered amount",
            total_cost="$0.00",
            items=[
                LabelCost(label="Maven Benefit", cost="$0.00"),
            ],
        ),
    )
    with mock.patch(
        "direct_payment.billing.billing_service.BillingService.get_bill_by_uuid",
        return_value=bill,
    ), mock.patch(
        "direct_payment.clinic.repository.clinic_location.FertilityClinicLocationRepository.get",
        return_value=estimates_clinic_location,
    ):
        assert (
            estimates_helper.get_estimate_detail_by_uuid(bill_uuid="1232421")
            == expected
        )


def test_get_estimate_adjustment_by_uuid(
    estimates_helper,
    estimates_bills,
    estimates_tps,
    estimates_cost_breakdowns,
    estimates_clinic_location,
):
    estimate_bill = estimates_bills[3]
    expected = EstimateDetail(
        procedure_id=6,
        bill_uuid=str(estimate_bill.uuid),
        procedure_title="Frozen IVF",
        clinic="Maven Fertility",
        clinic_location="Brooklyn, NY",
        estimate_creation_date="Dec 11, 2018",
        estimate_creation_date_raw=estimate_bill.created_at,
        estimated_member_responsibility="$20.00",
        estimated_total_cost="$2,000.00",
        estimated_boilerplate=ESTIMATED_BOILERPLATE,
        credits_used="1 credit",
        responsibility_breakdown=EstimateBreakdown(
            title="Your estimated responsibility",
            total_cost="$20.00",
            items=[
                LabelCost(label="Total Member Responsibility", cost="$100.00"),
                LabelCost(label="Previous Charge(s)", cost="-$80.00"),
                LabelCost(label="Estimate Adjustment", cost="$20.00"),
            ],
        ),
        covered_breakdown=EstimateBreakdown(
            title="Covered amount",
            total_cost="$1,900.00",
            items=[
                LabelCost(label="Maven Benefit", cost="$1,900.00"),
            ],
        ),
    )
    with mock.patch(
        "direct_payment.billing.billing_service.BillingService.get_bill_by_uuid",
        return_value=estimate_bill,
    ), mock.patch(
        "direct_payment.clinic.repository.clinic_location.FertilityClinicLocationRepository.get",
        return_value=estimates_clinic_location,
    ):
        assert (
            estimates_helper.get_estimate_detail_by_uuid(bill_uuid="1232421")
            == expected
        )


def test_get_estimate_detail_by_uuid_no_cost_breakdown(
    estimates_helper,
    estimates_bills,
    estimates_tps,
):
    with pytest.raises(EstimateMissingCriticalDataException):
        with mock.patch(
            "direct_payment.billing.billing_service.BillingService.get_bill_by_uuid",
            return_value=estimates_bills[0],
        ):
            estimates_helper.get_estimate_detail_by_uuid(bill_uuid="1232421")


def test_get_estimate_detail_by_uuid_no_treatment_procedure(
    estimates_helper,
    estimates_bills,
    estimates_cost_breakdowns,
):
    with pytest.raises(EstimateMissingCriticalDataException):
        with mock.patch(
            "direct_payment.billing.billing_service.BillingService.get_bill_by_uuid",
            return_value=estimates_bills[0],
        ):
            estimates_helper.get_estimate_detail_by_uuid(bill_uuid="1232421")


def test_get_estimate_detail_by_uuid_no_clinic_location(
    estimates_helper,
    estimates_bills,
    estimates_tps,
    estimates_cost_breakdowns,
):
    expected = EstimateDetail(
        procedure_id=4,
        bill_uuid=str(estimates_bills[0].uuid),
        procedure_title="Fresh IVF",
        clinic="",
        clinic_location="",
        estimate_creation_date="Dec 15, 2018",
        estimate_creation_date_raw=estimates_bills[0].created_at,
        estimated_member_responsibility="$200.00",
        estimated_total_cost="$1,000.00",
        estimated_boilerplate=ESTIMATED_BOILERPLATE,
        credits_used=None,
        responsibility_breakdown=EstimateBreakdown(
            title="Your estimated responsibility",
            total_cost="$200.00",
            items=[
                LabelCost(label="Deductible", cost="$100.00"),
                LabelCost(label="Coinsurance", cost="$0.00"),
                LabelCost(label="Copay", cost="$30.00"),
            ],
        ),
        covered_breakdown=EstimateBreakdown(
            title="Covered amount",
            total_cost="$800.00",
            items=[
                LabelCost(label="Maven Benefit", cost="$800.00"),
            ],
        ),
    )
    with mock.patch(
        "direct_payment.billing.billing_service.BillingService.get_bill_by_uuid",
        return_value=estimates_bills[0],
    ), mock.patch(
        "direct_payment.clinic.repository.clinic_location.FertilityClinicLocationRepository.get",
        return_value=None,
    ):
        assert (
            estimates_helper.get_estimate_detail_by_uuid(bill_uuid="1232421")
            == expected
        )


def test_get_estimate_details_by_wallet(
    estimates_helper,
    estimates_bills,
    estimates_tps,
    estimates_cost_breakdowns,
    estimates_clinic_location,
):
    with mock.patch(
        "direct_payment.billing.billing_service.BillingService.get_estimates_by_payor",
        return_value=estimates_bills[:-1],
    ), mock.patch(
        "direct_payment.clinic.repository.clinic_location.FertilityClinicLocationRepository.get",
        return_value=estimates_clinic_location,
    ):
        res = estimates_helper.get_estimates_by_wallet(wallet_id=5)
        assert len(res) == 3
        assert res[0].procedure_id == 4
        assert res[1].procedure_id == 5
        assert res[2].procedure_id == 5
        assert res[0].estimate_creation_date == "Dec 15, 2018"
        assert res[1].estimate_creation_date == "Dec 11, 2018"
        assert res[2].estimate_creation_date == "Dec 10, 2018"


def test_get_estimates_by_wallet_no_treatment_procedures(
    estimates_helper,
    estimates_bills,
    estimates_cost_breakdowns,
    estimates_clinic_location,
):
    with pytest.raises(EstimateMissingCriticalDataException):
        with mock.patch(
            "direct_payment.billing.billing_service.BillingService.get_estimates_by_payor",
            return_value=estimates_bills,
        ):
            estimates_helper.get_estimates_by_wallet(wallet_id=5)


def test_get_estimates_by_wallet_no_cost_breakdowns(
    estimates_helper,
    estimates_bills,
    estimates_tps,
):
    with pytest.raises(EstimateMissingCriticalDataException):
        with mock.patch(
            "direct_payment.billing.billing_service.BillingService.get_estimates_by_payor",
            return_value=estimates_bills,
        ):
            estimates_helper.get_estimates_by_wallet(wallet_id=5)


def test_get_estimates_by_wallet_no_clinic_locations(
    estimates_helper,
    estimates_bills,
    estimates_tps,
    estimates_cost_breakdowns,
):
    with mock.patch(
        "direct_payment.billing.billing_service.BillingService.get_estimates_by_payor",
        return_value=estimates_bills[:-1],
    ):
        assert len(estimates_helper.get_estimates_by_wallet(wallet_id=5)) == 3


def test_get_estimates_summary_by_wallet(
    estimates_helper,
    estimates_bills,
    estimates_tps,
    estimates_cost_breakdowns,
):
    with mock.patch(
        "direct_payment.billing.billing_service.BillingService.get_estimates_by_payor",
        return_value=estimates_bills[:-1],
    ):
        expected = EstimateSummaryForReimbursementWallet(
            estimate_text="Estimated total (3)",
            total_estimates=3,
            total_member_estimate="$300.00",
            payment_text="Estimated total upcoming cost to you",
            estimate_bill_uuid=None,
        )
        assert estimates_helper.get_estimates_summary_by_wallet(wallet_id=5) == expected


def test_get_estimates_summary_by_wallet_no_bills(
    estimates_helper,
):
    # a wallet that does not exist will have no estimates
    assert estimates_helper.get_estimates_summary_by_wallet(wallet_id=515) is None


def test_get_estimates_summary_by_wallet_one_bill(
    estimates_helper, estimates_bills, estimates_tps, estimates_cost_breakdowns
):
    with mock.patch(
        "direct_payment.billing.billing_service.BillingService.get_estimates_by_payor",
        return_value=[estimates_bills[0]],
    ):
        expected = EstimateSummaryForReimbursementWallet(
            estimate_text="Fresh IVF",
            total_estimates=1,
            total_member_estimate="$200.00",
            payment_text="Estimated total upcoming cost to you",
            estimate_bill_uuid=estimates_bills[0].uuid,
        )
        assert estimates_helper.get_estimates_summary_by_wallet(wallet_id=5) == expected


def test_get_estimates_summary_with_es_locale(
    app, estimates_helper, estimates_bills, estimates_tps, estimates_cost_breakdowns
):
    with test_data() as td, mock.patch(
        "l10n.config.negotiate_locale", return_value="es"
    ), mock.patch(
        "direct_payment.billing.billing_service.BillingService.get_estimates_by_payor",
        return_value=[estimates_bills[0]],
    ):
        td.update(td.flag("release-mono-api-localization").variation_for_all(True))
        estimate_summary = estimates_helper.get_estimates_summary_by_wallet(wallet_id=5)
        assert estimate_summary.payment_text != "payments_mmb_estimated_total_cost"
