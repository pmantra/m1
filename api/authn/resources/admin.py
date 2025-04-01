from __future__ import annotations

import flask_admin
import sqlalchemy
from sqlalchemy import orm

from admin.views import base
from authn.domain import repository
from storage import connection
from storage.repository.base import BaseRepository
from utils.log import logger

log = logger(__name__)


def init_admin(
    admin: flask_admin.Admin, *, session: orm.scoping.ScopedSession = None  # type: ignore[assignment] # Incompatible default for argument "session" (default has type "None", argument has type "scoped_session")
) -> flask_admin.Admin:
    admin.add_views(
        IdentityProviderView.factory(
            session=session,  # type: ignore[arg-type] # Argument "session" to "factory" of "MavenAdminView" has incompatible type "Optional[scoped_session]"; expected "Optional[RoutingSQLAlchemy]"
            category=base.AdminCategory.AUTHN,
        ),
        IdentityProviderFieldAliasView.factory(
            session=session,  # type: ignore[arg-type] # Argument "session" to "factory" of "MavenAdminView" has incompatible type "Optional[scoped_session]"; expected "Optional[RoutingSQLAlchemy]"
            category=base.AdminCategory.AUTHN,
        ),
        UserExternalIdentityView.factory(
            session=session,  # type: ignore[arg-type] # Argument "session" to "factory" of "MavenAdminView" has incompatible type "Optional[scoped_session]"; expected "Optional[RoutingSQLAlchemy]"
            category=base.AdminCategory.AUTHN,
        ),
        UserAuthView.factory(
            session=session,  # type: ignore[arg-type] # Argument "session" to "factory" of "MavenAdminView" has incompatible type "Optional[scoped_session]"; expected "Optional[RoutingSQLAlchemy]"
            category=base.AdminCategory.AUTHN,
        ),
    )
    return admin


class BaseClassicalMappedView(base.MavenAuditedView):
    repo: BaseRepository

    @classmethod
    def instantiate_mapping(cls):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        if sqlalchemy.inspect(cls.repo.model, raiseerr=False) is None:
            mapper = orm.mapper(cls.repo.model, cls.repo.table)
            cls.repo.model.__mapper__ = mapper

    @classmethod
    def factory(  # type: ignore[no-untyped-def] # Function is missing a return type annotation #type: ignore[no-untyped-def] # Function is missing a type annotation for one or more arguments
        cls,
        *,
        session: orm.scoping.ScopedSession = None,  # type: ignore[override,assignment] # Argument 1 of "factory" is incompatible with supertype "MavenAdminView"; supertype defines the argument type as "Optional[RoutingSQLAlchemy]" #type: ignore[assignment] # Incompatible default for argument "session" (default has type "None", argument has type "scoped_session")
        category: base.AdminCategory = None,  # type: ignore[override,assignment] # Argument 2 of "factory" is incompatible with supertype "MavenAdminView"; supertype defines the argument type as "Optional[AdminCategory]" #type: ignore[assignment] # Incompatible default for argument "category" (default has type "None", argument has type "AdminCategory")
        name: str = None,  # type: ignore[override,assignment] # Argument 3 of "factory" is incompatible with supertype "MavenAdminView"; supertype defines the argument type as "Optional[str]" #type: ignore[assignment] # Incompatible default for argument "name" (default has type "None", argument has type "str")
        endpoint: str = None,  # type: ignore[override,assignment] # Argument 4 of "factory" is incompatible with supertype "MavenAdminView"; supertype defines the argument type as "Optional[str]" #type: ignore[assignment] # Incompatible default for argument "endpoint" (default has type "None", argument has type "str")
        **kwargs,
    ):
        cls.instantiate_mapping()
        return cls(
            cls.repo.model,
            session or connection.db.session,
            category=category,
            name=name,
            endpoint=endpoint,
            **kwargs,
        )


class IdentityProviderView(BaseClassicalMappedView):
    read_permission = "read:identity-provider"
    delete_permission = "delete:identity-provider"
    create_permission = "create:identity-provider"
    edit_permission = "edit:identity-provider"

    repo = repository.IdentityProviderRepository  # type: ignore[assignment] # Incompatible types in assignment (expression has type "Type[IdentityProviderRepository]", base class "BaseClassicalMappedView" defined the type as "BaseRepository[Any]")
    can_view_details = True
    column_display_pk = True
    column_filters = ("id", "name")
    form_excluded_columns = ("created_at", "modified_at")


class IdentityProviderFieldAliasView(BaseClassicalMappedView):
    read_permission = "read:identity-provider-field-alias"
    delete_permission = "delete:identity-provider-field-alias"
    create_permission = "create:identity-provider-field-alias"
    edit_permission = "edit:identity-provider-field-alias"

    repo = repository.IDPFieldAliasRepository  # type: ignore[assignment] # Incompatible types in assignment (expression has type "Type[IDPFieldAliasRepository]", base class "BaseClassicalMappedView" defined the type as "BaseRepository[Any]")
    can_view_details = True
    form_excluded_columns = ("created_at", "modified_at")
    column_filters = ("identity_provider_id", "field", "alias")


class UserExternalIdentityView(BaseClassicalMappedView):
    read_permission = "read:user-external-identity"
    delete_permission = "delete:user-external-identity"
    create_permission = "create:user-external-identity"
    edit_permission = "edit:user-external-identity"

    repo = repository.UserExternalIdentityRepository  # type: ignore[assignment] # Incompatible types in assignment (expression has type "Type[UserExternalIdentityRepository]", base class "BaseClassicalMappedView" defined the type as "BaseRepository[Any]")
    can_view_details = True
    column_display_pk = True
    column_filters = (
        "user_id",
        "identity_provider_id",
        "external_user_id",
        "external_organization_id",
        "unique_corp_id",
        "id",
    )
    form_excluded_columns = ("created_at", "modified_at")


class UserAuthView(BaseClassicalMappedView):
    read_permission = "read:identity-provider-field-alias-tab"
    create_permission = "create:identity-provider-field-alias-tab"
    edit_permission = "edit:identity-provider-field-alias-tab"
    delete_permission = "delete:identity-provider-field-alias-tab"

    repo = repository.UserAuthRepository  # type: ignore[assignment] # Incompatible types in assignment (expression has type "Type[UserAuthRepository]", base class "BaseClassicalMappedView" defined the type as "BaseRepository[Any]")
    can_view_details = True
    column_filters = ("user_id",)
    form_widget_args = {
        "id": {"readonly": True},
    }
    column_list = ("id", "user_id", "external_id", "refresh_token")
    form_columns = ("id", "user_id", "external_id", "refresh_token")
