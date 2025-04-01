import datetime
import json
from unittest.mock import patch

import pytest
import pytz

from bms.models.bms import BMSOrder
from bms.pytests.conftest import create_start_date
from bms.resources.bms import _validate_bms_order
from eligibility.pytests import factories as e9y_factories
from pytests.freezegun import freeze_time


def test_no_organization(
    client,
    api_helpers,
    bms_order_data_generator,
    default_user,
    valid_start_date,
    end_date,
):
    bms_order_data = bms_order_data_generator(
        start_date=valid_start_date,
        end_date=end_date,
    )
    res = client.post(
        "/api/v1/bms_order",
        data=json.dumps(bms_order_data),
        headers=api_helpers.json_headers(default_user),
    )
    assert res.status_code == 400


def test_bms_disabled(
    client,
    api_helpers,
    bms_order_data_generator,
    enterprise_user,
    valid_start_date,
    end_date,
):
    bms_order_data = bms_order_data_generator(
        start_date=valid_start_date,
        end_date=end_date,
    )
    res = client.post(
        "/api/v1/bms_order",
        data=json.dumps(bms_order_data),
        headers=api_helpers.json_headers(enterprise_user),
    )
    assert res.status_code == 400
    assert res.json["error"] == "BMS Not enabled for user's org."


def test_create_bms_order(
    client, api_helpers, bms_order_data_generator, bms_user, valid_start_date, end_date
):
    bms_order_data = bms_order_data_generator(
        start_date=valid_start_date,
        end_date=end_date,
    )

    with patch("bms.resources.bms.notify_about_bms_order.delay") as mock_notify:
        res = client.post(
            "/api/v1/bms_order",
            data=json.dumps(bms_order_data),
            headers=api_helpers.json_headers(bms_user),
        )
        assert res.status_code == 201

        results = BMSOrder.query.all()
        assert len(results) == 1
        bms_order = results[0]
        assert len(bms_order.shipments) == 2
        assert bms_order.is_work_travel

        bms_order_data["id"] = bms_order.id
        assert bms_order_data == api_helpers.load_json(res)

    assert mock_notify.call_count == 1
    mock_notify.assert_called_with(
        bms_user.id,
        bms_order.id,
        service_ns="breast_milk_shipping",
        team_ns="payments_platform",
    )


def test_missing_is_work_travel(
    client, api_helpers, bms_order_data_generator, bms_user, valid_start_date, end_date
):
    bms_order_data = bms_order_data_generator(
        start_date=valid_start_date,
        end_date=end_date,
    )
    bms_order_data.pop("is_work_travel")

    res = client.post(
        "/api/v1/bms_order",
        data=json.dumps(bms_order_data),
        headers=api_helpers.json_headers(bms_user),
    )

    assert res.status_code == 201

    results = BMSOrder.query.all()
    assert len(results) == 1
    bms_order = results[0]
    assert len(bms_order.shipments) == 2
    assert bms_order.is_work_travel is None

    assert res.json["is_work_travel"] is None


def test_capture_trip_id(
    client, api_helpers, bms_order_data_generator, bms_user, valid_start_date, end_date
):
    bms_order_data = bms_order_data_generator(
        start_date=valid_start_date,
        end_date=end_date,
    )
    bms_order_data["external_trip_id"] = "a-trip"

    res = client.post(
        "/api/v1/bms_order",
        data=json.dumps(bms_order_data),
        headers=api_helpers.json_headers(bms_user),
    )

    assert res.status_code == 201
    assert res.json["external_trip_id"] == "a-trip"


def test_invalid_arrival_dates__start_today(
    client, api_helpers, bms_order_data_generator, bms_user, end_date
):
    # can't set today or a date in the past as arrival date
    start_date = datetime.datetime.now()
    res = client.post(
        "/api/v1/bms_order",
        data=api_helpers.json_data(bms_order_data_generator(start_date, end_date)),
        headers=api_helpers.json_headers(bms_user),
    )

    assert res.status_code == 400


def test_invalid_arrival_dates__start_is_past(
    client, api_helpers, bms_order_data_generator, bms_user, end_date
):
    # can't set today or a date in the past as arrival date
    start_date = datetime.datetime(2020, 9, 25).date()
    res = client.post(
        "/api/v1/bms_order",
        data=api_helpers.json_data(bms_order_data_generator(start_date, end_date)),
        headers=api_helpers.json_headers(bms_user),
    )

    assert res.status_code == 400
    expected_err = {
        "error": "Travel start date must be in the future",
        "errors": [
            {
                "status": 400,
                "title": "Bad Request",
                "detail": "Travel start date must be in the future",
            }
        ],
    }
    assert res.json == expected_err


def test_invalid_arrival_dates__start_is_holiday(
    client, api_helpers, bms_order_data_generator, bms_user, end_date
):
    # can't arrive on a holiday
    start_date = datetime.datetime.now().replace(month=12, day=25)
    res = client.post(
        "/api/v1/bms_order",
        data=api_helpers.json_data(bms_order_data_generator(start_date, end_date)),
        headers=api_helpers.json_headers(bms_user),
    )

    assert res.status_code == 400
    expected_err = {
        "error": "Not a valid date.",
        "errors": [
            {"status": 400, "title": "Bad Request", "detail": "Not a valid date."}
        ],
    }
    assert res.json == expected_err


def test_invalid_arrival_dates__start_is_sunday(
    client, api_helpers, bms_order_data_generator, bms_user, end_date
):
    # can't arrive on a sunday
    start_date = (datetime.datetime.now() + datetime.timedelta(days=7)).date()
    while start_date.isoweekday() != 7:
        start_date = start_date + datetime.timedelta(days=1)
    res = client.post(
        "/api/v1/bms_order",
        data=api_helpers.json_data(bms_order_data_generator(start_date, end_date)),
        headers=api_helpers.json_headers(bms_user),
    )

    assert res.status_code == 400


def test_cutoff_time__tomorrow_okay(
    client, api_helpers, bms_order_data_generator, bms_user, end_date
):
    base_time = datetime.datetime(2018, 9, 17)  # this is a monday
    base_et_time = pytz.timezone("America/New_York").localize(base_time)

    # can get it tomorrow before cutoff time
    with freeze_time(base_et_time.replace(hour=8)):
        start_date = (base_time + datetime.timedelta(days=1)).date()
        res = client.post(
            "/api/v1/bms_order",
            data=api_helpers.json_data(bms_order_data_generator(start_date, end_date)),
            headers=api_helpers.json_headers(bms_user),
        )

        assert res.status_code == 201


def test_cutoff_time__tomorrow_missed(
    client, api_helpers, bms_order_data_generator, bms_user, end_date
):
    base_time = datetime.datetime(2018, 9, 17)  # this is a monday
    base_et_time = pytz.timezone("America/New_York").localize(base_time)

    # can't get it tomorrow after cutoff time
    with freeze_time(base_et_time.replace(hour=16)):
        start_date = (base_time + datetime.timedelta(days=1)).date()
        res = client.post(
            "/api/v1/bms_order",
            data=api_helpers.json_data(bms_order_data_generator(start_date, end_date)),
            headers=api_helpers.json_headers(bms_user),
        )

        assert res.status_code == 400
        expected_err = {
            "error": "Past order cutoff time",
            "errors": [
                {
                    "status": 400,
                    "title": "Bad Request",
                    "detail": "Past order cutoff time",
                }
            ],
        }
        assert res.json == expected_err


def test_cutoff_time__monday_missed(
    client, api_helpers, bms_order_data_generator, bms_user, end_date
):
    base_time = datetime.datetime(2018, 9, 17)  # this is a monday
    base_et_time = pytz.timezone("America/New_York").localize(base_time)

    # can't get it monday after cutoff time on saturday
    with freeze_time(base_et_time.replace(hour=16, day=14)):
        res = client.post(
            "/api/v1/bms_order",
            data=api_helpers.json_data(bms_order_data_generator(base_time, end_date)),
            headers=api_helpers.json_headers(bms_user),
        )

        assert res.status_code == 400


def test_friday_shipping__avoided(
    client, api_helpers, bms_order_data_generator, bms_user, end_date
):
    base_time = datetime.datetime(2018, 9, 20)  # this is a thursday
    base_et_time = pytz.timezone("America/New_York").localize(base_time)

    with freeze_time(base_et_time.replace(hour=8)):
        start_date = create_start_date(datetime.datetime.now())  # at freeze_time
        res = client.post(
            "/api/v1/bms_order",
            data=api_helpers.json_data(bms_order_data_generator(start_date, end_date)),
            headers=api_helpers.json_headers(bms_user),
        )
        assert res.status_code == 201
        assert not BMSOrder.query.one().shipments[0].friday_shipping


def test_friday_shipping__needed(
    client, api_helpers, bms_order_data_generator, bms_user, end_date
):
    base_time = datetime.datetime(2018, 9, 20)  # this is a thursday
    base_et_time = pytz.timezone("America/New_York").localize(base_time)

    with freeze_time(base_et_time.replace(hour=17)):
        start_date = create_start_date(datetime.datetime.now())  # at freeze_time
        res = client.post(
            "/api/v1/bms_order",
            data=api_helpers.json_data(bms_order_data_generator(start_date, end_date)),
            headers=api_helpers.json_headers(bms_user),
        )
        assert res.status_code == 201
        assert BMSOrder.query.one().shipments[0].friday_shipping


def test_bms_fails_missing_trip_id(
    client,
    api_helpers,
    bms_order_data_generator,
    bms_user,
    valid_start_date,
    end_date,
    eligible_verification,
):
    user = bms_user
    bms_order_data = bms_order_data_generator(
        start_date=valid_start_date, end_date=end_date, external_trip_id=None
    )
    with patch("bms.resources.bms._user_org_is_google", return_value=True), patch(
        "eligibility.service.EnterpriseVerificationService.get_verification_for_user_and_org",
        return_value=eligible_verification,
    ):
        res = client.post(
            "/api/v1/bms_order",
            data=json.dumps(bms_order_data),
            headers=api_helpers.json_headers(user),
        )
    assert res.status_code == 400
    assert res.json["error"] == "BMS validation error: trip_id required"


def test_bms_fails_dependent_user(
    client,
    api_helpers,
    bms_order_data_generator,
    bms_user,
    valid_start_date,
    end_date,
):
    user = bms_user
    bms_order_data = bms_order_data_generator(
        start_date=valid_start_date, end_date=end_date, external_trip_id="1234"
    )

    verification = e9y_factories.build_dependent_verification(
        user.id, user.organization_v2.id
    )
    with patch(
        "eligibility.service.EnterpriseVerificationService.get_verification_for_user_and_org",
        return_value=verification,
    ), patch(
        "bms.resources.bms._user_org_is_google",
    ) as mock:
        mock.return_value = True
        res = client.post(
            "/api/v1/bms_order",
            data=json.dumps(bms_order_data),
            headers=api_helpers.json_headers(user),
        )
    assert res.status_code == 400
    assert res.json["error"] == "Ineligible Order"


def test_bms_google_user(
    client,
    api_helpers,
    bms_order_data_generator,
    bms_user,
    valid_start_date,
    end_date,
    eligible_verification,
):
    user = bms_user
    bms_order_data = bms_order_data_generator(
        start_date=valid_start_date, end_date=end_date, external_trip_id="1234"
    )
    with patch("bms.resources.bms._user_org_is_google", return_value=True), patch(
        "eligibility.service.EnterpriseVerificationService.get_verification_for_user_and_org",
        return_value=eligible_verification,
    ):
        res = client.post(
            "/api/v1/bms_order",
            data=json.dumps(bms_order_data),
            headers=api_helpers.json_headers(user),
        )
    assert res.status_code == 201
    assert res.json["external_trip_id"] == "1234"
    assert res.json["return_shipments"]
    assert res.json["outbound_shipments"]


def test_bms_dependent_relationship_code_non_google(
    bms_order_data_generator,
    bms_user,
    valid_start_date,
    end_date,
):
    user = bms_user
    bms_order_data = bms_order_data_generator(
        start_date=valid_start_date, end_date=end_date, external_trip_id="1234"
    )
    with patch("bms.resources.bms._user_org_is_google", return_value=False):
        message = _validate_bms_order(user, bms_order_data)
    assert message is None


def test_bms_dependent_relationship_code_no_verification(
    bms_order_data_generator,
    bms_user,
    valid_start_date,
    end_date,
):
    user = bms_user
    bms_order_data = bms_order_data_generator(
        start_date=valid_start_date, end_date=end_date, external_trip_id="1234"
    )
    with patch("bms.resources.bms._user_org_is_google", return_value=True), patch(
        "eligibility.service.EnterpriseVerificationService.get_verification_for_user_and_org",
        return_value=None,
    ):
        message = _validate_bms_order(user, bms_order_data)
    assert message == "Ineligible Order"


@pytest.mark.parametrize(
    argnames="dynamic_eligible_verification, expected_error_message",
    argvalues=[
        ("Employee ", None),
        ("Employeee", "Ineligible Order"),
        (None, "Ineligible Order"),
        ("Dependant", "Ineligible Order"),
        (" Dependant", "Ineligible Order"),
    ],
    indirect=["dynamic_eligible_verification"],
)
def test_bms_dependent_relationship_code(
    bms_order_data_generator,
    bms_user,
    valid_start_date,
    end_date,
    dynamic_eligible_verification,
    expected_error_message,
):
    user = bms_user
    bms_order_data = bms_order_data_generator(
        start_date=valid_start_date, end_date=end_date, external_trip_id="1234"
    )
    with patch("bms.resources.bms._user_org_is_google", return_value=True), patch(
        "eligibility.service.EnterpriseVerificationService.get_verification_for_user_and_org",
        return_value=dynamic_eligible_verification,
    ):
        message = _validate_bms_order(user, bms_order_data)
    assert message == expected_error_message
