from incentives.models.incentive import IncentiveAction
from incentives.schemas.incentive import IncentiveSchemaMsg


class TestUserIncentiveResource:
    def test_user_incentive__unauthenticated_user(
        self, default_user, client, api_helpers
    ):
        # When we send a request with no authenticated user
        resp = client.get(
            f"/api/v1/users/{default_user.id}/incentive",
            headers=api_helpers.json_headers(),
        )
        # Then we get a 401
        assert resp.status_code == 401

    def test_user_incentive__user_doesnt_exist(
        self, default_user, invalid_user_id, client, api_helpers
    ):
        # When we send a request with a user that doesnt exist
        resp = client.get(
            f"/api/v1/users/{invalid_user_id}/incentive",
            headers=api_helpers.json_headers(default_user),
        )
        # Then we get a 404
        assert resp.status_code == 404

    def test_user_incentive__user_doesnt_match_logged_user(
        self, default_user, factories, client, api_helpers
    ):
        # When we send a request with a user that doesnt match the logged user
        another_default_user = factories.DefaultUserFactory()
        resp = client.get(
            f"/api/v1/users/{another_default_user.id}/incentive",
            headers=api_helpers.json_headers(default_user),
        )
        # Then we get a 404
        assert resp.status_code == 404

    def test_user_incentive__missing_incentivized_action(
        self, client, api_helpers, default_user
    ):
        # When we send a request with no incentivized_action param
        resp = client.get(
            f"/api/v1/users/{default_user.id}/incentive?track=adoption",
            headers=api_helpers.json_headers(default_user),
        )
        # Then we get a 400
        assert resp.status_code == 400

        assert api_helpers.load_json(resp)["errors"][0] == {
            "status": 400,
            "title": "Bad Request",
            "detail": "Missing data for required field.",
            "field": "incentivized_action",
        }

    def test_user_incentive__invalid_incentivized_action(
        self, client, api_helpers, default_user
    ):
        # Given
        invalid_incentivized_action = "hello"
        # When we send a request with an invalid incentivized_action param
        resp = client.get(
            f"/api/v1/users/{default_user.id}/incentive?incentivized_action={invalid_incentivized_action}&track=adoption",
            headers=api_helpers.json_headers(default_user),
        )
        # Then we get a 400
        assert resp.status_code == 400
        assert api_helpers.load_json(resp)["errors"][0] == {
            "status": 400,
            "title": "Bad Request",
            "detail": IncentiveSchemaMsg.INVALID_INCENTIVIZED_ACTION,
            "field": "incentivized_action",
        }

    def test_user_incentive__missing_track(self, client, api_helpers, default_user):
        # When we send a request with no track param
        resp = client.get(
            f"/api/v1/users/{default_user.id}/incentive?incentivized_action=ca_intro",
            headers=api_helpers.json_headers(default_user),
        )
        # Then we get a 400
        assert resp.status_code == 400
        assert api_helpers.load_json(resp)["errors"][0] == {
            "status": 400,
            "title": "Bad Request",
            "detail": "Missing data for required field.",
            "field": "track",
        }

    def test_user_incentive__invalid_track(self, client, api_helpers, default_user):
        # Given
        invalid_track = "hello"
        # When we send a request with an invalid track param
        resp = client.get(
            f"/api/v1/users/{default_user.id}/incentive?incentivized_action=ca_intro&track={invalid_track}",
            headers=api_helpers.json_headers(default_user),
        )
        # Then we get a 400
        assert resp.status_code == 400
        assert api_helpers.load_json(resp)["errors"][0] == {
            "status": 400,
            "title": "Bad Request",
            "detail": f"'{invalid_track}' is not a valid track",
            "field": "track",
        }

    def test_user_incentive__incentive_exists(
        self, user_and_incentive, client, api_helpers, default_user, factories
    ):

        # Given a user and an incentive configured for them
        user, incentive = user_and_incentive
        user_id = user.id
        incentive_action = incentive.incentive_organizations[0].action
        track = incentive.incentive_organizations[0].track_name

        # When we request their incentive
        resp = client.get(
            f"/api/v1/users/{user_id}/incentive?incentivized_action={incentive_action._name_.lower()}&track={track}",
            headers=api_helpers.json_headers(user),
        )

        # Then we get a 200 with the incentive info
        assert resp.status_code == 200

        expected_incentive_data = {
            "incentive_id": incentive.id,
            "incentive_type": incentive.type._name_.lower(),
            "design_asset": incentive.design_asset._name_.lower(),
            "amount": incentive.amount,
        }
        assert api_helpers.load_json(resp) == expected_incentive_data

    def test_user_incentive__incentive_doesnt_exist(
        self, client, api_helpers, default_user, factories
    ):
        # Given a user but no incentive configured for it
        uoe = factories.UserOrganizationEmployeeFactory()
        user = uoe.user
        user_id = user.id
        incentive_action = IncentiveAction.CA_INTRO
        track = "adoption"

        # When we request their incentive
        resp = client.get(
            f"/api/v1/users/{user_id}/incentive?incentivized_action={incentive_action._name_.lower()}&track={track}",
            headers=api_helpers.json_headers(user),
        )

        # Then we get a 200 with no incentive info
        assert resp.status_code == 200
        assert api_helpers.load_json(resp) == {}
