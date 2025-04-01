from typing import Tuple

from .base import AdminCategory, AdminViewT, AuthenticatedMenuLink
from .models.enterprise import (
    BusinessLeadView,
    InboundPhoneNumberView,
    IncentiveFulfillmentView,
    IncentiveOrganizationView,
    IncentiveView,
    InviteView,
    OrganizationEligibilityFieldView,
    OrganizationEmailDomainView,
    OrganizationEmployeeView,
    OrganizationModuleExtensionView,
    OrganizationView,
    UserOrganizationEmployeeView,
)
from .models.tracks import ClientTrackView, MemberTrackView, TracksExtensionView
from .models.users import AssignableAdvocateView


class EligibilityAdminLink(AuthenticatedMenuLink):
    create_permission = "create:eligibility-admin"
    read_permission = "read:eligibility-admin"
    edit_permission = "edit:eligibility-admin"
    delete_permission = "delete:eligibility-admin"


def get_views() -> Tuple[AdminViewT, ...]:
    return (
        AssignableAdvocateView.factory(
            category=AdminCategory.ENTERPRISE.value, name="Advocate-Patient Assignment"  # type: ignore[arg-type] # Argument "category" to "factory" of "MavenAdminView" has incompatible type "str"; expected "Optional[AdminCategory]"
        ),
        BusinessLeadView.factory(category=AdminCategory.ENTERPRISE.value),  # type: ignore[arg-type] # Argument "category" to "factory" of "MavenAdminView" has incompatible type "str"; expected "Optional[AdminCategory]"
        IncentiveView.factory(category=AdminCategory.ENTERPRISE.value),  # type: ignore[arg-type] # Argument "category" to "factory" of "MavenAdminView" has incompatible type "str"; expected "Optional[AdminCategory]"
        IncentiveOrganizationView.factory(category=AdminCategory.ENTERPRISE.value),  # type: ignore[arg-type] # Argument "category" to "factory" of "MavenAdminView" has incompatible type "str"; expected "Optional[AdminCategory]"
        IncentiveFulfillmentView.factory(category=AdminCategory.ENTERPRISE.value),  # type: ignore[arg-type] # Argument "category" to "factory" of "MavenAdminView" has incompatible type "str"; expected "Optional[AdminCategory]"
        InviteView.factory(category=AdminCategory.ENTERPRISE.value),  # type: ignore[arg-type] # Argument "category" to "factory" of "MavenAdminView" has incompatible type "str"; expected "Optional[AdminCategory]"
        OrganizationEmployeeView.factory(category=AdminCategory.ENTERPRISE.value),  # type: ignore[arg-type] # Argument "category" to "factory" of "MavenAdminView" has incompatible type "str"; expected "Optional[AdminCategory]"
        UserOrganizationEmployeeView.factory(category=AdminCategory.ENTERPRISE.value),  # type: ignore[arg-type] # Argument "category" to "factory" of "MavenAdminView" has incompatible type "str"; expected "Optional[AdminCategory]"
        OrganizationModuleExtensionView.factory(
            category=AdminCategory.ENTERPRISE.value  # type: ignore[arg-type] # Argument "category" to "factory" of "MavenAdminView" has incompatible type "str"; expected "Optional[AdminCategory]"
        ),
        OrganizationEligibilityFieldView.factory(
            category=AdminCategory.ENTERPRISE.value  # type: ignore[arg-type] # Argument "category" to "factory" of "MavenAdminView" has incompatible type "str"; expected "Optional[AdminCategory]"
        ),
        OrganizationEmailDomainView.factory(category=AdminCategory.ENTERPRISE.value),  # type: ignore[arg-type] # Argument "category" to "factory" of "MavenAdminView" has incompatible type "str"; expected "Optional[AdminCategory]"
        OrganizationView.factory(category=AdminCategory.ENTERPRISE.value),  # type: ignore[arg-type] # Argument "category" to "factory" of "MavenAdminView" has incompatible type "str"; expected "Optional[AdminCategory]"
        MemberTrackView.factory(category=AdminCategory.ENTERPRISE.value),  # type: ignore[arg-type] # Argument "category" to "factory" of "MavenAdminView" has incompatible type "str"; expected "Optional[AdminCategory]"
        ClientTrackView.factory(category=AdminCategory.ENTERPRISE.value),  # type: ignore[arg-type] # Argument "category" to "factory" of "MavenAdminView" has incompatible type "str"; expected "Optional[AdminCategory]"
        TracksExtensionView.factory(
            category=AdminCategory.ENTERPRISE.value,  # type: ignore[arg-type] # Argument "category" to "factory" of "MavenAdminView" has incompatible type "str"; expected "Optional[AdminCategory]"
            name="Tracks Extension",
            endpoint="tracks_extension",
        ),
        InboundPhoneNumberView.factory(
            category=AdminCategory.ENTERPRISE.value,  # type: ignore[arg-type] # Argument "category" to "factory" of "MavenAdminView" has incompatible type "str"; expected "Optional[AdminCategory]"
            name="Phone Support",
        ),
    )


# test
def get_links() -> Tuple[AuthenticatedMenuLink, ...]:
    return (
        EligibilityAdminLink(
            name="Eligibility Admin",
            category=AdminCategory.ENTERPRISE.value,
            url="/eligibility-admin/",
        ),
    )
