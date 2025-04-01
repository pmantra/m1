import pytest

from preferences.utils import member_communications


def test_get_opted_in_email_communications_preference(
    mock_preference_service_with_preference,
):
    """
    When:
        The preference exists
    Then:
        It is returned
    Test that:
        - No new preference is created
    """
    preference = member_communications.get_opted_in_email_communications_preference()

    assert preference

    mock_preference_service_with_preference.create.assert_not_called()


def test_get_opted_in_email_communications_preference_creates_preference(
    mock_preference_service_without_preference,
):
    """
    When:
        The preference does not exist
    Then:
        It is created and returned
    Test that:
        - New preference is created
    """
    preference = member_communications.get_opted_in_email_communications_preference()

    assert preference

    mock_preference_service_without_preference.create.assert_called_once()


def test_set_member_communications_preference_creates_preference(
    default_user,
    preference,
    mock_preference_service_with_preference,
    mock_member_preference_service_without_preference,
):
    """
    When:
        The member preference does not exist
    Then:
        It is created
    Test that:
        - New member preference is created
    """
    member_communications.set_member_communications_preference(default_user.id, True)

    mock_member_preference_service_without_preference.get_by_preference_name.assert_called_once_with(
        member_id=default_user.id, preference_name=preference.name
    )
    mock_member_preference_service_without_preference.create.assert_called_once_with(
        member_id=default_user.id, preference_id=preference.id, value=str(True)
    )


def test_set_member_communications_preference_updates_preference(
    default_user,
    mock_preference_service_with_preference,
    mock_member_preference_service_with_true_preference,
    member_preference_true,
):
    """
    When:
        The member preference exists with a different value
    Then:
        It is updated
    Test that:
        - Member preference is updated
    """
    member_communications.set_member_communications_preference(default_user.id, False)

    mock_member_preference_service_with_true_preference.update_value.assert_called_once_with(
        id=member_preference_true.id, value=str(False)
    )


def test_set_member_communications_preference_does_not_update_preference(
    default_user,
    mock_preference_service_with_preference,
    mock_member_preference_service_with_true_preference,
    member_preference_true,
):
    """
    When:
        The member preference exists with the same value
    Then:
        It is not updated
    Test that:
        - Member preference is not updated
    """
    member_communications.set_member_communications_preference(default_user.id, True)

    mock_member_preference_service_with_true_preference.update_value.assert_not_called()


@pytest.mark.parametrize("preference_value", [True, False])
def test_get_member_communications_preference(
    default_user, factories, preference_value
):
    factories.MemberProfileFactory.create(
        user_id=default_user.id,
    )
    member_communications.set_member_communications_preference(
        default_user.id, preference_value
    )
    expected = member_communications.get_member_communications_preference(
        default_user.id
    )
    assert expected is preference_value
