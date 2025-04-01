from flask import abort
from marshmallow import ValidationError
from maven import feature_flags

from appointments.schemas.v2.member_appointment import (
    MemberAppointmentByIdGetResponse,
    MemberAppointmentByIdServiceResponse,
)
from appointments.services.common import (
    deobfuscate_appointment_id,
    obfuscate_appointment_id,
)
from appointments.services.v2.member_appointment import MemberAppointmentService
from appointments.utils.errors import (
    AppointmentNotFoundException,
    MemberNotFoundException,
    ProviderNotFoundException,
)
from common.services.api import AuthenticatedResource
from utils import launchdarkly


class MemberAppointmentByIdResource(AuthenticatedResource):
    def get(self, appointment_id: int):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        """
        HTTP resource to get user's appointment by id

        @param appointment_id: obfuscated appointment_id
        """
        l10n_flag = feature_flags.bool_variation(
            "release-disco-be-localization",
            launchdarkly.user_context(self.user),
            default=False,
        )

        deobfuscated_appt_id = deobfuscate_appointment_id(appointment_id)
        try:
            appointment: MemberAppointmentByIdServiceResponse = (
                MemberAppointmentService().get_member_appointment_by_id(
                    self.user,
                    deobfuscated_appt_id,
                )
            )
        except ValidationError as e:
            abort(400, e.messages)
        except AppointmentNotFoundException as e:
            abort(404, e.message)
        except MemberNotFoundException as e:
            abort(500, e.message)
        except ProviderNotFoundException as e:
            abort(500, e.message)

        if l10n_flag:
            appointment = appointment.translate()

        schema = MemberAppointmentByIdGetResponse()
        response = schema.dump(appointment.get_response_dict())
        response["id"] = obfuscate_appointment_id(response["id"])
        return response
