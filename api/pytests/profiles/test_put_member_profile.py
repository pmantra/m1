def test_update_country(factories, default_user, api_helpers, client):
    """
    When:
        - The member profile does not have a country_code
    Then:
        - The PUT request is made with a country
    Test that:
        - The response has a 200 status code
        - The member profile's country_code is set
    """
    profile = factories.MemberProfileFactory.create(user=default_user)

    assert profile.country_code is None

    res = client.put(
        f"/api/v1/users/{default_user.id}/profiles/member",
        headers=api_helpers.standard_headers(default_user),
        json={"country": "US"},
    )

    assert res.status_code == 200
    assert profile.country_code == "US"


def test_update_state_existing_country_code(
    factories, default_user, api_helpers, client
):
    """
    When:
        - The member profile has a country_code
        - The member profile does not have a subdivision_code
        - The member profile does not have a state
    Then:
        - The PUT request is made with a state, but not a country
    Test that:
        - The response has a 200 status code
        - The member profile's country_code remains the same
        - The member profile's subdivision_code is set
        - The member profile's state is set
    """
    profile = factories.MemberProfileFactory.create(
        user=default_user, state=None, country_code="US"
    )
    state = factories.StateFactory.create(abbreviation="NY")

    assert profile.country_code == "US"
    assert profile.subdivision_code is None
    assert profile.state is None

    res = client.put(
        f"/api/v1/users/{default_user.id}/profiles/member",
        headers=api_helpers.standard_headers(default_user),
        json={"state": "NY"},
    )

    assert res.status_code == 200
    assert profile.country_code == "US"
    assert profile.subdivision_code == "US-NY"
    assert profile.state == state


def test_update_country_and_state(factories, default_user, api_helpers, client):
    """
    When:
        - The member profile does not have a country_code
        - The member profile does not have a subdivision_code
        - The member profile does not have a state
    Then:
        - The PUT request is made with a country and a state
    Test that:
        - The response has a 200 status code
        - The member profile's country_code is set
        - The member profile's subdivision_code is set
        - The member profile's state is set
    """
    profile = factories.MemberProfileFactory.create(user=default_user)
    state = factories.StateFactory.create(abbreviation="NY")

    assert profile.country_code is None
    assert profile.subdivision_code is None
    assert profile.state is None

    res = client.put(
        f"/api/v1/users/{default_user.id}/profiles/member",
        headers=api_helpers.standard_headers(default_user),
        json={"country": "US", "state": "NY"},
    )

    assert res.status_code == 200
    assert profile.country_code == "US"
    assert profile.subdivision_code == "US-NY"
    assert profile.state == state


def test_update_state_no_country(factories, default_user, api_helpers, client):
    """
    When:
        - The member profile does not have a country_code
        - The member profile does not have a subdivision_code
        - The member profile does not have a state
    Then:
        - The PUT request is made with a state, but not a country
    Test that:
        - The response has a 200 status code
        - The member profile's country_code is set
        - The member profile's subdivision_code is set
        - The member profile's state is set
    """
    profile = factories.MemberProfileFactory.create(user=default_user)
    state = factories.StateFactory.create(abbreviation="NY")

    assert profile.country_code is None
    assert profile.subdivision_code is None
    assert profile.state is None

    res = client.put(
        f"/api/v1/users/{default_user.id}/profiles/member",
        headers=api_helpers.standard_headers(default_user),
        json={"state": "NY"},
    )

    assert res.status_code == 200
    assert profile.country_code == "US"
    assert profile.subdivision_code == "US-NY"
    assert profile.state == state


def test_update_subdivision(factories, default_user, api_helpers, client):
    """
    When:
        - The member profile does not have a country_code
        - The member profile does not have a subdivision_code
        - The member profile does not have a state
    Then:
        - The PUT request is made with a subdivision, but not a state nor country
    Test that:
        - The response has a 200 status code
        - The member profile's country_code is set
        - The member profile's state is not set
        - The member profile's subdivision_code is set
    """
    profile = factories.MemberProfileFactory.create(user=default_user)

    assert profile.country_code is None
    assert profile.subdivision_code is None
    assert profile.state is None

    res = client.put(
        f"/api/v1/users/{default_user.id}/profiles/member",
        headers=api_helpers.standard_headers(default_user),
        json={"subdivision_code": "US-NY"},
    )

    assert res.status_code == 200
    assert profile.country_code == "US"
    assert profile.subdivision_code == "US-NY"
    assert profile.state is None


def test_update_subdivision__invalid_subdivision_code(
    factories, default_user, api_helpers, client
):
    """
    When:
        - The member profile does not have a country_code
        - The member profile does not have a subdivision_code
        - The member profile does not have a state
    Then:
        - The PUT request is made with an invalid subdivision, but not a state nor country
    Test that:
        - The response has a 400 status code
        - The member profile's country_code is not set
        - The member profile's subdivision_code is not set
        - The member profile's state is not set
    """
    profile = factories.MemberProfileFactory.create(user=default_user)

    assert profile.country_code is None
    assert profile.subdivision_code is None
    assert profile.state is None

    res = client.put(
        f"/api/v1/users/{default_user.id}/profiles/member",
        headers=api_helpers.standard_headers(default_user),
        json={"subdivision_code": "NY"},
    )

    assert res.status_code == 400

    assert profile.country_code is None
    assert profile.subdivision_code is None
    assert profile.state is None


def test_update_country_state_and_subdivision(
    factories, default_user, api_helpers, client
):
    """
    When:
        - The member profile does not have a country_code
        - The member profile does not have a subdivision_code
        - The member profile does not have a state
    Then:
        - The PUT request is made with a country, a state, and a subdivision
    Test that:
        - The response has a 200 status code
        - The member profile's country_code is set based on the country provided
        - The member profile's subdivision_code is set based on the country and state provided, not the subdivision code
        - The member profile's state is set based on the state from the request
    """
    profile = factories.MemberProfileFactory.create(user=default_user)
    state = factories.StateFactory.create(abbreviation="NY")

    assert profile.country_code is None
    assert profile.subdivision_code is None
    assert profile.state is None

    res = client.put(
        f"/api/v1/users/{default_user.id}/profiles/member",
        headers=api_helpers.standard_headers(default_user),
        json={"country": "US", "state": "NY", "subdivision_code": "DE-NW"},
    )

    assert res.status_code == 200
    assert profile.country_code == "US"
    assert profile.subdivision_code == "US-NY"
    assert profile.state == state


def test_update_country_state_and_subdivision_for_non_us(
    factories, default_user, api_helpers, client
):
    """
    When:
        - The member profile does have a country_code
        - The member profile does have a subdivision_code
        - The member profile does have a state
    Then:
        - The PUT request is made with a non US country
    Test that:
        - The response has a 200 status code
        - The member profile's country_code is set based on the country provided
        - The member profile's subdivision_code is set no None
    """
    factories.CountryMetadataFactory.create(country_code="GB")
    state_ny = factories.StateFactory.create(abbreviation="NY")
    profile = factories.MemberProfileFactory.create(
        user=default_user, state=state_ny, country_code="US"
    )

    assert profile.country_code == "US"
    assert profile.subdivision_code == "US-NY"
    assert profile.state is state_ny

    res = client.put(
        f"/api/v1/users/{default_user.id}/profiles/member",
        headers=api_helpers.standard_headers(default_user),
        json={"country": "GB", "state": "NY"},
    )

    assert res.status_code == 200
    assert profile.country_code == "GB"
    assert profile.subdivision_code is None
