from __future__ import annotations

from unittest import mock

from pytests import stripe_fixtures as test_utils
from pytests.db_util import enable_db_performance_warnings

stripe_account_id = test_utils.stripe_account_id


@mock.patch(
    "views.payments.RecipientInformationResource._stripe_client",
)
def test_put_receipt_information(
    mock__stripe_client,
    client,
    api_helpers,
    db,
    factories,
):
    mock__stripe_client.get_connect_account_for_user.return_value = (
        test_utils.verified_account
    )

    practitioner = factories.PractitionerUserFactory.create()
    practitioner.practitioner_profile.stripe_account_id = stripe_account_id

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
        failure_threshold=8,
    ):
        res = client.put(
            f"/api/v1/users/{practitioner.id}/recipient_information",
            headers=api_helpers.standard_headers(practitioner),
            json={"legal_entity": legal_entity},
        )
        assert res.status_code == 200


@mock.patch(
    "views.payments.RecipientInformationResource._stripe_client",
)
def test_post_receipt_information(
    mock__stripe_client,
    client,
    api_helpers,
    db,
    factories,
):
    mock__stripe_client.get_connect_account_for_user.return_value = (
        test_utils.verified_account
    )

    practitioner = factories.PractitionerUserFactory.create()
    practitioner.practitioner_profile.stripe_account_id = None

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
        failure_threshold=8,
    ):
        res = client.post(
            f"/api/v1/users/{practitioner.id}/recipient_information",
            headers=api_helpers.standard_headers(practitioner),
            json={"legal_entity": legal_entity},
        )
        assert res.status_code == 201
