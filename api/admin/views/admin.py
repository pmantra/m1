from typing import Tuple

import flask_login

from .base import AdminCategory, AdminViewT, AuthenticatedMenuLink
from .models.marketing import URLRedirectPathView, URLRedirectView
from .models.users import HighRiskUsersView


class PaymentToolsLink(AuthenticatedMenuLink):
    read_permission = "read:payment-tools"
    delete_permission = "delete:payment-tools"
    create_permission = "create:payment-tools"
    edit_permission = "edit:payment-tools"

    required_capability = "admin_payment_tools"  # type: ignore[assignment] # Incompatible types in assignment (expression has type "str", base class "AdminAuth" defined the type as "None")


class MarketingToolsLink(AuthenticatedMenuLink):
    read_permission = "read:marketing-tools"
    delete_permission = "delete:marketing-tools"
    create_permission = "create:marketing-tools"
    edit_permission = "edit:marketing-tools"
    required_capability = "admin_marketing_tools"  # type: ignore[assignment] # Incompatible types in assignment (expression has type "str", base class "AdminAuth" defined the type as "None")


class LogoutLink(AuthenticatedMenuLink):
    def is_accessible(self) -> bool:
        return flask_login.current_user.is_authenticated


class BulkMFAMenuLink(AuthenticatedMenuLink):
    read_permission = "read:bulk-practitioner-mfa-tools"
    delete_permission = "delete:bulk-practitioner-mfa-tools"
    create_permission = "create:bulk-practitioner-mfa-tools"
    edit_permission = "edit:bulk-practitioner-mfa-tools"


class DeleteUserMenuLink(AuthenticatedMenuLink):
    read_permission = "read:delete-user"
    delete_permission = "delete:delete-user"
    create_permission = "create:delete-user"
    edit_permission = "edit:delete-user"


class EnterpriseSetupLink(AuthenticatedMenuLink):
    read_permission = "read:enterprise-setup"
    delete_permission = "delete:enterprise-setup"
    create_permission = "create:enterprise-setup"
    edit_permission = "edit:enterprise-setup"


def get_views() -> Tuple[AdminViewT, ...]:
    return (
        HighRiskUsersView.factory(
            name="CC High Risk Users Dashboard",
            endpoint="high_risk_dashboard",
            category=AdminCategory.ADMIN.value,  # type: ignore[arg-type] # Argument "category" to "factory" of "HighRiskUsersView" has incompatible type "str"; expected "Optional[AdminCategory]"
        ),
        URLRedirectPathView.factory(
            name="URL Redirect Path", category=AdminCategory.ADMIN.value  # type: ignore[arg-type] # Argument "category" to "factory" of "MavenAdminView" has incompatible type "str"; expected "Optional[AdminCategory]"
        ),
        URLRedirectView.factory(
            name="URL Redirect", category=AdminCategory.ADMIN.value  # type: ignore[arg-type] # Argument "category" to "factory" of "MavenAdminView" has incompatible type "str"; expected "Optional[AdminCategory]"
        ),
    )


class WalletToolsLink(AuthenticatedMenuLink):
    create_permission = "create:wallet-tools"
    edit_permission = "edit:wallet-tools"
    delete_permission = "delete:wallet-tools"
    read_permission = "read:wallet-tools"


class SubscriptionSetupLink(AuthenticatedMenuLink):
    create_permission = "create:subscription-set-up"
    edit_permission = "edit:subscription-set-up"
    delete_permission = "delete:subscription-set-up"
    read_permission = "read:subscription-set-up"


class AffectedAppointmentsLink(AuthenticatedMenuLink):
    read_permission = "read:affected-appointments"
    delete_permission = "delete:affected-appointments"
    create_permission = "create:affected-appointments"
    edit_permission = "edit:affected-appointments"


def get_links() -> Tuple[AuthenticatedMenuLink, ...]:
    return (
        EnterpriseSetupLink(
            name="Enterprise Setup",
            category=AdminCategory.ADMIN.value,
            url="/admin/enterprise_setup",
        ),
        MarketingToolsLink(
            name="Marketing Tools",
            category=AdminCategory.ADMIN.value,
            url="/admin/marketing_tools",
        ),
        PaymentToolsLink(
            name="Payment Tools",
            category=AdminCategory.ADMIN.value,
            url="/admin/payment_tools",
        ),
        DeleteUserMenuLink(
            name="Delete User",
            category=AdminCategory.ADMIN.value,
            url="/admin/delete_user",
        ),
        WalletToolsLink(
            name="Wallet Tools",
            category=AdminCategory.ADMIN.value,
            url="/admin/wallet_tools",
        ),
        WalletToolsLink(
            name="Direct Payment Tools",
            category=AdminCategory.ADMIN.value,
            url="/admin/direct_payment_tools",
        ),
        BulkMFAMenuLink(
            name="Bulk Practitioner MFA Tools",
            category=AdminCategory.ADMIN.value,
            url="/admin/bulk_practitioner_mfa_tools",
        ),
        AffectedAppointmentsLink(
            name="Affected Appointments",
            category=AdminCategory.ADMIN.value,
            url="/admin/affected_appointments",
        ),
        LogoutLink(
            name="Logout", category=AdminCategory.ADMIN.value, url="/admin/logout"
        ),
    )
