# there are legacy tests in /tests/test_resources.py
import datetime
from unittest import mock

import pytest

from learn.models import article_type, migration
from learn.models.media_type import MediaType
from learn.services import article_thumbnail_service
from models import marketing


@mock.patch("views.resources.article_thumbnail_service")
@mock.patch(
    "learn.services.article_title_service.LocalizedArticleTitleService.get_values"
)
@mock.patch("learn.utils.resource_utils.ReadTimeService")
@mock.patch("learn.services.contentful.LibraryContentfulClient")
class TestGetResources:
    @pytest.fixture(autouse=True)
    def _setup(self, factories):
        self.user = factories.EnterpriseUserFactory.create()
        self.tag = factories.TagFactory.create()
        tag2 = factories.TagFactory.create()
        self.resource1 = factories.ResourceFactory.create(
            tags=[self.tag],
            published_at=datetime.datetime.now() - datetime.timedelta(weeks=1),
            resource_type=marketing.ResourceTypes.ENTERPRISE,
            contentful_status=migration.ContentfulMigrationStatus.LIVE,
        )
        self.resource2 = factories.ResourceFactory.create(
            tags=[self.tag],
            published_at=datetime.datetime.now() - datetime.timedelta(weeks=2),
            resource_type=marketing.ResourceTypes.ENTERPRISE,
            contentful_status=migration.ContentfulMigrationStatus.LIVE,
        )
        self.resource3 = factories.ResourceFactory.create(
            tags=[tag2],
            published_at=datetime.datetime.now() - datetime.timedelta(weeks=3),
            resource_type=marketing.ResourceTypes.ENTERPRISE,
            contentful_status=migration.ContentfulMigrationStatus.NOT_STARTED,
        )

    @pytest.mark.parametrize(
        "content_type",
        (
            marketing.ResourceContentTypes.article,
            marketing.ResourceContentTypes.real_talk,
            marketing.ResourceContentTypes.ask_a_practitioner,
            marketing.ResourceContentTypes.curriculum_step,
        ),
    )
    def test_get_resources_has_article_type(
        self,
        _,
        mock_read_time_service_constructor,
        mock_article_title_cache,
        cache_mock,
        client,
        api_helpers,
        factories,
        content_type: marketing.ResourceContentTypes,
    ):
        tag = factories.TagFactory.create()
        resource1 = factories.ResourceFactory.create(
            tags=[tag],
            published_at=datetime.datetime.now() - datetime.timedelta(weeks=1),
            resource_type=marketing.ResourceTypes.ENTERPRISE,
            content_type=content_type.name,
            contentful_status=migration.ContentfulMigrationStatus.NOT_STARTED,
        )
        resource2 = factories.ResourceFactory.create(
            tags=[tag],
            published_at=datetime.datetime.now() - datetime.timedelta(weeks=2),
            resource_type=marketing.ResourceTypes.ENTERPRISE,
            content_type=content_type.name,
            contentful_status=migration.ContentfulMigrationStatus.IN_PROGRESS,
        )
        resource3 = factories.ResourceFactory.create(
            tags=[tag],
            published_at=datetime.datetime.now() - datetime.timedelta(weeks=3),
            resource_type=marketing.ResourceTypes.ENTERPRISE,
            content_type=content_type.name,
            contentful_status=migration.ContentfulMigrationStatus.LIVE,
        )
        resource4 = factories.ResourceFactory.create(
            tags=[tag],
            published_at=datetime.datetime.now() - datetime.timedelta(weeks=4),  # noqa
            resource_type=marketing.ResourceTypes.ENTERPRISE,
            content_type=content_type.name,
            contentful_status=migration.ContentfulMigrationStatus.LIVE,
        )
        thumb_service_mock = mock.Mock()
        cache_mock.ArticleThumbnailService.return_value = thumb_service_mock
        resource_with_thumbnail_3 = _make_resource_with_thumbnail(resource3)
        resource_with_thumbnail_3.estimated_read_time_minutes = 420
        resource_with_thumbnail_3.media_type = MediaType.ARTICLE
        resource_with_thumbnail_4 = _make_resource_with_thumbnail(resource4)
        resource_with_thumbnail_4.media_type = MediaType.VIDEO
        thumb_service_mock.get_thumbnails_for_resources.return_value = [
            _make_resource_with_thumbnail(resource1),
            _make_resource_with_thumbnail(resource2),
            resource_with_thumbnail_3,
            resource_with_thumbnail_4,
        ]

        mock_read_time_service_constructor.return_value.get_values_without_filtering.return_value = {
            resource3.slug: 420,
            resource4.slug: -1,
        }

        # this is the most common request from the front ends
        # iOS sorts the other way but that's not relevant to this case
        res = client.get(
            f"/api/v1/resources?tags={tag.name}&limit=500&offset=0",
            headers=api_helpers.json_headers(user=self.user),
        )
        data = api_helpers.load_json(res)

        thumb_service_mock.get_thumbnails_for_resources.assert_called_with(
            [resource1, resource2, resource3, resource4]
        )
        mock_read_time_service_constructor.return_value.get_values_without_filtering.assert_called_once_with(
            [resource3.slug, resource4.slug]
        )

        assert data[0]["slug"] == resource1.slug
        assert data[0]["type"] == article_type.ArticleType.HTML

        assert data[1]["slug"] == resource2.slug
        assert data[1]["type"] == article_type.ArticleType.HTML

        assert data[2]["slug"] == resource3.slug
        assert data[2]["type"] == article_type.ArticleType.RICH_TEXT
        assert data[2]["estimated_read_time_minutes"] == 420
        assert data[2]["media_type"] == MediaType.ARTICLE

        assert data[3]["slug"] == resource4.slug
        assert data[3]["type"] == article_type.ArticleType.RICH_TEXT
        assert data[3]["estimated_read_time_minutes"] is None
        assert data[3]["media_type"] == MediaType.VIDEO

    def test_get_resources_images(
        self,
        _,
        mock_read_time_service_constructor,
        mock_article_title_cache,
        cache_mock,
        client,
        api_helpers,
        factories,
    ):
        tag = factories.TagFactory.create()
        resource = factories.ResourceFactory.create(
            tags=[tag],
            published_at=datetime.datetime.now() - datetime.timedelta(weeks=1),
            resource_type=marketing.ResourceTypes.ENTERPRISE,
            contentful_status=migration.ContentfulMigrationStatus.LIVE,
        )
        image_mock = mock.Mock()
        url = "same.url/sorry.jpg"
        image_mock.asset_url.return_value = url
        resource_with_thumb = _make_resource_with_thumbnail(resource)
        resource_with_thumb.image = image_mock

        thumb_service_mock = mock.Mock()
        cache_mock.ArticleThumbnailService.return_value = thumb_service_mock
        thumb_service_mock.get_thumbnails_for_resources.return_value = [
            resource_with_thumb
        ]

        mock_read_time_service_constructor.return_value.get_values.return_value = {}

        res = client.get(
            f"/api/v1/resources?tags={tag.name}&limit=500&offset=0",
            headers=api_helpers.json_headers(user=self.user),
        )
        data = api_helpers.load_json(res)

        thumb_service_mock.get_thumbnails_for_resources.assert_called_with([resource])
        call1 = mock.call(None, None)
        call2 = mock.call(428, 760, smart=False)
        call3 = mock.call(90, 120, smart=False)
        for img_type in ["original", "hero", "thumbnail"]:
            assert data[0]["image"][img_type] == url
        image_mock.asset_url.assert_has_calls([call1, call2, call3])

    def test_no_params_list(
        self,
        _,
        mock_read_time_service_constructor,
        mock_article_title_cache,
        cache_mock,
        factories,
        client,
        api_helpers,
    ):
        # unpublished resource, shouldn't be returned
        factories.ResourceFactory(
            resource_type=marketing.ResourceTypes.ENTERPRISE,
            content_type=marketing.ResourceContentTypes.article.name,
            published_at=None,
        )
        # published in the future, shouldn't be returned yet
        factories.ResourceFactory(
            resource_type=marketing.ResourceTypes.ENTERPRISE,
            content_type=marketing.ResourceContentTypes.article.name,
            published_at=datetime.datetime.now() + datetime.timedelta(weeks=2),
        )
        # private resource, shouldn't be returned
        factories.ResourceFactory(
            resource_type=marketing.ResourceTypes.PRIVATE,
            content_type=marketing.ResourceContentTypes.article.name,
        )

        thumb_service_mock = mock.Mock()
        cache_mock.ArticleThumbnailService.return_value = thumb_service_mock
        thumb_service_mock.get_thumbnails_for_resources.return_value = [
            _make_resource_with_thumbnail(self.resource1),
            _make_resource_with_thumbnail(self.resource2),
            _make_resource_with_thumbnail(self.resource3),
        ]

        mock_read_time_service_constructor.return_value.get_values.return_value = {}

        res = client.get(
            "/api/v1/resources",
            headers=api_helpers.json_headers(user=self.user),
        )
        data = api_helpers.load_json(res)

        thumb_service_mock.get_thumbnails_for_resources.assert_called_with(
            [self.resource1, self.resource2, self.resource3]
        )

        assert data[0] == _make_expected_resource(self.resource1)
        assert data[1] == _make_expected_resource(self.resource2)
        assert data[2] == _make_expected_resource(self.resource3)

    def test_get_resources_limit(
        self,
        _,
        mock_read_time_service_constructor,
        mock_article_title_cache,
        cache_mock,
        client,
        api_helpers,
    ):
        thumb_service_mock = mock.Mock()
        cache_mock.ArticleThumbnailService.return_value = thumb_service_mock
        thumb_service_mock.get_thumbnails_for_resources.return_value = [
            _make_resource_with_thumbnail(self.resource1),
        ]
        mock_read_time_service_constructor.return_value.get_values.return_value = {}

        client.get(
            f"/api/v1/resources?tags={self.tag.name}&limit=1",
            headers=api_helpers.json_headers(user=self.user),
        )

        thumb_service_mock.get_thumbnails_for_resources.assert_called_with(
            [self.resource1]
        )

    def test_get_resources_offset(
        self,
        _,
        mock_read_time_service_constructor,
        mock_article_title_cache,
        cache_mock,
        client,
        api_helpers,
    ):
        thumb_service_mock = mock.Mock()
        cache_mock.ArticleThumbnailService.return_value = thumb_service_mock
        thumb_service_mock.get_thumbnails_for_resources.return_value = [
            _make_resource_with_thumbnail(self.resource2),
        ]
        mock_read_time_service_constructor.return_value.get_values.return_value = {}

        client.get(
            f"/api/v1/resources?tags={self.tag.name}&offset=1",
            headers=api_helpers.json_headers(user=self.user),
        )

        thumb_service_mock.get_thumbnails_for_resources.assert_called_with(
            [self.resource2]
        )

    def test_get_resources_offset_plus_limit(
        self,
        _,
        mock_read_time_service_constructor,
        mock_article_title_cache,
        cache_mock,
        client,
        api_helpers,
    ):
        thumb_service_mock = mock.Mock()
        cache_mock.ArticleThumbnailService.return_value = thumb_service_mock
        thumb_service_mock.get_thumbnails_for_resources.return_value = [
            _make_resource_with_thumbnail(self.resource3),
        ]
        mock_read_time_service_constructor.return_value.get_values.return_value = {}

        client.get(
            "/api/v1/resources?limit=1&offset=2",
            headers=api_helpers.json_headers(user=self.user),
        )

        thumb_service_mock.get_thumbnails_for_resources.assert_called_with(
            [self.resource3]
        )

    def test_get_resources_order(
        self,
        _,
        mock_read_time_service_constructor,
        mock_article_title_cache,
        cache_mock,
        client,
        api_helpers,
    ):
        thumb_service_mock = mock.Mock()
        cache_mock.ArticleThumbnailService.return_value = thumb_service_mock
        thumb_service_mock.get_thumbnails_for_resources.return_value = [
            _make_resource_with_thumbnail(self.resource2),
            _make_resource_with_thumbnail(self.resource1),
        ]
        mock_read_time_service_constructor.return_value.get_values.return_value = {}

        client.get(
            f"/api/v1/resources?tags={self.tag.name}&order_direction=asc",
            headers=api_helpers.json_headers(user=self.user),
        )

        thumb_service_mock.get_thumbnails_for_resources.assert_called_with(
            [self.resource2, self.resource1]
        )

    def test_get_resources_slugs(
        self,
        _,
        mock_read_time_service_constructor,
        mock_article_title_cache,
        cache_mock,
        client,
        api_helpers,
        factories,
    ):
        thumb_service_mock = mock.Mock()
        cache_mock.ArticleThumbnailService.return_value = thumb_service_mock
        thumb_service_mock.get_thumbnails_for_resources.return_value = [
            _make_resource_with_thumbnail(self.resource1),
            _make_resource_with_thumbnail(self.resource2),
        ]
        mock_read_time_service_constructor.return_value.get_values.return_value = {}

        response = client.get(
            f"/api/v1/resources?slugs={self.resource1.slug},{self.resource2.slug}",
            headers=api_helpers.json_headers(user=self.user),
        )
        data = api_helpers.load_json(response)

        assert len(data) == 2
        assert data[0]["slug"] == self.resource1.slug
        assert data[1]["slug"] == self.resource2.slug

    def test_get_resources_uses_contentful_titles(
        self,
        _,
        mock_read_time_service_constructor,
        get_article_title_values_mock,
        cache_mock,
        client,
        api_helpers,
        factories,
    ):
        get_article_title_values_mock.return_value = {
            self.resource1.slug: "New title from contentful 1",
            self.resource2.slug: "New title from contentful 2",
        }

        thumb_service_mock = mock.Mock()
        cache_mock.ArticleThumbnailService.return_value = thumb_service_mock

        thumb_service_mock.get_thumbnails_for_resources.side_effect = lambda _: [
            _make_resource_with_thumbnail(self.resource1),
            _make_resource_with_thumbnail(self.resource2),
            _make_resource_with_thumbnail(self.resource3),
        ]
        mock_read_time_service_constructor.return_value.get_values.return_value = {}

        response = client.get(
            f"/api/v1/resources?slugs={self.resource1.slug},{self.resource2.slug},{self.resource3.slug}",
            headers=api_helpers.json_headers(user=self.user),
        )
        data = api_helpers.load_json(response)

        assert len(data) == 3
        assert data[0]["slug"] == self.resource1.slug
        assert data[1]["slug"] == self.resource2.slug
        assert data[2]["slug"] == self.resource3.slug

        assert data[0]["title"] == "New title from contentful 1"
        assert data[1]["title"] == "New title from contentful 2"
        assert data[2]["title"] == self.resource3.title

        get_article_title_values_mock.assert_called_once_with(
            identifier_values=[self.resource1.slug, self.resource2.slug]
        )

    def test_get_resources_too_many_slugs(
        self,
        _,
        mock_read_time_service_constructor,
        mock_article_title_cache,
        cache_mock,
        client,
        api_helpers,
        factories,
    ):
        response = client.get(
            f"/api/v1/resources?slugs={','.join([str(i) for i in range(105)])}",
            headers=api_helpers.json_headers(user=self.user),
        )
        data = api_helpers.load_json(response)

        assert data == {
            "errors": [
                {
                    "status": 400,
                    "title": "{'slugs': ['slugs must have between 1 and 104 values, inclusive.']}",
                }
            ]
        }


def _make_expected_resource(r):
    return {
        "assessment_id": None,
        "resource_id": r.id,
        "content_type": r.content_type,
        "title": r.title,
        "description": None,
        "slug": r.slug,
        "image": (
            {
                "original": r.image.asset_url(None, None),
                "hero": r.image.asset_url(428, 760, smart=False),
                "thumbnail": r.image.asset_url(90, 120, smart=False),
            }
            if r.image
            else None
        ),
        "type": r.article_type.value,
        "estimated_read_time_minutes": None,
        "media_type": None,
    }


def _make_resource_with_thumbnail(resource):
    return article_thumbnail_service.ResourceWithThumbnail(
        id=resource.id,
        slug=resource.slug,
        title=resource.title,
        article_type=resource.article_type,
        image=resource.image,
        content_type=resource.content_type,
        content_url=resource.content_url,
        subhead=resource.subhead,
    )
