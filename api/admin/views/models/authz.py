import copy
from typing import Type

import flask_admin
from flask import flash
from flask_admin.babel import gettext
from flask_login import current_user
from wtforms import fields
from wtforms.validators import Email, InputRequired

from admin.views.base import AdminCategory, AdminViewT, MavenAuditedView
from authn.models.user import User
from authz.models.rbac import (
    AllowedList,
    AuthzPermission,
    AuthzRole,
    AuthzRolePermission,
    AuthzScope,
    AuthzUserRole,
    AuthzUserScope,
)
from authz.utils.permissions import get_data_from_model
from models.base import ModelBase
from storage.connection import RoutingSQLAlchemy, db
from utils.log import logger

log = logger(__name__)


class BaseAuthzView(MavenAuditedView):
    read_permission = "read:authz-object"
    edit_permission = "edit:authz-object"
    create_permission = "create:authz-object"
    delete_permission = "delete:authz-object"

    def create_model(self, form: Type[flask_admin.form.BaseForm]) -> Type[ModelBase]:
        model = super().create_model(form)
        model_name = model.__class__.__name__
        log.info(
            f"{model_name} created by user {current_user.id}: "
            f"id={model.id}, name={model.name}"
        )
        return model

    def update_model(
        self,
        form: Type[flask_admin.form.BaseForm],
        model: Type[ModelBase],
    ) -> Type[ModelBase]:
        model_name = model.__class__.__name__
        old_model = copy.copy(model)
        super().update_model(form, model)
        model_diff = _get_model_diff(old_model, model)
        if model_diff:
            log.info(
                f"User {current_user.id} updated {model_name} record with ID {model.id}: {model_diff}"
            )
        return model

    def delete_model(self, model: Type[ModelBase]) -> Type[ModelBase]:
        model_name = model.__class__.__name__

        if model_name == "AuthzRolePermission":
            _log_authz_role_permission_deletion(model)
        elif model_name == "AuthzUserRole":
            _log_authz_user_role_deletion(model)

        return super().delete_model(model)


class AuthzRoleView(BaseAuthzView):
    form_excluded_columns = ("created_at", "modified_at")
    column_list = ("id", "name", "description", "created_at", "modified_at")
    column_sortable_list = ("id", "name", "description", "created_at", "modified_at")
    column_searchable_list = ("id", "name", "description", "created_at", "modified_at")
    column_filters = ("id", "name", "description", "created_at", "modified_at")

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
            AuthzRole,
            session or db.session,
            category=category,
            name=name,
            endpoint=endpoint,
            **kwargs,
        )


class AuthzUserRoleView(BaseAuthzView):
    form_excluded_columns = ("created_at", "modified_at")
    column_list = (
        "user_id",
        "user_email",
        "role_id",
        "role_name",
        "created_at",
        "modified_at",
    )
    form_columns = ("user_id", "role_id")
    column_sortable_list = (
        "user_id",
        "user.email",
        "role_id",
        "role.name",
        "created_at",
        "modified_at",
    )
    column_searchable_list = (
        "user_id",
        "user.email",
        "role_id",
        "role.name",
    )
    column_filters = (
        "user_id",
        "user.email",
        "role_id",
        "role.name",
    )

    # add a column formatter to display user email
    column_formatters = {
        "user_email": lambda v, c, m, p: m.user.email if m.user else None,
        "role_name": lambda v, c, m, p: m.role.name if m.role else None,
    }

    def scaffold_form(self):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        form = super().scaffold_form()
        # add new fields
        form.user_email = fields.StringField(
            "User email", validators=[Email(), InputRequired()]
        )
        form.role_name = fields.StringField("Role name", validators=[InputRequired()])
        # hide the others
        form.user_id = fields.HiddenField()
        form.role_id = fields.HiddenField()
        return form

    def create_model(self, form):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        user_email = form["user_email"].data
        role_name = form["role_name"].data
        err_msgs = []
        user, err = get_data_from_model(User, User.email, user_email)  # type: ignore[arg-type] # Argument 2 to "get_data_from_model" has incompatible type "Column[str]"; expected "Type[Column[Any]]"
        if err:
            err_msgs.append(err)

        role, err = get_data_from_model(AuthzRole, AuthzRole.name, role_name)  # type: ignore[arg-type] # Argument 2 to "get_data_from_model" has incompatible type "Column[str]"; expected "Type[Column[Any]]"
        if err:
            err_msgs.append(err)

        if len(err_msgs):
            msg = " ".join(err_msgs)
            flash(msg, category="error")
            return False

        record = AuthzUserRole.query.filter_by(user_id=user.id, role_id=role.id).first()
        if record:
            flash("Record already present!", category="error")
            return False

        try:
            model = self.model(role_id=role.id, user_id=user.id)
            self.session.add(model)
            self.session.commit()
            log.info(
                f"AuthzUserRole record created by user {current_user.id}. Data: User ID: {user.id}; Role ID: {role.id}, "
                f"Role Name: {role.name}."
            )
        except Exception as e:
            if not self.handle_view_exception(e):
                flash(
                    gettext("Failed to create record. %(error)s", error=str(e)), "error"
                )
            log.error(
                "Record creation failed.",
                errors=e,
            )
            self.session.rollback()
            return False
        return model

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
            AuthzUserRole,
            session or db.session,
            category=category,
            name=name,
            endpoint=endpoint,
            **kwargs,
        )


class AuthzScopeView(BaseAuthzView):
    form_excluded_columns = ("created_at", "modified_at")
    column_list = ("id", "name", "description", "created_at", "modified_at")
    column_sortable_list = ("id", "name", "description", "created_at", "modified_at")
    column_searchable_list = ("id", "name", "description", "created_at", "modified_at")
    column_filters = ("id", "name", "description", "created_at", "modified_at")

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
            AuthzScope,
            session or db.session,
            category=category,
            name=name,
            endpoint=endpoint,
            **kwargs,
        )


class AuthzUserScopeView(MavenAuditedView):
    form_excluded_columns = ("created_at", "modified_at")
    column_list = (
        "user_id",
        "user_email",
        "scope_id",
        "scope_name",
        "created_at",
        "modified_at",
    )
    form_columns = ("user_id", "scope_id")
    column_sortable_list = (
        "user_id",
        "user.email",
        "scope_id",
        "scope.name",
        "created_at",
        "modified_at",
    )
    column_searchable_list = (
        "user_id",
        "user.email",
        "scope_id",
        "scope.name",
    )
    column_filters = (
        "user_id",
        "user.email",
        "scope_id",
        "scope.name",
    )

    # add a column formatter to display user email
    column_formatters = {
        "user_email": lambda value, context, model, col_property: model.user.email
        if model.user
        else None,
        "scope_name": lambda value, context, model, col_property: model.scope.name
        if model.scope
        else None,
    }

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
            AuthzUserScope,
            session or db.session,
            category=category,
            name=name,
            endpoint=endpoint,
            **kwargs,
        )


class AuthzPermissionView(BaseAuthzView):
    form_excluded_columns = ("created_at", "modified_at")
    column_list = ("id", "name", "description", "created_at", "modified_at")
    column_sortable_list = ("id", "name", "description", "created_at", "modified_at")
    column_searchable_list = ("id", "name", "description", "created_at", "modified_at")
    column_filters = ("id", "name", "description", "created_at", "modified_at")

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
            AuthzPermission,
            session or db.session,
            category=category,
            name=name,
            endpoint=endpoint,
            **kwargs,
        )


class AuthzRolePermissionView(BaseAuthzView):
    form_excluded_columns = ("created_at", "modified_at")
    column_list = (
        "role_id",
        "role_name",
        "permission_id",
        "permission_name",
        "created_at",
        "modified_at",
    )
    form_columns = ("role_id", "permission_id")
    column_sortable_list = (
        "role_id",
        "permission_id",
        "created_at",
        "modified_at",
    )
    column_searchable_list = (
        "role_id",
        "role.name",
        "permission_id",
        "permission.name",
    )
    column_filters = (
        "role_id",
        "role.name",
        "permission_id",
        "permission.name",
    )

    # add a column formatter to display permission name and role name
    column_formatters = {
        "permission_name": lambda v, c, m, p: m.permission.name
        if m.permission
        else None,
        "role_name": lambda v, c, m, p: m.role.name if m.role else None,
    }

    def scaffold_form(self):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        form = super().scaffold_form()
        # add new fields
        form.role_name = fields.StringField("Role name", validators=[InputRequired()])
        form.permission_name = fields.StringField(
            "Permission name", validators=[InputRequired()]
        )
        # hide the others
        form.permission_id = fields.HiddenField()
        form.role_id = fields.HiddenField()
        return form

    def create_model(self, form):  # type: ignore[no-untyped-def] # Function is missing a type annotation

        permission_name = form["permission_name"].data
        role_name = form["role_name"].data
        err_msgs = []
        permission, err = get_data_from_model(
            AuthzPermission, AuthzPermission.name, permission_name  # type: ignore[arg-type] # Argument 2 to "get_data_from_model" has incompatible type "Column[str]"; expected "Type[Column[Any]]"
        )
        if err:
            err_msgs.append(err)

        role, err = get_data_from_model(AuthzRole, AuthzRole.name, role_name)  # type: ignore[arg-type] # Argument 2 to "get_data_from_model" has incompatible type "Column[str]"; expected "Type[Column[Any]]"
        if err:
            err_msgs.append(err)

        if len(err_msgs):
            msg = " ".join(err_msgs)
            flash(msg, category="error")
            return False

        record = AuthzRolePermission.query.filter_by(
            permission_id=permission.id, role_id=role.id
        ).first()
        if record:
            flash("Record already present!", category="error")
            return False

        try:

            role = AuthzRole.query.get(role.id)
            if role is None or not all(hasattr(role, attr) for attr in ("id", "name")):
                flash("Failed to create record. Role not found.", "error")
                return False

            permission = AuthzPermission.query.get(permission.id)
            if permission is None or not all(
                hasattr(permission, attr) for attr in ("id", "name")
            ):
                flash("Failed to create record. permission not found.", "error")
                return False

            model = self.model(role_id=role.id, permission_id=permission.id)
            self.session.add(model)
            self.session.commit()

            log.info(
                f"AuthzRolePermission record created by user {current_user.id}. Role ID: {role.id}, "
                f"Role Name: {role.name}; Permission ID: {permission.id}, "
                f"Permission Name: {permission.name}."
            )

            return True
        except Exception as e:
            if not self.handle_view_exception(e):
                flash(
                    gettext("Failed to create record. %(error)s", error=str(e)), "error"
                )
                log.error(f"Record creation failed: {e}")
            self.session.rollback()
            return False

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
            AuthzRolePermission,
            session or db.session,
            category=category,
            name=name,
            endpoint=endpoint,
            **kwargs,
        )


def _get_model_diff(old_model: Type[ModelBase], new_model: Type[ModelBase]) -> dict:
    diff = {}
    for key, value in old_model.__dict__.items():
        if key not in ("id", "created_at", "modified_at"):
            if value != getattr(new_model, key):
                diff[key] = (value, getattr(new_model, key))
    return diff


def _log_authz_role_permission_deletion(model: Type[ModelBase]):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
    by_user_id = current_user.id
    role_id = model.role_id
    role_name = model.role.name if model.role else "role missing"
    permission_id = model.permission_id
    permission_name = (
        model.permission.name if model.permission else "missing permission"
    )

    log.info(
        "AuthzRolePermission record deleted",
        by_user_id=by_user_id,
        role_id=role_id,
        permission_id=permission_id,
        role_name=role_name,
        permission_name=permission_name,
    )


def _log_authz_user_role_deletion(model: Type[ModelBase]):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
    by_user_id = current_user.id
    role_id = model.role_id
    role_name = model.role.name if model.role else "role missing"
    user_id = model.user_id
    log.info(
        "AuthzUserRole record deleted",
        by_user_id=by_user_id,
        role_id=role_id,
        user_id=user_id,
        role_name=role_name,
    )


class AllowedListView(MavenAuditedView):
    read_permission = "read:allowed-list"
    edit_permission = "edit:allowed-list"
    create_permission = "create:allowed-list"
    delete_permission = "delete:allowed-list"

    column_list = ("view_name", "is_rbac_allowed")
    column_sortable_list = ("view_name", "is_rbac_allowed")
    column_searchable_list = ("view_name", "is_rbac_allowed")
    column_filters = ("view_name", "is_rbac_allowed")
    form_columns = ("view_name", "is_rbac_allowed")

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
            AllowedList,
            session or db.session,
            category=category,
            name=name,
            endpoint=endpoint,
            **kwargs,
        )
