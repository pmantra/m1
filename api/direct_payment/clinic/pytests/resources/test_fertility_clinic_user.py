from unittest.mock import patch

from authn.models.user import User


def test_me(client, api_helpers, active_fc_user):
    with patch("common.services.api._get_user") as mock_get_user:
        given_user = User(id=active_fc_user.user_id, active=True)
        mock_get_user.return_value = given_user

        res = client.get(
            "/api/v1/direct_payment/clinic/me",
            headers=api_helpers.json_headers(user=given_user),
        )
    assert res.status_code == 200

    data = api_helpers.load_json(res)
    assert data["id"] == active_fc_user.id
    assert data["first_name"] == active_fc_user.first_name
    assert data["last_name"] == active_fc_user.last_name
    assert data["role"] == active_fc_user.role
