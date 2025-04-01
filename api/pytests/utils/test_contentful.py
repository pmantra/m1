from dataclasses import dataclass
from typing import Dict, List
from unittest.mock import Mock

import pytest

from direct_payment.help.services.contentful import MMBContentfulClient
from utils.contentful import (
    create_link_from_entry_or_asset,
    parse_preview,
    process_rich_text_and_includes,
)


@dataclass
class MockAccordionContentType:
    __slots__ = ("id",)
    id: str


@dataclass
class MockAccordionData:
    __slots__ = ("content_type", "items", "id", "heading_level")
    content_type: MockAccordionContentType
    items: List[Dict]
    id: str
    heading_level: str


def test_process_rich_text_with_embedded_entry():
    mock_accordion_data = MockAccordionData(
        content_type=MockAccordionContentType(id="accordion"),
        items=[],
        id="6FLZDHh3pkX7XPp0Yd4qiL",
        heading_level="h2",
    )

    rich_text_input = {
        "nodeType": "document",
        "data": {},
        "content": [
            {
                "nodeType": "embedded-entry-block",
                "data": {"target": mock_accordion_data},
                "content": [],
            },
            {
                "nodeType": "paragraph",
                "data": {},
                "content": [
                    {
                        "nodeType": "text",
                        "value": "",
                        "marks": [{"type": "bold"}],
                        "data": {},
                    },
                    {
                        "nodeType": "hyperlink",
                        "data": {"uri": "https://www.google.com"},
                        "content": [
                            {
                                "nodeType": "text",
                                "value": "test link",
                                "marks": [{"type": "bold"}],
                                "data": {},
                            }
                        ],
                    },
                    {"nodeType": "text", "value": "", "marks": [], "data": {}},
                ],
            },
        ],
    }

    includes = []

    result = process_rich_text_and_includes(
        rich_text_input,
        includes,
        MMBContentfulClient._handle_embedded_entry,
        MMBContentfulClient._handle_embedded_asset,
    )

    expected_result = {
        "nodeType": "document",
        "data": {},
        "content": [
            {
                "nodeType": "embedded-entry-block",
                "data": {
                    "target": {
                        "sys": {
                            "id": "6FLZDHh3pkX7XPp0Yd4qiL",
                            "type": "Link",
                            "linkType": "Entry",
                        }
                    }
                },
                "content": [],
            },
            {
                "nodeType": "paragraph",
                "data": {},
                "content": [
                    {
                        "nodeType": "text",
                        "value": "",
                        "marks": [{"type": "bold"}],
                        "data": {},
                    },
                    {
                        "nodeType": "hyperlink",
                        "data": {"uri": "https://www.google.com"},
                        "content": [
                            {
                                "nodeType": "text",
                                "value": "test link",
                                "marks": [{"type": "bold"}],
                                "data": {},
                            }
                        ],
                    },
                    {"nodeType": "text", "value": "", "marks": [], "data": {}},
                ],
            },
        ],
    }

    assert len(includes) == 1
    assert result == expected_result


def test_create_link_from_entry():
    mock_entry = Mock()
    mock_entry.id = "12345"

    result = create_link_from_entry_or_asset(mock_entry)

    assert result == {
        "sys": {
            "id": "12345",
            "type": "Link",
            "linkType": "Entry",
        }
    }


@pytest.mark.parametrize(
    ("args", "result"),
    [
        ({}, False),
        ({"preview": ""}, False),
        ({"preview": "someothervalue"}, False),
        ({"preview": "false"}, False),
        ({"preview": "False"}, False),
        ({"preview": "true"}, True),
        ({"preview": "True"}, True),
    ],
)
def test_parse_preview(args: Dict[str, str], result: bool):
    assert parse_preview(args) == result
