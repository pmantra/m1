from __future__ import annotations

from datetime import date, datetime

import ddtrace

from activity import models, repository
from storage.unit_of_work import SQLAlchemyUnitOfWork

__all__ = (
    "get_user_activity_service",
    "UserActivityService",
)


def get_user_activity_service() -> UserActivityService:
    return UserActivityService()


class UserActivityService:
    @staticmethod
    def uow() -> SQLAlchemyUnitOfWork[repository.UserActivityRepository]:
        return SQLAlchemyUnitOfWork(repository.UserActivityRepository)

    @ddtrace.tracer.wrap()
    def create(
        self, *, user_id: int, activity_type: str, activity_date: datetime
    ) -> models.UserActivity:
        with self.uow() as uow:
            user_activity_repository = uow.get_repo(repository.UserActivityRepository)

            # identify existing entries. we'll get rid of these soon
            existing_entries = user_activity_repository.get_by_activity_type(
                user_id=user_id, activity_type=activity_type
            )

            # create a new entry
            user_activity = user_activity_repository.create(
                instance=models.UserActivity(
                    user_id=user_id,
                    activity_type=activity_type,
                    activity_date=activity_date,
                )
            )

            # after creating a new entry, delete the old ones.
            # we only want to keep the latest entry
            for existing_entry in existing_entries:
                user_activity_repository.delete(id=existing_entry.id)

            uow.commit()

            return user_activity

    @ddtrace.tracer.wrap()
    def get(self, *, id: int) -> models.UserActivity | None:
        with self.uow() as uow:
            return uow.get_repo(repository.UserActivityRepository).get(id=id)

    @ddtrace.tracer.wrap()
    def get_by_activity_type(
        self, *, user_id: int, activity_type: str
    ) -> list[models.UserActivity] | None:
        with self.uow() as uow:
            return uow.get_repo(repository.UserActivityRepository).get_by_activity_type(
                user_id=user_id, activity_type=activity_type
            )

    @ddtrace.tracer.wrap()
    def delete_by_user_id(self, *, user_id: int) -> int | None:
        with self.uow() as uow:
            rows_affected = uow.get_repo(
                repository.UserActivityRepository
            ).delete_by_user_id(
                user_id=user_id,
            )
            uow.commit()
            return rows_affected

    @ddtrace.tracer.wrap()
    def get_last_login_date(self, *, user_id: int) -> date | None:
        with self.uow() as uow:
            logins = uow.get_repo(
                repository.UserActivityRepository
            ).get_by_activity_type(
                user_id=user_id,
                activity_type=models.UserActivityType.LAST_LOGIN,
            )
            if not logins:
                return  # type: ignore[return-value] # Return value expected
            last_login = logins[0]
            return last_login.activity_date.date()
