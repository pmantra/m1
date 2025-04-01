import copy
import datetime
from unittest import mock

import pytest
from dateutil import parser
from flask.testing import FlaskClient

from learn.models import (
    article,
    article_type,
    course_factory,
    image,
    migration,
    resource_interaction,
)
from learn.models.article_type import ArticleType
from learn.models.course import (
    Course,
    CourseCallout,
    CourseChapter,
    RelatedCourse,
    RelatedCourseChapter,
)
from learn.models.course_member_status import MemberStatus
from learn.models.migration import ContentfulMigrationStatus
from learn.services import article_thumbnail_service
from learn.services.course_service import CourseService
from models import marketing
from models.marketing import ResourceContentTypes, ResourceOnDemandClass, ResourceTypes
from models.tracks import TrackName
from models.virtual_events import get_valid_virtual_events_for_track
from pytests.factories import (
    EnterpriseUserFactory,
    MemberTrackFactory,
    PopularTopicFactory,
    ResourceFactory,
    TagFactory,
    VirtualEventCategoryFactory,
    VirtualEventCategoryTrackFactory,
    VirtualEventFactory,
)
from storage.connection import db
from utils.api_interaction_mixin import APIInteractionMixin
from views.library import (
    ClassesSectionSchema,
    get_classes_section,
    get_courses_for_track,
    get_featured_resource,
    get_popular_topics,
    get_tags,
)
from views.models import cta

__COURSE = Course(
    id="1KWykUOEklzRooTKhG755S",
    slug="course-1",
    title="title",
    image=image.Image(
        url="https://upload.wikimedia.org/wikipedia",  # this is what PyCharm autocompleted for some reason 🤷
        description="description",
    ),
    description="description",
    callout=CourseCallout(
        title="title", cta=cta.CTA(text="text", url="https://upload.wikimedia.org")
    ),
    chapters=[
        CourseChapter(
            slug="chapter-1-1",
            title="title",
            description="description",
            image=image.Image(
                url="https://upload.wikimedia", description="description"
            ),
        ),
        CourseChapter(
            slug="chapter-1-2",
            title="title",
            description="description",
            image=image.Image(
                url="https://upload.wikimedia", description="description"
            ),
        ),
        CourseChapter(
            slug="chapter-1-3",
            title="title",
            description="description",
            image=image.Image(
                url="https://upload.wikimedia", description="description"
            ),
        ),
    ],
    related=[
        RelatedCourse(
            title="title",
            thumbnail=image.Image(
                url="https://upload.wikimedia", description="description"
            ),
            slug="course-2",
            chapters=[
                RelatedCourseChapter(
                    slug="chapter-2-1",
                ),
                RelatedCourseChapter(
                    slug="chapter-2-2",
                ),
            ],
        ),
        article.RelatedRead(
            title="title",
            thumbnail=image.Image(url="https://upload", description="description"),
            slug="article-1",
            type=article_type.ArticleType.RICH_TEXT,
        ),
    ],
)
__COURSE.chapters[0].length_in_minutes = 123
__COURSE.related[0].chapters[0].length_in_minutes = 456


def weeks_ago(n: int):
    return datetime.datetime.now() - datetime.timedelta(weeks=n)


def create_tag():
    tag = TagFactory.create()
    (oldest, middle, newest) = (weeks_ago(n) for n in [3, 2, 1])
    resources = [
        ResourceFactory.create(tracks=["pregnancy"], tags=[tag], published_at=oldest),
        ResourceFactory.create(
            tracks=["pregnancy", "postpartum"], tags=[tag], published_at=middle
        ),
        ResourceFactory.create(tracks=["pregnancy"], tags=[tag], published_at=newest),
    ]
    return tag, resources


def _make_resource_with_thumbnail(resource):
    return article_thumbnail_service.ResourceWithThumbnail(
        id=resource.id,
        slug=resource.slug,
        title=resource.title,
        article_type=resource.article_type,
        image=resource.image,
        content_type=resource.content_type,
        content_url=resource.content_url,
        subhead=resource.subhead,
    )


@mock.patch("learn.services.courses_tag_service.CoursesTagService")
@mock.patch("learn.services.read_time_service.ReadTimeService")
class TestLibraryView:
    def test_library_works_with_no_content(self, _, __, client, api_helpers):
        user = EnterpriseUserFactory.create()
        track_id = user.active_tracks[0].id
        res = client.get(
            f"/api/v1/library/{track_id}", headers=api_helpers.json_headers(user)
        )
        assert res.status_code == 200

    def test_library_endpoint_with_content(self, _, __, client, api_helpers):
        create_tag()
        create_tag()
        ResourceFactory.create(phases=[("pregnancy", "week-2")])
        user = EnterpriseUserFactory.create(
            tracks__name="pregnancy", tracks__current_phase="week-2"
        )

        PopularTopicFactory.create(track_name="pregnancy")
        PopularTopicFactory.create(track_name="pregnancy")
        PopularTopicFactory.create(track_name="not-pregnancy")

        ResourceFactory.create(
            content_type=ResourceContentTypes.on_demand_class.name,
            tracks=["pregnancy"],
            on_demand_class_fields=ResourceOnDemandClass(
                length=datetime.timedelta(hours=1, minutes=2),
                instructor="Postpartum Doula",
            ),
            published_at=weeks_ago(3),
        )

        ResourceFactory.create(
            content_type=ResourceContentTypes.on_demand_class.name,
            tracks=["pregnancy"],
            on_demand_class_fields=ResourceOnDemandClass(
                length=datetime.timedelta(minutes=43), instructor="Postpartum Doula 2"
            ),
            published_at=weeks_ago(1),
        )
        stress_category = VirtualEventCategoryFactory(name="stress-and-anxiety")
        VirtualEventCategoryTrackFactory(
            category=stress_category, track_name="pregnancy"
        )
        event = VirtualEventFactory.create(
            scheduled_start=datetime.datetime.now() + datetime.timedelta(days=1),
            title="Don't be stressed!",
            virtual_event_category=stress_category,
        )

        preg_101_category = VirtualEventCategoryFactory(name="pregnancy-101")
        VirtualEventCategoryTrackFactory(
            category=preg_101_category, track_name="pregnancy"
        )
        VirtualEventFactory.create(
            scheduled_start=datetime.datetime.now() + datetime.timedelta(days=2),
            virtual_event_category=preg_101_category,
        )
        VirtualEventFactory.create(
            scheduled_start=datetime.datetime.now() + datetime.timedelta(days=3),
            virtual_event_category=preg_101_category,
        )
        VirtualEventFactory.create(
            scheduled_start=datetime.datetime.now() + datetime.timedelta(days=4),
            title="All you need to know!",
            virtual_event_category=preg_101_category,
        )

        # this class already happened so shouldn't be in the list
        VirtualEventFactory.create(
            scheduled_start=datetime.datetime.now() - datetime.timedelta(days=2),
            virtual_event_category=preg_101_category,
        )
        # "infant-cpr" class category is not available for this user track/phase, so it shouldn't show up in the response
        VirtualEventFactory.create(
            virtual_event_category=VirtualEventCategoryFactory(name="infant-cpr"),
        )

        res = client.get(
            f"/api/v1/library/{user.active_tracks[0].id}",
            headers=api_helpers.json_headers(user=user),
        )
        data = api_helpers.load_json(res)
        assert res.status_code == 200
        assert len(data["tags"]) == 2
        assert "slug" in api_helpers.load_json(res)["featured_resource"]

        assert len(data["popular_topics"]) == 2
        assert len(data["classes_section"]["on_demand_classes"]) == 2
        assert data["classes_section"]["on_demand_classes"][0].get("sub_header") is None
        assert data["classes_section"]["on_demand_classes"][0]["length"] == "00:43"
        assert len(data["classes_section"]["virtual_events"]) == 4
        assert (
            data["classes_section"]["virtual_events"][0]["title"]
            == "Don't be stressed!"
        )
        assert (
            data["classes_section"]["virtual_events"][0]["host_specialty"]
            == event.host_specialty
        )
        assert (
            data["classes_section"]["virtual_events"][3]["title"]
            == "All you need to know!"
        )

    def test_library_filters_out_private_resources(self, _, __, client, api_helpers):
        tag = TagFactory.create()
        user = EnterpriseUserFactory.create(tracks__name="pregnancy")
        enterprise_resource = ResourceFactory.create(
            tracks=["pregnancy"],
            tags=[tag],
            published_at=weeks_ago(1),
            resource_type=ResourceTypes.ENTERPRISE,
        )
        ResourceFactory.create(
            tracks=["pregnancy"],
            tags=[tag],
            published_at=weeks_ago(1),
            resource_type=ResourceTypes.PRIVATE,
        )
        res = client.get(
            f"/api/v1/library/{user.active_tracks[0].id}",
            headers=api_helpers.json_headers(user=user),
        )
        data = api_helpers.load_json(res)

        assert len(data["tags"]) == 1
        assert len(data["tags"][0]["resources"]) == 1
        assert data["tags"][0]["resources"][0]["id"] == str(enterprise_resource.id)

    def test_library_shows_rich_text_type(self, _, __, client, api_helpers):
        tag = TagFactory.create()
        tag2 = TagFactory.create()
        user = EnterpriseUserFactory.create(tracks__name="pregnancy")
        resource1 = ResourceFactory.create(
            tracks=["pregnancy"],
            tags=[tag],
            published_at=weeks_ago(1),
            resource_type=ResourceTypes.ENTERPRISE,
            contentful_status=ContentfulMigrationStatus.NOT_STARTED,
        )
        resource2 = ResourceFactory.create(
            tracks=["pregnancy"],
            tags=[tag],
            published_at=weeks_ago(2),
            resource_type=ResourceTypes.ENTERPRISE,
            contentful_status=ContentfulMigrationStatus.IN_PROGRESS,
        )
        resource3 = ResourceFactory.create(
            tracks=["pregnancy"],
            tags=[tag2],
            published_at=weeks_ago(1),
            resource_type=ResourceTypes.ENTERPRISE,
            contentful_status=ContentfulMigrationStatus.LIVE,
        )
        res = client.get(
            f"/api/v1/library/{user.active_tracks[0].id}",
            headers=api_helpers.json_headers(user=user),
        )
        data = api_helpers.load_json(res)
        tagged_resources = [tag["resources"] for tag in data["tags"]]
        # this flattens the list
        resources = [
            resource for resource_list in tagged_resources for resource in resource_list
        ]

        assert resources[0]["slug"] == resource1.slug
        assert resources[0]["type"] == ArticleType.HTML

        assert resources[1]["slug"] == resource2.slug
        assert resources[1]["type"] == ArticleType.HTML

        assert resources[2]["slug"] == resource3.slug
        assert resources[2]["type"] == ArticleType.RICH_TEXT

    @mock.patch("views.library.article_thumbnail_service")
    def test_library_images(self, cache_mock, _, __, client, api_helpers):
        user = EnterpriseUserFactory.create(
            tracks__name="pregnancy", tracks__current_phase="week-5"
        )

        # Resource that will show up in the "featured_resource" portion of the response
        featured_resource = ResourceFactory.create(
            tracks=["pregnancy"],
            phases=[("pregnancy", "week-5")],
            published_at=weeks_ago(2),
        )
        featured_img_mock = mock.Mock()
        featured_img_url = "imag.es/img1.png"
        featured_img_mock.asset_url.return_value = featured_img_url

        # Resource that will show up in the "tags" portion of the response
        tag = TagFactory.create()
        resource = ResourceFactory.create(
            tracks=["pregnancy"],
            tags=[tag],
            published_at=weeks_ago(1),
        )
        tag_img_mock = mock.Mock()
        tag_img_url = "imag.es/img2.png"
        tag_img_mock.asset_url.return_value = tag_img_url

        thumb_service_mock = mock.Mock()
        cache_mock.ArticleThumbnailService.return_value = thumb_service_mock
        thumb_service_mock.get_thumbnails_for_resources.side_effect = [
            # Return value when called for tags
            [
                article_thumbnail_service.ResourceWithThumbnail(
                    id=resource.id,
                    slug=resource.slug,
                    title=resource.title,
                    article_type=resource.article_type,
                    image=tag_img_mock,
                    content_type=resource.content_type,
                    content_url=resource.content_url,
                    subhead=resource.subhead,
                )
            ],
            # Return value when called for featured resource
            [
                article_thumbnail_service.ResourceWithThumbnail(
                    id=featured_resource.id,
                    slug=featured_resource.slug,
                    title=featured_resource.title,
                    article_type=featured_resource.article_type,
                    image=featured_img_mock,
                    content_type=featured_resource.content_type,
                    content_url=featured_resource.content_url,
                    subhead=featured_resource.subhead,
                )
            ],
        ]

        res = client.get(
            f"/api/v1/library/{user.active_tracks[0].id}",
            headers=api_helpers.json_headers(user=user),
        )
        data = api_helpers.load_json(res)

        get_thumbs_call1 = mock.call([resource])
        get_thumbs_call2 = mock.call([featured_resource])
        thumb_service_mock.get_thumbnails_for_resources.assert_has_calls(
            [get_thumbs_call1, get_thumbs_call2]
        )

        call1 = mock.call(None, None)
        call2 = mock.call(428, 760, smart=False)
        call3 = mock.call(90, 120, smart=False)
        assert tag_img_mock.has_calls([call1, call2, call3])
        for img_type in ["original", "hero", "thumbnail"]:
            assert data["tags"][0]["resources"][0]["image"][img_type] == tag_img_url

        call1 = mock.call(None, None)
        call2 = mock.call(428, 760, smart=False)
        call3 = mock.call(90, 120, smart=False)
        assert featured_img_mock.has_calls([call1, call2, call3])
        for img_type in ["original", "hero", "thumbnail"]:
            assert data["featured_resource"]["image"][img_type] == featured_img_url


@mock.patch("learn.services.read_time_service.ReadTimeService")
def test_library_featured_resource(mock_read_time_service_constructor):
    (oldest, middle, newer, newest) = (weeks_ago(n) for n in [4, 3, 2, 1])

    resources = [
        ResourceFactory.create(phases=[("pregnancy", "week-1")], published_at=newest),
        ResourceFactory.create(
            phases=[("pregnancy", "week-2")],
            published_at=newer,
            content_type=ResourceContentTypes.on_demand_class.name,
        ),
        ResourceFactory.create(
            phases=[("pregnancy", "week-2")],
            published_at=middle,
            content_type=marketing.ResourceContentTypes.article.name,
            contentful_status=migration.ContentfulMigrationStatus.LIVE,
        ),
        ResourceFactory.create(phases=[("pregnancy", "week-2")], published_at=oldest),
    ]
    track = MemberTrackFactory.create(name="pregnancy", current_phase="week-2")

    mock_read_time_service_constructor.return_value.get_value.return_value = 420

    thumb_service_mock = mock.Mock()
    resource_with_thumbnail = mock.Mock()
    thumb_service_mock.get_thumbnails_for_resources.return_value = [
        resource_with_thumbnail
    ]

    featured_resource = get_featured_resource(track, thumb_service_mock)

    # Featured resource should be latest resource associated with current phase that isn't an on demand class
    mock_read_time_service_constructor.return_value.get_value.assert_called_once_with(
        resources[2].slug
    )
    thumb_service_mock.get_thumbnails_for_resources.assert_called_with([resources[2]])
    assert featured_resource == resource_with_thumbnail


@mock.patch("learn.services.read_time_service.ReadTimeService")
def test_library_tag_sections_limit(_):
    tag1, tag1_resources = create_tag()
    tag2, tag2_resources = create_tag()

    pregnancy_track = MemberTrackFactory.create(name="pregnancy")
    thumb_service_mock = mock.Mock()
    # We expect each tag to come back with these two pregnancy resources, because
    # they're the most recently published
    expected_resources = tag1_resources[1:3] + tag2_resources[1:3]
    thumb_service_mock.get_thumbnails_for_resources.return_value = [
        _make_resource_with_thumbnail(r) for r in expected_resources
    ]

    returned_tags = get_tags(
        track=pregnancy_track, thumbnail_service=thumb_service_mock
    )

    thumb_service_mock.get_thumbnails_for_resources.assert_called_with(
        expected_resources
    )
    assert len(returned_tags) == 2
    for configured_tag in [tag1, tag2]:
        matching_tag = next(t for t in returned_tags if t.name == configured_tag.name)
        assert {r.id for r in matching_tag.resources} == {
            r.id for r in configured_tag.resources[1:3]
        }


@mock.patch("learn.services.read_time_service.ReadTimeService")
def test_library_tag_sections_multiple_tracks(_):
    tag1, tag1_resources = create_tag()
    tag2, tag2_resources = create_tag()

    postpartum_track = MemberTrackFactory.create(name="postpartum")
    thumb_service_mock = mock.Mock()
    # We expect each tag to come back with just the resource tagged postpartum
    expected_resources = [tag1_resources[1], tag2_resources[1]]
    thumb_service_mock.get_thumbnails_for_resources.return_value = [
        _make_resource_with_thumbnail(r) for r in expected_resources
    ]

    returned_tags = get_tags(
        track=postpartum_track, thumbnail_service=thumb_service_mock
    )

    thumb_service_mock.get_thumbnails_for_resources.assert_called_with(
        expected_resources
    )
    assert len(returned_tags) == 2
    for configured_tag in [tag1, tag2]:
        matching_tag = next(t for t in returned_tags if t.name == configured_tag.name)
        assert len(matching_tag.resources) == 1
        assert matching_tag.resources[0].id == configured_tag.resources[1].id


@mock.patch("learn.services.read_time_service.ReadTimeService")
def test_library_tag_sections_none(_):
    tag1, tag1_resources = create_tag()
    tag2, tag2_resources = create_tag()
    fertility_track = MemberTrackFactory.create(name="fertility")
    thumb_service_mock = mock.Mock()
    thumb_service_mock.get_thumbnails_for_resources.return_value = []

    returned_tags = get_tags(
        track=fertility_track, thumbnail_service=thumb_service_mock
    )

    thumb_service_mock.get_thumbnails_for_resources.assert_called_with([])
    assert len(returned_tags) == 0


@mock.patch("learn.services.read_time_service.ReadTimeService")
def test_library_tag_sections_with_multiple_tags(_):
    tag1, tag2, tag3 = TagFactory.create(), TagFactory.create(), TagFactory.create()
    (time1, time2, time3, time4, time5) = (weeks_ago(n) for n in [5, 4, 3, 2, 1])
    resources = [
        ResourceFactory.create(tracks=["pregnancy"], tags=[tag2], published_at=time1),
        ResourceFactory.create(tracks=["pregnancy"], tags=[tag2], published_at=time2),
        ResourceFactory.create(
            tracks=["pregnancy"], tags=[tag1, tag2], published_at=time3
        ),
        ResourceFactory.create(
            tracks=["pregnancy"], tags=[tag1, tag2], published_at=time4
        ),
    ]
    # On-demand class shouldn't show up since it goes in the classes section
    ResourceFactory.create(
        tracks=["pregnancy"],
        tags=[tag3],
        published_at=time5,
        content_type=ResourceContentTypes.on_demand_class.name,
    )
    track = MemberTrackFactory.create(name="pregnancy")

    thumb_service_mock = mock.Mock()
    thumb_service_mock.get_thumbnails_for_resources.return_value = [
        _make_resource_with_thumbnail(r) for r in resources
    ]
    tags = get_tags(track=track, thumbnail_service=thumb_service_mock)

    thumb_service_mock.get_thumbnails_for_resources.assert_called_with(resources)
    assert len(tags) == 2
    for tag in tags:
        assert len(tag.resources) == 2


@pytest.mark.parametrize(
    "content_type",
    (
        marketing.ResourceContentTypes.article,
        marketing.ResourceContentTypes.real_talk,
        marketing.ResourceContentTypes.ask_a_practitioner,
        marketing.ResourceContentTypes.curriculum_step,
    ),
)
@mock.patch("learn.services.read_time_service.ReadTimeService")
def test_library_tag_sections_with_estimated_read_time_minutes(
    mock_read_time_service_constructor, content_type: marketing.ResourceContentTypes
):
    tag = TagFactory.create()
    track = MemberTrackFactory.create(name="pregnancy")
    resource = ResourceFactory.create(
        tracks=[track.name],
        tags=[tag],
        published_at=weeks_ago(1),
        content_type=content_type.name,
        contentful_status=migration.ContentfulMigrationStatus.LIVE,
    )

    mock_read_time_service_constructor.return_value.get_values.return_value = {
        resource.slug: 420
    }

    thumb_service_mock = mock.Mock()
    resource_with_thumbnail = _make_resource_with_thumbnail(resource)
    resource_with_thumbnail.estimated_read_time_minutes = 420
    thumb_service_mock.get_thumbnails_for_resources.return_value = [
        resource_with_thumbnail
    ]

    returned_tags = get_tags(track=track, thumbnail_service=thumb_service_mock)

    mock_read_time_service_constructor.return_value.get_values.assert_called_once_with(
        [resource.slug]
    )
    thumb_service_mock.get_thumbnails_for_resources.assert_called_once_with([resource])

    assert len(returned_tags) == 1
    assert len(returned_tags[0].resources) == 1
    assert returned_tags[0].resources[0].id == tag.resources[0].id
    assert returned_tags[0].resources[0].estimated_read_time_minutes == 420


@mock.patch("learn.services.read_time_service.ReadTimeService")
def test_library_tag_sections_with_estimated_read_time_minutes_but_there_is_none(
    mock_read_time_service_constructor,
):
    tag = TagFactory.create()
    track = MemberTrackFactory.create(name="pregnancy")
    resource = ResourceFactory.create(
        tracks=[track.name],
        tags=[tag],
        published_at=weeks_ago(1),
        content_type=marketing.ResourceContentTypes.article.name,
        contentful_status=migration.ContentfulMigrationStatus.LIVE,
    )

    mock_read_time_service_constructor.return_value.get_values.return_value = {}

    thumb_service_mock = mock.Mock()
    thumb_service_mock.get_thumbnails_for_resources.return_value = [
        _make_resource_with_thumbnail(resource)
    ]

    returned_tags = get_tags(track=track, thumbnail_service=thumb_service_mock)

    mock_read_time_service_constructor.return_value.get_values.assert_called_once_with(
        [resource.slug]
    )
    thumb_service_mock.get_thumbnails_for_resources.assert_called_once_with([resource])

    assert len(returned_tags) == 1
    assert len(returned_tags[0].resources) == 1
    assert returned_tags[0].resources[0].id == tag.resources[0].id
    assert returned_tags[0].resources[0].estimated_read_time_minutes is None


def test_virtual_events_postpartum_offset():
    week_9_postpartum = MemberTrackFactory(
        name="postpartum",
        anchor_date=(datetime.date.today() - datetime.timedelta(weeks=8)),
    )

    # 8 weeks ago = 9th week + 39 offset
    assert week_9_postpartum.current_phase.name == "week-48"
    early_postpartum_category = VirtualEventCategoryFactory(name="breastfeeding-101")
    VirtualEventCategoryTrackFactory(
        category=early_postpartum_category,
        track_name="postpartum",
        availability_end_week=10,
    )
    virtual_event = VirtualEventFactory.create(
        scheduled_start=datetime.datetime.now() + datetime.timedelta(days=2),
        virtual_event_category=early_postpartum_category,
    )

    valid_events = get_valid_virtual_events_for_track(week_9_postpartum)
    assert len(valid_events) == 1
    assert valid_events[0].host_name == virtual_event.host_name
    assert valid_events[0].virtual_event_category.name == early_postpartum_category.name


def test_virtual_events_urls(factories):
    user = factories.EnterpriseUserFactory(tracks__name="fertility")
    category = factories.VirtualEventCategoryFactory(name="fertility-101")
    factories.VirtualEventCategoryTrackFactory(
        category=category, track_name="fertility"
    )
    event = factories.VirtualEventFactory(
        virtual_event_category=category, rsvp_required=True
    )
    event2 = factories.VirtualEventFactory(
        virtual_event_category=category, rsvp_required=False
    )
    event3 = factories.VirtualEventFactory(
        virtual_event_category=category, rsvp_required=True, registration_form_url=None
    )

    virtual_events = get_valid_virtual_events_for_track(user.active_tracks[0])
    classes_section = ClassesSectionSchema().dump({"virtual_events": virtual_events})

    assert (
        classes_section["virtual_events"][0]["registration_form_url"]
        == f"/app/event-registration/{event.id}"
    )
    assert (
        classes_section["virtual_events"][1]["registration_form_url"]
        == event2.registration_form_url
    )
    assert (
        classes_section["virtual_events"][2]["registration_form_url"]
        == f"/app/event-registration/{event3.id}"
    )


@mock.patch("views.library.log")
def test_virtual_events_urls_misconfiguration(mock_log, factories):
    user = factories.EnterpriseUserFactory(tracks__name="fertility")
    category = factories.VirtualEventCategoryFactory(name="fertility-101")
    factories.VirtualEventCategoryTrackFactory(
        category=category, track_name="fertility"
    )
    event = factories.VirtualEventFactory(
        virtual_event_category=category, rsvp_required=False, registration_form_url=None
    )

    virtual_events = get_valid_virtual_events_for_track(user.active_tracks[0])
    classes_section = ClassesSectionSchema().dump({"virtual_events": virtual_events})

    assert (
        classes_section["virtual_events"][0]["registration_form_url"]
        == f"/app/event-registration/{event.id}"
    )
    mock_log.warning.called_once_with(
        "registration_form_url is not set when rsvp_required is False",
        event_id=event.id,
    )


def test_popular_topics():
    adoption_user_track = MemberTrackFactory.create(name="adoption")
    egg_freezing_user_track = MemberTrackFactory.create(name="egg_freezing")
    bms_user_track = MemberTrackFactory.create(name="breast_milk_shipping")

    PopularTopicFactory.create(
        track_name="adoption", topic="A nice topic", sort_order=2
    )
    PopularTopicFactory.create(
        track_name="adoption", topic="Another nice topic", sort_order=1
    )
    PopularTopicFactory.create(
        track_name="egg_freezing", topic="A different nice topic", sort_order=1
    )
    PopularTopicFactory.create(
        track_name="egg_freezing", topic="One more nice topic", sort_order=2
    )

    adoption_topics = get_popular_topics(adoption_user_track)
    egg_freezing_topics = get_popular_topics(egg_freezing_user_track)
    bms_user_topics = get_popular_topics(bms_user_track)

    assert adoption_topics == ["Another nice topic", "A nice topic"]
    assert egg_freezing_topics == ["A different nice topic", "One more nice topic"]
    assert bms_user_topics == []


@mock.patch("learn.services.courses_tag_service.CoursesTagService")
class TestLibraryClassesSection:
    def test_library_on_demand_classes_limit(self, _):
        for _ in range(5):
            ResourceFactory.create(
                content_type=ResourceContentTypes.on_demand_class.name,
                tracks=["pregnancy"],
                on_demand_class_fields=ResourceOnDemandClass(
                    length=datetime.timedelta(hours=1),
                    instructor="Kat",
                ),
            )
        track = MemberTrackFactory.create(name="pregnancy")
        classes_section = get_classes_section(track)
        assert len(classes_section.on_demand_classes) == 4


def test_on_demand_classes(client, api_helpers):
    user = EnterpriseUserFactory.create(tracks__name="pregnancy")
    track_id = user.active_tracks[0].id
    ResourceFactory.create(
        content_type=ResourceContentTypes.on_demand_class.name,
        published_at=weeks_ago(2),
        tracks=["pregnancy", "postpartum"],
        on_demand_class_fields=ResourceOnDemandClass(
            length=datetime.timedelta(hours=1, minutes=2),
            instructor="Postpartum Doula 1",
        ),
    )
    ResourceFactory.create(
        content_type=ResourceContentTypes.on_demand_class.name,
        published_at=weeks_ago(1),
        tracks=["pregnancy"],
        on_demand_class_fields=ResourceOnDemandClass(
            length=datetime.timedelta(hours=1, minutes=32),
            instructor="Postpartum Doula 2",
        ),
    )
    ResourceFactory.create(
        content_type=ResourceContentTypes.on_demand_class.name,
        published_at=weeks_ago(4),
        tracks=["fertility"],
        on_demand_class_fields=ResourceOnDemandClass(
            length=datetime.timedelta(hours=2, minutes=22),
            instructor="Instructor",
        ),
    )

    res = client.get(
        f"/api/v1/library/on_demand_classes/{track_id}",
        headers=api_helpers.json_headers(user=user),
    )
    data = api_helpers.load_json(res)
    assert len(data["on_demand_classes"]) == 2


def test_get_course_not_logged_in(
    client: FlaskClient, api_helpers: APIInteractionMixin
):
    response = client.get("/api/v1/library/courses/test")
    assert response.status_code == 401


@mock.patch("learn.services.course_service.CourseService")
def test_get_course(
    mock_course_service_constructor,
    client: FlaskClient,
    api_helpers: APIInteractionMixin,
):
    user = EnterpriseUserFactory.create(
        tracks__name="pregnancy", tracks__current_phase="week-5"
    )

    timestamp_1 = parser.parse("2023-03-14T03:14:00")
    timestamp_2 = parser.parse("2023-03-15T03:14:00")

    db.session.add(
        resource_interaction.ResourceInteraction(
            user_id=user.id,
            resource_type=resource_interaction.ResourceType.ARTICLE,
            slug=__COURSE.chapters[0].slug,
            resource_viewed_at=timestamp_1,
            created_at=timestamp_1,
            modified_at=timestamp_1,
        )
    )

    db.session.add(
        resource_interaction.ResourceInteraction(
            user_id=user.id,
            resource_type=resource_interaction.ResourceType.ARTICLE,
            slug=__COURSE.chapters[1].slug,
            resource_viewed_at=timestamp_2,
            created_at=timestamp_2,
            modified_at=timestamp_2,
        )
    )

    mock_course_service_constructor.return_value.get_value.return_value = __COURSE

    response = client.get(
        "/api/v1/library/courses/test", headers=api_helpers.json_headers(user=user)
    )
    assert response.status_code == 200
    response_data = api_helpers.load_json(response)

    course_copy = copy.deepcopy(__COURSE)
    course_copy.chapters[0].viewed_at = timestamp_1
    course_copy.chapters[1].viewed_at = timestamp_2

    assert response_data == course_copy.to_response_dict()


@mock.patch("learn.services.course_service.CourseService")
def test_get_course_no_callout(
    mock_course_service_constructor,
    client: FlaskClient,
    api_helpers: APIInteractionMixin,
):
    user = EnterpriseUserFactory.create(
        tracks__name="pregnancy", tracks__current_phase="week-5"
    )

    course_dict = __COURSE.to_response_dict()
    course_dict["callout"] = None
    course_without_callout = course_factory.from_dict(course_dict)
    mock_course_service_constructor.return_value.get_value.return_value = (
        course_without_callout
    )

    response = client.get(
        "/api/v1/library/courses/test", headers=api_helpers.json_headers(user=user)
    )
    assert response.status_code == 200
    response_data = api_helpers.load_json(response)

    assert response_data == course_without_callout.to_response_dict()


@mock.patch("learn.services.course_service.CourseService")
def test_get_course_not_found(
    mock_course_service_constructor,
    client: FlaskClient,
    api_helpers: APIInteractionMixin,
):
    user = EnterpriseUserFactory.create(
        tracks__name="pregnancy", tracks__current_phase="week-5"
    )

    mock_course_service_constructor.return_value.get_value.return_value = None

    response = client.get(
        "/api/v1/library/courses/test", headers=api_helpers.json_headers(user=user)
    )

    assert response.status_code == 404


@mock.patch("learn.services.course_member_status_service.CourseMemberStatusService")
@mock.patch("learn.services.course_service.CourseService")
def test_get_course_has_member_status(
    mock_course_service_class,
    mock_course_member_status_service_class,
    client,
    api_helpers,
):
    user = EnterpriseUserFactory.create()
    mock_course_service_class.return_value.get_value.return_value = __COURSE
    status_record_mock = mock.Mock(status=MemberStatus.IN_PROGRESS)
    mock_course_member_status_service_class.get.return_value = status_record_mock

    response = client.get(
        "/api/v1/library/courses/test", headers=api_helpers.json_headers(user=user)
    )

    assert response.status_code == 200
    response_data = api_helpers.load_json(response)
    assert response_data["member_status"] == "in_progress"


@mock.patch("learn.services.course_member_status_service.CourseMemberStatusService")
@mock.patch("learn.services.courses_tag_service.CoursesTagService")
def test_get_courses_for_track(
    mock_courses_tag_service_class, mock_course_member_status_service_class
):
    track = MemberTrackFactory.create(name="postpartum")
    course1 = mock.Mock()
    course2 = mock.Mock()
    mock_courses_tag_service_class.return_value.get_courses_for_tag.return_value = [
        course1,
        course2,
    ]
    mock_course_member_status_service_class.set_statuses_on_courses.return_value = [
        course1,
        course2,
    ]

    result = get_courses_for_track(TrackName(track.name), track.user.id, limit=4)

    assert result == [course1, course2]
    mock_courses_tag_service_class.assert_called_with(preview=False, user_facing=True)
    mock_courses_tag_service_class.return_value.get_courses_for_tag.assert_called_with(
        tag="postpartum", limit=4
    )
    mock_course_member_status_service_class.set_statuses_on_courses.assert_called_with(
        courses=[course1, course2], user_id=track.user.id
    )


@mock.patch("learn.services.read_time_service.ReadTimeService")
@mock.patch("views.library.get_courses_for_track")
def test_courses_in_classes_section(get_courses_mock, _, client, api_helpers):
    user = EnterpriseUserFactory.create()
    track = user.active_tracks[0]
    course_copy = copy.deepcopy(__COURSE)
    course_copy.member_status = MemberStatus.NOT_STARTED.value
    get_courses_mock.return_value = [course_copy, course_copy]

    response = client.get(
        f"/api/v1/library/{track.id}", headers=api_helpers.json_headers(user=user)
    )
    response_data = api_helpers.load_json(response)

    expected_dict = {
        "slug": course_copy.slug,
        "title": course_copy.title,
        "image": {
            "url": course_copy.image.url,
            "description": course_copy.image.description,
        },
        "chapters": [
            {
                "slug": course_copy.chapters[0].slug,
                "length_in_minutes": course_copy.chapters[0].length_in_minutes,
            },
            {
                "slug": course_copy.chapters[1].slug,
                "length_in_minutes": course_copy.chapters[1].length_in_minutes,
            },
            {
                "slug": course_copy.chapters[2].slug,
                "length_in_minutes": course_copy.chapters[2].length_in_minutes,
            },
        ],
        "member_status": "not_started",
    }
    assert response_data["classes_section"]["courses"][0] == expected_dict
    assert response_data["classes_section"]["courses"][1] == expected_dict


def test_get_courses_not_logged_in(client):
    response = client.get("/api/v1/library/courses")

    assert response.status_code == 401


@pytest.mark.parametrize(
    "query_string",
    [
        "",
        "?track_name=",
        "?track_name=🛤",
        "?slugs=",
        f"?slugs={','.join([f'slug-{i}' for i in range(105)])}",
        "?track_name=fertility&slugs=1,2,3",
    ],
)
def test_get_courses_bad_query_parameters(client, api_helpers, query_string: str):
    user = EnterpriseUserFactory.create()
    response = client.get(
        f"/api/v1/library/courses{query_string}",
        headers=api_helpers.json_headers(user=user),
    )

    assert response.status_code == 400


@pytest.mark.parametrize("preview", (True, False))
@mock.patch("learn.services.course_member_status_service.CourseMemberStatusService")
@mock.patch("learn.services.courses_tag_service.CoursesTagService")
def test_get_courses_by_track_name(
    mock_courses_tag_service_constructor,
    mock_course_member_status_service_class,
    client,
    api_helpers,
    preview: bool,
):
    user = EnterpriseUserFactory.create()
    timestamp = parser.parse("2023-03-14T03:14:00")
    db.session.add(
        resource_interaction.ResourceInteraction(
            user_id=user.id,
            resource_type=resource_interaction.ResourceType.ARTICLE,
            slug=__COURSE.chapters[0].slug,
            resource_viewed_at=timestamp,
            created_at=timestamp,
            modified_at=timestamp,
        )
    )
    course_1, course_2, course_3 = (copy.deepcopy(__COURSE) for _ in range(3))
    course_1.slug = "ccc"
    course_2.slug = "bbb"
    course_3.slug = "aaa"
    course_1_copy = copy.deepcopy(course_1)
    course_2_copy = copy.deepcopy(course_2)
    course_3_copy = copy.deepcopy(course_3)
    course_1_copy.member_status = MemberStatus.NOT_STARTED
    course_2_copy.member_status = MemberStatus.IN_PROGRESS
    course_3_copy.member_status = MemberStatus.COMPLETED
    mock_courses_tag_service_constructor.return_value.get_courses_for_tag.return_value = [
        course_1,
        course_2,
        course_3,
    ]
    mock_course_member_status_service_class.set_statuses_on_courses.return_value = [
        course_1_copy,
        course_2_copy,
        course_3_copy,
    ]

    response = client.get(
        f"/api/v1/library/courses?track_name={TrackName.FERTILITY}{'&preview=True' if preview else ''}",
        headers=api_helpers.json_headers(user=user),
    )

    for course in [course_1_copy, course_2_copy, course_3_copy]:
        course.chapters[0].viewed_at = timestamp

    assert response.status_code == 200
    data = api_helpers.load_json(response)
    assert data == {
        "courses": [
            course_3_copy.to_response_dict(),
            course_2_copy.to_response_dict(),
            course_1_copy.to_response_dict(),
        ]
    }
    mock_courses_tag_service_constructor.assert_called_once_with(
        preview=preview, user_facing=True
    )
    mock_courses_tag_service_constructor.return_value.get_courses_for_tag.assert_called_once_with(
        tag=TrackName.FERTILITY, limit=None
    )
    mock_course_member_status_service_class.set_statuses_on_courses.assert_called_once_with(
        courses=[course_1, course_2, course_3], user_id=user.id
    )


@pytest.mark.parametrize("preview", (True, False))
@mock.patch("learn.services.course_member_status_service.CourseMemberStatusService")
@mock.patch("learn.services.course_service.CourseService")
def test_get_courses_by_slugs(
    mock_course_service_constructor,
    mock_course_member_status_service_class,
    client,
    api_helpers,
    preview: bool,
):
    user = EnterpriseUserFactory.create()
    timestamp = parser.parse("2023-03-14T03:14:00")
    db.session.add(
        resource_interaction.ResourceInteraction(
            user_id=user.id,
            resource_type=resource_interaction.ResourceType.ARTICLE,
            slug=__COURSE.chapters[0].slug,
            resource_viewed_at=timestamp,
            created_at=timestamp,
            modified_at=timestamp,
        )
    )
    course_1, course_2, course_3 = (copy.deepcopy(__COURSE) for _ in range(3))
    course_1.slug = "ccc"
    course_2.slug = "bbb"
    course_3.slug = "aaa"
    course_1_copy = copy.deepcopy(course_1)
    course_2_copy = copy.deepcopy(course_2)
    course_3_copy = copy.deepcopy(course_3)
    course_1_copy.member_status = MemberStatus.NOT_STARTED
    course_2_copy.member_status = MemberStatus.IN_PROGRESS
    course_3_copy.member_status = MemberStatus.COMPLETED
    mock_course_service_constructor.return_value.get_values.return_value = {
        course_1.slug: course_1,
        course_2.slug: course_2,
        course_3.slug: course_3,
    }
    mock_course_service_constructor.populate_viewed_at = (
        CourseService.populate_viewed_at
    )
    mock_course_member_status_service_class.set_statuses_on_courses.return_value = [
        course_1_copy,
        course_2_copy,
        course_3_copy,
    ]

    response = client.get(
        f"/api/v1/library/courses?slugs={course_1.slug},{course_2.slug},{course_3.slug},{'this-slug-does-not-exist'}{'&preview=True' if preview else ''}",  # noqa E231
        headers=api_helpers.json_headers(user=user),
    )

    for course in [course_1_copy, course_2_copy, course_3_copy]:
        course.chapters[0].viewed_at = timestamp

    assert response.status_code == 200
    data = api_helpers.load_json(response)
    assert data == {
        "courses": [
            course_3_copy.to_response_dict(),
            course_2_copy.to_response_dict(),
            course_1_copy.to_response_dict(),
        ]
    }
    mock_course_service_constructor.assert_called_once_with(preview=preview)
    mock_course_service_constructor.return_value.get_values.assert_called_once_with(
        [course_1.slug, course_2.slug, course_3.slug, "this-slug-does-not-exist"]
    )
    mock_course_member_status_service_class.set_statuses_on_courses.assert_called_once_with(
        courses=[course_1, course_2, course_3], user_id=user.id
    )
