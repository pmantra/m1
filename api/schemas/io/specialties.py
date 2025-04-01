import warnings
from itertools import chain

from models.verticals_and_specialties import (
    Specialty,
    VerticalGroup,
    vertical_group_specialties,
)
from storage.connection import db

from .sorting import sorted_by


@sorted_by("name")
def export():  # type: ignore[no-untyped-def] # Function is missing a return type annotation
    return [
        dict(
            name=s.name,
            ordering_weight=s.ordering_weight,
            vertical_groups=[g.name for g in s.vertical_groups],
        )
        for s in Specialty.query
    ]


def restore(ss):  # type: ignore[no-untyped-def] # Function is missing a type annotation
    db.session.bulk_insert_mappings(Specialty, ss)
    vertical_group_id_by_name = {
        vg.name: vg.id
        for vg in db.session.query(VerticalGroup.name, VerticalGroup.id).all()
    }
    if not vertical_group_id_by_name:
        warnings.warn(  # noqa  B028  TODO:  No explicit stacklevel keyword argument found. The warn method from the warnings module uses a stacklevel of 1 by default. This will only show a stack trace for the line on which the warn method is called. It is therefore recommended to use a stacklevel of 2 or greater to provide more information to the user.
            "Restoring Specialties without Verticals will result in incomplete data!"
        )
    else:
        specialty_name_to_vertical_groups = {
            s["name"]: {
                vertical_group_id_by_name[n]
                for n in vertical_group_id_by_name.keys() & s["vertical_groups"]
            }
            for s in ss
        }
        specialty_id_by_name = {
            s.name: s.id for s in db.session.query(Specialty.name, Specialty.id).all()
        }
        specialties_vertical_groups = chain()
        for name, groups in specialty_name_to_vertical_groups.items():
            if groups:
                s_id = specialty_id_by_name[name]
                specialties_vertical_groups = chain(
                    specialties_vertical_groups,
                    [
                        {"specialty_id": s_id, "vertical_group_id": vgid}
                        for vgid in groups
                    ],
                )
        db.session.execute(
            vertical_group_specialties.insert(), [*specialties_vertical_groups]
        )
