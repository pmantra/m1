from unittest.mock import ANY, patch

from sqlalchemy import func

from messaging.models.messaging import Message
from messaging.tasks.messaging_reconciliation import (
    MAVEN_TO_ZENDESK_RECONCILIATION_LIST_KEY,
    maven_to_zendesk_message_reconciliation,
)


class TestMavenToZendeskMessageReconciliation:
    @patch(
        "messaging.tasks.messaging_reconciliation.ReconciliationZendeskTicket.update_zendesk"
    )
    def test_maven_to_zendesk_message_reconciliation__ff_is_off(
        self, mock_update_zendesk, maven_to_zendesk_reconciliation_ff_off
    ):

        # When
        maven_to_zendesk_message_reconciliation()

        # Then, internal functions triggered by job do not get called
        assert not mock_update_zendesk.called

    @patch("messaging.tasks.messaging_reconciliation.log.info")
    @patch(
        "messaging.tasks.messaging_reconciliation.ReconciliationZendeskTicket.update_zendesk"
    )
    @patch("messaging.tasks.messaging_reconciliation.redis_client")
    def test_maven_to_zendesk_message_reconciliation__empty_reconciliation_list(
        self,
        mock_redis_client_method,
        mock_update_zendesk,
        mock_log_info,
        maven_to_zendesk_reconciliation_ff_on,
        db,
    ):

        # Given reconciliation list is empty
        mock_redis_client_method.return_value.smembers.return_value = {}

        # When calling reconciliation
        maven_to_zendesk_message_reconciliation()

        # Then we log the case and assert send_to_zendesk is never called
        mock_log_info.assert_called_with(
            "maven_to_zendesk_message_reconciliation job picked up no messages to reconcile",
            created_at_before=ANY,
            created_at_after=ANY,
        )
        assert not mock_update_zendesk.called

    @patch("messaging.tasks.messaging_reconciliation.log.warning")
    @patch(
        "messaging.tasks.messaging_reconciliation.ReconciliationZendeskTicket.update_zendesk"
    )
    @patch("messaging.tasks.messaging_reconciliation.redis_client")
    def test_maven_to_zendesk_message_reconciliation__wrong_message_id_in_reconciliation_list(
        self,
        mock_redis_client_method,
        mock_update_zendesk,
        mock_log_warning,
        maven_to_zendesk_reconciliation_ff_on,
        db,
    ):

        # Given reconciliation list has an incorrect message id
        max_message_id = db.session.query(func.max(Message.id)).first()[0]
        invalid_message_id = (max_message_id + 1) if max_message_id else 1

        mock_redis_client_method.return_value.smembers.return_value = {
            invalid_message_id
        }

        # When calling reconciliation
        maven_to_zendesk_message_reconciliation()

        # Then we log the case and assert send_to_zendesk is never called
        mock_log_warning.assert_called_with(
            "Could not find message as part of maven_to_zendesk_message_reconciliation.",
            message_id=invalid_message_id,
        )
        assert not mock_update_zendesk.called

    @patch("messaging.tasks.messaging_reconciliation.log.info")
    @patch(
        "messaging.tasks.messaging_reconciliation.ReconciliationZendeskTicket.update_zendesk"
    )
    @patch("messaging.tasks.messaging_reconciliation.redis_client")
    def test_maven_to_zendesk_message_reconciliation__not_old_enough_message_in_reconciliation_list(
        self,
        mock_redis_client_method,
        mock_update_zendesk,
        mock_log_info,
        now_message,
        maven_to_zendesk_reconciliation_ff_on,
        db,
    ):

        # Given reconciliation list with a too recent message
        mock_redis_client_method.return_value.smembers.return_value = {now_message.id}

        # When calling reconciliation
        maven_to_zendesk_message_reconciliation()

        # Then we log the case and assert send_to_zendesk is never called
        mock_log_info.assert_called_with(
            "Skipping message for reconciliation given that it is not old enough",
            message_id=now_message.id,
            created_at_before=ANY,
            message_created_at=ANY,
        )
        assert not mock_update_zendesk.called

    @patch("messaging.tasks.messaging_reconciliation.log.info")
    @patch(
        "messaging.tasks.messaging_reconciliation.ReconciliationZendeskTicket.update_zendesk"
    )
    @patch("messaging.tasks.messaging_reconciliation.redis_client")
    def test_maven_to_zendesk_message_reconciliation__too_old_message_in_reconciliation_list(
        self,
        mock_redis_client_method,
        mock_update_zendesk,
        mock_log_info,
        two_days_ago_message,
        maven_to_zendesk_reconciliation_ff_on,
        db,
    ):
        # Given reconciliation list with a too old message
        mock_redis_client_method.return_value.smembers.return_value = {
            two_days_ago_message.id
        }

        # When calling reconciliation
        maven_to_zendesk_message_reconciliation()

        # Then we log the case and assert send_to_zendesk is never called
        mock_log_info.assert_called_with(
            "Removing message from reconciliation list as it is too old",
            message_id=two_days_ago_message.id,
            message_created_at=ANY,
            created_at_after=ANY,
        )
        mock_redis_client_method.return_value.srem.assert_called_once_with(
            MAVEN_TO_ZENDESK_RECONCILIATION_LIST_KEY, two_days_ago_message.id
        )
        assert not mock_update_zendesk.called

    @patch("messaging.tasks.messaging_reconciliation.log.info")
    @patch(
        "messaging.tasks.messaging_reconciliation.ReconciliationZendeskTicket.update_zendesk"
    )
    @patch("messaging.tasks.messaging_reconciliation.redis_client")
    def test_maven_to_zendesk_message_reconciliation__message_with_zd_id_in_reconciliation_list(
        self,
        mock_redis_client_method,
        mock_update_zendesk,
        mock_log_info,
        one_hour_ago_message,
        maven_to_zendesk_reconciliation_ff_on,
        db,
    ):
        # Given reconciliation list with a message that has zd id
        one_hour_ago_message.zendesk_comment_id = 1
        db.session.commit()
        mock_redis_client_method.return_value.smembers.return_value = {
            one_hour_ago_message.id
        }

        # When calling reconciliation
        maven_to_zendesk_message_reconciliation()

        # Then we log the case and assert send_to_zendesk is never called
        mock_log_info.assert_called_with(
            "Removing message from reconciliation list as it already has a zendesk_comment_id",
            message_id=one_hour_ago_message.id,
        )
        mock_redis_client_method.return_value.srem.assert_called_once_with(
            MAVEN_TO_ZENDESK_RECONCILIATION_LIST_KEY, one_hour_ago_message.id
        )
        assert not mock_update_zendesk.called

    @patch("messaging.tasks.messaging_reconciliation.braze.update_message_attrs")
    @patch(
        "messaging.tasks.messaging_reconciliation.ReconciliationZendeskTicket.update_zendesk"
    )
    @patch("messaging.tasks.messaging_reconciliation.redis_client")
    def test_maven_to_zendesk_message_reconciliation__messages_reconciled(
        self,
        mock_redis_client_method,
        mock_update_zendesk,
        mock_update_message_attrs,
        one_hour_ago_message,
        maven_to_zendesk_reconciliation_ff_on,
        db,
    ):

        # Given reconciliation list with valid message to be reconciled
        mock_redis_client_method.return_value.smembers.return_value = {
            one_hour_ago_message.id,
        }

        # When calling reconciliation
        maven_to_zendesk_message_reconciliation()

        # Then, update_zendesk and update_message_attrs are called once
        mock_update_zendesk.assert_called_once()
        mock_update_message_attrs.assert_called_once_with(
            one_hour_ago_message.channel.member
        )

    @patch("messaging.tasks.messaging_reconciliation.braze.update_message_attrs")
    @patch(
        "messaging.tasks.messaging_reconciliation.ReconciliationZendeskTicket.update_zendesk"
    )
    @patch("messaging.tasks.messaging_reconciliation.redis_client")
    def test_maven_to_zendesk_message_reconciliation__only_max_n_messages_reconciled(
        self,
        mock_redis_client_method,
        mock_update_zendesk,
        mock_update_message_attrs,
        one_hour_ago_message,
        two_hours_ago_message,
        maven_to_zendesk_reconciliation_ff_on,
    ):

        # Given two messages in list for reconciliation, both appropriate for reconciliation
        mock_redis_client_method.return_value.smembers.return_value = {
            one_hour_ago_message.id,
            two_hours_ago_message.id,
        }

        # When calling reconciliation with max jobs = 1
        maven_to_zendesk_message_reconciliation(max_per_job_run=1)

        # Then, update_zendesk and update_message_attrs are called once for one of the eligible messages
        mock_update_zendesk.assert_called_once()
        mock_update_message_attrs.assert_called_once()
        member_arg = mock_update_message_attrs.call_args_list[0][0][0]
        assert member_arg in (
            one_hour_ago_message.channel.member,
            two_hours_ago_message.channel.member,
        )
