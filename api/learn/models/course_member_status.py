import enum

import sqlalchemy

from models import base


class MemberStatus(str, enum.Enum):
    NOT_STARTED = "not_started"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"


class CourseMemberStatus(base.TimeLoggedModelBase):
    __tablename__ = "course_member_status"
    __table_args__ = (sqlalchemy.PrimaryKeyConstraint("user_id", "course_slug"),)

    user_id = sqlalchemy.Column(
        sqlalchemy.Integer, sqlalchemy.ForeignKey("user.id"), nullable=False
    )
    course_slug = sqlalchemy.Column(sqlalchemy.String(length=50), nullable=False)
    status = sqlalchemy.Column(sqlalchemy.String(length=50), nullable=False)

    @sqlalchemy.orm.validates("status")
    def validate_status(self, _, status):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        if status not in set(MemberStatus):
            raise ValueError(f"Invalid status {status}")
        return status
