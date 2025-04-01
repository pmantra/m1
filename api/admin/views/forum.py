from typing import Tuple

from .base import AdminCategory, AdminViewT, AuthenticatedMenuLink
from .models.forum import CategoryVersionView, CategoryView, ForumBanView, PostView


def get_views() -> Tuple[AdminViewT, ...]:
    return (
        CategoryVersionView.factory(category=AdminCategory.FORUM.value),  # type: ignore[arg-type] # Argument "category" to "factory" of "MavenAdminView" has incompatible type "str"; expected "Optional[AdminCategory]"
        CategoryView.factory(category=AdminCategory.FORUM.value),  # type: ignore[arg-type] # Argument "category" to "factory" of "MavenAdminView" has incompatible type "str"; expected "Optional[AdminCategory]"
        PostView.factory(category=AdminCategory.FORUM.value),  # type: ignore[arg-type] # Argument "category" to "factory" of "MavenAdminView" has incompatible type "str"; expected "Optional[AdminCategory]"
        ForumBanView.factory(category=AdminCategory.FORUM.value),  # type: ignore[arg-type] # Argument "category" to "factory" of "MavenAdminView" has incompatible type "str"; expected "Optional[AdminCategory]"
    )


def get_links() -> Tuple[AuthenticatedMenuLink, ...]:
    return ()
