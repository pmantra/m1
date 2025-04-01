import io
from datetime import datetime
from unittest.mock import patch

import paramiko
import pytest

from bms.models.bms import OrderStatus, ShippingMethods
from bms.tasks.bms import process_bms_orders, upload_bms_orders
from pytests.factories import DefaultUserFactory


@patch("utils.slack_v2._notify_slack_channel")
@patch("bms.tasks.bms.upload_blob_from_memory")
@patch("bms.tasks.bms.is_date_qualified", return_value=True)
def test_upload_bms_orders_success(
    date, mock_sftp_upload_blob, slack_mail, create_valid_bms_order_set
):
    bms_orders = create_valid_bms_order_set
    assert bms_orders[0].status.value == OrderStatus.NEW.value

    upload_bms_orders()

    assert mock_sftp_upload_blob.call_count == 1

    assert bms_orders[0].status.value == OrderStatus.PROCESSING.value
    assert slack_mail.called
    assert (
        slack_mail.call_args[1]["notification_title"]
        == "Milk order file sent to vendor with 3 order(s)."
    )


@patch("bms.tasks.bms.upload_blob_from_memory")
@patch("utils.slack_v2._notify_slack_channel")
@patch("bms.tasks.bms.is_date_qualified", return_value=True)
def test_upload_bms_orders_ftp_failure(
    date, slack_mail, mock_sftp_upload_blob, create_valid_bms_order_set
):
    bms_orders = create_valid_bms_order_set
    assert bms_orders[0].status.value == OrderStatus.NEW.value

    mock_sftp_upload_blob.side_effect = TypeError

    with pytest.raises(TypeError):
        upload_bms_orders()

    assert mock_sftp_upload_blob.call_count == 1
    assert bms_orders[0].status.value == OrderStatus.NEW.value
    assert slack_mail.called
    assert (
        slack_mail.call_args[1]["notification_title"]
        == "Error uploading milk order csv to vendor"
    )


@patch("utils.slack_v2._notify_slack_channel")
@patch("bms.tasks.bms.is_date_qualified", return_value=True)
def test_upload_bms_orders_no_orders(date, slack_mail, create_invalid_bms_order_set):
    bms_orders = create_invalid_bms_order_set
    assert bms_orders[0].status.value == OrderStatus.CANCELLED.value

    upload_bms_orders()

    assert bms_orders[0].status.value == OrderStatus.CANCELLED.value
    assert slack_mail.called
    assert (
        slack_mail.call_args[1]["notification_title"] == "No milk orders found today."
    )


@patch("bms.tasks.bms.generate_bms_orders_csv")
@patch("utils.slack_v2._notify_slack_channel")
@patch("bms.tasks.bms.is_date_qualified", return_value=True)
def test_upload_bms_orders_csv_failure(
    date, slack_mail, csv, create_valid_bms_order_set
):
    csv.side_effect = ValueError

    bms_orders = create_valid_bms_order_set
    assert bms_orders[0].status.value == OrderStatus.NEW.value

    with pytest.raises(ValueError):
        upload_bms_orders()

    assert bms_orders[0].status.value == OrderStatus.NEW.value
    assert slack_mail.called
    assert (
        slack_mail.call_args[1]["notification_title"]
        == "Error creating milk order csv."
    )


@patch("utils.braze_events.send_bms_tracking_email")
@patch("bms.tasks.bms.download_bms_file_from_indicia")
@patch("utils.slack_v2._notify_slack_channel")
@patch("bms.tasks.bms.is_date_qualified", return_value=True)
@patch("bms.tasks.bms.emit_bulk_audit_log_update")
@patch("flask_login.current_user")
def test_process_bms_orders_success(
    mock_current_user,
    mock_emit_bulk_audit_log_update,
    date,
    slack_mail,
    mock_downloaded_file,
    braze_email,
    bms_bytes_blob,
    create_pump_and_post_factories,
    create_pump_and_carry_factories,
    patch_send_bm_tracking_email,
):
    mock_current_user.return_value = DefaultUserFactory.create()
    mock_emit_bulk_audit_log_update.return_value = None
    bms_order1, ship_one, milk_ship_two, bms_product = create_pump_and_post_factories
    assert bms_order1.status == OrderStatus.PROCESSING

    assert ship_one.id == 1
    assert ship_one.cost is None
    assert ship_one.shipped_at is None
    assert ship_one.tracking_numbers is None
    assert ship_one.shipping_method is None

    assert milk_ship_two.id == 2
    assert milk_ship_two.cost is None
    assert milk_ship_two.shipped_at is None
    assert milk_ship_two.tracking_numbers is None
    assert milk_ship_two.shipping_method is None

    bms_order2, ship_three, bms_product_two = create_pump_and_carry_factories
    assert bms_order2.status == OrderStatus.PROCESSING

    assert ship_three.id == 3
    assert ship_three.cost is None
    assert ship_three.shipped_at is None
    assert ship_three.tracking_numbers is None
    assert ship_three.shipping_method is None

    mock_downloaded_file.return_value = (
        f"bms-orders-{datetime.now().strftime('%y_%m_%d-%H_%M_%S')}.csv",
        bms_bytes_blob,
    )

    process_bms_orders()
    mock_emit_bulk_audit_log_update.assert_called_once()
    assert braze_email.call_count == 2
    assert slack_mail.called

    assert bms_order1.status == OrderStatus.FULFILLED
    assert bms_order2.status == OrderStatus.FULFILLED

    assert ship_one.tracking_numbers == "1Z9Y3Y280342676837"
    assert (
        milk_ship_two.tracking_numbers
        == "1Z9Y3Y280142470464, 1Z9Y3Y280142573657, 1Z9Y3Y280142820871, 1Z9Y3Y284442074446"
    )
    assert ship_three.tracking_numbers == "1Z9Y3Y280142314614"
    assert ship_three.shipping_method == ShippingMethods.UPS_2_DAY.value


@patch("bms.tasks.bms.download_bms_file_from_indicia")
@patch("utils.slack_v2._notify_slack_channel")
@patch("bms.tasks.bms.is_date_qualified", return_value=True)
def test_process_bms_orders_fail_sftp_login(
    date,
    slack_mail,
    mock_downloaded_file,
    create_pump_and_post_factories,
):
    bms_order1, ship_one, milk_ship_two, bms_product = create_pump_and_post_factories
    assert bms_order1.status == OrderStatus.PROCESSING

    mock_downloaded_file.side_effect = paramiko.ssh_exception.AuthenticationException

    with pytest.raises(paramiko.ssh_exception.AuthenticationException):
        process_bms_orders()

    assert mock_downloaded_file.call_count == 1
    assert slack_mail.called
    assert (
        slack_mail.call_args[1]["notification_title"]
        == "Error downloading milk order csv from vendor."
    )

    assert bms_order1.status == OrderStatus.PROCESSING


@patch("bms.tasks.bms.download_bms_file_from_indicia")
@patch("utils.slack_v2._notify_slack_channel")
@patch("bms.tasks.bms.is_date_qualified", return_value=True)
def test_process_bms_orders_no_file_found(
    date,
    slack_mail,
    mock_download_file,
    create_pump_and_post_factories,
):
    """This test cannot find the file to download"""
    bms_order1, ship_one, milk_ship_two, bms_product = create_pump_and_post_factories
    assert bms_order1.status == OrderStatus.PROCESSING

    mock_download_file.return_value = None, None
    process_bms_orders()

    assert mock_download_file.call_count == 1
    assert slack_mail.called
    assert (
        slack_mail.call_args[1]["notification_title"]
        == "File not found. No orders processed."
    )

    assert bms_order1.status == OrderStatus.PROCESSING


@patch("utils.slack_v2._notify_slack_channel")
@patch("bms.tasks.bms.download_bms_file_from_indicia")
@patch("bms.tasks.bms.is_date_qualified", return_value=True)
def test_process_bms_orders_fails_file_empty(
    date,
    mock_download_file,
    slack_mail,
    create_pump_and_post_factories,
    create_pump_and_carry_factories,
):
    """This test downloads an empty file"""
    bms_order1, ship_one, milk_ship_two, bms_product = create_pump_and_post_factories
    assert bms_order1.status == OrderStatus.PROCESSING

    mock_download_file.return_value = "filename", io.BytesIO(b"")

    with pytest.raises(ValueError):
        process_bms_orders()

    assert mock_download_file.call_count == 1
    assert slack_mail.called
    assert (
        slack_mail.call_args[1]["notification_title"]
        == "Error converting milk order csv from vendor."
    )

    assert bms_order1.status == OrderStatus.PROCESSING


@patch("bms.tasks.bms.download_bms_file_from_indicia")
@patch("utils.slack_v2._notify_slack_channel")
@patch("bms.tasks.bms.is_date_qualified", return_value=True)
def test_process_bms_orders_fails_file_missing_data(
    date,
    slack_mail,
    mock_download_file,
    incomplete_bms_bytes_blob,
    create_pump_and_post_factories,
):
    """This test downloads a file missing values"""
    bms_order1, ship_one, milk_ship_two, bms_product = create_pump_and_post_factories
    assert bms_order1.status == OrderStatus.PROCESSING

    mock_download_file.return_value = (
        f"bms-orders-{datetime.now().strftime('%y_%m_%d-%H_%M_%S')}.csv",
        incomplete_bms_bytes_blob,
    )

    with pytest.raises(ValueError):
        process_bms_orders()

    assert mock_download_file.call_count == 1
    assert slack_mail.called
    assert (
        slack_mail.call_args[1]["notification_title"]
        == "Error converting milk order csv from vendor."
    )

    assert bms_order1.status == OrderStatus.PROCESSING


@patch("bms.tasks.bms.download_bms_file_from_indicia")
@patch("utils.slack_v2._notify_slack_channel")
@patch("bms.tasks.bms.is_date_qualified", return_value=True)
@patch("flask_login.current_user")
def test_process_bms_orders_fails_shipment_not_found(
    mock_current_user,
    date,
    slack_mail,
    mock_download_file,
    wrong_order_bms_bytes_blob,
    create_pump_and_post_factories,
):
    """This test sets the wrong shipping id in the downloaded file"""
    mock_current_user.return_value = DefaultUserFactory.create()
    bms_order1, ship_one, milk_ship_two, bms_product = create_pump_and_post_factories
    assert bms_order1.status == OrderStatus.PROCESSING

    mock_download_file.return_value = (
        f"bms-orders-{datetime.now().strftime('%y_%m_%d-%H_%M_%S')}.csv",
        wrong_order_bms_bytes_blob,
    )

    with pytest.raises(ValueError):
        process_bms_orders()

    assert mock_download_file.call_count == 1
    assert slack_mail.called
    assert slack_mail.call_args[1]["notification_title"] == "BMSOrder not found!"

    assert bms_order1.status == OrderStatus.PROCESSING


@patch("bms.tasks.bms.download_bms_file_from_indicia")
@patch("utils.slack_v2._notify_slack_channel")
@patch("bms.tasks.bms.is_date_qualified", return_value=True)
def test_process_bms_orders_fails_shipment_bad_data(
    date,
    slack_mail,
    mock_download_file,
    bad_data_bms_bytes_blob,
    create_pump_and_post_factories,
):
    """This test sends a string "hello" for shipping cost"""
    bms_order1, ship_one, milk_ship_two, bms_product = create_pump_and_post_factories
    assert bms_order1.status == OrderStatus.PROCESSING

    mock_download_file.return_value = (
        f"bms-orders-{datetime.now().strftime('%y_%m_%d-%H_%M_%S')}.csv",
        bad_data_bms_bytes_blob,
    )

    with pytest.raises(ValueError):
        process_bms_orders()

    assert mock_download_file.call_count == 1
    assert slack_mail.called
    assert (
        slack_mail.call_args[1]["notification_title"]
        == "Kit Shipment not found or missing data."
    )

    assert bms_order1.status == OrderStatus.PROCESSING


@patch("bms.tasks.bms.download_bms_file_from_indicia")
@patch("utils.slack_v2._notify_slack_channel")
@patch("bms.tasks.bms.is_date_qualified", return_value=True)
@patch("bms.tasks.bms.emit_bulk_audit_log_update")
@patch("flask_login.current_user")
def test_process_bms_orders_skips_if_fulfilled(
    mock_current_user,
    mock_emit_bulk_audit_log_update,
    date,
    slack_mail,
    mock_downloaded_file,
    bms_bytes_blob,
    create_pump_and_post_factories,
    create_pump_and_carry_factories,
    patch_send_bm_tracking_email,
):
    mock_emit_bulk_audit_log_update.return_value = None
    bms_order1, ship_one, milk_ship_two, bms_product = create_pump_and_post_factories
    bms_order1.status = OrderStatus.FULFILLED
    bms_order2, ship_three, bms_product_two = create_pump_and_carry_factories

    assert bms_order2.status == OrderStatus.PROCESSING

    mock_downloaded_file.return_value = (
        f"bms-orders-{datetime.now().strftime('%y_%m_%d-%H_%M_%S')}.csv",
        bms_bytes_blob,
    )
    process_bms_orders()

    mock_emit_bulk_audit_log_update.assert_called_once()
    patch_send_bm_tracking_email.assert_called_once_with(
        [ship_three], bms_product_two, bms_order2
    )
    assert slack_mail.call_count == 1
