import datetime
from unittest import mock
from unittest.mock import patch

import pytest

from pytests import factories
from pytests.db_util import enable_db_performance_warnings

# This file is largely copied from api/pytests/profiles/test_providers_api.py.
# since this endpoint is meant to replace that one for our usecase.


@pytest.fixture
def three_languages(factories):
    eng = factories.LanguageFactory.create(name="English")
    fr = factories.LanguageFactory.create(name="French")
    deu = factories.LanguageFactory.create(name="German")
    return eng, fr, deu


@pytest.fixture
def create_test_env(factories, three_languages):
    state = factories.StateFactory.create(abbreviation="NY", name="New York")
    nj_state = factories.StateFactory.create(abbreviation="NJ", name="New Jersey")
    member = factories.MemberFactory.create(member_profile__state=state)

    verticals = [
        factories.VerticalFactory.create(name="Nurse Practitioner"),
        factories.VerticalFactory.create(name="Doula And Childbirth Educator"),
        factories.VerticalFactory.create(name="Midwife"),
    ]

    specialties = [
        factories.SpecialtyFactory.create(
            name=f"specialty-{i:02d}", ordering_weight=10 - i
        )
        for i in range(3)
    ]

    eng, fr, deu = three_languages

    avail_time = datetime.datetime.utcnow() + datetime.timedelta(minutes=5)
    practitioners = [
        factories.PractitionerProfileFactory.create(
            user_id=factories.DefaultUserFactory.create().id,
            certified_states=[state, nj_state],
            verticals=[verticals[0]],
            specialties=[specialties[0]],
            next_availability=avail_time,
            languages=[eng, fr, deu],
        ),
        factories.PractitionerProfileFactory.create(
            user_id=factories.DefaultUserFactory.create().id,
            certified_states=[state],
            verticals=[verticals[1]],
            specialties=[specialties[1]],
            next_availability=avail_time,
            languages=[eng],
        ),
        factories.PractitionerProfileFactory.create(
            user_id=factories.DefaultUserFactory.create().id,
            certified_states=[state],
            verticals=[verticals[2]],
            specialties=[specialties[2]],
            next_availability=avail_time,
        ),
    ]

    needs = [
        factories.NeedFactory.create(verticals=[verticals[0]]),
        factories.NeedFactory.create(verticals=[verticals[1]]),
        factories.NeedFactory.create(verticals=[verticals[2]]),
    ]

    return member, verticals, practitioners, needs, specialties


@pytest.fixture
def request_providers(db, client, api_helpers):
    def _request_providers(request_user, query_string_dict=None):
        if query_string_dict is None:
            query_string_dict = {}
        with enable_db_performance_warnings(
            database=db,
            warning_threshold=10,
            query_analyzers=(),
        ):
            res = client.get(
                "/api/v1/providers",
                query_string=query_string_dict,
                headers=api_helpers.json_headers(request_user),
            )
            data = res.json["data"]
            return data

    return _request_providers


class TestPractitionersAPI:
    def test_at_least_one_filter_required(
        self, create_test_env, client, api_helpers, default_user
    ):
        # User must pass in at least one filter
        res = client.get(
            "/api/v1/providers",
            query_string={},
            headers=api_helpers.json_headers(default_user),
        )
        assert res.status_code == 400

    def test_provider_vertical_ids_filter(
        self,
        create_test_env,
        request_providers,
    ):
        member, verticals, practitioners, needs, specialties = create_test_env
        query_string = {
            "vertical_ids": f"{practitioners[1].vertical.id}, {practitioners[2].vertical.id}"
        }
        data = request_providers(member, query_string)
        assert len(data) == 2
        assert practitioners[0].user.full_name not in [u["full_name"] for u in data]

        query_string = {"vertical_ids": f"{practitioners[0].vertical.id}"}
        data = request_providers(member, query_string)
        assert len(data) == 1
        assert "Nurse Practitioner" == data[0]["vertical"]
        assert {"NY", "NJ"} == set(data[0]["certified_states"])

        # checking that we renamed this field as requested
        assert "name" in data[0]
        assert not data[0]["is_care_advocate"]

        assert "is_vertical_state_filtered" in data[0]
        assert data[0]["is_vertical_state_filtered"]
        assert data[0]["appointment_type"] == "standard"

    def test_provider_intl_filter(
        self,
        create_test_env,
        request_providers,
    ):
        member, verticals, practitioners, needs, specialties = create_test_env
        query_string = {
            "vertical_ids": f"{practitioners[1].vertical.id}, {practitioners[2].vertical.id}"
        }
        data = request_providers(member, query_string)
        assert len(data) == 2

        practitioners[2].country_code = "FR"
        data = request_providers(member, query_string)
        assert len(data) == 1
        assert practitioners[2].user.id not in [u["id"] for u in data]
        assert data[0]["appointment_type"] == "standard"

    def test_provider_specialty_ids_filter(
        self,
        create_test_env,
        request_providers,
    ):
        member, verticals, practitioners, needs, specialties = create_test_env
        query_string = {"specialty_ids": f"{practitioners[0].specialties[0].id}"}
        data = request_providers(member, query_string)
        assert len(data) == 1
        assert practitioners[0].user.full_name == data[0]["full_name"]

    def test_provider_dynamic_subtext_last_met(
        self,
        create_test_env,
        request_providers,
    ):
        member, verticals, practitioners, needs, specialties = create_test_env

        member_schedule = factories.ScheduleFactory.create(user=member)
        factories.AppointmentFactory.create_with_practitioner(
            practitioner=practitioners[0].user,
            member_schedule=member_schedule,
            scheduled_start=datetime.date(2023, 1, 1),
            member_ended_at=datetime.date(2023, 1, 1),
            practitioner_ended_at=datetime.date(2023, 1, 1),
        )
        factories.AppointmentFactory.create_with_practitioner(
            practitioner=practitioners[0].user,
            member_schedule=member_schedule,
            scheduled_start=datetime.date(2023, 2, 1),
            member_ended_at=datetime.date(2023, 2, 1),
            practitioner_ended_at=datetime.date(2023, 2, 1),
        )

        query_string = {"vertical_ids": f"{practitioners[0].vertical.id}"}
        data = request_providers(member, query_string)
        assert len(data) == 1
        assert data[0]["dynamic_subtext"] == "Last met with on 02/01/23"

    @pytest.mark.parametrize("locale_str", [None, "en", "es", "fr"])
    def test_provider__with_locale(
        self,
        locale_str,
        client,
        api_helpers,
        create_test_env,
        request_providers,
        release_mono_api_localization_on,
    ):
        member, verticals, practitioners, needs, specialties = create_test_env

        member_schedule = factories.ScheduleFactory.create(user=member)
        factories.AppointmentFactory.create_with_practitioner(
            practitioner=practitioners[0].user,
            member_schedule=member_schedule,
            scheduled_start=datetime.date(2023, 1, 1),
            member_ended_at=datetime.date(2023, 1, 1),
            practitioner_ended_at=datetime.date(2023, 1, 1),
        )
        factories.AppointmentFactory.create_with_practitioner(
            practitioner=practitioners[0].user,
            member_schedule=member_schedule,
            scheduled_start=datetime.date(2023, 2, 1),
            member_ended_at=datetime.date(2023, 2, 1),
            practitioner_ended_at=datetime.date(2023, 2, 1),
        )

        expected_vertical_text = "abc"

        query_string = {"vertical_ids": f"{practitioners[0].vertical.id}"}
        with patch(
            "appointments.resources.provider_profile.feature_flags.bool_variation",
            return_value=True,
        ), patch(
            "appointments.schemas.provider.TranslateDBFields.get_translated_vertical",
            return_value=expected_vertical_text,
        ) as translation_mock:
            headers = api_helpers.with_locale_header(
                api_helpers.json_headers(member), locale_str
            )
            res = client.get(
                "/api/v1/providers",
                query_string=query_string,
                headers=headers,
            )
            data = res.json["data"]

            assert translation_mock.call_count == 1

        assert len(data) == 1
        assert (
            data[0]["dynamic_subtext"] != "provider_dynamic_subtext_last_met 02/01/23"
        )
        assert data[0]["vertical"] == expected_vertical_text

    @pytest.mark.parametrize(
        "locale, expected_date",
        [(None, "2/1/23"), ("en", "2/1/23"), ("es", "1/2/23"), ("fr", "01/02/2023")],
    )
    def test_provider_dynamic_subtext_last_met__with_locale(
        self,
        locale,
        expected_date,
        client,
        api_helpers,
        create_test_env,
        request_providers,
        release_mono_api_localization_on,
    ):
        member, verticals, practitioners, needs, specialties = create_test_env

        member_schedule = factories.ScheduleFactory.create(user=member)
        factories.AppointmentFactory.create_with_practitioner(
            practitioner=practitioners[0].user,
            member_schedule=member_schedule,
            scheduled_start=datetime.date(2023, 1, 1),
            member_ended_at=datetime.date(2023, 1, 1),
            practitioner_ended_at=datetime.date(2023, 1, 1),
        )
        factories.AppointmentFactory.create_with_practitioner(
            practitioner=practitioners[0].user,
            member_schedule=member_schedule,
            scheduled_start=datetime.date(2023, 2, 1),
            member_ended_at=datetime.date(2023, 2, 1),
            practitioner_ended_at=datetime.date(2023, 2, 1),
        )

        query_string = {"vertical_ids": f"{practitioners[0].vertical.id}"}
        with patch(
            "appointments.resources.provider_profile.feature_flags.bool_variation",
            return_value=True,
        ):
            headers = api_helpers.with_locale_header(
                api_helpers.json_headers(member), locale
            )
            res = client.get(
                "/api/v1/providers",
                query_string=query_string,
                headers=headers,
            )
            data = res.json["data"]
        assert len(data) == 1

        actual_dynamic_subtext = data[0]["dynamic_subtext"]
        # Split on date
        space_index = actual_dynamic_subtext.rfind(" ")
        actual_dynamic_subtext_text = actual_dynamic_subtext[:space_index]
        actual_dynamic_subtext_date = actual_dynamic_subtext[space_index + 1 :]
        assert actual_dynamic_subtext_text != "provider_dynamic_subtext_last_met"
        assert actual_dynamic_subtext_date == expected_date

    def test_provider_dynamic_subtext_languages(
        self,
        create_test_env,
        request_providers,
    ):
        member, verticals, practitioners, needs, specialties = create_test_env

        query_string = {"vertical_ids": f"{practitioners[0].vertical.id}"}
        data = request_providers(member, query_string)
        assert len(data) == 1
        assert data[0]["dynamic_subtext"] == "Speaks French, German & English"

    @pytest.mark.parametrize("locale_str", [None, "en", "es", "fr"])
    def test_provider_dynamic_subtext_languages__with_locale(
        self,
        locale_str,
        create_test_env,
        api_helpers,
        client,
        request_providers,
        release_mono_api_localization_on,
    ):
        member, verticals, practitioners, needs, specialties = create_test_env

        query_string = {"vertical_ids": f"{practitioners[0].vertical.id}"}
        with patch(
            "appointments.resources.provider_profile.feature_flags.bool_variation",
            return_value=True,
        ):
            headers = api_helpers.with_locale_header(
                api_helpers.json_headers(member), locale_str
            )
            res = client.get(
                "/api/v1/providers",
                query_string=query_string,
                headers=headers,
            )
            data = res.json["data"]

        assert len(data) == 1
        assert (
            data[0]["dynamic_subtext"]
            != "provider_dynamic_subtext_speaks French, German & English"
        )

    def test_provider_dynamic_subtext_eng_only(
        self,
        create_test_env,
        request_providers,
    ):
        member, verticals, practitioners, needs, specialties = create_test_env

        query_string = {"vertical_ids": f"{practitioners[1].vertical.id}"}
        data = request_providers(member, query_string)
        assert len(data) == 1
        assert data[0]["dynamic_subtext"] == ""

    def test_provider_need_ids_filtering(
        self,
        create_test_env,
        request_providers,
    ):
        member, verticals, practitioners, needs, specialties = create_test_env
        query_string = {"need_ids": f"{needs[0].id},{needs[1].id}"}
        data = request_providers(member, query_string)
        assert len(data) == 2

        expected_ids = {practitioners[0].user_id, practitioners[1].user_id}
        actual_ids = {prac.get("id") for prac in data}
        assert expected_ids == actual_ids

    def test_provider_language_ids_filtering(
        self,
        create_test_env,
        three_languages,
        request_providers,
    ):
        """
        Tests that practitioners with no languages are filtered out
        """
        member, _, practitioners, _, _ = create_test_env
        _, _, deu = three_languages

        # only practitioner 1 has "deu" as a language
        expected_practitioner_ids = {practitioners[0].user_id}

        query_string = {"language_ids": f"{deu.id}"}
        data = request_providers(member, query_string)
        assert len(data) == 1

        actual_ids = {prac.get("id") for prac in data}
        assert expected_practitioner_ids == actual_ids

    def test_provider_language_ids_filtering__no_language(
        self,
        create_test_env,
        three_languages,
        request_providers,
    ):
        """
        Tests that practitioners with no languages are filtered out
        """
        member, _, practitioners, _, _ = create_test_env
        eng, _, deu = three_languages

        # practitioners 1 and 2 have languages while 3 does not
        expected_practitioner_ids = {practitioners[0].user_id, practitioners[1].user_id}

        query_string = {"language_ids": f"{eng.id}, {deu.id}"}
        data = request_providers(member, query_string)
        assert len(data) == 2

        actual_ids = {prac.get("id") for prac in data}
        assert expected_practitioner_ids == actual_ids

    def test_bypass_availability_filter(
        self,
        create_test_env,
        request_providers,
    ):
        member, verticals, practitioners, needs, specialties = create_test_env

        for practitioner in practitioners:
            practitioner.next_availability = None
            practitioner.show_when_unavailable = False

        query_string = {
            "vertical_ids": f"{practitioners[1].vertical.id}, {practitioners[2].vertical.id}"
        }

        # Should not return practitioner without availability set
        data = request_providers(member, query_string)
        assert len(data) == 0

        # Should not return practitioner without availability set
        # and bypass_availability param set to False
        query_string = {
            "vertical_ids": f"{practitioners[1].vertical.id}, {practitioners[2].vertical.id}",
            "bypass_availability": False,
        }
        data = request_providers(member, query_string)
        assert len(data) == 0

        query_string = {
            "vertical_ids": f"{practitioners[1].vertical.id}",
            "bypass_availability": True,
        }
        data = request_providers(member, query_string)
        assert len(data) == 1
        assert "Doula And Childbirth Educator" == data[0]["vertical"]


@mock.patch("models.tracks.client_track.should_enable_doula_only_track")
def test_apply_track_modifiers_filtering(
    should_enable_doula_only_track, create_doula_only_member, request_providers
):
    # Given
    member = create_doula_only_member

    vertical_1 = factories.VerticalFactory.create(
        name="Doula and Childbirth Educator",
    )
    vertical_2 = factories.VerticalFactory.create(name="Diabetes Coach")

    doula_provider = factories.PractitionerProfileFactory.create(
        user_id=factories.DefaultUserFactory.create().id,
        verticals=[vertical_1],
    )
    non_doula_provider = factories.PractitionerProfileFactory.create(
        user_id=factories.DefaultUserFactory.create().id,
        verticals=[vertical_2],
    )

    # When
    query_string = {
        "vertical_ids": f"{doula_provider.vertical.id}, {non_doula_provider.vertical.id}"
    }
    data = request_providers(member, query_string)

    # Then
    assert len(data) == 1
    assert data[0]["vertical"] == "Doula and Childbirth Educator"


@mock.patch("models.tracks.client_track.should_enable_doula_only_track")
def test_apply_track_modifiers_filtering__missing_query_params(
    mock_should_enable_doula_only_track,
    create_doula_only_member,
    request_providers,
):
    # Given
    member = create_doula_only_member

    vertical_1 = factories.VerticalFactory.create(
        name="Doula and Childbirth Educator",
    )
    vertical_2 = factories.VerticalFactory.create(name="Diabetes Coach")

    factories.PractitionerProfileFactory.create(
        user_id=factories.DefaultUserFactory.create().id,
        verticals=[vertical_2],
    )

    factories.PractitionerProfileFactory.create(
        user_id=factories.DefaultUserFactory.create().id,
        verticals=[vertical_1],
    )

    # When
    # a request is made without any search queries
    data = request_providers(member)

    # Then
    assert len(data) == 1

    # the only returned providers have doula-only verticals and care advocates should not be returned
    assert data[0]["vertical"] == "Doula and Childbirth Educator"
