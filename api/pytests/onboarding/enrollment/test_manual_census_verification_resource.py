import copy
import json

from pytests import factories

DEFAULT_DATA = {
    "first_name": "Test",
    "last_name": "Human",
    "organization": None,
    "date_of_birth": "2000-01-01",
    "isSSO": True,
    "user_id": 88915,
    "due_date": "None",
    "last_child_birthday": "None",
}


def test_census_verification_without_external_identity(
    client,
    api_helpers,
    mock_enterprise_zendesk,
    mock_enterprise_verification_service,
    mock_redis_lock,
):
    # Given
    given_user = factories.MemberFactory.create()
    expected_org_data = {"organization_id": None, "organization_name": None}
    # When
    client.post(
        "/api/v1/_/manual_census_verification",
        headers=api_helpers.json_headers(user=given_user),
        json=DEFAULT_DATA,
    )
    kwargs = mock_enterprise_zendesk.comment.call_args[1]
    comment_data = json.loads(kwargs["comment_body"])
    org_data = comment_data["organization"]
    # Then
    assert org_data == expected_org_data


def test_census_verification_with_org_from_search_page(
    client,
    api_helpers,
    mock_enterprise_zendesk,
    mock_enterprise_verification_service,
    mock_redis_lock,
):
    # Given
    given_user = factories.MemberFactory.create()
    given_org = factories.OrganizationFactory.create()
    expected_org_data = {
        "organization_id": given_org.id,
        "organization_name": given_org.name,
    }
    get_org_by_name_query_method = (
        mock_enterprise_verification_service.orgs.get_organization_by_name
    )
    get_org_by_name_query_method.return_value = given_org

    # When
    data = copy.copy(DEFAULT_DATA)
    data["organizationFromSearchPage"] = "test org"
    client.post(
        "/api/v1/_/manual_census_verification",
        headers=api_helpers.json_headers(user=given_user),
        json=data,
    )
    # Then
    kwargs = mock_enterprise_zendesk.comment.call_args[1]
    comment_data = json.loads(kwargs["comment_body"])
    org_data = comment_data["organization"]
    # Then
    assert org_data == expected_org_data


def test_census_verification_with_org_from_link(
    client,
    api_helpers,
    mock_enterprise_zendesk,
    mock_enterprise_verification_service,
    mock_redis_lock,
):
    # Given
    given_user = factories.MemberFactory.create()
    given_org = factories.OrganizationFactory.create()
    expected_org_data = {
        "organization_id": given_org.id,
        "organization_name": given_org.name,
    }
    get_org_by_id_query_method = (
        mock_enterprise_verification_service.orgs.get_by_organization_id
    )
    get_org_by_id_query_method.return_value = given_org

    # When
    data = copy.copy(DEFAULT_DATA)
    data["externallySourcedOrganization"] = 18
    client.post(
        "/api/v1/_/manual_census_verification",
        headers=api_helpers.json_headers(user=given_user),
        json=data,
    )
    # Then
    kwargs = mock_enterprise_zendesk.comment.call_args[1]
    comment_data = json.loads(kwargs["comment_body"])
    org_data = comment_data["organization"]
    # Then
    assert org_data == expected_org_data
