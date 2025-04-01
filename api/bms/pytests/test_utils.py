import csv
import datetime
import io
from unittest.mock import patch

import paramiko
import pytest

from bms.models.bms import BMSOrder, OrderStatus, ShippingMethods
from bms.pytests.factories import BMSOrderFactory
from bms.utils.bms import (
    UPS_CHAR_LIMITS,
    EnterMilkShipmentManually,
    break_up_address_with_delimiter,
    cleanup_phone_number,
    cleanup_zip_code,
    convert_orders_to_dicts,
    generate_bms_orders_csv,
    get_last_business_date,
    get_submittable_bms_orders,
    is_date_qualified,
    return_file_name,
    ssh_connect_retry_on_timeout,
    truncate_field,
    update_kit_shipment,
    update_milk_shipment,
    validate_shipping_cost,
    validate_shipping_date,
    validate_shipping_method,
)
from storage.connection import db


@pytest.mark.parametrize(
    argnames="start_date,expected_date",
    argvalues=(
        # date in the middle of the week -  no holiday
        (datetime.datetime(2022, 6, 1).date(), datetime.datetime(2022, 6, 8).date()),
        # date in the end of the month holiday on Monday
        (datetime.datetime(2022, 6, 30).date(), datetime.datetime(2022, 7, 11).date()),
        # date in the beginning of the week holiday on Sunday observed Monday
        (datetime.datetime(2022, 6, 14).date(), datetime.datetime(2022, 6, 22).date()),
        # date on the weekend
        (datetime.datetime(2022, 6, 11).date(), datetime.datetime(2022, 6, 17).date()),
        # date on the weekend before holiday on Sunday that is observed on Monday
        (datetime.datetime(2022, 6, 18).date(), datetime.datetime(2022, 6, 27).date()),
    ),
)
def test_get_last_business_date(
    start_date, expected_date, frozen_shipping_blackout_dates
):
    with patch("bms.utils.bms.SHIPPING_BLACKOUT_DATES", frozen_shipping_blackout_dates):
        last_business_day = get_last_business_date(start_date=start_date)
    assert last_business_day == expected_date


@pytest.mark.parametrize(
    argnames="start_date_one, start_date_two, start_date_three, count_expected",
    argvalues=(
        # happy path dates within a 5 business day period
        (
            datetime.datetime(2022, 6, 5),
            datetime.datetime(2022, 6, 5) + datetime.timedelta(days=1),
            datetime.datetime(2022, 6, 5) + datetime.timedelta(days=2),
            3,
        ),
        # two fall within the 5 day range
        (
            datetime.datetime(2022, 6, 5) + datetime.timedelta(days=3),
            datetime.datetime(2022, 6, 5) + datetime.timedelta(days=4),
            datetime.datetime(2022, 6, 5) + datetime.timedelta(days=6),
            2,
        ),
        # one fall within the 5 day range
        (
            datetime.datetime(2022, 6, 5) + datetime.timedelta(days=5),
            datetime.datetime(2022, 6, 5) + datetime.timedelta(days=6),
            datetime.datetime(2022, 6, 5) + datetime.timedelta(days=8),
            1,
        ),
        # zero fall within the 5 day range
        (
            datetime.datetime(2022, 6, 5) + datetime.timedelta(days=11),
            datetime.datetime(2022, 6, 5) + datetime.timedelta(days=14),
            datetime.datetime(2022, 6, 5) + datetime.timedelta(days=25),
            0,
        ),
    ),
)
def test_get_submittable_bms_orders_dates(
    start_date_one,
    start_date_two,
    start_date_three,
    count_expected,
):
    start_date = datetime.datetime(2022, 6, 5).date()
    BMSOrderFactory.create(travel_start_date=start_date_one)
    BMSOrderFactory.create(travel_start_date=start_date_two)
    BMSOrderFactory.create(travel_start_date=start_date_three)
    BMSOrderFactory.create(
        travel_start_date=start_date_one, status=OrderStatus.PROCESSING
    )
    bms_orders = get_submittable_bms_orders(filter_date=start_date)
    assert len(bms_orders) == count_expected


@pytest.mark.parametrize(
    argnames="date,expected",
    argvalues=(
        # Monday - actual holiday
        (datetime.datetime(2022, 7, 4).date(), False),
        # Tuesday after the holiday
        (datetime.datetime(2022, 7, 5).date(), False),
        # Saturday
        (datetime.datetime(2022, 6, 25).date(), False),
        # Sunday
        (datetime.datetime(2022, 6, 26).date(), False),
        # Monday that is observed as a holiday
        (datetime.datetime(2022, 6, 20).date(), False),
        # Sunday and a holiday
        (datetime.datetime(2022, 4, 17).date(), False),
        # Random day that isn't a weekend or a holiday
        (datetime.datetime(2022, 7, 28).date(), True),
    ),
)
def test_is_date_qualified(date, expected, frozen_shipping_blackout_dates):
    with patch("bms.utils.bms.SHIPPING_BLACKOUT_DATES", frozen_shipping_blackout_dates):
        qualified = is_date_qualified(date)
    assert qualified == expected


def test_return_file_name_found():
    time_one = datetime.datetime.now()
    time_two = datetime.datetime.now() + datetime.timedelta(seconds=30)
    time_three = datetime.datetime.now() + datetime.timedelta(days=-1)
    filelist = [
        f"bms-orders-{time_one.strftime('%y_%m_%d-%H_%M_%S')}.csv",
        f"bms-orders-{time_two.strftime('%y_%m_%d-%H_%M_%S')}.csv",
        f"bms-orders-{time_three.strftime('%y_%m_%d-%H_%M_%S')}.csv",
    ]
    file_found = return_file_name(filelist)
    assert (
        file_found
        == f"bms-orders-{datetime.datetime.now().strftime('%y_%m_%d-%H_%M_%S')}.csv"
    )


def test_return_file_name_none():
    time_one = datetime.datetime.now() + datetime.timedelta(days=1)
    time_two = datetime.datetime.now() + datetime.timedelta(days=1)
    time_three = datetime.datetime.now() + datetime.timedelta(days=1)
    filelist = [
        f"bms-orders-{time_one.strftime('%y_%m_%d-%H_%M_%S')}.csv",
        f"bms-orders-{time_two.strftime('%y_%m_%d-%H_%M_%S')}.csv",
        f"bms-orders-{time_three.strftime('%y_%m_%d-%H_%M_%S')}.csv",
    ]
    assert return_file_name(filelist) is None


def test_return_file_name_empty_list_none():
    filelist = []
    assert return_file_name(filelist) is None


def test_convert_orders_to_dicts(bms_bytes_blob):
    bms_orders_list = convert_orders_to_dicts(bms_bytes_blob)
    assert len(bms_orders_list) == 2
    assert (
        bms_orders_list[0].get("milk_tracking_numbers")
        == "1Z9Y3Y280142470464, 1Z9Y3Y280142573657, 1Z9Y3Y280142820871, 1Z9Y3Y284442074446"
    )
    assert bms_orders_list[1].get("milk_shipment_id") is None


def test_convert_orders_to_dicts_empty_file():
    file = b""
    empty_file = io.BytesIO(file)
    with pytest.raises(ValueError):
        convert_orders_to_dicts(empty_file)


def test_convert_orders_to_dicts_headers_only():
    file = (
        b"order_id,kit_shipment_id,order_fulfilled_at,kit_tracking_numbers,kit_shipment_cost,kit_shipping_method,"
        b"milk_shipment_id,milk_tracking_numbers,milk_shipment_cost,milk_shipping_method"
    )
    headers_file = io.BytesIO(file)
    with pytest.raises(ValueError):
        convert_orders_to_dicts(headers_file)


def test_update_kit_shipment(bms_pump_carry_dict, create_pump_and_carry_factories):
    bms_order, shipment_one, bms_product = create_pump_and_carry_factories
    assert shipment_one.cost is None
    assert shipment_one.shipped_at is None
    assert shipment_one.tracking_numbers is None
    assert shipment_one.shipping_method is None

    kit_shipment = update_kit_shipment(bms_pump_carry_dict)

    assert kit_shipment.id == 3
    assert kit_shipment.cost == 21.62
    assert kit_shipment.shipped_at == datetime.datetime.strptime(
        "6/2/2022 16:00:00", "%m/%d/%Y %H:%M:%S"
    )
    assert kit_shipment.tracking_numbers == "abc123tracking"
    assert kit_shipment.shipping_method == "UPS Ground"


def test_update_milk_kit_shipment(bms_pump_post_dict, create_pump_and_post_factories):
    (
        bms_order,
        shipment_one,
        milk_shipment_two,
        bms_product,
    ) = create_pump_and_post_factories

    assert milk_shipment_two.id == 2
    assert milk_shipment_two.cost is None
    assert milk_shipment_two.shipped_at is None
    assert milk_shipment_two.tracking_numbers is None
    assert milk_shipment_two.shipping_method is None

    milk_kit_shipment = update_milk_shipment(bms_pump_post_dict, milk_shipment_two.id)

    assert milk_kit_shipment.id == 2
    assert milk_kit_shipment.cost == 388.98
    assert milk_kit_shipment.shipped_at is None
    assert milk_kit_shipment.tracking_numbers == "ghi789tracking,jkl1112tracking"
    assert milk_kit_shipment.shipping_method == "UPS Next Day Air"


def test_update_kit_shipment_error_missing_id(create_pump_and_carry_factories):
    """This test sets the order_id to None"""
    bms_order, shipment_one, bms_product = create_pump_and_carry_factories
    assert shipment_one.id == 3
    assert shipment_one.bms_order.id == 2

    missing_order_dict = {
        "order_id": None,
        "kit_shipment_id": "3",
        "order_fulfilled_at": "6/2/2022 16:00:00",
        "kit_tracking_numbers": "abc123tracking",
        "kit_shipment_cost": "21.62",
        "kit_shipping_method": "UPS Ground",
    }
    with pytest.raises(ValueError):
        update_kit_shipment(missing_order_dict)


def test_update_kit_shipment_error_shipment_not_found(create_pump_and_carry_factories):
    """This test sets the wrong bms shipment id"""
    bms_order, shipment_one, bms_product = create_pump_and_carry_factories
    assert shipment_one.id == 3

    wrong_shipment_dict = {
        "order_id": "9",
        "kit_shipment_id": "42",
        "order_fulfilled_at": "6/2/2022 16:00:00",
        "kit_tracking_numbers": "abc123tracking",
        "kit_shipment_cost": "21.62",
        "kit_shipping_method": "UPS Ground",
    }
    with pytest.raises(ValueError):
        update_kit_shipment(wrong_shipment_dict)


def test_update_milk_shipment_error_shipment_not_found(create_pump_and_post_factories):
    """This test sets the wrong bms shipment id for the milk tracking"""
    bms_order, shipment_one, shipment_two, bms_product = create_pump_and_post_factories
    assert shipment_one.id == 1
    assert shipment_two.id == 2

    missing_order_dict = {
        "order_id": "1",
        "kit_shipment_id": "1",
        "order_fulfilled_at": "6/2/2022 16:00:00",
        "kit_tracking_numbers": "def456tracking",
        "kit_shipment_cost": "71.94",
        "kit_shipment_method": "UPS Ground",
        "milk_shipment_id": "88",
        "milk_tracking_numbers": "ghi789tracking,jkl1112tracking",
        "milk_shipment_cost": "388.98",
        "milk_shipping_method": "UPS Next Day Air",
    }
    with pytest.raises(ValueError):
        update_milk_shipment(missing_order_dict, "88")


def test_update_milk_shipment_error_no_data(
    bms_pump_post_dict, create_pump_and_post_factories
):
    (
        bms_order,
        shipment_one,
        milk_shipment_two,
        bms_product,
    ) = create_pump_and_post_factories
    bms_pump_post_dict["milk_tracking_numbers"] = " "
    bms_pump_post_dict["milk_shipment_cost"] = " "
    bms_pump_post_dict["milk_shipping_method"] = " "

    with pytest.raises(EnterMilkShipmentManually):
        update_milk_shipment(bms_pump_post_dict, milk_shipment_two.id)


def test_validate_date_with_no_seconds_success():
    date = "2022-6-2 16:00"
    assert validate_shipping_date(date) == datetime.datetime(2022, 6, 2, 16, 0)


def test_validate_date_with_seconds_success():
    date = "2022-6-2 16:00:17"
    assert validate_shipping_date(date) == datetime.datetime(2022, 6, 2, 16, 0, 17)


def test_validate_date_with_slashes():
    date = "6/2/2022 16:00"
    assert validate_shipping_date(date) == datetime.datetime(2022, 6, 2, 16, 0)


def test_validate_date_failure():
    date = "2022/6/2 16:00:00"
    with pytest.raises(ValueError):
        validate_shipping_date(date)


@pytest.mark.parametrize(
    argnames="cost,expected",
    argvalues=(
        ("29.99", 29.99),
        ("-123.22", -123.22),
        ("7", 7.0),
        ("0.0000", 0.0),
        ("", 0.0),
    ),
)
def test_validate_shipping_cost(cost, expected):
    assert validate_shipping_cost(cost, 123) == expected


def test_validate_shipping_cost_failure():
    with pytest.raises(ValueError):
        validate_shipping_cost("ABC", 1)


def test_validate_shipping_method_success():
    assert validate_shipping_method("UPS Ground") == ShippingMethods.UPS_GROUND


def test_validate_shipping_method_with_new_shipping_method():
    assert validate_shipping_method("UPS Super Sonic Speed") == ShippingMethods.UNKNOWN


def test_validate_shipping_method_with_no_shipping_method():
    assert validate_shipping_method(None) is None


def test_validate_shipping_method_with_empty_str():
    assert validate_shipping_method(" ") is None


def test_generate_bms_orders_csv(create_valid_bms_kits):
    bms_orders = db.session.query(BMSOrder).all()
    bms_csv_report = generate_bms_orders_csv(bms_orders)

    bms_order_csv = list(csv.DictReader(bms_csv_report))
    bms_order_1 = bms_order_csv[0]

    assert len(bms_order_1["kit_shipment_city"]) == UPS_CHAR_LIMITS["shipment_city"]
    assert len(bms_order_1["kit_shipment_state"]) == UPS_CHAR_LIMITS["shipment_state"]
    assert (
        len(bms_order_1["kit_shipment_country"]) == UPS_CHAR_LIMITS["shipment_country"]
    )
    assert len(bms_order_1["user_email"]) == UPS_CHAR_LIMITS["user_email"]
    assert (
        len(bms_order_1["kit_shipment_recipient_name"])
        == UPS_CHAR_LIMITS["recipient_name"]
    )
    assert (
        bms_order_1["kit_shipment_shipping_address"]
        == "748 Adam Coves Suite|thelongeststreetnameintheworld"
    )
    assert (
        len(bms_order_1["kit_shipment_shipping_address"].split("|")[0])
        < UPS_CHAR_LIMITS["shipping_address"]
    )
    assert bms_order_1["kit_shipment_zip_code"] == "123456789"
    assert bms_order_1["kit_shipment_telephone_number"] == "+161789412345"


@pytest.mark.parametrize(
    argnames="field,char_limit,expected",
    argvalues=(("abcdef", 4, 4), ("1234567890", 5, 5)),
)
def test_truncate_field(field, char_limit, expected):
    assert len(truncate_field(field, char_limit)) == expected


def test_break_up_address_with_delimiter():
    address = "hello, this is address text to break up, with some reeeeeeeeeaaaaaaally long words"
    assert break_up_address_with_delimiter(None, 35, "|") is None
    assert break_up_address_with_delimiter("123 E 39th st", 35, "|") == "123 E 39th st"
    assert (
        break_up_address_with_delimiter(address, 35, "|")
        == "hello, this is address text to|break up, with "
        "some|reeeeeeeeeaaaaaaally long words"
    )


@pytest.mark.parametrize(
    argnames="zipcode,char_limit,expected",
    argvalues=(
        ("12345-6789", UPS_CHAR_LIMITS["shipment_zip_code"], "123456789"),
        ("12345-67", UPS_CHAR_LIMITS["shipment_zip_code"], "12345-67"),
        ("12345-67890000", UPS_CHAR_LIMITS["shipment_zip_code"], "123456789"),
        (None, UPS_CHAR_LIMITS["shipment_zip_code"], None),
    ),
)
def test_cleanup_zip_code(zipcode, char_limit, expected):
    assert cleanup_zip_code(zipcode, char_limit) == expected


@pytest.mark.parametrize(
    argnames="phone_number,char_limit,expected",
    argvalues=(
        (
            "+1-617-894 12345",
            UPS_CHAR_LIMITS["shipment_telephone_number"],
            "+161789412345",
        ),
        (
            "+1-617-894-0779",
            UPS_CHAR_LIMITS["shipment_telephone_number"],
            "+1-617-894-0779",
        ),
        (None, UPS_CHAR_LIMITS["shipment_zip_code"], None),
    ),
)
def test_cleanup_phone_number(phone_number, char_limit, expected):
    assert cleanup_phone_number(phone_number, char_limit) == expected


def test_ssh_connect_retry_on_timeout_raises_timeout_exception():
    with patch("paramiko.SSHClient") as mock_client:
        mock_client.connect.side_effect = paramiko.ssh_exception.SSHException
        with pytest.raises(TimeoutError):
            ssh_connect_retry_on_timeout(
                mock_client,
                "INDICIA_MOCK_HOST",
                port=22,
                username="INDICIA_MOCK_USERNAME",
                password="INDICIA_MOCK_PASSWORD",
                max_attempts=3,
            )


def test_ssh_connect_retry_on_timeout_succeeds():
    expected_conn = {
        "port": 22,
        "username": "INDICIA_MOCK_USERNAME",
        "password": "INDICIA_MOCK_PASSWORD",
    }
    with patch("paramiko.SSHClient") as mock_client:
        client = ssh_connect_retry_on_timeout(
            mock_client, "INDICIA_MOCK_HOST", **expected_conn, max_attempts=3
        )
        mock_client.connect.assert_called_once_with(
            "INDICIA_MOCK_HOST", **expected_conn
        )
        # Assert ssh_connect_retry_on_timeout returning client
        assert client == mock_client
