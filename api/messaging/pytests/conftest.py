import datetime

import pytest

from appointments.models.payments import Credit
from messaging.models.messaging import Channel, MessageCredit
from messaging.schemas.messaging import ChannelSchema, MessageSchema
from messaging.schemas.messaging_v3 import ChannelSchemaV3, MessageSchemaV3
from pytests.factories import EnterpriseUserFactory
from pytests.util import enable_serialization_attribute_errors
from storage.connection import db
from utils.flag_groups import CARE_DELIVERY_RELEASE
from wallet.models.constants import WalletState
from wallet.services.reimbursement_wallet_messaging import get_or_create_rwu_channel


@pytest.fixture
def enable_set_user_need_if_solving_ticket_ff_on(ff_test_data):
    ff_test_data.update(
        ff_test_data.flag("enable-set-user-need-if-solving-ticket").value_for_all(True)
    )


@pytest.fixture
def enable_set_user_need_if_solving_ticket_ff_off(ff_test_data):
    ff_test_data.update(
        ff_test_data.flag("enable-set-user-need-if-solving-ticket").value_for_all(False)
    )


@pytest.fixture
def maven_to_zendesk_reconciliation_ff_on(ff_test_data):
    ff_test_data.update(
        ff_test_data.flag(
            CARE_DELIVERY_RELEASE.ENABLE_MAVEN_TO_ZENDESK_RECONCILIATION_JOB
        ).value_for_all(True)
    )


@pytest.fixture
def maven_to_zendesk_reconciliation_ff_off(ff_test_data):
    ff_test_data.update(
        ff_test_data.flag(
            CARE_DELIVERY_RELEASE.ENABLE_MAVEN_TO_ZENDESK_RECONCILIATION_JOB
        ).value_for_all(False)
    )


@pytest.fixture()
def message_channel(factories):
    member = factories.EnterpriseUserFactory.create()
    practitioner = factories.PractitionerUserFactory.create()
    return Channel.get_or_create_channel(practitioner, [member])


@pytest.fixture()
def message_member_practitioner_channel(factories):
    member = factories.MemberFactory.create()
    practitioner = factories.PractitionerUserFactory.create()
    channel = Channel.get_or_create_channel(practitioner, [member])
    return member, practitioner, channel


@pytest.fixture()
def wallet_member_channel(factories):
    member = EnterpriseUserFactory.create()
    member.organization_employee.json = {"wallet_enabled": True}
    member.organization.name = "Test Org"
    resource = factories.ResourceFactory()
    reimbursement_organization_settings = (
        factories.ReimbursementOrganizationSettingsFactory(
            organization_id=member.organization.id,
            benefit_faq_resource_id=resource.id,
            survey_url="fake_url",
        )
    )
    wallet = factories.ReimbursementWalletFactory.create(
        user_id=member.id,
        reimbursement_organization_settings_id=reimbursement_organization_settings.id,
        state=WalletState.QUALIFIED,
    )
    reimbursement_wallet_user = factories.ReimbursementWalletUsersFactory.create(
        reimbursement_wallet_id=wallet.id,
        user_id=member.id,
    )
    channel = get_or_create_rwu_channel(reimbursement_wallet_user)

    return member, channel


@pytest.fixture()
def message_channel_with_credits(message_channel):
    credit = Credit(user_id=message_channel.member.id, amount=10)
    message_credit = MessageCredit(user_id=message_channel.member.id)
    db.session.add(credit)
    db.session.add(message_credit)
    db.session.commit()
    return message_channel


@pytest.fixture()
def now(factories):
    now = datetime.datetime.utcnow()
    return now


@pytest.fixture()
def one_hour_ago(now, factories):
    return now - datetime.timedelta(hours=1)


@pytest.fixture()
def two_hours_ago(now, factories):
    return now - datetime.timedelta(hours=2)


@pytest.fixture()
def three_hours_ago(now, factories):
    return now - datetime.timedelta(hours=3)


@pytest.fixture()
def now_message(now, message_channel, factories):
    return factories.MessageFactory(
        created_at=now,
        modified_at=now,
        channel_id=message_channel.id,
    )


@pytest.fixture()
def one_hour_ago_message(one_hour_ago, message_channel, factories):
    return factories.MessageFactory(
        created_at=one_hour_ago,
        modified_at=one_hour_ago,
        channel_id=message_channel.id,
    )


@pytest.fixture()
def two_hours_ago_message(two_hours_ago, message_channel, factories):
    return factories.MessageFactory(
        created_at=two_hours_ago,
        modified_at=two_hours_ago,
        channel_id=message_channel.id,
    )


@pytest.fixture()
def three_hours_ago_message(three_hours_ago, message_channel, factories):
    return factories.MessageFactory(
        created_at=three_hours_ago,
        modified_at=three_hours_ago,
        channel_id=message_channel.id,
    )


@pytest.fixture()
def two_days_ago_message(now, message_channel, factories):
    return factories.MessageFactory(
        created_at=now - datetime.timedelta(days=2),
        modified_at=three_hours_ago,
        channel_id=message_channel.id,
    )


@pytest.fixture(scope="function", autouse=True)
def enable_marshmallow_v1_serialization_exceptions():
    with enable_serialization_attribute_errors():
        yield


@pytest.fixture()
def v1_and_v3_message_schema(factories):
    return MessageSchema(), MessageSchemaV3()


@pytest.fixture()
def v1_and_v3_channel_schema(factories):
    return ChannelSchema(), ChannelSchemaV3()
