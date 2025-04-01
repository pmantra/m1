import copy
from typing import List, Optional

import sqlalchemy
from sqlalchemy import dialects

from learn.models import course
from learn.models.course_member_status import CourseMemberStatus, MemberStatus
from storage.connection import db


class CourseMemberStatusService:
    @staticmethod
    def get(user_id: int, course_slug: str) -> CourseMemberStatus:
        return CourseMemberStatus.query.filter_by(
            user_id=user_id, course_slug=course_slug
        ).one_or_none()

    @staticmethod
    def list(
        user_id: int, member_status: Optional[MemberStatus] = None
    ) -> List[CourseMemberStatus]:
        kwargs = {"user_id": user_id}
        if member_status:
            kwargs["status"] = member_status  # type: ignore[assignment] # Incompatible types in assignment (expression has type "MemberStatus", target has type "int")
        return CourseMemberStatus.query.filter_by(**kwargs).all()

    @staticmethod
    def create(user_id: int, course_slug: str) -> CourseMemberStatus:
        status = CourseMemberStatus(
            user_id=user_id, course_slug=course_slug, status=MemberStatus.IN_PROGRESS
        )
        # Prevent race condition of two concurrent calls
        insert = dialects.mysql.insert(CourseMemberStatus, bind=db.engine).values(
            status.to_dict()
        )
        # Not a big deal if this overwrites created_at
        insert = insert.on_duplicate_key_update(**status.to_dict())
        db.session.execute(insert)
        db.session.commit()

        return status

    @staticmethod
    def update(
        member_status: CourseMemberStatus, new_status_value: str
    ) -> CourseMemberStatus:
        if member_status.status == MemberStatus.COMPLETED:
            raise ValueError("Cannot change status from completed")
        if new_status_value == MemberStatus.NOT_STARTED:
            raise ValueError("Cannot change status to not started")
        # For an accurate return value and validating the status
        member_status.status = new_status_value

        update = (
            sqlalchemy.update(CourseMemberStatus)  # type: ignore[arg-type] # Argument 1 to "Update" has incompatible type "Type[CourseMemberStatus]"; expected "Union[str, Selectable]"
            .where(CourseMemberStatus.user_id == member_status.user_id)
            .where(CourseMemberStatus.course_slug == member_status.course_slug)
            .values({"status": new_status_value})
        )
        db.session.execute(update)
        db.session.commit()

        return member_status

    @staticmethod
    def delete(member_status: CourseMemberStatus):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        db.session.delete(member_status)
        # If member status has already been deleted, a warning will occur but no error
        db.session.commit()

    @staticmethod
    def set_statuses_on_courses(
        courses: List[course.Course], user_id: int
    ) -> List[course.Course]:
        if len(courses) == 0:
            return courses

        courses_with_statuses = copy.deepcopy(courses)
        statuses_by_course_slug = {
            status.course_slug: status
            for status in CourseMemberStatus.query.filter(
                CourseMemberStatus.user_id == user_id,
                CourseMemberStatus.course_slug.in_(
                    [course.slug for course in courses_with_statuses]
                ),
            )
        }
        for member_course in courses_with_statuses:
            member_course.set_status(statuses_by_course_slug.get(member_course.slug))
        return courses_with_statuses
