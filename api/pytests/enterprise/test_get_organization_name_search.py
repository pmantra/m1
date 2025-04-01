import datetime
from unittest.mock import patch

from redis.exceptions import ConnectionError

from models.enterprise import OrganizationType
from utils.org_search_autocomplete import OrganizationSearchAutocomplete


def test_no_input__name(api_helpers, client, default_user):
    """
    When there is an empty input to the `name` parameter, test that we return:
      - 400 status code
      - one error
      - "Required query parameter 'name' not found" as the error message
    """
    res = client.get(
        "/api/v1/organizations/search?name=",
        headers=api_helpers.standard_headers(default_user),
    )
    json = api_helpers.load_json(res)

    assert res.status_code == 400
    assert json.get("results") is None
    assert len(json["errors"]) == 1
    assert json["errors"][0]["detail"] == "Required query parameter 'name' not found"


def test_one_character_input__name(api_helpers, client, default_user):
    """
    When there is an empty input to the `name` parameter, test that we return:
      - 400 status code
      - one error
      - "Must include query of at least two characters" as the error message
    """
    res = client.get(
        "/api/v1/organizations/search?name=F",
        headers=api_helpers.standard_headers(default_user),
    )
    json = api_helpers.load_json(res)

    assert res.status_code == 400
    assert json.get("results") is None
    assert len(json["errors"]) == 1
    assert (
        json["errors"][0]["detail"] == "Must include query of at least two characters"
    )


def test_no_orgs_in_cache(api_helpers, client, default_user, random_prefix):
    """
    When there are no organizations in the cache,
    test that we return and empty list with a 200 status code.
    """
    res = client.get(
        f"/api/v1/organizations/search?name={random_prefix}",
        headers=api_helpers.standard_headers(default_user),
    )
    json = api_helpers.load_json(res)

    assert res.status_code == 200
    assert len(json["results"]) == 0


def test_no_matching_orgs__name(
    api_helpers, client, default_user, default_organization, random_prefix
):
    """
    When there are no organizations matching the search criteria,
    test that we return and empty list with a 200 status code.
    """
    default_organization.name = f"{random_prefix}FunCorp"

    # the orgs won't show up until we reload the set in redis
    OrganizationSearchAutocomplete().reload_orgs()
    res = client.get(
        "/api/v1/organizations/search?name=FunCorp",
        headers=api_helpers.standard_headers(default_user),
    )
    json = api_helpers.load_json(res)

    assert res.status_code == 200
    assert len(json["results"]) == 0


def test_invalid_query_param(api_helpers, client, default_user):
    """
    When an invalid query parameter is passed to the endpoint,
    test that we return:
      - 400 status code
    """
    res = client.get(
        "/api/v1/organizations/search?q=abc",
        headers=api_helpers.standard_headers(default_user),
    )
    json = api_helpers.load_json(res)

    assert res.status_code == 400
    assert json.get("results") is None
    assert len(json["errors"]) == 1
    assert json["errors"][0]["detail"] == "Required query parameter 'name' not found"


def test_one_matching_org__name(
    api_helpers, client, default_user, default_organization, random_prefix
):
    """
    When one organization name matches the search criteria,
    test that we return:
      - 200 status code
      - no errors
      - the results list containing one item
      - the item in the results list is a JSON object with the matching organization name and its ID
    """
    default_organization.name = f"{random_prefix}FunCorp"

    # the orgs won't show up until we reload the set in redis
    OrganizationSearchAutocomplete().reload_orgs()

    res = client.get(
        f"/api/v1/organizations/search?name={random_prefix}",
        headers=api_helpers.standard_headers(default_user),
    )
    json = api_helpers.load_json(res)

    assert res.status_code == 200
    assert json.get("errors") is None
    assert len(json["results"]) == 1
    assert json["results"][0]["id"] == str(default_organization.id)
    assert json["results"][0]["name"] == default_organization.name


def test_two_matching_orgs__name(
    api_helpers, client, default_user, factories, random_prefix
):
    """
    When two organization names match the search criteria,
    test that we return:
      - 200 status code
      - no errors
      - the results list containing one item
      - the item in the results list is a JSON object with the matching organization name and its ID
    """
    org_1 = factories.OrganizationFactory.create(name=f"{random_prefix}FunCorp")
    org_2 = factories.OrganizationFactory.create(name=f"{random_prefix}FunkyCorp")
    factories.OrganizationFactory.create(name="FooBar")

    # the orgs won't show up until we reload the set in redis
    OrganizationSearchAutocomplete().reload_orgs()

    res = client.get(
        f"/api/v1/organizations/search?name={random_prefix}",
        headers=api_helpers.standard_headers(default_user),
    )
    json = api_helpers.load_json(res)

    assert res.status_code == 200
    assert json.get("errors") is None
    assert len(json["results"]) == 2
    assert json["results"][0]["id"] == str(org_1.id)
    assert json["results"][0]["name"] == org_1.name
    assert json["results"][1]["id"] == str(org_2.id)
    assert json["results"][1]["name"] == org_2.name


def test_matching_org_with_real_internal_type(
    api_helpers, client, default_user, default_organization, random_prefix
):
    """
    When
      - One organization name matches the search criteria
      - Organization has an internal type of REAL
    test that we return:
      - 200 status code
      - no errors
      - the results list containing one item
      - the item in the results list is a JSON object with the matching organization name and its ID
    """
    default_organization.name = f"{random_prefix}FunCorp"
    default_organization.internap_type = OrganizationType.REAL

    # the orgs won't show up until we reload the set in redis
    OrganizationSearchAutocomplete().reload_orgs()

    res = client.get(
        f"/api/v1/organizations/search?name={random_prefix}",
        headers=api_helpers.standard_headers(default_user),
    )
    json = api_helpers.load_json(res)

    assert res.status_code == 200
    assert json.get("errors") is None
    assert len(json["results"]) == 1
    assert json["results"][0]["id"] == str(default_organization.id)
    assert json["results"][0]["name"] == default_organization.name


def test_matching_org_with_maven_for_maven_internal_type(
    api_helpers, client, default_user, default_organization, random_prefix
):
    """
    When
      - One organization name matches the search criteria
      - Organization has an internal type of MAVEN_FOR_MAVEN
    test that we return:
      - 200 status code
      - no errors
      - the results list containing one item
      - the item in the results list is a JSON object with the matching organization name and its ID
    """
    default_organization.name = f"{random_prefix}Maven Clinic Users"
    default_organization.internal_type = OrganizationType.MAVEN_FOR_MAVEN

    # the orgs won't show up until we reload the set in redis
    OrganizationSearchAutocomplete().reload_orgs()

    res = client.get(
        f"/api/v1/organizations/search?name={random_prefix}",
        headers=api_helpers.standard_headers(default_user),
    )
    json = api_helpers.load_json(res)

    assert res.status_code == 200
    assert json.get("errors") is None
    assert len(json["results"]) == 1
    assert json["results"][0]["id"] == str(default_organization.id)
    assert json["results"][0]["name"] == default_organization.name


def test_matching_org_with_other_internal_types(
    api_helpers, client, default_user, factories, random_prefix
):
    """
    When
      - Organization name matches the search criteria
      - Organization has an internal type of DEMO_OR_VIP or TEST
    test that we return:
      - 200 status code
      - no errors
      - empty list
    """
    factories.OrganizationFactory.create(
        name=f"{random_prefix}FunCorp1", internal_type=OrganizationType.DEMO_OR_VIP
    )

    factories.OrganizationFactory.create(
        name=f"{random_prefix}FunCorp2", internal_type=OrganizationType.TEST
    )

    # the orgs won't show up until we reload the set in redis
    OrganizationSearchAutocomplete().reload_orgs()

    res = client.get(
        f"/api/v1/organizations/search?name={random_prefix}",
        headers=api_helpers.standard_headers(default_user),
    )
    json = api_helpers.load_json(res)

    assert res.status_code == 200
    assert len(json["results"]) == 0


def test_matching_inactive_org(
    api_helpers, client, default_user, factories, random_prefix
):
    """
    When
      - Organization name matches the search criteria
      - Organization has an internal type of REAL or MAVEN_FOR_MAVEN
      - Organization is not active
    Test that we return:
      - 200 status code
      - no errors
      - empty list
    """
    now = datetime.datetime.utcnow()
    yesterday = now - datetime.timedelta(days=1)
    last_year = now - datetime.timedelta(days=365)
    org1 = factories.OrganizationFactory.create(
        name=f"{random_prefix}FunCorp1", internal_type=OrganizationType.REAL
    )
    org1.activated_at = last_year
    org1.terminated_at = yesterday

    org2 = factories.OrganizationFactory.create(
        name=f"{random_prefix}FunCorp2", internal_type=OrganizationType.MAVEN_FOR_MAVEN
    )
    org2.activated_at = last_year
    org2.terminated_at = yesterday

    # the orgs won't show up until we reload the set in redis
    OrganizationSearchAutocomplete().reload_orgs()

    res = client.get(
        f"/api/v1/organizations/search?name={random_prefix}",
        headers=api_helpers.standard_headers(default_user),
    )
    json = api_helpers.load_json(res)

    assert res.status_code == 200
    assert len(json["results"]) == 0


def test_redis_connection_error(api_helpers, client, default_user):
    """
    When Redis encounters a connection error during command execution, test that we return:
      - 200 status code
      - no errors
      - empty results list
    """
    with patch("redis.Redis.execute_command") as mock_redis_execute:
        mock_redis_execute.side_effect = ConnectionError(
            "Error 111 connecting to redis:6379. Connection refused."
        )

        res = client.get(
            "/api/v1/organizations/search?name=test",
            headers=api_helpers.standard_headers(default_user),
        )
        json = api_helpers.load_json(res)

        assert res.status_code == 200
        assert json.get("errors") is None
        assert len(json["results"]) == 0

    """
    When Redis encounters a timeout error during command execution, test that we return:
      - 503 status code
      - timeout errors
    """
    with patch("redis.Redis.execute_command") as mock_redis_execute:
        mock_redis_execute.side_effect = TimeoutError("timeout")

        res = client.get(
            "/api/v1/organizations/search?name=test",
            headers=api_helpers.standard_headers(default_user),
        )
        json = api_helpers.load_json(res)

        assert res.status_code == 503
        assert json.get("errors") == [
            {
                "status": 503,
                "title": "Service Unavailable",
                "detail": "Timed out on operation: timeout. Please try again later.",
            }
        ]
