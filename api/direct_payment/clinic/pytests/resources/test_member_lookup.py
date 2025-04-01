import datetime
from unittest import mock

import pytest

from common.payments_gateway import Customer


@pytest.fixture(scope="function")
def mock_e9y(enterprise_user):
    with mock.patch(
        "eligibility.service.EnterpriseVerificationService.get_eligible_organization_ids_for_user"
    ) as mock_get_eligible_org_ids:
        mock_get_eligible_org_ids.return_value = {enterprise_user.organization_v2.id}
        yield


@pytest.fixture(scope="function")
def mock_payments_gateway():
    with mock.patch(
        "common.payments_gateway.client.PaymentsGatewayClient", autospec=True
    ) as mock_client, mock.patch(
        "wallet.services.member_lookup.get_client"
    ) as mock_get_client:
        mock_get_client.return_value = mock_client
        yield mock_client


@pytest.fixture(scope="function")
def mock_payment_method(mock_payments_gateway):
    mock_payments_gateway.get_customer.return_value = Customer(
        customer_id="",
        customer_setup_status=None,
        payment_method_types=[],
        payment_methods=[mock.MagicMock()],
    )


@pytest.fixture(scope="function")
def mock_missing_payment_method(mock_payments_gateway):
    mock_payments_gateway.get_customer.return_value = None


@pytest.fixture(scope="function")
def mock_access_member_lookup_request(enterprise_user):
    enterprise_user.health_profile.birthday = datetime.date(year=2000, month=1, day=1)
    return {
        "last_name": enterprise_user.last_name,
        "benefit_id": enterprise_user.member_benefit.benefit_id,
        "date_of_birth": enterprise_user.health_profile.birthday.strftime("%Y-%m-%d"),
    }


@pytest.fixture(scope="function")
def mock_green_member_lookup_request(enterprise_user):
    enterprise_user.health_profile.birthday = datetime.date(year=2000, month=1, day=1)
    return {
        "last_name": enterprise_user.last_name,
        "benefit_id": enterprise_user.member_benefit.benefit_id,
        "date_of_birth": enterprise_user.health_profile.birthday.strftime("%Y-%m-%d"),
    }


@pytest.fixture(scope="function")
def mock_gold_member_lookup_request(user_for_direct_payment_wallet):
    user_for_direct_payment_wallet.health_profile.birthday = datetime.date(
        year=2000, month=1, day=1
    )
    return {
        "last_name": user_for_direct_payment_wallet.last_name,
        "benefit_id": user_for_direct_payment_wallet.member_benefit.benefit_id,
        "date_of_birth": user_for_direct_payment_wallet.health_profile.birthday.strftime(
            "%Y-%m-%d"
        ),
    }


@pytest.fixture(scope="function")
def mock_unlimited_gold_member_lookup_request(user_for_unlimited_direct_payment_wallet):
    user_for_unlimited_direct_payment_wallet.health_profile.birthday = datetime.date(
        year=2000, month=1, day=1
    )
    return {
        "last_name": user_for_unlimited_direct_payment_wallet.last_name,
        "benefit_id": user_for_unlimited_direct_payment_wallet.member_benefit.benefit_id,
        "date_of_birth": user_for_unlimited_direct_payment_wallet.health_profile.birthday.strftime(
            "%Y-%m-%d"
        ),
    }


class TestMemberLookup:
    @staticmethod
    def test_member_not_found(
        fc_user,
        client,
        api_helpers,
        fertility_clinic,
    ):
        # Given a user that doesn't exist
        request = {
            "last_name": "Smith",
            "benefit_id": "M12345",
            "date_of_birth": "2000-01-01",
        }

        # When
        res = client.post(
            "/api/v1/direct_payment/clinic/member-lookup",
            headers=api_helpers.json_headers(user=fc_user),
            json=request,
        )

        # Then
        assert res.status_code == 404


class TestAccessMemberLookup:
    @staticmethod
    def test_access_member_lookup(
        fc_user,
        client,
        api_helpers,
        fertility_clinic,
        enterprise_user,
        mock_e9y,
        mock_access_member_lookup_request,
    ):
        res = client.post(
            "/api/v1/direct_payment/clinic/member-lookup",
            headers=api_helpers.json_headers(user=fc_user),
            json=mock_access_member_lookup_request,
        )

        data = api_helpers.load_json(res)

        assert res.status_code == 200
        assert data["member"]["current_type"] == "MAVEN_ACCESS"
        assert data["member"]["eligible_type"] == "MAVEN_ACCESS"
        # validate content is null
        assert data["content"] is None


class TestGreenMemberLookup:
    @staticmethod
    def test_green_member_lookup(
        fc_user,
        client,
        api_helpers,
        fertility_clinic,
        enterprise_user,
        qualified_alegeus_wallet_hra,
        mock_e9y,
        mock_green_member_lookup_request,
    ):

        res = client.post(
            "/api/v1/direct_payment/clinic/member-lookup",
            headers=api_helpers.json_headers(user=fc_user),
            json=mock_green_member_lookup_request,
        )

        data = api_helpers.load_json(res)

        assert res.status_code == 200
        assert data["member"]["current_type"] == "MAVEN_GREEN"
        assert data["member"]["eligible_type"] == "MAVEN_GREEN"
        # validate content is null
        assert data["content"] is None
        # validate balance information
        assert data["benefit"]["wallet"]["balance"] == {
            "total": 0,
            "available": 0,
            "is_unlimited": False,
        }


class TestGoldMemberLookup:
    @staticmethod
    def test_gold_member_lookup(
        fc_user,
        client,
        api_helpers,
        fertility_clinic,
        user_for_direct_payment_wallet,
        direct_payment_wallet,
        mock_e9y,
        mock_gold_member_lookup_request,
        mock_payment_method,
    ):
        """Test that a Gold member with payment method on file can be looked up"""
        # When
        res = client.post(
            "/api/v1/direct_payment/clinic/member-lookup",
            headers=api_helpers.json_headers(user=fc_user),
            json=mock_gold_member_lookup_request,
        )

        data = api_helpers.load_json(res)

        assert res.status_code == 200
        # validate member type
        assert data["member"]["current_type"] == "MAVEN_GOLD"
        assert data["member"]["eligible_type"] == "MAVEN_GOLD"
        # validate org information
        assert (
            data["benefit"]["organization"]["name"]
            == user_for_direct_payment_wallet.organization_v2.name
        )
        assert (
            data["benefit"]["organization"]["fertility_program"][
                "direct_payment_enabled"
            ]
            is True
        )
        # validate wallet data
        assert data["benefit"]["wallet"]["payment_method_on_file"] is True
        assert data["benefit"]["wallet"]["allow_treatment_scheduling"] is True
        assert data["benefit"]["wallet"]["benefit_type"] == "CURRENCY"
        # validate content is null
        assert data["content"] is None
        # validate balance information
        assert data["benefit"]["wallet"]["balance"] == {
            "total": 2500000,
            "available": 2500000,
            "is_unlimited": False,
        }

    @staticmethod
    def test_gold_member_lookup_unlimited_benefits(
        fc_user,
        client,
        api_helpers,
        fertility_clinic,
        user_for_unlimited_direct_payment_wallet,
        unlimited_direct_payment_wallet,
        mock_e9y,
        mock_unlimited_gold_member_lookup_request,
        mock_payment_method,
    ):
        """Test that a Gold member with unlimited benefits can be looked up"""
        # When
        res = client.post(
            "/api/v1/direct_payment/clinic/member-lookup",
            headers=api_helpers.json_headers(user=fc_user),
            json=mock_unlimited_gold_member_lookup_request,
        )

        data = api_helpers.load_json(res)

        assert res.status_code == 200
        # validate member type
        assert data["member"]["current_type"] == "MAVEN_GOLD"
        assert data["member"]["eligible_type"] == "MAVEN_GOLD"
        # validate org information
        assert (
            data["benefit"]["organization"]["name"]
            == user_for_unlimited_direct_payment_wallet.organization_v2.name
        )
        assert (
            data["benefit"]["organization"]["fertility_program"][
                "direct_payment_enabled"
            ]
            is True
        )
        # validate wallet data
        assert data["benefit"]["wallet"]["payment_method_on_file"] is True
        assert data["benefit"]["wallet"]["allow_treatment_scheduling"] is True
        assert data["benefit"]["wallet"]["benefit_type"] == "CURRENCY"
        # validate content is null
        assert data["content"] is None
        # validate balance information
        assert data["benefit"]["wallet"]["balance"] == {
            "total": None,
            "available": None,
            "is_unlimited": True,
        }

    @staticmethod
    def test_gold_member_lookup_missing_payment_method(
        fc_user,
        client,
        api_helpers,
        fertility_clinic,
        user_for_direct_payment_wallet,
        direct_payment_wallet,
        mock_e9y,
        mock_gold_member_lookup_request,
        mock_missing_payment_method,
    ):
        """Test that a Gold member without payment method on file can be looked up"""
        res = client.post(
            "/api/v1/direct_payment/clinic/member-lookup",
            headers=api_helpers.json_headers(user=fc_user),
            json=mock_gold_member_lookup_request,
        )

        data = api_helpers.load_json(res)

        assert res.status_code == 200
        # validate member type
        assert data["member"]["current_type"] == "MAVEN_GOLD"
        assert data["member"]["eligible_type"] == "MAVEN_GOLD"
        # validate org information
        assert (
            data["benefit"]["organization"]["name"]
            == user_for_direct_payment_wallet.organization_v2.name
        )
        assert (
            data["benefit"]["organization"]["fertility_program"][
                "direct_payment_enabled"
            ]
            is True
        )
        # validate wallet data
        assert data["benefit"]["wallet"]["payment_method_on_file"] is False
        assert data["benefit"]["wallet"]["allow_treatment_scheduling"] is False
        assert data["benefit"]["wallet"]["benefit_type"] == "CURRENCY"
        # validate content is null
        assert data["content"] is None
        # validate balance information
        assert data["benefit"]["wallet"]["balance"] == {
            "total": 2500000,
            "available": 2500000,
            "is_unlimited": False,
        }

    @staticmethod
    def test_gold_member_lookup_missing_direct_payment_category_toc(
        fc_user,
        client,
        api_helpers,
        fertility_clinic,
        user_for_direct_payment_wallet,
        mock_missing_payment_method,
        direct_payment_wallet_without_dp_category_access,
        mock_e9y,
        mock_gold_member_lookup_request,
        ff_test_data,
    ):
        """Test that a Gold member without direct payment category access can be looked up"""
        res = client.post(
            "/api/v1/direct_payment/clinic/member-lookup",
            headers=api_helpers.json_headers(user=fc_user),
            json=mock_gold_member_lookup_request,
        )

        data = api_helpers.load_json(res)

        assert res.status_code == 200
        # validate member type
        assert data["member"]["current_type"] == "MAVEN_GOLD"
        assert data["member"]["eligible_type"] == "MAVEN_GOLD"
        # validate org information
        assert (
            data["benefit"]["organization"]["name"]
            == user_for_direct_payment_wallet.organization_v2.name
        )
        assert (
            data["benefit"]["organization"]["fertility_program"][
                "direct_payment_enabled"
            ]
            is True
        )
        # validate wallet data
        assert data["benefit"]["wallet"]["payment_method_on_file"] is False
        assert data["benefit"]["wallet"]["allow_treatment_scheduling"] is False
        assert data["benefit"]["wallet"]["benefit_type"] is None
        # validate content is rendered
        assert data["content"] == {
            "messages": [
                {
                    "text": "Please submit authorizations for this member to Progyny through 4/30/2025.",
                    "level": "attention",
                }
            ],
            "body_variant": "PROGYNY_TOC",
        }
        # validate balance information
        assert data["benefit"]["wallet"]["balance"] == {
            "total": 0,
            "available": 0,
            "is_unlimited": False,
        }
