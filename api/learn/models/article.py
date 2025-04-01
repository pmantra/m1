import dataclasses
from typing import Dict, List, Optional

import contentful
from typing_extensions import Self

from l10n.utils import is_default_langauge
from learn.models import article_type, image, media_type, related_content
from models import marketing


@dataclasses.dataclass
class MedicallyReviewed:
    __slots__ = ("reviewers",)
    reviewers: Optional[str]

    @classmethod
    def from_contentful_entry(cls, reviewers: Optional[List[contentful.Entry]]) -> Self:
        # we only end up here if medically_reviewed = true
        # hide medical reviewers if not english
        if reviewers is None or not is_default_langauge():
            # this is the default medically reviewed component
            return cls(reviewers=None)
        if reviewers is not None:
            return cls(
                reviewers=join_with_comma_and_and([r.name_vertical for r in reviewers])
            )


@dataclasses.dataclass
class RelatedRead(related_content.RelatedContent):
    related_content_type: media_type.MediaType = dataclasses.field(
        init=False, default=media_type.MediaType.ARTICLE
    )
    type: article_type.ArticleType

    @classmethod
    def from_resource(cls, resource: marketing.Resource):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        # todo check on sizing of thumbnail
        return cls(
            title=resource.title,
            slug=resource.slug,
            # eventually should probably look at migration status in DB
            type=article_type.ArticleType.HTML,
            # was copied from thumbnail url size but should probably confirm that this is what web is using
            thumbnail=image.Image(url=resource.image.asset_url(90, 120, smart=False))
            if resource.image
            else None,
        )

    @classmethod
    def from_contentful(cls, entry: contentful.Entry):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        return cls(
            title=entry.title,
            slug=entry.slug,
            type=article_type.ArticleType.RICH_TEXT,
            thumbnail=image.Image.from_contentful_asset(
                entry.fields().get("hero_image")
            ),
        )


@dataclasses.dataclass
class RelatedReadWithReadTime(RelatedRead):
    estimated_read_time: Optional[int]


@dataclasses.dataclass
class ArticleEntry:
    __slots__ = (
        "title",
        "medically_reviewed",
        "hero_image",
        "rich_text",
        "related_reads",
        "rich_text_includes",
    )
    title: str
    medically_reviewed: Optional[MedicallyReviewed]
    hero_image: image.Image
    rich_text: Dict
    related_reads: List[RelatedRead]
    rich_text_includes: List[Dict]


def join_with_comma_and_and(items: List[str]) -> str:  # type: ignore[return] # Missing return statement
    """
    Joins a list of strings with commas and a final "and" with logic for cases where an item has a comma in it too
    ex. ["apples", "oranges", "bananas"] -> "apples, oranges, and bananas"
    ex. ["apples, my favorite", "oranges"] -> "apples, my favorite, and bananas"
    """
    if items:
        if len(items) == 1:
            return items[0]
        if len(items) == 2 and "," not in items[0]:
            # if there's not a comma in the first item, then no comma before "and"
            return items[0] + " and Maven " + items[1]
        else:
            # when more than 2 items or there's a comma in first item, yes comma before "and"
            modified_items = [items[0]] + [f"Maven {item}" for item in items[1:]]
            return f"{', '.join(modified_items[:-1])}, and {modified_items[-1]}"
