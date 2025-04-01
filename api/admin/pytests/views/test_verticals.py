import pytest

from models.products import Product


@pytest.fixture
def product(factories):
    minutes = 12
    price = 24
    product = factories.ProductFactory.create(
        minutes=minutes,
        price=price,
        vertical=factories.VerticalFactory.build(
            name="Test Vertical", products=[{"minutes": minutes, "price": price}]
        ),
        is_active=True,
    )
    product.practitioner.profile.verticals = [product.vertical]
    return product


class TestVertical:
    def test_deactivate_vertical_products(self, admin_client, product):
        assert product.is_active is True
        res = admin_client.post(
            "/admin/vertical/deactivate_products/",
            json={
                "vertical_id": product.vertical_id,
                "product": {"minutes": product.minutes, "price": product.price},
            },
        )
        assert res.status_code == 200
        assert product.is_active is False

    def test_create_vertical_products(self, admin_client, product):
        new_minute_value = 40
        res = admin_client.post(
            "/admin/vertical/create_products/",
            json={
                "vertical_id": product.vertical_id,
                "product": {"minutes": new_minute_value, "price": product.price},
            },
        )
        assert res.status_code == 200
        assert res.json == {"count": 1}
        new_product = Product.query.filter_by(
            vertical_id=product.vertical_id,
            user_id=product.user_id,
            minutes=new_minute_value,
            price=product.price,
        ).one()
        assert new_product.is_active is True

    def test_create_vertical_products_for_all_practitioners_in_vertical(
        self, admin_client, factories, product
    ):
        new_minute_value = 42
        factories.PractitionerUserFactory.create_batch(
            size=4, practitioner_profile__verticals=[product.vertical]
        )
        res = admin_client.post(
            "/admin/vertical/create_products/",
            json={
                "vertical_id": product.vertical_id,
                "product": {"minutes": new_minute_value, "price": product.price},
            },
        )
        assert res.status_code == 200
        assert res.json == {"count": 5}
        products = Product.query.filter_by(
            vertical_id=product.vertical_id,
            minutes=new_minute_value,
            price=product.price,
        ).all()
        assert len(products) == 5

    def test_create_vertical_products_already_product(
        self, admin_client, factories, product
    ):
        product_count = Product.query.filter_by(
            vertical_id=product.vertical_id,
            minutes=product.minutes,
        ).count()
        res = admin_client.post(
            "/admin/vertical/create_products/",
            json={
                "vertical_id": product.vertical_id,
                "product": {"minutes": product.minutes, "price": product.price},
            },
        )
        new_product_count = Product.query.filter_by(
            vertical_id=product.vertical_id,
            minutes=product.minutes,
        ).count()

        assert res.status_code == 200
        assert res.json == {"count": 0}
        assert product_count == new_product_count

    def test_create_vertical_products_already_product_higher_amount(
        self, admin_client, product
    ):
        new_price = product.price + 20
        res = admin_client.post(
            "/admin/vertical/create_products/",
            json={
                "vertical_id": product.vertical_id,
                "product": {"minutes": product.minutes, "price": new_price},
            },
        )
        new_product = Product.query.filter_by(
            vertical_id=product.vertical_id, minutes=product.minutes, price=new_price
        ).one()

        assert res.status_code == 200
        assert res.json == {"count": 1}
        assert new_product.is_active

    def test_create_vertical_products_already_product_lower_amount(
        self, admin_client, product
    ):
        new_price = product.price - 20
        res = admin_client.post(
            "/admin/vertical/create_products/",
            json={
                "vertical_id": product.vertical_id,
                "product": {"minutes": product.minutes, "price": new_price},
            },
        )
        new_product = Product.query.filter_by(
            vertical_id=product.vertical_id, minutes=product.minutes, price=new_price
        ).first()
        assert res.status_code == 200
        assert res.json == {"count": 0}
        assert new_product is None
