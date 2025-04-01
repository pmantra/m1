from bms.models.bms import BMSOrder, BMSProduct, BMSShipment, OrderStatus
from bms.pytests.factories import BMSOrderFactory, BMSShipmentFactory


def test_tracking_email_event_for_pump_and_post(
    create_pump_and_post_factories, patch_send_bm_tracking_email
):
    (
        bms_order_one,
        shipment_one,
        shipment_two,
        bms_product,
    ) = create_pump_and_post_factories
    shipment_one.tracking_numbers = "123abc"
    shipment_two.tracking_numbers = "456def,789ghi"
    patch_send_bm_tracking_email(
        [shipment_one, shipment_two], bms_product, bms_order_one
    )

    patch_send_bm_tracking_email.assert_called_once_with(
        [shipment_one, shipment_two], bms_product, bms_order_one
    )
    assert (
        type(patch_send_bm_tracking_email.call_args_list[0].args[0][0]) is BMSShipment
    )
    assert (
        patch_send_bm_tracking_email.call_args_list[0].args[0][0].id
        < patch_send_bm_tracking_email.call_args_list[0].args[0][1].id
    )
    assert len(patch_send_bm_tracking_email.call_args_list[0].args[0]) == 2
    assert (
        patch_send_bm_tracking_email.call_args_list[0].args[0][0].tracking_numbers
        == "123abc"
    )
    assert (
        patch_send_bm_tracking_email.call_args_list[0].args[0][1].tracking_numbers
        == "456def,789ghi"
    )
    assert type(patch_send_bm_tracking_email.call_args_list[0].args[1]) is BMSProduct
    assert type(patch_send_bm_tracking_email.call_args_list[0].args[2]) is BMSOrder
    assert (
        patch_send_bm_tracking_email.call_args_list[0].args[1].name == "pump_and_post"
    )


def test_tracking_email_event_for_pump_and_carry(
    create_pump_and_carry_factories, patch_send_bm_tracking_email
):
    bms_order_one, shipment_one, bms_product = create_pump_and_carry_factories
    shipment_one.tracking_numbers = "123abc"
    patch_send_bm_tracking_email([shipment_one], bms_product, bms_order_one)

    patch_send_bm_tracking_email.assert_called_once_with(
        [shipment_one], bms_product, bms_order_one
    )
    assert (
        type(patch_send_bm_tracking_email.call_args_list[0].args[0][0]) is BMSShipment
    )
    assert len(patch_send_bm_tracking_email.call_args_list[0].args[0]) == 1
    assert (
        patch_send_bm_tracking_email.call_args_list[0].args[0][0].tracking_numbers
        == "123abc"
    )
    assert type(patch_send_bm_tracking_email.call_args_list[0].args[1]) is BMSProduct
    assert type(patch_send_bm_tracking_email.call_args_list[0].args[2]) is BMSOrder
    assert (
        patch_send_bm_tracking_email.call_args_list[0].args[1].name == "pump_and_carry"
    )


def test_tracking_email_event_for_pump_and_check(
    create_pump_and_carry_factories, patch_send_bm_tracking_email
):
    bms_order_one, shipment_one, bms_product = create_pump_and_carry_factories
    bms_product.name = "pump_and_check"
    shipment_one.tracking_numbers = "123abc"
    patch_send_bm_tracking_email([shipment_one], bms_product, bms_order_one)

    patch_send_bm_tracking_email.assert_called_once_with(
        [shipment_one], bms_product, bms_order_one
    )
    assert (
        type(patch_send_bm_tracking_email.call_args_list[0].args[0][0]) is BMSShipment
    )
    assert len(patch_send_bm_tracking_email.call_args_list[0].args[0]) == 1
    assert (
        patch_send_bm_tracking_email.call_args_list[0].args[0][0].tracking_numbers
        == "123abc"
    )
    assert type(patch_send_bm_tracking_email.call_args_list[0].args[1]) is BMSProduct
    assert type(patch_send_bm_tracking_email.call_args_list[0].args[2]) is BMSOrder
    assert (
        patch_send_bm_tracking_email.call_args_list[0].args[1].name == "pump_and_check"
    )


def test_tracking_for_bms_pump_and_check(patch_braze_bms_check_order):
    bms_order = BMSOrderFactory(id=3, status=OrderStatus.PROCESSING)
    bms_shipment = BMSShipmentFactory(id=3, bms_order=bms_order)
    bms_shipment.tracking_numbers = "abc123"

    patch_braze_bms_check_order(order=bms_order, shipment=bms_shipment)

    patch_braze_bms_check_order.assert_called_once_with(
        order=bms_order, shipment=bms_shipment
    )
    assert (
        type(patch_braze_bms_check_order.call_args_list[0].kwargs["order"]) is BMSOrder
    )
    assert patch_braze_bms_check_order.call_args_list[0].kwargs["order"].id == 3
    assert (
        patch_braze_bms_check_order.call_args_list[0]
        .kwargs["shipment"]
        .tracking_numbers
        == "abc123"
    )
