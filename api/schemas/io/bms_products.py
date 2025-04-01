from bms.models.bms import BMSProduct
from storage.connection import db

from .sorting import sorted_by


@sorted_by("name")
def export():  # type: ignore[no-untyped-def] # Function is missing a return type annotation
    return [dict(name=p.name, description=p.description) for p in BMSProduct.query]


def restore(products):  # type: ignore[no-untyped-def] # Function is missing a type annotation
    db.session.bulk_insert_mappings(BMSProduct, products)
