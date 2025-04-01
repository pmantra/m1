import asyncio

from flask import request
from flask_restful import abort
from marshmallow_v1 import ValidationError, fields
from sqlalchemy.orm.exc import NoResultFound

from appointments.models.appointment import Appointment
from appointments.services.common import deobfuscate_appointment_id
from common.services import ratelimiting
from common.services.api import AuthenticatedResource
from dosespot.constants import (
    DOSESPOT_GLOBAL_CLINIC_ID_V2,
    DOSESPOT_GLOBAL_CLINIC_KEY_V2,
    DOSESPOT_GLOBAL_CLINIC_USER_ID_V2,
)
from dosespot.resources.dosespot_api import DoseSpotAPI
from models.profiles import MemberProfile, PractitionerProfile
from providers.service.provider import ProviderService
from storage.connection import db
from utils.log import logger
from utils.marshmallow_experiment import marshmallow_experiment_enabled
from views.schemas.base import IntegerWithDefaultV3, MavenSchemaV3, StringWithDefaultV3
from views.schemas.common import DoseSpotPharmacySchema, MavenSchema, WithDefaultsSchema
from views.schemas.common_v3 import DoseSpotPharmacySchemaV3
from views.schemas.prescription import (
    PharmacySearchRequestSchemaV3,
    PharmacySearchResponseSchemaV3,
)

log = logger(__name__)


def validate_zip(value: str) -> None:
    if len(value) > 10:
        raise ValidationError(f"Bad zip_code: {value}")

    try:
        int(value)
    except ValueError:
        raise ValidationError(f"Bad zip_code: {value}")


class PharmacySearchSchema(WithDefaultsSchema):
    zip_code = fields.String(validate=validate_zip, required=True)
    pharmacy_name = fields.String(required=False)


class PharmacySearchSchemaV3(MavenSchemaV3):
    zip_code = StringWithDefaultV3(validate=validate_zip, required=True, default="")
    pharmacy_name = StringWithDefaultV3(required=False, default="")


class RefillTransmissionCountSchema(MavenSchema):
    refill_count = fields.Integer()
    transaction_count = fields.Integer()
    url = fields.String()


class RefillTransmissionCountSchemaV3(MavenSchemaV3):
    refill_count = IntegerWithDefaultV3(default=0)
    transaction_count = IntegerWithDefaultV3(default=0)
    url = StringWithDefaultV3(default="")


class DoseSpotResource(AuthenticatedResource):
    def _api(  # type: ignore[no-untyped-def] # Function is missing a return type annotation #type: ignore[no-untyped-def] # Function is missing a type annotation for one or more arguments
        self,
        practitioner: PractitionerProfile,
        message: str = "You are not enabled for ePrescribing.",
    ) -> DoseSpotAPI:
        if not ProviderService().enabled_for_prescribing(practitioner.user_id):
            abort(400, message=message)

        return DoseSpotAPI(
            clinic_id=DOSESPOT_GLOBAL_CLINIC_ID_V2,
            clinic_key=DOSESPOT_GLOBAL_CLINIC_KEY_V2,
            user_id=practitioner.dosespot["user_id"],
            maven_user_id=practitioner.user_id,
        )


class PharmacySearchResource(DoseSpotResource):
    @ratelimiting.ratelimited(attempts=6, cooldown=60)
    def get(self, appointment_id):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        # launch darkly flag
        experiment_enabled = marshmallow_experiment_enabled(
            "experiment-marshmallow-pharmacy-search-resource",
            self.user.esp_id if self.user else None,
            self.user.email if self.user else None,
            default=False,
        )
        schema = (
            PharmacySearchSchemaV3() if experiment_enabled else PharmacySearchSchema()
        )
        args = (
            schema.load(request.args)  # type: ignore[attr-defined]
            if experiment_enabled
            else schema.load(request.args).data  # type: ignore[attr-defined]
        )

        appointment_id = deobfuscate_appointment_id(appointment_id)
        try:
            appointment = (
                db.session.query(Appointment)
                .filter(Appointment.id == appointment_id)
                .one()
            )
        except NoResultFound:
            abort(404)

        if self.user.id != appointment.member_id:
            abort(403, message="Not Authorized!")

        try:
            practitioner = (
                db.session.query(PractitionerProfile)
                .filter(PractitionerProfile.user_id == int(appointment.practitioner_id))
                .one()
            )
        except NoResultFound:
            abort(404)

        api = self._api(
            practitioner,
            "This practitioner is not enabled for ePrescribing.",
        )
        pharmacies = asyncio.run(
            api.pharmacy_search(args["zip_code"], args.get("pharmacy_name"))
        )

        if experiment_enabled:
            schema = DoseSpotPharmacySchemaV3()
            return schema.dump(pharmacies, many=True)
        else:
            schema = DoseSpotPharmacySchema()
            return schema.dump(pharmacies, many=True).data


class PharmacySearchResourceV2(AuthenticatedResource):
    @ratelimiting.ratelimited(attempts=6, cooldown=60)
    def get(self):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        request_schema = PharmacySearchRequestSchemaV3()
        args = {}
        try:
            args = request_schema.load(request.args)
        except Exception as e:
            log.error("Failed to parse pharmacy search request", error=e)
            abort(400, message="Invalid request")

        page_number = args["page_number"] if args.get("page_number") else 1
        try:
            api = DoseSpotAPI(
                clinic_id=DOSESPOT_GLOBAL_CLINIC_ID_V2,
                clinic_key=DOSESPOT_GLOBAL_CLINIC_KEY_V2,
                user_id=DOSESPOT_GLOBAL_CLINIC_USER_ID_V2,
                maven_user_id=self.user.id,
            )
            pharmacies, pagination = api.paginated_pharmacy_search(
                page_number=page_number,
                zipcode=args.get("zip_code"),
                pharmacy_name=args.get("pharmacy_name"),
            )
            response_schema = PharmacySearchResponseSchemaV3()
            response = {"data": pharmacies, "pagination": pagination}
            return response_schema.dump(response)
        except Exception as e:
            log.error("Failed to get pharmacy search result", exception=e)
            abort(500)


class RefillTransmissionErrorCountsResource(DoseSpotResource):
    @ratelimiting.ratelimited(attempts=6, cooldown=60)
    def get(self, practitioner_id):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        if not self.user.id == practitioner_id:
            abort(403, message="Can only get this for yourself!")

        try:
            practitioner = (
                db.session.query(PractitionerProfile)
                .filter(PractitionerProfile.user_id == int(practitioner_id))
                .one()
            )
        except NoResultFound:
            abort(404)

        # launch darkly flag
        experiment_enabled = marshmallow_experiment_enabled(
            "experiment-marshmallow-refill-transmission-error-counts-resource",
            self.user.esp_id if self.user else None,
            self.user.email if self.user else None,
            default=False,
        )

        api = self._api(practitioner)
        data = api.refills_and_transmission_counts()
        data["url"] = api.practitioner_refill_errors_request_url()

        schema = (
            RefillTransmissionCountSchemaV3()
            if experiment_enabled
            else RefillTransmissionCountSchema()
        )
        # Note: Counts are hardcoded on the front end to display as 9 if >9, for space reasons.
        return schema.dump(data) if experiment_enabled else schema.dump(data).data  # type: ignore[attr-defined]


class PatientDetailsURLResource(DoseSpotResource):
    @ratelimiting.ratelimited(attempts=10, cooldown=(5 * 60))
    def get(self, appointment_id):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        # TODO: maybe only allow once per appontment?
        appointment_id = deobfuscate_appointment_id(appointment_id)

        try:
            appointment = (
                db.session.query(Appointment)
                .filter(Appointment.id == appointment_id)
                .one()
            )
        except NoResultFound:
            abort(404)

        if self.user.id != appointment.practitioner_id:
            abort(403, message="Not Authorized!")

        try:
            mp = (
                db.session.query(MemberProfile)
                .filter(MemberProfile.user_id == appointment.member_id)
                .one()
            )
        except NoResultFound:
            abort(404)

        if not mp.enabled_for_prescription:
            abort(400, message="Member info not complete!")

        try:
            practitioner = (
                db.session.query(PractitionerProfile)
                .filter(PractitionerProfile.user_id == int(self.user.id))
                .one()
            )
        except NoResultFound:
            abort(404)

        api = self._api(practitioner)
        patient_id, url = api.patient_details_request(appointment, create_patient=True)

        if patient_id:
            mp.set_patient_info(
                patient_id=patient_id, practitioner_id=appointment.practitioner_id
            )
            db.session.add(mp)
            db.session.commit()

        if url:
            return {"url": url}
        else:
            abort(
                400,
                message=(
                    "Error creating patient, please try again. The "
                    "most common error here is an incorrect patient address"
                ),
            )
