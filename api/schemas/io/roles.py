from authz.models.roles import Capability, Role, role_capability
from storage.connection import db

from .sorting import sorted_by


@sorted_by("object_type", "method")
def _export_capabilities():  # type: ignore[no-untyped-def] # Function is missing a return type annotation
    return [
        dict(
            object_type=c.object_type, method=c.method, roles=[r.name for r in c.roles]
        )
        for c in Capability.query
    ]


def export():  # type: ignore[no-untyped-def] # Function is missing a return type annotation
    return dict(
        roles=sorted([r.name for r in Role.query]), capabilities=_export_capabilities()
    )


def restore(data):  # type: ignore[no-untyped-def] # Function is missing a type annotation
    # Create the many-to-many mapping for later
    capability_roles = {
        (c["object_type"], c["method"]): {*c["roles"]} for c in data["capabilities"]
    }
    # Bulk insert the data
    db.session.bulk_insert_mappings(Role, [{"name": r} for r in data["roles"]])
    db.session.bulk_insert_mappings(Capability, data["capabilities"])
    # Get the data into mappings we can use against the `capability_roles`
    # Query individual columns so we're not loading in the whole ORM object (much faster)
    capabilities_by_key = {
        (c.object_type, c.method): c.id
        for c in db.session.query(
            Capability.id, Capability.object_type, Capability.method
        ).all()
    }
    roles_by_name = {r.name: r.id for r in db.session.query(Role.id, Role.name).all()}
    # Re-map the relationships using a chain so we only iterate twice
    # (once to build, once to insert)
    roles_capabilities = []
    for key, rolenames in capability_roles.items():
        role_ids = {roles_by_name[n] for n in roles_by_name.keys() & rolenames}
        if role_ids:
            c_id = capabilities_by_key[key]
            roles_capabilities.extend(
                ({"capability_id": c_id, "role_id": rid} for rid in role_ids)
            )
    # Create the relationships and explode the chain for the parameter mapping
    db.session.execute(role_capability.insert(), [*roles_capabilities])
