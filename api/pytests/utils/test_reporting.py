import datetime
from unittest.mock import patch

from models.verticals_and_specialties import (
    BIRTH_PLANNING_VERTICAL_NAME,
    CX_VERTICAL_NAME,
)
from payments.models.practitioner_contract import ContractType
from payments.pytests.factories import PractitionerContractFactory
from utils.reporting import invoices_by_date_csv


@patch("utils.reporting.invoices_csv")
def test_invoices_by_date_csv__invoices_in_range(mock_invoices_csv, factories):

    today = datetime.datetime.today()
    yesterday = datetime.datetime.today() - datetime.timedelta(days=1)
    tomorrow = datetime.datetime.today() + datetime.timedelta(days=1)

    # Given some invoices
    invoice1 = factories.InvoiceFactory()
    invoice1.created_at = today
    invoice2 = factories.InvoiceFactory()
    invoice2.created_at = today

    # When
    invoices_by_date_csv(yesterday, tomorrow)

    # Then invoices_csv is called with all invoices
    mock_invoices_csv.assert_called_once_with([invoice1, invoice2])


@patch("utils.reporting.invoices_csv")
def test_invoices_by_date_csv__no_invoices_in_range(mock_invoices_csv, factories):

    today = datetime.datetime.today()
    yesterday = datetime.datetime.today() - datetime.timedelta(days=1)
    tomorrow = datetime.datetime.today() + datetime.timedelta(days=1)

    # Given some invoices
    invoice1 = factories.InvoiceFactory()
    invoice1.created_at = yesterday
    invoice2 = factories.InvoiceFactory()
    invoice2.created_at = tomorrow

    # When
    invoices_by_date_csv(today, today)

    # Then invoices_csv is called with no invoices
    mock_invoices_csv.assert_called_once_with([])


@patch("utils.reporting.invoices_csv")
def test_invoices_by_date_csv__with_distributed_providers_only__prac_doesnt_emit_fees(
    mock_invoices_csv, factories
):

    today = datetime.datetime.today()
    yesterday = datetime.datetime.today() - datetime.timedelta(days=1)
    tomorrow = datetime.datetime.today() + datetime.timedelta(days=1)

    # Given a practitioner, and an invoice with entries
    cx_vertical = factories.VerticalFactory(name=CX_VERTICAL_NAME)
    prac = factories.PractitionerUserFactory(
        practitioner_profile__verticals=[cx_vertical]
    )
    PractitionerContractFactory.create(
        practitioner=prac.practitioner_profile,
        start_date=datetime.datetime.today(),
        contract_type=ContractType.W2,
    )

    invoice = factories.InvoiceFactory()
    invoice.created_at = today
    fee = factories.FeeAccountingEntryFactory()
    fee.invoice_id = invoice.id
    fee.practitioner_id = prac.id

    # When
    invoices_by_date_csv(yesterday, tomorrow, distributed_providers_only=True)

    # Then invoices_csv is called with no invoices
    mock_invoices_csv.assert_called_once_with([])


@patch("utils.reporting.invoices_csv")
def test_invoices_by_date_csv__with_distributed_providers_only__prac_emits_fees(
    mock_invoices_csv, factories
):

    today = datetime.datetime.today()
    yesterday = datetime.datetime.today() - datetime.timedelta(days=1)
    tomorrow = datetime.datetime.today() + datetime.timedelta(days=1)

    # Given a practitioner, and an invoice with entries
    bp_vertical = factories.VerticalFactory(name=BIRTH_PLANNING_VERTICAL_NAME)
    prac = factories.PractitionerUserFactory(
        practitioner_profile__verticals=[bp_vertical]
    )
    PractitionerContractFactory.create(
        practitioner=prac.practitioner_profile,
        start_date=datetime.datetime.today(),
        contract_type=ContractType.BY_APPOINTMENT,
    )

    invoice = factories.InvoiceFactory()
    invoice.created_at = today
    fee = factories.FeeAccountingEntryFactory()
    fee.invoice_id = invoice.id
    fee.practitioner_id = prac.id

    # When
    invoices_by_date_csv(yesterday, tomorrow, distributed_providers_only=True)

    # Then invoices_csv is called with the invoice
    mock_invoices_csv.assert_called_once_with([invoice])
