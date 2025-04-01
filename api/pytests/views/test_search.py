from json import dumps
from unittest.mock import Mock, patch

import pytest

from learn.models.media_type import MediaType


@pytest.fixture
def mock_read_time_service():
    with patch("views.search.ReadTimeService") as mock_read_time_service_class:
        mock_read_time_service = Mock()
        mock_read_time_service_class.return_value = mock_read_time_service
        yield mock_read_time_service


@pytest.fixture
def post_data():
    return dumps({"query": "test", "request_id": "test", "document_id": "test"})


def build_meta(total_results):
    return {
        "alerts": [],
        "engine": {"name": "test-resource-index", "type": "default"},
        "page": {
            "current": 1,
            "size": 10,
            "total_pages": int(total_results / 10),
            "total_results": total_results,
        },
        "request_id": "7c96f34b-e623-4a2f-bf00-2a87485cbceb",
        "warnings": [],
    }


def build_indexed_resource(_id):
    return {
        "_meta": {"engine": "test-engine", "id": f"resource:{_id}", "score": 1},
        "body_content": {"snippet": "<em>a</em> <em>match</em> blah blah blah"},
        "id": {"raw": f"resource:{_id}"},
        "raw_id": {"raw": str(_id)},
        "image_storage_key": {"raw": "test-storage-key"},
        "title": {"raw": "Example resource"},
        "slug": {"raw": f"example-resource-{_id}"},
    }


def test_unauthenticated_user(client, api_helpers):
    res = client.get(
        "/api/v1/search/resources?query=test", headers=api_helpers.json_headers()
    )
    assert res.status_code == 401


def test_search_with_no_query(client, api_helpers, default_user):
    res = client.get(
        "/api/v1/search/resources", headers=api_helpers.json_headers(default_user)
    )
    assert res.status_code == 400


@patch("views.search.app_search_enabled", return_value=False)
def test_authenticated_user_with_search_disabled(_, client, api_helpers, default_user):
    res = client.get(
        "/api/v1/search/resources?query=test",
        headers=api_helpers.json_headers(default_user),
    )
    assert res.status_code == 200
    assert res.json["total_results"] == 0


@patch("views.search.app_search_enabled", return_value=True)
@patch("views.search.get_client")
def test_authenticated_user_with_search_enabled(
    client_mock, _, client, api_helpers, default_user, mock_read_time_service
):
    resources = [build_indexed_resource(i) for i in range(0, 3)]
    return_value = {
        "meta": build_meta(3),
        "results": resources,
    }
    client_mock.return_value.search.return_value = return_value
    mock_read_time_service.get_values_without_filtering.return_value = {
        resources[0]["slug"]["raw"]: 42,
        resources[1]["slug"]["raw"]: -1,
    }

    res = client.get(
        "/api/v1/search/resources?query=test",
        headers=api_helpers.json_headers(default_user),
    )
    assert res.status_code == 200
    assert res.json["total_results"] == 3
    assert len(res.json["results"]) == 3
    assert res.json["results"][0]["data"]["id"] == 0
    assert res.json["request_id"] is not None

    assert res.json["results"][0]["data"]["estimated_read_time_minutes"] == 42
    assert res.json["results"][0]["data"]["media_type"] == MediaType.ARTICLE.value
    assert "document_id" not in res.json["results"][0]["data"]
    assert res.json["results"][0]["document_id"] == "resource:0"
    assert res.json["results"][1]["data"]["estimated_read_time_minutes"] is None
    assert res.json["results"][1]["data"]["media_type"] == MediaType.VIDEO.value
    assert "document_id" not in res.json["results"][1]["data"]
    assert res.json["results"][1]["document_id"] == "resource:1"
    assert res.json["results"][2]["data"]["estimated_read_time_minutes"] is None
    assert res.json["results"][2]["data"]["media_type"] is None
    assert "document_id" not in res.json["results"][2]["data"]
    assert res.json["results"][2]["document_id"] == "resource:2"

    mock_read_time_service.get_values_without_filtering.assert_called_once_with(
        slugs=[resource["slug"]["raw"] for resource in resources]
    )


@patch("views.search.app_search_enabled", return_value=True)
@patch("views.search.get_client")
def test_authenticated_user_with_search_enabled_image_url(
    client_mock, _, client, api_helpers, default_user, mock_read_time_service
):
    resource = build_indexed_resource(1)
    img_url = "https://i.mg/img.img"
    resource["image_url"] = {"raw": img_url}
    return_value = {"meta": build_meta(1), "results": [resource]}
    client_mock.return_value.search.return_value = return_value
    mock_read_time_service.get_values_without_filtering.return_value = {}

    res = client.get(
        "/api/v1/search/resources?query=test",
        headers=api_helpers.json_headers(default_user),
    )

    assert res.json["results"][0]["data"]["image_url"] == img_url


@patch("views.search.app_search_enabled", return_value=True)
@patch("views.search.get_client")
def test_authenticated_user_with_search_enabled_article_type(
    client_mock, _, client, api_helpers, default_user, mock_read_time_service
):
    resource = build_indexed_resource(1)
    article_type = "html"
    resource["article_type"] = {"raw": article_type}
    return_value = {"meta": build_meta(1), "results": [resource]}
    client_mock.return_value.search.return_value = return_value
    mock_read_time_service.get_values_without_filtering.return_value = {}

    res = client.get(
        "/api/v1/search/resources?query=test",
        headers=api_helpers.json_headers(default_user),
    )

    assert res.json["results"][0]["data"]["type"] == article_type


def test_click_unauthenticated_user(client, post_data, api_helpers, default_user):
    res = client.post(
        "/api/v1/search/resources/click",
        headers=api_helpers.json_headers(),
        data=post_data,
    )
    assert res.status_code == 401


@patch("views.search.app_search_enabled", return_value=False)
def test_click_authenticated_user(_, client, post_data, api_helpers, default_user):
    res = client.post(
        "/api/v1/search/resources/click",
        headers=api_helpers.json_headers(default_user),
        data=post_data,
    )
    assert res.status_code == 200


@patch("views.search.app_search_enabled", return_value=True)
@patch("views.search.get_client")
def test_click_authenticated_user_with_search_enabled(
    client_mock, _, client, post_data, api_helpers, default_user
):
    client_mock.return_value.click.return_value = True
    res = client.post(
        "/api/v1/search/resources/click",
        headers=api_helpers.json_headers(default_user),
        data=post_data,
    )
    assert res.status_code == 200


@patch("views.search.app_search_enabled", return_value=True)
def test_click_authenticated_user_with_invalid_body(
    _, client, api_helpers, default_user
):
    invalid_bodies = [
        dict(query="test", request_id="test"),
        dict(request_id="test", document_id="test"),
        dict(query="test", document_id="test"),
    ]
    for body in invalid_bodies:
        res = client.post(
            "/api/v1/search/resources/click",
            headers=api_helpers.json_headers(default_user),
            data=dumps(body),
        )
        assert res.status_code == 400
