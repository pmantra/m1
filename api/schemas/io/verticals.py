from itertools import chain

from models.verticals_and_specialties import (
    Vertical,
    VerticalGroup,
    VerticalGroupVersion,
    vertical_grouping_versions,
    vertical_groupings,
)
from storage.connection import db

from .sorting import sorted_by


@sorted_by("name")
def _export_verticals():  # type: ignore[no-untyped-def] # Function is missing a return type annotation
    return [
        dict(
            name=v.name,
            description=v.description,
            display_name=v.display_name,
            pluralized_display_name=v.pluralized_display_name,
            products=v.products,
            filter_by_state=v.filter_by_state,
            can_prescribe=v.can_prescribe,
        )
        for v in Vertical.query
    ]


def _restore_verticals(vv):  # type: ignore[no-untyped-def] # Function is missing a type annotation
    db.session.add_all([Vertical(**v) for v in vv])


@sorted_by("name")
def _export_vertical_groups():  # type: ignore[no-untyped-def] # Function is missing a return type annotation
    return [
        dict(
            name=g.name,
            title=g.title,
            description=g.description,
            ordering_weight=g.ordering_weight,
            verticals=[v.name for v in g.verticals],
            tracks=[t.value for t in g.allowed_track_names],
        )
        for g in VerticalGroup.query
    ]


def _restore_vertical_groups(gg):  # type: ignore[no-untyped-def] # Function is missing a type annotation
    db.session.add_all(
        [
            VerticalGroup(
                name=g["name"],
                title=g["title"],
                description=g["description"],
                ordering_weight=g["ordering_weight"],
                verticals=Vertical.query.filter(
                    Vertical.name.in_(g["verticals"])
                ).all(),
            )
            for g in gg
        ]
    )


@sorted_by("name")
def _export_vertical_group_versions():  # type: ignore[no-untyped-def] # Function is missing a return type annotation
    return [
        dict(name=gv.name, groups=[g.name for g in gv.verticals])
        for gv in VerticalGroupVersion.query
    ]


def _restore_vertical_group_versions(vv):  # type: ignore[no-untyped-def] # Function is missing a type annotation
    db.session.add_all(
        [
            VerticalGroupVersion(
                name=v["name"],
                verticals=VerticalGroup.query.filter(
                    VerticalGroup.name.in_(v["groups"])
                ).all(),
            )
            for v in vv
        ]
    )


def export():  # type: ignore[no-untyped-def] # Function is missing a return type annotation
    return dict(
        verticals=_export_verticals(),
        vertical_groups=_export_vertical_groups(),
        vertical_group_versions=_export_vertical_group_versions(),
    )


def restore(data):  # type: ignore[no-untyped-def] # Function is missing a type annotation
    # Restore the base vertical objects
    db.session.bulk_insert_mappings(Vertical, data["verticals"])
    db.session.flush()
    # Get a mapping of vertical name to vertical id
    vertical_id_by_name = {
        v.name: v.id for v in db.session.query(Vertical.name, Vertical.id).all()
    }
    # Create the vertical groups
    db.session.bulk_insert_mappings(VerticalGroup, data["vertical_groups"])
    db.session.flush()
    # Create the vertical-group -> vertical relationships
    vertical_group_id_by_name = {
        vg.name: vg.id
        for vg in db.session.query(VerticalGroup.name, VerticalGroup.id).all()
    }
    # Build the vertical-group-id -> vertical-ids mapping
    vertical_group_id_to_verticals = {
        vertical_group_id_by_name[vg["name"]]: {
            vertical_id_by_name[n]
            for n in vertical_id_by_name.keys() & {*vg["verticals"]}
        }
        for vg in data["vertical_groups"]
    }
    vertical_groups_verticals = chain()
    for vg_id, vertical_ids in vertical_group_id_to_verticals.items():
        if vertical_ids:
            vertical_groups_verticals = chain(
                vertical_groups_verticals,
                [
                    {"vertical_group_id": vg_id, "vertical_id": vid}
                    for vid in vertical_ids
                ],
            )
    db.session.execute(vertical_groupings.insert(), [*vertical_groups_verticals])
    # Build the vertical-group-version-name -> vertical-group-ids mapping
    vertical_group_version_name_to_vertical_groups = {
        vgv["name"]: {
            vertical_group_id_by_name[n]
            for n in vertical_group_id_by_name.keys() & {*vgv["groups"]}
        }
        for vgv in data["vertical_group_versions"]
    }
    # Create the vertical group versions
    db.session.bulk_insert_mappings(
        VerticalGroupVersion, data["vertical_group_versions"]
    )
    # Create the vertical-group-version -> vertical-group relationships
    vertical_group_version_id_by_name = {
        vgv.name: vgv.id
        for vgv in db.session.query(
            VerticalGroupVersion.name, VerticalGroupVersion.id
        ).all()
    }
    vertical_group_versions_vertical_groups = chain()
    for name, vertical_groups in vertical_group_version_name_to_vertical_groups.items():
        if vertical_groups:
            vgv_id = vertical_group_version_id_by_name[name]
            vertical_group_versions_vertical_groups = chain(
                vertical_group_versions_vertical_groups,
                [
                    {"vertical_group_version_id": vgv_id, "vertical_group_id": vgid}
                    for vgid in vertical_groups
                ],
            )
    db.session.execute(
        vertical_grouping_versions.insert(), [*vertical_group_versions_vertical_groups]
    )
