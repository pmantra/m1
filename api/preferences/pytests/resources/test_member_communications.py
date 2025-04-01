from unittest import mock

from authn.models.user import User
from storage.connection import db


@mock.patch("braze.client.utils.feature_flags.bool_variation")
def test_unsubscribe(
    mock_bool_variation,
    default_user,
    client,
    api_helpers,
    mock_preference_service_with_preference,
    mock_member_preference_service_with_true_preference,
):
    """
    When:
        A member exists
    Then:
        The member calls unsubscribe endpoint
    Test that:
        - The response returns a 200 status code
        - The braze job to trigger the unsubscribe request is called
        - The member preference is updated
    """
    mock_bool_variation.return_value = True
    with mock.patch(
        "tasks.braze.unsubscribe_from_member_communications.delay"
    ) as mock_unsubscribe:
        res = client.post(
            f"/api/v1/users/{default_user.id}/member_communications/unsubscribe",
            headers=api_helpers.json_headers(default_user),
        )

        assert res.status_code == 200
        mock_unsubscribe.assert_called_once()
        mock_member_preference_service_with_true_preference.update_value.assert_called_once()

    mock_bool_variation.return_value = False
    with mock.patch(
        "tasks.braze.unsubscribe_from_member_communications.delay"
    ) as mock_unsubscribe:
        res = client.post(
            f"/api/v1/users/{default_user.id}/member_communications/unsubscribe",
            headers=api_helpers.json_headers(default_user),
        )

        assert res.status_code == 200
        mock_unsubscribe.assert_not_called()


@mock.patch("braze.client.utils.feature_flags.bool_variation")
def test_unsubscribe_user_not_found(
    mock_bool_variation, default_user, client, api_helpers
):
    """
    When:
        A member exists
    Then:
        A different user ID is used in the endpoint that does not match the authenticated user
    Test that:
        - The response returns a 404 status code
        - The braze job to trigger the unsubscribe request is not called
    """
    mock_bool_variation.return_value = True
    with mock.patch(
        "preferences.resources.member_communications.unsubscribe_from_member_communications.delay"
    ) as mock_unsubscribe:
        non_existent_user_id = (
            db.session.query(User.id).order_by(User.id.desc()).first()[0] + 1
        )

        res = client.post(
            f"/api/v1/users/{non_existent_user_id}/member_communications/unsubscribe",
            headers=api_helpers.json_headers(default_user),
        )

        assert res.status_code == 404
        mock_unsubscribe.assert_not_called()


@mock.patch("braze.client.utils.feature_flags.bool_variation")
def test_opt_in(
    mock_bool_variation,
    default_user,
    client,
    api_helpers,
    mock_preference_service_with_preference,
    mock_member_preference_service_with_false_preference,
):
    """
    When:
        A member exists
    Then:
        The member calls opt-in endpoint
    Test that:
        - The response returns a 200 status code
        - The braze job to trigger the opt-in request is called
        - The member preference is updated
    """
    mock_bool_variation.return_value = True
    with mock.patch(
        "preferences.resources.member_communications.opt_into_member_communications.delay"
    ) as mock_opt_in:
        res = client.post(
            f"/api/v1/users/{default_user.id}/member_communications/opt_in",
            headers=api_helpers.json_headers(default_user),
        )

        assert res.status_code == 200
        mock_opt_in.assert_called_once()
        mock_member_preference_service_with_false_preference.update_value.assert_called_once()

    mock_bool_variation.return_value = False
    with mock.patch(
        "preferences.resources.member_communications.opt_into_member_communications.delay"
    ) as mock_opt_in:
        res = client.post(
            f"/api/v1/users/{default_user.id}/member_communications/opt_in",
            headers=api_helpers.json_headers(default_user),
        )

        assert res.status_code == 200
        mock_opt_in.assert_not_called()


@mock.patch("braze.client.utils.feature_flags.bool_variation")
def test_opt_in_user_not_found(mock_bool_variation, default_user, client, api_helpers):
    """
    When:
        A member exists
    Then:
        A different user ID is used in the endpoint that does not match the authenticated user
    Test that:
        - The response returns a 404 status code
        - The braze job to trigger the opt-in request is not called
    """
    mock_bool_variation.return_value = True
    with mock.patch(
        "preferences.resources.member_communications.opt_into_member_communications.delay"
    ) as mock_opt_in:
        non_existent_user_id = (
            db.session.query(User.id).order_by(User.id.desc()).first()[0] + 1
        )

        res = client.post(
            f"/api/v1/users/{non_existent_user_id}/member_communications/opt_in",
            headers=api_helpers.json_headers(default_user),
        )

        assert res.status_code == 404
        mock_opt_in.assert_not_called()


@mock.patch("braze.client.utils.feature_flags.bool_variation")
def test_member_communications_unsubscribe(
    mock_bool_variation,
    default_user,
    client,
    api_helpers,
    mock_preference_service_with_preference,
    mock_member_preference_service_with_true_preference,
):
    """
    When:
        A member exists
    Then:
        The member calls unsubscribe endpoint
    Test that:
        - The response returns a 200 status code
        - The braze job to trigger the unsubscribe request is called
        - The member preference is updated
    """
    mock_bool_variation.return_value = True
    with mock.patch(
        "preferences.resources.member_communications.unsubscribe_from_member_communications.delay"
    ) as mock_unsubscribe:
        res = client.post(
            f"/api/v1/users/{default_user.id}/member_communications",
            headers=api_helpers.json_headers(default_user),
            data=api_helpers.json_data({"opted_in": False}),
        )

        assert res.status_code == 200
        mock_unsubscribe.assert_called_once()
        mock_member_preference_service_with_true_preference.update_value.assert_called_once()

    mock_bool_variation.return_value = False
    with mock.patch(
        "preferences.resources.member_communications.unsubscribe_from_member_communications.delay"
    ) as mock_unsubscribe:
        res = client.post(
            f"/api/v1/users/{default_user.id}/member_communications",
            headers=api_helpers.json_headers(default_user),
            data=api_helpers.json_data({"opted_in": False}),
        )

        assert res.status_code == 200
        mock_unsubscribe.assert_not_called()


@mock.patch("braze.client.utils.feature_flags.bool_variation")
def test_member_communications_unsubscribe_user_not_found(
    mock_bool_variation, default_user, client, api_helpers
):
    """
    When:
        A member exists
    Then:
        A different user ID is used in the endpoint that does not match the authenticated user
    Test that:
        - The response returns a 404 status code
        - The braze job to trigger the unsubscribe request is not called
    """
    mock_bool_variation.return_value = True
    with mock.patch(
        "preferences.resources.member_communications.unsubscribe_from_member_communications.delay"
    ) as mock_unsubscribe:
        non_existent_user_id = (
            db.session.query(User.id).order_by(User.id.desc()).first()[0] + 1
        )

        res = client.post(
            f"/api/v1/users/{non_existent_user_id}/member_communications",
            headers=api_helpers.json_headers(default_user),
            data=api_helpers.json_data({"opted_in": False}),
        )

        assert res.status_code == 404
        mock_unsubscribe.assert_not_called()


@mock.patch("braze.client.utils.feature_flags.bool_variation")
def test_member_communications_opt_in(
    mock_bool_variation,
    default_user,
    client,
    api_helpers,
    mock_preference_service_with_preference,
    mock_member_preference_service_with_false_preference,
):
    """
    When:
        A member exists
    Then:
        The member calls opt-in endpoint
    Test that:
        - The response returns a 200 status code
        - The braze job to trigger the opt-in request is called
        - The member preference is updated
    """
    mock_bool_variation.return_value = True
    with mock.patch(
        "preferences.resources.member_communications.opt_into_member_communications.delay"
    ) as mock_opt_in:
        res = client.post(
            f"/api/v1/users/{default_user.id}/member_communications",
            headers=api_helpers.json_headers(default_user),
            data=api_helpers.json_data({"opted_in": True}),
        )

        assert res.status_code == 200
        mock_opt_in.assert_called_once()
        mock_member_preference_service_with_false_preference.update_value.assert_called_once()

    mock_bool_variation.return_value = False
    with mock.patch(
        "preferences.resources.member_communications.opt_into_member_communications.delay"
    ) as mock_opt_in:
        res = client.post(
            f"/api/v1/users/{default_user.id}/member_communications",
            headers=api_helpers.json_headers(default_user),
            data=api_helpers.json_data({"opted_in": True}),
        )

        assert res.status_code == 200
        mock_opt_in.assert_not_called()


@mock.patch("braze.client.utils.feature_flags.bool_variation")
def test_member_communications_opt_in_user_not_found(
    mock_bool_variation,
    default_user,
    client,
    api_helpers,
    mock_member_preferences_service,
):
    """
    When:
        A member exists
    Then:
        A different user ID is used in the endpoint that does not match the authenticated user
    Test that:
        - The response returns a 404 status code
        - The braze job to trigger the opt-in request is not called
        - A member preference is not created or updated
    """
    mock_bool_variation.return_value = True
    with mock.patch(
        "preferences.resources.member_communications.opt_into_member_communications.delay"
    ) as mock_opt_in:
        non_existent_user_id = (
            db.session.query(User.id).order_by(User.id.desc()).first()[0] + 1
        )

        res = client.post(
            f"/api/v1/users/{non_existent_user_id}/member_communications",
            headers=api_helpers.json_headers(default_user),
            data=api_helpers.json_data({"opted_in": True}),
        )

        assert res.status_code == 404
        mock_opt_in.assert_not_called()
        mock_member_preferences_service.create.assert_not_called()
        mock_member_preferences_service.update_value.assert_not_called()


@mock.patch("braze.client.utils.feature_flags.bool_variation")
def test_member_communications_with_empty_json_body(
    mock_bool_variation,
    default_user,
    client,
    api_helpers,
    mock_member_preferences_service,
):
    """
    When:
        A member exists
    Then:
        The member calls member_communications endpoint with an empty JSON body
    Test that:
        - The response returns a 400 status code
        - The braze job to trigger the unsubscribe request is not called
        - The braze job to trigger the opt-in request is not called
        - A member preference is not created or updated
    """
    mock_bool_variation.return_value = True
    with mock.patch(
        "preferences.resources.member_communications.unsubscribe_from_member_communications.delay"
    ) as mock_unsubscribe, mock.patch(
        "preferences.resources.member_communications.opt_into_member_communications.delay"
    ) as mock_opt_in:
        res = client.post(
            f"/api/v1/users/{default_user.id}/member_communications",
            headers=api_helpers.json_headers(default_user),
            data=api_helpers.json_data({}),
        )

        assert res.status_code == 400
        mock_unsubscribe.assert_not_called()
        mock_opt_in.assert_not_called()
        mock_member_preferences_service.create.assert_not_called()
        mock_member_preferences_service.update_value.assert_not_called()


@mock.patch("braze.client.utils.feature_flags.bool_variation")
def test_member_communications_with_no_content(
    mock_bool_variation,
    default_user,
    client,
    api_helpers,
    mock_member_preferences_service,
):
    """
    When:
        A member exists
    Then:
        The member calls member_communications endpoint with no `Content-Type` header
    Test that:
        - The response returns a 400 status code
        - The braze job to trigger the unsubscribe request is not called
        - The braze job to trigger the opt-in request is not called
        - A member preference is not created or updated
    """
    mock_bool_variation.return_value = True
    with mock.patch(
        "preferences.resources.member_communications.unsubscribe_from_member_communications.delay"
    ) as mock_unsubscribe, mock.patch(
        "preferences.resources.member_communications.opt_into_member_communications.delay"
    ) as mock_opt_in:
        res = client.post(
            f"/api/v1/users/{default_user.id}/member_communications",
            headers=api_helpers.standard_headers(default_user),
        )

        # flask version >2.1.3 behavior
        # 415 Unsupported Media Type if no request.is_json check
        # keep the existing behavior with the check
        assert res.status_code == 400
        mock_unsubscribe.assert_not_called()
        mock_opt_in.assert_not_called()
        mock_member_preferences_service.create.assert_not_called()
        mock_member_preferences_service.update_value.assert_not_called()
