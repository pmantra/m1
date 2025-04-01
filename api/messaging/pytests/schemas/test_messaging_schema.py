from __future__ import annotations

from unittest import mock

import pytest

from authn.models.user import User
from messaging.models.messaging import Channel
from messaging.schemas.messaging import (
    MESSAGE_REPLY_SLA_USER_MESSAGE_CA_DEFAULT,
    MESSAGE_REPLY_SLA_USER_MESSAGE_PROVIDER_DEFAULT,
    MESSAGE_REPLY_SLA_USER_MESSAGE_WALLET,
    MESSAGE_REPLY_SLA_USER_MESSAGE_WALLET_WITH_INBOUND_PHONE_NUMBER,
    ChannelSchema,
    MessageSchema,
    add_maven_wallet_author,
)
from messaging.schemas.messaging_v3 import MemberTrackInChannelSchemaV3
from models.enterprise import InboundPhoneNumber
from storage.connection import db
from wallet.models.constants import WalletState, WalletUserStatus, WalletUserType


def test_ChannelSchema_cannot_accept_messages_with_no_participants(factories):
    chan = factories.ChannelFactory()
    schema = ChannelSchema()
    dumped = schema.dump(chan).data
    assert not dumped["can_accept_messages"]


def test_ChannelSchema_cannot_accept_messages_with_one_participant_and_no_wallet(
    factories,
):
    user = factories.MemberFactory.create()
    channel = factories.ChannelFactory.create()
    factories.ChannelUsersFactory.create(
        channel_id=channel.id, user_id=user.id, is_initiator=False
    )

    schema = ChannelSchema()
    dumped = schema.dump(channel).data
    assert dumped["can_accept_messages"] is False


def test_ChannelSchema_can_accept_messages_with_one_participant_and_wallet(
    factories,
):
    user = factories.MemberFactory.create()
    channel = factories.ChannelFactory.create()
    factories.ChannelUsersFactory.create(
        channel_id=channel.id, user_id=user.id, is_initiator=False
    )

    resource = factories.ResourceFactory(id=5)
    reimbursement_organization_settings = (
        factories.ReimbursementOrganizationSettingsFactory(
            id=6,
            organization_id=1,
            benefit_faq_resource_id=resource.id,
            survey_url="fake_url",
        )
    )
    wallet = factories.ReimbursementWalletFactory.create(
        id=1,
        user_id=user.id,  # Delete after user_id is dropped
        reimbursement_organization_settings_id=reimbursement_organization_settings.id,
    )
    factories.ReimbursementWalletUsersFactory.create(
        user_id=user.id,
        reimbursement_wallet_id=wallet.id,
        status=WalletUserStatus.ACTIVE,
        type=WalletUserType.DEPENDENT,
        channel_id=channel.id,
    )

    schema = ChannelSchema()
    dumped = schema.dump(channel).data
    assert dumped["can_accept_messages"] is True


def test_ChannelSchema_cannot_accept_messages_when_practitioner_not_active(
    factories,
):
    user = factories.MemberFactory.create()
    practitioner = factories.PractitionerUserFactory.create()
    practitioner.practitioner_profile.active = False

    channel = factories.ChannelFactory.create()
    factories.ChannelUsersFactory.create(
        channel_id=channel.id, user_id=user.id, is_initiator=False
    )
    factories.ChannelUsersFactory.create(
        channel_id=channel.id, user_id=practitioner.id, is_initiator=False
    )

    schema = ChannelSchema()
    dumped = schema.dump(channel).data
    assert dumped["can_accept_messages"] is False


def test_ChannelSchema_cannot_accept_messages_when_practitioner_disabled_messaging(
    factories,
):
    user = factories.MemberFactory.create()
    practitioner = factories.PractitionerUserFactory.create()
    practitioner.practitioner_profile.messaging_enabled = False

    channel = factories.ChannelFactory.create()
    factories.ChannelUsersFactory.create(
        channel_id=channel.id, user_id=user.id, is_initiator=False
    )
    factories.ChannelUsersFactory.create(
        channel_id=channel.id, user_id=practitioner.id, is_initiator=False
    )

    schema = ChannelSchema()
    dumped = schema.dump(channel).data
    assert dumped["can_accept_messages"] is False


def test_ChannelSchema_can_accept_messages_with_member_and_practitioner(
    factories,
):
    user = factories.MemberFactory.create()
    practitioner = factories.PractitionerUserFactory.create()
    channel = factories.ChannelFactory.create()

    channel = factories.ChannelFactory.create()
    factories.ChannelUsersFactory.create(
        channel_id=channel.id, user_id=user.id, is_initiator=False
    )
    factories.ChannelUsersFactory.create(
        channel_id=channel.id, user_id=practitioner.id, is_initiator=False
    )

    schema = ChannelSchema()
    dumped = schema.dump(channel).data
    assert dumped["can_accept_messages"] is True


@pytest.mark.parametrize(
    "is_ca, is_wallet, has_inbound_phone_number, expected",
    [
        (True, None, None, MESSAGE_REPLY_SLA_USER_MESSAGE_CA_DEFAULT),
        (False, None, None, MESSAGE_REPLY_SLA_USER_MESSAGE_PROVIDER_DEFAULT),
        (True, False, None, MESSAGE_REPLY_SLA_USER_MESSAGE_CA_DEFAULT),
        (False, True, False, MESSAGE_REPLY_SLA_USER_MESSAGE_WALLET),
        (
            False,
            True,
            True,
            MESSAGE_REPLY_SLA_USER_MESSAGE_WALLET_WITH_INBOUND_PHONE_NUMBER,
        ),
    ],
)
@mock.patch("phone_support.service.phone_support.should_include_inbound_phone_number")
def test_ChannelSchema_reply_sla_user_message(
    mock_should_include_inbound_phone_number,
    is_ca,
    is_wallet,
    has_inbound_phone_number,
    expected,
    wallet_member_channel,
    factories,
):
    mock_should_include_inbound_phone_number.return_value = has_inbound_phone_number

    member = factories.EnterpriseUserFactory.create()
    if is_ca:
        ca_vertical = factories.VerticalFactory.create(name="Care Advocate")
        # assign verticals to make 'is_cx' return true to signify that this user is a CA
        practitioner = factories.PractitionerUserFactory.create(
            practitioner_profile__verticals=[ca_vertical]
        )
        channel = Channel.get_or_create_channel(practitioner, [member])
    elif is_wallet:
        member, channel = wallet_member_channel
    else:
        channel = factories.ChannelFactory.create()

    db_phone_number = InboundPhoneNumber(
        id=1, number="5703024100", organizations=[member.organization]
    )
    db.session.add(db_phone_number)
    db.session.commit()

    with mock.patch.object(
        channel,
        "is_wallet",
        is_wallet,
    ):
        schema = ChannelSchema()
        dumped = schema.dump(channel).data
        # Need to add inbound phone number to the expected string
        if expected == MESSAGE_REPLY_SLA_USER_MESSAGE_WALLET_WITH_INBOUND_PHONE_NUMBER:
            expected = expected.format(phone_number="+1-570-302-4100")
        assert dumped["reply_sla_user_message"] == expected


def test_ChannelSchema_active_tracks_for_member(factories):
    member: User = factories.EnterpriseUserFactory.create()
    practitioner: User = factories.PractitionerUserFactory.create()
    channel = factories.ChannelFactory.create()
    factories.ChannelUsersFactory.create(channel_id=channel.id, user_id=member.id)
    factories.ChannelUsersFactory.create(channel_id=channel.id, user_id=practitioner.id)
    schema = ChannelSchema()

    dumped = schema.dump(channel).data

    for participant in dumped["participants"]:
        user = participant["user"]
        if user["id"] == member.id:
            assert user["active_tracks"] == [
                MemberTrackInChannelSchemaV3().dump(active_track)
                for active_track in member.active_tracks
            ]
        else:
            assert user["active_tracks"] == []


def test_MessageSchema_add_maven_wallet_author(
    factories,
):
    user = factories.MemberFactory.create()
    channel = factories.ChannelFactory.create()
    factories.ChannelUsersFactory.create(
        channel_id=channel.id,
        user_id=user.id,
    )

    resource = factories.ResourceFactory(id=5)
    reimbursement_organization_settings = (
        factories.ReimbursementOrganizationSettingsFactory(
            id=6,
            organization_id=1,
            benefit_faq_resource_id=resource.id,
            survey_url="fake_url",
        )
    )

    wallet = factories.ReimbursementWalletFactory.create(
        state=WalletState.QUALIFIED,
        user_id=user.id,
        reimbursement_organization_settings_id=reimbursement_organization_settings.id,
    )
    factories.ReimbursementWalletUsersFactory.create(
        user_id=user.id,
        channel_id=channel.id,
        reimbursement_wallet_id=wallet.id,
    )

    wallet_message = factories.MessageFactory.create(
        channel_id=channel.id,
    )
    user_message = factories.MessageFactory.create(
        channel_id=channel.id,
        user_id=user.id,
    )

    # below we are asserting that given a channel with messages from a user and
    # from maven wallet, the message author is only over written for the wallet
    # message and not for the user message.
    schema = MessageSchema(many=True)
    data = [{}, {}]
    messages = [wallet_message, user_message]
    results = add_maven_wallet_author(schema, data, messages)
    assert len(results) == 2

    new_author_for_wallet_message = results[0].get("author")
    new_author_for_user_message = results[1].get("author")

    # assert the add_maven_wallet_author data handler did not attempt to
    # override the author field of the user message
    assert new_author_for_user_message is None
    assert new_author_for_wallet_message is not None
    assert new_author_for_wallet_message.get("full_name") == "Maven Wallet"
