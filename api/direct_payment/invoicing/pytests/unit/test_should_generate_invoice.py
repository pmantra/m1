from datetime import datetime
from unittest.mock import patch

from direct_payment.invoicing.tasks.generate_invoices_job import should_generate_invoice


def test_should_generate_invoice_invalid_input():
    assert not should_generate_invoice(None, 123)

    assert not should_generate_invoice("1 ** 234 *", 123)


@patch("direct_payment.invoicing.tasks.generate_invoices_job.datetime")
def test_should_generate_invoice_valid_input(mock_datetime):
    mock_datetime.utcnow.return_value = datetime(2024, 10, 20)

    assert should_generate_invoice("* * 20 * *", 123)
    assert should_generate_invoice("* * 20 10 *", 123)
    assert should_generate_invoice("* * * * 0", 123)

    assert not should_generate_invoice("* * 19 * *", 123)
    assert not should_generate_invoice("* * 20 11 *", 123)
    assert not should_generate_invoice("* * * * 3", 123)
