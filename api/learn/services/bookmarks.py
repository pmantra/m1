from typing import List

import sqlalchemy
from sqlalchemy.dialects import mysql

from learn.models import bookmarks
from learn.services import article_thumbnail_service, article_title_service
from learn.utils.resource_utils import populate_estimated_read_times_and_media_types
from models import marketing
from storage.connection import db
from utils.log import logger

log = logger(__name__)


class BookmarksService:
    def delete_bookmark(self, user_id: int, resource: marketing.Resource) -> bool:
        member_resource = self.get_bookmark(user_id=user_id, resource=resource)
        if member_resource:
            db.session.delete(member_resource)
            db.session.commit()
            return True

        return False

    def get_saved_resources(
        self, user_id: int
    ) -> List[article_thumbnail_service.ResourceWithThumbnail]:
        saved_resources_query = (
            db.session.query(marketing.Resource)
            .join(bookmarks.MemberSavedResource)
            .filter(bookmarks.MemberSavedResource.member_id == user_id)
            .filter(
                marketing.Resource.resource_type
                == marketing.ResourceTypes.ENTERPRISE.name
            )
            .filter(marketing.Resource.published_at <= sqlalchemy.func.now())
            .order_by(bookmarks.MemberSavedResource.created_at.desc())
        )

        resources = saved_resources_query.all()

        resources = populate_estimated_read_times_and_media_types(resources)

        title_service = article_title_service.LocalizedArticleTitleService()
        title_service.populate_remote_resource_titles(resources)

        return article_thumbnail_service.ArticleThumbnailService().get_thumbnails_for_resources(
            resources
        )

    # WARNING: This method is never used to return a bookmark back to a user, so it may not populate the thumbnail of
    # the bookmark in all cases. Use at your own risk.
    def get_bookmark(
        self, user_id: int, resource: marketing.Resource
    ) -> bookmarks.MemberSavedResource:
        member_resource = (
            db.session.query(bookmarks.MemberSavedResource)
            .filter(
                bookmarks.MemberSavedResource.member_id == user_id,
                bookmarks.MemberSavedResource.resource_id == resource.id,
            )
            .one_or_none()
        )
        return member_resource

    def save_bookmark(
        self, user_id: int, resource: marketing.Resource
    ) -> bookmarks.MemberSavedResource:
        saved_member_resource = bookmarks.MemberSavedResource(
            member_id=user_id, resource_id=resource.id
        )

        # this handles a race condition where two calls are made concurrently. in this case, we just want to update
        # the existing record, rather than failing.
        insert = mysql.insert(bookmarks.MemberSavedResource, bind=db.engine).values(
            saved_member_resource.to_dict()
        )
        insert = insert.on_duplicate_key_update(
            **{
                column.name: getattr(insert.inserted, column.name)
                for column in bookmarks.MemberSavedResource.__table__.columns
            }
        )
        db.session.execute(insert)
        db.session.commit()

        # mysql does not support getting the updated row from an insert, so we
        # have to make a separate query to get the new row
        return self.get_bookmark(user_id, resource)
