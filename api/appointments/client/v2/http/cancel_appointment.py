from flask import request
from flask_restful import abort
from marshmallow import ValidationError

from appointments.schemas.v2.cancel_appointment import (
    ProviderCancelAppointmentRequestSchema,
)
from appointments.schemas.v2.member_appointment import (
    MemberAppointmentByIdGetResponse,
    MemberAppointmentByIdServiceResponse,
)
from appointments.services.common import (
    deobfuscate_appointment_id,
    obfuscate_appointment_id,
)
from appointments.services.v2.cancel_appointment_service import CancelAppointmentService
from appointments.services.v2.member_appointment import MemberAppointmentService
from appointments.utils.errors import (
    AppointmentAlreadyCancelledException,
    AppointmentCancelledByUserIdNotFoundException,
    AppointmentNotFoundException,
    AppointmentNotInCancellableStateException,
    ErrorFetchingCancellationPolicy,
    QueryError,
)
from common.services.api import AuthenticatedResource


class CancelAppointmentResource(AuthenticatedResource):
    def post(self, appointment_id: int):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        deobfuscated_appt_id = deobfuscate_appointment_id(appointment_id)

        cancelled_note = None
        request_json = request.json if request.is_json else None
        # When a provider calls the endpoint to cancel, the request might contain cancelled_note
        if request_json is not None:
            request_schema = ProviderCancelAppointmentRequestSchema()
            request_data = request_schema.load(request_json)
            cancelled_note = request_data.get("cancelled_note")

        try:
            CancelAppointmentService().cancel_appointment(
                user=self.user,
                appointment_id=deobfuscated_appt_id,
                cancelled_note=cancelled_note,  # type: ignore[arg-type] # Argument "cancelled_note" to "cancel_appointment" of "CancelAppointmentService" has incompatible type "Optional[Any]"; expected "str"
            )
        except ValidationError:
            abort(400, message="Invalid request to cancel an appointment")
        except AppointmentAlreadyCancelledException as e:
            abort(400, message=e.message)
        except AppointmentNotFoundException as e:
            abort(404, message=e.message)
        except AppointmentNotInCancellableStateException as e:
            abort(409, message=e.message)
        except AppointmentCancelledByUserIdNotFoundException:
            abort(
                500,
                message="Cancelled_by_user_id not found, appointment is not cancelled",
            )
        except ErrorFetchingCancellationPolicy as e:
            abort(500, message=e.message)
        except QueryError as e:
            abort(500, message=e.message)

        appointment: (
            MemberAppointmentByIdServiceResponse
        ) = MemberAppointmentService().get_member_appointment_by_id(
            user=self.user,
            appointment_id=deobfuscated_appt_id,
            skip_check_permissions=True,
        )

        schema = MemberAppointmentByIdGetResponse()
        response = schema.dump(appointment.get_response_dict())
        response["id"] = obfuscate_appointment_id(response["id"])
        return response
