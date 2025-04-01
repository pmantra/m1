import json
from unittest import mock

from care_advocates.models.assignable_advocates import DEFAULT_CARE_COORDINATOR_EMAIL
from utils.rotatable_token import BRAZE_BULK_MESSAGING_TOKEN
from utils.service_owner_mapper import service_ns_team_mapper

FAKE_CONTENT_TOKEN = "blerp"


@mock.patch.object(BRAZE_BULK_MESSAGING_TOKEN, "primary", FAKE_CONTENT_TOKEN)
class TestBrazeBulkMessageResource:
    @mock.patch("messaging.resources.braze.send_to_zendesk")
    def test_post(
        self,
        mock_send_to_zendesk,
        factories,
        client,
        api_helpers,
        default_user,
        braze_ips,
    ):
        # Given
        factories.PractitionerUserFactory(
            email=DEFAULT_CARE_COORDINATOR_EMAIL
        )  # So that create_cx_message passes

        # When
        resp = client.post(
            "/api/v1/vendor/braze/bulk_messaging",
            data=json.dumps(
                {
                    "message": "a_message",
                    "user_id": default_user.esp_id,
                    "campaign_id": 1,
                    "dispatch_id": 1,
                    "message_type": "a_message_type",
                    "token": FAKE_CONTENT_TOKEN,
                }
            ),
        )

        # Then
        expected_service_ns = "messaging_system"
        mock_send_to_zendesk.delay.assert_called_once_with(
            mock.ANY,
            initial_cx_message=True,
            user_need_when_solving_ticket="customer-need-member-proactive-outreach-other",
            service_ns=expected_service_ns,
            team_ns=service_ns_team_mapper.get(expected_service_ns),
            caller="BrazeBulkMessageResource",
        )

        assert resp.status_code == 200
