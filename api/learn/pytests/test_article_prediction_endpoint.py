from unittest.mock import Mock, patch

import pytest

from learn.models.article_type import ArticleType
from learn.models.media_type import MediaType


@pytest.fixture
def resource_1():

    mock_resource = Mock()
    mock_resource.title = "Test Article"
    mock_resource.article_type = ArticleType.RICH_TEXT.value
    mock_resource.content_type = MediaType.ARTICLE.value

    return mock_resource


@pytest.fixture
def mock_article():
    mock = Mock()

    mock.get_value.return_value = {
        "title": "Baby Proof Your Home",
        "slug": "how-to-baby-proof-your-home",
        "article_type": ArticleType.RICH_TEXT,
        "related_reads": [
            {
                "slug": "related-read-1",
                "title": "Related Read 1",
                "thumbnail": {"url": "thumbnail-1-url"},
            },
            {
                "slug": "related-read-2",
                "title": "Related Read 2",
                "thumbnail": {"url": "thumbnail-2-url"},
            },
        ],
    }
    return mock


@patch("views.content.EnterprisePublicContentResource.user", return_value=True)
@patch(
    "views.content.EnterprisePublicContentResource._EnterprisePublicContentResource__save_resource_viewed_time",
    return_value=True,
)
@patch(
    "care_plans.care_plans_service.CarePlansService.send_content_completed",
    return_value=True,
)
@patch("views.content.enable_predicted_related_reads", return_value=False)
@patch("views.content.article_service.ArticleService")
@patch("models.marketing.Resource.get_public_published_resource_by_slug")
def test_enterprise_public_content_resource_disabled_related_reads(
    mock_get_resource,
    article_service_mock,
    related_reads_enabled,
    save_resource_view,
    user,
    send_content_completed,
    client,
    resource_1,
    mock_article,
):
    # Set up the mock
    mock_get_resource.return_value = resource_1
    article_service_mock.return_value = mock_article

    # Make the request to the endpoint
    response = client.get(
        "/api/v1/content/resources/public/how-to-baby-proof-your-home"
    )

    # Assertions
    assert response.status_code == 200
    data = response.get_json()
    assert data["title"] == "Baby Proof Your Home"
    assert data["content_type"] == "article"

    related_reads = data["related_reads"]
    assert related_reads is not None
    assert related_reads[0]["title"] == "Related Read 1"
    assert related_reads[0]["slug"] == "related-read-1"
    assert related_reads[0]["thumbnail"]["url"] == "thumbnail-1-url"
    assert len(related_reads) == 2


@patch("views.content.EnterprisePublicContentResource.user", return_value=True)
@patch(
    "views.content.EnterprisePublicContentResource._EnterprisePublicContentResource__save_resource_viewed_time",
    return_value=True,
)
@patch(
    "care_plans.care_plans_service.CarePlansService.send_content_completed",
    return_value=True,
)
@patch("views.content.enable_predicted_related_reads", return_value=True)
@patch("views.content.article_service.ArticleService")
@patch("models.marketing.Resource.get_public_published_resource_by_slug")
def test_enterprise_public_content_resource_enabled_related_reads(
    mock_get_resource,
    mock_article_service_mock,
    related_reads_enabled,
    save_resource_view,
    user,
    send_content_completed,
    client,
    resource_1,
    mock_article,
    thumbnail_service_mock,
    title_service_mock,
    related_reads_list,
):

    # Set up the mock
    mock_get_resource.return_value = resource_1
    mock_article_service_mock.return_value = mock_article
    # Make the request to the endpoint
    response = client.get(
        "/api/v1/content/resources/public/how-to-baby-proof-your-home"
    )

    # Assertions
    assert response.status_code == 200
    data = response.get_json()
    assert data["title"] == "Baby Proof Your Home"
    assert data["content_type"] == "article"

    related_reads = data["related_reads"]
    assert related_reads is not None

    # Test that related reads were not overwritten
    assert related_reads[0]["title"] != "Related Read 1"
    assert related_reads[0]["slug"] != "related-read-1"
    assert related_reads[0]["thumbnail"]["url"] != "thumbnail-1-url"
    assert len(related_reads) == 3

    for i, result_related_read in enumerate(related_reads_list):
        assert result_related_read.slug == related_reads[i]["slug"]
        assert result_related_read.title == related_reads[i]["title"]
        assert result_related_read.thumbnail.url == related_reads[i]["thumbnail"]["url"]
