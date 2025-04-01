from utils.random_string import generate_random_string
from wallet.pytests.factories import (
    OrganizationFactory,
    ReimbursementOrganizationSettingsFactory,
)


def test_reimbursement_organization_name_retrieval_successful_with_org_name(
    client,
    api_helpers,
    enterprise_user,
):
    org_name = generate_random_string(10)
    ros_name = generate_random_string(10)
    org = OrganizationFactory.create(name=org_name)
    ros = ReimbursementOrganizationSettingsFactory.create(
        name=ros_name, organization_id=org.id
    )

    url = f"/api/v1/-/wqs/reimbursement_org_setting_name/{ros.id}"

    res = client.get(
        url,
        headers=api_helpers.json_headers(enterprise_user),
    )
    assert res.status_code == 200

    content = api_helpers.load_json(res)
    assert org_name == content.get("org_setting_name")
    assert content.get("error_message") is None


def test_reimbursement_organization_name_retrieval_successful_with_org_display_name(
    client,
    api_helpers,
    enterprise_user,
):
    org_name = generate_random_string(10)
    org_display_name = generate_random_string(10)
    ros_name = generate_random_string(10)
    org = OrganizationFactory.create(name=org_name, display_name=org_display_name)
    ros = ReimbursementOrganizationSettingsFactory.create(
        name=ros_name, organization_id=org.id
    )

    url = f"/api/v1/-/wqs/reimbursement_org_setting_name/{ros.id}"

    res = client.get(
        url,
        headers=api_helpers.json_headers(enterprise_user),
    )
    assert res.status_code == 200

    content = api_helpers.load_json(res)
    assert org_display_name == content.get("org_setting_name")
    assert content.get("error_message") is None


def test_reimbursement_organization_name_retrieval_successful_ros_name_not_available(
    client,
    api_helpers,
    enterprise_user,
):
    org_name = generate_random_string(10)
    org = OrganizationFactory.create(name=org_name)
    ros = ReimbursementOrganizationSettingsFactory.create(organization_id=org.id)

    url = f"/api/v1/-/wqs/reimbursement_org_setting_name/{ros.id}"

    res = client.get(
        url,
        headers=api_helpers.json_headers(enterprise_user),
    )
    assert res.status_code == 200

    content = api_helpers.load_json(res)
    assert org_name == content.get("org_setting_name")
    assert content.get("error_message") is None


def test_reimbursement_organization_name_retrieval_ros_not_found(
    client,
    api_helpers,
    enterprise_user,
):
    org_name = generate_random_string(10)
    org = OrganizationFactory.create(name=org_name)
    ros = ReimbursementOrganizationSettingsFactory.create(
        name=org_name, organization_id=org.id
    )

    url = f"/api/v1/-/wqs/reimbursement_org_setting_name/{ros.id + 1}"
    res = client.get(
        url,
        headers=api_helpers.json_headers(enterprise_user),
    )
    assert res.status_code == 200

    content = api_helpers.load_json(res)
    assert content.get("org_setting_name") is None
    assert (
        content.get("error_message")
        == "Cannot find the reimbursement organization setting"
    )


def test_reimbursement_organization_name_retrieval_org_name_not_found(
    client,
    api_helpers,
    enterprise_user,
):
    ros = ReimbursementOrganizationSettingsFactory.create(organization_id=123)

    url = f"/api/v1/-/wqs/reimbursement_org_setting_name/{ros.id}"

    res = client.get(
        url,
        headers=api_helpers.json_headers(enterprise_user),
    )
    assert res.status_code == 200

    content = api_helpers.load_json(res)
    assert content.get("org_setting_name") is None
    assert (
        content.get("error_message") == "Cannot find the reimbursement org name in mono"
    )
