import datetime
from unittest import mock

import pytest

from models.tracks import TrackName
from models.tracks.client_track import TrackModifiers
from models.verticals_and_specialties import Vertical
from pytests.db_util import enable_db_performance_warnings
from storage.connection import db


@pytest.fixture
def create_test_env(factories):
    state = factories.StateFactory.create(abbreviation="NY", name="New York")
    nj_state = factories.StateFactory.create(abbreviation="NJ", name="New Jersey")

    member = factories.MemberFactory.create(member_profile__state=state)

    verticals = [
        factories.VerticalFactory.create(name="Nurse Practitioner"),
        factories.VerticalFactory.create(name="Doula And Childbirth Educator"),
        factories.VerticalFactory.create(name="Midwife"),
        factories.VerticalFactory.create(
            name="Geo-limited Vertical", filter_by_state=True
        ),
    ]

    avail_time = datetime.datetime.utcnow() + datetime.timedelta(minutes=5)
    practitioners = [
        factories.PractitionerProfileFactory.create(
            user_id=factories.DefaultUserFactory.create().id,
            certified_states=[state],
            verticals=[verticals[0]],
            next_availability=avail_time,
        ),
        factories.PractitionerProfileFactory.create(
            user_id=factories.DefaultUserFactory.create().id,
            certified_states=[state],
            verticals=[verticals[1]],
            next_availability=avail_time,
        ),
        factories.PractitionerProfileFactory.create(
            user_id=factories.DefaultUserFactory.create().id,
            certified_states=[state],
            verticals=[verticals[2]],
            next_availability=avail_time,
        ),
        factories.PractitionerProfileFactory.create(
            user_id=factories.DefaultUserFactory.create().id,
            certified_states=[nj_state],
            verticals=[verticals[3]],
            next_availability=avail_time,
            anonymous_allowed=False,
        ),
    ]

    needs = [
        factories.NeedFactory.create(verticals=[verticals[0]]),
        factories.NeedFactory.create(verticals=[verticals[1]]),
        factories.NeedFactory.create(verticals=[verticals[2]]),
    ]

    return member, verticals, practitioners, needs


@pytest.fixture
def request_practitioners(client, api_helpers, db):
    def _request_practitioners(request_user, query_string_dict=None):
        if query_string_dict is None:
            query_string_dict = {}

        # 2023-12-15 After query optimization we reached 31 DB queries to
        # satisfy this request. If you cause this test to fail due to exceeding
        # the failure_threshold, please send your MR to the care_discovery team.
        # Increases in DB call counts directly and negatively impact response
        # latency. It is acceptable to raise this number but it must be done
        # weighed against the negative impact.
        with enable_db_performance_warnings(
            database=db,
            failure_threshold=32,
        ):
            res = client.get(
                "/api/v1/practitioners",
                query_string=query_string_dict,
                headers=api_helpers.json_headers(request_user),
            )
            data = res.json["data"]
        return data

    return _request_practitioners


class TestPractitionersAPI:
    def test_no_filter(
        self,
        create_test_env,
        request_practitioners,
    ):
        member, verticals, practitioners, needs = create_test_env
        query_string = {}
        data = request_practitioners(member, query_string)
        assert len(data) == 3

    def test_practitioner_vertical_ids_filter(
        self,
        create_test_env,
        request_practitioners,
    ):
        member, verticals, practitioners, needs = create_test_env
        query_string = {
            "vertical_ids": f"{practitioners[1].vertical.id}, {practitioners[2].vertical.id}"
        }
        data = request_practitioners(member, query_string)
        assert len(data) == 2
        assert practitioners[0].user.first_name not in [u["first_name"] for u in data]

        query_string = {"vertical_ids": f"{practitioners[0].vertical.id}"}
        data = request_practitioners(member, query_string)
        assert len(data) == 1
        assert "Nurse Practitioner" in data[0]["profiles"]["practitioner"]["verticals"]

    def test_practitioner_needs_filtering(
        self,
        create_test_env,
        request_practitioners,
    ):
        member, verticals, practitioners, needs = create_test_env
        query_string = {"needs": f"{needs[0].name},{needs[1].name}"}
        data = request_practitioners(member, query_string)
        assert len(data) == 2

        expected_ids = {practitioners[0].user_id, practitioners[1].user_id}
        actual_ids = {prac.get("id") for prac in data}
        assert expected_ids == actual_ids

    def test_practitioner_need_ids_filtering(
        self,
        create_test_env,
        request_practitioners,
    ):
        member, verticals, practitioners, needs = create_test_env
        query_string = {"need_ids": f"{needs[0].id},{needs[1].id}"}
        data = request_practitioners(member, query_string)
        assert len(data) == 2

        expected_ids = {practitioners[0].user_id, practitioners[1].user_id}
        actual_ids = {prac.get("id") for prac in data}
        assert expected_ids == actual_ids

    def test_bypass_availability_filter(
        self,
        create_test_env,
        request_practitioners,
    ):
        member, verticals, practitioners, needs = create_test_env

        for practitioner in practitioners:
            practitioner.next_availability = None
            practitioner.show_when_unavailable = False

        # Should not return practitioner without availability set
        data = request_practitioners(member)
        assert len(data) == 0

        # Should not return practitioner without availability set
        # and bypass_availability param set to False
        query_string = {"bypass_availability": False}
        data = request_practitioners(member, query_string)
        assert len(data) == 0

        query_string = {"bypass_availability": True}
        data = request_practitioners(member, query_string)

        # matches length of practitioners in test_no_filter, based on implicit geo-filtering
        assert len(data) == 3

        retrieved_ids = frozenset(profile["id"] for profile in data)
        # matches length of practitioners in test_no_filter, based on implicit geo-filtering
        for practitioner in practitioners[0:3]:
            assert practitioner.user_id in retrieved_ids

    @mock.patch("views.schemas.base.should_enable_can_member_interact")
    @mock.patch("models.tracks.client_track.should_enable_doula_only_track")
    def test_get_practitioners__can_member_interact__doula_member(
        self,
        mock_should_enable_doula_only_track,
        mock_should_enable_can_member_interact,
        create_doula_only_member,
        factories,
        request_practitioners,
    ):
        # Given
        mock_should_enable_can_member_interact.return_value = True
        member = create_doula_only_member
        active_member_track = member.active_tracks[0]
        client_track_id = active_member_track.client_track_id

        # get the assigned care advocate id
        ca_vertical = (
            db.session.query(Vertical).filter(Vertical.name == "Care Advocate").one()
        )

        # create a VerticalAccessByTrack record to allow vertical <> client track interaction
        factories.VerticalAccessByTrackFactory.create(
            client_track_id=client_track_id,
            vertical_id=ca_vertical.id,
            track_modifiers=TrackModifiers.DOULA_ONLY,
        )

        # create a second provider that is non-doula
        state = factories.StateFactory.create(abbreviation="NY", name="New York")
        avail_time = datetime.datetime.utcnow() + datetime.timedelta(minutes=5)
        vertical = factories.VerticalFactory.create(name="Midwife")

        factories.PractitionerProfileFactory.create(
            user_id=factories.DefaultUserFactory.create().id,
            certified_states=[state],
            verticals=[vertical],
            next_availability=avail_time,
        )

        # When
        data = request_practitioners(
            request_user=member,
        )

        # Then
        assert len(data) == 2

        # assert that `can_member_interact` is only true for provider with a doula allowable vertical
        assert data[0]["profiles"]["practitioner"]["verticals"] == ["Care Advocate"]
        assert data[0]["profiles"]["practitioner"]["can_member_interact"] is True

        assert data[1]["profiles"]["practitioner"]["verticals"] == ["Midwife"]
        assert data[1]["profiles"]["practitioner"]["can_member_interact"] is False

    def test_get_practitioners__can_member_interact__non_doula_member(
        self, factories, request_practitioners
    ):
        # Given
        client_track = factories.ClientTrackFactory.create(
            track=TrackName.PREGNANCY,
        )
        member = factories.EnterpriseUserFactory.create(
            tracks=[],
        )
        tracks = [
            factories.MemberTrackFactory.create(
                name="pregnancy", user=member, client_track=client_track
            )
        ]
        need_categories = [factories.NeedCategoryFactory.create()]
        factories.NeedCategoryTrackFactory.create(
            track_name=tracks[0].name,
            need_category_id=need_categories[0].id,
        )

        # When
        data = request_practitioners(
            request_user=member,
        )

        # Then
        assert len(data) == 1
        assert data[0]["profiles"]["practitioner"]["verticals"] == ["Care Advocate"]
        assert data[0]["profiles"]["practitioner"]["can_member_interact"] is True

    @mock.patch("views.schemas.common.should_enable_can_member_interact")
    @pytest.mark.parametrize("doula_flag_on", [True, False])
    def test_get_practitioners__can_member_interact__non_doula_marketplace_member(
        self,
        mock_should_enable_can_member_interact,
        doula_flag_on,
        request_practitioners,
        create_test_env,
    ):
        # Given
        mock_should_enable_can_member_interact.return_value = doula_flag_on
        # marketplace member
        member, verticals, practitioners, needs = create_test_env

        # When
        data = request_practitioners(
            request_user=member,
        )

        # Then
        assert len(data) == 3
        for prac in data:
            assert prac["profiles"]["practitioner"]["can_member_interact"] is True
