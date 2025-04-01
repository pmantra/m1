import datetime
from unittest.mock import patch

import pytest

from eligibility import EnterpriseVerificationError
from pytests.freezegun import freeze_time
from wallet.models.constants import (
    BenefitTypes,
    CategoryRuleAccessLevel,
    CategoryRuleAccessSource,
    ReimbursementRequestExpenseTypes,
)
from wallet.pytests.factories import (
    ReimbursementRequestCategoryExpenseTypesFactory,
    ReimbursementWalletAllowedCategorySettingsFactory,
)
from wallet.services.reimbursement_category_activation_rules import (
    AmazonProgenyTOCRule,
    LowesProgenyTOCRule,
    Tenure30DaysCategoryRule,
    Tenure90DaysCategoryRule,
    Tenure180DaysCategoryRule,
    TenureOneCalendarYearCategoryRule,
)


class TestTenureOneCalendarYearCategoryRule:
    @pytest.mark.parametrize(
        "start_date, current_date, expected_evaluation",
        [
            (datetime.date(2020, 2, 29), datetime.datetime(2021, 2, 27), False),
            (datetime.date(2020, 2, 29), datetime.datetime(2021, 2, 28), True),
            (datetime.date(2020, 2, 29), datetime.datetime(2021, 3, 1), True),
            (datetime.date(2023, 2, 28), datetime.datetime(2024, 2, 28), True),
            (datetime.date(2023, 3, 1), datetime.datetime(2024, 2, 28), False),
            (datetime.date(2023, 3, 1), datetime.datetime(2024, 3, 28), True),
        ],
        ids=[
            "LeapYear_NotYetOneYear",
            "LeapYear_ExactlyOneYear",
            "LeapYear_OverOneYear",
            "NonLeapYear_ExactlyOneYear",
            "NonLeapYear_UnderOneYear",
            "NonLeapYear_OverOneYear",
        ],
    )
    def test_tenure_one_year(
        self,
        start_date,
        current_date,
        expected_evaluation,
        qualified_alegeus_wallet_hra,
        qualified_wallet_eligibility_verification,
        mock_enterprise_verification_service,
    ):
        qualified_wallet_eligibility_verification.record["employee_start_date"] = str(
            start_date
        )
        mock_enterprise_verification_service.get_verification_for_user_and_org.return_value = (
            qualified_wallet_eligibility_verification
        )
        with freeze_time(current_date):
            rule_evaluation = TenureOneCalendarYearCategoryRule.execute(
                qualified_alegeus_wallet_hra
            )
            assert rule_evaluation == expected_evaluation

    def test_test_tenure_one_year_verification_does_not_exist(
        self, qualified_alegeus_wallet_hra, mock_enterprise_verification_service
    ):
        mock_enterprise_verification_service.get_verification_for_user_and_org.return_value = (
            None
        )
        rule_evaluation = TenureOneCalendarYearCategoryRule.execute(
            qualified_alegeus_wallet_hra
        )
        assert rule_evaluation is False

    def test_test_tenure_one_year_record_does_not_exist(
        self,
        qualified_alegeus_wallet_hra,
        mock_enterprise_verification_service,
        qualified_wallet_eligibility_verification,
    ):
        qualified_wallet_eligibility_verification.record = None

        mock_enterprise_verification_service.get_verification_for_user_and_org.return_value = (
            qualified_wallet_eligibility_verification
        )
        rule_evaluation = TenureOneCalendarYearCategoryRule.execute(
            qualified_alegeus_wallet_hra
        )
        assert rule_evaluation is False

    def test_test_tenure_one_year_eligible_date_none(
        self,
        qualified_alegeus_wallet_hra,
        qualified_wallet_eligibility_verification,
        mock_enterprise_verification_service,
    ):
        qualified_wallet_eligibility_verification.record["employee_start_date"] = None

        mock_enterprise_verification_service.get_verification_for_user_and_org.return_value = (
            qualified_wallet_eligibility_verification
        )
        rule_evaluation = TenureOneCalendarYearCategoryRule.execute(
            qualified_alegeus_wallet_hra
        )
        assert rule_evaluation is False

    def test_test_tenure_one_year_eligible_service_exception(
        self,
        qualified_alegeus_wallet_hra,
        mock_enterprise_verification_service,
    ):
        mock_enterprise_verification_service.get_verification_for_user_and_org.side_effect = (
            Exception()
        )
        with pytest.raises(EnterpriseVerificationError):
            TenureOneCalendarYearCategoryRule.execute(qualified_alegeus_wallet_hra)

    def test_tenure_one_year_no_user_in_wallet(self, qualified_wallet):
        rule_evaluation = TenureOneCalendarYearCategoryRule.execute(qualified_wallet)
        assert rule_evaluation is False


class TestTenure30DaysCategoryRule:
    @pytest.mark.parametrize(
        "start_date, current_date, expected_evaluation",
        [
            (datetime.date(2023, 10, 1), datetime.datetime(2023, 10, 30), False),
            (datetime.date(2023, 10, 1), datetime.datetime(2023, 10, 31), True),
            (datetime.date(2023, 10, 1), datetime.datetime(2023, 11, 1), True),
        ],
        ids=[
            "Under",
            "Exactly",
            "Over",
        ],
    )
    def test_tenure_30_days(
        self,
        start_date,
        current_date,
        expected_evaluation,
        qualified_alegeus_wallet_hra,
        qualified_wallet_eligibility_verification,
        mock_enterprise_verification_service,
    ):
        qualified_wallet_eligibility_verification.record["employee_start_date"] = str(
            start_date
        )
        mock_enterprise_verification_service.get_verification_for_user_and_org.return_value = (
            qualified_wallet_eligibility_verification
        )

        with freeze_time(current_date):
            rule_evaluation = Tenure30DaysCategoryRule.execute(
                qualified_alegeus_wallet_hra
            )
            assert rule_evaluation == expected_evaluation


class TestTenure90DaysCategoryRule:
    @pytest.mark.parametrize(
        "start_date, current_date, expected_evaluation",
        [
            (datetime.date(2023, 6, 1), datetime.datetime(2023, 8, 29), False),
            (datetime.date(2023, 6, 1), datetime.datetime(2023, 8, 30), True),
            (datetime.date(2023, 6, 1), datetime.datetime(2023, 9, 30), True),
        ],
        ids=[
            "Under",
            "Exactly",
            "Over",
        ],
    )
    def test_tenure_90_days(
        self,
        start_date,
        current_date,
        expected_evaluation,
        qualified_alegeus_wallet_hra,
        qualified_wallet_eligibility_verification,
        mock_enterprise_verification_service,
    ):
        qualified_wallet_eligibility_verification.record["employee_start_date"] = str(
            start_date
        )
        mock_enterprise_verification_service.get_verification_for_user_and_org.return_value = (
            qualified_wallet_eligibility_verification
        )

        with freeze_time(current_date):
            rule_evaluation = Tenure90DaysCategoryRule.execute(
                qualified_alegeus_wallet_hra
            )
            assert rule_evaluation == expected_evaluation


class TestTenure180DaysCategoryRule:
    @pytest.mark.parametrize(
        "start_date, current_date, expected_evaluation",
        [
            (datetime.date(2023, 6, 1), datetime.datetime(2023, 11, 28), True),
            (datetime.date(2023, 6, 1), datetime.datetime(2023, 11, 27), False),
            (datetime.date(2023, 6, 1), datetime.datetime(2023, 11, 30), True),
        ],
        ids=[
            "Exactly",
            "Under",
            "Over",
        ],
    )
    def test_tenure_180_days(
        self,
        start_date,
        current_date,
        expected_evaluation,
        qualified_alegeus_wallet_hra,
        qualified_wallet_eligibility_verification,
        mock_enterprise_verification_service,
    ):
        qualified_wallet_eligibility_verification.record["employee_start_date"] = str(
            start_date
        )
        mock_enterprise_verification_service.get_verification_for_user_and_org.return_value = (
            qualified_wallet_eligibility_verification
        )
        with freeze_time(current_date):
            rule_evaluation = Tenure180DaysCategoryRule.execute(
                qualified_alegeus_wallet_hra
            )
            assert rule_evaluation == expected_evaluation


class TestAddTenureToStartDate:
    def test_add_tenure_days(self):
        starting_date = datetime.date(year=2025, month=1, day=1)
        new_date = Tenure180DaysCategoryRule().add_tenure_to_start_date(
            date=starting_date
        )
        assert new_date == starting_date + datetime.timedelta(days=180)

    def test_add_tenure_years(self):
        starting_date = datetime.date(year=2025, month=1, day=1)
        new_date = TenureOneCalendarYearCategoryRule().add_tenure_to_start_date(
            date=starting_date
        )
        assert new_date == datetime.date(year=2026, month=1, day=1)


class TestAmazonLowesProgenyTOCRule:
    @pytest.mark.parametrize(
        "benefit_type, num_cycles, max_amount, ledger_data, verification, expected_result, todays_date",
        [
            # Case 1: No Visibility:  No eligibility data lookup
            (
                BenefitTypes.CURRENCY,
                None,
                1000,
                None,
                False,  # No ledger entries
                False,
                "2025-01-02",
            ),
            # Case 2: Visibility: No ledger entries found
            (
                BenefitTypes.CYCLE,
                10,
                None,
                {},
                True,  # Empty ledger entries
                True,
                "2025-01-02",
            ),
            # Case 3: Visibility: Ledger entry with spend exceeding max before auth date period
            (
                BenefitTypes.CYCLE,
                12,
                None,
                {
                    "historical_spend": None,
                    "historical_cycles_used": 12,
                    "most_recent_auth_date": datetime.date(2023, 12, 15),
                },
                True,
                True,
                "2025-01-02",
            ),
            # Case 4: Visibility: Ledger entry within spend limits, pre-2024 auth date
            (
                BenefitTypes.CURRENCY,
                None,
                1000,
                {
                    "historical_spend": 300,
                    "historical_cycles_used": None,
                    "most_recent_auth_date": datetime.date(2023, 12, 15),
                },
                True,
                True,
                "2025-01-02",
            ),
            # Case 5: No Visibility: Ledger entry within spend limits, auth date between 2024-01-01 and 2025-06-30
            (
                BenefitTypes.CYCLE,
                15,
                None,
                {
                    "historical_spend": None,
                    "historical_cycles_used": 5,
                    "most_recent_auth_date": datetime.date(2024, 5, 1),
                },
                True,
                False,
                "2025-01-02",
            ),
            # Case 6: No Visibility: Ledger entry within over limits, auth date between 2024-01-01 and 2025-06-30
            (
                BenefitTypes.CYCLE,
                12,
                None,
                {
                    "historical_spend": None,
                    "historical_cycles_used": 12,
                    "most_recent_auth_date": datetime.date(2024, 5, 1),
                },
                True,
                False,
                "2025-01-02",
            ),
            # Case 7: Visibility: Ledger entry within spend limits, auth date post-2025-07-01
            (
                BenefitTypes.CURRENCY,
                None,
                1000,
                {
                    "historical_spend": 700,
                    "historical_cycles_used": None,
                    "most_recent_auth_date": datetime.date(2024, 5, 1),
                },
                True,
                True,
                "2025-08-02",
            ),
        ],
    )
    def test_historic_spend_date_rule_amazon(
        self,
        historical_spend_service,
        mock_enterprise_verification_service,
        qualified_alegeus_wallet_hra,
        eligibility_verification,
        mock_ledger_entry,
        benefit_type,
        num_cycles,
        max_amount,
        ledger_data,
        expected_result,
        verification,
        todays_date,
    ):
        # Given
        mock_verification = eligibility_verification() if verification else None
        mock_enterprise_verification_service.get_verification_for_user_and_org.return_value = (
            mock_verification
        )

        mock_ledger_entry.historical_spend = (
            ledger_data["historical_spend"] if ledger_data else None
        )
        mock_ledger_entry.historical_cycles_used = (
            ledger_data["historical_cycles_used"] if ledger_data else None
        )
        mock_ledger_entry.most_recent_auth_date = (
            ledger_data["most_recent_auth_date"] if ledger_data else None
        )

        association = qualified_alegeus_wallet_hra.reimbursement_organization_settings.allowed_reimbursement_categories[
            0
        ]
        association.benefit_type = benefit_type
        association.num_cycles = num_cycles
        association.reimbursement_request_category_maximum = max_amount

        with patch(
            "common.wallet_historical_spend.WalletHistoricalSpendClient.get_historic_spend_records"
        ) as mock_get_historic_spend_records:
            mock_get_historic_spend_records.return_value = (
                [mock_ledger_entry] if ledger_data else []
            )
            # When
            with freeze_time(datetime.date.fromisoformat(todays_date), tick=False):
                rule_evaluation = AmazonProgenyTOCRule.execute(
                    wallet=qualified_alegeus_wallet_hra, association=association
                )
            assert rule_evaluation == expected_result

    @pytest.mark.parametrize(
        "benefit_type, num_cycles, max_amount, ledger_data, verification, expected_result, todays_date",
        [
            # Case 1: No Visibility:  No eligibility data lookup
            (
                BenefitTypes.CURRENCY,
                None,
                1000,
                None,
                False,  # No ledger entries
                False,
                "2025-01-02",
            ),
            # Case 2: Visibility: No ledger entries found
            (
                BenefitTypes.CYCLE,
                10,
                None,
                {},
                True,  # Empty ledger entries
                True,
                "2025-01-02",
            ),
            # Case 3: Visibility: Ledger entry with spend exceeding max
            (
                BenefitTypes.CURRENCY,
                None,
                500,
                {
                    "historical_spend": 600,
                    "historical_cycles_used": 3,
                    "most_recent_auth_date": datetime.date(2023, 12, 15),
                },
                True,
                True,
                "2025-01-02",
            ),
            # Case 4: Visibility: Ledger entry within spend limits, pre-auth date
            (
                BenefitTypes.CURRENCY,
                None,
                1000,
                {
                    "historical_spend": 300,
                    "historical_cycles_used": None,
                    "most_recent_auth_date": datetime.date(2024, 9, 15),
                },
                True,
                True,
                "2025-01-02",
            ),
            # Case 5: No Visibility: Ledger entry within spend limits, auth date between 2024-12-31 and 2025-04-1
            (
                BenefitTypes.CYCLE,
                15,
                None,
                {
                    "historical_spend": 3000,
                    "historical_cycles_used": 5,
                    "most_recent_auth_date": datetime.date(2024, 12, 31),
                },
                True,
                False,
                "2025-03-02",
            ),
            # Case 6: No Visibility: Ledger entry within spend limits, auth date between 2024-12-31 and 2025-04-1
            (
                BenefitTypes.CYCLE,
                15,
                None,
                {
                    "historical_spend": 3000,
                    "historical_cycles_used": 15,
                    "most_recent_auth_date": datetime.date(2024, 12, 31),
                },
                True,
                False,
                "2025-03-02",
            ),
            # Case 7: Visibility: Ledger entry within spend limits, auth date post-2025-07-01
            (
                BenefitTypes.CYCLE,
                4,
                1000,
                {
                    "historical_spend": 700,
                    "historical_cycles_used": 1,
                    "most_recent_auth_date": datetime.date(2025, 2, 1),
                },
                True,
                True,
                "2025-08-02",
            ),
        ],
    )
    def test_historic_spend_date_rule_lowes(
        self,
        historical_spend_service,
        mock_enterprise_verification_service,
        qualified_alegeus_wallet_hra,
        eligibility_verification,
        mock_ledger_entry,
        benefit_type,
        num_cycles,
        max_amount,
        ledger_data,
        expected_result,
        verification,
        todays_date,
    ):
        # Given
        mock_verification = eligibility_verification() if verification else None
        mock_enterprise_verification_service.get_verification_for_user_and_org.return_value = (
            mock_verification
        )

        mock_ledger_entry.historical_spend = (
            ledger_data["historical_spend"] if ledger_data else None
        )
        mock_ledger_entry.historical_cycles_used = (
            ledger_data["historical_cycles_used"] if ledger_data else None
        )
        mock_ledger_entry.most_recent_auth_date = (
            ledger_data["most_recent_auth_date"] if ledger_data else None
        )

        association = qualified_alegeus_wallet_hra.reimbursement_organization_settings.allowed_reimbursement_categories[
            0
        ]
        association.benefit_type = benefit_type
        association.num_cycles = num_cycles
        association.reimbursement_request_category_maximum = max_amount

        with patch(
            "common.wallet_historical_spend.WalletHistoricalSpendClient.get_historic_spend_records"
        ) as mock_get_historic_spend_records:
            mock_get_historic_spend_records.return_value = (
                [mock_ledger_entry] if ledger_data else []
            )
            # When
            with freeze_time(datetime.date.fromisoformat(todays_date), tick=False):
                rule_evaluation = LowesProgenyTOCRule.execute(
                    wallet=qualified_alegeus_wallet_hra, association=association
                )
            assert rule_evaluation == expected_result

    @pytest.mark.parametrize("rule_class", [AmazonProgenyTOCRule, LowesProgenyTOCRule])
    def test_historic_spend_date_rule_existing_visibility_no_adjustments_success(
        self,
        historical_spend_service,
        mock_enterprise_verification_service,
        qualified_alegeus_wallet_hra,
        eligibility_verification,
        mock_ledger_entry,
        valid_alegeus_plan_hra,
        rule_class,
    ):
        # Given

        association = qualified_alegeus_wallet_hra.reimbursement_organization_settings.allowed_reimbursement_categories[
            0
        ]
        association.reimbursement_request_category.reimbursement_plan = (
            valid_alegeus_plan_hra
        )
        ReimbursementRequestCategoryExpenseTypesFactory.create(
            reimbursement_request_category=association.reimbursement_request_category,
            expense_type=ReimbursementRequestExpenseTypes.FERTILITY,
        )
        ReimbursementWalletAllowedCategorySettingsFactory.create(
            reimbursement_organization_settings_allowed_category_id=association.id,
            reimbursement_wallet_id=qualified_alegeus_wallet_hra.id,
            access_level=CategoryRuleAccessLevel.NO_ACCESS,
            access_level_source=CategoryRuleAccessSource.RULES,
        )
        mock_verification = eligibility_verification(dob=datetime.date(1980, 1, 1))
        mock_enterprise_verification_service.get_verification_for_user_and_org.return_value = (
            mock_verification
        )

        with patch(
            "common.wallet_historical_spend.WalletHistoricalSpendClient.get_historic_spend_records"
        ) as mock_get_historic_spend_records, patch(
            "wallet.services.wallet_historical_spend.WalletHistoricalSpendService.submit_claim_to_alegeus"
        ) as mock_alegeus_request, patch(
            "wallet.services.wallet_historical_spend.gcp_pubsub"
        ) as mock_gcp_pubsub:
            mock_get_historic_spend_records.side_effect = [
                [mock_ledger_entry],
                [mock_ledger_entry],
            ]
            mock_alegeus_request.return_value = None
            # When
            with freeze_time(datetime.date(2025, 8, 2), tick=False):
                rule_evaluation = rule_class.execute(
                    wallet=qualified_alegeus_wallet_hra, association=association
                )

        assert rule_evaluation is True
        assert mock_get_historic_spend_records.call_count == 2
        assert mock_alegeus_request.call_count == 1
        assert mock_gcp_pubsub.publish.called

    @pytest.mark.parametrize("rule_class", [AmazonProgenyTOCRule, LowesProgenyTOCRule])
    def test_historic_spend_date_rule_existing_visibility_with_adjustments_success(
        self,
        historical_spend_service,
        mock_enterprise_verification_service,
        qualified_alegeus_wallet_hra,
        eligibility_verification,
        mock_ledger_entry,
        valid_alegeus_plan_hra,
        rule_class,
    ):
        # Given
        association = qualified_alegeus_wallet_hra.reimbursement_organization_settings.allowed_reimbursement_categories[
            0
        ]
        association.reimbursement_request_category.reimbursement_plan = (
            valid_alegeus_plan_hra
        )
        ReimbursementRequestCategoryExpenseTypesFactory.create(
            reimbursement_request_category=association.reimbursement_request_category,
            expense_type=ReimbursementRequestExpenseTypes.FERTILITY,
        )
        ReimbursementWalletAllowedCategorySettingsFactory.create(
            reimbursement_organization_settings_allowed_category_id=association.id,
            reimbursement_wallet_id=qualified_alegeus_wallet_hra.id,
            access_level=CategoryRuleAccessLevel.NO_ACCESS,
            access_level_source=CategoryRuleAccessSource.RULES,
        )
        mock_verification = eligibility_verification(dob=datetime.date(1980, 1, 1))
        mock_enterprise_verification_service.get_verification_for_user_and_org.return_value = (
            mock_verification
        )
        with patch(
            "common.wallet_historical_spend.WalletHistoricalSpendClient.get_historic_spend_records"
        ) as mock_get_historic_spend_records, patch(
            "wallet.services.wallet_historical_spend.WalletHistoricalSpendService.submit_claim_to_alegeus"
        ) as mock_alegeus_request, patch(
            "wallet.services.wallet_historical_spend.gcp_pubsub"
        ) as mock_gcp_pubsub:

            first_mock = mock_ledger_entry
            first_mock.adjustment_id = "232"
            mock_get_historic_spend_records.side_effect = [
                [first_mock],
                [mock_ledger_entry],
            ]
            mock_alegeus_request.return_value = None
            # When
            with freeze_time(datetime.date(2025, 8, 2), tick=False):
                rule_evaluation = rule_class.execute(
                    wallet=qualified_alegeus_wallet_hra, association=association
                )

        assert rule_evaluation is True
        assert mock_get_historic_spend_records.call_count == 2
        assert mock_alegeus_request.call_count == 0
        assert mock_gcp_pubsub.publish.call_count == 0

    @pytest.mark.parametrize("rule_class", [AmazonProgenyTOCRule, LowesProgenyTOCRule])
    def test_historic_spend_date_rule_existing_visibility_no_category_found(
        self,
        historical_spend_service,
        mock_enterprise_verification_service,
        qualified_alegeus_wallet_hra,
        eligibility_verification,
        mock_ledger_entry,
        rule_class,
    ):
        # Given
        association = qualified_alegeus_wallet_hra.reimbursement_organization_settings.allowed_reimbursement_categories[
            0
        ]
        ReimbursementWalletAllowedCategorySettingsFactory.create(
            reimbursement_organization_settings_allowed_category_id=association.id,
            reimbursement_wallet_id=qualified_alegeus_wallet_hra.id,
            access_level=CategoryRuleAccessLevel.NO_ACCESS,
            access_level_source=CategoryRuleAccessSource.RULES,
        )
        mock_verification = eligibility_verification(dob=datetime.date(1980, 1, 1))
        mock_enterprise_verification_service.get_verification_for_user_and_org.return_value = (
            mock_verification
        )

        with patch(
            "common.wallet_historical_spend.WalletHistoricalSpendClient.get_historic_spend_records"
        ) as mock_get_historic_spend_records, patch(
            "wallet.services.wallet_historical_spend.WalletHistoricalSpendService.submit_claim_to_alegeus"
        ) as mock_alegeus_request, patch(
            "wallet.services.wallet_historical_spend.gcp_pubsub"
        ) as mock_gcp_pubsub:
            mock_get_historic_spend_records.side_effect = [
                [mock_ledger_entry],
                [mock_ledger_entry],
            ]
            # When
            with freeze_time(datetime.date(2025, 8, 2), tick=False):
                rule_evaluation = AmazonProgenyTOCRule.execute(
                    wallet=qualified_alegeus_wallet_hra, association=association
                )
        assert rule_evaluation is True
        assert mock_get_historic_spend_records.call_count == 2
        assert mock_alegeus_request.call_count == 0
        assert mock_gcp_pubsub.publish.call_count == 0

    @pytest.mark.parametrize("rule_class", [AmazonProgenyTOCRule, LowesProgenyTOCRule])
    def test_historic_spend_date_rule_existing_visibility_fails_exception(
        self,
        historical_spend_service,
        mock_enterprise_verification_service,
        qualified_alegeus_wallet_hra,
        eligibility_verification,
        mock_ledger_entry,
        valid_alegeus_plan_hra,
        rule_class,
    ):
        # Given

        association = qualified_alegeus_wallet_hra.reimbursement_organization_settings.allowed_reimbursement_categories[
            0
        ]
        association.reimbursement_request_category.reimbursement_plan = (
            valid_alegeus_plan_hra
        )
        ReimbursementRequestCategoryExpenseTypesFactory.create(
            reimbursement_request_category=association.reimbursement_request_category,
            expense_type=ReimbursementRequestExpenseTypes.FERTILITY,
        )
        ReimbursementWalletAllowedCategorySettingsFactory.create(
            reimbursement_organization_settings_allowed_category_id=association.id,
            reimbursement_wallet_id=qualified_alegeus_wallet_hra.id,
            access_level=CategoryRuleAccessLevel.NO_ACCESS,
            access_level_source=CategoryRuleAccessSource.RULES,
        )
        mock_verification = eligibility_verification(dob=datetime.date(1980, 1, 1))
        mock_enterprise_verification_service.get_verification_for_user_and_org.return_value = (
            mock_verification
        )

        with patch(
            "common.wallet_historical_spend.WalletHistoricalSpendClient.get_historic_spend_records"
        ) as mock_get_historic_spend_records, patch(
            "wallet.services.wallet_historical_spend.WalletHistoricalSpendService.submit_claim_to_alegeus"
        ) as mock_alegeus_request, patch(
            "wallet.services.wallet_historical_spend.gcp_pubsub"
        ) as mock_gcp_pubsub:
            mock_get_historic_spend_records.side_effect = [
                [mock_ledger_entry],
                [mock_ledger_entry],
            ]
            mock_alegeus_request.side_effect = Exception
            # When
            with freeze_time(datetime.date(2025, 8, 2), tick=False):
                rule_evaluation = AmazonProgenyTOCRule.execute(
                    wallet=qualified_alegeus_wallet_hra, association=association
                )

        assert rule_evaluation is False
        assert mock_get_historic_spend_records.call_count == 2
        assert mock_alegeus_request.call_count == 1
        assert mock_gcp_pubsub.publish.call_count == 0
