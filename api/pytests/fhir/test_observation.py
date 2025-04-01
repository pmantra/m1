import datetime

from models.FHIR.observation import Observation
from views.schemas.FHIR.observation import FHIRObservationSchema


def test_due_date_observation_export(default_user):
    default_user.health_profile.due_date = (
        datetime.datetime.utcnow() + datetime.timedelta(days=75)
    )
    observation = Observation.return_due_date_observation(default_user)
    assert observation["identifier"][0]["value"] == str(default_user.id)
    assert observation["code"]["text"] == "Due Date"
    assert observation["valueDateTime"] == default_user.health_profile.due_date


def test_observation_status_validation_does_not_work(default_user):
    result = Observation.construct_fhir_observation_json(
        identifiers=[("user", f"{default_user.id}")],
        status="Invalid Status",
        observation_type="Due Date",
        value_type="valueDateTime",
        value=datetime.datetime.utcnow() + datetime.timedelta(days=75),
        subject=default_user,
        recorded_date=datetime.datetime.now(),
    )
    # TODO: the use of dump instead of load in FHIRPatientHealthResource
    #  means all uses of validate in the marshmallow schemas are not applied to data, this is a no-op
    output = FHIRObservationSchema().dump(result)
    assert output["status"] == "Invalid Status"
