from unittest import mock

import pytest

from authz.pytests.factories import (
    AuthzPermissionFactory,
    AuthzRoleFactory,
    AuthzRolePermissionFactory,
    AuthzScopeFactory,
    AuthzUserRoleFactory,
    AuthzUserScopeFactory,
)


@pytest.fixture(scope="function")
def auth_permission():
    return dict(
        push=AuthzPermissionFactory.create(name="gitlab-push"),
        merge=AuthzPermissionFactory.create(name="gitlab-merge"),
        delete=AuthzPermissionFactory.create(name="gitlab-delete-repo"),
        extra=AuthzPermissionFactory.create(name="random-extra-permission"),
    )


@pytest.fixture(scope="function")
def auth_role():
    return AuthzRoleFactory.create(name="sde-3")


@pytest.fixture(scope="function")
def auth_role_permission(auth_role, auth_permission):
    role_permissions = dict(
        push=AuthzRolePermissionFactory.create(
            role_id=auth_role.id, permission_id=auth_permission["push"].id
        ),
        merge=AuthzRolePermissionFactory.create(
            role_id=auth_role.id, permission_id=auth_permission["merge"].id
        ),
        extra=AuthzRolePermissionFactory.create(
            role_id=auth_role.id, permission_id=auth_permission["extra"].id
        ),
    )
    return role_permissions


@pytest.fixture(scope="function")
def auth_user(auth_user_scope, auth_user_role, auth_role_permission):
    return auth_user_role.user


@pytest.fixture(scope="function")
def auth_user_role(default_user, auth_role):
    return AuthzUserRoleFactory.create(user_id=default_user.id, role_id=auth_role.id)


@pytest.fixture(scope="function")
def auth_user_scope(default_user, auth_scope):
    return AuthzUserScopeFactory.create(
        user_id=default_user.id, scope_id=auth_scope["internal"].id
    )


@pytest.fixture(scope="function")
def auth_scope():
    return dict(
        internal=AuthzScopeFactory.create(name="maven-internal-secrets"),
        external=AuthzScopeFactory.create(name="maven-external-secrets"),
    )


@pytest.fixture(scope="function")
def mock_user_service():
    with mock.patch("authn.domain.service.user.UserService") as m:
        yield m.return_value
