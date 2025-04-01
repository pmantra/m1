from unittest import mock

import pytest

from tasks.users import user_post_creation


@pytest.mark.parametrize("should_enable_zendesk_user_profile_creation", [True, False])
@pytest.mark.parametrize("has_phone_number", [True, False])
@mock.patch("tasks.users.should_enable_zendesk_user_profile_creation")
@mock.patch("messaging.services.zendesk_client.ZendeskClient.create_or_update_user")
def test_user_post_creation(
    mock_zendesk_create_or_update_user,
    mock_should_enable_zendesk_user_profile_creation,
    has_phone_number,
    should_enable_zendesk_user_profile_creation,
    factories,
):
    # Given

    # a new User profile
    user = factories.MemberFactory.create()
    if has_phone_number:
        user.member_profile.phone_number = "+17733220000"

    # a Zendesk user
    zd_user = factories.DefaultUserFactory.create()

    mock_zendesk_create_or_update_user.return_value = zd_user
    mock_should_enable_zendesk_user_profile_creation.return_value = (
        should_enable_zendesk_user_profile_creation
    )

    # When
    user_post_creation(user_id=user.id)

    # Then
    assert user.zendesk_user_id == user.zendesk_user_id
    mock_zendesk_create_or_update_user.assert_called_once_with(
        user,
        called_by="Not set",
    ) if should_enable_zendesk_user_profile_creation else mock_zendesk_create_or_update_user.assert_not_called()
