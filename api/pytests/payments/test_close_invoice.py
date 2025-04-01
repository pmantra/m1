import datetime


class TestInvoiceModelCloseInvoice:
    def test_close_invoice__started_at_not_none(self, factories):
        invoice = factories.InvoiceFactory()
        invoice.started_at = datetime.datetime.utcnow()

        invoice_closed = invoice.close_invoice()
        assert invoice_closed is False

    def test_close_invoice___started_at_is_none(self, factories):
        invoice = factories.InvoiceFactory()
        invoice.started_at = None

        invoice_closed = invoice.close_invoice()

        assert invoice.started_at is not None
        assert invoice.completed_at is not None
        assert invoice.transfer_id is not None
        assert invoice_closed is True
