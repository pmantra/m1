from preferences import models


def test_get_user_with_preferences_that_user_set(
    client,
    api_helpers,
    created_member_preference: models.MemberPreference,
    created_preference: models.Preference,
):
    """
    WHEN:
        - A request is made to get all user preferences
    THEN:
        - Return a json object containing key/value pairs
          of the preference name and the user's value
    TEST:
        - That a 200 response is sent
        - That an object containing all of the user's
          set preferences is returned
    """

    res = client.get(
        f"/api/v1/users/{created_member_preference.member_id}/preferences",
        headers={"x-maven-user-id": created_member_preference.member_id},
    )
    assert res.status_code == 200
    data = api_helpers.load_json(res)
    assert created_preference.name in data
    assert data[created_preference.name] == "VALUE"


def test_get_user_with_preferences_that_user_did_not_set(
    default_user,
    client,
    api_helpers,
    created_preference: models.Preference,
):
    """
    WHEN:
        - A request is made to get all user preferences
    THEN:
        - Return a json object containing key/value pairs
          of the preference name and the user's value
    TEST:
        - That a 200 response is sent
        - That an object containing the default value for
          the preference
    """

    res = client.get(
        f"/api/v1/users/{default_user.id}/preferences",
        headers=api_helpers.standard_headers(default_user),
    )
    assert res.status_code == 200
    data = api_helpers.load_json(res)
    assert created_preference.name in data
    assert data[created_preference.name] == "DEFAULT"
