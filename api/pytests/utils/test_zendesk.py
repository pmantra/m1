from unittest.mock import ANY, MagicMock, patch

import pytest
from sqlalchemy.exc import SQLAlchemyError
from zenpy.lib.api_objects import Ticket as ZDTicket

from messaging.models.messaging import Channel, Message
from messaging.services.zendesk import (
    MAVEN_TO_ZENDESK_RECONCILIATION_LIST_KEY,
    MessagingZendeskTicket,
    ZendeskInvalidRecordException,
)
from storage.connection import db


@pytest.fixture()
def message_channel(factories):
    member = factories.MemberFactory.create()
    practitioner = factories.PractitionerUserFactory.create()
    return Channel.get_or_create_channel(practitioner, [member])


def test_desired_ticket_tags_contains_new_automated_message(message_channel):
    """
    Scenario:
        A message is created with a `braze_campaign_id`, assert that the tag
        to indicate that a new automated message is added to the Zendesk tags.
    """
    message = Message(
        channel_id=message_channel.id,
        braze_campaign_id="foobar1234",
        user=message_channel.member,
    )
    db.session.add(message)
    db.session.commit()

    mzt = MessagingZendeskTicket(message=message, initial_cx_message=True)

    assert MessagingZendeskTicket.NEW_AUTOMATED_MESSAGE in mzt.desired_ticket_tags


def test_desired_ticket_tags_contains_automated_message_in_thread(message_channel):
    """
    Scenario:
        A message comes in that is automated (contains a braze_campaign_id), followed by a
        second message, the tags in this case will not contain the new automated message tag,
        but will contain a tag to indicate that there is an automated message in the thread.
    """
    first_message = Message(
        channel_id=message_channel.id,
        braze_campaign_id="foobar1234",
        user=message_channel.member,
    )
    second_message = Message(
        channel_id=message_channel.id,
        braze_campaign_id=None,
        user=message_channel.member,
    )

    db.session.add_all([first_message, second_message])
    db.session.commit()

    mzt = MessagingZendeskTicket(message=second_message, initial_cx_message=True)

    assert MessagingZendeskTicket.AUTOMATED_MESSAGE_IN_THREAD in mzt.desired_ticket_tags
    assert MessagingZendeskTicket.NEW_AUTOMATED_MESSAGE not in mzt.desired_ticket_tags


def test_update_zendesk_with_existing_tags(factories, message_channel, mock_zendesk):
    """
    Scenario:
        We don't want to remove tags that users may have added when updating Zendesk tags.
        Assert that any tags added by a user in Zendesk are preserved when regenerating the
        desired_ticket_tags.
    """
    ticket = MessagingZendeskTicket(
        message=factories.MessageFactory(
            user=message_channel.member,
            channel=message_channel,
            braze_campaign_id="foobar1234",
        ),
        initial_cx_message=False,
    )
    ticket.update_zendesk()
    user_tag = "user_tag"
    mock_zendesk.add_user_tags_to_ticket(ticket.recorded_ticket_id, [user_tag])
    ticket.update_zendesk()
    assert user_tag in ticket.desired_ticket_tags


@pytest.mark.parametrize(
    argnames="ticket_status",
    argvalues=["open", "closed"],
)
@pytest.mark.parametrize(
    argnames="comment_id",
    argvalues=["the_best_zendesk_comment_id", None],
)
@patch("messaging.services.zendesk.reconcile_zendesk_comment_id.delay")
@patch("messaging.services.zendesk.MessagingZendeskTicket.record_comment_id")
@patch("messaging.services.zendesk.SynchronizedZendeskTicket._parse_comment_id")
@patch("messaging.services.zendesk.SynchronizedZendeskTicket._create_new_ticket")
@patch(
    "messaging.services.zendesk.SynchronizedZendeskTicket._comment_on_existing_ticket"
)
@patch("messaging.services.zendesk.SynchronizedZendeskTicket._get_existing_ticket")
@patch("messaging.services.zendesk.redis_client")
def test_update_zendesk__happy_paths(
    mock_redis_client_method,
    mock_get_existing_ticket,
    mock_comment_on_existing_ticket,
    mock_create_new_ticket,
    mock_parse_comment_id,
    mock_record_comment_id,
    mock_reconcile_zendesk_comment_id_delay,
    comment_id,
    ticket_status,
    message_channel,
    factories,
):
    # Given
    mocked_ticket = MagicMock(status=ticket_status)
    mock_get_existing_ticket.return_value = mocked_ticket

    mocked_ticket_audit = MagicMock()
    mocked_ticket_audit.ticket.id = 1
    mock_comment_on_existing_ticket.return_value = mocked_ticket_audit
    mock_create_new_ticket.return_value = mocked_ticket_audit
    mock_parse_comment_id.return_value = comment_id

    # Create a ticket to update
    message = factories.MessageFactory(
        user=message_channel.member,
        channel=message_channel,
    )
    mzt = MessagingZendeskTicket(
        message=message,
        initial_cx_message=False,
    )

    # When
    mzt.update_zendesk()

    # Then, internal functions called
    mock_redis_client_method.return_value.sadd.assert_called_once_with(
        MAVEN_TO_ZENDESK_RECONCILIATION_LIST_KEY, str(message.id)
    )
    mock_get_existing_ticket.assert_called_once_with(str(message.id))
    # We call _comment_on_existing_ticket or _create_new_ticket depending on ticket status
    if ticket_status == "open":
        mock_comment_on_existing_ticket.assert_called_once_with(
            mocked_ticket, str(message.id)
        )
    elif ticket_status == "closed":
        mock_create_new_ticket.assert_called_once_with(mocked_ticket, str(message.id))
    mock_parse_comment_id.assert_called_once_with(mocked_ticket_audit, mzt.user_id)
    # We call record_comment_id or reconcile_zendesk_comment_id depending on value of comment_id
    if comment_id:
        mock_record_comment_id.assert_called_once_with(comment_id)
        mock_redis_client_method.return_value.srem.assert_called_once_with(
            MAVEN_TO_ZENDESK_RECONCILIATION_LIST_KEY, str(message.id)
        )
    else:
        mock_reconcile_zendesk_comment_id_delay.assert_called_once_with(
            ticket_id=mocked_ticket_audit.ticket.id,
            message_id=str(message.id),
            team_ns="virtual_care",
        )


@pytest.mark.parametrize(
    argnames="function_that_raises_expectation",
    argvalues=["_get_existing_ticket", "_comment_on_existing_ticket"],
)
@patch(
    "messaging.services.zendesk.SynchronizedZendeskTicket._comment_on_existing_ticket"
)
@patch("messaging.services.zendesk.SynchronizedZendeskTicket._get_existing_ticket")
@patch("messaging.services.zendesk.redis_client")
def test_update_zendesk__zendesk_invalid_record_exception_when_getting_ticket(
    mock_redis_client_method,
    mock_get_existing_ticket,
    mock_comment_on_existing_ticket,
    function_that_raises_expectation,
    message_channel,
    factories,
):

    # Given
    mocked_ticket = MagicMock(status="open")
    if function_that_raises_expectation == "_get_existing_ticket":
        mock_get_existing_ticket.side_effect = ZendeskInvalidRecordException
    else:
        mock_get_existing_ticket.return_value = mocked_ticket
        mock_comment_on_existing_ticket.side_effect = ZendeskInvalidRecordException

    # Create a ticket to update
    message = factories.MessageFactory(
        user=message_channel.member,
        channel=message_channel,
    )
    mzt = MessagingZendeskTicket(
        message=message,
        initial_cx_message=False,
    )

    # Then
    with pytest.raises(ZendeskInvalidRecordException):
        # When
        mzt.update_zendesk()

    # Then, internal functions called
    mock_redis_client_method.return_value.sadd.assert_called_once_with(
        MAVEN_TO_ZENDESK_RECONCILIATION_LIST_KEY, str(message.id)
    )
    mock_get_existing_ticket.assert_called_once_with(str(message.id))
    if function_that_raises_expectation == "_comment_on_existing_ticket":
        mock_comment_on_existing_ticket.assert_called_once_with(
            mocked_ticket, str(message.id)
        )
    mock_redis_client_method.return_value.srem.assert_called_once_with(
        MAVEN_TO_ZENDESK_RECONCILIATION_LIST_KEY, str(message.id)
    )


@pytest.mark.parametrize(
    argnames="function_that_raises_expectation",
    argvalues=["_get_existing_ticket", "_comment_on_existing_ticket"],
)
@patch(
    "messaging.services.zendesk.SynchronizedZendeskTicket._comment_on_existing_ticket"
)
@patch("messaging.services.zendesk.SynchronizedZendeskTicket._get_existing_ticket")
@patch("messaging.services.zendesk.redis_client")
def test_update_zendesk__generic_exception_when_getting_ticket(
    mock_redis_client_method,
    mock_get_existing_ticket,
    mock_comment_on_existing_ticket,
    function_that_raises_expectation,
    message_channel,
    factories,
):

    # Given
    exception_message = "an_exception_message"
    mocked_ticket = MagicMock(status="open")
    if function_that_raises_expectation == "_get_existing_ticket":
        mock_get_existing_ticket.side_effect = Exception(exception_message)
    else:
        mock_get_existing_ticket.return_value = mocked_ticket
        mock_comment_on_existing_ticket.side_effect = Exception(exception_message)

    # Create a ticket to update
    message = factories.MessageFactory(
        user=message_channel.member,
        channel=message_channel,
    )
    mzt = MessagingZendeskTicket(
        message=message,
        initial_cx_message=False,
    )

    # Then
    with pytest.raises(Exception, match=exception_message):
        # When
        mzt.update_zendesk()

    # Then, internal functions called
    mock_redis_client_method.return_value.sadd.assert_called_once_with(
        MAVEN_TO_ZENDESK_RECONCILIATION_LIST_KEY, str(message.id)
    )
    mock_get_existing_ticket.assert_called_once_with(str(message.id))
    if function_that_raises_expectation == "_comment_on_existing_ticket":
        mock_comment_on_existing_ticket.assert_called_once_with(
            mocked_ticket, str(message.id)
        )
    # Message not removed from reconciliation list
    assert not mock_redis_client_method.return_value.srem.called


@pytest.mark.parametrize(
    argnames="exception_raised",
    argvalues=[SQLAlchemyError, Exception],
)
@pytest.mark.parametrize(
    argnames="function_that_raises_expectation",
    argvalues=["_parse_comment_id", "record_comment_id"],
)
@patch("messaging.services.zendesk.MessagingZendeskTicket.record_comment_id")
@patch("messaging.services.zendesk.SynchronizedZendeskTicket._parse_comment_id")
@patch(
    "messaging.services.zendesk.SynchronizedZendeskTicket._comment_on_existing_ticket"
)
@patch("messaging.services.zendesk.SynchronizedZendeskTicket._get_existing_ticket")
@patch("messaging.services.zendesk.redis_client")
def test_update_zendesk__exception_during_comment_id_processing(
    mock_redis_client_method,
    mock_get_existing_ticket,
    mock_comment_on_existing_ticket,
    mock_parse_comment_id,
    mock_record_comment_id,
    function_that_raises_expectation,
    exception_raised,
    message_channel,
    factories,
):

    # Given
    mocked_ticket = MagicMock(status="open")
    mock_get_existing_ticket.return_value = mocked_ticket

    mocked_ticket_audit = MagicMock()
    mocked_ticket_audit.ticket.id = 1
    mock_comment_on_existing_ticket.return_value = mocked_ticket_audit

    comment_id = "a_comment_id"
    if function_that_raises_expectation == "_parse_comment_id":
        mock_parse_comment_id.side_effect = exception_raised
    elif function_that_raises_expectation == "record_comment_id":
        mock_parse_comment_id.return_value = comment_id
        mock_record_comment_id.side_effect = exception_raised

    # Create a ticket to update
    message = factories.MessageFactory(
        user=message_channel.member,
        channel=message_channel,
    )
    mzt = MessagingZendeskTicket(
        message=message,
        initial_cx_message=False,
    )

    # Then
    with pytest.raises(exception_raised):
        # When
        mzt.update_zendesk()

    # Then, internal functions called
    mock_redis_client_method.return_value.sadd.assert_called_once_with(
        MAVEN_TO_ZENDESK_RECONCILIATION_LIST_KEY, str(message.id)
    )
    mock_get_existing_ticket.assert_called_once_with(str(message.id))
    mock_comment_on_existing_ticket.assert_called_once_with(
        mocked_ticket, str(message.id)
    )
    mock_parse_comment_id.assert_called_once_with(mocked_ticket_audit, mzt.user_id)

    if function_that_raises_expectation == "record_comment_id":
        mock_record_comment_id.assert_called_once_with(comment_id)
    assert not mock_redis_client_method.return_value.srem.called


@patch("messaging.services.zendesk.ZendeskClient.update_ticket")
@patch(
    "messaging.services.zendesk.SynchronizedZendeskTicket._set_user_need_if_solving_ticket"
)
@patch("messaging.services.zendesk.SynchronizedZendeskTicket._compose_comment")
def test__comment_on_existing_ticket(
    mock_compose_comment,
    mock_set_user_need_if_solving_ticket,
    mock_update_ticket,
    message_channel,
    factories,
):

    # Create a ticket to comment on
    message = factories.MessageFactory(
        user=message_channel.member,
        channel=message_channel,
    )
    mzt = MessagingZendeskTicket(
        message=message,
        initial_cx_message=False,
    )

    ticket = ZDTicket()

    # When
    mzt._comment_on_existing_ticket(ticket, message.id)

    # Then
    mock_compose_comment.assert_called_once()
    mock_set_user_need_if_solving_ticket.assert_called_once_with(ticket)
    mock_update_ticket.assert_called_once_with(
        ticket, mzt.user_id, called_by="MessagingZendeskTicket", message_id=message.id
    )


@patch("messaging.services.zendesk.ZendeskClient.create_ticket")
@patch(
    "messaging.services.zendesk.SynchronizedZendeskTicket._set_user_need_if_solving_ticket"
)
@patch("messaging.services.zendesk.SynchronizedZendeskTicket._compose_comment")
@patch("messaging.services.zendesk.SynchronizedZendeskTicket._get_or_create_zenpy_user")
def test__create_new_ticket(
    mock_get_or_create_zenpy_user,
    mock_compose_comment,
    mock_set_user_need_if_solving_ticket,
    mock_create_ticket,
    message_channel,
    factories,
):

    # Given
    requester_id = 1
    mock_compose_comment.return_value = "a_comment"
    mock_get_or_create_zenpy_user.return_value = MagicMock(id=requester_id)
    message = factories.MessageFactory(
        user=message_channel.member,
        channel=message_channel,
    )
    mzt = MessagingZendeskTicket(
        message=message,
        initial_cx_message=False,
    )
    existing_ticket = ZDTicket()

    # When
    mzt._create_new_ticket(existing_ticket, message.id)

    # Then
    mock_get_or_create_zenpy_user.assert_called_once()
    mock_set_user_need_if_solving_ticket.assert_called_once()
    mock_create_ticket.assert_called_once_with(
        ANY,
        mzt.user_id,
        requester_id,
        called_by="MessagingZendeskTicket",
        message_id=message.id,
    )


class TestSetUserNeedIfSolvingTicket:
    @patch(
        "messaging.services.zendesk.enable_set_user_need_if_solving_ticket",
        return_value=False,
    )
    def test_set_user_need_if_solving_ticket__ff_off(
        self, mock_enable_set_user_need_if_solving_ticket, message_channel, factories
    ):

        # Given
        ticket = ZDTicket(status="solved")
        assert ticket.custom_fields == None

        message = factories.MessageFactory(
            user=message_channel.member,
            channel=message_channel,
        )
        mzt = MessagingZendeskTicket(
            message=message,
            initial_cx_message=False,
            user_need_when_solving_ticket="a_great_user_need_when_solving_ticket",
        )

        # When
        mzt._set_user_need_if_solving_ticket(ticket)

        # Then
        assert ticket.custom_fields == None

    @patch(
        "messaging.services.zendesk.enable_set_user_need_if_solving_ticket",
        return_value=True,
    )
    def test_set_user_need_if_solving_ticket__ticket_not_solved(
        self,
        mock_enable_set_user_need_if_solving_ticket,
        message_channel,
        factories,
    ):

        # Given
        ticket = ZDTicket(status="not-solved")
        assert ticket.custom_fields == None

        message = factories.MessageFactory(
            user=message_channel.member,
            channel=message_channel,
        )
        mzt = MessagingZendeskTicket(
            message=message,
            initial_cx_message=False,
            user_need_when_solving_ticket="a_great_user_need_when_solving_ticket",
        )

        # When
        mzt._set_user_need_if_solving_ticket(ticket)

        # Then
        assert ticket.custom_fields == None

    @patch("messaging.services.zendesk.get_user_need_custom_field_id")
    @patch(
        "messaging.services.zendesk.enable_set_user_need_if_solving_ticket",
        return_value=True,
    )
    def test_set_user_need_if_solving_ticket__no_user_need_defined(
        self,
        mock_enable_set_user_need_if_solving_ticket,
        mock_get_user_need_custom_field_id,
        message_channel,
        factories,
    ):
        # Given
        user_need_custom_field_id = 1
        mock_get_user_need_custom_field_id.return_value = user_need_custom_field_id
        ticket = ZDTicket(status="solved")
        assert ticket.custom_fields == None

        message = factories.MessageFactory(
            user=message_channel.member,
            channel=message_channel,
        )
        # Explicitly not passing user_need
        mzt = MessagingZendeskTicket(
            message=message,
            initial_cx_message=False,
        )

        # When
        mzt._set_user_need_if_solving_ticket(ticket)

        # Then, default user_need used
        assert ticket.custom_fields == [
            {
                "id": user_need_custom_field_id,
                "value": "customer-need-member-proactive-outreach-other",
            }
        ]

    @patch("messaging.services.zendesk.get_user_need_custom_field_id")
    @patch(
        "messaging.services.zendesk.enable_set_user_need_if_solving_ticket",
        return_value=True,
    )
    def test_set_user_need_if_solving_ticket__ticket_with_no_previous_custom_fields(
        self,
        mock_enable_set_user_need_if_solving_ticket,
        mock_get_user_need_custom_field_id,
        message_channel,
        factories,
    ):

        # Given
        user_need_custom_field_id = 1
        mock_get_user_need_custom_field_id.return_value = user_need_custom_field_id
        ticket = ZDTicket(status="solved")
        assert ticket.custom_fields == None

        message = factories.MessageFactory(
            user=message_channel.member,
            channel=message_channel,
        )
        mzt = MessagingZendeskTicket(
            message=message,
            initial_cx_message=False,
            user_need_when_solving_ticket="a_great_user_need_when_solving_ticket",
        )

        # When
        mzt._set_user_need_if_solving_ticket(ticket)

        # Then
        assert ticket.custom_fields == [
            {
                "id": user_need_custom_field_id,
                "value": "a_great_user_need_when_solving_ticket",
            }
        ]

    @patch("messaging.services.zendesk.get_user_need_custom_field_id")
    @patch(
        "messaging.services.zendesk.enable_set_user_need_if_solving_ticket",
        return_value=True,
    )
    def test_set_user_need_if_solving_ticket__ticket_with_previous_custom_fields(
        self,
        mock_enable_set_user_need_if_solving_ticket,
        mock_get_user_need_custom_field_id,
        message_channel,
        factories,
    ):

        # Given
        user_need_custom_field_id = 1
        another_user_need_custom_field_id = 2
        mock_get_user_need_custom_field_id.return_value = user_need_custom_field_id
        ticket = ZDTicket(status="solved")
        ticket.custom_fields = [
            {
                "id": another_user_need_custom_field_id,
                "value": "some_user_need",
            },
            {
                "id": user_need_custom_field_id,
                "value": "a_NOT_great_user_need_when_solving_ticket",
            },
        ]

        message = factories.MessageFactory(
            user=message_channel.member,
            channel=message_channel,
        )
        mzt = MessagingZendeskTicket(
            message=message,
            initial_cx_message=False,
            user_need_when_solving_ticket="a_great_user_need_when_solving_ticket",
        )

        # When
        mzt._set_user_need_if_solving_ticket(ticket)

        # Then, user_need custom field updated
        assert ticket.custom_fields == [
            {
                "id": another_user_need_custom_field_id,
                "value": "some_user_need",
            },
            {
                "id": user_need_custom_field_id,
                "value": "a_great_user_need_when_solving_ticket",
            },
        ]

    @patch("messaging.services.zendesk.log.warning")
    @patch("messaging.services.zendesk.get_user_need_custom_field_id")
    @patch(
        "messaging.services.zendesk.enable_set_user_need_if_solving_ticket",
        return_value=True,
    )
    def test_set_user_need_if_solving_ticket__ticket_with_previous_custom_fields_but_none_match_user_need(
        self,
        mock_enable_set_user_need_if_solving_ticket,
        mock_get_user_need_custom_field_id,
        mock_log_warn,
        message_channel,
        factories,
    ):

        # Given
        user_need_custom_field_id = 1
        another_user_need_custom_field_id = 2
        mock_get_user_need_custom_field_id.return_value = user_need_custom_field_id
        ticket = ZDTicket(status="solved")
        ticket.custom_fields = [
            {
                "id": another_user_need_custom_field_id,
                "value": "some_user_need",
            },
        ]

        message = factories.MessageFactory(
            user=message_channel.member,
            channel=message_channel,
        )
        mzt = MessagingZendeskTicket(
            message=message,
            initial_cx_message=False,
            user_need_when_solving_ticket="a_great_user_need_when_solving_ticket",
        )

        # When
        mzt._set_user_need_if_solving_ticket(ticket)

        # Then, user_need custom field updated
        assert ticket.custom_fields == [
            {
                "id": another_user_need_custom_field_id,
                "value": "some_user_need",
            },
            {
                "id": user_need_custom_field_id,
                "value": "a_great_user_need_when_solving_ticket",
            },
        ]
        mock_log_warn.assert_called_once_with(
            "user_need_custom_field_id not found in ticket.custom_fields. added, but unclear if it will persist",
            ticket_id=ticket.id,
            user_need_custom_field_id=user_need_custom_field_id,
        )
