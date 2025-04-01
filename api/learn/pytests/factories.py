import conftest
from learn.models import bookmarks, course_member_status
from pytests import factories


class MemberSavedResourceFactory(factories.SQLAlchemyModelFactory):
    class Meta(conftest.BaseMeta):
        model = bookmarks.MemberSavedResource


class CourseMemberStatusFactory(factories.SQLAlchemyModelFactory):
    class Meta(conftest.BaseMeta):
        model = course_member_status.CourseMemberStatus
