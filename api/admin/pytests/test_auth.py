from unittest import mock

import pytest as pytest

from admin.views.auth import AdminAuth
from authz.models.roles import Capability
from common.constants import Environment


@pytest.mark.parametrize(
    argnames="permission_dict,environment,expected,view_allowed,capabilities",
    argvalues=[
        (
            {
                "read:object": True,
                "edit:object": True,
                "create:object": True,
                "delete:object": True,
            },
            Environment.PRODUCTION,
            True,  # expected
            True,  # view_allowed
            [],
        ),
        (
            {
                "read:object": True,
                "edit:object": True,
                "create:object": True,
                "delete:object": True,
            },
            Environment.QA1,
            True,  # expected
            False,  # view_allowed
            [],
        ),
        (
            {
                "read:object": True,
                "edit:object": True,
                "create:object": True,
                "delete:object": True,
            },
            Environment.PRODUCTION,
            True,  # expected
            False,  # view_allowed
            [Capability(object_type="admin_all")],
        ),
        (
            {
                "read:object": True,
                "edit:object": True,
                "create:object": True,
                "delete:object": True,
            },
            Environment.PRODUCTION,
            False,  # expected
            False,  # view_allowed
            [Capability(object_type="random")],
        ),
        (
            {
                "read:object": False,
                "edit:object": False,
                "create:object": False,
                "delete:object": False,
            },
            Environment.LOCAL,
            True,  # expected
            False,  # view_allowed
            [Capability(object_type="random")],
        ),
    ],
    ids=[
        "view is in allowed list, user has all the permissions, will use rbac",
        "view is NOT in allowed list, environment is qa, will use rbac",
        "view is NOT in allowed list, environment is not qa, will use capabilities",
        "view is NOT in allowed list, environment is not qa, will use capabilities, user doesn't have the capabilities",
        "view is NOT in allowed list, no permission but environment is local, is_accessible will return true",
    ],
)
def test_auth_flow(
    permission_dict,
    environment,
    expected,
    view_allowed,
    capabilities,
    factories,
):
    a = AdminAuth()
    a.read_permission = "read:object"
    a.edit_permission = "edit:object"
    a.create_permission = "create:object"
    a.delete_permission = "delete:object"
    factories.AllowedListFactory.create(
        view_name=a.__class__.__name__, is_rbac_allowed=view_allowed
    )
    # need to clear the cache to have the allowed list return the correct value
    a.get_allowed_list.cache_clear()
    with mock.patch(
        "admin.views.auth.get_permission_dictionary"
    ) as mock_permission, mock.patch(
        "admin.views.auth.Environment.current", return_value=environment
    ), mock.patch(
        "flask_login.current_user",
        is_authenticated=True,
        capabilities=mock.MagicMock(return_value=capabilities),
    ):
        mock_permission.return_value = permission_dict
        assert a.is_accessible() is expected
