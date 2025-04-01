from typing import Any, Dict, List

import ddtrace

from l10n.utils import request_locale_str
from learn.models import migration
from learn.services import contentful_caching_service
from learn.services.contentful import LibraryContentfulClient
from models.marketing import Resource
from utils import log

log = log.logger(__name__)


class LocalizedArticleTitleService(
    contentful_caching_service.ContentfulCachingService[str]
):
    __CACHE_KEY_PREFIX = "article_title"

    def __init__(
        self,
        preview: bool = False,
        user_facing: bool = True,
    ):
        super().__init__(preview=preview, user_facing=user_facing)
        self.request_locale = request_locale_str()

    @ddtrace.tracer.wrap()
    def populate_remote_resource_titles(
        self, resources: List[Resource]
    ) -> List[Resource]:
        remote_resource_slugs = [
            resource.slug
            for resource in resources
            if resource.contentful_status == migration.ContentfulMigrationStatus.LIVE
        ]
        remote_resource_titles = self.get_values(
            identifier_values=remote_resource_slugs
        )
        for resource in resources:
            if resource.slug in remote_resource_titles:
                resource.title = remote_resource_titles[resource.slug]
        return resources

    def _get_cache_key(self, identifier_value: str, **kwargs: Any) -> str:
        return f"{self.__CACHE_KEY_PREFIX}:{self.request_locale}:{identifier_value}"

    def _get_cache_key_pattern(self, identifier_value: str) -> str:
        return f"{self.__CACHE_KEY_PREFIX}:*:{identifier_value}"

    @staticmethod
    def _serialize_value(value: str) -> str:
        return value

    @staticmethod
    def _deserialize_value(value_str: str) -> str:
        return value_str

    @ddtrace.tracer.wrap()
    def _get_values_from_contentful(
        self, identifier_values: List[str], **kwargs: Any
    ) -> Dict[str, str]:
        entries = self.contentful_client.get_articles_with_only_titles_by_slug(
            identifier_values, locale=self.request_locale
        )

        return {entry.slug: entry.title for entry in entries}

    def remove_value_from_cache(self, entry_id: str) -> None:
        contentful_client = LibraryContentfulClient(preview=True, user_facing=False)
        entry = contentful_client.get_entry_by_id(entry_id)
        self.remove_keys_from_cache_by_pattern(self._get_cache_key_pattern(entry.slug))
