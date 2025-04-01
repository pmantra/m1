from unittest.mock import patch

import requests
from requests import Response

from wallet.alegeus_api import ALEGEUS_WCA_URL, ALEGEUS_WCP_URL
from wallet.constants import MAVEN_ADDRESS
from wallet.models.constants import CardStatus, CardStatusReason


def test_issue_debit_card__success(
    client,
    enterprise_user,
    qualified_alegeus_wallet_hra,
    post_card_issue_response,
    get_card_details_response,
    api_helpers,
    factories,
    eligibility_factories,
    faker,
):
    def make_api_request_side_effect(
        url,
        data=None,
        params=None,
        api_version=None,
        extra_headers=None,
        method="GET",
        **kwargs,
    ):
        mock_response = requests.Response()
        key = f"{method}:{url}"

        # post_issue_new_card
        if key == f"POST:{ALEGEUS_WCP_URL}/participant/cards/new/None/123/456":
            mock_response.status_code = 200
            mock_response.json = lambda: post_card_issue_response(
                qualified_alegeus_wallet_hra
            )

        # add member phone to Alegeus
        elif (
            key
            == f"POST{ALEGEUS_WCP_URL}/participant/communications/mobile/None/123/456/5555555555"
        ):
            mock_response.status_code = 200

        # get_debit_card_details
        elif key == f"GET:{ALEGEUS_WCP_URL}/participant/cards/details/None/123/456":
            mock_response.status_code = 200
            mock_response.json = lambda: get_card_details_response(
                qualified_alegeus_wallet_hra
            )

        elif key == f"GET:{ALEGEUS_WCA_URL}/Services/Employee/None/123/456":
            mock_response.status_code = 200

        elif key == f"PUT:{ALEGEUS_WCA_URL}/Services/Employee/None/123/456":
            mock_response.status_code = 200

        elif (
            key
            == f"POST:{ALEGEUS_WCP_URL}/participant/communications/mobile/None/123/456/2015550123"
        ):
            mock_response.status_code = 200

        return mock_response

    factories.HealthProfileFactory.create(
        user=qualified_alegeus_wallet_hra.member, has_birthday=True
    )
    factories.AddressFactory(user=qualified_alegeus_wallet_hra.member)
    e9y_member = eligibility_factories.EligibilityMemberFactory.create(
        id=1,
        organization_id=qualified_alegeus_wallet_hra.reimbursement_organization_settings.organization_id,
        date_of_birth=faker.date_of_birth(),
    )

    with patch(
        "wallet.alegeus_api.AlegeusApi.make_api_request",
        side_effect=make_api_request_side_effect,
    ) as mock_api_request, patch(
        "eligibility.e9y.grpc_service.member_id_search"
    ) as member_id_search_mock:
        member_id_search_mock.return_value = e9y_member
        enterprise_user.profile.country_code = "US"
        qualified_alegeus_wallet_hra.reimbursement_organization_settings.debit_card_enabled = (
            True
        )
        res = client.post(
            "/api/v1/reimbursement_wallets/"
            + str(qualified_alegeus_wallet_hra.id)
            + "/debit_card",
            headers=api_helpers.json_headers(enterprise_user),
            data=api_helpers.json_data({"sms_opt_in": True}),
        )

        assert mock_api_request.call_count == 5
        assert res.status_code == 200

        content = api_helpers.load_json(res)
        debit_card = content["data"]
        assert debit_card["card_proxy_number"] == "1100054003980205"
        assert debit_card["card_status"] == CardStatus.NEW.value
        assert debit_card["created_date"] == "2022-07-12"


def test_report_card_lost_stolen__success(
    client,
    enterprise_user,
    qualified_alegeus_wallet_hra,
    put_debit_card_update_status_response,
    wallet_debitcardinator,
    api_helpers,
):

    mock_update_debit_response = Response()
    mock_update_debit_response.status_code = 200
    mock_update_debit_response.json = lambda: put_debit_card_update_status_response(
        qualified_alegeus_wallet_hra
    )

    with patch(
        "wallet.alegeus_api.AlegeusApi.make_api_request",
    ) as mock_api_request:
        mock_api_request.return_value = mock_update_debit_response

        wallet_debitcardinator(
            qualified_alegeus_wallet_hra, card_status=CardStatus.ACTIVE
        )
        res = client.post(
            f"/api/v1/reimbursement_wallets/{qualified_alegeus_wallet_hra.id}/debit_card/lost_stolen",
            headers=api_helpers.json_headers(enterprise_user),
        )

        assert mock_api_request.call_count == 1
        assert res.status_code == 200
        content = api_helpers.load_json(res)
        debit_card = content["data"]
        assert debit_card["card_status"] == CardStatus.CLOSED.value
        assert debit_card["card_status_reason"] == CardStatusReason.LOST_STOLEN.value


def test_request_debit_card_canadian_address__successful(
    client,
    enterprise_user,
    qualified_alegeus_wallet_hra,
    post_card_issue_response,
    get_card_details_response,
    api_helpers,
    factories,
    eligibility_factories,
    faker,
):
    def make_api_request_side_effect(
        url,
        data=None,
        params=None,
        api_version=None,
        extra_headers=None,
        method="GET",
        **kwargs,
    ):
        mock_response = requests.Response()
        key = f"{method}:{url}"
        # post_issue_new_card
        if key == f"POST:{ALEGEUS_WCP_URL}/participant/cards/new/None/123/456":
            mock_response.status_code = 200
            mock_response.json = lambda: post_card_issue_response(
                qualified_alegeus_wallet_hra
            )

        # add member phone to Alegeus
        elif (
            key
            == f"POST{ALEGEUS_WCP_URL}/participant/communications/mobile/None/123/456/5555555555"
        ):
            mock_response.status_code = 200

        # get_debit_card_details
        elif key == f"GET:{ALEGEUS_WCP_URL}/participant/cards/details/None/123/456":
            mock_response.status_code = 200
            mock_response.json = lambda: get_card_details_response(
                qualified_alegeus_wallet_hra
            )

        elif key == f"GET:{ALEGEUS_WCA_URL}/Services/Employee/None/123/456":
            mock_response.status_code = 200

        elif key == f"PUT:{ALEGEUS_WCA_URL}/Services/Employee/None/123/456":
            mock_response.status_code = 200

        elif (
            key
            == f"POST:{ALEGEUS_WCP_URL}/participant/communications/mobile/None/123/456/2015550123"
        ):
            mock_response.status_code = 200

        return mock_response

    factories.HealthProfileFactory.create(
        user=qualified_alegeus_wallet_hra.member, has_birthday=True
    )
    factories.AddressFactory(
        user=qualified_alegeus_wallet_hra.member,
        state="PE",
        zip_code="C0A1N0",
        country="CA",
    )
    e9y_member = eligibility_factories.EligibilityMemberFactory.create(
        id=1,
        organization_id=qualified_alegeus_wallet_hra.reimbursement_organization_settings.organization_id,
        date_of_birth=faker.date_of_birth(),
    )

    with patch(
        "wallet.alegeus_api.AlegeusApi.make_api_request",
        side_effect=make_api_request_side_effect,
    ) as mock_api_request, patch(
        "eligibility.e9y.grpc_service.member_id_search"
    ) as member_id_search_mock, patch(
        "wallet.utils.alegeus.debit_cards.manage.upload_employee_demographics_ib_file_to_alegeus.delay"
    ) as edi_ib_update_mock:
        member_id_search_mock.return_value = e9y_member
        enterprise_user.profile.country_code = "CA"
        qualified_alegeus_wallet_hra.reimbursement_organization_settings.debit_card_enabled = (
            True
        )
        res = client.post(
            "/api/v1/reimbursement_wallets/"
            + str(qualified_alegeus_wallet_hra.id)
            + "/debit_card",
            headers=api_helpers.json_headers(enterprise_user),
            data=api_helpers.json_data({"sms_opt_in": True}),
        )

        assert mock_api_request.call_count == 5
        assert res.status_code == 200

        content = api_helpers.load_json(res)
        debit_card = content["data"]
        assert debit_card["card_proxy_number"] == "1100054003980205"
        assert debit_card["card_status"] == CardStatus.NEW.value
        assert debit_card["created_date"] == "2022-07-12"

        demographics_params = mock_api_request.call_args_list[1].kwargs["data"]
        assert demographics_params["Address1"] == MAVEN_ADDRESS["address_1"]
        assert demographics_params["Country"] == MAVEN_ADDRESS["country"]
        assert edi_ib_update_mock.call_count == 1
        assert edi_ib_update_mock.call_args[0][0] == qualified_alegeus_wallet_hra.id


def test_request_debit_card_invalid_address(
    client,
    enterprise_user,
    qualified_alegeus_wallet_hra,
    api_helpers,
    factories,
):

    factories.HealthProfileFactory.create(
        user=qualified_alegeus_wallet_hra.member, has_birthday=True
    )
    factories.AddressFactory(
        user=qualified_alegeus_wallet_hra.member,
        state="NA",
        zip_code="12345",
        country="IN",
    )
    qualified_alegeus_wallet_hra.reimbursement_organization_settings.debit_card_enabled = (
        True
    )

    res = client.post(
        "/api/v1/reimbursement_wallets/"
        + str(qualified_alegeus_wallet_hra.id)
        + "/debit_card",
        headers=api_helpers.json_headers(enterprise_user),
        data=api_helpers.json_data({"sms_opt_in": True}),
    )
    assert res.status_code == 500
    assert res.json["message"] == "Could not issue debit card"
