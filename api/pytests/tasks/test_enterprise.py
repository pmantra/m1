from unittest.mock import patch

from tasks.enterprise import enterprise_user_post_setup


# with patch("utils.braze._braze_request") as mock_request:
@patch("tasks.enterprise.braze.send_incentives_allowed")
@patch("tasks.enterprise.braze.track_user")
def test_enterprise_user_post_setup(
    mock_braze_track_user, mock_braze_send_incentives_allowed, factories
):

    # Given
    user = factories.EnterpriseUserFactory()
    user.organization.welcome_box_allowed = True
    user.organization.gift_card_allowed = True

    # When
    enterprise_user_post_setup(user.id)

    # Then
    mock_braze_track_user.assert_called_once_with(user)
    mock_braze_send_incentives_allowed.assert_called_once_with(
        external_id=user.esp_id, welcome_box_allowed=True, gift_card_allowed=True
    )
