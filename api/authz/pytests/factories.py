import factory
from factory.alchemy import SQLAlchemyModelFactory

from authz.models.rbac import (
    AuthzPermission,
    AuthzRole,
    AuthzRolePermission,
    AuthzScope,
    AuthzUserRole,
    AuthzUserScope,
)
from conftest import BaseMeta


class AuthzScopeFactory(SQLAlchemyModelFactory):
    class Meta(BaseMeta):
        model = AuthzScope
        sqlalchemy_get_or_create = ("name",)

    name = factory.Faker("name")
    description = factory.Faker("word")


class AuthzRoleFactory(SQLAlchemyModelFactory):
    class Meta(BaseMeta):
        model = AuthzRole
        sqlalchemy_get_or_create = ("name",)

    name = factory.Faker("name")
    description = factory.Faker("word")


class AuthzPermissionFactory(SQLAlchemyModelFactory):
    class Meta(BaseMeta):
        model = AuthzPermission
        sqlalchemy_get_or_create = ("name",)

    name = factory.Faker("name")
    description = factory.Faker("word")


class AuthzRolePermissionFactory(SQLAlchemyModelFactory):
    class Meta(BaseMeta):
        model = AuthzRolePermission
        sqlalchemy_get_or_create = (
            "role_id",
            "permission_id",
        )

    role_id = factory.Sequence(lambda integer: integer + 1)
    permission_id = factory.Sequence(lambda integer: integer + 1)


class AuthzUserRoleFactory(SQLAlchemyModelFactory):
    class Meta(BaseMeta):
        model = AuthzUserRole
        sqlalchemy_get_or_create = (
            "user_id",
            "role_id",
        )

    user_id = factory.Sequence(lambda integer: integer + 1)
    role_id = factory.Sequence(lambda integer: integer + 1)


class AuthzUserScopeFactory(SQLAlchemyModelFactory):
    class Meta(BaseMeta):
        model = AuthzUserScope
        sqlalchemy_get_or_create = (
            "user_id",
            "scope_id",
        )

    user_id = factory.Sequence(lambda integer: integer + 1)
    scope_id = factory.Sequence(lambda integer: integer + 1)
