import dataclasses
import os
from typing import Any, Dict, Optional

import contentful

from direct_payment.help.models.article import ArticleEntry
from direct_payment.help.models.image import Image
from direct_payment.help.models.rich_text_embeds import (
    Accordion,
    AccordionItem,
    EmbeddedEntryType,
    EmbeddedImage,
)
from learn.schemas.rich_text_embeds import AccordionSchema, EmbeddedImageSchema
from utils import log
from utils.contentful import (
    log_warning_about_contentful_entry,
    process_rich_text_and_includes,
)

log = log.logger(__name__)

MMB_SPACE_ID = os.getenv("CONTENTFUL_MMB_SPACE_ID")
MMB_ENVIRONMENT_ID = os.getenv("CONTENTFUL_MMB_ENVIRONMENT_ID", "master")
CONTENT_DELIVERY_TOKEN = os.getenv("CONTENTFUL_MMB_CONTENT_DELIVERY_TOKEN")
CONTENT_PREVIEW_TOKEN = os.getenv("CONTENTFUL_MMB_CONTENT_PREVIEW_TOKEN")
CLIENT_TIMEOUT_SECONDS_USER_FACING = 2
CLIENT_TIMEOUT_SECONDS_NON_USER_FACING = 5

HELP_DOCUMENTS = "helpDocuments"
LINKED_RESOURCE_DEPTH = 2


class MMBContentfulClient:
    def __init__(self, preview: bool, user_facing: bool):
        # user-facing clients need a shorter timeout than non-user-facing
        timeout_s = (
            CLIENT_TIMEOUT_SECONDS_USER_FACING
            if user_facing
            else CLIENT_TIMEOUT_SECONDS_NON_USER_FACING
        )
        if preview:
            self._client = contentful.Client(
                MMB_SPACE_ID,
                CONTENT_PREVIEW_TOKEN,
                api_url="preview.contentful.com",
                environment=MMB_ENVIRONMENT_ID,
                reuse_entries=True,  # was getting recursion error (circular reference) without this
                timeout_s=timeout_s,
            )
        else:
            self._client = contentful.Client(
                MMB_SPACE_ID,
                CONTENT_DELIVERY_TOKEN,
                environment=MMB_ENVIRONMENT_ID,
                reuse_entries=True,
                timeout_s=timeout_s,
            )

    def get_article_by_slug(self, slug: str, category: str) -> Optional[Dict[str, Any]]:  # type: ignore[return] # Missing return statement
        entry = self._get_article_entry_by_slug_and_category("article", slug, category)
        if entry:
            return self.entry_to_article_dict(entry)

    def entry_to_article_dict(self, entry: contentful.Entry) -> Dict[str, Any]:
        includes = []
        rich_text = process_rich_text_and_includes(
            rich_text=entry.body,
            includes=includes,
            handle_embedded_entry=self._handle_embedded_entry,
            handle_embedded_asset=self._handle_embedded_asset,
        )

        article_entry = ArticleEntry(
            title=entry.title,
            rich_text=rich_text,
            rich_text_includes=includes,
            id=entry.id,
        )
        return dataclasses.asdict(article_entry)

    def _get_article_entry_by_slug_and_category(
        self, content_type: str, slug: str, category: str
    ) -> Optional[contentful.Entry]:
        entries = self._client.entries(
            {
                "content_type": content_type,
                "fields.slug": slug,
                "fields.category": category,
                "include": 2,
                "limit": 1,
            }
        )
        return entries[0] if entries else None

    def get_help_topics_for_category(self, category: str) -> Optional[Dict[str, Any]]:  # type: ignore[return] # Missing return statement
        entry = self._get_help_topics_by_category(category)
        if entry:
            return self.entry_to_topics_dict(entry)

    def entry_to_topics_dict(self, entry: contentful.Entry) -> Dict[str, Any]:
        topics_details = []
        fields = entry.fields()
        articles = fields["articles"] if "articles" in fields else []
        for article in articles:
            article_id = article.id
            article_fields = article.fields()
            title = article_fields["title"]
            slug = article_fields["slug"]

            topics_details.append({"id": article_id, "title": title, "slug": slug})

        return topics_details  # type: ignore[return-value] # Incompatible return value type (got "List[Dict[str, Any]]", expected "Dict[str, Any]")

    def _get_help_topics_by_category(self, category: str) -> Optional[contentful.Entry]:
        entries = self._client.entries(
            {
                "content_type": HELP_DOCUMENTS,
                "fields.category": category,
                "include": LINKED_RESOURCE_DEPTH,
                "limit": 1,
            }
        )
        return entries[0] if entries else None

    @staticmethod
    def _handle_embedded_asset(asset: contentful.Asset) -> dict:
        return EmbeddedImageSchema().dump(
            EmbeddedImage(id=asset.id, image=Image.from_contentful_asset(asset))
        )

    @staticmethod
    def _handle_embedded_entry(entry):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        content_type = entry.content_type.id
        if content_type == EmbeddedEntryType.ACCORDION.value:
            items = [
                AccordionItem(title=item.header, rich_text=item.body)
                for item in entry.items
            ]
            accordion = Accordion(
                id=entry.id, heading_level=entry.heading_level, items=items
            )
            return AccordionSchema().dump(accordion)
        elif content_type == EmbeddedEntryType.EMBEDDED_IMAGE.value:
            return EmbeddedImageSchema().dump(
                EmbeddedImage(
                    id=entry.id,
                    image=Image.from_contentful_asset(entry.image),
                    caption=entry.caption,
                )
            )
        else:
            # If someone has embedded an unsupported entry, error and fall back
            log_warning_about_contentful_entry("Unsupported entry type embedded", entry)
            raise
