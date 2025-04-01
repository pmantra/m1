from marshmallow import Schema, fields
from sqlalchemy.orm import joinedload
from sqlalchemy.orm.exc import NoResultFound

from authn.models.user import User
from common.services.api import PermissionedCareTeamResource
from models.FHIR.allergy import AllergyIntolerance
from models.FHIR.careTeam import CareTeam
from models.FHIR.condition import Condition
from models.FHIR.managed_benefits import ManagedBenefitsInfo
from models.FHIR.medication import MedicationStatement
from models.FHIR.observation import Observation
from models.FHIR.patient import FHIRPatientSchemaData
from models.FHIR.patient_tracks import PatientTracks
from models.FHIR.pharmacy import PharmacyInfo
from models.FHIR.wallet import WalletInfo
from storage.connection import db
from views.schemas.FHIR.allergy import FHIRAllergyIntoleranceSchema
from views.schemas.FHIR.careTeam import FHIRCareTeamMemberSchema
from views.schemas.FHIR.condition import FHIRConditionSchema
from views.schemas.FHIR.managed_benefits import ManagedBenefitsInfoSchema
from views.schemas.FHIR.medication import FHIRMedicationStatementSchema
from views.schemas.FHIR.observation import FHIRObservationSchema
from views.schemas.FHIR.patient import FHIRPatientSchema
from views.schemas.FHIR.patient_track import PatientTracksSchema
from views.schemas.FHIR.pharmacy import FHIRPharmacyInfoSchema
from views.schemas.FHIR.wallet import WalletInfoSchema


class PatientHealthResourceSchema(Schema):
    patient = fields.Nested(FHIRPatientSchema)
    careTeam = fields.Nested(FHIRCareTeamMemberSchema, many=True)
    medicationStatement = fields.List(fields.Nested(FHIRMedicationStatementSchema))
    condition = fields.List(fields.Nested(FHIRConditionSchema))
    allergyIntolerance = fields.List(fields.Nested(FHIRAllergyIntoleranceSchema))
    observation = fields.List(fields.Nested(FHIRObservationSchema))
    pharmacyInfo = fields.Nested(FHIRPharmacyInfoSchema)
    tracks = fields.Nested(PatientTracksSchema)
    walletInformation = fields.Nested(WalletInfoSchema)
    managedBenefits = fields.Nested(ManagedBenefitsInfoSchema)
    zendesk_user_id = fields.String()


class FHIRPatientHealthResource(PermissionedCareTeamResource):
    """
    Faux-gateway endpoint to supply FHIR formatted data to the front end.

    Note: This is an PermissionedCareTeamResource, not a PermissionedUserResource
    as it can be used to view data for users other than yourself.
    """

    def get(self, user_id):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        try:
            user = (
                db.session.query(User)
                .filter(User.id == user_id)
                .options(joinedload(User.health_profile))
                .one()
            )
        except NoResultFound:
            self._throw_invalid_user_access_error()
            return
        self._user_has_access_to_user_or_403(self.user, user)
        schema = PatientHealthResourceSchema()
        return schema.dump(
            {
                "patient": FHIRPatientSchemaData.generate_for_user(user, 1),
                "careTeam": CareTeam.get_care_team_by_user_id(user_id),
                "medicationStatement": MedicationStatement.get_medication_statement_by_user(
                    user
                ),
                "condition": Condition.get_conditions_by_user_id(user_id),
                "allergyIntolerance": AllergyIntolerance.get_allergy_intolerance_by_user(
                    user
                ),
                "pharmacyInfo": PharmacyInfo.get_pharmacy_info_by_user_id(user_id),
                "tracks": PatientTracks.get_tracks_by_user_id(user_id),
                "observation": [Observation.return_due_date_observation(user)]
                if user.health_profile.due_date
                else [],
                # Only show wallet info to care coordinators
                "walletInformation": (
                    WalletInfo.get_wallet_info_by_user_id(user_id)
                    if self.user.is_care_coordinator
                    else None
                ),
                "managedBenefits": (
                    ManagedBenefitsInfo.get_mmb_info_by_user(user)
                    if self.user.is_care_coordinator
                    else None
                ),
            }
        )


class V2FHIRPatientHealthResource(PermissionedCareTeamResource):
    """
    Version 2 of a Faux-gateway endpoint to supply FHIR formatted data to the front end.

    Note: This is an PermissionedCareTeamResource, not a PermissionedUserResource
    as it can be used to view data for users other than yourself.
    """

    def get(self, user_id):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        try:
            user = (
                db.session.query(User)
                .filter(User.id == user_id)
                .options(joinedload(User.health_profile))
                .one()
            )
        except NoResultFound:
            self._throw_invalid_user_access_error()
            return
        self._user_has_access_to_user_or_403(self.user, user)
        schema = PatientHealthResourceSchema()
        return schema.dump(
            {
                "patient": FHIRPatientSchemaData.generate_for_user(user, 2),
                "careTeam": CareTeam.get_care_team_by_user_id(user_id),
                "medicationStatement": MedicationStatement.get_medication_statement_by_user(
                    user
                ),
                "condition": Condition.get_conditions_by_user_id(user_id),
                "allergyIntolerance": AllergyIntolerance.get_allergy_intolerance_by_user(
                    user
                ),
                "pharmacyInfo": PharmacyInfo.get_pharmacy_info_by_user_id(user_id),
                "tracks": PatientTracks.get_tracks_by_user_id(user_id),
                # Only show wallet info to care coordinators
                "walletInformation": (
                    WalletInfo.get_wallet_info_by_user_id(user_id)
                    if self.user.is_care_coordinator
                    else None
                ),
                "managedBenefits": (
                    ManagedBenefitsInfo.get_mmb_info_by_user(user)
                    if self.user.is_care_coordinator
                    else None
                ),
                # TODO: zendesk user id should be moved out of the patient health record response
                #  once a new endpoint is created to return this ID.
                #  This is a temporary workaround to enable new messaging flow in the MPractice app.
                "zendesk_user_id": user.zendesk_user_id,
            }
        )
