import datetime
from unittest.mock import call, patch

import pytest
from requests import Response
from structlog import testing

from common.wallet_historical_spend import LedgerEntry, WalletHistoricalSpendClient
from common.wallet_historical_spend.client import WalletHistoricalSpendClientException
from pytests.factories import DefaultUserFactory
from storage.connection import db
from wallet.constants import HISTORICAL_SPEND_LABEL, HistoricalSpendRuleResults
from wallet.models.constants import (
    BenefitTypes,
    ReimbursementRequestExpenseTypes,
    ReimbursementRequestState,
    ReimbursementRequestType,
    WalletUserStatus,
    WalletUserType,
)
from wallet.models.reimbursement import ReimbursementRequest
from wallet.models.reimbursement_wallet_credit import ReimbursementCycleCredits
from wallet.pytests.factories import (
    ReimbursementCycleCreditsFactory,
    ReimbursementRequestCategoryExpenseTypesFactory,
    ReimbursementRequestFactory,
    ReimbursementWalletFactory,
    ReimbursementWalletUsersFactory,
)
from wallet.services.wallet_historical_spend import (
    INTERNAL_TRUST_WHS_URL,
    HistoricalSpendProcessingError,
)


@pytest.fixture
def mock_ledger_entry_with_dependent():
    return LedgerEntry(
        id="3fa85f64-5717-4562-b3fc-2c963f66afa6",
        configuration_id="3fa85f64-5717-4562-b3fc-2c963f66afa6",
        reimbursement_organization_settings_id="12324452543",
        employee_id="321",
        first_name="JOHN",
        last_name="DOE",
        date_of_birth="1990-01-01",
        calculated_spend=9007199254740991,
        calculated_cycles=9007199254740991,
        historical_spend=90072,
        historical_cycles_used=3,
        category="fertility",
        balance_id="3fa85f64-5717-4562-b3fc-2c963f66afa6",
        file_id="3fa85f64-5717-4562-b3fc-2c963f66afa6",
        most_recent_auth_date=datetime.date(2024, 12, 4),
        created_at=datetime.datetime(2024, 12, 4),
        service_date="2024-12-04",
        adjustment_id="3fa85f64-5717-4562-b3fc-2c963f66afa6",
        dependent_first_name="Jane",
        dependent_last_name="Doe",
        dependent_date_of_birth="1990-02-01",
        dependent_id="dep_123",
        subscriber_id="sub_123",
    )


@pytest.fixture
def raw_ledger_entry_mock():
    def _raw_ledger_entry_mock(
        ros_id="abc123", category="fertility", date_string="2024-12-04"
    ):
        today = datetime.date.today().isoformat()
        return {
            "id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
            "configuration_id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
            "reimbursement_organization_settings_id": ros_id,
            "employee_id": "321",
            "first_name": "JANE",
            "last_name": "DOE",
            "date_of_birth": today,
            "category": category,
            "balance_id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
            "file_id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
            "service_date": "2024-12-04",
            "most_recent_auth_date": "2024-12-04",
            "created_at": f"{date_string}T17:14:01.199947+00:00",
            "adjustment_id": None,
            "calculated_spend": 9200,
            "calculated_cycles": 2,
            "historical_spend": 90072,
            "historical_cycles_used": 3,
            "subscriber_id": "sub_123",
        }

    return _raw_ledger_entry_mock


@pytest.fixture
def ledger_entry():
    def _ledger_entry(
        ros_id="12324452543",
        category="fertility",
        adjustment_id=None,
        date_passed=None,
        dependent_first_name="",
        dependent_last_name="",
        dependent_date_of_birth=None,
    ):
        if date_passed is None:
            date_passed = datetime.datetime(2024, 12, 4)
        return LedgerEntry(
            id="3fa85f64-5717-4562-b3fc-2c963f66afa6",
            configuration_id="3fa85f64-5717-4562-b3fc-2c963f66afa6",
            reimbursement_organization_settings_id=ros_id,
            employee_id="321",
            first_name="John",
            last_name="Doe",
            date_of_birth="1980-01-01",
            calculated_spend=90071,
            calculated_cycles=5,
            historical_spend=90072,
            historical_cycles_used=3,
            category=category,
            balance_id="3fa85f64-5717-4562-b3fc-2c963f66afa6",
            file_id="3fa85f64-5717-4562-b3fc-2c963f66afa6",
            most_recent_auth_date=datetime.date(2024, 12, 4),
            created_at=date_passed,
            service_date="2024-12-04",
            adjustment_id=adjustment_id,
            dependent_first_name=dependent_first_name,
            dependent_last_name=dependent_last_name,
            dependent_date_of_birth=dependent_date_of_birth,
            dependent_id=None,
            subscriber_id="sub_123",
        )

    return _ledger_entry


@pytest.fixture
def response_mock():
    def _response_mock(status_code=200):
        mock_response = Response()
        mock_response.status_code = status_code
        mock_response.encoding = "application/json"
        return mock_response

    return _response_mock


class TestProcessHistoricalSpendFile:
    @pytest.mark.parametrize(
        "file_id",
        ["abc123", None],
    )
    def test_process_historical_spend_file_currency_success(
        self,
        qualified_alegeus_wallet_hra,
        raw_ledger_entry_mock,
        mock_enterprise_verification_service,
        eligibility_verification,
        historical_spend_service,
        make_mocked_alegeus_direct_claim_response,
        valid_alegeus_account_hra,
        valid_alegeus_plan_hra,
        file_id,
    ):
        # Given
        mock_alegeus_response = make_mocked_alegeus_direct_claim_response(
            200, 0, 50.00, 50.00
        )

        valid_alegeus_account_hra.wallet = qualified_alegeus_wallet_hra
        valid_alegeus_account_hra.plan = valid_alegeus_plan_hra
        category_associations = (
            qualified_alegeus_wallet_hra.reimbursement_organization_settings.allowed_reimbursement_categories
        )
        category = category_associations[0].reimbursement_request_category
        category.reimbursement_plan = valid_alegeus_plan_hra
        ReimbursementRequestCategoryExpenseTypesFactory.create(
            reimbursement_request_category=category,
            expense_type=ReimbursementRequestExpenseTypes.FERTILITY,
        )
        with patch(
            "common.wallet_historical_spend.WalletHistoricalSpendClient.get_historic_spend_records"
        ) as mock_get_historic_spend_records, patch(
            "wallet.alegeus_api.AlegeusApi.make_api_request"
        ) as mock_alegeus_request, patch(
            "wallet.services.wallet_historical_spend.gcp_pubsub"
        ) as mock_gcp_pubsub:

            mock_get_historic_spend_records.return_value = LedgerEntry.create_ledger_entries_from_dict(
                [
                    raw_ledger_entry_mock(
                        ros_id=qualified_alegeus_wallet_hra.reimbursement_organization_settings.id
                    )
                ]
            )
            mock_enterprise_verification_service.get_verification_for_user_and_org.return_value = eligibility_verification(
                first_name="Jane", last_name="Doe"
            )
            mock_alegeus_request.return_value = mock_alegeus_response
            # When
            historical_spend_service.process_historical_spend_wallets(
                file_id=file_id,
                reimbursement_organization_settings_id=qualified_alegeus_wallet_hra.reimbursement_organization_settings.id,
                wallet_ids=[qualified_alegeus_wallet_hra.id],
            )
            # Then
            all_user_rr = ReimbursementRequest.query.filter(
                ReimbursementRequest.wallet == qualified_alegeus_wallet_hra
            ).all()
            assert all_user_rr[0].label == HISTORICAL_SPEND_LABEL
            assert mock_alegeus_request.called
            assert mock_gcp_pubsub.publish.called

    @pytest.mark.parametrize(
        "file_id",
        ["abc123", None],
    )
    def test_process_historical_spend_file_currency_success_0_entry(
        self,
        qualified_alegeus_wallet_hra,
        raw_ledger_entry_mock,
        mock_enterprise_verification_service,
        eligibility_verification,
        historical_spend_service,
        make_mocked_alegeus_direct_claim_response,
        valid_alegeus_account_hra,
        valid_alegeus_plan_hra,
        file_id,
    ):
        # Given
        valid_alegeus_account_hra.wallet = qualified_alegeus_wallet_hra
        valid_alegeus_account_hra.plan = valid_alegeus_plan_hra
        category_associations = (
            qualified_alegeus_wallet_hra.reimbursement_organization_settings.allowed_reimbursement_categories
        )
        category = category_associations[0].reimbursement_request_category
        category.reimbursement_plan = valid_alegeus_plan_hra
        ReimbursementRequestCategoryExpenseTypesFactory.create(
            reimbursement_request_category=category,
            expense_type=ReimbursementRequestExpenseTypes.FERTILITY,
        )
        with patch(
            "common.wallet_historical_spend.WalletHistoricalSpendClient.get_historic_spend_records"
        ) as mock_get_historic_spend_records, patch(
            "wallet.alegeus_api.AlegeusApi.make_api_request"
        ) as mock_alegeus_request, patch(
            "wallet.services.wallet_historical_spend.gcp_pubsub"
        ) as mock_gcp_pubsub:
            ledger_entry = raw_ledger_entry_mock(
                ros_id=qualified_alegeus_wallet_hra.reimbursement_organization_settings.id
            )
            ledger_entry["calculated_spend"] = 0
            ledger_entry["historical_spend"] = 0
            mock_get_historic_spend_records.return_value = (
                LedgerEntry.create_ledger_entries_from_dict([ledger_entry])
            )
            mock_enterprise_verification_service.get_verification_for_user_and_org.return_value = eligibility_verification(
                first_name="Jane", last_name="Doe"
            )
            # When
            historical_spend_service.process_historical_spend_wallets(
                file_id=file_id,
                reimbursement_organization_settings_id=qualified_alegeus_wallet_hra.reimbursement_organization_settings.id,
                wallet_ids=[qualified_alegeus_wallet_hra.id],
            )
            # Then
            all_user_rr = ReimbursementRequest.query.all()
            assert len(all_user_rr) == 0
            mock_alegeus_request.assert_not_called()
            assert mock_gcp_pubsub.publish.called

    @pytest.mark.parametrize(
        "file_id, expected_rrs",
        [("abc123", 3), (None, 2)],
    )
    def test_process_historical_spend_file_currency_success_multiple_entries(
        self,
        qualified_alegeus_wallet_hra,
        raw_ledger_entry_mock,
        mock_enterprise_verification_service,
        eligibility_verification,
        historical_spend_service,
        make_mocked_alegeus_direct_claim_response,
        valid_alegeus_account_hra,
        valid_alegeus_plan_hra,
        file_id,
        expected_rrs,
    ):
        # Given
        mock_alegeus_response = make_mocked_alegeus_direct_claim_response(
            200, 0, 50.00, 50.00
        )
        valid_alegeus_account_hra.wallet = qualified_alegeus_wallet_hra
        valid_alegeus_account_hra.plan = valid_alegeus_plan_hra
        category_associations = (
            qualified_alegeus_wallet_hra.reimbursement_organization_settings.allowed_reimbursement_categories
        )
        fertility_category = category_associations[0].reimbursement_request_category
        adoption_category = category_associations[1].reimbursement_request_category

        fertility_category.reimbursement_plan = valid_alegeus_plan_hra

        ReimbursementRequestCategoryExpenseTypesFactory.create(
            reimbursement_request_category=fertility_category,
            expense_type=ReimbursementRequestExpenseTypes.FERTILITY,
        )
        ReimbursementRequestCategoryExpenseTypesFactory.create(
            reimbursement_request_category=adoption_category,
            expense_type=ReimbursementRequestExpenseTypes.ADOPTION,
        )
        with patch(
            "common.wallet_historical_spend.WalletHistoricalSpendClient.get_historic_spend_records"
        ) as mock_get_historic_spend_records, patch(
            "wallet.alegeus_api.AlegeusApi.make_api_request"
        ) as mock_alegeus_request, patch(
            "wallet.services.wallet_historical_spend.gcp_pubsub"
        ) as mock_gcp_pubsub:
            mock_alegeus_request.return_value = mock_alegeus_response

            fertility_ledger_entry = raw_ledger_entry_mock(
                ros_id=qualified_alegeus_wallet_hra.reimbursement_organization_settings.id
            )

            adoption_ledger_entry_1 = raw_ledger_entry_mock(
                ros_id=qualified_alegeus_wallet_hra.reimbursement_organization_settings.id,
                category="adoption",
            )
            adoption_ledger_entry_2 = raw_ledger_entry_mock(
                ros_id=qualified_alegeus_wallet_hra.reimbursement_organization_settings.id,
                category="adoption",
                date_string="2024-12-07",
            )
            mock_get_historic_spend_records.return_value = (
                LedgerEntry.create_ledger_entries_from_dict(
                    [
                        fertility_ledger_entry,
                        adoption_ledger_entry_1,
                        adoption_ledger_entry_2,
                    ]
                )
            )

            mock_enterprise_verification_service.get_verification_for_user_and_org.return_value = eligibility_verification(
                first_name="Jane", last_name="Doe"
            )
            # When
            historical_spend_service.process_historical_spend_wallets(
                file_id=file_id,
                reimbursement_organization_settings_id=qualified_alegeus_wallet_hra.reimbursement_organization_settings.id,
                wallet_ids=[qualified_alegeus_wallet_hra.id],
            )
            alegeus_call_count = expected_rrs
            # Then
            all_user_rr = ReimbursementRequest.query.all()
            assert len(all_user_rr) == expected_rrs
            assert mock_alegeus_request.call_count == alegeus_call_count
            assert mock_gcp_pubsub.publish.called

    def test_process_historical_spend_file_cycles_success(
        self,
        wallet_cycle_based,
        raw_ledger_entry_mock,
        mock_enterprise_verification_service,
        eligibility_verification,
        historical_spend_service,
        make_mocked_alegeus_direct_claim_response,
        valid_alegeus_account_hra,
        valid_alegeus_plan_hra,
    ):
        # Given
        mock_alegeus_response = make_mocked_alegeus_direct_claim_response(
            200, 0, 50.00, 50.00
        )

        wallet_cycle_based.reimbursement_organization_settings.organization.alegeus_employer_id = (
            "ABC234"
        )
        wallet_cycle_based.alegeus_id = "DEF567"
        valid_alegeus_account_hra.wallet = wallet_cycle_based
        valid_alegeus_account_hra.plan = valid_alegeus_plan_hra
        category_associations = (
            wallet_cycle_based.reimbursement_organization_settings.allowed_reimbursement_categories
        )
        category = category_associations[0].reimbursement_request_category
        category.reimbursement_plan = valid_alegeus_plan_hra

        with patch(
            "common.wallet_historical_spend.get_client"
        ) as mock_get_client, patch(
            "common.wallet_historical_spend.WalletHistoricalSpendClient.get_historic_spend_records"
        ) as mock_get_historic_spend_records, patch(
            "wallet.alegeus_api.AlegeusApi.make_api_request"
        ) as mock_alegeus_request, patch(
            "wallet.services.wallet_historical_spend.gcp_pubsub"
        ) as mock_gcp_pubsub:

            mock_get_client.return_value = WalletHistoricalSpendClient(
                base_url=INTERNAL_TRUST_WHS_URL
            )
            # Creating the ledger entry with credit spend of 2
            mock_get_historic_spend_records.return_value = LedgerEntry.create_ledger_entries_from_dict(
                [
                    raw_ledger_entry_mock(
                        ros_id=wallet_cycle_based.reimbursement_organization_settings.id
                    )
                ]
            )
            mock_enterprise_verification_service.get_verification_for_user_and_org.return_value = eligibility_verification(
                first_name="Jane", last_name="Doe"
            )
            mock_alegeus_request.return_value = mock_alegeus_response

            # When
            historical_spend_service.process_historical_spend_wallets(
                file_id="abc123",
                reimbursement_organization_settings_id=wallet_cycle_based.reimbursement_organization_settings.id,
                wallet_ids=[wallet_cycle_based.id],
            )
            # Then

            # Starting credits is 12
            credits_list: list[ReimbursementCycleCredits] = (
                db.session.query(ReimbursementCycleCredits)
                .filter(
                    ReimbursementCycleCredits.reimbursement_wallet_id
                    == wallet_cycle_based.id
                )
                .all()
            )
            assert credits_list[0].amount == 10
            assert mock_alegeus_request.called
            assert mock_gcp_pubsub.publish.call_count == 1

    def test_process_historical_spend_file_no_wallets(
        self, qualified_alegeus_wallet_hra, historical_spend_service
    ):
        # Given/When
        with patch("wallet.alegeus_api.AlegeusApi.make_api_request") as mock_alegeus:
            with testing.capture_logs() as logs:
                historical_spend_service.process_historical_spend_wallets(
                    file_id="abc123",
                    reimbursement_organization_settings_id=qualified_alegeus_wallet_hra.reimbursement_organization_settings.id,
                    wallet_ids=[],
                )
        # Then
        expected_event = {
            "event": "No qualified or run out wallets found for wallet historical spend.",
            "file_id": "abc123",
            "log_level": "error",
            "reimbursement_organization_settings_id": str(
                qualified_alegeus_wallet_hra.reimbursement_organization_settings.id
            ),
        }
        assert expected_event in logs
        assert mock_alegeus.call_count == 0

    def test_process_historical_spend_file_whs_exception(
        self,
        qualified_alegeus_wallet_hra,
        raw_ledger_entry_mock,
        mock_enterprise_verification_service,
        eligibility_verification,
        response_mock,
        historical_spend_service,
    ):
        # Given
        with patch(
            "common.base_http_client.requests.request"
        ) as mock_get_historic_spend_request:
            mock_get_historic_spend_request.return_value = response_mock(
                status_code=404
            )
            mock_enterprise_verification_service.get_verification_for_user_and_org.return_value = eligibility_verification(
                first_name="Jane", last_name="Doe"
            )
            # When/Then
            with pytest.raises(WalletHistoricalSpendClientException):
                historical_spend_service.process_historical_spend_wallets(
                    file_id="abc123",
                    reimbursement_organization_settings_id=qualified_alegeus_wallet_hra.reimbursement_organization_settings.id,
                    wallet_ids=[qualified_alegeus_wallet_hra.id],
                )

    def test_process_historical_spend_no_ledger_entries(
        self,
        qualified_alegeus_wallet_hra,
        mock_enterprise_verification_service,
        eligibility_verification,
        historical_spend_service,
    ):
        # Given
        with patch(
            "common.wallet_historical_spend.WalletHistoricalSpendClient.get_historic_spend_records"
        ) as mock_get_historic_spend_records, patch(
            "wallet.alegeus_api.AlegeusApi.make_api_request"
        ) as mock_alegeus_request:
            mock_get_historic_spend_records.return_value = []
            mock_enterprise_verification_service.get_verification_for_user_and_org.return_value = eligibility_verification(
                first_name="Jane", last_name="Doe"
            )
            # When
            with testing.capture_logs() as logs:
                historical_spend_service.process_historical_spend_wallets(
                    file_id="abc123",
                    reimbursement_organization_settings_id=qualified_alegeus_wallet_hra.reimbursement_organization_settings.id,
                    wallet_ids=[qualified_alegeus_wallet_hra.id],
                )
            # Then
            expected_event = {
                "event": "No ledger entries found for wallet historical spend.",
                "file_id": "abc123",
                "log_level": "info",
                "reason": "No ledger entries returned.",
                "reimbursement_organization_settings_id": str(
                    qualified_alegeus_wallet_hra.reimbursement_organization_settings.id
                ),
            }
            assert expected_event in logs
            assert mock_get_historic_spend_records.call_count == 1
            assert mock_alegeus_request.call_count == 0

    def test_process_historical_spend_file_ledger_entry_wallet_not_found(
        self,
        qualified_alegeus_wallet_hra,
        raw_ledger_entry_mock,
        mock_enterprise_verification_service,
        eligibility_verification,
        historical_spend_service,
    ):
        # Given
        with patch(
            "common.wallet_historical_spend.WalletHistoricalSpendClient.get_historic_spend_records"
        ) as mock_get_historic_spend_records, patch(
            "wallet.alegeus_api.AlegeusApi.make_api_request"
        ) as mock_alegeus_request:
            mock_get_historic_spend_records.return_value = LedgerEntry.create_ledger_entries_from_dict(
                [
                    raw_ledger_entry_mock(
                        ros_id=qualified_alegeus_wallet_hra.reimbursement_organization_settings.id
                    )
                ]
            )
            mock_enterprise_verification_service.get_verification_for_user_and_org.return_value = eligibility_verification(
                first_name="Someone", last_name="Else"
            )
            # When
            with testing.capture_logs() as logs:
                historical_spend_service.process_historical_spend_wallets(
                    file_id="abc123",
                    reimbursement_organization_settings_id=qualified_alegeus_wallet_hra.reimbursement_organization_settings.id,
                    wallet_ids=[qualified_alegeus_wallet_hra.id],
                )
            # Then
            expected_log = {
                "event": "Wallet ledger entry not found in wallet lookup",
                "file_id": "abc123",
                "ledger_entry_balance_id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
                "log_level": "error",
                "reason": "Wallet ledger entry not found in wallet lookup.",
                "reimbursement_organization_settings_id": str(
                    qualified_alegeus_wallet_hra.reimbursement_organization_settings.id
                ),
            }
            assert mock_alegeus_request.call_count == 0
            assert expected_log in logs

    def test_process_historical_spend_file_alegeus_fails(
        self,
        qualified_alegeus_wallet_hra,
        raw_ledger_entry_mock,
        mock_enterprise_verification_service,
        eligibility_verification,
        historical_spend_service,
        valid_alegeus_account_hra,
        valid_alegeus_plan_hra,
    ):
        # Given

        valid_alegeus_account_hra.wallet = qualified_alegeus_wallet_hra
        valid_alegeus_account_hra.plan = valid_alegeus_plan_hra
        category_associations = (
            qualified_alegeus_wallet_hra.reimbursement_organization_settings.allowed_reimbursement_categories
        )
        category = category_associations[0].reimbursement_request_category
        category.reimbursement_plan = valid_alegeus_plan_hra
        ReimbursementRequestCategoryExpenseTypesFactory.create(
            reimbursement_request_category=category,
            expense_type=ReimbursementRequestExpenseTypes.FERTILITY,
        )
        with patch(
            "common.wallet_historical_spend.WalletHistoricalSpendClient.get_historic_spend_records"
        ) as mock_get_historic_spend_records, patch(
            "wallet.alegeus_api.AlegeusApi.make_api_request"
        ) as mock_alegeus_request:
            mock_get_historic_spend_records.return_value = LedgerEntry.create_ledger_entries_from_dict(
                [
                    raw_ledger_entry_mock(
                        ros_id=qualified_alegeus_wallet_hra.reimbursement_organization_settings.id
                    )
                ]
            )
            mock_enterprise_verification_service.get_verification_for_user_and_org.return_value = eligibility_verification(
                first_name="Jane", last_name="Doe"
            )
            mock_alegeus_request.side_effect = Exception
            # When
            historical_spend_service.process_historical_spend_wallets(
                file_id="abc123",
                reimbursement_organization_settings_id=qualified_alegeus_wallet_hra.reimbursement_organization_settings.id,
                wallet_ids=[qualified_alegeus_wallet_hra.id],
            )
            # Then
            all_user_rr = ReimbursementRequest.query.filter(
                ReimbursementRequest.wallet == qualified_alegeus_wallet_hra
            ).all()
            assert all_user_rr == []
            assert mock_alegeus_request.called


class TestProcessWalletHistoricalSpendEntry:
    def test_process_wallet_historical_spend_entry__no_spend_category(
        self, ledger_entry, qualified_alegeus_wallet_hra, historical_spend_service
    ):
        # Given
        mock_ledger_entry = ledger_entry(category="unknown")
        # When/Then
        with patch(
            "wallet.alegeus_api.AlegeusApi.make_api_request"
        ) as mock_alegeus_request:
            historical_spend_service.process_wallet_historical_spend_entry(
                mock_ledger_entry, qualified_alegeus_wallet_hra
            )
        assert mock_alegeus_request.call_count == 0

    def test_process_wallet_historical_spend_entry__alegeus_fails(
        self, qualified_alegeus_wallet_hra, ledger_entry, historical_spend_service
    ):
        #
        given_category = qualified_alegeus_wallet_hra.reimbursement_organization_settings.allowed_reimbursement_categories[
            0
        ].reimbursement_request_category
        ReimbursementRequestCategoryExpenseTypesFactory.create(
            reimbursement_request_category=given_category,
            expense_type=ReimbursementRequestExpenseTypes.FERTILITY,
        )
        # When/Then
        with pytest.raises(HistoricalSpendProcessingError) as e:
            historical_spend_service.process_wallet_historical_spend_entry(
                ledger_entry(), qualified_alegeus_wallet_hra
            )
        assert e.value.message == "Failed to create historical spend claim in Alegeus"

    def test_process_wallet_historical_spend_entry__fails_pubsub(
        self,
        qualified_alegeus_wallet_hra,
        raw_ledger_entry_mock,
        mock_enterprise_verification_service,
        eligibility_verification,
        historical_spend_service,
        make_mocked_alegeus_direct_claim_response,
        valid_alegeus_account_hra,
        valid_alegeus_plan_hra,
        ledger_entry,
    ):
        # Given
        mock_alegeus_response = make_mocked_alegeus_direct_claim_response(
            200, 0, 50.00, 50.00
        )

        valid_alegeus_account_hra.wallet = qualified_alegeus_wallet_hra
        valid_alegeus_account_hra.plan = valid_alegeus_plan_hra
        category_associations = (
            qualified_alegeus_wallet_hra.reimbursement_organization_settings.allowed_reimbursement_categories
        )
        category = category_associations[0].reimbursement_request_category
        category.reimbursement_plan = valid_alegeus_plan_hra
        ReimbursementRequestCategoryExpenseTypesFactory.create(
            reimbursement_request_category=category,
            expense_type=ReimbursementRequestExpenseTypes.FERTILITY,
        )
        with patch(
            "common.wallet_historical_spend.get_client"
        ) as mock_get_client, patch(
            "common.wallet_historical_spend.WalletHistoricalSpendClient.get_historic_spend_records"
        ) as mock_get_historic_spend_records, patch(
            "wallet.alegeus_api.AlegeusApi.make_api_request"
        ) as mock_alegeus_request, patch(
            "wallet.services.wallet_historical_spend.gcp_pubsub"
        ) as mock_gcp_pubsub:
            mock_gcp_pubsub.publish.side_effect = Exception("ouchie")
            mock_get_client.return_value = WalletHistoricalSpendClient(
                base_url=INTERNAL_TRUST_WHS_URL
            )
            mock_get_historic_spend_records.return_value = LedgerEntry.create_ledger_entries_from_dict(
                [
                    raw_ledger_entry_mock(
                        ros_id=qualified_alegeus_wallet_hra.reimbursement_organization_settings.id
                    )
                ]
            )
            mock_enterprise_verification_service.get_verification_for_user_and_org.return_value = eligibility_verification(
                first_name="Jane", last_name="Doe"
            )
            mock_alegeus_request.return_value = mock_alegeus_response
            # When
            historical_spend_service.process_wallet_historical_spend_entry(
                ledger_entry(), qualified_alegeus_wallet_hra
            )
            # Then
            all_user_rr = ReimbursementRequest.query.filter(
                ReimbursementRequest.wallet == qualified_alegeus_wallet_hra
            ).all()
            assert all_user_rr[0].label == HISTORICAL_SPEND_LABEL

    def test_process_wallet_historical_spend_entry__fails_cycle_adjustment(
        self,
        wallet_cycle_based,
        raw_ledger_entry_mock,
        mock_enterprise_verification_service,
        eligibility_verification,
        historical_spend_service,
        make_mocked_alegeus_direct_claim_response,
        valid_alegeus_account_hra,
        valid_alegeus_plan_hra,
        ledger_entry,
    ):
        # Given
        wallet_cycle_based.reimbursement_organization_settings.organization.alegeus_employer_id = (
            "ABC234"
        )
        wallet_cycle_based.alegeus_id = "DEF567"
        valid_alegeus_account_hra.wallet = wallet_cycle_based
        valid_alegeus_account_hra.plan = valid_alegeus_plan_hra
        category_associations = (
            wallet_cycle_based.reimbursement_organization_settings.allowed_reimbursement_categories
        )
        category = category_associations[0].reimbursement_request_category
        category.reimbursement_plan = valid_alegeus_plan_hra

        with patch(
            "common.wallet_historical_spend.get_client"
        ) as mock_get_client, patch(
            "common.wallet_historical_spend.WalletHistoricalSpendClient.get_historic_spend_records"
        ) as mock_get_historic_spend_records, patch(
            "wallet.services.wallet_historical_spend.WalletHistoricalSpendService.submit_claim_to_alegeus"
        ) as mock_alegeus_request, patch(
            "wallet.services" ".wallet_historical_spend.gcp_pubsub"
        ) as mock_publisher:

            mock_get_client.return_value = WalletHistoricalSpendClient(
                base_url=INTERNAL_TRUST_WHS_URL
            )
            mock_get_historic_spend_records.return_value = LedgerEntry.create_ledger_entries_from_dict(
                [
                    raw_ledger_entry_mock(
                        ros_id=wallet_cycle_based.reimbursement_organization_settings.id
                    )
                ]
            )
            mock_enterprise_verification_service.get_verification_for_user_and_org.return_value = eligibility_verification(
                first_name="Jane", last_name="Doe"
            )
            mock_alegeus_request.return_value = True

            # breaking code
            ledger_entry.calculated_cycles = None

            historical_spend_service.process_wallet_historical_spend_entry(
                ledger_entry(), wallet_cycle_based
            )
            assert mock_publisher.publish.called


class TestWalletHistoricalSpendHelpers:
    @pytest.mark.parametrize(
        "lookup, expected_members",
        [
            # Single entry in the lookup
            (
                {
                    ("John", "Doe", "1980-01-01"): "wallet_1",
                },
                [
                    {
                        "first_name": "John",
                        "last_name": "Doe",
                        "date_of_birth": "1980-01-01",
                    },
                ],
            ),
            # Multiple entries in the lookup
            (
                {
                    ("Jane", "Smith", "1990-02-01"): {"wallet_2"},
                    ("John", "Doe", "1980-01-01"): {"wallet_1"},
                },
                [
                    {
                        "first_name": "Jane",
                        "last_name": "Smith",
                        "date_of_birth": "1990-02-01",
                    },
                    {
                        "first_name": "John",
                        "last_name": "Doe",
                        "date_of_birth": "1980-01-01",
                    },
                ],
            ),
            # Empty lookup
            (
                {},
                [],
            ),
        ],
    )
    def test_create_members_from_lookup(
        self, lookup, expected_members, historical_spend_service
    ):
        # Given/When
        result = historical_spend_service.create_members_from_lookup(lookup)
        # Then
        assert result == expected_members

    @pytest.mark.parametrize(
        "lookup, ros_id, file_id, limit, exclude_adjusted, category_filter, sort_filter, expected_request_body",
        [
            # All parameters provided
            (
                {
                    ("John", "Doe", "1980-01-01"): {"wallet_1"},
                },
                12345,
                "file_123",
                500,
                True,
                ReimbursementRequestExpenseTypes.FERTILITY,
                "created_at",
                {
                    "sort": {"direction": "DESC", "field": "created_at"},
                    "limit": 500,
                    "file_ids": ["file_123"],
                    "exclude_adjusted": True,
                    "category": ReimbursementRequestExpenseTypes.FERTILITY,
                    "members": [
                        {
                            "first_name": "John",
                            "last_name": "Doe",
                            "date_of_birth": "1980-01-01",
                        },
                    ],
                },
            ),
            # No file_id
            (
                {
                    ("Jane", "Smith", "1990-02-01"): {"wallet_id": "wallet_2"},
                },
                12345,
                None,
                1,
                True,
                None,
                "created_at",
                {
                    "sort": {"direction": "DESC", "field": "created_at"},
                    "limit": 1,
                    "reimbursement_organization_settings_id": "12345",
                    "exclude_adjusted": False,
                    "members": [
                        {
                            "first_name": "Jane",
                            "last_name": "Smith",
                            "date_of_birth": "1990-02-01",
                        },
                    ],
                },
            ),
            # Updated filters
            (
                {
                    ("Jane", "Smith", "1990-02-01"): {"wallet_id": "wallet_2"},
                },
                12345,
                None,
                1,
                False,
                None,
                "most_recent_auth_date",
                {
                    "sort": {"direction": "DESC", "field": "most_recent_auth_date"},
                    "limit": 1,
                    "exclude_adjusted": False,
                    "reimbursement_organization_settings_id": "12345",
                    "members": [
                        {
                            "first_name": "Jane",
                            "last_name": "Smith",
                            "date_of_birth": "1990-02-01",
                        },
                    ],
                },
            ),
            # Empty lookup
            (
                {},
                12345,
                "file_789",
                1,
                True,
                None,
                "created_at",
                {
                    "sort": {"direction": "DESC", "field": "created_at"},
                    "limit": 1,
                    "exclude_adjusted": True,
                    "file_ids": ["file_789"],
                    "members": [],
                },
            ),
        ],
    )
    def test_format_request_body(
        self,
        lookup,
        ros_id,
        file_id,
        limit,
        expected_request_body,
        exclude_adjusted,
        category_filter,
        sort_filter,
        historical_spend_service,
    ):
        # Given/When
        result = historical_spend_service.format_request_body(
            lookup=lookup,
            reimbursement_organization_settings_id=ros_id,
            file_id=file_id,
            limit=limit,
            exclude_adjusted=exclude_adjusted,
            category_filter=category_filter,
            sort_field=sort_filter,
        )
        # Then
        assert result == expected_request_body

    @pytest.mark.parametrize(
        "lookup, expected_wallet",
        [
            # Matching key found in lookup
            ({("JOHN", "DOE", "1980-01-01"): "mock_wallet"}, "mock_wallet"),
            # Wallet Not Found
            ({("JOHN", "DOE", "1980-01-01"): None}, None),
            # No Matching Key
            ({("JOHN", "BOE", "1980-01-01"): "4567"}, None),
        ],
    )
    def test_lookup_wallet(
        self, lookup, expected_wallet, ledger_entry, historical_spend_service
    ):
        # Given/When
        result = historical_spend_service.lookup_wallet(lookup, ledger_entry())
        # Then
        assert result == expected_wallet

    def test_lookup_wallet_matches_dependent(
        self, ledger_entry, historical_spend_service
    ):
        # Given
        wallet_dependent = ReimbursementWalletFactory.create(id=1234)
        wallet_member = ReimbursementWalletFactory.create(id=1235)
        lookup = {
            ("JOHN", "DOE", "1980-01-01"): wallet_member,
            ("JANE", "DOE", "1990-02-01"): wallet_dependent,
        }
        # When
        result = historical_spend_service.lookup_wallet(
            lookup,
            ledger_entry(
                dependent_first_name="Jane",
                dependent_last_name="Doe",
                dependent_date_of_birth="1990-02-01",
            ),
        )
        # Then
        assert result == wallet_dependent

    def test_get_wallet_eligibility_data_success(
        self,
        mock_enterprise_verification_service,
        eligibility_verification,
        qualified_alegeus_wallet_hra,
        historical_spend_service,
    ):
        # Given
        expected_today = datetime.date.today()
        wallet = qualified_alegeus_wallet_hra
        mock_enterprise_verification_service.get_verification_for_user_and_org.return_value = (
            eligibility_verification()
        )
        # When
        lookup_dict = historical_spend_service.get_wallet_eligibility_data(
            wallets=[wallet]
        )
        # Then
        assert list(lookup_dict.items())[0] == (
            ("JOHN", "DOE", expected_today.isoformat()),
            wallet,
        )

    def test_get_wallet_eligibility_data_bad_data(
        self,
        mock_enterprise_verification_service,
        eligibility_verification,
        qualified_alegeus_wallet_hra,
        historical_spend_service,
    ):
        # Given
        e9y_record = eligibility_verification()
        e9y_record.date_of_birth = None
        wallet = qualified_alegeus_wallet_hra
        mock_enterprise_verification_service.get_verification_for_user_and_org.return_value = (
            e9y_record
        )
        # When
        lookup_dict = historical_spend_service.get_wallet_eligibility_data(
            wallets=[wallet]
        )
        # Then
        assert lookup_dict == {}

    def test_get_wallet_eligibility_data_no_eligibility_record(
        self,
        mock_enterprise_verification_service,
        qualified_alegeus_wallet_hra,
        historical_spend_service,
    ):
        # Given
        wallet = qualified_alegeus_wallet_hra
        mock_enterprise_verification_service.get_verification_for_user_and_org.return_value = (
            None
        )
        # When
        lookup_dict = historical_spend_service.get_wallet_eligibility_data(
            wallets=[wallet]
        )
        # Then
        assert lookup_dict == {}

    def test_get_wallet_eligibility_data_exception(
        self,
        mock_enterprise_verification_service,
        qualified_alegeus_wallet_hra,
        historical_spend_service,
    ):
        # Given
        wallet = qualified_alegeus_wallet_hra
        mock_enterprise_verification_service.get_verification_for_user_and_org.side_effect = (
            Exception
        )
        # When
        lookup_dict = historical_spend_service.get_wallet_eligibility_data(
            wallets=[wallet]
        )
        # Then
        assert lookup_dict == {}

    def test_get_wallet_eligibility_data_different_multiple_record(
        self,
        mock_enterprise_verification_service,
        eligibility_verification,
        qualified_alegeus_wallet_hra,
        cycle_benefits_wallet,
        historical_spend_service,
    ):
        # Given
        wallet = qualified_alegeus_wallet_hra
        ReimbursementWalletUsersFactory.create(
            user_id=cycle_benefits_wallet.user_id,
            reimbursement_wallet_id=cycle_benefits_wallet.id,
        )
        mock_enterprise_verification_service.get_verification_for_user_and_org.side_effect = [
            eligibility_verification(),
            eligibility_verification(first_name="Jane", last_name="Doe"),
        ]
        # When
        lookup_dict = historical_spend_service.get_wallet_eligibility_data(
            wallets=[wallet, cycle_benefits_wallet]
        )
        # Then
        assert len(lookup_dict) == 2

    # New eligibility tests

    def test_shared_eligibility_same_wallet(
        self,
        mock_enterprise_verification_service,
        qualified_alegeus_wallet_hra,
        historical_spend_service,
        eligibility_verification,
    ):
        # Test that shared eligibility within the same wallet maps to one key.
        # Given
        active_user = DefaultUserFactory.create()

        ReimbursementWalletUsersFactory.create(
            user_id=active_user.id,
            reimbursement_wallet_id=qualified_alegeus_wallet_hra.id,
            type=WalletUserType.DEPENDENT,
            status=WalletUserStatus.ACTIVE,
        )

        # Same eligibility for both users
        mock_enterprise_verification_service.get_verification_for_user_and_org.side_effect = [
            eligibility_verification(
                first_name="John", last_name="Doe", dob=datetime.date(1980, 1, 1)
            ),
            eligibility_verification(
                first_name="John", last_name="Doe", dob=datetime.date(1980, 1, 1)
            ),
        ]
        # When
        result = historical_spend_service.get_wallet_eligibility_data(
            [qualified_alegeus_wallet_hra]
        )
        # Then
        assert len(result) == 1
        assert (
            result[("JOHN", "DOE", "1980-01-01")].id == qualified_alegeus_wallet_hra.id
        )

    def test_conflicting_keys_across_wallets(
        self,
        mock_enterprise_verification_service,
        qualified_alegeus_wallet_hra,
        historical_spend_service,
        eligibility_verification,
        cycle_benefits_wallet,
    ):
        # Test that conflicting keys across wallets are removed.
        # Given
        active_user = DefaultUserFactory.create()

        ReimbursementWalletUsersFactory.create(
            user_id=active_user.id,
            reimbursement_wallet_id=cycle_benefits_wallet.id,
            type=WalletUserType.DEPENDENT,
            status=WalletUserStatus.ACTIVE,
        )

        # Same key but different wallets
        mock_enterprise_verification_service.get_verification_for_user_and_org.side_effect = [
            eligibility_verification(
                first_name="John", last_name="Doe", dob=datetime.date(1980, 1, 1)
            ),
            eligibility_verification(
                first_name="John", last_name="Doe", dob=datetime.date(1980, 1, 1)
            ),
        ]

        # When
        result = historical_spend_service.get_wallet_eligibility_data(
            [qualified_alegeus_wallet_hra, cycle_benefits_wallet]
        )
        # Then
        assert len(result) == 0  # Both keys should be removed

    def test_no_conflicting_keys_across_wallets(
        self,
        mock_enterprise_verification_service,
        qualified_alegeus_wallet_hra,
        historical_spend_service,
        eligibility_verification,
        cycle_benefits_wallet,
    ):
        # Given
        active_user = DefaultUserFactory.create()

        ReimbursementWalletUsersFactory.create(
            user_id=active_user.id,
            reimbursement_wallet_id=cycle_benefits_wallet.id,  # cycles wallet
            type=WalletUserType.DEPENDENT,
            status=WalletUserStatus.ACTIVE,
        )

        active_shared_wallet_user = DefaultUserFactory.create()

        ReimbursementWalletUsersFactory.create(
            user_id=active_shared_wallet_user.id,
            reimbursement_wallet_id=qualified_alegeus_wallet_hra.id,  # hra wallet
            type=WalletUserType.DEPENDENT,
            status=WalletUserStatus.ACTIVE,
        )

        # Same eligibility for both users
        mock_enterprise_verification_service.get_verification_for_user_and_org.side_effect = [
            eligibility_verification(
                first_name="John", last_name="Doe", dob=datetime.date(1980, 1, 1)
            ),
            eligibility_verification(
                first_name="John", last_name="Doe", dob=datetime.date(1980, 1, 1)
            ),
            eligibility_verification(
                first_name="Jane", last_name="Doe", dob=datetime.date(1980, 1, 1)
            ),
        ]
        # When
        result = historical_spend_service.get_wallet_eligibility_data(
            [qualified_alegeus_wallet_hra, cycle_benefits_wallet]
        )
        # Then
        assert len(result) == 2
        assert (
            result[("JOHN", "DOE", "1980-01-01")].id == qualified_alegeus_wallet_hra.id
        )
        assert result[("JANE", "DOE", "1980-01-01")].id == cycle_benefits_wallet.id

    @pytest.mark.parametrize(
        "ledger_entry_category, expense_types",
        [
            ("fertility", [ReimbursementRequestExpenseTypes.FERTILITY]),
            ("preservation", [ReimbursementRequestExpenseTypes.PRESERVATION]),
            (
                "surrogacy",
                [
                    ReimbursementRequestExpenseTypes.FERTILITY,
                    ReimbursementRequestExpenseTypes.SURROGACY,
                ],
            ),
        ],
    )
    def test_get_spend_category(
        self,
        ledger_entry_category,
        expense_types,
        ledger_entry,
        qualified_alegeus_wallet_hra,
        historical_spend_service,
    ):
        # Given
        given_category = qualified_alegeus_wallet_hra.reimbursement_organization_settings.allowed_reimbursement_categories[
            0
        ].reimbursement_request_category
        for et in expense_types:
            ReimbursementRequestCategoryExpenseTypesFactory.create(
                reimbursement_request_category=given_category,
                expense_type=et,
            )
        ledger_entry(category=ledger_entry_category)
        # When
        result = historical_spend_service.get_spend_category(
            qualified_alegeus_wallet_hra, ledger_entry_category
        )
        # Then
        assert result == given_category

    def test_get_spend_category_expense_type_not_found(
        self, ledger_entry, qualified_alegeus_wallet_hra, historical_spend_service
    ):
        # Given
        ledger_entry(category="unknown")
        # When/Then

        spend_category = historical_spend_service.get_spend_category(
            qualified_alegeus_wallet_hra, "unknown"
        )
        assert spend_category is None

    def test_get_spend_category_no_match(
        self, ledger_entry, qualified_alegeus_wallet_hra, historical_spend_service
    ):
        # Given
        given_category = qualified_alegeus_wallet_hra.reimbursement_organization_settings.allowed_reimbursement_categories[
            0
        ].reimbursement_request_category

        ReimbursementRequestCategoryExpenseTypesFactory.create(
            reimbursement_request_category=given_category,
            expense_type=ReimbursementRequestExpenseTypes.SURROGACY,
        )
        ledger_entry(category="fertility")
        # When/Then
        spend_category = historical_spend_service.get_spend_category(
            qualified_alegeus_wallet_hra, "fertility"
        )
        assert spend_category is None

    def test_create_reimbursement_request(
        self, qualified_alegeus_wallet_hra, ledger_entry, historical_spend_service
    ):
        # Given
        given_category = qualified_alegeus_wallet_hra.reimbursement_organization_settings.allowed_reimbursement_categories[
            0
        ].reimbursement_request_category
        ledger = ledger_entry()
        # When
        reimbursement_request = historical_spend_service.create_reimbursement_request(
            ledger, qualified_alegeus_wallet_hra, given_category, "file_id"
        )

        # Then
        assert reimbursement_request.wallet == qualified_alegeus_wallet_hra
        assert reimbursement_request.category == given_category
        assert (
            reimbursement_request.reimbursement_type == ReimbursementRequestType.MANUAL
        )
        assert reimbursement_request.cost_credit == ledger.calculated_cycles
        assert reimbursement_request.amount == ledger.calculated_spend

    def test_submit_claim_to_alegeus_success(
        self,
        historical_spend_service,
        qualified_alegeus_wallet_hra,
        valid_alegeus_account_hra,
        valid_alegeus_plan_hra,
        make_mocked_alegeus_direct_claim_response,
    ):
        # Given
        valid_alegeus_account_hra.wallet = qualified_alegeus_wallet_hra
        valid_alegeus_account_hra.plan = valid_alegeus_plan_hra

        category_associations = (
            qualified_alegeus_wallet_hra.reimbursement_organization_settings.allowed_reimbursement_categories
        )
        category = category_associations[0].reimbursement_request_category
        category.reimbursement_plan = valid_alegeus_plan_hra

        reimbursement_request = ReimbursementRequestFactory.create(
            wallet=qualified_alegeus_wallet_hra,
            category=category,
            amount=5000,
            state=ReimbursementRequestState.REIMBURSED,
            label="Balance adjustment for prior benefit usage",
        )
        mock_response = make_mocked_alegeus_direct_claim_response(200, 0, 50.00, 50.00)
        # When
        with patch("wallet.alegeus_api.AlegeusApi.make_api_request") as mock_request:
            mock_request.return_value = mock_response
            historical_spend_service.submit_claim_to_alegeus(
                qualified_alegeus_wallet_hra, reimbursement_request
            )

        kwargs = mock_request.call_args.kwargs["data"]
        assert kwargs["ApprovedClaimAmount"] == 50.00
        assert kwargs["ReimbursementMode"] == "None"

    def test_submit_claim_to_alegeus_failure(
        self,
        historical_spend_service,
        qualified_alegeus_wallet_hra,
        valid_alegeus_account_hra,
        valid_alegeus_plan_hra,
        make_mocked_alegeus_direct_claim_response,
    ):
        # Given
        valid_alegeus_account_hra.wallet = qualified_alegeus_wallet_hra
        valid_alegeus_account_hra.plan = valid_alegeus_plan_hra

        category_associations = (
            qualified_alegeus_wallet_hra.reimbursement_organization_settings.allowed_reimbursement_categories
        )
        category = category_associations[0].reimbursement_request_category
        category.reimbursement_plan = valid_alegeus_plan_hra

        reimbursement_request = ReimbursementRequestFactory.create(
            wallet=qualified_alegeus_wallet_hra,
            category=category,
            amount=5000,
            state=ReimbursementRequestState.REIMBURSED,
            label="Balance adjustment for prior benefit usage",
        )
        # Return a 400
        mock_response = make_mocked_alegeus_direct_claim_response(400, 0, 50.00, 50.00)
        # When
        with patch("wallet.alegeus_api.AlegeusApi.make_api_request") as mock_request:
            mock_request.return_value = mock_response
            with pytest.raises(
                HistoricalSpendProcessingError,
                match="Failed to create historical spend claim in Alegeus",
            ):
                historical_spend_service.submit_claim_to_alegeus(
                    qualified_alegeus_wallet_hra, reimbursement_request
                )

        assert mock_request.called

    @pytest.mark.parametrize(
        "calculated_cycles, historical_cycles, file_id, reimbursement_credits_amount, expected_amount",
        [
            (5, 0, "Test_file", 10, 5),  # File Processing Happy path
            (15, 0, "Test_file", 10, 0),  # File Processing Don't go below zero credits
            (-5, 0, "Test_file", 10, 15),  # File ProcessingAdd credits back
            (0, 5, None, 10, 5),  # Wallet Qualification Happy path
            (0, 15, None, 10, 0),  # Wallet Qualification Don't go below zero credits
            (0, -5, None, 10, 15),  # Wallet Qualification Add credits back
        ],
    )
    def test_adjust_reimbursement_credits(
        self,
        calculated_cycles,
        historical_cycles,
        file_id,
        reimbursement_credits_amount,
        expected_amount,
        ledger_entry,
        qualified_alegeus_wallet_hra,
        historical_spend_service,
    ):
        # Given
        ledger = ledger_entry()
        category_associations = (
            qualified_alegeus_wallet_hra.reimbursement_organization_settings.allowed_reimbursement_categories
        )
        spend_category = category_associations[0].reimbursement_request_category

        reimbursement_request = ReimbursementRequestFactory.create(
            wallet=qualified_alegeus_wallet_hra,
            category=spend_category,
            amount=5000,
            state=ReimbursementRequestState.REIMBURSED,
            label="Balance adjustment for prior benefit usage",
        )
        given_credits = ReimbursementCycleCreditsFactory.create(
            reimbursement_wallet_id=qualified_alegeus_wallet_hra.id,
            reimbursement_organization_settings_allowed_category_id=category_associations[
                0
            ].id,
            amount=reimbursement_credits_amount,
        )
        ledger.calculated_cycles = calculated_cycles
        ledger.historical_cycles_used = historical_cycles
        with patch(
            "wallet.services.wallet_historical_spend.WalletHistoricalSpendService"
            ".get_reimbursement_credits_from_category"
        ) as mock_credits:
            mock_credits.return_value = given_credits
            historical_spend_service.adjust_reimbursement_credits(
                qualified_alegeus_wallet_hra,
                ledger,
                spend_category,
                reimbursement_request,
                file_id,
            )

        updated_credits = ReimbursementCycleCredits.query.filter(
            ReimbursementCycleCredits.reimbursement_wallet_id
            == qualified_alegeus_wallet_hra.id,
            ReimbursementCycleCredits.reimbursement_organization_settings_allowed_category_id
            == category_associations[0].id,
        ).first()
        assert updated_credits.amount == expected_amount

    def test_get_wallet_eligibility_data_duplicate_key_removal(
        self,
        mock_enterprise_verification_service,
        eligibility_verification,
        qualified_alegeus_wallet_hra,
        cycle_benefits_wallet,
        historical_spend_service,
    ):
        # Given
        wallet_1 = qualified_alegeus_wallet_hra
        wallet_2 = cycle_benefits_wallet
        ReimbursementWalletUsersFactory.create(
            user_id=cycle_benefits_wallet.user_id,
            reimbursement_wallet_id=cycle_benefits_wallet.id,
        )
        # Mock eligibility verification for two users with the same key
        mock_enterprise_verification_service.get_verification_for_user_and_org.side_effect = [
            eligibility_verification(
                first_name="John", last_name="Doe", dob=datetime.date(1980, 1, 1)
            ),
            eligibility_verification(
                first_name="John", last_name="Doe", dob=datetime.date(1980, 1, 1)
            ),
        ]
        # When
        lookup_dict = historical_spend_service.get_wallet_eligibility_data(
            wallets=[wallet_1, wallet_2]
        )
        # Then
        assert lookup_dict == {}

    @pytest.mark.parametrize(
        "benefit_type,file_id,expected_spend",
        [
            # Cycle processed via file ingestion
            (BenefitTypes.CYCLE, "abc245", 5),
            # Cycle processed via wallet qualification
            (BenefitTypes.CYCLE, None, 3),
            # Currency processed via wallet qualification
            (BenefitTypes.CURRENCY, None, 90072),
            # Currency processed via file ingestion
            (BenefitTypes.CURRENCY, "abc245", 90071),
        ],
    )
    def test_publish_adjustment_notification__success(
        self,
        ledger_entry,
        wallet_cycle_based,
        qualified_alegeus_wallet_hra,
        historical_spend_service,
        benefit_type,
        file_id,
        expected_spend,
    ):
        # Given
        wallet = (
            wallet_cycle_based
            if benefit_type == BenefitTypes.CYCLE
            else qualified_alegeus_wallet_hra
        )
        is_currency = benefit_type != BenefitTypes.CYCLE
        reimbursement_request_id = 12345
        # When
        with patch(
            "wallet.services.wallet_historical_spend.gcp_pubsub"
        ) as mock_gcp_pubsub:
            historical_spend_service.publish_adjustment_notification(
                ledger_entry=ledger_entry(),
                wallet=wallet,
                benefit_type=benefit_type,
                reimbursement_request_id=reimbursement_request_id,
                file_id=file_id,
            )

        expected_data = {
            "balance_id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
            "wallet_id": str(wallet.id),
            "user_id": str(wallet.user_id),
            "value": expected_spend,
            "is_currency": is_currency,
            "reimbursement_request_id": "12345",
        }

        # Then
        assert mock_gcp_pubsub.publish.called
        assert mock_gcp_pubsub.publish.call_args[0][1] == expected_data

    def test_publish_adjustment_notification_fails(
        self, ledger_entry, qualified_alegeus_wallet_hra, historical_spend_service
    ):
        # Given
        benefit_type = BenefitTypes.CURRENCY
        reimbursement_request_id = 12345
        # When
        with patch(
            "wallet.services.wallet_historical_spend.gcp_pubsub"
        ) as mock_gcp_pubsub:
            mock_gcp_pubsub.publish.side_effect = Exception("ouchie")
            historical_spend_service.publish_adjustment_notification(
                ledger_entry=ledger_entry(),
                wallet=qualified_alegeus_wallet_hra,
                benefit_type=benefit_type,
                reimbursement_request_id=reimbursement_request_id,
            )
            assert mock_gcp_pubsub.publish.called


class TestHistoricalSpendForRules:
    @pytest.mark.parametrize(
        "auth_date, expected_result",
        [
            # Case 1: Auth date before 2024
            (
                datetime.date(2023, 12, 15),
                (True, "Eligible"),
            ),
            # Case 2: Auth date between 2024-01-01 and 2025-06-30
            (
                datetime.date(2024, 3, 1),
                (False, "Awaiting Transition"),
            ),
            # Case 3: Auth date on 2025-07-01
            (
                datetime.date(2025, 7, 1),
                (True, "Eligible"),
            ),
            # Case 4: Auth date empty
            (
                None,
                (False, "Maven Error"),
            ),
        ],
    )
    def test_evaluate_auth_date(
        self,
        historical_spend_service,
        qualified_alegeus_wallet_hra,
        ledger_entry,
        auth_date,
        expected_result,
    ):
        # Given
        ledger_entry = ledger_entry()
        ledger_entry.most_recent_auth_date = auth_date
        # When
        result = historical_spend_service._evaluate_auth_date(
            wallet=qualified_alegeus_wallet_hra,
            entry=ledger_entry,
            transition_start_date=datetime.date(2024, 1, 1),
            transition_end_date=datetime.date(2025, 7, 1),
            rule_name="cat rule",
        )
        # Then
        assert result == expected_result

    @pytest.mark.parametrize(
        "benefit_type, num_cycles, max_amount, ledger_data, verification, expected_result",
        [
            # Case 1: No eligibility data lookup
            (
                BenefitTypes.CURRENCY,
                None,
                1000,
                None,
                False,  # No ledger entries
                (False, HistoricalSpendRuleResults.MAVEN_ERROR),
            ),
            # Case 2: No ledger entries found
            (
                BenefitTypes.CYCLE,
                10,
                None,
                {},
                True,  # Empty ledger entries
                (True, HistoricalSpendRuleResults.ELIGIBLE),
            ),
            # Case 3: Ledger entry with spend exceeding max
            (
                BenefitTypes.CURRENCY,
                None,
                500,
                {
                    "historical_spend": 600,
                    "historical_cycles_used": None,
                    "most_recent_auth_date": datetime.date(2023, 12, 15),
                },
                True,
                (True, HistoricalSpendRuleResults.ELIGIBLE),
            ),
            # Case 4: Ledger entry within spend limits, pre-2024 auth date
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
                (True, HistoricalSpendRuleResults.ELIGIBLE),
            ),
            # Case 5: Ledger entry within spend limits, auth date between 2024-01-01 and 2025-06-30
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
                (False, HistoricalSpendRuleResults.AWAITING_TRANSITION),
            ),
            # Case 6: Ledger entry with spend exceeding max auth date between 2024-01-01 and 2025-06-30
            (
                BenefitTypes.CURRENCY,
                None,
                500,
                {
                    "historical_spend": 600,
                    "historical_cycles_used": None,
                    "most_recent_auth_date": datetime.date(2024, 5, 1),
                },
                True,
                (False, HistoricalSpendRuleResults.AWAITING_TRANSITION),
            ),
            # Case 7: Ledger entry within spend limits, auth date post-2025-07-01
            (
                BenefitTypes.CURRENCY,
                None,
                1000,
                {
                    "historical_spend": 700,
                    "historical_cycles_used": None,
                    "most_recent_auth_date": datetime.date(2025, 8, 1),
                },
                True,
                (True, HistoricalSpendRuleResults.ELIGIBLE),
            ),
        ],
    )
    def test_determine_category_eligibility(
        self,
        historical_spend_service,
        mock_enterprise_verification_service,
        qualified_alegeus_wallet_hra,
        eligibility_verification,
        ledger_entry,
        benefit_type,
        num_cycles,
        max_amount,
        ledger_data,
        expected_result,
        verification,
    ):
        # Given
        mock_verification = eligibility_verification() if verification else None
        mock_enterprise_verification_service.get_verification_for_user_and_org.return_value = (
            mock_verification
        )

        mock_ledger_entry = ledger_entry()
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
            result = historical_spend_service.determine_category_eligibility(
                wallet=qualified_alegeus_wallet_hra,
                category_association=association,
                transition_start_date=datetime.date(2024, 1, 1),
                transition_end_date=datetime.date(2025, 7, 1),
                rule_name="cat rule",
            )
            # Then
            assert result == expected_result

    def test_determine_category_eligibility_exception(
        self,
        historical_spend_service,
        mock_enterprise_verification_service,
        qualified_alegeus_wallet_hra,
        eligibility_verification,
        mock_ledger_entry,
    ):
        # Given
        association = qualified_alegeus_wallet_hra.reimbursement_organization_settings.allowed_reimbursement_categories[
            0
        ]
        mock_enterprise_verification_service.get_verification_for_user_and_org.return_value = (
            eligibility_verification()
        )

        with patch(
            "common.wallet_historical_spend.WalletHistoricalSpendClient.get_historic_spend_records"
        ) as mock_get_historic_spend_records:
            mock_get_historic_spend_records.side_effect = Exception
            # When
            result = historical_spend_service.determine_category_eligibility(
                wallet=qualified_alegeus_wallet_hra,
                category_association=association,
                transition_start_date=datetime.date(2024, 1, 1),
                transition_end_date=datetime.date(2025, 7, 1),
                rule_name="cat rule",
            )
            # Then
            assert result == (False, HistoricalSpendRuleResults.MAVEN_ERROR)

    @pytest.mark.parametrize(
        "entries_data, expected_output_data",
        [
            # Test case 1: Single category with one entry
            (
                [
                    {
                        "category": "adoption",
                        "date_passed": datetime.datetime(2024, 12, 7),
                    },
                ],
                {
                    "adoption": [
                        {
                            "category": "adoption",
                            "date_passed": datetime.datetime(2024, 12, 7),
                        },
                    ],
                },
            ),
            # Test case 2: Single category with multiple entries sorted by created_at
            (
                [
                    {
                        "category": "adoption",
                        "date_passed": datetime.datetime(2024, 12, 8),
                    },
                    {
                        "category": "adoption",
                        "date_passed": datetime.datetime(2024, 12, 7),
                    },
                    {
                        "category": "adoption",
                        "date_passed": datetime.datetime(2024, 12, 6),
                    },
                ],
                {
                    "adoption": [
                        {
                            "category": "adoption",
                            "date_passed": datetime.datetime(2024, 12, 8),
                        },
                        {
                            "category": "adoption",
                            "date_passed": datetime.datetime(2024, 12, 7),
                        },
                        {
                            "category": "adoption",
                            "date_passed": datetime.datetime(2024, 12, 6),
                        },
                    ],
                },
            ),
            # Test case 3: Multiple categories, each with one entry
            (
                [
                    {
                        "category": "adoption",
                        "date_passed": datetime.datetime(2024, 12, 7),
                    },
                    {
                        "category": "childcare",
                        "date_passed": datetime.datetime(2024, 12, 8),
                    },
                    {
                        "category": "fertility",
                        "date_passed": datetime.datetime(2024, 12, 9),
                    },
                ],
                {
                    "adoption": [
                        {
                            "category": "adoption",
                            "date_passed": datetime.datetime(2024, 12, 7),
                        },
                    ],
                    "childcare": [
                        {
                            "category": "childcare",
                            "date_passed": datetime.datetime(2024, 12, 8),
                        },
                    ],
                    "fertility": [
                        {
                            "category": "fertility",
                            "date_passed": datetime.datetime(2024, 12, 9),
                        },
                    ],
                },
            ),
            # Test case 4: Multiple categories with multiple entries, sorted by created_at
            (
                [
                    {
                        "category": "adoption",
                        "date_passed": datetime.datetime(2024, 12, 8),
                    },
                    {
                        "category": "childcare",
                        "date_passed": datetime.datetime(2024, 12, 9),
                    },
                    {
                        "category": "adoption",
                        "date_passed": datetime.datetime(2024, 12, 7),
                    },
                    {
                        "category": "childcare",
                        "date_passed": datetime.datetime(2024, 12, 6),
                    },
                ],
                {
                    "adoption": [
                        {
                            "category": "adoption",
                            "date_passed": datetime.datetime(2024, 12, 8),
                        },
                        {
                            "category": "adoption",
                            "date_passed": datetime.datetime(2024, 12, 7),
                        },
                    ],
                    "childcare": [
                        {
                            "category": "childcare",
                            "date_passed": datetime.datetime(2024, 12, 9),
                        },
                        {
                            "category": "childcare",
                            "date_passed": datetime.datetime(2024, 12, 6),
                        },
                    ],
                },
            ),
            # Test case 5: Single category with multiple entries unsorted
            (
                [
                    {
                        "category": "adoption",
                        "date_passed": datetime.datetime(2024, 12, 7),
                    },
                    {
                        "category": "adoption",
                        "date_passed": datetime.datetime(2024, 12, 8),
                    },
                    {
                        "category": "adoption",
                        "date_passed": datetime.datetime(2024, 12, 6),
                    },
                ],
                {
                    "adoption": [
                        {
                            "category": "adoption",
                            "date_passed": datetime.datetime(2024, 12, 8),
                        },
                        {
                            "category": "adoption",
                            "date_passed": datetime.datetime(2024, 12, 7),
                        },
                        {
                            "category": "adoption",
                            "date_passed": datetime.datetime(2024, 12, 6),
                        },
                    ],
                },
            ),
            # Test case 6: No entries
            (
                [],
                {},
            ),
        ],
    )
    def test_create_category_map(
        self,
        ledger_entry,
        historical_spend_service,
        entries_data,
        expected_output_data,
    ):
        # given

        entries = [ledger_entry(**data) for data in entries_data]
        expected_output = {
            category: [ledger_entry(**entry) for entry in entry_list]
            for category, entry_list in expected_output_data.items()
        }
        # when
        result = historical_spend_service.create_category_map(entries)
        # then
        assert result.keys() == expected_output.keys()
        for category in result:
            assert result[category] == expected_output[category]


class TestProcessWalletQualificationEntries:
    def test_process_wallet_qualification_entries_multiple_entries_no_adjustment_id(
        self, ledger_entry, qualified_alegeus_wallet_hra, historical_spend_service
    ):
        # Given
        entries = [
            ledger_entry(category="fertility", adjustment_id=None),
            ledger_entry(category="fertility", adjustment_id=None),
        ]
        wallet_data_lookup = {
            ("JOHN", "DOE", entries[0].date_of_birth): qualified_alegeus_wallet_hra
        }

        with patch(
            "wallet.services.wallet_historical_spend.WalletHistoricalSpendService._process_entries"
        ) as mock_process_entries:
            mock_process_entries.return_value = []
            # When
            historical_spend_service._process_wallet_qualification_entries(
                wallet_ledger_entries=entries,
                wallet_data_lookup=wallet_data_lookup,
                messages=[],
                reimbursement_organization_settings_id=qualified_alegeus_wallet_hra.reimbursement_organization_settings.id,
            )
            # Then: Assert only one entry processed with the original amount and other with 0
            assert mock_process_entries.call_count == 2
            mock_process_entries.assert_has_calls(
                [
                    call(
                        entries=[entries[0]],  # The most recent entry
                        wallet_data_lookup=wallet_data_lookup,
                        messages=[],
                        file_id=None,
                        reimbursement_organization_settings_id=qualified_alegeus_wallet_hra.reimbursement_organization_settings.id,
                    ),
                    call(  # Second call with override amount of 0
                        entries=[entries[1]],
                        wallet_data_lookup=wallet_data_lookup,
                        messages=[],
                        file_id=None,
                        reimbursement_organization_settings_id=qualified_alegeus_wallet_hra.reimbursement_organization_settings.id,
                        override_amount=0,
                    ),
                ],
                any_order=False,
            )

    def test_process_wallet_qualification_entries_multiple_entries_with_adjustment_id(
        self, ledger_entry, qualified_alegeus_wallet_hra, historical_spend_service
    ):
        # Given
        entries = [
            ledger_entry(category="fertility", adjustment_id="123"),
            ledger_entry(category="fertility", adjustment_id="456"),
        ]
        wallet_data_lookup = {  # Example wallet data lookup for testing
            ("JOHN", "DOE", entries[0].date_of_birth): qualified_alegeus_wallet_hra
        }

        with patch(
            "wallet.services.wallet_historical_spend.WalletHistoricalSpendService._process_entries"
        ) as mock_process_entries:
            mock_process_entries.return_value = []
            # When
            historical_spend_service._process_wallet_qualification_entries(
                wallet_ledger_entries=entries,
                wallet_data_lookup=wallet_data_lookup,
                messages=[],
                reimbursement_organization_settings_id=qualified_alegeus_wallet_hra.reimbursement_organization_settings.id,
            )
            mock_process_entries.assert_not_called()

    def test_process_wallet_qualification_entries_multiple_entries_mixed_adjustment_id(
        self, ledger_entry, qualified_alegeus_wallet_hra, historical_spend_service
    ):
        # Given
        entries = [
            ledger_entry(
                category="fertility", adjustment_id=None
            ),  # processed with historical spend
            ledger_entry(
                category="adoption", adjustment_id=None
            ),  # Skipped because of other adj id
            ledger_entry(
                category="fertility", adjustment_id=None
            ),  # processed as 0 spend
            ledger_entry(
                category="adoption", adjustment_id="456"
            ),  # Skipped because of adj id
            ledger_entry(
                category="preservation", adjustment_id="123"
            ),  # Skipped because of adj id
        ]
        wallet_data_lookup = {
            ("JOHN", "DOE", entries[0].date_of_birth): qualified_alegeus_wallet_hra
        }
        with patch(
            "wallet.services.wallet_historical_spend.WalletHistoricalSpendService._process_entries"
        ) as mock_process_entries:
            mock_process_entries.return_value = []
            # When
            historical_spend_service._process_wallet_qualification_entries(
                wallet_ledger_entries=entries,
                wallet_data_lookup=wallet_data_lookup,
                messages=[],
                reimbursement_organization_settings_id=qualified_alegeus_wallet_hra.reimbursement_organization_settings.id,
            )
            # Then
            assert mock_process_entries.call_count == 2
            mock_process_entries.assert_has_calls(
                [
                    call(
                        entries=[
                            entries[0]
                        ],  # The most recent entry without adjustment_id
                        wallet_data_lookup=wallet_data_lookup,
                        messages=[],
                        file_id=None,
                        reimbursement_organization_settings_id=qualified_alegeus_wallet_hra.reimbursement_organization_settings.id,
                    ),
                    call(  # Second call with override amount of 0
                        entries=[entries[2]],
                        wallet_data_lookup=wallet_data_lookup,
                        messages=[],
                        file_id=None,
                        reimbursement_organization_settings_id=qualified_alegeus_wallet_hra.reimbursement_organization_settings.id,
                        override_amount=0,
                    ),
                ],
                any_order=False,
            )
