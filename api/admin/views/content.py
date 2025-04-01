import enum
from typing import Tuple

from .base import AdminCategory, AdminViewT, AuthenticatedMenuLink
from .models.enterprise import (
    AssessmentLifecycleView,
    AssessmentView,
    HDCAssessmentView,
    NeedsAssessmentView,
)
from .models.marketing import (
    ConnectedContentFieldView,
    IosNonDeeplinkUrlView,
    PopularTopicView,
    ResourceView,
    TagView,
    VirtualEventCategoryTrackView,
    VirtualEventCategoryView,
    VirtualEventView,
)
from .models.programs import CareProgramView, EnrollmentView, ModuleView, PhaseView
from .models.risk_flags import RiskFlagView


class DashViewType(str, enum.Enum):
    DASH = "Dashboard"
    PROMPT = "Prompt"


def get_views() -> Tuple[AdminViewT, ...]:
    return (
        AssessmentLifecycleView.factory(category=AdminCategory.CONTENT.value),  # type: ignore[arg-type] # Argument "category" to "factory" of "MavenAdminView" has incompatible type "str"; expected "Optional[AdminCategory]"
        AssessmentView.factory(category=AdminCategory.CONTENT.value),  # type: ignore[arg-type] # Argument "category" to "factory" of "MavenAdminView" has incompatible type "str"; expected "Optional[AdminCategory]"
        HDCAssessmentView.factory(category=AdminCategory.CONTENT.value),  # type: ignore[arg-type] # Argument "category" to "factory" of "MavenAdminView" has incompatible type "str"; expected "Optional[AdminCategory]"
        RiskFlagView.factory(category=AdminCategory.CONTENT.value),  # type: ignore[arg-type] # Argument "category" to "factory" of "MavenAdminView" has incompatible type "str"; expected "Optional[AdminCategory]"
        CareProgramView.factory(category=AdminCategory.CONTENT.value),  # type: ignore[arg-type] # Argument "category" to "factory" of "MavenAdminView" has incompatible type "str"; expected "Optional[AdminCategory]"
        ConnectedContentFieldView.factory(category=AdminCategory.CONTENT.value),  # type: ignore[arg-type] # Argument "category" to "factory" of "MavenAdminView" has incompatible type "str"; expected "Optional[AdminCategory]"
        EnrollmentView.factory(category=AdminCategory.CONTENT.value),  # type: ignore[arg-type] # Argument "category" to "factory" of "MavenAdminView" has incompatible type "str"; expected "Optional[AdminCategory]"
        ModuleView.factory(category=AdminCategory.CONTENT.value),  # type: ignore[arg-type] # Argument "category" to "factory" of "MavenAdminView" has incompatible type "str"; expected "Optional[AdminCategory]"
        NeedsAssessmentView.factory(category=AdminCategory.CONTENT.value),  # type: ignore[arg-type] # Argument "category" to "factory" of "MavenAdminView" has incompatible type "str"; expected "Optional[AdminCategory]"
        PhaseView.factory(category=AdminCategory.CONTENT.value),  # type: ignore[arg-type] # Argument "category" to "factory" of "MavenAdminView" has incompatible type "str"; expected "Optional[AdminCategory]"
        PopularTopicView.factory(category=AdminCategory.CONTENT.value),  # type: ignore[arg-type] # Argument "category" to "factory" of "MavenAdminView" has incompatible type "str"; expected "Optional[AdminCategory]"
        ResourceView.factory(category=AdminCategory.CONTENT.value),  # type: ignore[arg-type] # Argument "category" to "factory" of "MavenAdminView" has incompatible type "str"; expected "Optional[AdminCategory]"
        VirtualEventView.factory(category=AdminCategory.CONTENT.value),  # type: ignore[arg-type] # Argument "category" to "factory" of "MavenAdminView" has incompatible type "str"; expected "Optional[AdminCategory]"
        VirtualEventCategoryView.factory(category=AdminCategory.CONTENT.value),  # type: ignore[arg-type] # Argument "category" to "factory" of "MavenAdminView" has incompatible type "str"; expected "Optional[AdminCategory]"
        VirtualEventCategoryTrackView.factory(category=AdminCategory.CONTENT.value),  # type: ignore[arg-type] # Argument "category" to "factory" of "MavenAdminView" has incompatible type "str"; expected "Optional[AdminCategory]"
        TagView.factory(category=AdminCategory.CONTENT.value),  # type: ignore[arg-type] # Argument "category" to "factory" of "MavenAdminView" has incompatible type "str"; expected "Optional[AdminCategory]"
        IosNonDeeplinkUrlView.factory(category=AdminCategory.CONTENT.value),  # type: ignore[arg-type] # Argument "category" to "factory" of "MavenAdminView" has incompatible type "str"; expected "Optional[AdminCategory]"
    )


def get_links() -> Tuple[AuthenticatedMenuLink, ...]:
    return ()
