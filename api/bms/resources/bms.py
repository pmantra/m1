from flask import request
from flask_restful import abort
from marshmallow import ValidationError

from bms.models.bms import BMSOrder, BMSProduct, BMSShipment, BMSShipmentProducts
from bms.schemas.bms import BMSOrderPostSchema, BMSOrderSchema
from bms.tasks.bms import notify_about_bms_order
from common.services.api import AuthenticatedResource
from eligibility import service as e9y_service
from eligibility.e9y import model as e9y_model
from models.profiles import Address
from storage.connection import db
from utils.log import logger
from utils.service_owner_mapper import service_ns_team_mapper

log = logger(__name__)


class BMSOrdersResource(AuthenticatedResource):
    def post(self):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        order_schema = BMSOrderPostSchema()
        error_message = None
        user = self.user
        try:
            data = order_schema.load(request.json if request.is_json else {})
        except ValidationError as err:
            # This is the best practice: https://marshmallow.readthedocs.io/en/stable/quickstart.html#validation
            # errors is a dict containing the field names as keys and list of error messages as the value
            log.exception("BMS Validation Error")
            errors = err.messages
            dict_values = list(errors.values())  # type: ignore[union-attr] # Item "List[str]" of "Union[List[str], List[Any], Dict[Any, Any]]" has no attribute "values" #type: ignore[union-attr] # Item "List[Any]" of "Union[List[str], List[Any], Dict[Any, Any]]" has no attribute "values"
            if (
                len(dict_values) > 0
                and isinstance(dict_values, list)
                and len(dict_values[0]) > 0
                and isinstance(dict_values[0], list)
            ):
                error_message = dict_values[0][0]
            else:
                error_message = "BMS validation error"
        error_message = error_message or _validate_bms_order(user, data)
        if error_message:
            log.warning(f"BMS Validation Error: {error_message} for user_id {user.id}")
            abort(400, error=f"{error_message}")

        outbound_shipments, return_shipments = _create_shipments(data)

        bms_order = BMSOrder(
            user=user,
            is_work_travel=data.get("is_work_travel"),
            travel_start_date=data["travel_start_date"],
            travel_end_date=data.get("travel_end_date"),
            shipments=outbound_shipments + return_shipments,
            terms=data["terms"],
            external_trip_id=data.get("external_trip_id", None),
        )
        db.session.add(bms_order)
        db.session.commit()

        service_ns_tag = "breast_milk_shipping"
        team_ns_tag = service_ns_team_mapper.get(service_ns_tag)
        notify_about_bms_order.delay(
            self.user.id, bms_order.id, service_ns=service_ns_tag, team_ns=team_ns_tag
        )
        bms_order_schema = BMSOrderSchema()
        bms_order_schema.context = {
            "outbound_shipments": outbound_shipments,
            "return_shipments": return_shipments,
        }
        bms_data = bms_order_schema.dump(bms_order)
        return (
            bms_data,
            201,
        )


def _validate_bms_order(user, data):  # type: ignore[no-untyped-def] # Function is missing a type annotation
    # Avoid circular import
    from tracks import service as tracks

    track_svc = tracks.TrackSelectionService()
    if not track_svc.is_enterprise(user_id=user.id):
        return "User has no org role"
    organization = track_svc.get_organization_for_user(user_id=user.id)
    if not organization or not organization.bms_enabled:  # type: ignore[union-attr] # Item "None" of "Optional[Organization]" has no attribute "bms_enabled"
        return "BMS Not enabled for user's org."
    # Hotfix for Google
    if _user_org_is_google(organization_id=organization.id):  # type: ignore[union-attr] # Item "None" of "Optional[Organization]" has no attribute "id"
        error_message = None
        if not data.get("external_trip_id"):
            error_message = "BMS validation error: trip_id required"

        e9y_svc = e9y_service.EnterpriseVerificationService()
        verification: e9y_model.EligibilityVerification = (
            e9y_svc.get_verification_for_user_and_org(
                user_id=user.id, organization_id=organization.id
            )
        )
        dependent_relationship_code = (
            verification.record.get("dependent_relationship_code", None)
            if verification
            else None
        )
        if (
            not dependent_relationship_code
            or dependent_relationship_code.strip() != "Employee"
        ):
            error_message = "Ineligible Order"

        if error_message:
            log.info(
                f"Invalid BMS submission for Google employee - {user.id}"
                f"valid trip_id: {bool(data.get('external_trip_id'))}, "
                f"valid dependent_relationship_code: {dependent_relationship_code == 'Employee'} "
                f"{error_message}"
            )
        return error_message


def _user_org_is_google(organization_id: int) -> bool:
    return organization_id == 191


def _create_shipments(data):  # type: ignore[no-untyped-def] # Function is missing a type annotation
    friday_shipping = data["travel_start_date"].isoweekday() == 6
    products_by_name = {p.name: p for p in db.session.query(BMSProduct).all()}
    outbound_shipments, return_shipments = [], []
    for shipment_info in data["outbound_shipments"]:
        products = shipment_info.pop("products")
        shipment = BMSShipment(
            address=Address(**shipment_info.pop("address")),
            friday_shipping=friday_shipping,
            **shipment_info,
        )
        _add_products(shipment, products, products_by_name)
        outbound_shipments.append(shipment)
    for shipment_info in data.get("return_shipments", []):
        return_shipments.append(
            BMSShipment(
                address=Address(**shipment_info.pop("address")), **shipment_info
            )
        )
    return outbound_shipments, return_shipments


def _add_products(shipment, products, products_by_type):  # type: ignore[no-untyped-def] # Function is missing a type annotation
    for product in products:
        bms_product = products_by_type.get(product["bms_product"]["name"])
        if bms_product is None:
            raise ValidationError(
                f"Unknown product type: {product['bms_product']['name']}"
            )
        db.session.add(
            BMSShipmentProducts(
                bms_shipment=shipment,
                bms_product=bms_product,
                quantity=product["quantity"],
            )
        )
