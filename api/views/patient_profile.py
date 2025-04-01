import asyncio
import json

from flask import request
from flask_restful import abort
from marshmallow import Schema, fields
from marshmallow.exceptions import ValidationError

from common.services import ratelimiting
from common.services.api import AuthenticatedResource
from dosespot.constants import (
    DOSESPOT_GLOBAL_CLINIC_ID_V2,
    DOSESPOT_GLOBAL_CLINIC_KEY_V2,
    DOSESPOT_GLOBAL_CLINIC_USER_ID_V2,
)
from dosespot.resources.dosespot_api import DoseSpotAPI
from models.profiles import MemberProfile
from storage.connection import db
from utils.log import logger

log = logger(__name__)


class V3DoseSpotPharmacySchema(Schema):
    PharmacyId = fields.String()
    Pharmacy = fields.String(default=None, allow_none=True)
    State = fields.String()
    ZipCode = fields.String()
    PrimaryFax = fields.String(default=None, allow_none=True)
    StoreName = fields.String()
    Address1 = fields.String()
    Address2 = fields.String(default=None, allow_none=True)
    PrimaryPhone = fields.String()
    PrimaryPhoneType = fields.String(default=None, allow_none=True)
    City = fields.String()


class PatientProfileSchema(Schema):
    user_id = fields.Integer()
    pharmacy_id = fields.String(default=None, allow_none=True)
    pharmacy_info = fields.Nested(
        V3DoseSpotPharmacySchema, default=None, allow_none=True
    )


class V3PharmacySearchSchema(Schema):
    zip_code = fields.String(required=True)


class PatientProfileResource(AuthenticatedResource):
    def get(self, user_id):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        member_profile = MemberProfile.query.filter(
            MemberProfile.user_id == user_id
        ).one()
        if not member_profile or not self._practitioner_or_same_user(user_id):
            abort(404, message="Cannot access patient profile")

        patient_profile = {**member_profile.get_prescription_info(), "user_id": user_id}

        schema = PatientProfileSchema()
        return schema.dump(patient_profile), 200

    def patch(self, user_id):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        args = PatientProfileSchema().load(json.loads(request.data))
        member_profile = MemberProfile.query.filter(
            MemberProfile.user_id == user_id
        ).one()
        if not member_profile or self.user.id != user_id:
            abort(404, message="Cannot access patient profile")

        new_pharmacy_info = {}
        if args.get("pharmacy_id"):
            new_pharmacy_info["pharmacy_id"] = args.get("pharmacy_id")
        if args.get("pharmacy_info"):
            new_pharmacy_info["pharmacy_info"] = args.get("pharmacy_info")
        if new_pharmacy_info:
            member_profile.set_prescription_info(**new_pharmacy_info)
            self._update_dosespot_pharmacy_info(
                member_profile, new_pharmacy_info["pharmacy_id"]
            )
            db.session.add(member_profile)
            db.session.commit()

        patient_profile = {**member_profile.get_prescription_info(), "user_id": user_id}

        schema = PatientProfileSchema()
        return schema.dump(patient_profile), 200

    def _practitioner_or_same_user(self, user_id: int) -> bool:
        if not self.user.is_practitioner and self.user.id != user_id:
            return False
        return True

    def _update_dosespot_pharmacy_info(  # type: ignore[no-untyped-def] # Function is missing a return type annotation #type: ignore[no-untyped-def] # Function is missing a type annotation for one or more arguments
        self, member_profile: MemberProfile, pharmacy_id
    ):
        api = DoseSpotAPI(
            clinic_id=DOSESPOT_GLOBAL_CLINIC_ID_V2,
            clinic_key=DOSESPOT_GLOBAL_CLINIC_KEY_V2,
            user_id=DOSESPOT_GLOBAL_CLINIC_USER_ID_V2,
            maven_user_id=self.user.id,
        )
        user_id = member_profile.user_id
        dosespot_info = member_profile.dosespot
        dosespot_data = [
            dosespot_info.get(key)
            for key in dosespot_info.keys()
            if "practitioner:" in key
        ]
        for entry in dosespot_data:
            if entry.get("patient_id") is not None:
                result = api.add_patient_pharmacy(
                    user_id, entry.get("patient_id"), pharmacy_id
                )
                if result is None:
                    log.warning(
                        "Error updating pharmacy information for Member Profile User: (%s) Dosespot Patient Id: (%s) Dosespot Pharmacy Id: (%s)",
                        user_id,
                        entry.get("patient_id"),
                        pharmacy_id,
                    )


class NonAppointmentPharmacySearchResource(AuthenticatedResource):
    @ratelimiting.ratelimited(attempts=6, cooldown=60)
    def get(self):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        args = self._load_args(request.args)
        api = DoseSpotAPI(
            clinic_id=DOSESPOT_GLOBAL_CLINIC_ID_V2,
            clinic_key=DOSESPOT_GLOBAL_CLINIC_KEY_V2,
            user_id=DOSESPOT_GLOBAL_CLINIC_USER_ID_V2,
            maven_user_id=self.user.id,
        )
        pharmacies = asyncio.run(api.pharmacy_search(args["zip_code"]))
        schema = V3DoseSpotPharmacySchema()
        return {"data": schema.dump(pharmacies, many=True)}, 200

    def _load_args(self, args):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        schema = V3PharmacySearchSchema()
        try:
            return schema.load(args)
        except ValidationError:
            abort(400, message="Missing data for required field")
