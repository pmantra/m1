from unittest import mock

from pytests import stripe_fixtures as test_utils
from pytests.db_util import enable_db_performance_warnings
from storage.connection import db
from utils.log import logger
from views.payments import RecipientInformationResource

log = logger(__name__)

stripe_account_id = test_utils.stripe_account_id
stripe_customer_id = test_utils.stripe_customer_id
stripe_card_id = test_utils.stripe_card_id


@mock.patch(
    "views.payments.RecipientInformationResource._stripe_client",
)
def test_update_recipient_information(
    mock_stripe_client,
    default_user,
    api_helpers,
    client,
    factories,
):

    mock_stripe_client.get_connect_account_for_user.return_value = (
        test_utils.verified_account
    )
    practitioner = factories.PractitionerUserFactory.create()
    practitioner.practitioner_profile.stripe_account_id = stripe_account_id

    # Given - we are updating the stripe recipient information
    legal_entity = {
        "dob": {"day": "06", "month": "08", "year": "1986"},
        "address": {
            "line1": "1234 Fake St",
            "city": "Brooklyn",
            "state": "NY",
            "postal_code": "11222",
        },
        "first_name": "Elizabeth",
        "last_name": "Blackwell",
        "ssn_last_4": "0000",
        "id_number": "000000000",
        "type": "individual",
    }

    with enable_db_performance_warnings(
        database=db,
        failure_threshold=3,
    ):
        # When - we call the update
        res = client.put(
            f"/api/v1/users/{default_user.id}/recipient_information",
            data=api_helpers.json_data({"legal_entity": legal_entity}),
            headers=api_helpers.json_headers(default_user),
        )

        # Then - the call succeeds and with the correct data
        assert res.status_code == 200


@mock.patch("views.payments.RecipientInformationResource._get_request_ip")
@mock.patch(
    "views.payments.RecipientInformationResource._stripe_client",
)
def test_update_recipient_information_accept_tos(
    mock_stripe_client,
    mock_get_request_ip,
    default_user,
    api_helpers,
    client,
    factories,
):
    mock_stripe_client.get_connect_account_for_user.return_value = (
        test_utils.stripe_business_practitioner_account
    )
    practitioner = factories.PractitionerUserFactory.create()
    practitioner.practitioner_profile.stripe_account_id = stripe_account_id

    # Given - we are accepting the terms of service with the following data
    accept_tos = True
    request_ip = "1.2.3.4"
    data = {
        "legal_entity": {
            "dob": {"day": "06", "month": "08", "year": "1986"},
            "address": {
                "line1": "1234 Fake St",
                "city": "Brooklyn",
                "state": "NY",
                "postal_code": "11222",
            },
            "first_name": "Elizabeth",
            "last_name": "Blackwell",
            "ssn_last_4": "0000",
            "id_number": "000000000",
            "type": "individual",
        },
        "accept_tos": accept_tos,
    }

    # When - we request to update the recipient info
    mock_get_request_ip.return_value = request_ip

    with enable_db_performance_warnings(
        database=db,
        failure_threshold=3,
    ):
        response = client.put(
            f"/api/v1/users/{default_user.id}/recipient_information",
            data=api_helpers.json_data(data),
            headers=api_helpers.json_headers(default_user),
        )

        # Then - the call succeeds and with the correct data (including ip)
        assert response.status_code == 200


@mock.patch(
    "views.payments.RecipientInformationResource._stripe_client",
)
@mock.patch("views.payments.marshmallow_experiment_enabled")
def test_update_recipient_information_with_type_change(
    experiment_enabled,
    mock_stripe_client,
    default_user,
    api_helpers,
    client,
    factories,
):
    mock_client = mock.Mock()
    mock_client.get_connect_account_for_user.return_value = test_utils.verified_account
    mock_client.edit_connect_account_for_user.return_value = test_utils.verified_account
    mock_client.create_connect_account.return_value = test_utils.verified_account
    mock_stripe_client.return_value = mock_client
    experiment_enabled.return_value = True
    practitioner = factories.PractitionerUserFactory.create()
    practitioner.practitioner_profile.stripe_account_id = stripe_account_id

    """If a user changes from company to individual or individual to company, handle that."""
    legal_entity = {
        "dob": {"day": "06", "month": "08", "year": "1986"},
        "address": {
            "line1": "1234 Fake St",
            "city": "Brooklyn",
            "state": "NY",
            "postal_code": "11222",
        },
        "first_name": "Elizabeth",
        "last_name": "Blackwell",
        "ssn_last_4": "0000",
        "id_number": "000000000",
        "type": "individual",
    }
    with enable_db_performance_warnings(
        database=db,
        failure_threshold=3,
    ):
        res = client.put(
            f"/api/v1/users/{default_user.id}/recipient_information",
            data=api_helpers.json_data({"legal_entity": legal_entity}),
            headers=api_helpers.json_headers(default_user),
        )
        assert res.status_code == 200


@mock.patch("views.payments.marshmallow_experiment_enabled")
@mock.patch("views.payments.RecipientInformationResource._stripe_client")
def test_get_recipient_information_success(
    mock_stripe_client, experiment_enabled, default_user, api_helpers, client, factories
):
    mock_client = mock.Mock()
    mock_client.get_connect_account_for_user.return_value = test_utils.verified_account
    mock_stripe_client.return_value = mock_client
    practitioner = factories.PractitionerUserFactory.create()
    practitioner.practitioner_profile.stripe_account_id = stripe_account_id

    experiment_enabled.return_value = False
    res = client.get(
        f"/api/v1/users/{default_user.id}/recipient_information",
        headers=api_helpers.json_headers(default_user),
    )
    assert res.status_code == 200
    assert res.json["individual"]["address"]["line1"] == "111 anywhere ave"

    experiment_enabled.return_value = True
    res = client.get(
        f"/api/v1/users/{default_user.id}/recipient_information",
        headers=api_helpers.json_headers(default_user),
    )
    assert res.status_code == 200
    assert res.json["individual"]["address"]["line1"] == "111 anywhere ave"


@mock.patch("views.payments.RecipientInformationResource._stripe_client")
def test_get_recipient_information_no_account(
    mock_stripe_client, default_user, api_helpers, client
):
    mock_client = mock.Mock()
    mock_client.get_connect_account_for_user.return_value = None
    mock_stripe_client.return_value = mock_client

    res = client.get(
        f"/api/v1/users/{default_user.id}/recipient_information",
        headers=api_helpers.json_headers(default_user),
    )

    assert res.status_code == 200
    assert res.json == {}


@mock.patch("views.payments.RecipientInformationResource._stripe_client")
def test_get_recipient_information_no_stripe_client(
    mock_stripe_client, default_user, api_helpers, client
):
    mock_stripe_client.return_value = None

    res = client.get(
        f"/api/v1/users/{default_user.id}/recipient_information",
        headers=api_helpers.json_headers(default_user),
    )

    assert res.status_code == 400
    assert "Cannot get Stripe account" in res.json["message"]


@mock.patch("views.payments.marshmallow_experiment_enabled")
@mock.patch("views.payments.RecipientInformationResource._stripe_client")
@mock.patch("views.payments.RecipientInformationResource._get_request_ip")
def test_post_recipient_information_success(
    mock_get_ip,
    mock_stripe_client,
    experiment_enabled,
    default_user,
    api_helpers,
    client,
    factories,
):
    mock_get_ip.return_value = "127.0.0.1"
    mock_client = mock.Mock()
    mock_connected_account = test_utils.stripe_business_practitioner_account
    mock_client.create_connect_account.return_value = mock_connected_account
    mock_stripe_client.return_value = mock_client
    practitioner = factories.PractitionerUserFactory.create()
    practitioner.practitioner_profile.stripe_account_id = None

    # Given - we are accepting the terms of service with the following data
    accept_tos = True
    data = {
        "legal_entity": {
            "dob": {"day": "06", "month": "08", "year": "1986"},
            "address": {
                "line1": "1234 Fake St",
                "city": "Brooklyn",
                "state": "NY",
                "postal_code": "11222",
            },
            "first_name": "Elizabeth",
            "last_name": "Blackwell",
            "ssn_last_4": "0000",
            "id_number": "000000000",
            "type": "individual",
        },
        "accept_tos": accept_tos,
    }

    experiment_enabled.return_value = False
    res = client.post(
        f"/api/v1/users/{practitioner.id}/recipient_information",
        data=api_helpers.json_data(data),
        headers=api_helpers.json_headers(practitioner),
    )
    assert res.status_code == 201
    assert res.json["company"]["address"]["line1"] == "111 anywhere ave"

    experiment_enabled.return_value = True
    experiment_enabled.side_effect = lambda flag_name, esp_id, email, default: True
    practitioner.practitioner_profile.stripe_account_id = None
    res = client.post(
        f"/api/v1/users/{practitioner.id}/recipient_information",
        data=api_helpers.json_data(data),
        headers=api_helpers.json_headers(practitioner),
    )
    assert res.status_code == 201
    assert res.json["company"]["address"]["line1"] == "111 anywhere ave"


@mock.patch("views.payments.marshmallow_experiment_enabled")
def test_post_recipient_information_existing_account(
    experiment_enabled, default_user, api_helpers, client, factories
):
    practitioner = factories.PractitionerUserFactory.create()
    practitioner.practitioner_profile.stripe_account_id = stripe_account_id

    experiment_enabled.return_value = False
    res = client.post(
        f"/api/v1/users/{practitioner.id}/recipient_information",
        data=api_helpers.json_data({"legal_entity": {}}),
        headers=api_helpers.json_headers(practitioner),
    )
    assert res.status_code == 400
    assert "You already have an account" in res.json["message"]

    experiment_enabled.return_value = True
    res = client.post(
        f"/api/v1/users/{practitioner.id}/recipient_information",
        data=api_helpers.json_data({"legal_entity": {}}),
        headers=api_helpers.json_headers(practitioner),
    )
    assert res.status_code == 400
    assert "You already have an account" in res.json["message"]


@mock.patch("views.payments.marshmallow_experiment_enabled")
@mock.patch("views.payments.RecipientInformationResource._stripe_client")
def test_update_recipient_information_no_account(
    mock_stripe_client, experiment_enabled, default_user, api_helpers, client
):
    mock_client = mock.Mock()
    mock_client.get_connect_account_for_user.return_value = None
    mock_stripe_client.return_value = mock_client
    experiment_enabled.return_value = True
    res = client.put(
        f"/api/v1/users/{default_user.id}/recipient_information",
        data=api_helpers.json_data({"legal_entity": {}}),
        headers=api_helpers.json_headers(default_user),
    )

    assert res.status_code == 400
    assert "Cannot get Stripe account" in res.json["message"]


@mock.patch("views.payments.marshmallow_experiment_enabled")
def test_get_legal_entity_information_from_json_individual(experiment_enabled):
    experiment_enabled.return_value = True
    raw_data = {
        "legal_entity": {
            "type": "individual",
            "first_name": "John",
            "last_name": "Doe",
            "ssn_last_4": "1234",
        }
    }

    result = RecipientInformationResource.get_legal_entity_information_from_json(
        raw_data
    )

    assert result["type"] == "individual"
    assert result["first_name"] == "John"
    assert result["last_name"] == "Doe"


@mock.patch("views.payments.marshmallow_experiment_enabled")
def test_get_legal_entity_information_from_json_invalid(experiment_enabled):
    experiment_enabled.return_value = True
    raw_data = {"not_legal_entity": {}}

    result = RecipientInformationResource.get_legal_entity_information_from_json(
        raw_data
    )

    assert result is None
