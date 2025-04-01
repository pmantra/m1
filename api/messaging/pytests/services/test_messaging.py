import pytest

from authn.models.user import User
from messaging.models.messaging import Channel, Message
from messaging.services.messaging import (
    ChannelMetadata,
    ChannelMetadataStore,
    filter_channels,
    filter_channels_by_message_count,
    gather_metadata_for_channels,
    get_channel_ids_for_user,
    get_channel_metadata_for_channel_ids,
    get_channels_by_id,
    get_list_of_channel_ids_user_participates_in,
    get_message_metadata_for_channel_ids,
    sort_channels,
)
from pytests import factories
from pytests.freezegun import freeze_time


def make_channel(
    user: User,
    num_messages: int = 0,
) -> Channel:
    prac_1 = factories.PractitionerUserFactory.create()

    factories.MemberTrackFactory.create(user=user)

    channel = factories.ChannelFactory.create(
        name=f"{user.first_name}, {prac_1.first_name}"
    )

    cu_1 = factories.ChannelUsersFactory.create(
        channel_id=channel.id, user_id=user.id, is_initiator=False
    )
    cu_2 = factories.ChannelUsersFactory.create(
        channel_id=channel.id, user_id=prac_1.id, is_initiator=False
    )

    channel.participants = [cu_1, cu_2]

    for _ in range(num_messages):
        add_messages_to_channel(channel, user)

    return channel


def add_messages_to_channel(channel: Channel, from_user: User) -> Message:
    return factories.MessageFactory.create(channel_id=channel.id, user_id=from_user.id)


def test_get_list_of_channel_ids_user_participates_in():
    member = factories.MemberFactory.create()

    num_channels = 10
    channel_list = []

    channel_list = [make_channel(member) for _ in range(num_channels)]

    user_channel_ids = get_list_of_channel_ids_user_participates_in(user=member)
    assert len(user_channel_ids) == num_channels
    for channel in channel_list:
        assert channel.id in user_channel_ids


@freeze_time("2021-05-25 17:00:00")
def test_get_channel_metadata_for_channel_ids():
    member = factories.MemberFactory.create()

    num_channels = 10
    channel_list = [make_channel(member) for _ in range(num_channels)]

    channel_meta = get_channel_metadata_for_channel_ids(
        channel_ids=[channel.id for channel in channel_list]
    )
    assert len(channel_meta) == num_channels

    for meta in channel_meta:
        assert meta["channel_id"] in [channel.id for channel in channel_list]
        assert str(meta["created_at"]) == "2021-05-25 17:00:00"


@freeze_time("2021-05-25 17:00:00")
def test_get_message_metadata_for_channel_ids(db):
    member = factories.MemberFactory.create()

    c = make_channel(member)
    add_messages_to_channel(c, member)

    message_meta = get_message_metadata_for_channel_ids([c.id])
    assert len(message_meta) == 1
    meta = message_meta[0]

    assert meta["channel_id"] == c.id
    assert meta["message_count"] == 1
    assert str(meta["latest_message_timestamp"]) == "2021-05-25 17:00:00"


def test_channel_metadata_creation():
    with pytest.raises(ValueError):
        ChannelMetadata(channel_id=None)


def test_channel_metadata_defaults():
    cm = ChannelMetadata(channel_id=1)
    assert cm.channel_id == 1
    assert cm.created_at is None
    assert cm.message_count == 0
    assert cm.latest_message_timestamp is None


def test_channel_metadata_updates():
    cm = ChannelMetadata(channel_id=1)
    assert cm.created_at is None
    cm.update_properties(created_at="2021-05-25 17:00:00")
    assert str(cm.created_at) == "2021-05-25 17:00:00"

    cm.update_properties(message_count=123)
    assert cm.message_count == 123


def test_channel_metadata_store():
    member = factories.MemberFactory.create()

    c_1 = make_channel(user=member)
    c_2 = make_channel(user=member)

    cms = ChannelMetadataStore()

    cms.add_metadata(channel_id=c_1.id, message_count=1)
    cms.add_metadata(channel_id=c_2.id, message_count=2)

    assert len(cms.get_all()) == 2
    assert cms.get(c_1.id).channel_id == c_1.id
    assert cms.get(c_1.id).message_count == 1
    assert cms.get(c_2.id).channel_id == c_2.id
    assert cms.get(c_2.id).message_count == 2


def test_gather_metadata_for_channels_missing_channels():
    with pytest.raises(  # noqa  B017  TODO:  `assertRaises(Exception)` and `pytest.raises(Exception)` should be considered evil. They can lead to your test passing even if the code being tested is never executed due to a typo. Assert for a more specific exception (builtin or custom), or use `assertRaisesRegex` (if using `assertRaises`), or add the `match` keyword argument (if using `pytest.raises`), or use the context manager form with a target.
        Exception
    ):
        gather_metadata_for_channels([9999])


def test_gather_metadata_for_channels():
    member = factories.MemberFactory.create()
    with freeze_time("2021-05-25 17:00:00"):
        c = make_channel(member)

    with freeze_time("2021-05-25 18:00:00"):
        add_messages_to_channel(c, member)

    meta = gather_metadata_for_channels([c.id])

    assert len(meta.get_all()) == 1
    c_meta = meta.get(c.id)
    assert c_meta is not None
    assert str(c_meta.created_at) == "2021-05-25 17:00:00"
    assert c_meta.message_count == 1
    assert str(c_meta.latest_message_timestamp) == "2021-05-25 18:00:00"


@pytest.mark.parametrize(
    "min_count_of_messages_in_channel, expected_count",
    [
        (0, 2),
        (1, 1),
    ],
)
def test_filter_channels_by_message_count(
    min_count_of_messages_in_channel, expected_count
):
    member = factories.MemberFactory.create()

    c_1 = make_channel(member)
    c_2 = make_channel(member)
    add_messages_to_channel(c_2, member)

    meta = gather_metadata_for_channels([c_1.id, c_2.id])
    assert len(meta.get_all()) == 2

    filtered = filter_channels_by_message_count(
        channel_ids=[c_1.id, c_2.id],
        channel_metadata_store=meta,
        min_count_of_messages_in_channel=min_count_of_messages_in_channel,
    )
    assert len(filtered) == expected_count
    for c in [c_1, c_2]:
        if len(c.messages) >= min_count_of_messages_in_channel:
            assert c.id in filtered
        else:
            assert c.id not in filtered


def test_sort_channels_missing_metadata():
    member = factories.MemberFactory.create()

    # no errors for empty list
    meta = gather_metadata_for_channels([])
    sorted = sort_channels(
        channel_ids=[],
        channel_metadata_store=meta,
    )
    assert sorted == []

    with pytest.raises(ValueError):
        c_1 = make_channel(member)
        sort_channels(
            channel_ids=[c_1.id],
            channel_metadata_store=meta,
        )


def test_sort_channels_no_messages():
    member = factories.MemberFactory.create()
    with freeze_time("2021-05-25 17:00:00"):
        c_1 = make_channel(member)

    with freeze_time("2021-05-25 18:00:00"):
        c_2 = make_channel(member)

    with freeze_time("2021-05-25 19:00:00"):
        c_3 = make_channel(member)

    meta = gather_metadata_for_channels([c_1.id, c_2.id, c_3.id])

    sorted = sort_channels(
        channel_ids=[c_1.id, c_2.id, c_3.id],
        channel_metadata_store=meta,
    )

    assert len(sorted) == 3
    # expect most recently created channel to be first
    assert sorted[0] == c_3.id
    assert sorted[1] == c_2.id
    assert sorted[2] == c_1.id


def test_sort_channels_no_messages_asc():
    member = factories.MemberFactory.create()
    with freeze_time("2021-05-25 17:00:00"):
        c_1 = make_channel(member)

    with freeze_time("2021-05-25 18:00:00"):
        c_2 = make_channel(member)

    with freeze_time("2021-05-25 19:00:00"):
        c_3 = make_channel(member)

    meta = gather_metadata_for_channels([c_1.id, c_2.id, c_3.id])

    sorted = sort_channels(
        channel_ids=[c_1.id, c_2.id, c_3.id],
        channel_metadata_store=meta,
        sort_descending=False,
    )

    assert len(sorted) == 3
    # expect oldest chan to be first
    assert sorted[0] == c_1.id
    assert sorted[1] == c_2.id
    assert sorted[2] == c_3.id


def test_sort_channels_recent_messages():
    member = factories.MemberFactory.create()

    with freeze_time("2021-05-25 17:00:00"):
        # oldest channel but with most recent message
        c_1 = make_channel(member)

    with freeze_time("2021-05-25 18:00:00"):
        c_2 = make_channel(member)

    with freeze_time("2021-05-25 19:00:00"):
        c_3 = make_channel(member)

    with freeze_time("2021-05-25 20:00:00"):
        add_messages_to_channel(c_1, member)

    meta = gather_metadata_for_channels([c_1.id, c_2.id, c_3.id])

    sorted = sort_channels(
        channel_ids=[c_1.id, c_2.id, c_3.id],
        channel_metadata_store=meta,
    )

    assert len(sorted) == 3
    assert sorted[0] == c_1.id
    assert sorted[1] == c_3.id
    assert sorted[2] == c_2.id


def test_get_channels_for_user():
    member = factories.MemberFactory.create()
    other_member = factories.MemberFactory.create()

    user_chans = get_channel_ids_for_user(member)
    assert user_chans == []

    # ensure the new channel shows up on the expected user
    with freeze_time("2021-05-25 17:00:00"):
        c_1 = make_channel(other_member)
        assert [] == get_channel_ids_for_user(member)
        assert [c_1.id] == get_channel_ids_for_user(other_member)

    # now ensure the same chan can show up for both participants
    with freeze_time("2021-05-25 18:00:00"):
        c_2 = make_channel(member)
        cu_2 = factories.ChannelUsersFactory.create(
            channel_id=c_2.id, user_id=other_member.id, is_initiator=False
        )
        c_2.participants.append(cu_2)

    assert [c_2.id] == get_channel_ids_for_user(member)
    assert [c_2.id, c_1.id] == get_channel_ids_for_user(other_member)


def test_get_channels_by_id():
    member = factories.MemberFactory.create()
    num_channels = 10
    channel_list = []

    channel_list = [make_channel(member) for _ in range(num_channels)]
    channel_ids = [c.id for c in channel_list]

    chans = get_channels_by_id(channel_ids)
    assert len(chans) == num_channels
    for c in chans:
        assert isinstance(c, Channel)
        assert c.id in channel_ids


@pytest.mark.parametrize(
    "limit, offset",
    [
        (None, None),
        (5, 0),
        (5, 5),
        (2, 7),
    ],
)
def test_get_channels_by_id_limit_offset(limit, offset):
    member = factories.MemberFactory.create()
    num_channels = 10
    channel_list = []

    channel_list = [make_channel(member) for _ in range(num_channels)]
    channel_ids = [c.id for c in channel_list]
    expected_ids = []
    for i in range(limit or 10):
        expected_ids.append(channel_ids[(offset or 0) + i])

    chans = get_channels_by_id(
        channel_ids=channel_ids,
        limit=limit,
        offset=offset,
    )
    assert len(chans) == len(expected_ids)
    for c in chans:
        assert c.id in expected_ids


@pytest.mark.parametrize(
    [
        "include_no_messages",
        "num_channels",
        "num_messages_in_channel",
        "expected_count",
    ],
    [
        (True, 10, 1, 10),
        (True, 10, 0, 10),
        (False, 10, 0, 0),
        (False, 10, 1, 10),
    ],
)
def test_filter_channels_include_no_messages(
    include_no_messages,
    num_channels,
    num_messages_in_channel,
    expected_count,
):
    member = factories.MemberFactory.create()
    channel_list = [
        make_channel(member, num_messages=num_messages_in_channel)
        for _ in range(num_channels)
    ]

    result = filter_channels(
        channel_list,
        include_no_messages=include_no_messages,
    )

    assert len(result) == expected_count


@pytest.mark.parametrize(
    [
        "include_wallet",
        "expected_count",
    ],
    [
        (True, 1),
        (False, 0),
    ],
)
def test_filter_channels_include_wallet(
    include_wallet,
    expected_count,
    wallet_member_channel,
):
    _, channel = wallet_member_channel

    assert channel.is_wallet

    result = filter_channels(
        [channel],
        include_wallet=include_wallet,
    )

    assert len(result) == expected_count


def test_count_unread_channels_for_user(db):

    # Given
    member = factories.MemberFactory.create()

    # Create 2 channels for the member with different practitioners
    channel_1 = make_channel(member)
    channel_2 = make_channel(member)

    practitioner_1 = channel_1.practitioner
    practitioner_2 = channel_2.practitioner

    # Send messages to the channel from the practitioner that have yet to be read by the member
    add_messages_to_channel(channel_1, practitioner_1)
    add_messages_to_channel(channel_2, practitioner_2)

    # When/Then

    # assert that only the members return a count for unread messages in their channels
    assert Channel.count_unread_channels_for_user(member.id) == 2
    assert Channel.count_unread_channels_for_user(practitioner_1.id) == 0
    assert Channel.count_unread_channels_for_user(practitioner_2.id) == 0
