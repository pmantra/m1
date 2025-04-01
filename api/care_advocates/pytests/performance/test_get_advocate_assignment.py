from models.tracks import TrackName
from pytests.db_util import enable_db_performance_warnings


def test_get_advocate_assignment_reassign(
    factories, client, api_helpers, db, default_user
):

    # generate member
    member = factories.EnterpriseUserFactory.create()

    factories.MemberTrackFactory.create(
        name=TrackName.PARENTING_AND_PEDIATRICS,
        user=member,
    )
    factories.MemberTrackFactory.create(name=TrackName.PREGNANCY, user=member)

    # generate a new practitioner to assign to the member
    new_practitioner = factories.PractitionerUserFactory.create()
    factories.AssignableAdvocateFactory.create_with_practitioner(
        practitioner=new_practitioner
    )

    with enable_db_performance_warnings(database=db, failure_threshold=14):

        res = client.post(
            f"/api/v1/advocate-assignment/reassign/{member.id}",
            headers=api_helpers.json_headers(default_user),
        )

        assert res.status_code == 200
