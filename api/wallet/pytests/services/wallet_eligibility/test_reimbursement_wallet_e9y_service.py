from datetime import date, datetime, timedelta
from unittest import mock
from unittest.mock import ANY, MagicMock, patch

import pytest
from requests import Response
from sqlalchemy.exc import SQLAlchemyError

from pytests.factories import AddressFactory
from wallet.constants import MAVEN_ADDRESS
from wallet.models.constants import (
    ChangeType,
    ReimbursementRequestState,
    ReimbursementRequestType,
    SyncIndicator,
    WalletState,
    WalletUserStatus,
)
from wallet.models.reimbursement import ReimbursementClaim
from wallet.models.reimbursement_organization_settings import (
    ReimbursementOrganizationSettings,
    ReimbursementOrgSettingCategoryAssociation,
)
from wallet.models.reimbursement_wallet import (
    ReimbursementWalletAllowedCategorySettings,
)
from wallet.models.reimbursement_wallet_user import ReimbursementWalletUsers
from wallet.pytests.factories import ReimbursementOrganizationSettingsFactory
from wallet.services import reimbursement_wallet_e9y_service
from wallet.services.currency import DEFAULT_CURRENCY_CODE
from wallet.services.reimbursement_wallet_e9y_service import (
    ReimbursementWalletEligibilitySyncMeta,
)


@pytest.fixture
def wallet_eligibility_service(db):
    return reimbursement_wallet_e9y_service.WalletEligibilityService(db)


@pytest.fixture
def mock_alegeus_api():
    return MagicMock()


@pytest.fixture
def wallet_eligibility_service_with_mocks(db, mock_alegeus_api):
    service = reimbursement_wallet_e9y_service.WalletEligibilityService(db)
    service.alegeus_api = mock_alegeus_api
    return service


def test_set_wallet_to_runout(
    wallet_eligibility_service, mock_wallet, mock_eligibility_record, session
):
    with patch.object(
        wallet_eligibility_service.alegeus_api, "update_employee_termination_date"
    ) as mock_update_employee_termination_date, patch.object(
        wallet_eligibility_service, "get_user_address", return_value=None
    ) as mock_get_address:
        mock_response = MagicMock()
        mock_response.ok = True
        mock_response.status_code = 200
        mock_update_employee_termination_date.return_value = mock_response

        sync_meta = wallet_eligibility_service.set_wallet_to_runout(
            mock_wallet, mock_eligibility_record, session
        )

        assert mock_wallet.state == WalletState.RUNOUT
        assert sync_meta.change_type == ChangeType.RUNOUT

        mock_get_address.assert_called_once_with(
            mock_wallet.employee_member.id, session
        )
        mock_update_employee_termination_date.assert_called_once_with(
            mock_wallet, ANY, None
        )


def test_set_wallet_to_runout_us_member(
    wallet_eligibility_service, mock_wallet, mock_eligibility_record, session
):
    # Given
    mock_response = MagicMock()
    mock_response.ok = True
    mock_response.status_code = 200
    mock_wallet.get_first_name_last_name_and_dob.return_value = [
        "John",
        "Doe",
        "1980-01-01",
    ]

    mock_address = AddressFactory.create()

    expected_request_body = {
        "Address1": mock_address.street_address,
        "City": mock_address.city,
        "Country": mock_address.country,
        "EmployeeId": ANY,
        "EmployerId": ANY,
        "FirstName": "John",
        "LastName": "Doe",
        "State": mock_address.state,
        "ZipCode": mock_address.zip_code,
        "TpaId": ANY,
        "EmployeeStatus": "Active",
        "NoOverwrite": True,
        "TerminationDate": ANY,
    }

    with mock.patch(
        "wallet.alegeus_api.AlegeusApi.make_api_request"
    ) as mock_make_api_request, mock.patch(
        "wallet.services.reimbursement_wallet_e9y_service.WalletEligibilityService.get_user_address"
    ) as mock_get_user_address:
        mock_make_api_request.return_value = mock_response
        mock_get_user_address.return_value = mock_address
        # When
        _ = wallet_eligibility_service.set_wallet_to_runout(
            mock_wallet, mock_eligibility_record, session
        )

    # Then
    mock_make_api_request.assert_called_once_with(
        ANY, api_version="1.1", data=expected_request_body, method="PUT"
    )


def test_set_wallet_to_runout_international_member(
    wallet_eligibility_service, mock_wallet, mock_eligibility_record, session
):
    # Given
    mock_response = MagicMock()
    mock_response.ok = True
    mock_response.status_code = 200
    mock_wallet.get_first_name_last_name_and_dob.return_value = [
        "John",
        "Doe",
        "1980-01-01",
    ]

    mock_address = AddressFactory.create(country="GB")

    expected_request_body = {
        "Address1": MAVEN_ADDRESS.get("address_1"),
        "City": MAVEN_ADDRESS.get("city"),
        "Country": MAVEN_ADDRESS.get("country"),
        "EmployeeId": ANY,
        "EmployerId": ANY,
        "FirstName": "John",
        "LastName": "Doe",
        "State": MAVEN_ADDRESS.get("state"),
        "ZipCode": MAVEN_ADDRESS.get("zip"),
        "TpaId": ANY,
        "EmployeeStatus": "Active",
        "NoOverwrite": True,
        "TerminationDate": ANY,
    }

    with mock.patch(
        "wallet.alegeus_api.AlegeusApi.make_api_request"
    ) as mock_make_api_request, mock.patch(
        "wallet.services.reimbursement_wallet_e9y_service.WalletEligibilityService.get_user_address"
    ) as mock_get_user_address:
        mock_make_api_request.return_value = mock_response
        mock_get_user_address.return_value = mock_address
        # When
        _ = wallet_eligibility_service.set_wallet_to_runout(
            mock_wallet, mock_eligibility_record, session
        )

    # Then
    mock_make_api_request.assert_called_once_with(
        ANY, api_version="1.1", data=expected_request_body, method="PUT"
    )


def test_change_wallet_ros(
    wallet_eligibility_service, mock_wallet, mock_eligibility_record, session
):
    new_ros = MagicMock(spec=ReimbursementOrganizationSettings)
    new_ros.id = 2
    with patch.object(
        wallet_eligibility_service, "create_sync_meta"
    ) as mock_create_sync_meta, patch.object(
        wallet_eligibility_service, "update_category_settings"
    ) as mock_update_category_settings, patch.object(
        wallet_eligibility_service, "notify_payment_ops_of_ros_change"
    ) as mock_notify_payment_ops_of_ros_change:

        expected_sync_meta = ReimbursementWalletEligibilitySyncMeta(
            wallet_id=1,
            sync_time=datetime.utcnow(),
            sync_initiator=SyncIndicator.CRON_JOB,
            change_type=ChangeType.ROS_CHANGE,
            previous_end_date=None,
            latest_end_date=datetime(2023, 12, 31),
            previous_ros_id=1,
            latest_ros_id=2,
            user_id=100,
        )
        expected_sync_meta.dependents_ids = []
        mock_create_sync_meta.return_value = expected_sync_meta

        # Act
        result = wallet_eligibility_service.change_wallet_ros(
            mock_wallet, new_ros, mock_eligibility_record, session
        )

        # Assert
        assert result == expected_sync_meta
        mock_create_sync_meta.assert_called_once_with(
            mock_wallet,
            ChangeType.ROS_CHANGE,
            mock_eligibility_record,
            new_ros=new_ros,
            old_ros_id=1,
            sync_indicator=SyncIndicator.CRON_JOB,
        )
        mock_update_category_settings.assert_called_once_with(
            mock_wallet, 1, 2, session
        )
        mock_notify_payment_ops_of_ros_change.assert_called_once_with(mock_wallet, 1, 2)


def test_remove_user_access(wallet_eligibility_service, mock_wallet, session):
    mock_user = MagicMock()
    mock_user.id = 200
    mock_wallet_user = MagicMock(spec=ReimbursementWalletUsers)
    mock_wallet_user.status = WalletUserStatus.ACTIVE
    mock_wallet_user.wallet = mock_wallet
    # Mock the query chain
    mock_query = MagicMock()
    mock_query.join.return_value.filter.return_value.first.return_value = (
        mock_wallet_user
    )

    session.query = MagicMock(return_value=mock_query)
    wallet_eligibility_service.remove_user_access(mock_wallet, mock_user, session)

    assert mock_wallet_user.status == WalletUserStatus.REVOKED
    session.query.assert_called_once_with(ReimbursementWalletUsers)
    mock_query.join.return_value.filter.return_value.first.assert_called_once()


@patch("wallet.services.reimbursement_wallet_e9y_service.get_verification_service")
def test_get_ros_for_user(
    mock_get_verification_service,
    wallet_eligibility_service,
    mock_eligibility_record,
    session,
):
    mock_sub_population_id = 123
    mock_ros_id = 456
    mock_ros = MagicMock(spec=ReimbursementOrganizationSettings)

    # Mock e9y service methods
    mock_e9y_service = MagicMock()
    mock_get_verification_service.return_value = mock_e9y_service
    mock_e9y_service.get_sub_population_id_for_user_and_org.return_value = (
        mock_sub_population_id
    )
    mock_e9y_service.get_eligible_features_by_sub_population_id.return_value = [
        mock_ros_id
    ]
    wallet_eligibility_service.e9y_service = mock_e9y_service

    mock_query = MagicMock()
    mock_query.get.return_value = mock_ros
    session.query = MagicMock(return_value=mock_query)

    result = wallet_eligibility_service.get_ros_for_user(
        mock_eligibility_record, session
    )

    assert result == mock_ros
    session.query.assert_called_once_with(ReimbursementOrganizationSettings)


def test_get_ros_for_user_no_record(wallet_eligibility_service, session):
    result = wallet_eligibility_service.get_ros_for_user(None, session)

    assert result is None


@patch("wallet.services.reimbursement_wallet_e9y_service.get_verification_service")
def test_get_ros_for_user_no_org_record(
    mock_get_verification_service,
    wallet_eligibility_service,
    mock_eligibility_record,
    session,
):
    # Mock the query chain to return None
    mock_query = MagicMock()
    mock_query.filter.return_value.one_or_none.return_value = None
    mock_e9y_service = MagicMock()
    mock_get_verification_service.return_value = mock_e9y_service
    mock_e9y_service.get_sub_population_id_for_user_and_org.return_value = None
    wallet_eligibility_service.e9y_service = mock_e9y_service

    session.query = MagicMock(return_value=mock_query)

    result = wallet_eligibility_service.get_ros_for_user(
        mock_eligibility_record, session
    )

    assert result is None


@patch(
    "wallet.services.reimbursement_wallet_e9y_service.NoEligibilityPaymentOpsZendeskTicket"
)
def test_escalate_eligibility_issue_to_payment_ops(
    mock_zendesk_ticket, wallet_eligibility_service, mock_wallet
):
    mock_zendesk_ticket.return_value.update_zendesk.return_value = None

    wallet_eligibility_service.escalate_eligibility_issue_to_payment_ops(
        mock_wallet, "Test reason"
    )

    assert mock_zendesk_ticket.called
    assert mock_zendesk_ticket.return_value.update_zendesk.called


@patch("wallet.services.reimbursement_wallet_e9y_service.get_verification_service")
def test_process_wallet_no_employee(
    mock_get_verification_service, wallet_eligibility_service, mock_wallet
):
    mock_wallet.employee_member = None

    result = wallet_eligibility_service.process_wallet(mock_wallet)

    assert result is None
    assert not mock_get_verification_service.called


@patch("wallet.services.reimbursement_wallet_e9y_service.get_verification_service")
def test_process_wallet_no_eligibility_record(
    mock_get_verification_service, wallet_eligibility_service, mock_wallet
):
    mock_e9y_service = MagicMock()
    mock_get_verification_service.return_value = mock_e9y_service
    mock_e9y_service.get_verification_for_user_and_org.return_value = None
    wallet_eligibility_service.e9y_service = mock_e9y_service

    with patch.object(
        wallet_eligibility_service, "escalate_eligibility_issue_to_payment_ops"
    ) as mock_escalate:
        result = wallet_eligibility_service.process_wallet(mock_wallet)

    assert result is None
    assert mock_escalate.called


@patch("wallet.services.reimbursement_wallet_e9y_service.get_verification_service")
def test_process_wallet_runout(
    mock_get_verification_service,
    wallet_eligibility_service,
    mock_wallet,
    mock_eligibility_record,
    session,
):
    mock_eligibility_record.effective_range.upper = date.today() - timedelta(days=1)
    # Create a mock for the EnterpriseVerificationService
    mock_e9y_service = MagicMock()
    mock_get_verification_service.return_value = mock_e9y_service
    mock_e9y_service.get_verification_for_user_and_org.return_value = (
        mock_eligibility_record
    )
    wallet_eligibility_service.e9y_service = mock_e9y_service
    session.add = MagicMock()
    session.commit = MagicMock()
    with patch.object(
        wallet_eligibility_service, "set_wallet_to_runout", return_value=MagicMock()
    ) as mock_set_runout, patch.object(
        wallet_eligibility_service, "is_wallet_blacklisted", return_value=False
    ), patch.object(
        wallet_eligibility_service,
        "_fresh_session",
        return_value=MagicMock(
            __enter__=lambda _: session, __exit__=lambda *args: None
        ),
    ):
        result = wallet_eligibility_service.process_wallet(mock_wallet)

    assert mock_set_runout.called
    assert result == mock_set_runout.return_value


@patch("wallet.services.reimbursement_wallet_e9y_service.get_verification_service")
def test_process_wallet_change_ros(
    mock_get_verification_service,
    wallet_eligibility_service,
    mock_wallet,
    mock_eligibility_record,
    session,
):
    mock_e9y_service = MagicMock()
    mock_get_verification_service.return_value = mock_e9y_service
    mock_e9y_service.get_verification_for_user_and_org.return_value = (
        mock_eligibility_record
    )
    wallet_eligibility_service.e9y_service = mock_e9y_service

    new_ros = MagicMock(spec=ReimbursementOrganizationSettings)
    new_ros.id = 2
    session.add = MagicMock()
    session.commit = MagicMock()

    with patch.object(
        wallet_eligibility_service, "get_ros_for_user", return_value=new_ros
    ), patch.object(
        wallet_eligibility_service, "change_wallet_ros"
    ) as mock_change_ros, patch.object(
        wallet_eligibility_service, "process_dependent_users", return_value=[]
    ), patch.object(
        wallet_eligibility_service,
        "_fresh_session",
        return_value=MagicMock(
            __enter__=lambda *_: session, __exit__=lambda *args: None
        ),
    ):
        result = wallet_eligibility_service.process_wallet(mock_wallet)

    assert mock_change_ros.called
    assert result == mock_change_ros.return_value


@patch("wallet.services.reimbursement_wallet_e9y_service.get_verification_service")
@patch(
    "wallet.services.reimbursement_wallet_e9y_service.WalletEligibilityService.escalate_eligibility_issue_to_payment_ops"
)
def test_process_wallet_no_changes(
    mock_escalate_to_ops,
    mock_get_verification_service,
    wallet_eligibility_service,
    mock_wallet,
    mock_eligibility_record,
):
    mock_e9y_service = MagicMock()
    mock_e9y_service.get_verification_for_user_and_org.return_value = (
        mock_eligibility_record
    )
    mock_get_verification_service.return_value = mock_e9y_service
    current_ros = MagicMock(spec=ReimbursementOrganizationSettings)
    current_ros.id = mock_wallet.reimbursement_organization_settings_id

    with patch.object(
        wallet_eligibility_service, "get_ros_for_user", return_value=current_ros
    ), patch.object(
        wallet_eligibility_service, "process_dependent_users", return_value=[]
    ):
        result = wallet_eligibility_service.process_wallet(mock_wallet)

    assert result is None


@patch("wallet.services.reimbursement_wallet_e9y_service.get_verification_service")
def test_process_dependent_users(
    mock_get_verification_service, wallet_eligibility_service, mock_wallet, session
):
    mock_employee = MagicMock()
    mock_employee.id = 100
    mock_dependent1 = MagicMock()
    mock_dependent1.id = 101
    mock_dependent2 = MagicMock()
    mock_dependent2.id = 102

    associated_users = [mock_employee, mock_dependent1, mock_dependent2]

    # Create a mock for the EnterpriseVerificationService
    mock_e9y_service = MagicMock()
    mock_get_verification_service.return_value = mock_e9y_service

    mock_e9y_service.get_verification_for_user_and_org.side_effect = [
        MagicMock(
            effective_range=MagicMock(upper=date.today() + timedelta(days=30))
        ),  # Valid for dependent1
        None,  # No record for dependent2
    ]

    # Replace the e9y_service on the wallet_eligibility_service instance
    wallet_eligibility_service.e9y_service = mock_e9y_service

    with patch.object(
        wallet_eligibility_service, "remove_user_access"
    ) as mock_remove_access:
        changes = wallet_eligibility_service.process_dependent_users(
            mock_wallet, associated_users, mock_employee, session
        )

    assert len(changes) == 1
    assert changes == [(102, "access_removed")]
    mock_remove_access.assert_called_once_with(mock_wallet, mock_dependent2, session)

    # Verify that get_verification_for_user_and_org was called twice
    assert mock_e9y_service.get_verification_for_user_and_org.call_count == 2


@patch(
    "wallet.services.reimbursement_wallet_e9y_service.WalletEligibilityService.get_or_create_categories_by_ros_id"
)
@patch(
    "wallet.services.reimbursement_wallet_e9y_service.WalletEligibilityService.get_categories_for_wallet"
)
@patch(
    "wallet.services.reimbursement_wallet_e9y_service.WalletEligibilityService.get_expense_types"
)
@patch(
    "wallet.services.reimbursement_wallet_e9y_service.WalletEligibilityService.get_spent_amount"
)
@patch(
    "wallet.services.reimbursement_wallet_e9y_service.WalletEligibilityService.get_alegeus_plan"
)
@patch(
    "wallet.services.reimbursement_wallet_e9y_service.WalletEligibilityService.update_internal_balance"
)
@patch(
    "wallet.services.reimbursement_wallet_e9y_service.WalletEligibilityService.create_claim"
)
@patch(
    "wallet.services.reimbursement_wallet_e9y_service.WalletEligibilityService.is_wallet_mmb_gold"
)
@patch(
    "wallet.services.reimbursement_wallet_e9y_service.WalletEligibilityService.get_matching_alegeus_categories"
)
def test_update_category_settings_no_alegeus_update(
    mock_matching_categories,
    mock_is_mmb_gold,
    mock_create_claim,
    mock_update_internal,
    mock_get_alegeus_plan,
    mock_get_spent_amount,
    mock_get_expense_types,
    mock_get_categories_for_wallet,
    mock_get_or_create_categories_by_ros_id,
    wallet_eligibility_service,
    mock_wallet,
    session,
):
    old_ros_id = 1
    new_ros_id = 2

    old_ros = MagicMock(spec=ReimbursementOrganizationSettings)
    old_ros.id = old_ros_id
    new_ros = MagicMock(spec=ReimbursementOrganizationSettings)
    new_ros.id = new_ros_id

    old_category1 = MagicMock(spec=ReimbursementOrgSettingCategoryAssociation)
    old_category1.reimbursement_organization_settings_id = 1
    old_category1.reimbursement_request_category_id = 1
    old_category2 = MagicMock(spec=ReimbursementOrgSettingCategoryAssociation)
    old_category2.reimbursement_organization_settings_id = 1
    old_category2.reimbursement_request_category_id = 2

    new_category = MagicMock(spec=ReimbursementOrgSettingCategoryAssociation)
    new_category.reimbursement_organization_settings_id = 2
    new_category.reimbursement_request_category_id = 3

    mock_query, mock_expire = MagicMock(), MagicMock()
    mock_query.get.side_effect = [old_ros, new_ros]

    session.query = mock_query
    session.expire = mock_expire

    def mock_get_or_create_categories_func(mock_wallet, ros_id=1):
        categories = {
            1: [old_category1, old_category2],
            2: [new_category],
        }
        return categories.get(ros_id, [])

    def mock_get_categories_for_wallet_func(mock_wallet):
        categories = {
            1: [old_category1, old_category2],
            2: [new_category],
        }
        return categories.get(mock_wallet.reimbursement_organization_settings_id, [])

    mock_get_or_create_categories_by_ros_id.side_effect = (
        mock_get_or_create_categories_func
    )
    mock_get_categories_for_wallet.side_effect = mock_get_categories_for_wallet_func

    def mock_get_expense_types_func(category_id, session):
        expense_types = {
            1: ["FERTILITY"],
            2: ["ADOPTION"],
            3: ["FERTILITY", "ADOPTION"],
        }
        return expense_types.get(category_id, [])

    def mock_matching_category_func(a, b, session):
        return []

    mock_get_expense_types.side_effect = mock_get_expense_types_func
    mock_matching_categories.side_effect = mock_matching_category_func

    # Mock spent amounts
    def mock_get_spent_amount_func(wallet, category):
        spent_amounts = {1: 1000, 2: 2000, 3: 0}
        return spent_amounts.get(category.reimbursement_request_category_id, 0)

    mock_get_spent_amount.side_effect = mock_get_spent_amount_func

    def mock_get_alegeus_plan_id_func(category, session):
        plan_ids = {1: "plan1", 2: "plan1", 3: "plan2"}
        return plan_ids.get(category.reimbursement_request_category_id, "unknown")

    mock_get_alegeus_plan.side_effect = mock_get_alegeus_plan_id_func
    mock_reimbursement_claim = MagicMock(spec=ReimbursementClaim)
    mock_reimbursement_claim.alegeus_claim_id = "test_claim"
    mock_create_claim.return_value = mock_reimbursement_claim

    mock_is_mmb_gold.side_effect = [False, True]

    wallet_eligibility_service.update_category_settings(
        mock_wallet, old_ros_id, new_ros_id, session
    )
    # Verify that get_expense_types was called for each category
    assert mock_get_expense_types.call_count == 3

    # Verify that get_spent_amount was called for overlapping categories
    assert mock_get_spent_amount.call_count == 2

    # Verify that get_alegeus_plan_id was not called since there were two categories overlap
    assert mock_get_alegeus_plan.call_count == 3

    # Verify that update_internal_balance was not called (since we called Alegeus)
    mock_update_internal.assert_called_once_with(
        mock_wallet, new_category, 3000, session=session
    )


def test_process_wallet_sql_alchemy_error(
    wallet_eligibility_service_with_mocks, mock_wallet, mock_eligibility_record, session
):
    with patch.object(
        session,
        "commit",
        side_effect=SQLAlchemyError("Test error"),
    ):
        result = wallet_eligibility_service_with_mocks.process_wallet(mock_wallet)
        assert result is None


def test_process_wallet_unexpected_error(
    wallet_eligibility_service_with_mocks, mock_wallet, mock_eligibility_record
):
    with patch.object(
        wallet_eligibility_service_with_mocks,
        "get_ros_for_user",
        side_effect=Exception("Unexpected error"),
    ):
        result = wallet_eligibility_service_with_mocks.process_wallet(mock_wallet)
        assert result is None


def test_update_category_settings_overlap_single_category_same_alegeus_plan(
    wallet_eligibility_service_with_mocks, mock_wallet, session
):
    old_ros_id = 1
    new_ros_id = 2
    resp = MagicMock(spec=Response)
    resp.status_code = 200

    wallet_eligibility_service_with_mocks.alegeus_api.terminate_employee_account.side_effect = [
        resp,
        resp,
    ]
    old_ros = MagicMock(spec=ReimbursementOrganizationSettings)
    old_ros.id = old_ros_id
    new_ros = MagicMock(spec=ReimbursementOrganizationSettings)
    new_ros.id = new_ros_id

    old_category = MagicMock(reimbursement_request_category_id=1)
    new_category = MagicMock(reimbursement_request_category_id=2)

    mock_query, mock_expire = MagicMock(), MagicMock()
    mock_query.get.side_effect = [old_ros, new_ros]

    session.query = mock_query
    session.expire = mock_expire

    with patch.object(
        wallet_eligibility_service_with_mocks, "get_or_create_categories_by_ros_id"
    ) as mock_get_or_create_categories_by_ros_id, patch.object(
        wallet_eligibility_service_with_mocks, "get_categories_for_wallet"
    ) as mock_get_categories_for_wallet, patch.object(
        wallet_eligibility_service_with_mocks, "get_expense_types"
    ) as mock_get_expense_types, patch.object(
        wallet_eligibility_service_with_mocks, "get_spent_amount"
    ) as mock_get_spent_amount, patch.object(
        wallet_eligibility_service_with_mocks, "get_alegeus_plan"
    ) as mock_get_alegeus_plan, patch.object(
        wallet_eligibility_service_with_mocks, "update_internal_balance"
    ) as mock_update_internal, patch.object(
        wallet_eligibility_service_with_mocks, "is_wallet_mmb_gold"
    ) as mock_is_mmb_gold:
        mock_is_mmb_gold.side_effect = [False, True]
        mock_get_or_create_categories_by_ros_id.side_effect = [new_category]
        mock_get_categories_for_wallet.side_effect = [[old_category], [new_category]]
        mock_get_expense_types.side_effect = [["FERTILITY"], ["FERTILITY"]]
        mock_get_spent_amount.return_value = 1000
        mock_get_alegeus_plan.return_value = MagicMock(alegeus_plan_id="same_id")

        wallet_eligibility_service_with_mocks.update_category_settings(
            mock_wallet, old_ros_id, new_ros_id, session
        )

        mock_update_internal.assert_not_called()


def test_update_category_settings_overlap_single_category_different_alegeus_plan(
    wallet_eligibility_service_with_mocks, mock_wallet, session
):
    old_ros_id = 1
    new_ros_id = 2

    resp = MagicMock(spec=Response)
    resp.status_code = 200

    wallet_eligibility_service_with_mocks.alegeus_api.terminate_employee_account.side_effect = [
        resp,
        resp,
    ]

    old_ros = MagicMock(spec=ReimbursementOrganizationSettings)
    old_ros.id = old_ros_id
    new_ros = MagicMock(spec=ReimbursementOrganizationSettings)
    new_ros.id = new_ros_id

    old_category = MagicMock(reimbursement_request_category_id=1)
    new_category = MagicMock(reimbursement_request_category_id=2)

    mock_query, mock_expire = MagicMock(), MagicMock()
    mock_query.get.side_effect = [old_ros, new_ros]

    mock_reimburse_request = MagicMock()
    mock_reimbursement_claim = MagicMock(spec=ReimbursementClaim)
    mock_reimbursement_claim.alegeus_claim_id = "test_claim"

    session.query = mock_query
    session.expire = mock_expire

    with patch.object(
        wallet_eligibility_service_with_mocks, "get_or_create_categories_by_ros_id"
    ) as mock_get_or_create_categories_by_ros_id, patch.object(
        wallet_eligibility_service_with_mocks, "get_categories_for_wallet"
    ) as mock_get_categories_for_wallet, patch.object(
        wallet_eligibility_service_with_mocks, "get_expense_types"
    ) as mock_get_expense_types, patch.object(
        wallet_eligibility_service_with_mocks, "get_spent_amount"
    ) as mock_get_spent_amount, patch.object(
        wallet_eligibility_service_with_mocks, "get_alegeus_plan"
    ) as mock_get_alegeus_plan, patch.object(
        wallet_eligibility_service_with_mocks, "call_alegeus_for_adjustment"
    ) as mock_call_alegeus, patch.object(
        wallet_eligibility_service_with_mocks,
        "create_claim",
        return_value=mock_reimbursement_claim,
    ), patch.object(
        wallet_eligibility_service_with_mocks, "update_internal_balance"
    ) as mock_update_internal, patch.object(
        wallet_eligibility_service_with_mocks, "is_wallet_mmb_gold"
    ) as mock_is_mmb_gold, patch.object(
        wallet_eligibility_service_with_mocks, "get_matching_alegeus_categories"
    ) as mock_match_categories:
        mock_match_categories.return_value = []
        mock_is_mmb_gold.side_effect = [False, True]
        mock_update_internal.return_value = mock_reimburse_request
        mock_get_or_create_categories_by_ros_id.side_effect = [[new_category]]
        mock_get_categories_for_wallet.side_effect = [[old_category], [new_category]]
        mock_get_expense_types.side_effect = [["FERTILITY"], ["FERTILITY"]]
        mock_get_spent_amount.return_value = 1000
        mock_get_alegeus_plan.side_effect = [
            MagicMock(alegeus_plan_id="old_id"),
            MagicMock(alegeus_plan_id="new_id"),
            MagicMock(alegeus_plan_id="old_id"),
        ]

        wallet_eligibility_service_with_mocks.update_category_settings(
            mock_wallet, old_ros_id, new_ros_id, session
        )

        mock_call_alegeus.assert_called_once_with(
            mock_wallet, new_category, mock_reimburse_request, 1000, session=session
        )


@patch(
    "wallet.services.reimbursement_wallet_e9y_service.WalletEligibilityService.get_category_expense_type_map"
)
def test_update_category_settings_green_to_gold(
    mock_get_category_expense_type_map,
    session,
    wallet_eligibility_service_with_mocks,
    non_dp_wallet,
    configured_dp_currency_ros,
):
    """Test the Green -> Gold case gets past all the checks"""
    # When
    result = wallet_eligibility_service_with_mocks.update_category_settings(
        wallet=non_dp_wallet,
        old_ros_id=non_dp_wallet.reimbursement_organization_settings_id,
        new_ros_id=configured_dp_currency_ros.id,
        session=session,
    )
    allowed_category_settings = (
        session.query(ReimbursementWalletAllowedCategorySettings)
        .filter(
            ReimbursementWalletAllowedCategorySettings.reimbursement_wallet_id
            == non_dp_wallet.id
        )
        .all()
    )

    # Then
    # We persist the new categories
    assert allowed_category_settings
    assert result is True
    mock_get_category_expense_type_map.assert_called_once()


@patch(
    "wallet.services.reimbursement_wallet_e9y_service.WalletEligibilityService.escalate_eligibility_issue_to_payment_ops"
)
def test_update_category_settings_green_to_green(
    mock_escalate_to_ops,
    session,
    wallet_eligibility_service_with_mocks,
    non_dp_wallet,
    configured_another_non_dp_currency_ros,
):
    """Test the Green -> Green case exits early and raises ops ticket"""
    # When
    result = wallet_eligibility_service_with_mocks.update_category_settings(
        wallet=non_dp_wallet,
        old_ros_id=non_dp_wallet.reimbursement_organization_settings_id,
        new_ros_id=configured_another_non_dp_currency_ros.id,
        session=session,
    )

    # Then
    assert result is False
    mock_escalate_to_ops.assert_called_once_with(
        non_dp_wallet,
        "Got a carry over case we can't handle - wallet with new ROS is not MMB wallet, still traditional",
    )


@patch(
    "wallet.services.reimbursement_wallet_e9y_service.WalletEligibilityService.escalate_eligibility_issue_to_payment_ops"
)
def test_update_category_settings_gold_to_green(
    mock_escalate_to_ops,
    session,
    wallet_eligibility_service_with_mocks,
    wallet_cycle_based,
    configured_another_non_dp_currency_ros,
):
    """Test the Gold -> Green case exits early and raises ops ticket"""
    # When
    result = wallet_eligibility_service_with_mocks.update_category_settings(
        wallet=wallet_cycle_based,
        old_ros_id=wallet_cycle_based.reimbursement_organization_settings_id,
        new_ros_id=configured_another_non_dp_currency_ros.id,
        session=session,
    )

    # Then
    assert result is False
    mock_escalate_to_ops.assert_called_once_with(
        wallet_cycle_based,
        "Got a carry over case we can't handle - existing wallet is MMB wallet instead of traditional",
    )


@patch(
    "wallet.services.reimbursement_wallet_e9y_service.WalletEligibilityService.escalate_eligibility_issue_to_payment_ops"
)
def test_update_category_settings_gold_to_gold_no_cycle_currency_check_ff_off(
    mock_escalate_to_ops,
    session,
    wallet_eligibility_service_with_mocks,
    wallet_cycle_based,
    configured_dp_currency_ros,
    ff_test_data,
):
    """
    Test the Gold -> Gold case with feature flag on
    Should fallthrough to the other checks for now
    """
    # Given
    ff_test_data.update(
        ff_test_data.flag("wallet-amazon-cycle-currency-switch").variation_for_all(
            False
        )
    )

    # When
    result = wallet_eligibility_service_with_mocks.update_category_settings(
        wallet=wallet_cycle_based,
        old_ros_id=wallet_cycle_based.reimbursement_organization_settings_id,
        new_ros_id=configured_dp_currency_ros.id,
        session=session,
    )

    # Then
    assert result is False
    mock_escalate_to_ops.assert_called_once_with(
        wallet_cycle_based,
        "Got a carry over case we can't handle - existing wallet is MMB wallet instead of traditional",
    )


def test_update_category_settings_gold_to_gold_no_cycle_currency_check_ff_on(
    session,
    wallet_eligibility_service_with_mocks,
    wallet_cycle_based,
    configured_dp_currency_ros,
    ff_test_data,
):
    """
    Test the Gold -> Gold case with feature flag on
    Should fallthrough to the other checks for now
    """
    # Given
    ff_test_data.update(
        ff_test_data.flag("wallet-amazon-cycle-currency-switch").variation_for_all(True)
    )
    mock_success_response = MagicMock(spec=Response)
    mock_success_response.status_code = 200
    wallet_eligibility_service_with_mocks.alegeus_api.terminate_employee_account.return_value = (
        mock_success_response
    )
    wallet_eligibility_service_with_mocks.alegeus_api.post_add_employee_account.return_value = (
        mock_success_response
    )

    # When
    with mock.patch(
        "wallet.services.reimbursement_wallet_benefit_type_converter.configure_account"
    ) as mock_configure_account:
        mock_configure_account.return_value = True, None
        result = wallet_eligibility_service_with_mocks.update_category_settings(
            wallet=wallet_cycle_based,
            old_ros_id=wallet_cycle_based.reimbursement_organization_settings_id,
            new_ros_id=configured_dp_currency_ros.id,
            session=session,
        )

    # Then
    assert result is True


@patch("wallet.services.reimbursement_wallet_e9y_service.get_verification_service")
def test_process_dependent_users_mixed_eligibility(
    mock_get_verification_service,
    wallet_eligibility_service_with_mocks,
    mock_wallet,
    session,
):
    employee = MagicMock(id=1)
    dependent1 = MagicMock(id=2)
    dependent2 = MagicMock(id=3)
    associated_users = [employee, dependent1, dependent2]

    eligibility_record1 = MagicMock(
        effective_range=MagicMock(upper=date.today() + timedelta(days=30))
    )
    eligibility_record2 = MagicMock(
        effective_range=MagicMock(upper=date.today() - timedelta(days=1))
    )

    # Create a mock for the EnterpriseVerificationService
    mock_e9y_service = MagicMock()
    mock_get_verification_service.return_value = mock_e9y_service

    mock_e9y_service.get_verification_for_user_and_org.side_effect = [
        eligibility_record1,
        eligibility_record2,
    ]

    # Replace the e9y_service on the wallet_eligibility_service instance
    wallet_eligibility_service_with_mocks.e9y_service = mock_e9y_service

    with patch.object(
        wallet_eligibility_service_with_mocks, "remove_user_access"
    ) as mock_remove_access:
        changes = wallet_eligibility_service_with_mocks.process_dependent_users(
            mock_wallet, associated_users, employee, session
        )

        assert len(changes) == 1
        assert changes[0] == (3, "access_removed")
        mock_remove_access.assert_called_once_with(mock_wallet, dependent2, session)


def test_call_alegeus_for_adjustment(
    wallet_eligibility_service_with_mocks, mock_wallet, session
):
    new_category = MagicMock()
    amount = 1000
    plan = MagicMock()
    mock_reimburse_request = MagicMock()
    mock_reimburse_request.service_start_date = datetime.today().date()
    mock_reimbursement_claim = MagicMock(spec=ReimbursementClaim)
    mock_reimbursement_claim.alegeus_claim_id = "test_claim"

    with patch.object(
        wallet_eligibility_service_with_mocks, "get_alegeus_plan", return_value=plan
    ), patch.object(
        wallet_eligibility_service_with_mocks,
        "create_claim",
        return_value=mock_reimbursement_claim,
    ), patch.object(
        wallet_eligibility_service_with_mocks, "validate_response"
    ) as mock_validate_response:
        wallet_eligibility_service_with_mocks.call_alegeus_for_adjustment(
            mock_wallet, new_category, mock_reimburse_request, amount, session=session
        )

        # Assert create_claim was called with correct arguments
        wallet_eligibility_service_with_mocks.create_claim.assert_called_once_with(
            mock_reimburse_request, mock_wallet, amount
        )

        # Assert post_adjust_plan_amount was called with correct arguments
        wallet_eligibility_service_with_mocks.alegeus_api.post_adjust_plan_amount.assert_called_once_with(
            wallet=mock_wallet,
            claim_id="test_claim",
            reimbursement_amount=amount,
            plan=plan,
            service_start_date=datetime.today().date(),
        )

        # Assert _validate_response was called
        mock_validate_response.assert_called_once()


def test_get_ros_for_user_no_eligibility_record(
    wallet_eligibility_service_with_mocks, session
):
    result = wallet_eligibility_service_with_mocks.get_ros_for_user(None, session)
    assert result is None


def test_create_sync_meta(
    wallet_eligibility_service_with_mocks, mock_wallet, mock_eligibility_record
):
    new_ros = MagicMock(id=2)
    sync_meta = wallet_eligibility_service_with_mocks.create_sync_meta(
        mock_wallet,
        ChangeType.ROS_CHANGE,
        mock_eligibility_record,
        new_ros=new_ros,
        sync_indicator=SyncIndicator.MANUAL,
    )

    assert sync_meta.wallet_id == mock_wallet.id
    assert sync_meta.sync_initiator == SyncIndicator.MANUAL
    assert sync_meta.change_type == ChangeType.ROS_CHANGE
    assert (
        sync_meta.previous_ros_id == mock_wallet.reimbursement_organization_settings_id
    )
    assert sync_meta.latest_ros_id == new_ros.id


def test_update_internal_balance(
    qualified_alegeus_wallet_hdhp_single, wallet_eligibility_service_with_mocks, session
):
    """Test that reimbursement request is created and all fields are properly populated"""
    # Given
    wallet_eligibility_service_with_mocks.dry_run = False
    category_association = (
        qualified_alegeus_wallet_hdhp_single.get_or_create_wallet_allowed_categories[0]
    )
    amount = 1_000_00  # $1,000.00

    # When
    reimbursement = wallet_eligibility_service_with_mocks.update_internal_balance(
        wallet=qualified_alegeus_wallet_hdhp_single,
        new_category=category_association,
        amount=amount,
        session=session,
    )

    # Then
    assert reimbursement.label == "historical spend adjustment"
    assert (
        reimbursement.description
        == "historical spend adjustment based on eligibility change"
    )
    assert reimbursement.service_provider == "historical spend adjustment"
    assert reimbursement.transaction_amount == amount
    assert reimbursement.transaction_currency_code == DEFAULT_CURRENCY_CODE
    assert reimbursement.amount == amount
    assert reimbursement.benefit_currency_code == DEFAULT_CURRENCY_CODE
    assert reimbursement.usd_amount == amount
    assert reimbursement.wallet == qualified_alegeus_wallet_hdhp_single
    assert reimbursement.category == category_association.reimbursement_request_category
    assert reimbursement.state == ReimbursementRequestState.REIMBURSED
    assert reimbursement.reimbursement_type == ReimbursementRequestType.MANUAL


def test_convert_benefit_type_is_valid_case(
    wallet_eligibility_service_with_mocks,
    wallet_cycle_based,
    cycle_based_category_association,
    currency_based_category_association,
    currency_shared_adoption_category_association,
    currency_shared_surrogacy_category_association,
    cycle_shared_adoption_category_association,
    cycle_shared_surrogacy_category_association,
    configured_dp_currency_ros,
):
    # Given

    # When
    conversion_categories = (
        wallet_eligibility_service_with_mocks.is_cycle_currency_conversion(
            wallet=wallet_cycle_based,
            old_categories=[
                cycle_based_category_association,
                cycle_shared_surrogacy_category_association,
                cycle_shared_adoption_category_association,
            ],
            new_categories=[
                currency_based_category_association,
                currency_shared_surrogacy_category_association,
                currency_shared_adoption_category_association,
            ],
        )
    )

    assert conversion_categories == (
        cycle_based_category_association,
        currency_based_category_association,
    )


def test_convert_benefit_type_is_valid_case_no_shared_categories(
    wallet_eligibility_service_with_mocks,
    wallet_cycle_based,
    cycle_based_category_association,
    currency_based_category_association,
    currency_shared_adoption_category_association,
    currency_shared_surrogacy_category_association,
    cycle_shared_adoption_category_association,
    cycle_shared_surrogacy_category_association,
    configured_dp_currency_ros,
):
    # Given

    # When
    conversion_categories = (
        wallet_eligibility_service_with_mocks.is_cycle_currency_conversion(
            wallet=wallet_cycle_based,
            old_categories=[
                cycle_based_category_association,
            ],
            new_categories=[
                currency_based_category_association,
            ],
        )
    )

    assert conversion_categories == (
        cycle_based_category_association,
        currency_based_category_association,
    )


def test_convert_benefit_type_missing_cycle_category(
    wallet_eligibility_service_with_mocks,
    wallet_cycle_based,
    cycle_based_category_association,
    currency_based_category_association,
    currency_shared_adoption_category_association,
    currency_shared_surrogacy_category_association,
    cycle_shared_adoption_category_association,
    cycle_shared_surrogacy_category_association,
    configured_dp_currency_ros,
):
    # Given

    # When
    conversion_categories = (
        wallet_eligibility_service_with_mocks.is_cycle_currency_conversion(
            wallet=wallet_cycle_based,
            old_categories=[
                cycle_shared_surrogacy_category_association,
                cycle_shared_adoption_category_association,
            ],
            new_categories=[
                currency_based_category_association,
                currency_shared_surrogacy_category_association,
                currency_shared_adoption_category_association,
            ],
        )
    )

    assert conversion_categories == (None, None)


def test_convert_benefit_type_missing_shared_category(
    wallet_eligibility_service_with_mocks,
    wallet_cycle_based,
    cycle_based_category_association,
    currency_based_category_association,
    currency_shared_adoption_category_association,
    currency_shared_surrogacy_category_association,
    cycle_shared_adoption_category_association,
    cycle_shared_surrogacy_category_association,
    configured_dp_currency_ros,
):
    # Given

    # When
    conversion_categories = (
        wallet_eligibility_service_with_mocks.is_cycle_currency_conversion(
            wallet=wallet_cycle_based,
            old_categories=[
                cycle_based_category_association,
                cycle_shared_surrogacy_category_association,
            ],
            new_categories=[
                currency_based_category_association,
                currency_shared_surrogacy_category_association,
                currency_shared_adoption_category_association,
            ],
        )
    )

    assert conversion_categories == (None, None)


class TestUndoSetWalletToRunout:
    @staticmethod
    @patch(
        "wallet.services.reimbursement_wallet_e9y_service.WalletEligibilityService.get_ros_for_user"
    )
    @patch(
        "eligibility.service.EnterpriseVerificationService.get_verification_for_user_and_org"
    )
    def test_undo_set_wallet_to_runout_success(
        mock_get_verification_for_user_and_org,
        mock_get_ros_for_user,
        wallet_eligibility_service_with_mocks,
        mock_eligibility_record,
        session,
        wallet_currency_based,
        enterprise_user,
    ):
        # Given
        wallet_currency_based.state = WalletState.RUNOUT
        wallet_currency_based.reimbursement_wallet_users[
            0
        ].status = WalletUserStatus.REVOKED

        # Mock e9y
        mock_get_verification_for_user_and_org.return_value = mock_eligibility_record
        mock_get_ros_for_user.return_value = (
            wallet_currency_based.reimbursement_organization_settings
        )

        # Mock Alegeus
        resp = MagicMock(spec=Response)
        resp.status_code = 200
        wallet_eligibility_service_with_mocks.alegeus_api.update_employee_termination_date.return_value = (
            resp
        )

        # When
        result = wallet_eligibility_service_with_mocks.undo_set_wallet_to_runout(
            wallet=wallet_currency_based, session=session
        )

        # Then
        assert result is True
        assert wallet_currency_based.state == WalletState.QUALIFIED
        assert (
            wallet_currency_based.reimbursement_wallet_users[0].status
            == WalletUserStatus.ACTIVE
        )

    @staticmethod
    @patch(
        "wallet.services.reimbursement_wallet_e9y_service.WalletEligibilityService.get_ros_for_user"
    )
    @patch(
        "eligibility.service.EnterpriseVerificationService.get_verification_for_user_and_org"
    )
    def test_undo_set_wallet_to_runout_failure_no_valid_ros(
        mock_get_verification_for_user_and_org,
        mock_get_ros_for_user,
        wallet_eligibility_service_with_mocks,
        mock_eligibility_record,
        session,
        wallet_currency_based,
        enterprise_user,
    ):
        # Given
        wallet_eligibility_service_with_mocks.bypass_alegeus = True
        wallet_currency_based.state = WalletState.RUNOUT

        # Mock e9y
        mock_get_verification_for_user_and_org.return_value = mock_eligibility_record

        mock_get_ros_for_user.return_value = None

        # When
        result = wallet_eligibility_service_with_mocks.undo_set_wallet_to_runout(
            wallet=wallet_currency_based, session=session
        )

        # Then
        assert result is False

    @staticmethod
    @patch(
        "wallet.services.reimbursement_wallet_e9y_service.WalletEligibilityService.get_ros_for_user"
    )
    @patch(
        "eligibility.service.EnterpriseVerificationService.get_verification_for_user_and_org"
    )
    def test_undo_set_wallet_to_runout_failure_ros_mismatch(
        mock_get_verification_for_user_and_org,
        mock_get_ros_for_user,
        wallet_eligibility_service_with_mocks,
        mock_eligibility_record,
        session,
        wallet_currency_based,
        enterprise_user,
    ):
        # Given
        wallet_eligibility_service_with_mocks.bypass_alegeus = True
        wallet_currency_based.state = WalletState.RUNOUT

        # Mock e9y
        mock_get_verification_for_user_and_org.return_value = mock_eligibility_record
        mock_get_ros_for_user.return_value = (
            ReimbursementOrganizationSettingsFactory.create(
                organization_id=enterprise_user.organization_v2.id,
                survey_url="fake_url",
            )
        )

        # When
        result = wallet_eligibility_service_with_mocks.undo_set_wallet_to_runout(
            wallet=wallet_currency_based, session=session
        )

        # Then
        assert result is False
