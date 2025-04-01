from typing import Any, Dict, List
from unittest import mock

import pytest
from contentful import Asset, Entry

from learn.models import rich_text_embeds
from learn.services import read_time_service
from learn.services.contentful_caching_service import TTL

__SLUG = "𓆑"

# this is about 250 words total so ~2 minutes reading time when rounded up

__LONG_RICH_TEXT = {
    "nodeType": "document",
    "content": [
        {
            "nodeType": "paragraph",
            "content": [
                {"nodeType": "text", "value": "Somebody once told me"},
                {"nodeType": "text", "value": "the world is gonna roll me"},
            ],
        },
        {"nodeType": "text", "value": "I ain't the sharpest tool in the shed"},
        {
            "nodeType": "paragraph",
            "content": [
                {"nodeType": "text", "value": "She was looking kinda dumb"},
                {"nodeType": "text", "value": "with her finger and her thumb"},
            ],
        },
        {"nodeType": "text", "value": "in the shape of an L on her forehead"},
        {"nodeType": "text", "value": "well"},
        {
            "nodeType": "paragraph",
            "content": [
                {
                    "nodeType": "text",
                    "value": "The years start coming and they don't stop coming",
                },
                {
                    "nodeType": "text",
                    "value": "Fed to the rules and I hit the ground running",
                },
                {
                    "nodeType": "text",
                    "value": "Didn't make sense not to live for fun",
                },
                {
                    "nodeType": "text",
                    "value": "Your brain gets smart but your head gets dumb",
                },
                {
                    "nodeType": "paragraph",
                    "content": [
                        {
                            "nodeType": "embedded-entry-block",
                            "data": {
                                "target": mock.Mock(
                                    spec=Entry,
                                    content_type=mock.Mock(
                                        id=rich_text_embeds.EmbeddedEntryType.ACCORDION.value
                                    ),
                                    items=[
                                        mock.Mock(
                                            header="So much",
                                            body={
                                                "nodeType": "document",
                                                "content": [
                                                    {
                                                        "nodeType": "text",
                                                        "value": "to do",
                                                    }
                                                ],
                                            },
                                        ),
                                        mock.Mock(
                                            header="So much",
                                            body={
                                                "nodeType": "document",
                                                "content": [
                                                    {
                                                        "nodeType": "text",
                                                        "value": "to see",
                                                    }
                                                ],
                                            },
                                        ),
                                    ],
                                )
                            },
                        },
                        {
                            "nodeType": "text",
                            "value": "So what's wrong with taking the back streets?",
                        },
                    ],
                },
                {
                    "nodeType": "text",
                    "value": "You'll never know if you don't go",
                },
                {
                    "nodeType": "text",
                    "value": "You'll never shine if you don't glow",
                },
            ],
        },
        {
            "nodeType": "paragraph",
            "content": [
                {"nodeType": "text", "value": "Hey now"},
                {"nodeType": "text", "value": "You're an all star"},
                {"nodeType": "text", "value": "Get your game on"},
                {"nodeType": "text", "value": "Go play"},
            ],
        },
        {
            "nodeType": "paragraph",
            "content": [
                {"nodeType": "text", "value": "Hey now"},
                {"nodeType": "text", "value": "You're a rock star"},
                {"nodeType": "text", "value": "Get the show on"},
                {"nodeType": "text", "value": "Get played"},
            ],
        },
        {"nodeType": "text", "value": "And all that glitters is gold"},
        {"nodeType": "text", "value": "Only shooting stars break the mold"},
        {
            "nodeType": "paragraph",
            "content": [
                {"nodeType": "text", "value": "It's a cool place"},
                {"nodeType": "text", "value": "and they say it gets colder"},
            ],
        },
        {
            "nodeType": "text",
            "value": "You're bundled up now, wait til you get older",
        },
        {
            "nodeType": "paragraph",
            "content": [
                {
                    "nodeType": "text",
                    "value": "But the media men beg to differ",
                },
                {
                    "nodeType": "text",
                    "value": "judging by the hole in the satellite picture",
                },
            ],
        },
        {
            "nodeType": "text",
            "value": "The ice we skate is getting pretty thin",
        },
        {
            "nodeType": "text",
            "value": "The water's getting warm so you might as well swim",
        },
        {"nodeType": "text", "value": "My world's on fire, how bout yours?"},
        {
            "nodeType": "text",
            "value": "That's the way I like it and I'll never get bored",
        },
        {
            "nodeType": "paragraph",
            "content": [
                {"nodeType": "text", "value": "Hey now"},
                {"nodeType": "text", "value": "You're an all star"},
                {"nodeType": "text", "value": "Get your game on"},
                {"nodeType": "text", "value": "Go play"},
            ],
        },
        {
            "nodeType": "paragraph",
            "content": [
                {"nodeType": "text", "value": "Hey now"},
                {"nodeType": "text", "value": "You're a rock star"},
                {"nodeType": "text", "value": "Get the show on"},
                {"nodeType": "text", "value": "Get played"},
            ],
        },
        {"nodeType": "text", "value": "And all that glitters is gold"},
        {"nodeType": "text", "value": "Only shooting stars break the mold"},
    ],
}
__EXPECTED_READ_TIME_MINUTES = 2

__TEXT_NODE = {
    "nodeType": "text",
    "value": "this is a short string for your reading pleasure!",
}

__KEY = f"estimated_read_time_minutes:{__SLUG}"


def __build_video_node():
    video_node = {
        "nodeType": "embedded-entry-block",
        "data": {
            "target": mock.Mock(
                spec=Entry,
                id="video",
                video_link="https://link/tovideo.test/video.mp4",
                thumbnail=mock.Mock(),
                captions=mock.Mock(),
                content_type=mock.Mock(
                    id=rich_text_embeds.EmbeddedEntryType.EMBEDDED_VIDEO.value
                ),
            )
        },
    }
    video_node["data"]["target"].thumbnail.url.return_value = "//domain.test/thumbnail"
    video_node["data"]["target"].thumbnail.fields.return_value = {"description": None}
    video_node["data"][
        "target"
    ].captions.url.return_value = "//domain.test/captions.vtt"
    video_node["data"]["target"].fields.return_value = {
        "thumbnail": video_node["data"]["target"].thumbnail
    }
    return video_node


def __build_accordion_node(nodes: List[Dict[str, Any]]):
    return {
        "nodeType": "embedded-entry-block",
        "data": {
            "target": mock.Mock(
                spec=Entry,
                id="accordion",
                content_type=mock.Mock(
                    id=rich_text_embeds.EmbeddedEntryType.ACCORDION.value
                ),
                heading_level="heading level?",
                items=[
                    mock.Mock(
                        header="header",
                        body={"nodeType": "document", "content": [node]},
                    )
                    for node in nodes
                ],
            )
        },
    }


def __build_embedded_asset_node():
    embedded_assets_node = {
        "nodeType": "embedded-asset-block",
        "data": {"target": mock.Mock(spec=Asset, id="embedded-asset")},
    }
    embedded_assets_node["data"]["target"].url.return_value = "//doma.in/img.bmp"
    return embedded_assets_node


@mock.patch("learn.services.contentful.LibraryContentfulClient")
@mock.patch("learn.services.caching_service.redis_client")
def test_get_value_error_initializing_redis_client(
    mock_redis_client_method, mock_contentful_client_constructor
):
    mock_redis_client_method.side_effect = Exception
    mock_contentful_client_constructor.return_value.get_article_entries_by_slug.return_value = [
        mock.Mock(slug=__SLUG, rich_text=__LONG_RICH_TEXT)
    ]

    assert (
        read_time_service.ReadTimeService().get_value(__SLUG)
        == __EXPECTED_READ_TIME_MINUTES
    )

    mock_contentful_client_constructor.assert_called_once_with(
        preview=False, user_facing=True
    )
    mock_contentful_client_constructor.return_value.get_article_entries_by_slug.assert_called_once_with(
        [__SLUG]
    )


@pytest.mark.parametrize("value", (__EXPECTED_READ_TIME_MINUTES, -1))
@mock.patch("learn.services.contentful.LibraryContentfulClient")
@mock.patch("learn.services.caching_service.redis_client")
def test_get_value_already_in_cache(mock_redis_client_method, _, value: int):
    mock_redis_client_method.return_value.pipeline.return_value.execute.return_value = [
        str(value)
    ]

    assert read_time_service.ReadTimeService().get_value(__SLUG) == (
        value if value > 0 else None
    )

    mock_redis_client_method.return_value.pipeline.return_value.get.assert_called_once_with(
        __KEY
    )
    mock_redis_client_method.return_value.pipeline.return_value.execute.assert_called_once_with()


@mock.patch("learn.services.contentful.LibraryContentfulClient")
@mock.patch("learn.services.caching_service.redis_client")
def test_get_value_article_not_found(
    mock_redis_client_method, mock_contentful_client_constructor
):
    mock_redis_client_method.return_value.pipeline.return_value.execute.return_value = [
        None
    ]
    mock_contentful_client_constructor.return_value.get_article_entries_by_slug.return_value = [
        None
    ]

    assert read_time_service.ReadTimeService().get_value(__SLUG) is None

    mock_redis_client_method.return_value.pipeline.return_value.get.assert_called_once_with(
        __KEY
    )
    mock_redis_client_method.return_value.pipeline.return_value.execute.assert_called_once_with()
    mock_contentful_client_constructor.assert_called_once_with(
        preview=False, user_facing=True
    )
    mock_contentful_client_constructor.return_value.get_article_entries_by_slug.assert_called_once_with(
        [__SLUG]
    )
    mock_redis_client_method.return_value.set.assert_not_called()


@pytest.mark.parametrize(
    ("rich_text", "expected_estimated_read_time_minutes"),
    (
        ({"content": []}, 1),
        (__LONG_RICH_TEXT, __EXPECTED_READ_TIME_MINUTES),
        ({"content": [__build_video_node()]}, -1),
        ({"content": [__TEXT_NODE, __build_video_node()]}, -1),
        ({"content": [__build_accordion_node([__TEXT_NODE, __TEXT_NODE])]}, 1),
        (
            {
                "content": [
                    __build_accordion_node([__TEXT_NODE, __TEXT_NODE]),
                    __build_video_node(),
                ]
            },
            -1,
        ),
        ({"content": [__build_embedded_asset_node()]}, 1),
    ),
)
@mock.patch("learn.services.contentful.LibraryContentfulClient")
@mock.patch("learn.services.caching_service.redis_client")
def test_get_value_not_in_cache(
    mock_redis_client_method,
    mock_contentful_client_constructor,
    rich_text: Dict[str, Any],
    expected_estimated_read_time_minutes: int,
):
    mock_redis_client_method.return_value.pipeline.return_value.execute.return_value = [
        None
    ]
    mock_contentful_client_constructor.return_value.get_article_entries_by_slug.return_value = [
        mock.Mock(rich_text=rich_text, slug=__SLUG)
    ]

    assert read_time_service.ReadTimeService().get_value(__SLUG) == (
        expected_estimated_read_time_minutes
        if expected_estimated_read_time_minutes > 0
        else None
    )

    mock_redis_client_method.return_value.pipeline.return_value.get.assert_called_once_with(
        __KEY
    )
    mock_redis_client_method.return_value.pipeline.return_value.execute.assert_has_calls(
        [mock.call(), mock.call()]
    )
    mock_contentful_client_constructor.assert_called_once_with(
        preview=False, user_facing=True
    )
    mock_contentful_client_constructor.return_value.get_article_entries_by_slug.assert_called_once_with(
        [__SLUG]
    )
    mock_redis_client_method.return_value.pipeline.return_value.set.assert_called_once_with(
        __KEY, str(expected_estimated_read_time_minutes), ex=TTL
    )


@mock.patch("learn.services.contentful.LibraryContentfulClient")
@mock.patch("learn.services.caching_service.redis_client")
def test_get_value_error_reading_from_cache(
    mock_redis_client_method,
    mock_contentful_client_constructor,
):
    mock_redis_client_method.return_value.pipeline.return_value.execute.side_effect = (
        Exception
    )
    mock_contentful_client_constructor.return_value.get_article_entries_by_slug.return_value = [
        mock.Mock(rich_text=__LONG_RICH_TEXT, slug=__SLUG)
    ]

    assert (
        read_time_service.ReadTimeService().get_value(__SLUG)
        == __EXPECTED_READ_TIME_MINUTES
    )

    mock_redis_client_method.return_value.pipeline.return_value.get.assert_called_once_with(
        __KEY
    )
    mock_redis_client_method.return_value.pipeline.return_value.execute.assert_has_calls(
        [mock.call(), mock.call()]
    )
    mock_contentful_client_constructor.assert_called_once_with(
        preview=False, user_facing=True
    )
    mock_contentful_client_constructor.return_value.get_article_entries_by_slug.assert_called_once_with(
        [__SLUG]
    )
    mock_redis_client_method.return_value.pipeline.return_value.set.assert_called_once_with(
        __KEY, str(__EXPECTED_READ_TIME_MINUTES), ex=TTL
    )


@mock.patch("learn.services.contentful.LibraryContentfulClient")
@mock.patch("learn.services.caching_service.redis_client")
def test_get_value_bad_data_in_cache(
    mock_redis_client_method,
    mock_contentful_client_constructor,
):
    mock_redis_client_method.return_value.pipeline.return_value.execute.return_value = [
        "I am not an int!"
    ]
    mock_contentful_client_constructor.return_value.get_article_entries_by_slug.return_value = [
        mock.Mock(rich_text=__LONG_RICH_TEXT, slug=__SLUG)
    ]

    assert (
        read_time_service.ReadTimeService().get_value(__SLUG)
        == __EXPECTED_READ_TIME_MINUTES
    )

    mock_redis_client_method.return_value.pipeline.return_value.get.assert_called_once_with(
        __KEY
    )
    mock_redis_client_method.return_value.pipeline.return_value.execute.assert_has_calls(
        [mock.call(), mock.call()]
    )
    mock_redis_client_method.return_value.delete.assert_called_once_with(__KEY)
    mock_contentful_client_constructor.assert_called_once_with(
        preview=False, user_facing=True
    )
    mock_contentful_client_constructor.return_value.get_article_entries_by_slug.assert_called_once_with(
        [__SLUG]
    )
    mock_redis_client_method.return_value.pipeline.return_value.set.assert_called_once_with(
        __KEY, str(__EXPECTED_READ_TIME_MINUTES), ex=TTL
    )


@mock.patch("learn.services.contentful.LibraryContentfulClient")
@mock.patch("learn.services.caching_service.redis_client")
def test_get_value_error_from_contentful(
    mock_redis_client_method, mock_contentful_client_constructor
):
    mock_redis_client_method.return_value.pipeline.return_value.execute.return_value = [
        None
    ]
    mock_contentful_client_constructor.return_value.get_article_entries_by_slug.side_effect = (
        Exception
    )

    assert read_time_service.ReadTimeService().get_value(__SLUG) is None

    mock_redis_client_method.return_value.pipeline.return_value.get.assert_called_once_with(
        __KEY
    )
    mock_redis_client_method.return_value.pipeline.return_value.execute.assert_called_once_with()
    mock_contentful_client_constructor.assert_called_once_with(
        preview=False, user_facing=True
    )
    mock_contentful_client_constructor.return_value.get_article_entries_by_slug.assert_called_once_with(
        [__SLUG]
    )
    mock_redis_client_method.return_value.set.assert_not_called()


@mock.patch("learn.services.contentful.LibraryContentfulClient")
@mock.patch("learn.services.caching_service.redis_client")
def test_get_value_error_writing_to_cache(
    mock_redis_client_method, mock_contentful_client_constructor
):
    mock_redis_client_method.return_value.pipeline.return_value.execute.return_value = [
        None
    ]
    mock_contentful_client_constructor.return_value.get_article_entries_by_slug.return_value = [
        mock.Mock(rich_text=__LONG_RICH_TEXT, slug=__SLUG)
    ]
    mock_redis_client_method.return_value.set.side_effect = Exception

    assert (
        read_time_service.ReadTimeService().get_value(__SLUG)
        == __EXPECTED_READ_TIME_MINUTES
    )

    mock_redis_client_method.return_value.pipeline.return_value.get.assert_called_once_with(
        __KEY
    )
    mock_redis_client_method.return_value.pipeline.return_value.execute.assert_has_calls(
        [mock.call(), mock.call()]
    )
    mock_contentful_client_constructor.assert_called_once_with(
        preview=False, user_facing=True
    )
    mock_contentful_client_constructor.return_value.get_article_entries_by_slug.assert_called_once_with(
        [__SLUG]
    )
    mock_redis_client_method.return_value.pipeline.return_value.set.assert_called_once_with(
        __KEY, str(__EXPECTED_READ_TIME_MINUTES), ex=TTL
    )


@mock.patch("learn.services.contentful.LibraryContentfulClient")
@mock.patch("learn.services.caching_service.redis_client")
def test_get_values(mock_redis_client_method, mock_contentful_client_constructor):
    mock_redis_client_method.return_value.pipeline.return_value.execute.return_value = [
        1,
        None,
    ]
    mock_contentful_client_constructor.return_value.get_article_entries_by_slug.return_value = [
        mock.Mock(rich_text=__LONG_RICH_TEXT, slug=__SLUG)
    ]

    assert read_time_service.ReadTimeService().get_values(["slug-1", __SLUG]) == {
        "slug-1": 1,
        __SLUG: __EXPECTED_READ_TIME_MINUTES,
    }

    mock_redis_client_method.return_value.pipeline.return_value.get.assert_has_calls(
        [
            mock.call("estimated_read_time_minutes:slug-1"),
            mock.call(f"estimated_read_time_minutes:{__SLUG}"),
        ]
    )
    mock_redis_client_method.return_value.pipeline.return_value.execute.assert_has_calls(
        [mock.call(), mock.call()]
    )
    mock_contentful_client_constructor.assert_called_once_with(
        preview=False, user_facing=True
    )
    mock_contentful_client_constructor.return_value.get_article_entries_by_slug.assert_called_once_with(
        [__SLUG]
    )
    mock_redis_client_method.return_value.pipeline.return_value.set.assert_called_once_with(
        f"estimated_read_time_minutes:{__SLUG}",
        str(__EXPECTED_READ_TIME_MINUTES),
        ex=TTL,
    )


@mock.patch("learn.services.contentful.LibraryContentfulClient")
@mock.patch("learn.services.caching_service.redis_client")
def test_get_values_without_filtering(mock_redis_client_method, _):
    mock_redis_client_method.return_value.pipeline.return_value.execute.return_value = [
        -1,
        -1,
    ]

    assert read_time_service.ReadTimeService().get_values_without_filtering(
        ["slug-1", "slug-2"]
    ) == {
        "slug-1": -1,
        "slug-2": -1,
    }

    mock_redis_client_method.return_value.pipeline.return_value.get.assert_has_calls(
        [
            mock.call("estimated_read_time_minutes:slug-1"),
            mock.call("estimated_read_time_minutes:slug-2"),
        ]
    )
    mock_redis_client_method.return_value.pipeline.return_value.execute.assert_called_once_with()


@mock.patch("learn.services.contentful.LibraryContentfulClient")
@mock.patch("learn.services.caching_service.redis_client")
def test_save_value_in_cache_error_initializing_redis_client(
    mock_redis_client_method, _
):
    mock_redis_client_method.side_effect = Exception
    with pytest.raises(RuntimeError):
        read_time_service.ReadTimeService().save_value_in_cache(
            __SLUG, __EXPECTED_READ_TIME_MINUTES
        )


@mock.patch("learn.services.contentful.LibraryContentfulClient")
@mock.patch("learn.services.caching_service.redis_client")
def test_save_value_in_cache(mock_redis_client_method, _):
    read_time_service.ReadTimeService().save_value_in_cache(
        __SLUG, __EXPECTED_READ_TIME_MINUTES
    )

    mock_redis_client_method.return_value.set.assert_called_once_with(
        __KEY, str(__EXPECTED_READ_TIME_MINUTES), ex=TTL
    )


@mock.patch("learn.services.contentful.LibraryContentfulClient")
@mock.patch("learn.services.caching_service.redis_client")
def test_remove_value_from_cache(
    mock_redis_client_method, mock_contentful_client_constructor
):
    entry_id = "12345abcde"
    mock_contentful_client_constructor.return_value.get_entry_by_id.return_value.slug = (
        __SLUG
    )

    read_time_service.ReadTimeService().remove_value_from_cache(entry_id)

    mock_contentful_client_constructor.assert_has_calls(
        [
            mock.call(preview=False, user_facing=True),
            mock.call(preview=True, user_facing=False),
        ]
    )
    mock_contentful_client_constructor.return_value.get_entry_by_id.assert_called_once_with(
        entry_id
    )
    mock_redis_client_method.return_value.delete.assert_called_once_with(__KEY)
