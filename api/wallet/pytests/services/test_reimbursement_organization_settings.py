import datetime
import time

from utils.random_string import generate_random_string
from wallet.pytests.factories import (
    OrganizationFactory,
    ReimbursementOrganizationSettingsFactory,
)
from wallet.resources.reimbursement_org_settings import DEFAULT_LIMIT


def test_reimbursement_organization_settings_happy_path_no_filter(
    client,
    api_helpers,
    enterprise_user,
):
    batch_size = DEFAULT_LIMIT
    org_name_prefix = generate_random_string(10)

    input_org_settings = _set_org_settings(batch_size, org_name_prefix)
    res = client.get(
        "/api/v1/-/wqs/reimbursement_org",
        headers=api_helpers.json_headers(enterprise_user),
    )
    assert res.status_code == 200
    content = api_helpers.load_json(res)
    assert content["total_results"] == batch_size
    reimbursement_org_settings = content["reimbursement_orgs"]
    output_org_settings = {
        (ros["reimbursement_org_settings_id"], ros["name"])
        for ros in reimbursement_org_settings
    }
    assert len(input_org_settings) == len(output_org_settings)
    assert input_org_settings == output_org_settings


def test_reimbursement_organization_settings_ros_id(
    client,
    api_helpers,
    enterprise_user,
):
    org_1 = OrganizationFactory.create(name="hello")
    ros_1 = ReimbursementOrganizationSettingsFactory.create(
        name=None, organization_id=org_1.id
    )

    org_2 = OrganizationFactory.create(name="Super Corp! Should not show!")
    ReimbursementOrganizationSettingsFactory.create(
        name="hello corp, should show!", organization_id=org_2.id
    )

    org_3 = OrganizationFactory.create(name="banana")
    ros_3 = ReimbursementOrganizationSettingsFactory.create(
        name="banana", organization_id=org_3.id
    )

    res = client.get(
        f'/api/v1/-/wqs/reimbursement_org?filter={{"ros_id": [{ros_1.id}, {ros_3.id}]}}',
        headers=api_helpers.json_headers(enterprise_user),
    )
    assert res.status_code == 200
    content = api_helpers.load_json(res)
    assert content["total_results"] == 2
    reimbursement_org_settings = content["reimbursement_orgs"]
    output_org_settings = {
        (ros["reimbursement_org_settings_id"], ros["name"])
        for ros in reimbursement_org_settings
    }

    assert output_org_settings == {
        (str(ros_1.id), "hello"),
        (str(ros_3.id), "banana"),
    }


def test_reimbursement_organization_settings_org_name(
    client,
    api_helpers,
    enterprise_user,
):
    org_1 = OrganizationFactory.create(name="hello")
    ros_1 = ReimbursementOrganizationSettingsFactory.create(
        name=None, organization_id=org_1.id
    )

    org_2 = OrganizationFactory.create(name="Super Corp! Should not show!")
    ros_2 = ReimbursementOrganizationSettingsFactory.create(
        name="hello corp, should show!", organization_id=org_2.id
    )

    org_3 = OrganizationFactory.create(name="banana")
    ReimbursementOrganizationSettingsFactory.create(
        name="banana", organization_id=org_3.id
    )

    res = client.get(
        "/api/v1/-/wqs/reimbursement_org?filter=hel",
        headers=api_helpers.json_headers(enterprise_user),
    )
    assert res.status_code == 200
    content = api_helpers.load_json(res)
    assert content["total_results"] == 2
    reimbursement_org_settings = content["reimbursement_orgs"]
    output_org_settings = {
        (ros["reimbursement_org_settings_id"], ros["name"])
        for ros in reimbursement_org_settings
    }

    assert output_org_settings == {
        (str(ros_1.id), "hello"),
        (str(ros_2.id), "hello corp, should show!"),
    }


def test_reimbursement_organization_settings_name_and_ros_id(
    client,
    api_helpers,
    enterprise_user,
):
    org_1 = OrganizationFactory.create(name="hello")
    ros_1 = ReimbursementOrganizationSettingsFactory.create(
        name=None, organization_id=org_1.id
    )

    org_2 = OrganizationFactory.create(name="Super Corp! Should not show!")
    ReimbursementOrganizationSettingsFactory.create(
        name="hello corp, should show!", organization_id=org_2.id
    )

    org_3 = OrganizationFactory.create(name="banana")
    ros_3 = ReimbursementOrganizationSettingsFactory.create(
        name="banana", organization_id=org_3.id
    )

    res_1 = client.get(
        f'/api/v1/-/wqs/reimbursement_org?filter={{"name": "hel", "ros_id": [{ros_1.id}, {ros_3.id}]}}',
        headers=api_helpers.json_headers(enterprise_user),
    )
    assert res_1.status_code == 200
    content_1 = api_helpers.load_json(res_1)
    assert content_1["total_results"] == 1
    reimbursement_org_settings_1 = content_1["reimbursement_orgs"]
    output_org_settings_1 = {
        (ros["reimbursement_org_settings_id"], ros["name"])
        for ros in reimbursement_org_settings_1
    }
    assert output_org_settings_1 == {
        (str(ros_1.id), "hello"),
    }

    res_2 = client.get(
        f'/api/v1/-/wqs/reimbursement_org?filter={{"name": "hel", "ros_id": [{ros_3.id}]}}',
        headers=api_helpers.json_headers(enterprise_user),
    )
    assert res_2.status_code == 200
    content_2 = api_helpers.load_json(res_2)
    assert content_2["total_results"] == 0
    reimbursement_org_settings_2 = content_2["reimbursement_orgs"]
    output_org_settings_2 = {
        (ros["reimbursement_org_settings_id"], ros["name"])
        for ros in reimbursement_org_settings_2
    }
    assert output_org_settings_2 == set()


def test_reimbursement_organization_settings_happy_path_with_small_limit(
    client,
    api_helpers,
    enterprise_user,
):
    batch_size = DEFAULT_LIMIT
    limit = batch_size - 10
    org_name_prefix = generate_random_string(10)

    input_org_settings = _set_org_settings(
        batch_size, org_name_prefix, should_wait=True
    )
    res = client.get(
        f"/api/v1/-/wqs/reimbursement_org?limit={limit}",
        headers=api_helpers.json_headers(enterprise_user),
    )
    assert res.status_code == 200
    content = api_helpers.load_json(res)
    assert content["total_results"] == batch_size
    reimbursement_org_settings = content["reimbursement_orgs"]
    output_org_settings = {
        (ros["reimbursement_org_settings_id"], ros["name"])
        for ros in reimbursement_org_settings
    }
    assert len(input_org_settings) - 10 == len(output_org_settings)
    assert output_org_settings < input_org_settings

    expected_output_org_setting_names = [
        f"{org_name_prefix}_{i}" for i in range(0, min(limit, batch_size))
    ]
    for output_org_setting in output_org_settings:
        assert output_org_setting[1] in expected_output_org_setting_names


def test_reimbursement_organization_settings_happy_path_with_large_limit(
    client,
    api_helpers,
    enterprise_user,
):
    batch_size = DEFAULT_LIMIT
    limit = batch_size + 10
    org_name_prefix = generate_random_string(10)

    input_org_settings = _set_org_settings(batch_size, org_name_prefix)
    res = client.get(
        f"/api/v1/-/wqs/reimbursement_org?limit={limit}",
        headers=api_helpers.json_headers(enterprise_user),
    )
    assert res.status_code == 200
    content = api_helpers.load_json(res)
    assert content["total_results"] == batch_size
    reimbursement_org_settings = content["reimbursement_orgs"]
    output_org_settings = {
        (ros["reimbursement_org_settings_id"], ros["name"])
        for ros in reimbursement_org_settings
    }
    assert len(input_org_settings) == len(output_org_settings)
    assert output_org_settings == input_org_settings


def test_reimbursement_organization_settings_happy_path_with_small_offset(
    client,
    api_helpers,
    enterprise_user,
):
    batch_size = DEFAULT_LIMIT
    offset = 10
    org_name_prefix = generate_random_string(10)

    input_org_settings = _set_org_settings(
        batch_size, org_name_prefix, should_wait=True
    )
    res = client.get(
        f"/api/v1/-/wqs/reimbursement_org?offset={offset}",
        headers=api_helpers.json_headers(enterprise_user),
    )
    assert res.status_code == 200
    content = api_helpers.load_json(res)
    assert content["total_results"] == batch_size
    reimbursement_org_settings = content["reimbursement_orgs"]
    output_org_settings = {
        (ros["reimbursement_org_settings_id"], ros["name"])
        for ros in reimbursement_org_settings
    }
    assert len(input_org_settings) - 10 == len(output_org_settings)
    assert output_org_settings < input_org_settings

    expected_output_org_setting_names = [
        f"{org_name_prefix}_{i}" for i in range(offset, batch_size)
    ]
    for output_org_setting in output_org_settings:
        assert output_org_setting[1] in expected_output_org_setting_names


def test_reimbursement_organization_settings_happy_path_with_large_offset(
    client,
    api_helpers,
    enterprise_user,
):
    batch_size = 10
    offset = 20
    org_name_prefix = generate_random_string(10)

    _set_org_settings(batch_size, org_name_prefix)
    res = client.get(
        f"/api/v1/-/wqs/reimbursement_org?offset={offset}",
        headers=api_helpers.json_headers(enterprise_user),
    )
    assert res.status_code == 200
    content = api_helpers.load_json(res)
    assert content["total_results"] == batch_size
    reimbursement_org_settings = content["reimbursement_orgs"]
    output_org_settings = {
        (ros["reimbursement_org_settings_id"], ros["name"])
        for ros in reimbursement_org_settings
    }
    assert len(output_org_settings) == 0


def test_reimbursement_organization_settings_happy_path_with_old_name_filter(
    client,
    api_helpers,
    enterprise_user,
):
    batch_size = DEFAULT_LIMIT
    org_name_prefix = generate_random_string(10)
    input_org_settings = _set_org_settings(batch_size, org_name_prefix)

    # exact match
    res_one = client.get(
        f"/api/v1/-/wqs/reimbursement_org?filter={org_name_prefix}",
        headers=api_helpers.json_headers(enterprise_user),
    )
    assert res_one.status_code == 200
    content_one = api_helpers.load_json(res_one)
    assert content_one["total_results"] == batch_size
    reimbursement_org_settings_one = content_one["reimbursement_orgs"]
    output_org_settings_one = {
        (ros["reimbursement_org_settings_id"], ros["name"])
        for ros in reimbursement_org_settings_one
    }
    assert len(output_org_settings_one) == batch_size
    assert input_org_settings == output_org_settings_one

    # substring match
    res_two = client.get(
        f"/api/v1/-/wqs/reimbursement_org?filter={org_name_prefix[:3]}",
        headers=api_helpers.json_headers(enterprise_user),
    )
    assert res_two.status_code == 200
    content_two = api_helpers.load_json(res_two)
    assert content_two["total_results"] == batch_size
    reimbursement_org_settings_two = content_two["reimbursement_orgs"]
    output_org_settings_two = {
        (ros["reimbursement_org_settings_id"], ros["name"])
        for ros in reimbursement_org_settings_two
    }
    assert len(reimbursement_org_settings_two) == batch_size
    assert input_org_settings == output_org_settings_two

    # ignore-case match
    res_three = client.get(
        f"/api/v1/-/wqs/reimbursement_org?filter={org_name_prefix[:3].upper()}",
        headers=api_helpers.json_headers(enterprise_user),
    )
    assert res_three.status_code == 200
    content_three = api_helpers.load_json(res_three)
    assert content_three["total_results"] == batch_size
    reimbursement_org_settings_three = content_three["reimbursement_orgs"]
    output_org_settings_three = {
        (ros["reimbursement_org_settings_id"], ros["name"])
        for ros in reimbursement_org_settings_three
    }
    assert len(output_org_settings_three) == batch_size
    assert input_org_settings == output_org_settings_three

    # not match
    res_four = client.get(
        f"/api/v1/-/wqs/reimbursement_org?filter={org_name_prefix}lol",
        headers=api_helpers.json_headers(enterprise_user),
    )
    assert res_four.status_code == 200
    content_four = api_helpers.load_json(res_four)
    assert content_four["total_results"] == 0
    reimbursement_org_settings_four = content_four["reimbursement_orgs"]
    output_org_settings_four = {
        (ros["reimbursement_org_settings_id"], ros["name"])
        for ros in reimbursement_org_settings_four
    }
    assert len(output_org_settings_four) == 0


def test_reimbursement_organization_settings_happy_path_with_new_name_filter(
    client,
    api_helpers,
    enterprise_user,
):
    batch_size = DEFAULT_LIMIT
    org_name_prefix = generate_random_string(10)
    input_org_settings = _set_org_settings(batch_size, org_name_prefix)

    # exact match
    res_one = client.get(
        f'/api/v1/-/wqs/reimbursement_org?filter={{"name":"{org_name_prefix}"}}',
        headers=api_helpers.json_headers(enterprise_user),
    )
    assert res_one.status_code == 200
    content_one = api_helpers.load_json(res_one)
    assert content_one["total_results"] == batch_size
    reimbursement_org_settings_one = content_one["reimbursement_orgs"]
    output_org_settings_one = {
        (ros["reimbursement_org_settings_id"], ros["name"])
        for ros in reimbursement_org_settings_one
    }
    assert len(output_org_settings_one) == batch_size
    assert input_org_settings == output_org_settings_one

    # substring match
    res_two = client.get(
        f'/api/v1/-/wqs/reimbursement_org?filter={{"name":"{org_name_prefix[:3]}"}}',
        headers=api_helpers.json_headers(enterprise_user),
    )
    assert res_two.status_code == 200
    content_two = api_helpers.load_json(res_two)
    assert content_two["total_results"] == batch_size
    reimbursement_org_settings_two = content_two["reimbursement_orgs"]
    output_org_settings_two = {
        (ros["reimbursement_org_settings_id"], ros["name"])
        for ros in reimbursement_org_settings_two
    }
    assert len(reimbursement_org_settings_two) == batch_size
    assert input_org_settings == output_org_settings_two

    # ignore-case match
    res_three = client.get(
        f'/api/v1/-/wqs/reimbursement_org?filter={{"name":"{org_name_prefix[:3].upper()}"}}',
        headers=api_helpers.json_headers(enterprise_user),
    )
    assert res_three.status_code == 200
    content_three = api_helpers.load_json(res_three)
    assert content_three["total_results"] == batch_size
    reimbursement_org_settings_three = content_three["reimbursement_orgs"]
    output_org_settings_three = {
        (ros["reimbursement_org_settings_id"], ros["name"])
        for ros in reimbursement_org_settings_three
    }
    assert len(output_org_settings_three) == batch_size
    assert input_org_settings == output_org_settings_three

    # not match
    res_four = client.get(
        f'/api/v1/-/wqs/reimbursement_org?filter={{"name":"{org_name_prefix}lol"}}',
        headers=api_helpers.json_headers(enterprise_user),
    )
    assert res_four.status_code == 200
    content_four = api_helpers.load_json(res_four)
    assert content_four["total_results"] == 0
    reimbursement_org_settings_four = content_four["reimbursement_orgs"]
    output_org_settings_four = {
        (ros["reimbursement_org_settings_id"], ros["name"])
        for ros in reimbursement_org_settings_four
    }
    assert len(output_org_settings_four) == 0


def test_reimbursement_organization_settings_happy_path_with_multiple_filters(
    client,
    api_helpers,
    enterprise_user,
):
    batch_size = DEFAULT_LIMIT
    limit = DEFAULT_LIMIT - 10
    offset = 20
    org_name_prefix = generate_random_string(10)

    input_org_settings = _set_org_settings(
        batch_size, org_name_prefix, should_wait=True
    )

    res = client.get(
        f'/api/v1/-/wqs/reimbursement_org?filter={{"name":"{org_name_prefix.upper()}"}}&limit={limit}&offset={offset}',
        headers=api_helpers.json_headers(enterprise_user),
    )
    assert res.status_code == 200
    content = api_helpers.load_json(res)
    assert content["total_results"] == DEFAULT_LIMIT
    reimbursement_org_settings = content["reimbursement_orgs"]
    output_org_settings = {
        (ros["reimbursement_org_settings_id"], ros["name"])
        for ros in reimbursement_org_settings
    }
    assert len(output_org_settings) == DEFAULT_LIMIT - 20
    assert output_org_settings < input_org_settings

    expected_output_org_setting_names = [
        f"{org_name_prefix}_{i}" for i in range(offset, min(offset + limit, batch_size))
    ]
    for output_org_setting in output_org_settings:
        assert output_org_setting[1] in expected_output_org_setting_names


def _set_org_settings(
    batch_size: int, org_name_prefix: str, should_wait: bool = False
) -> set[tuple[str, str]]:
    ros_es = []
    for i in range(0, batch_size):
        org_name = f"{org_name_prefix}_{i}"
        if should_wait:
            time.sleep(
                1
            )  # need to sleep for 1 second so we can test which rows to return from the query which sorts the result by created_at
        ros_es.append(
            ReimbursementOrganizationSettingsFactory.create(
                name=org_name, created_at=datetime.datetime.utcnow()
            )
        )

    return {(str(ros.id), ros.name) for ros in ros_es}
