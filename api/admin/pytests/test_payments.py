import factory
import pytest

from admin.views.models.payments import (
    DistributedNetworkPractitionerFilter,
    InvoiceForDistributedPractitionersFilter,
    InvoicePractitionerIDEmptyFilter,
    InvoicePractitionerIDFilter,
)
from appointments.models.payments import (
    FeeAccountingEntry,
    FeeAccountingEntryTypes,
    Invoice,
)
from storage.connection import db


@pytest.fixture
def practitioner(factories):
    return factories.PractitionerUserFactory.create()


@pytest.fixture
def care_advocate(factories):
    ca_vertical = factories.VerticalFactory.create_cx_vertical()
    return factories.PractitionerUserFactory.create(
        practitioner_profile__verticals=[ca_vertical],
    )


@pytest.fixture
def invoices(factories, practitioner):
    entries = factories.FeeAccountingEntryFactory.create_batch(
        size=3,
        amount=10,
        practitioner=practitioner,
        type=factory.Iterator(
            [
                FeeAccountingEntryTypes.ONE_OFF,
                FeeAccountingEntryTypes.APPOINTMENT,
                FeeAccountingEntryTypes.UNKNOWN,
            ]
        ),
    )
    invoices = factories.InvoiceFactory.create_batch(
        size=3,
        entries=factory.Iterator(
            [
                [entries[0]],
                [entries[1]],
                [entries[2]],
            ]
        ),
    )
    return set(invoices)


@pytest.fixture
def distributed_invoices(factories, practitioner, care_advocate):
    # given the data to create invoices
    distributed_appointment = factories.AppointmentFactory.create_with_practitioner(
        practitioner=practitioner
    )
    channel = factories.ChannelFactory.create()
    factories.ChannelUsersFactory.create_batch(
        size=2,
        channel_id=channel.id,
        user_id=factory.Iterator(
            [distributed_appointment.member_schedule.user_id, care_advocate.id]
        ),
    )
    non_distributed_message = factories.MessageFactory.create(
        user_id=care_advocate.id, channel_id=channel.id
    )
    # and three types of invoices with different associations
    accounting_entry_appointment_practitioner = (
        factories.FeeAccountingEntryFactory.create(
            practitioner=practitioner, type=FeeAccountingEntryTypes.APPOINTMENT
        )
    )
    accounting_entry_appointment = factories.FeeAccountingEntryFactory.create(
        appointment_id=distributed_appointment.id,
        type=FeeAccountingEntryTypes.APPOINTMENT,
    )
    accounting_entry_message = factories.FeeAccountingEntryFactory.create(
        message_id=non_distributed_message.id, type=FeeAccountingEntryTypes.MESSAGE
    )
    return factories.InvoiceFactory.create_batch(
        size=3,
        entries=factory.Iterator(
            [
                [accounting_entry_appointment_practitioner],
                [accounting_entry_message],
                [accounting_entry_appointment],
            ]
        ),
    )


class TestAdminInvoicePractitionerFilter:
    def test_filter_invoices_by_practitioner(self, invoices, practitioner):
        result = (
            InvoicePractitionerIDFilter(None, None)
            .apply(db.session.query(Invoice), practitioner.id)
            .all()
        )
        assert len(result) == 3
        assert set(result) == invoices

    def test_filter_invoices_by_invalid_practitioner(self, invoices):
        result = (
            InvoicePractitionerIDFilter(None, None)
            .apply(db.session.query(Invoice), -1)
            .all()
        )
        assert result == []

    def test_filter_invoices_by_practitioner_none(self, invoices):
        result = (
            InvoicePractitionerIDEmptyFilter(None, None)
            .apply(db.session.query(Invoice), "1")
            .all()
        )
        assert result == []

    def test_filter_invoices_by_practitioner_any(self, invoices):
        result = (
            InvoicePractitionerIDEmptyFilter(None, None)
            .apply(db.session.query(Invoice), "0")
            .all()
        )
        assert len(result) == 3
        assert set(result) == invoices


class TestAdminDistributedPractitionerFilters:
    def test_invoice_distributed_practitioner(self, distributed_invoices):
        res_on = (
            InvoiceForDistributedPractitionersFilter(None, None)
            .apply(db.session.query(Invoice), "1")
            .all()
        )
        res_off = (
            InvoiceForDistributedPractitionersFilter(None, None)
            .apply(db.session.query(Invoice), "0")
            .all()
        )

        assert len(res_on) == 2
        assert len(res_off) == 1

    def test_distributed_practitioner(self, distributed_invoices):
        res_on = (
            DistributedNetworkPractitionerFilter(None, None)
            .apply(db.session.query(FeeAccountingEntry), "1")
            .all()
        )
        res_off = (
            DistributedNetworkPractitionerFilter(None, None)
            .apply(db.session.query(FeeAccountingEntry), "0")
            .all()
        )

        assert len(res_on) == 2
        assert len(res_off) == 1
