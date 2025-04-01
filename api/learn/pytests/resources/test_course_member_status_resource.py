import json
from unittest import mock

from learn.models import course_member_status
from learn.pytests import factories as learn_factories


def test_post_marketplace_user(default_user, client, api_helpers):
    response = client.post(
        "/api/v1/library/courses/slug/member_statuses",
        headers=api_helpers.json_headers(default_user),
    )

    assert response.status_code == 403


@mock.patch("learn.services.course_service.CourseService")
def test_post_no_course(course_service_mock, factories, client, api_helpers):
    user = factories.EnterpriseUserFactory()
    course_service_mock.return_value.get_value.return_value = None

    response = client.post(
        "/api/v1/library/courses/slug/member_statuses",
        headers=api_helpers.json_headers(user),
    )

    assert response.status_code == 404
    course_service_mock.return_value.get_value.assert_called_with("slug")


@mock.patch("learn.services.course_member_status_service.CourseMemberStatusService")
@mock.patch("learn.services.course_service.CourseService")
def test_post_creates_member_status(
    course_service_mock, member_status_service_mock, factories, client, api_helpers
):
    user = factories.EnterpriseUserFactory()
    course_slug = "abc"
    course = mock.Mock(slug=course_slug)
    course_service_mock.return_value.get_value.return_value = course
    member_status = learn_factories.CourseMemberStatusFactory(
        user_id=user.id,
        course_slug=course_slug,
        status=course_member_status.MemberStatus.IN_PROGRESS,
    )
    member_status_service_mock.create.return_value = member_status

    response = client.post(
        "/api/v1/library/courses/slug/member_statuses",
        headers=api_helpers.json_headers(user),
    )

    assert response.status_code == 200
    assert response.json["course_slug"] == course_slug
    assert response.json["user_id"] == user.id
    assert response.json["status"] == member_status.status
    course_service_mock.return_value.get_value.assert_called_with("slug")
    member_status_service_mock.create.assert_called_with(
        user_id=user.id, course_slug=course_slug
    )


def test_patch_marketplace_user(default_user, client, api_helpers):
    response = client.patch(
        "/api/v1/library/courses/slug/member_statuses/1",
        headers=api_helpers.json_headers(default_user),
    )

    assert response.status_code == 403


def test_patch_user_mismatch(factories, client, api_helpers):
    user1 = factories.EnterpriseUserFactory()
    user2 = factories.EnterpriseUserFactory()

    response = client.patch(
        f"/api/v1/library/courses/slug/member_statuses/{user1.id}",
        headers=api_helpers.json_headers(user2),
    )

    assert response.status_code == 404


@mock.patch("learn.services.course_service.CourseService")
def test_patch_no_course(course_service_mock, factories, client, api_helpers):
    user = factories.EnterpriseUserFactory()
    course_service_mock.return_value.get_value.return_value = None

    response = client.patch(
        f"/api/v1/library/courses/slug/member_statuses/{user.id}",
        headers=api_helpers.json_headers(user),
    )

    assert response.status_code == 404


@mock.patch("learn.services.course_member_status_service.CourseMemberStatusService")
@mock.patch("learn.services.course_service.CourseService")
def test_patch_user_not_enrolled(
    course_service_mock, member_status_service_mock, factories, client, api_helpers
):
    user = factories.EnterpriseUserFactory()
    course_slug = "abc"
    course = mock.Mock(slug=course_slug)
    course_service_mock.return_value.get_value.return_value = course
    member_status_service_mock.get.return_value = None

    response = client.patch(
        f"/api/v1/library/courses/slug/member_statuses/{user.id}",
        headers=api_helpers.json_headers(user),
    )

    assert response.status_code == 404


@mock.patch("learn.services.course_member_status_service.CourseMemberStatusService")
@mock.patch("learn.services.course_service.CourseService")
def test_patch_no_body(
    course_service_mock,
    member_status_service_mock,
    factories,
    client,
    api_helpers,
):
    user = factories.EnterpriseUserFactory()

    course_slug = "abc"
    course = mock.Mock(slug=course_slug)
    course_service_mock.return_value.get_value.return_value = course

    member_status = learn_factories.CourseMemberStatusFactory(
        user_id=user.id,
        course_slug=course_slug,
        status=course_member_status.MemberStatus.IN_PROGRESS,
    )
    member_status_service_mock.create.return_value = member_status
    member_status_service_mock.update.side_effect = ValueError("Invalid status")

    response = client.patch(
        f"/api/v1/library/courses/slug/member_statuses/{user.id}",
        headers=api_helpers.json_headers(user),
    )

    assert response.status_code == 400


@mock.patch("learn.services.course_member_status_service.CourseMemberStatusService")
@mock.patch("learn.services.course_service.CourseService")
def test_patch_invalid_status(
    course_service_mock,
    member_status_service_mock,
    factories,
    client,
    api_helpers,
):
    user = factories.EnterpriseUserFactory()

    course_slug = "abc"
    course = mock.Mock(slug=course_slug)
    course_service_mock.return_value.get_value.return_value = course

    member_status = learn_factories.CourseMemberStatusFactory(
        user_id=user.id,
        course_slug=course_slug,
        status=course_member_status.MemberStatus.IN_PROGRESS,
    )
    member_status_service_mock.create.return_value = member_status
    member_status_service_mock.update.side_effect = ValueError("Invalid status")

    response = client.patch(
        f"/api/v1/library/courses/slug/member_statuses/{user.id}",
        headers=api_helpers.json_headers(user),
        data=json.dumps({"status": "lsdkvlvlvfkdmva;"}),
    )

    assert response.status_code == 400


@mock.patch("learn.services.course_member_status_service.CourseMemberStatusService")
@mock.patch("learn.services.course_service.CourseService")
def test_patch_valid_status(
    course_service_mock,
    member_status_service_mock,
    factories,
    client,
    api_helpers,
):
    user = factories.EnterpriseUserFactory()

    course_slug = "abc"
    course = mock.Mock(slug=course_slug)
    course_service_mock.return_value.get_value.return_value = course

    member_status = learn_factories.CourseMemberStatusFactory(
        user_id=user.id,
        course_slug=course_slug,
        status=course_member_status.MemberStatus.IN_PROGRESS,
    )
    member_status_service_mock.create.return_value = member_status
    member_status_service_mock.update.return_value = member_status

    response = client.patch(
        f"/api/v1/library/courses/slug/member_statuses/{user.id}",
        headers=api_helpers.json_headers(user),
        data=json.dumps({"status": "completed"}),
    )

    assert response.status_code == 200


def test_delete_marketplace_user(default_user, client, api_helpers):
    response = client.delete(
        "/api/v1/library/courses/slug/member_statuses/1",
        headers=api_helpers.json_headers(default_user),
    )

    assert response.status_code == 403


def test_delete_user_mismatch(factories, client, api_helpers):
    user1 = factories.EnterpriseUserFactory()
    user2 = factories.EnterpriseUserFactory()

    response = client.delete(
        f"/api/v1/library/courses/slug/member_statuses/{user1.id}",
        headers=api_helpers.json_headers(user2),
    )

    assert response.status_code == 404


@mock.patch("learn.services.course_service.CourseService")
def test_delete_no_course(course_service_mock, factories, client, api_helpers):
    user = factories.EnterpriseUserFactory()
    course_service_mock.return_value.get_value.return_value = None

    response = client.delete(
        f"/api/v1/library/courses/slug/member_statuses/{user.id}",
        headers=api_helpers.json_headers(user),
    )

    assert response.status_code == 404


@mock.patch("learn.services.course_member_status_service.CourseMemberStatusService")
@mock.patch("learn.services.course_service.CourseService")
def test_delete_user_not_enrolled(
    course_service_mock, member_status_service_mock, factories, client, api_helpers
):
    user = factories.EnterpriseUserFactory()
    course = mock.Mock(id="abc")
    course_service_mock.return_value.get_value.return_value = course
    member_status_service_mock.get.return_value = None

    response = client.delete(
        f"/api/v1/library/courses/slug/member_statuses/{user.id}",
        headers=api_helpers.json_headers(user),
    )

    assert response.status_code == 404


@mock.patch("learn.services.course_member_status_service.CourseMemberStatusService")
@mock.patch("learn.services.course_service.CourseService")
def test_valid_delete(
    course_service_mock,
    member_status_service_mock,
    factories,
    client,
    api_helpers,
):
    user = factories.EnterpriseUserFactory()

    course_slug = "asdf"
    course = mock.Mock(slug=course_slug)
    course_service_mock.return_value.get_value.return_value = course

    member_status = learn_factories.CourseMemberStatusFactory(
        user_id=user.id,
        course_slug=course_slug,
        status=course_member_status.MemberStatus.IN_PROGRESS,
    )
    member_status_service_mock.get.return_value = member_status

    response = client.delete(
        f"/api/v1/library/courses/slug/member_statuses/{user.id}",
        headers=api_helpers.json_headers(user),
    )

    assert response.status_code == 204
    member_status_service_mock.get.assert_called_with(
        user_id=user.id, course_slug=course_slug
    )
    member_status_service_mock.delete.assert_called_with(member_status)
