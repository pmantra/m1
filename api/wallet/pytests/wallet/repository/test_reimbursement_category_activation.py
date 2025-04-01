import datetime

import pytest
import sqlalchemy

from wallet.models.constants import (
    BenefitTypes,
    CategoryRuleAccessLevel,
    CategoryRuleAccessSource,
    WalletState,
)
from wallet.models.reimbursement import ReimbursementRequestCategory
from wallet.models.reimbursement_organization_settings import (
    ReimbursementOrgSettingCategoryAssociation,
)
from wallet.models.reimbursement_wallet import (
    ReimbursementWalletCategoryRuleEvaluationFailure,
)
from wallet.pytests.factories import (
    ReimbursementOrgSettingCategoryAssociationFactory,
    ReimbursementOrgSettingsAllowedCategoryRuleFactory,
    ReimbursementRequestCategoryFactory,
    ReimbursementWalletCategoryRuleEvaluationFailureFactory,
    ReimbursementWalletCategoryRuleEvaluationResultFactory,
)
from wallet.repository.reimbursement_category_activation import (
    CategoryActivationRepository,
)
from wallet.services.reimbursement_category_activation_constants import SYSTEM_USER


@pytest.fixture
def category_repo(
    session, category_associations_with_rules_and_settings
) -> CategoryActivationRepository:
    return CategoryActivationRepository(session=session)


class TestCategoryActivationService:
    def test_get_all_allowed_categories_with_rules(self, category_repo):
        categories_with_rules = (
            category_repo.get_all_allowed_category_ids_that_have_rules()
        )
        assert len(categories_with_rules) == 1

    def test_get_all_allowed_categories_without_rules(self, category_repo):
        categories_without_rules = (
            category_repo.get_all_allowed_category_ids_without_rules()
        )
        assert len(categories_without_rules) == 1

    def test_get_all_reimbursement_org_allowed_categories(
        self, category_repo, qualified_wallet
    ):
        categories = category_repo.get_all_allowed_categories_from_org_settings(
            reimbursement_org_settings_id=qualified_wallet.reimbursement_organization_settings.id
        )
        assert len(categories) == 2

    def test_get_all_reimbursement_org_allowed_categories_none(
        self, category_repo, qualified_wallet
    ):
        org_settings_id = None
        allowed_categories = category_repo.get_all_allowed_categories_from_org_settings(
            reimbursement_org_settings_id=org_settings_id
        )
        assert allowed_categories == []

    def test_get_all_category_rules_from_allowed_category(
        self, category_repo, category_associations_with_rules_and_settings
    ):
        allowed_category = category_associations_with_rules_and_settings
        rules = category_repo.get_all_category_rules_from_allowed_category(
            allowed_category_id=allowed_category.id
        )
        assert len(rules) == 1

    def test_get_all_category_rules_from_allowed_category_none(self, category_repo):
        rules = category_repo.get_all_category_rules_from_allowed_category(
            allowed_category_id=99
        )
        assert len(rules) == 0

    def test_get_all_category_settings_from_allowed_categories_and_wallet(
        self, category_repo, qualified_wallet
    ):
        category_ids = [
            allowed_category.id
            for allowed_category in qualified_wallet.reimbursement_organization_settings.allowed_reimbursement_categories
        ]
        settings = (
            category_repo.get_all_category_settings_from_allowed_categories_and_wallet(
                allowed_category_ids=category_ids, wallet_id=qualified_wallet.id
            )
        )
        assert len(settings) == 2

    def test_get_all_category_settings_from_allowed_categories_and_wallet_none(
        self, category_repo, qualified_wallet
    ):
        category_ids = []
        settings = (
            category_repo.get_all_category_settings_from_allowed_categories_and_wallet(
                allowed_category_ids=category_ids, wallet_id=qualified_wallet.id
            )
        )
        assert len(settings) == 0

    def test_get_category_setting_from_allowed_category_and_wallet(
        self,
        category_repo,
        category_associations_with_rules_and_settings,
        qualified_wallet,
    ):
        category = category_associations_with_rules_and_settings
        wallet_id = qualified_wallet.id
        setting = category_repo.get_category_setting_from_allowed_category_and_wallet(
            allowed_category_id=category.id, wallet_id=wallet_id
        )
        assert setting is not None

    def test_get_category_setting_from_allowed_category_and_wallet_none(
        self,
        category_repo,
        category_associations_with_rules_and_settings,
    ):
        category = category_associations_with_rules_and_settings
        wallet_id = 99
        setting = category_repo.get_category_setting_from_allowed_category_and_wallet(
            allowed_category_id=category.id, wallet_id=wallet_id
        )
        assert setting is None

    def test_get_all_category_settings(self, category_repo):
        settings = category_repo.get_all_category_settings()
        assert len(settings) >= 2

    def test_get_all_category_settings_from_wallet(
        self, category_repo, qualified_wallet
    ):
        settings = category_repo.get_all_category_settings_from_wallet(
            wallet_id=qualified_wallet.id
        )
        assert len(settings) == 2

    def test_get_all_category_settings_from_wallet_none(self, category_repo):
        wallet_id = 99
        settings = category_repo.get_all_category_settings_from_wallet(
            wallet_id=wallet_id
        )
        assert len(settings) == 0

    def test_get_category_rule_evaluation_result(
        self,
        category_repo,
        category_association_with_rule,
        qualified_wallet,
    ):
        allowed_category, rule = category_association_with_rule
        ReimbursementWalletCategoryRuleEvaluationResultFactory(
            reimbursement_organization_settings_allowed_category_id=allowed_category.id,
            reimbursement_wallet_id=qualified_wallet.id,
            evaluation_result=True,
        )

        rule = category_repo.get_category_rule_evaluation_result(
            allowed_category_id=allowed_category.id, wallet_id=qualified_wallet.id
        )
        assert rule is not None
        assert rule.reimbursement_wallet_id == qualified_wallet.id
        assert (
            rule.reimbursement_organization_settings_allowed_category_id
            == allowed_category.id
        )

    def test_get_category_rule_evaluation_result_None(
        self,
        category_repo,
        category_associations_with_rules_and_settings,
        qualified_wallet,
    ):
        allowed_category = category_associations_with_rules_and_settings

        rule = category_repo.get_category_rule_evaluation_result(
            allowed_category_id=allowed_category.id, wallet_id=qualified_wallet.id
        )
        assert rule is None

    def test_create_rule_evaluation(
        self,
        category_repo,
        category_associations_with_rules_and_settings,
        qualified_wallet,
    ):
        allowed_category = category_associations_with_rules_and_settings

        created_rule = category_repo.create_rule_evaluation(
            allowed_category_id=allowed_category.id,
            wallet_id=qualified_wallet.id,
            result=False,
        )
        result = category_repo.get_category_rule_evaluation_result(
            allowed_category_id=allowed_category.id, wallet_id=qualified_wallet.id
        )
        assert result == created_rule
        assert result.evaluation_result is False

    def test_update_rule_evaluation(
        self,
        category_repo,
        category_associations_with_rules_and_settings,
        qualified_wallet,
    ):
        allowed_category = category_associations_with_rules_and_settings
        mock_rule = ReimbursementWalletCategoryRuleEvaluationResultFactory(
            reimbursement_organization_settings_allowed_category_id=allowed_category.id,
            reimbursement_wallet_id=qualified_wallet.id,
            evaluation_result=True,
        )

        result = category_repo.update_rule_evaluation(
            evaluated_rule=mock_rule, result=False
        )
        assert result.id == mock_rule.id
        assert result.evaluation_result is False

    def test_upsert_rule_evaluation_no_conflict(
        self,
        category_repo,
        category_associations_with_rules_and_settings,
        qualified_wallet,
    ):
        # Given
        allowed_category = category_associations_with_rules_and_settings

        # When
        category_repo.upsert_rule_evaluation(
            allowed_category_id=allowed_category.id,
            wallet_id=qualified_wallet.id,
            result=True,
        )

        inserted_result = category_repo.get_category_rule_evaluation_result(
            allowed_category_id=allowed_category.id, wallet_id=qualified_wallet.id
        )

        # Then
        assert inserted_result.evaluation_result is True
        assert inserted_result.reimbursement_wallet_id == qualified_wallet.id
        assert (
            inserted_result.reimbursement_organization_settings_allowed_category_id
            == allowed_category.id
        )

    def test_upsert_rule_evaluation_on_conflict(
        self,
        category_repo,
        category_associations_with_rules_and_settings,
        qualified_wallet,
        session,
    ):
        allowed_category = category_associations_with_rules_and_settings

        existing_result = ReimbursementWalletCategoryRuleEvaluationResultFactory(
            reimbursement_organization_settings_allowed_category_id=allowed_category.id,
            reimbursement_wallet_id=qualified_wallet.id,
            evaluation_result=True,
        )

        category_repo.upsert_rule_evaluation(
            allowed_category_id=allowed_category.id,
            wallet_id=qualified_wallet.id,
            result=False,
        )

        updated = category_repo.get_category_rule_evaluation_result(
            allowed_category_id=allowed_category.id, wallet_id=qualified_wallet.id
        )

        session.refresh(updated)

        assert updated.id == existing_result.id
        assert updated.evaluation_result is False

    def test_create_allowed_category_setting(
        self, category_repo, qualified_wallet, valid_alegeus_plan_hra
    ):
        org_settings = qualified_wallet.reimbursement_organization_settings
        category: ReimbursementRequestCategory = (
            ReimbursementRequestCategoryFactory.create(
                label="Test", reimbursement_plan=valid_alegeus_plan_hra
            )
        )
        allowed_category: ReimbursementOrgSettingCategoryAssociation = (
            ReimbursementOrgSettingCategoryAssociationFactory.create(
                reimbursement_organization_settings=org_settings,
                reimbursement_request_category=category,
                benefit_type=BenefitTypes.CURRENCY,
            )
        )
        access_level = CategoryRuleAccessLevel.FULL_ACCESS
        access_level_source = CategoryRuleAccessSource.RULES

        result = category_repo.create_allowed_category_setting(
            allowed_category_id=allowed_category.id,
            wallet_id=qualified_wallet.id,
            access_level=access_level,
            access_level_source=access_level_source,
        )
        assert result

    def test_upsert_allowed_category_setting_no_conflict(
        self, category_repo, qualified_wallet, valid_alegeus_plan_hra
    ):
        # Given
        org_settings = qualified_wallet.reimbursement_organization_settings
        category: ReimbursementRequestCategory = (
            ReimbursementRequestCategoryFactory.create(
                label="Test", reimbursement_plan=valid_alegeus_plan_hra
            )
        )
        allowed_category: ReimbursementOrgSettingCategoryAssociation = (
            ReimbursementOrgSettingCategoryAssociationFactory.create(
                reimbursement_organization_settings=org_settings,
                reimbursement_request_category=category,
                benefit_type=BenefitTypes.CURRENCY,
            )
        )
        access_level = CategoryRuleAccessLevel.FULL_ACCESS
        access_level_source = CategoryRuleAccessSource.RULES

        # When
        category_repo.upsert_allowed_category_setting(
            allowed_category_id=allowed_category.id,
            wallet_id=qualified_wallet.id,
            access_level=access_level,
            access_level_source=access_level_source,
        )

        # Then
        settings = category_repo.get_category_setting_from_allowed_category_and_wallet(
            allowed_category_id=allowed_category.id, wallet_id=qualified_wallet.id
        )
        assert (
            settings.reimbursement_organization_settings_allowed_category_id
            == allowed_category.id
        )
        assert settings.reimbursement_wallet_id == qualified_wallet.id
        assert settings.access_level == access_level
        assert settings.access_level_source == access_level_source
        assert settings.updated_by == SYSTEM_USER

    def test_upsert_allowed_category_setting_on_conflict(
        self,
        category_repo,
        category_association_with_setting,
        qualified_wallet,
        session,
    ):
        # Given
        allowed_category, settings = category_association_with_setting

        assert settings.access_level == CategoryRuleAccessLevel.FULL_ACCESS
        assert settings.access_level_source == CategoryRuleAccessSource.NO_RULES

        # When
        category_repo.upsert_allowed_category_setting(
            allowed_category_id=allowed_category.id,
            wallet_id=qualified_wallet.id,
            access_level=CategoryRuleAccessLevel.NO_ACCESS,
            access_level_source=CategoryRuleAccessSource.RULES,
            updated_by="someone else",
        )

        # Then
        settings = category_repo.get_category_setting_from_allowed_category_and_wallet(
            allowed_category_id=allowed_category.id, wallet_id=qualified_wallet.id
        )

        # reload the object with the upserted values
        session.refresh(settings)

        assert (
            settings.reimbursement_organization_settings_allowed_category_id
            == allowed_category.id
        )
        assert settings.reimbursement_wallet_id == qualified_wallet.id
        assert settings.access_level == CategoryRuleAccessLevel.NO_ACCESS
        assert settings.access_level_source == CategoryRuleAccessSource.RULES
        assert settings.updated_by == "someone else"

    @pytest.mark.parametrize(
        argnames="new_access_level",
        argvalues=[
            CategoryRuleAccessLevel.FULL_ACCESS,
            CategoryRuleAccessLevel.NO_ACCESS,
        ],
    )
    def test_create_allowed_category_setting_duelling(
        self, category_repo, qualified_wallet, valid_alegeus_plan_hra, new_access_level
    ):
        org_settings = qualified_wallet.reimbursement_organization_settings
        category: ReimbursementRequestCategory = (
            ReimbursementRequestCategoryFactory.create(
                label="Test", reimbursement_plan=valid_alegeus_plan_hra
            )
        )
        allowed_category: ReimbursementOrgSettingCategoryAssociation = (
            ReimbursementOrgSettingCategoryAssociationFactory.create(
                reimbursement_organization_settings=org_settings,
                reimbursement_request_category=category,
                benefit_type=BenefitTypes.CURRENCY,
            )
        )
        access_level = CategoryRuleAccessLevel.FULL_ACCESS
        access_level_source = CategoryRuleAccessSource.RULES

        _ = category_repo.create_allowed_category_setting(
            allowed_category_id=allowed_category.id,
            wallet_id=qualified_wallet.id,
            access_level=access_level,
            access_level_source=access_level_source,
        )
        result = category_repo.create_allowed_category_setting(
            allowed_category_id=allowed_category.id,
            wallet_id=qualified_wallet.id,
            access_level=new_access_level,
            access_level_source=access_level_source,
        )
        assert result
        assert result.access_level == new_access_level

    def test_update_allowed_category_setting(
        self,
        category_repo,
        category_associations_with_rules_and_settings,
        qualified_wallet,
    ):
        allowed_category = category_associations_with_rules_and_settings
        access_level = CategoryRuleAccessLevel.NO_ACCESS
        access_level_source = CategoryRuleAccessSource.NO_RULES
        setting = category_repo.get_category_setting_from_allowed_category_and_wallet(
            allowed_category_id=allowed_category.id, wallet_id=qualified_wallet.id
        )

        result = category_repo.update_allowed_category_setting(
            category_setting=setting,
            access_level=access_level,
            access_level_source=access_level_source,
        )
        assert result == setting
        assert result.access_level == CategoryRuleAccessLevel.NO_ACCESS

    def test_get_wallet_allowed_categories_and_category_settings(
        self, category_repo, qualified_wallet
    ):
        results = category_repo.get_wallet_allowed_categories_and_access_level(
            wallet_id=qualified_wallet.id,
            org_settings_id=qualified_wallet.reimbursement_organization_settings.id,
        )
        assert len(results) == 2
        assert (
            results[0]["wallet_access_level"]
            == CategoryRuleAccessLevel.FULL_ACCESS.value
        )

    def test_get_all_category_rules_for_categories(
        self,
        category_repo,
        qualified_wallet,
        category_associations_with_rules_and_settings,
    ):
        category = category_associations_with_rules_and_settings
        allowed_category_ids = [
            cat.id
            for cat in qualified_wallet.reimbursement_organization_settings.allowed_reimbursement_categories
        ]
        mapped_rules = category_repo.get_all_category_rules_for_allowed_categories(
            allowed_category_ids
        )
        assert isinstance(mapped_rules, dict)
        assert isinstance(mapped_rules[category.id], list)
        assert len(mapped_rules) == 1
        assert len(mapped_rules[category.id]) == 1

    def test_get_all_wallets_from_allowed_categories(
        self, category_repo, qualified_wallet, pending_alegeus_wallet_hra
    ):
        qualified_category_ids = [
            cat.id
            for cat in qualified_wallet.reimbursement_organization_settings.allowed_reimbursement_categories
        ]
        pending_category_ids = [
            cat.id
            for cat in pending_alegeus_wallet_hra.reimbursement_organization_settings.allowed_reimbursement_categories
        ]

        mapped_wallets = category_repo.get_all_wallets_from_allowed_categories(
            qualified_category_ids + pending_category_ids
        )
        assert isinstance(mapped_wallets, dict)
        assert len(mapped_wallets) == 2
        assert isinstance(mapped_wallets[qualified_category_ids[0]], list)
        for _, wallets in mapped_wallets.items():
            assert wallets[0].state == WalletState.QUALIFIED

    def test_get_mapped_allowed_settings(
        self,
        category_repo,
        qualified_wallet,
        category_association_with_setting,
    ):
        category, setting = category_association_with_setting
        mapped_settings = category_repo.get_mapped_allowed_settings()
        mapped_result = mapped_settings[category.id][qualified_wallet.id]
        assert mapped_result.id == setting.id

    def test_get_mapped_allowed_settings_empty(self, session):
        category_repo = CategoryActivationRepository(session)
        mapped_settings = category_repo.get_mapped_allowed_settings()
        assert mapped_settings == {}


class TestGetActiveRule:
    def test_get_active_tenure_rule_for_allowed_category_no_rule(
        self, category_repo, qualified_wallet
    ):
        category = qualified_wallet.reimbursement_organization_settings.allowed_reimbursement_categories[
            0
        ]
        rule = category_repo.get_active_tenure_rule_for_allowed_category(
            allowed_category_id=category.id
        )
        assert rule is None

    @pytest.mark.parametrize(
        "invalid_start_date",
        [None, datetime.date.today() + datetime.timedelta(days=10)],
    )
    def test_get_active_tenure_rule_for_allowed_category_inactive_rule(
        self, category_repo, qualified_wallet, invalid_start_date
    ):
        category = qualified_wallet.reimbursement_organization_settings.allowed_reimbursement_categories[
            0
        ]
        ReimbursementOrgSettingsAllowedCategoryRuleFactory.create(
            reimbursement_organization_settings_allowed_category_id=category.id,
            rule_name="TENURE_ONE_CALENDAR_YEAR",
            started_at=invalid_start_date,
        )
        rule = category_repo.get_active_tenure_rule_for_allowed_category(
            allowed_category_id=category.id
        )
        assert rule is None

    def test_get_active_tenure_rule_for_allowed_category(
        self, category_repo, qualified_wallet
    ):
        category = qualified_wallet.reimbursement_organization_settings.allowed_reimbursement_categories[
            0
        ]
        expected_rule = ReimbursementOrgSettingsAllowedCategoryRuleFactory.create(
            reimbursement_organization_settings_allowed_category_id=category.id,
            rule_name="TENURE_ONE_CALENDAR_YEAR",
            started_at=datetime.date.today() - datetime.timedelta(days=365),
        )
        ReimbursementOrgSettingsAllowedCategoryRuleFactory.create(
            reimbursement_organization_settings_allowed_category_id=category.id,
            rule_name="NON_TENURE_RULE",
            started_at=datetime.date.today() - datetime.timedelta(days=365),
        )
        rule = category_repo.get_active_tenure_rule_for_allowed_category(
            allowed_category_id=category.id
        )
        assert rule == expected_rule


class TestDeleteEvaluationFailures:
    def test_delete_evaluation_failures_success(
        self, category_repo, category_association_with_rule, qualified_wallet, session
    ):
        """Test successful deletion of evaluation failures"""
        # Given
        allowed_category, rule = category_association_with_rule

        result = ReimbursementWalletCategoryRuleEvaluationResultFactory(
            reimbursement_organization_settings_allowed_category_id=allowed_category.id,
            reimbursement_wallet_id=qualified_wallet.id,
            evaluation_result=False,
        )

        ReimbursementWalletCategoryRuleEvaluationFailureFactory.create(
            evaluation_result_id=result.id, rule_name="RULE_ONE"
        )
        ReimbursementWalletCategoryRuleEvaluationFailureFactory.create(
            evaluation_result_id=result.id, rule_name="RULE_TWO"
        )

        # Check that failure are in DB
        assert (
            session.query(ReimbursementWalletCategoryRuleEvaluationFailure)
            .filter(
                ReimbursementWalletCategoryRuleEvaluationFailure.evaluation_result_id
                == result.id
            )
            .all()
        )

        # When
        deleted = category_repo.delete_evaluation_failures(result_id=result.id)

        # Then
        assert deleted == 2

    def test_delete_evaluation_failures_none_deleted(
        self, category_repo, category_association_with_rule, qualified_wallet, session
    ):
        """Test deletion of evaluation failures - but nothing was deleted"""
        # Given
        allowed_category, rule = category_association_with_rule

        result = ReimbursementWalletCategoryRuleEvaluationResultFactory(
            reimbursement_organization_settings_allowed_category_id=allowed_category.id,
            reimbursement_wallet_id=qualified_wallet.id,
            evaluation_result=False,
        )

        # When
        deleted = category_repo.delete_evaluation_failures(result_id=result.id)

        # Then
        assert deleted == 0


class TestCreateEvaluationFailures:
    def test_create_evaluation_failures_success(
        self, category_repo, category_association_with_rule, qualified_wallet, session
    ):
        """Test successful creation of evaluation failures"""
        # Given
        allowed_category, rule = category_association_with_rule

        result = ReimbursementWalletCategoryRuleEvaluationResultFactory(
            reimbursement_organization_settings_allowed_category_id=allowed_category.id,
            reimbursement_wallet_id=qualified_wallet.id,
            evaluation_result=False,
        )

        failed_rules = ["RULE_ONE", "RULE_TWO"]

        # When
        added_failures = category_repo.create_evaluation_failures(
            result_id=result.id, failed_rules=failed_rules
        )

        # Then
        failures = (
            session.query(ReimbursementWalletCategoryRuleEvaluationFailure)
            .filter(
                ReimbursementWalletCategoryRuleEvaluationFailure.evaluation_result_id
                == result.id
            )
            .all()
        )

        assert failures == added_failures
        assert len(failures) == 2
        assert set(rule.rule_name for rule in failures) == set(failed_rules)

    def test_create_evaluation_failures_unique_key_violation(
        self, category_repo, category_association_with_rule, qualified_wallet, session
    ):
        """Test creation of evaluation failures that result in unique key violation"""
        # Given
        allowed_category, rule = category_association_with_rule

        result = ReimbursementWalletCategoryRuleEvaluationResultFactory(
            reimbursement_organization_settings_allowed_category_id=allowed_category.id,
            reimbursement_wallet_id=qualified_wallet.id,
            evaluation_result=False,
        )

        failed_rules = ["RULE_ONE", "RULE_ONE"]

        # When - Then
        with pytest.raises(sqlalchemy.exc.IntegrityError):
            _ = category_repo.create_evaluation_failures(
                result_id=result.id, failed_rules=failed_rules
            )
            session.commit()


class TestGetEvaluationFailures:
    def test_get_evaluation_failures_success(
        self, category_repo, category_association_with_rule, qualified_wallet, session
    ):
        """Test successful fetch of evaluation failures"""
        # Given
        allowed_category, rule = category_association_with_rule

        result = ReimbursementWalletCategoryRuleEvaluationResultFactory(
            reimbursement_organization_settings_allowed_category_id=allowed_category.id,
            reimbursement_wallet_id=qualified_wallet.id,
            evaluation_result=False,
        )
        expected_failure = (
            ReimbursementWalletCategoryRuleEvaluationFailureFactory.create(
                evaluation_result_id=result.id, rule_name="RULE_ONE"
            )
        )

        # When
        failures = category_repo.get_evaluation_failures(
            wallet_id=qualified_wallet.id,
            category_id=allowed_category.reimbursement_request_category_id,
        )

        # Then
        assert len(failures) == 1
        assert failures[0] == expected_failure

    def test_get_evaluation_failures_not_found(
        self, category_repo, category_association_with_rule, qualified_wallet, session
    ):
        """Test fetch of evaluation failures but nothing found"""
        # Given
        allowed_category, rule = category_association_with_rule

        result = ReimbursementWalletCategoryRuleEvaluationResultFactory(
            reimbursement_organization_settings_allowed_category_id=allowed_category.id,
            reimbursement_wallet_id=qualified_wallet.id,
            evaluation_result=False,
        )
        _ = ReimbursementWalletCategoryRuleEvaluationFailureFactory.create(
            evaluation_result_id=result.id, rule_name="RULE_ONE"
        )

        # When
        failures = category_repo.get_evaluation_failures(
            wallet_id=qualified_wallet.id + 1,
            category_id=allowed_category.reimbursement_request_category_id,
        )

        # Then
        assert not failures
