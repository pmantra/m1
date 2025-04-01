from datetime import timedelta
from uuid import uuid4

from factory import Factory, Faker, LazyAttribute

from direct_payment.invoicing import models
from direct_payment.invoicing.models import Process


class OrganizationInvoicingSettingsFactory(Factory):
    class Meta:
        model = models.OrganizationInvoicingSettings

    id = Faker("random_int", min=1)
    uuid = uuid4()
    created_at = Faker("date_time_this_year")
    updated_at = Faker("date_time_this_year")
    created_by_user_id = Faker("random_int", min=1)
    updated_by_user_id = Faker("random_int", min=1)
    invoicing_active_at = Faker("future_datetime")
    invoice_cadence = Faker("random_element", elements=["0 0 * * *", "0 0 1 * *"])
    bill_processing_delay_days = Faker("random_int", min=1, max=30)
    bill_cutoff_at_buffer_days = Faker("random_int", min=1, max=7)


class DirectPaymentInvoiceFactory(Factory):
    class Meta:
        model = models.DirectPaymentInvoice

    id = Faker("random_int", min=1)
    uuid = LazyAttribute(lambda o: uuid4())
    created_at = Faker("date_time_this_year")

    bill_creation_cutoff_start_at = LazyAttribute(
        lambda o: o.created_at + timedelta(days=1)
    )
    bill_creation_cutoff_end_at = LazyAttribute(
        lambda o: o.bill_creation_cutoff_start_at + timedelta(days=7)
    )
    created_by_process = Faker("random_element", elements=[p for p in Process])
    created_by_user_id = Faker("random_int", min=1)
    bills_allocated_at = LazyAttribute(
        lambda o: o.bill_creation_cutoff_end_at + timedelta(days=1)
    )
    bills_allocated_by_process = Faker("random_element", elements=[p for p in Process])
    voided_at = None
    voided_by_user_id = None
    report_generated_at = LazyAttribute(
        lambda o: o.bills_allocated_at + timedelta(days=2)
    )
    report_generated_json = Faker("json")
    bill_allocated_by_user_id = Faker("random_int", min=1)


class DirectPaymentInvoiceBillAllocationFactory(Factory):
    class Meta:
        model = models.DirectPaymentInvoiceBillAllocation

    id = Faker("random_int", min=1)
    uuid = Faker("uuid4")
    created_at = Faker("date_time_this_year")
    created_by_process = models.Process.ADMIN
    created_by_user_id = Faker("pyint")
    bill_uuid = uuid4()
