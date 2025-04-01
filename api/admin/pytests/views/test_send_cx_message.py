from unittest import mock

from care_advocates.models.assignable_advocates import DEFAULT_CARE_COORDINATOR_EMAIL


class TestSendCXMessage:
    @mock.patch("admin.blueprints.actions.flash")
    @mock.patch("admin.blueprints.actions.send_to_zendesk")
    @mock.patch("admin.blueprints.actions.notify_new_message")
    def test_send_cx_message(
        self,
        mock_notify_new_message,
        mock_send_to_zendesk,
        mock_flash,
        default_user,
        admin_client,
        factories,
    ):
        # Given
        message_text = "the_best_message_text"
        factories.PractitionerUserFactory(
            email=DEFAULT_CARE_COORDINATOR_EMAIL
        )  # So that create_cx_message passes

        # When
        res = admin_client.post(
            "/admin/actions/send_cx_message",
            data={
                "user_id": default_user.id,
                "message_text": message_text,
            },
            headers={"Referer": "best_referer"},
        )
        # Then
        mock_notify_new_message.delay.assert_called_once_with(default_user.id, mock.ANY)
        mock_send_to_zendesk.delay.assert_called_once_with(
            mock.ANY,
            initial_cx_message=True,
            user_need_when_solving_ticket="customer-need-member-proactive-outreach-other",
            caller="send_cx_message",
        )
        mock_flash.assert_called_once_with("All set adding 1 Message!")
        assert res.status_code == 302
