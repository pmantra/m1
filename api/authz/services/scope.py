from typing import List

from authn.domain.model import User
from authz.models.rbac import AuthzScope, AuthzUserScope
from storage.connection import db


def user_has_any_scope(user: User, scopes: List[str]) -> bool:
    if not scopes:
        return True

    return bool(
        db.session.query(AuthzUserScope)
        .join(AuthzScope, AuthzUserScope.scope_id == AuthzScope.id)
        .filter(AuthzUserScope.user_id == user.id, AuthzScope.name.in_(scopes))
        .count()
    )
