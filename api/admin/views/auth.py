from __future__ import annotations

from typing import Optional

import cachetools.func
import ddtrace
import flask_login as login

from authz.models.rbac import AllowedList
from authz.utils.permissions import get_permission_dictionary
from common.constants import Environment
from storage.connection import db
from utils.log import logger

log = logger(__name__)


class AdminAuth:
    # By default, only expose views to the admin_all capability
    required_capability = None

    can_delete = True
    can_create = True
    can_edit = True

    read_permission: Optional[str] = None
    delete_permission: Optional[str] = None
    create_permission: Optional[str] = None
    edit_permission: Optional[str] = None
    _is_allowed: Optional[bool] = None

    @ddtrace.tracer.wrap()
    def is_accessible(self) -> bool:
        if not login.current_user.is_authenticated:
            return False

        if Environment.current() == Environment.LOCAL:
            return True

        permissions_dict = self.rbac_permissions()
        if permissions_dict and (
            self.view_is_allowed or "qa" in Environment.current().name.lower()
        ):
            self.can_edit = permissions_dict.get(self.edit_permission, False)
            self.can_delete = permissions_dict.get(self.delete_permission, False)
            self.can_create = permissions_dict.get(self.create_permission, False)

            return permissions_dict[self.read_permission]
        else:
            user_has_capabilities = self.user_has_capabilities()
            return user_has_capabilities

    @property
    @ddtrace.tracer.wrap()
    def view_is_allowed(self) -> bool:
        return self.get_allowed_list().get(self.__class__.__name__, False)

    @staticmethod
    @cachetools.func.ttl_cache(maxsize=None, ttl=30 * 60 * 60)  # 15 mins
    def get_allowed_list() -> dict[str, bool]:
        allowed_list = db.session.query(
            AllowedList.view_name, AllowedList.is_rbac_allowed
        ).all()
        return {a.view_name: a.is_rbac_allowed for a in allowed_list}

    @ddtrace.tracer.wrap()
    def user_has_capabilities(self) -> bool:
        cap_names = frozenset(c.object_type for c in login.current_user.capabilities())

        if "admin_all" in cap_names:
            return True

        if (
            "admin_all_without_access_control" in cap_names
            and self.required_capability
            not in {
                "admin_access_control",
                "admin_organization",
                "admin_practitioner_contract",
            }
        ):
            return True

        if self.required_capability and self.required_capability in cap_names:
            return True

        return False

    @ddtrace.tracer.wrap()
    def rbac_permissions(self) -> Optional[dict]:
        crud_permissions = (
            self.create_permission,
            self.read_permission,
            self.edit_permission,
            self.delete_permission,
        )

        crud_permissions = [  # type: ignore[assignment] # Incompatible types in assignment (expression has type "List[str]", variable has type "Tuple[Optional[str], Optional[str], Optional[str], Optional[str]]")
            a for a in crud_permissions if a
        ]  # we don't want the permissions that are not defined.
        if any(crud_permissions):
            permissions_dict = get_permission_dictionary(
                login.current_user.id, *crud_permissions
            )
            return permissions_dict
        return None

    @ddtrace.tracer.wrap()
    def log_permissions_differences(
        self, has_capabilities: bool, permissions_dict: dict
    ) -> None:
        """
        if they are opposite of each other. We should capture the cases:
         1. User had capability to access the view before, and now they don't have rbac permissions.
         2. User did not have capability, but now they have rbac permissions.
        """
        if not (has_capabilities ^ permissions_dict.get(self.read_permission)):
            return
        current_class = self.__class__.__name__
        message = f"RBAC discrepancies: user with id: {login.current_user.id}. View name: {current_class}."
        data = {
            "user_id": login.current_user.id,
            "view_name": current_class,
            **permissions_dict,
            "env": Environment.current().name,
        }
        log.info(message, data=data)
