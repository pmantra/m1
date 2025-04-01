import datetime
import io
from unittest.mock import patch

import pytest
from marshmallow import ValidationError

from bms.models.bms import OrderStatus
from bms.pytests.factories import (
    BMSOrderFactory,
    BMSProductFactory,
    BMSShipmentFactory,
    BMSShipmentProductsFactory,
)
from bms.schemas.bms import validate_travel_start_date
from eligibility.pytests.factories import EligibilityMemberFactory
from models.enterprise import BMS_ORDER_RESOURCE
from models.tracks import TrackName
from pytests.factories import AddressFactory, EnterpriseUserFactory


@pytest.fixture(autouse=True, scope="function")
def bms_resource(factories):
    factories.ResourceFactory.create(slug=BMS_ORDER_RESOURCE)


@pytest.fixture(autouse=True, scope="function")
def bms_products(factories):
    BMSProductFactory.create(name="kit")
    BMSProductFactory.create(name="cooler")


@pytest.fixture
def bms_order_data_generator():
    def _bms_order_data(
        start_date: datetime.datetime,
        end_date: datetime.datetime,
        external_trip_id: str = None,
    ):
        return {
            "is_work_travel": True,
            "travel_start_date": start_date.isoformat(),
            "travel_end_date": end_date.isoformat(),
            "outbound_shipments": [
                {
                    "recipient_name": "Jane Smith",
                    "tel_number": "tel:+1-913-476-8475",
                    "tel_region": "US",
                    "tracking_email": "bob@aol.com",
                    "accommodation_name": "Mariott",
                    "residential_address": False,
                    "address": {
                        "street_address": "394 Broadway, 3rd Floor",
                        "zip_code": "10013",
                        "city": "New York",
                        "state": "NY",
                        "country": "US",
                    },
                    "products": [
                        {"name": "kit", "quantity": 2},
                        {"name": "cooler", "quantity": 1},
                    ],
                }
            ],
            "return_shipments": [
                {
                    "recipient_name": "John Smith",
                    "tel_number": "tel:+1-913-476-8475",
                    "tel_region": "US",
                    "tracking_email": "bob@aol.com",
                    "accommodation_name": "Mariott",
                    "residential_address": False,
                    "friday_shipping": True,
                    "address": {
                        "street_address": "123 Fake St",
                        "zip_code": "10001",
                        "city": "New York",
                        "state": "NY",
                        "country": "US",
                    },
                }
            ],
            "terms": {"terms1": "yes"},
            "external_trip_id": external_trip_id,
        }

    return _bms_order_data


@pytest.fixture
def valid_start_date():
    return create_start_date(datetime.datetime.now())


def create_start_date(now):
    start_date = now + datetime.timedelta(days=1)
    while True:
        try:
            validate_travel_start_date(start_date.date())
        except ValidationError:
            start_date = start_date + datetime.timedelta(days=1)
            continue
        return start_date.date()


@pytest.fixture
def end_date():
    return (datetime.datetime.now() + datetime.timedelta(days=14)).date()


@pytest.fixture
def bms_user(factories):
    return factories.EnterpriseUserFactory(
        enabled_tracks=[TrackName.GENERIC],
        tracks__name=TrackName.GENERIC,
        tracks__client_track__organization__bms_enabled=True,
    )


def bms_order(start_date, status=OrderStatus.NEW):
    valid_start_date = create_start_date(start_date)
    order = BMSOrderFactory(travel_start_date=valid_start_date, status=status)
    return order


@pytest.fixture()
def create_valid_bms_order_set():
    start_date = datetime.datetime.now()
    order_one = bms_order(start_date)
    order_two = bms_order(start_date + datetime.timedelta(days=1))
    order_three = bms_order(start_date + datetime.timedelta(days=4))
    return [order_one, order_two, order_three]


@pytest.fixture()
def create_invalid_bms_order_set():
    start_date = datetime.datetime.now()
    start_date_one = start_date + datetime.timedelta(days=8)
    order_one = bms_order(start_date_one, status=OrderStatus.CANCELLED)
    order_two = bms_order(start_date, status=OrderStatus.FULFILLED)
    start_date_three = start_date + datetime.timedelta(days=2)
    order_three = bms_order(start_date_three, status=OrderStatus.PROCESSING)
    return [order_one, order_two, order_three]


@pytest.fixture()
def bms_bytes_blob():
    file = (
        b"order_id,kit_shipment_id,order_fulfilled_at,kit_tracking_numbers,kit_shipment_cost,kit_shipping_method,"
        b"milk_shipment_id,milk_tracking_numbers,milk_shipment_cost,milk_shipping_method"
        b"\r\n1,1,2022-6-2 16:00:00,1Z9Y3Y280342676837,80.83,UPS Ground,2,"
        b'"1Z9Y3Y280142470464, 1Z9Y3Y280142573657, 1Z9Y3Y280142820871, 1Z9Y3Y284442074446",'
        b"698.4,UPS Next Day Air\r\n"
        b"2,3,2022-6-2 16:00:00,1Z9Y3Y280142314614,297.5,UPS 2nd Day Air\r\n"
    )
    return io.BytesIO(file)


@pytest.fixture()
def incomplete_bms_bytes_blob():
    file = (
        b"order_id,kit_shipment_id,order_fulfilled_at,kit_tracking_numbers,kit_shipment_cost,kit_shipping_method,"
        b"milk_shipment_id,milk_tracking_numbers,milk_shipment_cost,milk_shipping_method"
        b"\r\n1,1,2022-6-2 16:00:00,1Z9Y3Y280342676837,80.83\r\n"
    )
    return io.BytesIO(file)


@pytest.fixture()
def wrong_order_bms_bytes_blob():
    file = (
        b"order_id,kit_shipment_id,order_fulfilled_at,kit_tracking_numbers,kit_shipment_cost,kit_shipping_method,"
        b"milk_shipment_id,milk_tracking_numbers,milk_shipment_cost,milk_shipping_method"
        b"\r\n2,3,2022-6-2 16:00:00,1Z9Y3Y280142314614,297.5,UPS 2nd Day Air\r\n"
    )
    return io.BytesIO(file)


@pytest.fixture()
def bad_data_bms_bytes_blob():
    file = (
        b"order_id,kit_shipment_id,order_fulfilled_at,kit_tracking_numbers,kit_shipment_cost,kit_shipping_method,"
        b"milk_shipment_id,milk_tracking_numbers,milk_shipment_cost,milk_shipping_method"
        b"\r\n1,1,2022-6-2 16:00:00,1Z9Y3Y280342676837,twenty-two,UPS Ground,2,"
        b'"1Z9Y3Y280142470464, 1Z9Y3Y280142573657, 1Z9Y3Y280142820871, 1Z9Y3Y284442074446",'
        b"698.4,UPS Next Day Air\r\n"
        b"2,3,2022-6-2 16:00:00,1Z9Y3Y280142314614,297.5,UPS 2nd Day Air\r\n"
    )
    return io.BytesIO(file)


@pytest.fixture()
def bms_pump_carry_dict():
    return {
        "order_id": "2",
        "kit_shipment_id": "3",
        "order_fulfilled_at": "2022-6-2 16:00:00",
        "kit_tracking_numbers": "abc123tracking",
        "kit_shipment_cost": "21.62",
        "kit_shipping_method": "UPS Ground",
    }


@pytest.fixture()
def bms_pump_post_dict():
    return {
        "order_id": "1",
        "kit_shipment_id": "2",
        "order_fulfilled_at": "2022-6-2 16:00:00",
        "kit_tracking_numbers": "def456tracking",
        "kit_shipment_cost": "71.94",
        "kit_shipment_method": "UPS Ground",
        "milk_shipment_id": "3",
        "milk_tracking_numbers": "ghi789tracking,jkl1112tracking",
        "milk_shipment_cost": "388.98",
        "milk_shipping_method": "UPS Next Day Air",
    }


@pytest.fixture()
def create_pump_and_post_factories():
    ship_bms_order = BMSOrderFactory(id=1, status=OrderStatus.PROCESSING)
    ship_one = BMSShipmentFactory(id=1, bms_order=ship_bms_order)
    ship_two = BMSShipmentFactory(id=2, bms_order=ship_bms_order)
    bms_product = BMSProductFactory.create(name="pump_and_post")
    BMSShipmentProductsFactory(bms_shipment=ship_one, bms_product=bms_product)
    BMSShipmentProductsFactory(bms_shipment=ship_two, bms_product=bms_product)
    return ship_bms_order, ship_one, ship_two, bms_product


@pytest.fixture()
def create_pump_and_carry_factories():
    ship_bms_order = BMSOrderFactory(id=2, status=OrderStatus.PROCESSING)
    ship_one = BMSShipmentFactory(id=3, bms_order=ship_bms_order)
    bms_product = BMSProductFactory.create(name="pump_and_carry")
    BMSShipmentProductsFactory(bms_shipment=ship_one, bms_product=bms_product)
    return ship_bms_order, ship_one, bms_product


@pytest.fixture()
def create_valid_bms_kits():
    # Fixtures with values exceeding character limits to test for testing generating BMS Order CSV for UPS
    bms_user = EnterpriseUserFactory.create(
        email="fakelongestemailcdefghijklmnopqrstuwxyzhshdgeggdgdgdgdgdgdg@email.com"
    )
    bms_first_order = BMSOrderFactory.create(
        travel_start_date=datetime.datetime.now(),
        status=OrderStatus.PROCESSING,
        user=bms_user,
    )
    bms_address = AddressFactory.create(
        street_address="748 Adam Coves Suite thelongeststreetnameintheworld",
        city="fakelongestcitynameabcdefghijklmnop",
        state="thelongeststatewithoverthirtycharacters",
        country="thelongestcountrywithoverfiftycharactersabcdefghijklmnopqrst",
        zip_code="12345-6789",
    )
    bms_product = BMSProductFactory.create(name="pump_and_carry")
    bms_shipment = BMSShipmentFactory.create(
        bms_order=bms_first_order,
        recipient_name="longestkitshipmentrecipientnameofalltime1",
        address=bms_address,
        tracking_email="abc@mail.com",
        tel_number="+1-617-894-12345",
    )

    BMSShipmentProductsFactory(bms_shipment=bms_shipment, bms_product=bms_product)


@pytest.fixture
def patch_send_bm_tracking_email():
    with patch("utils.braze_events.send_bms_tracking_email") as p:
        yield p


@pytest.fixture
def patch_braze_bms_post_orders():
    with patch("utils.braze_events.bms_post_orders_sent") as p:
        yield p


@pytest.fixture
def patch_braze_bms_check_order():
    with patch("utils.braze_events.bms_check_order_sent") as p:
        yield p


@pytest.fixture
def patch_braze_bms_carry_order():
    with patch("utils.braze_events.bms_carry_order_sent") as p:
        yield p


@pytest.fixture
def frozen_shipping_blackout_dates():
    return frozenset(
        (
            datetime.date(2021, 12, 24),
            datetime.date(2021, 12, 25),
            datetime.date(2021, 12, 27),
            datetime.date(2021, 12, 31),
            datetime.date(2022, 1, 1),
            datetime.date(2022, 1, 3),
            datetime.date(2022, 1, 17),
            datetime.date(2022, 1, 18),
            datetime.date(2022, 2, 21),
            datetime.date(2022, 2, 22),
            datetime.date(2022, 5, 30),
            datetime.date(2022, 5, 31),
            datetime.date(2022, 6, 19),
            datetime.date(2022, 6, 20),
            datetime.date(2022, 7, 4),
            datetime.date(2022, 7, 5),
            datetime.date(2022, 9, 5),
            datetime.date(2022, 9, 6),
            datetime.date(2022, 10, 10),
            datetime.date(2022, 10, 11),
            datetime.date(2022, 11, 11),
            datetime.date(2022, 11, 12),
            datetime.date(2022, 11, 14),
            datetime.date(2022, 11, 24),
            datetime.date(2022, 11, 25),
            datetime.date(2022, 11, 26),
            datetime.date(2022, 11, 28),
            datetime.date(2022, 12, 24),
            datetime.date(2022, 12, 25),
            datetime.date(2022, 12, 26),
        )
    )


@pytest.fixture
def eligible_verification():
    return EligibilityMemberFactory.create(
        record={"dependent_relationship_code": "Employee"}
    )


@pytest.fixture
def dynamic_eligible_verification(request):
    return EligibilityMemberFactory.create(
        record={"dependent_relationship_code": request.param}
    )
