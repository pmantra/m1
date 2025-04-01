import uuid

import factory
import pytest

from direct_payment.invoicing.pytests import factories
from pytests.factories import OrganizationFactory
from wallet.pytests.factories import ReimbursementOrganizationSettingsFactory


class TestOrganizationInvoicingSettingsBase:
    def test_create_organization_invoicing_settings(
        self, organization_invoicing_settings_repository
    ):
        org = OrganizationFactory.create()
        ois = factories.OrganizationInvoicingSettingsFactory.build(
            organization_id=org.id
        )
        created = organization_invoicing_settings_repository.create(instance=ois)
        assert created.id

    def test_get_organization_invoicing_settings(
        self,
        organization_invoicing_settings_repository,
        new_organization_invoicing_settings,
    ):
        retrieved = organization_invoicing_settings_repository.get(
            id=new_organization_invoicing_settings.id
        )
        assert retrieved

    def test_get_no_organization_invoicing_settings(
        self, organization_invoicing_settings_repository
    ):
        retrieved = organization_invoicing_settings_repository.get(id=-1)
        assert retrieved is None

    def test_get_organization_invoicing_settings_by_organization_id(
        self,
        organization_invoicing_settings_repository,
        new_organization_invoicing_settings,
    ):
        retrieved = organization_invoicing_settings_repository.get_by_organization_id(
            organization_id=new_organization_invoicing_settings.organization_id
        )
        assert retrieved
        assert retrieved.uuid == new_organization_invoicing_settings.uuid

    def test_get_no_organization_invoicing_settings_by_organization_id(
        self,
        organization_invoicing_settings_repository,
    ):
        retrieved = organization_invoicing_settings_repository.get_by_organization_id(
            organization_id=-1
        )
        assert retrieved is None

    def test_get_organization_invoicing_settings_by_uuid(
        self,
        organization_invoicing_settings_repository,
        new_organization_invoicing_settings,
    ):
        retrieved = organization_invoicing_settings_repository.get_by_uuid(
            uuid=new_organization_invoicing_settings.uuid
        )
        assert retrieved
        assert retrieved.uuid == new_organization_invoicing_settings.uuid

    def test_get_no_organization_invoicing_settings_by_uuid(
        self,
        organization_invoicing_settings_repository,
    ):
        retrieved = organization_invoicing_settings_repository.get_by_uuid(
            uuid=uuid.uuid4()
        )
        assert retrieved is None

    def test_delete(
        self,
        organization_invoicing_settings_repository,
        new_organization_invoicing_settings,
    ):
        result_one = organization_invoicing_settings_repository.delete(id=-1)
        assert result_one == 0

        result_two = organization_invoicing_settings_repository.delete(
            id=new_organization_invoicing_settings.id
        )
        assert result_two == 1

    def test_delete_by_uuid(
        self,
        organization_invoicing_settings_repository,
        new_organization_invoicing_settings,
    ):
        result_one = organization_invoicing_settings_repository.delete_by_uuid(
            uuid=uuid.uuid4()
        )
        assert result_one == 0

        result_two = organization_invoicing_settings_repository.delete_by_uuid(
            uuid=new_organization_invoicing_settings.uuid
        )
        assert result_two == 1

    def test_delete_by_organization_id(
        self,
        organization_invoicing_settings_repository,
        new_organization_invoicing_settings,
    ):
        result_one = (
            organization_invoicing_settings_repository.delete_by_organization_id(
                organization_id=-1
            )
        )
        assert result_one == 0

        result_two = (
            organization_invoicing_settings_repository.delete_by_organization_id(
                organization_id=new_organization_invoicing_settings.organization_id
            )
        )
        assert result_two == 1

    @pytest.mark.parametrize(argnames="org_row_count", argvalues=(1, 2, 3))
    def test_get_organization_invoicing_settings_by_payments_customer_id(
        self,
        organization_invoicing_settings_repository,
        org_row_count,
    ):
        org = OrganizationFactory.create()
        ois = factories.OrganizationInvoicingSettingsFactory.build(
            organization_id=org.id
        )
        exp = organization_invoicing_settings_repository.create(instance=ois)
        payments_customer_id = 1234
        for _ in range(0, org_row_count):
            _ = ReimbursementOrganizationSettingsFactory.create(
                organization_id=org.id, payments_customer_id=payments_customer_id
            )
        res = organization_invoicing_settings_repository.get_by_payments_customer_id(
            payments_customer_id=payments_customer_id
        )
        assert res is not None
        assert res.id == exp.id
        assert res.uuid == exp.uuid

    def test_get_organization_invoicing_settings_by_payments_customer_id_not_found(
        self,
        organization_invoicing_settings_repository,
    ):
        org = OrganizationFactory.create()
        payments_customer_id = 1234
        _ = ReimbursementOrganizationSettingsFactory.create(
            organization_id=org.id, payments_customer_id=payments_customer_id
        )
        ois = factories.OrganizationInvoicingSettingsFactory.build(
            organization_id=org.id
        )
        _ = organization_invoicing_settings_repository.create(instance=ois)
        res = organization_invoicing_settings_repository.get_by_payments_customer_id(
            payments_customer_id=payments_customer_id + 1
        )
        assert res is None

    def test_get_organization_invoicing_settings_by_payments_customer_id_bad_data(
        self,
        organization_invoicing_settings_repository,
    ):
        orgs = OrganizationFactory.create_batch(2)
        org_ids = [o.id for o in orgs]
        payments_customer_id = 1234
        _ = ReimbursementOrganizationSettingsFactory.create_batch(
            2,
            organization_id=factory.Iterator(org_ids),
            payments_customer_id=factory.Iterator([payments_customer_id] * 2),
        )
        ois = factories.OrganizationInvoicingSettingsFactory.create_batch(
            2,
            organization_id=factory.Iterator(org_ids),
            uuid=factory.Iterator([uuid.uuid4(), uuid.uuid4()]),
        )
        for oi in ois:
            _ = organization_invoicing_settings_repository.create(instance=oi)
        with pytest.raises(ValueError):
            _ = organization_invoicing_settings_repository.get_by_payments_customer_id(
                payments_customer_id=payments_customer_id
            )

    def test_get_organization_invoicing_settings_by_reimbursement_organization_settings_id(
        self,
        organization_invoicing_settings_repository,
    ):
        org = OrganizationFactory.create()
        ois = factories.OrganizationInvoicingSettingsFactory.build(
            organization_id=org.id
        )
        _ = factories.OrganizationInvoicingSettingsFactory.build(
            organization_id=org.id + 1000
        )  # junk ois - org id guaranteed to not match the real one
        exp = organization_invoicing_settings_repository.create(instance=ois)

        ros = ReimbursementOrganizationSettingsFactory.create(organization_id=org.id)
        res = organization_invoicing_settings_repository.get_by_reimbursement_org_settings_id(
            reimbursement_organization_settings_id=ros.id
        )
        assert res is not None
        assert res.id == exp.id
        assert res.uuid == exp.uuid
        assert res.organization_id == ois.organization_id
        assert res.organization_id == exp.organization_id

    def test_get_organization_invoicing_settings_by_reimbursement_organization_settings_id_not_found(
        self,
        organization_invoicing_settings_repository,
    ):
        org = OrganizationFactory.create()
        ois = factories.OrganizationInvoicingSettingsFactory.build(
            organization_id=org.id
        )
        _ = factories.OrganizationInvoicingSettingsFactory.build(
            organization_id=org.id + 1000
        )  # junk ois - org id guaranteed to not match the real one
        _ = organization_invoicing_settings_repository.create(instance=ois)
        res = organization_invoicing_settings_repository.get_by_reimbursement_org_settings_id(
            reimbursement_organization_settings_id=100  # fake ros id
        )
        assert res is None
