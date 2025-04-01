from sqlalchemy import Column, Enum, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import relationship

from models.base import ModelBase, db


class ROLES:
    """
    @see https://gitlab.mvnctl.net/maven/maven/wikis/Add-a-New-Admin-Role
    """

    banned_member = "banned_member"
    member = "member"
    practitioner = "practitioner"
    moderator = "moderator"
    staff = "staff"
    marketing_staff = "marketing_staff"
    payments_staff = "payments_staff"
    producer = "producer"
    superuser = "superuser"
    care_coordinator = "care_coordinator"
    care_coordinator_manager = "care_coordinator_manager"
    program_operations_staff = "program_operations_staff"
    content_admin = "content_admin"
    fertility_clinic_user = "fertility_clinic_user"
    fertility_clinic_billing_user = "fertility_clinic_billing_user"


ROLE_NAMES = [v for k, v in ROLES.__dict__.items() if not k.startswith("_")]

role_capability = db.Table(
    "role_capability",
    Column("role_id", Integer, ForeignKey("role.id")),
    Column("capability_id", Integer, ForeignKey("capability.id")),
    UniqueConstraint("role_id", "capability_id"),
)


class Role(ModelBase):
    __tablename__ = "role"

    id = Column(Integer, primary_key=True)
    name = Column(
        Enum(*ROLE_NAMES, name="role_name"),
        nullable=False,
        default=ROLES.member,
        unique=True,
    )

    capabilities = relationship(
        "Capability", backref="roles", secondary=role_capability
    )
    users = relationship("User", secondary="role_profile", back_populates="roles")

    def __repr__(self) -> str:
        return f"<Role {self.id} [{self.name}]>"

    __str__ = __repr__


class Capability(ModelBase):
    __tablename__ = "capability"
    constraints = (UniqueConstraint("object_type", "method"),)  # type: ignore[assignment] # Incompatible types in assignment (expression has type "Tuple[UniqueConstraint]", base class "ModelBase" defined the type as "Tuple[()]")

    id = Column(Integer, primary_key=True)
    object_type = Column(String(100), nullable=False)
    method = Column(String(100), nullable=False)

    def __repr__(self) -> str:
        return f"<Capability {self.id} [({self.object_type}, {self.method})]>"

    __str__ = __repr__


_role_id_cache = {}


# Note: _role_id_cache will persist between rollbacks, which can lead to undesired
#       behavior during testing
def default_role(role_name):  # type: ignore[no-untyped-def] # Function is missing a type annotation
    def default():  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        if role_name not in _role_id_cache:
            _role_id_cache[role_name] = (
                Role.query.filter(Role.name == role_name).one().id
            )
        return _role_id_cache[role_name]

    return default
