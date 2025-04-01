from unittest.mock import patch

from appointments.services.common import obfuscate_appointment_id
from dosespot.resources.dosespot_api import DoseSpotAPI
from pytests.db_util import enable_db_performance_warnings


@patch.object(
    DoseSpotAPI,
    "api_request",
    return_value=(
        200,
        {
            "Items": [
                {
                    "PharmacyId": 1,
                    "StoreName": "Test One Pharmacy",
                    "Address1": "90001 1ST ST",
                    "Address2": "1ST FL",
                    "City": "Washington",
                    "State": "DC",
                    "ZipCode": "20000",
                    "PrimaryPhone": "2025551212",
                    "PrimaryPhoneType": "Work",
                    "PrimaryFax": "2025551213",
                    "PharmacySpecialties": [],
                }
            ],
            "Result": {
                "ResultCode": "Result Code 1",
                "ResultDescription": "Result Code 2",
            },
        },
    ),
)
def test_get_prescriptions_pharmacy_search(
    dosespot_api_response, factories, client, api_helpers, default_user, db
):

    member = factories.MemberFactory.create()
    member_schedule = factories.ScheduleFactory.create(user=member)

    practitioner = factories.PractitionerUserFactory.create()
    # ensure practitioner is enabled for prescribing
    practitioner.practitioner_profile.dosespot = {
        "clinic_key": "secret_key",
        "user_id": 1,
        "clinic_id": 1,
    }

    product = factories.ProductFactory.create(practitioner=practitioner)
    appointment = factories.AppointmentFactory.create(
        member_schedule=member_schedule, product=product
    )

    with enable_db_performance_warnings(database=db, failure_threshold=17):
        res = client.get(
            f"/api/v1/prescriptions/pharmacy_search/{obfuscate_appointment_id(appointment.id)}?zip_code=20000",
            headers=api_helpers.json_headers(member),
        )
        assert res.status_code == 200
