import datetime

import flask_login as login
from sqlalchemy.sql import func

from audit_log.utils import emit_bulk_audit_log_update
from authn.models.user import User
from bms.models.bms import BMSOrder, OrderStatus
from bms.utils.bms import (
    EnterMilkShipmentManually,
    convert_orders_to_dicts,
    download_bms_file_from_indicia,
    generate_bms_orders_csv,
    get_submittable_bms_orders,
    is_date_qualified,
    notify_on_new_shipment_method,
    send_bms_error,
    update_kit_shipment,
    update_milk_shipment,
    upload_blob_from_memory,
)
from common import stats
from storage.connection import db
from tasks.queues import job
from utils import braze_events
from utils.log import logger
from utils.slack import notify_bms_channel
from utils.slack_v2 import notify_bms_alerts_channel

log = logger(__name__)


@job
def check_for_unfulfilled_orders() -> None:
    """
    Check for orders with a travel_start_date within 48 hours or less, without a shipped_at date, and order status is
    not cancelled.
    Notify the Slack channel #mavenmilkorders with order details if unfulfilled orders found
    """
    unfulfilled_orders = (
        db.session.query(BMSOrder)
        .filter(
            BMSOrder.travel_start_date <= func.current_date() + 2,
            BMSOrder.fulfilled_at.is_(None),
            BMSOrder.status != OrderStatus.CANCELLED,
        )
        .all()
    )

    for order in unfulfilled_orders:
        notify_bms_order_no_fulfilled_at_date(order.id, order.travel_start_date)

    n_unfulfilled_orders = len(unfulfilled_orders)
    log.info(
        "Sent Slack message(s) to channel #mavenmilkorders regarding unfulfilled orders.",
        n_unfulfilled_orders=n_unfulfilled_orders,
    )


def notify_bms_order_no_fulfilled_at_date(bms_order_id, travel_start_date):  # type: ignore[no-untyped-def] # Function is missing a type annotation
    """
    Notify the Slack channel #mavenmilkorders with order details if unfulfilled orders found
    """
    message = (
        f"<!channel> Order id: {bms_order_id} "
        "does not have a fulfilled at date from "
        f"Indicia, with a travel start date of {travel_start_date}"
    )
    notify_bms_channel(message)


@job(traced_parameters=("user_id", "bms_order_id"))
def notify_about_bms_order(user_id, bms_order_id):  # type: ignore[no-untyped-def] # Function is missing a type annotation
    message = (
        "User {} has placed a new breast milk shipping order! "
        "Order id: {}".format(user_id, bms_order_id)
    )
    notify_bms_channel(message)
    braze_events.bms_order_received(User.query.get(user_id))


@job
def notify_bms_travel_end_date() -> None:
    p24 = datetime.datetime.utcnow() - datetime.timedelta(hours=24)
    now = datetime.datetime.utcnow()

    recently_ended_bms_orders = (
        db.session.query(BMSOrder)
        .filter(BMSOrder.travel_end_date >= p24, BMSOrder.travel_end_date < now)
        .all()
    )

    for bms_order in recently_ended_bms_orders:
        braze_events.bms_travel_end_date(bms_order.user, bms_order.travel_end_date)


@job
def upload_bms_orders() -> None:
    """
    Uploads BMS orders csv to vendor INDICIA
    """
    today = datetime.date.today()
    if is_date_qualified(today):
        metric_name = "api.bms.tasks.upload_bms_orders"
        log.debug("upload_bms_orders: Starting job to upload bms csv.")

        bms_orders = get_submittable_bms_orders()
        if bms_orders:
            bms_order_ids = [order.id for order in bms_orders]
            try:
                bms_csv = generate_bms_orders_csv(bms_orders)
            except Exception as e:
                stats.increment(
                    metric_name=metric_name,
                    pod_name=stats.PodNames.PAYMENTS_POD,
                    tags=["error:true", "error_cause:generate_bms_orders_csv"],
                )
                log.warning(
                    f"Error creating BMS csv. BMSOrders: {bms_order_ids}. Exception: {e}"
                )
                notify_bms_alerts_channel(
                    notification_title="Error creating milk order csv.",
                    notification_body=f"An error encountered when creating the csv. Orders not uploaded: {bms_order_ids}",
                )
                raise e
            filename = f"bms-orders-{datetime.datetime.now().strftime('%y_%m_%d-%H_%M_%S')}.csv"
            try:
                upload_blob_from_memory(bms_csv, filename)
            except Exception as e:
                log.info(f"There was an error uploading the blob {e}")
                stats.increment(
                    metric_name=metric_name,
                    pod_name=stats.PodNames.PAYMENTS_POD,
                    tags=["error:true", "error_cause:failed_upload_bms_orders"],
                )
                log.warning(
                    f"Error uploading BMS csv. BMSOrders: {bms_order_ids}. Exception: {e}"
                )
                notify_bms_alerts_channel(
                    notification_title="Error uploading milk order csv to vendor",
                    notification_body=f"An error encountered when uploading milk order to vendor. Error message: {e}"
                    f"for ids: {bms_order_ids}",
                )
                raise e
            # update all BMSOrders status to PROCESSING
            for order in bms_orders:
                order.status = OrderStatus.PROCESSING  # type: ignore
                db.session.add(order)
            db.session.commit()

            stats.increment(
                metric_name=metric_name,
                pod_name=stats.PodNames.PAYMENTS_POD,
                tags=["success:true"],
            )
            log.debug("upload_bms_orders: Completing job to upload bms order csv.")
            notify_bms_alerts_channel(
                notification_title=f"Milk order file sent to vendor with {len(bms_order_ids)} order(s).",
                notification_body=f"Successfully uploaded milk order csv for order ids: {bms_order_ids}.",
            )
        else:
            notify_bms_alerts_channel(
                notification_title="No milk orders found today.",
                notification_body="There were no milk orders to submit. No csv uploaded.",
            )


@job
def process_bms_orders() -> None:
    """
    Downloads BMS orders csv to vendor INDICIA via SFTP.
    """
    today = datetime.date.today()
    if is_date_qualified(today):
        metric_name = "api.bms.tasks.process_bms_orders"
        log.debug("process_bms_orders: Starting job to download bms csv.")
        try:
            # Download the file from Indicia
            filename, downloaded_file = download_bms_file_from_indicia()
            if not filename:
                notify_bms_alerts_channel(
                    notification_title="File not found. No orders processed.",
                    notification_body="No file found - No milk orders processed - no orders updated.",
                )
                return
        except Exception as error:
            log.warning(
                f"process_bms_orders: Error downloading BMS csv within SFTP server. Exception: {error}"
            )
            send_bms_error(
                "Error downloading milk order csv from vendor.",
                "An error encountered when downloading milk order to vendor."
                " Please manually check and process today's file. "
                f" Error message: {error}",
                metric_name,
            )
            raise error
        try:
            # Convert each row item in the csv file into a dictionary.
            fetched_bms_shipments = convert_orders_to_dicts(downloaded_file)
        except (IndexError, ValueError) as error:
            log.warning(
                f"process_bms_orders: Error converting file. Exception: {error}"
            )
            send_bms_error(
                "Error converting milk order csv from vendor.",
                "An error encountered when converting milk order from vendor."
                " Please manually check and process today's file. "
                f"Error message: {error}",
                metric_name,
            )
            raise error
        # Process BMSShipment and update BMSOrder to FULFILLED
        bms_shipment_ids = []
        bms_order_ids = []
        bulk_audit_log_updates = []
        for fetched_shipment in fetched_bms_shipments:
            bms_order_id = fetched_shipment.get("order_id")
            bms_order = BMSOrder.query.get(bms_order_id)
            if bms_order and bms_order.status != OrderStatus.FULFILLED:
                try:
                    kit_shipment = update_kit_shipment(fetched_shipment)
                    if kit_shipment:
                        notify_on_new_shipment_method(
                            kit_shipment.shipment_method,  # type: ignore
                            fetched_shipment.get("kit_shipping_method"),
                        )
                        db.session.add(kit_shipment)
                        bms_shipment_ids.append(kit_shipment.id)

                        # Update the BMS order here - in case there isn't a milk shipment
                        bms_order = kit_shipment.bms_order
                        bms_order.status = OrderStatus.FULFILLED
                        bms_order.fulfilled_at = kit_shipment.shipped_at
                        db.session.add(bms_order)
                        bulk_audit_log_updates.append(bms_order)
                        bms_order_ids.append(bms_order.id)
                except ValueError as error:
                    log.warning(
                        f"process_bms_orders: Kit Shipment not found or missing order data. Error: {error}"
                    )
                    send_bms_error(
                        "Kit Shipment not found or missing data.",
                        f"Please manually check and process today's file. Error: {error}",
                        metric_name,
                    )
                    raise error

                milk_shipment_id = fetched_shipment.get("milk_shipment_id")
                if milk_shipment_id:
                    try:
                        milk_shipment = update_milk_shipment(
                            fetched_shipment, milk_shipment_id
                        )
                        if milk_shipment:
                            notify_on_new_shipment_method(
                                milk_shipment.shipment_method,  # type: ignore
                                fetched_shipment.get("milk_shipping_method"),
                            )
                            db.session.add(milk_shipment)
                            bms_shipment_ids.append(milk_shipment.id)
                    except EnterMilkShipmentManually:
                        log.warning(
                            "process_bms_orders: Milk shipment without shipping data found.",
                            milk_shipment_id=milk_shipment_id,
                        )
                        # by using notify_bms here directly, we skip updating the error metric in send_bms_error
                        notify_bms_alerts_channel(
                            notification_title="Milk Shipment missing data.",
                            notification_body=f"Please manually check and process the shipment for order {milk_shipment_id} for today's file.",
                        )
                        notify_bms_channel(
                            f"Please manually check and process the shipment for order {milk_shipment_id} for today's file.",
                        )
                        # we also skip re-raising the error here as this is an expected circumstance
                    except ValueError as error:
                        log.warning(
                            f"process_bms_orders: Milk Shipment error for id: {milk_shipment_id}. Error: {error}",
                            milk_shipment_id=milk_shipment_id,
                        )
                        send_bms_error(
                            "Milk Shipment not found or missing data.",
                            f"Please manually check and process today's file. Error: {error}",
                            metric_name,
                        )
                        raise error
            else:
                if not bms_order:
                    send_bms_error(
                        "BMSOrder not found!",
                        "Please manually check and process today's file.",
                        metric_name,
                    )
                    raise ValueError(
                        f"Missing BMSOrder for bms_order_id: {bms_order_id}."
                    )
        user = login.current_user
        # if user is available this means we are not in a cron job. This will only emit audit logs
        # that have a flask request context with a user
        if user:
            emit_bulk_audit_log_update(bulk_audit_log_updates)
        db.session.commit()

        log.debug("process_bms_orders: Finishing job to download bms csv.")
        for bms_id in bms_order_ids:
            bms_order = BMSOrder.query.filter_by(id=bms_id).one()
            if bms_order.status == OrderStatus.FULFILLED:
                bms_shipments = sorted(
                    bms_order.shipments, key=lambda shipment: shipment.id
                )
                bms_product = bms_shipments[0].products[0].bms_product
                braze_events.send_bms_tracking_email(
                    bms_shipments, bms_product, bms_order
                )
                log.debug("sent tracking email for BMS order id %s ", bms_order.id)

        notify_bms_alerts_channel(
            notification_title=f"{len(bms_order_ids)} milk orders were processed today.",
            notification_body=f"File processing complete. Successfully updated Kit/Milk Shipments for BMS order ids: {bms_order_ids}.",
        )
