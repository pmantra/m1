import datetime
from unittest.mock import call, patch

from appointments.tasks.availability_requests import (
    find_stale_request_availability_messages,
)


class AnyMemberWithId(dict):
    def __eq__(self, other):
        return self["id"] == other.__dict__["id"]


def test_find_stale_request_availability_messages(availability_notification_req):
    """
    Verifies that we successfully find stale availability request messages
    """
    request_dt = datetime.datetime.utcnow() - datetime.timedelta(days=2, minutes=30)
    avail_req, channel = availability_notification_req(request_dt)
    member = avail_req.member
    practitioner = avail_req.practitioner
    prac_name = f"{practitioner.first_name} {practitioner.last_name}"

    with patch(
        "appointments.tasks.availability_requests.create_zendesk_ticket"
    ) as patch_zendesk:
        find_stale_request_availability_messages()
        patch_zendesk.assert_called_once_with(
            avail_req.id, prac_name, AnyMemberWithId(member.__dict__), ""
        )


def test_find_stale_request_availability_messages_multiple_requests(
    factories, availability_notification_req
):
    """
    Verifies that we successfully find stale availability request messages when there are multiple requests
    """
    expected_zendesk_calls = []
    first_channel = None
    second_channel = None
    first_prac = None
    second_prac = None
    for i in range(0, 5):
        request_dt = datetime.datetime.utcnow() - datetime.timedelta(days=2, minutes=30)
        avail_req, channel = availability_notification_req(request_dt)
        member = avail_req.member
        practitioner = avail_req.practitioner
        prac_name = f"{practitioner.first_name} {practitioner.last_name}"

        # practitioner response will be created for the first two
        if i == 0:
            first_channel = channel
            first_prac = practitioner
        elif i == 1:
            second_channel = channel
            second_prac = practitioner
        else:
            expected_zendesk_calls.append(
                call(avail_req.id, prac_name, AnyMemberWithId(member.__dict__), "")
            )

    # prac response to first request
    response_dt = datetime.datetime.utcnow() - datetime.timedelta(days=1, hours=4)
    factories.MessageFactory.create(
        availability_notification_request_id=None,
        body="Request availability message body",
        channel_id=first_channel.id,
        created_at=response_dt,
        modified_at=response_dt,
        status=1,
        user_id=first_prac.id,
    )

    # prac response to second request
    response_dt = datetime.datetime.utcnow() - datetime.timedelta(days=1, hours=14)
    factories.MessageFactory.create(
        availability_notification_request_id=None,
        body="Request availability message body",
        channel_id=second_channel.id,
        created_at=response_dt,
        modified_at=response_dt,
        status=1,
        user_id=second_prac.id,
    )

    with patch(
        "appointments.tasks.availability_requests.create_zendesk_ticket"
    ) as patch_zendesk:
        find_stale_request_availability_messages()
        patch_zendesk.assert_has_calls(expected_zendesk_calls, any_order=True)


def test_no_stale_request_availability_messages_too_old(availability_notification_req):
    """
    Verifies that we do not find stale availability request messages when they are > 25 hours
    """
    request_dt = datetime.datetime.utcnow() - datetime.timedelta(days=2, hours=12)
    avail_req, channel = availability_notification_req(request_dt)

    with patch(
        "appointments.tasks.availability_requests.create_zendesk_ticket"
    ) as patch_zendesk:
        find_stale_request_availability_messages()
        patch_zendesk.assert_not_called()


def test_no_stale_request_availability_messages_too_new(availability_notification_req):
    """
    Verifies that we do not find stale availability request messages when they are < 24 hours
    """
    request_dt = datetime.datetime.utcnow() - datetime.timedelta(days=1, hours=12)
    avail_req, channel = availability_notification_req(request_dt)

    with patch(
        "appointments.tasks.availability_requests.create_zendesk_ticket"
    ) as patch_zendesk:
        find_stale_request_availability_messages()
        patch_zendesk.assert_not_called()


def test_no_stale_request_availability_messages_already_responded(
    db, factories, availability_notification_req
):
    """
    Verifies that we do not find stale availability request messages when they have been responded to
    """
    request_dt = datetime.datetime.utcnow() - datetime.timedelta(days=2, minutes=30)
    avail_req, channel = availability_notification_req(request_dt)

    # Stale before response
    with patch(
        "appointments.tasks.availability_requests.create_zendesk_ticket"
    ) as patch_zendesk:
        find_stale_request_availability_messages()

        # Runs into caching issues if this is not called
        db.session.expire_all()

        prac_name = (
            f"{avail_req.practitioner.first_name} {avail_req.practitioner.last_name}"
        )
        patch_zendesk.assert_called_once_with(
            avail_req.id, prac_name, AnyMemberWithId(avail_req.member.__dict__), ""
        )

    # Practitioner response
    response_dt = datetime.datetime.utcnow() - datetime.timedelta(days=1, hours=4)
    factories.MessageFactory.create(
        availability_notification_request_id=avail_req.id,
        body="",
        channel_id=channel.id,
        created_at=response_dt,
        modified_at=response_dt,
        status=1,
        user_id=avail_req.practitioner.id,
    )

    with patch(
        "appointments.tasks.availability_requests.create_zendesk_ticket"
    ) as patch_zendesk:
        find_stale_request_availability_messages()
        patch_zendesk.assert_not_called()


def test_no_stale_request_availability_messages_previous_messages(
    factories, availability_notification_req
):
    """
    Tests find_stale_request_availability_messages when there are previous messages in the channel
    """
    request_dt = datetime.datetime.utcnow() - datetime.timedelta(days=2, minutes=30)
    avail_req, channel = availability_notification_req(request_dt)

    # Older messages
    factories.MessageFactory.create(
        availability_notification_request_id=avail_req.id,
        body="",
        channel_id=channel.id,
        created_at=request_dt - datetime.timedelta(days=5),
        modified_at=request_dt - datetime.timedelta(days=5),
        status=1,
        user_id=avail_req.member.id,
    )
    factories.MessageFactory.create(
        availability_notification_request_id=avail_req.id,
        body="",
        channel_id=channel.id,
        created_at=request_dt - datetime.timedelta(days=4),
        modified_at=request_dt - datetime.timedelta(days=4),
        status=1,
        user_id=avail_req.practitioner.id,
    )

    # Practitioner response
    response_dt = datetime.datetime.utcnow() - datetime.timedelta(days=1, hours=4)
    factories.MessageFactory.create(
        availability_notification_request_id=avail_req.id,
        body="",
        channel_id=channel.id,
        created_at=response_dt,
        modified_at=response_dt,
        status=1,
        user_id=avail_req.practitioner.id,
    )

    with patch(
        "appointments.tasks.availability_requests.create_zendesk_ticket"
    ) as patch_zendesk:
        find_stale_request_availability_messages()
        patch_zendesk.assert_not_called()


def test_no_stale_request_availability_messages_member_messages_again(
    factories, availability_notification_req
):
    """
    Tests find_stale_request_availability_messages when the member sends a follow up message
    """
    request_dt = datetime.datetime.utcnow() - datetime.timedelta(days=2, minutes=30)
    avail_req, channel = availability_notification_req(request_dt)

    # Member follow up message
    factories.MessageFactory.create(
        availability_notification_request_id=avail_req.id,
        body="",
        channel_id=channel.id,
        created_at=request_dt + datetime.timedelta(minutes=5),
        modified_at=request_dt + datetime.timedelta(minutes=5),
        status=1,
        user_id=avail_req.member.id,
    )

    # Practitioner response
    response_dt = datetime.datetime.utcnow() - datetime.timedelta(days=1, hours=4)
    factories.MessageFactory.create(
        availability_notification_request_id=avail_req.id,
        body="",
        channel_id=channel.id,
        created_at=response_dt,
        modified_at=response_dt,
        status=1,
        user_id=avail_req.practitioner.id,
    )

    with patch(
        "appointments.tasks.availability_requests.create_zendesk_ticket"
    ) as patch_zendesk:
        find_stale_request_availability_messages()
        patch_zendesk.assert_not_called()


def test_find_stale_request_availability_messages_previous_request(
    factories, availability_notification_req
):
    """
    Verifies that we successfully find stale availability request messages if has been a previous availability request
    """
    # Old request
    request_dt = datetime.datetime.utcnow() - datetime.timedelta(days=4, minutes=30)
    avail_req, channel = availability_notification_req(request_dt)
    member = avail_req.member
    practitioner = avail_req.practitioner

    # Practitioner response
    response_dt = datetime.datetime.utcnow() - datetime.timedelta(days=3, hours=4)
    factories.MessageFactory.create(
        availability_notification_request_id=None,
        body="Request availability response",
        channel_id=channel.id,
        created_at=response_dt,
        modified_at=response_dt,
        status=1,
        user_id=practitioner.id,
    )

    # New, unresponded request
    request_dt = datetime.datetime.utcnow() - datetime.timedelta(days=2, minutes=30)
    avail_req, channel = availability_notification_req(request_dt)
    member = avail_req.member
    practitioner = avail_req.practitioner
    prac_name = f"{practitioner.first_name} {practitioner.last_name}"

    with patch(
        "appointments.tasks.availability_requests.create_zendesk_ticket"
    ) as patch_zendesk:
        find_stale_request_availability_messages()
        patch_zendesk.assert_called_once_with(
            avail_req.id, prac_name, AnyMemberWithId(member.__dict__), ""
        )
