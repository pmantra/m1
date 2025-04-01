def test_update_country(factories, default_user, api_helpers, client):
    """
    When:
        - The practitioner profile does not have a country_code
    Then:
        - The PUT request is made with a country
    Test that:
        - The response has a 200 status code
        - The practitioner profile's country_code is set
    """
    profile = factories.PractitionerProfileFactory.create(user=default_user)

    assert profile.country_code is None

    res = client.put(
        f"/api/v1/users/{default_user.id}/profiles/practitioner",
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
        - The practitioner profile has a country_code
        - The practitioner profile does not have a subdivision_code
        - The practitioner profile does not have a state
    Then:
        - The PUT request is made with a state, but not a country
    Test that:
        - The response has a 200 status code
        - The practitioner profile's country_code remains the same
        - The practitioner profile's subdivision_code is set
        - The practitioner profile's state is set
    """
    profile = factories.PractitionerProfileFactory.create(
        user=default_user, state=None, country_code="US"
    )
    state = factories.StateFactory.create(abbreviation="NY")

    assert profile.country_code == "US"
    assert profile.subdivision_code is None
    assert profile.state is None

    res = client.put(
        f"/api/v1/users/{default_user.id}/profiles/practitioner",
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
        - The practitioner profile does not have a country_code
        - The practitioner profile does not have a subdivision_code
        - The practitioner profile does not have a state
    Then:
        - The PUT request is made with a country and a state
    Test that:
        - The response has a 200 status code
        - The practitioner profile's country_code is set
        - The practitioner profile's subdivision_code is set
        - The practitioner profile's state is set
    """
    profile = factories.PractitionerProfileFactory.create(user=default_user, state=None)
    state = factories.StateFactory.create(abbreviation="NY")

    assert profile.country_code is None
    assert profile.subdivision_code is None
    assert profile.state is None

    res = client.put(
        f"/api/v1/users/{default_user.id}/profiles/practitioner",
        headers=api_helpers.standard_headers(default_user),
        json={"country": "US", "state": "NY"},
    )

    assert res.status_code == 200
    assert profile.country_code == "US"
    assert profile.subdivision_code == "US-NY"
    assert profile.state == state


def test_update_state_no_country_code(factories, default_user, api_helpers, client):
    """
    When:
        - The practitioner profile does not have a country_code
        - The practitioner profile does not have a subdivision_code
        - The practitioner profile does not have a state
    Then:
        - The PUT request is made with a state, but not a country
    Test that:
        - The response has a 200 status code
        - The practitioner profile's country_code is set
        - The practitioner profile's subdivision_code is set
        - The practitioner profile's state is set
    """
    profile = factories.PractitionerProfileFactory.create(user=default_user, state=None)
    state = factories.StateFactory.create(abbreviation="NY")

    assert profile.country_code is None
    assert profile.subdivision_code is None
    assert profile.state is None

    res = client.put(
        f"/api/v1/users/{default_user.id}/profiles/practitioner",
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
        - The practitioner profile does not have a country_code
        - The practitioner profile does not have a subdivision_code
        - The practitioner profile does not have a state
    Then:
        - The PUT request is made with a subdivision, but not a state
    Test that:
        - The response has a 200 status code
        - The practitioner profile's country_code is set
        - The practitioner profile's subdivision_code is set
        - The practitioner profile's state is not set
    """
    profile = factories.PractitionerProfileFactory.create(user=default_user, state=None)

    assert profile.country_code is None
    assert profile.subdivision_code is None
    assert profile.state is None

    res = client.put(
        f"/api/v1/users/{default_user.id}/profiles/practitioner",
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
        - The practitioner profile does not have a country_code
        - The practitioner profile does not have a subdivision_code
        - The practitioner profile does not have a state
    Then:
        - The PUT request is made with an invalid subdivision and no state
    Test that:
        - The response has a 400 status code
        - The practitioner profile's country_code is not set
        - The practitioner profile's subdivision_code is not set
        - The practitioner profile's state is not set
    """
    profile = factories.PractitionerProfileFactory.create(user=default_user, state=None)

    assert profile.country_code is None
    assert profile.subdivision_code is None
    assert profile.state is None

    res = client.put(
        f"/api/v1/users/{default_user.id}/profiles/practitioner",
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
        - The practitioner profile does not have a country_code
        - The practitioner profile does not have a subdivision_code
        - The practitioner profile does not have a state
    Then:
        - The PUT request is made with a state and a subdivision
    Test that:
        - The response has a 200 status code
        - The practitioner profile's country_code is set based on the country provided
        - The practitioner profile's subdivision_code is set based on the country and state provided, not the subdivision code
        - The practitioner profile's state is set based on the state from the request
    """
    profile = factories.PractitionerProfileFactory.create(user=default_user, state=None)
    state = factories.StateFactory.create(abbreviation="NY")

    assert profile.country_code is None
    assert profile.subdivision_code is None
    assert profile.state is None

    res = client.put(
        f"/api/v1/users/{default_user.id}/profiles/practitioner",
        headers=api_helpers.standard_headers(default_user),
        json={"country": "US", "state": "NY", "subdivision_code": "DE-NW"},
    )

    assert res.status_code == 200
    assert profile.country_code == "US"
    assert profile.subdivision_code == "US-NY"
    assert profile.state == state


def test_update_address(factories, default_user, api_helpers, client):
    """
    When:
        - The practitioner profile does not have a country
        - The practitioner profile does not have a country_code
    Then:
        - The PUT request is made with an address that includes a valid country
    Test that:
        - The response has a 200 status code
        - The practitioner profile's country_code is not set because PractitionerProfile's are configured to not update
          the country using an address
    """
    profile = factories.PractitionerProfileFactory.create(user=default_user)
    factories.StateFactory.create(abbreviation="NY")

    assert profile.country_code is None
    assert len(default_user.addresses) == 0

    res = client.put(
        f"/api/v1/users/{default_user.id}/profiles/practitioner",
        headers=api_helpers.standard_headers(default_user),
        json={
            "address": {
                "street_address": "123 Fake Street",
                "zip_code": "12345",
                "city": "New York",
                "country": "US",
                "state": "NY",
            },
        },
    )

    assert res.status_code == 200
    assert profile.country_code is None
    assert len(default_user.addresses) == 1
