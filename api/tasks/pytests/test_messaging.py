from datetime import datetime, timedelta
from unittest import mock
from unittest.mock import ANY, patch

import pytest
from zenpy.lib.exception import APIException as ZendeskAPIException

from common import stats
from messaging.models.messaging import (
    Channel,
    ChannelUsers,
    Message,
    MessageCredit,
    MessageSourceEnum,
)
from messaging.services.zendesk import (
    MessagingZendeskTicket,
    ZendeskInvalidRecordException,
)
from models.tracks import TrackName
from pytests.freezegun import freeze_time
from tasks.messaging import (
    create_zd_ticket_for_unresponded_promoted_messages,
    refund_message_credits,
    send_cx_intro_message_for_enterprise_users,
    send_to_zendesk,
)
from utils.constants import SEND_TO_ZENDESK_ERROR_COUNT_METRICS


def create_zd_ticket_content(message, member, provider):
    return (
        "A message to a provider has not been responded to in 24 hours. Please "
        "recommend a provider in the same vertical who has availability in the next 24 hours.\n"
        f"Provider: {provider.full_name}\n"
        f"Provider Vertical: {provider.practitioner_profile.vertical}\n"
        f"Member ID: {member.id}\n"
        f"Message date: {message.created_at}"
    )


@pytest.fixture()
def make_message_credits(db):
    def _make_message_credits(member, credit_count):
        message_credits = [
            MessageCredit(
                user_id=member.id,
                respond_by=datetime.utcnow() - timedelta(days=1),
            )
            for _ in range(credit_count)
        ]
        db.session.add_all(message_credits)
        db.session.commit()

    return _make_message_credits


@pytest.fixture
def new_channel(factories):
    def create_new_channel():
        practitioner = factories.PractitionerUserFactory.create()
        member = factories.EnterpriseUserFactory.create()
        message_channel = factories.ChannelFactory.create(
            name=f"{member.first_name}, {practitioner.first_name}"
        )
        channel_user_member = factories.ChannelUsersFactory.create(
            channel_id=message_channel.id,
            user_id=member.id,
            channel=message_channel,
            user=member,
        )
        channel_user_provider = factories.ChannelUsersFactory.create(
            channel_id=message_channel.id,
            user_id=practitioner.id,
            channel=message_channel,
            user=practitioner,
        )
        message_channel.participants = [channel_user_member, channel_user_provider]

        return message_channel, member, practitioner

    return create_new_channel


@freeze_time("2023-12-23 18:45:00")
def test_create_zd_ticket_for_unresponded_promoted_messages(
    factories,
    new_channel,
):
    top_of_hour = datetime.utcnow().replace(minute=0, second=0, microsecond=0)
    message_channel, member, provider = new_channel()

    # This message should not be found because it is too old
    factories.MessageFactory.create(
        body="testing test",
        channel_id=message_channel.id,
        created_at=top_of_hour - timedelta(days=1, hours=3),
        modified_at=top_of_hour,
        status=1,
        user_id=member.id,
        credit=MessageCredit(respond_by=top_of_hour, user=message_channel.member),
        source=MessageSourceEnum.PROMOTE_MESSAGING.value,
    )

    # This message should not be found because it is too new
    factories.MessageFactory.create(
        body="testing test",
        channel_id=message_channel.id,
        created_at=top_of_hour - timedelta(hours=9),
        modified_at=top_of_hour,
        status=1,
        user_id=member.id,
        credit=MessageCredit(respond_by=top_of_hour, user=message_channel.member),
        source=MessageSourceEnum.PROMOTE_MESSAGING.value,
    )

    expected_message = factories.MessageFactory.create(
        body="testing test",
        channel_id=message_channel.id,
        created_at=top_of_hour - timedelta(hours=24, minutes=30),
        modified_at=top_of_hour,
        status=1,
        user_id=member.id,
        credit=MessageCredit(respond_by=top_of_hour, user=message_channel.member),
        source=MessageSourceEnum.PROMOTE_MESSAGING.value,
    )

    with patch("tasks.messaging.send_general_ticket_to_zendesk") as patch_zendesk:
        create_zd_ticket_for_unresponded_promoted_messages()

        expected_ticket_content = create_zd_ticket_content(
            expected_message, member, provider
        )
        patch_zendesk.assert_called_once_with(
            user=ANY, ticket_subject=ANY, content=expected_ticket_content, tags=ANY
        )


@freeze_time("2023-12-23 18:45:00")
def test_create_zd_ticket_for_unresponded_promoted_messages__multiple_channels(
    factories,
    new_channel,
):
    top_of_hour = datetime.utcnow().replace(minute=0, second=0, microsecond=0)
    message_channel_1, member_1, provider_1 = new_channel()
    message_channel_2, member_2, provider_2 = new_channel()
    message_channel_3, member_3, provider_3 = new_channel()

    factories.MessageFactory.create(
        body="testing test",
        channel_id=message_channel_1.id,
        created_at=top_of_hour - timedelta(days=1, minutes=30),
        modified_at=top_of_hour,
        status=1,
        user_id=member_1.id,
        credit=MessageCredit(respond_by=top_of_hour, user=message_channel_1.member),
        source=MessageSourceEnum.PROMOTE_MESSAGING.value,
    )
    factories.MessageFactory.create(
        body="testing test two",
        channel_id=message_channel_2.id,
        created_at=top_of_hour - timedelta(days=1, minutes=30),
        modified_at=top_of_hour,
        status=1,
        user_id=member_2.id,
        credit=MessageCredit(respond_by=top_of_hour, user=message_channel_2.member),
        source=MessageSourceEnum.PROMOTE_MESSAGING.value,
    )
    factories.MessageFactory.create(
        body="testing test three",
        channel_id=message_channel_3.id,
        created_at=top_of_hour - timedelta(days=1, minutes=30),
        modified_at=top_of_hour,
        status=1,
        user_id=member_3.id,
        credit=MessageCredit(respond_by=top_of_hour, user=message_channel_3.member),
        source=MessageSourceEnum.PROMOTE_MESSAGING.value,
    )

    with patch("tasks.messaging.send_general_ticket_to_zendesk") as patch_zendesk:
        create_zd_ticket_for_unresponded_promoted_messages()
        assert patch_zendesk.call_count == 3


@mock.patch("messaging.services.zendesk.SynchronizedZendeskTicket.update_zendesk")
def test_send_to_zendesk(
    mock_update_zendesk,
    factories,
    new_channel,
):
    message_channel_1, member_1, provider_1 = new_channel()
    msg = factories.MessageFactory.create(
        channel_id=message_channel_1.id,
        user_id=member_1.id,
    )
    # When
    send_to_zendesk(msg.id)

    # Then
    mock_update_zendesk.assert_called_once()


@mock.patch(
    "tasks.messaging.stats.increment",
)
@mock.patch.object(
    MessagingZendeskTicket,
    "update_zendesk",
    side_effect=ZendeskInvalidRecordException(),
)
def test_send_to_zendesk_validation_errors(
    mock_messaging_zendesk_ticket,
    mock_stats,
    factories,
    new_channel,
):
    message_channel_1, member_1, provider_1 = new_channel()
    msg = factories.MessageFactory.create(
        channel_id=message_channel_1.id,
        user_id=member_1.id,
    )
    # we expect success of the job when we hit data validation errors
    send_to_zendesk(msg.id)
    # and we expect a metric
    mock_stats.assert_any_call(
        metric_name=SEND_TO_ZENDESK_ERROR_COUNT_METRICS,
        pod_name=stats.PodNames.VIRTUAL_CARE,
        tags=["reason:zendesk_data_validation_error"],
    )


@mock.patch(
    "messaging.services.zendesk_client.ZendeskClient.create_or_update_user",
)
@mock.patch(
    "zenpy.lib.api.TicketApi.create",
)
def test_update_zendesk_validation_errors(
    mock_zenpy_create,
    mock_create_or_update_user,
    factories,
    new_channel,
):
    # Given
    message_channel_1, member_1, provider_1 = new_channel()
    msg = factories.MessageFactory.create(
        channel_id=message_channel_1.id,
        user_id=member_1.id,
    )
    mock_create_or_update_user.return_value = member_1
    mockResponse = mock.Mock()
    mockResponse.json.return_value = {
        "error": "RecordInvalid",
        "description": "Record validation errors",
    }
    mock_zenpy_create.side_effect = ZendeskAPIException(response=mockResponse)

    # Then expect a ZendeskInvalidRecordException raised
    with pytest.raises(ZendeskInvalidRecordException):
        # When
        MessagingZendeskTicket(message=msg, initial_cx_message=False).update_zendesk()


def test_refund_message_credits(make_message_credits, factories):
    credit_count = 10

    member = factories.MemberFactory.create()
    make_message_credits(member, credit_count)

    with mock.patch("messaging.models.messaging.MessageCredit.refund") as refund_mock:
        refund_message_credits(chunk_size=credit_count, max_per_job_run=credit_count)
        assert refund_mock.call_count == credit_count


def test_refund_message_credits_audit_trail(make_message_credits, factories):
    credit_count = 10

    member = factories.MemberFactory.create()
    make_message_credits(member, credit_count)

    with mock.patch("tasks.messaging.audit") as audit_mock:
        refund_message_credits(chunk_size=credit_count, max_per_job_run=credit_count)
        assert audit_mock.call_count == credit_count


def test_refund_message_credits_stats(make_message_credits, factories):
    credit_count = 10
    member = factories.MemberFactory.create()
    make_message_credits(member, credit_count)

    with mock.patch("tasks.messaging.stats.gauge") as mocked_gauge:
        refund_message_credits(chunk_size=credit_count, max_per_job_run=credit_count)

        # filter to the gauge calls specific to pending refunds
        pending_refund_gauge_calls = [
            call
            for call in mocked_gauge.call_args_list
            if call[1]["metric_name"] == "mono.messaging.message_credits.pending_refund"
        ]

        # expect gauge call before AND after job
        assert len(pending_refund_gauge_calls) == 2

        # first call should be total credits
        args, kwargs = pending_refund_gauge_calls[0]
        assert kwargs["metric_value"] == credit_count

        # we should have processed all of them
        args, kwargs = pending_refund_gauge_calls[1]
        assert kwargs["metric_value"] == 0


def test_refund_message_credits_isolation(db, make_message_credits, factories):
    credit_count = 10
    member = factories.MemberFactory.create()
    make_message_credits(member, credit_count)

    count_before = db.session.query(MessageCredit).count()
    assert count_before == credit_count

    # exceptions thrown for a given refund should not impact other refunds
    with mock.patch.object(
        MessageCredit, "refund", side_effect=Exception("test"), autospec=True
    ) as refund_mock:
        refund_message_credits(chunk_size=credit_count, max_per_job_run=credit_count)

    assert refund_mock.call_count == credit_count
    # ensure credit refunds will be retried. while this can pile up if
    # exceptions are thrown on each retry, it will give us a clear indicator
    # of the problem and allow for an explicit fix
    count_before = db.session.query(MessageCredit).count()
    assert count_before == credit_count


def test_refund_message_credits_chunking(make_message_credits, factories):
    credit_count = 10
    member = factories.MemberFactory.create()
    make_message_credits(member, credit_count)

    chunk_size = 2
    # ensure multiple chunks will be required to get all credit records
    assert chunk_size < credit_count

    with mock.patch("messaging.models.messaging.MessageCredit.refund") as refund_mock:
        refund_message_credits(chunk_size=2, max_per_job_run=credit_count)

    # ensure multiple chunks were processed and all credits were refunded
    assert refund_mock.call_count == credit_count


def test_refund_message_credits_job_limit(make_message_credits, factories):
    credit_count = 10
    member = factories.MemberFactory.create()
    make_message_credits(member, credit_count)

    chunk_size = 1
    max_per_job_run = 5

    assert chunk_size < max_per_job_run

    with mock.patch("messaging.models.messaging.MessageCredit.refund") as refund_mock:
        refund_message_credits(chunk_size=1, max_per_job_run=max_per_job_run)

    # ensure we respect the max_per_job_run limit
    assert refund_mock.call_count == max_per_job_run


def test_cx_intro_message(factories, db):
    # given
    user = factories.EnterpriseUserFactory(
        created_at=datetime.now() - timedelta(hours=1), tracks=[]  # noqa
    )
    factories.MemberTrackFactory.create(user=user, name=TrackName.PREGNANCY)
    # channel with no messages
    cx_id = user.care_coordinators[0].id
    cx_channel = ChannelUsers.find_existing_channel([user.id, cx_id])
    assert not cx_channel
    # when
    send_cx_intro_message_for_enterprise_users(hours_ago=1)
    db.session.commit()

    # then
    cx_channel = ChannelUsers.find_existing_channel([user.id, cx_id])
    assert len(cx_channel.messages) == 1
    assert cx_channel.messages[0].user.id == cx_id


def test_cx_intro_message__track_ca_message_off(factories, db):
    # given
    user = factories.EnterpriseUserFactory(
        created_at=datetime.now() - timedelta(hours=1), tracks=[]  # noqa
    )
    client_track = factories.ClientTrackFactory(
        track=TrackName.SURROGACY,
    )
    factories.MemberTrackFactory.create(
        user=user,
        name=TrackName.SURROGACY,
        client_track=client_track,
    )
    # channel with no messages
    cx_id = user.care_coordinators[0].id
    cx_channel = ChannelUsers.find_existing_channel([user.id, cx_id])
    assert not cx_channel
    # when
    send_cx_intro_message_for_enterprise_users(hours_ago=1)
    db.session.commit()

    # then
    cx_channel = ChannelUsers.find_existing_channel([user.id, cx_id])
    assert not cx_channel


def test_cx_intro_message__thread_started(factories, db):
    # given
    user = factories.EnterpriseUserFactory(
        created_at=datetime.now() - timedelta(hours=1), tracks=[]  # noqa
    )
    factories.MemberTrackFactory.create(user=user, name=TrackName.PREGNANCY)
    # channel with no messages
    cx_channel = Channel.get_or_create_channel(user.care_coordinators[0], [user])
    Message(user=user.care_coordinators[0], channel=cx_channel, body="intro message")
    db.session.commit()
    assert len(cx_channel.messages) == 1
    # when
    send_cx_intro_message_for_enterprise_users(hours_ago=1)
    db.session.commit()

    # then assert no new messages written
    assert len(cx_channel.messages) == 1


def test_cx_intro_message__intro_app_scheduled(factories, db):
    # given
    user = factories.EnterpriseUserFactory(
        created_at=datetime.now() - timedelta(hours=1), tracks=[]  # noqa
    )
    factories.MemberTrackFactory.create(user=user, name=TrackName.PREGNANCY)
    # channel with no messages
    cx_id = user.care_coordinators[0].id
    cx_channel = ChannelUsers.find_existing_channel([user.id, cx_id])
    assert not cx_channel
    # pre-existing intro appt
    schedule = factories.ScheduleFactory.create(user=user)
    factories.AppointmentFactory.create_with_practitioner(
        member_schedule=schedule,
        purpose="introduction",
        practitioner=user.care_coordinators[0],
        scheduled_start=datetime.now() + timedelta(minutes=30),  # noqa
        scheduled_end=None,
    )
    # when
    send_cx_intro_message_for_enterprise_users(hours_ago=1)
    db.session.commit()

    # then
    cx_channel = ChannelUsers.find_existing_channel([user.id, cx_id])
    assert not cx_channel


def test_cx_intro_message__no_track(factories, db):
    # given
    user = factories.EnterpriseUserFactory(
        created_at=datetime.now() - timedelta(hours=1), tracks=[]  # noqa
    )
    factories.MemberTrackFactory.create(
        user=user,
        name=TrackName.PREGNANCY,
        ended_at=datetime.now(),  # noqa
    )

    # channel with no messages
    cx_id = user.care_coordinators[0].id
    cx_channel = ChannelUsers.find_existing_channel([user.id, cx_id])
    assert not cx_channel
    # when
    send_cx_intro_message_for_enterprise_users(hours_ago=1)
    db.session.commit()

    # then
    cx_channel = ChannelUsers.find_existing_channel([user.id, cx_id])
    assert not cx_channel
