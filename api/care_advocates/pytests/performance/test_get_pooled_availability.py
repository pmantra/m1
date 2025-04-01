import datetime

from pytests.db_util import enable_db_performance_warnings


def test_get_pooled_availability_one_ca(
    factories, jan_1st_next_year, client, api_helpers, db, default_user
):
    prac = factories.PractitionerUserFactory()
    factories.AssignableAdvocateFactory.create_with_practitioner(practitioner=prac)

    availability_start_at = datetime.datetime.utcnow()
    availability_end_at = datetime.datetime.utcnow() + datetime.timedelta(days=1)
    factories.ScheduleEventFactory.create(
        schedule=prac.schedule,
        starts_at=availability_start_at,
        ends_at=availability_end_at,
    )

    with enable_db_performance_warnings(database=db, failure_threshold=16):

        resp = client.get(
            f"/api/v1/care_advocates/pooled_availability?ca_ids={prac.id}&start_at={availability_start_at.isoformat()}&end_at={availability_end_at.isoformat()}",
            headers=api_helpers.json_headers(default_user),
        )

        assert resp.status_code == 200


def test_get_pooled_availability_multiple_cas(
    factories, client, api_helpers, db, default_user
):

    # generate timestamps to use as search parameters in the request
    availability_start_at = datetime.datetime.utcnow()
    availability_end_at = datetime.datetime.utcnow() + datetime.timedelta(days=1)

    # create 2 practitioners with availability
    prac1 = factories.PractitionerUserFactory()
    factories.AssignableAdvocateFactory.create_with_practitioner(practitioner=prac1)
    factories.ScheduleEventFactory.create(
        schedule=prac1.schedule,
        starts_at=availability_start_at,
        ends_at=availability_end_at,
    )

    prac2 = factories.PractitionerUserFactory()
    factories.AssignableAdvocateFactory.create_with_practitioner(practitioner=prac2)
    factories.ScheduleEventFactory.create(
        schedule=prac2.schedule,
        starts_at=availability_start_at,
        ends_at=availability_end_at,
    )

    ca_user_ids = f"{prac1.id},{prac2.id}"

    with enable_db_performance_warnings(database=db, failure_threshold=21):
        res = client.get(
            f"/api/v1/care_advocates/pooled_availability?ca_ids={ca_user_ids}&start_at={availability_start_at.isoformat()}&end_at={availability_end_at.isoformat()}",
            headers=api_helpers.json_headers(default_user),
        )
        assert res.status_code, 200
