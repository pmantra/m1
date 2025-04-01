import copy
from unittest import mock

import pytest
from dateutil import parser

from learn.models.article import RelatedRead
from learn.models.article_type import ArticleType
from learn.models.course import (
    Course,
    CourseCallout,
    CourseChapter,
    RelatedCourse,
    RelatedCourseChapter,
)
from learn.models.course_member_status import MemberStatus
from learn.models.image import Image
from learn.pytests.factories import CourseMemberStatusFactory
from views.models.cta import CTA

__COURSE = Course(
    id="id",
    slug="🐌",
    title="title",
    image=Image(url="/image.png", description="description"),
    description="description",
    callout=CourseCallout(
        title="title", cta=CTA(text="cta text", url="https://example.com")
    ),
    chapters=[
        CourseChapter(
            slug="article-1",
            title="title",
            description="description",
            image=Image(url="/image.png", description="description"),
        ),
        CourseChapter(
            slug="article-2",
            title="title",
            description="description",
            image=Image(url="/image.png", description="description"),
        ),
    ],
    related=[
        RelatedCourse(
            title="title",
            thumbnail=Image(url="/image.png", description="description"),
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
        RelatedRead(
            title="title",
            thumbnail=Image(url="/image.png", description="description"),
            slug="article-1",
            type=ArticleType.RICH_TEXT,
        ),
        RelatedRead(
            title="title",
            thumbnail=Image(url="/image.png", description="description"),
            slug="article-1",
            type=ArticleType.HTML,
        ),
    ],
)


def test_get_marketplace_user(default_user, client, api_helpers):
    response = client.get(
        f"/api/v1/users/{default_user.id}/courses",
        headers=api_helpers.json_headers(default_user),
    )

    assert response.status_code == 403


def test_get_not_logged_in(factories, client, api_helpers):
    user = factories.EnterpriseUserFactory()
    response = client.get(f"/api/v1/users/{user.id}/courses")

    assert response.status_code == 401


def test_get_user_id_does_not_match(factories, client, api_helpers):
    user = factories.EnterpriseUserFactory()
    response = client.get(
        f"/api/v1/users/{420}/courses",
        headers=api_helpers.json_headers(user),
    )

    assert response.status_code == 404


@pytest.mark.parametrize("limit", ["0", "-1", "notanint" "4.20"])
def test_get_invalid_limit(factories, client, api_helpers, limit):
    user = factories.EnterpriseUserFactory()
    response = client.get(
        f"/api/v1/users/{user.id}/courses?limit={limit}",
        headers=api_helpers.json_headers(user),
    )

    assert response.status_code == 400
    data = api_helpers.load_json(response)
    assert data["errors"][0]["title"] == "limit must be a positive integer."


@mock.patch("learn.resources.user_courses_resource.CourseService")
def test_get_no_courses(_, factories, client, api_helpers):
    user = factories.EnterpriseUserFactory()
    response = client.get(
        f"/api/v1/users/{user.id}/courses", headers=api_helpers.json_headers(user)
    )

    assert response.status_code == 200
    data = api_helpers.load_json(response)
    assert len(data["courses"]) == 0


@mock.patch("learn.resources.user_courses_resource.CourseService")
def test_get_no_in_progress_courses(_, factories, client, api_helpers):
    user = factories.EnterpriseUserFactory()
    CourseMemberStatusFactory(
        user_id=user.id,
        course_slug="🐌",
        status=MemberStatus.COMPLETED,
    )
    response = client.get(
        f"/api/v1/users/{user.id}/courses", headers=api_helpers.json_headers(user)
    )

    assert response.status_code == 200
    data = api_helpers.load_json(response)
    assert len(data["courses"]) == 0


@pytest.mark.parametrize("limit", range(1, 5))
@mock.patch("learn.resources.user_courses_resource.CourseService")
def test_get_number_of_courses_is_less_than_limit(
    mock_course_service_constructor, factories, client, api_helpers, limit: int
):
    user = factories.EnterpriseUserFactory()

    course_1 = copy.deepcopy(__COURSE)
    course_1.slug = "🐌-1"
    course_1.chapters[0].slug = "1-1"
    course_1.chapters[1].slug = "1-2"
    course_2 = copy.deepcopy(__COURSE)
    course_2.slug = "🐌-2"
    course_2.chapters[0].slug = "2-1"
    course_2.chapters[1].slug = "2-2"
    course_3 = copy.deepcopy(__COURSE)
    course_3.slug = "🐌-3"
    course_3.chapters[0].slug = "3-1"
    course_3.chapters[1].slug = "3-2"

    CourseMemberStatusFactory(
        user_id=user.id,
        course_slug=course_1.slug,
        status=MemberStatus.IN_PROGRESS,
    )
    CourseMemberStatusFactory(
        user_id=user.id,
        course_slug=course_2.slug,
        status=MemberStatus.IN_PROGRESS,
    )
    CourseMemberStatusFactory(
        user_id=user.id,
        course_slug=course_3.slug,
        status=MemberStatus.IN_PROGRESS,
    )

    mock_course_service_constructor.return_value.get_values.return_value = {
        course.slug: course for course in [course_1, course_2, course_3]
    }

    course_1_with_viewed_at = copy.deepcopy(course_1)
    course_1_with_viewed_at.chapters[0].viewed_at = parser.parse("2023-03-15T03:14:00")
    course_2_with_viewed_at = copy.deepcopy(course_2)
    course_2_with_viewed_at.chapters[0].viewed_at = parser.parse("2023-03-14T03:14:00")
    course_2_with_viewed_at = copy.deepcopy(course_3)
    course_2_with_viewed_at.chapters[1].viewed_at = parser.parse("2023-03-16T03:14:00")
    # no viewed_at for course_3

    mock_course_service_constructor.populate_viewed_at.return_value = [
        course_1_with_viewed_at,
        course_2_with_viewed_at,
        course_3,
    ]

    response = client.get(
        f"/api/v1/users/{user.id}/courses?limit={limit}",
        headers=api_helpers.json_headers(user),
    )

    assert response.status_code == 200
    data = api_helpers.load_json(response)
    assert data["courses"] == [
        course.to_response_dict()
        for course in [course_2_with_viewed_at, course_1_with_viewed_at, course_3][
            0:limit
        ]
    ]
