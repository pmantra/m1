from typing import Tuple

from .base import AdminCategory, AdminViewT, AuthenticatedMenuLink
from .models.marketing import TextCopyView
from .models.schedules import ScheduledMaintenanceView


def get_views() -> Tuple[AdminViewT, ...]:
    return (
        ScheduledMaintenanceView.factory(category=AdminCategory.DEV.value),  # type: ignore[arg-type] # Argument "category" to "factory" of "MavenAdminView" has incompatible type "str"; expected "Optional[AdminCategory]"
        TextCopyView.factory(category=AdminCategory.DEV.value),  # type: ignore[arg-type] # Argument "category" to "factory" of "MavenAdminView" has incompatible type "str"; expected "Optional[AdminCategory]"
    )


def get_links() -> Tuple[AuthenticatedMenuLink, ...]:
    return ()
