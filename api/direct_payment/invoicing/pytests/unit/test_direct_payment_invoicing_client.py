import uuid
from collections import defaultdict
from dataclasses import fields
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

import pytest

from direct_payment.billing.billing_service import BillingService
from direct_payment.billing.models import Bill, BillStatus, PayorType
from direct_payment.billing.pytests import factories as bill_factories
from direct_payment.invoicing.direct_payment_invoicing_client import (
    DEFAULT_BILL_CUTOFF_AT_BUFFER_DAYS,
    DEFAULT_BILL_PROCESSING_DELAY_DAYS,
    DirectPaymentInvoicingClient,
)
from direct_payment.invoicing.models import (
    BillInformation,
    BillingReport,
    OrganizationInvoicingSettings,
    Process,
)
from pytests.factories import OrganizationFactory
from utils.random_string import generate_random_string
from wallet.pytests.factories import ReimbursementOrganizationSettingsFactory

T = datetime.now(timezone.utc)
T_MINUS_15 = T - timedelta(days=15)
T_MINUS_20 = T - timedelta(days=15)
T_MINUS_35 = T - timedelta(days=35)
T_PLUS_1 = T + timedelta(days=1)


class TestInvoicingSetting:
    def test_invoicing_setting_creation_normal_case(
        self, organization_invoicing_settings_repository
    ):
        org = OrganizationFactory.create()
        client = DirectPaymentInvoicingClient()
        invoice_cadence = "* * * * *"
        created_by_user_id = 123

        result = client.create_invoice_setting(
            organization_id=org.id,
            created_by_user_id=created_by_user_id,
            invoicing_active_at=datetime.utcnow(),
            invoice_cadence=invoice_cadence,
            bill_processing_delay_days=15,
            bill_cutoff_at_buffer_days=5,
        )

        assert isinstance(result, OrganizationInvoicingSettings)

        ois = organization_invoicing_settings_repository.get_by_organization_id(
            organization_id=org.id
        )
        assert ois is not None
        assert ois.invoice_cadence == invoice_cadence
        assert ois.created_by_user_id == created_by_user_id
        assert ois.updated_by_user_id == created_by_user_id
        assert ois.bill_processing_delay_days == 15
        assert ois.bill_cutoff_at_buffer_days == 5

    def test_invoicing_setting_creation_null_value(
        self, organization_invoicing_settings_repository
    ):
        org = OrganizationFactory.create()
        client = DirectPaymentInvoicingClient()
        created_by_user_id = 123

        result = client.create_invoice_setting(
            organization_id=org.id,
            created_by_user_id=created_by_user_id,
            invoicing_active_at=datetime.utcnow(),
        )

        assert isinstance(result, OrganizationInvoicingSettings)

        ois = organization_invoicing_settings_repository.get_by_organization_id(
            organization_id=org.id
        )
        assert ois is not None
        assert ois.invoice_cadence is None
        assert ois.created_by_user_id == created_by_user_id
        assert ois.updated_by_user_id == created_by_user_id
        assert ois.bill_processing_delay_days == DEFAULT_BILL_PROCESSING_DELAY_DAYS
        assert ois.bill_cutoff_at_buffer_days == DEFAULT_BILL_CUTOFF_AT_BUFFER_DAYS

    def test_invoicing_setting_creation_invalid_org_id(
        self, organization_invoicing_settings_repository
    ):
        org = OrganizationFactory.create()
        client = DirectPaymentInvoicingClient()
        invoice_cadence = "* * * * *"
        created_by_user_id = 123

        result = client.create_invoice_setting(
            organization_id=org.id + 1,
            created_by_user_id=created_by_user_id,
            invoicing_active_at=datetime.utcnow(),
            invoice_cadence=invoice_cadence,
            bill_processing_delay_days=15,
            bill_cutoff_at_buffer_days=5,
        )

        assert isinstance(result, str)
        assert "IntegrityError" in result

        ois = organization_invoicing_settings_repository.get_by_organization_id(
            organization_id=(org.id + 1)
        )
        assert ois is None

    def test_invoicing_setting_creation_invalid_cadence(
        self, organization_invoicing_settings_repository
    ):
        org = OrganizationFactory.create()
        client = DirectPaymentInvoicingClient()
        invoice_cadence = "lol"
        created_by_user_id = 123

        result = client.create_invoice_setting(
            organization_id=org.id + 1,
            created_by_user_id=created_by_user_id,
            invoicing_active_at=datetime.utcnow(),
            invoice_cadence=invoice_cadence,
            bill_processing_delay_days=15,
            bill_cutoff_at_buffer_days=5,
        )

        assert isinstance(result, str)
        assert "The cron expression of the invoice cadence is invalid" in result

        ois = organization_invoicing_settings_repository.get_by_organization_id(
            organization_id=(org.id + 1)
        )
        assert ois is None

    def test_invoicing_setting_update(self, organization_invoicing_settings_repository):
        org = OrganizationFactory.create()
        client = DirectPaymentInvoicingClient()
        invoice_cadence = "* * * * *"
        created_by_user_id = 123

        client.create_invoice_setting(
            organization_id=org.id,
            created_by_user_id=created_by_user_id,
            invoicing_active_at=datetime.utcnow(),
            invoice_cadence=invoice_cadence,
            bill_processing_delay_days=15,
            bill_cutoff_at_buffer_days=5,
        )

        ois = organization_invoicing_settings_repository.get_by_organization_id(
            organization_id=org.id
        )
        assert ois is not None

        updated_by_user_id = 456
        result = client.update_invoicing_setting(
            existing_invoicing_setting=ois,
            updated_by_user_id=updated_by_user_id,
            invoice_cadence="* * * * 5",
        )
        assert isinstance(result, OrganizationInvoicingSettings)

        ois = organization_invoicing_settings_repository.get_by_organization_id(
            organization_id=org.id
        )
        assert ois is not None
        assert ois.invoice_cadence == "* * * * 5"
        assert ois.created_by_user_id == created_by_user_id
        assert ois.updated_by_user_id == updated_by_user_id
        assert ois.bill_processing_delay_days == DEFAULT_BILL_PROCESSING_DELAY_DAYS
        assert ois.bill_cutoff_at_buffer_days == DEFAULT_BILL_CUTOFF_AT_BUFFER_DAYS

    def test_invoicing_setting_update_invalid_input(
        self, organization_invoicing_settings_repository
    ):
        org = OrganizationFactory.create()
        client = DirectPaymentInvoicingClient()
        invoice_cadence = "* * * * *"
        created_by_user_id = 123

        client.create_invoice_setting(
            organization_id=org.id,
            created_by_user_id=created_by_user_id,
            invoicing_active_at=datetime.utcnow(),
            invoice_cadence=invoice_cadence,
            bill_processing_delay_days=15,
            bill_cutoff_at_buffer_days=5,
        )

        ois = organization_invoicing_settings_repository.get_by_organization_id(
            organization_id=org.id
        )
        assert ois is not None

        updated_by_user_id = 456
        result = client.update_invoicing_setting(
            existing_invoicing_setting=ois,
            updated_by_user_id=updated_by_user_id,
            invoice_cadence="lol",
        )
        assert isinstance(result, str)
        assert "The cron expression of the invoice cadence is invalid" in result

        ois = organization_invoicing_settings_repository.get_by_organization_id(
            organization_id=org.id
        )
        assert ois is not None
        assert ois.invoice_cadence == "* * * * *"
        assert ois.created_by_user_id == created_by_user_id
        assert ois.updated_by_user_id == created_by_user_id
        assert ois.bill_processing_delay_days == 15
        assert ois.bill_cutoff_at_buffer_days == 5

    def test_invoicing_setting_deletion(
        self, organization_invoicing_settings_repository
    ):
        org = OrganizationFactory.create()
        client = DirectPaymentInvoicingClient()
        user_id = 123

        client.create_invoice_setting(
            organization_id=org.id,
            created_by_user_id=user_id,
            invoicing_active_at=datetime.utcnow(),
        )

        ois = organization_invoicing_settings_repository.get_by_organization_id(
            organization_id=org.id
        )
        assert ois is not None

        error_message = client.delete_invoicing_setting(
            invoicing_setting_id=ois.id, deleted_by_user_id=user_id
        )
        assert error_message is None

        ois = organization_invoicing_settings_repository.get_by_organization_id(
            organization_id=org.id
        )
        assert ois is None


class TestDeleteInvoice:
    def test_invoice_deletion(
        self,
        new_direct_payment_invoice,
        new_direct_payment_invoice_bill_allocation,
        direct_payment_invoice_repository,
        direct_payment_invoice_bill_allocation_repository,
    ):
        invoice = direct_payment_invoice_repository.get(
            id=new_direct_payment_invoice.id
        )
        assert str(invoice.uuid) == str(new_direct_payment_invoice.uuid)

        invoice_bill_allocation = direct_payment_invoice_bill_allocation_repository.get(
            id=new_direct_payment_invoice_bill_allocation.id
        )
        assert str(invoice_bill_allocation.uuid) == str(
            new_direct_payment_invoice_bill_allocation.uuid
        )
        assert (
            invoice_bill_allocation.direct_payment_invoice_id
            == new_direct_payment_invoice.id
        )

        client = DirectPaymentInvoicingClient()
        client.delete_invoice(
            invoice_id=new_direct_payment_invoice.id, deleted_by_user_id=123
        )

        # Check if invoice is deleted
        invoice = direct_payment_invoice_repository.get(
            id=new_direct_payment_invoice.id
        )
        assert invoice is None

        # Check if the bills allocated to the invoice are deleted
        invoice_bill_allocation = direct_payment_invoice_bill_allocation_repository.get(
            id=new_direct_payment_invoice_bill_allocation.id
        )
        assert invoice_bill_allocation is None


class TestProcessInvoiceBills:
    def test_process_invoice_bills_successful_processing(
        self,
        invoice_bills,
        create_mock_response_fixture,
        bill_repository,
        bill_processing_record_repository,
    ):
        client = DirectPaymentInvoicingClient()

        mocked_cust_uuid = uuid.uuid4()
        with patch(
            "direct_payment.billing.billing_service.payments_customer_id",
        ) as _get_customer_id_from_payor_mock:
            with patch(
                "common.base_triforce_client.BaseTriforceClient.make_service_request",
            ) as mock_make_request:
                mock_make_request.return_value = create_mock_response_fixture(
                    transaction_data={"test_key": "test_transaction_data"},
                    uuid_param_str=str(uuid.uuid4()),
                    metadata={"source_id": "test_pg", "source_type": "test_pg_type"},
                )

                _get_customer_id_from_payor_mock.return_value = mocked_cust_uuid
                finished_bills, exception_bills = client.process_invoice_bills()

                assert len(finished_bills) == 2
                assert len(exception_bills) == 0

                finished_bill_map = {
                    str(finished_bill.uuid): finished_bill
                    for finished_bill in finished_bills
                }

                finished_small_amount_bill = finished_bill_map.get(
                    str(invoice_bills[3].uuid)
                )
                assert finished_small_amount_bill is not None

                finished_large_amount_bill = finished_bill_map.get(
                    str(invoice_bills[5].uuid)
                )
                assert finished_large_amount_bill is not None

                # Test if the small-amount bill's status is changed to PAID
                bill: Bill = bill_repository.get_by_uuid(
                    finished_small_amount_bill.uuid
                )
                assert bill is not None
                assert str(bill.uuid) == str(invoice_bills[3].uuid)
                assert bill.status == BillStatus.PAID

                # Test if the clinic bill is generated from the amount-amount employer bill
                clinic_bills = (
                    bill_repository.get_bills_by_procedure_id_payor_type_status(
                        bill.procedure_id,
                        PayorType.CLINIC,
                        [BillStatus.PAID, BillStatus.PROCESSING],
                    )
                )
                assert len(clinic_bills) == 1

                # Test if the large-amount bill's status is changed to PROCESSING
                bill: Bill = bill_repository.get_by_uuid(
                    finished_large_amount_bill.uuid
                )
                assert bill is not None
                assert str(bill.uuid) == str(invoice_bills[5].uuid)
                assert bill.status == BillStatus.PROCESSING

                # Test if bill processing records are created
                bill_processing_records = bill_processing_record_repository.all()
                assert len(bill_processing_records) == 6

                count_of_employer_bill_processing_records_from_small_amount_bill = 0
                count_of_employer_bill_processing_records_from_large_amount_bill = 0
                count_of_clinic_bill_processing_records_from_small_amount_bill = 0
                for bill_processing_record in bill_processing_records:
                    if bill_processing_record.bill_id == finished_small_amount_bill.id:
                        count_of_employer_bill_processing_records_from_small_amount_bill = (
                            count_of_employer_bill_processing_records_from_small_amount_bill
                            + 1
                        )
                        assert bill_processing_record.bill_status in (
                            "PROCESSING",
                            "PAID",
                        )
                        assert (
                            bill_processing_record.processing_record_type
                            == "billing_service_workflow"
                        )
                    elif (
                        bill_processing_record.bill_id == finished_large_amount_bill.id
                    ):
                        count_of_employer_bill_processing_records_from_large_amount_bill = (
                            count_of_employer_bill_processing_records_from_large_amount_bill
                            + 1
                        )
                        assert bill_processing_record.bill_status == "PROCESSING"
                        assert bill_processing_record.processing_record_type in (
                            "payment_gateway_request",
                            "payment_gateway_response",
                        )
                    elif bill_processing_record.bill_id == clinic_bills[0].id:
                        count_of_clinic_bill_processing_records_from_small_amount_bill = (
                            count_of_clinic_bill_processing_records_from_small_amount_bill
                            + 1
                        )
                        assert bill_processing_record.bill_status in (
                            "PROCESSING",
                            "PAID",
                        )
                        assert bill_processing_record.processing_record_type in (
                            "payment_gateway_request",
                            "payment_gateway_response",
                        )
                    else:
                        raise Exception("Unexpected bill id")

                assert (
                    count_of_employer_bill_processing_records_from_small_amount_bill
                    == 2
                )
                assert (
                    count_of_employer_bill_processing_records_from_large_amount_bill
                    == 2
                )
                assert (
                    count_of_clinic_bill_processing_records_from_small_amount_bill == 2
                )

    def test_process_invoice_bills_failed_processing(
        self,
        invoice_bills,
        create_mock_response_fixture,
        bill_repository,
        bill_processing_record_repository,
    ):
        client = DirectPaymentInvoicingClient()

        with patch(
            "direct_payment.billing.billing_service.payments_customer_id",
        ) as _get_customer_id_from_payor_mock:
            _get_customer_id_from_payor_mock.return_value = None
            finished_bills, exception_bills = client.process_invoice_bills()

            # One finished bill which has a small amount
            assert len(finished_bills) == 1
            # One failed bill which has a large enough amount but no custom id
            assert len(exception_bills) == 1
            assert str(finished_bills[0].uuid) == str(invoice_bills[3].uuid)
            assert str(exception_bills[0].uuid) == str(invoice_bills[5].uuid)

            # Check if the status of the small-amount bill is PAID
            bill: Bill = bill_repository.get_by_uuid(finished_bills[0].uuid)
            assert bill is not None
            assert str(bill.uuid) == str(invoice_bills[3].uuid)
            assert bill.status == BillStatus.PAID

            # Check if the status of the large-amount bill is FAID
            bill: Bill = bill_repository.get_by_uuid(exception_bills[0].uuid)
            assert bill is not None
            assert str(bill.uuid) == str(invoice_bills[5].uuid)
            assert bill.status == BillStatus.FAILED

            # Test if bill processing records are created
            bill_processing_records = bill_processing_record_repository.all()

            assert len(bill_processing_records) == 3

            for bill_processing_record in bill_processing_records:
                if bill_processing_record.bill_status == "FAILED":
                    assert (
                        bill_processing_record.processing_record_type
                        == "billing_service_workflow"
                    )
                    assert bill_processing_record.bill_id == exception_bills[0].id
                elif bill_processing_record.bill_status in ("PROCESSING", "PAID"):
                    assert (
                        bill_processing_record.processing_record_type
                        == "billing_service_workflow"
                    )
                    assert bill_processing_record.bill_id == finished_bills[0].id
                else:
                    raise Exception("Unexpected bill status")


class TestGetAllInvoiceSettings:
    def test_get_all_invoice_setting(
        self,
        new_organization_invoicing_settings_fixed_buffer,
    ):
        client = DirectPaymentInvoicingClient()
        invoice_settings = client.get_all_invoice_settings()

        loaded_id_to_invoice_setting_map = {
            invoice_setting.id: invoice_setting for invoice_setting in invoice_settings
        }

        assert len(loaded_id_to_invoice_setting_map) == 1

        loaded_invoice_setting = loaded_id_to_invoice_setting_map.get(
            new_organization_invoicing_settings_fixed_buffer.id
        )
        assert (
            loaded_invoice_setting == new_organization_invoicing_settings_fixed_buffer
        )


class TestCreateInvoicesAndAllocate:
    @pytest.mark.parametrize(
        argnames="ros_direct_payment_enabled_flags, inputs, previous_invoices, expected_invoiced_bills",
        argvalues=[
            (
                [True, True],
                [
                    (BillStatus.NEW, T_MINUS_35, 0),
                    (BillStatus.FAILED, T_MINUS_35, 0),
                    (BillStatus.PAID, T_MINUS_35, 1),
                    (BillStatus.NEW, T_MINUS_35, 1),
                    (BillStatus.NEW, T_PLUS_1, 0),
                    (BillStatus.NEW, T_MINUS_35, 1),
                ],
                False,
                {0, 3, 5},
            ),
            (
                [True, True, False],
                [
                    (BillStatus.NEW, T_MINUS_15, 0),
                    (BillStatus.NEW, T_MINUS_35, 1),
                    (BillStatus.NEW, T_MINUS_35, 1),
                ],
                False,
                {0, 1, 2},
            ),
            (
                [True],
                [
                    (BillStatus.NEW, T_MINUS_35, 0),
                    (BillStatus.PAID, T_MINUS_35, 0),
                    (BillStatus.FAILED, T_MINUS_35, 0),
                    (BillStatus.NEW, T_PLUS_1, 0),
                    (BillStatus.NEW, T_MINUS_35, 0),
                ],
                False,
                {0, 4},
            ),
            (
                [True, False],
                [
                    (BillStatus.PAID, T_MINUS_35, 0),
                    (BillStatus.FAILED, T_MINUS_35, 0),
                    (BillStatus.NEW, T_PLUS_1, 0),
                ],
                False,
                set(),
            ),
            (
                [True, False],
                [
                    (BillStatus.NEW, T_MINUS_35, 0),
                    (BillStatus.FAILED, T_MINUS_35, 0),
                    (BillStatus.PAID, T_MINUS_35, 1),
                    (BillStatus.NEW, T_MINUS_35, 1),
                    (BillStatus.NEW, T_PLUS_1, 0),
                    (BillStatus.NEW, T_MINUS_35, 1),
                ],
                True,
                set(),
            ),
            (
                [True, True, False],
                [
                    (BillStatus.NEW, T_MINUS_15, 0),
                    (BillStatus.FAILED, T_MINUS_35, 0),
                    (BillStatus.PAID, T_MINUS_35, 1),
                    (BillStatus.NEW, T_MINUS_35, 1),
                    (BillStatus.NEW, T_PLUS_1, 0),
                    (BillStatus.NEW, T_MINUS_35, 1),
                ],
                True,
                {0},
            ),
        ],
        ids=[
            "two ROS, both dp enabled - some eligible bills - mixed statuses and dates",
            "three ROS, two dp enabled - all bills eligible",
            "one ROS, dp enabled - some eligible bills - mixed statuses and date",
            "two ROS, one enabled, no eligible bills",
            "two ROS, one enabled, all bills in previous invoice",
            "Three ROS, two enabled, some bills in previous invoice",
        ],
    )
    def test_create_invoices_and_allocate(
        self,
        new_organization_invoicing_settings_fixed_buffer,
        new_direct_payment_invoice_for_ros,
        ros_direct_payment_enabled_flags,
        inputs,
        previous_invoices,
        expected_invoiced_bills,
    ):
        ois = new_organization_invoicing_settings_fixed_buffer
        roses = [
            ReimbursementOrganizationSettingsFactory.create(
                organization_id=ois.organization_id,
                direct_payment_enabled=direct_payment_enabled,
            )
            for direct_payment_enabled in ros_direct_payment_enabled_flags
        ]
        if previous_invoices:
            for ros in roses:
                new_direct_payment_invoice_for_ros(ros, T_MINUS_35, T_MINUS_20)

        billing_service = BillingService()
        ros_bills_map = defaultdict(set)

        for i, inp in enumerate(inputs):
            ros_id = roses[inp[2]].id
            bill = bill_factories.BillFactory(
                status=inp[0],
                payor_type=PayorType.EMPLOYER,
                payor_id=ros_id,
                created_at=inp[1],
            )
            billing_service.bill_repo.create(instance=bill)
            if i in expected_invoiced_bills:
                ros_bills_map[ros_id].add(bill.uuid)

        client = DirectPaymentInvoicingClient()
        res = client.create_invoices_and_allocate(
            organization_id=ois.organization_id,
            created_by_process=Process.INVOICE_GENERATOR,
            created_by_user_id=None,
        )

        expected_enabled_count = sum(ros_direct_payment_enabled_flags)
        assert (
            len(res) == expected_enabled_count
        ), f"Expected {expected_enabled_count} results, got {len(res)}"

        report_field_names_bill_report = [field.name for field in fields(BillingReport)]
        report_field_names_bill_information = [
            field.name for field in fields(BillInformation)
        ]

        for inv_id, allocs in res.items():
            if allocs:
                assert len({alloc.direct_payment_invoice_id for alloc in allocs}) == 1
                assert allocs[0].direct_payment_invoice_id == inv_id

                res_bills = {str(alloc.bill_uuid) for alloc in allocs}
                invoice = client._invoicing_service.get_invoice(invoice_id=inv_id)
                assert (
                    res_bills
                    == ros_bills_map[invoice.reimbursement_organization_settings_id]
                )

                assert invoice.report_generated_at is not None
                assert invoice.report_generated_json is not None

                for report_field_name in report_field_names_bill_report:
                    assert report_field_name in invoice.report_generated_json

                for report_field_name in report_field_names_bill_information:
                    assert report_field_name in invoice.report_generated_json

    def test_no_org_invoicing_setting(
        self,
    ):
        _ = [
            ReimbursementOrganizationSettingsFactory.create(
                organization_id=12345, direct_payment_enabled=True
            )
            for _ in range(2)
        ]

        res = DirectPaymentInvoicingClient().create_invoices_and_allocate(
            organization_id=12345,
            created_by_process=Process.INVOICE_GENERATOR,
            created_by_user_id=None,
        )
        assert res == {}

    @pytest.mark.parametrize(
        argnames="ros_direct_payment_enabled_flags, inputs, previous_invoices, expected_invoiced_bills",
        argvalues=[
            (
                [True, True],
                [
                    (BillStatus.NEW, T_MINUS_35, 0),
                    (BillStatus.FAILED, T_MINUS_35, 0),
                    (BillStatus.PAID, T_MINUS_35, 1),
                    (BillStatus.NEW, T_MINUS_35, 1),
                    (BillStatus.NEW, T_PLUS_1, 0),
                    (BillStatus.NEW, T_MINUS_35, 1),
                ],
                False,
                {0, 3, 5},
            ),
            (
                [True, True, False],
                [
                    (BillStatus.NEW, T_MINUS_15, 0),
                    (BillStatus.NEW, T_MINUS_35, 1),
                    (BillStatus.NEW, T_MINUS_35, 1),
                ],
                False,
                {0, 1, 2},
            ),
            (
                [True],
                [
                    (BillStatus.NEW, T_MINUS_35, 0),
                    (BillStatus.PAID, T_MINUS_35, 0),
                    (BillStatus.FAILED, T_MINUS_35, 0),
                    (BillStatus.NEW, T_PLUS_1, 0),
                    (BillStatus.NEW, T_MINUS_35, 0),
                ],
                False,
                {0, 4},
            ),
            (
                [True, False],
                [
                    (BillStatus.PAID, T_MINUS_35, 0),
                    (BillStatus.FAILED, T_MINUS_35, 0),
                    (BillStatus.NEW, T_PLUS_1, 0),
                ],
                False,
                set(),
            ),
            (
                [True, False],
                [
                    (BillStatus.NEW, T_MINUS_35, 0),
                    (BillStatus.FAILED, T_MINUS_35, 0),
                    (BillStatus.PAID, T_MINUS_35, 1),
                    (BillStatus.NEW, T_MINUS_35, 1),
                    (BillStatus.NEW, T_PLUS_1, 0),
                    (BillStatus.NEW, T_MINUS_35, 1),
                ],
                True,
                set(),
            ),
            (
                [True, True, False],
                [
                    (BillStatus.NEW, T_MINUS_15, 0),
                    (BillStatus.FAILED, T_MINUS_35, 0),
                    (BillStatus.PAID, T_MINUS_35, 1),
                    (BillStatus.NEW, T_MINUS_35, 1),
                    (BillStatus.NEW, T_PLUS_1, 0),
                    (BillStatus.NEW, T_MINUS_35, 1),
                ],
                True,
                {0},
            ),
        ],
        ids=[
            "two ROS, both dp enabled - some eligible bills - mixed statuses and dates",
            "three ROS, two dp enabled - all bills eligible",
            "one ROS, dp enabled - some eligible bills - mixed statuses and date",
            "two ROS, one enabled, no eligible bills",
            "two ROS, one enabled, all bills in previous invoice",
            "Three ROS, two enabled, some bills in previous invoice",
        ],
    )
    def test_invalid_report_cadence(
        self,
        new_organization_invoicing_setting_invalid_cadence,
        new_direct_payment_invoice_for_ros,
        ros_direct_payment_enabled_flags,
        inputs,
        previous_invoices,
        expected_invoiced_bills,
    ):
        ois = new_organization_invoicing_setting_invalid_cadence
        roses = [
            ReimbursementOrganizationSettingsFactory.create(
                organization_id=ois.organization_id,
                direct_payment_enabled=direct_payment_enabled,
            )
            for direct_payment_enabled in ros_direct_payment_enabled_flags
        ]
        if previous_invoices:
            for ros in roses:
                new_direct_payment_invoice_for_ros(ros, T_MINUS_35, T_MINUS_20)

        billing_service = BillingService()
        ros_bills_map = defaultdict(set)

        for i, inp in enumerate(inputs):
            ros_id = roses[inp[2]].id
            bill = bill_factories.BillFactory(
                status=inp[0],
                payor_type=PayorType.EMPLOYER,
                payor_id=ros_id,
                created_at=inp[1],
            )
            billing_service.bill_repo.create(instance=bill)
            if i in expected_invoiced_bills:
                ros_bills_map[ros_id].add(bill.uuid)

        client = DirectPaymentInvoicingClient()
        res = client.create_invoices_and_allocate(
            organization_id=ois.organization_id,
            created_by_process=Process.INVOICE_GENERATOR,
            created_by_user_id=None,
        )

        expected_enabled_count = sum(ros_direct_payment_enabled_flags)
        assert (
            len(res) == expected_enabled_count
        ), f"Expected {expected_enabled_count} results, got {len(res)}"

        for inv_id, allocs in res.items():
            if allocs:
                assert len({alloc.direct_payment_invoice_id for alloc in allocs}) == 1
                assert allocs[0].direct_payment_invoice_id == inv_id

                res_bills = {str(alloc.bill_uuid) for alloc in allocs}
                invoice = client._invoicing_service.get_invoice(invoice_id=inv_id)
                assert (
                    res_bills
                    == ros_bills_map[invoice.reimbursement_organization_settings_id]
                )

                assert invoice.report_generated_at is None
                assert invoice.report_generated_json is None

    @pytest.mark.parametrize(
        argnames="ros_direct_payment_enabled_flags, inputs, previous_invoices, expected_invoiced_bills",
        argvalues=[
            (
                [True, True],
                [
                    (BillStatus.NEW, T_MINUS_35, 0),
                    (BillStatus.FAILED, T_MINUS_35, 0),
                    (BillStatus.PAID, T_MINUS_35, 1),
                    (BillStatus.NEW, T_MINUS_35, 1),
                    (BillStatus.NEW, T_PLUS_1, 0),
                    (BillStatus.NEW, T_MINUS_35, 1),
                ],
                False,
                {0, 3, 5},
            ),
            (
                [True, True, False],
                [
                    (BillStatus.NEW, T_MINUS_15, 0),
                    (BillStatus.NEW, T_MINUS_35, 1),
                    (BillStatus.NEW, T_MINUS_35, 1),
                ],
                False,
                {0, 1, 2},
            ),
            (
                [True],
                [
                    (BillStatus.NEW, T_MINUS_35, 0),
                    (BillStatus.PAID, T_MINUS_35, 0),
                    (BillStatus.FAILED, T_MINUS_35, 0),
                    (BillStatus.NEW, T_PLUS_1, 0),
                    (BillStatus.NEW, T_MINUS_35, 0),
                ],
                False,
                {0, 4},
            ),
            (
                [True, False],
                [
                    (BillStatus.PAID, T_MINUS_35, 0),
                    (BillStatus.FAILED, T_MINUS_35, 0),
                    (BillStatus.NEW, T_PLUS_1, 0),
                ],
                False,
                set(),
            ),
            (
                [True, False],
                [
                    (BillStatus.NEW, T_MINUS_35, 0),
                    (BillStatus.FAILED, T_MINUS_35, 0),
                    (BillStatus.PAID, T_MINUS_35, 1),
                    (BillStatus.NEW, T_MINUS_35, 1),
                    (BillStatus.NEW, T_PLUS_1, 0),
                    (BillStatus.NEW, T_MINUS_35, 1),
                ],
                True,
                set(),
            ),
            (
                [True, True, False],
                [
                    (BillStatus.NEW, T_MINUS_15, 0),
                    (BillStatus.FAILED, T_MINUS_35, 0),
                    (BillStatus.PAID, T_MINUS_35, 1),
                    (BillStatus.NEW, T_MINUS_35, 1),
                    (BillStatus.NEW, T_PLUS_1, 0),
                    (BillStatus.NEW, T_MINUS_35, 1),
                ],
                True,
                {0},
            ),
        ],
        ids=[
            "two ROS, both dp enabled - some eligible bills - mixed statuses and dates",
            "three ROS, two dp enabled - all bills eligible",
            "one ROS, dp enabled - some eligible bills - mixed statuses and date",
            "two ROS, one enabled, no eligible bills",
            "two ROS, one enabled, all bills in previous invoice",
            "Three ROS, two enabled, some bills in previous invoice",
        ],
    )
    def test_create_invoices_and_allocate_bill_processing_fails(
        self,
        new_organization_invoicing_settings_fixed_buffer,
        new_direct_payment_invoice_for_ros,
        ros_direct_payment_enabled_flags,
        inputs,
        previous_invoices,
        expected_invoiced_bills,
    ):
        ois = new_organization_invoicing_settings_fixed_buffer
        roses = [
            ReimbursementOrganizationSettingsFactory.create(
                organization_id=ois.organization_id,
                direct_payment_enabled=direct_payment_enabled,
            )
            for direct_payment_enabled in ros_direct_payment_enabled_flags
        ]
        if previous_invoices:
            for ros in roses:
                new_direct_payment_invoice_for_ros(ros, T_MINUS_35, T_MINUS_20)

        billing_service = BillingService()
        ros_bills_map = defaultdict(set)

        for i, inp in enumerate(inputs):
            ros_id = roses[inp[2]].id
            bill = bill_factories.BillFactory(
                status=inp[0],
                payor_type=PayorType.EMPLOYER,
                payor_id=ros_id,
                created_at=inp[1],
            )
            billing_service.bill_repo.create(instance=bill)
            if i in expected_invoiced_bills:
                ros_bills_map[ros_id].add(bill.uuid)

        client = DirectPaymentInvoicingClient()

        with patch(
            "direct_payment.invoicing.direct_payment_invoicing_client.DirectPaymentInvoicingClient._create_and_stamp_report_on_invoice"
        ) as mock_generate_report:
            mock_generate_report.side_effect = Exception()

            res = client.create_invoices_and_allocate(
                organization_id=ois.organization_id,
                created_by_process=Process.INVOICE_GENERATOR,
                created_by_user_id=None,
            )

            expected_enabled_count = sum(ros_direct_payment_enabled_flags)
            assert (
                len(res) == expected_enabled_count
            ), f"Expected {expected_enabled_count} results, got {len(res)}"

            for inv_id, allocs in res.items():
                if allocs:
                    assert (
                        len({alloc.direct_payment_invoice_id for alloc in allocs}) == 1
                    )
                    assert allocs[0].direct_payment_invoice_id == inv_id

                    res_bills = {str(alloc.bill_uuid) for alloc in allocs}
                    invoice = client._invoicing_service.get_invoice(invoice_id=inv_id)
                    assert (
                        res_bills
                        == ros_bills_map[invoice.reimbursement_organization_settings_id]
                    )

                    assert invoice.report_generated_at is None
                    assert invoice.report_generated_json is None


class TestCreateInvoiceAndAllocate:
    @pytest.mark.parametrize(
        argnames="ros_direct_payment_enabled_flags, inputs, previous_invoices, expected_invoiced_bills",
        argvalues=[
            (
                [True, True],
                [
                    (BillStatus.NEW, T_MINUS_35, 0),
                    (BillStatus.FAILED, T_MINUS_35, 0),
                    (BillStatus.PAID, T_MINUS_35, 1),
                    (BillStatus.NEW, T_MINUS_35, 1),
                    (BillStatus.NEW, T_PLUS_1, 0),
                    (BillStatus.NEW, T_MINUS_35, 1),
                ],
                False,
                {0, 3, 5},
            ),
            (
                [True, True, False],
                [
                    (BillStatus.NEW, T_MINUS_15, 0),
                    (BillStatus.NEW, T_MINUS_35, 1),
                    (BillStatus.NEW, T_MINUS_35, 1),
                ],
                False,
                {0, 1, 2},
            ),
            (
                [True],
                [
                    (BillStatus.NEW, T_MINUS_35, 0),
                    (BillStatus.PAID, T_MINUS_35, 0),
                    (BillStatus.FAILED, T_MINUS_35, 0),
                    (BillStatus.NEW, T_PLUS_1, 0),
                    (BillStatus.NEW, T_MINUS_35, 0),
                ],
                False,
                {0, 4},
            ),
            (
                [True, False],
                [
                    (BillStatus.PAID, T_MINUS_35, 0),
                    (BillStatus.FAILED, T_MINUS_35, 0),
                    (BillStatus.NEW, T_PLUS_1, 0),
                ],
                False,
                set(),
            ),
            (
                [True, False],
                [
                    (BillStatus.NEW, T_MINUS_35, 0),
                    (BillStatus.FAILED, T_MINUS_35, 0),
                    (BillStatus.PAID, T_MINUS_35, 1),
                    (BillStatus.NEW, T_MINUS_35, 1),
                    (BillStatus.NEW, T_PLUS_1, 0),
                    (BillStatus.NEW, T_MINUS_35, 1),
                ],
                True,
                set(),
            ),
            (
                [True, True, False],
                [
                    (BillStatus.NEW, T_MINUS_15, 0),
                    (BillStatus.FAILED, T_MINUS_35, 0),
                    (BillStatus.PAID, T_MINUS_35, 1),
                    (BillStatus.NEW, T_MINUS_35, 1),
                    (BillStatus.NEW, T_PLUS_1, 0),
                    (BillStatus.NEW, T_MINUS_35, 1),
                ],
                True,
                {0},
            ),
        ],
        ids=[
            "two ROS, both dp enabled - some eligible bills - mixed statuses and dates",
            "three ROS, two dp enabled - all bills eligible",
            "one ROS, dp enabled - some eligible bills - mixed statuses and date",
            "two ROS, one enabled, no eligible bills",
            "two ROS, one enabled, all bills in previous invoice",
            "Three ROS, two enabled, some bills in previous invoice",
        ],
    )
    def test_create_invoices_and_allocate(
        self,
        new_organization_invoicing_settings_fixed_buffer,
        new_direct_payment_invoice_for_ros,
        ros_direct_payment_enabled_flags,
        inputs,
        previous_invoices,
        expected_invoiced_bills,
    ):
        ois = new_organization_invoicing_settings_fixed_buffer
        roses = [
            ReimbursementOrganizationSettingsFactory.create(
                organization_id=ois.organization_id,
                direct_payment_enabled=direct_payment_enabled,
            )
            for direct_payment_enabled in ros_direct_payment_enabled_flags
        ]

        if previous_invoices:
            for ros in roses:
                new_direct_payment_invoice_for_ros(ros, T_MINUS_35, T_MINUS_20)

        billing_service = BillingService()
        ros_bills_map = defaultdict(set)

        client = DirectPaymentInvoicingClient()
        results = {}

        for i, inp in enumerate(inputs):
            ros_id = roses[inp[2]].id
            bill = bill_factories.BillFactory(
                status=inp[0],
                payor_type=PayorType.EMPLOYER,
                payor_id=ros_id,
                created_at=inp[1],
            )
            billing_service.bill_repo.create(instance=bill)
            if i in expected_invoiced_bills:
                ros_bills_map[ros_id].add(bill.uuid)

        for ros in roses:
            results = results | client.create_invoice_and_allocate(
                ros_id=ros.id,
                created_by_process=Process.INVOICE_GENERATOR,
                created_by_user_id=123,
            )

        expected_enabled_count = sum(ros_direct_payment_enabled_flags)

        assert (
            len(results) == expected_enabled_count
        ), f"Expected {expected_enabled_count} results, got {len(results)}"

        report_field_names_bill_report = [field.name for field in fields(BillingReport)]
        report_field_names_bill_information = [
            field.name for field in fields(BillInformation)
        ]

        for inv_id, allocs in results.items():
            if allocs:
                assert len({alloc.direct_payment_invoice_id for alloc in allocs}) == 1
                assert allocs[0].direct_payment_invoice_id == inv_id

                res_bills = {str(alloc.bill_uuid) for alloc in allocs}
                invoice = client._invoicing_service.get_invoice(invoice_id=inv_id)
                assert (
                    res_bills
                    == ros_bills_map[invoice.reimbursement_organization_settings_id]
                )

                assert invoice.report_generated_at is not None
                assert invoice.report_generated_json is not None

                for report_field_name in report_field_names_bill_report:
                    assert report_field_name in invoice.report_generated_json

                for report_field_name in report_field_names_bill_information:
                    assert report_field_name in invoice.report_generated_json

    def test_ros_id_not_exist(self):
        client = DirectPaymentInvoicingClient()
        results = {}

        for _ in range(4):
            ros_id = generate_random_string(
                10,
                include_lower_case_char=False,
                include_upper_case_char=False,
                include_digit=True,
            )
            results = results | client.create_invoice_and_allocate(
                ros_id=int(ros_id),
                created_by_process=Process.INVOICE_GENERATOR,
                created_by_user_id=123,
            )
        assert results == {}

    def test_no_org_invoicing_setting(self):
        roses = [
            ReimbursementOrganizationSettingsFactory.create(
                organization_id=12345, direct_payment_enabled=True
            )
            for _ in range(2)
        ]

        client = DirectPaymentInvoicingClient()
        results = {}

        for ros in roses:

            results = results | client.create_invoice_and_allocate(
                ros_id=ros.id,
                created_by_process=Process.INVOICE_GENERATOR,
                created_by_user_id=123,
            )
        assert results == {}

    @pytest.mark.parametrize(
        argnames="ros_direct_payment_enabled_flags, inputs, previous_invoices, expected_invoiced_bills",
        argvalues=[
            (
                [True, True],
                [
                    (BillStatus.NEW, T_MINUS_35, 0),
                    (BillStatus.FAILED, T_MINUS_35, 0),
                    (BillStatus.PAID, T_MINUS_35, 1),
                    (BillStatus.NEW, T_MINUS_35, 1),
                    (BillStatus.NEW, T_PLUS_1, 0),
                    (BillStatus.NEW, T_MINUS_35, 1),
                ],
                False,
                {0, 3, 5},
            ),
            (
                [True, True, False],
                [
                    (BillStatus.NEW, T_MINUS_15, 0),
                    (BillStatus.NEW, T_MINUS_35, 1),
                    (BillStatus.NEW, T_MINUS_35, 1),
                ],
                False,
                {0, 1, 2},
            ),
            (
                [True],
                [
                    (BillStatus.NEW, T_MINUS_35, 0),
                    (BillStatus.PAID, T_MINUS_35, 0),
                    (BillStatus.FAILED, T_MINUS_35, 0),
                    (BillStatus.NEW, T_PLUS_1, 0),
                    (BillStatus.NEW, T_MINUS_35, 0),
                ],
                False,
                {0, 4},
            ),
            (
                [True, False],
                [
                    (BillStatus.PAID, T_MINUS_35, 0),
                    (BillStatus.FAILED, T_MINUS_35, 0),
                    (BillStatus.NEW, T_PLUS_1, 0),
                ],
                False,
                set(),
            ),
            (
                [True, False],
                [
                    (BillStatus.NEW, T_MINUS_35, 0),
                    (BillStatus.FAILED, T_MINUS_35, 0),
                    (BillStatus.PAID, T_MINUS_35, 1),
                    (BillStatus.NEW, T_MINUS_35, 1),
                    (BillStatus.NEW, T_PLUS_1, 0),
                    (BillStatus.NEW, T_MINUS_35, 1),
                ],
                True,
                set(),
            ),
            (
                [True, True, False],
                [
                    (BillStatus.NEW, T_MINUS_15, 0),
                    (BillStatus.FAILED, T_MINUS_35, 0),
                    (BillStatus.PAID, T_MINUS_35, 1),
                    (BillStatus.NEW, T_MINUS_35, 1),
                    (BillStatus.NEW, T_PLUS_1, 0),
                    (BillStatus.NEW, T_MINUS_35, 1),
                ],
                True,
                {0},
            ),
        ],
        ids=[
            "two ROS, both dp enabled - some eligible bills - mixed statuses and dates",
            "three ROS, two dp enabled - all bills eligible",
            "one ROS, dp enabled - some eligible bills - mixed statuses and date",
            "two ROS, one enabled, no eligible bills",
            "two ROS, one enabled, all bills in previous invoice",
            "Three ROS, two enabled, some bills in previous invoice",
        ],
    )
    def test_invalid_report_cadence(
        self,
        new_organization_invoicing_setting_invalid_cadence,
        new_direct_payment_invoice_for_ros,
        ros_direct_payment_enabled_flags,
        inputs,
        previous_invoices,
        expected_invoiced_bills,
    ):
        ois = new_organization_invoicing_setting_invalid_cadence
        roses = [
            ReimbursementOrganizationSettingsFactory.create(
                organization_id=ois.organization_id,
                direct_payment_enabled=direct_payment_enabled,
            )
            for direct_payment_enabled in ros_direct_payment_enabled_flags
        ]
        if previous_invoices:
            for ros in roses:
                new_direct_payment_invoice_for_ros(ros, T_MINUS_35, T_MINUS_20)

        billing_service = BillingService()
        ros_bills_map = defaultdict(set)

        for i, inp in enumerate(inputs):
            ros_id = roses[inp[2]].id
            bill = bill_factories.BillFactory(
                status=inp[0],
                payor_type=PayorType.EMPLOYER,
                payor_id=ros_id,
                created_at=inp[1],
            )
            billing_service.bill_repo.create(instance=bill)
            if i in expected_invoiced_bills:
                ros_bills_map[ros_id].add(bill.uuid)

        client = DirectPaymentInvoicingClient()
        results = {}

        for ros in roses:
            results = results | client.create_invoice_and_allocate(
                ros_id=ros.id,
                created_by_process=Process.INVOICE_GENERATOR,
                created_by_user_id=123,
            )

        expected_enabled_count = sum(ros_direct_payment_enabled_flags)
        assert (
            len(results) == expected_enabled_count
        ), f"Expected {expected_enabled_count} results, got {len(results)}"

        for inv_id, allocs in results.items():
            if allocs:
                assert len({alloc.direct_payment_invoice_id for alloc in allocs}) == 1
                assert allocs[0].direct_payment_invoice_id == inv_id

                res_bills = {str(alloc.bill_uuid) for alloc in allocs}
                invoice = client._invoicing_service.get_invoice(invoice_id=inv_id)
                assert (
                    res_bills
                    == ros_bills_map[invoice.reimbursement_organization_settings_id]
                )

                assert invoice.report_generated_at is None
                assert invoice.report_generated_json is None

    @pytest.mark.parametrize(
        argnames="ros_direct_payment_enabled_flags, inputs, previous_invoices, expected_invoiced_bills",
        argvalues=[
            (
                [True, True],
                [
                    (BillStatus.NEW, T_MINUS_35, 0),
                    (BillStatus.FAILED, T_MINUS_35, 0),
                    (BillStatus.PAID, T_MINUS_35, 1),
                    (BillStatus.NEW, T_MINUS_35, 1),
                    (BillStatus.NEW, T_PLUS_1, 0),
                    (BillStatus.NEW, T_MINUS_35, 1),
                ],
                False,
                {0, 3, 5},
            ),
            (
                [True, True, False],
                [
                    (BillStatus.NEW, T_MINUS_15, 0),
                    (BillStatus.NEW, T_MINUS_35, 1),
                    (BillStatus.NEW, T_MINUS_35, 1),
                ],
                False,
                {0, 1, 2},
            ),
            (
                [True],
                [
                    (BillStatus.NEW, T_MINUS_35, 0),
                    (BillStatus.PAID, T_MINUS_35, 0),
                    (BillStatus.FAILED, T_MINUS_35, 0),
                    (BillStatus.NEW, T_PLUS_1, 0),
                    (BillStatus.NEW, T_MINUS_35, 0),
                ],
                False,
                {0, 4},
            ),
            (
                [True, False],
                [
                    (BillStatus.PAID, T_MINUS_35, 0),
                    (BillStatus.FAILED, T_MINUS_35, 0),
                    (BillStatus.NEW, T_PLUS_1, 0),
                ],
                False,
                set(),
            ),
            (
                [True, False],
                [
                    (BillStatus.NEW, T_MINUS_35, 0),
                    (BillStatus.FAILED, T_MINUS_35, 0),
                    (BillStatus.PAID, T_MINUS_35, 1),
                    (BillStatus.NEW, T_MINUS_35, 1),
                    (BillStatus.NEW, T_PLUS_1, 0),
                    (BillStatus.NEW, T_MINUS_35, 1),
                ],
                True,
                set(),
            ),
            (
                [True, True, False],
                [
                    (BillStatus.NEW, T_MINUS_15, 0),
                    (BillStatus.FAILED, T_MINUS_35, 0),
                    (BillStatus.PAID, T_MINUS_35, 1),
                    (BillStatus.NEW, T_MINUS_35, 1),
                    (BillStatus.NEW, T_PLUS_1, 0),
                    (BillStatus.NEW, T_MINUS_35, 1),
                ],
                True,
                {0},
            ),
        ],
        ids=[
            "two ROS, both dp enabled - some eligible bills - mixed statuses and dates",
            "three ROS, two dp enabled - all bills eligible",
            "one ROS, dp enabled - some eligible bills - mixed statuses and date",
            "two ROS, one enabled, no eligible bills",
            "two ROS, one enabled, all bills in previous invoice",
            "Three ROS, two enabled, some bills in previous invoice",
        ],
    )
    def test_create_invoices_and_allocate_bill_processing_fails(
        self,
        new_organization_invoicing_settings_fixed_buffer,
        new_direct_payment_invoice_for_ros,
        ros_direct_payment_enabled_flags,
        inputs,
        previous_invoices,
        expected_invoiced_bills,
    ):
        ois = new_organization_invoicing_settings_fixed_buffer
        roses = [
            ReimbursementOrganizationSettingsFactory.create(
                organization_id=ois.organization_id,
                direct_payment_enabled=direct_payment_enabled,
            )
            for direct_payment_enabled in ros_direct_payment_enabled_flags
        ]
        if previous_invoices:
            for ros in roses:
                new_direct_payment_invoice_for_ros(ros, T_MINUS_35, T_MINUS_20)

        billing_service = BillingService()
        ros_bills_map = defaultdict(set)

        for i, inp in enumerate(inputs):
            ros_id = roses[inp[2]].id
            bill = bill_factories.BillFactory(
                status=inp[0],
                payor_type=PayorType.EMPLOYER,
                payor_id=ros_id,
                created_at=inp[1],
            )
            billing_service.bill_repo.create(instance=bill)
            if i in expected_invoiced_bills:
                ros_bills_map[ros_id].add(bill.uuid)

        client = DirectPaymentInvoicingClient()

        with patch(
            "direct_payment.invoicing.direct_payment_invoicing_client.DirectPaymentInvoicingClient._create_and_stamp_report_on_invoice"
        ) as mock_generate_report:
            mock_generate_report.side_effect = Exception()

            results = {}

            for ros in roses:
                results = results | client.create_invoice_and_allocate(
                    ros_id=ros.id,
                    created_by_process=Process.INVOICE_GENERATOR,
                    created_by_user_id=123,
                )

            expected_enabled_count = sum(ros_direct_payment_enabled_flags)
            assert (
                len(results) == expected_enabled_count
            ), f"Expected {expected_enabled_count} results, got {len(results)}"

            for inv_id, allocs in results.items():
                if allocs:
                    assert (
                        len({alloc.direct_payment_invoice_id for alloc in allocs}) == 1
                    )
                    assert allocs[0].direct_payment_invoice_id == inv_id

                    res_bills = {str(alloc.bill_uuid) for alloc in allocs}
                    invoice = client._invoicing_service.get_invoice(invoice_id=inv_id)
                    assert (
                        res_bills
                        == ros_bills_map[invoice.reimbursement_organization_settings_id]
                    )

                    assert invoice.report_generated_at is None
                    assert invoice.report_generated_json is None
