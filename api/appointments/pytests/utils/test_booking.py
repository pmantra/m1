import datetime

import pytest

from appointments.utils.booking import AvailabilityTools, _bump_datetime_by_increment
from pytests.factories import PractitionerUserFactory, ProductFactory


class TestGetProductForPractitioner:
    def test_get_product_for_practitioner(self):
        # Given, a practitioner with some products of the same price
        practitioner = PractitionerUserFactory.create()
        vertical = practitioner.practitioner_profile.verticals[0]
        products = [
            ProductFactory.create(
                vertical=vertical, practitioner=practitioner, minutes=15, price=40
            ),
            ProductFactory.create(
                vertical=vertical, practitioner=practitioner, minutes=20, price=20
            ),
            ProductFactory.create(
                vertical=vertical, practitioner=practitioner, minutes=100, price=20
            ),
            ProductFactory.create(
                vertical=vertical, practitioner=practitioner, minutes=15, price=20
            ),
        ]
        practitioner.products = products

        # When, getting practitioner's product
        min_product = AvailabilityTools.get_product_for_practitioner(
            practitioner.practitioner_profile
        )

        # Then, we get the product with price 20 and length 15 minutes
        assert min_product.price == 20
        assert min_product.minutes == 15

    def test_get_product_for_practitioner__with_vertical(self):
        # Given, a practitioner with 3 products, all with OB-GYN vertical (by default)
        practitioner = PractitionerUserFactory.create()
        vertical = practitioner.practitioner_profile.verticals[0]
        products = [
            ProductFactory.create(
                vertical=vertical,
                practitioner=practitioner,
                minutes=15,
                price=20,
            ),
            ProductFactory.create(
                vertical=vertical,
                practitioner=practitioner,
                minutes=20,
                price=20,
            ),
            ProductFactory.create(
                vertical=vertical,
                practitioner=practitioner,
                minutes=20,
                price=40,
            ),
        ]
        practitioner.products = products

        # When, getting practitioner's product for OBGYN
        min_product = AvailabilityTools.get_product_for_practitioner(
            practitioner.practitioner_profile, "OB-GYN"
        )

        # Then, we get the product with price 20 and length 15 minutes
        assert min_product.price == 20
        assert min_product.minutes == 15

        # When, changing the product with minutes=15 vertical, and getting again the product with min price for OBGYN
        min_product.vertical = None
        min_product_2 = AvailabilityTools.get_product_for_practitioner(
            practitioner.practitioner_profile, "OB-GYN"
        )

        # Then, we get the product with price 20 and length 20 minutes
        assert min_product_2.price == 20
        assert min_product_2.minutes == 20

        # When, changing the product with price=20 and minutes=20 vertical, and getting again the product with min price for OBGYN
        min_product_2.vertical = None
        min_product_3 = AvailabilityTools.get_product_for_practitioner(
            practitioner.practitioner_profile, "OB-GYN"
        )

        # Then, we get the product with price 40 and length 20 minutes
        assert min_product_3.price == 40
        assert min_product_3.minutes == 20

        # When, getting the min price for a vertical for which there are no products
        min_product = AvailabilityTools.get_product_for_practitioner(
            practitioner.practitioner_profile, "radiology"
        )
        # Then, we get no product
        assert min_product is None


class TestGetLowestPriceProductsForPractitioners:
    def test_get_lowest_price_products_for_practitioners__no_product(
        self, factories, practitioner_profile_with_product_prices
    ):
        # Given a practitioner with no product
        prac = factories.PractitionerUserFactory()
        prac.products = []

        # When
        min_price_products = (
            AvailabilityTools.get_lowest_price_products_for_practitioners(
                [prac.practitioner_profile]
            )
        )

        # Then
        expected_min_price_products = {
            prac.id: None,
        }
        assert min_price_products == expected_min_price_products

    def test_get_lowest_price_products_for_practitioners__for_no_specific_vertical(
        self, factories, practitioner_profile_with_product_prices
    ):
        # Given two practitioners with different products
        pp_1 = practitioner_profile_with_product_prices([40, 20, 20])
        pp_2 = practitioner_profile_with_product_prices([41, 21, 101])

        # Lets manually change the min product verticals to different ones (we know that by default they are all OB-GYN)
        pp_1_min_price_product = [
            prod for prod in pp_1.user.products if prod.price == 20
        ][0]
        pp_1_min_price_product.vertical = factories.VerticalFactory(name="Green")

        pp_2_min_price_product = [
            prod for prod in pp_2.user.products if prod.price == 21
        ][0]
        pp_2_min_price_product.vertical = factories.VerticalFactory(name="Purple")

        # When, getting the lowest products without specifying a vertical
        min_price_products = (
            AvailabilityTools.get_lowest_price_products_for_practitioners([pp_1, pp_2])
        )

        # Then
        expected_min_price_products = {
            pp_1.user_id: pp_1_min_price_product,
            pp_2.user_id: pp_2_min_price_product,
        }
        assert min_price_products == expected_min_price_products

    def test_get_lowest_price_products_for_practitioners__for_specific_vertical(
        self, factories, practitioner_profile_with_product_prices
    ):
        # Given two practitioners with different products, all OB-GYN by default
        pp_1 = practitioner_profile_with_product_prices([40, 20, 20])
        pp_2 = practitioner_profile_with_product_prices([41, 21, 101])

        # When, getting the min product for OB-GYN
        min_price_products = (
            AvailabilityTools.get_lowest_price_products_for_practitioners(
                [pp_1, pp_2], "OB-GYN"
            )
        )

        # Then,
        # Build expected result
        pp_1_min_price_obgyn_product = [
            prod for prod in pp_1.user.products if prod.price == 20
        ][0]
        pp_2_min_price_obgyn_product = [
            prod for prod in pp_2.user.products if prod.price == 21
        ][0]
        expected_min_price_products = {
            pp_1.user_id: pp_1_min_price_obgyn_product,
            pp_2.user_id: pp_2_min_price_obgyn_product,
        }
        assert min_price_products == expected_min_price_products

        # And, when changing one of the product with min price's vertical
        pp_2_min_price_obgyn_product.vertical = factories.VerticalFactory(
            name="adoption"
        )

        # When, getting again min product for OB-GYN
        min_price_products = (
            AvailabilityTools.get_lowest_price_products_for_practitioners(
                [pp_1, pp_2], "OB-GYN"
            )
        )

        # Then,
        # Build expected result
        pp_2_new_obgyn_min_price_product = [
            prod for prod in pp_2.user.products if prod.price == 41
        ][0]
        expected_min_price_products = {
            pp_1.user_id: pp_1_min_price_obgyn_product,
            pp_2.user_id: pp_2_new_obgyn_min_price_product,
        }

        assert min_price_products == expected_min_price_products

    def test_get_lowest_price_products_for_practitioners__nonexistent_vertical(
        self, practitioner_profile_with_product_prices
    ):
        # Given two practitioners with different products
        pp_1 = practitioner_profile_with_product_prices([40, 20, 20])
        pp_2 = practitioner_profile_with_product_prices([41, 21, 101])

        # When
        min_products = AvailabilityTools.get_lowest_price_products_for_practitioners(
            [pp_1, pp_2], "an unexisting vertical name"
        )

        # Then
        expected_min_products_for_unexisting_vertical = {
            pp_1.user_id: None,
            pp_2.user_id: None,
        }
        assert min_products == expected_min_products_for_unexisting_vertical


class TestBumpDatetimeByIncrement:

    dt = datetime.datetime.fromisoformat("2022-06-30T00:05:23")
    increment_length_10_min = datetime.timedelta(minutes=10)

    @pytest.mark.parametrize(
        "dt,target,increment_length,expected",
        [
            # If we're already past target time we should just get the same time
            (
                dt,
                dt - datetime.timedelta(minutes=15),
                increment_length_10_min,
                dt,
            ),
            # If we're under target time by 5 minutes, we should get 5 min after target
            (
                dt,
                dt + datetime.timedelta(minutes=5),
                increment_length_10_min,
                dt + datetime.timedelta(minutes=10),
            ),
            # If we're under target time by 25 minutes, we should get 5 min after target
            (
                dt,
                dt + datetime.timedelta(minutes=25),
                increment_length_10_min,
                dt + datetime.timedelta(minutes=30),
            ),
        ],
    )
    def test_bump_datetime_by_increment(self, dt, target, increment_length, expected):
        actual = _bump_datetime_by_increment(
            dt,
            target,
            increment_length,
        )
        assert actual == expected
