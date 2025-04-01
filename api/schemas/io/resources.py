from dataclasses import asdict

from models.enterprise import BMS_ORDER_RESOURCE
from models.marketing import (
    ConnectedContentField,
    Resource,
    ResourceConnectedContent,
    ResourceTrack,
    ResourceTrackPhase,
    Tag,
    resource_modules,
    resource_phases,
    tags_resources,
)
from models.programs import Module, Phase
from storage.connection import db

from .sorting import sorted_by


@sorted_by("resource_type", "slug")
def export():  # type: ignore[no-untyped-def] # Function is missing a return type annotation
    return [
        dict(
            resource_type=r.resource_type.value,
            content_type=r.content_type,
            published_at=r.published_at,
            body=r.body,
            title=r.title,
            subhead=r.subhead,
            slug=r.slug,
            modules=[m.name for m in r.allowed_modules],
            phases=[dict(module=p.module.name, phase=p.name) for p in r.allowed_phases],
            connected_content_fields=[
                {"name": rcc.field.name, "value": rcc.value}
                for rcc in r.connected_content_fields
            ],
            tags=[t.name for t in r.tags],
            tracks=[t.value for t in r.allowed_track_names],
            track_phases=[asdict(n) for n in r.allowed_track_phase_names],
            webflow_url=r.webflow_url,
        )
        for r in Resource.query
        if (not r.allowed_organizations or r.slug == BMS_ORDER_RESOURCE)
    ]


def restore(rr):  # type: ignore[no-untyped-def] # Function is missing a type annotation
    # Get the required relational data
    module_id_by_name = {
        m.name: m.id for m in db.session.query(Module.name, Module.id).all()
    }
    tag_id_by_name = {t.name: t.id for t in db.session.query(Tag.name, Tag.id).all()}
    phase_id_by_key = {
        (p.module_name, p.name): p.id
        for p in db.session.query(
            Phase.id, Phase.name, Module.name.label("module_name")
        )
        .select_from(Phase)
        .join(Module, Phase.module_id == Module.id)
        .all()
    }
    connected_content_id_by_name = {
        cc.name: cc.id
        for cc in db.session.query(
            ConnectedContentField.name, ConnectedContentField.id
        ).all()
    }
    assert (
        module_id_by_name and tag_id_by_name and connected_content_id_by_name
    ), "Resources require Modules, Tags, and ConnectedContentFields to be restored!"
    # Create the resources
    db.session.bulk_insert_mappings(Resource, rr)
    resources_by_key = {
        (r.resource_type.value, r.slug): r.id
        for r in db.session.query(
            Resource.resource_type, Resource.slug, Resource.id
        ).all()
    }
    # Build out the relationships
    resources_modules = []
    resources_tracks = []
    resources_phases = []
    resources_track_phases = []
    resources_tags = []
    resource_connected_content = []
    for r in rr:
        resource_id = resources_by_key[(r["resource_type"], r["slug"])]
        resources_modules.extend(
            {"resource_id": resource_id, "module_id": module_id_by_name[n]}
            for n in r["modules"]
        )
        resources_tracks.extend(
            {"resource_id": resource_id, "track_name": n} for n in r["modules"]
        )

        resources_phases.extend(
            {
                "resource_id": resource_id,
                "phase_id": phase_id_by_key[(p["module"], p["phase"])],
            }
            for p in r["phases"]
        )
        resources_track_phases.extend(
            {
                "resource_id": resource_id,
                "track_name": p["module"],
                "phase_name": p["phase"],
            }
            for p in r["phases"]
        )
        resources_tags.extend(
            {"resource_id": resource_id, "tag_id": tag_id_by_name[n]} for n in r["tags"]
        )
        resource_connected_content.extend(
            rcc.update(
                resource_id=resource_id,
                connected_content_field_id=connected_content_id_by_name[rcc["name"]],
            )
            or rcc
            for rcc in r["connected_content_fields"]
        )
    # Create the relationships
    db.session.execute(resource_modules.insert(), resources_modules)
    db.session.execute(resource_phases.insert(), resources_phases)
    db.session.execute(tags_resources.insert(), resources_tags)
    db.session.bulk_insert_mappings(
        ResourceConnectedContent, resource_connected_content
    )

    db.session.bulk_insert_mappings(ResourceTrack, resources_tracks)
    db.session.bulk_insert_mappings(ResourceTrackPhase, resources_track_phases)
