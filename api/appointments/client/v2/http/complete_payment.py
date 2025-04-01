from flask import request
from flask_restful import abort
from marshmallow import ValidationError
from stripe.error import StripeError

from appointments.schemas.appointments_v3 import AppointmentV3Schema
from common.services.api import InternalServiceResource
from models.products import Product
from payments.services.appointment_payments import AppointmentPaymentsService
from storage.connection import db
from utils.log import logger

log = logger(__name__)


class AppointmentCompletePaymentResource(InternalServiceResource):
    def post(self):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        request_json = request.json if request.is_json else None
        try:
            request_data = AppointmentV3Schema().load(request_json)
            # Fetch product price
            product_id = request_data.get("product_id")
            product = db.session.query(Product).filter(Product.id == product_id).first()
            if product is None or product.price is None:
                log.error(f"product not found for product id {product_id}")
                abort(404, message="Product not found")

            success, amount = AppointmentPaymentsService(
                session=db.session
            ).complete_payment(
                appointment_id=request_data.get("appointment_id"),
                product_price=product.price,
            )
            return {"success": success}
        except StripeError as e:
            abort(503, message=e.user_message)
        except ValidationError:
            abort(400, message="Invalid request to complete payment")
