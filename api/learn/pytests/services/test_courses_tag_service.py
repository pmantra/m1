import json
from unittest import mock

import pytest

from learn.services import courses_tag_service as courses_tag_service_class
from learn.services.contentful_caching_service import TTL


@pytest.fixture
@mock.patch("learn.services.caching_service.redis_client")
@mock.patch("learn.services.contentful.LibraryContentfulClient")
@mock.patch("learn.services.read_time_service.ReadTimeService")
@mock.patch("learn.services.course_service.CourseService")
def courses_tag_service(_, __, ___, ____):
    return courses_tag_service_class.CoursesTagService(preview=False, user_facing=True)


@mock.patch("learn.services.contentful_caching_service.log")
def test_get_value_not_in_cache_contentful_error(log_mock, courses_tag_service):
    courses_tag_service.redis_client.pipeline.return_value.execute.return_value = [None]
    error = Exception("😡")
    courses_tag_service.contentful_client.get_courses_by_tags.side_effect = error

    result = courses_tag_service.get_value("someTag")

    assert result is None
    courses_tag_service.redis_client.pipeline.return_value.get.assert_called_with(
        "courses:someTag"
    )
    courses_tag_service.redis_client.pipeline.return_value.execute.assert_called_once_with()
    courses_tag_service.contentful_client.get_courses_by_tags.assert_called_with(
        ["someTag"]
    )
    log_mock.exception.assert_called_with(
        "Error fetching value from Contentful",
        error=error,
        missing_identifier_values=["someTag"],
        class_name="CoursesTagService",
    )
    courses_tag_service.redis_client.pipeline.return_value.set.assert_not_called()


def test_get_value_not_in_cache(courses_tag_service):
    courses_tag_service.redis_client.pipeline.return_value.execute.return_value = [None]
    course1 = mock.Mock(slug="course-1", _metadata={"tags": [mock.Mock(id="someTag")]})
    course2 = mock.Mock(slug="course-2", _metadata={"tags": [mock.Mock(id="someTag")]})
    courses_tag_service.contentful_client.get_courses_by_tags.return_value = [
        course1,
        course2,
    ]

    result = courses_tag_service.get_value("someTag")

    assert result == ["course-1", "course-2"]
    courses_tag_service.contentful_client.get_courses_by_tags.assert_called_with(
        ["someTag"]
    )
    courses_tag_service.redis_client.pipeline.return_value.set.assert_called_with(
        "courses:someTag", json.dumps(["course-1", "course-2"]), ex=TTL
    )


def test_get_value_not_in_cache_saves_empty_array(courses_tag_service):
    courses_tag_service.redis_client.pipeline.return_value.execute.return_value = [None]
    courses_tag_service.contentful_client.get_courses_by_tags.return_value = []

    result = courses_tag_service.get_value("someTag")

    assert result == []
    courses_tag_service.contentful_client.get_courses_by_tags.assert_called_with(
        ["someTag"]
    )
    courses_tag_service.redis_client.pipeline.return_value.set.assert_called_with(
        "courses:someTag", json.dumps([]), ex=TTL
    )


def test_get_value_in_cache(courses_tag_service):
    courses_tag_service.redis_client.pipeline.return_value.execute.return_value = [
        json.dumps(["course-1", "course-2"])
    ]

    result = courses_tag_service.get_value("someTag")

    assert result == ["course-1", "course-2"]
    courses_tag_service.contentful_client.get_courses_by_tags.assert_not_called()
    courses_tag_service.redis_client.pipeline.return_value.set.assert_not_called()


def test_get_value_empty_array_in_cache(courses_tag_service):
    courses_tag_service.redis_client.pipeline.return_value.execute.return_value = [
        json.dumps([])
    ]

    result = courses_tag_service.get_value("someTag")

    assert result == []
    courses_tag_service.contentful_client.get_courses_by_tags.assert_not_called()
    courses_tag_service.redis_client.pipeline.return_value.set.assert_not_called()


def test_get_courses_for_tag_no_value(courses_tag_service):
    courses_tag_service.get_value = mock.Mock()
    courses_tag_service.get_value.return_value = None

    result = courses_tag_service.get_courses_for_tag("someTag")

    assert result == []
    courses_tag_service.get_value.assert_called_with("someTag")
    courses_tag_service.course_service.get_values.assert_not_called()


def test_get_courses_for_tag_has_value(courses_tag_service):
    courses_tag_service.get_value = mock.Mock()
    courses_tag_service.get_value.return_value = ["course-1", "course-2"]
    course1 = mock.Mock()
    course2 = mock.Mock()
    courses_tag_service.course_service.get_values.return_value = {
        "course-1": course1,
        "course-2": course2,
    }

    result = courses_tag_service.get_courses_for_tag("someTag")

    assert result == [course1, course2]
    courses_tag_service.get_value.assert_called_with("someTag")
    courses_tag_service.course_service.get_values.assert_called_with(
        identifier_values=["course-1", "course-2"]
    )


def test_courses_for_tag_limit(courses_tag_service):
    courses_tag_service.get_value = mock.Mock()
    courses_tag_service.get_value.return_value = [
        "course-1",
        "course-2",
        "course-3",
        "course-4",
    ]
    course1 = mock.Mock()
    course2 = mock.Mock()
    courses_tag_service.course_service.get_values.return_value = {
        "course-1": course1,
        "course-2": course2,
    }

    result = courses_tag_service.get_courses_for_tag("someTag", limit=2)

    assert result == [course1, course2]
    courses_tag_service.get_value.assert_called_with("someTag")
    courses_tag_service.course_service.get_values.assert_called_with(
        identifier_values=["course-1", "course-2"]
    )


def test_clear_cache(courses_tag_service):
    courses_tag_service.redis_client.keys.return_value = [
        "courses:pregnancy",
        "courses:fertility",
    ]

    courses_tag_service.clear_cache()

    courses_tag_service.redis_client.keys.assert_called_with("courses:*")
    call1 = mock.call("courses:pregnancy")
    call2 = mock.call("courses:fertility")
    courses_tag_service.redis_client.pipeline.return_value.delete.assert_has_calls(
        [call1, call2]
    )
