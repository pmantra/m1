import asyncio
import datetime
import random
from typing import Dict
from unittest import mock
from unittest.mock import MagicMock, patch

import pytest
from dateutil.relativedelta import relativedelta

from dosespot.pytests.conftest import paginated_medications
from dosespot.resources.dosespot_api import DoseSpotAPI
from dosespot.services.dosespot_service import convert_phone_number


@pytest.fixture()
def appointment(factories):
    practitioner = factories.PractitionerUserFactory.create()
    appointment = factories.AppointmentFactory.create_with_practitioner(practitioner)
    appointment.member.health_profile.json = {
        "birthday": str(datetime.datetime.now() - relativedelta(years=18))
    }
    factories.AddressFactory(user=appointment.member)
    appointment.member.member_profile.phone_number = random_phone_num_generator()
    return appointment


def random_phone_num_generator():
    # some generated phone numbers are not valid, regenerate in that case
    phone_number = None
    while not convert_phone_number(phone_number):
        first = str(random.randint(100, 999))
        second = str(random.randint(1, 888)).zfill(3)
        last = str(random.randint(1, 9998)).zfill(4)
        while last in ["1111", "2222", "3333", "4444", "5555", "6666", "7777", "8888"]:
            last = str(random.randint(1, 9998)).zfill(4)
        phone_number = f"{first}{second}{last}"

    return phone_number


def mock_request(url):
    def m_response(*args, **kwargs):
        return MagicMock(status_code=200, url=url)

    return m_response


@mock.patch.object(DoseSpotAPI, "api_request")
def test_patient_details_request_create_patient(api_request, appointment):
    patient_id = "12345"

    dose_spot_patient_search_id = {
        "Id": 12345,
    }
    api_request.return_value = (200, dose_spot_patient_search_id)

    ds = DoseSpotAPI(should_audit=False)
    returned_patient_id, url = ds.patient_details_request(
        appointment=appointment, create_patient=True
    )

    assert returned_patient_id == patient_id


@mock.patch("dosespot.services.dosespot_service.get_existing_patient_id")
def test_patient_details_request_existing_patient_id(
    get_existing_patient_id, appointment
):
    patient_id = "12345"
    with patch.object(
        DoseSpotAPI,
        "api_request",
        return_value=(
            200,
            {"Id": patient_id},
        ),
    ):
        get_existing_patient_id.return_value = patient_id

        ds = DoseSpotAPI(should_audit=False)
        returned_patient_id, url = ds.patient_details_request(
            appointment=appointment, create_patient=True
        )

        assert returned_patient_id == patient_id


def test_patient_details_request_without_create_patient(appointment):
    ds = DoseSpotAPI(should_audit=False)
    returned_patient_id, url = ds.patient_details_request(
        appointment, create_patient=False
    )

    assert returned_patient_id is None


@mock.patch.object(DoseSpotAPI, "api_request_async")
def test_pharmacy_search(api_request_async, valid_pharmacy):
    dose_spot_pharma_results = {
        "Items": [valid_pharmacy],
        "Result": {"ResultCode": "Result Code 1", "ResultDescription": "Result Code 2"},
    }
    api_request_async.return_value = (200, dose_spot_pharma_results)
    zip_code = "90210"

    ds = DoseSpotAPI(should_audit=False)
    results = asyncio.run(ds.pharmacy_search(zip_code))

    assert len(results) == len(dose_spot_pharma_results["Items"])


@mock.patch.object(DoseSpotAPI, "api_request")
def test_medication_list_no_next_page(
    api_request: MagicMock,
    active_prescription: Dict,
    completed_prescription: Dict,
    inactive_prescription: Dict,
    translated_active_prescription: Dict,
    translated_completed_prescription: Dict,
):
    dose_spot_medications_response = {
        "Items": [active_prescription, completed_prescription, inactive_prescription],
        "PageResult": {"hasNext": False},
    }
    api_request.return_value = (200, dose_spot_medications_response)
    patient_id = "47"
    start_date = datetime.datetime(2021, 6, 14, 10, 0, 0)
    end_date = datetime.datetime(2021, 6, 15, 10, 0, 0)

    ds = DoseSpotAPI(should_audit=False)
    results = ds.medication_list(
        patient_id=patient_id, start_date=start_date, end_date=end_date
    )

    assert results == [
        translated_active_prescription,
        translated_completed_prescription,
    ]
    api_request.assert_called_once_with(
        f"api/patients/{patient_id}/prescriptions",
        params={
            "startDate": "2021-06-14T10:00:00",
            "endDate": "2021-06-15T10:00:00",
            "pageNumber": 1,
        },
        method="GET",
        endpoint="get_patient_prescriptions",
    )


@mock.patch.object(DoseSpotAPI, "api_request", side_effect=paginated_medications)
def test_medication_list_has_next_page(
    api_request: MagicMock,
    translated_active_prescription: Dict,
    translated_completed_prescription: Dict,
):
    patient_id = "47"
    start_date = datetime.datetime(2021, 6, 14, 10, 0, 0)
    end_date = datetime.datetime(2021, 6, 15, 10, 0, 0)

    ds = DoseSpotAPI(should_audit=False)
    results = ds.medication_list(
        patient_id=patient_id, start_date=start_date, end_date=end_date
    )

    assert results == [
        translated_active_prescription,
        translated_completed_prescription,
    ]
    assert api_request.call_count == 2


@mock.patch.object(DoseSpotAPI, "api_request")
def test_add_patient_pharmacy(api_request):
    dose_spot_add_pharmacy_response = {
        "Result": {
            "ResultCode": "Success",
            "ResultDescription": "Pharmacy added Successfully",
        }
    }
    api_request.return_value = (200, dose_spot_add_pharmacy_response)
    patient_id = "47"
    member_id = "1"
    pharmacy_id = "20"

    ds = DoseSpotAPI(should_audit=False)
    result = ds.add_patient_pharmacy(member_id, patient_id, pharmacy_id)

    assert result == pharmacy_id
    api_request.assert_called_with(
        f"api/patients/{patient_id}/pharmacies",
        data={"PharmacyId": pharmacy_id, "SetAsPrimary": True},
        method="POST",
        endpoint="add_patient_pharmacy",
    )


@mock.patch.object(DoseSpotAPI, "api_request")
def test_get_patient_pharmacy(api_request):
    pharmacy = {
        "PharmacyId": "11856",
        "StoreName": "Test Pharmacy 1",
        "Address1": "989 E Hillsdale Blvd",
        "Address2": "",
        "City": "Foster City",
        "State": "CA",
        "ZipCode": "944042113",
        "PrimaryPhone": "6505455637x669",
        "PrimaryPhoneType": "Work",
        "PrimaryFax": "6503433333",
        "PharmacySpecialties": ["Retail", "EPCS"],
    }
    dosespot_get_pharmacy_response = {
        "Result": {
            "ResultCode": "Success",
        },
        "Items": [pharmacy],
    }
    api_request.return_value = (200, dosespot_get_pharmacy_response)
    patient_id = "123"
    member_id = "456"

    ds = DoseSpotAPI(should_audit=False)
    result = ds.get_patient_pharmacy(member_id, patient_id)

    assert result == pharmacy
    api_request.assert_called_with(
        f"api/patients/{patient_id}/pharmacies",
        method="GET",
        endpoint="get_patient_pharmacy",
    )
