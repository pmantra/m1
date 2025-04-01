from typing import Tuple

from .base import AdminCategory, AdminViewT, AuthenticatedMenuLink
from .models.authz import (
    AllowedListView,
    AuthzPermissionView,
    AuthzRolePermissionView,
    AuthzRoleView,
    AuthzUserRoleView,
)


def get_views() -> Tuple[AdminViewT, ...]:
    return (
        AuthzRoleView.factory(category=AdminCategory.AUTHZ.value),  # type: ignore[arg-type] # Argument "category" to "factory" of "MavenAdminView" has incompatible type "str"; expected "Optional[AdminCategory]"
        AuthzUserRoleView.factory(category=AdminCategory.AUTHZ.value),  # type: ignore[arg-type] # Argument "category" to "factory" of "MavenAdminView" has incompatible type "str"; expected "Optional[AdminCategory]"
        AuthzPermissionView.factory(category=AdminCategory.AUTHZ.value),  # type: ignore[arg-type] # Argument "category" to "factory" of "MavenAdminView" has incompatible type "str"; expected "Optional[AdminCategory]"
        AuthzRolePermissionView.factory(category=AdminCategory.AUTHZ.value),  # type: ignore[arg-type] # Argument "category" to "factory" of "MavenAdminView" has incompatible type "str"; expected "Optional[AdminCategory]"
        AllowedListView.factory(category=AdminCategory.AUTHZ.value),  # type: ignore[arg-type] # Argument "category" to "factory" of "MavenAdminView" has incompatible type "str"; expected "Optional[AdminCategory]"
    )


class RBACBulkInsertMenuLink(AuthenticatedMenuLink):
    create_permission = "create:rbac-bulk-insert"
    read_permission = "read:rbac-bulk-insert"
    edit_permission = "edit:rbac-bulk-insert"
    delete_permission = "delete:rbac-bulk-insert"


def get_links() -> Tuple[AuthenticatedMenuLink, ...]:
    return (
        AuthenticatedMenuLink(
            name="Block List",
            category=AdminCategory.AUTHZ.value,
            url="/admin/block_list",
        ),
        RBACBulkInsertMenuLink(
            name="RBAC Bulk Insert",
            category=AdminCategory.AUTHZ.value,
            url="/admin/authz_bulk_insert",
        ),
    )
