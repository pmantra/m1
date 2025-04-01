import datetime
from uuid import uuid4

import factory
import pytest

from cost_breakdown.pytests.factories import (
    CostBreakdownFactory,
    ReimbursementRequestToCostBreakdownFactory,
)
from direct_payment.billing import models as billing_models
from direct_payment.billing.constants import MEMBER_BILLING_OFFSET_DAYS
from direct_payment.billing.pytests import factories as billing_factories
from direct_payment.payments.constants import DetailLabel
from direct_payment.payments.models import PaymentRecord
from direct_payment.payments.payments_helper import PaymentsHelper
from direct_payment.treatment_procedure.models.treatment_procedure import (
    TreatmentProcedureStatus,
)
from direct_payment.treatment_procedure.pytests import factories as procedure_factories
from pytests.factories import ReimbursementWalletUsersFactory
from storage.connection import db
from wallet.models.constants import (
    BenefitTypes,
    ReimbursementRequestExpenseTypes,
    WalletState,
    WalletUserStatus,
    WalletUserType,
)
from wallet.models.reimbursement_wallet_credit import ReimbursementCycleCredits
from wallet.pytests.factories import (
    ReimbursementAccountTypeFactory,
    ReimbursementCycleCreditsFactory,
    ReimbursementCycleMemberCreditTransactionFactory,
    ReimbursementOrganizationSettingsFactory,
    ReimbursementPlanFactory,
    ReimbursementRequestCategoryExpenseTypesFactory,
    ReimbursementRequestFactory,
    ReimbursementWalletFactory,
)

CURRENT_TIME = datetime.datetime(2024, 3, 1, 10, 30, 0)
OFFSET_TIME = datetime.datetime(2024, 3, 8, 10, 30, 0)

android_request_headers = {
    "User-Agent": "MAVEN_ANDROID/202406.2.0-qa (com.mavenclinic.android.member.qa; build:37241; Android:13; Manufacturer:Google; Model:Pixel 7 Pro)",
    "Device-Model": None,
}
iOS_request_headers = {
    "User-Agent": "MavenQA/202406.2.0 (com.mavenclinic.MavenQA; build:159; iOS 17.2.0) Alamofire/5.7.1",
    "Device-Model": "iPhone16,2",
}
android_request_headers_2 = {
    "User-Agent": "MAVEN_ANDROID/202403.2.0-qa (com.mavenclinic.android.member.qa; build:37241; Android:13; Manufacturer:Google; Model:Pixel 7 Pro)",
    "Device-Model": None,
}
iOS_request_headers_2 = {
    "User-Agent": "MavenQA/202403.2.0 (com.mavenclinic.MavenQA; build:159; iOS 17.2.0) Alamofire/5.7.1",
    "Device-Model": "iPhone16,2",
}
web_request_headers = {"User-Agent": "QA-cypress-tests", "Device-Model": "react-web"}


@pytest.fixture
def payments_helper(session):
    return PaymentsHelper(session)


@pytest.fixture(scope="function")
def wallet_cycle_based(enterprise_user):
    org_settings = ReimbursementOrganizationSettingsFactory(
        organization_id=enterprise_user.organization.id,
        allowed_reimbursement_categories__cycle_based=True,
        direct_payment_enabled=True,
    )
    wallet = ReimbursementWalletFactory.create(
        reimbursement_organization_settings=org_settings,
        state=WalletState.QUALIFIED,
    )
    wallet_user = ReimbursementWalletUsersFactory.create(
        user_id=enterprise_user.id,
        reimbursement_wallet_id=wallet.id,
        status=WalletUserStatus.ACTIVE,
        type=WalletUserType.EMPLOYEE,
    )
    wallet.reimbursement_organization_settings.direct_payment_enabled = True
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
    year = datetime.datetime.utcnow().year
    request_category.reimbursement_plan = ReimbursementPlanFactory.create(
        reimbursement_account_type=ReimbursementAccountTypeFactory.create(
            alegeus_account_type="HRA"
        ),
        alegeus_plan_id="FERTILITY",
        start_date=datetime.date(year=year, month=1, day=1),
        end_date=datetime.date(year=year, month=12, day=31),
        is_hdhp=False,
    )

    credits = ReimbursementCycleCreditsFactory.create(
        reimbursement_wallet_id=wallet.id,
        reimbursement_organization_settings_allowed_category_id=category_association.id,
        amount=12,
    )
    ReimbursementCycleMemberCreditTransactionFactory.create(
        reimbursement_cycle_credits_id=credits.id,
        amount=12,
        notes="Initial Fund",
    )
    return wallet


class TestPaymentsHelperDataRetrieval:
    def test_return_relevant_cost_breakdown_none(self, payments_helper, procedure):
        c_b, h_c_b = payments_helper.return_relevant_cost_breakdowns(
            procedure_uuid=procedure.uuid,
            expected_cost_breakdown_id=-1,
        )
        assert c_b is None
        assert h_c_b is None

    def test_return_relevant_cost_breakdown_single(self, payments_helper, procedure):
        expected_cost_breakdown = CostBreakdownFactory.create(
            treatment_procedure_uuid=procedure.uuid, wallet_id=1000
        )
        c_b, h_c_b = payments_helper.return_relevant_cost_breakdowns(
            procedure_uuid=procedure.uuid,
            expected_cost_breakdown_id=expected_cost_breakdown.id,
        )
        assert c_b == expected_cost_breakdown
        assert h_c_b is None

    def test_return_relevant_cost_breakdown_double(self, payments_helper, procedure):
        breakdowns = CostBreakdownFactory.create_batch(
            size=2,
            treatment_procedure_uuid=procedure.uuid,
            created_at=factory.Iterator(
                [
                    datetime.datetime.now(),
                    datetime.datetime.now() + datetime.timedelta(days=1),
                ]
            ),
            wallet_id=1001,
        )
        expected_cost_breakdown = breakdowns[1]
        historical_cost_breakdown = breakdowns[0]
        c_b, h_c_b = payments_helper.return_relevant_cost_breakdowns(
            procedure_uuid=procedure.uuid,
            expected_cost_breakdown_id=expected_cost_breakdown.id,
        )
        assert c_b == expected_cost_breakdown
        assert h_c_b == historical_cost_breakdown
        assert h_c_b.created_at < c_b.created_at

    def test_return_relevant_cost_breakdown_many(self, payments_helper, procedure):
        breakdowns = CostBreakdownFactory.create_batch(
            size=4,
            treatment_procedure_uuid=procedure.uuid,
            created_at=factory.Iterator(
                [
                    datetime.datetime.now(),
                    datetime.datetime.now() + datetime.timedelta(days=1),
                    datetime.datetime.now() + datetime.timedelta(days=2),
                    datetime.datetime.now() + datetime.timedelta(days=3),
                ]
            ),
            wallet_id=1002,
        )
        expected_cost_breakdown = breakdowns[2]
        historical_cost_breakdown = breakdowns[1]
        c_b, h_c_b = payments_helper.return_relevant_cost_breakdowns(
            procedure_uuid=procedure.uuid,
            expected_cost_breakdown_id=expected_cost_breakdown.id,
        )
        assert c_b == expected_cost_breakdown
        assert h_c_b == historical_cost_breakdown
        assert h_c_b.created_at < c_b.created_at

    @pytest.mark.parametrize(
        "benefit_type, expected_result",
        [(BenefitTypes.CURRENCY, False), (BenefitTypes.CYCLE, True)],
    )
    def test_credit_use_bool_by_procedure(
        self,
        add_association_for_procedure_and_wallet,
        payments_helper,
        procedure,
        bill_wallet,
        benefit_type,
        expected_result,
    ):
        add_association_for_procedure_and_wallet(procedure, bill_wallet, benefit_type)
        res = payments_helper.return_credit_use_bool_for_procedure(procedure)
        assert res == expected_result


class TestPaymentsHelperFormatting:
    def test_return_upcoming_records(
        self, payments_helper, cost_breakdown, procedure, billing_service
    ):
        expected_time_first = datetime.datetime.now() + datetime.timedelta(
            days=4
        )  # assigned to failed: goes first
        expected_time_second = datetime.datetime.now() + datetime.timedelta(days=1)
        expected_time_third = datetime.datetime.now() + datetime.timedelta(
            days=9
        )  # pending: doesn't +3, others do.
        expected_time_fourth = datetime.datetime.now() + datetime.timedelta(days=3)

        bills = billing_factories.BillFactory.build_batch(
            size=4,
            procedure_id=procedure.id,
            cost_breakdown_id=cost_breakdown.id,
            processing_scheduled_at_or_after=None,
            status=factory.Iterator(
                [
                    billing_models.BillStatus.NEW,
                    billing_models.BillStatus.PAID,
                    billing_models.BillStatus.PROCESSING,
                    billing_models.BillStatus.FAILED,
                ]
            ),
            # out of order to test the sort
            created_at=factory.Iterator(
                [expected_time_fourth, None, expected_time_second, expected_time_first]
            ),
        )
        # also add an estimate for the the previous set of bills. this should not be returned
        estimate_for_cb1 = billing_service.bill_repo.create(
            instance=billing_factories.BillFactory.build(
                procedure_id=procedure.id,
                cost_breakdown_id=cost_breakdown.id,
                processing_scheduled_at_or_after=None,
                status=billing_models.BillStatus.NEW,
                is_ephemeral=True,
                payor_id=bills[0].payor_id,
            )
        )

        pending_procedure = procedure_factories.TreatmentProcedureFactory.build(
            status=TreatmentProcedureStatus.SCHEDULED,
            created_at=expected_time_third,
            reimbursement_wallet_id=bills[0].payor_id,
            id=50001,  # this factory does not stamp an id here for some reason
        )

        # Procedure with estimates only should not show up
        estimate_procedure = procedure_factories.TreatmentProcedureFactory.create(
            status=TreatmentProcedureStatus.SCHEDULED,
            reimbursement_wallet_id=bills[0].payor_id,
        )
        estimate_for_cb2 = billing_service.bill_repo.create(
            instance=billing_factories.BillFactory.build(
                procedure_id=estimate_procedure.id,
                cost_breakdown_id=cost_breakdown.id + 2,  # just a different CB id
                processing_scheduled_at_or_after=None,
                status=billing_models.BillStatus.NEW,
                is_ephemeral=True,
                payor_id=bills[0].payor_id,
            )
        )

        estimate_uuids = {estimate_for_cb1.uuid, estimate_for_cb2.uuid}
        records = payments_helper.return_upcoming_records(
            bills=bills,
            bill_procedure_ids={bill.procedure_id for bill in bills},
            procedure_map={
                procedure.id: procedure,
                pending_procedure.id: pending_procedure,
                estimate_procedure.id: estimate_procedure,
            },
            cost_breakdown_map={cost_breakdown.id: cost_breakdown},
        )
        assert len(records) == 4
        assert [record.payment_status for record in records] == [
            "FAILED",
            "PROCESSING",
            "PENDING",
            "NEW",
        ]
        assert [record.due_at for record in records] == [
            expected_time_first + datetime.timedelta(days=MEMBER_BILLING_OFFSET_DAYS),
            expected_time_second + datetime.timedelta(days=MEMBER_BILLING_OFFSET_DAYS),
            None,  # pending has no due date
            expected_time_fourth + datetime.timedelta(days=MEMBER_BILLING_OFFSET_DAYS),
        ]
        bill_uuids = {r.bill_uuid for r in records}
        # none of these records wshould be estimates
        assert estimate_uuids.isdisjoint(bill_uuids)

    def test_return_historic_records(self, payments_helper, cost_breakdown, procedure):
        expected_time_first = datetime.datetime.utcnow() + datetime.timedelta(days=2)
        expected_time_second = datetime.datetime.utcnow() + datetime.timedelta(days=1)
        bills = billing_factories.BillFactory.build_batch(
            size=3,
            procedure_id=procedure.id,
            cost_breakdown_id=cost_breakdown.id,
            status=factory.Iterator(
                [
                    billing_models.BillStatus.NEW,
                    billing_models.BillStatus.PAID,
                    billing_models.BillStatus.REFUNDED,
                ]
            ),
            # out of order to test the sort
            paid_at=factory.Iterator([None, expected_time_second, None]),
            refunded_at=factory.Iterator([None, None, expected_time_first]),
        )
        records = payments_helper.return_historic_records(
            bills=bills,
            procedure_map={procedure.id: procedure},
            cost_breakdown_map={cost_breakdown.id: cost_breakdown},
        )
        assert len(records) == 2
        assert [record.payment_status for record in records] == [
            billing_models.BillStatus.REFUNDED.value,
            billing_models.BillStatus.PAID.value,
        ]
        assert [record.completed_at for record in records] == [
            expected_time_first,
            expected_time_second,
        ], f"{expected_time_second.isoformat()} shouldn't come before {expected_time_first.isoformat()}."

    @pytest.mark.parametrize(
        "coinsurance, copay, created_at, processing_scheduled_at_or_after, exp_due_at, expected",
        (
            [0, 1000, CURRENT_TIME, None, OFFSET_TIME, "Copay"],
            [1000, 0, CURRENT_TIME, None, OFFSET_TIME, "Coinsurance"],
            [0, 0, CURRENT_TIME, None, OFFSET_TIME, "Copay"],
            [0, 1000, CURRENT_TIME, CURRENT_TIME, CURRENT_TIME, "Copay"],
            [1000, 0, CURRENT_TIME, CURRENT_TIME, CURRENT_TIME, "Coinsurance"],
            [0, 0, CURRENT_TIME, CURRENT_TIME, CURRENT_TIME, "Copay"],
        ),
    )
    def test_create_payment_detail(
        self,
        payments_helper,
        coinsurance,
        copay,
        created_at,
        processing_scheduled_at_or_after,
        exp_due_at,
        expected,
    ):
        procedure = procedure_factories.TreatmentProcedureFactory.build(
            cost=2000, created_at=created_at
        )
        cost_breakdown = CostBreakdownFactory.build(
            deductible=0,  # will show regardless of value
            coinsurance=coinsurance,
            copay=copay,
            overage_amount=0,  # to test the filter
            hra_applied=0,
            total_member_responsibility=1000,
            total_employer_responsibility=1000,
        )
        bill = billing_factories.BillFactory.build(
            amount=1000,
            procedure_id=procedure.id,
            cost_breakdown_id=cost_breakdown.id,
            last_calculated_fee=100,
            created_at=created_at,
            processing_scheduled_at_or_after=processing_scheduled_at_or_after,
        )
        clinic_name = "Test Clinic"
        clinic_loc_name = "Test Maven Clinic"
        detail = payments_helper.create_payment_detail(
            bill=bill,
            past_bill_fees=0,
            cost_breakdown=cost_breakdown,
            past_cost_breakdown=None,
            procedure=procedure,
            clinic_name=clinic_name,
            clinic_loc_name=clinic_loc_name,
        )
        assert detail.label == procedure.procedure_name
        assert detail.treatment_procedure_id == procedure.id
        assert detail.treatment_procedure_clinic == clinic_name
        assert detail.treatment_procedure_location == clinic_loc_name
        assert detail.treatment_procedure_started_at == procedure.start_date
        assert detail.payment_status == bill.status.value
        assert detail.member_responsibility == bill.amount + bill.last_calculated_fee
        assert detail.total_cost == procedure.cost
        assert detail.cost_responsibility_type == "shared"
        assert detail.error_type == bill.error_type
        assert len(detail.responsibility_breakdown) == 3
        assert {r_b.label for r_b in detail.responsibility_breakdown} == {
            expected,
            "Deductible",
            "Fees",
        }
        assert len(detail.benefit_breakdown) == 2
        assert {b_b.label for b_b in detail.benefit_breakdown} == {
            "Maven Benefit",
            "Medical Plan",
        }
        assert detail.created_at == created_at
        assert detail.due_at == exp_due_at

    @pytest.mark.parametrize(
        argnames="credits_used",
        argvalues=[2, -3, 0],
        ids=["positive credits", "negative credits", "zero credits"],
    )
    def test_create_payment_detail_with_credit_transaction(
        self, payments_helper, wallet_cycle_based, credits_used
    ):
        wallet_category_association = wallet_cycle_based.reimbursement_organization_settings.allowed_reimbursement_categories[
            0
        ]
        category = wallet_category_association.reimbursement_request_category
        reimbursement_request = ReimbursementRequestFactory.create(
            wallet=wallet_cycle_based, category=category, amount=750000
        )
        procedure = procedure_factories.TreatmentProcedureFactory.create(
            cost=2000,
            created_at=CURRENT_TIME,
            uuid=uuid4(),
        )
        cost_breakdown = CostBreakdownFactory.create(
            deductible=0,  # will show regardless of value
            coinsurance=0,
            copay=0,
            overage_amount=0,  # to test the filter
            hra_applied=0,
            total_member_responsibility=1000,
            total_employer_responsibility=1000,
        )

        bill = billing_factories.BillFactory.build(
            amount=1000,
            procedure_id=procedure.id,
            cost_breakdown_id=cost_breakdown.id,
            last_calculated_fee=100,
            created_at=CURRENT_TIME,
            processing_scheduled_at_or_after=None,
        )
        clinic_name = "Test Clinic"
        clinic_loc_name = "Test Maven Clinic"
        cycle_credits_id = (
            db.session.query(ReimbursementCycleCredits.id)
            .filter(
                ReimbursementCycleCredits.reimbursement_wallet_id
                == wallet_cycle_based.id
            )
            .scalar()
        )
        assert cycle_credits_id is not None
        ReimbursementCycleMemberCreditTransactionFactory.create(
            reimbursement_cycle_credits_id=cycle_credits_id,
            amount=credits_used,
            reimbursement_request_id=reimbursement_request.id,
        )

        ReimbursementRequestToCostBreakdownFactory.create(
            reimbursement_request_id=reimbursement_request.id,
            cost_breakdown_id=cost_breakdown.id,
            treatment_procedure_uuid=procedure.uuid,
        )
        detail = payments_helper.create_payment_detail(
            bill=bill,
            past_bill_fees=0,
            cost_breakdown=cost_breakdown,
            past_cost_breakdown=None,
            procedure=procedure,
            clinic_name=clinic_name,
            clinic_loc_name=clinic_loc_name,
            is_credit_based_wallet=True,
        )

        assert detail.credits_used == abs(credits_used)

    def test_create_payment_detail_past_bills_none(self, payments_helper):
        procedure = procedure_factories.TreatmentProcedureFactory.build(cost=2000)
        cost_breakdown = CostBreakdownFactory.build(
            deductible=0,  # will show regardless of value
            coinsurance=1000,
            overage_amount=0,  # to test the filter
            hra_applied=0,
            total_member_responsibility=1000,
            total_employer_responsibility=1000,
        )
        bill = billing_factories.BillFactory.build(
            amount=1000,
            procedure_id=procedure.id,
            cost_breakdown_id=cost_breakdown.id,
            last_calculated_fee=100,
        )
        clinic_name = "Test Clinic"
        clinic_loc_name = "Test Maven Clinic"
        detail = payments_helper.create_payment_detail(
            bill=bill,
            past_bill_fees=None,
            cost_breakdown=cost_breakdown,
            past_cost_breakdown=None,
            procedure=procedure,
            clinic_name=clinic_name,
            clinic_loc_name=clinic_loc_name,
        )
        assert len(detail.responsibility_breakdown) == 3
        fees_breakdown = [
            r_b
            for r_b in detail.responsibility_breakdown
            if r_b.label == DetailLabel.FEES.value
        ][0]
        assert fees_breakdown.cost == bill.last_calculated_fee
        assert fees_breakdown.original is None

        deductible_breakdown = [
            r_b
            for r_b in detail.responsibility_breakdown
            if r_b.label == DetailLabel.DEDUCTIBLE.value
        ][0]
        assert deductible_breakdown.original is None

        coinsurance_breakdown = [
            r_b
            for r_b in detail.responsibility_breakdown
            if r_b.label == DetailLabel.COINSURANCE.value
        ][0]
        assert coinsurance_breakdown.original is None

    def test_create_payment_detail_no_fees(self, payments_helper):
        procedure = procedure_factories.TreatmentProcedureFactory.build(cost=2000)
        cost_breakdown = CostBreakdownFactory.build(
            deductible=0,  # will show regardless of value
            coinsurance=1000,
            overage_amount=0,  # to test the filter
            hra_applied=0,
            total_member_responsibility=1000,
            total_employer_responsibility=1000,
        )
        bill = billing_factories.BillFactory.build(
            amount=1000,
            procedure_id=procedure.id,
            cost_breakdown_id=cost_breakdown.id,
            last_calculated_fee=0,
        )
        clinic_name = "Test Clinic"
        clinic_loc_name = "Test Maven Clinic"
        detail = payments_helper.create_payment_detail(
            bill=bill,
            past_bill_fees=None,
            cost_breakdown=cost_breakdown,
            past_cost_breakdown=None,
            procedure=procedure,
            clinic_name=clinic_name,
            clinic_loc_name=clinic_loc_name,
        )
        assert len(detail.responsibility_breakdown) == 2
        assert {r_b.label for r_b in detail.responsibility_breakdown} == {
            "Coinsurance",
            "Deductible",
        }

    def test_create_pending_payment_record(self, payments_helper):
        procedure = procedure_factories.TreatmentProcedureFactory.build(
            status=TreatmentProcedureStatus.SCHEDULED
        )
        pending_record: PaymentRecord = payments_helper.create_pending_payment_records(
            pending_procedure_ids={procedure.id},
            procedure_map={procedure.id: procedure},
        ).pop()

        assert pending_record.treatment_procedure_id == procedure.id
        assert pending_record.label == procedure.procedure_name
        assert pending_record.payment_status == "PENDING"
        assert (
            pending_record.payment_method_type
            == billing_models.PaymentMethod.PAYMENT_GATEWAY
        )
        assert pending_record.created_at == procedure.created_at
        assert pending_record.display_date == "created_at"
        assert pending_record.member_responsibility is None
        assert pending_record.total_cost is None
        assert pending_record.cost_responsibility_type is None
        assert pending_record.payment_method_display_label is None
        assert pending_record.due_at is None
        assert pending_record.completed_at is None
        assert pending_record.bill_uuid is None

    @pytest.mark.parametrize("fee", [0, 100])
    def test_create_payment_record(self, payments_helper, fee):
        procedure = procedure_factories.TreatmentProcedureFactory.build(
            status=TreatmentProcedureStatus.SCHEDULED
        )
        cost_breakdown = CostBreakdownFactory.build(
            total_member_responsibility=10, total_employer_responsibility=0
        )
        bill = billing_factories.BillFactory.build(
            procedure_id=procedure.id,
            cost_breakdown_id=cost_breakdown.id,
            last_calculated_fee=fee,
        )
        record: PaymentRecord = payments_helper.create_payment_records(
            bills=[bill],
            procedure_map={procedure.id: procedure},
            cost_breakdown_map={cost_breakdown.id: cost_breakdown},
        ).pop()
        assert record.label == procedure.procedure_name
        assert record.treatment_procedure_id == procedure.id
        assert record.payment_status == bill.status.value
        assert record.created_at == procedure.created_at
        assert record.bill_uuid == str(bill.uuid)
        assert record.payment_method_type == bill.payment_method
        assert record.payment_method_display_label == bill.payment_method_label
        assert record.member_responsibility == bill.amount + bill.last_calculated_fee
        assert record.total_cost == procedure.cost
        assert record.cost_responsibility_type == "member_only"
        assert record.due_at == bill.created_at + datetime.timedelta(
            days=MEMBER_BILLING_OFFSET_DAYS
        )
        assert record.completed_at is None
        assert record.display_date == "due_at"
        # TODO: add tests for breakdown data

    @pytest.mark.parametrize(
        "allow_voided_payment_status,expected_status",
        ((True, "VOIDED"), (False, "CANCELLED")),
    )
    def test_create_payment_record_handles_voided_payment_status(
        self, payments_helper, allow_voided_payment_status, expected_status
    ):
        procedure = procedure_factories.TreatmentProcedureFactory.build(
            status=TreatmentProcedureStatus.CANCELLED
        )
        cost_breakdown = CostBreakdownFactory.build(
            total_member_responsibility=10, total_employer_responsibility=0
        )
        bill = billing_factories.BillFactory.build(
            procedure_id=procedure.id,
            cost_breakdown_id=cost_breakdown.id,
            last_calculated_fee=0,
            status=billing_models.BillStatus.PAID,
            amount=0,
        )
        record: PaymentRecord = payments_helper.create_payment_records(
            bills=[bill],
            procedure_map={procedure.id: procedure},
            cost_breakdown_map={cost_breakdown.id: cost_breakdown},
            allow_voided_payment_status=allow_voided_payment_status,
        ).pop()
        assert record.payment_status == expected_status

    @pytest.mark.parametrize(
        "member_responsibility,employer_responsibility,expected_type",
        [
            (0, 100, "no_member"),
            (100, 0, "member_only"),
            (100, 100, "shared"),
            (0, 0, "shared"),
        ],
    )
    def test_calculate_cost_responsibility_type(
        self,
        payments_helper,
        member_responsibility,
        employer_responsibility,
        expected_type,
    ):
        cost_breakdown = CostBreakdownFactory.build(
            total_member_responsibility=member_responsibility,
            total_employer_responsibility=employer_responsibility,
        )
        cost_responsibility_type = payments_helper._calculate_cost_responsibility_type(
            cost_breakdown
        )
        assert cost_responsibility_type == expected_type

    @pytest.mark.parametrize("amount", [100, -100, 0])
    def test_determine_completed_at_incomplete(self, payments_helper, amount):
        bill = billing_factories.BillFactory.build(
            amount=amount, status=billing_models.BillStatus.NEW
        )
        completed_date = payments_helper._calculate_completed_at(bill)
        assert completed_date is None

    @pytest.mark.parametrize("amount", [100, 0])
    def test_determine_completed_at_paid(self, payments_helper, amount):
        bill = billing_factories.BillFactory.build(
            amount=amount,
            status=billing_models.BillStatus.PAID,
            paid_at=datetime.datetime.now(),
        )
        completed_date = payments_helper._calculate_completed_at(bill)
        assert bill.paid_at is not None
        assert bill.refunded_at is None
        assert completed_date == bill.paid_at

    def test_determine_completed_at_refund(self, payments_helper):
        bill = billing_factories.BillFactory.build(
            amount=-100,
            status=billing_models.BillStatus.REFUNDED,
            refunded_at=datetime.datetime.now(),
        )
        completed_date = payments_helper._calculate_completed_at(bill)
        assert bill.paid_at is None
        assert bill.refunded_at is not None
        assert completed_date == bill.refunded_at

    @pytest.mark.parametrize(
        "bill_status,expected_field",
        [
            (billing_models.BillStatus.NEW, "due_at"),
            (billing_models.BillStatus.PROCESSING, "due_at"),
            (billing_models.BillStatus.FAILED, "due_at"),
            (billing_models.BillStatus.PAID, "completed_at"),
            (billing_models.BillStatus.REFUNDED, "completed_at"),
        ],
    )
    def test_determine_display_date(self, payments_helper, bill_status, expected_field):
        bill = billing_factories.BillFactory.build(status=bill_status)
        display_date_field = payments_helper._calculate_display_date(bill)
        assert display_date_field == expected_field

    def test_determine_display_date_pending(self, payments_helper):
        display_date_field = payments_helper._calculate_display_date()
        assert display_date_field == "created_at"

    def test_is_iOS_true(self, payments_helper):
        assert payments_helper.is_iOS(iOS_request_headers)

    def test_is_iOS_false(self, payments_helper):
        assert not payments_helper.is_iOS(android_request_headers)

    def test_is_android_true(self, payments_helper):
        assert payments_helper.is_android(android_request_headers)

    def test_is_android_false(self, payments_helper):
        assert not payments_helper.is_android(iOS_request_headers)

    @pytest.mark.parametrize(
        "request_headers,support_version,result",
        [
            (iOS_request_headers, "202404.3.0", True),
            (iOS_request_headers, "202406.3.0", False),
            (android_request_headers, "202404.3.0", True),
            (android_request_headers, "202406.3.0", False),
            (web_request_headers, "202404.3.0", True),
        ],
    )
    def test_support_app_version(
        self, payments_helper, request_headers, support_version, result
    ):
        assert (
            payments_helper.support_app_version(
                request_headers=request_headers, version=support_version
            )
            == result
        )

    @pytest.mark.parametrize(
        "request_headers,use_refunds_refinement, result",
        [
            (iOS_request_headers, True, True),
            (iOS_request_headers, False, False),
            (iOS_request_headers_2, True, False),
            (android_request_headers, True, True),
            (android_request_headers, False, False),
            (android_request_headers_2, True, False),
            (web_request_headers, True, True),
            (web_request_headers, False, False),
        ],
    )
    def test_show_payment_status_voided(
        self, payments_helper, use_refunds_refinement, request_headers, result
    ):
        assert (
            payments_helper.show_payment_status_voided(
                request_headers=request_headers,
                use_refunds_refinement=use_refunds_refinement,
            )
        ) == result
