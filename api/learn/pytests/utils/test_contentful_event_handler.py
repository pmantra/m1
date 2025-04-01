import copy
from typing import Any, Dict
from unittest import mock

import pytest

from learn.models import article, article_type, image, media_type
from learn.models.course import (
    Course,
    CourseCallout,
    CourseChapter,
    RelatedCourse,
    RelatedCourseChapter,
)
from learn.models.video import Video
from learn.services import contentful
from learn.utils import contentful_event_handler
from views.models import cta

__ENTITY_ID = "42"
__SLUG = "🐌"


@pytest.fixture
def mock_contentful_preview_client():
    return mock.Mock()


@pytest.fixture
def mock_contentful_delivery_client():
    return mock.Mock()


@pytest.fixture
def mock_article_thumbnail_service():
    return mock.Mock()


@pytest.fixture
def mock_article_service():
    return mock.Mock()


@pytest.fixture
def mock_banner_service():
    return mock.Mock()


@pytest.fixture
def mock_course_service():
    return mock.Mock()


@pytest.fixture
def mock_read_time_service():
    return mock.Mock()


@pytest.fixture
def mock_courses_tag_service():
    return mock.Mock()


@pytest.fixture
def mock_video_service():
    return mock.Mock()


@pytest.fixture
@mock.patch("learn.utils.contentful_event_handler.video_service.VideoService")
@mock.patch(
    "learn.utils.contentful_event_handler.courses_tag_service.CoursesTagService"
)
@mock.patch("learn.utils.contentful_event_handler.read_time_service.ReadTimeService")
@mock.patch("learn.utils.contentful_event_handler.course_service.CourseService")
@mock.patch("learn.utils.contentful_event_handler.banner_service.BannerService")
@mock.patch("learn.utils.contentful_event_handler.article_service.ArticleService")
@mock.patch(
    "learn.utils.contentful_event_handler.article_title_service.LocalizedArticleTitleService"
)
@mock.patch(
    "learn.utils.contentful_event_handler.article_thumbnail_service.ArticleThumbnailService"
)
@mock.patch(
    "learn.utils.contentful_event_handler.contentful_svc.LibraryContentfulClient"
)
def handler(
    mock_contentful_client_constructor,
    mock_article_thumbnail_service_constructor,
    mock_article_title_service_constructor,
    mock_article_service_constructor,
    mock_banner_service_constructor,
    mock_course_service_constructor,
    mock_read_time_service_constructor,
    mock_courses_tag_service_constructor,
    mock_video_service_constructor,
    mock_contentful_preview_client,
    mock_contentful_delivery_client,
    mock_article_thumbnail_service,
    mock_article_service,
    mock_banner_service,
    mock_course_service,
    mock_read_time_service,
    mock_courses_tag_service,
    mock_video_service,
) -> contentful_event_handler.ContentfulEventHandler:
    mock_contentful_client_constructor.side_effect = [
        mock_contentful_preview_client,
        mock_contentful_delivery_client,
    ]
    mock_article_thumbnail_service_constructor.return_value = (
        mock_article_thumbnail_service
    )
    mock_article_title_service_constructor.return_value = mock.Mock()
    mock_article_service_constructor.return_value = mock_article_service
    mock_banner_service_constructor.return_value = mock_banner_service
    mock_course_service_constructor.return_value = mock_course_service
    mock_read_time_service_constructor.return_value = mock_read_time_service
    mock_courses_tag_service_constructor.return_value = mock_courses_tag_service
    mock_video_service_constructor.return_value = mock_video_service
    return contentful_event_handler.ContentfulEventHandler()


@pytest.fixture
def mock_asset():
    mock_asset = mock.Mock()
    mock_asset.url.return_value = "https://example.com"
    return mock_asset


@pytest.fixture
def article_dict() -> Dict[str, Any]:
    return {
        "title": "A B C",
        "medically_reviewed": None,
        "hero_image": {"url": "https://ima.ge/image.img", "description": "desc"},
        "rich_text": {"content": []},
        "related_reads": [],
        "rich_text_includes": [],
    }


@pytest.fixture
def banner_entry_fields(mock_asset) -> Dict[str, Any]:
    return {
        "title": "title",
        "body": "👤",
        "image": mock_asset,
        "cta_text": "📞",
        "cta_url": "https://example.com",
        "secondary_cta_text": "🤙",
        "secondary_cta_url": "https://example.com",
    }


@pytest.fixture
def banner_dict() -> Dict[str, Any]:
    return {
        "title": "title",
        "body": "👤",
        "image": "https://example.com",
        "cta": {
            "text": "📞",
            "url": "https://example.com",
        },
        "secondary_cta": {"text": "🤙", "url": "https://example.com"},
    }


@pytest.fixture()
def mock_course_entry():
    mock_asset = mock.Mock()
    mock_asset.url.return_value = "/image.png"
    mock_asset.fields.return_value = {"description": "description"}

    return mock.Mock(
        id=__ENTITY_ID,
        slug=__SLUG,
        content_type=mock.Mock(id="course"),
        title="title",
        image=mock_asset,
        description="description",
        course_callout=mock.Mock(
            title="title", cta_text="cta text", cta_url="https://example.com"
        ),
        chapters=[
            mock.Mock(
                title="title",
                description="description",
                content=mock.Mock(
                    content_type=mock.Mock(id="article"),
                    slug="article-1",
                    hero_image=mock_asset,
                ),
                slug="chapter-1",
            ),
            mock.Mock(
                title="title",
                description="description",
                content=mock.Mock(
                    content_type=mock.Mock(id="nonContentfulArticle"),
                    slug="article-2",
                    hero_image=mock_asset,
                ),
            ),
        ],
        related=[
            mock.Mock(
                content_type=mock.Mock(id="course"),
                slug="course-2",
                title="title",
                image=mock_asset,
                chapters=[
                    mock.Mock(
                        title="title",
                        description="description",
                        content=mock.Mock(
                            content_type=mock.Mock(id="article"),
                            slug="article-3",
                            hero_image=mock_asset,
                        ),
                    ),
                    mock.Mock(
                        title="title",
                        description="description",
                        content=mock.Mock(
                            content_type=mock.Mock(id="nonContentfulArticle"),
                            slug="article-4",
                            hero_image=mock_asset,
                        ),
                    ),
                ],
            ),
            mock.Mock(content_type=mock.Mock(id="article"), slug="article-1"),
            mock.Mock(
                content_type=mock.Mock(id="nonContentfulArticle"), slug="article-2"
            ),
        ],
    )


@pytest.fixture()
def course_from_contentful() -> Course:
    return get_course_from_contentful(__ENTITY_ID, __SLUG)


def get_course_from_contentful(contentful_id: str, slug: str):
    return Course(
        id=contentful_id,
        slug=slug,
        title="title",
        image=image.Image(url="/image.png", description="description"),
        description="description",
        callout=CourseCallout(
            title="title", cta=cta.CTA(text="cta text", url="https://example.com")
        ),
        chapters=[
            CourseChapter(
                title="title",
                slug="article-1",
                description="description",
                image=image.Image(url="/image.png", description="description"),
            ),
            CourseChapter(
                title="title",
                slug="article-2",
                description="description",
                image=image.Image(url="/image.png", description="description"),
            ),
        ],
        related=[
            RelatedCourse(
                slug="course-2",
                title="title",
                thumbnail=image.Image(url="/image.png", description="description"),
                chapters=[
                    RelatedCourseChapter(
                        slug="article-3",
                    ),
                    RelatedCourseChapter(
                        slug="article-4",
                    ),
                ],
            ),
            article.RelatedRead(
                title="title",
                thumbnail=image.Image(url="/image.png", description="description"),
                slug="article-1",
                type=article_type.ArticleType.RICH_TEXT,
            ),
            article.RelatedRead(
                title="title",
                thumbnail=image.Image(url="/image.png", description="description"),
                slug="article-1",
                type=article_type.ArticleType.HTML,
            ),
        ],
    )


@pytest.fixture
def full_course(course_from_contentful: Course) -> Course:
    full_course = copy.deepcopy(course_from_contentful)
    full_course.chapters[0].length_in_minutes = 1
    full_course.chapters[0].media_type = media_type.MediaType.ARTICLE
    full_course.chapters[1].media_type = media_type.MediaType.VIDEO
    full_course.related[0].chapters[0].length_in_minutes = 1
    full_course.related[0].chapters[0].media_type = media_type.MediaType.ARTICLE
    full_course.related[0].chapters[1].media_type = media_type.MediaType.VIDEO
    return full_course


@pytest.fixture
def estimated_read_times(full_course: Course) -> Dict[str, int]:
    return {
        full_course.chapters[0].slug: full_course.chapters[0].length_in_minutes,
        full_course.chapters[1].slug: -1,
        full_course.related[0]
        .chapters[0]
        .slug: full_course.related[0]
        .chapters[0]
        .length_in_minutes,
        full_course.related[0].chapters[1].slug: -1,
    }


@pytest.fixture
def video() -> Video:
    video = Video(
        title="test",
        slug="test",
        image=image.Image(url="/image.png", description="description"),
        video_url="/video/url",
        captions_url="/video/captions",
        related=[],
    )
    return video


@pytest.fixture
def mock_video_class_with_video(video):
    with mock.patch("learn.utils.contentful_event_handler.Video") as mock_video_class:
        mock_video_class.from_contentful_entry.return_value = video
        yield mock_video_class


def test_handle_event_unpublish_asset_no_references(
    mock_article_thumbnail_service,
    mock_contentful_preview_client,
    mock_asset,
    handler: contentful_event_handler.ContentfulEventHandler,
):
    mock_contentful_preview_client.get_asset_by_id.return_value = mock_asset
    mock_contentful_preview_client.get_entity_references.return_value = []

    handler.handle_event(
        action="unpublish",
        entity_type=contentful.EntityType.ASSET.value,
        content_type="undefined",
        entity_id=__ENTITY_ID,
    )

    mock_contentful_preview_client.get_asset_by_id.assert_called_once_with(__ENTITY_ID)
    mock_article_thumbnail_service.remove_asset_from_cache_by_id.assert_called_once_with(
        __ENTITY_ID
    )
    mock_contentful_preview_client.get_entity_references.assert_called_once_with(
        mock_asset
    )


def test_handle_event_unpublish_asset_unpublished_reference(
    mock_contentful_preview_client,
    mock_contentful_delivery_client,
    mock_article_thumbnail_service,
    mock_asset,
    handler: contentful_event_handler.ContentfulEventHandler,
):
    mock_contentful_preview_client.get_asset_by_id.return_value = mock_asset
    mock_entry = mock.Mock(id="id")
    mock_contentful_preview_client.get_entity_references.return_value = [mock_entry]
    mock_contentful_delivery_client.get_entry_by_id_or_none.return_value = None

    handler.handle_event(
        action="unpublish",
        entity_type=contentful.EntityType.ASSET.value,
        content_type="undefined",
        entity_id=__ENTITY_ID,
    )

    mock_contentful_preview_client.get_asset_by_id.assert_called_once_with(__ENTITY_ID)
    mock_article_thumbnail_service.remove_asset_from_cache_by_id.assert_called_once_with(
        __ENTITY_ID
    )
    mock_contentful_preview_client.get_entity_references.assert_called_once_with(
        mock_asset
    )
    mock_contentful_delivery_client.get_entry_by_id_or_none.asset_called_once_with(
        mock_entry.id
    )


@mock.patch(
    "learn.utils.contentful_event_handler.index_resources.index_article_from_contentful_entry"
)
def test_handle_event_unpublish_asset_article_reference(
    mock_index_article_from_contentful_entry,
    mock_contentful_preview_client,
    mock_contentful_delivery_client,
    mock_article_thumbnail_service,
    mock_article_service,
    mock_asset,
    article_dict,
    handler: contentful_event_handler.ContentfulEventHandler,
):
    mock_contentful_preview_client.get_asset_by_id.return_value = mock_asset
    mock_entry = mock.Mock(
        id="id",
        slug=__SLUG,
        content_type=mock.Mock(id=contentful.ContentfulContentType.ARTICLE),
    )
    mock_contentful_preview_client.get_entity_references.return_value = [mock_entry]
    mock_contentful_delivery_client.get_entry_by_id_or_none.return_value = mock_entry
    mock_article_service.entry_to_article_dict.return_value = article_dict
    mock_contentful_delivery_client.get_entity_references.return_value = []

    handler.handle_event(
        action="unpublish",
        entity_type=contentful.EntityType.ASSET.value,
        content_type="undefined",
        entity_id=__ENTITY_ID,
    )

    mock_contentful_preview_client.get_asset_by_id.assert_called_once_with(__ENTITY_ID)
    mock_article_thumbnail_service.remove_asset_from_cache_by_id.assert_called_once_with(
        __ENTITY_ID
    )
    mock_contentful_preview_client.get_entity_references.assert_called_once_with(
        mock_asset
    )
    mock_contentful_delivery_client.get_entry_by_id_or_none.asset_called_once_with(
        mock_entry.id
    )
    mock_index_article_from_contentful_entry.assert_called_once_with(mock_entry)
    mock_article_service.entry_to_article_dict.assert_called_once_with(mock_entry)
    mock_article_service.save_value_in_cache.assert_called_once_with(
        mock_entry.slug, article_dict
    )
    mock_contentful_delivery_client.get_entity_references.assert_called_once_with(
        mock_entry
    )


def test_handle_event_unpublish_asset_video_reference(
    mock_video_class_with_video,
    video,
    mock_contentful_preview_client,
    mock_contentful_delivery_client,
    mock_article_service,
    mock_video_service,
    mock_asset,
    handler: contentful_event_handler.ContentfulEventHandler,
):
    mock_contentful_preview_client.get_asset_by_id.return_value = mock_asset
    mock_entry = mock.Mock(
        id="id",
        slug=__SLUG,
        content_type=mock.Mock(id=contentful.ContentfulContentType.VIDEO),
    )
    mock_contentful_preview_client.get_entity_references.return_value = [mock_entry]
    mock_contentful_delivery_client.get_entry_by_id_or_none.return_value = mock_entry
    mock_contentful_delivery_client.get_entity_references.return_value = []
    handler.handle_event(
        action="unpublish",
        entity_type=contentful.EntityType.ASSET.value,
        content_type="undefined",
        entity_id=__ENTITY_ID,
    )

    mock_contentful_preview_client.get_asset_by_id.assert_called_once_with(__ENTITY_ID)
    mock_contentful_preview_client.get_entity_references.assert_called_once_with(
        mock_asset
    )
    mock_contentful_delivery_client.get_entry_by_id_or_none.asset_called_once_with(
        mock_entry.id
    )
    mock_video_class_with_video.from_contentful_entry.assert_called_once_with(
        mock_entry
    )
    mock_video_service.save_value_in_cache.assert_called_once_with(
        mock_entry.slug, video
    )
    mock_contentful_delivery_client.get_entity_references.assert_called_once_with(
        mock_entry
    )


def test_handle_event_unpublish_asset_banner_reference(
    mock_contentful_preview_client,
    mock_contentful_delivery_client,
    mock_banner_service,
    mock_article_thumbnail_service,
    mock_asset,
    banner_entry_fields,
    banner_dict,
    handler: contentful_event_handler.ContentfulEventHandler,
):
    mock_asset.url.return_value = "https://example.com"
    mock_contentful_preview_client.get_asset_by_id.return_value = mock_asset
    mock_entry = mock.Mock(
        id="id",
        slug=__SLUG,
        content_type=mock.Mock(id=contentful.ContentfulContentType.BANNER),
    )
    mock_entry.fields.return_value = banner_entry_fields
    mock_contentful_preview_client.get_entity_references.return_value = [mock_entry]
    mock_contentful_delivery_client.get_entry_by_id_or_none.return_value = mock_entry
    mock_banner_service.entry_to_article_dict.return_value = vars(mock_entry)
    mock_contentful_delivery_client.get_entity_references.return_value = []

    handler.handle_event(
        action="unpublish",
        entity_type=contentful.EntityType.ASSET.value,
        content_type="undefined",
        entity_id=__ENTITY_ID,
    )

    mock_contentful_preview_client.get_asset_by_id.assert_called_once_with(__ENTITY_ID)
    mock_article_thumbnail_service.remove_asset_from_cache_by_id.assert_called_once_with(
        __ENTITY_ID
    )
    mock_contentful_preview_client.get_entity_references.assert_called_once_with(
        mock_asset
    )
    mock_contentful_delivery_client.get_entry_by_id_or_none.asset_called_once_with(
        mock_entry.id
    )
    mock_banner_service.save_value_in_cache.assert_called_once_with(
        mock_entry.slug, banner_dict
    )
    mock_contentful_delivery_client.get_entity_references.assert_called_once_with(
        mock_entry
    )


@mock.patch("learn.models.course_factory.ReadTimeService")
@mock.patch("learn.models.related_content_factory.article_service.ArticleService")
def test_handle_event_unpublish_asset_course_reference(
    mock_article_service_constructor,
    mock_read_time_service_constructor_from_course_factory,
    mock_contentful_preview_client,
    mock_contentful_delivery_client,
    mock_article_service,
    mock_course_service,
    mock_article_thumbnail_service,
    mock_read_time_service,
    mock_asset,
    mock_course_entry,
    course_from_contentful,
    full_course,
    estimated_read_times,
    handler: contentful_event_handler.ContentfulEventHandler,
):
    mock_article_service_constructor.return_value = mock_article_service
    mock_read_time_service_constructor_from_course_factory.return_value = (
        mock_read_time_service
    )
    mock_contentful_preview_client.get_asset_by_id.return_value = mock_asset
    mock_contentful_preview_client.get_entity_references.return_value = [
        mock_course_entry
    ]
    mock_contentful_delivery_client.get_entry_by_id_or_none.return_value = (
        mock_course_entry
    )
    mock_article_service.parse_as_related_read.side_effect = [
        full_course.related[1],
        full_course.related[2],
    ]

    mock_read_time_service.calculate_read_time.side_effect = list(
        estimated_read_times.values()
    )
    mock_contentful_delivery_client.get_entity_references.return_value = []

    handler.handle_event(
        action="unpublish",
        entity_type=contentful.EntityType.ASSET.value,
        content_type="undefined",
        entity_id=__ENTITY_ID,
    )

    mock_contentful_preview_client.get_asset_by_id.assert_called_once_with(__ENTITY_ID)
    mock_article_thumbnail_service.remove_asset_from_cache_by_id.assert_called_once_with(
        __ENTITY_ID
    )
    mock_contentful_preview_client.get_entity_references.assert_called_once_with(
        mock_asset
    )
    mock_contentful_delivery_client.get_entry_by_id_or_none.asset_called_once_with(
        mock_course_entry.id
    )
    mock_article_service.parse_as_related_read.assert_has_calls(
        [
            mock.call(mock_course_entry.related[1]),
            mock.call(mock_course_entry.related[2]),
        ]
    )
    mock_course_service.save_value_in_cache.assert_called_once_with(
        mock_course_entry.slug, full_course
    )
    mock_contentful_delivery_client.get_entity_references.assert_called_once_with(
        mock_course_entry
    )
    mock_read_time_service.try_to_save_values_in_cache.assert_called_once_with(
        estimated_read_times
    )


def test_handle_event_unpublish_asset_non_cached_content_type_reference(
    mock_contentful_preview_client,
    mock_contentful_delivery_client,
    mock_article_thumbnail_service,
    mock_asset,
    handler: contentful_event_handler.ContentfulEventHandler,
):
    mock_contentful_preview_client.get_asset_by_id.return_value = mock_asset
    mock_entry = mock.Mock(
        id="id",
        slug=__SLUG,
        content_type=mock.Mock(
            id=contentful.ContentfulContentType.NON_CONTENTFUL_ARTICLE
        ),
    )
    mock_contentful_preview_client.get_entity_references.return_value = [mock_entry]
    mock_contentful_delivery_client.get_entry_by_id_or_none.return_value = mock_entry
    mock_contentful_delivery_client.get_entity_references.return_value = []

    handler.handle_event(
        action="unpublish",
        entity_type=contentful.EntityType.ASSET.value,
        content_type="undefined",
        entity_id=__ENTITY_ID,
    )

    mock_contentful_preview_client.get_asset_by_id.assert_called_once_with(__ENTITY_ID)
    mock_article_thumbnail_service.remove_asset_from_cache_by_id.assert_called_once_with(
        __ENTITY_ID
    )
    mock_contentful_preview_client.get_entity_references.assert_called_once_with(
        mock_asset
    )
    mock_contentful_delivery_client.get_entry_by_id_or_none.asset_called_once_with(
        mock_entry.id
    )
    mock_contentful_delivery_client.get_entity_references.assert_called_once_with(
        mock_entry
    )


@mock.patch(
    "learn.utils.contentful_event_handler.index_resources.index_article_from_contentful_entry"
)
def test_handle_event_unpublish_asset_nested_article_references(
    mock_index_article_from_contentful_entry,
    mock_contentful_preview_client,
    mock_contentful_delivery_client,
    mock_article_thumbnail_service,
    mock_article_service,
    mock_asset,
    article_dict,
    handler: contentful_event_handler.ContentfulEventHandler,
):
    mock_contentful_preview_client.get_asset_by_id.return_value = mock_asset
    mock_entry_1 = mock.Mock(
        id="id-1",
        slug="slug-1",
        content_type=mock.Mock(id=contentful.ContentfulContentType.ARTICLE),
    )
    mock_entry_2 = mock.Mock(
        id="id-2",
        slug="slug-2",
        content_type=mock.Mock(id=contentful.ContentfulContentType.ARTICLE),
    )
    mock_contentful_preview_client.get_entity_references.return_value = [mock_entry_1]
    mock_contentful_delivery_client.get_entry_by_id_or_none.return_value = mock_entry_1
    mock_contentful_delivery_client.get_entity_references.return_value = [mock_entry_2]
    mock_article_service.entry_to_article_dict.side_effect = [
        article_dict,
        article_dict,
    ]

    handler.handle_event(
        action="unpublish",
        entity_type=contentful.EntityType.ASSET.value,
        content_type="undefined",
        entity_id=__ENTITY_ID,
    )

    mock_contentful_preview_client.get_asset_by_id.assert_called_once_with(__ENTITY_ID)
    mock_article_thumbnail_service.remove_asset_from_cache_by_id.assert_called_once_with(
        __ENTITY_ID
    )
    mock_contentful_preview_client.get_entity_references.assert_called_once_with(
        mock_asset
    )
    mock_contentful_delivery_client.get_entry_by_id_or_none.assert_called_once_with(
        mock_entry_1.id
    )
    mock_index_article_from_contentful_entry.assert_has_calls(
        [mock.call(mock_entry_1), mock.call(mock_entry_2)]
    )
    mock_article_service.entry_to_article_dict.assert_has_calls(
        [mock.call(mock_entry_1), mock.call(mock_entry_2)]
    )
    mock_article_service.save_value_in_cache.assert_has_calls(
        [
            mock.call(mock_entry_1.slug, article_dict),
            mock.call(mock_entry_2.slug, article_dict),
        ]
    )
    mock_contentful_delivery_client.get_entity_references.assert_called_once_with(
        mock_entry_1
    )


@mock.patch(
    "learn.utils.contentful_event_handler.index_resources.index_article_from_contentful_entry"
)
def test_handle_event_unpublish_asset_non_cached_content_type_nested_reference(
    mock_index_article_from_contentful_entry,
    mock_contentful_preview_client,
    mock_contentful_delivery_client,
    mock_article_thumbnail_service,
    mock_article_service,
    mock_asset,
    article_dict,
    handler: contentful_event_handler.ContentfulEventHandler,
):
    mock_contentful_preview_client.get_asset_by_id.return_value = mock_asset
    mock_entry_1 = mock.Mock(
        id="id-1",
        slug="slug-1",
        content_type=mock.Mock(
            id=contentful.ContentfulContentType.NON_CONTENTFUL_ARTICLE
        ),
    )
    mock_entry_2 = mock.Mock(
        id="id-2",
        slug="slug-2",
        content_type=mock.Mock(id=contentful.ContentfulContentType.ARTICLE),
    )
    mock_contentful_preview_client.get_entity_references.return_value = [mock_entry_1]
    mock_contentful_delivery_client.get_entry_by_id_or_none.return_value = mock_entry_1
    mock_contentful_delivery_client.get_entity_references.return_value = [mock_entry_2]
    mock_article_service.entry_to_article_dict.return_value = article_dict

    handler.handle_event(
        action="unpublish",
        entity_type=contentful.EntityType.ASSET.value,
        content_type="undefined",
        entity_id=__ENTITY_ID,
    )

    mock_contentful_preview_client.get_asset_by_id.assert_called_once_with(__ENTITY_ID)
    mock_article_thumbnail_service.remove_asset_from_cache_by_id.assert_called_once_with(
        __ENTITY_ID
    )
    mock_contentful_preview_client.get_entity_references.assert_called_once_with(
        mock_asset
    )
    mock_contentful_delivery_client.get_entry_by_id_or_none.assert_called_once_with(
        mock_entry_1.id
    )
    mock_index_article_from_contentful_entry.assert_called_once_with(mock_entry_2)
    mock_article_service.entry_to_article_dict.assert_called_once_with(mock_entry_2)
    mock_article_service.save_value_in_cache.assert_called_once_with(
        mock_entry_2.slug, article_dict
    )
    mock_contentful_delivery_client.get_entity_references.assert_has_calls(
        [mock.call(mock_entry_1), mock.call(mock_entry_2)]
    )


def test_handle_event_publish_asset_no_references(
    mock_article_thumbnail_service,
    mock_contentful_delivery_client,
    mock_asset,
    handler: contentful_event_handler.ContentfulEventHandler,
):
    mock_contentful_delivery_client.get_asset_by_id.return_value = mock_asset
    mock_contentful_delivery_client.get_entity_references.return_value = []

    handler.handle_event(
        action="publish",
        entity_type=contentful.EntityType.ASSET.value,
        content_type="undefined",
        entity_id=__ENTITY_ID,
    )

    mock_contentful_delivery_client.get_asset_by_id.assert_called_once_with(__ENTITY_ID)
    mock_article_thumbnail_service.remove_asset_from_cache_by_id.assert_not_called()
    mock_contentful_delivery_client.get_entity_references.assert_called_once_with(
        mock_asset
    )


def test_handle_event_publish_asset_article_reference_not_thumbnail(
    mock_contentful_delivery_client,
    mock_article_thumbnail_service,
    mock_article_service,
    mock_asset,
    article_dict,
    handler: contentful_event_handler.ContentfulEventHandler,
):
    mock_contentful_delivery_client.get_asset_by_id.return_value = mock_asset
    mock_entry = mock.Mock(
        id="id",
        slug=__SLUG,
        content_type=mock.Mock(id=contentful.ContentfulContentType.ARTICLE),
        hero_image=mock.Mock(id="not-the-one"),
    )
    mock_contentful_delivery_client.get_entity_references.side_effect = [
        [mock_entry],
        [],
    ]
    mock_article_service.entry_to_article_dict.return_value = article_dict

    handler.handle_event(
        action="publish",
        entity_type=contentful.EntityType.ASSET.value,
        content_type="undefined",
        entity_id=__ENTITY_ID,
    )

    mock_contentful_delivery_client.get_asset_by_id.assert_called_once_with(__ENTITY_ID)
    mock_contentful_delivery_client.get_entity_references.assert_has_calls(
        [mock.call(mock_asset), mock.call(mock_entry)]
    )
    mock_article_service.entry_to_article_dict.assert_called_once_with(mock_entry)
    mock_article_service.save_value_in_cache.assert_called_once_with(
        mock_entry.slug, article_dict
    )
    mock_contentful_delivery_client.get_entity_references.assert_has_calls(
        [mock.call(mock_asset), mock.call(mock_entry)]
    )
    mock_article_thumbnail_service.remove_asset_from_cache_by_id.assert_not_called()
    mock_article_thumbnail_service.save_image_to_cache.assert_not_called()


def test_handle_event_publish_asset_article_reference_thumbnail(
    mock_contentful_delivery_client,
    mock_article_thumbnail_service,
    mock_article_service,
    mock_asset,
    article_dict,
    handler: contentful_event_handler.ContentfulEventHandler,
):
    mock_contentful_delivery_client.get_asset_by_id.return_value = mock_asset
    mock_entry = mock.Mock(
        id="id",
        slug=__SLUG,
        content_type=mock.Mock(id=contentful.ContentfulContentType.ARTICLE),
        hero_image=mock.Mock(id=__ENTITY_ID),
    )
    mock_contentful_delivery_client.get_entity_references.side_effect = [
        [mock_entry],
        [],
    ]
    mock_article_service.entry_to_article_dict.return_value = article_dict

    handler.handle_event(
        action="publish",
        entity_type=contentful.EntityType.ASSET.value,
        content_type="undefined",
        entity_id=__ENTITY_ID,
    )

    mock_contentful_delivery_client.get_asset_by_id.assert_called_once_with(__ENTITY_ID)
    mock_contentful_delivery_client.get_entity_references.assert_has_calls(
        [mock.call(mock_asset), mock.call(mock_entry)]
    )
    mock_article_service.entry_to_article_dict.assert_called_once_with(mock_entry)
    mock_article_service.save_value_in_cache.assert_called_once_with(
        mock_entry.slug, article_dict
    )
    mock_contentful_delivery_client.get_entity_references.assert_has_calls(
        [mock.call(mock_asset), mock.call(mock_entry)]
    )
    mock_article_thumbnail_service.save_image_to_cache.assert_called_once_with(
        __SLUG, image.Image.from_contentful_asset(mock_asset)
    )


def test_handle_event_publish_asset_video_reference(
    mock_video_class_with_video,
    video,
    mock_contentful_delivery_client,
    mock_video_service,
    mock_asset,
    handler: contentful_event_handler.ContentfulEventHandler,
):
    mock_contentful_delivery_client.get_asset_by_id.return_value = mock_asset
    mock_entry = mock.Mock(
        id="id",
        slug=__SLUG,
        content_type=mock.Mock(id=contentful.ContentfulContentType.VIDEO),
        image=mock.Mock(id=__ENTITY_ID),
    )
    mock_contentful_delivery_client.get_entity_references.side_effect = [
        [mock_entry],
        [],
    ]

    handler.handle_event(
        action="publish",
        entity_type=contentful.EntityType.ASSET.value,
        content_type="undefined",
        entity_id=__ENTITY_ID,
    )

    mock_contentful_delivery_client.get_asset_by_id.assert_called_once_with(__ENTITY_ID)
    mock_contentful_delivery_client.get_entity_references.assert_has_calls(
        [mock.call(mock_asset), mock.call(mock_entry)]
    )
    mock_video_class_with_video.from_contentful_entry.assert_called_once_with(
        mock_entry
    )
    mock_video_service.save_value_in_cache.assert_called_once_with(
        mock_entry.slug, video
    )
    mock_contentful_delivery_client.get_entity_references.assert_has_calls(
        [mock.call(mock_asset), mock.call(mock_entry)]
    )


def test_handle_event_publish_asset_banner_reference(
    mock_contentful_delivery_client,
    mock_banner_service,
    banner_entry_fields,
    banner_dict,
    mock_asset,
    handler: contentful_event_handler.ContentfulEventHandler,
):
    mock_contentful_delivery_client.get_asset_by_id.return_value = mock_asset
    mock_entry = mock.Mock(
        id="id",
        slug=__SLUG,
        content_type=mock.Mock(id=contentful.ContentfulContentType.BANNER),
    )
    mock_entry.fields.return_value = banner_entry_fields
    mock_contentful_delivery_client.get_entity_references.side_effect = [
        [mock_entry],
        [],
    ]

    handler.handle_event(
        action="publish",
        entity_type=contentful.EntityType.ASSET.value,
        content_type="undefined",
        entity_id=__ENTITY_ID,
    )

    mock_contentful_delivery_client.get_asset_by_id.assert_called_once_with(__ENTITY_ID)
    mock_contentful_delivery_client.get_entity_references.assert_has_calls(
        [mock.call(mock_asset), mock.call(mock_entry)]
    )
    mock_banner_service.save_value_in_cache.assert_called_once_with(
        mock_entry.slug, banner_dict
    )
    mock_contentful_delivery_client.get_entity_references.assert_has_calls(
        [mock.call(mock_asset), mock.call(mock_entry)]
    )


@mock.patch("learn.models.course_factory.ReadTimeService")
@mock.patch("learn.models.related_content_factory.article_service.ArticleService")
def test_handle_event_publish_asset_course_reference(
    mock_article_service_constructor,
    mock_read_time_service_constructor_from_course_factory,
    mock_article_service,
    mock_contentful_delivery_client,
    mock_course_service,
    mock_read_time_service,
    mock_asset,
    mock_course_entry,
    course_from_contentful,
    full_course,
    estimated_read_times,
    handler: contentful_event_handler.ContentfulEventHandler,
):
    mock_article_service_constructor.return_value = mock_article_service
    mock_read_time_service_constructor_from_course_factory.return_value = (
        mock_read_time_service
    )
    mock_contentful_delivery_client.get_asset_by_id.return_value = mock_asset
    mock_article_service.parse_as_related_read.side_effect = [
        full_course.related[1],
        full_course.related[2],
    ]
    mock_read_time_service.calculate_read_time.side_effect = list(
        estimated_read_times.values()
    )
    mock_contentful_delivery_client.get_entity_references.side_effect = [
        [mock_course_entry],
        [],
    ]

    handler.handle_event(
        action="publish",
        entity_type=contentful.EntityType.ASSET.value,
        content_type="undefined",
        entity_id=__ENTITY_ID,
    )

    mock_contentful_delivery_client.get_asset_by_id.assert_called_once_with(__ENTITY_ID)
    mock_contentful_delivery_client.get_entity_references.assert_has_calls(
        [mock.call(mock_asset), mock.call(mock_course_entry)]
    )
    mock_course_service.save_value_in_cache.assert_called_once_with(
        mock_course_entry.slug, full_course
    )
    mock_contentful_delivery_client.get_entity_references.assert_has_calls(
        [mock.call(mock_asset), mock.call(mock_course_entry)]
    )
    mock_read_time_service.try_to_save_values_in_cache.assert_called_once_with(
        estimated_read_times
    )


def test_handle_event_publish_asset_non_cached_content_type_reference(
    mock_contentful_delivery_client,
    mock_asset,
    handler: contentful_event_handler.ContentfulEventHandler,
):
    mock_contentful_delivery_client.get_asset_by_id.return_value = mock_asset
    mock_entry = mock.Mock(
        id="id",
        slug=__SLUG,
        content_type=mock.Mock(
            id=contentful.ContentfulContentType.NON_CONTENTFUL_ARTICLE
        ),
    )
    mock_contentful_delivery_client.get_entity_references.side_effect = [
        [mock_entry],
        [],
    ]

    handler.handle_event(
        action="publish",
        entity_type=contentful.EntityType.ASSET.value,
        content_type="undefined",
        entity_id=__ENTITY_ID,
    )

    mock_contentful_delivery_client.get_asset_by_id.assert_called_once_with(__ENTITY_ID)
    mock_contentful_delivery_client.get_entity_references.assert_has_calls(
        [mock.call(mock_asset), mock.call(mock_entry)]
    )
    mock_contentful_delivery_client.get_entity_references.assert_has_calls(
        [mock.call(mock_asset), mock.call(mock_entry)]
    )


@mock.patch(
    "learn.utils.contentful_event_handler.index_resources.index_article_from_contentful_entry"
)
def test_handle_event_publish_asset_nested_article_reference(
    mock_index_article_from_contentful_entry,
    mock_contentful_delivery_client,
    mock_article_thumbnail_service,
    mock_article_service,
    mock_asset,
    article_dict,
    handler: contentful_event_handler.ContentfulEventHandler,
):
    mock_contentful_delivery_client.get_asset_by_id.return_value = mock_asset
    mock_entry_1 = mock.Mock(
        id="id-1",
        slug="slug-1",
        content_type=mock.Mock(id=contentful.ContentfulContentType.ARTICLE),
    )
    mock_entry_2 = mock.Mock(
        id="id-2",
        slug="slug-2",
        content_type=mock.Mock(id=contentful.ContentfulContentType.ARTICLE),
    )
    mock_contentful_delivery_client.get_entity_references.side_effect = [
        [mock_entry_1],
        [mock_entry_2],
        [],
    ]
    mock_article_service.entry_to_article_dict.side_effect = [
        article_dict,
        article_dict,
    ]

    handler.handle_event(
        action="publish",
        entity_type=contentful.EntityType.ASSET.value,
        content_type="undefined",
        entity_id=__ENTITY_ID,
    )

    mock_contentful_delivery_client.get_asset_by_id.assert_called_once_with(__ENTITY_ID)
    mock_contentful_delivery_client.get_entity_references.assert_has_calls(
        [mock.call(mock_asset), mock.call(mock_entry_1)]
    )
    mock_index_article_from_contentful_entry.assert_has_calls(
        [mock.call(mock_entry_1), mock.call(mock_entry_2)]
    )
    mock_article_service.entry_to_article_dict.assert_has_calls(
        [mock.call(mock_entry_1), mock.call(mock_entry_2)]
    )
    mock_article_service.save_value_in_cache.assert_has_calls(
        [
            mock.call(mock_entry_1.slug, article_dict),
            mock.call(mock_entry_2.slug, article_dict),
        ]
    )


@mock.patch(
    "learn.utils.contentful_event_handler.index_resources.index_article_from_contentful_entry"
)
def test_handle_event_publish_asset_non_cached_content_type_nested_reference(
    mock_index_article_from_contentful_entry,
    mock_contentful_delivery_client,
    mock_article_thumbnail_service,
    mock_article_service,
    mock_asset,
    article_dict,
    handler: contentful_event_handler.ContentfulEventHandler,
):
    mock_contentful_delivery_client.get_asset_by_id.return_value = mock_asset
    mock_entry_1 = mock.Mock(
        id="id-1",
        slug="slug-1",
        content_type=mock.Mock(
            id=contentful.ContentfulContentType.NON_CONTENTFUL_ARTICLE
        ),
    )
    mock_entry_2 = mock.Mock(
        id="id-2",
        slug="slug-2",
        content_type=mock.Mock(id=contentful.ContentfulContentType.ARTICLE),
    )
    mock_contentful_delivery_client.get_entity_references.side_effect = [
        [mock_entry_1],
        [mock_entry_2],
        [],
    ]
    mock_article_service.entry_to_article_dict.return_value = article_dict

    handler.handle_event(
        action="publish",
        entity_type=contentful.EntityType.ASSET.value,
        content_type="undefined",
        entity_id=__ENTITY_ID,
    )

    mock_contentful_delivery_client.get_asset_by_id.assert_called_once_with(__ENTITY_ID)
    mock_contentful_delivery_client.get_entity_references.assert_has_calls(
        [mock.call(mock_asset), mock.call(mock_entry_1), mock.call(mock_entry_2)]
    )
    mock_index_article_from_contentful_entry.assert_called_once_with(mock_entry_2)
    mock_article_service.entry_to_article_dict.assert_called_once_with(mock_entry_2)
    mock_article_service.save_value_in_cache.assert_called_once_with(
        mock_entry_2.slug, article_dict
    )
    mock_contentful_delivery_client.get_entity_references.assert_has_calls(
        [mock.call(mock_entry_1), mock.call(mock_entry_2)]
    )


def test_handle_event_delete_asset(
    mock_contentful_delivery_client,
    mock_contentful_preview_client,
    handler: contentful_event_handler.ContentfulEventHandler,
):
    handler.handle_event(
        action="delete",
        entity_type=contentful.EntityType.ASSET.value,
        content_type="undefined",
        entity_id=__ENTITY_ID,
    )

    mock_contentful_delivery_client.get_asset_by_id.assert_not_called()
    mock_contentful_preview_client.get_asset_by_id.assert_not_called()


@mock.patch(
    "learn.utils.contentful_event_handler.index_resources.remove_contentful_article_from_index"
)
def test_handle_event_unpublish_entry_article(
    mock_remove_contentful_article_from_index,
    mock_article_thumbnail_service,
    mock_read_time_service,
    mock_article_service,
    mock_contentful_preview_client,
    handler: contentful_event_handler.ContentfulEventHandler,
):
    mock_entry = mock.Mock(
        id=__ENTITY_ID,
        slug=__SLUG,
        content_type=mock.Mock(id=contentful.ContentfulContentType.ARTICLE),
    )
    mock_contentful_preview_client.get_entry_by_id.return_value = mock_entry
    mock_contentful_preview_client.get_entity_references.return_value = []

    handler.handle_event(
        action="unpublish",
        entity_type=contentful.EntityType.DELETED_ENTRY.value,
        content_type=contentful.ContentfulContentType.ARTICLE.value,
        entity_id=__ENTITY_ID,
    )

    mock_contentful_preview_client.get_entry_by_id.assert_called_once_with(__ENTITY_ID)
    mock_article_thumbnail_service.remove_article_from_cache_by_id.assert_called_once_with(
        __ENTITY_ID
    )
    mock_read_time_service.remove_value_from_cache.assert_called_once_with(__ENTITY_ID)
    mock_remove_contentful_article_from_index.assert_called_once_with(mock_entry)
    mock_article_service.remove_value_from_cache.assert_called_once_with(__ENTITY_ID)
    mock_contentful_preview_client.get_entity_references.assert_called_once_with(
        mock_entry
    )


def test_handle_event_unpublish_entry_video(
    mock_video_service,
    mock_contentful_preview_client,
    handler: contentful_event_handler.ContentfulEventHandler,
):
    mock_entry = mock.Mock(
        id=__ENTITY_ID,
        slug=__SLUG,
        content_type=mock.Mock(id=contentful.ContentfulContentType.VIDEO),
    )
    mock_contentful_preview_client.get_entry_by_id.return_value = mock_entry
    mock_contentful_preview_client.get_entity_references.return_value = []

    handler.handle_event(
        action="unpublish",
        entity_type=contentful.EntityType.DELETED_ENTRY.value,
        content_type=contentful.ContentfulContentType.VIDEO.value,
        entity_id=__ENTITY_ID,
    )

    mock_contentful_preview_client.get_entry_by_id.assert_called_once_with(__ENTITY_ID)
    mock_video_service.remove_value_from_cache.assert_called_once_with(__ENTITY_ID)


def test_handle_event_unpublish_entry_banner(
    mock_banner_service,
    mock_contentful_preview_client,
    banner_entry_fields,
    handler: contentful_event_handler.ContentfulEventHandler,
):
    mock_entry = mock.Mock(
        id=__ENTITY_ID,
        slug=__SLUG,
        content_type=mock.Mock(id=contentful.ContentfulContentType.BANNER),
    )
    mock_entry.fields.return_value = banner_entry_fields
    mock_contentful_preview_client.get_entry_by_id.return_value = mock_entry
    mock_contentful_preview_client.get_entity_references.return_value = []

    handler.handle_event(
        action="unpublish",
        entity_type=contentful.EntityType.DELETED_ENTRY.value,
        content_type=contentful.ContentfulContentType.BANNER.value,
        entity_id=__ENTITY_ID,
    )

    mock_contentful_preview_client.get_entry_by_id.assert_called_once_with(__ENTITY_ID)
    mock_banner_service.remove_value_from_cache.assert_called_once_with(__ENTITY_ID)
    mock_contentful_preview_client.get_entity_references.assert_called_once_with(
        mock_entry
    )


def test_handle_event_unpublish_entry_course(
    mock_course_service,
    mock_courses_tag_service,
    mock_contentful_preview_client,
    mock_course_entry,
    handler: contentful_event_handler.ContentfulEventHandler,
):
    mock_contentful_preview_client.get_entry_by_id.return_value = mock_course_entry
    mock_contentful_preview_client.get_entity_references.return_value = []

    handler.handle_event(
        action="unpublish",
        entity_type=contentful.EntityType.DELETED_ENTRY.value,
        content_type=contentful.ContentfulContentType.COURSE.value,
        entity_id=__ENTITY_ID,
    )

    mock_contentful_preview_client.get_entry_by_id.assert_called_once_with(__ENTITY_ID)
    mock_course_service.remove_value_from_cache.assert_called_once_with(__ENTITY_ID)
    mock_contentful_preview_client.get_entity_references.assert_called_once_with(
        mock_course_entry
    )
    mock_courses_tag_service.clear_cache.assert_called_once_with()


@mock.patch(
    "learn.utils.contentful_event_handler.index_resources.remove_contentful_article_from_index"
)
def test_handle_event_unpublish_entry_unpublished_reference(
    mock_remove_contentful_article_from_index,
    mock_article_thumbnail_service,
    mock_read_time_service,
    mock_article_service,
    mock_contentful_preview_client,
    mock_contentful_delivery_client,
    handler: contentful_event_handler.ContentfulEventHandler,
):
    mock_entry = mock.Mock(
        id=__ENTITY_ID,
        slug=__SLUG,
        content_type=mock.Mock(id=contentful.ContentfulContentType.ARTICLE),
    )
    mock_reference = mock.Mock(id="id")
    mock_contentful_preview_client.get_entry_by_id.return_value = mock_entry
    mock_contentful_preview_client.get_entity_references.return_value = [mock_reference]
    mock_contentful_delivery_client.get_entry_by_id_or_none.return_value = None

    handler.handle_event(
        action="unpublish",
        entity_type=contentful.EntityType.DELETED_ENTRY.value,
        content_type=contentful.ContentfulContentType.ARTICLE.value,
        entity_id=__ENTITY_ID,
    )

    mock_contentful_preview_client.get_entry_by_id.assert_called_once_with(__ENTITY_ID)
    mock_article_thumbnail_service.remove_article_from_cache_by_id.assert_called_once_with(
        __ENTITY_ID
    )
    mock_read_time_service.remove_value_from_cache.assert_called_once_with(__ENTITY_ID)
    mock_remove_contentful_article_from_index.assert_called_once_with(mock_entry)
    mock_article_service.remove_value_from_cache.assert_called_once_with(__ENTITY_ID)
    mock_contentful_preview_client.get_entity_references.assert_called_once_with(
        mock_entry
    )
    mock_contentful_delivery_client.get_entry_by_id_or_none.assert_called_once_with(
        mock_reference.id
    )


def test_handle_event_unpublish_entry_non_cached_type(
    mock_contentful_preview_client,
    handler: contentful_event_handler.ContentfulEventHandler,
):
    mock_entry = mock.Mock(
        id=__ENTITY_ID,
        slug=__SLUG,
        content_type=mock.Mock(
            id=contentful.ContentfulContentType.NON_CONTENTFUL_ARTICLE
        ),
    )
    mock_contentful_preview_client.get_entry_by_id.return_value = mock_entry
    mock_contentful_preview_client.get_entity_references.return_value = []

    handler.handle_event(
        action="unpublish",
        entity_type=contentful.EntityType.DELETED_ENTRY.value,
        content_type=contentful.ContentfulContentType.NON_CONTENTFUL_ARTICLE.value,
        entity_id=__ENTITY_ID,
    )

    mock_contentful_preview_client.get_entry_by_id.assert_called_once_with(__ENTITY_ID)
    mock_contentful_preview_client.get_entity_references.assert_called_once_with(
        mock_entry
    )


@mock.patch(
    "learn.utils.contentful_event_handler.index_resources.remove_contentful_article_from_index"
)
def test_handle_event_unpublish_entry_nested_references(
    mock_remove_contentful_article_from_index,
    mock_article_thumbnail_service,
    mock_read_time_service,
    mock_article_service,
    mock_contentful_preview_client,
    mock_contentful_delivery_client,
    mock_asset,
    article_dict,
    handler: contentful_event_handler.ContentfulEventHandler,
):
    mock_entry_1 = mock.Mock(
        id="1",
        slug="1",
        content_type=mock.Mock(id=contentful.ContentfulContentType.ARTICLE),
        hero_image=mock_asset,
    )
    mock_entry_2 = mock.Mock(
        id="2",
        slug="2",
        content_type=mock.Mock(id=contentful.ContentfulContentType.ACCORDION),
    )
    mock_entry_3 = mock.Mock(
        id="3",
        slug="3",
        content_type=mock.Mock(id=contentful.ContentfulContentType.ACCORDION_ITEM),
    )
    mock_contentful_preview_client.get_entry_by_id.return_value = mock_entry_1
    mock_contentful_preview_client.get_entity_references.return_value = [mock_entry_2]
    mock_contentful_delivery_client.get_entry_by_id_or_none.return_value = mock_entry_2
    mock_contentful_delivery_client.get_entity_references.side_effect = [
        [mock_entry_3],
        [],
    ]
    mock_article_service.entry_to_article_dict.return_value = article_dict

    handler.handle_event(
        action="unpublish",
        entity_type=contentful.EntityType.DELETED_ENTRY.value,
        content_type=contentful.ContentfulContentType.ARTICLE.value,
        entity_id=mock_entry_1.id,
    )

    mock_contentful_preview_client.get_entry_by_id.assert_called_once_with(
        mock_entry_1.id
    )
    mock_contentful_preview_client.get_entity_references.assert_called_once_with(
        mock_entry_1
    )
    mock_article_thumbnail_service.remove_article_from_cache_by_id.assert_called_once_with(
        mock_entry_1.id
    )
    mock_read_time_service.remove_value_from_cache.assert_called_once_with(
        mock_entry_1.id
    )
    mock_remove_contentful_article_from_index.assert_called_once_with(mock_entry_1)
    mock_article_service.remove_value_from_cache.assert_called_once_with(
        mock_entry_1.id
    )
    mock_contentful_delivery_client.get_entry_by_id_or_none.assert_called_once_with(
        mock_entry_2.id
    )
    mock_contentful_delivery_client.get_entity_references.assert_has_calls(
        [mock.call(mock_entry_2), mock.call(mock_entry_3)]
    )


def test_handle_event_unpublish_entry_circular_reference(
    mock_contentful_preview_client,
    mock_contentful_delivery_client,
    handler: contentful_event_handler.ContentfulEventHandler,
):
    mock_entry_1 = mock.Mock(
        id="1",
        slug="1",
        content_type=mock.Mock(id=contentful.ContentfulContentType.ACCORDION),
    )
    mock_entry_2 = mock.Mock(
        id="2",
        slug="2",
        content_type=mock.Mock(id=contentful.ContentfulContentType.ACCORDION_ITEM),
    )
    mock_contentful_preview_client.get_entry_by_id.return_value = mock_entry_1
    mock_contentful_preview_client.get_entity_references.return_value = [mock_entry_2]
    mock_contentful_delivery_client.get_entry_by_id_or_none.return_value = mock_entry_2
    # this is not technically possible with our current Contentful models, but useful to test nonetheless
    mock_contentful_delivery_client.get_entity_references.return_value = [mock_entry_1]

    handler.handle_event(
        action="unpublish",
        entity_type=contentful.EntityType.DELETED_ENTRY.value,
        content_type=contentful.ContentfulContentType.ARTICLE.value,
        entity_id=mock_entry_1.id,
    )

    mock_contentful_preview_client.get_entry_by_id.assert_called_once_with(
        mock_entry_1.id
    )
    mock_contentful_preview_client.get_entity_references.assert_called_once_with(
        mock_entry_1
    )
    mock_contentful_delivery_client.get_entry_by_id_or_none.assert_called_once_with(
        mock_entry_2.id
    )
    mock_contentful_delivery_client.get_entity_references.assert_called_once_with(
        mock_entry_2
    )


@mock.patch(
    "learn.utils.contentful_event_handler.index_resources.remove_contentful_article_from_index"
)
def test_handle_event_unpublish_entry_self_reference(
    mock_remove_contentful_article_from_index,
    mock_article_thumbnail_service,
    mock_read_time_service,
    mock_article_service,
    mock_contentful_preview_client,
    mock_contentful_delivery_client,
    article_dict,
    handler: contentful_event_handler.ContentfulEventHandler,
):
    mock_entry = mock.Mock(
        id=__ENTITY_ID,
        slug=__SLUG,
        content_type=mock.Mock(id=contentful.ContentfulContentType.ARTICLE),
    )
    mock_contentful_preview_client.get_entry_by_id.return_value = mock_entry
    mock_contentful_preview_client.get_entity_references.return_value = [mock_entry]

    handler.handle_event(
        action="unpublish",
        entity_type=contentful.EntityType.DELETED_ENTRY.value,
        content_type=contentful.ContentfulContentType.ARTICLE.value,
        entity_id=__ENTITY_ID,
    )

    mock_contentful_preview_client.get_entry_by_id.assert_called_once_with(__ENTITY_ID)
    mock_contentful_preview_client.get_entity_references.assert_called_once_with(
        mock_entry
    )
    mock_article_thumbnail_service.remove_article_from_cache_by_id.assert_called_once_with(
        __ENTITY_ID
    )
    mock_read_time_service.remove_value_from_cache.assert_called_once_with(__ENTITY_ID)
    mock_remove_contentful_article_from_index.assert_called_once_with(mock_entry)
    mock_article_service.remove_value_from_cache.assert_called_once_with(__ENTITY_ID)


@mock.patch(
    "learn.utils.contentful_event_handler.index_resources.index_article_from_contentful_entry"
)
def test_handle_event_publish_entry_article(
    mock_index_article_from_contentful_entry,
    mock_read_time_service,
    mock_article_service,
    mock_contentful_delivery_client,
    article_dict,
    handler: contentful_event_handler.ContentfulEventHandler,
):
    mock_entry = mock.Mock(
        id=__ENTITY_ID,
        slug=__SLUG,
        content_type=mock.Mock(id=contentful.ContentfulContentType.ARTICLE),
    )
    mock_contentful_delivery_client.get_entry_by_id.return_value = mock_entry
    mock_contentful_delivery_client.get_entity_references.return_value = []
    mock_article_service.entry_to_article_dict.return_value = article_dict
    mock_read_time_service.calculate_read_time.return_value = 420

    handler.handle_event(
        action="publish",
        entity_type=contentful.EntityType.ENTRY.value,
        content_type=contentful.ContentfulContentType.ARTICLE.value,
        entity_id=__ENTITY_ID,
    )

    mock_contentful_delivery_client.get_entry_by_id.assert_called_once_with(__ENTITY_ID)
    mock_article_service.entry_to_article_dict.assert_called_once_with(mock_entry)
    mock_article_service.save_value_in_cache.assert_called_once_with(
        __SLUG, article_dict
    )
    mock_index_article_from_contentful_entry.assert_called_once_with(mock_entry)
    mock_read_time_service.calculate_read_time.assert_called_once_with(mock_entry)
    mock_read_time_service.save_value_in_cache.assert_called_once_with(__SLUG, 420)
    mock_contentful_delivery_client.get_entity_references.assert_called_once_with(
        mock_entry
    )


def test_handle_event_publish_entry_banner(
    mock_banner_service,
    mock_contentful_delivery_client,
    banner_entry_fields,
    banner_dict,
    handler: contentful_event_handler.ContentfulEventHandler,
):
    mock_entry = mock.Mock(
        id=__ENTITY_ID,
        slug=__SLUG,
        content_type=mock.Mock(id=contentful.ContentfulContentType.BANNER),
    )
    mock_entry.fields.return_value = banner_entry_fields
    mock_contentful_delivery_client.get_entry_by_id.return_value = mock_entry
    mock_contentful_delivery_client.get_entity_references.return_value = []

    handler.handle_event(
        action="publish",
        entity_type=contentful.EntityType.ENTRY.value,
        content_type=contentful.ContentfulContentType.ARTICLE.value,
        entity_id=__ENTITY_ID,
    )

    mock_contentful_delivery_client.get_entry_by_id.assert_called_once_with(__ENTITY_ID)
    mock_banner_service.save_value_in_cache.assert_called_once_with(__SLUG, banner_dict)
    mock_contentful_delivery_client.get_entity_references.assert_called_once_with(
        mock_entry
    )


@mock.patch("learn.models.course_factory.ReadTimeService")
@mock.patch("learn.models.related_content_factory.article_service.ArticleService")
def test_handle_event_publish_entry_course(
    mock_article_service_constructor,
    mock_read_time_service_constructor_from_course_factory,
    mock_article_service,
    mock_course_service,
    mock_courses_tag_service,
    mock_read_time_service,
    mock_contentful_delivery_client,
    mock_course_entry,
    course_from_contentful,
    full_course,
    estimated_read_times,
    handler: contentful_event_handler.ContentfulEventHandler,
):
    mock_article_service_constructor.return_value = mock_article_service
    mock_read_time_service_constructor_from_course_factory.return_value = (
        mock_read_time_service
    )
    mock_article_service.parse_as_related_read.side_effect = [
        full_course.related[1],
        full_course.related[2],
    ]
    mock_read_time_service.calculate_read_time.side_effect = list(
        estimated_read_times.values()
    )
    mock_contentful_delivery_client.get_entry_by_id.return_value = mock_course_entry
    mock_contentful_delivery_client.get_entity_references.return_value = []

    handler.handle_event(
        action="publish",
        entity_type=contentful.EntityType.ENTRY.value,
        content_type=contentful.ContentfulContentType.COURSE.value,
        entity_id=__ENTITY_ID,
    )

    mock_contentful_delivery_client.get_entry_by_id.assert_called_once_with(__ENTITY_ID)
    mock_read_time_service.try_to_save_values_in_cache.assert_called_once_with(
        estimated_read_times
    )
    mock_course_service.save_value_in_cache.assert_called_once_with(
        mock_course_entry.slug, full_course
    )
    mock_contentful_delivery_client.get_entity_references.assert_called_once_with(
        mock_course_entry
    )
    mock_courses_tag_service.clear_cache.assert_called_once_with()


def test_handle_event_publish_entry_video(
    mock_video_service,
    mock_contentful_delivery_client,
    mock_video_class_with_video,
    video,
    handler: contentful_event_handler.ContentfulEventHandler,
):
    mock_entry = mock.Mock(
        id=__ENTITY_ID,
        slug=__SLUG,
        content_type=mock.Mock(id=contentful.ContentfulContentType.VIDEO),
    )
    mock_contentful_delivery_client.get_entry_by_id.return_value = mock_entry
    mock_contentful_delivery_client.get_entity_references.return_value = []

    handler.handle_event(
        action="publish",
        entity_type=contentful.EntityType.ENTRY.value,
        content_type=contentful.ContentfulContentType.VIDEO.value,
        entity_id=__ENTITY_ID,
    )

    mock_contentful_delivery_client.get_entry_by_id.assert_called_once_with(__ENTITY_ID)
    mock_video_service.save_value_in_cache.assert_called_once_with(__SLUG, video)
    mock_contentful_delivery_client.get_entity_references.assert_called_once_with(
        mock_entry
    )


@mock.patch(
    "learn.utils.contentful_event_handler.index_resources.index_article_from_contentful_entry"
)
def test_handle_event_publish_entry_nested_article_reference(
    mock_index_article_from_contentful_entry,
    mock_read_time_service,
    mock_article_service,
    mock_contentful_delivery_client,
    article_dict,
    handler: contentful_event_handler.ContentfulEventHandler,
):
    mock_entry_1 = mock.Mock(
        id="1",
        slug="1",
        content_type=mock.Mock(id=contentful.ContentfulContentType.ARTICLE),
    )
    mock_entry_2 = mock.Mock(
        id="2",
        slug="2",
        content_type=mock.Mock(id=contentful.ContentfulContentType.ARTICLE),
    )
    mock_contentful_delivery_client.get_entry_by_id.return_value = mock_entry_1
    mock_contentful_delivery_client.get_entity_references.return_value = [mock_entry_2]

    mock_article_service.entry_to_article_dict.return_value = article_dict
    mock_read_time_service.calculate_read_time.side_effect = [1, 2]

    handler.handle_event(
        action="publish",
        entity_type=contentful.EntityType.ENTRY.value,
        content_type=contentful.ContentfulContentType.ARTICLE.value,
        entity_id=mock_entry_1.id,
    )

    mock_contentful_delivery_client.get_entry_by_id.assert_called_once_with(
        mock_entry_1.id
    )
    mock_article_service.entry_to_article_dict.assert_has_calls(
        [mock.call(mock_entry_1), mock.call(mock_entry_2)]
    )
    mock_article_service.save_value_in_cache.assert_has_calls(
        [
            mock.call(mock_entry_1.slug, article_dict),
            mock.call(mock_entry_2.slug, article_dict),
        ]
    )
    mock_index_article_from_contentful_entry.assert_has_calls(
        [mock.call(mock_entry_1), mock.call(mock_entry_2)]
    )
    mock_read_time_service.calculate_read_time.assert_has_calls(
        [mock.call(mock_entry_1), mock.call(mock_entry_2)]
    )
    mock_read_time_service.save_value_in_cache.assert_has_calls(
        [mock.call(mock_entry_1.slug, 1), mock.call(mock_entry_2.slug, 2)]
    )
    mock_contentful_delivery_client.get_entity_references.assert_called_once_with(
        mock_entry_1
    )


@mock.patch("learn.models.course_factory.ReadTimeService")
@mock.patch(
    "learn.utils.contentful_event_handler.index_resources.index_article_from_contentful_entry"
)
@mock.patch("learn.models.related_content_factory.article_service.ArticleService")
def test_handle_event_publish_entry_nested_course_to_article_reference(
    mock_article_service_constructor,
    mock_index_article_from_contentful_entry,
    mock_read_time_service_constructor_from_course_factory,
    mock_read_time_service,
    mock_article_service,
    mock_course_service,
    mock_courses_tag_service,
    mock_contentful_delivery_client,
    article_dict,
    mock_course_entry,
    course_from_contentful,
    full_course,
    estimated_read_times,
    handler: contentful_event_handler.ContentfulEventHandler,
):
    mock_article_service_constructor.return_value = mock_article_service
    mock_read_time_service_constructor_from_course_factory.return_value = (
        mock_read_time_service
    )
    mock_article_entry = mock.Mock(
        id="1",
        slug="1",
        content_type=mock.Mock(id=contentful.ContentfulContentType.ARTICLE),
    )
    mock_article_service.parse_as_related_read.side_effect = [
        full_course.related[1],
        full_course.related[2],
    ]
    mock_read_time_service.calculate_read_time.side_effect = [
        1,
        *estimated_read_times.values(),
    ]
    mock_contentful_delivery_client.get_entry_by_id.return_value = mock_article_entry
    mock_contentful_delivery_client.get_entity_references.return_value = [
        mock_course_entry
    ]

    mock_article_service.entry_to_article_dict.return_value = article_dict

    handler.handle_event(
        action="publish",
        entity_type=contentful.EntityType.ENTRY.value,
        content_type=contentful.ContentfulContentType.ARTICLE.value,
        entity_id=mock_article_entry.id,
    )

    mock_contentful_delivery_client.get_entry_by_id.assert_called_once_with(
        mock_article_entry.id
    )
    mock_article_service.entry_to_article_dict.assert_called_once_with(
        mock_article_entry
    )
    mock_article_service.save_value_in_cache.assert_called_once_with(
        mock_article_entry.slug, article_dict
    )
    mock_index_article_from_contentful_entry.assert_called_once_with(mock_article_entry)
    mock_read_time_service.calculate_read_time.assert_has_calls(
        [
            mock.call(article_entry)
            for article_entry in [
                mock_article_entry,
                *[
                    chapter.content
                    for chapter in [
                        *mock_course_entry.chapters,
                        *mock_course_entry.related[0].chapters,
                    ]
                ],
            ]
        ]
    )
    mock_read_time_service.save_value_in_cache.assert_called_once_with(
        mock_article_entry.slug, 1
    )
    mock_contentful_delivery_client.get_entity_references.assert_called_once_with(
        mock_article_entry
    )
    mock_read_time_service.try_to_save_values_in_cache.assert_called_once_with(
        estimated_read_times
    )
    mock_course_service.save_value_in_cache.assert_called_once_with(
        mock_course_entry.slug, full_course
    )
    mock_courses_tag_service.clear_cache.assert_not_called()


@mock.patch("learn.models.course_factory.ReadTimeService")
@mock.patch("learn.models.related_content_factory.article_service.ArticleService")
def test_handle_event_publish_entry_nested_course_reference(
    mock_article_service_constructor,
    mock_read_time_service_constructor_from_course_factory,
    mock_article_service,
    mock_course_service,
    mock_read_time_service,
    mock_contentful_delivery_client,
    article_dict,
    mock_course_entry,
    full_course,
    estimated_read_times,
    handler: contentful_event_handler.ContentfulEventHandler,
):
    mock_article_service_constructor.return_value = mock_article_service
    mock_read_time_service_constructor_from_course_factory.return_value = (
        mock_read_time_service
    )
    full_course_1 = copy.deepcopy(full_course)
    full_course_1.slug = "slug-1"
    full_course_1.id = "1"
    full_course_2 = copy.deepcopy(full_course)
    full_course_2.slug = "slug-2"
    full_course_2.id = "2"
    mock_course_entry_1 = copy.deepcopy(mock_course_entry)
    mock_course_entry_1.slug = "slug-1"
    mock_course_entry_1.id = "1"
    mock_course_entry_2 = copy.deepcopy(mock_course_entry)
    mock_course_entry_2.slug = "slug-2"
    mock_course_entry_2.id = "2"
    mock_article_service.parse_as_related_read.side_effect = [
        full_course.related[1],
        full_course.related[2],
        full_course.related[1],
        full_course.related[2],
    ]
    mock_read_time_service.calculate_read_time.side_effect = [
        *estimated_read_times.values(),
        *estimated_read_times.values(),
    ]
    mock_contentful_delivery_client.get_entry_by_id.return_value = mock_course_entry_1
    mock_contentful_delivery_client.get_entity_references.return_value = [
        mock_course_entry_2
    ]

    handler.handle_event(
        action="publish",
        entity_type=contentful.EntityType.ENTRY.value,
        content_type=contentful.ContentfulContentType.ARTICLE.value,
        entity_id=mock_course_entry_1.id,
    )

    mock_contentful_delivery_client.get_entry_by_id.assert_called_once_with(
        mock_course_entry_1.id
    )
    mock_contentful_delivery_client.get_entity_references.assert_called_once_with(
        mock_course_entry_1
    )
    mock_read_time_service.try_to_save_values_in_cache.assert_has_calls(
        [mock.call(estimated_read_times), mock.call(estimated_read_times)]
    )
    mock_course_service.save_value_in_cache.assert_has_calls(
        [
            mock.call(mock_course_entry_1.slug, full_course_1),
            mock.call(mock_course_entry_2.slug, full_course_2),
        ]
    )


def test_handle_event_publish_entry_circular_reference(
    mock_contentful_delivery_client,
    article_dict,
    handler: contentful_event_handler.ContentfulEventHandler,
):
    mock_entry_1 = mock.Mock(
        id="1",
        slug="1",
        content_type=mock.Mock(id=contentful.ContentfulContentType.ACCORDION),
    )
    mock_entry_2 = mock.Mock(
        id="2",
        slug="2",
        content_type=mock.Mock(id=contentful.ContentfulContentType.ACCORDION_ITEM),
    )
    mock_contentful_delivery_client.get_entry_by_id.return_value = mock_entry_1
    mock_contentful_delivery_client.get_entity_references.side_effect = [
        [mock_entry_2],
        [mock_entry_1],
    ]

    handler.handle_event(
        action="publish",
        entity_type=contentful.EntityType.ENTRY.value,
        content_type=contentful.ContentfulContentType.ARTICLE.value,
        entity_id=mock_entry_1.id,
    )

    mock_contentful_delivery_client.get_entry_by_id.assert_called_once_with(
        mock_entry_1.id
    )
    mock_contentful_delivery_client.get_entity_references.assert_has_calls(
        [mock.call(mock_entry_1), mock.call(mock_entry_2)]
    )


@mock.patch(
    "learn.utils.contentful_event_handler.index_resources.index_article_from_contentful_entry"
)
def test_handle_event_publish_entry_self_reference(
    mock_index_article_from_contentful_entry,
    mock_read_time_service,
    mock_article_service,
    mock_contentful_delivery_client,
    article_dict,
    handler: contentful_event_handler.ContentfulEventHandler,
):
    mock_entry = mock.Mock(
        id=__ENTITY_ID,
        slug=__SLUG,
        content_type=mock.Mock(id=contentful.ContentfulContentType.ARTICLE),
    )
    mock_contentful_delivery_client.get_entry_by_id.return_value = mock_entry
    mock_contentful_delivery_client.get_entity_references.return_value = [mock_entry]
    mock_article_service.entry_to_article_dict.return_value = article_dict
    mock_read_time_service.calculate_read_time.return_value = 420

    handler.handle_event(
        action="publish",
        entity_type=contentful.EntityType.ENTRY.value,
        content_type=contentful.ContentfulContentType.ARTICLE.value,
        entity_id=__ENTITY_ID,
    )

    mock_contentful_delivery_client.get_entry_by_id.assert_called_once_with(__ENTITY_ID)
    mock_article_service.entry_to_article_dict.assert_called_once_with(mock_entry)
    mock_article_service.save_value_in_cache.assert_called_once_with(
        __SLUG, article_dict
    )
    mock_index_article_from_contentful_entry.assert_called_once_with(mock_entry)
    mock_read_time_service.calculate_read_time.assert_called_once_with(mock_entry)
    mock_read_time_service.save_value_in_cache.assert_called_once_with(__SLUG, 420)
    mock_contentful_delivery_client.get_entity_references.assert_called_once_with(
        mock_entry
    )


def test_handle_event_delete_entry(
    mock_contentful_delivery_client,
    mock_contentful_preview_client,
    handler: contentful_event_handler.ContentfulEventHandler,
):
    handler.handle_event(
        action="delete",
        entity_type=contentful.EntityType.ENTRY.value,
        content_type=contentful.ContentfulContentType.ARTICLE.value,
        entity_id=__ENTITY_ID,
    )

    mock_contentful_delivery_client.get_entry_by_id.assert_not_called()
    mock_contentful_preview_client.get_entry_by_id.assert_not_called()
