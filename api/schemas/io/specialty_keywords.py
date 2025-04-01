from itertools import chain

from models.verticals_and_specialties import (
    Specialty,
    SpecialtyKeyword,
    specialty_specialty_keywords,
)
from storage.connection import db

from .sorting import sorted_by


@sorted_by("name")
def export():  # type: ignore[no-untyped-def] # Function is missing a return type annotation
    return [
        dict(name=s.name, specialties=[s.name for s in s.specialties])
        for s in SpecialtyKeyword.query
    ]


def restore(sks):  # type: ignore[no-untyped-def] # Function is missing a type annotation

    specialty_ids_by_name = {
        s.name: s.id for s in db.session.query(Specialty.name, Specialty.id).all()
    }
    assert (
        specialty_ids_by_name
    ), "Specialty Keywords require Specialties to be restored."

    specialty_keyword_name_to_specialty_ids = {
        sk["name"]: {
            specialty_ids_by_name[n]
            for n in specialty_ids_by_name.keys() & {*sk["specialties"]}
        }
        for sk in sks
    }
    db.session.bulk_insert_mappings(SpecialtyKeyword, sks)
    specialty_keyword_id_by_name = {
        sk.name: sk.id
        for sk in db.session.query(SpecialtyKeyword.name, SpecialtyKeyword.id).all()
    }
    specialty_keywords_specialties = chain()
    for name, specialty_ids in specialty_keyword_name_to_specialty_ids.items():
        if specialty_ids:
            sk_id = specialty_keyword_id_by_name[name]
            specialty_keywords_specialties = chain(
                specialty_keywords_specialties,
                [
                    {"specialty_keyword_id": sk_id, "specialty_id": sid}
                    for sid in specialty_ids
                ],
            )
    db.session.execute(
        specialty_specialty_keywords.insert(), [*specialty_keywords_specialties]
    )
