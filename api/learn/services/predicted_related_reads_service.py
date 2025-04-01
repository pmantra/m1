import json
import pathlib
from typing import Optional

from learn.models import article_type
from learn.models.article import RelatedRead
from learn.services.article_thumbnail_service import ArticleThumbnailService
from learn.services.article_title_service import LocalizedArticleTitleService

RELATED_READS_JSON = (
    pathlib.Path(__file__).resolve().parent / "predicted_related_reads.json"
)


class PredictedRelatedReadsService:
    def __init__(self, preview: bool = False, user_facing: bool = True):

        self.article_title_service = LocalizedArticleTitleService(
            preview=preview, user_facing=user_facing
        )
        self.article_thumbnail_service = ArticleThumbnailService()
        with open(RELATED_READS_JSON, "r") as json_file:
            self.related_read_dict = json.load(json_file)

    def get_related_reads(
        self, source_article_slug: str
    ) -> Optional[list[RelatedRead]]:
        """
        Returns a list of RelatedRead objects based on predictions from the source article slug.

        Args:
            source_article_slug: The slug of the source article.

        Returns:
            A list of RelatedRead objects.
        """
        related_read_slugs = self.related_read_dict.get(source_article_slug)
        if not related_read_slugs:
            return []
        related_read_objects = []
        for related_read_slug in related_read_slugs:
            if related_read_obj := self._get_related_read_object(related_read_slug):
                related_read_objects.append(related_read_obj)
        return related_read_objects

    def _get_related_read_object(self, related_read_slug: str) -> Optional[RelatedRead]:
        article_title = self.article_title_service.get_value(related_read_slug)
        article_thumbnail = self.article_thumbnail_service.get_thumbnail_by_slug(
            related_read_slug
        )
        if article_title:
            read_object = RelatedRead(
                title=article_title,
                slug=related_read_slug,
                thumbnail=article_thumbnail,
                type=article_type.ArticleType.RICH_TEXT,
            )
            return read_object
        else:
            return None
