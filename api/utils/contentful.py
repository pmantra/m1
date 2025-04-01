from typing import Dict, Union

import contentful

from utils import log

log = log.logger(__name__)


def process_rich_text_and_includes(  # type: ignore[no-untyped-def] # Function is missing a return type annotation #type: ignore[no-untyped-def] # Function is missing a type annotation for one or more arguments
    rich_text: dict,
    includes: list,
    handle_embedded_entry,
    handle_embedded_asset,
):
    # Assumes embedded entries will be at the top level of rich text, i.e. not nested in other
    # nodes. We should not be allowing inline embeds, so this should hold true
    for node in rich_text["content"]:
        if node["nodeType"] == "embedded-entry-block":
            entry = node["data"]["target"]

            includes.append(handle_embedded_entry(entry=entry))
            # Replace entry with a fake link, the only important part of which is the id
            node["data"]["target"] = create_link_from_entry_or_asset(entry)
        elif node["nodeType"] == "embedded-asset-block":
            asset = node["data"]["target"]
            includes.append(handle_embedded_asset(asset=asset))
            # Replace asset with a fake entry link, the only important part of which is the id
            node["nodeType"] = "embedded-entry-block"
            node["data"]["target"] = create_link_from_entry_or_asset(asset)
    return rich_text


def create_link_from_entry_or_asset(  # type: ignore[no-untyped-def] # Function is missing a return type annotation
    entry_or_asset: Union[contentful.Entry, contentful.Asset]
):
    return {
        "sys": {
            "id": entry_or_asset.id,
            "type": "Link",
            "linkType": "Entry",
        }
    }


def log_warning_about_contentful_entry(message, entry, exc_info=False, error=None):  # type: ignore[no-untyped-def] # Function is missing a type annotation
    log.warn(  # type: ignore[attr-defined] # Module has no attribute "warn"
        message,
        contentful_id=entry.id,
        content_type=entry.content_type.id,
        slug=entry.fields().get("slug"),
        exc_info=exc_info,
        error=error,
    )


def parse_preview(request_args: Dict[str, str]) -> bool:
    return request_args.get("preview", "").lower() == "true"
