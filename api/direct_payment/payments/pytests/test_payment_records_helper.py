import uuid
from datetime import datetime
from unittest import mock
from unittest.mock import PropertyMock

import factory
import pytest

from cost_breakdown.pytests.factories import CostBreakdownFactory
from direct_payment.billing.models import BillStatus, PayorType
from direct_payment.billing.pytests.factories import BillFactory
from direct_payment.payments.constants import (
    ENABLE_UNLIMITED_BENEFITS_FOR_PAYMENTS_HELPER,
)
from direct_payment.payments.models import (
    PaymentRecordForReimbursementWallet,
    UpcomingPaymentsAndSummaryForReimbursementWallet,
    UpcomingPaymentSummaryForReimbursementWallet,
)
from direct_payment.payments.payment_records_helper import (
    PaymentRecordsHelper,
    compute_num_errors,
    compute_summary_for_reimbursement_wallet,
)
from direct_payment.treatment_procedure.models.treatment_procedure import (
    TreatmentProcedureStatus,
)
from direct_payment.treatment_procedure.pytests.factories import (
    TreatmentProcedureFactory,
)
from pytests.factories import ReimbursementWalletFactory
from wallet.models.constants import BenefitTypes, WalletState
from wallet.models.reimbursement_wallet import ReimbursementWallet
from wallet.pytests.factories import (
    ReimbursementOrganizationSettingsFactory,
    ReimbursementOrgSettingCategoryAssociationFactory,
    ReimbursementRequestCategoryFactory,
)


class TestPaymentDetail:
    def test_returns_none_when_no_upcoming_records(self, bill_wallet):
        with mock.patch(
            "direct_payment.payments.payment_records_helper.PaymentsHelper",
        ) as helper_mock:
            billing_service_mock = mock.Mock()
            billing_service_mock.get_upcoming_bills_by_payor.return_value = []
            billing_service_mock.get_bills_by_procedure_ids.return_value = []
            billing_service_mock.get_estimates_by_procedure_ids.return_value = []

            mock_instance = mock.Mock()
            mock_instance.billing_service = billing_service_mock

            mock_treatment_repo = mock.Mock()
            mock_treatment_repo.get_wallet_payment_history_procedures.return_value = []
            mock_treatment_repo.get_all_treatments_from_wallet_id.return_value = []

            mock_instance.treatment_procedure_repo = mock_treatment_repo
            mock_instance.return_upcoming_records_for_reimbursement_wallet.return_value = (
                []
            )
            helper_mock.return_value = mock_instance

            payment_records_helper = PaymentRecordsHelper()
            result = (
                payment_records_helper.get_upcoming_payments_for_reimbursement_wallet(
                    bill_wallet
                )
            )

            # Mainly want to check that this is called, i.e. that we are going through the entire code path
            # and not short-circuiting at the top.
            mock_instance.return_upcoming_records_for_reimbursement_wallet.assert_called()
            assert result is None

    @pytest.mark.parametrize(
        argnames="enable_unlimited, inp_tp_status, is_ephemeral_list, total_benefit_amount",
        argvalues=(
            (False, TreatmentProcedureStatus.SCHEDULED, [False] * 3, 3),
            (False, TreatmentProcedureStatus.COMPLETED, [False] * 3, 3),
            (False, TreatmentProcedureStatus.SCHEDULED, [True, False, False], 2),
            (False, TreatmentProcedureStatus.COMPLETED, [True, False, False], 2),
            (True, TreatmentProcedureStatus.SCHEDULED, [False] * 3, 3),
            (True, TreatmentProcedureStatus.COMPLETED, [False] * 3, 3),
            (True, TreatmentProcedureStatus.SCHEDULED, [True, False, False], 2),
            (True, TreatmentProcedureStatus.COMPLETED, [True, False, False], 2),
        ),
    )
    def test_returns_happy_path_computation(
        self,
        enterprise_user,
        upcoming_bills_fixture,
        cost_breakdown_for_upcoming_bills,
        enable_unlimited,
        inp_tp_status,
        is_ephemeral_list,
        total_benefit_amount,
        ff_test_data,
    ):
        ff_test_data.update(
            ff_test_data.flag(
                ENABLE_UNLIMITED_BENEFITS_FOR_PAYMENTS_HELPER
            ).variation_for_all(enable_unlimited)
        )

        org_settings = ReimbursementOrganizationSettingsFactory(
            organization_id=enterprise_user.organization.id,
            direct_payment_enabled=True,
        )

        wallet = ReimbursementWalletFactory.create(
            reimbursement_organization_settings=org_settings,
            member=enterprise_user,
            state=WalletState.QUALIFIED,
        )

        created_objs = upcoming_bills_fixture(wallet, inp_tp_status, is_ephemeral_list)
        upcoming_bills = [obj for obj in created_objs if not obj.is_ephemeral]
        expected_tma = sum(
            (upcoming_bill.amount + upcoming_bill.last_calculated_fee)
            for upcoming_bill in upcoming_bills
        )
        expected_summary = UpcomingPaymentSummaryForReimbursementWallet(
            total_member_amount=expected_tma,
            member_method="this one should show",
            total_benefit_amount=total_benefit_amount,
            benefit_remaining=0,
            procedure_title="IVF",
        )
        cat = ReimbursementRequestCategoryFactory.create(
            label="fertility",
        )

        ReimbursementOrgSettingCategoryAssociationFactory.create(
            reimbursement_organization_settings_id=wallet.reimbursement_organization_settings_id,
            reimbursement_request_category_id=cat.id,
            benefit_type=BenefitTypes.CURRENCY,
            reimbursement_request_category_maximum=5000,
        )
        with mock.patch.object(
            ReimbursementWallet,
            "get_direct_payment_category",
            new=PropertyMock(return_value=cat),
        ), mock.patch.object(
            ReimbursementWallet,
            "available_currency_amount_by_category",
            new=PropertyMock(return_value={cat.id: 5000}),
        ):
            payment_records_helper = PaymentRecordsHelper()
            result = (
                payment_records_helper.get_upcoming_payments_for_reimbursement_wallet(
                    wallet
                )
            )
        assert result.upcoming_payments_and_summary.summary == expected_summary
        upcoming_payments = result.upcoming_payments_and_summary.payments
        assert len(upcoming_payments) == len(upcoming_bills)
        assert {payment.bill_uuid for payment in upcoming_payments} == {
            upcoming_payment.bill_uuid for upcoming_payment in upcoming_payments
        }
        assert result.client_layout.value == "MEMBER"
        assert result.show_benefit_amount is True

    @pytest.mark.parametrize(argnames="enable_unlimited", argvalues=[True, False])
    def test_returns_happy_path_computation2(
        self,
        enterprise_user,
        upcoming_bills_fixture,
        cost_breakdown_for_upcoming_bills,
        bill_repository,
        enable_unlimited,
        ff_test_data,
    ):
        ff_test_data.update(
            ff_test_data.flag(
                ENABLE_UNLIMITED_BENEFITS_FOR_PAYMENTS_HELPER
            ).variation_for_all(enable_unlimited)
        )

        org_settings = ReimbursementOrganizationSettingsFactory(
            organization_id=enterprise_user.organization.id,
            direct_payment_enabled=True,
        )

        wallet = ReimbursementWalletFactory.create(
            reimbursement_organization_settings=org_settings,
            member=enterprise_user,
            state=WalletState.QUALIFIED,
        )

        tp_schd = TreatmentProcedureFactory.create(
            status=TreatmentProcedureStatus.SCHEDULED,
            member_id=wallet.user_id,
            reimbursement_wallet_id=wallet.id,
        )
        tp_comp = TreatmentProcedureFactory.create(
            status=TreatmentProcedureStatus.COMPLETED,
            member_id=wallet.user_id,
            reimbursement_wallet_id=wallet.id,
        )

        cbs = [
            CostBreakdownFactory.create(
                treatment_procedure_uuid=tp.uuid, ending_wallet_balance=1000
            )
            for tp in [tp_schd, tp_comp, tp_comp]
        ]

        bills = BillFactory.build_batch(
            size=3,
            status=factory.Iterator([BillStatus.NEW, BillStatus.NEW, BillStatus.PAID]),
            payor_type=PayorType.MEMBER,
            payor_id=wallet.id,
            paid_at=factory.Iterator([None, None, datetime.utcnow()]),
            procedure_id=factory.Iterator([tp_schd.id, tp_comp.id, tp_comp.id]),
            cost_breakdown_id=factory.Iterator([cb.id for cb in cbs]),
            processing_at=factory.Iterator([None, datetime.utcnow(), None]),
            payment_method_label=factory.Iterator(["estimate", "upcoming", "historic"]),
            created_at=factory.Iterator(
                [datetime(3000, 1, 1), datetime(3000, 1, 20), datetime(3000, 1, 2)]
            ),
            is_ephemeral=factory.Iterator([True, False, False]),
        )
        bills = [bill_repository.create(instance=bill) for bill in bills]

        upcoming_bills = bills[1:2]
        expected_tma = sum(
            (upcoming_bill.amount + upcoming_bill.last_calculated_fee)
            for upcoming_bill in upcoming_bills
            if upcoming_bill.status.value != "PROCESSING"
        )
        expected_summary = UpcomingPaymentSummaryForReimbursementWallet(
            total_member_amount=expected_tma,
            member_method="upcoming",
            total_benefit_amount=0,
            benefit_remaining=1000,
            procedure_title="IVF",
        )
        cat = ReimbursementRequestCategoryFactory.create(
            label="fertility",
        )

        ReimbursementOrgSettingCategoryAssociationFactory.create(
            reimbursement_organization_settings_id=wallet.reimbursement_organization_settings_id,
            reimbursement_request_category_id=cat.id,
            benefit_type=BenefitTypes.CURRENCY,
            reimbursement_request_category_maximum=5000,
        )
        with mock.patch.object(
            ReimbursementWallet,
            "get_direct_payment_category",
            new=PropertyMock(return_value=cat),
        ), mock.patch.object(
            ReimbursementWallet,
            "available_currency_amount_by_category",
            new=PropertyMock(return_value={cat.id: 5000}),
        ):
            payment_records_helper = PaymentRecordsHelper()
            result = (
                payment_records_helper.get_upcoming_payments_for_reimbursement_wallet(
                    wallet
                )
            )
        assert result.upcoming_payments_and_summary.summary == expected_summary
        upcoming_payments = result.upcoming_payments_and_summary.payments
        assert len(upcoming_payments) == len(upcoming_bills)
        assert {payment.bill_uuid for payment in upcoming_payments} == {
            upcoming_payment.bill_uuid for upcoming_payment in upcoming_payments
        }
        assert result.client_layout.value == "MEMBER"
        assert result.show_benefit_amount is False

    def test_returns_no_upcoming_bills(
        self,
        enterprise_user,
        upcoming_bills_fixture,
        cost_breakdown_for_upcoming_bills,
    ):
        wallet = ReimbursementWalletFactory.create(
            reimbursement_organization_settings=(
                ReimbursementOrganizationSettingsFactory(
                    organization_id=enterprise_user.organization.id,
                    direct_payment_enabled=True,
                )
            ),
            member=enterprise_user,
            state=WalletState.QUALIFIED,
        )
        payment_records_helper = PaymentRecordsHelper()
        result = payment_records_helper.get_upcoming_payments_for_reimbursement_wallet(
            wallet
        )
        assert result is None


def test_compute_num_errors():
    payments = [
        PaymentRecordForReimbursementWallet(
            payment_status="NEW",
            procedure_id=1,
            procedure_title="TB12",
            created_at=None,
            error_type="hi",
        ),
        PaymentRecordForReimbursementWallet(
            payment_status="NEW",
            procedure_id=1,
            procedure_title="TB12",
            created_at=None,
            error_type="hi",
        ),
        PaymentRecordForReimbursementWallet(
            payment_status="NEW",
            procedure_id=1,
            procedure_title="TB12",
            created_at=None,
        ),
    ]
    assert compute_num_errors(payments) == 2


def test_compute_summary_for_reimbursement_wallet():
    # It should filter out the PROCESSING bills
    upcoming_payment_records = [
        PaymentRecordForReimbursementWallet(
            payment_status="PROCESSING",
            procedure_id=123,
            procedure_title="this title is correct",
            created_at=datetime(2023, 12, 25),
            member_amount=1,
            member_method="***123",
            benefit_amount=1,
            error_type="REQUIRES_UPDATE_PAYMENT",
            # Should not choose this benefit_remaining
            benefit_remaining=4,
            bill_uuid=str(uuid.uuid4()),
            processing_scheduled_at_or_after=datetime.strptime(
                "2024-01-01", "%Y-%m-%d"
            ),
        ),
        PaymentRecordForReimbursementWallet(
            payment_status="NEW",
            procedure_id=2,
            procedure_title="and do not select this title",
            created_at=datetime(2024, 1, 25),
            member_amount=2,
            member_method="not this one either",
            benefit_amount=2,
            error_type=None,
            # Should not choose this benefit_remaining
            benefit_remaining=1,
            bill_uuid=str(uuid.uuid4()),
            processing_scheduled_at_or_after=datetime.strptime(
                "2024-02-01", "%Y-%m-%d"
            ),
        ),
        PaymentRecordForReimbursementWallet(
            payment_status="FAILED",
            procedure_id=3,
            # Should choose this title (last one)
            procedure_title="do not select this title",
            created_at=datetime(2024, 2, 25),
            member_amount=3,
            member_method="not this one",
            benefit_amount=3,
            error_type=None,
            # Should choose this benefit_remaining
            benefit_remaining=100,
            bill_uuid=str(uuid.uuid4()),
            processing_scheduled_at_or_after=datetime.strptime(
                "2024-01-03", "%Y-%m-%d"
            ),
        ),
        PaymentRecordForReimbursementWallet(
            payment_status="PROCESSING",
            procedure_id=321,
            # Should choose this title (last one)
            procedure_title="do not select this title either",
            created_at=datetime(2024, 2, 25),
            member_amount=5,
            member_method="not this one either",
            benefit_amount=3,
            error_type=None,
            # Should choose this benefit_remaining
            benefit_remaining=50,
            bill_uuid=str(uuid.uuid4()),
            processing_scheduled_at_or_after=None,
        ),
    ]
    result = compute_summary_for_reimbursement_wallet(upcoming_payment_records)
    expected_result = UpcomingPaymentsAndSummaryForReimbursementWallet(
        summary=(
            UpcomingPaymentSummaryForReimbursementWallet(
                # total_member_amount should exclude PENDING payments
                total_member_amount=11,
                # total_benefit_amount should not exclude pending payments
                total_benefit_amount=9,
                # Take the last nonempty member_method
                member_method="***123",
                # Take the last benefit_remaining
                benefit_remaining=50,
                # Take the last nonempty title.
                procedure_title="this title is correct",
            )
        ),
        payments=upcoming_payment_records,
    )
    assert result == expected_result
