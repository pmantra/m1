from datetime import datetime
from typing import Optional

from flask import make_response, request
from httpproblem import Problem

from common.services import api
from learn.models.course_member_status import MemberStatus
from learn.services.course_member_status_service import CourseMemberStatusService
from learn.services.course_service import CourseService


class UserCoursesResource(api.EnterpriseResource, api.PermissionedUserResource):
    def get(self, user_id: int):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        self._user_is_enterprise_else_403()
        self._user_or_404(user_id)

        try:
            limit = self.__get_limit(request.args)
        except ValueError:
            raise Problem(400, "limit must be a positive integer.")

        course_member_statuses_in_progress = CourseMemberStatusService.list(
            user_id, member_status=MemberStatus.IN_PROGRESS
        )

        courses_by_slug = CourseService().get_values(
            [
                course_member_status.course_slug
                for course_member_status in course_member_statuses_in_progress
            ]
        )

        for course_member_status in course_member_statuses_in_progress:
            courses_by_slug.get(  # type: ignore[union-attr] # Item "None" of "Optional[Course]" has no attribute "member_status"
                course_member_status.course_slug
            ).member_status = course_member_status.status

        courses = CourseService.populate_viewed_at(
            list(courses_by_slug.values()), user_id
        )

        courses.sort(
            key=lambda course: max(
                course.chapters, key=lambda chapter: chapter.viewed_at or datetime.min
            ).viewed_at
            or datetime.min,
            reverse=True,
        )

        if limit:
            courses = courses[0:limit]

        return make_response(
            {"courses": [course.to_response_dict() for course in courses]}, 200
        )

    @staticmethod
    def __get_limit(request_args) -> Optional[int]:  # type: ignore[no-untyped-def] # Function is missing a type annotation for one or more arguments
        if "limit" in request_args:
            limit = int(request_args.get("limit"))
            if limit < 1:
                raise ValueError()
            return limit
        return None
