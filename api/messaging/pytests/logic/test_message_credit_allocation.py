import datetime
from unittest import mock

import pytest

from appointments.models.payments import Credit
from messaging.logic.message_credit import (
    MessageCreditException,
    _create_reply_message,
    mark_all_message_credits_as_responded_to,
    pay_with_credits,
)
from messaging.models.messaging import MessageCredit
from pytests.freezegun import freeze_time
from storage.connection import db


@freeze_time("2023-12-01T17:00:00")
def test_use_all_message_credits_in_channel(factories, message_channel):
    """
    Scenario:
        When a practitioner sends a message, if there are unused credits,
        associate the response with all of the message credits since the
        most recent previously responded message
    """
    now = datetime.datetime.utcnow()

    # Already used credit
    expected_used_msg_credit_responded_at = now - datetime.timedelta(days=2)
    used_msg_credit = factories.MessageCreditFactory.create(
        user_id=message_channel.member.id,
        responded_at=expected_used_msg_credit_responded_at,
    )
    factories.MessageFactory.create(
        body="member test",
        channel_id=message_channel.id,
        user_id=message_channel.member.id,
        credit=used_msg_credit,
        created_at=now - datetime.timedelta(days=3),
    )

    # Unused credit older than 24 hours
    unused_message_credit_1 = factories.MessageCreditFactory.create(
        user_id=message_channel.member.id
    )
    factories.MessageFactory.create(
        body="member test",
        channel_id=message_channel.id,
        user_id=message_channel.member.id,
        credit=unused_message_credit_1,
        created_at=now - datetime.timedelta(hours=36),
    )
    # Recent unused credit
    unused_message_credit_2 = factories.MessageCreditFactory.create(
        user_id=message_channel.member.id
    )
    factories.MessageFactory.create(
        body="member test",
        channel_id=message_channel.id,
        user_id=message_channel.member.id,
        credit=unused_message_credit_2,
        created_at=now - datetime.timedelta(hours=1),
    )

    practitioner_response = factories.MessageFactory.create(
        body="prac test",
        channel_id=message_channel.id,
        user_id=message_channel.practitioner.id,
        created_at=now - datetime.timedelta(minutes=30),
    )
    mark_all_message_credits_as_responded_to(message_channel, practitioner_response)
    db.session.refresh(unused_message_credit_1)
    db.session.refresh(unused_message_credit_2)

    assert unused_message_credit_1.responded_at is not None
    assert unused_message_credit_1.response == practitioner_response
    assert unused_message_credit_2.responded_at is not None
    assert unused_message_credit_2.response == practitioner_response


def test_pay_with_credits_remaining_balance(message_channel):
    """
    Scenario:
        The amount of available credits covers the balance.
    """
    current_time = datetime.datetime.utcnow()

    available_credits = [
        Credit(
            amount=1,
            expires_at=current_time + datetime.timedelta(hours=1),
            user_id=message_channel.member.id,
        ),
        Credit(
            amount=1,
            expires_at=current_time + datetime.timedelta(hours=2),
            user_id=message_channel.member.id,
        ),
        Credit(
            amount=1,
            expires_at=current_time + datetime.timedelta(hours=2),
            user_id=message_channel.member.id,
        ),
    ]

    remaining, used_credits = pay_with_credits(2, available_credits)
    assert remaining == 0
    assert used_credits == available_credits[0:2]


def test_pay_with_credits_not_enough_credits(message_channel):
    """
    Scenario:
        There are not enough credits to cover the balance.
    """
    current_time = datetime.datetime.utcnow()

    available_credits = [
        Credit(
            amount=1,
            expires_at=current_time + datetime.timedelta(hours=1),
            user_id=message_channel.member.id,
        ),
    ]

    remaining, used_credits = pay_with_credits(2, available_credits)
    assert remaining == 1
    assert used_credits == available_credits


@mock.patch("tracks.service.TrackSelectionService.get_organization_id_for_user")
def test__create_reply_message_enterprise__user_has_credits(
    mock_organization_id, factories
):
    mock_organization_id.return_value = 123

    # Given a scenario where user has credit to send messages
    member = factories.EnterpriseUserFactory.create()
    factories.OrganizationFactory.create(
        id=123,
        name="Test Organization Name",
    )
    factories.CreditFactory(user_id=member.id, amount=10)
    new_message = factories.MessageFactory.create()
    # assert that we do not start out with a message credit for the member
    message_credit = MessageCredit.query.filter(
        MessageCredit.user_id == member.id
    ).one_or_none()
    assert message_credit is None

    # When we call the function that ensures that the enterprise member has enough credit to send a message
    _create_reply_message(
        message=new_message, respond_by=datetime.datetime.utcnow(), user=member
    )

    # Then assert that we have generated a message credit for the member
    message_credit = MessageCredit.query.filter(
        MessageCredit.user_id == member.id
    ).one_or_none()
    assert message_credit is not None


@mock.patch("tracks.service.TrackSelectionService.get_organization_id_for_user")
@mock.patch("appointments.models.payments.Credit.available_amount_for_user")
def test__create_reply_message_enterprise_failure__no_credit_and_no_refill(
    mock_credit_available, mock_organization_id, factories
):
    # Given a scenario where user has no credit and the refill job has no effect
    mock_organization_id.return_value = 123
    mock_credit_available.return_value = 0
    member = factories.EnterpriseUserFactory.create()
    factories.OrganizationFactory.create(
        id=123,
        name="Test Organization Name",
    )
    factories.CreditFactory(user_id=member.id, amount=0)
    new_message = factories.MessageFactory.create()

    # Then assert MessageCreditException is raised due to member having insufficient credit
    with pytest.raises(MessageCreditException) as e:

        # When we call the function that ensures that the enterprise member has enough credit to send a message
        _create_reply_message(
            message=new_message, respond_by=datetime.datetime.utcnow(), user=member
        )

    # Then confirm we hit the error specifically for enterprise members
    assert e.value.user_is_enterprise


@mock.patch("tracks.service.TrackSelectionService.get_organization_id_for_user")
@mock.patch("messaging.logic.message_credit.log.warn")
def test__create_reply_message_enterprise_failure__no_credit_and_refill(
    mock_log_warn, mock_organization_id, factories
):
    # Given a scenario where user has no credit and the refill job has the desired effect
    mock_organization_id.return_value = 123
    member = factories.EnterpriseUserFactory.create()
    factories.OrganizationFactory.create(
        id=123, name="Test Organization Name", message_price=2
    )
    new_message = factories.MessageFactory.create()

    # When we call the function that ensures that the enterprise member has enough credit to send a message
    _create_reply_message(
        message=new_message, respond_by=datetime.datetime.utcnow(), user=member
    )

    # Then assert that we've kicked off the job to refill member credits since they can't pay for future messages
    # We will only assert that log line is called so we can evaluate side effects of refill_credits_for_enterprise_member and of available_amount_for_user
    mock_log_warn.assert_called_once_with(
        "User does not have enough enterprise credit to buy a message, refilling now.",
        user_id=member.id,
        balance=0,
    )

    # assert that we have generated a message credit for the member
    message_credit = MessageCredit.query.filter(
        MessageCredit.user_id == member.id
    ).one_or_none()
    assert message_credit is not None


@mock.patch("tracks.service.TrackSelectionService.get_organization_id_for_user")
@mock.patch("appointments.tasks.credits.refill_credits_for_enterprise_member.delay")
def test__create_reply_message_enterprise_add_credits(
    mock_refill_job, mock_organization_id, factories
):
    # Given a scenario where user has some little credit to send only one message
    mock_organization_id.return_value = 123

    member = factories.EnterpriseUserFactory.create()
    factories.OrganizationFactory.create(
        id=123, name="Test Organization Name", message_price=2
    )
    # set credit with amount '3', we can pay for one message but can't pay for any more
    factories.CreditFactory(user_id=member.id, amount=3)
    new_message = factories.MessageFactory.create()

    # When we call the function that ensures that the enterprise member has enough credit to send a message
    _create_reply_message(
        message=new_message, respond_by=datetime.datetime.utcnow(), user=member
    )

    # Then assert that we have generated a message credit for the member
    message_credit = MessageCredit.query.filter(
        MessageCredit.user_id == member.id
    ).one_or_none()
    assert message_credit is not None
    # assert that we've kicked off the job to refill member credits since they can't pay for future messages
    mock_refill_job.assert_called_once()


@mock.patch("tracks.service.TrackSelectionService.get_organization_id_for_user")
def test__create_reply_message_failure(mock_organization_id, factories):

    # Given a marketplace member
    mock_organization_id.return_value = None
    member = factories.DefaultUserFactory.create()
    new_message = factories.MessageFactory.create()

    # Then assert MessageCreditException is raised due to member having insufficient credit
    with pytest.raises(MessageCreditException) as e:

        # When call the function that ensures that the non-enterprise member has enough credit to send a message
        _create_reply_message(
            message=new_message, respond_by=datetime.datetime.utcnow(), user=member
        )
    # Then assert we got regular error not enterprise error
    assert not e.value.user_is_enterprise


@mock.patch("tracks.service.TrackSelectionService.get_organization_id_for_user")
@mock.patch("tracks.repository.MemberTrackRepository.get_active_tracks")
def test__create_reply_message_enterprise__user_marketplace_with_track(
    mock_active_tracks, mock_organization_id, factories
):
    # Given a scenario where we have a current marketplace member with org_id and active track
    mock_organization_id.return_value = 123
    mock_active_tracks.return_value = "mock_track"
    member = factories.DefaultUserFactory.create()
    factories.OrganizationFactory.create(
        id=123, name="Test Organization Name", message_price=2
    )
    factories.CreditFactory(user_id=member.id, amount=10)
    new_message = factories.MessageFactory.create()

    # assert that we do not start out with a message credit for the member
    message_credit = MessageCredit.query.filter(
        MessageCredit.user_id == member.id
    ).one_or_none()
    assert message_credit is None

    # When we call the function that checks messaging credit
    _create_reply_message(
        message=new_message, respond_by=datetime.datetime.utcnow(), user=member
    )

    # Then assert that we have generated a message credit for the member i.e. treated them as enterprise
    message_credit = MessageCredit.query.filter(
        MessageCredit.user_id == member.id
    ).one_or_none()
    assert message_credit is not None


@mock.patch("tracks.service.TrackSelectionService.get_organization_id_for_user")
@mock.patch("tracks.repository.MemberTrackRepository.get_active_tracks")
@mock.patch(
    "eligibility.service.EnterpriseVerificationService.get_eligible_organization_ids_for_user"
)
def test__create_reply_message_enterprise__user_with_track(
    mock_old_org_id, mock_active_tracks, mock_organization_id, factories
):
    mock_organization_id.return_value = 123
    mock_active_tracks.return_value = "mock_track"
    mock_old_org_id.return_value = None

    # Given a scenario where we have an enterprise member with org_id and active track through
    # new eligibility verification but no org id through old eligibility verification
    member = factories.EnterpriseUserFactory.create()
    factories.OrganizationFactory.create(
        id=123, name="Test Organization Name", message_price=2
    )
    factories.CreditFactory(user_id=member.id, amount=10)
    new_message = factories.MessageFactory.create()

    # When we call the function that ensures that checks credit
    _create_reply_message(
        message=new_message, respond_by=datetime.datetime.utcnow(), user=member
    )

    # Then assert that we have generated a message credit for the member
    message_credit = MessageCredit.query.filter(
        MessageCredit.user_id == member.id
    ).one_or_none()
    assert message_credit is not None
