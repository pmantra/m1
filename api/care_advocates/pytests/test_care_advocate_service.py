import datetime
from unittest import mock

import pytest

from appointments.utils.booking import (
    PotentialAppointment,
    PotentialPractitionerAvailabilities,
)
from care_advocates.services.care_advocate import CareAdvocateService
from models.profiles import CareTeamTypes, MemberPractitionerAssociation
from models.tracks.track import TrackName
from models.verticals_and_specialties import CX_VERTICAL_NAME


class TestKeepExistingCaIfValidAndMemberTransitioningTracks:
    def test_keep_existing_ca_if_valid_and_member_transitioning_tracks__member_has_no_existing_ca(
        self, care_advocate_service, default_user
    ):
        # Given a member with no existing CAs
        # and an arbitrary list of potential new CAs for the member
        potential_new_cas_ids = [1, 2]

        # When
        new_potential_new_cas_ids = care_advocate_service.keep_existing_ca_if_valid_and_member_transitioning_tracks(
            user_id=default_user.id, potential_new_cas_ids=potential_new_cas_ids
        )

        # Then, we expect the potential_new_cas to remain the same
        assert new_potential_new_cas_ids == potential_new_cas_ids

    def test_keep_existing_ca_if_valid_and_member_transitioning_tracks__member_ca_not_in_list_of_potential_new_cas(
        self,
        care_advocate_service,
        default_member_with_ca,
    ):
        # Given a member whose CAs is not in the list of potential new CAs
        existing_ca_id = default_member_with_ca.care_coordinators[0].id
        potential_new_cas_ids = [existing_ca_id + 1, existing_ca_id + 2]

        # When
        new_potential_new_cas_ids = care_advocate_service.keep_existing_ca_if_valid_and_member_transitioning_tracks(
            user_id=default_member_with_ca.id,
            potential_new_cas_ids=potential_new_cas_ids,
        )

        # Then, we expect the potential_new_cas to remain the same
        assert new_potential_new_cas_ids == potential_new_cas_ids

    def test_keep_existing_ca_if_valid_and_member_transitioning_tracks__member_ca_in_list_of_potential_new_cas_but_member_not_transitioning_tracks(
        self, care_advocate_service, default_member_with_ca
    ):
        # Given a member whose CAs is in the list of potential new CAs, but who is not transitioning tracks
        existing_ca_id = default_member_with_ca.care_coordinators[0].id
        potential_new_cas_ids = [existing_ca_id, existing_ca_id + 1]

        # When
        new_potential_new_cas_ids = care_advocate_service.keep_existing_ca_if_valid_and_member_transitioning_tracks(
            user_id=default_member_with_ca.id,
            potential_new_cas_ids=potential_new_cas_ids,
        )

        # Then, we expect the potential_new_cas to remain the same
        assert new_potential_new_cas_ids == potential_new_cas_ids

    def test_keep_existing_ca_if_valid_and_member_transitioning_tracks__member_ca_in_list_of_potential_new_cas_and_member_transitioning_tracks(
        self, factories, care_advocate_service, default_member_with_ca
    ):
        # Given a member who is transitioning tracks
        track = factories.MemberTrackFactory.create(user=default_member_with_ca)
        track.activated_at = datetime.datetime.utcnow() - datetime.timedelta(days=2)
        track.ended_at = datetime.datetime.utcnow() - datetime.timedelta(days=1)

        # and whose CA is in the list of potential new CAs
        existing_ca_id = default_member_with_ca.care_coordinators[0].id
        potential_new_cas_ids = [existing_ca_id, existing_ca_id + 1]

        # When
        new_potential_new_cas_ids = care_advocate_service.keep_existing_ca_if_valid_and_member_transitioning_tracks(
            user_id=default_member_with_ca.id,
            potential_new_cas_ids=potential_new_cas_ids,
        )

        # Then, we expect the potential_new_cas to be their existing CA
        assert new_potential_new_cas_ids == [existing_ca_id]


class TestIsValidListCasIds:
    @mock.patch(
        "care_advocates.repository.assignable_advocate.AssignableAdvocateRepository.get_all_aa_ids"
    )
    def test_validate_list_cas_ids__valid_list(
        self,
        mock_get_all_aa_ids,
    ):
        # Given
        ca_ids_to_validate = [1, 2]
        mock_get_all_aa_ids.return_value = [1, 2, 3]

        # When
        is_valid_list = CareAdvocateService().is_valid_list_cas_ids(
            ca_ids=ca_ids_to_validate,
        )

        # Then
        mock_get_all_aa_ids.assert_called_once()
        assert is_valid_list

    @pytest.mark.parametrize(
        argnames="ca_ids_to_validate",
        argvalues=[
            ([]),
            ([1, 2]),
            (["invalid"]),
        ],
    )
    @mock.patch(
        "care_advocates.repository.assignable_advocate.AssignableAdvocateRepository.get_all_aa_ids"
    )
    def test_validate_list_cas_ids__invalid_list(
        self,
        mock_get_all_aa_ids,
        ca_ids_to_validate,
    ):
        # Given
        mock_get_all_aa_ids.return_value = [1]

        # When
        is_valid_list = CareAdvocateService().is_valid_list_cas_ids(
            ca_ids=ca_ids_to_validate,
        )

        # Then
        assert not is_valid_list
        if ca_ids_to_validate:
            mock_get_all_aa_ids.assert_called_once()


class TestGetPractitionersAvailabilities:
    @mock.patch(
        "appointments.utils.booking.MassAvailabilityCalculator.get_practitioner_availabilities"
    )
    def test_get_practitioners_availabilities__happy_path(
        self,
        mock_get_practitioner_availabilities,
        jan_1st_next_year,
    ):
        # Given a practitioner
        prac_profiles = ["fake_profile"]
        start_at = jan_1st_next_year - datetime.timedelta(days=1)
        end_at = jan_1st_next_year + datetime.timedelta(days=1)

        mocked_response_get_practitioner_availabilities = "the best response"
        mock_get_practitioner_availabilities.return_value = (
            mocked_response_get_practitioner_availabilities
        )

        # When
        availabilities = CareAdvocateService()._get_practitioners_availabilities(
            prac_profiles=prac_profiles, start_at=start_at, end_at=end_at
        )

        # Then
        mock_get_practitioner_availabilities.assert_called_once_with(
            practitioner_profiles=prac_profiles,
            start_time=start_at,
            end_time=end_at,
            limit=1000,
            offset=0,
            vertical_name=CX_VERTICAL_NAME,
        )
        assert availabilities == mocked_response_get_practitioner_availabilities


class TestMergeAvailabilities:
    def test_merge_availabilities__no_availabilities(self):
        # Given an empty list of availabilities
        all_pracs_availabilities = []
        expected_merged_availabilities = {}

        # When
        merged_availabilities = CareAdvocateService()._merge_availabilities(
            all_pracs_availabilities=all_pracs_availabilities
        )

        # Then
        assert merged_availabilities == expected_merged_availabilities

    def test__merge_availabilities__no_availabilities_intersection(
        self, jan_1st_next_year
    ):

        # Given a list of practitioners availabilities with no intersection
        prac_1_id = 1
        potential_appt_1_start = jan_1st_next_year
        potential_appt_1_end = jan_1st_next_year + datetime.timedelta(minutes=10)
        potential_appt_1 = PotentialAppointment(
            scheduled_start=potential_appt_1_start,
            scheduled_end=potential_appt_1_end,
            total_available_credits=0,
        )
        potential_prac_availability_1 = PotentialPractitionerAvailabilities(
            practitioner_id=prac_1_id,
            product_id=1,
            product_price=10,
            duration=10,
            availabilities=[potential_appt_1],
            contract_priority=99,
        )

        potential_appt_2_start = jan_1st_next_year + datetime.timedelta(minutes=20)
        potential_appt_2_end = jan_1st_next_year + datetime.timedelta(minutes=30)
        potential_appt_2 = PotentialAppointment(
            scheduled_start=potential_appt_2_start,
            scheduled_end=potential_appt_2_end,
            total_available_credits=0,
        )
        prac_2_id = 2
        potential_prac_availability_2 = PotentialPractitionerAvailabilities(
            practitioner_id=prac_2_id,
            product_id=2,
            product_price=10,
            duration=10,
            availabilities=[potential_appt_2],
            contract_priority=99,
        )
        all_pracs_availabilities = [
            potential_prac_availability_1,
            potential_prac_availability_2,
        ]

        expected_merged_availabilities = {
            potential_appt_1_start: [prac_1_id],
            potential_appt_2_start: [prac_2_id],
        }

        # When
        merged_availabilities = CareAdvocateService()._merge_availabilities(
            all_pracs_availabilities=all_pracs_availabilities
        )

        # Then
        assert merged_availabilities == expected_merged_availabilities

    def test__merge_availabilities__availabilities_intersection(
        self, jan_1st_next_year
    ):
        # Given a list of practitioners availabilities with no intersection
        prac_1_id = 1
        potential_appt_1_and_2_start = jan_1st_next_year
        potential_appt_1_and_2_end = jan_1st_next_year + datetime.timedelta(minutes=10)
        potential_appt_1 = PotentialAppointment(
            scheduled_start=potential_appt_1_and_2_start,
            scheduled_end=potential_appt_1_and_2_end,
            total_available_credits=0,
        )
        potential_prac_availability_1 = PotentialPractitionerAvailabilities(
            practitioner_id=prac_1_id,
            product_id=1,
            product_price=10,
            duration=10,
            availabilities=[potential_appt_1],
            contract_priority=99,
        )

        potential_appt_2 = PotentialAppointment(
            scheduled_start=potential_appt_1_and_2_start,
            scheduled_end=potential_appt_1_and_2_end,
            total_available_credits=0,
        )
        prac_2_id = 2
        potential_prac_availability_2 = PotentialPractitionerAvailabilities(
            practitioner_id=prac_2_id,
            product_id=2,
            product_price=10,
            duration=10,
            availabilities=[potential_appt_2],
            contract_priority=99,
        )
        all_pracs_availabilities = [
            potential_prac_availability_1,
            potential_prac_availability_2,
        ]

        expected_merged_availabilities = {
            potential_appt_1_and_2_start: [prac_1_id, prac_2_id]
        }

        # When
        merged_availabilities = CareAdvocateService()._merge_availabilities(
            all_pracs_availabilities=all_pracs_availabilities
        )

        # Then
        assert merged_availabilities == expected_merged_availabilities

    def test__merge_availabilities__sorting(self, jan_1st_next_year):
        # Given a list of practitioners availabilities
        potential_appointments = []
        for i in range(1, 24):
            prac_id = 1
            potential_appt_start = jan_1st_next_year + datetime.timedelta(hours=i)
            potential_appt_end = jan_1st_next_year + datetime.timedelta(
                hours=i, minutes=10
            )
            potential_appt = PotentialAppointment(
                scheduled_start=potential_appt_start,
                scheduled_end=potential_appt_end,
                total_available_credits=0,
            )
            potential_appointments.append(potential_appt)

        potential_prac_availability = PotentialPractitionerAvailabilities(
            practitioner_id=prac_id,
            product_id=1,
            product_price=10,
            duration=10,
            availabilities=potential_appointments,
            contract_priority=99,
        )

        # When
        merged_availabilities = CareAdvocateService()._merge_availabilities(
            all_pracs_availabilities=[potential_prac_availability]
        )

        # Then merged_availabilities are in the same order as our sorted expected_merged_availabilities
        expected_merged_availabilities = {}
        sorted_availabilities = sorted(
            potential_appointments, key=lambda x: x.scheduled_start
        )
        for availability in sorted_availabilities:
            expected_merged_availabilities[availability.scheduled_start] = [1]
        assert merged_availabilities == expected_merged_availabilities


class TestBuildPooledAvailability:
    @mock.patch(
        "care_advocates.services.care_advocate.CareAdvocateService._get_practitioners_availabilities"
    )
    @mock.patch(
        "care_advocates.services.care_advocate.CareAdvocateService._merge_availabilities"
    )
    def test_build_pooled_availability__happy_path(
        self,
        mock_merge_availabilities,
        mock_get_practitioners_availabilities,
        jan_1st_next_year,
        factories,
    ):

        # Given two practitioners
        prac_1 = factories.PractitionerUserFactory()
        prac_2 = factories.PractitionerUserFactory()

        ca_ids = [prac_1.id, prac_2.id]
        start_at = jan_1st_next_year - datetime.timedelta(days=1)
        end_at = jan_1st_next_year + datetime.timedelta(days=1)

        mocked_availabilities = []
        mock_get_practitioners_availabilities.return_value = mocked_availabilities

        # When
        CareAdvocateService().build_pooled_availability(
            ca_ids=ca_ids, start_at=start_at, end_at=end_at
        )

        # Then
        mock_get_practitioners_availabilities.assert_called_once_with(
            [prac_1.practitioner_profile, prac_2.practitioner_profile], start_at, end_at
        )
        mock_merge_availabilities.assert_called_once_with(mocked_availabilities)


class TestLogTimeCoverage:
    @mock.patch("care_advocates.services.care_advocate.log.info")
    def test_log_time_coverage__with_covered_datetimes(
        self, mock_log_info, jan_1st_next_year, factories
    ):

        # Given a set of covered datetimes that spans two hours
        n_pracs = 2
        start_at = jan_1st_next_year
        end_at = start_at + datetime.timedelta(days=1)

        hour_later = start_at + datetime.timedelta(hours=1)
        hour_10_min_later = start_at + datetime.timedelta(hours=1, minutes=10)
        two_hours_later = start_at + datetime.timedelta(hours=2)
        two_hours_10_min_later = start_at + datetime.timedelta(hours=2, minutes=10)

        covered_datetimes = [
            hour_later,
            hour_10_min_later,
            two_hours_later,
            two_hours_10_min_later,
        ]
        covered_hours = {hour_later, two_hours_later}

        user = factories.DefaultUserFactory.create()
        factories.MemberProfileFactory.create(user=user, country_code="AR")
        factories.MemberTrackFactory.create(name="adoption", user=user)

        # When logging coverage
        CareAdvocateService()._log_time_coverage(
            n_pracs=n_pracs,
            start_at=start_at,
            end_at=end_at,
            covered_datetimes=covered_datetimes,
            user=user,
        )

        # Then, the two hours are reported as covered, all others as not covered
        expected_coverage = {}
        hours_between_end_start = (
            int((end_at - start_at).total_seconds() / (60 * 60)) + 1
        )

        for h in range(1, hours_between_end_start):
            datetime_to_report = start_at + datetime.timedelta(hours=h)
            expected_coverage[datetime_to_report.hour] = False
        expected_coverage[hour_later.hour] = True
        expected_coverage[two_hours_later.hour] = True

        expected_fraction_of_hours_covered = round(2 / hours_between_end_start, 2)

        covered_datetimes_iso_format = [dt.isoformat() for dt in covered_datetimes]
        covered_hours_iso_format = [dt.isoformat() for dt in covered_hours]

        mock_log_info.assert_called_with(
            "Pooled availability coverage calculated!!!!",
            n_pracs=n_pracs,
            coverage=expected_coverage,
            fraction_of_hours_covered=expected_fraction_of_hours_covered,
            start_at=start_at.isoformat(),
            end_at=end_at.isoformat(),
            covered_datetimes=str(covered_datetimes_iso_format),
            covered_hours=str(covered_hours_iso_format),
            hours_between_end_start=25,
            user_track=user.current_member_track.name,
            user_country_code=user.country_code,
            user_id=user.id,
        )

    @mock.patch("care_advocates.services.care_advocate.log.info")
    def test_log_time_coverage__with_no_covered_datetimes(
        self, mock_log_info, jan_1st_next_year, factories
    ):
        # Given no set of covered datetimes
        n_pracs = (2,)
        start_at = jan_1st_next_year
        end_at = start_at + datetime.timedelta(days=1)

        covered_datetimes = []
        covered_hours = set()
        user = factories.DefaultUserFactory.create()
        factories.MemberProfileFactory.create(user=user, country_code="AR")
        factories.MemberTrackFactory.create(name="adoption", user=user)

        # When logging coverage
        CareAdvocateService()._log_time_coverage(
            n_pracs=n_pracs,
            start_at=start_at,
            end_at=end_at,
            covered_datetimes=covered_datetimes,
            user=user,
        )

        # Then, the two hours are reported as covered, all others as not covered
        expected_coverage = {}
        hours_between_end_start = (
            int((end_at - start_at).total_seconds() / (60 * 60)) + 1
        )
        for h in range(1, hours_between_end_start):
            datetime_to_report = start_at + datetime.timedelta(hours=h)
            expected_coverage[datetime_to_report.hour] = False

        expected_fraction_of_hours_covered = 0
        covered_datetimes_iso_format = [dt.isoformat() for dt in covered_datetimes]
        covered_hours_iso_format = [dt.isoformat() for dt in covered_hours]
        mock_log_info.assert_called_with(
            "Pooled availability coverage calculated!!!!",
            n_pracs=n_pracs,
            coverage=expected_coverage,
            fraction_of_hours_covered=expected_fraction_of_hours_covered,
            start_at=start_at.isoformat(),
            end_at=end_at.isoformat(),
            covered_datetimes=str(covered_datetimes_iso_format),
            covered_hours=str(covered_hours_iso_format),
            hours_between_end_start=25,
            user_track=user.current_member_track.name,
            user_country_code=user.country_code,
            user_id=user.id,
        )


class TestIsValidUserId:
    def test_is_valid_user_id__is_valid(self, default_user):
        # Given
        member_id_to_validate = default_user.id

        # When
        is_valid_id = CareAdvocateService().is_valid_user_id(
            user_id=member_id_to_validate,
        )

        # Then
        assert is_valid_id

    @pytest.mark.parametrize(
        argnames="member_id_to_validate",
        argvalues=[None, 0, "invalid"],
    )
    def test_is_valid_user_id__not_valid(self, member_id_to_validate):
        # Given
        # When
        is_valid_id = CareAdvocateService().is_valid_user_id(
            user_id=member_id_to_validate,
        )

        # Then
        assert not is_valid_id


class TestAssignCareAdvocate:
    @mock.patch(
        "care_advocates.models.assignable_advocates.AssignableAdvocate.get_cx_with_lowest_weekly_utilization"
    )
    def test_assign_care_advocate__happy_path(
        self,
        mock_get_cx_with_lowest_weekly_utilization,
        default_user,
        factories,
    ):
        prac1 = factories.PractitionerUserFactory()
        prac1_aa = factories.AssignableAdvocateFactory.create_with_practitioner(
            practitioner=prac1
        )

        prac2 = factories.PractitionerUserFactory()
        factories.AssignableAdvocateFactory.create_with_practitioner(practitioner=prac2)

        ca_ids = [prac1.id, prac2.id]
        mock_get_cx_with_lowest_weekly_utilization.return_value = prac1_aa

        assigned_ca = CareAdvocateService().assign_care_advocate(
            default_user.id, ca_ids
        )
        mpa_after_assignment = MemberPractitionerAssociation.query.filter_by(
            user_id=default_user.id,
            practitioner_id=prac1.id,
            type=CareTeamTypes.CARE_COORDINATOR,
        )

        assert assigned_ca == prac1.id
        assert mpa_after_assignment


class TestCheckListForCurrentCareAdvocate:
    def test_check_list_for_current_care_advocate__no_ca(self, factories, default_user):
        # Given a user with no CA
        prac = factories.PractitionerUserFactory()
        # When
        ca_result = CareAdvocateService().check_list_for_current_care_advocate(
            default_user, [prac.id]
        )
        # Then
        assert not ca_result

    def test_check_list_for_current_care_advocate__not_in_list(
        self, factories, default_user, care_advocate, care_advocate_2
    ):
        # Given a user with a CA
        factories.MemberProfileFactory.create(user=default_user)
        factories.MemberPractitionerAssociationFactory.create(
            user_id=default_user.id,
            practitioner_id=care_advocate.id,
            type=CareTeamTypes.CARE_COORDINATOR,
        )
        # When
        ca_result = CareAdvocateService().check_list_for_current_care_advocate(
            default_user, [care_advocate_2.id]
        )
        # Then
        assert not ca_result

    def test_check_list_for_current_care_advocate__in_list(
        self, factories, default_user, care_advocate, care_advocate_2
    ):
        # Given a user with a CA
        factories.MemberProfileFactory.create(user=default_user)
        factories.MemberPractitionerAssociationFactory.create(
            user_id=default_user.id,
            practitioner_id=care_advocate.id,
            type=CareTeamTypes.CARE_COORDINATOR,
        )
        # When
        ca_result = CareAdvocateService().check_list_for_current_care_advocate(
            default_user, [care_advocate.id, care_advocate_2.id]
        )
        # Then
        assert ca_result == care_advocate.id


class TestCareAdvocateSearch:
    @pytest.mark.parametrize(
        "availability_before",
        [None, datetime.datetime.utcnow() + datetime.timedelta(days=7)],
    )
    @mock.patch(
        "care_advocates.models.assignable_advocates.AssignableAdvocate.get_cx_choices_from_member_matching"
    )
    def test_get_potential_care_coordinators_for_member__success(
        self,
        get_cx_choices_from_member_matching_mock,
        availability_before,
        factories,
    ):
        # Given user has one track
        member = factories.EnterpriseUserFactory.create(
            tracks__name=TrackName.ADOPTION,
        )

        prac = factories.PractitionerUserFactory.create()
        aa = factories.AssignableAdvocateFactory.create_with_practitioner(
            practitioner=prac
        )
        get_cx_choices_from_member_matching_mock.return_value = [aa]

        # When
        result = CareAdvocateService().get_potential_care_coordinators_for_member(
            user_id=member.id, availability_before=availability_before
        )

        expected_care_advocate_ids = [prac.id]

        # Then
        assert result == expected_care_advocate_ids

    @pytest.mark.parametrize(
        "availability_before",
        [None, datetime.datetime.utcnow() + datetime.timedelta(days=7)],
    )
    def test_get_potential_care_coordinators_for_member__no_results(
        self, availability_before, factories
    ):
        # Given a user but no practitioners
        member = factories.EnterpriseUserFactory.create(
            tracks__name=TrackName.FERTILITY
        )

        # When
        result = CareAdvocateService().get_potential_care_coordinators_for_member(
            user_id=member.id, availability_before=availability_before
        )

        # Then we expect a successful call with no results
        assert result == []

    @pytest.mark.parametrize(
        "availability_before",
        [None, datetime.datetime.utcnow() + datetime.timedelta(days=7)],
    )
    @mock.patch(
        "care_advocates.models.assignable_advocates.AssignableAdvocate.get_advocates_with_capacity_and_availability"
    )
    @mock.patch(
        "care_advocates.models.assignable_advocates.AssignableAdvocate.get_advocates_with_next_availability_before"
    )
    @mock.patch(
        "care_advocates.models.assignable_advocates.AssignableAdvocate.get_cx_choices_from_member_matching"
    )
    def test_get_potential_care_coordinators_for_member__no_results__available_cas(
        self,
        get_cx_choices_from_member_matching_mock,
        get_advocates_with_next_availability_before_mock,
        get_advocates_with_capacity_and_availability_mock,
        availability_before,
        factories,
    ):
        # Given user has one track, but the available practitioner
        # is not returned as a valid match
        member = factories.EnterpriseUserFactory.create(
            tracks__name=TrackName.ADOPTION,
        )

        prac = factories.PractitionerUserFactory.create()
        aa = factories.AssignableAdvocateFactory.create_with_practitioner(
            practitioner=prac
        )
        get_advocates_with_capacity_and_availability_mock.return_value = [
            aa.practitioner_id
        ]
        get_advocates_with_next_availability_before_mock.return_value = [
            aa.practitioner_id
        ]
        get_cx_choices_from_member_matching_mock.return_value = []

        # When
        result = CareAdvocateService().get_potential_care_coordinators_for_member(
            user_id=member.id, availability_before=availability_before
        )

        expected_care_advocate_ids = [prac.id]

        # Then
        assert result == expected_care_advocate_ids

    @pytest.mark.parametrize(
        "lang_name, lang_iso",
        [("French", "fre"), ("Spanish", "spa")],
    )
    @mock.patch(
        "care_advocates.models.assignable_advocates.AssignableAdvocate.get_advocates_with_capacity_and_availability"
    )
    @mock.patch(
        "care_advocates.models.assignable_advocates.AssignableAdvocate.get_cx_choices_from_member_matching"
    )
    def test_get_potential_care_coordinators_for_member__filter_by_language(
        self,
        get_cx_choices_from_member_matching_mock,
        get_advocates_with_capacity_and_availability_mock,
        lang_name,
        lang_iso,
        factories,
    ):
        # Given user has one track, but the available practitioner
        # is not returned as a valid match
        member = factories.EnterpriseUserFactory.create(
            tracks__name=TrackName.ADOPTION,
        )

        # Expected practitioner
        expected_lang = factories.LanguageFactory.create(
            name=lang_name, iso_639_3=lang_iso
        )
        expected_prac = factories.PractitionerUserFactory.create(
            practitioner_profile__languages=[expected_lang]
        )
        expected_aa = factories.AssignableAdvocateFactory.create_with_practitioner(
            practitioner=expected_prac
        )

        # Filtered prac 1
        filtered_lang_1 = factories.LanguageFactory.create(
            name="German", iso_639_3="ger"
        )
        filtered_prac_1 = factories.PractitionerUserFactory.create(
            practitioner_profile__languages=[filtered_lang_1]
        )
        filtered_aa_1 = factories.AssignableAdvocateFactory.create_with_practitioner(
            practitioner=filtered_prac_1
        )

        # Filtered prac 2
        filtered_lang_2 = factories.LanguageFactory.create(
            name="English", iso_639_3="eng"
        )
        filtered_prac_2 = factories.PractitionerUserFactory.create(
            practitioner_profile__languages=[filtered_lang_2]
        )
        filtered_aa_2 = factories.AssignableAdvocateFactory.create_with_practitioner(
            practitioner=filtered_prac_2
        )

        # Mocks
        get_advocates_with_capacity_and_availability_mock.return_value = [
            expected_aa.practitioner_id,
            filtered_aa_1.practitioner_id,
            filtered_aa_2.practitioner_id,
        ]
        get_cx_choices_from_member_matching_mock.return_value = []

        # When
        result = CareAdvocateService().get_potential_care_coordinators_for_member(
            user_id=member.id,
            filter_by_language=lang_iso,
        )

        expected_care_advocate_ids = [expected_prac.id]

        # Then
        assert result == expected_care_advocate_ids
