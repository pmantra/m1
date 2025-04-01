import copy
from unittest import mock

import pytest

from learn.models import course, course_member_status, image
from learn.pytests import factories as learn_factories
from learn.services import course_member_status_service
from storage.connection import db

__COURSE = course.Course(
    id="asdfjkl",
    slug="course-slug",
    title="Course Title",
    image=image.Image(url="https://i.mg/img.img", description="an image"),
    description="course description",
    callout=course.CourseCallout(
        title="callout title", cta=course.CTA(text="call", url="out.call")
    ),
    chapters=[],
    related=[],
)


@pytest.fixture
def service():
    return course_member_status_service.CourseMemberStatusService()


def test_get_course_member_status_none(factories, service):
    user = factories.EnterpriseUserFactory()

    result = service.get(user.id, "abc")

    assert result is None


def test_get_course_member_status_one(factories, service):
    user = factories.EnterpriseUserFactory()
    member_status = learn_factories.CourseMemberStatusFactory(
        user_id=user.id,
        course_slug="abc",
        status=course_member_status.MemberStatus.IN_PROGRESS,
    )

    result = service.get(user.id, "abc")

    assert result.user_id == member_status.user_id
    assert result.course_slug == member_status.course_slug
    assert result.status == member_status.status


def test_list_user_does_not_exist(service):
    assert len(service.list(420)) == 0


def test_list_no_courses(factories, service):
    user = factories.EnterpriseUserFactory()
    assert len(service.list(user.id)) == 0


def test_list_without_member_status(factories, service):
    user = factories.EnterpriseUserFactory()
    member_status_in_progress = learn_factories.CourseMemberStatusFactory(
        user_id=user.id,
        course_slug="abc",
        status=course_member_status.MemberStatus.IN_PROGRESS,
    )
    member_status_completed = learn_factories.CourseMemberStatusFactory(
        user_id=user.id,
        course_slug="def",
        status=course_member_status.MemberStatus.COMPLETED,
    )
    assert service.list(user.id) == [member_status_in_progress, member_status_completed]


def test_list_with_member_status(factories, service):
    user = factories.EnterpriseUserFactory()
    member_status = learn_factories.CourseMemberStatusFactory(
        user_id=user.id,
        course_slug="abc",
        status=course_member_status.MemberStatus.IN_PROGRESS,
    )
    learn_factories.CourseMemberStatusFactory(
        user_id=user.id,
        course_slug="def",
        status=course_member_status.MemberStatus.COMPLETED,
    )
    assert service.list(
        user.id, member_status=course_member_status.MemberStatus.IN_PROGRESS
    ) == [member_status]


def test_create_course_member_status_exists(factories, service):
    user = factories.EnterpriseUserFactory()
    learn_factories.CourseMemberStatusFactory(
        user_id=user.id,
        course_slug="abc",
        status=course_member_status.MemberStatus.IN_PROGRESS,
    )

    result = service.create(user.id, "abc")

    assert result.user_id == user.id
    assert result.course_slug == "abc"
    assert result.status == course_member_status.MemberStatus.IN_PROGRESS
    assert course_member_status.CourseMemberStatus.query.count() == 1


def test_create_course_member_status_doesnt_exist(factories, service):
    user = factories.EnterpriseUserFactory()

    result = service.create(user.id, "abc")

    assert result.user_id == user.id
    assert result.course_slug == "abc"
    assert result.status == course_member_status.MemberStatus.IN_PROGRESS


@pytest.mark.parametrize(
    argnames=["old_status", "new_status"],
    argvalues=[
        [
            course_member_status.MemberStatus.IN_PROGRESS.value,
            course_member_status.MemberStatus.NOT_STARTED.value,
        ],
        [
            course_member_status.MemberStatus.COMPLETED.value,
            course_member_status.MemberStatus.IN_PROGRESS.value,
        ],
        [course_member_status.MemberStatus.IN_PROGRESS.value, "this is not valid"],
    ],
)
def test_invalid_update(factories, service, old_status, new_status):
    user = factories.EnterpriseUserFactory()
    status_record = learn_factories.CourseMemberStatusFactory(
        user_id=user.id,
        course_slug="abc",
        status=old_status,
    )

    with pytest.raises(ValueError):
        service.update(
            member_status=status_record,
            new_status_value=new_status,
        )


def test_update_valid(factories, service):
    user = factories.EnterpriseUserFactory()
    status_record = learn_factories.CourseMemberStatusFactory(
        user_id=user.id,
        course_slug="abc",
        status=course_member_status.MemberStatus.IN_PROGRESS.value,
    )

    result = service.update(
        member_status=status_record,
        new_status_value=course_member_status.MemberStatus.COMPLETED.value,
    )

    assert result.status == course_member_status.MemberStatus.COMPLETED.value
    status_from_db = course_member_status.CourseMemberStatus.query.filter_by(
        user_id=user.id, course_slug="abc"
    ).one()
    assert status_from_db.status == course_member_status.MemberStatus.COMPLETED.value


@mock.patch("learn.models.course_member_status.CourseMemberStatus")
def test_set_statuses_on_courses(course_member_status_class, factories, service):
    user = factories.EnterpriseUserFactory()
    course_slug_1 = "abc"
    course_slug_2 = "def"
    status_record_1 = learn_factories.CourseMemberStatusFactory(
        user_id=user.id,
        course_slug=course_slug_1,
        status=course_member_status.MemberStatus.IN_PROGRESS.value,
    )
    status_record_2 = learn_factories.CourseMemberStatusFactory(
        user_id=user.id,
        course_slug=course_slug_2,
        status=course_member_status.MemberStatus.COMPLETED.value,
    )
    course_member_status_class.query.filter.return_value = [
        status_record_1,
        status_record_2,
    ]

    course_1 = copy.deepcopy(__COURSE)
    course_1.slug = course_slug_1
    course_2 = copy.deepcopy(__COURSE)
    course_2.slug = course_slug_2
    course_3 = copy.deepcopy(__COURSE)
    course_3.slug = "course-id-3"

    result = service.set_statuses_on_courses(
        courses=[course_1, course_2, course_3], user_id=user.id
    )
    assert (
        result[0].member_status == course_member_status.MemberStatus.IN_PROGRESS.value
    )
    assert result[1].member_status == course_member_status.MemberStatus.COMPLETED.value
    assert (
        result[2].member_status == course_member_status.MemberStatus.NOT_STARTED.value
    )


@mock.patch("learn.services.course_member_status_service.CourseMemberStatus")
def test_set_statuses_on_courses_no_courses(
    mock_course_member_status_class, factories, service
):
    user = factories.EnterpriseUserFactory()

    assert service.set_statuses_on_courses(courses=[], user_id=user.id) == []

    mock_course_member_status_class.query.filter.assert_not_called()


def test_delete_already_deleted(service, factories):
    user = factories.EnterpriseUserFactory()
    status_record = learn_factories.CourseMemberStatusFactory(
        user_id=user.id,
        course_slug="abc",
        status=course_member_status.MemberStatus.IN_PROGRESS.value,
    )
    db.session.delete(status_record)
    db.session.commit()

    # Just tests that this doesn't raise an error
    service.delete(status_record)


def test_delete(service, factories):
    user = factories.EnterpriseUserFactory()
    status_record = learn_factories.CourseMemberStatusFactory(
        user_id=user.id,
        course_slug="abc",
        status=course_member_status.MemberStatus.IN_PROGRESS.value,
    )

    service.delete(status_record)

    assert course_member_status.CourseMemberStatus.query.count() == 0
