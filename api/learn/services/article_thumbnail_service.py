from dataclasses import dataclass
from typing import List, Optional, Union

from learn.models import image as contentful_image
from learn.models import migration
from learn.models.media_type import MediaType
from learn.services import contentful
from learn.services.caching_service import CachingService
from models import images as admin_image
from utils import log

log = log.logger(__name__)


@dataclass
class ResourceWithThumbnail:
    id: str
    slug: str
    title: str
    article_type: str
    image: Union[contentful_image.Image, admin_image.Image]
    content_type: str
    # These next two are just used for dashboard resources
    content_url: str
    subhead: Optional[str]
    estimated_read_time_minutes: Optional[int] = None
    media_type: Optional[MediaType] = None


class ArticleThumbnailService(CachingService):

    # These are not necessarily live contentful resources--but most of them
    # should be because most of them are by now (in production)...
    def get_thumbnails_for_resources(self, resources) -> List[ResourceWithThumbnail]:  # type: ignore[no-untyped-def] # Function is missing a type annotation for one or more arguments
        thumbnails = []
        if self.redis_client:
            thumbnails = self._get_thumbnail_pipeline(
                [resource.slug for resource in resources]
            )

        resources_with_thumbnails = []

        for i, resource in enumerate(resources):
            img = None
            # `thumbnails` is an array of 2-item arrays that may contain Nones
            if thumbnails and thumbnails[i] and thumbnails[i][0]:
                img = contentful_image.Image(
                    url=thumbnails[i][0], description=thumbnails[i][1]  # type: ignore[arg-type] # Argument "url" to "Image" has incompatible type "Optional[str]"; expected "str"
                )
            elif resource.contentful_status == migration.ContentfulMigrationStatus.LIVE:
                img = self._get_thumbnail_from_contentful(slug=resource.slug)
            else:
                img = resource.image
            resources_with_thumbnails.append(
                ResourceWithThumbnail(
                    id=resource.id,
                    slug=resource.slug,
                    title=resource.title,
                    article_type=resource.article_type,
                    image=img,  # type: ignore[arg-type] # Argument "image" to "ResourceWithThumbnail" has incompatible type "Optional[learn.models.image.Image]"; expected "Union[learn.models.image.Image, models.images.Image]"
                    content_type=resource.content_type,
                    estimated_read_time_minutes=resource.estimated_read_time_minutes,
                    media_type=resource.media_type,
                    content_url=resource.content_url,
                    subhead=resource.subhead,
                )
            )
        return resources_with_thumbnails

    def _get_thumbnail_from_contentful(
        self, slug: str
    ) -> Optional[contentful_image.Image]:
        img = self._fetch_remote_image(slug)
        if self.redis_client and img:
            self.save_image_to_cache(resource_slug=slug, img=img)
        return img

    def get_thumbnail_by_slug(self, slug: str) -> Optional[contentful_image.Image]:

        if self.redis_client:
            thumbnails = self._get_thumbnail_pipeline([slug])
            if thumbnails and thumbnails[0][0] and thumbnails[0][1]:
                single_thumbnail = thumbnails[0]
                return contentful_image.Image(
                    url=single_thumbnail[0], description=single_thumbnail[1]  # type: ignore[arg-type] # Argument "url" to "Image" has incompatible type "Optional[str]"; expected "str"
                )
            else:
                return self._get_thumbnail_from_contentful(slug)
        else:
            return None

    def remove_asset_from_cache_by_id(self, asset_id: str):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        client = contentful.LibraryContentfulClient(preview=True, user_facing=False)
        incoming_refs = client.get_entity_references(client.get_asset_by_id(asset_id))
        for ref in incoming_refs:
            self.redis_client.delete(f"thumbnails:{ref.slug}")  # type: ignore[union-attr] # Item "None" of "Optional[Any]" has no attribute "delete"

    def remove_article_from_cache_by_id(self, entry_id: str):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        client = contentful.LibraryContentfulClient(preview=True, user_facing=False)
        entry = client.get_entry_by_id(entry_id)
        self.redis_client.delete(f"thumbnails:{entry.slug}")  # type: ignore[union-attr] # Item "None" of "Optional[Any]" has no attribute "delete"

    def save_image_to_cache(self, resource_slug: str, img: contentful_image.Image):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        try:
            log.debug("Inserting thumbnail url into cache", resource_slug=resource_slug)  # type: ignore[attr-defined] # Module has no attribute "debug"
            self.redis_client.hset(  # type: ignore[union-attr] # Item "None" of "Optional[Any]" has no attribute "hset"
                f"thumbnails:{resource_slug}",
                "url",
                img.url,
                {"description": img.description or ""},
            )
        except Exception as e:
            log.error(  # type: ignore[attr-defined] # Module has no attribute "error"
                "Error writing image to cache",
                error=e,
                resource_slug=resource_slug,
            )

    def _get_thumbnail_pipeline(self, slugs) -> List[List[Optional[str]]]:  # type: ignore[no-untyped-def] # Function is missing a type annotation for one or more arguments
        try:
            pipeline = self.redis_client.pipeline()  # type: ignore[union-attr] # Item "None" of "Optional[Any]" has no attribute "pipeline"

            for slug in slugs:
                pipeline.hmget(
                    name=f"thumbnails:{slug}",
                    keys=["url", "description"],
                )

            return pipeline.execute()
        except Exception as e:
            log.error("Error retrieving thumbnails from cache", error=e)  # type: ignore[attr-defined] # Module has no attribute "error"
            return []

    def _fetch_url_and_description_from_cache(self, resource_slug):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        return self.redis_client.hmget(  # type: ignore[union-attr] # Item "None" of "Optional[Any]" has no attribute "hmget"
            name=f"thumbnails:{resource_slug}",
            keys=["url", "description"],
        )

    def _fetch_remote_image(self, resource_slug: str):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        # TODO: Support preview--the only page we can preview thumbnails from
        # is dashboard, and dash isn't sending preview info to mono yet, but
        # we'll probably want to
        try:
            contentful_client = contentful.LibraryContentfulClient(
                preview=False, user_facing=True
            )
            entry = contentful_client.get_article_entry_by_slug(resource_slug)
            return contentful_image.Image.from_contentful_asset(entry.hero_image)  # type: ignore[union-attr] # Item "None" of "Optional[Any]" has no attribute "hero_image"
        except Exception as e:
            log.error(  # type: ignore[attr-defined] # Module has no attribute "error"
                "Error fetching image from Contentful",
                error=e,
                resource_slug=resource_slug,
            )
