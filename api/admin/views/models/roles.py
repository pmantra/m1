from typing import Type

from flask_admin.contrib.sqla.ajax import QueryAjaxModelLoader

from admin.views.base import AdminCategory, AdminViewT, MavenAuditedView
from authn.models.user import User
from authz.models.roles import Role
from models.profiles import RoleProfile
from storage.connection import RoutingSQLAlchemy, db


class UserLoaderWithName(QueryAjaxModelLoader):
    def format(self, model):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        if model is None:
            return
        return (
            getattr(model, self.pk),
            f"<User [{model.id}] {model.full_name} {model.email}>",
        )


class RoleView(MavenAuditedView):
    read_permission = "read:role"
    create_permission = "create:role"
    edit_permission = "edit:role"

    form_excluded_columns = ("users",)
    required_capability = "admin_access_control"  # type: ignore[assignment] # Incompatible types in assignment (expression has type "str", base class "AdminAuth" defined the type as "None")

    @classmethod
    def factory(  # type: ignore[no-untyped-def] # Function is missing a type annotation for one or more arguments
        cls: Type[AdminViewT],
        *,
        session: RoutingSQLAlchemy = None,  # type: ignore[assignment] # Incompatible default for argument "session" (default has type "None", argument has type "RoutingSQLAlchemy")
        category: AdminCategory = None,  # type: ignore[assignment] # Incompatible default for argument "category" (default has type "None", argument has type "AdminCategory")
        name: str = None,  # type: ignore[assignment] # Incompatible default for argument "name" (default has type "None", argument has type "str")
        endpoint: str = None,  # type: ignore[assignment] # Incompatible default for argument "endpoint" (default has type "None", argument has type "str")
        **kwargs,
    ) -> AdminViewT:
        return cls(  # type: ignore[call-arg] # Too many arguments for "object" #type: ignore[call-arg] # Unexpected keyword argument "category" for "object" #type: ignore[call-arg] # Unexpected keyword argument "name" for "object" #type: ignore[call-arg] # Unexpected keyword argument "endpoint" for "object"
            Role,
            session or db.session,
            category=category,
            name=name,
            endpoint=endpoint,
            **kwargs,
        )


class RoleProfileView(MavenAuditedView):
    read_permission = "read:role-profile"
    delete_permission = "delete:role-profile"
    create_permission = "create:role-profile"
    edit_permission = "edit:role-profile"

    required_capability = "admin_access_control"  # type: ignore[assignment] # Incompatible types in assignment (expression has type "str", base class "AdminAuth" defined the type as "None")
    column_sortable_list = (("role", "role.name"),)
    column_list = ("user.id", "user.full_name", "user.email", "role")
    column_labels = {"user.id": "User", "user.full_name": "Name", "user.email": "Email"}
    column_filters = (User.username, User.email)

    form_rules = ["user", "role"]
    _form_ajax_refs = None

    @property
    def form_ajax_refs(self):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        if self._form_ajax_refs is None:
            self._form_ajax_refs = {
                "user": UserLoaderWithName(
                    "user",
                    self.session,
                    User,
                    fields=("first_name", "last_name", "username", "email"),
                )
            }
        return self._form_ajax_refs

    @classmethod
    def factory(  # type: ignore[no-untyped-def] # Function is missing a type annotation for one or more arguments
        cls: Type[AdminViewT],
        *,
        session: RoutingSQLAlchemy = None,  # type: ignore[assignment] # Incompatible default for argument "session" (default has type "None", argument has type "RoutingSQLAlchemy")
        category: AdminCategory = None,  # type: ignore[assignment] # Incompatible default for argument "category" (default has type "None", argument has type "AdminCategory")
        name: str = None,  # type: ignore[assignment] # Incompatible default for argument "name" (default has type "None", argument has type "str")
        endpoint: str = None,  # type: ignore[assignment] # Incompatible default for argument "endpoint" (default has type "None", argument has type "str")
        **kwargs,
    ) -> AdminViewT:
        return cls(  # type: ignore[call-arg] # Too many arguments for "object" #type: ignore[call-arg] # Unexpected keyword argument "category" for "object" #type: ignore[call-arg] # Unexpected keyword argument "name" for "object" #type: ignore[call-arg] # Unexpected keyword argument "endpoint" for "object"
            RoleProfile,
            session or db.session,
            category=category,
            name=name,
            endpoint=endpoint,
            **kwargs,
        )
