from models.profiles import Category, CategoryVersion, category_versions
from storage.connection import db

from .sorting import sorted_by


@sorted_by("name")
def _export_categories():  # type: ignore[no-untyped-def] # Function is missing a return type annotation
    return [
        dict(
            name=c.name,
            display_name=c.display_name,
            ordering_weight=c.ordering_weight,
            versions=[v.name for v in c.versions],
        )
        for c in Category.query
    ]


def export():  # type: ignore[no-untyped-def] # Function is missing a return type annotation
    return dict(
        versions=sorted([v.name for v in CategoryVersion.query]),
        categories=_export_categories(),
    )


def restore(data):  # type: ignore[no-untyped-def] # Function is missing a type annotation
    # Create the category versions
    db.session.bulk_insert_mappings(
        CategoryVersion, [{"name": v} for v in data["versions"]]
    )
    # Get their IDs by name
    category_version_id_by_name = {
        cv.name: cv.id
        for cv in db.session.query(CategoryVersion.name, CategoryVersion.id).all()
    }
    # Build a mapping of category-name -> category-version-id
    category_versions_by_category_name = {
        c["name"]: {
            category_version_id_by_name[n]
            for n in category_version_id_by_name.keys() & {*c["versions"]}
        }
        for c in data["categories"]
    }
    # Create the categories
    db.session.bulk_insert_mappings(Category, data["categories"])
    # Get their IDs by name
    category_id_by_name = {
        c.name: c.id for c in db.session.query(Category.name, Category.id).all()
    }
    # Build the category -> category-version relationships
    category_versions_categories = set()
    for name, versions in category_versions_by_category_name.items():
        if versions:
            category_id = category_id_by_name[name]
            category_versions_categories.update(
                (category_id, cvid) for cvid in versions
            )
    # Create the associations
    db.session.execute(
        category_versions.insert(),
        [
            {"category_id": cid, "category_version_id": cvid}
            for cid, cvid in category_versions_categories
        ],
    )
