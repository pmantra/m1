from __future__ import annotations

from traceback import format_exc
from typing import Optional, Union

from flask import request
from marshmallow import ValidationError

from common.global_procedures.procedure import MissingProcedureData
from direct_payment.clinic.models.portal import MemberLookupResponse
from direct_payment.clinic.resources.clinic_auth import ClinicAuthorizedResource
from direct_payment.clinic.schemas.patient import PatientLookupPOSTRequestSchema
from utils.log import logger
from wallet.services.member_lookup import MemberLookupService

log = logger(__name__)


class MemberLookupResource(ClinicAuthorizedResource):
    def __init__(self) -> None:
        super().__init__()
        self.member_lookup_service = MemberLookupService()

    def post(self) -> tuple[Union[MemberLookupResponse, str], int]:
        request_schema = PatientLookupPOSTRequestSchema()

        try:
            args = request_schema.load(request.json)

            response: Optional[
                MemberLookupResponse
            ] = self.member_lookup_service.lookup(**args, headers=request.headers)

            if response is None:
                return "Member not found", 404

            return response, 200
        except ValidationError:
            log.exception("validation error", exc=format_exc())
            return "Validation error", 400
        except MissingProcedureData:
            log.exception("missing procedure error", exc=format_exc())
            return (
                "Cannot retrieve patient data due to lack of Global Procedure data.",
                500,
            )
        except Exception:
            log.exception("generic exception encountered", exc=format_exc())
            return "Exception encountered", 500
