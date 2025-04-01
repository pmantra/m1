from pytests.db_util import enable_db_performance_warnings


def test_get_prescriptions_errors_valid_id(
    factories, client, api_helpers, default_user, db
):

    practitioner_profile = factories.PractitionerProfileFactory.create(
        user_id=factories.DefaultUserFactory.create().id
    )

    # ensure user in enabled for prescribing
    practitioner_profile.dosespot = {
        "clinic_key": "secret_key",
        "user_id": 1,
        "clinic_id": 1,
    }

    with enable_db_performance_warnings(database=db, failure_threshold=20):
        res = client.get(
            f"/api/v1/prescriptions/errors/{practitioner_profile.user_id}",
            headers=api_helpers.json_headers(practitioner_profile.user),
        )
        assert res.status_code == 200


def test_get_prescriptions_errors_invalid_id(
    factories, client, api_helpers, default_user, db
):

    practitioner_profile = factories.PractitionerProfileFactory.create(
        user_id=factories.DefaultUserFactory.create().id
    )

    with enable_db_performance_warnings(database=db, failure_threshold=8):
        res = client.get(
            f"/api/v1/prescriptions/errors/{practitioner_profile.user_id + 1}",
            headers=api_helpers.json_headers(practitioner_profile.user),
        )
        assert res.status_code == 403
