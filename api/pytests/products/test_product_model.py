from models.products import Product, add_products
from storage.connection import db


def test_add_products(factories):
    vertical1 = factories.VerticalFactory(
        name="1", products=[{"price": 1, "minutes": 1, "purpose": "one"}]
    )
    vertical2 = factories.VerticalFactory(
        name="2", products=[{"price": 2, "minutes": 2, "purpose": "two"}]
    )
    prac = factories.PractitionerUserFactory(
        products=[], practitioner_profile__verticals=[vertical1, vertical2]
    )
    # The products already get added by the PractitionerProfiles.append
    # event listeners...but let's remove them so we can test this method
    Product.query.filter_by(user_id=prac.id).delete()
    db.session.expire(prac)
    assert len(prac.products) == 0

    add_products(prac)
    assert len(prac.products) > 0
    for vert in [vertical1, vertical2]:
        for product_dict in vert.products:
            assert next(
                (
                    p
                    for p in prac.products
                    if p.vertical_id == vert.id
                    and p.minutes == product_dict["minutes"]
                    and p.price == product_dict["price"]
                    and p.purpose == product_dict["purpose"]
                ),
                False,
            )


def test_add_products_updated_vertical(factories):
    vertical = factories.VerticalFactory(name="1")
    prac = factories.PractitionerUserFactory(
        products=[], practitioner_profile__verticals=[vertical]
    )
    original_length = len(prac.products)

    vertical.products.append({"minutes": 75, "price": 122})
    add_products(prac)
    assert len(prac.products) == original_length + 1
