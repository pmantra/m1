from pytests.db_util import enable_db_performance_warnings


def test_practitioners(client, api_helpers, db, factories):

    member = factories.MemberFactory.create()
    factories.PractitionerUserFactory.create()

    with enable_db_performance_warnings(
        database=db,
        failure_threshold=21,
    ):
        client.get(
            "/api/v1/practitioners",
            query_string={},
            headers=api_helpers.json_headers(member),
        )
