import datetime

import pytest

from admin.views.models.wallet_org_setting import (
    ReimbursementOrganizationSettingsForm,
    ReimbursementOrganizationSettingsView,
)
from pytests import factories
from wallet.models.constants import BenefitTypes, WalletState
from wallet.pytests.factories import (
    ReimbursementAccountTypeFactory,
    ReimbursementOrganizationSettingsFactory,
    ReimbursementOrgSettingCategoryAssociationFactory,
    ReimbursementPlanFactory,
    ReimbursementRequestCategoryFactory,
    ReimbursementWalletFactory,
)


class TestReimbursementOrganizationSettingsView:
    def setup_method(self):
        self.enterprise_user = factories.EnterpriseUserFactory.create()
        self.wallet = ReimbursementWalletFactory.create(state=WalletState.QUALIFIED)
        self.org_settings = self.wallet.reimbursement_organization_settings
        factories.ReimbursementWalletUsersFactory.create(
            user_id=self.enterprise_user.id,
            reimbursement_wallet_id=self.wallet.id,
        )

    @staticmethod
    def _create_reimbursement_plan(start_year, end_year):
        return ReimbursementPlanFactory.create(
            reimbursement_account_type=ReimbursementAccountTypeFactory.create(
                alegeus_account_type="HRA"
            ),
            alegeus_plan_id="test_pan_1",
            start_date=datetime.date(year=start_year, month=1, day=1),
            end_date=datetime.date(year=end_year, month=12, day=31),
            is_hdhp=False,
        )

    @staticmethod
    def _create_reimbursement_request_category(benefit_type):
        # Helper method to create a reimbursement request category with specified benefit type
        return ReimbursementRequestCategoryFactory.create(
            label="category", reimbursement_plan=benefit_type
        )

    def _create_reimbursement_org_setting_category_association(
        self, benefit_type, category
    ):
        return ReimbursementOrgSettingCategoryAssociationFactory.create(
            benefit_type=benefit_type,
            reimbursement_organization_settings=self.org_settings,
            reimbursement_request_category=category,
            reimbursement_request_category_maximum=5000,
            num_cycles=2,
        )

    @staticmethod
    def test__debit_card_validations():
        # Test case 1: Debit card and direct payment enabled together
        with pytest.raises(ValueError) as exc_info:
            ReimbursementOrganizationSettingsForm._debit_card_validations(
                True, False, True, False
            )
        assert (
            str(exc_info.value)
            == "Debit card and direct payment cannot be enabled together."
        )

        # Test case 2: Debit card and deductible accumulation enabled together
        with pytest.raises(ValueError) as exc_info:
            ReimbursementOrganizationSettingsForm._debit_card_validations(
                False, True, True, False
            )
        assert (
            str(exc_info.value)
            == "Debit card and deductible accumulation cannot be enabled together."
        )

        # Test case 3: Debit card and cycles enabled together
        with pytest.raises(ValueError) as exc_info:
            ReimbursementOrganizationSettingsForm._debit_card_validations(
                False, False, True, True
            )
        assert (
            str(exc_info.value)
            == "Debit card and cycles cannot be enabled together. Org has an allowed category that has the "
            "benefit type of cycle."
        )

        # Test case 4: No exception raised when validations pass
        assert (
            ReimbursementOrganizationSettingsForm._debit_card_validations(
                False, False, False, False
            )
            is None
        )

        # Test case 5: No exception raised when debit card enabled and everything disabled
        assert (
            ReimbursementOrganizationSettingsForm._debit_card_validations(
                False, False, True, False
            )
            is None
        )

    @staticmethod
    def test__cycles_enabled_validations():
        # Test case 1: Cycles enabled, but direct payment disabled
        with pytest.raises(ValueError) as exc_info:
            ReimbursementOrganizationSettingsForm._cycles_enabled_validations(
                False, True, True
            )
        assert (
            str(exc_info.value)
            == "If direct payment is disabled, cycles cannot be enabled."
        )

        # Test case 2: Cycles enabled, but closed network disabled
        with pytest.raises(ValueError) as exc_info:
            ReimbursementOrganizationSettingsForm._cycles_enabled_validations(
                True, False, True
            )
        assert (
            str(exc_info.value)
            == "If closed network is disabled, cycles cannot be enabled."
        )

        # Test case 3: Cycles disabled, no exception raised
        assert (
            ReimbursementOrganizationSettingsForm._cycles_enabled_validations(
                True, True, False
            )
            is None
        )

        # Test case 4: Cycles, closed network and direct payment enabled
        assert (
            ReimbursementOrganizationSettingsForm._cycles_enabled_validations(
                True, True, True
            )
            is None
        )

    def test__is_cycles_enabled__no_allowed_categories(self):
        # Test case 1: No allowed reimbursement categories
        allowed_reimbursement_categories = None
        assert (
            ReimbursementOrganizationSettingsForm._is_cycles_enabled(
                allowed_reimbursement_categories
            )
            is False
        )

    def test__is_cycles_enabled_current_plan_with_cycle(self):
        plan = self._create_reimbursement_plan(
            datetime.date.today().year - 1, datetime.date.today().year + 2
        )
        category1 = self._create_reimbursement_request_category(plan)
        category2 = self._create_reimbursement_request_category(plan)
        org_settings_association_1 = (
            self._create_reimbursement_org_setting_category_association(
                BenefitTypes.CYCLE, category1
            )
        )
        org_settings_association_2 = (
            self._create_reimbursement_org_setting_category_association(
                BenefitTypes.CYCLE, category2
            )
        )
        # Test case 2: Current plan, benefit type is cycle
        allowed_reimbursement_categories = [
            org_settings_association_1,
            org_settings_association_2,
        ]
        assert (
            ReimbursementOrganizationSettingsForm._is_cycles_enabled(
                allowed_reimbursement_categories
            )
            is True
        )

    def test__is_cycles_enabled_current_plan_no_cycle(self):
        plan_current = self._create_reimbursement_plan(
            datetime.date.today().year - 1, datetime.date.today().year + 1
        )

        category1 = self._create_reimbursement_request_category(plan_current)
        category2 = self._create_reimbursement_request_category(plan_current)
        org_settings_association_1 = (
            self._create_reimbursement_org_setting_category_association(
                BenefitTypes.CURRENCY, category1
            )
        )
        org_settings_association_2 = (
            self._create_reimbursement_org_setting_category_association(
                BenefitTypes.CURRENCY, category2
            )
        )
        # Test case 3: Current plan, benefit type is not cycle
        allowed_reimbursement_categories = [
            org_settings_association_1,
            org_settings_association_2,
        ]
        assert (
            ReimbursementOrganizationSettingsForm._is_cycles_enabled(
                allowed_reimbursement_categories
            )
            is False
        )

    def test__is_cycles_enabled_expired_plan_and_with_cycle(self):
        plan_expired = self._create_reimbursement_plan(2020, 2021)

        category1 = self._create_reimbursement_request_category(plan_expired)
        category2 = self._create_reimbursement_request_category(plan_expired)
        org_settings_association_1 = (
            self._create_reimbursement_org_setting_category_association(
                BenefitTypes.CYCLE, category1
            )
        )
        org_settings_association_2 = (
            self._create_reimbursement_org_setting_category_association(
                BenefitTypes.CYCLE, category2
            )
        )
        # Test case 4: Expired plan, benefit type is cycle
        allowed_reimbursement_categories = [
            org_settings_association_1,
            org_settings_association_2,
        ]
        assert (
            ReimbursementOrganizationSettingsForm._is_cycles_enabled(
                allowed_reimbursement_categories
            )
            is False
        )

    def test__is_cycles_enabled_expired_plan_and_no_cycle(self):
        plan_expired = self._create_reimbursement_plan(2020, 2021)

        category1 = self._create_reimbursement_request_category(plan_expired)
        category2 = self._create_reimbursement_request_category(plan_expired)
        org_settings_association_1 = (
            self._create_reimbursement_org_setting_category_association(
                BenefitTypes.CURRENCY, category1
            )
        )
        org_settings_association_2 = (
            self._create_reimbursement_org_setting_category_association(
                BenefitTypes.CURRENCY, category2
            )
        )

        # Test case 5: Expired plan, benefit type is not cycle
        allowed_reimbursement_categories = [
            org_settings_association_1,
            org_settings_association_2,
        ]
        assert (
            ReimbursementOrganizationSettingsForm._is_cycles_enabled(
                allowed_reimbursement_categories
            )
            is False
        )

    @pytest.mark.parametrize(
        argvalues=[(0, True), (9, False)],
        argnames="id_offset, exp",
        ids=[
            "1. Org exists and has a linked wallet",
            "2. Org does not exist",
        ],
    )
    def test_org_id_has_linked_wallet(self, id_offset, exp):
        id_ = self.org_settings.id + id_offset
        assert (
            ReimbursementOrganizationSettingsView.reimbursement_organization_setting_has_linked_wallet(
                str(id_)
            )
            == exp
        )

    def test_org_id_has_linked_wallet_org_has_no_wallet(self):
        ros = ReimbursementOrganizationSettingsFactory.create(organization_id=9000)
        assert not ReimbursementOrganizationSettingsView.reimbursement_organization_setting_has_linked_wallet(
            str(ros.id)
        )

    @pytest.mark.parametrize(
        argvalues=[0, None, "", "NOT_AN_INTEGER", "100.1"],
        argnames="id_",
    )
    def test_org_id_has_linked_wallet_invalid_input(self, id_):
        assert not ReimbursementOrganizationSettingsView.reimbursement_organization_setting_has_linked_wallet(
            str(id_)
        )
