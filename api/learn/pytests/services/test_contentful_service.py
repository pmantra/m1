from unittest import mock

import pytest

from learn.services import contentful
from learn.services.contentful import ContentfulContentType

EXPECTED_CLIENT_TIMEOUT_SECONDS_USER_FACING = 2
EXPECTED_CLIENT_TIMEOUT_SECONDS_NON_USER_FACING = 5


@pytest.fixture(autouse=True)
def clear_contentful_clients():
    contentful.LibraryContentfulClient._instances = {}


@mock.patch("learn.services.contentful.contentful")
@mock.patch("learn.services.contentful.CONTENT_PREVIEW_TOKEN")
def test_initiate_preview_client(preview_token_mock, contentful_mock):
    contentful.LibraryContentfulClient(preview=True, user_facing=False)
    contentful_mock.Client.assert_called_with(
        mock.ANY,
        preview_token_mock,
        api_url="preview.contentful.com",
        environment=mock.ANY,
        reuse_entries=mock.ANY,
        timeout_s=EXPECTED_CLIENT_TIMEOUT_SECONDS_NON_USER_FACING,
    )


@mock.patch("learn.services.contentful.contentful")
@mock.patch("learn.services.contentful.CONTENT_DELIVERY_TOKEN")
def test_initiate_delivery_client(delivery_token_mock, contentful_mock):
    contentful.LibraryContentfulClient(preview=False, user_facing=False)
    contentful_mock.Client.assert_called_with(
        mock.ANY,
        delivery_token_mock,
        environment=mock.ANY,
        reuse_entries=mock.ANY,
        timeout_s=EXPECTED_CLIENT_TIMEOUT_SECONDS_NON_USER_FACING,
    )


@mock.patch("learn.services.contentful.contentful")
@mock.patch("learn.services.contentful.CONTENT_DELIVERY_TOKEN")
def test_initiate_user_facing_client(delivery_token_mock, contentful_mock):
    contentful.LibraryContentfulClient(preview=False, user_facing=True)
    contentful_mock.Client.assert_called_with(
        mock.ANY,
        delivery_token_mock,
        environment=mock.ANY,
        reuse_entries=mock.ANY,
        timeout_s=EXPECTED_CLIENT_TIMEOUT_SECONDS_USER_FACING,
    )


@mock.patch("learn.services.contentful.contentful")
@mock.patch("learn.services.contentful.CONTENT_DELIVERY_TOKEN")
def test_initiate_non_user_facing_client(delivery_token_mock, contentful_mock):
    contentful.LibraryContentfulClient(preview=False, user_facing=False)
    contentful_mock.Client.assert_called_with(
        mock.ANY,
        delivery_token_mock,
        environment=mock.ANY,
        reuse_entries=mock.ANY,
        timeout_s=EXPECTED_CLIENT_TIMEOUT_SECONDS_NON_USER_FACING,
    )


@pytest.mark.parametrize(
    argnames=["preview", "user_facing"],
    argvalues=[(True, False), (True, True), (False, True), (False, False)],
)
@mock.patch("learn.services.contentful.contentful")
def test_one_instance_of_each_client(contentful_mock, preview, user_facing):
    client1 = contentful.LibraryContentfulClient(
        preview=preview, user_facing=user_facing
    )
    client2 = contentful.LibraryContentfulClient(
        preview=preview, user_facing=user_facing
    )

    assert contentful_mock.Client.call_count == 1
    assert client1 == client2


@mock.patch("learn.services.contentful.contentful")
def test_different_arg_clients_coexist(contentful_mock):
    client1 = contentful.LibraryContentfulClient(preview=True, user_facing=True)
    client2 = contentful.LibraryContentfulClient(preview=True, user_facing=False)
    client3 = contentful.LibraryContentfulClient(preview=False, user_facing=True)
    client4 = contentful.LibraryContentfulClient(preview=False, user_facing=False)

    assert contentful_mock.Client.call_count == 4
    assert client1 != client2
    assert client3 != client4


@mock.patch("learn.services.contentful.contentful")
def test_one_instance_disregarding_arg_order(contentful_mock):
    client1 = contentful.LibraryContentfulClient(preview=True, user_facing=True)
    client2 = contentful.LibraryContentfulClient(user_facing=True, preview=True)

    assert contentful_mock.Client.call_count == 1
    assert client1 == client2


@mock.patch("learn.services.contentful.contentful")
def test_get_entity_references_with_asset(contentful_mock):
    asset_mock = mock.Mock()
    article_mock = mock.Mock(sys={"content_type": mock.Mock(id="article")})
    other_mock = mock.Mock(sys={"content_type": mock.Mock(id="callout")})
    asset_mock.incoming_references.return_value = [article_mock, other_mock]

    client = contentful.LibraryContentfulClient(preview=False, user_facing=False)
    refs = client.get_entity_references(asset_mock)

    asset_mock.incoming_references.assert_called_with(
        contentful_mock.Client.return_value, query={"include": 5, "locale": "en-US"}
    )
    assert refs == [article_mock, other_mock]


@mock.patch("learn.services.contentful.contentful")
def test_get_entity_references_with_entry(contentful_mock):
    entry_mock = mock.Mock()
    ref1 = mock.Mock()
    ref2 = mock.Mock()
    entry_mock.incoming_references.return_value = [ref1, ref2]

    client = contentful.LibraryContentfulClient(preview=False, user_facing=False)
    refs = client.get_entity_references(entry_mock)

    entry_mock.incoming_references.assert_called_with(
        contentful_mock.Client.return_value, query={"include": 5, "locale": "en-US"}
    )
    assert refs == [ref1, ref2]


@mock.patch("learn.services.contentful.contentful")
def test_get_entry_by_id(contentful_mock):
    entry_mock = mock.Mock()
    contentful_mock.Client.return_value.entry.return_value = entry_mock

    client = contentful.LibraryContentfulClient(preview=False, user_facing=False)
    result_entry = client.get_entry_by_id("defg")

    contentful_mock.Client.return_value.entry.assert_called_with(
        "defg", query={"include": 5, "locale": "en-US"}
    )
    assert result_entry == entry_mock


@mock.patch("learn.services.contentful.contentful")
def test_get_asset_by_id(contentful_mock):
    asset_mock = mock.Mock()
    contentful_mock.Client.return_value.asset.return_value = asset_mock

    client = contentful.LibraryContentfulClient(preview=False, user_facing=False)
    result_entry = client.get_asset_by_id("defg")

    contentful_mock.Client.return_value.asset.assert_called_once_with(
        "defg", query={"locale": "en-US"}
    )
    assert result_entry == asset_mock


@mock.patch("learn.services.contentful.contentful")
def test_get_entry_by_id_or_none_entry_exists(contentful_mock):
    entry_mock = mock.Mock()
    contentful_mock.Client.return_value.entry.return_value = entry_mock

    client = contentful.LibraryContentfulClient(preview=False, user_facing=False)
    result = client.get_entry_by_id_or_none("defg")

    assert result == entry_mock


@mock.patch("learn.services.contentful.contentful")
def test_get_entry_by_id_or_none_no_entry(contentful_mock):
    contentful_mock.Client.return_value.entry.side_effect = Exception("not found")

    client = contentful.LibraryContentfulClient(preview=False, user_facing=False)
    result = client.get_entry_by_id_or_none("defg")

    assert result is None


@mock.patch("learn.services.contentful.contentful")
def test_get_articles_unsupported_locale_falls_back(contentful_mock):
    english_entry_mock = mock.Mock()
    get_entries_mock = contentful_mock.Client.return_value.entries
    # First call (for global article) gets back empty array, second gets a result
    get_entries_mock.side_effect = [[], [english_entry_mock]]

    client = contentful.LibraryContentfulClient(preview=False, user_facing=False)
    result = client.get_article_global_entries_by_slug_and_locale(
        slugs=["a-b-c"], locale="🥥"
    )

    assert result == [english_entry_mock]
    call1 = mock.call(
        {
            "content_type": "articleGlobal",
            "fields.slug[in]": ["a-b-c"],
            "locale": "🥥",
            "include": 3,
        }
    )
    call2 = mock.call(
        {
            "content_type": "article",
            "fields.slug[in]": ["a-b-c"],
            "locale": "en-US",
            "include": 3,
        }
    )
    get_entries_mock.assert_has_calls([call1, call2])


@mock.patch("learn.services.contentful.contentful")
def test_get_article_entry_by_slug(contentful_mock):
    mock_entry = mock.Mock()
    contentful_mock.Client.return_value.entries.return_value = [mock_entry]

    client = contentful.LibraryContentfulClient(preview=False, user_facing=False)
    result = client.get_article_entry_by_slug("a-b-c")

    assert result == mock_entry
    contentful_mock.Client.return_value.entries.assert_called_once_with(
        {
            "content_type": "article",
            "fields.slug[in]": ["a-b-c"],
            "locale": "en-US",
            "include": 3,
        }
    )


@mock.patch("learn.services.contentful.contentful")
def test_get_article_entries_by_slug(contentful_mock):
    mock_entry_1 = mock.Mock()
    mock_entry_2 = mock.Mock()
    contentful_mock.Client.return_value.entries.return_value = [
        mock_entry_1,
        mock_entry_2,
    ]

    client = contentful.LibraryContentfulClient(preview=False, user_facing=False)
    result = client.get_article_entries_by_slug(["a-b-c", "d-e-f"])

    assert result == [mock_entry_1, mock_entry_2]
    contentful_mock.Client.return_value.entries.assert_called_once_with(
        {
            "content_type": "article",
            "fields.slug[in]": ["a-b-c", "d-e-f"],
            "locale": "en-US",
            "include": 3,
        }
    )


@pytest.mark.parametrize("locale", ["en", "fr", "fr-CA"])
@mock.patch("learn.services.contentful.contentful")
def test_get_articles_with_only_titles_by_slug(contentful_mock, locale):
    mock_entry_1 = mock.Mock()
    mock_entry_2 = mock.Mock()
    contentful_mock.Client.return_value.entries.return_value = [
        mock_entry_1,
        mock_entry_2,
    ]

    client = contentful.LibraryContentfulClient(preview=False, user_facing=False)
    result = client.get_articles_with_only_titles_by_slug(["a-b-c", "d-e-f"], locale)

    assert result == [mock_entry_1, mock_entry_2]
    contentful_mock.Client.return_value.entries.assert_called_once_with(
        {
            "content_type": "article",
            "fields.slug[in]": ["a-b-c", "d-e-f"],
            "select": "fields.title,fields.slug",
            "locale": locale,
            "include": 0,
        }
    )


@mock.patch("learn.services.contentful.contentful")
def test_get_banner_by_slug(contentful_mock):
    banner = mock.Mock(title="🏳", slug="hey-banner-banner-⚾️")

    contentful_mock.Client.return_value.entries.return_value = [banner]

    client = contentful.LibraryContentfulClient(preview=False, user_facing=False)
    result = client.get_banners_by_slug([banner.slug])

    assert result == [banner]
    contentful_mock.Client.return_value.entries.assert_called_once_with(
        {
            "content_type": "banner",
            "fields.slug[in]": [banner.slug],
            "locale": "en-US",
            "include": 1,
        }
    )


@mock.patch("learn.services.contentful.contentful")
def test_get_courses_by_slug(contentful_mock):
    course = mock.Mock(title="🧑‍🏫", slug="🤓")

    contentful_mock.Client.return_value.entries.return_value = [course]

    client = contentful.LibraryContentfulClient(preview=False, user_facing=False)
    result = client.get_courses_by_slug([course.slug])

    assert result == [course]
    contentful_mock.Client.return_value.entries.assert_called_once_with(
        {
            "content_type": "course",
            "fields.slug[in]": [course.slug],
            "locale": "en-US",
            "include": 5,
        }
    )


@mock.patch("learn.services.contentful.contentful")
def test_get_entries_by_type_and_slug(contentful_mock):
    entry = mock.Mock(field="value", slug="🐌")

    contentful_mock.Client.return_value.entries.return_value = [entry]

    client = contentful.LibraryContentfulClient(preview=False, user_facing=False)
    result = client.get_entries_by_type_and_slug(
        ContentfulContentType.BANNER, [entry.slug], include=2
    )

    assert result == [entry]
    contentful_mock.Client.return_value.entries.assert_called_once_with(
        {
            "content_type": "banner",
            "fields.slug[in]": [entry.slug],
            "locale": "en-US",
            "include": 2,
        }
    )


@mock.patch("learn.services.contentful.contentful")
def test_get_entries_by_type_and_slug_not_found(contentful_mock):
    contentful_mock.Client.return_value.entries.return_value = []

    client = contentful.LibraryContentfulClient(preview=False, user_facing=False)
    result = client.get_entries_by_type_and_slug(
        ContentfulContentType.BANNER, ["🐌"], include=2
    )

    assert result == []
    contentful_mock.Client.return_value.entries.assert_called_once_with(
        {
            "content_type": "banner",
            "fields.slug[in]": ["🐌"],
            "locale": "en-US",
            "include": 2,
        }
    )


@mock.patch("learn.services.contentful.contentful")
def test_get_courses_by_tags(contentful_mock):
    contentful_mock.Client.return_value.entries.return_value = []

    client = contentful.LibraryContentfulClient(preview=False, user_facing=False)
    result = client.get_courses_by_tags(["pregnancy"], limit=2)

    assert result == []
    contentful_mock.Client.return_value.entries.assert_called_once_with(
        {
            "content_type": "course",
            "metadata.tags.sys.id[all]": ["pregnancy"],
            "include": 1,
            "locale": "en-US",
            "limit": 2,
        }
    )


@mock.patch("learn.services.contentful.contentful")
def test_get_courses_by_slugs(contentful_mock):
    course_mock1 = mock.Mock()
    course_mock2 = mock.Mock()
    contentful_mock.Client.return_value.entries.return_value = [
        course_mock1,
        course_mock2,
    ]

    client = contentful.LibraryContentfulClient(preview=False, user_facing=False)
    result = client.get_courses_by_slug(["🐌", "🧑‍🏫"])

    assert result == [course_mock1, course_mock2]
    contentful_mock.Client.return_value.entries.assert_called_once_with(
        {
            "content_type": "course",
            "fields.slug[in]": ["🐌", "🧑‍🏫"],
            "locale": "en-US",
            "include": 5,
        }
    )


@mock.patch("learn.services.contentful.contentful")
def test_get_video_entries_by_slugs(contentful_mock):
    video_mock1 = mock.Mock()
    video_mock2 = mock.Mock()
    contentful_mock.Client.return_value.entries.return_value = [
        video_mock1,
        video_mock2,
    ]

    client = contentful.LibraryContentfulClient(preview=False, user_facing=False)
    result = client.get_video_entries_by_slugs(["🐌", "🧑‍🏫"])

    assert result == [video_mock1, video_mock2]
    contentful_mock.Client.return_value.entries.assert_called_once_with(
        {
            "content_type": "video",
            "fields.slug[in]": ["🐌", "🧑‍🏫"],
            "locale": "en-US",
            "include": 3,
        }
    )
