from datetime import datetime

from authn.models.user import User
from views.schemas.FHIR.common import fhir_reference_from_model
from views.schemas.FHIR.observation import FHIRObservationStatusEnum


class Observation:
    @classmethod
    def construct_fhir_observation_json(  # type: ignore[no-untyped-def] # Function is missing a return type annotation #type: ignore[no-untyped-def] # Function is missing a type annotation for one or more arguments
        cls,
        identifiers,
        status,
        observation_type,
        value_type,
        value,
        subject: User,
        recorded_date: datetime,
        effective_type=None,
        effective=None,
        extensions=None,
    ):
        def create_identifier(type_text, value):  # type: ignore[no-untyped-def] # Function is missing a type annotation
            return {"type": {"text": type_text}, "value": value}

        json = {
            "resourceType": "Observation",
            "identifier": [
                create_identifier(type, value) for type, value in identifiers
            ],
            "status": status,
            "code": {"text": observation_type},
            "subject": fhir_reference_from_model(subject),
            "issued": recorded_date,
            f"{value_type}": value,
        }
        if effective and effective_type:
            json[f"{effective_type}"] = effective
        if extensions:
            json["extensions"] = extensions
        return json

    @classmethod
    def return_due_date_observation(cls, user):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        if not user.health_profile.due_date:
            return False
        return Observation.construct_fhir_observation_json(
            identifiers=[("user", f"{user.id}")],
            status=FHIRObservationStatusEnum.registered.value,
            observation_type="Due Date",
            value_type="valueDateTime",
            value=user.health_profile.due_date,
            subject=user,
            recorded_date=datetime.now(),
        )
