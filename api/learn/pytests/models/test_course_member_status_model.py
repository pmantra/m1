import pytest

from learn.models import course_member_status


def test_status_validation(factories):
    user = factories.EnterpriseUserFactory()

    with pytest.raises(ValueError):
        course_member_status.CourseMemberStatus(
            user_id=user.id,
            course_slug="abc",
            status="unsupported-status",
        )


def test_valid_status(factories):
    user = factories.EnterpriseUserFactory()

    enrollment = course_member_status.CourseMemberStatus(
        user_id=user.id,
        course_slug="abc",
        status=course_member_status.MemberStatus.IN_PROGRESS.value,
    )

    assert enrollment.user_id == user.id
    assert enrollment.course_slug == "abc"
    assert enrollment.status == course_member_status.MemberStatus.IN_PROGRESS.value
