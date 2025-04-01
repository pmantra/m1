from models.enterprise import OrganizationEligibilityType


def test_no_orgs(api_helpers, client, default_user):
    """
    When there are no organizations, test that we return and empty list with a 200 response.
    """
    res = client.get(
        "/api/v1/organizations",
        headers=api_helpers.standard_headers(default_user),
    )
    json = api_helpers.load_json(res)

    assert res.status_code == 200
    assert len(json) == 0


def test_multiple_orgs(api_helpers, client, enterprise_user, factories):
    """
    When multiple organizations are known, test that we return:
      - the organization's eligibility type
      - the organization's id, name, marketing name
    for each organization, and the response should have:
      - 200 status code
    """
    org = enterprise_user.organization
    org.eligibility_type = OrganizationEligibilityType.HEALTHPLAN

    org2 = factories.OrganizationFactory.create()
    org2.eligibility_type = OrganizationEligibilityType.STANDARD

    res = client.get(
        "/api/v1/organizations",
        headers=api_helpers.standard_headers(enterprise_user),
    )
    json = api_helpers.load_json(res)

    assert res.status_code == 200
    assert len(json) == 2

    assert (
        json[0]["eligibility"]["type"] == OrganizationEligibilityType.HEALTHPLAN.value
    )
    assert json[0]["organization"]["id"] == org.id
    assert json[0]["organization"]["name"] == org.name
    assert json[0]["organization"]["marketing_name"] == org.marketing_name
    assert json[0]["organization"]["logo"] == org.icon

    assert json[1]["eligibility"]["type"] == OrganizationEligibilityType.STANDARD.value
    assert json[1]["organization"]["id"] == org2.id
    assert json[1]["organization"]["name"] == org2.name
    assert json[1]["organization"]["marketing_name"] == org2.marketing_name
    assert json[1]["organization"]["logo"] == org2.icon


def test_org_name_not_found(api_helpers, client, enterprise_user):
    """
    When the organization is not found, test that we return:
      - UNKNOWN as the eligibility type
      - 400 status code
      - one error
      - "Invalid organization" as the error message
    """
    res = client.get(
        "/api/v1/organizations?name=invalid",
        headers=api_helpers.standard_headers(enterprise_user),
    )
    json = api_helpers.load_json(res)

    assert res.status_code == 400
    assert json["eligibility"]["type"] == OrganizationEligibilityType.UNKNOWN.value
    assert len(json["errors"]) == 1
    assert json["errors"][0]["detail"] == "Invalid organization"


def test_org_found_by_name(api_helpers, client, enterprise_user):
    """
    When the organization is found by matching on the Organization.name, test that we return:
      - the organization's eligibility type
      - the organization's id, name, marketing name
      - 200 status code
      - no errors
    """
    org = enterprise_user.organization
    org.eligibility_type = OrganizationEligibilityType.HEALTHPLAN
    res = client.get(
        f"/api/v1/organizations?name={org.name}",
        headers=api_helpers.standard_headers(enterprise_user),
    )
    json = api_helpers.load_json(res)

    assert res.status_code == 200
    assert json.get("errors") is None
    assert json["eligibility"]["type"] == OrganizationEligibilityType.HEALTHPLAN.value
    assert json["organization"]["id"] == org.id
    assert json["organization"]["name"] == org.name
    assert json["organization"]["marketing_name"] == org.marketing_name
    assert json["organization"]["logo"] == org.icon


def test_org_found_by_display_name(api_helpers, client, enterprise_user):
    """
    When the organization is found by matching on the Organization.display_name, test that we return:
      - the organization's eligibility type
      - the organization's id, name, marketing name
      - 200 status code
      - no errors
    """
    org = enterprise_user.organization
    org.display_name = f"{org.name} Display"
    org.eligibility_type = OrganizationEligibilityType.HEALTHPLAN
    res = client.get(
        f"/api/v1/organizations?name={org.display_name}",
        headers=api_helpers.standard_headers(enterprise_user),
    )
    json = api_helpers.load_json(res)

    assert res.status_code == 200
    assert json.get("errors") is None
    assert json["eligibility"]["type"] == OrganizationEligibilityType.HEALTHPLAN.value
    assert json["organization"]["id"] == org.id
    assert json["organization"]["name"] == org.name
    assert json["organization"]["marketing_name"] == org.marketing_name
    assert json["organization"]["logo"] == org.icon


def test_org_name_found__client_specific(api_helpers, client, enterprise_user):
    """
    When the organization is found, test that we return:
      - the organization's eligibility type
      - the organization's id, name, marketing name
      - 200 status code
      - no errors
    """
    org = enterprise_user.organization
    org.eligibility_type = OrganizationEligibilityType.CLIENT_SPECIFIC
    res = client.get(
        f"/api/v1/organizations/{org.id}",
        headers=api_helpers.standard_headers(enterprise_user),
    )
    json = api_helpers.load_json(res)

    assert res.status_code == 200
    assert json.get("errors") is None
    assert (
        json["eligibility"]["type"] == OrganizationEligibilityType.CLIENT_SPECIFIC.value
    )
    assert json["eligibility"]["code"] == "CLIENT_SPECIFIC_ELIGIBILITY_ENABLED"
    assert json["eligibility"].get("fields") is not None
    assert json["organization"]["id"] == org.id
    assert json["organization"]["name"] == org.name
    assert json["organization"]["marketing_name"] == org.marketing_name
    assert json["organization"]["logo"] == org.icon
