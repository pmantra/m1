from functools import wraps
from typing import Callable

import ddtrace
from flask.typing import ResponseReturnValue
from flask_restful import Resource, abort

from appointments.models.appointment import Appointment
from appointments.repository.appointment import AppointmentRepository
from appointments.services.common import deobfuscate_appointment_id


@ddtrace.tracer.wrap()
def with_valid_appointment(f: Callable[[Resource, Appointment], ResponseReturnValue]):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
    @wraps(f)
    def decorated_function(*args, **kwargs) -> ResponseReturnValue:  # type: ignore[no-untyped-def] # Function is missing a type annotation for one or more arguments
        resource: Resource = args[0]  # request handler context object
        appointment_api_id = kwargs.pop("appointment_api_id")
        if not appointment_api_id:
            abort(400)

        # path provided appt id will always be obfuscated
        appointment_id: int = deobfuscate_appointment_id(int(appointment_api_id or 0))
        appointment: Appointment = AppointmentRepository().get_by_id(appointment_id)
        if not appointment:
            abort(404)

        # ensure requestor is a participant
        user_id = resource.user.id
        if user_id not in [
            appointment.member_id,
            appointment.practitioner_id,
        ]:
            abort(401)

        # we already paid the cost of fetching the appointment, make it
        # available to the request handler, should it need it
        kwargs["appointment"] = appointment
        return f(*args, **kwargs)

    return decorated_function
