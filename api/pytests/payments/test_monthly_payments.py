from datetime import date, datetime
from decimal import Decimal
from unittest import mock

import pytest
from dateutil.relativedelta import relativedelta

from admin.views.models.payments import (
    MonthlyPaymentsView,
    create_fees_with_date,
    create_invoice_with_single_fee,
)
from appointments.models.payments import FeeAccountingEntry, FeeAccountingEntryTypes
from pytests.freezegun import freeze_time
from storage.connection import db
from tasks.payments import (
    PROVIDER_PAYMENTS_EMAIL,
    generate_invoices_from_fees,
    process_invoices_from_fees,
    start_invoice_transfers_job,
)


@pytest.fixture
def practitioners(factories):
    return factories.PractitionerUserFactory.create_batch(size=2)


@pytest.fixture
def practitioners_fees(factories):
    practitioners_fees = {"practitioners": [], "fees": []}
    now = datetime.utcnow()
    created_at = date(now.year, now.month, 1) - relativedelta(months=1)
    for i in range(2):
        practitioner = factories.PractitionerUserFactory.create()
        practitioners_fees["practitioners"].append(practitioner)
        # Create fees based on current prac count (allows for variance)
        for j in range(i):
            practitioners_fees["fees"].append(
                factories.FeeAccountingEntryFactory.create(
                    practitioner=practitioner,
                    amount=Decimal(j * 5),
                    created_at=created_at,
                )
            )
    return practitioners_fees


@pytest.fixture
@mock.patch("flask_login.current_user")
def practitioners_invoices(mock_current_user, factories):
    practitioners_invoices = {"practitioners": [], "invoices": []}
    now = datetime.utcnow()
    last_month = date(now.year, now.month, 1) - relativedelta(months=1)
    for i in range(2):
        # Create prac
        stripe_account_id = f"stripe-{i}"
        practitioner = factories.PractitionerUserFactory.create(
            practitioner_profile__stripe_account_id=stripe_account_id
        )
        practitioners_invoices["practitioners"].append(practitioner)
        # Create invoice with fee attached
        fee_amount_cents = i * 1000
        invoice = create_invoice_with_single_fee(
            practitioner.practitioner_profile.user_id, fee_amount_cents
        )
        # Set the start date for the invoice to last month and add
        invoice.started_at = last_month
        practitioners_invoices["invoices"].append(invoice)

    return practitioners_invoices


@freeze_time("2021-05-25T17:00:00")
@mock.patch("admin.views.models.payments.emit_bulk_audit_log_create")
def test_create_fees_with_date(mock_audit_log, practitioners):
    practitioner_amounts = {}
    for prac in practitioners:
        practitioner_amounts[prac.id] = round(Decimal(500.23), 2)
    today = datetime.today()

    mock_audit_log.return_value = None

    fees = create_fees_with_date(practitioner_amounts, today)
    mock_audit_log.assert_called_once()

    for fee in fees:
        fee_entry = FeeAccountingEntry.query.get(fee["fae_id"])
        assert fee_entry.amount == practitioner_amounts[fee["practitioner_id"]]
        assert fee_entry.created_at == today
        assert fee["status"] in f"Fee accounting entry creation on {today} successful"


@freeze_time("2021-05-25T17:00:00")
def test_create_fees_with_date_amount_less_than_zero(factories, practitioners):
    prac = practitioners[0]
    practitioner_amount = {prac.id: round(Decimal(-1.00), 2)}

    today = datetime.today()
    fees = create_fees_with_date(practitioner_amount, today)

    for fee in fees:
        prac_ids = list(practitioner_amount.keys())
        assert fee["practitioner_id"] == prac_ids[0]
        assert fee["amount"] == practitioner_amount[fee["practitioner_id"]]
        assert fee["status"] in "Skipping: row: {0}, amount={1}".format(
            today, practitioner_amount[fee["practitioner_id"]]
        )


@pytest.fixture
def practitioners_with_fee(factories):
    practitioners = []
    for i in range(2):
        practitioner = factories.PractitionerUserFactory.create()
        vertical = factories.VerticalFactory.create(
            name="Wellness Coach",
            pluralized_display_name="Wellness Coaches",
            can_prescribe=False,
            filter_by_state=False,
        )
        practitioner.practitioner_profile.verticals = [vertical]
        practitioner.practitioner_profile.stripe_account_id = i + 1
        prac = {"prac": practitioner, "fee": i + 100}

        practitioners.append(prac)
    return practitioners


@mock.patch("flask_login.current_user")
def test_create_invoice_with_single_fee(mock_current_user, practitioners_with_fee):
    for prac_with_fee in practitioners_with_fee:
        inv = create_invoice_with_single_fee(
            prac_with_fee["prac"].id, prac_with_fee["fee"]
        )
        assert len(inv.entries) == 1
        assert inv.entries[0].type == FeeAccountingEntryTypes.NON_STANDARD_HOURLY
        # convert amount from USD to cents before check
        assert inv.entries[0].amount * 100 == prac_with_fee["fee"]


@mock.patch("flask_login.current_user")
def test_create_invoice_with_single_fee_remove_fae_on_error(
    mock_current_user, factories
):
    practitioner = factories.PractitionerUserFactory.create()
    inv = create_invoice_with_single_fee(practitioner.id, 9999)
    assert inv is None
    assert (
        len(
            db.session.query(FeeAccountingEntry)
            .filter(FeeAccountingEntry.amount == 99.99)
            .all()
        )
        == 0
    )


@mock.patch("flask_login.current_user")
def test_generate_invoices_from_fees__one_prac_two_fees(
    mock_current_user, practitioners_with_fee
):
    # Given a practitioner with two fees in the last month
    now = datetime.utcnow()
    last_month = date(now.year, now.month, 1) - relativedelta(months=1)
    prac = practitioners_with_fee[0]["prac"]
    create_fees_with_date({prac.id: 10}, last_month)
    create_fees_with_date({prac.id: 10}, last_month)

    # When
    invoices, _ = generate_invoices_from_fees()

    # Then
    assert len(invoices) == 1
    assert len(invoices[0].entries) == 2


@mock.patch("flask_login.current_user")
def test_generate_invoices_from_fees__two_pracs_one_fee_each(
    mock_current_user, practitioners_with_fee
):
    # Given two practitioners with one fee each
    now = datetime.utcnow()
    last_month = date(now.year, now.month, 1) - relativedelta(months=1)
    prac = practitioners_with_fee[0]["prac"]
    prac_2 = practitioners_with_fee[1]["prac"]
    create_fees_with_date({prac.id: 10}, last_month)
    create_fees_with_date({prac_2.id: 10}, last_month)

    # When
    invoices, _ = generate_invoices_from_fees()

    # Then
    assert len(invoices) == 2
    assert len(invoices[0].entries) == 1
    assert len(invoices[1].entries) == 1


@mock.patch("flask_login.current_user")
def test_generate_invoices_from_fees__old_invoice_skipped(
    mock_current_user, factories, practitioners_with_fee
):
    # Given
    now = datetime.utcnow()
    last_month = date(now.year, now.month, 1) - relativedelta(months=1)
    prac = practitioners_with_fee[0]["prac"]

    # Add old open invoice
    with freeze_time("2022-05-25T17:00:00"):
        old_invoice = factories.InvoiceFactory.create(
            recipient_id=prac.practitioner_profile.stripe_account_id,
            started_at=None,
        )

    # Add new fee
    create_fees_with_date({prac.id: Decimal(10.02)}, last_month)

    # When
    invoices, _ = generate_invoices_from_fees()

    # Then
    assert len(invoices) == 1
    assert len(invoices[0].entries) == 1
    assert invoices[0].id != old_invoice.id


class TestStartInvoiceTransfersJob:
    @mock.patch("tasks.payments.get_fees")
    @mock.patch("tasks.payments.send_message")
    def test_start_invoice_transfers_job__invalid_fee_hash(
        self,
        mock_send_message,
        mock_get_fees,
    ):
        # Given
        invalid_fee_hash = "invalid_fee_hash"
        valid_fee_hash = "valid_fee_hash"
        mock_get_fees.return_value = [], valid_fee_hash

        # When
        start_invoice_transfers_job(invalid_fee_hash)

        # Then
        mock_get_fees.assert_called_once()
        mock_send_message.assert_called_with(
            to_email=PROVIDER_PAYMENTS_EMAIL,
            subject="Invoice Transfer job failed before starting - invalid fee hash",
            text=mock.ANY,
            internal_alert=True,
            production_only=True,
        )

    @mock.patch("tasks.payments.get_fees")
    @mock.patch("tasks.payments.send_message")
    def test_start_invoice_transfers_job__empty_fees(
        self,
        mock_send_message,
        mock_get_fees,
    ):

        # Given
        valid_fee_hash = "valid_fee_hash"
        mock_get_fees.return_value = [], valid_fee_hash

        # When
        start_invoice_transfers_job(valid_fee_hash)

        # Then
        mock_get_fees.assert_called_once()
        mock_send_message.assert_called_with(
            to_email=PROVIDER_PAYMENTS_EMAIL,
            subject="Invoice Transfer job failed before starting - no fees found",
            text=mock.ANY,
            internal_alert=True,
            production_only=True,
        )

    @mock.patch("tasks.payments.get_fees")
    @mock.patch("tasks.payments.send_message")
    @mock.patch("tasks.payments.process_invoices_from_fees")
    def test_start_invoice_transfers_job__valid(
        self,
        mock_process_invoices_from_fees,
        mock_send_message,
        mock_get_fees,
        factories,
    ):

        # Given
        valid_fee_hash = "valid_fee_hash"
        fee = factories.FeeAccountingEntryFactory()
        mock_get_fees.return_value = [fee], valid_fee_hash
        mock_process_invoices_from_fees.return_value = None

        # When
        start_invoice_transfers_job(valid_fee_hash)

        # Then
        mock_get_fees.assert_called_once()
        mock_process_invoices_from_fees.assert_called_once()
        send_message_started = mock.call(
            to_email=PROVIDER_PAYMENTS_EMAIL,
            subject="Invoice Transfer job started",
            text=mock.ANY,
            internal_alert=True,
            production_only=True,
        )
        send_message_completed = mock.call(
            to_email=PROVIDER_PAYMENTS_EMAIL,
            subject="Invoice Transfer job completed",
            text=mock.ANY,
            internal_alert=True,
            production_only=True,
        )
        mock_send_message.assert_has_calls(
            [send_message_started, send_message_completed]
        )
        assert mock_send_message.call_count == 2

    @mock.patch("tasks.payments.get_fees")
    @mock.patch("tasks.payments.send_message")
    @mock.patch("tasks.payments.process_invoices_from_fees")
    def test_start_invoice_transfers_job__override_hash(
        self,
        mock_process_invoices_from_fees,
        mock_send_message,
        mock_get_fees,
        factories,
    ):

        # Given
        no_fee_hash = None
        override_hash = True
        valid_fee_hash = "valid_fee_hash"
        fee = factories.FeeAccountingEntryFactory()
        mock_get_fees.return_value = [fee], valid_fee_hash
        mock_process_invoices_from_fees.return_value = None

        # When
        start_invoice_transfers_job(no_fee_hash, override_hash)

        # Then
        mock_get_fees.assert_called_once()
        mock_process_invoices_from_fees.assert_called_once()
        send_message_started = mock.call(
            to_email=PROVIDER_PAYMENTS_EMAIL,
            subject="Invoice Transfer job started",
            text=mock.ANY,
            internal_alert=True,
            production_only=True,
        )
        send_message_completed = mock.call(
            to_email=PROVIDER_PAYMENTS_EMAIL,
            subject="Invoice Transfer job completed",
            text=mock.ANY,
            internal_alert=True,
            production_only=True,
        )
        mock_send_message.assert_has_calls(
            [send_message_started, send_message_completed]
        )
        assert mock_send_message.call_count == 2


class TestGenerateFeesProcessRow:
    def test__generate_fees_process_row__valid_empty_row(self):
        # Given - an empty row
        prac_id = ""
        amount = ""
        line_num = 2

        # When - the row is processed
        amount = MonthlyPaymentsView._generate_fees_process_row(
            prac_id, amount, line_num
        )

        # Then - Nothing is returned because it is skipped
        assert amount is None

    def test__generate_fees_process_row__missing_practitioner(self):
        # Given - the prac_id is empty
        prac_id = ""
        amount = "50.00"
        line_num = 2

        # When - the row is processed
        with pytest.raises(ValueError) as ex:
            MonthlyPaymentsView._generate_fees_process_row(prac_id, amount, line_num)

        # Then - the correct exception is raised
        # TODO: Does the str() need to be there
        assert str(ex.value) == f"Missing practitioner on row {line_num}."

    def test__generate_fees_process_row__missing_amount(self):
        # Given - the amount is empty
        prac_id = "789"
        amount = ""
        line_num = 2

        # When - the row is processed
        with pytest.raises(ValueError) as ex:
            MonthlyPaymentsView._generate_fees_process_row(prac_id, amount, line_num)

        # Then - the correct exception is raised
        assert (
            str(ex.value)
            == f"Missing amount for practitioner {prac_id} on row {line_num}."
        )

    def test__generate_fees_process_row__invalid_prac_id_format(self):
        # Given - the prac_id is not an integer
        prac_id = "123a"
        amount = "50.00"
        line_num = 2

        # When - the row is processed
        with pytest.raises(ValueError) as ex:
            MonthlyPaymentsView._generate_fees_process_row(prac_id, amount, line_num)

        # Then - the correct exception is raised
        assert (
            str(ex.value)
            == f"Invalid number for practitioner {prac_id} on row {line_num}."
        )

    def test__generate_fees_process_row__invalid_amount_format_1(self):
        # Given - the amount is not in the correct format
        prac_id = "789"
        amount = "50.000.50"
        line_num = 2

        # When - the row is processed
        with pytest.raises(ValueError) as ex:
            MonthlyPaymentsView._generate_fees_process_row(prac_id, amount, line_num)

        # Then - the correct exception is raised
        assert (
            str(ex.value)
            == f"Invalid amount for practitioner {prac_id} on row {line_num}."
        )

    def test__generate_fees_process_row__invalid_amount_format_2(self):
        # Given - the amount is not in the correct format
        prac_id = "789"
        amount = "123,50"
        line_num = 2

        # When - the row is processed
        with pytest.raises(ValueError) as ex:
            MonthlyPaymentsView._generate_fees_process_row(prac_id, amount, line_num)

        # Then - the correct exception is raised
        assert (
            str(ex.value)
            == f"Invalid amount for practitioner {prac_id} on row {line_num}."
        )

    def test__generate_fees_process_row__invalid_amount_format_3(self):
        # Given - the amount is not in the correct format
        prac_id = "789"
        amount = "123.500"
        line_num = 2

        # When - the row is processed
        with pytest.raises(ValueError) as ex:
            MonthlyPaymentsView._generate_fees_process_row(prac_id, amount, line_num)

        # Then - the correct exception is raised
        assert (
            str(ex.value)
            == f"Invalid amount for practitioner {prac_id} on row {line_num}."
        )

    def test__generate_fees_process_row__invalid_amount_format_4(self):
        # Given - the amount is not in the correct format
        prac_id = "789"
        amount = "1.500,00"
        line_num = 2

        # When - the row is processed
        with pytest.raises(ValueError) as ex:
            MonthlyPaymentsView._generate_fees_process_row(prac_id, amount, line_num)

        # Then - the correct exception is raised
        assert (
            str(ex.value)
            == f"Invalid amount for practitioner {prac_id} on row {line_num}."
        )

    def test__generate_fees_process_row__invalid_multiple_entries(self):
        # Given - a prac_id is in the csv multiple times
        prac_id = "789"
        amount = "50.00"
        line_num = 2
        provider_amounts = {122: 50, 124: 50, 789: 50}

        # When - the row is processed
        with pytest.raises(ValueError) as ex:
            MonthlyPaymentsView._generate_fees_process_row(
                prac_id, amount, line_num, provider_amounts
            )

        # Then - the correct exception is raised
        assert str(ex.value) == f"practitioner {prac_id} cannot have multiple payments."

    def test__generate_fees_process_row___valid(self):
        # Given - valid data
        prac_id = "789"
        amount = "50.00"
        correct_amount = 50.00
        line_num = 2

        # When - the row is processed
        amount_returned = MonthlyPaymentsView._generate_fees_process_row(
            prac_id, amount, line_num
        )

        # Then - the correct amount is returned
        assert amount_returned == correct_amount

    def test__generate_fees_process_row__valid_amount_format_1(self):
        # Given - the amount is formatted how we can handle
        prac_id = "789"
        amount = "$50"
        correct_amount = 50.00
        line_num = 2

        # When - the row is processed
        amount_returned = MonthlyPaymentsView._generate_fees_process_row(
            prac_id, amount, line_num
        )

        # Then - the correct amount is returned
        assert amount_returned == correct_amount

    def test__generate_fees_process_row__valid_amount_format_2(self):
        # Given - the amount is formatted how we can handle
        prac_id = "789"
        amount = "50.0"
        correct_amount = 50.00
        line_num = 2

        # When - the row is processed
        amount_returned = MonthlyPaymentsView._generate_fees_process_row(
            prac_id, amount, line_num
        )

        # Then - the correct amount is returned
        assert amount_returned == correct_amount

    def test__generate_fees_process_row__valid_amount_format_3(self):
        # Given - the amount is formatted how we can handle
        prac_id = "789"
        amount = "$1,234"
        correct_amount = 1234.00
        line_num = 2

        # When - the row is processed
        amount_returned = MonthlyPaymentsView._generate_fees_process_row(
            prac_id, amount, line_num
        )

        # Then - the correct amount is returned
        assert amount_returned == correct_amount

    def test__generate_fees_process_row__valid_amount_format_4(self):
        # Given - the amount is formatted how we can handle
        prac_id = "789"
        amount = "1234"
        correct_amount = 1234.00
        line_num = 2

        # When - the row is processed
        amount_returned = MonthlyPaymentsView._generate_fees_process_row(
            prac_id, amount, line_num
        )

        # Then - the correct amount is returned
        assert amount_returned == correct_amount

    def test__generate_fees_process_row__valid_amount_format_5(self):
        # Given - the amount is formatted how we can handle
        prac_id = "789"
        amount = "$123,456,789.50"
        correct_amount = 123456789.50
        line_num = 2

        # When - the row is processed
        amount_returned = MonthlyPaymentsView._generate_fees_process_row(
            prac_id, amount, line_num
        )

        # Then
        assert amount_returned == correct_amount

    def test__generate_fees_process_row__valid_multiple_entries(self):
        # Given - practitioner amounts are passed, but doesn't contain the current id
        prac_id = "789"
        amount = "50.00"
        correct_amount = 50.00
        line_num = 2
        provider_amounts = {122: 52, 124: 54}

        # When - the row is processed
        amount_returned = MonthlyPaymentsView._generate_fees_process_row(
            prac_id, amount, line_num, provider_amounts
        )

        # Then - the amount returned is correct
        assert amount_returned == correct_amount


class TestProcessInvoicesFromCleanFees:
    @mock.patch("tasks.payments.create_fee_invoices")
    @mock.patch("tasks.payments.send_message")
    def test_process_invoices_from_fees__valid_hash_no_email(
        self, mock_send_message, mock_create_fee_invoices, practitioners_fees
    ):
        # Given - a valid hash is passed
        valid_hash = "valid-hash-value"
        valid_fees = practitioners_fees["fees"]
        valid_fee_ids = [fee.id for fee in valid_fees]

        # When - we process invoices from fees
        mock_create_fee_invoices.return_value = [], valid_hash
        process_invoices_from_fees(valid_fee_ids, valid_hash)

        # Then - no error email is sent
        mock_send_message.assert_not_called()

    @mock.patch("tasks.payments.create_fee_invoices")
    @mock.patch("tasks.payments.send_message")
    def test_process_invoices_from_fees__invalid_hash_email_sent(
        self, mock_send_message, mock_create_fee_invoices, practitioners_fees
    ):
        # Given - an invalid hash is passed
        valid_hash = "valid-hash-value"
        invalid_hash = "invalid-hash-value"
        valid_fees = practitioners_fees["fees"]
        valid_fee_ids = [fee.id for fee in valid_fees]

        # When - we process invoices from fees
        mock_create_fee_invoices.return_value = [], valid_hash
        process_invoices_from_fees(valid_fee_ids, invalid_hash)

        # Then - error email is sent
        mock_send_message.assert_called_once()

    @mock.patch("tasks.payments.create_fee_invoices")
    def test_process_invoices_from_fees__create_fee_invoices(
        self, mock_create_fee_invoices, practitioners_fees
    ):
        # Given - valid fees are passed
        valid_hash = "valid-hash-value"
        valid_fees = practitioners_fees["fees"]
        valid_fee_ids = [fee.id for fee in valid_fees]

        # When - process_invoices_from_fees calls create_fee_invoices
        mock_create_fee_invoices.return_value = [], valid_hash
        process_invoices_from_fees(valid_fee_ids, valid_hash)

        # Then - the correct parameters are passed to create_fee_invoices
        mock_create_fee_invoices.assert_called_with(
            valid_fees, to_email=PROVIDER_PAYMENTS_EMAIL
        )

    @mock.patch("tasks.payments.create_fee_invoices")
    @mock.patch("tasks.payments.start_invoices.delay")
    @mock.patch("flask_login.current_user")
    def test_process_invoices_from_fees__start_invoices(
        self,
        mock_current_user,
        mock_start_invoices_delay,
        mock_create_fee_invoices,
        practitioners_invoices,
    ):
        # Given - valid invoices are returned from create_fee_invoices
        valid_hash = "valid-hash-value"
        valid_invoices = practitioners_invoices["invoices"]
        valid_invoice_ids = [invoice.id for invoice in valid_invoices]

        # When - process_invoices_from_fees calls create_fee_invoices
        mock_create_fee_invoices.return_value = valid_invoices, valid_hash
        process_invoices_from_fees([], valid_hash)

        # Then - start_invoices is called for those invoices
        mock_start_invoices_delay.assert_called_with(
            team_ns="payments_platform",
            job_timeout=30 * 60,
            invoice_ids=valid_invoice_ids,
        )
