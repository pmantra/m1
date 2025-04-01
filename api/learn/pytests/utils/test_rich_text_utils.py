import re
from unittest import mock

from learn.utils import rich_text_utils


def test_headers():
    node = {
        "nodeType": "document",
        "content": [
            paragraph_node(["hi", "there"]),
            {
                "nodeType": "heading2",
                "content": [
                    {"nodeType": "text", "value": "header"},
                ],
            },
            paragraph_node(["friend"]),
        ],
    }
    result_array = []
    rich_text_utils.rich_text_to_plain_string_array(node, result_array)
    result_with_trimmed_whitespace = re.sub(" +", " ", " ".join(result_array)).strip()
    assert result_with_trimmed_whitespace == "hi there header friend"


def test_callouts():
    callout_rich_text = {
        "nodeType": "document",
        "content": [
            {
                "nodeType": "heading2",
                "content": [
                    {"nodeType": "text", "value": "header"},
                ],
            },
            paragraph_node(["callout1"]),
            paragraph_node(["callout2", "callout3"]),
        ],
    }
    callout_mock = mock.Mock(rich_text=callout_rich_text)
    callout_mock.content_type.id = "callout"

    node = {
        "nodeType": "document",
        "content": [
            paragraph_node(["start"]),
            {
                "nodeType": "embedded-entry-block",
                "data": {
                    "target": callout_mock,
                },
                "content": [],
            },
            paragraph_node(["end"]),
        ],
    }
    result_array = []
    rich_text_utils.rich_text_to_plain_string_array(node, result_array)
    result_with_trimmed_whitespace = re.sub(" +", " ", " ".join(result_array)).strip()
    assert (
        result_with_trimmed_whitespace == "start header callout1 callout2 callout3 end"
    )


def test_embedded_image_with_caption():
    caption_rich_text = {
        "nodeType": "document",
        "content": [paragraph_node(["caption"])],
    }
    embedded_image_mock = mock.Mock(caption=caption_rich_text)
    embedded_image_mock.content_type.id = "embeddedImage"

    node = {
        "nodeType": "document",
        "content": [
            paragraph_node(["start"]),
            {
                "nodeType": "embedded-entry-block",
                "data": {"target": embedded_image_mock},
                "content": [],
            },
            paragraph_node(["end"]),
        ],
    }
    result_array = []
    rich_text_utils.rich_text_to_plain_string_array(node, result_array)
    result_with_trimmed_whitespace = re.sub(" +", " ", " ".join(result_array)).strip()
    assert result_with_trimmed_whitespace == "start caption end"


def test_accordion():
    item_1_attrs = {
        "header": "header1",
        "body": {
            "nodeType": "document",
            "content": [
                paragraph_node(["body1"]),
            ],
        },
    }

    item_2_attrs = {
        "header": "header2",
        "body": {
            "nodeType": "document",
            "content": [paragraph_node(["body2a", "body2b"])],
        },
    }

    accordion_mock = mock.Mock(
        items=[mock.Mock(**item_1_attrs), mock.Mock(**item_2_attrs)]
    )
    accordion_mock.content_type.id = "accordion"

    node = {
        "nodeType": "document",
        "content": [
            paragraph_node(["start"]),
            {
                "nodeType": "embedded-entry-block",
                "data": {"target": accordion_mock},
                "content": [],
            },
            paragraph_node(["end"]),
        ],
    }

    result_array = []
    rich_text_utils.rich_text_to_plain_string_array(node, result_array)
    result_with_trimmed_whitespace = re.sub(" +", " ", " ".join(result_array)).strip()
    assert (
        result_with_trimmed_whitespace
        == "start header1 body1 header2 body2a body2b end"
    )


@mock.patch("learn.services.contentful.log")
def test_unsupported_embedded_entry_is_skipped(log_mock):
    unsupported_mock = mock.Mock()
    unsupported_mock.content_type.id = "unsupportedType"
    unsupported_mock.fields.return_value.get.return_value = "embedded-slug"

    node = {
        "nodeType": "document",
        "content": [
            paragraph_node(["start"]),
            {
                "nodeType": "embedded-entry-block",
                "data": {"target": unsupported_mock},
                "content": [],
            },
            paragraph_node(["end"]),
        ],
    }
    result_array = []
    rich_text_utils.rich_text_to_plain_string_array(node, result_array)
    result_with_trimmed_whitespace = re.sub(" +", " ", " ".join(result_array)).strip()
    assert result_with_trimmed_whitespace == "start end"
    log_mock.warn.assert_called_with(
        "Unsupported entry type embedded",
        contentful_id=mock.ANY,
        content_type="unsupportedType",
        slug="embedded-slug",
        exc_info=False,
        error=None,
    )


def test_embedded_asset_is_skipped():
    asset_mock = mock.Mock(id="whatever")
    asset_mock.url.return_value = "//doma.in/img.bmp"
    asset_mock.fields.return_value.get.return_value = "description"

    asset_mock = mock.Mock()
    node = {
        "nodeType": "document",
        "content": [
            paragraph_node(["hi", "there"]),
            {
                "nodeType": "embedded-asset-block",
                "content": [],
                "data": {"target": asset_mock},
            },
            paragraph_node(["friend"]),
        ],
    }
    result_array = []
    rich_text_utils.rich_text_to_plain_string_array(node, result_array)
    result_with_trimmed_whitespace = re.sub(" +", " ", " ".join(result_array)).strip()
    assert result_with_trimmed_whitespace == "hi there friend"


def paragraph_node(contents: list):
    return {
        "nodeType": "paragraph",
        "data": {},
        "content": [{"nodeType": "text", "value": content} for content in contents],
    }
