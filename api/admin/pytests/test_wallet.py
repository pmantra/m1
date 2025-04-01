import factory

from admin.blueprints.wallet import (
    _parse_employer_configuration_form_data,
    _parse_employer_direct_billing_account_form_data,
)
from admin.views.models.wallet_category import ReimbursementOrganizationSettingsFilter
from wallet.models.reimbursement_organization_settings import (
    ReimbursementOrgSettingCategoryAssociation,
)
from wallet.pytests.factories import ReimbursementOrganizationSettingsFactory


class TestWalletToolsHelpers:
    def test_parse_employer_configuration_form_data_with_banking__success(self):
        data = {
            "org_id": "1",
            "bank_account_usage_code": "3",
            "financial_institution": "Test Bank",
            "account_number": "123456789",
            "routing_number": "987654321",
            "payroll_only": False,
        }
        success, bank_data = _parse_employer_configuration_form_data(data)
        assert success
        assert bank_data == data

    def test_parse_employer_configuration_form_data_sans_banking__success(self):
        data = {
            "org_id": "1",
            "bank_account_usage_code": "3",
            "financial_institution": "",
            "account_number": "",
            "routing_number": "",
            "payroll_only": True,
        }
        success, bank_data = _parse_employer_configuration_form_data(data)
        assert success

    def test_parse_employer_configuration_form_data_with_banking_account_validation__fails(
        self,
    ):
        data = {
            "org_id": "1",
            "bank_account_usage_code": "3",
            "financial_institution": "Test Bank",
            "account_number": "12",
            "routing_number": "987654321",
            "payroll_only": False,
        }
        success, bank_data = _parse_employer_configuration_form_data(data)
        assert success is False

    def test_parse_employer_configuration_form_data_with_banking_routing_validation__fails(
        self,
    ):
        data = {
            "org_id": "1",
            "bank_account_usage_code": "3",
            "financial_institution": "Test Bank",
            "account_number": "123456789",
            "routing_number": "2",
            "payroll_only": False,
        }
        success, bank_data = _parse_employer_configuration_form_data(data)
        assert success is False

    def test_parse_employer_direct_billing_account_form_data__success(self):
        data = {
            "org_settings_id": "1",
            "account_type": "checking",
            "account_holder_type": "company",
            "account_number": "123456789",
            "routing_number": "987654321",
        }
        success, bank_data = _parse_employer_direct_billing_account_form_data(data)
        assert success
        assert bank_data == data

    def test_parse_employer_direct_billing_account_form_data__account_validation_fails(
        self,
    ):
        data = {
            "org_settings_id": "1",
            "account_type": "checking",
            "account_holder_type": "company",
            "account_number": "12",
            "routing_number": "987654321",
        }
        success, bank_data = _parse_employer_direct_billing_account_form_data(data)
        assert success is False

    def test_parse_employer_direct_billing_account_form_data__routing_validation_fails(
        self,
    ):
        data = {
            "org_settings_id": "1",
            "account_type": "checking",
            "account_holder_type": "company",
            "account_number": "123456789",
            "routing_number": "2",
        }
        success, bank_data = _parse_employer_direct_billing_account_form_data(data)
        assert success is False


class TestReimbursementOrgSettingCategoryAssociationFilter:
    def test_reimbursement_org_category_association_filter(self, factories, db):
        organizations = factories.OrganizationFactory.create_batch(
            size=2, name=factory.Iterator(["test123", "abc123"])
        )
        ReimbursementOrganizationSettingsFactory.create_batch(
            size=2,
            organization_id=factory.Iterator(
                [organization.id for organization in organizations]
            ),
        )
        org, org2 = organizations

        assert len(self._query_by_organization(db, org2.name)) == 1
        assert len(self._query_by_organization(db, org.name)) == 1
        assert len(self._query_by_organization(db, "123")) == 2
        assert len(self._query_by_organization(db, "wrong")) == 0

    @staticmethod
    def _query_by_organization(db, organization_name) -> list:
        return (
            ReimbursementOrganizationSettingsFilter(None, None)
            .apply(
                db.session.query(ReimbursementOrgSettingCategoryAssociation),
                organization_name,
            )
            .all()
        )
