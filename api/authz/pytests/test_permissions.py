import pytest

from authz.models.roles import ROLES
from authz.services.permission import add_role_to_user
from authz.utils.permissions import get_permission_dictionary, user_has_any_permission


@pytest.mark.parametrize(
    argnames="permissions,expected",
    argvalues=[
        ([], True),
        (["gitlab-push"], True),
        (["gitlab-push", "gitlab-merge"], True),
        ("gitlab-delete-repo", False),
    ],
    ids=[
        "no permissions",
        "one of the applicable permissions",
        "all of applicable permissions",
        "no applicable permission",
    ],
)
def test_user_has_any_permission(auth_user, permissions, expected):
    assert user_has_any_permission(auth_user, *permissions, fresh=True) == expected


@pytest.mark.parametrize(
    argnames="permissions,expected",
    argvalues=[
        # TODO: https://mavenclinic.atlassian.net/browse/CPFR-769
        # ([], {"gitlab-merge": True, "gitlab-push": True}),
        (["gitlab-push", "gitlab-merge"], {"gitlab-push": True, "gitlab-merge": True}),
        (
            ["gitlab-merge", "gitlab-delete-repo"],
            {"gitlab-merge": True, "gitlab-delete-repo": False},
        ),
        (
            ["gitlab-delete-repo", "some-random-permission"],
            {"gitlab-delete-repo": False, "some-random-permission": False},
        ),
    ],
    ids=[
        # "empty permission list, should return all the permissions user has",
        "user has all the permissions, should be all true",
        "user has some permissions, some would be false, rest true",
        "user has none of the permissions, all should be false",
    ],
)
def test_get_permission_dictionary(auth_user, permissions, expected):
    results = get_permission_dictionary(auth_user.id, *permissions, fresh=True)
    assert results == expected


@pytest.fixture(autouse=True)
def member_role(factories):
    factories.RoleFactory.create(name=ROLES.member)


@pytest.mark.parametrize(
    argnames="role_name,expected",
    argvalues=[
        (None, []),
        ("invalid", []),
        ("member", ["member"]),
    ],
    ids=[
        "no role name",
        "invalid role name",
        "valid role name",
    ],
)
def test_add_role_to_user(auth_user, role_name, expected):
    add_role_to_user(auth_user, role_name)
    role_names = [r.name for r in auth_user.roles]
    for e in expected:
        assert e in role_names
