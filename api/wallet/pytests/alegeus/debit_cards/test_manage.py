from datetime import date
from unittest.mock import ANY, DEFAULT, patch

from requests import Response

from utils.data import normalize_phone_number
from wallet.models.constants import (
    CardStatus,
    CardStatusReason,
    ReimbursementMethod,
    WalletUserStatus,
    WalletUserType,
)
from wallet.models.reimbursement_wallet import ReimbursementWallet
from wallet.pytests.factories import ReimbursementWalletUsersFactory
from wallet.utils.alegeus.debit_cards.manage import (
    add_phone_number_to_alegeus,
    remove_phone_number_from_alegeus,
    report_lost_stolen_debit_card,
    request_debit_card,
    update_alegeus_demographics_for_debit_card,
)


def test_request_debit_card__successful(
    qualified_alegeus_wallet_hra, post_card_issue_response, get_card_details_response
):
    mock_issue_response = Response()
    mock_issue_response.status_code = 200
    mock_issue_response.json = lambda: post_card_issue_response(
        qualified_alegeus_wallet_hra
    )

    mock_details_response = Response()
    mock_details_response.status_code = 200
    mock_details_response.json = lambda: get_card_details_response(
        qualified_alegeus_wallet_hra
    )

    with patch(
        "wallet.utils.alegeus.debit_cards.manage.alegeus_api.AlegeusApi.post_issue_new_card"
    ) as mock_issue_request, patch(
        "wallet.utils.alegeus.debit_cards.manage.alegeus_api.AlegeusApi.get_debit_card_details"
    ) as mock_details_request:
        mock_issue_request.return_value = mock_issue_response
        mock_details_request.return_value = mock_details_response

        success = request_debit_card(qualified_alegeus_wallet_hra)

        assert success is True
        assert qualified_alegeus_wallet_hra.debit_card is not None
        assert (
            qualified_alegeus_wallet_hra.debit_card.card_proxy_number
            == "1100054003980205"
        )
        assert qualified_alegeus_wallet_hra.debit_card.card_status == CardStatus.NEW
        assert qualified_alegeus_wallet_hra.debit_card.created_date == date(2022, 7, 12)


def test_request_debit_card__successful_dependent_user(
    qualified_alegeus_wallet_hra,
    post_card_issue_response,
    get_card_details_response,
    factories,
):
    mock_issue_response = Response()
    mock_issue_response.status_code = 200
    mock_issue_response.json = lambda: post_card_issue_response(
        qualified_alegeus_wallet_hra
    )

    mock_details_response = Response()
    mock_details_response.status_code = 200
    mock_details_response.json = lambda: get_card_details_response(
        qualified_alegeus_wallet_hra
    )

    # Add a DEPENDENT to the wallet who will request the debit card
    dependent_user = factories.EnterpriseUserFactory.create()
    ReimbursementWalletUsersFactory.create(
        user_id=dependent_user.id,
        reimbursement_wallet_id=qualified_alegeus_wallet_hra.id,
        type=WalletUserType.DEPENDENT,
        status=WalletUserStatus.ACTIVE,
    )

    with patch(
        "wallet.utils.alegeus.debit_cards.manage.alegeus_api.AlegeusApi.post_issue_new_card"
    ) as mock_issue_request, patch(
        "wallet.utils.alegeus.debit_cards.manage.alegeus_api.AlegeusApi.get_debit_card_details"
    ) as mock_details_request:
        mock_issue_request.return_value = mock_issue_response
        mock_details_request.return_value = mock_details_response

        success = request_debit_card(qualified_alegeus_wallet_hra, dependent_user)

        assert success is True
        assert qualified_alegeus_wallet_hra.debit_card is not None
        assert (
            qualified_alegeus_wallet_hra.debit_card.card_proxy_number
            == "1100054003980205"
        )
        assert qualified_alegeus_wallet_hra.debit_card.card_status == CardStatus.NEW
        assert qualified_alegeus_wallet_hra.debit_card.created_date == date(2022, 7, 12)


def test_request_debit_card__failed_issue(qualified_alegeus_wallet_hra):
    mock_issue_response = Response()
    mock_issue_response.status_code = 500
    mock_issue_response.json = lambda: {}  # unused

    with patch(
        "wallet.utils.alegeus.debit_cards.manage.alegeus_api.AlegeusApi.post_issue_new_card"
    ) as mock_issue_request, patch(
        "wallet.utils.alegeus.debit_cards.manage.alegeus_api.AlegeusApi.get_debit_card_details"
    ) as mock_details_request:
        mock_issue_request.return_value = mock_issue_response
        mock_details_request.call_count = 0

        success = request_debit_card(qualified_alegeus_wallet_hra)

        assert success is False


def test_request_debit_card__success_without_details(
    qualified_alegeus_wallet_hra, post_card_issue_response
):
    mock_issue_response = Response()
    mock_issue_response.status_code = 200
    mock_issue_response.json = lambda: post_card_issue_response(
        qualified_alegeus_wallet_hra
    )

    mock_details_response = Response()
    mock_details_response.status_code = 500
    mock_details_response.json = lambda: {}  # unused

    with patch(
        "wallet.utils.alegeus.debit_cards.manage.alegeus_api.AlegeusApi.post_issue_new_card"
    ) as mock_issue_request, patch(
        "wallet.utils.alegeus.debit_cards.manage.alegeus_api.AlegeusApi.get_debit_card_details"
    ) as mock_details_request:
        mock_issue_request.return_value = mock_issue_response
        mock_details_request.return_value = mock_details_response

        success = request_debit_card(qualified_alegeus_wallet_hra)

        assert success is True
        assert qualified_alegeus_wallet_hra.debit_card is not None
        assert (
            qualified_alegeus_wallet_hra.debit_card.card_proxy_number
            == "1100054003980205"
        )
        assert qualified_alegeus_wallet_hra.debit_card.card_status == CardStatus.NEW
        assert qualified_alegeus_wallet_hra.debit_card.created_date is None


def test_report_lost_stolen_debit_card__successful(
    qualified_alegeus_wallet_hra,
    put_debit_card_update_status_response,
    wallet_debitcardinator,
):
    mock_report_response = Response()
    mock_report_response.status_code = 200
    mock_report_response.json = lambda: put_debit_card_update_status_response(
        qualified_alegeus_wallet_hra
    )

    with patch(
        "wallet.utils.alegeus.debit_cards.manage.alegeus_api.AlegeusApi.put_debit_card_update_status"
    ) as mock_report_request, patch(
        "wallet.utils.alegeus.debit_cards.manage.emit_audit_log_update"
    ) as mock_emit_log:
        mock_report_request.return_value = mock_report_response
        mock_emit_log.return_value = None
        wallet_debitcardinator(
            qualified_alegeus_wallet_hra, card_status=CardStatus.ACTIVE
        )

        success = report_lost_stolen_debit_card(qualified_alegeus_wallet_hra)
        mock_emit_log.assert_called_once()
        assert success is True
        assert qualified_alegeus_wallet_hra.debit_card.card_status == CardStatus.CLOSED
        assert (
            qualified_alegeus_wallet_hra.debit_card.card_status_reason
            == CardStatusReason.LOST_STOLEN
        )


def test_report_lost_stolen_debit_card__failed_update(
    qualified_alegeus_wallet_hra,
    wallet_debitcardinator,
):
    mock_report_response = Response()
    mock_report_response.status_code = 500
    mock_report_response.json = lambda: {}  # unused

    with patch(
        "wallet.utils.alegeus.debit_cards.manage.alegeus_api.AlegeusApi.put_debit_card_update_status"
    ) as mock_report_request:
        mock_report_request.return_value = mock_report_response
        wallet_debitcardinator(
            qualified_alegeus_wallet_hra, card_status=CardStatus.ACTIVE
        )

        success = report_lost_stolen_debit_card(qualified_alegeus_wallet_hra)

        assert success is False


def test_update_alegeus_demographics_for_debit_card(
    qualified_alegeus_wallet_hra, factories, eligibility_factories
):
    qualified_alegeus_wallet_hra.reimbursement_method = ReimbursementMethod.PAYROLL
    address = factories.AddressFactory(
        user=qualified_alegeus_wallet_hra.employee_member
    )
    e9y_member_verification = eligibility_factories.VerificationFactory.create(
        user_id=1,
        organization_id=qualified_alegeus_wallet_hra.reimbursement_organization_settings.organization_id,
    )
    with patch(
        "wallet.utils.alegeus.debit_cards.manage.alegeus_api.AlegeusApi.make_api_request"
    ) as put_employee_demographic_api_request_mock, patch(
        "eligibility.service.EnterpriseVerificationService.get_verification_for_user_and_org"
    ) as member_id_search_mock:
        put_employee_demographic_api_request_mock.return_value.status_code = 200
        member_id_search_mock.return_value = e9y_member_verification
        user_id = qualified_alegeus_wallet_hra.employee_member.id
        expected_result = update_alegeus_demographics_for_debit_card(
            qualified_alegeus_wallet_hra, user_id, address
        )
        assert expected_result is True
        assert put_employee_demographic_api_request_mock.call_count == 1
        call_data_params = put_employee_demographic_api_request_mock.call_args.kwargs

        data = {
            "Address1": address.street_address,
            "BirthDate": e9y_member_verification.date_of_birth.strftime("%Y-%m-%d"),
            "City": address.city,
            "Country": "US",
            "EmployeeId": "456",
            "EmployerId": "123",
            "FirstName": e9y_member_verification.first_name,
            "LastName": e9y_member_verification.last_name,
            "State": "NY",
            "ZipCode": address.zip_code,
            "TpaId": ANY,
            "CurrentEmployeeSocialSecurityNumber": "",
            "NewEmployeeSocialSecurityNumber": "",
            "ReimbursementCode": ReimbursementMethod.PAYROLL.value,
            "EmployeeStatus": "Active",
            "NoOverwrite": True,
        }
        assert call_data_params["data"] == data


def test_update_alegeus_demographics_for_debit_card_without_dob(
    qualified_alegeus_wallet_hra, factories
):
    factories.HealthProfileFactory.create(
        user=qualified_alegeus_wallet_hra.employee_member, has_birthday=True
    )
    address = factories.AddressFactory(
        user=qualified_alegeus_wallet_hra.employee_member,
    )
    with patch(
        "wallet.utils.alegeus.debit_cards.manage.get_employee_health_profile_dob"
    ) as mock_profile_dob, patch.object(
        ReimbursementWallet, "get_first_name_last_name_and_dob"
    ) as mock_wallet_fnlndob, patch(
        "wallet.utils.alegeus.debit_cards.manage.alegeus_api.AlegeusApi.make_api_request"
    ) as put_employee_demographic_api_request_mock:
        mock_profile_dob.return_value = None
        mock_wallet_fnlndob.return_value = ["John", "Doe", None]
        user_id = qualified_alegeus_wallet_hra.employee_member.id
        expected_result = update_alegeus_demographics_for_debit_card(
            qualified_alegeus_wallet_hra, user_id, address
        )
        assert expected_result is False
        assert put_employee_demographic_api_request_mock.call_count == 0


def test_update_alegeus_address_name_and_dob_dependent(
    qualified_alegeus_wallet_hra, factories, eligibility_factories, faker
):
    qualified_alegeus_wallet_hra.reimbursement_method = ReimbursementMethod.PAYROLL
    address = factories.AddressFactory(
        user=qualified_alegeus_wallet_hra.employee_member
    )

    e9y_member_verification = eligibility_factories.VerificationFactory.create(
        user_id=qualified_alegeus_wallet_hra.user_id,
        organization_id=qualified_alegeus_wallet_hra.reimbursement_organization_settings.organization_id,
        date_of_birth=faker.date_of_birth(),
    )
    wallet_user = qualified_alegeus_wallet_hra.employee_member

    with patch(
        "wallet.utils.alegeus.debit_cards.manage.alegeus_api.AlegeusApi.make_api_request"
    ) as put_employee_demographic_api_request_mock, patch(
        "eligibility.service.EnterpriseVerificationService.get_verification_for_user_and_org"
    ) as member_id_search_mock:
        put_employee_demographic_api_request_mock.return_value.status_code = 200
        member_id_search_mock.return_value = e9y_member_verification
        expected_result = update_alegeus_demographics_for_debit_card(
            qualified_alegeus_wallet_hra, wallet_user.id, address
        )
        assert expected_result is True
        assert put_employee_demographic_api_request_mock.call_count == 1
        call_data_params = put_employee_demographic_api_request_mock.call_args.kwargs

        data = {
            "Address1": address.street_address,
            "BirthDate": e9y_member_verification.date_of_birth.strftime("%Y-%m-%d"),
            "City": address.city,
            "Country": "US",
            "EmployeeId": "456",
            "EmployerId": "123",
            "FirstName": e9y_member_verification.first_name,
            "LastName": e9y_member_verification.last_name,
            "State": "NY",
            "ZipCode": address.zip_code,
            "TpaId": ANY,
            "CurrentEmployeeSocialSecurityNumber": "",
            "NewEmployeeSocialSecurityNumber": "",
            "ReimbursementCode": ReimbursementMethod.PAYROLL.value,
            "EmployeeStatus": "Active",
            "NoOverwrite": True,
        }

        assert call_data_params["data"] == data


def test_update_alegeus_demographics_for_debit_card_with_unsupported_country(
    qualified_alegeus_wallet_hra,
    eligibility_factories,
    factories,
):
    factories.HealthProfileFactory.create(
        user=qualified_alegeus_wallet_hra.employee_member, has_birthday=True
    )
    address = factories.AddressFactory(
        user=qualified_alegeus_wallet_hra.employee_member, country="MX"
    )
    e9y_member_verification = eligibility_factories.VerificationFactory.create(
        user_id=1,
        organization_id=qualified_alegeus_wallet_hra.reimbursement_organization_settings.organization_id,
    )
    with patch.object(ReimbursementWallet, "get_first_name_last_name_and_dob"), patch(
        "eligibility.e9y.grpc_service.member_id_search"
    ) as member_id_search_mock, patch(
        "wallet.utils.alegeus.debit_cards.manage.alegeus_api.AlegeusApi.make_api_request"
    ) as put_employee_demographic_api_request_mock:
        member_id_search_mock.return_value = e9y_member_verification
        user_id = qualified_alegeus_wallet_hra.employee_member.id
        expected_result = update_alegeus_demographics_for_debit_card(
            qualified_alegeus_wallet_hra, user_id, address
        )
        assert expected_result is False
        assert put_employee_demographic_api_request_mock.call_count == 0


def test_update_alegeus_demographics_for_debit_card_without_input_address(
    qualified_alegeus_wallet_hra,
    eligibility_factories,
    factories,
):
    factories.HealthProfileFactory.create(
        user=qualified_alegeus_wallet_hra.employee_member, has_birthday=True
    )
    # Do not call factories.AddressFactory() so that wallet.member.addresses does not exist.
    e9y_member_verification = eligibility_factories.VerificationFactory.create(
        user_id=1,
        organization_id=qualified_alegeus_wallet_hra.reimbursement_organization_settings.organization_id,
    )
    assert not qualified_alegeus_wallet_hra.employee_member.addresses
    with patch.object(ReimbursementWallet, "get_first_name_last_name_and_dob"), patch(
        "eligibility.e9y.grpc_service.member_id_search"
    ) as member_id_search_mock:
        member_id_search_mock.return_value = e9y_member_verification
        user_id = qualified_alegeus_wallet_hra.employee_member.id
        expected_result = update_alegeus_demographics_for_debit_card(
            qualified_alegeus_wallet_hra, user_id, None
        )
        assert expected_result is False


def test_update_alegeus_demographics_for_debit_card_with_bad_put_employee_demographic(
    qualified_alegeus_wallet_hra, factories, eligibility_factories
):
    qualified_alegeus_wallet_hra.reimbursement_method = ReimbursementMethod.PAYROLL
    address = factories.AddressFactory(
        user=qualified_alegeus_wallet_hra.employee_member
    )
    e9y_member_verification = eligibility_factories.VerificationFactory.create(
        user_id=1,
        organization_id=qualified_alegeus_wallet_hra.reimbursement_organization_settings.organization_id,
    )
    wallet_user = qualified_alegeus_wallet_hra.employee_member
    with patch(
        "wallet.utils.alegeus.debit_cards.manage.alegeus_api.AlegeusApi.make_api_request"
    ) as put_employee_demographic_api_request_mock, patch(
        "eligibility.service.EnterpriseVerificationService.get_verification_for_user_and_org"
    ) as member_id_search_mock:
        put_employee_demographic_api_request_mock.return_value.status_code = 404
        member_id_search_mock.return_value = e9y_member_verification
        expected_result = update_alegeus_demographics_for_debit_card(
            qualified_alegeus_wallet_hra, wallet_user.id, address
        )
        assert expected_result is False
        assert put_employee_demographic_api_request_mock.call_count == 1
        call_data_params = put_employee_demographic_api_request_mock.call_args.kwargs
        data = {
            "Address1": address.street_address,
            "BirthDate": e9y_member_verification.date_of_birth.strftime("%Y-%m-%d"),
            "City": address.city,
            "Country": "US",
            "EmployeeId": "456",
            "EmployerId": "123",
            "FirstName": e9y_member_verification.first_name,
            "LastName": e9y_member_verification.last_name,
            "State": "NY",
            "ZipCode": address.zip_code,
            "TpaId": ANY,
            "CurrentEmployeeSocialSecurityNumber": "",
            "NewEmployeeSocialSecurityNumber": "",
            "ReimbursementCode": ReimbursementMethod.PAYROLL.value,
            "EmployeeStatus": "Active",
            "NoOverwrite": True,
        }
        assert call_data_params["data"] == data


def test_add_phone_number_to_alegeus__successful(
    qualified_alegeus_wallet_hra,
):
    mock_response = Response()
    mock_response.status_code = 200
    mock_response.json = lambda: {}

    def mock_api_request_side_effect(url, params=None, method=None, api_version=None):
        member_phone_number = (
            qualified_alegeus_wallet_hra.employee_member.member_profile.phone_number
        )
        res = normalize_phone_number(member_phone_number, None)
        normalized_phone_number = res[1].national_number

        assert f"{normalized_phone_number}" in url
        assert method == "POST"
        assert params is None
        assert api_version == "0.0"
        return DEFAULT

    with patch(
        "wallet.alegeus_api.AlegeusApi.make_api_request",
    ) as mock_make_api_request:
        mock_make_api_request.return_value = mock_response
        mock_make_api_request.side_effect = mock_api_request_side_effect
        user = qualified_alegeus_wallet_hra.employee_member
        success = add_phone_number_to_alegeus(qualified_alegeus_wallet_hra, user)

        assert mock_make_api_request.call_count == 1
        assert success is True


def test_international_phone_number_to_alegeus__failed(
    qualified_alegeus_wallet_hra,
):
    qualified_alegeus_wallet_hra.employee_member.member_profile.phone_number = (
        "+44-201-555-0123"
    )

    with patch(
        "wallet.alegeus_api.AlegeusApi.make_api_request",
    ) as mock_make_api_request:
        user = qualified_alegeus_wallet_hra.employee_member
        success = add_phone_number_to_alegeus(qualified_alegeus_wallet_hra, user)

        assert mock_make_api_request.call_count == 0
        assert success is False


def test_add_phone_number_to_alegeus__failed(qualified_alegeus_wallet_hra):
    mock_response = Response()
    mock_response.status_code = 500
    mock_response.json = lambda: {}

    qualified_alegeus_wallet_hra.employee_member.member_profile.phone_number = None

    with patch(
        "wallet.alegeus_api.AlegeusApi.make_api_request",
    ) as mock_make_api_request:
        mock_make_api_request.return_value = mock_response
        user = qualified_alegeus_wallet_hra.employee_member
        success = add_phone_number_to_alegeus(qualified_alegeus_wallet_hra, user)

        assert success is False


def test_remove_phone_number_from_alegeus__successful(
    qualified_alegeus_wallet_hra,
):
    mock_get_response = Response()
    mock_get_response.status_code = 200
    mock_get_response.json = lambda: [
        {
            "PAN": "9999920000000036937",
            "PhoneNumber": "12015550123",
            "RegisterStatus": 1,
        }
    ]

    mock_delete_response = Response()
    mock_delete_response.status_code = 200
    mock_delete_response.json = lambda: {}

    with patch(
        "wallet.utils.alegeus.debit_cards.manage.alegeus_api.AlegeusApi.make_api_request",
    ) as mock_make_api_request, patch(
        "wallet.utils.alegeus.debit_cards.manage.alegeus_api.AlegeusApi.get_member_phone_numbers"
    ) as mock_get_request, patch(
        "wallet.utils.alegeus.debit_cards.manage.alegeus_api.AlegeusApi.delete_remove_employee_phone_number"
    ) as mock_remove_request:
        mock_make_api_request.return_value = mock_delete_response
        mock_get_request.return_value = mock_get_response
        mock_remove_request.return_value = mock_delete_response

        success = remove_phone_number_from_alegeus(
            qualified_alegeus_wallet_hra, "201-555-0123"
        )

        assert mock_get_request.call_count == 1
        assert mock_remove_request.call_count == 1
        assert success is True


def test_remove_phone_number_from_alegeus__failed_with_no_nums(
    qualified_alegeus_wallet_hra,
):
    mock_response = Response()
    mock_response.status_code = 500
    mock_response.json = lambda: {}

    mock_get_list_response = Response()
    mock_get_list_response.status_code = 200
    mock_get_list_response.json = lambda: [{}]

    def mock_api_request_side_effect(url, extra_headers=None, params=None, method=None):
        assert "2025551212" in url
        return DEFAULT

    with patch(
        "wallet.utils.alegeus.debit_cards.manage.alegeus_api.AlegeusApi.make_api_request",
    ) as mock_make_api_request, patch(
        "wallet.utils.alegeus.debit_cards.manage.alegeus_api.AlegeusApi.get_member_phone_numbers"
    ) as mock_get_request, patch(
        "wallet.utils.alegeus.debit_cards.manage.alegeus_api.AlegeusApi.delete_remove_employee_phone_number"
    ) as mock_remove_request:
        mock_make_api_request.return_value = mock_response
        mock_make_api_request.side_effect = mock_api_request_side_effect
        mock_get_request.return_value = mock_get_list_response

        success = remove_phone_number_from_alegeus(
            qualified_alegeus_wallet_hra, "202-555-1212"
        )
        assert mock_get_request.call_count == 1
        mock_remove_request.call_count == 1  # noqa  B015  TODO:  Result of comparison is not used. This line doesn't do anything. Did you intend to prepend it with assert?
        assert success is False
