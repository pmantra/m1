import datetime
import unittest
from unittest.mock import patch

import pytest
from freezegun import freeze_time
from sqlalchemy import func

from authn.models.user import User
from care_advocates.models.assignable_advocates import AssignableAdvocate
from care_advocates.routes.care_advocate import (
    CareAdvocateSearchInvalidUserIdException,
    CareAdvocateSearchMissingUserIdException,
    CareAdvocateSearchNoActiveTrackException,
)
from care_advocates.schemas.care_advocates import (
    CareAdvocateAssignmentInvalidMemberException,
    PooledAvailabilityInvalidCAsException,
)
from models.profiles import CareTeamTypes, PractitionerProfile
from models.tracks.track import TrackName
from storage.connection import db


class TestCareAdvocatesSearchResource:
    url_prefix = "/api/v1/care_advocates/search"

    def test_care_advocate_search__unauthenticated_user(self, client, api_helpers):
        resp = client.get(
            f"{self.url_prefix}?member_id=1",
            headers=api_helpers.json_headers(),
        )
        assert resp.status_code == 401

    def test_care_advocate_search__missing_user_id(
        self, client, api_helpers, default_user
    ):
        resp = client.get(
            self.url_prefix,
            headers=api_helpers.json_headers(default_user),
        )
        assert resp.status_code == 400
        assert (
            api_helpers.load_json(resp)["error"]
            == CareAdvocateSearchMissingUserIdException.message
        )

    def test_care_advocate_search__invalid_user_id(
        self, client, api_helpers, default_user
    ):
        max_id = db.session.query(func.max(User.id)).first()[0]
        invalid_user_id = max_id + 1
        resp = client.get(
            f"{self.url_prefix}?member_id={invalid_user_id}",
            headers=api_helpers.json_headers(default_user),
        )
        assert resp.status_code == 400
        assert (
            api_helpers.load_json(resp)["error"]
            == CareAdvocateSearchInvalidUserIdException.message
        )

    def test_care_advocate_search__no_active_track(
        self, client, api_helpers, default_user
    ):
        resp = client.get(
            f"{self.url_prefix}?member_id={default_user.id}",
            headers=api_helpers.json_headers(default_user),
        )
        assert resp.status_code == 400
        assert (
            api_helpers.load_json(resp)["error"]
            == CareAdvocateSearchNoActiveTrackException.message
        )

    def test_care_advocate_search__no_cas_found(self, client, api_helpers, factories):
        # Given a user but no practitioners
        member = factories.EnterpriseUserFactory.create(
            tracks__name=TrackName.FERTILITY
        )

        # When we hit the care_advocates/search endpoint
        resp = client.get(
            f"{self.url_prefix}?member_id={member.id}",
            headers=api_helpers.json_headers(member),
        )

        # Then we expect a 200 response
        assert resp.status_code == 200
        assert api_helpers.load_json(resp)["care_advocate_ids"] == []

    @unittest.mock.patch(
        "care_advocates.routes.care_advocate.log_7_day_availability_in_pooled_calendar.delay"
    )
    def test_care_advocate_search__log_7_day_availabilities(
        self,
        mock_log_7_day_availability_in_pooled_calendar,
        client,
        api_helpers,
        factories,
    ):
        # Given a user but no practitioners
        member = factories.EnterpriseUserFactory.create(
            tracks__name=TrackName.FERTILITY
        )

        # When we hit the care_advocates/search endpoint
        resp = client.get(
            f"{self.url_prefix}?member_id={member.id}",
            headers=api_helpers.json_headers(member),
        )

        # Then we expect a 200 response
        assert resp.status_code == 200
        assert api_helpers.load_json(resp)["care_advocate_ids"] == []
        mock_log_7_day_availability_in_pooled_calendar.assert_called_once_with(
            care_advocate_ids=[], user_id=member.id, team_ns="care_discovery"
        )

    @freeze_time("2024-12-13")
    @pytest.mark.parametrize(
        argnames="flag_on",
        argvalues=[True, False],
        ids=[
            "release_ca_search_preferred_language_flag_on",
            "release_ca_search_preferred_language_flag_off",
        ],
    )
    def test_care_advocate_search__args_schema(
        self,
        flag_on,
        client,
        api_helpers,
        factories,
        catch_all_prac_profile,
    ):
        """
        Tests the happy path with and without the preferred language flag, but no filtering
        """
        # Given user has one track
        member = factories.EnterpriseUserFactory.create(
            tracks__name=TrackName.ADOPTION,
        )

        catch_all_prac_profile.next_availability = (
            datetime.datetime.utcnow() + datetime.timedelta(days=1)
        )

        # When we hit the care_advocates/search endpoint
        with patch("maven.feature_flags.bool_variation", return_value=flag_on):
            resp = client.get(
                f"{self.url_prefix}?member_id={member.id}",
                headers=api_helpers.json_headers(member),
            )

        expected_care_advocate_ids = [catch_all_prac_profile.user_id]

        # Then we expect a successful response containing expected CA id
        assert resp.status_code == 200
        resp_data = api_helpers.load_json(resp)
        assert resp_data["care_advocate_ids"] == expected_care_advocate_ids
        assert (
            resp_data["soonest_next_availability"]
            == catch_all_prac_profile.next_availability.isoformat()
        )

    @pytest.mark.parametrize(
        "availability_before",
        [None, datetime.datetime.utcnow() + datetime.timedelta(days=7)],
    )
    def test_care_advocate_search__one_track_not_pregnancy(
        self,
        availability_before,
        client,
        api_helpers,
        factories,
        catch_all_prac_profile,
    ):
        # Given user has one track
        member = factories.EnterpriseUserFactory.create(
            tracks__name=TrackName.ADOPTION,
        )

        catch_all_prac_profile.next_availability = (
            datetime.datetime.utcnow() + datetime.timedelta(days=1)
        )

        next_availability_query_str = (
            f"&availability_before={availability_before.isoformat()}"
            if availability_before
            else ""
        )

        # When we hit the care_advocates/search endpoint
        resp = client.get(
            f"{self.url_prefix}?member_id={member.id}{next_availability_query_str}",
            headers=api_helpers.json_headers(member),
        )

        expected_care_advocate_ids = [catch_all_prac_profile.user_id]

        # Then we expect a successful response containing expected CA id
        assert resp.status_code == 200
        assert (
            api_helpers.load_json(resp)["care_advocate_ids"]
            == expected_care_advocate_ids
        )

    @pytest.mark.parametrize(
        "availability_before",
        [None, datetime.datetime.utcnow() + datetime.timedelta(days=7)],
    )
    def test_care_advocate_search__one_track_pregnancy(
        self,
        availability_before,
        client,
        api_helpers,
        factories,
        catch_all_prac_profile,
    ):
        # # Given user has one track
        member = factories.EnterpriseUserFactory.create(
            tracks__name=TrackName.PREGNANCY,
        )

        catch_all_prac_profile.next_availability = (
            datetime.datetime.utcnow() + datetime.timedelta(days=1)
        )

        # When we hit the care_advocates/search endpoint
        resp = client.get(
            f"{self.url_prefix}?member_id={member.id}",
            headers=api_helpers.json_headers(member),
        )

        expected_care_advocate_ids = [catch_all_prac_profile.user_id]

        # Then we expect a successful response containing expected CA id
        assert resp.status_code == 200
        assert (
            api_helpers.load_json(resp)["care_advocate_ids"]
            == expected_care_advocate_ids
        )

    def test_care_advocate_search__multiple_tracks(
        self,
        client,
        api_helpers,
        factories,
        catch_all_prac_profile,
    ):
        # Given user has one track
        member = factories.EnterpriseUserFactory.create(
            tracks__name=TrackName.PREGNANCY,
            enabled_tracks=[TrackName.PREGNANCY, TrackName.ADOPTION],
        )
        # TODO: What is the purpose of this test? What's the effect of having two tracks? Also, I believe that we are not effectively creting two active tracks here

        catch_all_prac_profile.next_availability = (
            datetime.datetime.utcnow() + datetime.timedelta(days=1)
        )

        # When we hit the care_advocates/search endpoint
        resp = client.get(
            f"{self.url_prefix}?member_id={member.id}",
            headers=api_helpers.json_headers(member),
        )

        expected_care_advocate_ids = [catch_all_prac_profile.user_id]

        # Then we expect a successful response containing expected CA id
        assert resp.status_code == 200
        assert (
            api_helpers.load_json(resp)["care_advocate_ids"]
            == expected_care_advocate_ids
        )

    def test_care_advocate_search__user_with_ca_and_transitioning_tracks(
        self,
        client,
        api_helpers,
        factories,
        default_member_with_ca,
        catch_all_prac_profile,
        complete_matching_rule_set,
    ):
        # Given a user with an existing CA, who is transitioning tracks (from adoption to P&P)
        inactive_adoption_track = factories.MemberTrackFactory.create(
            name=TrackName.ADOPTION, user=default_member_with_ca
        )
        inactive_adoption_track.activated_at = (
            datetime.datetime.utcnow() - datetime.timedelta(days=2)
        )
        inactive_adoption_track.ended_at = (
            datetime.datetime.utcnow() - datetime.timedelta(days=1)
        )

        active_pp_track = factories.MemberTrackFactory.create(
            name=TrackName.PARENTING_AND_PEDIATRICS, user=default_member_with_ca
        )
        active_pp_track.activated_at = datetime.datetime.utcnow() - datetime.timedelta(
            days=1
        )

        # Make the members existing CA available
        existing_ca_id = default_member_with_ca.care_coordinators[0].id
        existing_ca_pp = db.session.query(PractitionerProfile).get(existing_ca_id)
        existing_ca_pp.next_availability = (
            datetime.datetime.utcnow() + datetime.timedelta(days=1)
        )

        # And lets create a valid matching rule set for the existing CA
        existing_aa = db.session.query(AssignableAdvocate).get(existing_ca_id)
        complete_matching_rule_set.get(existing_aa)

        # Given another CA is availale and matchable
        catch_all_prac_profile.next_availability = (
            datetime.datetime.utcnow() + datetime.timedelta(days=1)
        )

        # When we hit the care_advocates/search endpoint
        resp = client.get(
            f"{self.url_prefix}?member_id={default_member_with_ca.id}",
            headers=api_helpers.json_headers(default_member_with_ca),
        )

        # We expect to get only the existing CA
        expected_care_advocate_ids = [existing_ca_id]
        assert resp.status_code == 200
        assert (
            api_helpers.load_json(resp)["care_advocate_ids"]
            == expected_care_advocate_ids
        )

    @pytest.mark.parametrize(
        argnames="num_practitioners",
        argvalues=[20, 23],
    )
    def test_care_advocates_search__limit_pooled_calendar_number_of_cas(
        self,
        num_practitioners,
        datetime_today,
        client,
        api_helpers,
        complete_matching_rule_set,
        factories,
    ):
        member = factories.EnterpriseUserFactory.create(
            tracks__name=TrackName.PREGNANCY,
        )

        # Given - 20 or more practitioners with next_availability within next 7 days
        all_ca_ids = []
        for i in range(0, num_practitioners):
            prac = factories.PractitionerUserFactory.create(
                practitioner_profile__next_availability=datetime_today
                + datetime.timedelta(minutes=10 * i)
            )
            aa = factories.AssignableAdvocateFactory.create_with_practitioner(
                practitioner=prac
            )
            complete_matching_rule_set.get(aa)
            all_ca_ids.append(prac.id)

        # When we hit the care_advocates/search endpoint
        resp = client.get(
            f"{self.url_prefix}?member_id={member.id}",
            headers=api_helpers.json_headers(member),
        )

        # We expect to return the 20 CA's with first next_availability
        expected_care_advocate_ids = all_ca_ids[:20]
        assert resp.status_code == 200
        assert (
            api_helpers.load_json(resp)["care_advocate_ids"]
            == expected_care_advocate_ids
        )

    def test_care_advocate_search__member_preferred_language(
        self,
        client,
        api_helpers,
        factories,
        complete_matching_rule_set,
        datetime_today,
    ):
        """
        Tests that care_advocates/search will filter by a member's preferred language
        when the "use_preferred_language" parameter is sent
        """
        # Given
        member = factories.EnterpriseUserFactory.create(
            tracks__name=TrackName.PREGNANCY,
        )

        # Expected practitioner
        fr = factories.LanguageFactory.create(name="French", iso_639_3="fra")
        expected_prac = factories.PractitionerUserFactory.create(
            practitioner_profile__next_availability=datetime_today
            + datetime.timedelta(minutes=10),
            practitioner_profile__languages=[fr],
        )
        expected_aa = factories.AssignableAdvocateFactory.create_with_practitioner(
            practitioner=expected_prac
        )
        complete_matching_rule_set.get(expected_aa)

        # filtered_prac
        es = factories.LanguageFactory.create(name="Spanish", iso_639_3="spa")
        filtered_prac = factories.PractitionerUserFactory.create(
            practitioner_profile__next_availability=datetime_today
            + datetime.timedelta(minutes=15),
            practitioner_profile__languages=[es],
        )
        filtered_aa = factories.AssignableAdvocateFactory.create_with_practitioner(
            practitioner=filtered_prac
        )
        complete_matching_rule_set.get(filtered_aa)

        # The correct "Accept" headers are set and use_preferred_language is passed in
        headers = api_helpers.json_headers(member)
        headers["Accept-Language"] = "fr-CH"
        query_string = {"member_id": member.id, "use_preferred_language": True}

        # When we hit the care_advocates/search endpoint
        with patch("maven.feature_flags.bool_variation", return_value=True):
            resp = client.get(
                f"{self.url_prefix}",
                headers=headers,
                query_string=query_string,
            )

        expected_care_advocate_ids = [expected_prac.id]

        # Then we expect a successful response containing expected CA id
        assert resp.status_code == 200
        actual_care_advocate_ids = api_helpers.load_json(resp)["care_advocate_ids"]
        assert actual_care_advocate_ids == expected_care_advocate_ids


class TestCareAdvocatesPooledAvailabilityResource:
    url_prefix = "/api/v1/care_advocates/pooled_availability"

    def test_get_pooled_availability__unauthenticated_user(self, client, api_helpers):
        # When
        resp = client.get(
            f"{self.url_prefix}?ca_ids=1",
            headers=api_helpers.json_headers(),
        )
        # Then
        assert resp.status_code == 401

    def test_get_pooled_availability__missing_mandatory_params(
        self, client, api_helpers, default_user
    ):
        """
        Test that ca_ids, start_at and end_at are not missing in the URL params
        """

        # When hitting the pooled calendar endpoint with no params
        resp = client.get(
            self.url_prefix,
            headers=api_helpers.json_headers(default_user),
        )
        # Then
        assert resp.status_code == 400
        assert (
            api_helpers.load_json(resp)["errors"][0]["detail"]
            == "Missing data for required field."
        )

    def test_get_pooled_availability__invalid_cas_ids(
        self, jan_1st_next_year, client, api_helpers, default_user
    ):
        """
        Test that ca_ids correspond to existing CAs' ids
        """

        # Given an invalid CA id
        max_id = db.session.query(func.max(User.id)).first()[0]
        invalid_user_id = max_id + 1
        valid_start = jan_1st_next_year - datetime.timedelta(days=1)
        valid_end = jan_1st_next_year + datetime.timedelta(days=1)

        # When hitting the pooled calendar endpoint
        resp = client.get(
            f"{self.url_prefix}?ca_ids={invalid_user_id}&start_at={valid_start.isoformat()}&end_at={valid_end.isoformat()}",
            headers=api_helpers.json_headers(default_user),
        )

        # Then
        assert resp.status_code == 400
        assert (
            api_helpers.load_json(resp)["errors"][0]["detail"]
            == PooledAvailabilityInvalidCAsException().messages[0]
        )

    @pytest.mark.parametrize(
        argnames="valid_start, valid_end",
        argvalues=[(False, True), (True, False), (False, False)],
    )
    def test_get_pooled_availability__invalid_start_or_end_dates(
        self,
        valid_start,
        valid_end,
        jan_1st_next_year,
        factories,
        client,
        api_helpers,
        default_user,
    ):
        """
        Test that start_at and or ends_at are invalid dates.
        """

        # Given invalid start and end times
        start_at_str = (
            (jan_1st_next_year - datetime.timedelta(days=1)).isoformat()
            if valid_start
            else "an_invalid_start"
        )
        ends_at_str = (
            (jan_1st_next_year + datetime.timedelta(days=1)).isoformat()
            if valid_end
            else "an_invalid_end"
        )

        prac = factories.PractitionerUserFactory()
        factories.AssignableAdvocateFactory.create_with_practitioner(practitioner=prac)

        # When hitting the pooled calendar endpoint
        resp = client.get(
            f"{self.url_prefix}?ca_ids={prac.id}&start_at={start_at_str}&end_at={ends_at_str}",
            headers=api_helpers.json_headers(default_user),
        )

        # Then
        assert resp.status_code == 400
        assert api_helpers.load_json(resp)["errors"][0]["detail"] == "Not a valid date."

    def test_get_pooled_availability__no_availability(
        self, jan_1st_next_year, client, api_helpers, factories, default_user
    ):
        """
        Test that we get a successfull but empty response for a CA with no availability .
        """

        # Given a practitioner with no availability
        start_at = jan_1st_next_year - datetime.timedelta(days=1)
        end_at = jan_1st_next_year + datetime.timedelta(days=1)
        prac = factories.PractitionerUserFactory()
        factories.AssignableAdvocateFactory.create_with_practitioner(practitioner=prac)

        # When hitting the pooled calendar endpoint
        resp = client.get(
            f"{self.url_prefix}?ca_ids={prac.id}&start_at={start_at.isoformat()}&end_at={end_at.isoformat()}",
            headers=api_helpers.json_headers(default_user),
        )

        # Then we get a successful but empty response
        assert resp.status_code == 200
        assert api_helpers.load_json(resp)["care_advocates_pooled_availability"] == []

    def test_get_pooled_availability__availability_exists_for_prac(
        self, jan_1st_next_year, client, api_helpers, factories, default_user
    ):
        """
        Test that we get a successful response for a CA with availability .
        """

        # Given a practitioner with availability
        prac = factories.PractitionerUserFactory()
        factories.AssignableAdvocateFactory.create_with_practitioner(practitioner=prac)

        availability_start_at = jan_1st_next_year
        availability_end_at = jan_1st_next_year + datetime.timedelta(minutes=20)
        factories.ScheduleEventFactory.create(
            schedule=prac.schedule,
            starts_at=availability_start_at,
            ends_at=availability_end_at,
        )

        expected_availability = [
            {
                "start_time": availability_start_at.strftime("%Y-%m-%d %H:%M"),
                "ca_ids": [prac.id],
            },
            {
                "start_time": (
                    availability_start_at + datetime.timedelta(minutes=10)
                ).strftime("%Y-%m-%d %H:%M"),
                "ca_ids": [prac.id],
            },
        ]

        # When hitting the pooled calendar endpoint
        search_start_at = availability_start_at
        search_end_at = search_start_at + datetime.timedelta(days=1)

        resp = client.get(
            f"{self.url_prefix}?ca_ids={prac.id}&start_at={search_start_at.isoformat()}&end_at={search_end_at.isoformat()}",
            headers=api_helpers.json_headers(default_user),
        )

        # Then we get the pooled calendar equal to the practitioners availability
        assert resp.status_code == 200
        assert (
            api_helpers.load_json(resp)["care_advocates_pooled_availability"]
            == expected_availability
        )

    def test_get_pooled_availability__availability_exists_for_two_pracs(
        self, jan_1st_next_year, client, api_helpers, factories, default_user
    ):
        """
        Test that we get a successful response for a CA with availability .
        """

        # Given two care advocates with availability
        prac1 = factories.PractitionerUserFactory()
        factories.AssignableAdvocateFactory.create_with_practitioner(practitioner=prac1)
        availability_start_at_prac_1 = jan_1st_next_year + datetime.timedelta(
            hours=1, minutes=50
        )
        availability_end_at_prac_1 = jan_1st_next_year + datetime.timedelta(
            hours=2, minutes=10
        )
        factories.ScheduleEventFactory.create(
            schedule=prac1.schedule,
            starts_at=availability_start_at_prac_1,
            ends_at=availability_end_at_prac_1,
        )

        prac2 = factories.PractitionerUserFactory()
        factories.AssignableAdvocateFactory.create_with_practitioner(practitioner=prac2)
        availability_start_at_prac_2 = jan_1st_next_year + datetime.timedelta(hours=2)
        availability_end_at_prac_2 = availability_start_at_prac_2 + datetime.timedelta(
            minutes=20
        )
        factories.ScheduleEventFactory.create(
            schedule=prac2.schedule,
            starts_at=availability_start_at_prac_2,
            ends_at=availability_end_at_prac_2,
        )

        expected_availability = [
            {
                "start_time": availability_start_at_prac_1.strftime("%Y-%m-%d %H:%M"),
                "ca_ids": [prac1.id],
            },
            {
                "start_time": availability_start_at_prac_2.strftime("%Y-%m-%d %H:%M"),
                "ca_ids": [prac1.id, prac2.id],
            },
            {
                "start_time": (
                    availability_start_at_prac_2 + datetime.timedelta(minutes=10)
                ).strftime("%Y-%m-%d %H:%M"),
                "ca_ids": [prac2.id],
            },
        ]

        # When hitting the pooled calendar endpoint
        search_start_at = jan_1st_next_year
        search_end_at = search_start_at + datetime.timedelta(days=1)

        ca_ids_list = f"{prac1.id},{prac2.id}"
        resp = client.get(
            f"{self.url_prefix}?ca_ids={ca_ids_list}&start_at={search_start_at.isoformat()}&end_at={search_end_at.isoformat()}",
            headers=api_helpers.json_headers(default_user),
        )

        # Then, we get the pooled calendar for the two practitioners
        assert resp.status_code == 200
        assert (
            api_helpers.load_json(resp)["care_advocates_pooled_availability"]
            == expected_availability
        )


class TestCareAdvocatesAssignResource:
    url_prefix = "/api/v1/care_advocates/assign"

    def test_care_advocate_assign__unauthenticated_user(self, client, api_helpers):
        # When
        data = {
            "ca_ids": [1],
            "member_id": 2,
        }
        resp = client.post(
            self.url_prefix,
            data=api_helpers.json_data(data),
            headers=api_helpers.json_headers(),
        )
        # Then
        assert resp.status_code == 401

    def test_care_advocate_assign__missing_params(
        self, api_helpers, client, default_user
    ):
        # Given a missing CA id
        data = {
            "member_id": default_user.id,
        }
        # When hitting the assign endpoint
        resp = client.post(
            self.url_prefix,
            data=api_helpers.json_data(data),
            headers=api_helpers.json_headers(default_user),
        )

        # Then
        assert resp.status_code == 400
        assert (
            api_helpers.load_json(resp)["errors"][0]["detail"]
            == "Missing data for required field."
        )

    def test_care_advocate_assign__invalid_ca_id(
        self, client, api_helpers, default_user
    ):
        # Given an invalid CA id
        max_id = db.session.query(func.max(User.id)).first()[0]
        invalid_user_id = max_id + 1
        data = {
            "ca_ids": [invalid_user_id],
            "member_id": default_user.id,
        }

        # When hitting the assign endpoint
        resp = client.post(
            self.url_prefix,
            data=api_helpers.json_data(data),
            headers=api_helpers.json_headers(default_user),
        )

        # Then
        assert resp.status_code == 400
        assert (
            api_helpers.load_json(resp)["errors"][0]["detail"]
            == PooledAvailabilityInvalidCAsException().messages[0]
        )

    def test_care_advocate_assign__invalid_member_id(
        self, factories, client, api_helpers, default_user
    ):
        # Given an valid CA id's and an invalid member id
        prac1 = factories.PractitionerUserFactory()
        factories.AssignableAdvocateFactory.create_with_practitioner(practitioner=prac1)
        prac2 = factories.PractitionerUserFactory()
        factories.AssignableAdvocateFactory.create_with_practitioner(practitioner=prac2)

        ca_ids = [prac1.id, prac2.id]

        max_id = db.session.query(func.max(User.id)).first()[0]
        invalid_user_id = max_id + 1

        data = {
            "ca_ids": ca_ids,
            "member_id": invalid_user_id,
        }

        # When hitting the assign endpoint
        resp = client.post(
            self.url_prefix,
            data=api_helpers.json_data(data),
            headers=api_helpers.json_headers(default_user),
        )

        # Then
        assert resp.status_code == 400
        assert (
            api_helpers.load_json(resp)["errors"][0]["detail"]
            == CareAdvocateAssignmentInvalidMemberException().messages[0]
        )

    def test_care_advocate_assign__one_ca_success(
        self, factories, client, api_helpers, default_user, datetime_today
    ):
        # Given a valid CA id and valid member id
        prac = factories.PractitionerUserFactory()
        factories.AssignableAdvocateFactory.create_with_practitioner(practitioner=prac)
        start_at = datetime_today
        end_at = datetime_today + datetime.timedelta(minutes=20)
        factories.ScheduleEventFactory.create(
            schedule=prac.schedule,
            starts_at=start_at,
            ends_at=end_at,
        )

        expected_response = {
            "assigned_care_advocate": {
                "first_name": prac.first_name,
                "id": prac.id,
                "image_url": prac.avatar_url,
                "products": [
                    {
                        "is_intro_appointment_product": True,
                        "product_id": unittest.mock.ANY,
                    }
                ],
            }
        }

        data = {
            "ca_ids": [prac.id],
            "member_id": default_user.id,
        }

        # When hitting the assign endpoint
        resp = client.post(
            self.url_prefix,
            data=api_helpers.json_data(data),
            headers=api_helpers.json_headers(default_user),
        )

        # Then we expect our prac response
        assert resp.status_code == 200
        assert api_helpers.load_json(resp) == expected_response

    def test_care_advocate_assign__multiple_cas_success(
        self, factories, client, api_helpers, default_user, datetime_today
    ):
        # Given valid CA id's and valid member id
        prac1 = factories.PractitionerUserFactory()
        factories.AssignableAdvocateFactory.create_with_practitioner(practitioner=prac1)
        start_at_prac_1 = datetime_today
        end_at_prac_1 = datetime_today + datetime.timedelta(minutes=20)
        factories.ScheduleEventFactory.create(
            schedule=prac1.schedule,
            starts_at=start_at_prac_1,
            ends_at=end_at_prac_1,
        )

        prac2 = factories.PractitionerUserFactory()
        factories.AssignableAdvocateFactory.create_with_practitioner(practitioner=prac2)
        start_at_prac_2 = datetime_today + datetime.timedelta(minutes=10)
        end_at_prac_2 = datetime_today + datetime.timedelta(minutes=30)
        factories.ScheduleEventFactory.create(
            schedule=prac2.schedule,
            starts_at=start_at_prac_2,
            ends_at=end_at_prac_2,
        )
        ca_ids = [prac1.id, prac2.id]

        data = {
            "ca_ids": ca_ids,
            "member_id": default_user.id,
        }

        prac1_response = {
            "assigned_care_advocate": {
                "first_name": prac1.first_name,
                "id": prac1.id,
                "image_url": prac1.avatar_url,
                "products": [
                    {
                        "is_intro_appointment_product": True,
                        "product_id": unittest.mock.ANY,
                    }
                ],
            }
        }
        prac2_response = {
            "assigned_care_advocate": {
                "first_name": prac2.first_name,
                "id": prac2.id,
                "image_url": prac2.avatar_url,
                "products": [
                    {
                        "is_intro_appointment_product": True,
                        "product_id": unittest.mock.ANY,
                    }
                ],
            }
        }

        expected_responses = [prac1_response, prac2_response]

        # When hitting the assign endpoint
        resp = client.post(
            self.url_prefix,
            data=api_helpers.json_data(data),
            headers=api_helpers.json_headers(default_user),
        )

        # Then we expect one of our two potential prac responses
        assert resp.status_code == 200
        assert api_helpers.load_json(resp) in expected_responses

    def test_care_advocate_assign__check_for_current_ca_no_ca(
        self, factories, datetime_today, client, api_helpers, default_user
    ):
        # Given a user that does not have a CA assigned and a CA ready to be assigned
        prac = factories.PractitionerUserFactory()
        factories.AssignableAdvocateFactory.create_with_practitioner(practitioner=prac)
        start_at_prac = datetime_today
        end_at_prac = datetime_today + datetime.timedelta(minutes=20)
        factories.ScheduleEventFactory.create(
            schedule=prac.schedule,
            starts_at=start_at_prac,
            ends_at=end_at_prac,
        )

        expected_response = {
            "assigned_care_advocate": {
                "first_name": prac.first_name,
                "id": prac.id,
                "image_url": prac.avatar_url,
                "products": [
                    {
                        "is_intro_appointment_product": True,
                        "product_id": unittest.mock.ANY,
                    }
                ],
            }
        }

        data = {
            "ca_ids": [prac.id],
            "member_id": default_user.id,
        }

        # When hitting the assign endpoint
        resp = client.post(
            self.url_prefix,
            data=api_helpers.json_data(data),
            headers=api_helpers.json_headers(default_user),
        )

        # Then we expect our prac response
        assert resp.status_code == 200
        assert api_helpers.load_json(resp) == expected_response

    def test_care_advocate_assign__check_for_current_ca_not_in_list(
        self, factories, datetime_today, client, api_helpers, default_user
    ):
        # Given a user that does have a CA assigned and a different CA is ready to be assigned
        prac1 = factories.PractitionerUserFactory()
        factories.AssignableAdvocateFactory.create_with_practitioner(practitioner=prac1)
        factories.MemberProfileFactory.create(
            user_id=default_user.id,
        )
        factories.MemberPractitionerAssociationFactory.create(
            user_id=default_user.id,
            practitioner_id=prac1.id,
            type=CareTeamTypes.CARE_COORDINATOR,
        )

        prac2 = factories.PractitionerUserFactory()
        factories.AssignableAdvocateFactory.create_with_practitioner(practitioner=prac2)
        start_at_prac_2 = datetime_today + datetime.timedelta(minutes=10)
        end_at_prac_2 = datetime_today + datetime.timedelta(minutes=30)
        factories.ScheduleEventFactory.create(
            schedule=prac2.schedule,
            starts_at=start_at_prac_2,
            ends_at=end_at_prac_2,
        )

        expected_response = {
            "assigned_care_advocate": {
                "first_name": prac2.first_name,
                "id": prac2.id,
                "image_url": prac2.avatar_url,
                "products": [
                    {
                        "is_intro_appointment_product": True,
                        "product_id": unittest.mock.ANY,
                    }
                ],
            }
        }

        data = {
            "ca_ids": [prac2.id],
            "member_id": default_user.id,
        }

        # When hitting the assign endpoint with only the unassigned prac
        resp = client.post(
            self.url_prefix,
            data=api_helpers.json_data(data),
            headers=api_helpers.json_headers(default_user),
        )

        # Then we expect our prac response
        assert resp.status_code == 200
        assert api_helpers.load_json(resp) == expected_response

    def test_care_advocate_assign__check_for_current_ca_in_list(
        self, factories, datetime_today, client, api_helpers, default_user
    ):
        # Given a user that does have a CA assigned, and that CA and a different CA are both ready to be assigned
        prac1 = factories.PractitionerUserFactory()
        factories.AssignableAdvocateFactory.create_with_practitioner(practitioner=prac1)
        factories.MemberProfileFactory.create(
            user_id=default_user.id,
        )
        factories.MemberPractitionerAssociationFactory.create(
            user_id=default_user.id,
            practitioner_id=prac1.id,
            type=CareTeamTypes.CARE_COORDINATOR,
        )
        start_at_prac_1 = datetime_today
        end_at_prac_1 = datetime_today + datetime.timedelta(minutes=20)
        factories.ScheduleEventFactory.create(
            schedule=prac1.schedule,
            starts_at=start_at_prac_1,
            ends_at=end_at_prac_1,
        )

        prac2 = factories.PractitionerUserFactory()
        factories.AssignableAdvocateFactory.create_with_practitioner(practitioner=prac2)
        start_at_prac_2 = datetime_today + datetime.timedelta(minutes=10)
        end_at_prac_2 = datetime_today + datetime.timedelta(minutes=30)
        factories.ScheduleEventFactory.create(
            schedule=prac2.schedule,
            starts_at=start_at_prac_2,
            ends_at=end_at_prac_2,
        )

        expected_response = {
            "assigned_care_advocate": {
                "first_name": prac1.first_name,
                "id": prac1.id,
                "image_url": prac1.avatar_url,
                "products": [
                    {
                        "is_intro_appointment_product": True,
                        "product_id": unittest.mock.ANY,
                    }
                ],
            }
        }

        data = {
            "ca_ids": [prac1.id, prac2.id],
            "member_id": default_user.id,
        }

        # When hitting the assign endpoint with both pracs available
        resp = client.post(
            self.url_prefix,
            data=api_helpers.json_data(data),
            headers=api_helpers.json_headers(default_user),
        )

        # Then we expect our prac response
        assert resp.status_code == 200
        assert api_helpers.load_json(resp) == expected_response

    @unittest.mock.patch("tasks.braze.update_care_advocate_attrs.delay")
    def test_care_advocate_assign__braze_is_called(
        self,
        mock_update_care_advocate_attrs,
        factories,
        client,
        api_helpers,
        default_user,
        datetime_today,
    ):
        # Given a valid CA id and valid member id
        prac = factories.PractitionerUserFactory()
        factories.AssignableAdvocateFactory.create_with_practitioner(practitioner=prac)
        start_at = datetime_today
        end_at = datetime_today + datetime.timedelta(minutes=20)
        factories.ScheduleEventFactory.create(
            schedule=prac.schedule,
            starts_at=start_at,
            ends_at=end_at,
        )

        data = {
            "ca_ids": [prac.id],
            "member_id": default_user.id,
        }

        # When hitting the assign endpoint
        client.post(
            self.url_prefix,
            data=api_helpers.json_data(data),
            headers=api_helpers.json_headers(default_user),
        )

        # Then we expect braze to be updated with the new prac info
        mock_update_care_advocate_attrs.assert_called_once_with(default_user.id)
