from unittest.mock import patch

from messaging.models.messaging import Channel, Message


def test_channel_privilege_type(factories):
    practitioner = factories.PractitionerUserFactory.create()
    member = factories.MemberFactory.create()

    chan = Channel.get_or_create_channel(practitioner, [member])

    assert chan.privilege_type == "anonymous"
    assert chan.practitioner == practitioner
    assert chan.member == member


@patch("services.common.feature_flags.bool_variation")
def test_channel_privilege_type_scope_of_practice(mock_bool_variation, factories):
    mock_bool_variation.return_value = True
    practitioner = factories.PractitionerUserFactory.create()
    member = factories.MemberFactory.create()

    chan = Channel.get_or_create_channel(practitioner, [member])

    assert chan.privilege_type == "education_only"
    assert chan.practitioner == practitioner
    assert chan.member == member


def test_channel_messages(factories, db):
    practitioner = factories.PractitionerUserFactory.create()
    member = factories.MemberFactory.create()

    chan = Channel.get_or_create_channel(practitioner, [member])

    for ix in range(5):
        m = Message(
            user_id=practitioner.id,
            channel_id=chan.id,
            body=f"message {ix + 1}",
            status=True,
            zendesk_comment_id=ix + 1,
            braze_campaign_id="foo",
            user=practitioner,
        )
        db.session.add(m)

    db.session.commit()
    db.session.flush()

    chan = Channel.query.get(chan.id)
    assert chan.first_message.body == "message 1"
    assert chan.last_message.body == "message 5"
