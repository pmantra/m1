from typing import Dict

import contentful

from learn.models import rich_text_embeds
from learn.services.contentful import LibraryContentfulClient


def rich_text_to_plain_string_array(root_node: Dict, string_array: list) -> None:
    # Inspired by @contentful/rich-text-plain-text-renderer
    if not root_node or not root_node["content"]:
        return
    for node in root_node["content"]:
        if node["nodeType"] == "text":
            string_array.append(node["value"])
        elif node["nodeType"] == "embedded-entry-block":
            embedded_entry = node["data"]["target"]
            _embedded_entry_to_plain(embedded_entry, string_array)
        elif node["nodeType"] == "embedded-asset-block":
            # Confirmed that alt text is not meant to be searchable
            continue
        else:
            rich_text_to_plain_string_array(node, string_array)


def _embedded_entry_to_plain(entry: contentful.Entry, string_array: list) -> None:
    content_type = entry.content_type.id
    if content_type == rich_text_embeds.EmbeddedEntryType.ACCORDION.value:
        for item in entry.items:
            string_array.append(item.header)
            rich_text_to_plain_string_array(item.body, string_array)
    elif content_type == rich_text_embeds.EmbeddedEntryType.CALLOUT.value:
        rich_text_to_plain_string_array(entry.rich_text, string_array)
    elif content_type == rich_text_embeds.EmbeddedEntryType.EMBEDDED_IMAGE.value:
        rich_text_to_plain_string_array(entry.caption, string_array)
    elif content_type == rich_text_embeds.EmbeddedEntryType.EMBEDDED_VIDEO.value:
        # TODO: support search by caption [COCO-1666]
        pass
    else:
        # If someone has embedded an unsupported entry, continue
        LibraryContentfulClient.log_warning_about_contentful_entry(
            "Unsupported entry type embedded", entry
        )
