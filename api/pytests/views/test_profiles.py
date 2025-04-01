def test_get_member_profile(client, api_helpers, factories):
    user = factories.EnterpriseUserFactory()
    state = factories.StateFactory.create(abbreviation="NY")
    profile = factories.MemberProfileFactory(
        user=user,
        country_code="US",
        phone_number="+12125551515",
        state=state,
        subdivision_code="US-NY",
        care_plan_id=1,
    )
    address = factories.AddressFactory.create(user=user)

    res = client.get(
        "/api/v1/users/profiles/member", headers=api_helpers.standard_headers(user)
    )
    json = api_helpers.load_json(res)

    assert res.status_code == 200
    assert json["address"] == {
        "country": address.country,
        "city": address.city,
        "state": address.state,
        "street_address": address.street_address,
        "zip_code": address.zip_code,
    }
    assert json["care_plan_id"] == profile.care_plan_id
    assert json["country"] == profile.country_code
    assert json["phone_number"] == "2125551515"
    assert json["tel_number"] == "tel:+1-212-555-1515"
    assert json["tel_region"] == "US"
    assert json["state"] == state.abbreviation
    assert json["subdivision_code"] == profile.subdivision_code


def test_get_member_profile_when_no_profile(client, api_helpers, factories):
    user = factories.PractitionerUserFactory()

    res = client.get(
        "/api/v1/users/profiles/member", headers=api_helpers.standard_headers(user)
    )
    json = api_helpers.load_json(res)

    assert res.status_code == 200
    assert json == {}


def test_get_member_profile_when_unauthenticated(client):
    res = client.get("/api/v1/users/profiles/member")

    assert res.status_code == 401


def test_get_practitioner_profile(client, api_helpers, factories):
    user = factories.PractitionerUserFactory()
    state = factories.StateFactory.create(abbreviation="NY")
    profile = factories.PractitionerProfileFactory(
        user=user,
        country_code="US",
        phone_number="+12125551515",
        state=state,
        subdivision_code="US-NY",
    )
    address = factories.AddressFactory.create(user=user)

    res = client.get(
        "/api/v1/users/profiles/practitioner",
        headers=api_helpers.standard_headers(user),
    )
    json = api_helpers.load_json(res)

    assert res.status_code == 200
    assert json["address"] == {
        "country": address.country,
        "city": address.city,
        "state": address.state,
        "street_address": address.street_address,
        "zip_code": address.zip_code,
    }
    assert json["state"] == state.abbreviation
    assert json["subdivision_code"] == profile.subdivision_code
    assert json["phone_number"] == "2125551515"
    assert json["tel_number"] == "tel:+1-212-555-1515"
    assert json["tel_region"] == "US"
    assert json["can_member_interact"]


def test_get_practitioner_profile_when_no_profile(client, api_helpers, factories):
    user = factories.EnterpriseUserFactory()

    res = client.get(
        "/api/v1/users/profiles/practitioner",
        headers=api_helpers.standard_headers(user),
    )
    json = api_helpers.load_json(res)

    assert res.status_code == 200
    assert json == {}


def test_get_practitioner_profile_when_unauthenticated(client):
    res = client.get("/api/v1/users/profiles/practitioner")

    assert res.status_code == 401
