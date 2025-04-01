from __future__ import annotations

from datetime import date, datetime, timedelta
from unittest import mock
from unittest.mock import MagicMock

import factory
import pytest

from wallet.models.constants import (
    CategoryRuleAccessLevel,
    CategoryRuleAccessSource,
    WalletState,
)
from wallet.models.reimbursement_organization_settings import (
    ReimbursementOrgSettingsAllowedCategoryRule,
)
from wallet.models.reimbursement_wallet import (
    ReimbursementWalletCategoryRuleEvaluationFailure,
)
from wallet.pytests.factories import (
    ReimbursementOrgSettingsAllowedCategoryRuleFactory,
    ReimbursementPlanFactory,
    ReimbursementWalletAllowedCategorySettingsFactory,
    ReimbursementWalletCategoryRuleEvaluationFailureFactory,
    ReimbursementWalletCategoryRuleEvaluationResultFactory,
    ReimbursementWalletFactory,
)
from wallet.services.reimbursement_category_activation_rules import (
    ActionableCategoryActivationException,
    AmazonProgenyTOCRule,
    LowesProgenyTOCRule,
    Tenure30DaysCategoryRule,
    Tenure90DaysCategoryRule,
    Tenure180DaysCategoryRule,
    TenureOneCalendarYearCategoryRule,
)


@pytest.fixture()
def mock_category_rules_service():
    with mock.patch(
        "wallet.services.reimbursement_category_activation_rules.TenureOneCalendarYearCategoryRule",
        spec_set=True,
        autospec=True,
    ) as m:
        yield m.return_value


class TestGetCategoryRule:
    @pytest.mark.parametrize(
        argnames="rule_name, rule_class_instance",
        argvalues=[
            ("TENURE_ONE_CALENDAR_YEAR", TenureOneCalendarYearCategoryRule),
            ("TENURE_30_DAYS", Tenure30DaysCategoryRule),
            ("TENURE_90_DAYS", Tenure90DaysCategoryRule),
            ("TENURE_180_DAYS", Tenure180DaysCategoryRule),
            ("AMAZON_PROGENY_TOC_PERIOD", AmazonProgenyTOCRule),
            ("LOWES_PROGENY_TOC_PERIOD", LowesProgenyTOCRule),
        ],
    )
    def test_get_category_rule_existing_rule(
        self, category_service, rule_name, rule_class_instance
    ):
        # Given/When
        rule_class = category_service.get_category_rule(rule_name)
        # Then
        assert isinstance(rule_class, rule_class_instance)

    def test_get_category_rule_non_existing_rule(self, category_service):
        # Given
        rule_name = "non_existing_rule"
        # When/Then
        with pytest.raises(ActionableCategoryActivationException):
            category_service.get_category_rule(rule_name)


class TestExecuteCategoryRule:
    def test_execute_category_rule_success(
        self,
        category_service,
        qualified_alegeus_wallet_hra,
        qualified_wallet_eligibility_verification,
        mock_enterprise_verification_service,
    ):
        # Given
        association = qualified_alegeus_wallet_hra.reimbursement_organization_settings.allowed_reimbursement_categories[
            0
        ]
        rule_class = TenureOneCalendarYearCategoryRule()
        qualified_wallet_eligibility_verification.record["employee_start_date"] = str(
            datetime.utcnow().date()
        )
        mock_enterprise_verification_service.get_verification_for_user_and_org.return_value = (
            qualified_wallet_eligibility_verification
        )
        # When
        result = category_service.execute_category_rule(
            qualified_alegeus_wallet_hra, rule_class, association
        )
        # Then
        assert result is False

    def test_execute_category_rule_not_implemented(
        self,
        category_service,
        qualified_alegeus_wallet_hra,
        mock_category_rules_service,
    ):
        # Given
        association = qualified_alegeus_wallet_hra.reimbursement_organization_settings.allowed_reimbursement_categories[
            0
        ]
        rule_class = mock_category_rules_service
        mock_category_rules_service.execute.side_effect = NotImplementedError
        # When/Then
        with pytest.raises(ActionableCategoryActivationException):
            category_service.execute_category_rule(
                qualified_alegeus_wallet_hra, rule_class, association
            )


class TestGetWalletAllowedCategories:
    def test_get_wallet_allowed_categories(
        self,
        category_service,
        qualified_wallet,
        category_association_with_setting,
        qualified_wallet_eligibility_verification,
        mock_enterprise_verification_service,
    ):
        # Given
        qualified_wallet_eligibility_verification.record["employee_start_date"] = str(
            datetime.utcnow().date()
        )
        mock_enterprise_verification_service.get_verification_for_user.return_value = (
            qualified_wallet_eligibility_verification
        )
        # When
        with mock.patch(
            "wallet.tasks.alegeus.enroll_member_account.delay"
        ) as mock_task_configure_account:
            results = category_service.get_wallet_allowed_categories(qualified_wallet)
            # Then
            settings = (
                category_service.rules_repo.get_all_category_settings_from_wallet(
                    wallet_id=qualified_wallet.id
                )
            )
            assert len(results) == 2
            assert len(settings) == 2
            assert settings[0].access_level == CategoryRuleAccessLevel.FULL_ACCESS
            assert settings[1].access_level == CategoryRuleAccessLevel.FULL_ACCESS
            assert mock_task_configure_account.call_count == 1

    def test_get_wallet_allowed_categories_pending_wallet(
        self, category_service, enterprise_user
    ):
        # Given
        wallet = ReimbursementWalletFactory.create(
            member=enterprise_user, state=WalletState.PENDING
        )
        org_settings = wallet.reimbursement_organization_settings
        allowed_category_ids = [
            cat.id for cat in org_settings.allowed_reimbursement_categories
        ]
        # When
        with mock.patch(
            "wallet.tasks.alegeus.enroll_member_account.delay"
        ) as mock_task_configure_account:
            results = category_service.get_wallet_allowed_categories(wallet)
            # Then
            assert len(results) == 1
            setting = category_service.rules_repo.get_category_setting_from_allowed_category_and_wallet(
                wallet_id=wallet.id,
                allowed_category_id=allowed_category_ids[0],
            )
            assert setting.access_level == CategoryRuleAccessLevel.FULL_ACCESS
            assert setting.access_level_source == CategoryRuleAccessSource.NO_RULES
            mock_task_configure_account.assert_not_called()

    def test_get_wallet_allowed_categories_missing_settings_no_rule(
        self, category_service, qualified_wallet
    ):
        # Given
        org_settings = qualified_wallet.reimbursement_organization_settings
        allowed_category_ids = [
            cat.id for cat in org_settings.allowed_reimbursement_categories
        ]
        # When
        with mock.patch(
            "wallet.tasks.alegeus.enroll_member_account.delay"
        ) as mock_task_configure_account:
            results = category_service.get_wallet_allowed_categories(qualified_wallet)
            # Then
            assert len(results) == 1
            setting = category_service.rules_repo.get_category_setting_from_allowed_category_and_wallet(
                wallet_id=qualified_wallet.id,
                allowed_category_id=allowed_category_ids[0],
            )
            assert setting.access_level == CategoryRuleAccessLevel.FULL_ACCESS
            assert setting.access_level_source == CategoryRuleAccessSource.NO_RULES
            assert mock_task_configure_account.called
            assert mock_task_configure_account.call_count == len(allowed_category_ids)

    def test_get_wallet_allowed_categories_missing_settings_exception(
        self, category_service, qualified_wallet
    ):
        # Given
        with mock.patch(
            "wallet.repository.reimbursement_category_activation.CategoryActivationRepository"
            ".upsert_allowed_category_setting"
        ) as mock_create:
            mock_create.side_effect = [Exception]
            # When
            results = category_service.get_wallet_allowed_categories(qualified_wallet)
            # Then
            assert len(results) == 0


class TestProcessWalletCategoryRule:
    def test_process_wallet_category_rule_with_rule(
        self,
        category_service,
        category_association_with_rule,
        qualified_wallet,
        qualified_wallet_eligibility_verification,
        mock_enterprise_verification_service,
    ):
        # Given
        qualified_wallet_eligibility_verification.record["employee_start_date"] = str(
            datetime.utcnow().date()
        )
        mock_enterprise_verification_service.get_verification_for_user.return_value = (
            qualified_wallet_eligibility_verification
        )
        allowed_category, rule = category_association_with_rule

        # When
        with mock.patch(
            "wallet.utils.alegeus.enrollments.enroll_wallet.configure_account"
        ) as mock_configure_account:
            mock_configure_account.return_value = True, []
            setting = category_service.process_wallet_category_rule(
                allowed_category.id, qualified_wallet
            )
            # Then
            assert setting.access_level == CategoryRuleAccessLevel.NO_ACCESS
            assert setting.access_level_source == CategoryRuleAccessSource.RULES

    def test_process_wallet_category_rule_no_rule(
        self,
        category_service,
        qualified_wallet,
        qualified_wallet_eligibility_verification,
        mock_enterprise_verification_service,
    ):
        # Given
        allowed_category = qualified_wallet.reimbursement_organization_settings.allowed_reimbursement_categories[
            0
        ]
        qualified_wallet_eligibility_verification.record["employee_start_date"] = str(
            datetime.utcnow().date()
        )
        mock_enterprise_verification_service.get_verification_for_user.return_value = (
            qualified_wallet_eligibility_verification
        )
        # When
        with mock.patch(
            "wallet.utils.alegeus.enrollments.enroll_wallet.configure_account"
        ) as mock_configure_account:
            mock_configure_account.return_value = True, []
            setting = category_service.process_wallet_category_rule(
                allowed_category.id, qualified_wallet
            )
            # Then
            assert setting.access_level == CategoryRuleAccessLevel.FULL_ACCESS
            assert setting.access_level_source == CategoryRuleAccessSource.NO_RULES


class TestEvaluateProcessWalletCategoryRule:
    @pytest.mark.parametrize(argnames="persist_failures", argvalues=[True, False])
    def test_evaluate_and_process_rules_no_failures(
        self,
        session,
        category_service,
        category_association_with_rule,
        qualified_wallet,
        active_wallet_user,
        qualified_wallet_eligibility_verification,
        mock_enterprise_verification_service,
        ff_test_data,
        persist_failures: bool,
    ):
        # Given
        ff_test_data.update(
            ff_test_data.flag("release-persist-rule-failures").variations(
                persist_failures
            )
        )
        date = datetime.utcnow().date() - timedelta(days=366)
        qualified_wallet_eligibility_verification.record["employee_start_date"] = str(
            date
        )
        mock_enterprise_verification_service.get_verification_for_user_and_org.return_value = (
            qualified_wallet_eligibility_verification
        )
        allowed_category, rule = category_association_with_rule
        # When
        evaluated_result = category_service.evaluate_and_process_rules(
            category_id=allowed_category.id,
            wallet=qualified_wallet,
            all_category_rules=[rule],
        )
        evaluated_rule = (
            category_service.rules_repo.get_category_rule_evaluation_result(
                allowed_category_id=allowed_category.id, wallet_id=qualified_wallet.id
            )
        )
        # Then
        assert evaluated_result is True
        assert (
            evaluated_rule.reimbursement_organization_settings_allowed_category_id
            == allowed_category.id
        )
        assert evaluated_rule.reimbursement_wallet_id == qualified_wallet.id
        assert evaluated_rule.evaluation_result is True

        if persist_failures:
            # new behavior
            assert evaluated_rule.executed_category_rule is None
            assert evaluated_rule.failed_category_rule is None
        else:
            # old behavior
            assert evaluated_rule.executed_category_rule == "TENURE_ONE_CALENDAR_YEAR "
            assert evaluated_rule.failed_category_rule is None

    @pytest.mark.parametrize(argnames="persist_failures", argvalues=[True, False])
    def test_evaluate_and_process_rules_with_failures(
        self,
        session,
        category_service,
        category_association_with_rule,
        qualified_wallet,
        active_wallet_user,
        qualified_wallet_eligibility_verification,
        mock_enterprise_verification_service,
        ff_test_data,
        persist_failures: bool,
    ):
        # Given
        ff_test_data.update(
            ff_test_data.flag("release-persist-rule-failures").variations(
                persist_failures
            )
        )
        date = datetime.utcnow().date() - timedelta(days=360)  # Fails tenure rule
        qualified_wallet_eligibility_verification.record["employee_start_date"] = str(
            date
        )
        mock_enterprise_verification_service.get_verification_for_user_and_org.return_value = (
            qualified_wallet_eligibility_verification
        )
        allowed_category, rule = category_association_with_rule
        # When
        evaluated_result = category_service.evaluate_and_process_rules(
            category_id=allowed_category.id,
            wallet=qualified_wallet,
            all_category_rules=[rule],
        )
        evaluated_rule = (
            category_service.rules_repo.get_category_rule_evaluation_result(
                allowed_category_id=allowed_category.id, wallet_id=qualified_wallet.id
            )
        )

        # Then
        assert evaluated_result is False
        assert (
            evaluated_rule.reimbursement_organization_settings_allowed_category_id
            == allowed_category.id
        )
        assert evaluated_rule.reimbursement_wallet_id == qualified_wallet.id
        assert evaluated_rule.evaluation_result is False

        if persist_failures:
            # new behavior
            assert evaluated_rule.executed_category_rule is None
            assert evaluated_rule.failed_category_rule is None

            failed_rules = (
                session.query(ReimbursementWalletCategoryRuleEvaluationFailure)
                .filter(
                    ReimbursementWalletCategoryRuleEvaluationFailure.evaluation_result_id
                    == evaluated_rule.id
                )
                .all()
            )

            assert failed_rules[0].rule_name == "TENURE_ONE_CALENDAR_YEAR"
        else:
            # old behavior
            assert evaluated_rule.executed_category_rule is None
            assert evaluated_rule.failed_category_rule == "TENURE_ONE_CALENDAR_YEAR"

    @pytest.mark.parametrize(argnames="persist_failures", argvalues=[True, False])
    def test_evaluate_and_process_rules_with_failures_then_success(
        self,
        session,
        category_service,
        category_association_with_rule,
        qualified_wallet,
        active_wallet_user,
        qualified_wallet_eligibility_verification,
        mock_enterprise_verification_service,
        ff_test_data,
        persist_failures: bool,
    ):
        ff_test_data.update(
            ff_test_data.flag("release-persist-rule-failures").variations(
                persist_failures
            )
        )
        allowed_category, rule = category_association_with_rule

        # Given that the member initially fails the tenure rule
        date = datetime.utcnow().date() - timedelta(days=360)  # Fails tenure rule
        qualified_wallet_eligibility_verification.record["employee_start_date"] = str(
            date
        )
        mock_enterprise_verification_service.get_verification_for_user_and_org.return_value = (
            qualified_wallet_eligibility_verification
        )

        evaluated_result = category_service.evaluate_and_process_rules(
            category_id=allowed_category.id,
            wallet=qualified_wallet,
            all_category_rules=[rule],
        )
        evaluated_rule = (
            category_service.rules_repo.get_category_rule_evaluation_result(
                allowed_category_id=allowed_category.id, wallet_id=qualified_wallet.id
            )
        )

        assert evaluated_result is False
        assert (
            evaluated_rule.reimbursement_organization_settings_allowed_category_id
            == allowed_category.id
        )
        assert evaluated_rule.reimbursement_wallet_id == qualified_wallet.id
        assert evaluated_rule.evaluation_result is False

        if persist_failures:
            # new behavior
            assert evaluated_rule.executed_category_rule is None
            assert evaluated_rule.failed_category_rule is None

            failed_rules = (
                session.query(ReimbursementWalletCategoryRuleEvaluationFailure)
                .filter(
                    ReimbursementWalletCategoryRuleEvaluationFailure.evaluation_result_id
                    == evaluated_rule.id
                )
                .all()
            )

            assert failed_rules[0].rule_name == "TENURE_ONE_CALENDAR_YEAR"
        else:
            # old behavior
            assert evaluated_rule.executed_category_rule is None
            assert evaluated_rule.failed_category_rule == "TENURE_ONE_CALENDAR_YEAR"

        # When they then pass the tenure rule
        date = datetime.utcnow().date() - timedelta(days=366)  # Passes tenure rule
        qualified_wallet_eligibility_verification.record["employee_start_date"] = str(
            date
        )
        latest_evaluated_result = category_service.evaluate_and_process_rules(
            category_id=allowed_category.id,
            wallet=qualified_wallet,
            all_category_rules=[rule],
        )
        latest_evaluated_rule = (
            category_service.rules_repo.get_category_rule_evaluation_result(
                allowed_category_id=allowed_category.id, wallet_id=qualified_wallet.id
            )
        )

        assert latest_evaluated_result is True
        assert (
            evaluated_rule.reimbursement_organization_settings_allowed_category_id
            == allowed_category.id
        )
        assert latest_evaluated_rule.reimbursement_wallet_id == qualified_wallet.id
        assert latest_evaluated_rule.evaluation_result is True

        if persist_failures:
            # new behavior
            assert evaluated_rule.executed_category_rule is None
            assert evaluated_rule.failed_category_rule is None

            failed_rules = (
                session.query(ReimbursementWalletCategoryRuleEvaluationFailure)
                .filter(
                    ReimbursementWalletCategoryRuleEvaluationFailure.evaluation_result_id
                    == evaluated_rule.id
                )
                .all()
            )

            assert not failed_rules
        else:
            # old behavior
            assert evaluated_rule.executed_category_rule == "TENURE_ONE_CALENDAR_YEAR "
            assert evaluated_rule.failed_category_rule is None


class TestSaveRuleEvaluationFailures:
    def test_save_rule_evaluation_failures_success(
        self,
        session,
        category_service,
        category_association_with_rule,
        qualified_wallet,
    ):
        """Test insert of failures when evaluation_result is False"""
        # Given
        allowed_category, rule = category_association_with_rule
        result = ReimbursementWalletCategoryRuleEvaluationResultFactory.create(
            reimbursement_organization_settings_allowed_category_id=allowed_category.id,
            reimbursement_wallet_id=qualified_wallet.id,
            evaluation_result=False,
            executed_category_rule=None,
            failed_category_rule=None,
        )
        failed_rule_strings = ["RULE_ONE", "RULE_TWO"]

        # When
        category_service.save_rule_evaluation_failures(
            saved_rule_evaluation_record=result,
            failed_rules=failed_rule_strings,
        )

        # Then
        failed_rules = session.query(
            ReimbursementWalletCategoryRuleEvaluationFailure
        ).filter(
            ReimbursementWalletCategoryRuleEvaluationFailure.evaluation_result_id
            == result.id
        )

        assert set([rule.rule_name for rule in failed_rules]) == set(
            failed_rule_strings
        )

    def test_save_rule_evaluation_failures_delete_and_insert(
        self,
        session,
        category_service,
        category_association_with_rule,
        qualified_wallet,
    ):
        """Test that delete and inserts work"""
        # Given
        allowed_category, rule = category_association_with_rule
        result = ReimbursementWalletCategoryRuleEvaluationResultFactory.create(
            reimbursement_organization_settings_allowed_category_id=allowed_category.id,
            reimbursement_wallet_id=qualified_wallet.id,
            evaluation_result=False,
            executed_category_rule=None,
            failed_category_rule=None,
        )
        failed_rule_strings = ["RULE_ONE", "RULE_TWO"]
        ReimbursementWalletCategoryRuleEvaluationFailureFactory.create_batch(
            size=len(failed_rule_strings),
            evaluation_result_id=result.id,
            rule_name=factory.Iterator(failed_rule_strings),
        )
        assert (
            session.query(ReimbursementWalletCategoryRuleEvaluationFailure)
            .filter(
                ReimbursementWalletCategoryRuleEvaluationFailure.evaluation_result_id
                == result.id
            )
            .all()
        )

        # When
        category_service.save_rule_evaluation_failures(
            saved_rule_evaluation_record=result,
            failed_rules=failed_rule_strings,
        )

        # Then
        failed_rules = (
            session.query(ReimbursementWalletCategoryRuleEvaluationFailure)
            .filter(
                ReimbursementWalletCategoryRuleEvaluationFailure.evaluation_result_id
                == result.id
            )
            .all()
        )

        assert set([rule.rule_name for rule in failed_rules]) == set(
            failed_rule_strings
        )

    def test_save_rule_evaluation_failures_delete(
        self,
        session,
        category_service,
        category_association_with_rule,
        qualified_wallet,
    ):
        """Test that existing failures are deleted when the evaluation result is True"""
        # Given
        allowed_category, rule = category_association_with_rule
        result = ReimbursementWalletCategoryRuleEvaluationResultFactory.create(
            reimbursement_organization_settings_allowed_category_id=allowed_category.id,
            reimbursement_wallet_id=qualified_wallet.id,
            evaluation_result=True,
            executed_category_rule=None,
            failed_category_rule=None,
        )
        failed_rule_strings = ["RULE_ONE", "RULE_TWO"]
        ReimbursementWalletCategoryRuleEvaluationFailureFactory.create_batch(
            size=len(failed_rule_strings),
            evaluation_result_id=result.id,
            rule_name=factory.Iterator(failed_rule_strings),
        )
        assert (
            session.query(ReimbursementWalletCategoryRuleEvaluationFailure)
            .filter(
                ReimbursementWalletCategoryRuleEvaluationFailure.evaluation_result_id
                == result.id
            )
            .all()
        )

        # When
        category_service.save_rule_evaluation_failures(
            saved_rule_evaluation_record=result,
            failed_rules=[],
        )

        # Then
        failed_rules = (
            session.query(ReimbursementWalletCategoryRuleEvaluationFailure)
            .filter(
                ReimbursementWalletCategoryRuleEvaluationFailure.evaluation_result_id
                == result.id
            )
            .all()
        )

        assert not failed_rules


class TestEvaluateRulesForWallet:
    @pytest.mark.parametrize(
        argnames=("evaluated_value", "expected_string"),
        argvalues=[
            (True, "TENURE_ONE_CALENDAR_YEAR "),
            (False, "TENURE_ONE_CALENDAR_YEAR"),
        ],
    )
    def test_evaluate_rules_for_wallet(
        self,
        evaluated_value,
        expected_string,
        category_service,
        category_association_with_rule,
        qualified_wallet,
        active_wallet_user,
        qualified_wallet_eligibility_verification,
        mock_enterprise_verification_service,
    ):
        # Given
        if evaluated_value:
            date = datetime.utcnow().date() - timedelta(days=399)
            qualified_wallet_eligibility_verification.record[
                "employee_start_date"
            ] = str(date)
        else:
            qualified_wallet_eligibility_verification.record[
                "employee_start_date"
            ] = str(datetime.utcnow().date())

        mock_enterprise_verification_service.get_verification_for_user_and_org.return_value = (
            qualified_wallet_eligibility_verification
        )
        allowed_category, rule = category_association_with_rule
        # When
        result, rules_string = category_service.evaluate_rules_for_wallet(
            wallet=qualified_wallet, all_category_rules=[rule]
        )
        # Then
        assert result is evaluated_value
        assert rules_string == expected_string

    @pytest.mark.parametrize(
        argnames="started_at",
        argvalues=[
            None,
            datetime.utcnow().date() + timedelta(days=5),
        ],
    )
    def test_evaluate_rules_for_wallet_no_started_at(
        self,
        started_at,
        category_service,
        category_association_with_rule,
        qualified_wallet,
        qualified_wallet_eligibility_verification,
        mock_enterprise_verification_service,
    ):
        # Given
        qualified_wallet_eligibility_verification.record["employee_start_date"] = str(
            started_at
        )
        mock_enterprise_verification_service.get_verification_for_user.return_value = (
            qualified_wallet_eligibility_verification
        )
        allowed_category, rule = category_association_with_rule
        # When
        result, rules_string = category_service.evaluate_rules_for_wallet(
            wallet=qualified_wallet, all_category_rules=[rule]
        )
        # Then
        assert result is False
        assert rules_string == "TENURE_ONE_CALENDAR_YEAR"

    def test_evaluate_rules_for_wallet_exception(
        self, category_service, category_association_with_rule, qualified_wallet
    ):
        # Given
        allowed_category, rule = category_association_with_rule
        mock_execute = MagicMock()
        category_service.execute_category_rule = mock_execute
        mock_execute.side_effect = [
            ActionableCategoryActivationException(message="Bad Data")
        ]

        # When
        result, rules_string = category_service.evaluate_rules_for_wallet(
            wallet=qualified_wallet, all_category_rules=[rule]
        )
        # Then
        assert result is False
        assert rules_string == "TENURE_ONE_CALENDAR_YEAR"


class TestEvaluateAllRulesForWallet:
    @pytest.mark.parametrize(
        argnames=(
            "expected_all_rules",
            "rule_results",
            "expected_result",
            "expected_failed_rules",
        ),
        argvalues=[
            (
                ["TENURE_30_DAYS", "TENURE_90_DAYS", "TENURE_180_DAYS"],
                [True, True, True],
                True,
                [],
            ),
            (
                ["TENURE_30_DAYS", "TENURE_90_DAYS", "TENURE_180_DAYS"],
                [True, False, True],
                False,
                ["TENURE_90_DAYS"],
            ),
            (
                ["TENURE_30_DAYS", "TENURE_90_DAYS", "TENURE_180_DAYS"],
                [False, False, False],
                False,
                ["TENURE_30_DAYS", "TENURE_90_DAYS", "TENURE_180_DAYS"],
            ),
        ],
    )
    def test_evaluate_all_rules_for_wallet_active_rules(
        self,
        category_service,
        qualified_wallet,
        category_association_with_rule,
        expected_all_rules: list[str],
        rule_results: list[bool],
        expected_result: bool,
        expected_failed_rules: list[str],
    ):
        # Given
        allowed_category, _ = category_association_with_rule
        rules: list[
            ReimbursementOrgSettingsAllowedCategoryRule
        ] = ReimbursementOrgSettingsAllowedCategoryRuleFactory.create_batch(
            size=len(expected_all_rules),
            reimbursement_organization_settings_allowed_category_id=allowed_category.id,
            rule_name=factory.Iterator(expected_all_rules),
        )
        category_service.execute_category_rule = MagicMock(side_effect=rule_results)

        # When
        (
            result,
            all_rules,
            failed_rules,
        ) = category_service.evaluate_all_rules_for_wallet(
            wallet=qualified_wallet, all_category_rules=rules
        )

        # Then
        assert result is expected_result
        assert all_rules == expected_all_rules
        assert failed_rules == expected_failed_rules

    @pytest.mark.parametrize(
        argnames=(
            "expected_all_rules",
            "started_at",
            "expected_result",
            "expected_failed_rules",
        ),
        argvalues=[
            (
                ["TENURE_30_DAYS", "TENURE_90_DAYS", "TENURE_180_DAYS"],
                [
                    datetime.utcnow() - timedelta(days=3),
                    datetime.utcnow() - timedelta(days=3),
                    datetime.utcnow() - timedelta(days=3),
                ],
                True,
                [],
            ),
            (
                ["TENURE_30_DAYS", "TENURE_90_DAYS", "TENURE_180_DAYS"],
                [
                    datetime.utcnow() + timedelta(days=3),
                    datetime.utcnow() - timedelta(days=3),
                    datetime.utcnow() - timedelta(days=3),
                ],
                False,
                ["TENURE_30_DAYS"],
            ),
            (
                ["TENURE_30_DAYS", "TENURE_90_DAYS", "TENURE_180_DAYS"],
                [
                    datetime.utcnow() + timedelta(days=3),
                    datetime.utcnow() + timedelta(days=3),
                    datetime.utcnow() + timedelta(days=3),
                ],
                False,
                ["TENURE_30_DAYS", "TENURE_90_DAYS", "TENURE_180_DAYS"],
            ),
        ],
    )
    def test_evaluate_all_rules_for_wallet_rule_activeness(
        self,
        category_service,
        qualified_wallet,
        category_association_with_rule,
        expected_all_rules: list[str],
        started_at: list[datetime.date],
        expected_result: bool,
        expected_failed_rules: list[str],
    ):
        # Given
        allowed_category, _ = category_association_with_rule
        rules: list[
            ReimbursementOrgSettingsAllowedCategoryRule
        ] = ReimbursementOrgSettingsAllowedCategoryRuleFactory.create_batch(
            size=len(expected_all_rules),
            reimbursement_organization_settings_allowed_category_id=allowed_category.id,
            rule_name=factory.Iterator(expected_all_rules),
            started_at=factory.Iterator(started_at),
        )
        category_service.execute_category_rule = MagicMock(return_value=True)

        # When
        (
            result,
            all_rules,
            failed_rules,
        ) = category_service.evaluate_all_rules_for_wallet(
            wallet=qualified_wallet, all_category_rules=rules
        )

        # Then
        assert result is expected_result
        assert all_rules == expected_all_rules
        assert failed_rules == expected_failed_rules

    @pytest.mark.parametrize(
        argnames=(
            "expected_all_rules",
            "rule_results",
            "expected_result",
            "expected_failed_rules",
        ),
        argvalues=[
            (
                ["TENURE_30_DAYS", "TENURE_90_DAYS", "TENURE_180_DAYS"],
                [True, True, True],
                True,
                [],
            ),
            (
                ["TENURE_30_DAYS", "TENURE_90_DAYS", "TENURE_180_DAYS"],
                [True, True, ActionableCategoryActivationException("oh no")],
                False,
                ["TENURE_180_DAYS"],
            ),
            (
                ["TENURE_30_DAYS", "TENURE_90_DAYS", "TENURE_180_DAYS"],
                [
                    ActionableCategoryActivationException("oh no"),
                    ActionableCategoryActivationException("oh no"),
                    ActionableCategoryActivationException("oh no"),
                ],
                False,
                ["TENURE_30_DAYS", "TENURE_90_DAYS", "TENURE_180_DAYS"],
            ),
        ],
    )
    def test_evaluate_all_rules_for_wallet_exceptions(
        self,
        category_service,
        qualified_wallet,
        category_association_with_rule,
        expected_all_rules: list[str],
        rule_results: list[bool | Exception],
        expected_result: bool,
        expected_failed_rules: list[str],
    ):
        # Given
        allowed_category, _ = category_association_with_rule
        rules: list[
            ReimbursementOrgSettingsAllowedCategoryRule
        ] = ReimbursementOrgSettingsAllowedCategoryRuleFactory.create_batch(
            size=len(expected_all_rules),
            reimbursement_organization_settings_allowed_category_id=allowed_category.id,
            rule_name=factory.Iterator(expected_all_rules),
        )
        category_service.execute_category_rule = MagicMock(side_effect=rule_results)

        # When
        (
            result,
            all_rules,
            failed_rules,
        ) = category_service.evaluate_all_rules_for_wallet(
            wallet=qualified_wallet, all_category_rules=rules
        )

        # Then
        assert result is expected_result
        assert all_rules == expected_all_rules
        assert failed_rules == expected_failed_rules


class TestSaveRulesAndSettings:
    def test_save_rule_evaluation_record_creates(
        self, category_service, category_association_with_rule, qualified_wallet
    ):
        # Given
        rule_result = True
        failed_rules_string = None
        success_rules_string = "TENURE_ONE_CALENDAR_YEAR "
        allowed_category, rule = category_association_with_rule

        # When
        category_service.save_rule_evaluation_record(
            category_id=allowed_category.id,
            wallet_id=qualified_wallet.id,
            rule_result=rule_result,
            failed_rules_string=failed_rules_string,
            success_rules_string=success_rules_string,
        )
        # Then
        evaluated_rule = (
            category_service.rules_repo.get_category_rule_evaluation_result(
                allowed_category_id=allowed_category.id, wallet_id=qualified_wallet.id
            )
        )
        assert (
            evaluated_rule.reimbursement_organization_settings_allowed_category_id
            == allowed_category.id
        )
        assert evaluated_rule.reimbursement_wallet_id == qualified_wallet.id
        assert evaluated_rule.evaluation_result is True
        assert evaluated_rule.executed_category_rule == "TENURE_ONE_CALENDAR_YEAR "
        assert evaluated_rule.failed_category_rule is None

    def test_save_rule_evaluation_record_updates(
        self, category_service, category_association_with_rule, qualified_wallet
    ):
        # Given
        rule_result = False
        failed_rules_string = "TENURE_ONE_CALENDAR_YEAR"
        success_rules_string = None
        allowed_category, rule = category_association_with_rule
        ReimbursementWalletCategoryRuleEvaluationResultFactory.create(
            reimbursement_organization_settings_allowed_category_id=allowed_category.id,
            reimbursement_wallet_id=qualified_wallet.id,
            evaluation_result=True,
            executed_category_rule="TENURE_ONE_CALENDAR_YEAR ",
            failed_category_rule=None,
        )
        # When
        category_service.save_rule_evaluation_record(
            category_id=allowed_category.id,
            wallet_id=qualified_wallet.id,
            rule_result=rule_result,
            failed_rules_string=failed_rules_string,
            success_rules_string=success_rules_string,
        )
        # Then
        evaluated_rule = (
            category_service.rules_repo.get_category_rule_evaluation_result(
                allowed_category_id=allowed_category.id, wallet_id=qualified_wallet.id
            )
        )
        assert (
            evaluated_rule.reimbursement_organization_settings_allowed_category_id
            == allowed_category.id
        )
        assert evaluated_rule.reimbursement_wallet_id == qualified_wallet.id
        assert evaluated_rule.evaluation_result == rule_result
        assert evaluated_rule.executed_category_rule is None
        assert evaluated_rule.failed_category_rule == failed_rules_string

    @staticmethod
    def test_test_save_rule_evaluation_record_updates_integrity_error(
        category_service, category_association_with_rule, qualified_wallet
    ):
        # Given
        rule_result = False
        failed_rules_string = "TENURE_ONE_CALENDAR_YEAR"
        success_rules_string = None
        allowed_category, rule = category_association_with_rule
        ReimbursementWalletCategoryRuleEvaluationResultFactory.create(
            reimbursement_organization_settings_allowed_category_id=allowed_category.id,
            reimbursement_wallet_id=qualified_wallet.id,
            evaluation_result=True,
            executed_category_rule="TENURE_ONE_CALENDAR_YEAR ",
            failed_category_rule=None,
        )
        category_service.save_rule_evaluation_record(
            category_id=allowed_category.id,
            wallet_id=qualified_wallet.id,
            rule_result=rule_result,
            failed_rules_string=failed_rules_string,
            success_rules_string=success_rules_string,
        )
        updated_rule_result = not False

        # When
        category_service.save_rule_evaluation_record(
            category_id=allowed_category.id,
            wallet_id=qualified_wallet.id,
            rule_result=updated_rule_result,
            failed_rules_string=failed_rules_string,
            success_rules_string=success_rules_string,
        )

        evaluated_rule = (
            category_service.rules_repo.get_category_rule_evaluation_result(
                allowed_category_id=allowed_category.id, wallet_id=qualified_wallet.id
            )
        )

        # Then
        assert (
            evaluated_rule.reimbursement_organization_settings_allowed_category_id
            == allowed_category.id
        )
        assert evaluated_rule.reimbursement_wallet_id == qualified_wallet.id
        assert evaluated_rule.evaluation_result == updated_rule_result
        assert evaluated_rule.executed_category_rule is None
        assert evaluated_rule.failed_category_rule == failed_rules_string

    def test_save_category_settings_change(
        self, category_service, category_association_with_setting, qualified_wallet
    ):
        # Given
        # Full Access no Rules
        category, setting = category_association_with_setting
        given_mapped_settings = {category.id: {qualified_wallet.id: setting}}
        # When
        processed_setting = category_service.save_category_settings(
            category_id=category.id,
            wallet=qualified_wallet,
            evaluation_result=False,
            has_rules=True,
            mapped_settings_results=given_mapped_settings,
        )
        # Then
        assert processed_setting.access_level_source == CategoryRuleAccessSource.RULES
        assert processed_setting.access_level == CategoryRuleAccessLevel.NO_ACCESS

    def test_save_category_settings_override(
        self, category_service, category_association_with_setting, qualified_wallet
    ):
        # Given
        # Full Access
        category, setting = category_association_with_setting
        setting.access_level_source = CategoryRuleAccessSource.OVERRIDE
        given_mapped_settings = {category.id: {qualified_wallet.id: setting}}
        # When
        processed_setting = category_service.save_category_settings(
            category_id=category.id,
            wallet=qualified_wallet,
            evaluation_result=False,
            has_rules=False,
            mapped_settings_results=given_mapped_settings,
        )
        # Then
        assert (
            processed_setting.access_level_source == CategoryRuleAccessSource.OVERRIDE
        )
        assert processed_setting.access_level == CategoryRuleAccessLevel.FULL_ACCESS

    def test_save_category_settings_creates(
        self, category_service, category_association_with_rule, qualified_wallet
    ):
        # Given
        has_rules = True
        eval_result = True
        allowed_category, rule = category_association_with_rule
        given_mapped_settings = {allowed_category.id: {qualified_wallet.id: None}}
        # When
        with mock.patch(
            "wallet.utils.alegeus.enrollments.enroll_wallet.configure_account"
        ) as mock_configure_account:
            mock_configure_account.return_value = True, []
            category_service.save_category_settings(
                category_id=allowed_category.id,
                wallet=qualified_wallet,
                has_rules=has_rules,
                evaluation_result=eval_result,
                mapped_settings_results=given_mapped_settings,
            )
            # Then
            setting = category_service.rules_repo.get_category_setting_from_allowed_category_and_wallet(
                allowed_category_id=allowed_category.id, wallet_id=qualified_wallet.id
            )
            assert setting
            assert setting.access_level == CategoryRuleAccessLevel.FULL_ACCESS
            assert setting.access_level_source == CategoryRuleAccessSource.RULES
            assert setting.reimbursement_wallet_id == qualified_wallet.id
            assert mock_configure_account.called

    @pytest.mark.parametrize(
        argnames=("eval_results", "bypass", "access_level", "expected_mock_call_count"),
        argvalues=[
            (True, False, CategoryRuleAccessLevel.FULL_ACCESS, 1),
            (False, False, CategoryRuleAccessLevel.NO_ACCESS, 0),
            (True, True, CategoryRuleAccessLevel.FULL_ACCESS, 0),
            (False, False, CategoryRuleAccessLevel.NO_ACCESS, 0),
        ],
    )
    def test_save_category_settings_creates_alegeus_calls(
        self,
        category_service,
        category_association_with_rule,
        qualified_wallet,
        eval_results,
        bypass,
        access_level,
        expected_mock_call_count,
    ):
        # Given
        has_rules = True
        eval_result = eval_results
        allowed_category, rule = category_association_with_rule
        given_mapped_settings = {allowed_category.id: {qualified_wallet.id: None}}
        # When
        with mock.patch(
            "wallet.utils.alegeus.enrollments.enroll_wallet.configure_account"
        ) as mock_configure_account:
            mock_configure_account.return_value = True, []
            category_service.save_category_settings(
                category_id=allowed_category.id,
                wallet=qualified_wallet,
                has_rules=has_rules,
                evaluation_result=eval_result,
                mapped_settings_results=given_mapped_settings,
                bypass_alegeus=bypass,
            )
            # Then
            setting = category_service.rules_repo.get_category_setting_from_allowed_category_and_wallet(
                allowed_category_id=allowed_category.id, wallet_id=qualified_wallet.id
            )
            assert setting
            assert setting.access_level == access_level
            assert setting.access_level_source == CategoryRuleAccessSource.RULES
            assert setting.reimbursement_wallet_id == qualified_wallet.id
            assert mock_configure_account.call_count == expected_mock_call_count

    @pytest.mark.parametrize(
        argnames=(
            "eval_results",
            "initial_access_level",
            "access_level",
            "expected_mock_call_count",
        ),
        argvalues=[
            (
                True,
                CategoryRuleAccessLevel.NO_ACCESS,
                CategoryRuleAccessLevel.FULL_ACCESS,
                1,
            ),
            (
                False,
                CategoryRuleAccessLevel.NO_ACCESS,
                CategoryRuleAccessLevel.NO_ACCESS,
                0,
            ),
            (
                True,
                CategoryRuleAccessLevel.FULL_ACCESS,
                CategoryRuleAccessLevel.FULL_ACCESS,
                0,
            ),
            (
                False,
                CategoryRuleAccessLevel.FULL_ACCESS,
                CategoryRuleAccessLevel.NO_ACCESS,
                0,
            ),
        ],
    )
    def test_save_category_settings_updates(
        self,
        category_service,
        qualified_wallet,
        category_associations_with_a_rule,
        eval_results,
        initial_access_level,
        access_level,
        expected_mock_call_count,
    ):
        # Given
        allowed_category, setting = category_associations_with_a_rule[0]
        setting = ReimbursementWalletAllowedCategorySettingsFactory.create(
            reimbursement_organization_settings_allowed_category_id=allowed_category.id,
            reimbursement_wallet_id=qualified_wallet.id,
            access_level=initial_access_level,
            access_level_source=CategoryRuleAccessSource.RULES,
        )
        given_mapped_settings = {allowed_category.id: {qualified_wallet.id: setting}}
        # When
        with mock.patch(
            "wallet.utils.alegeus.enrollments.enroll_wallet.configure_account"
        ) as mock_configure_account:
            mock_configure_account.return_value = True, []
            category_service.save_category_settings(
                category_id=allowed_category.id,
                wallet=qualified_wallet,
                has_rules=True,
                evaluation_result=eval_results,
                mapped_settings_results=given_mapped_settings,
            )
            # Then
            setting = category_service.rules_repo.get_category_setting_from_allowed_category_and_wallet(
                allowed_category_id=allowed_category.id, wallet_id=qualified_wallet.id
            )
            assert setting
            assert setting.access_level == access_level
            assert setting.access_level_source == CategoryRuleAccessSource.RULES
            assert setting.reimbursement_wallet_id == qualified_wallet.id
            assert mock_configure_account.call_count == expected_mock_call_count

    def test_save_category_settings_exception(
        self, category_service, category_association_with_rule, qualified_wallet
    ):
        # Given
        has_rules = True
        eval_result = True
        allowed_category, rule = category_association_with_rule
        given_mapped_settings = {allowed_category.id: {qualified_wallet.id: None}}
        with mock.patch(
            "wallet.repository.reimbursement_category_activation.CategoryActivationRepository"
            ".upsert_allowed_category_setting"
        ) as mock_create:
            mock_create.side_effect = OSError
            # When/Then
            with pytest.raises(ActionableCategoryActivationException):
                category_service.save_category_settings(
                    category_id=allowed_category.id,
                    wallet=qualified_wallet,
                    has_rules=has_rules,
                    evaluation_result=eval_result,
                    mapped_settings_results=given_mapped_settings,
                )


class TestServiceHelpers:
    @pytest.mark.parametrize(
        argnames=(
            "evaluated_value",
            "expected_failed_string",
            "expected_success_string",
        ),
        argvalues=[
            (True, None, "TENURE_ONE_CALENDAR_YEAR"),
            (False, "TENURE_ONE_CALENDAR_YEAR", None),
        ],
    )
    def test_get_rules_strings(
        self,
        evaluated_value,
        expected_failed_string,
        expected_success_string,
        category_service,
    ):
        # Given
        rules_string = "TENURE_ONE_CALENDAR_YEAR"
        eval_result = evaluated_value
        # When
        failed_rules_string, success_rules_string = category_service.get_rules_strings(
            rules_string, eval_result
        )
        # Then
        assert failed_rules_string == expected_failed_string
        assert success_rules_string == expected_success_string

    @pytest.mark.parametrize(
        argnames=(
            "has_rules",
            "evaluated_results",
            "expected_access_level",
            "expected_access_source",
        ),
        argvalues=[
            (
                True,
                True,
                CategoryRuleAccessLevel.FULL_ACCESS,
                CategoryRuleAccessSource.RULES,
            ),
            (
                False,
                None,
                CategoryRuleAccessLevel.FULL_ACCESS,
                CategoryRuleAccessSource.NO_RULES,
            ),
            (
                True,
                False,
                CategoryRuleAccessLevel.NO_ACCESS,
                CategoryRuleAccessSource.RULES,
            ),
            (
                False,
                True,
                CategoryRuleAccessLevel.FULL_ACCESS,
                CategoryRuleAccessSource.NO_RULES,
            ),
        ],
    )
    def test_get_access_level_and_source(
        self,
        has_rules,
        evaluated_results,
        expected_access_level,
        expected_access_source,
        category_service,
    ):
        # Given
        has_rules = has_rules
        eval_result = evaluated_results
        # When
        access_level, access_source = category_service.get_access_level_and_source(
            has_rules, eval_result
        )
        # Then
        assert access_level == expected_access_level
        assert access_source == expected_access_source


class TestProcessAllowedCategoriesWithRules:
    def test_process_allowed_categories_that_have_rules(
        self,
        category_service,
        category_association_with_rule,
        qualified_wallet,
        qualified_wallet_eligibility_verification,
        mock_enterprise_verification_service,
    ):
        # Given
        qualified_wallet_eligibility_verification.record["employee_start_date"] = str(
            datetime.utcnow().date()
        )
        mock_enterprise_verification_service.get_verification_for_user.return_value = (
            qualified_wallet_eligibility_verification
        )
        expected_rule_result = False
        allowed_category, rule = category_association_with_rule

        with mock.patch(
            "wallet.utils.alegeus.enrollments.enroll_wallet.configure_account"
        ) as mock_configure_account:
            mock_configure_account.return_value = True, []
            # When
            for _ in category_service.process_allowed_categories_that_have_rules(
                bypass_alegeus=False, commit_size=10
            ):
                pass

            # Then
            settings = category_service.rules_repo.get_category_setting_from_allowed_category_and_wallet(
                wallet_id=qualified_wallet.id, allowed_category_id=allowed_category.id
            )
            rule_eval = category_service.rules_repo.get_category_rule_evaluation_result(
                allowed_category_id=allowed_category.id, wallet_id=qualified_wallet.id
            )
            assert settings
            assert rule_eval
            assert settings.access_level == CategoryRuleAccessLevel.NO_ACCESS
            assert settings.access_level_source == CategoryRuleAccessSource.RULES
            assert rule_eval.evaluation_result == expected_rule_result

    def test_process_allowed_categories_that_have_rules_no_ids(
        self, category_service, qualified_wallet
    ):
        # When
        with mock.patch(
            "wallet.utils.alegeus.enrollments.enroll_wallet.configure_account"
        ) as mock_configure_account:
            mock_configure_account.return_value = True, []
            category_service.process_allowed_categories_that_have_rules(
                bypass_alegeus=False, commit_size=10
            )
            # Then
            all_settings = category_service.rules_repo.get_all_category_settings()
            assert all_settings == []


class TestProcessAllowedCategoriesNoRules:
    def test_process_allowed_categories_without_rules(
        self, category_service, qualified_wallet
    ):
        # Given
        allowed_categories = qualified_wallet.get_or_create_wallet_allowed_categories
        allowed_category_ids = [ac.id for ac in allowed_categories]

        # When
        with mock.patch(
            "wallet.utils.alegeus.enrollments.enroll_wallet.configure_account"
        ) as mock_configure_account:
            mock_configure_account.return_value = True, []
            for _ in category_service.process_allowed_categories_without_rules(
                bypass_alegeus=False, commit_size=10
            ):
                pass
            # Then
            all_settings = category_service.rules_repo.get_all_category_settings()
            assert len(all_settings) == len(allowed_category_ids)

    def test_process_allowed_categories_without_rules_no_ids(self, category_service):
        # When
        category_service.process_allowed_categories_without_rules(
            bypass_alegeus=False, commit_size=10
        )
        # Then
        all_settings = category_service.rules_repo.get_all_category_settings()
        assert all_settings == []


class TestGetStartDate:
    @pytest.mark.parametrize(
        "plan_start_date,eligibility_start_date,expected",
        [
            (
                date(year=2025, month=1, day=1),
                date(year=2025, month=2, day=2),
                date(year=2025, month=2, day=2),
            ),
            (
                date(year=2025, month=1, day=1),
                None,
                date(year=2025, month=1, day=1),
            ),
            (None, None, None),
        ],
    )
    def test_get_start_date_for_user_no_allowed_category(
        self,
        category_service,
        qualified_wallet,
        plan_start_date,
        eligibility_start_date,
        expected,
    ):
        plan = ReimbursementPlanFactory.create(start_date=plan_start_date)
        user = qualified_wallet.member
        with mock.patch(
            "wallet.services.reimbursement_category_activation_visibility.get_user_eligibility_start_date",
            return_value=eligibility_start_date,
        ):
            start_date = category_service.get_start_date_for_user_allowed_category(
                plan=plan, allowed_category=None, user_id=user.id
            )
        assert start_date == expected

    @pytest.mark.parametrize(
        "plan_start_date,eligibility_start_date,rule_name,expected",
        [
            (
                date(year=2025, month=1, day=1),
                date(year=2025, month=2, day=2),
                "TENURE_30_DAYS",
                date(year=2025, month=2, day=2) + timedelta(days=30),
            ),
            (
                date(year=2025, month=1, day=1),
                None,
                "TENURE_30_DAYS",
                date(year=2025, month=1, day=1) + timedelta(days=30),
            ),
            (
                date(year=2025, month=1, day=1),
                None,
                "TENURE_ONE_CALENDAR_YEAR",
                date(year=2026, month=1, day=1),
            ),
            (
                date(year=2025, month=1, day=1),
                date(year=2023, month=1, day=1),
                "TENURE_30_DAYS",
                date(year=2025, month=1, day=1),
            ),
            (None, None, "TENURE_30_DAYS", None),
        ],
        ids=[
            "timedelta_30",
            "no eligibilty date",
            "timedelta_one_year",
            "date_too_early",
            "no_dates",
        ],
    )
    def test_get_start_date_for_user_allowed_category(
        self,
        category_service,
        qualified_wallet,
        plan_start_date,
        eligibility_start_date,
        rule_name,
        expected,
    ):
        plan = ReimbursementPlanFactory.create(start_date=plan_start_date)
        category = qualified_wallet.reimbursement_organization_settings.allowed_reimbursement_categories[
            0
        ]
        user = qualified_wallet.member
        ReimbursementOrgSettingsAllowedCategoryRuleFactory.create(
            reimbursement_organization_settings_allowed_category_id=category.id,
            rule_name=rule_name,
            started_at=date.today() - timedelta(days=10),
        )
        with mock.patch(
            "wallet.services.reimbursement_category_activation_visibility.get_user_eligibility_start_date",
            return_value=eligibility_start_date,
        ):
            start_date = category_service.get_start_date_for_user_allowed_category(
                plan=plan, allowed_category=category, user_id=user.id
            )
        assert start_date == expected

    @pytest.mark.parametrize(
        "plan_start_date,eligibility_start_date,expected",
        [
            (
                date(year=2025, month=6, day=1),
                date(year=2025, month=12, day=31),
                date(year=2025, month=12, day=31),
            ),
            (date(year=2025, month=6, day=1), None, date(year=2025, month=6, day=1)),
            (None, None, None),
        ],
    )
    def test_get_start_date_for_user_allowed_category_no_rule(
        self,
        category_service,
        qualified_wallet,
        plan_start_date,
        eligibility_start_date,
        expected,
    ):
        plan = ReimbursementPlanFactory.create(start_date=plan_start_date)
        category = qualified_wallet.reimbursement_organization_settings.allowed_reimbursement_categories[
            0
        ]
        user = qualified_wallet.member
        with mock.patch(
            "wallet.services.reimbursement_category_activation_visibility.get_user_eligibility_start_date",
            return_value=eligibility_start_date,
        ):
            start_date = category_service.get_start_date_for_user_allowed_category(
                plan=plan, allowed_category=category, user_id=user.id
            )
        assert start_date == expected
