from datetime import datetime

import factory
import pytest

from direct_payment.invoicing.pytests import factories
from wallet.pytests.factories import ReimbursementOrganizationSettingsFactory


class TestDirectPaymentInvoiceBase:
    def test_create_direct_payment_invoice(self, direct_payment_invoice_repository):
        ros = ReimbursementOrganizationSettingsFactory.create(organization_id=1000)
        dpi = factories.DirectPaymentInvoiceFactory.build(
            reimbursement_organization_settings_id=ros.id
        )
        created = direct_payment_invoice_repository.create(instance=dpi)
        assert created.id

    def test_get_direct_payment_invoice(
        self,
        direct_payment_invoice_repository,
        new_direct_payment_invoice,
    ):
        retrieved = direct_payment_invoice_repository.get(
            id=new_direct_payment_invoice.id
        )
        assert retrieved

    def test_get_no_direct_payment_invoice(self, direct_payment_invoice_repository):
        retrieved = direct_payment_invoice_repository.get(id=-1)
        assert retrieved is None

    def test_get_get_latest_invoice_by_reimbursement_organization_settings_id(
        self, direct_payment_invoice_repository, create_dpis
    ):
        ros = ReimbursementOrganizationSettingsFactory.create(organization_id=1000)
        dpis = create_dpis(ros.id)
        res = direct_payment_invoice_repository.get_latest_invoice_by_reimbursement_organization_settings_id(
            reimbursement_organization_settings_id=ros.id
        )
        assert res == dpis[1]

    def test_get_get_latest_invoice_by_reimbursement_organization_settings_id_not_found(
        self, direct_payment_invoice_repository, create_dpis
    ):
        ros = ReimbursementOrganizationSettingsFactory.create(organization_id=1000)
        _ = create_dpis(ros.id)
        res = direct_payment_invoice_repository.get_latest_invoice_by_reimbursement_organization_settings_id(
            reimbursement_organization_settings_id=ros.id + 1
        )
        assert res is None


@pytest.fixture()
def create_dpis(direct_payment_invoice_repository):
    def fn(ros_id):
        return [
            direct_payment_invoice_repository.create(instance=inv)
            for inv in factories.DirectPaymentInvoiceFactory.build_batch(
                size=3,
                reimbursement_organization_settings_id=ros_id,
                bill_creation_cutoff_end_at=factory.Iterator(
                    datetime(y, 1, 1)
                    for y in (2024, 2026, 2025)  # 3 dates, the middle one the latest
                ),
            )
        ]

    return fn
