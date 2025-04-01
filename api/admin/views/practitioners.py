from typing import Tuple

from .base import AdminCategory, AdminViewT, AuthenticatedMenuLink
from .models.careteam_assignment import CareTeamAssignmentView
from .models.in_state_matching import InStateMatchingView
from .models.medications import MedicationView
from .models.messaging import MessageProductView
from .models.practitioner import (
    CAMemberTransitionsView,
    CAMemberTransitionTemplateView,
    CareTeamControlCenterView,
    PractitionerReplacementView,
    PractitionerSpecialtyBulkUpdateView,
    PractitionerToolsView,
)
from .models.products import ProductView
from .models.questionnaires import (
    AnswerView,
    QuestionnaireView,
    QuestionSetView,
    QuestionView,
)
from .models.users import (
    CertificationView,
    CharacteristicView,
    LanguageView,
    NeedCategoryView,
    NeedsView,
    PractitionerInviteView,
    PractitionerProfileView,
    ScheduleEventView,
    SpecialtyKeywordView,
    SpecialtyView,
    VerticalAccessByTrackView,
    VerticalGroupVersionView,
    VerticalGroupView,
    VerticalView,
)


def get_views() -> Tuple[AdminViewT, ...]:
    views = (
        CertificationView.factory(category=AdminCategory.PRACTITIONER.value),  # type: ignore[arg-type] # Argument "category" to "factory" of "MavenAdminView" has incompatible type "str"; expected "Optional[AdminCategory]"
        CharacteristicView.factory(category=AdminCategory.PRACTITIONER.value),  # type: ignore[arg-type] # Argument "category" to "factory" of "MavenAdminView" has incompatible type "str"; expected "Optional[AdminCategory]"
        LanguageView.factory(category=AdminCategory.PRACTITIONER.value),  # type: ignore[arg-type] # Argument "category" to "factory" of "MavenAdminView" has incompatible type "str"; expected "Optional[AdminCategory]"
        MessageProductView.factory(category=AdminCategory.PRACTITIONER.value),  # type: ignore[arg-type] # Argument "category" to "factory" of "MavenAdminView" has incompatible type "str"; expected "Optional[AdminCategory]"
        PractitionerInviteView.factory(category=AdminCategory.PRACTITIONER.value),  # type: ignore[arg-type] # Argument "category" to "factory" of "MavenAdminView" has incompatible type "str"; expected "Optional[AdminCategory]"
        PractitionerProfileView.factory(category=AdminCategory.PRACTITIONER.value),  # type: ignore[arg-type] # Argument "category" to "factory" of "MavenAdminView" has incompatible type "str"; expected "Optional[AdminCategory]"
        ProductView.factory(category=AdminCategory.PRACTITIONER.value),  # type: ignore[arg-type] # Argument "category" to "factory" of "MavenAdminView" has incompatible type "str"; expected "Optional[AdminCategory]"
        ScheduleEventView.factory(category=AdminCategory.PRACTITIONER.value),  # type: ignore[arg-type] # Argument "category" to "factory" of "MavenAdminView" has incompatible type "str"; expected "Optional[AdminCategory]"
        SpecialtyKeywordView.factory(category=AdminCategory.PRACTITIONER.value),  # type: ignore[arg-type] # Argument "category" to "factory" of "MavenAdminView" has incompatible type "str"; expected "Optional[AdminCategory]"
        SpecialtyView.factory(category=AdminCategory.PRACTITIONER.value),  # type: ignore[arg-type] # Argument "category" to "factory" of "MavenAdminView" has incompatible type "str"; expected "Optional[AdminCategory]"
        PractitionerSpecialtyBulkUpdateView(
            category=AdminCategory.PRACTITIONER.value,
            name="Practitioner/Specialty Bulk Update",
            endpoint="practitioner_specialty_bulk_update",
        ),
        VerticalGroupView.factory(category=AdminCategory.PRACTITIONER.value),  # type: ignore[arg-type] # Argument "category" to "factory" of "MavenAdminView" has incompatible type "str"; expected "Optional[AdminCategory]"
        VerticalGroupVersionView.factory(category=AdminCategory.PRACTITIONER.value),  # type: ignore[arg-type] # Argument "category" to "factory" of "MavenAdminView" has incompatible type "str"; expected "Optional[AdminCategory]"
        VerticalView.factory(category=AdminCategory.PRACTITIONER.value),  # type: ignore[arg-type] # Argument "category" to "factory" of "MavenAdminView" has incompatible type "str"; expected "Optional[AdminCategory]"
        VerticalAccessByTrackView.factory(category=AdminCategory.PRACTITIONER.value),  # type: ignore[arg-type] # Argument "category" to "factory" of "MavenAdminView" has incompatible type "str"; expected "Optional[AdminCategory]"
        NeedsView.factory(category=AdminCategory.PRACTITIONER.value),  # type: ignore[arg-type] # Argument "category" to "factory" of "MavenAdminView" has incompatible type "str"; expected "Optional[AdminCategory]"
        NeedCategoryView.factory(category=AdminCategory.PRACTITIONER.value),  # type: ignore[arg-type] # Argument "category" to "factory" of "MavenAdminView" has incompatible type "str"; expected "Optional[AdminCategory]"
        QuestionnaireView.factory(category=AdminCategory.PRACTITIONER.value),  # type: ignore[arg-type] # Argument "category" to "factory" of "MavenAdminView" has incompatible type "str"; expected "Optional[AdminCategory]"
        QuestionSetView.factory(category=AdminCategory.PRACTITIONER.value),  # type: ignore[arg-type] # Argument "category" to "factory" of "MavenAdminView" has incompatible type "str"; expected "Optional[AdminCategory]"
        QuestionView.factory(category=AdminCategory.PRACTITIONER.value),  # type: ignore[arg-type] # Argument "category" to "factory" of "MavenAdminView" has incompatible type "str"; expected "Optional[AdminCategory]"
        AnswerView.factory(category=AdminCategory.PRACTITIONER.value),  # type: ignore[arg-type] # Argument "category" to "factory" of "MavenAdminView" has incompatible type "str"; expected "Optional[AdminCategory]"
        MedicationView.factory(category=AdminCategory.PRACTITIONER.value),  # type: ignore[arg-type] # Argument "category" to "factory" of "MavenAdminView" has incompatible type "str"; expected "Optional[AdminCategory]"
        CareTeamAssignmentView.factory(category=AdminCategory.PRACTITIONER.value),  # type: ignore[arg-type] # Argument "category" to "factory" of "MavenAdminView" has incompatible type "str"; expected "Optional[AdminCategory]"
        InStateMatchingView.factory(
            category=AdminCategory.PRACTITIONER.value,  # type: ignore[arg-type] # Argument "category" to "factory" of "MavenAdminView" has incompatible type "str"; expected "Optional[AdminCategory]"
            endpoint="in_state_match",
            name="In State Match",
        ),
        PractitionerReplacementView(
            category=AdminCategory.PRACTITIONER.value,
            name="Replace Practitioner in Care Teams",
            url="replace_practitioner",
        ),
        CAMemberTransitionsView(
            category=AdminCategory.PRACTITIONER.value,
            endpoint="ca_member_transitions",
            name="CA-Member Transitions",
        ),
        # We're supplying `category=None` so that this admin view isn't listed under any of the existing
        # top-level menu dropdowns. By default, it will appear as its own top-level menu item when we
        # do this. As such, we provide `menu_class_name="hidden"` so that this top-level menu item
        # is hidden, which gives us what we want: a flask admin view that we can redirect to/from,
        # but without it appearing in the top-level menu dropdowns.
        CAMemberTransitionTemplateView.factory(
            category=None,  # type: ignore[arg-type] # Argument "category" to "factory" of "MavenAdminView" has incompatible type "None"; expected "AdminCategory"
            endpoint="ca_member_transition_templates",
            menu_class_name="hidden",
        ),
    )

    return views


def get_links() -> Tuple[AuthenticatedMenuLink, ...]:
    return (
        PractitionerToolsView(
            name="Practitioner Tools",
            category=AdminCategory.PRACTITIONER.value,
            url="/admin/practitioner_tools",
        ),
        CareTeamControlCenterView(
            name="Care Team Control Center",
            category=AdminCategory.PRACTITIONER.value,
            url="/admin/care_team_control_center",
        ),
    )
