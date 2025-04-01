from datetime import datetime
from unittest import mock
from unittest.mock import MagicMock

from wallet.models.constants import CategoryRuleAccessLevel, CategoryRuleAccessSource
from wallet.tasks.reimbursement_category_rules_evaluator import job_driver


def test_job_driver(
    category_service,
    category_associations_with_a_rule,
    qualified_wallet,
    qualified_alegeus_wallet_hdhp_single,
    qualified_wallet_enablement_hdhp_single,
    qualified_wallet_eligibility_verification,
    mock_enterprise_verification_service,
):
    # Given
    qualified_wallet_eligibility_verification.record["employee_start_date"] = str(
        datetime.utcnow().date()
    )
    mock_enterprise_verification_service.get_verification_for_user_and_org.side_effect = [
        qualified_wallet_eligibility_verification,
        qualified_wallet_eligibility_verification,
    ]
    expected_rule_result = False
    allowed_category_with_rule_1, rule_1 = category_associations_with_a_rule[0]
    allowed_category_with_rule_2, rule_2 = category_associations_with_a_rule[1]
    # a fertility category was set up as part of org set up without a rule
    allowed_category_without_rule_id = (
        category_service.rules_repo.get_all_allowed_category_ids_without_rules()[0]
    )
    with mock.patch(
        "wallet.utils.alegeus.enrollments.enroll_wallet.configure_account"
    ) as mock_configure_account:
        mock_configure_account.return_value = True, []
        # When
        res = job_driver()

        # Then
        # Job was successful
        assert res == (True, 5, 0)

        for (cat_w_rule, qual_wal) in [
            (allowed_category_with_rule_1, qualified_wallet),
            (allowed_category_with_rule_2, qualified_alegeus_wallet_hdhp_single),
        ]:
            # The category that had the rule
            settings_with = category_service.rules_repo.get_category_setting_from_allowed_category_and_wallet(
                wallet_id=qual_wal.id,
                allowed_category_id=cat_w_rule.id,
            )
            rule_eval_with = (
                category_service.rules_repo.get_category_rule_evaluation_result(
                    allowed_category_id=cat_w_rule.id,
                    wallet_id=qual_wal.id,
                )
            )
            assert settings_with
            assert rule_eval_with
            assert settings_with.access_level == CategoryRuleAccessLevel.NO_ACCESS
            assert settings_with.access_level_source == CategoryRuleAccessSource.RULES
            assert rule_eval_with.evaluation_result == expected_rule_result

        # The category that did not have the rule
        settings_without = category_service.rules_repo.get_category_setting_from_allowed_category_and_wallet(
            wallet_id=qualified_wallet.id,
            allowed_category_id=allowed_category_without_rule_id,
        )
        rule_eval_without = (
            category_service.rules_repo.get_category_rule_evaluation_result(
                allowed_category_id=allowed_category_without_rule_id,
                wallet_id=qualified_wallet.id,
            )
        )
        assert settings_without
        assert rule_eval_without is None
        assert settings_without.access_level == CategoryRuleAccessLevel.FULL_ACCESS
        assert settings_without.access_level_source == CategoryRuleAccessSource.NO_RULES


def test_job_driver_with_failure(
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
    mock_enterprise_verification_service.get_verification_for_user_and_org.return_value = (
        qualified_wallet_eligibility_verification
    )
    expected_rule_result = False
    allowed_category_with_rule, rule = category_association_with_rule
    # a fertility category was set up as part of org set up without a rule
    allowed_category_without_rule_id = (
        category_service.rules_repo.get_all_allowed_category_ids_without_rules()[0]
    )
    mock_fn = MagicMock(side_effect=Exception("Mock exception"))
    mock_fn.__name__ = "mock_fn"
    with mock.patch(
        "wallet.services.reimbursement_category_activation_visibility.CategoryActivationService.process_allowed_categories_without_rules",
        new=mock_fn,
    ), mock.patch(
        "wallet.utils.alegeus.enrollments.enroll_wallet.configure_account"
    ) as mock_configure_account:
        mock_configure_account.return_value = True, []
        # When
        res = job_driver()

        # Then
        # Job was successful
        assert res == (False, 1, 0)

        # The category that had the rule
        settings_with = category_service.rules_repo.get_category_setting_from_allowed_category_and_wallet(
            wallet_id=qualified_wallet.id,
            allowed_category_id=allowed_category_with_rule.id,
        )
        rule_eval_with = (
            category_service.rules_repo.get_category_rule_evaluation_result(
                allowed_category_id=allowed_category_with_rule.id,
                wallet_id=qualified_wallet.id,
            )
        )
        assert settings_with
        assert rule_eval_with
        assert settings_with.access_level == CategoryRuleAccessLevel.NO_ACCESS
        assert settings_with.access_level_source == CategoryRuleAccessSource.RULES
        assert rule_eval_with.evaluation_result == expected_rule_result

        # The category that did not have the rule
        settings_without = category_service.rules_repo.get_category_setting_from_allowed_category_and_wallet(
            wallet_id=qualified_wallet.id,
            allowed_category_id=allowed_category_without_rule_id,
        )
        rule_eval_without = (
            category_service.rules_repo.get_category_rule_evaluation_result(
                allowed_category_id=allowed_category_without_rule_id,
                wallet_id=qualified_wallet.id,
            )
        )
        assert settings_without is None
        assert rule_eval_without is None
