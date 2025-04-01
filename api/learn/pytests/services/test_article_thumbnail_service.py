from unittest import mock

from learn.models import migration
from learn.models.media_type import MediaType
from learn.services import article_thumbnail_service


@mock.patch("learn.services.contentful.LibraryContentfulClient")
@mock.patch("learn.services.caching_service.redis_client")
def test_remove_asset_from_cache_by_id(redis_mock, contentful_client_mock):
    asset_id = "abc"
    slug1 = "incoming-resource-1"
    slug2 = "incoming-resource-2"
    ref_mock1 = mock.Mock(slug=slug1)
    ref_mock2 = mock.Mock(slug=slug2)
    mock_asset = mock.Mock(id=asset_id)
    contentful_client_mock.return_value.get_asset_by_id.return_value = mock_asset
    contentful_client_mock.return_value.get_entity_references.return_value = [
        ref_mock1,
        ref_mock2,
    ]

    cache_instance = article_thumbnail_service.ArticleThumbnailService()
    cache_instance.remove_asset_from_cache_by_id(asset_id)

    contentful_client_mock.assert_called_with(preview=True, user_facing=False)
    contentful_client_mock.return_value.get_asset_by_id.assert_called_once_with(
        asset_id
    )
    contentful_client_mock.return_value.get_entity_references.assert_called_with(
        mock_asset
    )
    call1 = mock.call(f"thumbnails:{slug1}")
    call2 = mock.call(f"thumbnails:{slug2}")
    redis_mock.return_value.delete.assert_has_calls([call1, call2])


@mock.patch("learn.services.contentful.LibraryContentfulClient")
@mock.patch("learn.services.caching_service.redis_client")
def test_remove_article_from_cache_by_id(redis_mock, contentful_client_mock):
    entry_id = "defg"
    slug = "slug-of-defg"
    entry_mock = mock.Mock(slug=slug)
    contentful_client_mock.return_value.get_entry_by_id.return_value = entry_mock

    cache_instance = article_thumbnail_service.ArticleThumbnailService()
    cache_instance.remove_article_from_cache_by_id(entry_id)

    contentful_client_mock.assert_called_with(preview=True, user_facing=False)
    contentful_client_mock.return_value.get_entry_by_id.assert_called_with(entry_id)
    redis_mock.return_value.delete.assert_called_with(f"thumbnails:{slug}")


@mock.patch("learn.services.contentful.LibraryContentfulClient")
@mock.patch("learn.services.caching_service.redis_client")
def test_get_thumbnails_for_resources_pipeline_error_continues(
    redis_mock, contentful_client_mock, factories
):
    resource = factories.ResourceFactory(
        contentful_status=migration.ContentfulMigrationStatus.LIVE
    )
    error = Exception("🫠")
    redis_mock.return_value.pipeline.side_effect = error

    cache_instance = article_thumbnail_service.ArticleThumbnailService()
    cache_instance.get_thumbnails_for_resources([resource])

    contentful_client_mock.return_value.get_article_entry_by_slug.assert_called_with(
        resource.slug
    )


@mock.patch("learn.services.caching_service.redis_client")
def test_get_thumbnails_for_resources_cached(redis_mock, factories):
    resource1 = factories.ResourceFactory(
        contentful_status=migration.ContentfulMigrationStatus.LIVE
    )
    resource2 = factories.ResourceFactory(
        contentful_status=migration.ContentfulMigrationStatus.LIVE,
        estimated_read_time_minutes=42,
        media_type=MediaType.ARTICLE,
    )
    pipe_mock = mock.Mock()
    redis_mock.return_value.pipeline.return_value = pipe_mock
    url1 = "i.mg/img.img"
    description = "a description"
    url2 = "2i.mg/img.img"
    pipe_mock.execute.return_value = [[url1, description], [url2, None]]

    cache_instance = article_thumbnail_service.ArticleThumbnailService()
    results = cache_instance.get_thumbnails_for_resources([resource1, resource2])

    call1 = mock.call(name=f"thumbnails:{resource1.slug}", keys=["url", "description"])
    call2 = mock.call(name=f"thumbnails:{resource2.slug}", keys=["url", "description"])
    pipe_mock.hmget.assert_has_calls([call1, call2])
    assert results[0].image.url == url1
    assert results[0].image.description == description
    assert results[1].image.url == url2
    assert results[1].image.description is None


@mock.patch("learn.services.article_thumbnail_service.contentful_image")
@mock.patch("learn.services.contentful.LibraryContentfulClient")
@mock.patch("learn.services.caching_service.redis_client")
def test_get_thumbnails_for_resources_contentful(
    redis_mock, contentful_client_mock, image_mock, factories
):
    resource = factories.ResourceFactory(
        contentful_status=migration.ContentfulMigrationStatus.LIVE
    )
    redis_mock.return_value.pipeline.return_value.execute.return_value = [[None, None]]
    entry_mock = mock.Mock()
    contentful_client_mock.return_value.get_article_entry_by_slug.return_value = (
        entry_mock
    )
    url = "https://img.us/img.bmp"
    description = "image description"
    image_mock.Image.from_contentful_asset.return_value = mock.Mock(
        url=url, description=description
    )

    cache_instance = article_thumbnail_service.ArticleThumbnailService()
    cache_instance.get_thumbnails_for_resources([resource])

    contentful_client_mock.return_value.get_article_entry_by_slug.assert_called_with(
        resource.slug
    )
    image_mock.Image.from_contentful_asset.assert_called_with(entry_mock.hero_image)
    redis_mock.return_value.hset.assert_called_with(
        f"thumbnails:{resource.slug}", "url", url, {"description": description}
    )


@mock.patch("learn.services.article_thumbnail_service.log")
@mock.patch("learn.services.article_thumbnail_service.contentful_image")
@mock.patch("learn.services.contentful.LibraryContentfulClient")
@mock.patch("learn.services.caching_service.redis_client")
def test_saving_image_to_cache_errored(
    redis_mock, contentful_client_mock, image_mock, log_mock, factories
):
    resource = factories.ResourceFactory(
        contentful_status=migration.ContentfulMigrationStatus.LIVE
    )
    entry_mock = mock.Mock()
    contentful_client_mock.return_value.get_article_entry_by_slug.return_value = (
        entry_mock
    )
    url = "https://img.us/img.bmp"
    description = "image description"
    result_image = mock.Mock(url=url, description=description)
    image_mock.Image.from_contentful_asset.return_value = result_image
    redis_mock.return_value.pipeline.return_value.execute.return_value = [[None, None]]
    error = Exception("failure 2 write")
    redis_mock.return_value.hset.side_effect = error

    cache_instance = article_thumbnail_service.ArticleThumbnailService()
    results = cache_instance.get_thumbnails_for_resources([resource])

    log_mock.error.assert_called_with(
        "Error writing image to cache",
        error=error,
        resource_slug=resource.slug,
    )
    # Failure to save image to cache has no effect on result
    assert results[0].image == result_image


@mock.patch("learn.services.contentful.LibraryContentfulClient")
@mock.patch("learn.services.caching_service.redis_client")
def test_get_thumbnails_for_resources_noncontentful(
    redis_mock, contentful_client_mock, factories
):
    image = factories.ImageFactory()
    resource = factories.ResourceFactory(
        contentful_status=migration.ContentfulMigrationStatus.NOT_STARTED, image=image
    )
    redis_mock.return_value.pipeline.return_value.execute.return_value = [[None, None]]

    cache_instance = article_thumbnail_service.ArticleThumbnailService()
    result = cache_instance.get_thumbnails_for_resources([resource])

    contentful_client_mock.assert_not_called()
    assert result[0].image == image
