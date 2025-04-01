from models.enterprise import OrganizationEligibilityType


def test_org_id_not_found(api_helpers, client):
    """
    When the organization_id is not found, test that we return:
      - UNKNOWN as the eligibility type
      - 400 status code
      - one error
      - "Invalid organization" as the error message
    """
    res = client.get("/api/v1/organizations/123123123123")
    json = api_helpers.load_json(res)

    assert res.status_code == 400
    assert json["eligibility"]["type"] == OrganizationEligibilityType.UNKNOWN.value
    assert len(json["errors"]) == 1
    assert json["errors"][0]["detail"] == "Invalid organization"


def test_org_id_found(api_helpers, client, enterprise_user):
    """
    When the organization is found, test that we return:
      - the organization's eligibility type
      - the organization's id, name, marketing name
      - 200 status code
      - no errors
    """
    org = enterprise_user.organization
    org.eligibility_type = OrganizationEligibilityType.HEALTHPLAN
    res = client.get(f"/api/v1/organizations/{org.id}")
    json = api_helpers.load_json(res)

    assert res.status_code == 200
    assert json.get("errors") is None
    assert json["eligibility"]["type"] == OrganizationEligibilityType.HEALTHPLAN.value
    assert json["organization"]["id"] == org.id
    assert json["organization"]["name"] == org.name
    assert json["organization"]["marketing_name"] == org.marketing_name
    assert json["organization"]["logo"] == org.icon


def test_org_id_found__client_specific(api_helpers, client, enterprise_user):
    """
    When the organization is found, test that we return:
      - the organization's eligibility type
      - the organization's id, name, marketing name
      - 200 status code
      - no errors
    """
    org = enterprise_user.organization
    org.eligibility_type = OrganizationEligibilityType.CLIENT_SPECIFIC
    res = client.get(f"/api/v1/organizations/{org.id}")
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
