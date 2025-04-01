from flask import abort, request

from common.global_procedures.procedure import ProcedureService
from direct_payment.clinic.resources.clinic_auth import ClinicAuthorizedResource
from direct_payment.clinic.schemas.procedures import FertilityClinicProceduresSchema
from direct_payment.clinic.services.clinic import FertilityClinicService
from storage.connection import db


class FertilityClinicProceduresResource(ClinicAuthorizedResource):
    def get(self, fertility_clinic_id: int):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        gps = FertilityClinicService(
            session=db.session
        ).get_global_procedure_ids_and_costs_for_clinic(
            fertility_clinic_id=fertility_clinic_id
        )

        if not gps:
            abort(404, "Global Procedures not found.")

        gp_ids = [gp["procedure_id"] for gp in gps]

        procedures = ProcedureService().get_procedures_by_ids(
            procedure_ids=gp_ids,
            headers=request.headers,  # type: ignore[arg-type] # Argument "headers" to "get_procedures_by_ids" of "ProcedureService" has incompatible type "EnvironHeaders"; expected "Optional[Mapping[str, str]]"
        )
        for procedure in procedures:
            gp = next(gp for gp in gps if gp["procedure_id"] == procedure["id"])  # type: ignore[typeddict-item] # TypedDict "PartialProcedure" has no key "id"
            procedure["cost"] = gp["cost"]  # type: ignore[typeddict-unknown-key] # TypedDict "GlobalProcedure" has no key "cost" #type: ignore[typeddict-unknown-key] # TypedDict "PartialProcedure" has no key "cost"

        return FertilityClinicProceduresSchema().dump(procedures, many=True)
