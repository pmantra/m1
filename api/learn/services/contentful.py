import enum
import os
from typing import List, Optional, Union

import contentful
import ddtrace

from utils import log

log = log.logger(__name__)

LEARN_SPACE_ID = os.getenv("CONTENTFUL_LEARN_SPACE_ID")
LEARN_ENVIRONMENT_ID = os.getenv("CONTENTFUL_LEARN_ENVIRONMENT_ID", "master")
CONTENT_DELIVERY_TOKEN = os.getenv("CONTENTFUL_LEARN_CONTENT_DELIVERY_TOKEN")
CONTENT_PREVIEW_TOKEN = os.getenv("CONTENTFUL_LEARN_CONTENT_PREVIEW_TOKEN")
CLIENT_TIMEOUT_SECONDS_USER_FACING = 2
CLIENT_TIMEOUT_SECONDS_NON_USER_FACING = 5
DEFAULT_CONTENTFUL_LOCALE = "en-US"


# not an exhaustive list, just the ones that are relevant
class ContentfulContentType(str, enum.Enum):
    ACCORDION = "accordion"
    ACCORDION_ITEM = "accordionItem"
    ARTICLE = "article"
    ARTICLE_GLOBAL = "articleGlobal"
    BANNER = "banner"
    COURSE = "course"
    NON_CONTENTFUL_ARTICLE = "nonContentfulArticle"
    VIDEO = "video"


class EntityType(str, enum.Enum):
    ASSET = "Asset"
    ENTRY = "Entry"
    DELETED_ENTRY = "DeletedEntry"


class SingletonContentfulClient(type):
    _instances = {}

    def __call__(cls, *args, **kwargs):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        key = str(sorted([(key, val) for key, val in kwargs.items()]))
        if not cls._instances.get(key):
            cls._instances[key] = super().__call__(*args, **kwargs)
        return cls._instances[key]


class LibraryContentfulClient(metaclass=SingletonContentfulClient):
    def __init__(self, preview: bool, user_facing: bool):
        # user-facing clients need a shorter timeout than non-user-facing
        timeout_s = (
            CLIENT_TIMEOUT_SECONDS_USER_FACING
            if user_facing
            else CLIENT_TIMEOUT_SECONDS_NON_USER_FACING
        )
        if preview:
            self._client = contentful.Client(
                LEARN_SPACE_ID,
                CONTENT_PREVIEW_TOKEN,
                api_url="preview.contentful.com",
                environment=LEARN_ENVIRONMENT_ID,
                reuse_entries=True,  # was getting recursion error (circular reference) without this
                timeout_s=timeout_s,
            )
        else:
            self._client = contentful.Client(
                LEARN_SPACE_ID,
                CONTENT_DELIVERY_TOKEN,
                environment=LEARN_ENVIRONMENT_ID,
                reuse_entries=True,
                timeout_s=timeout_s,
            )

    def get_entity_references(
        self, entity: Union[contentful.Entry, contentful.Asset]
    ) -> List[contentful.Entry]:
        # include 5 to get course -> chapter -> article -> accordion -> accordion item
        return entity.incoming_references(
            self._client, query={"include": 5, "locale": DEFAULT_CONTENTFUL_LOCALE}
        )

    def get_entry_by_id(self, entry_id: str) -> contentful.Entry:
        # include 5 to get course -> chapter -> article -> accordion -> accordion item
        return self._client.entry(
            entry_id, query={"include": 5, "locale": DEFAULT_CONTENTFUL_LOCALE}
        )

    def get_asset_by_id(self, asset_id: str) -> contentful.Asset:
        return self._client.asset(asset_id, query={"locale": DEFAULT_CONTENTFUL_LOCALE})

    def get_entry_by_id_or_none(self, id):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        try:
            return self.get_entry_by_id(id)
        except Exception as e:
            log.info("Could not fetch entry by id", id=id, error=e)  # type: ignore[attr-defined] # Module has no attribute "info"

    @ddtrace.tracer.wrap()
    def get_article_global_entries_by_slug_and_locale(
        self, slugs: List[str], locale: str
    ) -> List[contentful.Entry]:
        entries = self._client.entries(
            {
                "content_type": ContentfulContentType.ARTICLE_GLOBAL.value,
                "fields.slug[in]": slugs,
                "locale": locale,
                # include 3 to get article -> accordion -> accordion item
                "include": 3,
            }
        )

        if slugs_not_found := [
            slug
            for slug in slugs
            if slug not in [entry.fields().get("slug") for entry in entries]
        ]:
            # Attempt to fall back to regular locale-less (aka English) article
            # eventually this should be global english, not US english
            entries = entries + self.get_article_entries_by_slug(slugs_not_found)

        return entries

    def get_article_entry_by_slug(self, slug: str) -> Optional[contentful.Entry]:
        article_entries = self.get_article_entries_by_slug([slug])
        return article_entries[0] if article_entries else None

    def get_article_entries_by_slug(
        self, slugs: List[str], locale: Optional[str] = None
    ) -> List[contentful.Entry]:
        # include 3 to get article -> accordion -> accordion item
        return self.get_entries_by_type_and_slug(
            content_type=ContentfulContentType.ARTICLE,
            slugs=slugs,
            include=3,
            locale=locale,
        )

    @ddtrace.tracer.wrap()
    def get_articles_with_only_titles_by_slug(
        self, slugs: List[str], locale: str
    ) -> List[contentful.Entry]:
        return self._client.entries(
            {
                "content_type": ContentfulContentType.ARTICLE.value,
                "fields.slug[in]": slugs,
                "select": "fields.title,fields.slug",
                "locale": locale,
                "include": 0,
            }
        )

    def get_banners_by_slug(self, slugs: List[str]) -> List[contentful.Entry]:
        # include 1 because banners have no references
        return self.get_entries_by_type_and_slug(
            content_type=ContentfulContentType.BANNER, slugs=slugs, include=1
        )

    def get_courses_by_slug(self, slugs: List[str]) -> List[contentful.Entry]:
        # include 5 to get course -> chapter -> article -> accordion -> accordion item
        return self.get_entries_by_type_and_slug(
            content_type=ContentfulContentType.COURSE, slugs=slugs, include=5
        )

    @ddtrace.tracer.wrap()
    def get_entries_by_type_and_slug(
        self,
        content_type: ContentfulContentType,
        slugs: List[str],
        include: int,
        locale: Optional[str] = None,
    ) -> List[contentful.Entry]:
        return self._client.entries(
            {
                "content_type": content_type.value,
                "fields.slug[in]": slugs,
                "locale": locale or DEFAULT_CONTENTFUL_LOCALE,
                # To get embedded entries' children. This may result in circular references from
                # related reads but the client is fine with that
                "include": include,
            }
        )

    @ddtrace.tracer.wrap()
    def get_courses_by_tags(
        self, tags: List[str], limit: Optional[int] = None
    ) -> List[contentful.Entry]:
        return self._client.entries(
            {
                "content_type": ContentfulContentType.COURSE,
                "metadata.tags.sys.id[all]": tags,
                "locale": DEFAULT_CONTENTFUL_LOCALE,
                # include 1 because we only need the course slug and tags
                "include": 1,
                "limit": limit,
            }
        )

    @ddtrace.tracer.wrap()
    def get_video_entries_by_slugs(self, slugs: List[str]) -> List[contentful.Entry]:
        return self.get_entries_by_type_and_slug(
            content_type=ContentfulContentType.VIDEO, slugs=slugs, include=3
        )

    @staticmethod
    def log_warning_about_contentful_entry(message, entry, exc_info=False, error=None):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        log.warn(  # type: ignore[attr-defined] # Module has no attribute "warn"
            message,
            contentful_id=entry.id,
            content_type=entry.content_type.id,
            slug=entry.fields().get("slug"),
            exc_info=exc_info,
            error=error,
        )
