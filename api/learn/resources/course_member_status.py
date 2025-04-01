import flask
import httpproblem

from common.services import api
from learn.services import course_member_status_service, course_service


class CourseMemberStatusesResource(api.EnterpriseResource):
    def post(self, course_slug: str):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        self._user_is_enterprise_else_403()
        course = _get_course_or_404(course_slug)

        status = course_member_status_service.CourseMemberStatusService.create(
            user_id=self.user.id,
            course_slug=course.slug,
        )

        return flask.make_response(status.to_dict(), 200)


class CourseMemberStatusResource(api.EnterpriseResource, api.PermissionedUserResource):
    def patch(self, course_slug: str, user_id: int):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        self._user_is_enterprise_else_403()
        self._user_or_404(user_id)

        course = _get_course_or_404(course_slug)
        status = _get_member_status_or_404(
            user_id=self.user.id, course_slug=course.slug
        )
        patch_body = flask.request.json if flask.request.is_json else {}
        new_status_value = patch_body.get("status", "")
        try:
            status = course_member_status_service.CourseMemberStatusService.update(
                member_status=status,
                new_status_value=new_status_value,
            )
        except ValueError:
            raise httpproblem.Problem(400, message="Invalid or missing status value")

        return flask.make_response(status.to_dict(), 200)

    def delete(self, course_slug: str, user_id: int):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        self._user_is_enterprise_else_403()
        self._user_or_404(user_id)

        course = _get_course_or_404(course_slug)
        status = _get_member_status_or_404(
            user_id=self.user.id, course_slug=course.slug
        )
        course_member_status_service.CourseMemberStatusService.delete(status)

        return flask.Response(status=204)


def _get_course_or_404(course_slug: str):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
    course_svc = course_service.CourseService(preview=False, user_facing=True)
    course = course_svc.get_value(course_slug)
    if not course:
        raise httpproblem.Problem(404, message="Course not found")
    return course


def _get_member_status_or_404(user_id: int, course_slug: str):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
    status = course_member_status_service.CourseMemberStatusService.get(
        user_id=user_id,
        course_slug=course_slug,
    )
    if not status:
        raise httpproblem.Problem(404, message="User not enrolled in course")
    return status
