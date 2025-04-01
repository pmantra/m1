from __future__ import annotations

import datetime
import json

import pytest

from authn.models.user import User
from messaging.models.messaging import Channel, MessageProduct
from messaging.schemas.messaging import UserInChannelSchema
from messaging.services.messaging import (
    get_channel_metadata_for_channel_ids,
    get_channels_by_id,
    get_list_of_channel_ids_user_participates_in,
    get_message_metadata_for_channel_ids,
)

# from views.schemas.common import UserSchema
from models.profiles import CareTeamTypes
from pytests import factories
from pytests.db_util import enable_db_performance_warnings
from pytests.util import enable_serialization_attribute_errors


@pytest.fixture()
def make_channels():
    def _make_channels(
        num_channels: int = 10,
        requesting_user_factory=factories.MemberFactory,
        participant_factory=factories.PractitionerUserFactory,
    ) -> tuple[User, list[Channel]]:
        requesting_user = requesting_user_factory.create()
        now = datetime.datetime.utcnow()

        chans = []

        for i in range(num_channels):
            participant = participant_factory.create()

            org_1 = factories.OrganizationFactory.create(US_restricted=False)
            factories.MemberTrackFactory.create(
                user=requesting_user,
                client_track=factories.ClientTrackFactory.create(
                    organization=org_1,
                ),
            )

            channel = factories.ChannelFactory.create(
                name=f"{requesting_user.first_name}, {participant.first_name}",
                created_at=now + datetime.timedelta(minutes=i),
            )
            channel_user_member = factories.ChannelUsersFactory.create(
                channel_id=channel.id,
                user_id=requesting_user.id,
                channel=channel,
                user=requesting_user,
            )
            channel_user_prac = factories.ChannelUsersFactory.create(
                channel_id=channel.id,
                user_id=participant.id,
                channel=channel,
                user=participant,
            )
            channel.participants = [channel_user_member, channel_user_prac]
            factories.MessageFactory.create(
                channel_id=channel.id,
                user_id=requesting_user.id,
                created_at=now + datetime.timedelta(minutes=i),
            )

            chans.append(channel)
        return (requesting_user, chans)

    return _make_channels


@enable_serialization_attribute_errors()
def test_get_messages(make_channels, client, db, api_helpers):
    (requesting_user, chans) = make_channels(
        num_channels=1,
        requesting_user_factory=factories.MemberFactory,
        participant_factory=factories.PractitionerUserFactory,
    )

    with enable_db_performance_warnings(
        database=db,
        failure_threshold=15,
    ):
        res = client.get(
            f"/api/v1/channel/{chans[0].id}/messages",
            headers=api_helpers.json_headers(user=requesting_user),
        )
        assert res.status_code == 200
        resp = json.loads(res.data.decode("utf8"))
        assert len(resp["data"]) == 1


def test_get_channels(make_channels, client, db, api_helpers):
    num_channels = 1
    (member, _) = make_channels(num_channels=num_channels)

    with enable_db_performance_warnings(
        database=db,
        failure_threshold=28,
    ):
        res = client.get(
            "/api/v1/channels",
            headers=api_helpers.json_headers(user=member),
        )
        assert res.status_code == 200


# depending on the type of requesting user, schema field excludes can be different
# creating dramatically different performance profiles. this test should be used
# with test_get_channels to bring them into alignment,
def test_get_channels_for_practitioner(make_channels, client, db, api_helpers):
    num_channels = 1
    (requesting_user, _) = make_channels(
        num_channels=num_channels,
        requesting_user_factory=factories.PractitionerUserFactory,
        participant_factory=factories.MemberFactory,
    )

    with enable_db_performance_warnings(
        database=db,
        failure_threshold=30,
    ):
        res = client.get(
            "/api/v1/channels",
            headers=api_helpers.json_headers(user=requesting_user),
        )
        assert res.status_code == 200


def test_db_calls_during_serialization_UserInChannelSchema(db):
    m = factories.MemberFactory.create()
    cc_1 = factories.PractitionerUserFactory.create()

    # care_coordinators on a user were each being serialized using the
    # UserSchema which contained many unnecessary fields. This user property
    # is not used by any client for display so we should avoid the cost of
    # serializing it.
    m.add_practitioner_to_care_team(cc_1.id, CareTeamTypes.CARE_COORDINATOR)

    with enable_db_performance_warnings(
        database=db,
        failure_threshold=12,
    ):
        schema_out = UserInChannelSchema()
        schema_out.context["include_profile"] = True
        schema_out.context["user"] = m
        schema_out.dump(m).data


def test_get_list_of_channel_ids_user_participates_in(db, make_channels):
    num_channels = 10
    (requesting_user, _) = make_channels(
        num_channels=num_channels,
        requesting_user_factory=factories.MemberFactory,
        participant_factory=factories.PractitionerUserFactory,
    )

    with enable_db_performance_warnings(
        database=db,
        failure_threshold=2,
    ):
        user_channel_ids = get_list_of_channel_ids_user_participates_in(
            user=requesting_user
        )
        assert len(user_channel_ids) == num_channels


def test_get_channel_metadata_for_channel_ids(db, make_channels):
    num_channels = 10
    (_, channel_list) = make_channels(
        num_channels=num_channels,
        requesting_user_factory=factories.MemberFactory,
        participant_factory=factories.PractitionerUserFactory,
    )

    with enable_db_performance_warnings(
        database=db,
        failure_threshold=2,
    ):
        channel_meta = get_channel_metadata_for_channel_ids(
            channel_ids=[channel.id for channel in channel_list]
        )
        assert len(channel_meta) == num_channels


def test_get_message_metadata_for_channel_ids(db, make_channels):
    (_, channel_list) = make_channels(
        num_channels=1,
        requesting_user_factory=factories.MemberFactory,
        participant_factory=factories.PractitionerUserFactory,
    )

    with enable_db_performance_warnings(
        database=db,
        failure_threshold=2,
    ):
        message_meta = get_message_metadata_for_channel_ids([channel_list[0].id])
        assert len(message_meta) == 1


@pytest.mark.parametrize(
    "limit, offset",
    [
        (None, None),
        (5, 0),
        (5, 5),
        (2, 7),
    ],
)
def test_get_channels_by_id_limit_offset(limit, offset, db, make_channels):
    num_channels = 10

    (_, channel_list) = make_channels(
        num_channels=num_channels,
        requesting_user_factory=factories.MemberFactory,
        participant_factory=factories.PractitionerUserFactory,
    )

    channel_ids = [c.id for c in channel_list]
    expected_ids = []
    for i in range(limit or 10):
        expected_ids.append(channel_ids[(offset or 0) + i])

    with enable_db_performance_warnings(
        database=db,
        failure_threshold=3,
    ):
        chans = get_channels_by_id(
            channel_ids=channel_ids,
            limit=limit,
            offset=offset,
        )
        assert len(chans) == len(expected_ids)


def test_post_message_billing(client, api_helpers, db, factories):
    member = factories.DefaultUserFactory()
    product = MessageProduct(number_of_messages=3, price=1)
    db.session.add(product)
    db.session.commit()
    factories.CreditFactory.create(
        amount=10,
        user=member,
    )
    with enable_db_performance_warnings(
        database=db,
        failure_threshold=12,
    ):
        res = client.post(
            "/api/v1/message/billing",
            data=api_helpers.json_data({"product_id": product.id}),
            headers=api_helpers.json_headers(member),
        )
        assert res.status_code == 201
        data = api_helpers.load_json(res)
        assert data["available_messages"] == product.number_of_messages
