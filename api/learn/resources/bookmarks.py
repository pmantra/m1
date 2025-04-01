from flask import make_response
from httpproblem import Problem

from common.services.api import EnterpriseResource
from learn.schemas.bookmarks import SavedResourcesSchema
from learn.services.bookmarks import BookmarksService
from models.marketing import Resource


class MemberSavedContentLibraryResource(EnterpriseResource):
    def __init__(self) -> None:
        self.saved_resources_schema = SavedResourcesSchema()
        self.bookmarks_service = BookmarksService()
        super().__init__()

    def get(self):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        self._user_is_enterprise_else_403()
        member_resources = self.bookmarks_service.get_saved_resources(self.user.id)
        json = self.saved_resources_schema.dump({"saved_resources": member_resources})

        return make_response(json, 200)


class MemberSavedContentResource(EnterpriseResource):
    def __init__(self) -> None:
        self.bookmarks_service = BookmarksService()
        super().__init__()

    def post(self, url_slug):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        self._user_is_enterprise_else_403()
        resource = Resource.get_public_published_resource_by_slug(url_slug)
        if resource is None:
            raise Problem(404, detail=f"Article with slug '{url_slug}', not found")

        member_resource = self.bookmarks_service.get_bookmark(
            user_id=self.user.id, resource=resource
        )
        if not member_resource:
            self.bookmarks_service.save_bookmark(
                user_id=self.user.id, resource=resource
            )

        return {"success": True}

    def delete(self, url_slug):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        self._user_is_enterprise_else_403()
        resource = Resource.get_public_published_resource_by_slug(url_slug)
        if resource is None:
            raise Problem(404)

        self.bookmarks_service.delete_bookmark(user_id=self.user.id, resource=resource)

        return {"success": True}
