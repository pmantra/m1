from __future__ import annotations

import csv
import datetime
import enum
import io
import socket
from typing import List

import paramiko
from google.cloud import storage

from bms.constants import (
    BMS_SHIPPING_BUSINESS_DAYS,
    FTP_HOST,
    FTP_PASSWORD,
    FTP_USERNAME,
    INDICIA_DOWNLOAD_PATH,
    INDICIA_ITEM_NUMBERS,
    SHIPPING_BLACKOUT_DATES,
)
from bms.models.bms import BMSOrder, BMSShipment, OrderStatus, ShippingMethods
from common import stats
from common.constants import Environment
from utils.log import logger
from utils.slack_v2 import notify_bms_alerts_channel

log = logger(__name__)

UPS_CHAR_LIMITS = {
    "recipient_name": 35,
    "shipping_address": 35,
    "shipment_city": 30,
    "shipment_state": 30,
    "shipment_zip_code": 9,
    "shipment_country": 50,
    "user_email": 50,
    "shipment_telephone_number": 15,
}


class EnterMilkShipmentManually(ValueError):
    pass


class FTPBucket(str, enum.Enum):
    QA2 = "12344593-8e7b-4418-a5ba-cb2970f1042"
    PROD = "mvn-df3528g-data-sender-eventarc"


def generate_bms_orders_csv(orders: List) -> io.StringIO:
    report = io.StringIO()
    writer = csv.DictWriter(
        report,
        fieldnames=[
            "order_id",
            "user_id",
            "created_at",
            "travel_start_date",
            "travel_end_date",
            "products",
            "indicia_item_number",
            "quantity",
            "user_email",
            "kit_shipment_id",
            "kit_shipment_recipient_name",
            "kit_shipment_residential_address",
            "kit_shipment_accomodation_name",
            "kit_shipment_telephone_number",
            "kit_shipment_shipping_address",
            "kit_shipment_city",
            "kit_shipment_state",
            "kit_shipment_zip_code",
            "kit_shipment_country",
            "milk_shipment_id",
            "milk_shipment_friday_shipping",
            "milk_shipment_recipient_name",
            "milk_shipment_residential_address",
            "milk_shipment_telephone_number",
            "milk_shipment_shipping_address",
            "milk_shipment_city",
            "milk_shipment_state",
            "milk_shipment_zip_code",
            "milk_shipment_country",
        ],
        extrasaction="ignore",
    )
    writer.writeheader()

    for order in orders:
        kit_shipments = []
        milk_shipment = None
        for shipment in order.shipments:
            if len(shipment.products) >= 1:
                kit_shipments.append(shipment)
            else:
                milk_shipment = shipment
        for kit_shipment in kit_shipments:
            kit_address = kit_shipment.address
            milk_address = milk_shipment and milk_shipment.address
            kit_shipment_product = kit_shipment.products[0]
            writer.writerow(
                {
                    "order_id": order.id,
                    "user_id": order.user_id,
                    "created_at": order.created_at,
                    "travel_start_date": order.travel_start_date,
                    "travel_end_date": order.travel_end_date,
                    "products": kit_shipment_product.bms_product.name,
                    "indicia_item_number": INDICIA_ITEM_NUMBERS[
                        kit_shipment_product.bms_product.name
                    ],
                    "quantity": kit_shipment_product.quantity,
                    "user_email": truncate_field(
                        order.user.email, UPS_CHAR_LIMITS["user_email"]
                    ),
                    "kit_shipment_id": kit_shipment.id,
                    "kit_shipment_recipient_name": truncate_field(
                        kit_shipment.recipient_name,
                        UPS_CHAR_LIMITS["recipient_name"],
                    ),
                    "kit_shipment_residential_address": kit_shipment.residential_address,
                    "kit_shipment_accomodation_name": kit_shipment.accommodation_name,
                    "kit_shipment_telephone_number": cleanup_phone_number(
                        kit_shipment.tel_number,
                        UPS_CHAR_LIMITS["shipment_telephone_number"],
                    ),
                    "kit_shipment_shipping_address": break_up_address_with_delimiter(
                        kit_address.street_address,
                        UPS_CHAR_LIMITS["shipping_address"],
                        "|",
                    ),
                    "kit_shipment_city": truncate_field(
                        kit_address.city, UPS_CHAR_LIMITS["shipment_city"]
                    ),
                    "kit_shipment_state": truncate_field(
                        kit_address.state, UPS_CHAR_LIMITS["shipment_state"]
                    ),
                    "kit_shipment_zip_code": cleanup_zip_code(
                        kit_address.zip_code, UPS_CHAR_LIMITS["shipment_zip_code"]
                    ),
                    "kit_shipment_country": truncate_field(
                        kit_address.country, UPS_CHAR_LIMITS["shipment_country"]
                    ),
                    "milk_shipment_id": milk_shipment and milk_shipment.id,
                    "milk_shipment_friday_shipping": milk_shipment
                    and milk_shipment.friday_shipping,
                    "milk_shipment_recipient_name": milk_shipment
                    and truncate_field(
                        milk_shipment.recipient_name,
                        UPS_CHAR_LIMITS["recipient_name"],
                    ),
                    "milk_shipment_residential_address": milk_shipment
                    and milk_shipment.residential_address,
                    "milk_shipment_telephone_number": milk_shipment
                    and cleanup_phone_number(
                        milk_shipment.tel_number,
                        UPS_CHAR_LIMITS["shipment_telephone_number"],
                    ),
                    "milk_shipment_shipping_address": milk_address
                    and break_up_address_with_delimiter(
                        milk_address.street_address,
                        UPS_CHAR_LIMITS["shipping_address"],
                        "|",
                    ),
                    "milk_shipment_city": milk_address
                    and truncate_field(
                        milk_address.city, UPS_CHAR_LIMITS["shipment_city"]
                    ),
                    "milk_shipment_state": milk_address
                    and truncate_field(
                        milk_address.state, UPS_CHAR_LIMITS["shipment_state"]
                    ),
                    "milk_shipment_zip_code": milk_address
                    and cleanup_zip_code(
                        milk_address.zip_code, UPS_CHAR_LIMITS["shipment_zip_code"]
                    ),
                    "milk_shipment_country": milk_address
                    and truncate_field(
                        milk_address.country, UPS_CHAR_LIMITS["shipment_country"]
                    ),
                }
            )
    report.seek(0)
    return report


def get_submittable_bms_orders(
    filter_date: datetime.date | None = None,
) -> list[BMSOrder]:
    """
    Queries for all BMSOrders that fall within a range of dates and have an order status of NEW
    Returns a list of BMSOrder object ids if found otherwise returns None

    @param filter_date: The first date to filter the travel_start_date by
    """
    if filter_date is None:
        filter_date = datetime.date.today()
    business_date = get_last_business_date(start_date=filter_date)
    bms_orders = BMSOrder.query.filter(
        BMSOrder.travel_start_date.between(filter_date, business_date),
        BMSOrder.status == OrderStatus.NEW.value,
    )
    return bms_orders.all()


def get_last_business_date(
    business_days: int = BMS_SHIPPING_BUSINESS_DAYS,
    start_date: datetime.date | None = None,
) -> datetime.date:
    """
    Returns a datetime of the calculated n business day after a given start_date

    @param business_days: The amount of business days
    @param start_date: The date you begin to count business days from
    """
    if start_date is None:
        start_date = datetime.date.today()
    while business_days > 0:
        start_date = start_date + datetime.timedelta(days=1)
        weekday = start_date.weekday()
        if weekday >= 5:  # sunday = 6
            continue
        if start_date in SHIPPING_BLACKOUT_DATES:
            continue
        business_days -= 1
    return start_date


def is_date_qualified(date: datetime.date) -> bool:
    """
    Returns True if the date is not a weekend or a holiday

    @param date: The date we are checking
    """
    weekday = date.weekday()
    if weekday == 5 or weekday == 6:
        return False
    if date in SHIPPING_BLACKOUT_DATES:
        return False
    return True


def return_file_name(filenames: list[str]) -> str | None:
    """
    Returns a filename if found from a list of files otherwise None

    @param filenames: A list of files retrieved from the indicia server folder for downloading processed orders.
    """
    today_file = f"bms-orders-{datetime.datetime.now().strftime('%y_%m_%d-')}"
    if filenames:
        for filename in filenames:
            if filename.startswith(today_file):
                return filename
    return None


def convert_orders_to_dicts(file: io.BytesIO) -> list[dict]:
    """
    Converts bytes file to string file so that it can be formatted to read and format each line of a file.
    Returns a list of dictionaries (each dictionary is a row from the file)

    @param file: downloaded file as an bytesIO object
    """
    bms_orders = []
    file.seek(0)  # type: ignore[attr-defined] # "bytes" has no attribute "seek"
    read_file = file.read()  # type: ignore[attr-defined] # "bytes" has no attribute "read"
    if len(read_file) > 0:
        file_text = read_file.decode("UTF-8")
        file_string = io.StringIO(file_text)
        reader = csv.reader(file_string)
        next(reader)
        for row in reader:
            if len(row) < 6 or len(row) > 13:
                raise ValueError("Data in file is missing or improperly formatted.")
            order_id = row[0]
            kit_shipment_id = row[1]
            order_fulfilled_at = row[2]
            kit_tracking_numbers = row[3]
            kit_shipment_cost = row[4]
            kit_shipping_method = row[5]
            milk_shipment_id = None
            milk_tracking_numbers = None
            milk_shipment_cost = None
            milk_shipping_method = None
            if len(row) > 6:
                milk_shipment_id = row[6]
                milk_tracking_numbers = row[7]
                milk_shipment_cost = row[8]
                milk_shipping_method = row[9]

            bms_orders.append(
                {
                    "order_id": order_id,
                    "kit_shipment_id": kit_shipment_id,
                    "order_fulfilled_at": order_fulfilled_at,
                    "kit_tracking_numbers": kit_tracking_numbers,
                    "kit_shipment_cost": kit_shipment_cost,
                    "kit_shipping_method": kit_shipping_method,
                    "milk_shipment_id": milk_shipment_id,
                    "milk_tracking_numbers": milk_tracking_numbers,
                    "milk_shipment_cost": milk_shipment_cost,
                    "milk_shipping_method": milk_shipping_method,
                }
            )
    if bms_orders:
        return bms_orders
    else:
        raise ValueError("File empty or only contains headers.")


def validate_shipping_date(date_text: str) -> datetime.datetime:
    try:
        date_string, time = date_text.split(" ")
        time_segments = len(time.split(":"))
        date_format = "%m/%d/%Y" if "/" in date_string else "%Y-%m-%d"
        if time_segments < 3:
            return datetime.datetime.strptime(date_text, f"{date_format} %H:%M")
        else:
            return datetime.datetime.strptime(date_text, f"{date_format} %H:%M:%S")
    except ValueError:
        raise ValueError("Date format could not be validated.")


def validate_shipping_method(ship_method: str | None) -> ShippingMethods | None:
    if ship_method is None or ship_method.strip() == "":
        return None
    elif ShippingMethods.has_value(ship_method):
        return ShippingMethods(ship_method)
    else:
        return ShippingMethods.UNKNOWN


def validate_shipping_cost(shipping_cost: str, shipment_id: int) -> float:
    try:
        if shipping_cost == "":
            return float(0)
        if float(shipping_cost) <= 0:
            log.warning(
                f"process_bms_orders: Shipping cost negative or zero: {shipping_cost}, bms_shipment_id: {shipment_id}"
            )
        return float(shipping_cost)
    except ValueError:
        raise ValueError(f"Shipping cost is a non-numeric value: {shipping_cost}")


def update_kit_shipment(order: dict) -> BMSShipment:
    """
    Queries for the BMSShipment and updates the fields found from the order.
    Returns BMSShipment object.

    @param order: a dictionary of values representing one order
    """
    shipment_id = order.get("kit_shipment_id")
    bms_order_id = order.get("order_id")
    if shipment_id and bms_order_id:
        kit_shipment = BMSShipment.query.filter_by(
            id=shipment_id, bms_order_id=bms_order_id
        ).one_or_none()
        if kit_shipment:
            shipped_at = validate_shipping_date(order["order_fulfilled_at"])
            kit_ship_method = validate_shipping_method(order.get("kit_shipping_method"))
            kit_ship_cost = validate_shipping_cost(
                order["kit_shipment_cost"], shipment_id
            )

            kit_shipment.cost = kit_ship_cost
            kit_shipment.shipment_method = kit_ship_method
            kit_shipment.tracking_numbers = order.get("kit_tracking_numbers")
            kit_shipment.shipped_at = shipped_at
            return kit_shipment
        else:
            raise ValueError(
                f"Missing BMSShipment for shipment_id: {shipment_id} and bms_order_id: {bms_order_id}"
            )
    else:
        raise ValueError("Missing bms_order_id or shipment_id from file.")


def update_milk_shipment(order: dict, milk_shipment_id: int) -> BMSShipment:
    """
    Queries for the BMSShipment and updates the fields found from the order only if milk_shipment_is is present.
    Returns BMSShipment object.

    @param order: a dictionary of values representing one order
    @param milk_shipment_id: a string passed in from the order dictionary
    """
    bms_order_id = order.get("order_id")
    milk_shipment = BMSShipment.query.filter_by(
        id=milk_shipment_id, bms_order_id=bms_order_id
    ).one_or_none()

    def is_empty_field(order_field: str | None) -> bool:
        return order_field is None or order_field.strip() == ""

    if milk_shipment:
        if (
            is_empty_field(order.get("milk_shipping_method"))
            and is_empty_field(order.get("milk_shipment_cost"))
            and is_empty_field(order.get("milk_tracking_numbers"))
        ):
            raise EnterMilkShipmentManually(
                "This shipping label has not yet been created. The BMS team must update the shipment in admin."
            )
        milk_ship_method = validate_shipping_method(order.get("milk_shipping_method"))
        milk_shipment.cost = validate_shipping_cost(
            order.get("milk_shipment_cost", ""), milk_shipment_id
        )
        milk_shipment.shipment_method = milk_ship_method
        milk_shipment.tracking_numbers = order.get("milk_tracking_numbers")

        return milk_shipment
    else:
        raise ValueError(
            f"Missing BMSShipment for shipment_id: {milk_shipment_id} and bms_order_id: {bms_order_id}"
        )


def send_bms_error(slack_title, slack_message, metric_name):  # type: ignore[no-untyped-def] # Function is missing a type annotation
    stats.increment(
        metric_name=metric_name,
        pod_name=stats.PodNames.PAYMENTS_POD,
        tags=["error:true", f"error_cause:{metric_name}"],
    )
    notify_bms_alerts_channel(
        notification_title=slack_title,
        notification_body=slack_message,
    )


def upload_blob_from_memory(contents: io.StringIO, destination_blob_name: str) -> None:
    """Uploads a file to the bucket."""

    # The ID of your GCS bucket
    # bucket_name = "your-bucket-name"

    # The contents to upload to the file
    # contents = "these are my contents"

    # The ID of your GCS object
    # destination_blob_name = "storage-object-name"

    bucket_name = (
        FTPBucket.PROD
        if Environment.current() == Environment.PRODUCTION
        else FTPBucket.QA2
    )
    storage_client = storage.Client()
    bucket = storage_client.bucket(bucket_name)
    blob = bucket.blob(f"indicia/{destination_blob_name}")

    csv_contents = contents.getvalue()
    blob.upload_from_string(csv_contents)

    log.info(
        "File uploaded to bucket.",
        destination_blob_name=destination_blob_name,
        bucket_name=bucket_name,
    )


def download_bms_file_from_indicia() -> tuple[str, io.BytesIO]:
    """
    Logs into the Indicia SFTP server. Moves into the downloaded file folder and looks for the file from today.
    If found, write the file to the buffer file.

    Returns the filename and written file
    """
    downloaded_file = io.BytesIO()
    sftp = None
    if FTP_USERNAME is None or FTP_PASSWORD is None:
        raise ValueError(
            "Missing Username and Password for bms indicia file download. Not attempting ssh connection."
        )
    client = ssh_connect(
        FTP_HOST, username=FTP_USERNAME, password=FTP_PASSWORD, max_attempts=3
    )
    try:
        log.debug("process_bms_orders: Attempting to download the file.")
        sftp = client.open_sftp()
        sftp.chdir(INDICIA_DOWNLOAD_PATH)
        files = sftp.listdir()
        filename = return_file_name(files) or ""
        if filename:
            sftp.getfo(filename, downloaded_file)
    except Exception as e:
        if sftp:
            sftp.close()
        client.close()
        log.exception("process_bms_orders: Error opening or downloading file.", error=e)
        raise e
    else:
        log.debug("process_bms_orders: File downloaded.")
        sftp.close()
        client.close()
        return filename, downloaded_file


def ssh_connect(hostname, port=22, username=None, password=None, max_attempts=1):  # type: ignore[no-untyped-def] # Function is missing a type annotation
    """A wrapper for paramiko, returns a SSHClient after it connects."""
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    try:
        ssh_connect_retry_on_timeout(
            client,
            hostname,
            port=port,
            username=username,
            password=password,
            max_attempts=max_attempts,
        )
    except TimeoutError as e:
        log.exception(
            f"process_bms_orders: SFTP Connection timed out, attempts={max_attempts}.",
            error=e,
        )
        raise e
    except (
        paramiko.AuthenticationException,
        paramiko.BadHostKeyException,
        paramiko.SSHException,
        socket.error,
    ) as e:
        log.exception("process_bms_orders: SFTP Connection Failed.", error=e)
        raise e
    return client


def ssh_connect_retry_on_timeout(  # type: ignore[no-untyped-def] # Function is missing a type annotation
    client, hostname, port=22, username=None, password=None, max_attempts=1
):
    if max_attempts <= 0:
        log.exception(
            "process_bms_orders: SFTP Connection Failed, retry exceeded max attempts."
        )
        raise TimeoutError
    else:
        try:
            client.connect(hostname, port=port, username=username, password=password)
            return client
        except (paramiko.SSHException, socket.error):
            return ssh_connect_retry_on_timeout(
                client,
                hostname,
                port=port,
                username=username,
                password=password,
                max_attempts=max_attempts - 1,
            )


def truncate_field(field: str, char_limit: int) -> str:
    """Truncates string based on char limit provided"""

    return (field[:char_limit]) if len(field) > char_limit else field


def break_up_address_with_delimiter(
    address: str | None, line_char_limit: int, delimeter: str
) -> str | None:
    if address is None:
        return None

    if len(address) <= line_char_limit:
        return address

    address_arr = address.split(" ")
    expected_address_arr = []
    address = ""
    for word in address_arr:
        if len(address + " " + word) < line_char_limit:
            if len(address) > 0:
                address += " "
            address += word
        else:
            expected_address_arr.append(address)
            expected_address_arr.append(delimeter)
            address = word

    expected_address_arr.append(address)

    return "".join(expected_address_arr)


def cleanup_zip_code(zip_code: str | None, char_limit: int) -> str | None:
    if zip_code is None:
        return None

    if len(zip_code) <= char_limit:
        return zip_code

    clean_zipcode = zip_code.replace("-", "")

    if len(clean_zipcode) > char_limit:
        clean_zipcode = truncate_field(clean_zipcode, char_limit)

    return clean_zipcode


def cleanup_phone_number(phone_number: str | None, char_limit: int) -> str | None:
    if phone_number is None:
        return None

    if len(phone_number) <= char_limit:
        return phone_number

    return phone_number.replace("-", "").replace(" ", "")


def notify_on_new_shipment_method(
    shipment_method: ShippingMethods | None,
    unknown_shipment_name: str | None,
) -> None:
    if shipment_method == ShippingMethods.UNKNOWN:
        notify_bms_alerts_channel(
            notification_title=f"Unknown shipping method found: {unknown_shipment_name}",
            notification_body="There is a new shipping method that came from the "
            "Indicia file. Please update shipping method accordingly",
        )
