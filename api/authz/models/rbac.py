from typing import TYPE_CHECKING

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, String, func
from sqlalchemy.orm import relationship

from models import base

# These will cause a circular imports at run-time but are valid for static type-checking
if TYPE_CHECKING:
    from models.enterprise import Organization, OrganizationEmployee  # noqa: F401
    from models.programs import CareProgram, CareProgramPhase, Module  # noqa: F401
    from models.tracks import TrackConfig  # noqa: F401


class AuthzRole(base.ModelBase):
    __tablename__ = "authz_role"

    id = Column(Integer, primary_key=True)
    name = Column(String(64), nullable=False, unique=True)
    description = Column(String(256))
    created_at = Column(
        DateTime,
        default=func.now(),
        doc="When this record was created.",
    )
    modified_at = Column(
        DateTime,
        default=func.now(),
        onupdate=func.now(),
        doc="When this record was modified.",
    )

    def __repr__(self) -> str:
        return f"<Authz_Role [{self.name}]>"

    __str__ = __repr__


class AuthzUserRole(base.ModelBase):
    __tablename__ = "authz_user_role"

    user_id = Column(Integer, ForeignKey("user.id"), primary_key=True)
    role_id = Column(Integer, ForeignKey("authz_role.id"), primary_key=True)
    created_at = Column(
        DateTime,
        default=func.now(),
        doc="When this record was created.",
    )
    modified_at = Column(
        DateTime,
        default=func.now(),
        onupdate=func.now(),
        doc="When this record was modified.",
    )

    user = relationship("User", primaryjoin="AuthzUserRole.user_id==User.id")
    role = relationship("AuthzRole", primaryjoin="AuthzUserRole.role_id==AuthzRole.id")

    def __repr__(self) -> str:
        return f"<Authz_User_Role [{self.user_id}, {self.role_id}]>"

    __str__ = __repr__


class AuthzScope(base.ModelBase):
    __tablename__ = "authz_scope"

    id = Column(Integer, primary_key=True)
    name = Column(String(64), nullable=False, unique=True)
    description = Column(String(256))
    created_at = Column(DateTime, default=func.now(), doc="When the record is created")
    modified_at = Column(
        DateTime,
        default=func.now(),
        onupdate=func.now(),
        doc="When the record is updated",
    )

    def __repr__(self) -> str:
        return f"Authz_Scope [{self.name}]"

    __str__ = __repr__


class AuthzUserScope(base.ModelBase):
    __tablename__ = "authz_user_scope"

    user_id = Column(Integer, ForeignKey("user.id"), primary_key=True)
    scope_id = Column(Integer, ForeignKey("authz_scope.id"), primary_key=True)
    created_at = Column(
        DateTime,
        default=func.now(),
        doc="When the record was created.",
    )
    modified_at = Column(
        DateTime,
        default=func.now(),
        onupdate=func.now(),
        doc="When the record was modified.",
    )

    user = relationship("User", primaryjoin="AuthzUserScope.user_id==User.id")
    scope = relationship(
        "AuthzScope", primaryjoin="AuthzUserScope.scope_id==AuthzScope.id"
    )

    def __repr__(self) -> str:
        return f"Authz_User_Scope [{self.user_id},{self.scope_id}]"

    __str__ = __repr__


class AuthzPermission(base.ModelBase):
    __tablename__ = "authz_permission"

    id = Column(Integer, primary_key=True)
    name = Column(String(64), nullable=False, unique=True)
    description = Column(String(256))
    created_at = Column(
        DateTime,
        default=func.now(),
        doc="When this record was created.",
    )
    modified_at = Column(
        DateTime,
        default=func.now(),
        onupdate=func.now(),
        doc="When this record was modified.",
    )

    def __repr__(self) -> str:
        return f"<Authz_Permission [{self.name}]>"

    __str__ = __repr__


class AuthzRolePermission(base.ModelBase):
    __tablename__ = "authz_role_permission"

    role_id = Column(Integer, ForeignKey("authz_role.id"), primary_key=True)
    permission_id = Column(Integer, ForeignKey("authz_permission.id"), primary_key=True)
    created_at = Column(
        DateTime,
        default=func.now(),
        doc="When this record was created.",
    )
    modified_at = Column(
        DateTime,
        default=func.now(),
        onupdate=func.now(),
        doc="When this record was modified.",
    )

    role = relationship(
        "AuthzRole", primaryjoin="AuthzRolePermission.role_id==AuthzRole.id"
    )
    permission = relationship(
        "AuthzPermission",
        primaryjoin="AuthzRolePermission.permission_id==AuthzPermission.id",
    )

    def __repr__(self) -> str:
        return f"<Authz_Role_Permission [{self.role_id}, {self.permission_id}]>"

    __str__ = __repr__


class AllowedList(base.ModelBase):
    __tablename__ = "allowed_list"

    view_name = Column(String(50), primary_key=True)
    is_rbac_allowed = Column(Boolean, default=False)
