from pytests.db_util import enable_db_performance_warnings


def test_my_patients(client, api_helpers, db, default_user, factories):

    practitioner = factories.PractitionerUserFactory()

    with enable_db_performance_warnings(
        database=db,
        failure_threshold=16,
    ):
        client.get(
            f"/api/v1/users/{practitioner.id}/my_patients?first_name={default_user.first_name}&last_name={default_user.last_name}",
            headers=api_helpers.standard_headers(practitioner),
        )
