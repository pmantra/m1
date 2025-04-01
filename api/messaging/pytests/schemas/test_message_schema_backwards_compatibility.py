from unittest import mock

from messaging.models.messaging import Channel
from messaging.schemas.messaging import (
    MESSAGE_REPLY_SLA_USER_MESSAGE_CA_DEFAULT,
    MESSAGE_REPLY_SLA_USER_MESSAGE_PROVIDER_DEFAULT,
    MESSAGE_REPLY_SLA_USER_MESSAGE_WALLET,
    MESSAGE_REPLY_SLA_USER_MESSAGE_WALLET_WITH_INBOUND_PHONE_NUMBER,
    _get_reimbursements_bot_user_information,
    _get_request_availability_bot_user_information,
    add_maven_wallet_participant,
)
from messaging.schemas.messaging_v3 import (
    _get_reimbursements_bot_user_information_v3,
    _get_request_availability_bot_user_information_v3,
)
from models.enterprise import InboundPhoneNumber
from pytests import factories
from storage.connection import db
from views.schemas.base import UserSchemaV3
from views.schemas.common import UserSchema


def test_get_author__user_schema(
    message_member_practitioner_channel, v1_and_v3_message_schema
):
    # Given: enterprise user and message
    member, practitioner, channel = message_member_practitioner_channel
    message = factories.MessageFactory.create(channel_id=channel.id, user_id=member.id)
    v1_schema, v3_schema = v1_and_v3_message_schema

    # When: we get_author on both schemas
    v1_response = v1_schema.get_author(message, {}, UserSchema)
    v3_response = v3_schema.get_author(message, UserSchemaV3)

    # Then responses should be the same
    assert v1_response == v3_response


def test_get_wallet_id(wallet_member_channel, v1_and_v3_channel_schema):
    # Given: enterprise user and wallet channel
    member, channel = wallet_member_channel
    v1_schema, v3_schema = v1_and_v3_channel_schema

    # When: we get_wallet_id on both schemas
    v1_response = v1_schema.get_wallet_id(channel, {})
    v3_response = v3_schema.get_wallet_id(channel)

    # Then: responses should be the same
    assert v1_response is not None
    assert v3_response is not None
    assert v1_response == v3_response


def test_get_total_messages(
    message_member_practitioner_channel, v1_and_v3_channel_schema
):
    # Given: enterprise user and channel with 2 messages
    member, practitioner, channel = message_member_practitioner_channel
    factories.MessageFactory.create(channel_id=channel.id, user_id=member.id)
    factories.MessageFactory.create(channel_id=channel.id, user_id=member.id)

    v1_schema, v3_schema = v1_and_v3_channel_schema

    # When: we get_new_messages on both schemas
    v1_response = v1_schema.get_total_messages(channel, {})
    v3_response = v3_schema.get_total_messages(channel)

    # then: responses should be the same
    assert v1_response == 2
    assert v3_response == 2
    assert v1_response == v3_response


def test_get_can_accept_messages(message_channel, v1_and_v3_channel_schema):
    # Given: regular channels
    channel = message_channel
    v1_schema, v3_schema = v1_and_v3_channel_schema

    # When: we get_can_accept_messages
    v1_response = v1_schema.get_can_accept_messages(channel, {})
    v3_response = v3_schema.get_can_accept_messages(channel)

    # Then: schema responses should be the same
    assert v1_response == v3_response
    assert v1_response


def test_get_can_accept_messages__wallet(
    wallet_member_channel, v1_and_v3_channel_schema
):
    # Given: wallet channel
    _, wallet_channel = wallet_member_channel
    v1_schema, v3_schema = v1_and_v3_channel_schema

    # When: we get_can_accept_messages on all schemas
    v1_response_wallet = v1_schema.get_can_accept_messages(wallet_channel, {})
    v3_response_wallet = v3_schema.get_can_accept_messages(wallet_channel)

    # Then: schema responses should be the same
    assert v1_response_wallet == v3_response_wallet
    assert v1_response_wallet


def test_get_can_accept_messages__one_member(message_channel, v1_and_v3_channel_schema):
    # Given: regular channels with one participant
    channel = message_channel
    channel.participants.pop()
    v1_schema, v3_schema = v1_and_v3_channel_schema

    # When: we get_can_accept_messages on all schemas
    v1_response = v1_schema.get_can_accept_messages(channel, {})
    v3_response = v3_schema.get_can_accept_messages(channel)

    # Then: schema responses should be the same
    assert v1_response == v3_response
    assert v1_response is False


def test_get_reply_sla_user_message__ca_regular_channel(
    v1_and_v3_channel_schema,
):
    # Given: regular chanel with a CA provider
    member = factories.MemberFactory.create()
    ca_vertical = factories.VerticalFactory.create(name="Care Advocate")
    practitioner = factories.PractitionerUserFactory.create(
        practitioner_profile__verticals=[ca_vertical]
    )
    channel = Channel.get_or_create_channel(practitioner, [member])

    v1_schema, v3_schema = v1_and_v3_channel_schema

    # When: we get_wallet_id on schema
    v1_response = v1_schema.get_reply_sla_user_message(channel, {})
    v3_response = v3_schema.get_reply_sla_user_message(channel)

    # Then: schema responses should be the same
    assert v1_response == v3_response

    # the SLA response is for CAs
    assert v1_response == MESSAGE_REPLY_SLA_USER_MESSAGE_CA_DEFAULT


def test_get_reply_sla_user_message__non_ca_regular_channel(
    v1_and_v3_channel_schema,
):
    # Given: regular chanel with a non-ca provider
    non_ca_vertical = factories.VerticalFactory.create(
        name="Wellness Coach",
        pluralized_display_name="Wellness Coaches",
        can_prescribe=False,
        filter_by_state=False,
    )
    member = factories.MemberFactory.create()
    practitioner = factories.PractitionerUserFactory.create(
        practitioner_profile__verticals=[non_ca_vertical]
    )
    channel = Channel.get_or_create_channel(practitioner, [member])

    v1_schema, v3_schema = v1_and_v3_channel_schema

    # When: we get_wallet_id on schema
    v1_response = v1_schema.get_reply_sla_user_message(channel, {})
    v3_response = v3_schema.get_reply_sla_user_message(channel)

    # Then: schema responses should be the same
    assert v1_response == v3_response

    # the SLA response is for non_CAs
    assert v1_response == MESSAGE_REPLY_SLA_USER_MESSAGE_PROVIDER_DEFAULT


def test_get_reply_sla_user_message__wallet_channel(
    wallet_member_channel,
    v1_and_v3_channel_schema,
):
    # Given: wallet channel without phone number
    _, wallet_channel = wallet_member_channel
    v1_schema, v3_schema = v1_and_v3_channel_schema

    # When: we get_wallet_id on schema
    v1_response_wallet = v1_schema.get_reply_sla_user_message(wallet_channel, {})
    v3_response_wallet = v3_schema.get_reply_sla_user_message(wallet_channel)

    # Then: schema responses should be the same
    assert v1_response_wallet == v3_response_wallet
    assert v1_response_wallet == MESSAGE_REPLY_SLA_USER_MESSAGE_WALLET


@mock.patch("phone_support.service.phone_support.should_include_inbound_phone_number")
def test_get_reply_sla_user_message__wallet_channel_with_phone(
    mock_should_include_inbound_phone_number,
    wallet_member_channel,
    v1_and_v3_channel_schema,
):
    # Given: wallet channel with phone number
    user, wallet_channel = wallet_member_channel
    mock_should_include_inbound_phone_number.return_value = True
    db_phone_number = InboundPhoneNumber(
        id=1, number="5703024100", organizations=[user.organization]
    )
    db.session.add(db_phone_number)
    db.session.commit()
    v1_schema, v3_schema = v1_and_v3_channel_schema

    # When: we get_wallet_id on schema
    v1_response_wallet = v1_schema.get_reply_sla_user_message(wallet_channel, {})
    v3_response_wallet = v3_schema.get_reply_sla_user_message(wallet_channel)

    # Then: schema responses should be the same
    assert v1_response_wallet == v3_response_wallet
    assert (
        v1_response_wallet
        == MESSAGE_REPLY_SLA_USER_MESSAGE_WALLET_WITH_INBOUND_PHONE_NUMBER.format(
            phone_number="+1-570-302-4100"
        )
    )


@mock.patch("views.schemas.common.should_enable_can_member_interact")
def test_add_maven_wallet_participant(
    mock_should_enable_can_member_interact,
    wallet_member_channel,
    message_member_practitioner_channel,
    v1_and_v3_channel_schema,
):
    # Given channels schema V1 and V3, one wallet one regular channel
    mock_should_enable_can_member_interact.return_value = True

    v1_schema, v3_schema = v1_and_v3_channel_schema
    # create wallet channel
    member, wallet_channel = wallet_member_channel
    # create non-wallet channel
    member, _, channel = message_member_practitioner_channel

    # when add_maven_wallet_participants
    v1_response_wallet = add_maven_wallet_participant(
        v1_schema,
        {"participants": [], "name": wallet_channel.name, "id": wallet_channel.id},
        wallet_channel,
    )
    v3_response_wallet = v3_schema.add_maven_wallet_participant(
        {"participants": [], "name": wallet_channel.name, "id": wallet_channel.id}
    )
    v1_response = add_maven_wallet_participant(
        v1_schema, {"participants": [], "name": channel.name, "id": channel.id}, channel
    )
    v3_response = v3_schema.add_maven_wallet_participant(
        {"participants": [], "name": channel.name, "id": channel.id}
    )

    # Then: v1 and v2 response should be the same
    assert v1_response_wallet == v3_response_wallet
    assert len(v1_response_wallet["participants"]) == 1
    assert v1_response == v3_response
    # should not add participants if it's not a wallet channel
    assert len(v1_response["participants"]) == 0


# TODO after rollout write tests to ensure the v3 stubs stay in line with nested schemas
def test_get_request_availability_bot():
    v1 = _get_request_availability_bot_user_information()
    v3 = _get_request_availability_bot_user_information_v3()
    assert v1 == v3


def test_get_reimbursement_bot():
    v1 = _get_reimbursements_bot_user_information()
    v3 = _get_reimbursements_bot_user_information_v3()

    assert v1 == v3
