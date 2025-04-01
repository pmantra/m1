import dataclasses
from collections import defaultdict
from datetime import datetime
from typing import Dict, List, Optional

import ddtrace
from flask import make_response, request
from httpproblem import Problem
from marshmallow import Schema, fields
from sqlalchemy import and_, func
from sqlalchemy.orm import joinedload

from common.services.api import AuthenticatedResource
from learn.models.course import Course
from learn.models.resource_interaction import ResourceInteraction, ResourceType
from learn.schemas import article
from learn.services import (
    article_thumbnail_service,
    course_member_status_service,
    course_service,
    courses_tag_service,
    read_time_service,
)
from models import virtual_events
from models.marketing import (
    PopularTopic,
    Resource,
    ResourceContentTypes,
    ResourceOnDemandClass,
    ResourceTrack,
    ResourceTrackPhase,
    ResourceTypes,
    Tag,
)
from models.tracks import MemberTrack, TrackName
from models.virtual_events import VirtualEvent, get_valid_virtual_events_for_track
from storage.connection import db
from utils.contentful import parse_preview
from utils.log import logger
from views.schemas.common_v3 import ImageSchemaMixin
from views.tracks import get_user_active_track

RESOURCES_PER_TAG = 2

VIRTUAL_EVENTS_LIMIT = 4
ON_DEMAND_CLASSES_LIMIT = 4
COURSES_LIMIT = 4

log = logger(__name__)


class ResourceSchema(Schema, ImageSchemaMixin):
    id = fields.String()
    slug = fields.String()
    description = fields.String()
    title = fields.String()
    type = fields.String(attribute="article_type")
    media_type = fields.Function(lambda obj: obj.media_type)


class OnDemandClassResourceSchema(ResourceSchema):
    # doing math from epoch time because timedelta doesn't have strftime or equivalent
    # https://stackoverflow.com/a/50295735
    length = fields.Function(
        lambda x: (x.on_demand_class_fields.length + datetime.min).strftime("%H:%M")
    )
    instructor = fields.Function(lambda x: x.on_demand_class_fields.instructor)


class ArticleResourceSchema(ResourceSchema):
    estimated_read_time_minutes = fields.Integer(required=False)


class TagSchema(Schema):
    id = fields.String()
    name = fields.String()
    display_name = fields.String()
    resources = fields.List(fields.Nested(ArticleResourceSchema))


class OnDemandClassesSchema(Schema):
    on_demand_classes = fields.List(fields.Nested(OnDemandClassResourceSchema))


class SingleOnDemandClassSchema(Schema):
    on_demand_class = fields.Nested(OnDemandClassResourceSchema)


class LibraryVirtualEventSchema(Schema):
    id = fields.String()
    title = fields.String()
    host_name = fields.String()
    host_specialty = fields.String()
    registration_form_url = fields.Method("get_registration_form_url")
    rsvp_required = fields.Boolean()
    scheduled_start = fields.DateTime()
    scheduled_end = fields.DateTime()
    host_image_url = fields.String()

    def get_registration_form_url(self, obj):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        if obj.rsvp_required:
            # Return in-app registration page url
            return virtual_events.EVENT_REGISTRATION_PAGE_URL.format(event_id=obj.id)
        if obj.registration_form_url:
            # This is a drop-in group, which has no registration page;
            # this url is normally configured in admin to be the resource page
            return obj.registration_form_url

        log.warning(
            "registration_form_url is not set when rsvp_required is False",
            event_id=obj.id,
        )
        return virtual_events.EVENT_REGISTRATION_PAGE_URL.format(event_id=obj.id)


class LibraryCourseChapterSchema(Schema):
    slug = fields.String()
    length_in_minutes = fields.Integer()


class LibraryCourseSchema(Schema):
    slug = fields.String()
    title = fields.String()
    image = fields.Nested(article.ImageSchema)
    chapters = fields.List(fields.Nested(LibraryCourseChapterSchema))
    member_status = fields.String()


class ClassesSectionSchema(Schema):
    on_demand_classes = fields.List(fields.Nested(OnDemandClassResourceSchema))
    virtual_events = fields.List(fields.Nested(LibraryVirtualEventSchema))
    courses = fields.List(fields.Nested(LibraryCourseSchema))


class LibrarySchema(Schema):
    popular_topics = fields.List(fields.String)
    featured_resource = fields.Nested(ArticleResourceSchema)
    tags = fields.List(fields.Nested(TagSchema))
    classes_section = fields.Nested(ClassesSectionSchema)


@dataclasses.dataclass
class TagSection:
    id: str
    name: str
    display_name: str
    resources: List[Resource] = dataclasses.field(default_factory=list)


@dataclasses.dataclass
class ClassesSection:
    on_demand_classes: List[ResourceOnDemandClass] = dataclasses.field(
        default_factory=list
    )
    virtual_events: List[VirtualEvent] = dataclasses.field(default_factory=list)
    courses: List[Course] = dataclasses.field(default_factory=list)


@dataclasses.dataclass
class Library:
    __slots__ = ("featured_resource", "tags", "popular_topics", "classes_section")
    featured_resource: Resource
    tags: List[TagSection]
    popular_topics: List[str]
    classes_section: ClassesSection


@ddtrace.tracer.wrap()
def get_library(track: MemberTrack) -> Library:
    thumbnail_service = article_thumbnail_service.ArticleThumbnailService()
    tags = get_tags(track=track, thumbnail_service=thumbnail_service)
    featured_resource = get_featured_resource(track, thumbnail_service)
    popular_topics = get_popular_topics(track)
    classes_section = get_classes_section(track)

    return Library(
        tags=tags,
        featured_resource=featured_resource,
        popular_topics=popular_topics,
        classes_section=classes_section,
    )


@ddtrace.tracer.wrap()
def get_featured_resource(
    track: MemberTrack,
    thumbnail_service: article_thumbnail_service.ArticleThumbnailService,
) -> Optional[Resource]:
    # Return the last published resource related to this user's phase
    phase_name = track.current_phase.name

    # BEGIN TEMPORARY HACK FOR POSTPARTUM EXTENDED
    # To users in postpartum weeks > 24 (phase name week-63), we show the week 24
    # resource
    # We can get rid of this when frontends are okay receiving a NULL featured resource
    from models.tracks.phase import WEEKLY_PHASE_NAME_REGEX

    if track.name == "postpartum" and (
        phase_name == "end"
        or (
            WEEKLY_PHASE_NAME_REGEX.match(phase_name)
            and int(phase_name.split("-")[1]) > 63
        )
    ):
        phase_name = "week-63"
    # END HACK

    resource = (
        db.session.query(Resource)
        .join(ResourceTrackPhase)
        .filter(ResourceTrackPhase.track_name == track.name)
        .filter(ResourceTrackPhase.phase_name == phase_name)
        .filter(Resource.resource_type == ResourceTypes.ENTERPRISE.name)
        .filter(Resource.content_type != ResourceContentTypes.on_demand_class.name)
        .order_by(Resource.published_at.desc())
        .first()
    )

    if resource:
        if resource.is_contentful_article_ish():
            resource.estimated_read_time_minutes = (
                read_time_service.ReadTimeService().get_value(resource.slug)
            )

        return thumbnail_service.get_thumbnails_for_resources([resource])[0]  # type: ignore[return-value] # Incompatible return value type (got "ResourceWithThumbnail", expected "Optional[Resource]")

    return None


@ddtrace.tracer.wrap()
def get_tags(
    track: MemberTrack,
    thumbnail_service: article_thumbnail_service.ArticleThumbnailService,
) -> list[TagSection]:
    """
    Get all tags, each with a maximum of RESOURCE_PER_TAG resources attached to it. The
    resources are sorted by published_at in a descending way, so that the N newest
    articles are the ones that are selected.

    Only resources associated with the given track are loaded.

    This cannot be done with SQL because mysql does not support the ROW_NUMBER()
    function. Instead, we load all resource IDs into memory, group them by tag, and
    use that list of IDs to fetch the selected resources.
    """

    resource_tag_id_pairs = (
        db.session.query(Resource.id, Tag.id)
        .join(Resource.tags)
        .join(ResourceTrack)
        .filter(ResourceTrack.track_name == track.name)
        .filter(Resource.resource_type == ResourceTypes.ENTERPRISE.name)
        .filter(Resource.content_type != ResourceContentTypes.on_demand_class.name)
        .order_by(Resource.published_at.desc(), Tag.id)
        .group_by(Resource.id, Tag.id)
    )
    tag_id_by_resource = {}
    resource_ids_by_tag_id = defaultdict(list)
    resource_ids, tag_ids = set(), set()
    for resource_id, tag_id in resource_tag_id_pairs:
        if len(resource_ids_by_tag_id[tag_id]) >= RESOURCES_PER_TAG:
            continue
        if resource_id in tag_id_by_resource:
            # This resource has already been "claimed" by another tag
            continue
        resource_ids_by_tag_id[tag_id].append(resource_id)
        resource_ids.add(resource_id)
        tag_ids.add(tag_id)
        tag_id_by_resource[resource_id] = tag_id

    resources = (
        db.session.query(Resource)
        .filter(Resource.id.in_(resource_ids))
        .options(joinedload(Resource.image))
        .all()
    )

    resources_metadata = read_time_service.ReadTimeService().get_values(
        [
            resource.slug
            for resource in resources
            if resource.is_contentful_article_ish()
        ]
    )

    for resource in resources:
        resource.estimated_read_time_minutes = resources_metadata.get(resource.slug)

    resources = thumbnail_service.get_thumbnails_for_resources(resources)

    # TODO: sort tags by something in particular?
    tags_by_id = {
        tag.id: TagSection(*tag)
        for tag in db.session.query(Tag.id, Tag.name, Tag.display_name)
        .filter(Tag.id.in_(tag_ids))  # type: ignore[attr-defined] # "int" has no attribute "in_"
        .all()
    }

    for res in resources:
        tag = tags_by_id[tag_id_by_resource[res.id]]
        tag.resources.append(res)
    return [tag for tag in tags_by_id.values() if tag.resources]


@ddtrace.tracer.wrap()
def get_popular_topics(track: MemberTrack):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
    """
    Gets the popular topics per track
    """
    query = (
        db.session.query(PopularTopic.topic)
        .filter(PopularTopic.track_name == track.name)
        .order_by(PopularTopic.sort_order)
    )
    return [topic for topic, in query]


@ddtrace.tracer.wrap()
def get_classes_section(track: MemberTrack):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
    on_demand_classes = get_on_demand_classes(track, limit=ON_DEMAND_CLASSES_LIMIT)

    # limit number of classes shown to follow current designs
    virtual_events = get_valid_virtual_events_for_track(track, VIRTUAL_EVENTS_LIMIT)

    courses = get_courses_for_track(
        track_name=TrackName(track.name), user_id=track.user.id, limit=COURSES_LIMIT
    )

    return ClassesSection(
        on_demand_classes=on_demand_classes,
        virtual_events=virtual_events,
        courses=courses,
    )


@ddtrace.tracer.wrap()
def get_on_demand_classes(track: MemberTrack, limit: Optional[int] = None):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
    on_demand_classes_query = (
        db.session.query(Resource)
        .join(ResourceOnDemandClass)
        .join(ResourceTrack)
        .filter(ResourceTrack.track_name == track.name)
        .filter(Resource.resource_type == ResourceTypes.ENTERPRISE.name)
        .filter(Resource.content_type == ResourceContentTypes.on_demand_class.name)
        .filter(Resource.published_at <= func.now())
        .order_by(Resource.published_at.desc())
    )
    if limit:
        on_demand_classes_query = on_demand_classes_query.limit(limit)
    return on_demand_classes_query.all()


def get_courses_for_track(
    track_name: TrackName,
    user_id: int,
    limit: Optional[int] = None,
    preview: bool = False,
) -> List[Course]:
    service = courses_tag_service.CoursesTagService(preview=preview, user_facing=True)
    courses = service.get_courses_for_tag(tag=track_name, limit=limit)
    return (
        course_member_status_service.CourseMemberStatusService.set_statuses_on_courses(
            courses=courses, user_id=user_id
        )
    )


class OnDemandClassesResource(AuthenticatedResource):
    def __init__(self) -> None:
        self.on_demand_classes_schema = OnDemandClassesSchema()
        super().__init__()

    def get(self, track_id: int):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        track = get_user_active_track(self.user, track_id)
        on_demand_classes = get_on_demand_classes(track)
        json = self.on_demand_classes_schema.dump(
            {"on_demand_classes": on_demand_classes}
        )
        return make_response(json, 200)


class LibraryResource(AuthenticatedResource):
    def __init__(self) -> None:
        self.library_schema = LibrarySchema()
        super().__init__()

    def get(self, track_id: int):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        track = get_user_active_track(self.user, track_id)
        library = get_library(track)
        json = self.library_schema.dump(library)
        return make_response(json, 200)


class CourseResource(AuthenticatedResource):
    def get(self, slug: str):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        preview = parse_preview(request.args)
        course = course_service.CourseService(preview=preview).get_value(slug)
        if not course:
            raise Problem(404)

        resource_interactions = {
            resource_interaction.slug: resource_interaction
            for resource_interaction in db.session.query(ResourceInteraction)
            .filter(
                and_(
                    ResourceInteraction.user_id == self.user.id,
                    ResourceInteraction.resource_type == ResourceType.ARTICLE,
                    ResourceInteraction.slug.in_(
                        [chapter.slug for chapter in course.chapters]
                    ),
                )
            )
            .all()
        }

        for chapter in course.chapters:
            if resource_interaction := resource_interactions.get(chapter.slug):
                chapter.viewed_at = resource_interaction.resource_viewed_at

        status_record = course_member_status_service.CourseMemberStatusService.get(
            user_id=self.user.id,
            course_slug=course.slug,
        )
        course.set_status(status_record)

        return make_response(course.to_response_dict(), 200)


class CoursesResource(AuthenticatedResource):
    __MAXIMUM_NUMBER_OF_SLUGS = 104  # 2 per week

    def get(self):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        preview = parse_preview(request.args)

        track_name = self.__parse_track_name(request.args)
        slugs = self.__parse_slugs(request.args)

        if (track_name and slugs) or (not track_name and not slugs):
            raise Problem(
                400, "Exactly one filter (track_name or slugs) must be provided."
            )

        if track_name:
            courses = get_courses_for_track(
                track_name=track_name, user_id=self.user.id, preview=preview
            )
        else:
            courses = list(
                course_service.CourseService(preview=preview).get_values(slugs).values()  # type: ignore[arg-type] # Argument 1 to "get_values" of "ContentfulCachingService" has incompatible type "Optional[List[str]]"; expected "List[str]"
            )
            courses = course_member_status_service.CourseMemberStatusService.set_statuses_on_courses(
                courses=courses, user_id=self.user.id
            )

        courses = course_service.CourseService.populate_viewed_at(courses, self.user.id)

        courses.sort(key=lambda course: course.slug)

        return make_response(
            {"courses": [course.to_response_dict() for course in courses]}, 200
        )

    @staticmethod
    def __parse_track_name(request_args: Dict[str, str]) -> Optional[TrackName]:
        if "track_name" in request_args:
            try:
                return TrackName(request_args["track_name"])
            except ValueError:
                raise Problem(400, "Invalid track_name.")
        return None

    @staticmethod
    def __parse_slugs(request_args: Dict[str, str]) -> Optional[List[str]]:
        if "slugs" in request_args:
            slugs = request_args["slugs"].split(",")
            if (
                not slugs
                or not slugs[0]
                or len(slugs) > CoursesResource.__MAXIMUM_NUMBER_OF_SLUGS
            ):
                raise Problem(
                    400,
                    f"slugs must have between 1 and {CoursesResource.__MAXIMUM_NUMBER_OF_SLUGS} values, inclusive.",
                )
            return slugs
        return None
