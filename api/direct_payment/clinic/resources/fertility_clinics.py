from flask import request
from flask_restful import abort
from marshmallow import ValidationError

from direct_payment.clinic.repository import clinic
from direct_payment.clinic.resources.clinic_auth import ClinicAuthorizedResource
from direct_payment.clinic.schemas.fertility_clinics import (
    FertilityClinicArgsSchema,
    FertilityClinicsSchema,
)
from utils.log import logger

log = logger(__name__)


class FertilityClinicsResource(ClinicAuthorizedResource):
    """
    Get and update fertility clinics.

    Searches by fertility clinic id and returns fertility clinic object.

    Right now we only have a need to update the fertility clinic's payments_recipient_id by api.
    """

    def __init__(self) -> None:
        super().__init__()
        self.clinics = clinic.FertilityClinicRepository()

    def get(self, fertility_clinic_id: int):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        clinic = self.clinics.get(fertility_clinic_id=fertility_clinic_id)
        schema = FertilityClinicsSchema()
        return schema.dump(clinic)

    def put(self, fertility_clinic_id: int):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        in_schema = FertilityClinicArgsSchema()

        try:
            args = in_schema.load(request.json if request.is_json else {})
        except ValidationError as e:
            abort(400, message=str(e.messages))

        updated_clinic = self.clinics.put(
            fertility_clinic_id=fertility_clinic_id,
            payments_recipient_id=args["payments_recipient_id"],
        )
        schema = FertilityClinicsSchema()
        return schema.dump(updated_clinic)
