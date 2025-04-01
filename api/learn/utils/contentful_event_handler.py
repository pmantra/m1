from typing import List, Optional, Union

import contentful

from learn.models import course_factory, image
from learn.models.video import Video
from learn.services import (
    article_service,
    article_thumbnail_service,
    article_title_service,
    banner_service,
)
from learn.services import contentful as contentful_svc
from learn.services import (
    course_service,
    courses_tag_service,
    read_time_service,
    video_service,
)
from learn.services.contentful import ContentfulContentType
from utils import index_resources
from views.schemas import banner


class ContentfulEventHandler:
    def __init__(self) -> None:
        self.__preview_client = contentful_svc.LibraryContentfulClient(
            preview=True, user_facing=False
        )
        self.__delivery_client = contentful_svc.LibraryContentfulClient(
            preview=False, user_facing=False
        )
        self.__article_thumbnail_service = (
            article_thumbnail_service.ArticleThumbnailService()
        )
        self.__article_service = article_service.ArticleService(user_facing=False)
        self.__article_title_service = (
            article_title_service.LocalizedArticleTitleService(user_facing=False)
        )
        self.__banner_service = banner_service.BannerService(user_facing=False)
        self.__course_service = course_service.CourseService(user_facing=False)
        self.__courses_tag_service = courses_tag_service.CoursesTagService(
            user_facing=False
        )
        self.__read_time_service = read_time_service.ReadTimeService(user_facing=False)
        self.__video_service = video_service.VideoService(user_facing=False)

    def handle_event(
        self,
        action: str,
        entity_type: str,
        content_type: str,
        entity_id: str,
    ) -> None:
        if entity_type == contentful_svc.EntityType.ASSET.value:
            self.__handle_asset_event(action, entity_id)
        # Entry type for an unpublished entry is DeletedEntry
        elif (
            entity_type == contentful_svc.EntityType.ENTRY.value
            or entity_type == contentful_svc.EntityType.DELETED_ENTRY.value
        ):
            self.__handle_entry_event(action, content_type, entity_id)

    def __handle_asset_event(self, action: str, entity_id: str) -> None:
        if action == "unpublish":
            asset = self.__preview_client.get_asset_by_id(entity_id)
            self.__article_thumbnail_service.remove_asset_from_cache_by_id(entity_id)
            self.__handle_linked_entries_for_unpublished_entity(
                asset, contentful_svc.EntityType.ASSET
            )
        elif action == "publish":
            asset = self.__delivery_client.get_asset_by_id(entity_id)
            incoming_refs = self.__delivery_client.get_entity_references(asset)
            for ref in incoming_refs:
                if (
                    ref.content_type.id == ContentfulContentType.ARTICLE.value
                    and ref.hero_image.id == entity_id
                ):
                    self.__article_thumbnail_service.save_image_to_cache(
                        ref.slug, image.Image.from_contentful_asset(asset)
                    )
                self.__handle_single_modified_entry(
                    ref, contentful_svc.EntityType.ASSET, is_reference=True
                )
                self.__handle_linked_entries_for_modified_entry(
                    ref, contentful_svc.EntityType.ASSET
                )

    def __handle_entry_event(
        self,
        action: str,
        content_type: str,
        entity_id: str,
    ) -> None:
        if action == "unpublish":
            # Need the preview client so we can get the unpublished entry
            entry = self.__preview_client.get_entry_by_id(entity_id)
            if content_type == ContentfulContentType.ARTICLE.value:
                self.__article_thumbnail_service.remove_article_from_cache_by_id(
                    entity_id
                )
                self.__read_time_service.remove_value_from_cache(entity_id)
                index_resources.remove_contentful_article_from_index(entry)
                self.__article_service.remove_value_from_cache(entry.id)
                self.__article_title_service.remove_value_from_cache(entry.id)
            elif content_type == ContentfulContentType.BANNER.value:
                self.__banner_service.remove_value_from_cache(entity_id)
            elif content_type == ContentfulContentType.COURSE.value:
                self.__course_service.remove_value_from_cache(entry.id)
                # Ideally we'd look at the tags and remove just those entries
                # but the cache entry removal code doesn't support that rn
                self.__courses_tag_service.clear_cache()
                index_resources.remove_course_from_index(entry)
            elif content_type == ContentfulContentType.VIDEO.value:
                self.__video_service.remove_value_from_cache(entry.id)

            self.__handle_linked_entries_for_unpublished_entity(
                entry, contentful_svc.EntityType.ENTRY
            )
        elif action == "publish":
            entry = self.__delivery_client.get_entry_by_id(entity_id)
            self.__handle_single_modified_entry(
                entry, contentful_svc.EntityType.ENTRY, is_reference=False
            )
            self.__handle_linked_entries_for_modified_entry(
                entry, contentful_svc.EntityType.ENTRY
            )

    def __handle_linked_entries_for_unpublished_entity(
        self,
        entity: Union[contentful.Entry, contentful.Asset],
        entity_type: contentful_svc.EntityType,
    ) -> None:
        seen = [entity.id]
        incoming_refs = [
            ref
            for ref in self.__preview_client.get_entity_references(entity)
            if ref.id not in seen
        ]
        for ref in incoming_refs:
            # Check if the referencing article is even published before
            # attempting to index it--it's a risk since we got the embedded
            # entry with the preview client
            # Also need to get the content of the article WITHOUT the
            # unpublished embedded entry in it
            ref = self.__delivery_client.get_entry_by_id_or_none(ref.id)
            if ref:
                self.__handle_single_modified_entry(ref, entity_type, is_reference=True)
                if ContentfulEventHandler.__should_process_references(
                    entity, entity_type, ref
                ):
                    seen = self.__handle_linked_entries_for_modified_entry(
                        ref, entity_type, seen
                    )

    def __handle_linked_entries_for_modified_entry(
        self,
        entry: contentful.Entry,
        root_entity_type: contentful_svc.EntityType,
        seen: Optional[List[str]] = None,
    ) -> List[str]:
        if seen is None:
            seen = []
        seen.append(entry.id)
        incoming_refs = [
            ref
            for ref in self.__delivery_client.get_entity_references(entry)
            if ref.id not in seen
        ]
        for ref in incoming_refs:
            self.__handle_single_modified_entry(
                ref, root_entity_type, is_reference=True
            )
            if ContentfulEventHandler.__should_process_references(
                entry, contentful_svc.EntityType.ENTRY, ref
            ):
                seen = self.__handle_linked_entries_for_modified_entry(
                    ref, root_entity_type, seen
                )
        return seen

    def __handle_single_modified_entry(  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        self,
        ref: contentful.Entry,
        root_entity_type: contentful_svc.EntityType,
        is_reference: bool,
    ):
        if ref.content_type.id == ContentfulContentType.ARTICLE.value:
            self.__article_service.save_value_in_cache(
                ref.slug,
                self.__article_service.entry_to_article_dict(ref),
            )
            self.__article_service.remove_localized_articles_from_cache(ref.slug)
            self.__article_title_service.remove_value_from_cache(ref.id)
            index_resources.index_article_from_contentful_entry(ref)
            if root_entity_type != contentful_svc.EntityType.ASSET:
                # we don't need to re-calculate read time if only an image changed
                self.__read_time_service.save_value_in_cache(
                    ref.slug, self.__read_time_service.calculate_read_time(ref)
                )
        elif ref.content_type.id == ContentfulContentType.BANNER.value:
            self.__banner_service.save_value_in_cache(
                ref.slug, banner.Banner().load(ref.fields())
            )
        elif ref.content_type.id == ContentfulContentType.COURSE.value:
            self.__course_service.save_value_in_cache(
                ref.slug, course_factory.from_contentful_entry(ref)
            )
            # Only clear courses tag cache if it was a course that was updated
            # and not just a reference
            if not is_reference:
                # The update could have been removing a tag from a course
                # No way to know, so being safe and clearing the courses tag cache
                self.__courses_tag_service.clear_cache()
            index_resources.index_course_from_contentful_entry(ref)
        elif ref.content_type.id == ContentfulContentType.VIDEO.value:
            self.__video_service.save_value_in_cache(
                ref.slug, Video.from_contentful_entry(ref)
            )

    @staticmethod
    def __should_process_references(
        entity: Union[contentful.Entry, contentful.Asset],
        entity_type: contentful_svc.EntityType,
        ref: contentful.Entry,
    ) -> bool:
        # we don't need to continue processing up the chain of related content. Related content can happen via these
        # references chains:
        # article -> article
        # course -> article
        # course -> course
        # video -> article
        # video -> course
        # so, we should look for these reference patterns to know when to stop processing

        # this could be simplified into a single boolean return statement, but I found it way less readable
        if entity_type == contentful_svc.EntityType.ENTRY:
            if (
                entity.content_type.id == contentful_svc.ContentfulContentType.ARTICLE
                and ref.content_type.id
                in [
                    contentful_svc.ContentfulContentType.ARTICLE,
                    contentful_svc.ContentfulContentType.COURSE,
                    contentful_svc.ContentfulContentType.VIDEO,
                ]
            ):
                return False
            if (
                entity.content_type.id == contentful_svc.ContentfulContentType.COURSE
                and ref.content_type.id
                in [
                    contentful_svc.ContentfulContentType.COURSE,
                    contentful_svc.ContentfulContentType.VIDEO,
                ]
            ):
                return False

        return True
