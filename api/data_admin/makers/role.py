from authz.models.roles import ROLE_NAMES, Capability, Role
from data_admin.maker_base import _MakerBase
from storage.connection import db


class RoleMaker(_MakerBase):
    def create_object(self, spec):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        role = Role.query.filter(Role.name == spec.get("role_name")).one_or_none()
        if role:
            return role

        if spec.get("role_name") not in ROLE_NAMES:
            raise ValueError(
                f"Invalid Role Name {spec.get('role_name')} provided for role fixture."
            )

        role = Role(
            name=spec.get("role_name"),
            capabilities=[
                Capability(
                    object_type=capability.get("object_type"),
                    method=capability.get("method"),
                )
                for capability in spec.get("capabilities")
            ],
        )
        db.session.add(role)
        return role
