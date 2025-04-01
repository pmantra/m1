import json
from unittest import mock

from common.services.stripe import StripeCustomerClient
from pytests.factories import MemberFactory


def test_add_a_card(client, api_helpers, db):
    user = MemberFactory.create()
    mock_client = StripeCustomerClient("FAKE_KEY")
    mock_client.list_cards = mock.Mock(return_value=[])
    mock_client.get_customer = mock.Mock(return_value=mock.Mock(id=1))
    mock_client.audit = mock.Mock()
    assert user.profile.stripe_customer_id is None

    with mock.patch(
        "views.payments.new_stripe_customer", return_value="stripe_fake-user-id"
    ), mock.patch(
        "views.payments.UserPaymentMethodsResource._stripe_client",
        return_value=mock_client,
    ), mock.patch(
        "common.services.stripe.stripe.Customer.create_source",
        return_value=mock.Mock(fingerprint="fake"),
    ):
        res = client.post(
            f"/api/v1/users/{user.id}/payment_methods",
            headers=api_helpers.json_headers(user=user),
            data=api_helpers.json_data({"stripe_token": "stripe_fake-token"}),
        )

    assert res.status_code == 201
    db.session.expire(user)
    assert user.profile.stripe_customer_id == "stripe_fake-user-id"


def test_get_payment_methods(client, api_helpers, db):
    user = MemberFactory.create()
    mock_client = StripeCustomerClient("FAKE_KEY")
    tmp = {"id": "1", "brand": "1", "last4": "1234"}
    mock_client.list_cards = mock.Mock(return_value=[tmp])
    mock_client.get_customer = mock.Mock(return_value=mock.Mock(id=1))
    mock_client.audit = mock.Mock()
    assert user.profile.stripe_customer_id is None

    with mock.patch(
        "views.payments.UserPaymentMethodsResource._stripe_client",
        return_value=mock_client,
    ):
        res = client.get(
            f"/api/v1/users/{user.id}/payment_methods",
            headers=api_helpers.json_headers(user=user),
            data=api_helpers.json_data({"stripe_token": "stripe_fake-token"}),
        )

    assert res.status_code == 200
    assert json.loads(res.data.decode(encoding="utf-8")).get("data") == [tmp]
