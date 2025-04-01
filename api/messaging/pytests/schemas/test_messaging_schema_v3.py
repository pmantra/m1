from __future__ import annotations

from unittest import mock

import pytest

from messaging.models.messaging import Channel
from messaging.schemas.messaging import (
    MESSAGE_REPLY_SLA_USER_MESSAGE_CA_DEFAULT,
    MESSAGE_REPLY_SLA_USER_MESSAGE_PROVIDER_DEFAULT,
    MESSAGE_REPLY_SLA_USER_MESSAGE_WALLET_WITH_INBOUND_PHONE_NUMBER,
)
from messaging.schemas.messaging_v3 import (
    MESSAGE_REPLY_SLA_USER_MESSAGE_WALLET,
    ChannelSchemaV3,
)
from models.enterprise import InboundPhoneNumber
from storage.connection import db


def test_ChannelSchema_cannot_accept_messages_with_no_participants(factories):
    # Given: channel without participants and channel v3 schema
    chan = factories.ChannelFactory()
    schema = ChannelSchemaV3()
    # when: we dump
    dumped = schema.dump(chan)
    # then: we can't accept messages
    assert not dumped["can_accept_messages"]


def test_ChannelSchema_cannot_accept_messages_with_one_participant_and_no_wallet(
    factories,
):
    # Given: channel with one participant, v3 channel schema
    user = factories.MemberFactory.create()
    channel = factories.ChannelFactory.create()
    factories.ChannelUsersFactory.create(
        channel_id=channel.id, user_id=user.id, is_initiator=False
    )

    schema = ChannelSchemaV3()
    # when: we dump
    dumped = schema.dump(channel)
    # then: we can't accept messages
    assert dumped["can_accept_messages"] is False


def test_ChannelSchema_can_accept_messages_with_one_participant_and_wallet(
    wallet_member_channel,
):
    # Given: wallet channel with one participant, v3 channel schema
    _, channel = wallet_member_channel

    # when: we dump
    schema = ChannelSchemaV3()
    dumped = schema.dump(channel)
    # then: we can accept messages
    assert dumped["can_accept_messages"] is True


def test_ChannelSchema_cannot_accept_messages_when_practitioner_not_active(
    message_member_practitioner_channel,
):
    # given: channel with member and practitioner, practitioner not active
    user, practitioner, channel = message_member_practitioner_channel
    practitioner.practitioner_profile.active = False

    schema = ChannelSchemaV3()
    # when: we dump
    dumped = schema.dump(channel)
    # then: we can't accept messages
    assert dumped["can_accept_messages"] is False


def test_ChannelSchema_cannot_accept_messages_when_practitioner_disabled_messaging(
    message_member_practitioner_channel,
):
    # given: channel with member and practitioner, practitioner messaging disabled
    user, practitioner, channel = message_member_practitioner_channel
    practitioner.practitioner_profile.messaging_enabled = False

    # when: we dump
    schema = ChannelSchemaV3()
    dumped = schema.dump(channel)
    # then: we can't accept messages
    assert dumped["can_accept_messages"] is False


def test_ChannelSchema_can_accept_messages_with_member_and_practitioner(
    message_member_practitioner_channel,
):
    # given: channel with member and practitioner
    user, practitioner, channel = message_member_practitioner_channel  # when: we dump
    schema = ChannelSchemaV3()
    dumped = schema.dump(channel)
    # then: we can accept messages
    assert dumped["can_accept_messages"] is True


@pytest.mark.parametrize(
    "is_ca, expected",
    [
        (True, MESSAGE_REPLY_SLA_USER_MESSAGE_CA_DEFAULT),
        (
            False,
            MESSAGE_REPLY_SLA_USER_MESSAGE_PROVIDER_DEFAULT,
        ),  # non-CA provider SLA
    ],
)
def test_ChannelSchema_response_sla_user_message(
    is_ca,
    expected,
    factories,
):
    # given: non-wallet channel
    member = factories.EnterpriseUserFactory.create()
    if is_ca:
        # assign verticals to make 'is_cx' return true to signify that this user is a CA
        vertical = factories.VerticalFactory.create(name="Care Advocate")

    else:
        vertical = factories.VerticalFactory.create(name="OB-GYN")

    practitioner = factories.PractitionerUserFactory.create(
        practitioner_profile__verticals=[vertical]
    )
    channel = Channel.get_or_create_channel(practitioner, [member])
    # when: we dump
    schema = ChannelSchemaV3()
    dumped = schema.dump(channel)

    # then: the SLA matches the requirement from the channel
    assert dumped["reply_sla_user_message"] == expected


@pytest.mark.parametrize(
    "has_inbound_phone_number",
    [True, False],
)
@mock.patch("phone_support.service.phone_support.should_include_inbound_phone_number")
def test_ChannelSchema_response_sla_user_message__wallet(
    mock_should_include_inbound_phone_number,
    has_inbound_phone_number,
    wallet_member_channel,
):
    # given: wallet channel
    member, channel = wallet_member_channel
    mock_should_include_inbound_phone_number.return_value = has_inbound_phone_number
    db_phone_number = InboundPhoneNumber(
        id=1, number="5703024100", organizations=[member.organization]
    )
    db.session.add(db_phone_number)
    db.session.commit()

    # when: we dump
    schema = ChannelSchemaV3()
    dumped = schema.dump(channel)
    # Need to add inbound phone number to the expected string
    expected = MESSAGE_REPLY_SLA_USER_MESSAGE_WALLET
    if has_inbound_phone_number:
        expected = (
            MESSAGE_REPLY_SLA_USER_MESSAGE_WALLET_WITH_INBOUND_PHONE_NUMBER.format(
                phone_number="+1-570-302-4100"
            )
        )

    # then: the SLA matches the requirement from the channel
    assert dumped["reply_sla_user_message"] == expected
