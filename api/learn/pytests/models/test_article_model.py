import datetime
from unittest import mock

from learn.models import article, article_type
from models import images


def test_related_read_from_resource(factories):
    resource = factories.ResourceFactory(
        content_type="article",
        published_at=datetime.datetime.now() - datetime.timedelta(days=1),
        webflow_url=1,
    )
    resource.image = images.Image()

    related_read = article.RelatedRead.from_resource(resource)
    assert related_read.title == resource.title
    assert related_read.slug == resource.slug
    assert related_read.type == article_type.ArticleType.HTML
    # resource.image is setup above. don't know full URL because its generated from app config and image properties
    assert related_read.thumbnail.url.startswith("https://img-res.mavenclinic.com/")
    # no alt text is provided from DB resources
    assert related_read.thumbnail.description is None


def test_related_read_from_resource_no_image(factories):
    resource = factories.ResourceFactory(
        content_type="article",
        published_at=datetime.datetime.now() - datetime.timedelta(days=1),
        webflow_url=1,
    )

    related_read = article.RelatedRead.from_resource(resource)
    assert related_read.title == resource.title
    assert related_read.slug == resource.slug
    assert related_read.type == article_type.ArticleType.HTML
    assert related_read.thumbnail is None  # no image is set up


def test_related_read_from_contentful():
    description = "this field is used for alt text"
    hero_image = mock.Mock()
    hero_image.url.return_value = "//icons.co/icon.bmp"
    # this is how description is accessed
    hero_image.fields.return_value.get.return_value = description

    entry = contentful_entry()
    # this is how hero_image is accessed
    entry.fields.return_value.get.return_value = hero_image

    related_read = article.RelatedRead.from_contentful(entry)

    assert related_read.title == entry.title
    assert related_read.slug == entry.slug
    assert related_read.type == article_type.ArticleType.RICH_TEXT
    assert related_read.thumbnail.url == "https:" + hero_image.url()
    assert related_read.thumbnail.description == description


def test_related_read_from_contentful_no_image():
    entry = contentful_entry()
    # this is how hero_image is accessed <- no hero_image
    entry.fields.return_value.get.return_value = None

    related_read = article.RelatedRead.from_contentful(entry)

    assert related_read.title == entry.title
    assert related_read.slug == entry.slug
    assert related_read.type == article_type.ArticleType.RICH_TEXT
    assert related_read.thumbnail is None


def test_related_read_from_contentful_no_image_description():
    hero_image = mock.Mock()
    hero_image.url.return_value = "//icons.co/icon.bmp"
    # this is how description is accessed <- no description
    hero_image.fields.return_value.get.return_value = None

    entry = contentful_entry()
    # this is how hero_image is accessed <- yes hero image
    entry.fields.return_value.get.return_value = hero_image

    related_read = article.RelatedRead.from_contentful(entry)

    assert related_read.title == entry.title
    assert related_read.slug == entry.slug
    assert related_read.type == article_type.ArticleType.RICH_TEXT
    assert related_read.thumbnail.url == "https:" + hero_image.url()
    assert related_read.thumbnail.description is None


def contentful_entry():
    entry_attrs = {
        "title": "Is fresh vs. frozen spinach better for you?",
        "slug": "fresh-vs-frozen",
    }

    return mock.Mock(**entry_attrs)
