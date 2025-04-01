from unittest import mock

from zenpy.lib.api_objects import User as ZDUser

from scripts.zendesk_user_profile import (
    create_missing_zendesk_user_profile,
    update_zendesk_user_profile,
)


@mock.patch("scripts.zendesk_user_profile.log.info")
@mock.patch("messaging.services.zendesk_client.ZendeskClient.create_or_update_user")
def test_create_missing_zendesk_user_profile(
    mock_zendesk_create_or_update_user, mock_info_log, factories
):
    # Given

    # create members

    user_1 = factories.DefaultUserFactory.create()
    factories.MemberProfileFactory.create(
        user_id=user_1.id,
    )

    user_2 = factories.DefaultUserFactory.create()
    factories.MemberProfileFactory.create(
        user_id=user_2.id,
    )

    user_3 = factories.DefaultUserFactory.create()
    factories.MemberProfileFactory.create(
        user_id=user_3.id,
    )

    # user created before 2023, will be filtered out
    user_4 = factories.DefaultUserFactory.create(
        created_at="2010-11-29 19:18:41.000000"
    )
    factories.MemberProfileFactory.create(
        user_id=user_4.id, created_at="2010-11-29 19:18:41.000000"
    )

    # assert `zendesk_user_id` does not exist for these users
    assert user_1.zendesk_user_id is None
    assert user_2.zendesk_user_id is None
    assert user_3.zendesk_user_id is None
    assert user_4.zendesk_user_id is None

    # create new Zendesk User objects
    zendesk_user_1 = ZDUser(id=1)
    zendesk_user_2 = ZDUser(id=2)
    zendesk_user_3 = ZDUser(id=3)

    # mock the Zendesk API call to create a new Zendesk User Profile
    mock_zendesk_create_or_update_user.side_effect = [
        zendesk_user_1,
        zendesk_user_2,
        zendesk_user_3,
    ]

    # When

    # call script to create Zendesk Use profiles
    create_missing_zendesk_user_profile(batch_size=2, dry_run=False)

    # assert the `zendesk_user_id` field now exists on the User objects
    assert user_1.zendesk_user_id == zendesk_user_1.id
    assert user_2.zendesk_user_id == zendesk_user_2.id
    assert user_3.zendesk_user_id == zendesk_user_3.id

    mock_info_log.assert_called_with(
        "Retroactively created Zendesk User Profile for users",
        user_ids_to_zendesk_user_ids={
            user_1.id: user_1.zendesk_user_id,
            user_2.id: user_2.zendesk_user_id,
            user_3.id: user_3.zendesk_user_id,
        },
        user_ids_failed=[],
        user_ids_aborted=[],
    )


@mock.patch("scripts.zendesk_user_profile.log.info")
@mock.patch("messaging.services.zendesk_client.ZendeskClient.update_user")
@mock.patch("messaging.services.zendesk_client.ZendeskClient.update_primary_identity")
@mock.patch("messaging.services.zendesk_client.ZendeskClient.get_zendesk_user")
def test_update_zendesk_user_profile(
    mock_get_zendesk_user,
    mock_zendesk_update_primary_identity,
    mock_update_user,
    mock_info_log,
    factories,
):
    # Given

    # create members with populated `zendesk_user_id` fields

    user_1 = factories.DefaultUserFactory.create(zendesk_user_id=1)
    factories.MemberProfileFactory.create(
        user_id=user_1.id,
    )

    user_2 = factories.DefaultUserFactory.create(zendesk_user_id=2)
    factories.MemberProfileFactory.create(
        user_id=user_2.id,
    )

    user_3 = factories.DefaultUserFactory.create(zendesk_user_id=3)
    factories.MemberProfileFactory.create(
        user_id=user_3.id,
    )

    # create new Zendesk User objects
    zendesk_user_1 = ZDUser(id=1)
    zendesk_user_2 = ZDUser(id=2)
    zendesk_user_3 = ZDUser(id=3)

    mock_get_zendesk_user.side_effect = [zendesk_user_1, zendesk_user_2, zendesk_user_3]

    # When

    # call script to create Zendesk Use profiles
    update_zendesk_user_profile(batch_size=1)

    # Then

    # assert we updated the zendesk profile 3 times
    assert mock_update_user.call_count == 3

    mock_info_log.assert_called_with(
        "Retroactively updated the phone number on the Zendesk User Profile for users",
        user_ids_to_zendesk_user_ids={
            user_1.id: user_1.zendesk_user_id,
            user_2.id: user_2.zendesk_user_id,
            user_3.id: user_3.zendesk_user_id,
        },
        user_ids_failed=[],
    )
