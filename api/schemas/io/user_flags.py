from health.data_models.risk_flag import RiskFlag
from storage.connection import db

from .sorting import sorted_by


@sorted_by("name")
def export():  # type: ignore[no-untyped-def] # Function is missing a return type annotation
    return [dict(name=f.name, type=f.type.value) for f in RiskFlag.query]


def restore(ff):  # type: ignore[no-untyped-def] # Function is missing a type annotation
    db.session.bulk_insert_mappings(RiskFlag, ff)
