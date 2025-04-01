import copy
import dataclasses
import json
from unittest import mock

import pytest
from dateutil import parser

from learn.models import article, article_type, course_factory, image, media_type
from learn.models.course import (
    Course,
    CourseCallout,
    CourseChapter,
    RelatedCourse,
    RelatedCourseChapter,
)
from learn.models.resource_interaction import ResourceInteraction, ResourceType
from learn.services import course_service
from storage.connection import db
from views.models import cta

__SLUG = "🐌"
__KEY = f"course:{__SLUG}"
__ID = "1KWykUOEklzRooTKhG755S"

__COURSE_FROM_CONTENTFUL = Course(
    id=__ID,
    slug=__SLUG,
    title="title",
    image=image.Image(url="/image.png", description="description"),
    description="description",
    callout=CourseCallout(
        title="title", cta=cta.CTA(text="cta text", url="https://example.com")
    ),
    chapters=[
        CourseChapter(
            slug="article-1",
            title="title",
            description="description",
            image=image.Image(url="/image.png", description="description"),
        ),
        CourseChapter(
            slug="article-2",
            title="title",
            description="description",
            image=image.Image(url="/image.png", description="description"),
        ),
    ],
    related=[
        RelatedCourse(
            title="title",
            thumbnail=image.Image(url="/image.png", description="description"),
            slug="course-2",
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

__FULL_COURSE = copy.deepcopy(__COURSE_FROM_CONTENTFUL)
__FULL_COURSE.chapters[0].length_in_minutes = 1
__FULL_COURSE.chapters[0].media_type = media_type.MediaType.ARTICLE
__FULL_COURSE.chapters[1].media_type = media_type.MediaType.VIDEO
__FULL_COURSE.related[0].chapters[0].length_in_minutes = 1
__FULL_COURSE.related[0].chapters[0].media_type = media_type.MediaType.ARTICLE
__FULL_COURSE.related[0].chapters[1].media_type = media_type.MediaType.VIDEO

__READ_TIMES = [
    __FULL_COURSE.chapters[0].length_in_minutes,
    -1,
    __FULL_COURSE.related[0].chapters[0].length_in_minutes,
    -1,
]


@pytest.fixture()
def mock_course_entry():
    mock_asset = mock.Mock()
    mock_asset.url.return_value = "/image.png"
    mock_asset.fields.return_value = {"description": "description"}

    return mock.Mock(
        id=__ID,
        slug=__SLUG,
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
            mock.Mock(content_type=mock.Mock(id="article")),
            mock.Mock(content_type=mock.Mock(id="nonContentfulArticle")),
        ],
    )


@mock.patch("learn.services.contentful.LibraryContentfulClient")
@mock.patch("learn.services.caching_service.redis_client")
@mock.patch("learn.models.course_factory.ReadTimeService")
@mock.patch("learn.services.article_service.ArticleService")
def test_get_value_error_initializing_redis_client(
    mock_article_service_constructor,
    mock_read_time_service_constructor,
    mock_redis_client_method,
    mock_contentful_client_constructor,
    mock_course_entry,
):
    mock_redis_client_method.side_effect = Exception
    mock_contentful_client_constructor.return_value.get_courses_by_slug.return_value = [
        mock_course_entry
    ]
    mock_article_service_constructor.return_value.parse_as_related_read.side_effect = [
        __COURSE_FROM_CONTENTFUL.related[1],
        __COURSE_FROM_CONTENTFUL.related[2],
    ]
    mock_read_time_service_constructor.return_value.calculate_read_time.side_effect = (
        __READ_TIMES
    )

    assert course_service.CourseService().get_value(__SLUG) == __FULL_COURSE

    mock_contentful_client_constructor.assert_called_once_with(
        preview=False, user_facing=True
    )
    mock_contentful_client_constructor.return_value.get_courses_by_slug.assert_called_once_with(
        [__SLUG]
    )
    mock_article_service_constructor.return_value.parse_as_related_read.assert_has_calls(
        [
            mock.call(mock_course_entry.related[1]),
            mock.call(mock_course_entry.related[2]),
        ]
    )
    mock_read_time_service_constructor.return_value.calculate_read_time.assert_has_calls(
        [
            mock.call(mock_course_entry.chapters[0].content),
            mock.call(mock_course_entry.chapters[1].content),
            mock.call(mock_course_entry.related[0].chapters[0].content),
            mock.call(mock_course_entry.related[0].chapters[1].content),
        ]
    )


@mock.patch("learn.services.contentful.LibraryContentfulClient")
@mock.patch("learn.services.caching_service.redis_client")
@mock.patch("learn.models.course_factory.ReadTimeService")
@mock.patch("learn.services.article_service.ArticleService")
def test_get_value_already_in_cache(
    _,
    __,
    mock_redis_client_method,
    mock_contentful_client_constructor,
    mock_course_entry,
):
    mock_redis_client_method.return_value.pipeline.return_value.execute.return_value = [
        json.dumps(dataclasses.asdict(__FULL_COURSE))
    ]

    assert course_service.CourseService().get_value(__SLUG) == __FULL_COURSE

    mock_contentful_client_constructor.return_value.get_course_by_slug.assert_not_called()


@mock.patch("learn.services.contentful.LibraryContentfulClient")
@mock.patch("learn.services.caching_service.redis_client")
@mock.patch("learn.models.course_factory.ReadTimeService")
@mock.patch("learn.services.article_service.ArticleService")
def test_get_value_not_in_cache(
    mock_article_service_constructor,
    mock_read_time_service_constructor,
    mock_redis_client_method,
    mock_contentful_client_constructor,
    mock_course_entry,
):
    mock_redis_client_method.return_value.pipeline.return_value.execute.return_value = [
        None
    ]
    mock_contentful_client_constructor.return_value.get_courses_by_slug.return_value = [
        mock_course_entry
    ]
    mock_article_service_constructor.return_value.parse_as_related_read.side_effect = [
        __COURSE_FROM_CONTENTFUL.related[1],
        __COURSE_FROM_CONTENTFUL.related[2],
    ]
    mock_read_time_service_constructor.return_value.calculate_read_time.side_effect = (
        __READ_TIMES
    )

    assert course_service.CourseService().get_value(__SLUG) == __FULL_COURSE

    mock_contentful_client_constructor.assert_called_once_with(
        preview=False, user_facing=True
    )
    mock_contentful_client_constructor.return_value.get_courses_by_slug.assert_called_once_with(
        [__SLUG]
    )
    mock_article_service_constructor.return_value.parse_as_related_read.assert_has_calls(
        [
            mock.call(mock_course_entry.related[1]),
            mock.call(mock_course_entry.related[2]),
        ]
    )
    mock_read_time_service_constructor.return_value.calculate_read_time.assert_has_calls(
        [
            mock.call(mock_course_entry.chapters[0].content),
            mock.call(mock_course_entry.chapters[1].content),
            mock.call(mock_course_entry.related[0].chapters[0].content),
            mock.call(mock_course_entry.related[0].chapters[1].content),
        ]
    )
    set_args = (
        mock_redis_client_method.return_value.pipeline.return_value.set.call_args.args
    )
    assert set_args[0] == __KEY
    assert course_factory.from_dict(json.loads(set_args[1])) == __FULL_COURSE


@mock.patch("learn.services.contentful.LibraryContentfulClient")
@mock.patch("learn.services.caching_service.redis_client")
@mock.patch("learn.models.course_factory.ReadTimeService")
@mock.patch("learn.services.article_service.ArticleService")
def test_get_value_course_not_found(
    _,
    __,
    mock_redis_client_method,
    mock_contentful_client_constructor,
    mock_course_entry,
):
    mock_redis_client_method.return_value.pipeline.return_value.execute.return_value = [
        None
    ]
    mock_contentful_client_constructor.return_value.get_courses_by_slug.return_value = (
        []
    )

    assert course_service.CourseService().get_value(__SLUG) is None

    mock_redis_client_method.return_value.pipeline.return_value.get.assert_called_once_with(
        __KEY
    )
    mock_redis_client_method.return_value.pipeline.return_value.execute.assert_has_calls(
        [mock.call(), mock.call()]
    )
    mock_contentful_client_constructor.assert_called_once_with(
        preview=False, user_facing=True
    )
    mock_contentful_client_constructor.return_value.get_courses_by_slug.assert_called_once_with(
        [__SLUG]
    )
    mock_redis_client_method.return_value.set.assert_not_called()


@mock.patch("learn.services.contentful.LibraryContentfulClient")
@mock.patch("learn.services.caching_service.redis_client")
@mock.patch("learn.models.course_factory.ReadTimeService")
@mock.patch("learn.services.article_service.ArticleService")
def test_get_value_error_reading_from_cache(
    mock_article_service_constructor,
    mock_read_time_service_constructor,
    mock_redis_client_method,
    mock_contentful_client_constructor,
    mock_course_entry,
):
    mock_redis_client_method.return_value.pipeline.return_value.execute.side_effect = (
        Exception
    )
    mock_contentful_client_constructor.return_value.get_courses_by_slug.return_value = [
        mock_course_entry
    ]
    mock_article_service_constructor.return_value.parse_as_related_read.side_effect = [
        __COURSE_FROM_CONTENTFUL.related[1],
        __COURSE_FROM_CONTENTFUL.related[2],
    ]
    mock_read_time_service_constructor.return_value.calculate_read_time.side_effect = (
        __READ_TIMES
    )

    assert course_service.CourseService().get_value(__SLUG) == __FULL_COURSE

    mock_contentful_client_constructor.assert_called_once_with(
        preview=False, user_facing=True
    )
    mock_contentful_client_constructor.return_value.get_courses_by_slug.assert_called_once_with(
        [__SLUG]
    )
    mock_article_service_constructor.return_value.parse_as_related_read.assert_has_calls(
        [
            mock.call(mock_course_entry.related[1]),
            mock.call(mock_course_entry.related[2]),
        ]
    )
    mock_read_time_service_constructor.return_value.calculate_read_time.assert_has_calls(
        [
            mock.call(mock_course_entry.chapters[0].content),
            mock.call(mock_course_entry.chapters[1].content),
            mock.call(mock_course_entry.related[0].chapters[0].content),
            mock.call(mock_course_entry.related[0].chapters[1].content),
        ]
    )
    set_args = (
        mock_redis_client_method.return_value.pipeline.return_value.set.call_args.args
    )
    assert set_args[0] == __KEY
    assert course_factory.from_dict(json.loads(set_args[1])) == __FULL_COURSE


@mock.patch("learn.services.contentful.LibraryContentfulClient")
@mock.patch("learn.services.caching_service.redis_client")
@mock.patch("learn.models.course_factory.ReadTimeService")
@mock.patch("learn.services.article_service.ArticleService")
def test_get_value_old_model_in_cache(
    mock_article_service_constructor,
    mock_read_time_service_constructor,
    mock_redis_client_method,
    mock_contentful_client_constructor,
    mock_course_entry,
):
    bad_course_dict = dataclasses.asdict(__FULL_COURSE)
    del bad_course_dict["title"]

    mock_redis_client_method.return_value.pipeline.return_value.execute.return_value = [
        json.dumps(bad_course_dict)
    ]
    mock_contentful_client_constructor.return_value.get_courses_by_slug.return_value = [
        mock_course_entry
    ]
    mock_article_service_constructor.return_value.parse_as_related_read.side_effect = [
        __COURSE_FROM_CONTENTFUL.related[1],
        __COURSE_FROM_CONTENTFUL.related[2],
    ]
    mock_read_time_service_constructor.return_value.calculate_read_time.side_effect = (
        __READ_TIMES
    )

    assert course_service.CourseService().get_value(__SLUG) == __FULL_COURSE

    mock_redis_client_method.return_value.pipeline.return_value.get.assert_called_once_with(
        __KEY
    )
    mock_redis_client_method.return_value.delete.assert_called_once_with(__KEY)
    mock_contentful_client_constructor.assert_called_once_with(
        preview=False, user_facing=True
    )
    mock_contentful_client_constructor.return_value.get_courses_by_slug.assert_called_once_with(
        [__SLUG]
    )
    mock_article_service_constructor.return_value.parse_as_related_read.assert_has_calls(
        [
            mock.call(mock_course_entry.related[1]),
            mock.call(mock_course_entry.related[2]),
        ]
    )
    mock_read_time_service_constructor.return_value.calculate_read_time.assert_has_calls(
        [
            mock.call(mock_course_entry.chapters[0].content),
            mock.call(mock_course_entry.chapters[1].content),
            mock.call(mock_course_entry.related[0].chapters[0].content),
            mock.call(mock_course_entry.related[0].chapters[1].content),
        ]
    )
    set_args = (
        mock_redis_client_method.return_value.pipeline.return_value.set.call_args.args
    )
    assert (
        mock_redis_client_method.return_value.pipeline.return_value.execute.call_count
        == 2
    )
    assert set_args[0] == __KEY
    assert course_factory.from_dict(json.loads(set_args[1])) == __FULL_COURSE


@mock.patch("learn.services.contentful.LibraryContentfulClient")
@mock.patch("learn.services.caching_service.redis_client")
@mock.patch("learn.models.course_factory.ReadTimeService")
@mock.patch("learn.services.article_service.ArticleService")
def test_get_value_error_from_contentful(
    _,
    __,
    mock_redis_client_method,
    mock_contentful_client_constructor,
    mock_course_entry,
):
    mock_redis_client_method.return_value.pipeline.return_value.execute.return_value = [
        None
    ]
    mock_contentful_client_constructor.return_value.get_courses_by_slug.side_effect = (
        Exception
    )

    assert course_service.CourseService().get_value(__SLUG) is None

    mock_redis_client_method.return_value.pipeline.return_value.get.assert_called_once_with(
        __KEY
    )
    mock_redis_client_method.return_value.pipeline.return_value.execute.assert_called_once_with()
    mock_contentful_client_constructor.assert_called_once_with(
        preview=False, user_facing=True
    )
    mock_contentful_client_constructor.return_value.get_courses_by_slug.assert_called_once_with(
        [__SLUG]
    )
    mock_redis_client_method.pipeline.return_value.set.assert_not_called()


@mock.patch("learn.services.contentful.LibraryContentfulClient")
@mock.patch("learn.services.caching_service.redis_client")
@mock.patch("learn.models.course_factory.ReadTimeService")
@mock.patch("learn.services.article_service.ArticleService")
def test_get_value_error_writing_to_cache(
    mock_article_service_constructor,
    mock_read_time_service_constructor,
    mock_redis_client_method,
    mock_contentful_client_constructor,
    mock_course_entry,
):
    mock_redis_client_method.return_value.pipeline.return_value.execute.return_value = [
        None
    ]
    mock_contentful_client_constructor.return_value.get_courses_by_slug.return_value = [
        mock_course_entry
    ]
    mock_article_service_constructor.return_value.parse_as_related_read.side_effect = [
        __COURSE_FROM_CONTENTFUL.related[1],
        __COURSE_FROM_CONTENTFUL.related[2],
    ]
    mock_read_time_service_constructor.return_value.calculate_read_time.side_effect = (
        __READ_TIMES
    )

    mock_redis_client_method.return_value.set.side_effect = Exception

    assert course_service.CourseService().get_value(__SLUG) == __FULL_COURSE

    mock_contentful_client_constructor.assert_called_once_with(
        preview=False, user_facing=True
    )
    mock_contentful_client_constructor.return_value.get_courses_by_slug.assert_called_once_with(
        [__SLUG]
    )
    mock_article_service_constructor.return_value.parse_as_related_read.assert_has_calls(
        [
            mock.call(mock_course_entry.related[1]),
            mock.call(mock_course_entry.related[2]),
        ]
    )
    mock_read_time_service_constructor.return_value.calculate_read_time.assert_has_calls(
        [
            mock.call(mock_course_entry.chapters[0].content),
            mock.call(mock_course_entry.chapters[1].content),
            mock.call(mock_course_entry.related[0].chapters[0].content),
            mock.call(mock_course_entry.related[0].chapters[1].content),
        ]
    )
    set_args = (
        mock_redis_client_method.return_value.pipeline.return_value.set.call_args.args
    )
    assert set_args[0] == __KEY
    assert course_factory.from_dict(json.loads(set_args[1])) == __FULL_COURSE


@mock.patch("learn.services.contentful.LibraryContentfulClient")
@mock.patch("learn.services.caching_service.redis_client")
@mock.patch("learn.models.course_factory.ReadTimeService")
@mock.patch("learn.services.article_service.ArticleService")
def test_get_value_preview(
    mock_article_service_constructor,
    mock_read_time_service_constructor,
    mock_redis_client_method,
    mock_contentful_client_constructor,
    mock_course_entry,
):
    mock_contentful_client_constructor.return_value.get_courses_by_slug.return_value = [
        mock_course_entry
    ]
    mock_article_service_constructor.return_value.parse_as_related_read.side_effect = [
        __COURSE_FROM_CONTENTFUL.related[1],
        __COURSE_FROM_CONTENTFUL.related[2],
    ]
    mock_read_time_service_constructor.return_value.calculate_read_time.side_effect = (
        __READ_TIMES
    )

    assert course_service.CourseService(preview=True).get_value(__SLUG) == __FULL_COURSE

    mock_contentful_client_constructor.assert_called_once_with(
        preview=True, user_facing=True
    )
    mock_contentful_client_constructor.return_value.get_courses_by_slug.assert_called_once_with(
        [__SLUG]
    )
    mock_redis_client_method.return_value.pipeline.assert_not_called()


@mock.patch("learn.services.contentful.LibraryContentfulClient")
@mock.patch("learn.services.caching_service.redis_client")
@mock.patch("learn.models.course_factory.ReadTimeService")
@mock.patch("learn.services.article_service.ArticleService")
def test_get_values(
    mock_article_service_constructor,
    mock_read_time_service_constructor,
    mock_redis_client_method,
    mock_contentful_client_constructor,
    mock_course_entry,
):
    course_1 = copy.deepcopy(__FULL_COURSE)
    course_1.slug = "slug-1"
    course_2 = copy.deepcopy(__FULL_COURSE)
    course_2.slug = "slug-2"
    mock_redis_client_method.return_value.pipeline.return_value.execute.return_value = [
        json.dumps(dataclasses.asdict(course_1)),
        None,
    ]
    mock_course_entry.slug = "slug-2"
    mock_contentful_client_constructor.return_value.get_courses_by_slug.return_value = [
        mock_course_entry
    ]
    mock_article_service_constructor.return_value.parse_as_related_read.side_effect = [
        __COURSE_FROM_CONTENTFUL.related[1],
        __COURSE_FROM_CONTENTFUL.related[2],
    ]
    mock_read_time_service_constructor.return_value.calculate_read_time.side_effect = (
        __READ_TIMES
    )

    assert course_service.CourseService().get_values(["slug-1", "slug-2"]) == {
        "slug-1": course_1,
        "slug-2": course_2,
    }

    mock_redis_client_method.return_value.pipeline.return_value.get.assert_has_calls(
        [mock.call("course:slug-1"), mock.call("course:slug-2")]
    )
    mock_contentful_client_constructor.assert_called_once_with(
        preview=False, user_facing=True
    )
    mock_contentful_client_constructor.return_value.get_courses_by_slug.assert_called_once_with(
        ["slug-2"]
    )
    set_args = (
        mock_redis_client_method.return_value.pipeline.return_value.set.call_args.args
    )
    assert (
        mock_redis_client_method.return_value.pipeline.return_value.execute.call_count
        == 2
    )
    assert set_args[0] == "course:slug-2"
    assert course_factory.from_dict(json.loads(set_args[1])) == course_2


@mock.patch("learn.services.contentful.LibraryContentfulClient")
@mock.patch("learn.services.caching_service.redis_client")
@mock.patch("learn.models.course_factory.ReadTimeService")
@mock.patch("learn.services.article_service.ArticleService")
def test_get_values_error_fetching_from_contentful(
    mock_article_service_constructor,
    mock_read_time_service_constructor,
    mock_redis_client_method,
    mock_contentful_client_constructor,
):
    # One course is in the cache
    mock_redis_client_method.return_value.pipeline.return_value.execute.return_value = [
        json.dumps(dataclasses.asdict(__FULL_COURSE)),
        None,
    ]
    # The other can't be got
    mock_contentful_client_constructor.return_value.get_courses_by_slug.side_effect = (
        Exception
    )
    mock_article_service_constructor.return_value.parse_as_related_read.side_effect = [
        __COURSE_FROM_CONTENTFUL.related[1],
        __COURSE_FROM_CONTENTFUL.related[2],
    ]
    mock_read_time_service_constructor.return_value.calculate_read_time.side_effect = (
        __READ_TIMES
    )

    # Only the one in the cache is returned
    assert course_service.CourseService().get_values(["slug-1", "slug-2"]) == {
        "slug-1": __FULL_COURSE
    }

    mock_redis_client_method.return_value.pipeline.return_value.get.assert_has_calls(
        [mock.call("course:slug-1"), mock.call("course:slug-2")]
    )
    mock_contentful_client_constructor.assert_called_once_with(
        preview=False, user_facing=True
    )
    mock_contentful_client_constructor.return_value.get_courses_by_slug.assert_called_once_with(
        ["slug-2"]
    )
    mock_redis_client_method.return_value.pipeline.return_value.execute.assert_called_once_with()
    mock_redis_client_method.return_value.pipeline.return_value.set.assert_not_called()


@mock.patch("learn.services.contentful.LibraryContentfulClient")
@mock.patch("learn.services.caching_service.redis_client")
@mock.patch("learn.models.course_factory.ReadTimeService")
@mock.patch("learn.services.article_service.ArticleService")
def test_get_values_in_cache(
    mock_article_service_constructor,
    mock_read_time_service_constructor,
    mock_redis_client_method,
    mock_contentful_client_constructor,
):
    # Both courses in cache
    mock_redis_client_method.return_value.pipeline.return_value.execute.return_value = [
        json.dumps(dataclasses.asdict(__FULL_COURSE)),
        json.dumps(dataclasses.asdict(__FULL_COURSE)),
    ]
    mock_article_service_constructor.return_value.parse_as_related_read.side_effect = [
        __COURSE_FROM_CONTENTFUL.related[1],
        __COURSE_FROM_CONTENTFUL.related[2],
    ]
    mock_read_time_service_constructor.return_value.calculate_read_time.side_effect = (
        __READ_TIMES
    )

    assert course_service.CourseService().get_values(["slug-1", "slug-2"]) == {
        "slug-1": __FULL_COURSE,
        "slug-2": __FULL_COURSE,
    }
    mock_redis_client_method.return_value.pipeline.return_value.get.assert_has_calls(
        [mock.call("course:slug-1"), mock.call("course:slug-2")]
    )
    mock_contentful_client_constructor.assert_called_once_with(
        preview=False, user_facing=True
    )
    # Contentful not called
    mock_contentful_client_constructor.return_value.get_courses_by_slug.assert_not_called()
    mock_redis_client_method.return_value.pipeline.return_value.execute.assert_called_once_with()
    mock_redis_client_method.return_value.pipeline.return_value.set.assert_not_called()


@mock.patch("learn.services.contentful.LibraryContentfulClient")
@mock.patch("learn.services.caching_service.redis_client")
def test_save_value_in_cache_error_initializing_redis_client(
    mock_redis_client_method, _, mock_course_entry
):
    mock_redis_client_method.side_effect = Exception
    with pytest.raises(RuntimeError):
        course_service.CourseService().save_value_in_cache(__SLUG, __FULL_COURSE)


@mock.patch("learn.services.contentful.LibraryContentfulClient")
@mock.patch("learn.services.caching_service.redis_client")
def test_save_value_in_cache(mock_redis_client_method, _, mock_course_entry):
    course_service.CourseService().save_value_in_cache(__SLUG, __FULL_COURSE)

    set_args = mock_redis_client_method.return_value.set.call_args.args
    assert set_args[0] == __KEY
    assert course_factory.from_dict(json.loads(set_args[1])) == __FULL_COURSE


@mock.patch("learn.services.contentful.LibraryContentfulClient")
@mock.patch("learn.services.caching_service.redis_client")
def test_remove_value_from_cache(
    mock_redis_client_method, mock_contentful_client_constructor
):
    entry_id = "12345abcde"
    mock_contentful_client_constructor.return_value.get_entry_by_id.return_value.slug = (
        __SLUG
    )

    course_service.CourseService().remove_value_from_cache(entry_id)

    mock_contentful_client_constructor.assert_has_calls(
        [
            mock.call(preview=False, user_facing=True),
            mock.call(preview=True, user_facing=False),
        ]
    )
    mock_contentful_client_constructor.return_value.get_entry_by_id.assert_called_once_with(
        entry_id
    )
    mock_redis_client_method.return_value.delete.assert_called_once_with(__KEY)


def test_populate_viewed_at(factories):
    course_1 = copy.deepcopy(__COURSE_FROM_CONTENTFUL)
    course_2 = copy.deepcopy(__COURSE_FROM_CONTENTFUL)
    course_1.slug = "slug-1"
    course_2.slug = "slug-2"
    course_2.chapters[0].slug = "article-2-1"
    course_2.chapters[1].slug = "article-2-2"

    timestamp_1 = parser.parse("2023-03-14T03:14:00")
    timestamp_2 = parser.parse("2023-03-15T03:14:00")

    user = factories.EnterpriseUserFactory()

    db.session.add(
        ResourceInteraction(
            user_id=user.id,
            resource_type=ResourceType.ARTICLE,
            slug=course_1.chapters[0].slug,
            resource_viewed_at=timestamp_1,
            created_at=timestamp_1,
            modified_at=timestamp_1,
        )
    )

    db.session.add(
        ResourceInteraction(
            user_id=user.id,
            resource_type=ResourceType.ARTICLE,
            slug=course_2.chapters[1].slug,
            resource_viewed_at=timestamp_2,
            created_at=timestamp_2,
            modified_at=timestamp_2,
        )
    )

    result = course_service.CourseService.populate_viewed_at(
        [copy.deepcopy(course_1), copy.deepcopy(course_2)], user.id
    )

    course_1.chapters[0].viewed_at = timestamp_1
    course_2.chapters[1].viewed_at = timestamp_2

    assert result == [course_1, course_2]


@mock.patch("learn.services.course_service.db")
def test_populate_viewed_at_no_courses(mock_db, factories):
    user = factories.EnterpriseUserFactory()

    assert course_service.CourseService.populate_viewed_at([], user.id) == []

    mock_db.session.query.assert_not_called()
