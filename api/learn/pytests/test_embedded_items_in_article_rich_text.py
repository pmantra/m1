from unittest import mock

import pytest
from contentful import Asset, Entry

from learn.models.rich_text_embeds import EmbeddedEntryType
from learn.pytests.services.test_contentful_service import (  # noqa: F401
    clear_contentful_clients,
)
from learn.services import article_service
from learn.services.contentful import ContentfulContentType

__SLUG = "s-l-u-g"


@mock.patch("learn.services.contentful.contentful")
@mock.patch("learn.services.contentful.log")
def test_unsupported_embedded_entry(log_mock, _):
    entry_mock = mock.Mock(content_type=mock.Mock(id=ContentfulContentType.ARTICLE))
    embedded_entry_mock = mock.Mock(
        spec=Entry,
        id="12345",
        content_type=mock.Mock(id="unsupportedType"),
        fields=mock.Mock(return_value={"slug": "embedded-slug"}),
    )
    entry_mock.rich_text = {
        "data": {},
        "content": [
            {
                "data": {"target": embedded_entry_mock},
                "content": [],
                "nodeType": "embedded-entry-block",
            }
        ],
        "nodeType": "document",
    }
    article_svc = article_service.ArticleService(preview=False, user_facing=True)

    with pytest.raises(ValueError):
        article_svc.entry_to_article_dict(entry_mock)
    log_mock.warn.assert_called_with(
        "Unsupported entry type embedded",
        contentful_id=mock.ANY,
        content_type="unsupportedType",
        slug="embedded-slug",
        exc_info=False,
        error=None,
    )


@mock.patch("learn.services.contentful.contentful")
def test_accordion_in_rich_text(contentful_mock):
    entry_mock = mock.Mock(content_type=mock.Mock(id=ContentfulContentType.ARTICLE))
    entry_mock.fields.return_value = {"reviewed_by": None, "related_reads": []}
    embedded_entry_id = "embeddedid"
    heading_level = "h3"
    embedded_entry_mock = mock.Mock(
        spec=Entry,
        id=embedded_entry_id,
        heading_level=heading_level,
        content_type=mock.Mock(id=EmbeddedEntryType.ACCORDION),
    )

    item_attrs = {
        "header": "item header",
        "body": {
            "nodeType": "document",
            "data": {},
            "content": [],
        },
    }
    item_mock = mock.Mock(**item_attrs)
    embedded_entry_mock.items = [item_mock]
    entry_mock.slug = __SLUG
    entry_mock.rich_text = {
        "data": {},
        "content": [
            {
                "data": {"target": embedded_entry_mock},
                "content": [],
                "nodeType": "embedded-entry-block",
            }
        ],
        "nodeType": "document",
    }
    contentful_mock.Client.return_value.entries.return_value = [entry_mock]
    article_svc = article_service.ArticleService(preview=False, user_facing=True)

    result = article_svc.get_value(__SLUG)
    assert result["rich_text"] == {
        "data": {},
        "content": [
            {
                "data": {
                    "target": {
                        "sys": {
                            "id": embedded_entry_id,
                            "type": "Link",
                            "linkType": "Entry",
                        }
                    }
                },
                "content": [],
                "nodeType": "embedded-entry-block",
            }
        ],
        "nodeType": "document",
    }

    assert result["rich_text_includes"] == [
        {
            "id": embedded_entry_id,
            "entry_type": "accordion",
            "heading_level": heading_level,
            "items": [{"title": item_attrs["header"], "rich_text": item_attrs["body"]}],
        }
    ]


@mock.patch("learn.services.contentful.contentful")
def test_callout_in_rich_text(contentful_mock):
    entry_mock = mock.Mock(content_type=mock.Mock(id=ContentfulContentType.ARTICLE))
    entry_mock.fields.return_value = {"reviewed_by": None, "related_reads": []}
    embedded_entry_id = "embeddedid"
    embedded_rich_text = {
        "nodeType": "document",
        "data": {},
        "content": [],
    }
    embedded_entry_mock = mock.Mock(
        spec=Entry,
        id=embedded_entry_id,
        rich_text=embedded_rich_text,
        content_type=mock.Mock(id=EmbeddedEntryType.CALLOUT),
    )

    entry_mock.slug = __SLUG
    entry_mock.rich_text = {
        "data": {},
        "content": [
            {
                "data": {"target": embedded_entry_mock},
                "content": [],
                "nodeType": "embedded-entry-block",
            }
        ],
        "nodeType": "document",
    }
    contentful_mock.Client.return_value.entries.return_value = [entry_mock]
    article_svc = article_service.ArticleService(preview=False, user_facing=True)

    result = article_svc.get_value(__SLUG)
    assert result["rich_text"] == {
        "data": {},
        "content": [
            {
                "data": {
                    "target": {
                        "sys": {
                            "id": embedded_entry_id,
                            "type": "Link",
                            "linkType": "Entry",
                        }
                    }
                },
                "content": [],
                "nodeType": "embedded-entry-block",
            }
        ],
        "nodeType": "document",
    }
    assert result["rich_text_includes"] == [
        {
            "id": embedded_entry_id,
            "entry_type": "callout",
            "rich_text": embedded_rich_text,
        }
    ]


@pytest.mark.parametrize("with_thumbnail", [True, False])
@mock.patch("learn.services.contentful.contentful")
def test_video_in_rich_text(contentful_mock, with_thumbnail):
    entry_mock = mock.Mock(content_type=mock.Mock(id=ContentfulContentType.ARTICLE))
    entry_mock.fields.return_value = {"reviewed_by": None, "related_reads": []}
    embedded_entry_id = "embeddedid"

    if with_thumbnail:
        thumbnail_mock = mock.Mock()
        thumbnail_mock.url.return_value = "//domain.test/thumbnail"
        thumbnail_mock.fields.return_value = {"description": None}

    captions_mock = mock.Mock()
    captions_mock.url.return_value = "//domain.test/captions.vtt"

    if with_thumbnail:
        embedded_entry_mock = mock.Mock(
            spec=Entry,
            id=embedded_entry_id,
            content_type=mock.Mock(id=EmbeddedEntryType.EMBEDDED_VIDEO),
            video_link="https://link/tovideo.test/video.mp4",
            thumbnail=thumbnail_mock,
            captions=captions_mock,
        )
        embedded_entry_mock.fields.return_value = {"thumbnail": thumbnail_mock}
    else:
        embedded_entry_mock = mock.Mock(
            spec=Entry,
            id=embedded_entry_id,
            content_type=mock.Mock(id=EmbeddedEntryType.EMBEDDED_VIDEO),
            video_link="https://link/tovideo.test/video.mp4",
            captions=captions_mock,
        )
        embedded_entry_mock.fields.return_value = {}
    embedded_entry_mock.content_type.id = "embeddedVideo"

    entry_mock.slug = __SLUG
    entry_mock.rich_text = {
        "data": {},
        "content": [
            {
                "data": {"target": embedded_entry_mock},
                "content": [],
                "nodeType": "embedded-entry-block",
            }
        ],
        "nodeType": "document",
    }
    contentful_mock.Client.return_value.entries.return_value = [entry_mock]
    article_svc = article_service.ArticleService(preview=False, user_facing=True)

    result = article_svc.get_value(__SLUG)

    assert result["rich_text"] == {
        "data": {},
        "content": [
            {
                "data": {
                    "target": {
                        "sys": {
                            "id": embedded_entry_id,
                            "type": "Link",
                            "linkType": "Entry",
                        }
                    }
                },
                "content": [],
                "nodeType": "embedded-entry-block",
            }
        ],
        "nodeType": "document",
    }
    assert result["rich_text_includes"] == [
        {
            "captions_link": "https://domain.test/captions.vtt",
            "entry_type": "embeddedVideo",
            "id": "embeddedid",
            "thumbnail": {"description": None, "url": "https://domain.test/thumbnail"}
            if with_thumbnail
            else None,
            "video_link": "https://link/tovideo.test/video.mp4",
        }
    ]


@mock.patch("learn.services.contentful.contentful")
def test_embedded_image_in_rich_text(contentful_mock):
    entry_mock = mock.Mock(content_type=mock.Mock(id=ContentfulContentType.ARTICLE))
    entry_mock.fields.return_value = {"reviewed_by": None, "related_reads": []}
    embedded_entry_id = "embeddedid"

    description = "A brown dachshund wearing a spotted bowtie"
    asset_mock = mock.Mock()
    asset_mock.url.return_value = "//doma.in/img.bmp"
    asset_mock.fields.return_value.get.return_value = description
    embedded_rich_text = {
        "nodeType": "document",
        "data": {},
        "content": [
            {
                "data": {},
                "content": [
                    {"data": {}, "marks": [], "value": "caption", "nodeType": "text"}
                ],
                "nodeType": "paragraph",
            }
        ],
    }
    embedded_entry_mock = mock.Mock(
        spec=Entry,
        id=embedded_entry_id,
        content_type=mock.Mock(id=EmbeddedEntryType.EMBEDDED_IMAGE),
        image=asset_mock,
        caption=embedded_rich_text,
    )
    embedded_entry_mock.content_type.id = "embeddedImage"

    entry_mock.slug = __SLUG
    entry_mock.rich_text = {
        "data": {},
        "content": [
            {
                "data": {"target": embedded_entry_mock},
                "content": [],
                "nodeType": "embedded-entry-block",
            }
        ],
        "nodeType": "document",
    }

    contentful_mock.Client.return_value.entries.return_value = [entry_mock]
    article_svc = article_service.ArticleService(preview=False, user_facing=True)

    result = article_svc.get_value(__SLUG)
    assert result["rich_text"] == {
        "data": {},
        "content": [
            {
                "data": {
                    "target": {
                        "sys": {
                            "id": embedded_entry_id,
                            "type": "Link",
                            "linkType": "Entry",
                        }
                    }
                },
                "content": [],
                "nodeType": "embedded-entry-block",
            }
        ],
        "nodeType": "document",
    }
    assert result["rich_text_includes"] == [
        {
            "id": embedded_entry_id,
            "image": {
                "url": "https://doma.in/img.bmp",
                "description": description,
            },
            "entry_type": "embeddedImage",
            "caption": embedded_rich_text,
        }
    ]


@mock.patch("learn.services.contentful.contentful")
def test_embedded_asset_in_rich_text(contentful_mock):
    entry_mock = mock.Mock(content_type=mock.Mock(id=ContentfulContentType.ARTICLE))
    entry_mock.fields.return_value = {"reviewed_by": None, "related_reads": []}
    embedded_asset_id = "embeddedid"

    description = "A brown dachshund wearing a spotted bowtie"
    asset_mock = mock.Mock(spec=Asset)
    asset_mock.id = embedded_asset_id
    asset_mock.url.return_value = "//doma.in/img.bmp"
    asset_mock.fields.return_value.get.return_value = description

    entry_mock.slug = __SLUG
    entry_mock.rich_text = {
        "data": {},
        "content": [
            {
                "data": {"target": asset_mock},
                "content": [],
                "nodeType": "embedded-asset-block",
            }
        ],
        "nodeType": "document",
    }

    contentful_mock.Client.return_value.entries.return_value = [entry_mock]
    article_svc = article_service.ArticleService(preview=False, user_facing=True)

    result = article_svc.get_value(__SLUG)
    assert result["rich_text"] == {
        "data": {},
        "content": [
            {
                "data": {
                    "target": {
                        "sys": {
                            "id": embedded_asset_id,
                            "type": "Link",
                            "linkType": "Entry",
                        }
                    }
                },
                "content": [],
                "nodeType": "embedded-entry-block",  # convert to entry for the front ends
            }
        ],
        "nodeType": "document",
    }
    assert result["rich_text_includes"] == [
        {
            "caption": None,
            "id": embedded_asset_id,
            "image": {
                "url": "https://doma.in/img.bmp",
                "description": description,
            },
            "entry_type": "embeddedImage",
        }
    ]


@mock.patch("learn.services.contentful.contentful")
def test_article_global(contentful_mock):
    entry_mock = mock.Mock()
    entry_mock.fields.return_value = {"reviewed_by": None, "related_reads": []}
    entry_mock.slug = __SLUG
    entry_mock.rich_text = {
        "data": {},
        "content": [],
        "nodeType": "document",
    }

    global_entry_mock = mock.Mock(
        content_type=mock.Mock(id=ContentfulContentType.ARTICLE_GLOBAL),
        article=entry_mock,
        slug=__SLUG,
    )

    contentful_mock.Client.return_value.entries.return_value = [global_entry_mock]
    article_svc = article_service.ArticleService(preview=False, user_facing=True)

    result = article_svc.get_value(__SLUG)
    assert result["rich_text"] == {
        "data": {},
        "content": [],
        "nodeType": "document",
    }
