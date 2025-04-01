import math
from typing import Any, Dict, List

import contentful
from contentful import Entry

from learn.models import rich_text_embeds
from learn.services import article_service, contentful_caching_service
from learn.utils import rich_text_utils
from utils import log

log = log.logger(__name__)


class ReadTimeService(contentful_caching_service.ContentfulCachingService[int]):
    # according to internet (where everyone tells the truth all the time)
    # https://scholarwithin.com/average-reading-speed#:~:text=read%2020%20pages.-,Adult%20Average%20Reading%20Speed,of%20300%20words%20per%20minute.
    __AVERAGE_WORDS_PER_MINUTE = 238

    def get_values(self, slugs: List[str], **kwargs) -> Dict[str, int]:  # type: ignore[no-untyped-def,override] # Signature of "get_values" incompatible with supertype "ContentfulCachingService"
        # filter out the read times that are less than 1, which represent video articles (see line 42)
        return {
            slug: estimated_read_time_minutes
            for slug, estimated_read_time_minutes in self.get_values_without_filtering(
                slugs
            ).items()
            if estimated_read_time_minutes > 0
        }

    def get_values_without_filtering(self, slugs: List[str]) -> Dict[str, int]:
        return super().get_values(slugs)

    def calculate_read_time(self, article: contentful.Entry) -> int:
        plain_text_array = []
        rich_text_utils.rich_text_to_plain_string_array(
            article.rich_text, plain_text_array
        )
        word_count = len(
            [word for plain_text in plain_text_array for word in plain_text.split()]
        )
        # most confusing syntax ever ☝️
        estimated_read_time_minutes_raw = (
            word_count / ReadTimeService.__AVERAGE_WORDS_PER_MINUTE
        )
        if estimated_read_time_minutes_raw < 1:
            if self.__contains_embedded_video(article):
                estimated_read_time_minutes = (
                    -1
                )  # magic value that means "there is no read time but we already
                # calculated it so don't do it again" (yes I hate this and I'm sorry)
            else:
                estimated_read_time_minutes = 1
        else:
            estimated_read_time_minutes = math.ceil(estimated_read_time_minutes_raw)
        return estimated_read_time_minutes

    def _get_values_from_contentful(  # type: ignore[override] # Signature of "_get_values_from_contentful" incompatible with supertype "ContentfulCachingService"
        self,
        slugs: List[str],
    ) -> Dict[str, int]:
        article_entries = self.contentful_client.get_article_entries_by_slug(slugs)
        return {
            article_entry.slug: self.calculate_read_time(article_entry)
            for article_entry in article_entries
        }

    def _get_cache_key(self, identifier_value: str, **kwargs: Any) -> str:
        return f"estimated_read_time_minutes:{identifier_value}"

    @staticmethod
    def _serialize_value(value: int) -> str:
        return str(value)

    @staticmethod
    def _deserialize_value(value_str: str) -> int:
        return int(value_str)

    @staticmethod
    def __contains_embedded_video(article: Entry) -> bool:
        includes: List[Dict[str, Any]] = []
        article_service.ArticleService.process_rich_text_and_includes(
            article.rich_text, includes
        )
        return (
            next(
                (
                    include
                    for include in includes
                    if include["entry_type"]
                    == rich_text_embeds.EmbeddedEntryType.EMBEDDED_VIDEO
                ),
                None,
            )
            is not None
        )
