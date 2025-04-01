from unittest.mock import Mock, patch

from authn.models.user import User
from health.tasks import update_health_profile_in_braze


def test_update_health_profile_in_braze_success():
    user_id = 123
    mock_user = Mock(spec=User)

    with patch("health.tasks.health_profile.get_user") as mock_get_user, patch(
        "health.tasks.health_profile.braze"
    ) as mock_braze:
        mock_get_user.return_value = mock_user

        update_health_profile_in_braze(user_id)

        mock_get_user.assert_called_once_with(user_id)
        mock_braze.update_health_profile.assert_called_once_with(mock_user)

        actual_arg = mock_braze.update_health_profile.call_args[0][0]
        assert isinstance(
            actual_arg, User
        ), "Argument passed to update_health_profile must be a User instance"
