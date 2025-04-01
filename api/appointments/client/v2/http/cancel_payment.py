from flask import request
from flask_restful import abort
from marshmallow import ValidationError

from appointments.schemas.appointments_v3 import AppointmentV3Schema
from appointments.services.v2.cancel_appointment_service import (
    AppointmentPaymentsService,
)
from appointments.utils.errors import (
    AppointmentNotFoundException,
    ErrorFetchingCancellationPolicy,
    QueryError,
)
from common.services.api import InternalServiceResource
from models.products import Product
from storage.connection import db
from utils.log import logger

log = logger(__name__)


class AppointmentProcessPaymentForCancel(InternalServiceResource):
    def post(self):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        request_json = request.json if request.is_json else None
        try:
            request_data = AppointmentV3Schema().load(request_json)

            user_id = self.user.id
            appointment_id = request_data.get("appointment_id")
            provider_id = request_data.get("provider_id")
            member_id = request_data.get("member_id")

            service = AppointmentPaymentsService(session=db.session)
            if user_id == provider_id:
                log.info(
                    "Starting to cancel appointment for practitioner",
                    appointment_id=appointment_id,
                    member_id=member_id,
                )
                service.handle_cancel_appointment_by_practitioner_fees(
                    appointment_id=appointment_id,
                )
            elif user_id == member_id:
                log.info(
                    "Starting to cancel appointment for member",
                    appointment_id=appointment_id,
                    member_id=member_id,
                )
                scheduled_start = request_data.get("scheduled_start")

                product_id = request_data.get("product_id")
                product = (
                    db.session.query(Product).filter(Product.id == product_id).first()
                )
                if product is None or product.price is None:
                    log.error(f"product not found for product id {product_id}")
                    abort(404, message="Product not found")
                service.handle_cancel_appointment_by_member_fees(
                    appointment_id=appointment_id,
                    product_id=product_id,
                    member_id=member_id,
                    scheduled_start=scheduled_start,
                    product_price=product.price,
                    admin_initiated=False,
                )
            else:
                log.error(
                    "Not canceling appointment payment for unaffiliated user",
                    appointment_id=appointment_id,
                    user_id=user_id,
                )
                abort(
                    400,
                    message="Invalid request to cancel payment with unaffiliated user",
                )

            return {"success": True}
        except AppointmentNotFoundException as e:
            abort(404, message=e.message)
        except ErrorFetchingCancellationPolicy as e:
            abort(500, message=e.message)
        except QueryError as e:
            abort(500, message=e.message)
        except ValidationError:
            abort(400, message="Invalid request to cancel payment")
