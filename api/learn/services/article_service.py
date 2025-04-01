import copy
import dataclasses
import json
from typing import Any, Dict, List, Optional, Union

import contentful

from common import stats
from l10n.utils import is_default_langauge, request_locale_str
from learn.models.article import ArticleEntry, MedicallyReviewed, RelatedRead
from learn.models.article_type import ArticleType
from learn.models.image import Image
from learn.models.rich_text_embeds import (
    Accordion,
    AccordionItem,
    Callout,
    EmbeddedEntryType,
    EmbeddedImage,
    EmbeddedVideo,
)
from learn.schemas.rich_text_embeds import (
    AccordionSchema,
    CalloutSchema,
    EmbeddedImageSchema,
    EmbeddedVideoSchema,
)
from learn.services import contentful_caching_service
from learn.services.contentful import (
    DEFAULT_CONTENTFUL_LOCALE,
    ContentfulContentType,
    LibraryContentfulClient,
)
from learn.utils.contentful_utils import get_url
from models.marketing import Resource
from utils import log

logger = log.logger(__name__)


class ArticleService(
    contentful_caching_service.ContentfulCachingService[Dict[str, Any]]
):
    def __init__(
        self,
        preview: bool = False,
        user_facing: bool = True,
        should_localize: bool = False,
    ):
        super().__init__(preview=preview, user_facing=user_facing)
        self.request_locale = request_locale_str() if should_localize else None

    def _get_cache_key(self, identifier_value: str, **kwargs: Any) -> str:
        article_slug = identifier_value
        if query_string_locale := kwargs.get("locale", None):
            # this is for article globals, i.e. entry-level localization
            return f"article:{article_slug}-{query_string_locale}"
        elif self.request_locale and self.request_locale != DEFAULT_CONTENTFUL_LOCALE:
            # this is for localizing via header values, i.e. field-level localization
            return f"article:{self.request_locale}:{article_slug}"
        else:
            return f"article:{article_slug}"

    @staticmethod
    def _serialize_value(value: Dict[str, Any]) -> str:
        return json.dumps(value)

    @staticmethod
    def _deserialize_value(value_str: str) -> Dict[str, Any]:
        article_dict = json.loads(value_str)
        # Attempt to load as ArticleEntry before converting back to dict;
        # if this fails, the article model must have changed. The error will
        # be caught and cache entry removed
        return dataclasses.asdict(ArticleEntry(**article_dict))

    def _get_values_from_contentful(
        self, identifier_values: List[str], **kwargs: Any
    ) -> Dict[str, Dict[str, Any]]:
        if locale := kwargs.get("locale", None):
            # For now, most of our articles are not associated with the parent
            # content type Article - Global, so when a locale isn't included in
            # the request, we'll continue to query for the content type Article
            entries = (
                self.contentful_client.get_article_global_entries_by_slug_and_locale(
                    identifier_values, locale
                )
            )
        else:
            entries = self.contentful_client.get_article_entries_by_slug(
                identifier_values, locale=self.request_locale
            )

        return {entry.slug: self.entry_to_article_dict(entry) for entry in entries}

    def remove_value_from_cache(self, entry_id: str) -> None:
        contentful_client = LibraryContentfulClient(preview=True, user_facing=False)
        entry = contentful_client.get_entry_by_id(entry_id)
        if self.redis_client:
            self.redis_client.delete(self._get_cache_key(entry.slug))
        self.remove_localized_articles_from_cache(entry.slug)

    def remove_localized_articles_from_cache(self, slug: str) -> None:
        self.remove_keys_from_cache_by_pattern(f"article:*:{slug}")

    def entry_to_article_dict(self, entry: contentful.Entry) -> Dict[str, Any]:
        if entry.content_type.id == ContentfulContentType.ARTICLE_GLOBAL:
            entry = entry.article
        includes = []
        rich_text = self.process_rich_text_and_includes(
            rich_text=entry.rich_text, includes=includes
        )

        article_entry = ArticleEntry(
            title=entry.title,
            medically_reviewed=(
                MedicallyReviewed.from_contentful_entry(
                    entry.fields().get("reviewed_by", None)
                )
                if entry.medically_reviewed
                else None
            ),
            hero_image=Image.from_contentful_asset(entry.fields().get("hero_image")),
            rich_text=rich_text,
            related_reads=self.get_related_reads(
                entry.fields().get("related_reads", [])
            ),
            rich_text_includes=includes,
        )
        return dataclasses.asdict(article_entry)

    def get_related_reads(
        self, related_reads: list[contentful.Entry]
    ) -> list[RelatedRead]:
        if not is_default_langauge():
            return []
        return [
            related_read
            for related_read in [
                self.parse_as_related_read(read) for read in related_reads
            ]
            if related_read
        ]

    @staticmethod
    def process_rich_text_and_includes(
        rich_text: dict[str, Any], includes: list[dict[str, Any]]
    ) -> dict[str, Any]:
        rich_text = copy.deepcopy(rich_text)
        # Assumes embedded entries will be at the top level of rich text, i.e.
        # not nested in other nodes. We should not be allowing inline embeds,
        # so this should hold true
        for node in rich_text["content"]:
            if node["nodeType"] == "embedded-entry-block":
                entry = node["data"]["target"]
                if not isinstance(entry, contentful.Entry):
                    logger.error(
                        "Encountered an embedded entry block which is not an Entry type. Raising an exception "
                        "to force a retry.",
                        extra={"node": node, "data_target_type": type(entry)},
                    )
                    raise ValueError(
                        "Encountered an embedded entry block which is not an Entry type. Raising an exception "
                        "to force a retry."
                    )
                includes.append(ArticleService._handle_embedded_entry(entry=entry))
                # Replace entry with a fake link, the only important part of which is the id
                node["data"][
                    "target"
                ] = ArticleService._create_link_from_entry_or_asset(entry)
            elif node["nodeType"] == "embedded-asset-block":
                asset = node["data"]["target"]
                if not isinstance(asset, contentful.Asset):
                    logger.error(
                        "Encountered an embedded asset block which is not an Asset type. Raising an exception "
                        "to force a retry.",
                        extra={"node": node, "data_target_type": type(asset)},
                    )
                    raise ValueError(
                        "Encountered an embedded asset block which is not an Asset type. Raising an exception "
                        "to force a retry."
                    )
                includes.append(ArticleService._handle_embedded_asset(asset=asset))
                # Replace asset with a fake entry link, the only important part of which is the id
                node["nodeType"] = "embedded-entry-block"
                node["data"][
                    "target"
                ] = ArticleService._create_link_from_entry_or_asset(asset)
        return rich_text

    @staticmethod
    def _handle_embedded_asset(asset: contentful.Asset) -> dict[str, Any]:
        return EmbeddedImageSchema().dump(
            EmbeddedImage(id=asset.id, image=Image.from_contentful_asset(asset))
        )

    @staticmethod
    def _handle_embedded_entry(entry: contentful.Entry) -> dict[str, Any]:
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
        elif content_type == EmbeddedEntryType.CALLOUT.value:
            return CalloutSchema().dump(Callout(id=entry.id, rich_text=entry.rich_text))
        elif content_type == EmbeddedEntryType.EMBEDDED_IMAGE.value:
            return EmbeddedImageSchema().dump(
                EmbeddedImage(
                    id=entry.id,
                    image=Image.from_contentful_asset(entry.image),
                    caption=entry.caption,
                )
            )
        elif content_type == EmbeddedEntryType.EMBEDDED_VIDEO.value:
            return EmbeddedVideoSchema().dump(
                EmbeddedVideo(
                    id=entry.id,
                    video_link=entry.video_link,
                    thumbnail=Image.from_contentful_asset(
                        entry.fields().get("thumbnail")
                    ),
                    captions_link=get_url(entry.captions),
                )
            )
        else:
            # If someone has embedded an unsupported entry, error and fall back
            LibraryContentfulClient.log_warning_about_contentful_entry(
                "Unsupported entry type embedded", entry
            )
            raise ValueError("Unsupported entry type embedded")

    @staticmethod
    def _create_link_from_entry_or_asset(
        entry_or_asset: Union[contentful.Entry, contentful.Asset]
    ) -> dict[str, dict[str, str]]:
        return {
            "sys": {
                "id": entry_or_asset.id,
                "type": "Link",
                "linkType": "Entry",
            }
        }

    def parse_as_related_read(self, entry: contentful.Entry) -> Optional[RelatedRead]:
        try:
            resource = Resource.get_public_published_resource_by_slug(entry.slug)
            if resource:
                if resource.article_type == ArticleType.RICH_TEXT:
                    if entry.content_type.id == "article":
                        related_read = RelatedRead.from_contentful(entry)
                    else:
                        # There is a mismatch and Contentful still thinks this
                        # is an admin article
                        contentful_article = (
                            self.contentful_client.get_article_entry_by_slug(entry.slug)
                        )
                        LibraryContentfulClient.log_warning_about_contentful_entry(
                            "Related read is configured as non-contentful article"
                            " but is found as LIVE. Using contentful info instead",
                            entry,
                        )
                        related_read = RelatedRead.from_contentful(contentful_article)
                else:
                    # The only other option right now is HTML. In that case use
                    # DB info no matter which type of related read it is in Contentful
                    if entry.content_type.id == "article":
                        LibraryContentfulClient.log_warning_about_contentful_entry(
                            "Related read is configured as contentful article but"
                            " is not LIVE in database. Using db info instead.",
                            entry,
                        )
                    related_read = RelatedRead.from_resource(resource)

                # Monitor in Datadog for the 2 mismatch cases based on tags
                self.increment_related_reads_metric(
                    success=True,
                    article_type=resource.article_type,
                    contentful_content_type=entry.content_type.id,
                )
                return related_read

            else:
                # no resource
                LibraryContentfulClient.log_warning_about_contentful_entry(
                    "Related read could not be found in database", entry
                )
                self.increment_related_reads_metric(
                    success=False,
                    contentful_content_type=entry.content_type.id,
                    outcome="hidden",
                    detail="not_found",
                )
        except Exception as e:
            LibraryContentfulClient.log_warning_about_contentful_entry(
                "Could not parse entry as related read", entry, exc_info=True, error=e
            )
            self.increment_related_reads_metric(
                success=False,
                contentful_content_type=entry.content_type.id,
                outcome="hidden",
                detail="error",
            )
        return None

    @staticmethod
    def increment_related_reads_metric(**kwargs: Any) -> None:
        stats.increment(
            "learn.services.contentful.related_read",
            pod_name=stats.PodNames.COCOPOD,
            tags=[f"{key}:{format(value).lower()}" for key, value in kwargs.items()],
        )
