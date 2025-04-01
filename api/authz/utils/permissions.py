from __future__ import annotations

import json
from typing import Any, MutableMapping, Type

import cachetools.func
import ddtrace
import flask
import flask_login
from flask_login import current_user
from maven.feature_flags import bool_variation
from sqlalchemy import Column

from authn.models.user import User
from authz.models.rbac import AuthzPermission, AuthzRolePermission, AuthzUserRole
from models import base
from storage.connection import db
from utils.log import logger

log = logger(__name__)


def user_is_active_and_authenticated() -> bool:
    """Test whether the user associated to the current session is active and authenticated.

    Returns:
        Whether the user is active and authenticated.
    """
    return current_user.is_active and current_user.is_authenticated


@ddtrace.tracer.wrap()
def user_has_any_permission(user: User, *requires: str, fresh: bool = False) -> bool:
    """Check if the user has any of the required permissions.

    Args:
        user: The logged in User.
        *requires: The required permissions.
        fresh: Whether to prefer the database over the flask session.

    Returns:
        Whether the user has the associated permission.
    """
    if not requires:
        return True

    permissions = get_permission_dictionary(user.id, *requires, fresh=fresh)
    return any(permissions[k] for k in permissions.keys() & set(requires))


@ddtrace.tracer.wrap()
def get_permission_dictionary(
    user_id: int, *requires: str, fresh: bool = False
) -> dict[str, bool]:
    """Get a mapping of permission->bool.

    By default, will grab all associated permissions for the given user ID.

    Notes:
        If given a set of required permissions, we will fill missing permissions with a
        value of `False`.

    Examples:
        >>> given_user_id = 12345  # A User ID with "gitlab-push", "gitlab-merge" permissions
        >>> get_permission_dictionary(12345)
        {"gitlab-push": True, "gitlab-merge": True}
        >>> permissions_to_test = ["gitlab-push", "gitlab-merge", "gitlab-delete-repo"]
        >>> get_permission_dictionary(12345, *permissions_to_test)
        {"gitlab-push": True, "gitlab-merge": True, "gitlab-delete-repo": False}

    """
    # Try to fetch from the session first
    grants = dict.fromkeys(requires, False)
    permissions = None
    # If we've flagged that we can use the session storage,
    #   try fetching from there first.
    flag_value = bool_variation("enable-read-authz-permissions-from-db", default=False)
    fresh = fresh or flag_value
    if not fresh:
        log.info("Reading Authz Permissions from session", flag_value=flag_value)
        permissions = get_permissions_from_session(
            user_id=user_id, session=flask.session
        )
    # If we didn't find permissions in the session, fetch from the DB.
    if permissions is None:
        # Fetch from the db if not present in the session
        log.info("Reading Authz Permissions from DB or cache", flag_value=flag_value)
        if fresh:
            permissions = get_permissions_from_query(user_id=user_id)
        else:
            permissions = get_permissions_from_query_or_cache(user_id=user_id)
        set_permissions_on_session(
            user_id=user_id, session=flask.session, permissions=permissions
        )

    for key in grants:
        if key in permissions:
            grants[key] = True
    return grants


@ddtrace.tracer.wrap()
@cachetools.func.ttl_cache(maxsize=None, ttl=60)  # 1 minute
def get_permissions_from_query_or_cache(user_id: int) -> set[str]:
    """Get all granted permissions for the given user ID from the database.

    Args:
        user_id (int): The user ID to get permissions.

    Returns:
        The assigned permissions for a users, as a set.
    """
    return get_permissions_from_query(user_id)


@ddtrace.tracer.wrap()
def get_permissions_from_query(user_id: int) -> set[str]:
    """Get all granted permissions for the given user ID from the database.

    Args:
        user_id (int): The user ID to get permissions.

    Returns:
        The assigned permissions for a users, as a set.
    """
    log.info("Reading Authz Permissions from DB")
    granted_permissions = (
        db.session.query(AuthzPermission.name)
        .join(
            AuthzRolePermission,
            AuthzPermission.id == AuthzRolePermission.permission_id,
        )
        .join(AuthzUserRole, AuthzRolePermission.role_id == AuthzUserRole.role_id)
        .filter(
            AuthzUserRole.user_id == user_id,
        )
        .all()
    )
    permissions = {p.name for p in granted_permissions}
    return permissions


@ddtrace.tracer.wrap()
def get_permissions_from_session(
    user_id: int, session: MutableMapping[str, str]
) -> set[str] | None:
    """Extract the granted permissions for this user ID from the session.

    Args:
        user_id (int): The user ID to fetch permissions for.
        session (MutableMapping[str, str]): A session mapping.

    Returns:
        The assigned permissions for a user as a set, if any.
    """
    try:
        key = f"{user_id}:permissions"
        # Ensure we fetch fresh permissions if the login is stale / from an old session.
        if not flask_login.login_fresh():
            session.pop(key, None)
            return None

        perms = session.get(key)
        if perms is not None:
            try:
                return {*json.loads(perms)}
            except (ValueError, TypeError):
                log.warning(
                    "Could not parse permissions from session",
                    exc_info=True,
                    key=key,
                    user_id=user_id,
                )
                del session[key]
                return None
        return None
    except RuntimeError:
        # Operating outside of flask request context.
        return None


def set_permissions_on_session(  # type: ignore[no-untyped-def] # Function is missing a return type annotation
    user_id: int, session: MutableMapping[str, str], permissions: set[str]
):
    """Store the permissions for this user in the session.

    Args:
        user_id (int): The user ID to associate permissions with in storage.
        session (MutableMapping[str, str]): A session mapping.
        permissions (set[str]): The associated permissions for the user ID.
    """
    key = f"{user_id}:permissions"

    try:
        session[key] = json.dumps([*permissions])
    except ValueError:
        log.warning(
            "Could not serialize permissions to session",
            exc_info=True,
            key=key,
            user_id=user_id,
        )
    except RuntimeError:
        pass


def get_data_from_model(model: Type[base.ModelBase], attr: Type[Column], value: Any):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
    res, error_message = None, None
    try:
        res = model.query.filter(attr == value).scalar()
        if not res:
            error_message = f"No such {model.__name__} found: {value}."
    except Exception as e:
        logger.error(  # type: ignore[attr-defined] # "Callable[[str, KwArg(Any)], Any]" has no attribute "error"
            f"error occurred while getting data from {model.__name__}. {str(e)}"
        )
        error_message = str(e)

    return res, error_message
