from unittest import mock
from unittest.mock import call

import pytest
from babel import Locale

from l10n.utils import request_locale_str
from learn.services.article_title_service import LocalizedArticleTitleService
from learn.services.contentful_caching_service import TTL


@mock.patch("learn.services.caching_service.redis_client")
@mock.patch("learn.services.contentful.LibraryContentfulClient")
def create_article_title_service(_, __):
    return LocalizedArticleTitleService(preview=False, user_facing=True)


@pytest.mark.parametrize(
    "locale", [Locale("en", "US"), Locale("fr"), Locale("fr", "CA")]
)
@mock.patch("l10n.utils.get_locale")
def test_get_value_already_cached(get_locale, locale):
    get_locale.return_value = locale

    slug = "article-slug"
    title = "Article title"

    localized_article_title_service = create_article_title_service()
    localized_article_title_service.redis_client.pipeline.return_value.execute.return_value = [
        title
    ]

    cached_title = localized_article_title_service.get_value(slug)
    assert cached_title == title

    localized_article_title_service.redis_client.pipeline.return_value.get.assert_called_once_with(
        f"article_title:{request_locale_str()}:{slug}"
    )
    localized_article_title_service.contentful_client.get_articles_with_only_titles_by_slug.assert_not_called()
    localized_article_title_service.redis_client.pipeline.return_value.set.assert_not_called()


@pytest.mark.parametrize(
    "locale", [Locale("en", "US"), Locale("fr"), Locale("fr", "CA")]
)
@mock.patch("l10n.utils.get_locale")
def test_get_value_not_cached(get_locale, locale):
    get_locale.return_value = locale

    slug = "article-slug"
    title = "Article title"
    contentful_entry_mock = mock.Mock()
    contentful_entry_mock.slug = slug
    contentful_entry_mock.title = title

    localized_article_title_service = create_article_title_service()
    localized_article_title_service.redis_client.pipeline.return_value.execute.return_value = [
        None
    ]
    localized_article_title_service.contentful_client.get_articles_with_only_titles_by_slug.return_value = [
        contentful_entry_mock
    ]

    title_from_contentful = localized_article_title_service.get_value(slug)
    assert title_from_contentful == title

    localized_article_title_service.redis_client.pipeline.return_value.get.assert_called_once_with(
        f"article_title:{request_locale_str()}:{slug}"
    )
    localized_article_title_service.contentful_client.get_articles_with_only_titles_by_slug.assert_called_once_with(
        [slug], locale=request_locale_str()
    )

    localized_article_title_service.redis_client.pipeline.return_value.set.assert_called_once_with(
        f"article_title:{request_locale_str()}:{slug}", title_from_contentful, ex=TTL
    )


@pytest.mark.parametrize(
    "locale", [Locale("en", "US"), Locale("fr"), Locale("fr", "CA")]
)
@mock.patch("l10n.utils.get_locale")
def test_save_value_in_cache(get_locale, locale):
    get_locale.return_value = locale

    slug = "article-slug"
    title = "Article title"

    localized_article_title_service = create_article_title_service()
    localized_article_title_service.save_value_in_cache(slug, title)

    localized_article_title_service.redis_client.set.assert_called_once_with(
        f"article_title:{request_locale_str()}:{slug}", title, ex=TTL
    )


@mock.patch("learn.services.article_title_service.LibraryContentfulClient")
def test_remove_value_from_cache(library_contentful_client):
    localized_article_title_service = create_article_title_service()

    entry_id = "12345abcde"
    slug = "🐌"
    localized_cache_keys = [
        f"article_title:{locale}:{slug}" for locale in ["fr", "es", "fr-CA"]
    ]
    library_contentful_client.return_value.get_entry_by_id.return_value.slug = slug
    localized_article_title_service.redis_client.keys.return_value = (
        localized_cache_keys
    )

    localized_article_title_service.remove_value_from_cache(entry_id)
    library_contentful_client.assert_called_once_with(preview=True, user_facing=False)
    library_contentful_client.return_value.get_entry_by_id.assert_called_once_with(
        entry_id
    )
    localized_article_title_service.redis_client.keys.assert_called_once_with(
        f"article_title:*:{slug}"
    )
    localized_article_title_service.redis_client.pipeline.return_value.delete.assert_has_calls(
        [call(cache_key) for cache_key in localized_cache_keys]
    )
    localized_article_title_service.redis_client.pipeline.return_value.execute.assert_called_once_with()
