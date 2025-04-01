import datetime
from unittest import mock
from unittest.mock import ANY, patch

import pytest

from messaging.models.messaging import Channel, Message
from models.verticals_and_specialties import (
    BIRTH_PLANNING_VERTICAL_NAME,
    CX_VERTICAL_NAME,
)
from payments.models.constants import PROVIDER_CONTRACTS_EMAIL
from payments.models.practitioner_contract import ContractType
from payments.pytests.factories import PractitionerContractFactory


@pytest.fixture()
def practitioner_profile(factories):
    practitioner = factories.PractitionerUserFactory()
    return practitioner.practitioner_profile


@pytest.fixture()
def inactive_contract(practitioner_profile):
    inactive_contract = PractitionerContractFactory.create(
        practitioner=practitioner_profile,
        start_date=datetime.date.today() - datetime.timedelta(days=5),
        end_date=datetime.date.today() - datetime.timedelta(days=2),
    )
    return inactive_contract


@pytest.fixture()
def active_contract(practitioner_profile):
    active_contract = PractitionerContractFactory.create(
        practitioner=practitioner_profile,
        start_date=datetime.date.today() - datetime.timedelta(days=5),
        end_date=datetime.date.today() + datetime.timedelta(days=2),
    )
    return active_contract


class TestMessageRequiresFee:
    @mock.patch(
        "messaging.models.messaging.Channel.practitioner",
        new_callable=mock.PropertyMock,
    )
    def test_requires_fee__practitioner_is_care_coordinator(
        self,
        mock_channel_practitioner,
        factories,
        message_channel,
    ):
        # Given a message where the practitioner is a CA
        message = Message(channel_id=message_channel.id, user=message_channel.member)

        cx_vertical = factories.VerticalFactory(name=CX_VERTICAL_NAME)
        practitioner = factories.PractitionerUserFactory(
            practitioner_profile__verticals=[cx_vertical]
        )
        mock_channel_practitioner.return_value = practitioner
        message.channel = message_channel

        # Then, message does not requires fee
        assert message.requires_fee is False

    @pytest.mark.parametrize(
        argnames="practitioner_contract, is_staff_value",
        argvalues=[
            (None, False),
            (None, True),
            ("inactive_contract", False),
            ("inactive_contract", True),
        ],
    )
    @patch("messaging.models.messaging.send_message")
    def test_requires_fee__practitioner_has_no_contracts_or_only_an_inactive_contract(
        self,
        mock_send_message,
        practitioner_contract,
        is_staff_value,
        message_channel,
        request,
        factories,
    ):
        # Given a practitioner that has no contracts or only an inactive one, and a given is_staff_value
        message = Message(channel_id=message_channel.id, user=message_channel.member)
        message.channel = message_channel
        prac_profile = message.channel.practitioner.practitioner_profile
        birth_planning_vertical = factories.VerticalFactory(
            name=BIRTH_PLANNING_VERTICAL_NAME
        )
        prac_profile.verticals = [birth_planning_vertical]
        prac_profile.is_staff = is_staff_value

        # Restore values from fixture
        practitioner_contract = (
            request.getfixturevalue(practitioner_contract)
            if practitioner_contract
            else None
        )

        if practitioner_contract:
            # Associate the contract with the same practitioner from the message
            practitioner_contract.practitioner = prac_profile

        # When calling requires_fee
        message_requires_fee = message.requires_fee

        # Then, warning is sent to provider ops because they do not have an active contract
        mock_send_message.assert_called_with(
            to_email=PROVIDER_CONTRACTS_EMAIL,
            subject="Provider has no active contract",
            text=ANY,
            internal_alert=True,
            production_only=True,
        )
        # And we fall back to using is_staff: assert that requires_fee is opposite to is_staff value
        assert message_requires_fee != prac_profile.is_staff

    def test_requires_fee__practitioner_active_contract_emits_fee(
        self, active_contract, message_channel, factories
    ):
        # Given a practitioner with a contract that emits fee
        message = Message(channel_id=message_channel.id, user=message_channel.member)
        message.channel = message_channel
        prac_profile = message.channel.practitioner.practitioner_profile
        birth_planning_vertical = factories.VerticalFactory(
            name=BIRTH_PLANNING_VERTICAL_NAME
        )
        prac_profile.verticals = [birth_planning_vertical]
        prac_profile.is_staff = False
        active_contract.contract_type = ContractType.BY_APPOINTMENT

        # Associate the contract with the same practitioner from the message
        active_contract.practitioner = prac_profile

        # When calling requires_fee
        message_requires_fee = message.requires_fee

        # Then we should emit fee
        assert message_requires_fee

    @pytest.mark.parametrize(
        argnames="contract_type",
        argvalues=[
            ContractType.W2,
            ContractType.HYBRID_1_0,
            ContractType.HYBRID_2_0,
            ContractType.FIXED_HOURLY,
            ContractType.FIXED_HOURLY_OVERNIGHT,
            ContractType.NON_STANDARD_BY_APPOINTMENT,
        ],
    )
    def test_requires_fee__practitioner_active_contract_does_not_emits_fee(
        self, contract_type, active_contract, message_channel, factories
    ):
        # Given a practitioner with a contract that does not emits fee
        message = Message(channel_id=message_channel.id, user=message_channel.member)
        message.channel = message_channel
        prac_profile = message.channel.practitioner.practitioner_profile
        birth_planning_vertical = factories.VerticalFactory(
            name=BIRTH_PLANNING_VERTICAL_NAME
        )
        prac_profile.verticals = [birth_planning_vertical]
        prac_profile.is_staff = True
        active_contract.contract_type = contract_type

        # Associate the contract with the same practitioner from the message
        active_contract.practitioner = prac_profile

        # When calling requires_fee
        message_requires_fee = message.requires_fee

        # Then we should not emit fee
        assert not message_requires_fee

    @pytest.mark.parametrize(
        argnames="is_staff_value, contract_type",
        argvalues=[
            (True, ContractType.BY_APPOINTMENT),
            (False, ContractType.W2),
            (False, ContractType.HYBRID_1_0),
            (False, ContractType.HYBRID_2_0),
            (False, ContractType.FIXED_HOURLY),
            (False, ContractType.FIXED_HOURLY_OVERNIGHT),
            (False, ContractType.NON_STANDARD_BY_APPOINTMENT),
        ],
    )
    @patch("messaging.models.messaging.send_message")
    def test_requires_fee__practitioner_active_contract_emits_fee_conflicts_with_is_staff(
        self,
        mock_send_message,
        contract_type,
        is_staff_value,
        active_contract,
        message_channel,
        factories,
    ):
        # Given a practitioner with a contract type that conflicts with their is_staff value
        message = Message(channel_id=message_channel.id, user=message_channel.member)
        message.channel = message_channel
        prac_profile = message.channel.practitioner.practitioner_profile
        birth_planning_vertical = factories.VerticalFactory(
            name=BIRTH_PLANNING_VERTICAL_NAME
        )
        prac_profile.verticals = [birth_planning_vertical]
        prac_profile.is_staff = is_staff_value
        active_contract.contract_type = contract_type

        # Associate the contract with the same practitioner from the message
        active_contract.practitioner = prac_profile

        # When calling requires_fee
        message_requires_fee = message.requires_fee

        # Then, warning is sent to provider ops because the active contract conflicts with is_staff value
        mock_send_message.assert_called_with(
            to_email=PROVIDER_CONTRACTS_EMAIL,
            subject="Provider active contract inconsistent with is_staff value",
            text=ANY,
            internal_alert=True,
            production_only=True,
        )

        # And we fallback to using is_staff: assert that requires_fee is opposite to is_staff value
        assert message_requires_fee != prac_profile.is_staff


class TestChannel:
    def test_get_or_create_channel_with_missing_first_names(self, factories):
        member = factories.MemberFactory.create()
        practitioner = factories.PractitionerUserFactory.create()

        practitioner.first_name = None
        practitioner.last_name = None
        member.first_name = None
        member.last_name = None

        # ensure channel can be created without exception
        c = Channel.get_or_create_channel(practitioner, [member])
        assert c.name == ""

    def test_practitioner_property__channel_with_practitioner(self, factories):

        # Given a channel with practitioner
        member = factories.MemberFactory.create()
        practitioner = factories.PractitionerUserFactory.create()
        channel = Channel.get_or_create_channel(practitioner, [member])

        # When we call the practitioner property
        retrieved_practitioner = channel.practitioner

        # Then we get the appropiate practitioner
        assert practitioner == retrieved_practitioner

    def test_practitioner_property__channel_with_no_practitioner(self, factories):

        # Given a channel with no practitioner

        channel = factories.ChannelFactory()

        # When we call the practitioner property
        retrieved_practitioner = channel.practitioner

        # Then we get no practitioner
        assert retrieved_practitioner is None


class TestMessage:
    def test_message_user_with_id(self, factories):
        member = factories.MemberFactory.create()
        practitioner = factories.PractitionerUserFactory.create()

        c = Channel.get_or_create_channel(practitioner, [member])
        msg = factories.MessageFactory.create(channel_id=c.id, user_id=member.id)
        msg_user_member = factories.MessageUsersFactory.create(
            message_id=msg.id, user_id=member.id
        )
        msg_user_prac = factories.MessageUsersFactory.create(
            message_id=msg.id, user_id=practitioner.id
        )

        assert len(msg.message_users) == 2

        assert msg.message_user_with_id(member.id) == msg_user_member
        assert msg.message_user_with_id(practitioner.id) == msg_user_prac
