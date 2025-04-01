from contextlib import nullcontext as does_not_raise
from datetime import datetime, timedelta
from unittest import mock
from unittest.mock import PropertyMock, patch

import pytest
from redset.locks import LockTimeout
from zenpy.lib.api_objects import Comment as ZDComment
from zenpy.lib.api_objects import Ticket as ZDTicket
from zenpy.lib.api_objects import Via

from authn.models.user import User
from common import stats
from messaging.models.messaging import Channel, Message
from messaging.schemas.zendesk import (
    ZendeskInboundMessageSchema,
    ZendeskInboundMessageSource,
)
from messaging.services.zendesk_client import (
    _FALLBACK_UPDATED_TICKET_SEARCH_LOOKBACK_SECONDS,
)
from models.verticals_and_specialties import CX_VERTICAL_NAME
from tasks.zendesk_v2 import (
    MAVEN_SUPPORT_EMAIL_ADDRESS,
    ZENDESK_MESSAGE_PROCESSING_OUTCOME,
    ZENDESK_MESSAGE_PROCESSING_UNKNOWN_AUTHOR,
    ZENDESK_TAG_PREFIX_CHANNEL_ID,
    ZendeskMessageType,
    attempt_record_credit_usage,
    create_wallet_message,
    get_corresponding_channel_from_tags,
    get_member,
    get_message_this_in_reply_to,
    is_wallet_response,
    process_credits_after_message_receive,
    process_inbound_member_message,
    process_inbound_wallet_message,
    process_updated_zendesk_ticket_id,
    process_zendesk_comment,
    process_zendesk_inbound_message_worker,
    process_zendesk_webhook,
    public_comments_for_ticket,
    public_comments_for_ticket_id,
    reconcile_zendesk_messages,
    record_successful_processing_of_inbound_zendesk_message,
    recover_zendesk_user_id,
    route_and_handle_inbound_message,
    should_include_ticket_id_in_reconciliation,
    should_process_reconciliation_comment,
    signal_message_processing_error,
    signal_message_processing_skipped,
    signal_on_comment_author_error,
    ticket_with_id,
    zendesk_comment_processing_job_lock,
)
from utils.flag_groups import CARE_DELIVERY_RELEASE


class ZDTestMessageSchema(ZendeskInboundMessageSchema):
    """
    allows for partial instantiation of the ZendeskInboundMessageSchema
    """

    def __init__(self, **kwargs) -> None:
        comment_id = kwargs.get("comment_id")
        message_body = kwargs.get("message_body")
        maven_user_email = kwargs.get("maven_user_email")
        comment_author_email = kwargs.get("comment_author_email")
        zendesk_user_id = kwargs.get("zendesk_user_id")
        tags = kwargs.get("tags")
        source = kwargs.get("source")

        super().__init__(
            comment_id,
            message_body,
            maven_user_email,
            comment_author_email,
            zendesk_user_id,
            tags,
            source,
        )


@pytest.mark.parametrize(
    ["test_tags_str", "expected_result"],
    [
        [("tag_1", "tag_2", "tag_3"), False],
        [("tag_1", "tag_2", "wallet_tag", "tag_3"), False],
        [("tag_1", "tag_2", "maven_wallet", "tag_3"), True],
        [("tag_1", "tag_2", "maven_wallet_", "tag_3"), True],
    ],
)
def test_wallet_tags(test_tags_str, expected_result):
    result = is_wallet_response(test_tags_str)
    assert result == expected_result


@pytest.mark.parametrize(
    "channel_id, make_channel, expect_message",
    [
        (None, False, False),
        ("123", False, False),
        ("456", True, True),
    ],
)
def test_create_wallet_message(
    channel_id,
    make_channel,
    expect_message,
    factories,
):
    test_input = None

    if channel_id:
        if make_channel:
            factories.ChannelFactory(id=channel_id)
        test_input = ZDTestMessageSchema(
            tags=[f"{ZENDESK_TAG_PREFIX_CHANNEL_ID}{channel_id}"],
        )

    result = create_wallet_message(test_input)
    if expect_message:
        assert isinstance(result, Message)
    else:
        assert result is None


@mock.patch("tasks.zendesk_v2.stats")
@mock.patch("tasks.zendesk_v2.generate_user_trace_log")
@pytest.mark.parametrize(
    "provide_message_data, expect_record_markers",
    [
        (False, False),
        (True, True),
    ],
)
def test_record_successful_processing_of_inbound_zendesk_message(
    mock_generate_user_trace_log,
    mock_stats,
    factories,
    provide_message_data,
    expect_record_markers,
):
    zd_msg = None
    mvn_msg = None

    if provide_message_data:
        zd_msg = ZDTestMessageSchema(source=ZendeskInboundMessageSource.WEBHOOK)
        mvn_msg = factories.MessageFactory()

    record_successful_processing_of_inbound_zendesk_message(
        inbound_message=zd_msg,
        new_mvn_message=mvn_msg,
        message_type=ZendeskMessageType.MEMBER,
    )

    if expect_record_markers:
        mock_generate_user_trace_log.assert_called()
        mock_stats.increment.assert_any_call(
            metric_name=ZENDESK_MESSAGE_PROCESSING_OUTCOME,
            pod_name=mock_stats.PodNames.VIRTUAL_CARE,
            tags=["result:success", "type:member", "source:webhook"],
        )
    else:
        mock_generate_user_trace_log.assert_not_called()
        mock_stats.increment.assert_not_called()


@mock.patch("tasks.zendesk_v2.stats.increment")
@pytest.mark.parametrize(
    "source, expected_source_tag",
    [
        (ZendeskInboundMessageSource.WEBHOOK, "webhook"),
        (ZendeskInboundMessageSource.TICKET, "ticket"),
    ],
)
def test_signal_message_processing_skipped(
    mock_stats_incr,
    factories,
    source,
    expected_source_tag,
):
    # Given a reason and source
    a_reason = "a_reason"
    # When
    signal_message_processing_skipped(
        reason=a_reason,
        source=source,
    )
    # Then
    mock_stats_incr.assert_called_once_with(
        metric_name=ZENDESK_MESSAGE_PROCESSING_OUTCOME,
        pod_name=stats.PodNames.VIRTUAL_CARE,
        tags=["result:skipped", f"reason:{a_reason}", f"source:{expected_source_tag}"],
    )


@mock.patch("tasks.zendesk_v2.stats")
@pytest.mark.parametrize(
    "source, expected_source_tag",
    [
        (ZendeskInboundMessageSource.WEBHOOK, "webhook"),
        (ZendeskInboundMessageSource.TICKET, "ticket"),
    ],
)
def test_signal_message_processing_error(
    mock_stats,
    factories,
    source,
    expected_source_tag,
):
    # Given error reason and source
    error_reason = "an_error_reason"
    # When
    signal_message_processing_error(
        reason=error_reason,
        source=source,
    )
    # Then
    mock_stats.increment.assert_any_call(
        metric_name=ZENDESK_MESSAGE_PROCESSING_OUTCOME,
        pod_name=mock_stats.PodNames.VIRTUAL_CARE,
        tags=[
            "result:failure",
            f"reason:{error_reason}",
            f"source:{expected_source_tag}",
        ],
    )


@patch.object(Channel, "is_wallet", new_callable=PropertyMock)
@pytest.mark.parametrize(
    "provide_originating_msg, provide_originating_msg_has_credit, provide_response_msg, is_wallet_channel, expect_credit_created",
    [
        (False, False, False, False, False),
        (True, False, False, False, False),
        (True, False, True, False, False),
        (False, True, False, False, False),
        (True, True, True, False, True),
        (True, False, True, True, False),
    ],
)
def test_attempt_record_credit_usage(
    mock_is_wallet_call,
    factories,
    provide_originating_msg,
    provide_originating_msg_has_credit,
    provide_response_msg,
    is_wallet_channel,
    expect_credit_created,
):
    mock_is_wallet_call.return_value = is_wallet_channel
    originating_msg = None
    response_msg = None

    channel = factories.ChannelFactory()

    if provide_originating_msg:
        # wallet channels have messages w/o user IDs
        user_id = None if is_wallet_channel else factories.MemberFactory().id
        originating_msg = factories.MessageFactory(
            user_id=user_id,
            channel_id=channel.id,
        )

    if originating_msg and provide_originating_msg_has_credit:
        factories.MessageCreditFactory(
            user_id=originating_msg.user_id,
            message_id=originating_msg.id,
        )

    if provide_response_msg:
        response_msg = factories.MessageFactory(
            channel_id=channel.id,
        )

    created_credit = attempt_record_credit_usage(
        originating_msg=originating_msg,
        response_msg=response_msg,
    )

    assert bool(created_credit) == expect_credit_created


@mock.patch("tasks.zendesk_v2.attempt_record_credit_usage")
@pytest.mark.parametrize(
    "provide_member, provide_channel, provide_new_message",
    [
        (False, False, False),
        (True, False, False),
        (True, True, False),
        (True, True, True),
    ],
)
def test_process_credits_after_message_receive(
    mock_attempt_record_credit_usage,
    factories,
    provide_member,
    provide_channel,
    provide_new_message,
):
    inbound_message = ZDTestMessageSchema()
    member = None
    channel = None
    new_message = None

    if provide_member:
        member = factories.MemberFactory()
    if provide_channel:
        channel = factories.ChannelFactory()
    if provide_new_message:
        new_message = factories.MessageFactory()

    process_credits_after_message_receive(
        inbound_message=inbound_message,
        member=member,
        channel=channel,
        new_message=new_message,
    )

    # no last_message on channel
    mock_attempt_record_credit_usage.assert_not_called()


@mock.patch("tasks.zendesk_v2.attempt_record_credit_usage")
def test_process_credits_after_message_receive_credit_usage(
    mock_attempt_record_credit_usage,
    factories,
):
    inbound_message = ZDTestMessageSchema()
    member = factories.MemberFactory()
    channel = factories.ChannelFactory()
    channel_user = factories.ChannelUsersFactory(
        channel_id=channel.id,
        user_id=member.id,
    )
    channel.participants = [channel_user]
    last_message = factories.MessageFactory(channel_id=channel.id)
    new_message = factories.MessageFactory(channel_id=channel.id)

    process_credits_after_message_receive(
        inbound_message=inbound_message,
        member=member,
        channel=channel,
        new_message=new_message,
    )

    mock_attempt_record_credit_usage.assert_called_with(
        originating_msg=last_message,
        response_msg=new_message,
        log_tags=mock.ANY,
    )


@pytest.mark.parametrize(
    "provide_inbound_message, provide_member, expect_record_and_credits",
    [
        (False, False, False),
        (True, False, False),
        (True, True, True),
    ],
)
@mock.patch("tasks.zendesk_v2.create_wallet_message")
@mock.patch("tasks.zendesk_v2.record_successful_processing_of_inbound_zendesk_message")
@mock.patch("tasks.zendesk_v2.process_credits_after_message_receive")
def test_process_inbound_wallet_message(
    mock_process_credits_after_message_receive,
    mock_record_successful_processing_of_inbound_zendesk_message,
    mock_create_wallet_message,
    provide_inbound_message,
    provide_member,
    expect_record_and_credits,
    factories,
):
    inbound_message = None
    if provide_inbound_message:
        inbound_message = ZDTestMessageSchema()

    member = None
    if provide_member:
        member = factories.MemberFactory()

    channel = factories.ChannelFactory()
    new_message = factories.MessageFactory(channel_id=channel.id)
    mock_create_wallet_message.return_value = new_message

    process_inbound_wallet_message(
        inbound_message=inbound_message,
        member=member,
    )

    if expect_record_and_credits:
        mock_create_wallet_message.assert_called()
        mock_record_successful_processing_of_inbound_zendesk_message.assert_called()
        mock_process_credits_after_message_receive.assert_called()
    else:
        mock_create_wallet_message.assert_not_called()
        mock_record_successful_processing_of_inbound_zendesk_message.assert_not_called()
        mock_process_credits_after_message_receive.assert_not_called()


@pytest.mark.parametrize("maven_clinic_email", [True, False])
@mock.patch("tasks.zendesk_v2.record_successful_processing_of_inbound_zendesk_message")
@mock.patch("tasks.zendesk_v2.signal_message_processing_error")
@mock.patch("tasks.zendesk_v2.get_author")
@mock.patch("tasks.zendesk_v2.generate_user_trace_log")
def test_process_inbound_member_message_no_author(
    mock_log,
    mock_get_author,
    mock_signal_message_processing_error,
    mock_record_successful_processing_of_inbound_zendesk_message,
    maven_clinic_email,
):
    # Given cant find author
    mock_get_author.return_value = None
    inbound_message = ZDTestMessageSchema(
        source=ZendeskInboundMessageSource.WEBHOOK,
        comment_author_email="test@mavenclinic.com"
        if maven_clinic_email
        else "test@gmail.com",
    )

    # When
    process_inbound_member_message(
        inbound_message=inbound_message,
    )
    # Then, we emit metrics and bail out if we can't find the author
    mock_signal_message_processing_error.assert_called_once_with(
        reason="invalid_author",
        source=inbound_message.source,
    )
    mock_record_successful_processing_of_inbound_zendesk_message.assert_not_called()
    assert mock_log.call_args_list[0][1]["maven_clinic_email"] == maven_clinic_email


@mock.patch("tasks.zendesk_v2.emit_non_cx_comment_warning")
@mock.patch("tasks.zendesk_v2.record_successful_processing_of_inbound_zendesk_message")
@mock.patch("tasks.zendesk_v2.signal_message_processing_error")
@mock.patch("tasks.zendesk_v2.get_author")
def test_process_inbound_member_message_not_care_coordinator(
    mock_get_author,
    mock_signal_message_processing_error,
    mock_record_successful_processing_of_inbound_zendesk_message,
    mock_emit_non_cx_comment_warning,
    factories,
):
    # Given not CA author
    member = factories.MemberFactory()
    mock_get_author.return_value = member

    with mock.patch.object(
        User,
        "is_care_coordinator",
        new_callable=mock.PropertyMock,
        return_value=False,
    ) as mock_is_care_coordinator:
        inbound_message = ZDTestMessageSchema(
            source=ZendeskInboundMessageSource.WEBHOOK
        )

        # When
        process_inbound_member_message(
            inbound_message=inbound_message,
        )

        # Then, we emit metrics and bail out if the author is not a care_coordinator
        mock_is_care_coordinator.assert_called()
        mock_signal_message_processing_error.assert_called_once_with(
            reason="author_is_not_ca",
            source=inbound_message.source,
        )
        mock_emit_non_cx_comment_warning.assert_called()
        mock_record_successful_processing_of_inbound_zendesk_message.assert_not_called()


@mock.patch("tasks.zendesk_v2.get_channel_and_message_author")
@mock.patch("tasks.zendesk_v2.record_successful_processing_of_inbound_zendesk_message")
@mock.patch("tasks.zendesk_v2.signal_message_processing_error")
@mock.patch("tasks.zendesk_v2.get_author")
def test_process_inbound_member_message_no_channel_or_author(
    mock_get_author,
    mock_signal_message_processing_error,
    mock_record_successful_processing_of_inbound_zendesk_message,
    mock_get_channel_and_message_author,
    factories,
):
    # Given get_channel_and_message_author fail
    member = factories.MemberFactory()
    mock_get_author.return_value = member

    mock_get_channel_and_message_author.return_value = (None, None)

    with mock.patch.object(
        User,
        "is_care_coordinator",
        new_callable=mock.PropertyMock,
        return_value=True,
    ):
        inbound_message = ZDTestMessageSchema(
            source=ZendeskInboundMessageSource.WEBHOOK
        )

        # When
        process_inbound_member_message(
            inbound_message=inbound_message,
        )

        # this was a cx
        mock_signal_message_processing_error.assert_called_once_with(
            reason="invalid_channel_message_author",
            source=inbound_message.source,
        )
        mock_record_successful_processing_of_inbound_zendesk_message.assert_not_called()


@mock.patch("tasks.zendesk_v2.get_channel_and_message_author")
@mock.patch("tasks.zendesk_v2.emit_non_cx_comment_warning")
@mock.patch("tasks.zendesk_v2.process_credits_after_message_receive")
@mock.patch("tasks.zendesk_v2.record_successful_processing_of_inbound_zendesk_message")
@mock.patch("tasks.zendesk_v2.get_author")
def test_process_inbound_member_message_success(
    mock_get_author,
    mock_record_successful_processing_of_inbound_zendesk_message,
    mock_process_credits_after_message_receive,
    mock_emit_non_cx_comment_warning,
    mock_get_channel_and_message_author,
    factories,
    db,
):
    member = factories.MemberFactory()
    mock_get_author.return_value = member

    channel = factories.ChannelFactory()
    mock_get_channel_and_message_author.return_value = (channel, member)

    inbound_message = ZDTestMessageSchema(
        message_body="foobar",
        comment_id=1234,
    )
    with mock.patch.object(
        User,
        "is_care_coordinator",
        new_callable=mock.PropertyMock,
        return_value=True,
    ):
        process_inbound_member_message(
            inbound_message=inbound_message,
        )
        # this was a cx
        mock_emit_non_cx_comment_warning.assert_not_called()

        # we could not find the associated channel or author
        mock_process_credits_after_message_receive.assert_called()
        mock_record_successful_processing_of_inbound_zendesk_message.assert_called()

    new_messages = (
        db.session.query(Message)
        .filter(Message.user == member)
        .filter(Message.channel == channel)
        .all()
    )
    assert len(new_messages) == 1
    assert new_messages[0].zendesk_comment_id == inbound_message.comment_id
    assert new_messages[0].body == inbound_message.message_body


def test_process_zendesk_inbound_message_input_validation():
    # we dont expect an exception. a retry would not produce a different result
    result = process_zendesk_inbound_message_worker()
    assert result is None


@mock.patch("tasks.zendesk_v2.notify_new_message")
@mock.patch("tasks.zendesk_v2.update_message_attrs")
@mock.patch(
    "tasks.zendesk_v2.process_inbound_member_message",
    raise_exception=Exception("should not have called"),
)
@mock.patch("tasks.zendesk_v2.has_zendesk_comment_id_been_processed", return_value=True)
def test_process_zendesk_inbound_message_already_processed(
    mock_has_zendesk_comment_id_been_processed,
    mock_process_inbound_member_message,
    mock_update_message_attrs,
    mock_notify_new_message,
):
    inbound_message = ZDTestMessageSchema(
        message_body="foobar",
        comment_id=1234,
    )
    process_zendesk_inbound_message_worker(inbound_message=inbound_message)
    mock_has_zendesk_comment_id_been_processed.assert_called()
    mock_process_inbound_member_message.assert_not_called()
    mock_update_message_attrs.assert_not_called()
    mock_notify_new_message.assert_not_called()


@mock.patch("tasks.zendesk_v2.redis_client")
@mock.patch("tasks.zendesk_v2.notify_new_message")
@mock.patch("tasks.zendesk_v2.update_message_attrs")
@mock.patch(
    "tasks.zendesk_v2.process_inbound_member_message",
    raise_exception=Exception("should not have called"),
)
@mock.patch(
    "tasks.zendesk_v2.has_zendesk_comment_id_been_processed",
    return_value=False,
)
@mock.patch("tasks.zendesk_v2.get_member", return_value=None)
def test_process_zendesk_inbound_message_no_member(
    mock_get_member,
    mock_has_zendesk_comment_id_been_processed,
    mock_process_inbound_member_message,
    mock_update_message_attrs,
    mock_notify_new_message,
    mock_redis_client,
):
    redis_conn_mock = mock.MagicMock()
    mock_redis_client.return_value = redis_conn_mock

    inbound_message = ZDTestMessageSchema(
        message_body="foobar",
        comment_id=1234,
    )
    process_zendesk_inbound_message_worker(inbound_message=inbound_message)
    mock_has_zendesk_comment_id_been_processed.assert_called()
    mock_get_member.assert_called()
    mock_process_inbound_member_message.assert_not_called()
    mock_update_message_attrs.assert_not_called()
    mock_notify_new_message.assert_not_called()

    redis_conn_mock.setex.assert_called_with(
        name="zendesk_v2:temp:no_member:1234",
        value=mock.ANY,
        time=mock.ANY,
    )


@mock.patch("tasks.zendesk_v2.route_and_handle_inbound_message", return_value=Message())
@mock.patch("tasks.zendesk_v2.notify_new_message")
@mock.patch("tasks.zendesk_v2.update_message_attrs")
@mock.patch(
    "tasks.zendesk_v2.has_zendesk_comment_id_been_processed",
    return_value=False,
)
@mock.patch(
    "tasks.zendesk_v2.get_member",
    return_value=User(),
)
def test_process_zendesk_inbound_message(
    mock_get_member,
    mock_has_zendesk_comment_id_been_processed,
    mock_update_message_attrs,
    mock_notify_new_message,
    mock_route_and_handle_inbound_message,
):
    inbound_message = ZDTestMessageSchema(
        message_body="foobar",
        comment_id=1234,
    )
    process_zendesk_inbound_message_worker(inbound_message=inbound_message)

    mock_has_zendesk_comment_id_been_processed.assert_called()
    mock_get_member.assert_called()
    mock_route_and_handle_inbound_message.assert_called()

    mock_update_message_attrs.delay.assert_called()
    mock_notify_new_message.delay.assert_called()


@mock.patch("tasks.zendesk_v2.notify_new_message")
@mock.patch("tasks.zendesk_v2.update_message_attrs")
@mock.patch("tasks.zendesk_v2.process_inbound_member_message", return_value=Message())
@mock.patch(
    "tasks.zendesk_v2.has_zendesk_comment_id_been_processed",
    return_value=False,
)
@mock.patch(
    "tasks.zendesk_v2.get_member",
    return_value=User(),
)
@mock.patch("tasks.zendesk_v2.is_wallet_response", return_value=False)
@mock.patch("tasks.zendesk_v2.process_inbound_wallet_message")
def test_process_zendesk_inbound_message_member_message(
    mock_process_inbound_wallet_message,
    mock_is_wallet_response,
    mock_get_member,
    mock_has_zendesk_comment_id_been_processed,
    mock_process_inbound_member_message,
    mock_update_message_attrs,
    mock_notify_new_message,
):
    inbound_message = ZDTestMessageSchema(
        message_body="foobar",
        comment_id=1234,
    )
    process_zendesk_inbound_message_worker(inbound_message=inbound_message)
    mock_has_zendesk_comment_id_been_processed.assert_called()
    mock_get_member.assert_called()
    mock_is_wallet_response.assert_called()
    mock_process_inbound_wallet_message.assert_not_called()
    mock_process_inbound_member_message.assert_called()

    mock_notify_new_message.delay.assert_called()
    mock_update_message_attrs.delay.assert_called()


@mock.patch("tasks.zendesk_v2.process_zendesk_inbound_message_from_webhook")
@pytest.mark.parametrize(
    "data, process_called",
    [
        (None, False),
        ({}, False),
        ({"foo": "bar"}, False),
        (
            {
                "token": "tok",
                "comment_id": "123",  # must be a number
                "message_body": "bar",
                "maven_user_email": "bar",
                "comment_author_email": "bar",
                "zendesk_user_id": "1234",  # must be a number
                "tags": ["bar"],
            },
            True,
        ),
    ],
)
def test_process_zendesk_webhook(
    mock_process_zendesk_inbound_message_from_webhook,
    data,
    process_called,
):
    process_zendesk_webhook(data=data)
    assert (
        mock_process_zendesk_inbound_message_from_webhook.delay.called == process_called
    )


def test_process_updated_zendesk_ticket_id_input_validation():
    # expect no exception
    result = process_updated_zendesk_ticket_id(None)
    assert result is None


def test_route_and_handle_inbound_message_input_validation():
    new_message = route_and_handle_inbound_message(
        inbound_message=None,
        member=None,
        log_tags=None,
    )
    assert new_message is None


@mock.patch("tasks.zendesk_v2.is_wallet_response", return_value=True)
@mock.patch(
    "tasks.zendesk_v2.process_inbound_wallet_message",
)
@mock.patch("tasks.zendesk_v2.process_inbound_member_message")
def test_route_and_handle_inbound_message_wallet(
    mock_process_inbound_member_message,
    mock_process_inbound_wallet_message,
    mock_is_wallet_response,
):
    expected_result_message = Message()
    mock_process_inbound_wallet_message.return_value = expected_result_message
    inbound_message = ZDTestMessageSchema(
        message_body="foobar",
        comment_id=1234,
    )

    new_message = route_and_handle_inbound_message(
        inbound_message=inbound_message,
        member=None,
        log_tags=None,
    )
    mock_is_wallet_response.assert_called_once()
    mock_process_inbound_wallet_message.assert_called_once()
    mock_process_inbound_member_message.assert_not_called()
    assert new_message == expected_result_message


@mock.patch("tasks.zendesk_v2.is_wallet_response", return_value=False)
@mock.patch(
    "tasks.zendesk_v2.process_inbound_wallet_message",
)
@mock.patch("tasks.zendesk_v2.process_inbound_member_message")
def test_route_and_handle_inbound_message_member(
    mock_process_inbound_member_message,
    mock_process_inbound_wallet_message,
    mock_is_wallet_response,
):
    expected_result_message = Message()
    mock_process_inbound_member_message.return_value = expected_result_message
    inbound_message = ZDTestMessageSchema(
        message_body="foobar",
        comment_id=1234,
    )

    new_message = route_and_handle_inbound_message(
        inbound_message=inbound_message,
        member=None,
        log_tags=None,
    )
    mock_is_wallet_response.assert_called_once()
    mock_process_inbound_wallet_message.assert_not_called()
    mock_process_inbound_member_message.assert_called_once()
    assert new_message == expected_result_message


@mock.patch("tasks.zendesk_v2.ticket_with_id", return_value=None)
def test_process_updated_zendesk_ticket_id_no_ticket(mock_ticket_with_id):
    # expect no exception
    process_updated_zendesk_ticket_id(None)
    mock_ticket_with_id.assert_not_called()


@mock.patch(
    "tasks.zendesk_v2.should_include_ticket_id_in_reconciliation",
    return_value=True,
)
@mock.patch("tasks.zendesk_v2.process_zendesk_comment")
@mock.patch("tasks.zendesk_v2.public_comments_for_ticket", return_value=[])
@mock.patch("tasks.zendesk_v2.ticket_with_id", return_value=ZDTicket())
def test_process_updated_zendesk_ticket_id_no_comments(
    mock_ticket_with_id,
    mock_public_comments_for_ticket,
    mock_process_zendesk_comment,
    mock_should_include_ticket_id_in_reconciliation,
):
    # expect no exception
    process_updated_zendesk_ticket_id("123")
    mock_should_include_ticket_id_in_reconciliation.assert_called()
    mock_ticket_with_id.assert_called()
    mock_public_comments_for_ticket.assert_called()
    mock_process_zendesk_comment.assert_not_called()


@mock.patch(
    "tasks.zendesk_v2.should_include_ticket_id_in_reconciliation",
    return_value=False,
)
@mock.patch("tasks.zendesk_v2.process_zendesk_comment")
@mock.patch("tasks.zendesk_v2.public_comments_for_ticket", return_value=[])
@mock.patch("tasks.zendesk_v2.ticket_with_id", return_value=ZDTicket())
def test_process_updated_zendesk_ticket_id_flag_disabled(
    mock_ticket_with_id,
    mock_public_comments_for_ticket,
    mock_process_zendesk_comment,
    mock_should_include_ticket_id_in_reconciliation,
):
    # expect no exception
    process_updated_zendesk_ticket_id("123")
    mock_should_include_ticket_id_in_reconciliation.assert_called()
    mock_ticket_with_id.assert_not_called()
    mock_public_comments_for_ticket.assert_not_called()
    mock_process_zendesk_comment.assert_not_called()


@mock.patch(
    "tasks.zendesk_v2.should_include_ticket_id_in_reconciliation",
    return_value=True,
)
@mock.patch(
    "tasks.zendesk_v2.should_process_reconciliation_comment",
    return_value=True,
)
@mock.patch("tasks.zendesk_v2.process_zendesk_comment")
@mock.patch(
    "tasks.zendesk_v2.public_comments_for_ticket",
    return_value=[
        ZDComment(),
        ZDComment(),
        ZDComment(),
    ],
)
@mock.patch("tasks.zendesk_v2.ticket_with_id", return_value=ZDTicket())
def test_process_updated_zendesk_ticket_id(
    mock_ticket_with_id,
    mock_public_comments_for_ticket,
    mock_process_zendesk_comment,
    mock_should_process_reconciliation_comment,
    mock_should_include_ticket_id_in_reconciliation,
):
    # expect no exception
    process_updated_zendesk_ticket_id("123")
    mock_ticket_with_id.assert_called()
    mock_public_comments_for_ticket.assert_called()
    mock_should_process_reconciliation_comment.assert_called()
    assert mock_process_zendesk_comment.call_count == 3


@mock.patch(
    "tasks.zendesk_v2.signal_ticket_processing_error",
)
@mock.patch(
    "tasks.zendesk_v2.should_include_ticket_id_in_reconciliation",
    return_value=False,
)
def test_process_updated_zendesk_ticket_id_excluded_ticket(
    should_include_ticket_id_in_reconciliation,
    mock_signal_ticket_processing_error,
):
    # When
    process_updated_zendesk_ticket_id("123")

    # Then
    # expect no exception
    should_include_ticket_id_in_reconciliation.assert_called()

    mock_signal_ticket_processing_error.assert_called_once_with(
        reason="ticket_id_exclusion"
    )


@mock.patch(
    "tasks.zendesk_v2.signal_message_processing_skipped",
)
@mock.patch(
    "tasks.zendesk_v2.should_include_ticket_id_in_reconciliation",
    return_value=True,
)
@mock.patch(
    "tasks.zendesk_v2.should_process_reconciliation_comment",
    return_value=False,
)
@mock.patch("tasks.zendesk_v2.process_zendesk_comment")
@mock.patch(
    "tasks.zendesk_v2.public_comments_for_ticket",
    return_value=[
        ZDComment(),
    ],
)
@mock.patch("tasks.zendesk_v2.ticket_with_id", return_value=ZDTicket())
def test_process_updated_zendesk_ticket_id_out_of_window(
    mock_ticket_with_id,
    mock_public_comments_for_ticket,
    mock_process_zendesk_comment,
    mock_should_process_reconciliation_comment,
    mock_should_include_ticket_id_in_reconciliation,
    mock_signal_message_processing_skipped,
):

    # When
    process_updated_zendesk_ticket_id("123")

    # Then
    mock_ticket_with_id.assert_called()
    mock_public_comments_for_ticket.assert_called()
    mock_should_process_reconciliation_comment.assert_called()
    assert mock_process_zendesk_comment.call_count == 0
    mock_signal_message_processing_skipped.assert_called_once_with(
        reason="should_not_process_reconciliation_comment",
        source=ZendeskInboundMessageSource.TICKET,
    )


@pytest.mark.parametrize(
    "flag_value",
    [
        True,
        False,
    ],
)
@pytest.mark.parametrize(
    "test_ticket_id, should_include",
    [
        (None, False),  # None is excluded
        (111111, True),  # any random ticket id
        # these are explicitly copy/pasta'ed to ensure they do not change
        # without knowledge of the incident they are associated with
        # details can be found here https://mavenclinic.slack.com/archives/C06HGG70HKQ/p1707344038987089
        (180554, False),  # inc-126
        (559398, False),  # inc-126
        (561274, False),  # inc-126
    ],
)
def test_should_exclude_ticket_id_from_reconciliation(
    flag_value,
    test_ticket_id,
    should_include,
    ff_test_data,
):
    ff_test_data.update(
        ff_test_data.flag(
            CARE_DELIVERY_RELEASE.ENABLE_ZENDESK_V2_RECONCILIATION_OF_TICKET
        ).variation_for_all(flag_value)
    )
    assert should_include_ticket_id_in_reconciliation(test_ticket_id) == (
        should_include and flag_value
    )


@pytest.mark.parametrize(
    "is_public, was_processed",
    [
        (False, False),
        (True, True),
    ],
)
@mock.patch("tasks.zendesk_v2.process_zendesk_inbound_message_worker")
@mock.patch(
    "tasks.zendesk_v2.ticket_to_zendesk_inbound_message_schema",
    return_value=ZDTestMessageSchema(),
)
def test_process_zendesk_comment(
    mock_from_ticket_with_comment,
    mock_process_zendesk_inbound_message_worker,
    is_public,
    was_processed,
):
    # expect no exception
    process_zendesk_comment(ticket=ZDTicket(), comment=ZDComment(public=is_public))
    mock_from_ticket_with_comment.called_once()
    assert mock_process_zendesk_inbound_message_worker.called == was_processed


@mock.patch("tasks.zendesk_v2.zenpy_client")
def test_ticket_with_id(
    mock_zenpy_client,
):
    # input validation
    ticket_with_id(None)
    mock_zenpy_client.ticket_with_id.assert_not_called()

    ticket_with_id(ticket_id="123")
    mock_zenpy_client.ticket_with_id.assert_called_with(ticket_id="123")


@mock.patch(
    "tasks.zendesk_v2.public_comments_for_ticket_id",
)
def test_public_comments_for_ticket(
    mock_public_comments_for_ticket_id,
):
    empty_result = public_comments_for_ticket(None)
    assert empty_result == []
    mock_public_comments_for_ticket_id.assert_not_called()

    mock_public_comments_for_ticket_id.reset_mock()

    public_comments_for_ticket(ZDTicket(id=123))
    mock_public_comments_for_ticket_id.assert_called_once()


@mock.patch(
    "tasks.zendesk_v2.zenpy_client.get_comments_for_ticket_id",
)
def test_public_comments_for_ticket_id_no_id(
    mock_get_comments_for_ticket_id,
):
    empty_result = public_comments_for_ticket_id(ticket_id=None)
    mock_get_comments_for_ticket_id.assert_not_called()
    assert empty_result == []


@mock.patch("tasks.zendesk_v2.zenpy_client.get_comments_for_ticket_id")
def test_public_comments_for_ticket_id(
    mock_get_comments_for_ticket_id,
):
    public_comment = ZDComment(id=123, public=True)
    private_comment = ZDComment(id=456, public=False)

    mock_get_comments_for_ticket_id.return_value = [public_comment, private_comment]

    public_result = public_comments_for_ticket_id(ticket_id=123)
    mock_get_comments_for_ticket_id.assert_called()
    assert len(public_result) == 1
    assert public_comment in public_result


@mock.patch("tasks.zendesk_v2.process_updated_zendesk_ticket_id")
@mock.patch("tasks.zendesk_v2.zenpy_client")
def test_reconcile_zendesk_messages_no_tickets(
    mock_zenpy_client,
    mock_process_updated_zendesk_ticket_id,
):
    mock_zenpy_client.find_updated_ticket_ids.return_value = []
    reconcile_zendesk_messages()
    mock_zenpy_client.find_updated_ticket_ids.called_once()
    # no messages to process
    mock_process_updated_zendesk_ticket_id.assert_not_called()


@mock.patch("tasks.zendesk_v2.process_updated_zendesk_ticket_id")
@mock.patch("tasks.zendesk_v2.zenpy_client")
def test_reconcile_zendesk_messages_release_flag_off(
    mock_zenpy_client,
    mock_process_updated_zendesk_ticket_id,
    ff_test_data,
):
    ff_test_data.update(
        ff_test_data.flag(
            CARE_DELIVERY_RELEASE.ENABLE_ZENDESK_V2_RECONCILIATION_JOB
        ).variation_for_all(False)
    )

    mock_zenpy_client.find_updated_ticket_ids.return_value = [
        ZDTicket(id=123),
        ZDTicket(id=456),
        ZDTicket(id=789),
    ]
    reconcile_zendesk_messages()
    mock_zenpy_client.find_updated_ticket_ids.assert_not_called()
    mock_process_updated_zendesk_ticket_id.delay.not_called()


@mock.patch("tasks.zendesk_v2.process_updated_zendesk_ticket_id")
@mock.patch("tasks.zendesk_v2.zenpy_client")
def test_reconcile_zendesk_messages(
    mock_zenpy_client,
    mock_process_updated_zendesk_ticket_id,
    ff_test_data,
):
    ff_test_data.update(
        ff_test_data.flag(
            CARE_DELIVERY_RELEASE.ENABLE_ZENDESK_V2_RECONCILIATION_JOB
        ).variation_for_all(True)
    )

    mock_zenpy_client.find_updated_ticket_ids.return_value = [
        ZDTicket(id=123),
        ZDTicket(id=456),
        ZDTicket(id=789),
    ]
    reconcile_zendesk_messages()
    mock_zenpy_client.find_updated_ticket_ids.called_once()
    assert mock_process_updated_zendesk_ticket_id.delay.call_count == 3


@mock.patch("tasks.zendesk_v2.process_updated_zendesk_ticket_id")
@mock.patch("tasks.zendesk_v2.zenpy_client")
def test_reconcile_zendesk_messages_exception_tolerance(
    mock_zenpy_client,
    mock_process_updated_zendesk_ticket_id,
    ff_test_data,
):
    ff_test_data.update(
        ff_test_data.flag(
            CARE_DELIVERY_RELEASE.ENABLE_ZENDESK_V2_RECONCILIATION_JOB
        ).variation_for_all(True)
    )

    mock_zenpy_client.find_updated_ticket_ids.return_value = [
        ZDTicket(id=123),
        ZDTicket(id=456),
        ZDTicket(id=789),
    ]
    mock_process_updated_zendesk_ticket_id.delay.side_effect = Exception("ay yi yi")
    reconcile_zendesk_messages()
    mock_zenpy_client.find_updated_ticket_ids.called_once()
    # expect that we still called this for each ticket
    assert mock_process_updated_zendesk_ticket_id.delay.call_count == 3


@pytest.mark.parametrize("enable_check_member", [True, False])
@pytest.mark.parametrize(
    "create_channel, expect_channel",
    [
        (False, False),
        (True, True),
    ],
)
def test_get_corresponding_channel_from_tags(
    create_channel,
    expect_channel,
    enable_check_member,
    factories,
):
    # given
    author_id = None
    channel_id = None
    tags = None
    if create_channel:
        member = factories.EnterpriseUserFactory.create()
        practitioner = factories.PractitionerUserFactory.create()
        channel = Channel.get_or_create_channel(practitioner, [member])
        channel_id = channel.id
        author_id = practitioner.id
        tags = [f"{ZENDESK_TAG_PREFIX_CHANNEL_ID}{channel_id}"]
    # when
    c = get_corresponding_channel_from_tags(tags, author_id, enable_check_member)
    # then
    if expect_channel:
        assert c.id == channel_id
    else:
        assert c is None


@pytest.mark.parametrize("enable_check_member", [True, False])
@pytest.mark.parametrize("reverse_tags", [True, False])
def test_get_corresponding_channel_from_tags__multiple_channels(
    reverse_tags,
    enable_check_member,
    factories,
):
    # given
    channels = []
    tags = []
    reversed_tags = []
    for _ in range(2):
        member = factories.EnterpriseUserFactory.create()
        practitioner = factories.PractitionerUserFactory.create()
        channel = Channel.get_or_create_channel(practitioner, [member])
        tags.append(f"{ZENDESK_TAG_PREFIX_CHANNEL_ID}{channel.id}")
        channels.append(channel)
    if reverse_tags:
        reversed_tags = tags[::-1]
    # when
    c = get_corresponding_channel_from_tags(
        reversed_tags if reverse_tags else tags,
        channels[1].practitioner.id,
        enable_check_member,
    )
    # then
    if enable_check_member:
        assert c.id == channels[1].id
    else:
        assert c.id is not None
        # first channel found is returned
        if reversed_tags:
            assert c.id == channels[1].id
        else:
            assert c.id == channels[0].id


@pytest.mark.parametrize("enable_check_member", [True, False])
@pytest.mark.parametrize("author_id", [123456789, None])
@pytest.mark.parametrize("reverse_tags", [True, False])
def test_get_corresponding_channel_from_tags__multiple_channels_no_author_match(
    reverse_tags,
    author_id,
    enable_check_member,
    factories,
):
    # given
    channels = []
    tags = []
    reversed_tags = []
    for _ in range(2):
        member = factories.EnterpriseUserFactory.create()
        practitioner = factories.PractitionerUserFactory.create()
        channel = Channel.get_or_create_channel(practitioner, [member])
        tags.append(f"{ZENDESK_TAG_PREFIX_CHANNEL_ID}{channel.id}")
        channels.append(channel)
    if reverse_tags:
        reversed_tags = tags[::-1]
    # when
    c = get_corresponding_channel_from_tags(
        reversed_tags if reverse_tags else tags, author_id, enable_check_member
    )
    # then
    if enable_check_member:
        # assert last channel created is returned
        assert c.id == channels[1].id
    else:
        # first channel found is returned
        if reversed_tags:
            assert c.id == channels[1].id
        else:
            assert c.id == channels[0].id


@pytest.mark.parametrize("enable_check_member", [True, False])
def test_get_corresponding_channel_from_tags__no_channels(
    enable_check_member,
    factories,
):
    # when
    c = get_corresponding_channel_from_tags([], 123456789, enable_check_member)
    # then
    assert c is None


def test_get_message_this_in_reply_to(factories):
    c = factories.ChannelFactory()
    m1 = factories.MessageFactory(channel_id=c.id)
    m2 = factories.MessageFactory(channel_id=c.id)
    assert get_message_this_in_reply_to(reply_message=m1) is None
    assert get_message_this_in_reply_to(reply_message=m2) is m1


@pytest.mark.parametrize(
    "flag_value",
    [
        True,
        False,
    ],
)
@pytest.mark.parametrize(
    "comment, should_reconcile, comment_created_at, ticket_updated_at, should_process",
    [
        (None, None, None, None, False),
        (ZDComment(), False, None, None, False),
        # too old
        (
            ZDComment(),
            True,
            datetime.utcnow() - timedelta(days=1000),
            datetime.utcnow(),
            False,
        ),
        (
            ZDComment(),
            True,
            datetime.utcnow() - timedelta(days=100),
            datetime.utcnow(),
            False,
        ),
        (
            ZDComment(),
            True,
            datetime.utcnow() - timedelta(seconds=(30 * 60)),  # 30 min ago
            datetime.utcnow(),
            True,
        ),
        (
            ZDComment(),
            True,
            datetime.utcnow()
            - timedelta(
                seconds=_FALLBACK_UPDATED_TICKET_SEARCH_LOOKBACK_SECONDS,
            )
            + timedelta(seconds=30),  # to avoid making this tests flaky
            datetime.utcnow(),
            True,
        ),
        (
            # move the ticket_updated_at way back in time to ensure that the
            # comment that was created within lookback days of the ticket update
            # time stamp IS selected for processing.
            ZDComment(),
            True,
            datetime.utcnow()
            - timedelta(days=100)
            - timedelta(
                seconds=_FALLBACK_UPDATED_TICKET_SEARCH_LOOKBACK_SECONDS,
            )
            + timedelta(
                seconds=30,  # comment_created_at is 30 sec into the lookback window
            ),
            datetime.utcnow() - timedelta(days=100),
            True,
        ),
        # created via api
        (
            ZDComment(via=Via(channel="api")),
            True,
            datetime.utcnow() - timedelta(seconds=(30 * 60)),  # 30 min ago
            datetime.utcnow(),
            False,
        ),
    ],
)
@mock.patch("tasks.zendesk_v2.should_reconcile_zendesk_messages")
@mock.patch("tasks.zendesk_v2.zenpy_client.datetime_from_zendesk_date_str")
def test_should_process_reconciliation_comment(
    mock_datetime_from_zendesk_date_str,
    mock_should_reconcile_zendesk_messages,
    flag_value,
    comment,
    should_reconcile,
    comment_created_at,
    ticket_updated_at,
    should_process,
    ff_test_data,
):
    ff_test_data.update(
        ff_test_data.flag(
            CARE_DELIVERY_RELEASE.ENABLE_ZENDESK_V2_RECONCILIATION_OF_COMMENT
        ).variation_for_all(flag_value)
    )

    mock_should_reconcile_zendesk_messages.return_value = should_reconcile
    # returns ticket_updated_at on first call and comment_created_at on second
    mock_datetime_from_zendesk_date_str.side_effect = [
        ticket_updated_at,
        comment_created_at,
    ]

    assert should_process_reconciliation_comment(
        comment=comment,
        parent_ticket=ZDTicket(ticket_updated_at=ticket_updated_at),
    ) == (should_process and flag_value)


def test_zendesk_comment_processing_job_lock_timeout(factories):
    # first hold the lock
    with zendesk_comment_processing_job_lock(
        zendesk_comment_id=123,
        lock_timeout_sec=5,
    ):
        # for giggles lets try to grab the lock multiple times this validates
        # that lock timeouts dont affect the original lock
        for _ in range(3):
            # now we expect if someone else tries to get the lock (and timeout)
            # before we release the first lock we should except
            with pytest.raises(LockTimeout):
                with zendesk_comment_processing_job_lock(
                    zendesk_comment_id=123,
                    # we have this value low to increase the speed of the test.
                    # we are only testing that this lock grab fails because of upper
                    # scope lock
                    lock_timeout_sec=0.1,
                ):
                    pass


def test_zendesk_comment_processing_job_lock(factories):
    # this test shows that serial operations on the same lock happen without
    # interference
    counter = 0
    for _ in range(10):
        with zendesk_comment_processing_job_lock(
            zendesk_comment_id=123,
            lock_timeout_sec=0.5,
        ):
            counter += 1
        # lock is released when scope exits
    assert counter == 10


@mock.patch("common.stats.increment")
def test_signal_on_comment_author_error_no_user(
    mock_stats_incr,
):
    comment_author_email = "foo@bar.com"
    inbound_message = ZDTestMessageSchema(
        comment_author_email=comment_author_email,
    )
    signal_on_comment_author_error(
        inbound_message=inbound_message,
    )
    mock_stats_incr.assert_called_with(
        metric_name=ZENDESK_MESSAGE_PROCESSING_UNKNOWN_AUTHOR,
        pod_name=stats.PodNames.VIRTUAL_CARE,
        tags=[
            "group:no_user_found",
        ],
    )


@mock.patch("common.stats.increment")
def test_signal_on_comment_author_error_practitioner(
    mock_stats_incr,
    factories,
):
    practitioner = factories.PractitionerUserFactory.create()
    inbound_message = ZDTestMessageSchema(
        comment_author_email=practitioner.email,
    )
    signal_on_comment_author_error(
        inbound_message=inbound_message,
    )
    mock_stats_incr.assert_called_with(
        metric_name=ZENDESK_MESSAGE_PROCESSING_UNKNOWN_AUTHOR,
        pod_name=stats.PodNames.VIRTUAL_CARE,
        tags=[
            "group:practitioner",
        ],
    )


@mock.patch("common.stats.increment")
def test_signal_on_comment_author_error_member(
    mock_stats_incr,
    factories,
):
    member = factories.MemberFactory.create()
    inbound_message = ZDTestMessageSchema(
        comment_author_email=member.email,
    )
    signal_on_comment_author_error(
        inbound_message=inbound_message,
    )
    mock_stats_incr.assert_called_with(
        metric_name=ZENDESK_MESSAGE_PROCESSING_UNKNOWN_AUTHOR,
        pod_name=stats.PodNames.VIRTUAL_CARE,
        tags=[
            "group:member",
        ],
    )


@mock.patch("tasks.zendesk_v2.update_message_attrs")
@mock.patch("tasks.zendesk_v2.notify_new_message")
@mock.patch("tasks.zendesk_v2.process_credits_after_message_receive")
@mock.patch("tasks.zendesk_v2.record_successful_processing_of_inbound_zendesk_message")
@mock.patch("tasks.zendesk_v2.get_channel_and_message_author")
@mock.patch("tasks.zendesk_v2.get_author")
@mock.patch(
    "tasks.zendesk_v2.is_wallet_response",
    return_value=False,
)
@mock.patch(
    "tasks.zendesk_v2.get_member",
    return_value=User(),
)
@mock.patch(
    "tasks.zendesk_v2.has_zendesk_comment_id_been_processed",
    return_value=False,
)
def test_process_zendesk_inbound_message_message_creation(
    mock_has_zendesk_comment_id_been_processed,
    mock_get_member,
    mock_is_wallet_response,
    mock_get_author,
    mock_get_channel_and_message_author,
    mock_record_successful_processing_of_inbound_zendesk_message,
    mock_process_credits_after_message_receive,
    mock_notify_new_message,
    mock_update_message_attrs,
    factories,
    db,
):
    cx_vertical = factories.VerticalFactory(name=CX_VERTICAL_NAME)
    practitioner = factories.PractitionerUserFactory(
        practitioner_profile__verticals=[cx_vertical],
    )
    channel = factories.ChannelFactory.create()

    mock_get_author.return_value = practitioner
    mock_get_channel_and_message_author.return_value = (channel, practitioner)

    inbound_message = ZDTestMessageSchema(
        message_body="foobar",
        comment_id=1234,
        comment_author_email=practitioner.email,
    )

    process_zendesk_inbound_message_worker(inbound_message=inbound_message)

    mock_has_zendesk_comment_id_been_processed.assert_called()
    mock_get_member.assert_called()
    mock_is_wallet_response.assert_called()

    new_message = (
        db.session.query(Message)
        .filter(Message.zendesk_comment_id == inbound_message.comment_id)
        .filter(Message.channel == channel)
        .one()
    )
    assert new_message is not None


@pytest.mark.parametrize(
    ("maven_user_email", "zendesk_user_id", "expected_user_email"),
    (
        (None, None, None),
        (MAVEN_SUPPORT_EMAIL_ADDRESS, None, None),
        (MAVEN_SUPPORT_EMAIL_ADDRESS, 123, None),
        # no match
        ("no_match@maven.com", 999, None),
        ("no_match@maven.com", None, None),
        # match on zendesk_user_id and zd_id
        ("1@maven.com", 1, "1@maven.com"),
        # match on email but zd_id does not match
        ("no_zd_id@maven.com", 999, "no_zd_id@maven.com"),
        # match on zendesk user id but email does not match
        # to maintain legacy behavior we return the user identified by the zendesk_user_id
        ("no_match@maven.com", 1, "1@maven.com"),
        # match both to different users
        # we expect the zendesk_user_id to take precedence
        ("1@maven.com", 2, "2@maven.com"),
        # dont match on zd_id
        # match on email and the user.zendesk_user_id does not match
        # to maintain legacy behavior we return the user identified by email
        ("1@maven.com", 999, "1@maven.com"),
        # match by zd_id to a care coordinator
        # cc users should not be returned as the target member
        ("no_match@maven.com", 3, None),
        ("cc@maven.com", 3, None),
        # match by email only to a care coordinator
        # cc users should not be returned as the target member
        ("no_match@maven.com", 999, None),
        ("cc@maven.com", 999, None),
        # if only the zendesk user id is provided we should still make an
        # attempt to locate the member.
        (None, 1, "1@maven.com"),
    ),
)
def test_get_member(
    maven_user_email,
    zendesk_user_id,
    expected_user_email,
    factories,
):

    factories.MemberFactory.create(email="1@maven.com", zendesk_user_id=1)
    factories.MemberFactory.create(email="2@maven.com", zendesk_user_id=2)
    factories.MemberFactory.create(email="no_zd_id@maven.com", zendesk_user_id=None)

    ca_practitioner = factories.PractitionerUserFactory()
    ca_practitioner.email = "cc@maven.com"
    ca_practitioner.zendesk_user_id = 3
    ca_vertical = factories.VerticalFactory(name=CX_VERTICAL_NAME)
    ca_practitioner.practitioner_profile.verticals = [ca_vertical]

    found_member = get_member(
        maven_user_email=maven_user_email,
        zendesk_user_id=zendesk_user_id,
    )
    if expected_user_email:
        assert found_member
        assert found_member.email == expected_user_email
    else:
        assert not found_member


@pytest.mark.parametrize(
    ("maven_user_email", "zendesk_user_id"),
    (
        (None, None),
        (None, 123),
        ("foo@bar.com", None),
    ),
)
def test_recover_zendesk_user_id_required_data(
    maven_user_email,
    zendesk_user_id,
):
    with pytest.raises(ValueError):
        recover_zendesk_user_id(
            maven_user_email=maven_user_email,
            zendesk_user_id=zendesk_user_id,
        )


def test_recover_zendesk_user_id_no_matching_user(
    factories,
):
    m = factories.MemberFactory.create(email="member@maven.com", zendesk_user_id=123)
    # does not raise an error and does not modify the zendesk user id
    with does_not_raise():
        recover_zendesk_user_id(
            maven_user_email="foo@bar.com",
            zendesk_user_id=999,
        )
    assert m.zendesk_user_id == 123


def test_recover_zendesk_user_id_existing_zendesk_user_id(
    factories,
):
    member = factories.MemberFactory.create(
        email="member@maven.com",
        zendesk_user_id=123,
    )
    recover_zendesk_user_id(
        maven_user_email="member@maven.com",
        zendesk_user_id=999,
    )

    # no change to the member found by email
    assert member.zendesk_user_id == 123


def test_recover_zendesk_user_id_sets_zendesk_user_id(
    factories,
):
    member = factories.MemberFactory.create(
        email="member@maven.com",
        zendesk_user_id=None,
    )
    recover_zendesk_user_id(
        maven_user_email="member@maven.com",
        zendesk_user_id=456,
    )

    # no change to the member
    assert member.zendesk_user_id == 456
