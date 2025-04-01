import datetime
import enum
import html
import os
import re
from typing import Any, Optional, Union

import requests
import sqlalchemy
import tenacity
from contentful import Entry
from maven import feature_flags
from sqlalchemy.orm import joinedload

from common import stats
from learn.models import article_type
from learn.models import image as contentful_image
from learn.models.course import CourseChapter
from learn.services import contentful, course_service
from learn.utils import rich_text_utils
from models.marketing import (
    ContentfulMigrationStatus,
    Resource,
    ResourceTrack,
    ResourceTypes,
    tags_resources,
)
from models.virtual_events import (
    VirtualEvent,
    VirtualEventCategory,
    VirtualEventCategoryTrack,
)
from storage.connection import db
from utils.log import logger
from views.search import app_search_enabled, get_client, get_resources_engine

log = logger(__name__)
# Elastic app search can only index 100 documents at a time
BATCH_SIZE = 100
SEARCH_API_URL = (os.getenv("SEARCH_API_URL") or "") + "content_event"


def clean_resource_html(body_html: str) -> str:
    # Remove style tags
    body_html = re.sub(r"<style.*?</style>", "", body_html, flags=re.S)
    # Remove resource magic tags
    body_html = re.sub(r"{\|.*?\|}", "", body_html)
    # Remove html entities
    body_html = html.unescape(body_html)
    return body_html


def remove_html_tags(body_html: str) -> str:
    # Not super robust but does the job
    return re.sub(r"<[^<]+?>", "", body_html)


def batches(items, batch_size: int):  # type: ignore[no-untyped-def] # Function is missing a type annotation
    """Iterates over batches of items with size no bigger than batch_size"""
    count = len(items)
    for i in range(0, count, batch_size):
        yield items[i : min(i + batch_size, count)]


def run() -> None:
    # Articles must be published, have a track, and have a tag to show up in search
    resources = (
        Resource.query.filter(
            Resource.content_type.in_(["article", "real_talk", "ask_a_practitioner"])
        )
        .filter(
            Resource.resource_type == ResourceTypes.ENTERPRISE,
            Resource.published_at < sqlalchemy.func.now(),
            Resource.contentful_status.in_(
                [
                    ContentfulMigrationStatus.NOT_STARTED,
                    ContentfulMigrationStatus.IN_PROGRESS,
                ]
            ),
        )
        .join(ResourceTrack)
        .join(tags_resources)
        .all()
    )

    # On-demand classes must be published and have a track to show up in search
    # (they are not tagged)
    on_demand_classes = (
        Resource.query.filter(Resource.content_type == "on_demand_class")
        .filter(
            Resource.resource_type == ResourceTypes.ENTERPRISE,
            Resource.published_at < sqlalchemy.func.now(),
        )
        .join(ResourceTrack)
        .all()
    )

    resources.extend(on_demand_classes)

    log.debug("Building resources index", count=len(resources))

    results = []
    for resource in resources:
        # Note: this takes a while because `get_body_html()` sometimes talks to webflow
        record = _build_record_from_not_contentful_resource(resource)
        if record:
            results.append(record)

    log.debug("Sending resources index to app search", count=len(results))
    client = get_client()
    engine_name = get_resources_engine()

    for batch in batches(results, BATCH_SIZE):
        log.debug("Sending batch of resources", count=len(batch))
        client.index_documents(engine_name, batch)
        slugs = [resource.slug for resource in resources]
        publish_global_search_event(
            slugs, GlobalSearchEventType.UPDATE, ContentSource.NOT_CONTENTFUL
        )


def _build_record_from_not_contentful_resource(resource: Resource) -> dict[str, Any]:
    result = {}
    # Note: this takes a while because `get_body_html()` sometimes talks to webflow
    try:
        body_html: str = resource.get_body_html()
    except Exception as e:
        log.error(f"Error processing resource {resource.id}: {str(e)}")
        return result
    body_html = clean_resource_html(body_html)
    # Split by line breaks or <br> tags
    paragraphs = re.split(r"(?:<br[^>]*?>|\n\n|<p>)+", body_html)
    # Clean up paragraph html
    paragraphs = [remove_html_tags(p).strip() for p in paragraphs]
    # Remove empty paragraphs
    paragraphs = [p for p in paragraphs if p]

    tracks = [t.track_name for t in resource.allowed_tracks]

    result = {
        "id": f"resource:{resource.id}",
        "content_type": resource.content_type,
        "raw_id": resource.id,
        "slug": resource.slug,
        "title": resource.title,
        "body_content": "\n".join(paragraphs),
        "image_storage_key": resource.image and resource.image.storage_key,
        "tracks": tracks,
        "article_type": article_type.ArticleType.HTML,
    }
    return result


def remove_from_index(resource):  # type: ignore[no-untyped-def] # Function is missing a type annotation
    try:
        if app_search_enabled():
            client = get_client()
            engine_name = get_resources_engine()
            log.info(
                "Removing resource from Elasticsearch index",
                id=resource.id,
                slug=resource.slug,
            )
            # Will not error if a resource is not present in the index
            client.delete_documents(
                engine_name=engine_name, document_ids=[f"resource:{resource.id}"]
            )
            publish_global_search_event(
                [resource.slug],
                GlobalSearchEventType.DELETE,
                ContentSource.NOT_CONTENTFUL,
            )
    except Exception as e:
        log.error(
            "Error removing resource from Elasticsearch index",
            error=e,
            id=resource.id,
            slug=resource.slug,
        )
        raise e


def index_contentful_resource(resource):  # type: ignore[no-untyped-def] # Function is missing a type annotation
    try:
        client = contentful.LibraryContentfulClient(preview=False, user_facing=True)
        entry = client.get_article_entry_by_slug(resource.slug)
        if entry:
            index_article_from_contentful_entry(entry)
        else:
            log.warn(
                "Contentful entry not found when attempting to add to index",
                slug=resource.slug,
            )
    except Exception as e:
        log.error(
            "Error adding resource to Elasticsearch index",
            error=e,
            slug=resource.slug,
        )


def build_article_record_from_not_contentful_resource_slugs(
    resource_slugs: list[str],
) -> dict[str, dict[str, Any]]:
    records = {slug: {} for slug in resource_slugs}
    # Fetch 100 resources at a time
    for slug_batch in batches(resource_slugs, BATCH_SIZE):
        resources = Resource.query.filter(
            Resource.slug.in_(slug_batch),
            Resource.contentful_status != ContentfulMigrationStatus.LIVE,
        ).all()

        for resource in resources:
            if (
                not resource
                or resource.contentful_status == ContentfulMigrationStatus.LIVE
            ):
                log.warn(
                    "Contentful resource not found when attempting to build record",
                    slug=resource.slug,
                )
                continue
            records[resource.slug] = _build_record_from_not_contentful_resource(
                resource
            )
    return records


def build_article_record_from_contentful_resource_slugs(
    resource_slugs: list[str],
) -> dict[str, dict[str, Any]]:
    records = {slug: {} for slug in resource_slugs}
    # Fetch 100 resources at a time
    for slug_batch in batches(resource_slugs, BATCH_SIZE):
        resources = Resource.query.filter(
            Resource.slug.in_(slug_batch),
            Resource.contentful_status == ContentfulMigrationStatus.LIVE,
        ).all()

        for resource in resources:
            if (
                not resource
                or resource.contentful_status != ContentfulMigrationStatus.LIVE
            ):
                log.warn(
                    "Resource not found when attempting to build record",
                    slug=resource.slug,
                )
                continue
            client = contentful.LibraryContentfulClient(preview=False, user_facing=True)
            entry = client.get_article_entry_by_slug(resource.slug)
            if entry:
                records[resource.slug] = build_article_record_from_contentful_entry(
                    entry, resource
                )
            else:
                log.warn(
                    "Contentful not found for resource",
                    slug=resource.slug,
                )
    return records


def build_article_record_from_contentful_entry(
    entry: Entry, resource: Optional[Resource] = None
) -> dict[str, Any]:
    if not app_search_enabled():
        return {}

    if not resource:
        resource = (
            Resource.query.filter_by(
                slug=entry.slug, contentful_status=ContentfulMigrationStatus.LIVE
            )
            # Filters out resources without tracks or tags, which are not supposed
            # to show up in search
            .filter(Resource.allowed_tracks.any(), Resource.tags.any()).one_or_none()
        )

    if (
        not resource
        or not resource.published_at
        or not resource.published_at < datetime.datetime.now()
    ):
        log.info(
            "Resource not found or not eligible when attempting to add to index",
            slug=entry.slug,
        )
        return {}

    tracks = [t.track_name for t in resource.allowed_tracks]
    content_strings = []
    rich_text_utils.rich_text_to_plain_string_array(
        root_node=entry.rich_text, string_array=content_strings
    )
    image = contentful_image.Image.from_contentful_asset(entry.hero_image)
    record = {
        "id": f"resource:{resource.id}",
        "raw_id": resource.id,
        "slug": resource.slug,
        "title": entry.title,
        "body_content": " ".join(content_strings),
        "image_url": image.asset_url(width=120, height=90),
        "image_description": image.description,
        "content_type": resource.content_type,
        "tracks": tracks,
        "article_type": article_type.ArticleType.RICH_TEXT,
    }
    return record


def build_course_record_from_course_slugs(
    resource_slugs: list[str],
) -> dict[str, Any]:
    records = {}
    courses_by_slug = course_service.CourseService().get_values(resource_slugs)
    for slug, course in courses_by_slug.items():
        chapter_str = "; ".join(
            [f"{chapter.title}, {chapter.description}" for chapter in course.chapters]
        )
        course_json = {
            "id": f"course:{course.id}",
            "slug": course.slug,
            "title": course.title,
            "description": course.description,
            "body_content": f"{course.description} {chapter_str}",
            "image": {
                "url": course.image.url,
                "description": course.image.description,
            },
            "chapters": [
                _convert_course_chapter_to_json(chapter) for chapter in course.chapters
            ],
            "learning_type": LearningType.COURSE,
        }
        records[slug] = course_json
    return records


def _convert_course_chapter_to_json(course_chapter: CourseChapter) -> dict:
    if not course_chapter:
        return {}

    result = {
        "length_in_minutes": course_chapter.length_in_minutes,
    }
    return result


def build_virtual_event_record_from_event_ids(
    event_ids: list[int],
) -> dict[int, Any]:
    records = {}
    DATE_FORMAT_STR = "%Y-%m-%d %H:%M:%S"

    for event_id in event_ids:
        event, event_category, tracks = _fetch_event_and_tracks(event_id)
        if event and event_category:
            track_names_string = ", ".join([track.track_name for track in tracks])

            event_json = {
                "id": f"event:{event.id}",
                "slug": event.id,  # Global Search uses Slug as PK so reuse it for event.id
                "title": event.title,
                "body_content": f"{event.description_body} {event.what_youll_learn_body} {event.what_to_expect_body} {event_category.name} {track_names_string}",
                "description": event.description,
                "registration_form_url": event.registration_form_url,
                "scheduled_start": event.scheduled_start.strftime(DATE_FORMAT_STR),
                "scheduled_end": event.scheduled_end.strftime(DATE_FORMAT_STR),
                "active": event.active,
                "expired_at": event.scheduled_start.strftime(DATE_FORMAT_STR),
                "host_image_url": event.host_image_url,
                "host_name": event.host_name,
                "rsvp_required": event.rsvp_required,
                "cadence": getattr(event.cadence, "value", None),
                "event_image_url": event.event_image_url,
                "host_specialty": event.host_specialty,
                "provider_profile_url": event.provider_profile_url,
                "description_body": event.description_body,
                "what_youll_learn_body": event.what_youll_learn_body,
                "what_to_expect_body": event.what_to_expect_body,
                "event_category": {
                    "id": event_category.id,
                    "name": event_category.name,
                },
                "track_associations": [
                    {
                        "id": track.id,
                        "track_name": track.track_name,
                        "virtual_event_category_id": track.virtual_event_category_id,
                        "availability_start_week": track.availability_start_week,
                        "availability_end_week": track.availability_end_week,
                    }
                    for track in tracks
                ],
                "learning_type": LearningType.EVENT,
            }
        else:
            event_json = None

        records[event_id] = event_json
    return records


def _fetch_event_and_tracks(
    event_id: int,
) -> tuple[
    Union[VirtualEvent, None],
    Union[VirtualEventCategory, None],
    list[VirtualEventCategoryTrack],
]:
    event_query = (
        db.session.query(VirtualEvent, VirtualEventCategory, VirtualEventCategoryTrack)
        .join(
            VirtualEventCategory,
            VirtualEvent.virtual_event_category_id == VirtualEventCategory.id,
        )
        .join(
            VirtualEventCategoryTrack,
            VirtualEventCategory.id
            == VirtualEventCategoryTrack.virtual_event_category_id,
        )
        .filter(VirtualEvent.id == event_id)
        .all()
    )

    event: VirtualEvent = (
        db.session.query(VirtualEvent)
        .filter(VirtualEvent.id == event_id)
        .options(joinedload(VirtualEvent.virtual_event_category))
        .first()
    )
    if not event_query:
        return None, None, []

    event, event_category, _ = event_query[0]
    tracks = [track for _, _, track in event_query]

    return event, event_category, tracks


def index_article_from_contentful_entry(entry):  # type: ignore[no-untyped-def] # Function is missing a type annotation
    record = build_article_record_from_contentful_entry(entry)
    if not record:
        return

    client = get_client()
    engine_name = get_resources_engine()
    client.index_documents(engine_name, [record])
    publish_global_search_event([entry.slug], GlobalSearchEventType.UPDATE)


def remove_contentful_article_from_index(entry):  # type: ignore[no-untyped-def] # Function is missing a type annotation
    resource = Resource.query.filter_by(
        slug=entry.slug, contentful_status=ContentfulMigrationStatus.LIVE
    ).one_or_none()

    if resource:
        remove_from_index(resource)
    else:
        log.info(
            "Resource not found or not live when attempting to remove from index",
            slug=entry.slug,
        )
    publish_global_search_event([entry.slug], GlobalSearchEventType.DELETE)


def index_course_from_contentful_entry(entry: Entry) -> None:
    publish_global_search_event(
        article_slugs=[entry.slug],
        event_type=GlobalSearchEventType.UPDATE,
        learning_type=LearningType.COURSE,
    )


def remove_course_from_index(entry: Entry) -> None:
    publish_global_search_event(
        article_slugs=[entry.slug],
        event_type=GlobalSearchEventType.DELETE,
        learning_type=LearningType.COURSE,
    )


def upsert_event_from_index(event: VirtualEvent) -> None:
    if not event.active:
        publish_global_search_event(
            article_slugs=[str(event.id)],
            event_type=GlobalSearchEventType.DELETE,
            learning_type=LearningType.EVENT,
        )
    else:
        publish_global_search_event(
            article_slugs=[str(event.id)],
            event_type=GlobalSearchEventType.UPDATE,
            learning_type=LearningType.EVENT,
        )


def remove_event_from_index(event: VirtualEvent) -> None:
    publish_global_search_event(
        article_slugs=[str(event.id)],
        event_type=GlobalSearchEventType.DELETE,
        learning_type=LearningType.EVENT,
    )


class GlobalSearchEventType(str, enum.Enum):
    NEW = "NEW"
    DELETE = "DELETE"
    UPDATE = "UPDATE"


class ContentSource(str, enum.Enum):
    CONTENTFUL = "CONTENTFUL"
    NOT_CONTENTFUL = "NOT_CONTENTFUL"


# Corresponds to types from /app/library
class LearningType(str, enum.Enum):
    DEFAULT = "DEFAULT"
    COURSE = "COURSE"
    CLASS = "CLASS"
    EVENT = "EVENT"


def publish_global_search_event(
    article_slugs: list[str],
    event_type: GlobalSearchEventType,
    content_source: ContentSource = ContentSource.CONTENTFUL,
    learning_type: LearningType = LearningType.DEFAULT,
) -> None:
    headers = {"Content-type": "application/json"}
    payload = [
        {
            "slug": article_slug,
            "event_type": event_type,
            "content_source": content_source,
            "learning_type": learning_type.value,
        }
        for article_slug in article_slugs
    ]
    flag = feature_flags.bool_variation(
        "publish-global-search-events",
        default=False,
    )
    if flag:
        try:
            for attempt in tenacity.Retrying(stop=tenacity.stop_after_attempt(3)):
                with attempt:
                    stats.increment(
                        metric_name="mono.global_search_event.emitted",
                        pod_name=stats.PodNames.CORE_SERVICES,
                    )
                    requests.post(
                        SEARCH_API_URL, headers=headers, json=payload, timeout=2
                    )
        except Exception as e:
            stats.increment(
                metric_name="mono.global_search_event.failure",
                pod_name=stats.PodNames.CORE_SERVICES,
            )
            log.error(
                "Publish global search event failed",
                exception=e,
            )
