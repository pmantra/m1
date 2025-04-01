import datetime
from unittest.mock import patch

import pytest as pytest

from learn.models.article_type import ArticleType
from learn.models.migration import ContentfulMigrationStatus
from models.marketing import Resource, ResourceTypes
from storage.connection import db


def create_indexable_resource(factories):
    return factories.ResourceFactory(
        content_type="article",
        published_at=datetime.datetime.now() - datetime.timedelta(days=1),
        # Otherwise this method actually tries to get content from the Faker url
        webflow_url=None,
        tracks=["pregnancy"],
        tags=[factories.TagFactory()],
    )


@patch("utils.index_resources.remove_from_index")
def test_remove_from_index_on_delete(remove_from_index_mock, factories):
    resource = create_indexable_resource(factories)
    db.session.delete(resource)
    db.session.commit()
    remove_from_index_mock.assert_called()


@patch("utils.index_resources.remove_from_index")
def test_remove_from_index_if_not_published(remove_from_index_mock, factories):
    resource = create_indexable_resource(factories)
    resource.published_at = datetime.datetime.now() + datetime.timedelta(days=1)
    db.session.add(resource)
    db.session.commit()
    remove_from_index_mock.assert_called()


@patch("utils.index_resources.remove_from_index")
def test_remove_from_index_if_wrong_type(remove_from_index_mock, factories):
    resource = create_indexable_resource(factories)
    resource.content_type = "connected_content"
    db.session.add(resource)
    db.session.commit()
    remove_from_index_mock.assert_called()


@patch("utils.index_resources.remove_from_index")
def test_remove_from_index_if_no_tracks(remove_from_index_mock, factories):
    resource = create_indexable_resource(factories)
    resource.allowed_tracks = []
    db.session.add(resource)
    db.session.commit()
    remove_from_index_mock.assert_called()


@patch("utils.index_resources.remove_from_index")
def test_remove_from_index_if_no_tags(remove_from_index_mock, factories):
    resource = create_indexable_resource(factories)
    resource.tags = []
    db.session.add(resource)
    db.session.commit()
    remove_from_index_mock.assert_called()


@patch("utils.index_resources.remove_from_index")
def test_do_not_remove_from_index_if_no_tags_if_on_demand_class(
    remove_from_index_mock, factories
):
    resource = factories.ResourceFactory(
        content_type="on_demand_class",
        published_at=datetime.datetime.now() - datetime.timedelta(days=1),
        webflow_url=None,
        tracks=["pregnancy"],
        tags=[factories.TagFactory()],
    )
    resource.tags = []
    db.session.add(resource)
    db.session.commit()
    remove_from_index_mock.assert_not_called()


@patch("utils.index_resources.remove_from_index")
def test_do_not_remove_from_index_if_unneeded(remove_from_index_mock, factories):
    resource = create_indexable_resource(factories)
    resource.title = "I'm just a new title, don't remove me from the index!"
    db.session.add(resource)
    db.session.commit()
    remove_from_index_mock.assert_not_called()


@patch("utils.index_resources.index_contentful_resource")
def test_add_to_index_if_eligible_and_contentful_live(index_contentful_mock, factories):
    resource = create_indexable_resource(factories)
    resource.contentful_status = ContentfulMigrationStatus.LIVE.value
    db.session.add(resource)
    db.session.commit()
    index_contentful_mock.assert_called_with(resource)


def test_get_public_published_resource_by_slug(factories):
    public_published_article = factories.ResourceFactory(
        content_type="article",
        published_at=datetime.datetime.now() - datetime.timedelta(days=1),
        webflow_url=1,
    )

    found_public_published_article = Resource.get_public_published_resource_by_slug(
        public_published_article.slug
    )
    assert found_public_published_article is not None
    assert found_public_published_article == public_published_article


def test_get_public_published_resource_by_slug_not_published(factories):
    non_published_article = factories.ResourceFactory(
        content_type="article",
        published_at=datetime.datetime.now() + datetime.timedelta(days=1),  # future
        webflow_url=1,
    )

    non_published_article_not_found = Resource.get_public_published_resource_by_slug(
        non_published_article.slug
    )
    assert non_published_article_not_found is None


def test_get_public_published_resource_by_slug_not_public(factories):
    non_public_article = factories.ResourceFactory(
        content_type="article",
        published_at=datetime.datetime.now() - datetime.timedelta(days=1),
        webflow_url=1,
        resource_type=ResourceTypes.PRIVATE,
    )

    non_public_article_not_found = Resource.get_public_published_resource_by_slug(
        non_public_article.slug
    )
    assert non_public_article_not_found is None


@pytest.mark.parametrize(
    "contentful_status,expected_article_type",
    [
        (ContentfulMigrationStatus.NOT_STARTED, ArticleType.HTML),
        (ContentfulMigrationStatus.IN_PROGRESS, ArticleType.HTML),
        (ContentfulMigrationStatus.LIVE, ArticleType.RICH_TEXT),
    ],
)
def test_get_article_type(factories, contentful_status, expected_article_type):
    article = factories.ResourceFactory(
        content_type="article",
        published_at=datetime.datetime.now() - datetime.timedelta(days=1),
        resource_type=ResourceTypes.ENTERPRISE,
        contentful_status=contentful_status,
    )

    assert article.article_type == expected_article_type
