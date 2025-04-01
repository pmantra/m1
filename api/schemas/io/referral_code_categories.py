from models.referrals import ReferralCodeCategory, ReferralCodeSubCategory
from storage.connection import db

from .sorting import sorted_by


@sorted_by("name")
def export():  # type: ignore[no-untyped-def] # Function is missing a return type annotation
    return [
        dict(
            name=c.name,
            sub_categories=[
                sc.name
                for sc in ReferralCodeSubCategory.query.filter(
                    ReferralCodeSubCategory.category_name == c.name
                )
            ],
        )
        for c in ReferralCodeCategory.query
    ]


def restore(cc):  # type: ignore[no-untyped-def] # Function is missing a type annotation
    sub_categories = [
        {"category_name": c["name"], "name": sc}
        for c in cc
        for sc in c["sub_categories"]
    ]
    db.session.bulk_insert_mappings(ReferralCodeCategory, cc)
    db.session.bulk_insert_mappings(ReferralCodeSubCategory, sub_categories)
