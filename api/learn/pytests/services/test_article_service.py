import datetime
import json
from typing import Any, Tuple
from unittest import mock
from unittest.mock import ANY, call

import pytest
from babel import Locale
from contentful import Asset, Entry

from common import stats
from l10n.utils import request_locale_str
from learn.models import article_type, migration
from learn.models.rich_text_embeds import EmbeddedEntryType
from learn.services import article_service as article_svc
from learn.services.contentful import DEFAULT_CONTENTFUL_LOCALE
from learn.services.contentful_caching_service import TTL
from pytests import factories


def __get_accordion_mock_entry_and_entry_dict() -> Tuple[mock.Mock, dict[str, Any]]:
    mock_entry = mock.Mock(
        spec=Entry,
        content_type=mock.Mock(id=EmbeddedEntryType.ACCORDION.value),
        id="12345",
        heading_level="??",
        items=[
            mock.Mock(header="#1", body="I am the first item"),
            mock.Mock(header="#2", body="I am the second item"),
        ],
    )
    return (
        mock_entry,
        {
            "id": mock_entry.id,
            "entry_type": EmbeddedEntryType.ACCORDION.value,
            "heading_level": mock_entry.heading_level,
            "items": [
                {
                    "title": item.header,
                    "rich_text": item.body,
                }
                for item in mock_entry.items
            ],
        },
    )


def __get_callout_mock_entry_and_entry_dict() -> Tuple[mock.Mock, dict[str, Any]]:
    mock_entry = mock.Mock(
        spec=Entry,
        content_type=mock.Mock(id=EmbeddedEntryType.CALLOUT.value),
        id="12345",
        rich_text="🤑💬",
    )
    return (
        mock_entry,
        {
            "id": mock_entry.id,
            "entry_type": EmbeddedEntryType.CALLOUT.value,
            "rich_text": mock_entry.rich_text,
        },
    )


def __get_embedded_image_mock_entry_and_entry_dict() -> Tuple[
    mock.Mock, dict[str, Any]
]:
    mock_entry = mock.Mock(
        spec=Entry,
        content_type=mock.Mock(id=EmbeddedEntryType.EMBEDDED_IMAGE.value),
        id="12345",
        image=mock.Mock(
            url=mock.Mock(return_value="embedded.image"),
            fields=mock.Mock(
                return_value={"description": "I am so embedded right now"}
            ),
        ),
        caption="Look! An embedded image!",
    )
    return (
        mock_entry,
        {
            "id": mock_entry.id,
            "entry_type": EmbeddedEntryType.EMBEDDED_IMAGE.value,
            "image": {
                "url": mock_entry.image.url(),
                "description": mock_entry.image.fields()["description"],
            },
            "caption": mock_entry.caption,
        },
    )


def __get_embedded_video_mock_entry_and_entry_dict() -> Tuple[
    mock.Mock, dict[str, Any]
]:
    mock_entry = mock.Mock(
        spec=Entry,
        content_type=mock.Mock(id=EmbeddedEntryType.EMBEDDED_VIDEO.value),
        id="12345",
        captions=mock.Mock(url=mock.Mock(return_value="cap.tions")),
        video_link="video.link",
        fields=mock.Mock(
            return_value={
                "thumbnail": mock.Mock(
                    url=mock.Mock(return_value="thumb.nail"),
                    fields=mock.Mock(
                        return_value={"description": "I am so embedded right now"}
                    ),
                )
            }
        ),
    )
    return (
        mock_entry,
        {
            "id": mock_entry.id,
            "entry_type": EmbeddedEntryType.EMBEDDED_VIDEO.value,
            "video_link": mock_entry.video_link,
            "thumbnail": {
                "url": mock_entry.fields()["thumbnail"].url(),
                "description": mock_entry.fields()["thumbnail"].fields()["description"],
            },
            "captions_link": mock_entry.captions.url(),
        },
    )


@pytest.fixture
@mock.patch("learn.services.caching_service.redis_client")
@mock.patch("learn.services.contentful.LibraryContentfulClient")
def article_service(_, __):
    return article_svc.ArticleService(preview=False, user_facing=True)


@pytest.fixture
def localized_article_service():
    return create_localized_article_service()


@mock.patch("learn.services.caching_service.redis_client")
@mock.patch("learn.services.contentful.LibraryContentfulClient")
def create_localized_article_service(_, __):
    return article_svc.ArticleService(
        preview=False, user_facing=True, should_localize=True
    )


@pytest.fixture
def mock_entry():
    asset_mock = mock.Mock()
    asset_mock.url.return_value = "https://ima.ge/image.img"
    asset_mock.fields.return_value = {"description": "desc"}

    entry_mock = mock.Mock(
        title="A B C", medically_reviewed=False, rich_text={"content": []}, slug="a-b-c"
    )
    entry_mock.fields.return_value = {"related_reads": [], "hero_image": asset_mock}
    return entry_mock


@pytest.fixture
def resulting_article():
    return {
        "title": "A B C",
        "medically_reviewed": None,
        "hero_image": {"url": "https://ima.ge/image.img", "description": "desc"},
        "rich_text": {"content": []},
        "related_reads": [],
        "rich_text_includes": [],
    }


@pytest.fixture
def mock_logger():
    with mock.patch("learn.services.article_service.logger") as mock_logger:
        yield mock_logger


@mock.patch("l10n.utils.get_locale")
@mock.patch("learn.services.caching_service.redis_client")
@mock.patch("learn.services.contentful.LibraryContentfulClient")
def test_get_preview(
    contentful_mock, redis_mock, get_locale_mock, mock_entry, resulting_article
):
    get_locale_mock.return_value = Locale("en", "US")
    article_service = article_svc.ArticleService(
        preview=True, user_facing=True, should_localize=True
    )
    contentful_mock.return_value.get_article_entries_by_slug.return_value = [mock_entry]

    result = article_service.get_value(identifier_value=mock_entry.slug, locale=None)

    assert result == resulting_article
    contentful_mock.assert_called_once_with(preview=True, user_facing=True)
    contentful_mock.return_value.get_article_entries_by_slug.assert_called_once_with(
        [mock_entry.slug], locale="en-US"
    )
    redis_mock.pipeline.assert_not_called()
    redis_mock.set.assert_not_called()


@pytest.mark.parametrize(
    "locale", [Locale("en"), Locale("en", "US"), Locale("fr"), Locale("fr", "CA")]
)
@mock.patch("l10n.utils.get_locale")
def test_article_get_value_not_in_cache(
    get_locale_mock,
    locale,
    mock_entry,
    resulting_article,
):
    get_locale_mock.return_value = locale
    localized_article_service = create_localized_article_service()
    locale_str = request_locale_str()
    expected_cache_key = (
        "article:a-b-c" if locale_str == "en-US" else f"article:{locale_str}:a-b-c"
    )
    localized_article_service.redis_client.pipeline.return_value.execute.return_value = [
        None
    ]

    localized_article_service.contentful_client.get_article_entries_by_slug.return_value = [
        mock_entry
    ]

    result = localized_article_service.get_value(
        identifier_value=mock_entry.slug, locale=None
    )

    localized_article_service.contentful_client.get_article_entries_by_slug.assert_called_once_with(
        [mock_entry.slug], locale=locale_str
    )
    localized_article_service.redis_client.pipeline.return_value.set.assert_called_once_with(
        expected_cache_key, json.dumps(resulting_article), ex=TTL
    )
    localized_article_service.redis_client.pipeline.return_value.execute.assert_has_calls(
        [mock.call(), mock.call()]
    )
    assert result == resulting_article


@mock.patch("learn.services.article_service.request_locale_str")
def test_article_global_get_value_not_in_cache(
    request_locale_str_mock, mock_entry, resulting_article, localized_article_service
):
    locale = "🥥"
    resulting_slug = "article:a-b-c-🥥"
    request_locale_str_mock.return_value = "en-US"
    localized_article_service.redis_client.pipeline.return_value.execute.return_value = [
        None
    ]

    localized_article_service.contentful_client.get_article_global_entries_by_slug_and_locale.return_value = [
        mock_entry
    ]

    result = localized_article_service.get_value(
        identifier_value=mock_entry.slug, locale=locale
    )

    localized_article_service.contentful_client.get_article_global_entries_by_slug_and_locale.assert_called_once_with(
        [mock_entry.slug], locale
    )

    localized_article_service.redis_client.pipeline.return_value.set.assert_called_once_with(
        resulting_slug, json.dumps(resulting_article), ex=TTL
    )
    localized_article_service.redis_client.pipeline.return_value.execute.assert_has_calls(
        [mock.call(), mock.call()]
    )
    assert result == resulting_article


@pytest.mark.parametrize(
    argnames=["query_string_locale", "locale_from_header", "expected_cache_key"],
    argvalues=[
        ("🥥", Locale("de"), "article:a-b-c-🥥"),  # anything
        (None, Locale("en", "US"), "article:a-b-c"),
        (None, Locale("en"), "article:en:a-b-c"),
        (None, Locale("fr", "CA"), "article:fr-CA:a-b-c"),
    ],
)
@mock.patch("l10n.utils.get_locale")
def test_get_value_in_cache(
    get_locale,
    resulting_article,
    query_string_locale,
    locale_from_header,
    expected_cache_key,
):
    get_locale.return_value = locale_from_header
    localized_article_service = create_localized_article_service()
    localized_article_service.redis_client.pipeline.return_value.execute.return_value = [
        json.dumps(resulting_article)
    ]
    slug = "a-b-c"

    result = localized_article_service.get_value(
        identifier_value=slug, locale=query_string_locale
    )

    localized_article_service.redis_client.pipeline.return_value.get.assert_called_with(
        expected_cache_key
    )
    localized_article_service.contentful_client.get_article_entry_by_slug.assert_not_called()
    localized_article_service.contentful_client.get_article_entry_by_slug_and_locale.assert_not_called()
    localized_article_service.redis_client.set.assert_not_called()
    assert result == resulting_article


@pytest.mark.parametrize(
    "locale_from_header", [Locale("en", "US"), Locale("fr"), Locale("fr", "CA")]
)
@mock.patch("l10n.utils.get_locale")
@mock.patch("learn.services.contentful_caching_service.log")
def test_article_not_in_cache_nor_contentful(
    log_mock, get_locale_mock, locale_from_header
):
    get_locale_mock.return_value = locale_from_header
    localized_article_service = create_localized_article_service()
    localized_article_service.redis_client.pipeline.return_value.execute.return_value = [
        None
    ]
    localized_article_service.contentful_client.get_article_entries_by_slug.return_value = (
        []
    )
    slug = "a-b-c"

    result = localized_article_service.get_value(identifier_value=slug, locale=None)

    locale_str = request_locale_str()
    localized_article_service.redis_client.pipeline.return_value.get.assert_called_with(
        f"article:{slug}"
        if locale_str == DEFAULT_CONTENTFUL_LOCALE
        else f"article:{locale_str}:{slug}"
    )
    localized_article_service.contentful_client.get_article_entries_by_slug.assert_called_with(
        [slug], locale=locale_str
    )
    log_mock.warn.assert_called_once_with(
        "Value not found on Contentful or in cache", identifier_value=slug
    )
    assert result is None


@mock.patch("l10n.utils.get_locale")
@mock.patch("learn.services.contentful_caching_service.log")
def test_cache_deserialization_error(
    log_mock,
    get_locale_mock,
    mock_entry,
    resulting_article,
):
    get_locale_mock.return_value = Locale("en", "US")
    localized_article_service = create_localized_article_service()
    bad_value = {"title": "missing-other-values-tho"}
    localized_article_service.redis_client.pipeline.return_value.execute.return_value = [
        json.dumps(bad_value)
    ]
    localized_article_service.contentful_client.get_article_entries_by_slug.return_value = [
        mock_entry
    ]

    result = localized_article_service.get_value(
        identifier_value=mock_entry.slug, locale=None
    )

    localized_article_service.redis_client.pipeline.return_value.get.assert_called_with(
        f"article:{mock_entry.slug}"
    )
    localized_article_service.contentful_client.get_article_entries_by_slug.assert_called_with(
        [mock_entry.slug], locale="en-US"
    )
    log_mock.warn.assert_called_with(
        "Error deserializing value from redis. This likely means the code model "
        "has changed since the value was cached. Removing the cache entry.",
        error=mock.ANY,
        key=f"article:{mock_entry.slug}",
        value_str=json.dumps(bad_value),
        class_name="ArticleService",
        exc_info=True,
    )
    assert result == resulting_article


@mock.patch("common.stats.increment")
def test_parse_as_related_read_non_contentful(mock_stats_incr, article_service):
    db_resource = factories.ResourceFactory(
        content_type="article",
        published_at=datetime.datetime.now() - datetime.timedelta(days=1),
        webflow_url=None,
    )

    contentful_entry = mock.Mock()
    contentful_entry.content_type.id = "nonContentfulArticle"
    contentful_entry.slug = db_resource.slug

    related_read = article_service.parse_as_related_read(contentful_entry)
    assert related_read.slug == db_resource.slug
    assert related_read.title == db_resource.title
    assert related_read.type == article_type.ArticleType.HTML.value
    mock_stats_incr.assert_called_with(
        "learn.services.contentful.related_read",
        pod_name=stats.PodNames.COCOPOD,
        tags=[
            "success:true",
            "article_type:html",
            "contentful_content_type:noncontentfularticle",
        ],
    )


@pytest.mark.parametrize(
    "contentful_content_type",
    ["article", "nonContentfulArticle"],
)
@mock.patch("common.stats.increment")
@mock.patch("contentful.Client")
def test_parse_as_related_read_doesnt_exist(
    _, mock_stats_incr, contentful_content_type, article_service
):
    factories.ResourceFactory(
        content_type="article",
        published_at=datetime.datetime.now() - datetime.timedelta(days=1),
        webflow_url=None,
        slug="some-slug",
    )

    contentful_entry = mock.Mock()
    contentful_entry.content_type.id = contentful_content_type
    contentful_entry.slug = "a-different-slug"

    related_read = article_service.parse_as_related_read(contentful_entry)
    assert related_read is None
    mock_stats_incr.assert_called_with(
        "learn.services.contentful.related_read",
        pod_name=stats.PodNames.COCOPOD,
        tags=[
            "success:false",
            f"contentful_content_type:{contentful_content_type.lower()}",
            "outcome:hidden",
            "detail:not_found",
        ],
    )


@pytest.mark.parametrize(
    "contentful_content_type",
    ["article", "nonContentfulArticle"],
)
@mock.patch("models.marketing.Resource.get_public_published_resource_by_slug")
@mock.patch("common.stats.increment")
def test_parse_as_related_read_errors(
    mock_stats_incr, get_resource_db_mock, contentful_content_type, article_service
):
    resource = factories.ResourceFactory(
        content_type="article",
        published_at=datetime.datetime.now() - datetime.timedelta(days=1),
        webflow_url=None,
    )

    contentful_entry = mock.Mock()
    contentful_entry.content_type.id = contentful_content_type
    contentful_entry.slug = resource.slug

    get_resource_db_mock.side_effect = Exception

    related_read = article_service.parse_as_related_read(contentful_entry)

    assert related_read is None
    mock_stats_incr.assert_called_with(
        "learn.services.contentful.related_read",
        pod_name=stats.PodNames.COCOPOD,
        tags=[
            "success:false",
            f"contentful_content_type:{contentful_content_type.lower()}",
            "outcome:hidden",
            "detail:error",
        ],
    )


@mock.patch("common.stats.increment")
def test_parse_as_related_read_contentful(mock_stats_incr, article_service):
    resource = factories.ResourceFactory(
        content_type="article",
        published_at=datetime.datetime.now() - datetime.timedelta(days=1),
        webflow_url=None,
        contentful_status=migration.ContentfulMigrationStatus.LIVE,
    )

    contentful_entry = mock.Mock()
    contentful_entry.content_type.id = "article"
    contentful_entry.title = resource.title
    contentful_entry.slug = resource.slug
    contentful_entry.fields.return_value.get.return_value = None  # for hero image

    related_read = article_service.parse_as_related_read(contentful_entry)
    assert related_read.title == resource.title
    assert related_read.slug == resource.slug
    assert related_read.type == article_type.ArticleType.RICH_TEXT

    mock_stats_incr.assert_called_with(
        "learn.services.contentful.related_read",
        pod_name=stats.PodNames.COCOPOD,
        tags=[
            "success:true",
            "article_type:rich_text",
            "contentful_content_type:article",
        ],
    )


@mock.patch("common.stats.increment")
def test_parse_as_related_read_contentful_not_live(mock_stats_incr, article_service):
    resource = factories.ResourceFactory(
        content_type="article",
        published_at=datetime.datetime.now() - datetime.timedelta(days=1),
        webflow_url=None,
        contentful_status=migration.ContentfulMigrationStatus.IN_PROGRESS,
    )

    contentful_entry = mock.Mock()
    contentful_entry.content_type.id = "article"
    contentful_entry.title = resource.title
    contentful_entry.slug = resource.slug
    contentful_entry.fields.return_value.get.return_value = None  # for hero image

    related_read = article_service.parse_as_related_read(contentful_entry)
    assert related_read.title == resource.title
    assert related_read.slug == resource.slug
    assert related_read.type == article_type.ArticleType.HTML

    mock_stats_incr.assert_called_with(
        "learn.services.contentful.related_read",
        pod_name=stats.PodNames.COCOPOD,
        tags=[
            "success:true",
            "article_type:html",
            "contentful_content_type:article",
        ],
    )


@mock.patch("common.stats.increment")
def test_parse_as_related_read_non_contentful_live(mock_stats_incr, article_service):
    resource = factories.ResourceFactory(
        content_type="article",
        published_at=datetime.datetime.now() - datetime.timedelta(days=1),
        webflow_url=None,
        contentful_status=migration.ContentfulMigrationStatus.LIVE,
    )

    contentful_entry = mock.Mock()
    contentful_entry.content_type.id = "nonContentfulArticle"
    contentful_entry.slug = resource.slug

    related_read_entry = mock.Mock()
    related_read_entry.content_type.id = "article"
    related_read_entry.title = resource.title
    related_read_entry.slug = resource.slug
    related_read_entry.fields.return_value.get.return_value = None  # for hero image

    article_service.contentful_client.get_article_entry_by_slug.return_value = (
        related_read_entry
    )

    related_read = article_service.parse_as_related_read(contentful_entry)
    assert related_read.title == resource.title
    assert related_read.slug == resource.slug
    assert related_read.type == article_type.ArticleType.RICH_TEXT

    mock_stats_incr.assert_called_with(
        "learn.services.contentful.related_read",
        pod_name=stats.PodNames.COCOPOD,
        tags=[
            "success:true",
            "article_type:rich_text",
            "contentful_content_type:noncontentfularticle",
        ],
    )


@pytest.mark.parametrize(
    argnames=("locale", "show_related_reads"),
    argvalues=((Locale("en"), True), (Locale("en", "US"), True), (Locale("es"), False)),
)
@mock.patch("l10n.utils.get_locale")
def test_parse_related_reads_hides_not_english(
    get_locale, article_service, locale, show_related_reads
):
    get_locale.return_value = locale
    resource = factories.ResourceFactory(
        content_type="article",
        published_at=datetime.datetime.now(datetime.timezone.utc)
        - datetime.timedelta(days=1),
        webflow_url=None,
        contentful_status=migration.ContentfulMigrationStatus.LIVE,
    )

    contentful_entry = mock.Mock()
    contentful_entry.content_type.id = "article"
    contentful_entry.title = resource.title
    contentful_entry.slug = resource.slug
    contentful_entry.fields.return_value.get.return_value = None  # for hero image

    related_reads = article_service.get_related_reads([contentful_entry])
    if show_related_reads:
        assert related_reads[0].title == resource.title
        assert related_reads[0].slug == resource.slug
        assert related_reads[0].type == article_type.ArticleType.RICH_TEXT

    else:
        assert related_reads == []


@mock.patch("l10n.utils.get_locale")
@mock.patch("learn.services.article_service.LibraryContentfulClient")
def test_remove_value_from_cache(library_contentful_client, mock_get_locale):
    mock_get_locale.return_value = Locale("en", "US")
    localized_article_service = create_localized_article_service()
    entry_id = "12345abcde"
    slug = "🐌"
    localized_cache_keys = [
        f"article:{locale}:{slug}" for locale in ["fr", "es", "fr-CA"]
    ]
    library_contentful_client.return_value.get_entry_by_id.return_value.slug = slug
    localized_article_service.redis_client.keys.return_value = localized_cache_keys

    localized_article_service.remove_value_from_cache(entry_id)
    library_contentful_client.assert_called_once_with(preview=True, user_facing=False)
    library_contentful_client.return_value.get_entry_by_id.assert_called_once_with(
        entry_id
    )
    localized_article_service.redis_client.delete.assert_called_once_with(
        f"article:{slug}"
    )
    localized_article_service.redis_client.keys.assert_called_once_with(
        f"article:*:{slug}"
    )
    localized_article_service.redis_client.pipeline.return_value.delete.assert_has_calls(
        [call(cache_key) for cache_key in localized_cache_keys]
    )
    localized_article_service.redis_client.pipeline.return_value.execute.assert_called_once_with()


def test_process_rich_text_and_includes_nothing_to_process():
    includes = []
    rich_text = {"content": [{"nodeType": "just a regular node idk"}]}

    assert (
        article_svc.ArticleService.process_rich_text_and_includes(
            rich_text=rich_text, includes=includes
        )
        == rich_text
    )
    assert includes == []


@pytest.mark.parametrize(
    argnames=["mock_entry", "entry_dict"],
    argvalues=[
        __get_accordion_mock_entry_and_entry_dict(),
        __get_callout_mock_entry_and_entry_dict(),
        __get_embedded_image_mock_entry_and_entry_dict(),
        __get_embedded_video_mock_entry_and_entry_dict(),
    ],
)
def test_process_rich_text_and_includes_embedded_entry_block(
    mock_entry, entry_dict: dict[str, Any]
):
    includes = []

    assert article_svc.ArticleService.process_rich_text_and_includes(
        rich_text={
            "content": [
                {"nodeType": "embedded-entry-block", "data": {"target": mock_entry}}
            ]
        },
        includes=includes,
    ) == {
        "content": [
            {
                "nodeType": "embedded-entry-block",
                "data": {
                    "target": {
                        "sys": {
                            "id": mock_entry.id,
                            "type": "Link",
                            "linkType": "Entry",
                        }
                    }
                },
            }
        ]
    }
    assert includes == [entry_dict]


@mock.patch(
    "learn.services.article_service.LibraryContentfulClient.log_warning_about_contentful_entry"
)
def test_process_rich_text_and_includes_embedded_entry_block_unsupported_type(
    mock_log_warning_about_contentful_entry,
):
    includes = []
    mock_entry = mock.Mock(spec=Entry, content_type=mock.Mock(id="💩"))
    rich_text = {
        "content": [
            {"nodeType": "embedded-entry-block", "data": {"target": mock_entry}}
        ]
    }

    with pytest.raises(ValueError):
        assert (
            article_svc.ArticleService.process_rich_text_and_includes(
                rich_text=rich_text, includes=includes
            )
            == rich_text
        )
    assert includes == []

    mock_log_warning_about_contentful_entry.assert_called_once_with(
        "Unsupported entry type embedded", ANY
    )


def test_process_rich_text_and_includes_embedded_entry_block_not_an_entry(mock_logger):
    includes = []
    rich_text = {
        "content": [
            {
                "nodeType": "embedded-entry-block",
                "data": {"target": {"dict?": "I guess so"}},
            }
        ]
    }

    with pytest.raises(ValueError):
        assert (
            article_svc.ArticleService.process_rich_text_and_includes(
                rich_text=rich_text, includes=includes
            )
            == rich_text
        )
    assert includes == []

    mock_logger.error.assert_called_once_with(
        "Encountered an embedded entry block which is not an Entry type. Raising an exception "
        "to force a retry.",
        extra={"node": rich_text["content"][0], "data_target_type": dict},
    )


def test_process_rich_text_and_includes_embedded_asset_block():
    includes = []
    mock_asset = mock.Mock(
        spec=Asset,
        id="12345",
        url=mock.Mock(return_value="embedded.image"),
        fields=mock.Mock(return_value={"description": "I am so embedded right now"}),
    )

    assert article_svc.ArticleService.process_rich_text_and_includes(
        rich_text={
            "content": [
                {"nodeType": "embedded-asset-block", "data": {"target": mock_asset}}
            ]
        },
        includes=includes,
    ) == {
        "content": [
            {
                "nodeType": "embedded-entry-block",
                "data": {
                    "target": {
                        "sys": {
                            "id": mock_asset.id,
                            "type": "Link",
                            "linkType": "Entry",
                        }
                    }
                },
            }
        ]
    }
    assert includes == [
        {
            "id": mock_asset.id,
            "entry_type": EmbeddedEntryType.EMBEDDED_IMAGE.value,
            "image": {
                "url": mock_asset.url(),
                "description": mock_asset.fields()["description"],
            },
            "caption": None,
        }
    ]


def test_process_rich_text_and_includes_embedded_asset_block_not_an_asset(mock_logger):
    includes = []
    rich_text = {
        "content": [
            {
                "nodeType": "embedded-asset-block",
                "data": {"target": {"dict?": "I guess so"}},
            }
        ]
    }

    with pytest.raises(ValueError):
        assert (
            article_svc.ArticleService.process_rich_text_and_includes(
                rich_text=rich_text, includes=includes
            )
            == rich_text
        )
    assert includes == []

    mock_logger.error.assert_called_once_with(
        "Encountered an embedded asset block which is not an Asset type. Raising an exception "
        "to force a retry.",
        extra={"node": rich_text["content"][0], "data_target_type": dict},
    )
