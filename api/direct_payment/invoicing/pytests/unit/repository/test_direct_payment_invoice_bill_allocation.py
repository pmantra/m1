from direct_payment.invoicing.pytests import factories


class TestDirectPaymentInvoiceBase:
    def test_create_direct_payment_invoice_bill_allocation(
        self,
        direct_payment_invoice_bill_allocation_repository,
        new_direct_payment_invoice,
    ):
        created = direct_payment_invoice_bill_allocation_repository.create(
            instance=(
                factories.DirectPaymentInvoiceBillAllocationFactory(
                    direct_payment_invoice_id=new_direct_payment_invoice.id
                )
            )
        )
        assert created.id

    def test_get_direct_payment_invoice_bill_allocation(
        self,
        direct_payment_invoice_bill_allocation_repository,
        new_direct_payment_invoice_bill_allocation,
    ):
        retrieved = direct_payment_invoice_bill_allocation_repository.get(
            id=new_direct_payment_invoice_bill_allocation.id
        )
        assert retrieved

    def test_get_no_direct_payment_invoice_bill_allocation(
        self, direct_payment_invoice_bill_allocation_repository
    ):
        retrieved = direct_payment_invoice_bill_allocation_repository.get(id=-1)
        assert retrieved is None

    def test_get_invoice_bills_ready_to_process(
        self, invoice_bills, direct_payment_invoice_bill_allocation_repository
    ):
        results = (
            direct_payment_invoice_bill_allocation_repository.get_invoice_bills_ready_to_process()
        )

        assert len(results) == 2
        assert str(results[0].uuid) != str(results[1].uuid)
        assert str(results[0].uuid) in (
            str(invoice_bills[5].uuid),
            str(invoice_bills[3].uuid),
        )
        assert str(results[1].uuid) in (
            str(invoice_bills[5].uuid),
            str(invoice_bills[3].uuid),
        )
