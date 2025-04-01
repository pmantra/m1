from typing import Tuple

from .base import AdminCategory, AdminViewT, AuthenticatedMenuLink
from .models.bms import BMSOrderView, BMSProductView
from .models.member_risk_flags import MemberRiskFlagView
from .models.phone import BlockedPhoneNumberView
from .models.roles import RoleProfileView, RoleView
from .models.users import (
    AddressView,
    AgreementAcceptanceView,
    AgreementView,
    DeviceView,
    EmailDomainDenylistView,
    ExternalIdentityView,
    GDPRDeletionBackupView,
    GDPRUserRequestView,
    MemberPractitionerAssociationView,
    MemberPreferenceView,
    MemberProfileView,
    PreferenceView,
    UserAssetView,
    UserView,
)


def get_views() -> Tuple[AdminViewT, ...]:
    return (
        BlockedPhoneNumberView.factory(category=AdminCategory.USER.value),  # type: ignore[arg-type] # Argument "category" to "factory" of "MavenAdminView" has incompatible type "str"; expected "Optional[AdminCategory]"
        BMSOrderView.factory(category=AdminCategory.USER.value),  # type: ignore[arg-type] # Argument "category" to "factory" of "MavenAdminView" has incompatible type "str"; expected "Optional[AdminCategory]"
        BMSProductView.factory(category=AdminCategory.USER.value),  # type: ignore[arg-type] # Argument "category" to "factory" of "MavenAdminView" has incompatible type "str"; expected "Optional[AdminCategory]"
        DeviceView.factory(category=AdminCategory.USER.value),  # type: ignore[arg-type] # Argument "category" to "factory" of "MavenAdminView" has incompatible type "str"; expected "Optional[AdminCategory]"
        MemberPractitionerAssociationView.factory(category=AdminCategory.USER.value),  # type: ignore[arg-type] # Argument "category" to "factory" of "MavenAdminView" has incompatible type "str"; expected "Optional[AdminCategory]"
        MemberProfileView.factory(category=AdminCategory.USER.value),  # type: ignore[arg-type] # Argument "category" to "factory" of "MavenAdminView" has incompatible type "str"; expected "Optional[AdminCategory]"
        RoleProfileView.factory(category=AdminCategory.USER.value),  # type: ignore[arg-type] # Argument "category" to "factory" of "MavenAdminView" has incompatible type "str"; expected "Optional[AdminCategory]"
        RoleView.factory(category=AdminCategory.USER.value),  # type: ignore[arg-type] # Argument "category" to "factory" of "MavenAdminView" has incompatible type "str"; expected "Optional[AdminCategory]"
        UserView.factory(category=AdminCategory.USER.value),  # type: ignore[arg-type] # Argument "category" to "factory" of "MavenAdminView" has incompatible type "str"; expected "Optional[AdminCategory]"
        MemberRiskFlagView.factory(category=AdminCategory.USER.value),  # type: ignore[arg-type] # Argument "category" to "factory" of "MavenAdminView" has incompatible type "str"; expected "Optional[AdminCategory]"
        AgreementView.factory(category=AdminCategory.USER.value),  # type: ignore[arg-type] # Argument "category" to "factory" of "MavenAdminView" has incompatible type "str"; expected "Optional[AdminCategory]"
        AgreementAcceptanceView.factory(category=AdminCategory.USER.value),  # type: ignore[arg-type] # Argument "category" to "factory" of "MavenAdminView" has incompatible type "str"; expected "Optional[AdminCategory]"
        PreferenceView.factory(category=AdminCategory.USER.value),  # type: ignore[arg-type] # Argument "category" to "factory" of "MavenAdminView" has incompatible type "str"; expected "Optional[AdminCategory]"
        MemberPreferenceView.factory(category=AdminCategory.USER.value),  # type: ignore[arg-type] # Argument "category" to "factory" of "MavenAdminView" has incompatible type "str"; expected "Optional[AdminCategory]"
        ExternalIdentityView.factory(category=AdminCategory.USER.value),  # type: ignore[arg-type] # Argument "category" to "factory" of "MavenAdminView" has incompatible type "str"; expected "Optional[AdminCategory]"
        UserAssetView.factory(category=AdminCategory.USER.value),  # type: ignore[arg-type] # Argument "category" to "factory" of "MavenAdminView" has incompatible type "str"; expected "Optional[AdminCategory]"
        EmailDomainDenylistView.factory(category=AdminCategory.USER.value),  # type: ignore[arg-type] # Argument "category" to "factory" of "MavenAdminView" has incompatible type "str"; expected "Optional[AdminCategory]"
        AddressView.factory(category=None),  # type: ignore[arg-type] # Argument "category" to "factory" of "MavenAdminView" has incompatible type "None"; expected "AdminCategory"
        GDPRDeletionBackupView.factory(category=AdminCategory.USER.value),  # type: ignore[arg-type] # Argument "category" to "factory" of "MavenAdminView" has incompatible type "str"; expected "Optional[AdminCategory]"
        GDPRUserRequestView.factory(category=AdminCategory.USER.value),  # type: ignore[arg-type] # Argument "category" to "factory" of "MavenAdminView" has incompatible type "str"; expected "Optional[AdminCategory]"
    )


def get_links() -> Tuple[AuthenticatedMenuLink, ...]:
    return ()
