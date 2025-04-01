import random
from unittest import mock

from utils.rotatable_token import BRAZE_CONNECTED_CONTENT_TOKEN

FAKE_CONTENT_TOKEN = "blerp"


@mock.patch.object(BRAZE_CONNECTED_CONTENT_TOKEN, "primary", FAKE_CONTENT_TOKEN)
class TestBrazeConnectedContentResource:
    def test_invalid_token(self, client, api_helpers, default_user, braze_ips):
        resp = client.get(
            "/api/v1/vendor/braze/connected_content",
            query_string={"token": "blorp", "esp_id": default_user},
            headers={"X-Real-IP": random.sample(braze_ips, 1)},
        )
        assert resp.status_code == 403
        assert api_helpers.load_json(resp)["message"] == "Invalid Token"

    def test_unknown_user(self, client, api_helpers, default_user, braze_ips):
        resp = client.get(
            "/api/v1/vendor/braze/connected_content",
            query_string={"token": FAKE_CONTENT_TOKEN, "esp_id": "blerp"},
            headers={"X-Real-IP": random.sample(braze_ips, 1)},
        )
        assert resp.status_code == 404
        assert api_helpers.load_json(resp)["message"] == "user not found!"

    def test_no_track(self, client, api_helpers, default_user, braze_ips):
        resp = client.get(
            "/api/v1/vendor/braze/connected_content",
            query_string={"token": FAKE_CONTENT_TOKEN, "esp_id": default_user.esp_id},
            headers={"X-Real-IP": random.sample(braze_ips, 1)},
        )
        assert resp.status_code == 400
        assert api_helpers.load_json(resp)["message"] == "user not in any track"

    def test_no_resource_configured(
        self, client, api_helpers, enterprise_user, braze_ips
    ):
        resp = client.get(
            "/api/v1/vendor/braze/connected_content",
            query_string={
                "token": FAKE_CONTENT_TOKEN,
                "esp_id": enterprise_user.esp_id,
            },
            headers={"X-Real-IP": random.sample(braze_ips, 1)},
        )
        assert resp.status_code == 404
        assert (
            api_helpers.load_json(resp)["message"]
            == "connected content resource not found"
        )

    def test_success(
        self,
        client,
        api_helpers,
        enterprise_user,
        braze_ips,
        resource_1,
        resource_2,
    ):

        # Get content for type email1
        resp = client.get(
            "/api/v1/vendor/braze/connected_content",
            query_string={
                "token": FAKE_CONTENT_TOKEN,
                "esp_id": enterprise_user.esp_id,
                "type": "email1",
            },
            headers={"X-Real-IP": random.sample(braze_ips, 1)},
        )
        assert resp.status_code == 200
        assert api_helpers.load_json(resp) == {
            "image": resource_1.image.asset_url(),
            "copy": resource_1.body,
            "title": resource_1.title,
            "slug": resource_1.slug,
            "blerp": "blah",
        }

        # Get content for type email1 and email2
        resp = client.get(
            "/api/v1/vendor/braze/connected_content",
            query_string={
                "token": FAKE_CONTENT_TOKEN,
                "esp_id": enterprise_user.esp_id,
                "types": ["email1", "email2"],
            },
            headers={"X-Real-IP": random.sample(braze_ips, 1)},
        )
        assert resp.status_code == 200
        assert api_helpers.load_json(resp) == {
            "email1": {
                "image": resource_1.image.asset_url(),
                "copy": resource_1.body,
                "title": resource_1.title,
                "slug": resource_1.slug,
                "blerp": "blah",
            },
            "email2": {
                "image": resource_2.image.asset_url(),
                "copy": resource_2.body,
                "title": resource_2.title,
                "slug": resource_2.slug,
            },
        }
