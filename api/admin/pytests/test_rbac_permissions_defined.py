from unittest.mock import patch

from flask_admin.menu import MenuCategory, MenuLink, MenuView

from admin.factory import create_admin, setup_flask_app
from admin.views.auth import AdminAuth
from admin.views.base import AdminCategory, AuthenticatedMenuLink
from admin.views.models.authz import AllowedListView

base_class_list = {
    "AdminAuditLogMixin",
    "AuthenticatedMenuLink",
    "AuthzUserScopeView" "BaseClassicalMappedView",
    "LogoutLink",
    "MavenAdminView",
    "MavenAuditedView",
    "SoftDeletableView",
}

pending_list = {
    "AddressView",
    "AuthzUserScopeView",
    "BMSShipmentView",
    "BaseClassicalMappedView",
    "CAMemberTransitionTemplateView",
    "InlinePhaseView",
    "ReimbursementWalletGlobalProceduresView",
}


def get_admin_views_and_links_from_menu():
    app = setup_flask_app()
    admin = create_admin(app)
    a_views = set()
    for item in admin._menu:
        if isinstance(item, MenuView):
            a_views.add(item._view)
        elif isinstance(item, MenuLink):
            a_views.add(item)
        elif isinstance(item, MenuCategory):
            for child in item._children:
                if isinstance(child, MenuView):
                    a_views.add(child._view)
                elif isinstance(child, MenuLink):
                    a_views.add(child)
    return a_views


def test_view_can_variables_not_defined():
    admin_views = get_admin_views_and_links_from_menu()
    views_with_can_variables_set_to_false = {
        view.__class__.__name__
        for view in admin_views
        if isinstance(view, AdminAuth)
        and not (view.can_edit and view.can_create and view.can_delete)
    }
    filtered_views_with_missing_permission = (
        views_with_can_variables_set_to_false - pending_list - base_class_list
    )

    assert filtered_views_with_missing_permission == set(), (
        f"Found admin views {filtered_views_with_missing_permission} where some or all of the can_create, can_edit, "
        f"or can_delete are set to False. If you want to restrict an action, DON'T define the corresponding "
        f"permission variables instead; (create_permission, edit_permission, delete_permission)."
        f"Contact core-services if you need assistance"
    )


def test_verify_permissions_defined():
    admin_views = get_admin_views_and_links_from_menu()
    views_with_missing_permission = {
        view.__class__.__name__
        for view in admin_views
        if isinstance(view, AdminAuth)
        and getattr(view, "read_permission", None) is None
    }
    filtered_views_with_missing_permission = (
        views_with_missing_permission - pending_list - base_class_list
    )

    assert filtered_views_with_missing_permission == set(), (
        f"Found admin views {filtered_views_with_missing_permission} with unset permission variable(s).\n"
        f"Please define the permission variable(s) and set up rbac permission for your admin view.\n"
        f"Contact IT to add new permissions."
    )


# If this test is failing, you need to contact core-services, one shouldn't be changing the inheritance for admin auth.
def test_correct_inheritance():
    # this view makes use of all the inheritances from admin auth to adminmixiauditlogging.
    new_view = AllowedListView.factory(category=AdminCategory.AUTHZ.value)
    new_menu_link = AuthenticatedMenuLink("Test")

    # verify admin auth is_accessible function is only called.
    with patch.object(
        AdminAuth, "is_accessible", return_value="is_accessible called from AdminAuth"
    ) as mock_is_accessible:
        result = new_view.is_accessible()
        mock_is_accessible.assert_called_once()
        assert result == "is_accessible called from AdminAuth"

        result = new_menu_link.is_accessible()
        assert mock_is_accessible.call_count == 2
        assert result == "is_accessible called from AdminAuth"
