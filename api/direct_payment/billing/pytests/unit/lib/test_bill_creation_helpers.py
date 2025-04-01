from __future__ import annotations

import datetime
from unittest.mock import patch

import pytest

from direct_payment.billing.constants import MEMBER_BILLING_OFFSET_DAYS
from direct_payment.billing.lib.bill_creation_helpers import (
    calculate_fee,
    compute_processing_scheduled_at_or_after,
)
from direct_payment.billing.models import (
    CardFunding,
    PaymentMethod,
    PaymentMethodType,
    PayorType,
)
from direct_payment.billing.pytests.factories import BillFactory
from direct_payment.invoicing.pytests.factories import (
    OrganizationInvoicingSettingsFactory,
)
from direct_payment.invoicing.repository.organization_invoicing_settings import (
    OrganizationInvoicingSettingsRepository,
)
from direct_payment.treatment_procedure.models.treatment_procedure import (
    TreatmentProcedureStatus,
)
from pytests import freezegun
from pytests.factories import OrganizationFactory
from storage import connection
from wallet.pytests.factories import ReimbursementOrganizationSettingsFactory

INVOICED_EMPLOYER_BILLING_OFFSET_DAYS = 14
CURRENT_TIME = datetime.datetime(2024, 3, 1, 10, 30, 0)
OFFSET_BILL_TIME = CURRENT_TIME + datetime.timedelta(days=MEMBER_BILLING_OFFSET_DAYS)
OFFSET_EMPLOYER_BILL_TIME = CURRENT_TIME + datetime.timedelta(
    days=INVOICED_EMPLOYER_BILLING_OFFSET_DAYS
)


class TestBillCreationHelpers:
    @pytest.mark.parametrize(
        argnames="inp_payor_type, inp_amount, mocked_tp_dict, exp_res",
        ids=[
            " 1.  Clinic transfer with no TP information",
            " 2.  Clinic transfer with PARTIALLY_COMPLETED TP",
            " 3.  Clinic transfer with COMPLETED TP",
            " 4. Member charge with no TP information",
            " 5. Member charge with SCHEDULED TP",
            " 6. Member charge with PARTIALLY_COMPLETED TP",
            " 7. Member charge with COMPLETED TP",
            " 8. Member refund with no TP information",
            " 9. Member refund with SCHEDULED TP",
            "10. Member refund with PARTIALLY_COMPLETED TP",
            "11. Member refund with COMPLETED TP",  #
        ],
        argvalues=(
            (PayorType.CLINIC, 3300, {}, CURRENT_TIME),
            (
                PayorType.CLINIC,
                3400,
                {"status": TreatmentProcedureStatus("PARTIALLY_COMPLETED")},
                CURRENT_TIME,
            ),
            (
                PayorType.CLINIC,
                3500,
                {"status": TreatmentProcedureStatus("COMPLETED")},
                CURRENT_TIME,
            ),
            (PayorType.MEMBER, 3550, {}, None),
            (
                PayorType.MEMBER,
                3900,
                {"status": TreatmentProcedureStatus("SCHEDULED")},
                None,
            ),
            (
                PayorType.MEMBER,
                4000,
                {"status": TreatmentProcedureStatus("PARTIALLY_COMPLETED")},
                OFFSET_BILL_TIME,
            ),
            (
                PayorType.MEMBER,
                4100,
                {"status": TreatmentProcedureStatus("COMPLETED")},
                OFFSET_BILL_TIME,
            ),
            (PayorType.MEMBER, -4150, {}, CURRENT_TIME),
            (
                PayorType.MEMBER,
                -3600,
                {"status": TreatmentProcedureStatus("SCHEDULED")},
                CURRENT_TIME,
            ),
            (
                PayorType.MEMBER,
                -3700,
                {"status": TreatmentProcedureStatus("PARTIALLY_COMPLETED")},
                CURRENT_TIME,
            ),
            (
                PayorType.MEMBER,
                -3800,
                {"status": TreatmentProcedureStatus("COMPLETED")},
                CURRENT_TIME,
            ),
        ),
    )
    def test_compute_processing_scheduled_at_or_after(
        self,
        billing_service,
        inp_payor_type,
        inp_amount,
        mocked_tp_dict,
        exp_res,
    ):
        bill = BillFactory.build(payor_type=inp_payor_type, amount=inp_amount)

        billing_service.bill_repo.create(instance=bill)
        with freezegun.freeze_time(CURRENT_TIME), patch(
            "direct_payment.billing.lib.bill_creation_helpers.get_treatment_procedure_as_dict_from_id",
            return_value=mocked_tp_dict,
        ):
            res = compute_processing_scheduled_at_or_after(
                inp_payor_type, inp_amount, CURRENT_TIME, bill.procedure_id
            )
            assert res == exp_res

    @pytest.mark.parametrize(
        argnames="inp_payor_type, inp_amount, mocked_tp_dict, is_invoiced_org, exp_res",
        ids=[
            "1. Invoiced Org. Employer charge with no TP information",
            "2. Invoiced Org. Employer charge with PARTIALLY_COMPLETED TP",
            "3. Invoiced Org. Employer charge with COMPLETED TP",
            "4. Invoiced Org. Employer refund with no TP information",
            "5. Invoiced Org. Employer refund with PARTIALLY_COMPLETED TP",
            "6. Invoiced Org. Employer refund with COMPLETED TP",
            "7. Non-Invoiced Org. Employer charge with no TP information",
            "8. Non-Invoiced Org. Employer charge with PARTIALLY_COMPLETED TP",
            "9. Non-Invoiced Org. Employer charge with COMPLETED TP",
            "10. Non-Invoiced Org. Employer refund with no TP information",
            "11. Non-Invoiced Org. Employer refund with PARTIALLY_COMPLETED TP",
            "12. Non-Invoiced Org. Employer refund with COMPLETED TP",
        ],
        argvalues=(
            (
                PayorType.EMPLOYER,
                1000,
                {},
                True,
                OFFSET_EMPLOYER_BILL_TIME,
            ),
            (
                PayorType.EMPLOYER,
                2900,
                {"status": TreatmentProcedureStatus("PARTIALLY_COMPLETED")},
                True,
                OFFSET_EMPLOYER_BILL_TIME,
            ),
            (
                PayorType.EMPLOYER,
                3000,
                {"status": TreatmentProcedureStatus("COMPLETED")},
                True,
                OFFSET_EMPLOYER_BILL_TIME,
            ),
            (
                PayorType.EMPLOYER,
                -3050,
                {},
                True,
                OFFSET_EMPLOYER_BILL_TIME,
            ),
            (
                PayorType.EMPLOYER,
                -3100,
                {"status": TreatmentProcedureStatus("PARTIALLY_COMPLETED")},
                True,
                OFFSET_EMPLOYER_BILL_TIME,
            ),
            (
                PayorType.EMPLOYER,
                -3200,
                {"status": TreatmentProcedureStatus("COMPLETED")},
                True,
                OFFSET_EMPLOYER_BILL_TIME,
            ),
            (
                PayorType.EMPLOYER,
                1000,
                {},
                False,
                CURRENT_TIME,
            ),
            (
                PayorType.EMPLOYER,
                2900,
                {"status": TreatmentProcedureStatus("PARTIALLY_COMPLETED")},
                False,
                CURRENT_TIME,
            ),
            (
                PayorType.EMPLOYER,
                3000,
                {"status": TreatmentProcedureStatus("COMPLETED")},
                False,
                CURRENT_TIME,
            ),
            (
                PayorType.EMPLOYER,
                -3050,
                {},
                False,
                CURRENT_TIME,
            ),
            (
                PayorType.EMPLOYER,
                -3100,
                {"status": TreatmentProcedureStatus("PARTIALLY_COMPLETED")},
                False,
                CURRENT_TIME,
            ),
            (
                PayorType.EMPLOYER,
                -3200,
                {"status": TreatmentProcedureStatus("COMPLETED")},
                False,
                CURRENT_TIME,
            ),
        ),
    )
    def test_compute_processing_scheduled_at_or_after_for_employer(
        self,
        billing_service,
        ff_test_data,
        create_ois_and_ros,
        inp_payor_type,
        inp_amount,
        mocked_tp_dict,
        is_invoiced_org,
        exp_res,
    ):
        bill = BillFactory.build(
            payor_type=inp_payor_type,
            amount=inp_amount,
            payor_id=(create_ois_and_ros(is_invoiced_org)),
        )
        billing_service.bill_repo.create(instance=bill)
        with freezegun.freeze_time(CURRENT_TIME), patch(
            "direct_payment.billing.lib.bill_creation_helpers.get_treatment_procedure_as_dict_from_id",
            return_value=mocked_tp_dict,
        ):

            res_2 = compute_processing_scheduled_at_or_after(
                inp_payor_type,
                inp_amount,
                CURRENT_TIME,
                bill.procedure_id,
                bill.payor_id,
            )
            assert res_2 == exp_res

    @pytest.mark.parametrize(
        "payment_method, payment_method_type, amount, expected_fee",
        [
            (PaymentMethod.PAYMENT_GATEWAY, PaymentMethodType.card, 10001, 300),
            (PaymentMethod.WRITE_OFF, PaymentMethodType.card, 10001, 0),
            (
                PaymentMethod.PAYMENT_GATEWAY,
                PaymentMethodType.us_bank_account,
                10101,
                0,
            ),
        ],
    )
    def test_calculate_fee(
        self, billing_service, payment_method, payment_method_type, amount, expected_fee
    ):
        res = calculate_fee(payment_method, payment_method_type, amount)
        assert res == expected_fee

    @pytest.mark.parametrize(
        argnames="card_funding, amount, expected_fee",
        argvalues=[
            (CardFunding.PREPAID, 100, 0),
            (CardFunding.CREDIT, 100, 3),
            (CardFunding.DEBIT, 100, 0),
            (CardFunding.UNKNOWN, 100, 0),
        ],
        ids=[
            "0% fee for prepaid card",
            "3% fee for credit card",
            "0% fee for debit card",
            "0% fee for unknown card funding",
        ],
    )
    def test_calculate_fee_with_new_calculation(
        self,
        ff_test_data,
        billing_service,
        amount,
        expected_fee,
        card_funding,
    ):
        # When
        res = calculate_fee(
            PaymentMethod.PAYMENT_GATEWAY, PaymentMethodType.card, amount, card_funding
        )

        # Then
        assert res == expected_fee


@pytest.fixture
def create_ois_and_ros():
    def fn(create_ois_flag):
        org = OrganizationFactory.create()
        ros = ReimbursementOrganizationSettingsFactory.create(organization_id=org.id)
        if create_ois_flag:
            ois_repo = OrganizationInvoicingSettingsRepository(
                session=connection.db.session, is_in_uow=True
            )

            ois_repo.create(
                instance=(
                    OrganizationInvoicingSettingsFactory.build(
                        organization_id=org.id,
                        bill_processing_delay_days=INVOICED_EMPLOYER_BILLING_OFFSET_DAYS,
                    )
                )
            )

        return ros.id

    return fn
