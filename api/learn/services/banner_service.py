import json
from typing import Any, Dict, List, Union

from learn.services import contentful_caching_service
from utils import log
from views.schemas import banner

log = log.logger(__name__)


class BannerService(
    contentful_caching_service.ContentfulCachingService[
        Dict[str, Union[str, Dict[str, str]]]
    ]
):
    def _get_values_from_contentful(  # type: ignore[override] # Signature of "_get_values_from_contentful" incompatible with supertype "ContentfulCachingService"
        self,
        slugs: List[str],
    ) -> Dict[str, Dict[str, Union[str, Dict[str, str]]]]:
        banner_entries = self.contentful_client.get_banners_by_slug(slugs)
        banner_schema = banner.Banner()
        return {
            banner_entry.slug: banner_schema.load(banner_entry.fields())
            for banner_entry in banner_entries
        }

    def _get_cache_key(self, identifier_value: str, **kwargs: Any) -> str:
        return f"banner:{identifier_value}"

    @staticmethod
    def _serialize_value(value: Dict[str, Union[str, Dict[str, str]]]) -> str:
        return json.dumps(value)

    @staticmethod
    def _deserialize_value(value_str: str) -> Dict[str, Union[str, Dict[str, str]]]:
        return banner.Banner().load(json.loads(value_str))
