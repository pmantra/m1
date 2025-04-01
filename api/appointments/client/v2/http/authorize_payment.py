from flask import request
from flask_restful import abort
from marshmallow import ValidationError

from appointments.schemas.appointments_v3 import AppointmentV3Schema
from appointments.utils.errors import ProductNotFoundException
from common.services.api import InternalServiceResource
from payments.services.appointment_payments import AppointmentPaymentsService
from storage.connection import db


class AppointmentReservePaymentResource(InternalServiceResource):
    def post(self):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        request_json = request.json if request.is_json else None
        try:
            request_data = AppointmentV3Schema().load(request_json)
            res = AppointmentPaymentsService(session=db.session).authorize_payment(
                appointment_id=request_data.get("appointment_id"),
                product_id=request_data.get("product_id"),
                member_id=request_data.get("member_id"),
                scheduled_start=request_data.get("scheduled_start"),
            )
            success = True if res else False
            return {"success": success}

        except ValidationError:
            abort(400, message="Invalid request to authorize payment")
        except ProductNotFoundException:
            abort(404, message="Product not found")
