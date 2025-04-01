import datetime
from unittest import mock
from unittest.mock import patch

import pytest

from authn.models.user import User
from pytests import factories


@pytest.fixture
def three_languages(factories):
    eng = factories.LanguageFactory.create(name="English")
    fr = factories.LanguageFactory.create(name="French")
    deu = factories.LanguageFactory.create(name="German")
    return eng, fr, deu


@pytest.fixture
def create_test_env(factories, three_languages):
    state = factories.StateFactory.create(abbreviation="CA", name="California")
    member = factories.MemberFactory.create(member_profile__state=state)

    verticals = [
        factories.VerticalFactory.create(
            name="Nurse Practitioner", promote_messaging=True
        ),
        factories.VerticalFactory.create(
            name="Doula And Childbirth Educator", promote_messaging=True
        ),
        factories.VerticalFactory.create(name="Midwife", promote_messaging=True),
    ]

    specialties = [
        factories.SpecialtyFactory.create(
            name=f"specialty-{i:02d}", ordering_weight=10 - i
        )
        for i in range(3)
    ]

    eng, fr, deu = three_languages

    practitioners = [
        factories.PractitionerUserFactory.create(
            practitioner_profile__certified_states=[state],
            practitioner_profile__verticals=[verticals[0]],
            practitioner_profile__specialties=[specialties[0]],
            practitioner_profile__languages=[eng, fr, deu],
            practitioner_profile__messaging_enabled=True,
        ),
        factories.PractitionerUserFactory.create(
            practitioner_profile__certified_states=[state],
            practitioner_profile__verticals=[verticals[1]],
            practitioner_profile__specialties=[specialties[1]],
            practitioner_profile__languages=[fr],
            practitioner_profile__messaging_enabled=True,
        ),
        factories.PractitionerUserFactory.create(
            practitioner_profile__certified_states=[state],
            practitioner_profile__verticals=[verticals[2]],
            practitioner_profile__specialties=[specialties[2]],
            practitioner_profile__messaging_enabled=True,
        ),
    ]

    needs = [
        factories.NeedFactory.create(verticals=[verticals[0]], promote_messaging=True),
        factories.NeedFactory.create(verticals=[verticals[1]], promote_messaging=True),
        factories.NeedFactory.create(verticals=[verticals[2]], promote_messaging=True),
    ]

    return member, verticals, practitioners, needs, specialties


def create_uniform_schedules(practitioners):
    for p in practitioners:
        factories.ScheduleEventFactory.create(
            schedule=p.schedule,
            starts_at=datetime.datetime.now() + datetime.timedelta(hours=1),
            ends_at=datetime.datetime.now() + datetime.timedelta(hours=1),
        )


@pytest.fixture
def request_practitioners(client, api_helpers):
    def _request_practitioners(request_user, query_string_dict=None):
        if query_string_dict is None:
            query_string_dict = {}

        res = client.get(
            "/api/v1/providers/messageable_providers",
            query_string=query_string_dict,
            headers=api_helpers.json_headers(request_user),
        )
        data = res.json["data"]
        return data

    return _request_practitioners


class TestPractitionersAPI:
    def test_at_least_one_filter_required(
        self, create_test_env, client, api_helpers, default_user
    ):
        # User must pass in at least one filter
        res = client.get(
            "/api/v1/providers/messageable_providers",
            query_string={},
            headers=api_helpers.json_headers(default_user),
        )
        assert res.status_code == 400

    def test_practitioner_vertical_ids_filter(
        self,
        create_test_env,
        request_practitioners,
    ):
        member, verticals, practitioners, needs, specialties = create_test_env
        create_uniform_schedules(practitioners)

        query_string = {
            "vertical_ids": f"{practitioners[1].practitioner_profile.vertical.id}, {practitioners[2].practitioner_profile.vertical.id}",
            "need_ids": f"{needs[1].id},{needs[2].id}",
        }
        data = request_practitioners(member, query_string)
        assert len(data) == 2
        assert practitioners[0].full_name not in [u["full_name"] for u in data]

        query_string = {
            "vertical_ids": f"{practitioners[0].practitioner_profile.vertical.id}",
            "need_ids": f"{needs[0].id}",
        }
        data = request_practitioners(member, query_string)
        assert len(data) == 1
        assert "Nurse Practitioner" == data[0]["vertical"]

        # checking that we renamed this field as requested
        assert "name" in data[0]
        assert not data[0]["is_care_advocate"]

    def test_practitioner_vertical_ids_filter_no_needs(
        self,
        create_test_env,
        request_practitioners,
    ):
        member, verticals, practitioners, needs, specialties = create_test_env
        create_uniform_schedules(practitioners)

        query_string = {
            "vertical_ids": f"{practitioners[1].practitioner_profile.vertical.id}, {practitioners[2].practitioner_profile.vertical.id}",
        }

        # Currently we require that at least one need is passed in, otherwise we return no results.
        data = request_practitioners(member, query_string)
        assert len(data) == 0

    def test_practitioner_filter_for_schedule_events(
        self,
        create_test_env,
        request_practitioners,
    ):
        member, verticals, practitioners, needs, specialties = create_test_env
        all_vertical_ids = ",".join(str(v.id) for v in verticals)

        # this provider was only available yesterday
        factories.ScheduleEventFactory.create(
            schedule=practitioners[0].schedule,
            starts_at=datetime.datetime.now() - datetime.timedelta(days=1),
            ends_at=datetime.datetime.now() - datetime.timedelta(days=1),
        )
        # this provider is available in the window
        factories.ScheduleEventFactory.create(
            schedule=practitioners[1].schedule,
            starts_at=datetime.datetime.now() + datetime.timedelta(days=1),
            ends_at=datetime.datetime.now() + datetime.timedelta(days=1),
        )
        # this provider is only available too late
        factories.ScheduleEventFactory.create(
            schedule=practitioners[2].schedule,
            starts_at=datetime.datetime.now() + datetime.timedelta(days=5),
            ends_at=datetime.datetime.now() + datetime.timedelta(days=5),
        )

        query_string = {
            "vertical_ids": all_vertical_ids,
            "need_ids": f"{needs[0].id},{needs[1].id},{needs[2].id}",
        }

        data = request_practitioners(member, query_string)
        assert len(data) == 1
        assert practitioners[1].full_name in [u["full_name"] for u in data]

        # now this provider is also available inside the window
        factories.ScheduleEventFactory.create(
            schedule=practitioners[0].schedule,
            starts_at=datetime.datetime.now() + datetime.timedelta(days=1),
            ends_at=datetime.datetime.now() + datetime.timedelta(days=1),
        )

        data = request_practitioners(member, query_string)
        assert len(data) == 2
        assert practitioners[0].full_name in [u["full_name"] for u in data]
        assert practitioners[1].full_name in [u["full_name"] for u in data]

    def test_practitioner_need_ids_filtering(
        self,
        create_test_env,
        request_practitioners,
    ):
        member, verticals, practitioners, needs, specialties = create_test_env
        create_uniform_schedules(practitioners)

        query_string = {"need_ids": f"{needs[0].id},{needs[1].id}"}
        data = request_practitioners(member, query_string)
        assert len(data) == 2

        expected_ids = {practitioners[0].id, practitioners[1].id}
        actual_ids = {prac.get("id") for prac in data}
        assert expected_ids == actual_ids

    def test_practitioner_need_ids_filtering_checks_states(
        self,
        create_test_env,
        request_practitioners,
    ):
        member, verticals, practitioners, needs, specialties = create_test_env
        create_uniform_schedules(practitioners)

        query_string = {"need_ids": f"{needs[0].id},{needs[1].id}"}

        # If the user is not on a list of approved states, we return an empty result
        with patch(
            "providers.service.provider.ASYNC_CARE_ALLOWED_STATES",
            new=[],
        ):
            data = request_practitioners(member, query_string)
        assert len(data) == 0

    def test_practitioner_need_ids_filtering_checks_states_only_for_filtered(
        self,
        create_test_env,
        request_practitioners,
    ):
        member, verticals, practitioners, needs, specialties = create_test_env
        create_uniform_schedules(practitioners)

        query_string = {"need_ids": f"{needs[0].id},{needs[1].id}"}

        # If the user is not on a list of approved states, they can still get results for
        # filter_by_state = False verticals.

        for v in verticals:
            v.filter_by_state = False

        with patch(
            "providers.service.provider.ASYNC_CARE_ALLOWED_STATES",
            new=[],
        ):
            data = request_practitioners(member, query_string)
        assert len(data) == 2

    def test_practitioner_need_ids_filtering_for_member_without_state(
        self,
        create_test_env,
        request_practitioners,
    ):
        member, verticals, practitioners, needs, specialties = create_test_env
        member.member_profile.state = None
        create_uniform_schedules(practitioners)

        query_string = {"need_ids": f"{needs[0].id},{needs[1].id}"}

        # If the user is not on a list of approved states, they can still get results for
        # filter_by_state = False verticals.

        for v in verticals:
            v.filter_by_state = False

        with patch(
            "providers.service.provider.ASYNC_CARE_ALLOWED_STATES",
            new=[],
        ):
            data = request_practitioners(member, query_string)
        assert len(data) == 0

    def test_practitioner_need_ids_promote_messaging_flag_filtering(
        self,
        create_test_env,
        request_practitioners,
    ):
        member, verticals, practitioners, needs, specialties = create_test_env
        needs[0].promote_messaging = False

        create_uniform_schedules(practitioners)

        query_string = {"need_ids": f"{needs[0].id},{needs[1].id}"}
        data = request_practitioners(member, query_string)
        assert len(data) == 1

        expected_ids = {practitioners[1].id}
        actual_ids = {prac.get("id") for prac in data}
        assert expected_ids == actual_ids

    def test_practitioner_language_ids_filtering(
        self,
        create_test_env,
        three_languages,
        request_practitioners,
    ):
        _, fr, _ = three_languages
        member, _, practitioners, needs, _ = create_test_env
        create_uniform_schedules(practitioners)

        query_string = {
            "language_ids": f"{fr.id}",
            # /messageable_providers currently requires a "need_id", so we'll include
            # all needs here. See "api/appointments/resources/provider_search.py" line 112
            "need_ids": ",".join([str(n.id) for n in needs]),
        }
        data = request_practitioners(member, query_string)
        assert len(data) == 2

        # practitioners 1 and 2 both have french
        expected_ids = {practitioners[0].id, practitioners[1].id}
        actual_ids = {prac.get("id") for prac in data}
        assert expected_ids == actual_ids

    def test_practitioner_language_ids_filtering__no_match(
        self,
        create_test_env,
        three_languages,
        request_practitioners,
    ):
        member, _, practitioners, needs, _ = create_test_env
        create_uniform_schedules(practitioners)

        non_matching_language = factories.LanguageFactory.create(
            name="Non matching lang"
        )

        query_string = {
            "language_ids": f"{non_matching_language.id}",
            # /messageable_providers currently requires a "need_id", so we'll include
            # all needs here. See "api/appointments/resources/provider_search.py" line 112
            "need_ids": ",".join([str(n.id) for n in needs]),
        }
        data = request_practitioners(member, query_string)
        assert len(data) == 0

    @mock.patch("models.tracks.client_track.should_enable_doula_only_track")
    def test_apply_track_modifiers_filtering(
        self,
        should_enable_doula_only_track,
        create_doula_only_member: User,
        create_test_env,
        request_practitioners,
    ):
        _, _, practitioners, needs, _ = create_test_env
        create_uniform_schedules(practitioners)

        user = create_doula_only_member
        query_string_dict = {
            "need_ids": ",".join([str(need.id) for need in needs]),
        }
        data = request_practitioners(
            request_user=user, query_string_dict=query_string_dict
        )

        assert len(data) == 1
        assert data[0]["vertical"] == "Doula And Childbirth Educator"
