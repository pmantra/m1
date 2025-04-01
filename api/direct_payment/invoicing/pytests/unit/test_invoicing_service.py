import json
import uuid
from datetime import datetime, timedelta, timezone

import pytest
import pytz

from direct_payment.invoicing.direct_payment_invoicing_client import CustomJSONEncoder
from direct_payment.invoicing.invoicing_service import DirectPaymentInvoicingService
from direct_payment.invoicing.models import (
    BillingReport,
    DirectPaymentInvoice,
    OrganizationInvoicingSettings,
    Process,
)
from direct_payment.invoicing.pytests import factories
from direct_payment.invoicing.pytests.factories import DirectPaymentInvoiceFactory
from models.enterprise import Organization
from pytests.factories import OrganizationFactory, ResourceFactory
from storage import connection
from wallet.models.reimbursement_organization_settings import (
    ReimbursementOrganizationSettings,
)
from wallet.pytests.factories import ReimbursementOrganizationSettingsFactory

T = datetime.now(timezone.utc)
T_MINUS_15 = T - timedelta(days=15)
T_MINUS_20 = T - timedelta(days=15)
T_MINUS_35 = T - timedelta(days=35)
T_PLUS_1 = T + timedelta(days=1)


def _compare_organization_invoice_settings(
    one: OrganizationInvoicingSettings, two: OrganizationInvoicingSettings
):
    assert one.organization_id == two.organization_id
    assert one.created_by_user_id == two.created_by_user_id
    assert one.updated_by_user_id == two.updated_by_user_id
    assert one.bill_cutoff_at_buffer_days == two.bill_cutoff_at_buffer_days
    assert one.bill_processing_delay_days == two.bill_processing_delay_days
    assert one.invoice_cadence == two.invoice_cadence
    assert one.uuid == two.uuid


class TestDirectPaymentInvoicingService:
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

        dpis = DirectPaymentInvoicingService(session=connection.db.session)
        dpis.delete_invoice(invoice_id=new_direct_payment_invoice.id)

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

    def test_invoice_setting_crud_create(self):
        org_one = OrganizationFactory.create()
        org_two = OrganizationFactory.create()
        dpis = DirectPaymentInvoicingService(session=connection.db.session)

        organization_invoicing_setting_one: OrganizationInvoicingSettings = (
            OrganizationInvoicingSettings(
                uuid=uuid.uuid4(),
                organization_id=org_one.id,
                created_by_user_id=123,
                updated_by_user_id=123,
                invoicing_active_at=datetime.utcnow(),
                invoice_cadence="* * * * *",
                bill_processing_delay_days=10,
                bill_cutoff_at_buffer_days=5,
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow(),
            )
        )

        organization_invoicing_setting_two: OrganizationInvoicingSettings = (
            OrganizationInvoicingSettings(
                uuid=uuid.uuid4(),
                organization_id=org_two.id,
                created_by_user_id=234,
                updated_by_user_id=234,
                invoicing_active_at=datetime.utcnow(),
                invoice_cadence="* * * * *",
                bill_processing_delay_days=10,
                bill_cutoff_at_buffer_days=5,
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow(),
            )
        )

        assert 1 == dpis.create_invoice_setting(
            organization_invoicing_setting=organization_invoicing_setting_one,
            return_created_instance=False,
        )
        assert 1 == dpis.create_invoice_setting(
            organization_invoicing_setting=organization_invoicing_setting_two,
            return_created_instance=False,
        )

        get_invoice_setting_result_one = dpis.get_invoice_setting_by_organization_id(
            organization_id=organization_invoicing_setting_one.organization_id
        )
        _compare_organization_invoice_settings(
            get_invoice_setting_result_one, organization_invoicing_setting_one
        )

        get_invoice_setting_result_two = dpis.get_invoice_setting_by_uuid(
            uuid=organization_invoicing_setting_two.uuid
        )
        _compare_organization_invoice_settings(
            get_invoice_setting_result_two, organization_invoicing_setting_two
        )

    def test_invoice_setting_crud_create_valid(self):
        org = OrganizationFactory.create()
        dpis = DirectPaymentInvoicingService(session=connection.db.session)

        organization_invoicing_setting: OrganizationInvoicingSettings = (
            OrganizationInvoicingSettings(
                uuid=uuid.uuid4(),
                organization_id=org.id,
                created_by_user_id=123,
                updated_by_user_id=123,
                invoicing_active_at=datetime.utcnow(),
                invoice_cadence="lol",
                bill_processing_delay_days=10,
                bill_cutoff_at_buffer_days=5,
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow(),
            )
        )

        with pytest.raises(Exception) as excinfo:
            dpis.create_invoice_setting(
                organization_invoicing_setting=organization_invoicing_setting,
                return_created_instance=False,
            )
        assert (
            str(excinfo.value)
            == "The cron expression of the invoice cadence is invalid"
        )

        ois = dpis.get_invoice_setting_by_organization_id(
            organization_id=organization_invoicing_setting.organization_id
        )
        assert ois is None

    def test_invoice_setting_crud_update(self, new_organization_invoicing_settings):
        dpis = DirectPaymentInvoicingService(session=connection.db.session)

        new_invoice_cadence = "* * * * *"
        old_invoice_cadence = new_organization_invoicing_settings.invoice_cadence
        assert old_invoice_cadence != new_invoice_cadence
        new_organization_invoicing_settings.invoice_cadence = new_invoice_cadence

        assert 1 == dpis.update_invoice_setting(
            updated_organization_invoicing_setting=new_organization_invoicing_settings,
            return_updated_instance=False,
        )

        get_updated_invoice_setting_result = dpis.get_invoice_setting_by_uuid(
            uuid=new_organization_invoicing_settings.uuid
        )
        assert get_updated_invoice_setting_result.invoice_cadence == new_invoice_cadence
        _compare_organization_invoice_settings(
            get_updated_invoice_setting_result, new_organization_invoicing_settings
        )

    def test_invoice_setting_crud_update_invalid(
        self, new_organization_invoicing_settings
    ):
        dpis = DirectPaymentInvoicingService(session=connection.db.session)

        new_invoice_cadence = "lol"
        old_invoice_cadence = new_organization_invoicing_settings.invoice_cadence
        assert old_invoice_cadence != new_invoice_cadence
        new_organization_invoicing_settings.invoice_cadence = new_invoice_cadence

        with pytest.raises(Exception) as excinfo:
            dpis.update_invoice_setting(
                updated_organization_invoicing_setting=new_organization_invoicing_settings,
                return_updated_instance=False,
            )
        assert (
            str(excinfo.value)
            == "The cron expression of the invoice cadence is invalid"
        )

        get_updated_invoice_setting_result = dpis.get_invoice_setting_by_uuid(
            uuid=new_organization_invoicing_settings.uuid
        )
        assert get_updated_invoice_setting_result.invoice_cadence == old_invoice_cadence

    def test_invoice_setting_crud_get(self, new_organization_invoicing_settings):
        dpis = DirectPaymentInvoicingService(session=connection.db.session)

        get_invoice_setting_result_one = dpis.get_invoice_setting_by_organization_id(
            organization_id=new_organization_invoicing_settings.organization_id
        )
        _compare_organization_invoice_settings(
            get_invoice_setting_result_one, new_organization_invoicing_settings
        )

        get_invoice_setting_result_two = dpis.get_invoice_setting_by_uuid(
            uuid=get_invoice_setting_result_one.uuid
        )
        _compare_organization_invoice_settings(
            get_invoice_setting_result_two, new_organization_invoicing_settings
        )

        get_invoice_setting_result_three = dpis.get_invoice_setting_by_organization_id(
            organization_id=new_organization_invoicing_settings.organization_id + 1
        )
        assert get_invoice_setting_result_three is None

        get_invoice_setting_result_four = dpis.get_invoice_setting_by_uuid(
            uuid=uuid.uuid4()
        )
        assert get_invoice_setting_result_four is None

    def test_invoice_setting_crud_delete_by_org_id(
        self, new_organization_invoicing_settings
    ):
        dpis = DirectPaymentInvoicingService(session=connection.db.session)

        assert 0 == dpis.delete_invoice_setting_by_organization_id(
            organization_id=new_organization_invoicing_settings.organization_id + 1
        )
        assert 0 == dpis.delete_invoice_setting_by_uuid(uuid=uuid.uuid4())

        assert (
            dpis.get_invoice_setting_by_uuid(
                uuid=new_organization_invoicing_settings.uuid
            )
            is not None
        )

        assert 1 == dpis.delete_invoice_setting_by_organization_id(
            organization_id=new_organization_invoicing_settings.organization_id
        )
        assert (
            dpis.get_invoice_setting_by_organization_id(
                organization_id=new_organization_invoicing_settings.organization_id
            )
            is None
        )

    def test_invoice_setting_crud_delete_by_uuid(
        self, new_organization_invoicing_settings
    ):
        dpis = DirectPaymentInvoicingService(session=connection.db.session)

        assert 0 == dpis.delete_invoice_setting_by_organization_id(
            organization_id=new_organization_invoicing_settings.organization_id + 1
        )
        assert 0 == dpis.delete_invoice_setting_by_uuid(uuid=uuid.uuid4())

        assert (
            dpis.get_invoice_setting_by_uuid(
                uuid=new_organization_invoicing_settings.uuid
            )
            is not None
        )

        assert 1 == dpis.delete_invoice_setting_by_uuid(
            uuid=new_organization_invoicing_settings.uuid
        )
        assert (
            dpis.get_invoice_setting_by_uuid(
                uuid=new_organization_invoicing_settings.uuid
            )
            is None
        )

    def test_invoice_setting_crud_duplicate_insert(self):
        org = OrganizationFactory.create()
        dpis = DirectPaymentInvoicingService(session=connection.db.session)

        organization_invoicing_setting: OrganizationInvoicingSettings = (
            OrganizationInvoicingSettings(
                uuid=uuid.uuid4(),
                organization_id=org.id,
                created_by_user_id=123,
                updated_by_user_id=123,
                invoicing_active_at=datetime.utcnow(),
                invoice_cadence="* * * * *",
                bill_processing_delay_days=10,
                bill_cutoff_at_buffer_days=5,
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow(),
            )
        )

        dpis.create_invoice_setting(
            organization_invoicing_setting=organization_invoicing_setting
        )

        with pytest.raises(Exception) as exc_info:
            dpis.create_invoice_setting(
                organization_invoicing_setting=organization_invoicing_setting
            )
        assert "IntegrityError" in str(exc_info.value)
        assert "Duplicate entry" in str(exc_info.value)

    def test_invoice_setting_crud_duplicate_update(self):
        org_one = OrganizationFactory.create()
        org_two = OrganizationFactory.create()
        dpis = DirectPaymentInvoicingService(session=connection.db.session)

        organization_invoicing_setting_one: OrganizationInvoicingSettings = (
            OrganizationInvoicingSettings(
                uuid=uuid.uuid4(),
                organization_id=org_one.id,
                created_by_user_id=123,
                updated_by_user_id=123,
                invoicing_active_at=datetime.utcnow(),
                invoice_cadence="* * * * *",
                bill_processing_delay_days=10,
                bill_cutoff_at_buffer_days=5,
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow(),
            )
        )

        organization_invoicing_setting_two: OrganizationInvoicingSettings = (
            OrganizationInvoicingSettings(
                uuid=uuid.uuid4(),
                organization_id=org_two.id,
                created_by_user_id=234,
                updated_by_user_id=234,
                invoicing_active_at=datetime.utcnow(),
                invoice_cadence="* * * * *",
                bill_processing_delay_days=10,
                bill_cutoff_at_buffer_days=5,
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow(),
            )
        )

        dpis.create_invoice_setting(
            organization_invoicing_setting=organization_invoicing_setting_one,
            return_created_instance=False,
        )
        dpis.create_invoice_setting(
            organization_invoicing_setting=organization_invoicing_setting_two,
            return_created_instance=False,
        )

        get_invoice_setting_result = dpis.get_invoice_setting_by_uuid(
            uuid=organization_invoicing_setting_two.uuid
        )
        assert get_invoice_setting_result is not None

        get_invoice_setting_result.uuid = organization_invoicing_setting_one.uuid
        get_invoice_setting_result.invoice_cadence = "* * * * 3"
        with pytest.raises(Exception) as exc_info:
            dpis.update_invoice_setting(
                updated_organization_invoicing_setting=get_invoice_setting_result
            )

        assert "IntegrityError" in str(exc_info.value)
        assert "Duplicate entry" in str(exc_info.value)

    def test_create_new_invoice_no_previous_invoices(
        self, new_organization_invoicing_settings
    ):
        ros = ReimbursementOrganizationSettingsFactory.create(
            organization_id=new_organization_invoicing_settings.organization_id,
            benefit_faq_resource_id=ResourceFactory().id,
            survey_url="fake_url",
        )
        dpis = DirectPaymentInvoicingService(session=connection.db.session)
        res = dpis.create_new_invoice(
            created_by_process=Process.INVOICE_GENERATOR,
            created_by_user_id=None,
            reimbursement_organization_settings_id=ros.id,
            current_time=datetime.now(timezone.utc),
        )
        assert res is not None
        assert pytz.utc.localize(
            res.bill_creation_cutoff_start_at
        ) == datetime.fromtimestamp(0, tz=timezone.utc)
        assert res.bill_creation_cutoff_end_at > res.bill_creation_cutoff_start_at
        assert res.created_by_process == Process.INVOICE_GENERATOR
        assert res.reimbursement_organization_settings_id == ros.id

    @pytest.mark.parametrize(
        ids=[
            "1. No overlap with previous invoice - invoice generated from process",
            "2. No overlap with previous invoice - invoice generated from admin",
            "3. Overlap with previous invoice - no invoice generated from process",
            "4. Overlap with previous invoice - no invoice generated from admin",
        ],
        argnames="created_by_process, created_by_user_id, bill_cutoff_at_buffer_days, prev_inv_cutoff_start_at, "
        "prev_inv_cutoff_end_at, fake_now, exp_inv, exp_bill_cutoff_at_buffer_days",
        argvalues=(
            (
                Process.INVOICE_GENERATOR,
                None,
                2,
                datetime(2024, 3, 1, 0, 0, 0, tzinfo=timezone.utc),
                datetime(2024, 4, 1, 23, 59, 59, tzinfo=timezone.utc),
                datetime(2024, 5, 5, 10, 0, 0, tzinfo=timezone.utc),
                True,
                datetime(2024, 5, 2, 23, 59, 59, tzinfo=timezone.utc),
            ),
            (
                Process.ADMIN,
                100,
                3,
                datetime(2024, 3, 1, 0, 0, 0, tzinfo=timezone.utc),
                datetime(2024, 4, 1, 23, 59, 59, tzinfo=timezone.utc),
                datetime(2024, 5, 9, 10, 0, 0, tzinfo=timezone.utc),
                True,
                datetime(2024, 5, 5, 23, 59, 59, tzinfo=timezone.utc),
            ),
            (
                Process.INVOICE_GENERATOR,
                None,
                2,
                datetime(2024, 4, 1, 0, 0, 0, tzinfo=timezone.utc),
                datetime(2024, 4, 1, 23, 59, 59, tzinfo=timezone.utc),
                datetime(2024, 4, 2, 12, 0, 0, tzinfo=timezone.utc),
                False,
                None,
            ),
            (
                Process.ADMIN,
                200,
                3,
                datetime(2024, 4, 1, 0, 0, 0, tzinfo=timezone.utc),
                datetime(2024, 4, 1, 23, 59, 59, tzinfo=timezone.utc),
                datetime(2024, 4, 2, 12, 0, 0, tzinfo=timezone.utc),
                False,
                None,
            ),
        ),
    )
    def test_create_new_invoice_previous_invoice_exists(
        self,
        organization_invoicing_settings_repository,
        direct_payment_invoice_repository,
        created_by_process,
        created_by_user_id,
        bill_cutoff_at_buffer_days,
        prev_inv_cutoff_start_at,
        prev_inv_cutoff_end_at,
        fake_now,
        exp_inv,
        exp_bill_cutoff_at_buffer_days,
    ):
        org = OrganizationFactory.create()
        ois = factories.OrganizationInvoicingSettingsFactory.build(
            organization_id=org.id,
            bill_cutoff_at_buffer_days=bill_cutoff_at_buffer_days,
        )

        ois = organization_invoicing_settings_repository.create(instance=ois)
        ros = ReimbursementOrganizationSettingsFactory.create(
            organization_id=ois.organization_id,
            benefit_faq_resource_id=ResourceFactory().id,
            survey_url="fake_url",
        )
        dpi: DirectPaymentInvoice = factories.DirectPaymentInvoiceFactory.build(
            reimbursement_organization_settings_id=ros.id,
            bill_creation_cutoff_start_at=prev_inv_cutoff_start_at,
            bill_creation_cutoff_end_at=prev_inv_cutoff_end_at,
        )
        dpi = direct_payment_invoice_repository.create(instance=dpi)
        dpis = DirectPaymentInvoicingService(session=connection.db.session)
        res = dpis.create_new_invoice(
            created_by_process=created_by_process,
            created_by_user_id=created_by_user_id,
            reimbursement_organization_settings_id=ros.id,
            current_time=fake_now,
        )
        if exp_inv:
            assert res is not None
            assert (
                res.bill_creation_cutoff_start_at
                == dpi.bill_creation_cutoff_end_at + timedelta(seconds=1)
            )
            assert (
                pytz.utc.localize(res.bill_creation_cutoff_end_at)
                == exp_bill_cutoff_at_buffer_days
            )
            assert res.created_by_process == created_by_process
            assert res.reimbursement_organization_settings_id == ros.id
            assert res.created_by_user_id == created_by_user_id
        else:
            assert res is None

    def test_create_new_invoice_error(self, new_organization_invoicing_settings):
        ros = ReimbursementOrganizationSettingsFactory.create(
            organization_id=new_organization_invoicing_settings.organization_id,
            benefit_faq_resource_id=ResourceFactory().id,
            survey_url="fake_url",
        )
        dpis = DirectPaymentInvoicingService(session=connection.db.session)
        with pytest.raises(ValueError):
            _ = dpis.create_new_invoice(
                created_by_process=Process.ADMIN,
                created_by_user_id=None,
                reimbursement_organization_settings_id=ros.id,
                current_time=datetime(2024, 4, 2, 12, 0, 0, tzinfo=timezone.utc),
            )

    @pytest.mark.parametrize(argnames="bill_uuids_cnt", argvalues=(0, 5))
    def test_create_allocations(
        self, new_organization_invoicing_settings, bill_uuids_cnt
    ):
        ros = ReimbursementOrganizationSettingsFactory.create(
            organization_id=new_organization_invoicing_settings.organization_id,
            benefit_faq_resource_id=ResourceFactory().id,
            survey_url="fake_url",
        )
        dpis = DirectPaymentInvoicingService(session=connection.db.session)
        invoice = dpis.create_new_invoice(
            created_by_process=Process.INVOICE_GENERATOR,
            created_by_user_id=None,
            reimbursement_organization_settings_id=ros.id,
            current_time=datetime.now(timezone.utc),
        )

        bill_uuids = [uuid.uuid4() for _ in range(0, bill_uuids_cnt)]
        res = dpis.create_allocations(invoice=invoice, bill_uuids=bill_uuids)
        assert len(res) == len(bill_uuids)
        if bill_uuids:
            assert {a.bill_uuid for a in res} == set(bill_uuids)
            for a in res:
                assert a.created_by_process == invoice.created_by_process
                assert a.created_by_user_id == invoice.created_by_user_id
                assert a.direct_payment_invoice_id == invoice.id

    def test_get_org_level_invoice_report_data_query(
        self,
        direct_payment_invoice_repository,
    ):
        org_one: Organization = OrganizationFactory.create()
        org_two: Organization = OrganizationFactory.create()

        org_setting_one_in_org_one: ReimbursementOrganizationSettings = (
            ReimbursementOrganizationSettingsFactory.create(
                organization_id=org_one.id,
                direct_payment_enabled=True,
            )
        )

        invoice_report_org_setting_one_in_org_one = BillingReport(
            organisation_name=org_one.name,
            organisation_id=org_one.id,
            report_generated_at=datetime.utcnow(),
            report_cadence="* * * * *",
            start_date_time=T_MINUS_35,
            end_date_time=T_MINUS_20,
            total_bills=3,
            total_bill_amount="$300.00",
            clinic_bill_amount="$100.00",
            pharmacy_bill_amount="$200.00",
            bill_information=[],
        )

        org_setting_two_in_org_one: ReimbursementOrganizationSettings = (
            ReimbursementOrganizationSettingsFactory.create(
                organization_id=org_one.id,
                direct_payment_enabled=True,
            )
        )

        invoice_report_org_setting_two_in_org_one = BillingReport(
            organisation_name=org_one.name,
            organisation_id=org_one.id,
            report_generated_at=datetime.utcnow(),
            report_cadence="* * * * *",
            start_date_time=T_MINUS_35,
            end_date_time=T_MINUS_20,
            total_bills=3,
            total_bill_amount="$600.00",
            clinic_bill_amount="$300.00",
            pharmacy_bill_amount="$300.00",
            bill_information=[],
        )

        org_setting_one_in_org_two: ReimbursementOrganizationSettings = (
            ReimbursementOrganizationSettingsFactory.create(
                organization_id=org_two.id,
                direct_payment_enabled=True,
            )
        )

        invoice_report_org_setting_one_in_org_two = BillingReport(
            organisation_name=org_two.name,
            organisation_id=org_two.id,
            report_generated_at=datetime.utcnow(),
            report_cadence="* * * * *",
            start_date_time=T_MINUS_35,
            end_date_time=T_MINUS_20,
            total_bills=3,
            total_bill_amount="$1000.00",
            clinic_bill_amount="$700.00",
            pharmacy_bill_amount="$300.00",
            bill_information=[],
        )

        invoice_one = DirectPaymentInvoiceFactory.build(
            reimbursement_organization_settings_id=org_setting_one_in_org_one.id,
            bill_creation_cutoff_start_at=T_MINUS_35,
            bill_creation_cutoff_end_at=T_MINUS_20,
            report_generated_json=json.dumps(
                invoice_report_org_setting_one_in_org_one, cls=CustomJSONEncoder
            ),
        )
        direct_payment_invoice_repository.create(instance=invoice_one)

        invoice_two = DirectPaymentInvoiceFactory.build(
            reimbursement_organization_settings_id=org_setting_two_in_org_one.id,
            bill_creation_cutoff_start_at=T_MINUS_35,
            bill_creation_cutoff_end_at=T_MINUS_20,
            report_generated_json=json.dumps(
                invoice_report_org_setting_two_in_org_one, cls=CustomJSONEncoder
            ),
        )
        direct_payment_invoice_repository.create(instance=invoice_two)

        invoice_three = DirectPaymentInvoiceFactory.build(
            reimbursement_organization_settings_id=org_setting_one_in_org_two.id,
            bill_creation_cutoff_start_at=T_MINUS_35,
            bill_creation_cutoff_end_at=T_MINUS_20,
            report_generated_json=json.dumps(
                invoice_report_org_setting_one_in_org_two, cls=CustomJSONEncoder
            ),
        )
        direct_payment_invoice_repository.create(instance=invoice_three)

        dpis = DirectPaymentInvoicingService(session=connection.db.session)
        results = dpis.get_org_level_invoice_report_data_query().all()
        assert len(results) == 2
        for result in results:
            assert len(result) == 8
            if result[2] == org_one.id:
                assert result[1] == org_one.name
                assert result[4] == 400
                assert result[5] == 500
            elif result[2] == org_two.id:
                assert result[1] == org_two.name
                assert result[4] == 700
                assert result[5] == 300
            else:
                raise Exception(f"Unexpected org_id: {result[2]}")

        assert 2 == dpis.get_org_level_invoice_report_count_query().scalar()
