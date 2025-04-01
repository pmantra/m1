import datetime
from unittest import mock

import pytest

from learn.models import bookmarks, image, migration
from learn.models.media_type import MediaType
from learn.pytests import factories as learn_factories
from learn.services import article_thumbnail_service
from learn.services.bookmarks import BookmarksService
from models import marketing
from pytests import freezegun
from storage.connection import db


@pytest.mark.parametrize(
    "content_type",
    (
        marketing.ResourceContentTypes.article,
        marketing.ResourceContentTypes.real_talk,
        marketing.ResourceContentTypes.ask_a_practitioner,
        marketing.ResourceContentTypes.curriculum_step,
    ),
)
@mock.patch("learn.services.contentful.LibraryContentfulClient")
@mock.patch(
    "learn.services.bookmarks.article_thumbnail_service.ArticleThumbnailService"
)
@mock.patch(
    "learn.services.article_title_service.LocalizedArticleTitleService.get_values"
)
@mock.patch("learn.utils.resource_utils.ReadTimeService")
def test_get_saved_resources(
    mock_read_time_service_constructor,
    mock_article_title_cache,
    mock_article_thumbnail_service_constructor,
    _,
    content_type,
    factories,
):
    user = factories.EnterpriseUserFactory(tracks__name="fertility")
    resource1 = factories.ResourceFactory(
        webflow_url=None,
        content_type=content_type.name,
        contentful_status=migration.ContentfulMigrationStatus.LIVE,
    )
    resource2 = factories.ResourceFactory(
        webflow_url=None,
        content_type=content_type.name,
        contentful_status=migration.ContentfulMigrationStatus.LIVE,
    )
    resource3 = factories.ResourceFactory(
        webflow_url=None,
        content_type=content_type.name,
        contentful_status=migration.ContentfulMigrationStatus.LIVE,
    )

    # these cases will only happen if a resource was unpublished after the user bookmarked
    not_published_resource = factories.ResourceFactory(
        webflow_url=None, published_at=None
    )
    published_next_week_resource = factories.ResourceFactory(
        webflow_url=None,
        published_at=datetime.datetime.now() + datetime.timedelta(days=7),
    )

    with freezegun.freeze_time("2023-03-14"):
        learn_factories.MemberSavedResourceFactory(
            resource_id=resource1.id, member_id=user.id
        )

    with freezegun.freeze_time("2023-03-21"):  # more recent
        learn_factories.MemberSavedResourceFactory(
            resource_id=resource3.id, member_id=user.id
        )

    learn_factories.MemberSavedResourceFactory(
        resource_id=not_published_resource.id, member_id=user.id
    )
    learn_factories.MemberSavedResourceFactory(
        resource_id=published_next_week_resource.id, member_id=user.id
    )

    mock_read_time_service_constructor.return_value.get_values_without_filtering.return_value = {
        resource1.slug: 1,
        resource3.slug: -1,
    }

    mock_article_title_cache.return_value = {
        resource1.slug: "New title from contentful 1",
        resource3.slug: "New title from contentful 3",
    }

    resource1.estimated_read_time_minutes = 1
    resource1.media_type = MediaType.ARTICLE
    resource3.media_type = MediaType.VIDEO

    mock_article_thumbnail_service_constructor.return_value.get_thumbnails_for_resources.side_effect = lambda _: [
        __build_resource_with_thumbnail(resource1),
        __build_resource_with_thumbnail(resource3),
    ]

    saved_resources = BookmarksService().get_saved_resources(user.id)
    assert len(saved_resources) == 2

    assert saved_resources[0].slug == resource1.slug
    assert saved_resources[1].slug == resource3.slug

    assert saved_resources[0].title == "New title from contentful 1"
    assert saved_resources[1].title == "New title from contentful 3"

    assert saved_resources[0].content_type == resource1.content_type
    assert saved_resources[1].content_type == resource3.content_type

    saved_resource_slugs = [resource.slug for resource in saved_resources]
    assert resource2.slug not in saved_resource_slugs
    assert not_published_resource not in saved_resource_slugs
    assert published_next_week_resource not in saved_resource_slugs

    mock_read_time_service_constructor.return_value.get_values_without_filtering.assert_called_once_with(
        [resource3.slug, resource1.slug]
    )

    mock_article_thumbnail_service_constructor.return_value.get_thumbnails_for_resources.assert_called_once_with(
        [resource3, resource1]
    )

    mock_article_title_cache.assert_called_once_with(
        identifier_values=[resource3.slug, resource1.slug]
    )


# it's not actually possible to save an on-demand class, but let's make sure things won't break just in case we ever
# want to allow that
@mock.patch("learn.services.contentful.LibraryContentfulClient")
@mock.patch(
    "learn.services.bookmarks.article_thumbnail_service.ArticleThumbnailService"
)
@mock.patch("learn.utils.resource_utils.ReadTimeService")
def test_get_saved_resources_on_demand_class(
    mock_read_time_service_constructor,
    mock_article_thumbnail_service_constructor,
    _,
    factories,
):
    user = factories.EnterpriseUserFactory(tracks__name="fertility")
    resource = factories.ResourceFactory(
        webflow_url=None,
        content_type=marketing.ResourceContentTypes.on_demand_class.name,
    )
    resource_with_thumbnail = __build_resource_with_thumbnail(resource)
    resource_with_thumbnail.media_type = MediaType.ON_DEMAND_CLASS

    with freezegun.freeze_time("2023-03-14"):  # :🥧
        learn_factories.MemberSavedResourceFactory(
            resource_id=resource.id, member_id=user.id
        )

    mock_read_time_service_constructor.return_value.get_values_without_filtering.return_value = (
        {}
    )
    mock_article_thumbnail_service_constructor.return_value.get_thumbnails_for_resources.return_value = [
        resource_with_thumbnail
    ]

    saved_resources = BookmarksService().get_saved_resources(user.id)
    assert len(saved_resources) == 1
    assert saved_resources[0] == resource_with_thumbnail

    mock_read_time_service_constructor.return_value.get_values_without_filtering.assert_called_once_with(
        []
    )
    resource.media_type = MediaType.ON_DEMAND_CLASS
    mock_article_thumbnail_service_constructor.return_value.get_thumbnails_for_resources.assert_called_once_with(
        [resource]
    )


# not sure if it's possible to save a non-Contentful resource but what the hell
@mock.patch("learn.services.contentful.LibraryContentfulClient")
@mock.patch(
    "learn.services.bookmarks.article_thumbnail_service.ArticleThumbnailService"
)
@mock.patch("learn.utils.resource_utils.ReadTimeService")
def test_get_saved_resources_not_article(
    mock_read_time_service_constructor,
    mock_article_thumbnail_service_constructor,
    _,
    factories,
):
    user = factories.EnterpriseUserFactory(tracks__name="fertility")
    resource = factories.ResourceFactory(
        webflow_url=None,
        content_type=marketing.ResourceContentTypes.article.name,
        contentful_status=migration.ContentfulMigrationStatus.NOT_STARTED,
    )
    resource_with_thumbnail = __build_resource_with_thumbnail(resource)

    with freezegun.freeze_time("2023-03-14"):  # :🥧
        learn_factories.MemberSavedResourceFactory(
            resource_id=resource.id, member_id=user.id
        )

    mock_read_time_service_constructor.return_value.get_values_without_filtering.return_value = (
        {}
    )
    mock_article_thumbnail_service_constructor.return_value.get_thumbnails_for_resources.return_value = [
        resource_with_thumbnail
    ]

    saved_resources = BookmarksService().get_saved_resources(user.id)
    assert len(saved_resources) == 1
    assert saved_resources[0] == resource_with_thumbnail

    mock_read_time_service_constructor.return_value.get_values_without_filtering.assert_called_once_with(
        []
    )


def test_delete_bookmark(factories):
    user = factories.EnterpriseUserFactory(tracks__name="fertility")
    resource1 = factories.ResourceFactory(webflow_url=None)

    learn_factories.MemberSavedResourceFactory(
        resource_id=resource1.id, member_id=user.id
    )

    was_something_to_delete = BookmarksService().delete_bookmark(user.id, resource1)
    assert was_something_to_delete is True

    # run it again
    was_something_to_delete = BookmarksService().delete_bookmark(user.id, resource1)
    assert was_something_to_delete is False


def test_get_bookmark(factories):
    user = factories.EnterpriseUserFactory(tracks__name="fertility")
    resource1 = factories.ResourceFactory(webflow_url=None)

    learn_factories.MemberSavedResourceFactory(
        resource_id=resource1.id, member_id=user.id
    )

    saved_resource = BookmarksService().get_bookmark(user.id, resource1)
    assert saved_resource.resource_id == resource1.id
    assert saved_resource.member_id == user.id


def test_get_bookmark_not_found(factories):
    user = factories.EnterpriseUserFactory(tracks__name="fertility")
    resource_notsaved = factories.ResourceFactory(webflow_url=None)

    saved_resource = BookmarksService().get_bookmark(user.id, resource_notsaved)
    assert saved_resource is None


def test_save_bookmark(factories):
    user = factories.EnterpriseUserFactory(tracks__name="fertility")
    resource1 = factories.ResourceFactory(webflow_url=None)

    saved_resource = BookmarksService().save_bookmark(user.id, resource1)
    assert saved_resource.member_id == user.id
    assert saved_resource.resource_id == resource1.id


def test_save_bookmark_duplicate_entry(factories):
    user = factories.EnterpriseUserFactory(tracks__name="fertility")
    resource1 = factories.ResourceFactory(webflow_url=None)

    db.session.add(
        bookmarks.MemberSavedResource(member_id=user.id, resource_id=resource1.id)
    )
    db.session.commit()

    saved_resource = BookmarksService().save_bookmark(user.id, resource1)
    assert saved_resource.member_id == user.id
    assert saved_resource.resource_id == resource1.id


def __build_resource_with_thumbnail(
    resource: marketing.Resource,
) -> article_thumbnail_service.ResourceWithThumbnail:
    return article_thumbnail_service.ResourceWithThumbnail(
        id=str(resource.id),
        slug=resource.slug,
        title=resource.title,
        article_type=resource.article_type,
        image=image.Image(url="https://example.com", description="This is an example"),
        content_type=resource.content_type,
        content_url=resource.content_url,
        subhead=resource.subhead,
        estimated_read_time_minutes=resource.estimated_read_time_minutes,
    )
