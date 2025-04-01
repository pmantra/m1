import random
from datetime import datetime, timedelta
from unittest.mock import MagicMock, call, patch

import pytest
from sqlalchemy import func

from authn.models.user import User
from models.profiles import (
    CareTeamTypes,
    MemberPractitionerAssociation,
    PractitionerProfile,
)
from models.tracks.client_track import TrackModifiers
from models.tracks.track import TrackName
from models.verticals_and_specialties import CX_VERTICAL_NAME, Vertical
from provider_matching.models.constants import StateMatchType
from provider_matching.models.vgc import VGC
from provider_matching.routes.care_team_assignment import (
    CareTeamReassignEndpointMessage,
)
from provider_matching.services.care_team_assignment import (
    REPLACE_PRAC_JOB_TIMEOUT,
    assign_user_care_team_by_track,
    ensure_care_advocate,
    find_users_associated_to_practitioner,
    get_active_practitioners_per_vgc_for_track,
    get_practitioner_with_in_state_prioritization,
    is_an_active_available_practitioner,
    remove_member_practitioner_associations,
    replace_care_team_members_during_onboarding,
    replace_care_team_members_during_transition,
    replace_practitioner_in_care_teams,
    spin_off_replace_practitioner_in_care_teams_jobs,
)
from pytests.util import restore
from storage.connection import db


@pytest.fixture(scope="function", autouse=True)
def restore_verticals(db):
    from schemas.io import Fixture

    with restore(db, Fixture.VERTICALS):
        yield db


@pytest.fixture
def states(create_state):
    return {
        "NY": create_state(name="New York", abbreviation="NY"),
        "NJ": create_state(name="New Jersey", abbreviation="NJ"),
        "CA": create_state(name="California", abbreviation="CA"),
    }


class TestEnsureCareAdvocate:
    def test_ensure_care_advocate_no_change(self, factories):
        # Given
        user = factories.EnterpriseUserFactory.create(tracks__name=TrackName.PREGNANCY)
        user.member_tracks.append(
            factories.MemberTrackFactory(name=TrackName.POSTPARTUM)
        )
        # Then
        assert ensure_care_advocate(user) is False

    def test_ensure_care_advocate_successful(self, factories):
        # Given
        user = factories.DefaultUserFactory.create()
        # Then
        assert ensure_care_advocate(user)

    def test_ensure_care_advocate_successful_with_cx_change(self, factories):
        # Given
        member = factories.EnterpriseUserFactory.create()
        original_ca = member.care_coordinators[0]

        practitioner = factories.PractitionerUserFactory.create()
        aa = factories.AssignableAdvocateFactory.create_with_practitioner(
            practitioner=practitioner
        )
        with patch(
            "care_advocates.models.assignable_advocates.AssignableAdvocate.get_advocates_with_max_capacity"
        ) as get_advocates_with_max_capacity_mock:
            get_advocates_with_max_capacity_mock.return_value = [aa.practitioner_id]
            # Then
            assert ensure_care_advocate(member)
            new_ca = member.care_coordinators[0]
            assert original_ca.id != new_ca.id


class TestReplaceOnboardingCareTeamMembers:
    def test_removes_only_quiz_type_mpas(self, factories):
        inactive_track = factories.MemberTrackFactory(
            ended_at=datetime.today() - timedelta(days=3)
        )
        user = inactive_track.user
        existing_prac = factories.PractitionerUserFactory()
        existing_prac2 = factories.PractitionerUserFactory()
        factories.MemberPractitionerAssociationFactory(
            type="QUIZ",
            user=user,
            practitioner_profile=existing_prac.practitioner_profile,
            json={"member_track_id": inactive_track.id},
        )
        factories.MemberPractitionerAssociationFactory(
            type="QUIZ",
            user=user,
            practitioner_profile=existing_prac2.practitioner_profile,
            json={"member_track_id": inactive_track.id},
        )
        # Represents the fact that the member was assigned this practitioner
        # at onboarding, and then saw them for an appointment
        factories.MemberPractitionerAssociationFactory(
            type="APPOINTMENT",
            user=user,
            practitioner_profile=existing_prac2.practitioner_profile,
        )

        replace_care_team_members_during_transition(user)
        assert existing_prac.practitioner_profile not in user.care_team
        assert existing_prac2.practitioner_profile in user.care_team

    def test_removes_mpas_only_for_inactive_tracks(self, factories):
        user = factories.DefaultUserFactory.create()
        active_track = factories.MemberTrackFactory(
            user=user,
        )
        existing_prac_for_active_track = factories.PractitionerUserFactory()
        factories.MemberPractitionerAssociationFactory(
            type="QUIZ",
            user=user,
            practitioner_profile=existing_prac_for_active_track.practitioner_profile,
            json={"member_track_id": active_track.id},
        )

        inactive_track = factories.MemberTrackFactory(
            user=user,
            ended_at=datetime.today() - timedelta(days=1),
            client_track=active_track.client_track,
        )
        existing_prac_for_inactive_track_1 = factories.PractitionerUserFactory()
        factories.MemberPractitionerAssociationFactory(
            type="QUIZ",
            user=user,
            practitioner_profile=existing_prac_for_inactive_track_1.practitioner_profile,
            json={"member_track_id": inactive_track.id},
        )

        inactive_track_2 = factories.MemberTrackFactory(
            user=user,
            client_track=active_track.client_track,
            ended_at=datetime.today() - timedelta(days=2),
        )
        existing_prac_for_inactive_track_2 = factories.PractitionerUserFactory()
        factories.MemberPractitionerAssociationFactory(
            type="QUIZ",
            user=user,
            practitioner_profile=existing_prac_for_inactive_track_2.practitioner_profile,
            json={"member_track_id": inactive_track_2.id},
        )
        db.session.commit()

        replace_care_team_members_during_transition(user)
        assert existing_prac_for_active_track.practitioner_profile in user.care_team
        assert (
            existing_prac_for_inactive_track_1.practitioner_profile
            not in user.care_team
        )
        assert (
            existing_prac_for_inactive_track_2.practitioner_profile
            not in user.care_team
        )

    def test_removes_mpas_for_active_and_inactive_tracks(self, factories):
        user = factories.DefaultUserFactory.create()
        active_track = factories.MemberTrackFactory(
            user=user,
        )
        existing_prac_for_active_track = factories.PractitionerUserFactory()
        factories.MemberPractitionerAssociationFactory(
            type="QUIZ",
            user=user,
            practitioner_profile=existing_prac_for_active_track.practitioner_profile,
            json={"member_track_id": active_track.id},
        )

        inactive_track = factories.MemberTrackFactory(
            user=user,
            ended_at=datetime.today() - timedelta(days=1),
            client_track=active_track.client_track,
        )
        existing_prac_for_inactive_track = factories.PractitionerUserFactory()
        factories.MemberPractitionerAssociationFactory(
            type="QUIZ",
            user=user,
            practitioner_profile=existing_prac_for_inactive_track.practitioner_profile,
            json={"member_track_id": inactive_track.id},
        )

        db.session.commit()

        replace_care_team_members_during_onboarding(user)
        assert existing_prac_for_active_track.practitioner_profile not in user.care_team
        assert (
            existing_prac_for_inactive_track.practitioner_profile not in user.care_team
        )

    def test_removes_providers_who_cannot_be_interacted_with(self, factories):
        inactive_track = factories.MemberTrackFactory(
            ended_at=datetime.today() - timedelta(days=3)
        )
        user = inactive_track.user
        existing_practitioner_1 = factories.PractitionerUserFactory()
        existing_practitioner_2 = factories.PractitionerUserFactory()
        factories.MemberPractitionerAssociationFactory(
            type=CareTeamTypes.APPOINTMENT,
            user=user,
            practitioner_profile=existing_practitioner_1.practitioner_profile,
            json={"member_track_id": inactive_track.id},
        )
        factories.MemberPractitionerAssociationFactory(
            type=CareTeamTypes.MESSAGE,
            user=user,
            practitioner_profile=existing_practitioner_2.practitioner_profile,
            json={"member_track_id": inactive_track.id},
        )

        with patch(
            "provider_matching.services.care_team_assignment.ProviderService.provider_can_member_interact"
        ) as mock_provider_can_member_interact:
            mock_provider_can_member_interact.side_effect = [False, True]
            replace_care_team_members_during_transition(user)
        assert user.care_team == [existing_practitioner_2.practitioner_profile]

    @pytest.mark.parametrize("is_doula_only", [True, False])
    def test_remove_doula_from_non_doula_only_maternity_track(
        self, is_doula_only, factories
    ):

        # Given

        # track name is set to a maternity track where we want to prioritize doulas for doula only members
        track_name = TrackName.PREGNANCYLOSS

        vertical = factories.VerticalFactory.create(
            name="Doula And Childbirth Educator"
        )

        # create a VerticalAccessByTrack record to allow vertical <> client track interaction
        client_track_id = 1
        factories.VerticalAccessByTrackFactory.create(
            client_track_id=client_track_id,
            vertical_id=vertical.id,
            track_modifiers=TrackModifiers.DOULA_ONLY if is_doula_only else None,
        )

        doula = factories.PractitionerUserFactory(
            practitioner_profile__verticals=[vertical]
        )

        member = factories.MemberFactory.create()

        factories.PractitionerTrackVGCFactory(
            track=track_name.value,
            vgc=VGC.DOULA.value,
            practitioner_id=doula.id,
        )

        # When
        res = get_active_practitioners_per_vgc_for_track(
            track_name=track_name,
            track_modifiers=[TrackModifiers.DOULA_ONLY] if is_doula_only else [],
            client_track_ids=[client_track_id],
            member=member,
        )

        # Then
        # assert that the doula only member in maternity track 'pregnancyloss' has a doula assigned to them, and non doula-only member does not
        expected_res = {"Doula": [doula.id]} if is_doula_only else {}
        assert res == expected_res

    @pytest.mark.parametrize("is_doula_only", [True, False])
    def test_remove_doula_from_non_doula_only_maternity_track__non_prioritized_tracks(
        self, is_doula_only, factories
    ):
        # Given

        # track name is set to a maternity track where we do not want to prioritize doulas for doula only members
        track_name = TrackName.PREGNANCY

        vertical = factories.VerticalFactory.create(
            name="Doula And Childbirth Educator"
        )

        # create a VerticalAccessByTrack record to allow vertical <> client track interaction
        client_track_id = 1
        factories.VerticalAccessByTrackFactory.create(
            client_track_id=client_track_id,
            vertical_id=vertical.id,
            track_modifiers=TrackModifiers.DOULA_ONLY if is_doula_only else None,
        )

        doula = factories.PractitionerUserFactory(
            practitioner_profile__verticals=[vertical]
        )

        member = factories.MemberFactory.create()

        factories.PractitionerTrackVGCFactory(
            track=track_name.value,
            vgc=VGC.DOULA.value,
            practitioner_id=doula.id,
        )

        # When
        res = get_active_practitioners_per_vgc_for_track(
            track_name=track_name,
            track_modifiers=[TrackModifiers.DOULA_ONLY] if is_doula_only else [],
            client_track_ids=[client_track_id],
            member=member,
        )

        # Then
        # assert that both the doula and non doula only members in maternity track 'pregnnacy' have a doula assigned to them
        assert res == {"Doula": [doula.id]}


class TestAssignUserCareTeam:
    def test_care_team_assignment__no_practitioners_assigned(self, factories):
        track_name = TrackName.PREGNANCY
        member = factories.DefaultUserFactory.create()
        member_track = factories.MemberTrackFactory(
            name=track_name,
            user=member,
        )

        with patch(
            "provider_matching.services.care_team_assignment.get_active_practitioners_per_vgc_for_track"
        ) as care_team_assignment__get_active_practitioners_per_vgc_for_track_mock:
            care_team_assignment__get_active_practitioners_per_vgc_for_track_mock.return_value = (
                {}
            )

            assign_user_care_team_by_track(user=member, member_track=member_track)
            assert len(member.care_team) == 0

    def test_care_team_assignment_by_track_is_cumulative(self, factories):
        # Setup 2 non-cx verticals for pracs
        verticals = (
            Vertical.query.filter(Vertical.name.notlike(CX_VERTICAL_NAME))
            .limit(2)
            .all()
        )
        existing_vertical = [verticals[0]]
        new_vertical = [verticals[1]]

        # Sets up a CA by default in post_generation
        member = factories.EnterpriseUserFactory()
        care_advocate = member.care_coordinators[0]
        existing_prac = factories.PractitionerUserFactory.create(
            practitioner_profile__verticals=existing_vertical,
        )
        factories.MemberPractitionerAssociationFactory(
            type="QUIZ",
            user=member,
            practitioner_profile=existing_prac.practitioner_profile,
        )
        assert len(member.care_team) == 2

        new_track_name = TrackName.ADOPTION
        member_track = factories.MemberTrackFactory(
            name=new_track_name.value,
            user=member,
        )

        with patch(
            "provider_matching.services.care_team_assignment.get_active_practitioners_per_vgc_for_track"
        ) as care_team_assignment__get_active_practitioners_per_vgc_for_track_mock:
            p = factories.PractitionerUserFactory.create(
                practitioner_profile__verticals=new_vertical,
            )

            care_team_assignment__get_active_practitioners_per_vgc_for_track_mock.return_value = {
                VGC.CAREER_COACH: [p.id]
            }

            assign_user_care_team_by_track(user=member, member_track=member_track)
            db.session.commit()

            assert len(member.care_team) == 3
            assert care_advocate.practitioner_profile in member.care_team
            assert existing_prac.practitioner_profile in member.care_team

    def test_care_team_assignment_by_track_doesnt_assign_prac_of_same_vertical(
        self, factories
    ):
        track_name = random.choice([*TrackName])
        member_track = factories.MemberTrackFactory(name=track_name)
        existing_prac = factories.PractitionerUserFactory()
        factories.MemberPractitionerAssociationFactory(
            type="QUIZ",
            user=member_track.user,
            practitioner_profile=existing_prac.practitioner_profile,
        )
        existing_prac_vertical = existing_prac.practitioner_profile.verticals[0]
        assert len(member_track.user.care_team) == 1

        new_prac = factories.PractitionerUserFactory()
        # replace new practitioner's vertical with that of the already existing practitioner
        new_prac.practitioner_profile.verticals.pop()
        new_prac.practitioner_profile.verticals.append(existing_prac_vertical)

        with patch(
            "provider_matching.services.care_team_assignment.get_active_practitioners_per_vgc_for_track"
        ) as care_team_assignment__get_active_practitioners_per_vgc_for_track_mock, patch(
            "models.enterprise.logger"
        ) as logger_mock:
            care_team_assignment__get_active_practitioners_per_vgc_for_track_mock.return_value = {
                VGC.CAREER_COACH: [new_prac.id]
            }

            log_mock = MagicMock()
            logger_mock.return_value = log_mock

            assign_user_care_team_by_track(
                user=member_track.user, member_track=member_track
            )

            assert len(member_track.user.care_team) == 1
            assert log_mock.debug.called_with(
                "Practitioner with this vertical already in care team, not adding"
            )

    def test_care_team_assignment_by_track_sets_json_on_mpa(self, factories):
        track_name = random.choice([*TrackName])
        member_track = factories.MemberTrackFactory(name=track_name)

        with patch(
            "provider_matching.services.care_team_assignment.get_active_practitioners_per_vgc_for_track"
        ) as care_team_assignment__get_active_practitioners_per_vgc_for_track_mock:
            p = factories.PractitionerUserFactory()
            care_team_assignment__get_active_practitioners_per_vgc_for_track_mock.return_value = {
                1: [p.id]
            }

            assign_user_care_team_by_track(
                user=member_track.user, member_track=member_track
            )

            assert (
                member_track.user.practitioner_associations[0].member_track_id
            ) == member_track.id

    def test_care_team_assignment_by_track_prioritizes_in_state_practitioners(
        self, factories, states
    ):
        with patch(
            "provider_matching.services.care_team_assignment.get_active_practitioners_per_vgc_for_track"
        ) as care_team_assignment__get_active_practitioners_per_vgc_for_track_mock:
            # Create some fake data
            track_name = random.choice([*TrackName])
            member = factories.DefaultUserFactory.create()
            factories.MemberProfileFactory.create(user=member, state=states["NY"])

            member_track = factories.MemberTrackFactory(
                name=track_name,
                user=member,
            )

            p_ny = factories.PractitionerUserFactory()
            p_ny.practitioner_profile.certified_states = [states["NY"]]
            p_nj = factories.PractitionerUserFactory()
            p_nj.practitioner_profile.certified_states = [states["NJ"]]

            care_team_assignment__get_active_practitioners_per_vgc_for_track_mock.return_value = {
                VGC.CAREER_COACH: [p_ny.id, p_nj.id]
            }

            assign_user_care_team_by_track(
                user=member_track.user, member_track=member_track
            )

            assert len(member_track.user.practitioner_associations) > 0
            assert (
                member_track.user.practitioner_associations[0].member_track_id
            ) == member_track.id

            # Check that everyone in the user's care team is in_state
            for practitioner_association in member_track.user.practitioner_associations:
                user_state = practitioner_association.user.member_profile.state

                practitioner_profile = PractitionerProfile.query.get(
                    practitioner_association.practitioner_id
                )

                practitioner_certified_states = practitioner_profile.certified_states

                assert user_state in practitioner_certified_states


class TestGetActivePractitionersPerVgcForTrack:
    def test_one_active_prac(self, factories):
        track_name = TrackName.PREGNANCY
        practitioner = factories.PractitionerUserFactory(id=1)
        practitioner.practitioner_profile.active = True
        member = factories.MemberFactory.create()
        vgc = VGC.CAREER_COACH

        ptv = factories.PractitionerTrackVGCFactory(
            track=track_name.value,
            vgc=vgc.value,
            practitioner_id=practitioner.id,
        )

        result = get_active_practitioners_per_vgc_for_track(
            track_name=track_name,
            track_modifiers=[],
            client_track_ids=[],
            member=member,
        )
        expected_result = {
            vgc.value: [ptv.practitioner_id],
        }

        assert result == expected_result

    def test_one_inactive_prac(self, factories):
        track_name = TrackName.PREGNANCY
        member = factories.MemberFactory.create()

        practitioner = factories.PractitionerUserFactory(id=1)
        practitioner.practitioner_profile.active = False
        vgc = VGC.CAREER_COACH

        factories.PractitionerTrackVGCFactory(
            track=track_name.value,
            vgc=vgc.value,
            practitioner_id=practitioner.id,
        )

        result = get_active_practitioners_per_vgc_for_track(
            track_name=track_name,
            track_modifiers=[],
            client_track_ids=[],
            member=member,
        )
        expected_result = {}

        assert result == expected_result

    @pytest.mark.skip(reason="Skipping test due to excessive flakiness in CI.")
    def test_three_prac_two_vgc(self, factories):
        track_name = TrackName.PREGNANCY
        member = factories.MemberFactory.create()

        practitioner1 = factories.PractitionerUserFactory(id=1)
        practitioner1.practitioner_profile.active = True
        practitioner2 = factories.PractitionerUserFactory(id=2)
        practitioner2.practitioner_profile.active = True
        practitioner3 = factories.PractitionerUserFactory(id=3)
        practitioner3.practitioner_profile.active = False

        vgc1 = VGC.CAREER_COACH
        vgc2 = VGC.DOULA

        ptv1 = factories.PractitionerTrackVGCFactory(
            track=track_name.value,
            vgc=vgc1.value,
            practitioner_id=practitioner1.id,
        )
        ptv2 = factories.PractitionerTrackVGCFactory(
            track=track_name.value,
            vgc=vgc2.value,
            practitioner_id=practitioner2.id,
        )
        factories.PractitionerTrackVGCFactory(
            track=track_name.value,
            vgc=vgc2.value,
            practitioner_id=practitioner3.id,
        )

        result = get_active_practitioners_per_vgc_for_track(
            track_name=ptv1.track,
            track_modifiers=[],
            client_track_ids=[],
            member=member,
        )
        expected_result = {
            vgc1.value: [ptv1.practitioner_id],
            vgc2.value: [ptv2.practitioner_id],
        }

        assert result == expected_result

    def test_no_practitioners(self, factories):
        track_name = TrackName.SPONSORED
        member = factories.MemberFactory.create()
        result = get_active_practitioners_per_vgc_for_track(
            track_name=track_name,
            track_modifiers=[],
            client_track_ids=[],
            member=member,
        )
        expected_result = {}
        assert result == expected_result

    def test_member_cannot_interact(self, factories):
        practitioner_1 = factories.PractitionerUserFactory(id=1)
        practitioner_1.practitioner_profile.active = True
        practitioner_2 = factories.PractitionerUserFactory(id=2)
        practitioner_2.practitioner_profile.active = True

        practitioner_track_vgc_1 = factories.PractitionerTrackVGCFactory(
            track=TrackName.PREGNANCY,
            vgc=VGC.CAREER_COACH,
            practitioner_id=practitioner_1.id,
        )
        practitioner_track_vgc_2 = factories.PractitionerTrackVGCFactory(
            track=TrackName.PREGNANCY,
            vgc=VGC.DOULA,
            practitioner_id=practitioner_2.id,
        )
        member = factories.MemberFactory.create()
        client_track_id = 1

        with patch(
            "provider_matching.services.care_team_assignment.ProviderService.provider_can_member_interact"
        ) as mock_provider_can_member_interact:
            mock_provider_can_member_interact.side_effect = [False, True]
            assert get_active_practitioners_per_vgc_for_track(
                track_name=practitioner_track_vgc_1.track,
                track_modifiers=[TrackModifiers.DOULA_ONLY],
                client_track_ids=[client_track_id],
                member=member,
            ) == {
                VGC.DOULA: [practitioner_track_vgc_2.practitioner_id],
            }
            mock_provider_can_member_interact.assert_has_calls(
                [
                    call(
                        provider=practitioner_1.practitioner_profile,
                        modifiers=[TrackModifiers.DOULA_ONLY],
                        client_track_ids=[client_track_id],
                    ),
                    call(
                        provider=practitioner_2.practitioner_profile,
                        modifiers=[TrackModifiers.DOULA_ONLY],
                        client_track_ids=[client_track_id],
                    ),
                ]
            )

    def test_us_member_not_assigned_to_intl_providers(self, factories):
        practitioner_1 = factories.PractitionerUserFactory(id=1)
        practitioner_1.practitioner_profile.active = True
        practitioner_2 = factories.PractitionerUserFactory(id=2)
        practitioner_2.practitioner_profile.active = True
        practitioner_2.practitioner_profile.country_code = "UK"

        practitioner_track_vgc_1 = factories.PractitionerTrackVGCFactory(
            track=TrackName.PREGNANCY,
            vgc=VGC.CAREER_COACH,
            practitioner_id=practitioner_1.id,
        )
        factories.PractitionerTrackVGCFactory(
            track=TrackName.PREGNANCY,
            vgc=VGC.DOULA,
            practitioner_id=practitioner_2.id,
        )
        member = factories.MemberFactory.create()
        client_track_id = 1

        with patch("maven.feature_flags.bool_variation", return_value=True), patch(
            "provider_matching.services.care_team_assignment.ProviderService.provider_can_member_interact"
        ) as mock_provider_can_member_interact:
            mock_provider_can_member_interact.side_effect = [True, True]
            assert get_active_practitioners_per_vgc_for_track(
                track_name=practitioner_track_vgc_1.track,
                track_modifiers=[TrackModifiers.DOULA_ONLY],
                client_track_ids=[client_track_id],
                member=member,
            ) == {
                VGC.CAREER_COACH: [practitioner_track_vgc_1.practitioner_id],
            }

    def test_intl_member_can_be_assigned_to_us_providers(self, factories):
        practitioner_1 = factories.PractitionerUserFactory(id=1)
        practitioner_1.practitioner_profile.active = True
        practitioner_2 = factories.PractitionerUserFactory(id=2)
        practitioner_2.practitioner_profile.active = True

        practitioner_track_vgc_1 = factories.PractitionerTrackVGCFactory(
            track=TrackName.PREGNANCY,
            vgc=VGC.CAREER_COACH,
            practitioner_id=practitioner_1.id,
        )
        practitioner_track_vgc_2 = factories.PractitionerTrackVGCFactory(
            track=TrackName.PREGNANCY,
            vgc=VGC.DOULA,
            practitioner_id=practitioner_2.id,
        )
        # Create international member
        intl_state = factories.StateFactory.create(name="Other", abbreviation="ZZ")
        member = factories.MemberFactory.create(
            member_profile__state=intl_state, member_profile__country_code="AU"
        )
        client_track_id = 1

        with patch("maven.feature_flags.bool_variation", return_value=True), patch(
            "provider_matching.services.care_team_assignment.ProviderService.provider_can_member_interact"
        ) as mock_provider_can_member_interact:
            mock_provider_can_member_interact.side_effect = [True, True]
            assert get_active_practitioners_per_vgc_for_track(
                track_name=practitioner_track_vgc_1.track,
                track_modifiers=[TrackModifiers.DOULA_ONLY],
                client_track_ids=[client_track_id],
                member=member,
            ) == {
                VGC.CAREER_COACH: [practitioner_track_vgc_1.practitioner_id],
                VGC.DOULA: [practitioner_track_vgc_2.practitioner_id],
            }


class TestGetPractitionerWithInStatePrioritization:
    def test_get_practitioner_with_in_state_prioritization(self, default_user):
        with patch(
            "provider_matching.services.care_team_assignment.calculate_state_match_type_for_practitioners_v3"
        ) as calculate_state_match_type_for_practitioners_v3_mock:
            fake_prac_ids_in_state = [1, 2, 3]
            fake_prac_ids_out_of_state = [4, 5, 6]

            matches = {
                StateMatchType.IN_STATE.value: fake_prac_ids_in_state,
                StateMatchType.OUT_OF_STATE.value: fake_prac_ids_out_of_state,
                StateMatchType.MISSING.value: [],
            }
            calculate_state_match_type_for_practitioners_v3_mock.return_value = matches

            potential_practitioner_id = get_practitioner_with_in_state_prioritization(
                user=default_user,
                prac_ids=fake_prac_ids_in_state + fake_prac_ids_out_of_state,
                track_name="PREGNANCY",
                vgc="Mental Health",
            )

            assert potential_practitioner_id in fake_prac_ids_in_state


class TestIsAnActiveAvailablePractitioner:
    def test_active_practitioner(self, factories):
        practitioner = factories.PractitionerUserFactory.create()
        factories.PractitionerTrackVGCFactory.create(
            practitioner_id=practitioner.id,
            track=TrackName.PREGNANCY,
            vgc=VGC.CAREER_COACH,
        )
        assert is_an_active_available_practitioner(practitioner.id) is True

    def test_inactive_practitioner(self, factories):
        practitioner = factories.PractitionerUserFactory.create(active=False)
        assert is_an_active_available_practitioner(practitioner.id) is False


class TestFindUsersAssociatedToPractitioner:
    def test_find_users_quiz_only_no_users(self, factories):
        practitioner = factories.PractitionerUserFactory.create()

        assert (
            find_users_associated_to_practitioner(
                prac_id=practitioner.id, remove_only_quiz_type=True
            )
            == []
        )

    def test_find_users_quiz_only_succeeds(self, factories):
        user1 = factories.DefaultUserFactory.create()
        user2 = factories.DefaultUserFactory.create()
        practitioner = factories.PractitionerUserFactory.create()
        factories.MemberPractitionerAssociationFactory.create(
            user_id=user1.id, practitioner_id=practitioner.id, type=CareTeamTypes.QUIZ
        )
        factories.MemberPractitionerAssociationFactory.create(
            user_id=user2.id,
            practitioner_id=practitioner.id,
            type=CareTeamTypes.APPOINTMENT,
        )
        assert find_users_associated_to_practitioner(
            prac_id=practitioner.id, remove_only_quiz_type=True
        ) == [user1.id]

    def test_find_users_succeeds(self, factories):
        user1 = factories.DefaultUserFactory.create()
        user2 = factories.DefaultUserFactory.create()
        practitioner = factories.PractitionerUserFactory.create()
        factories.MemberPractitionerAssociationFactory.create(
            user_id=user1.id, practitioner_id=practitioner.id, type=CareTeamTypes.QUIZ
        )
        factories.MemberPractitionerAssociationFactory.create(
            user_id=user2.id,
            practitioner_id=practitioner.id,
            type=CareTeamTypes.APPOINTMENT,
        )
        assert find_users_associated_to_practitioner(
            prac_id=practitioner.id, remove_only_quiz_type=False
        ) == [
            user1.id,
            user2.id,
        ]


class TestRemoveMemberPractitionerAssociations:
    def test_remove_quiz_associations(self, factories):
        user = factories.DefaultUserFactory.create()
        practitioner = factories.PractitionerUserFactory.create()
        mpa = factories.MemberPractitionerAssociationFactory.create(
            user_id=user.id, practitioner_id=practitioner.id, type=CareTeamTypes.QUIZ
        )
        mpas_deleted = remove_member_practitioner_associations(
            prac_to_remove=practitioner.id, user_id=user.id, remove_only_quiz_type=True
        )
        assert mpas_deleted == [mpa.id]

        mpa_after_deletion = (
            db.session.query(MemberPractitionerAssociation)
            .filter_by(user_id=user.id)
            .filter_by(practitioner_id=practitioner.id)
            .all()
        )
        assert mpa_after_deletion == []

    def test_remove_all_associations(self, factories):
        user = factories.DefaultUserFactory.create()
        practitioner = factories.PractitionerUserFactory.create()
        mpa = factories.MemberPractitionerAssociationFactory.create(
            user_id=user.id,
            practitioner_id=practitioner.id,
            type=CareTeamTypes.APPOINTMENT,
        )
        mpas_deleted = remove_member_practitioner_associations(
            prac_to_remove=practitioner.id, user_id=user.id, remove_only_quiz_type=False
        )
        assert mpas_deleted == [mpa.id]
        mpa_after_deletion = (
            db.session.query(MemberPractitionerAssociation)
            .filter_by(user_id=user.id)
            .filter_by(practitioner_id=practitioner.id)
            .all()
        )
        assert mpa_after_deletion == []


@pytest.mark.skip(reason="Flaky tests. Addressed in sc-115182")
class TestReplacePractitionerInCareTeams:
    """
    Some first validation tests
    """

    def test_prac_to_replace_is_quiz_remove_only_quiz_type_true_replacement_successful(
        self, factories
    ):
        # Setup: create practitioner, and add it to a user's care teams
        user = factories.EnterpriseUserFactory.create(tracks__name=TrackName.PREGNANCY)

        original_practitioner = factories.PractitionerUserFactory.create()
        obgy_vertical = factories.VerticalFactory(name="OB-GYN")
        original_practitioner.practitioner_profile.verticals = [obgy_vertical]
        factories.MemberPractitionerAssociationFactory.create(
            user_id=user.id,
            practitioner_id=original_practitioner.id,
            type=CareTeamTypes.QUIZ,
        )

        # Create a new practitioner, and make them available
        new_practitioner = factories.PractitionerUserFactory.create()
        new_practitioner.practitioner_profile.verticals = [obgy_vertical]
        factories.PractitionerTrackVGCFactory.create(
            practitioner_id=new_practitioner.id,
            track=TrackName.PREGNANCY,
            vgc=VGC.OB_GYN,
        )

        # Call replace practitioner
        with patch("provider_matching.services.care_team_assignment.Lock") as LockMock:
            lock_instance = LockMock.return_value
            # We know that by the time we call replace_practitioner_in_care_teams, the lock has already been acquired, so we will mock that
            lock_instance.locked.return_value = True

            replace_practitioner_in_care_teams(
                prac_to_replace_id=original_practitioner.id,
                remove_only_quiz_type=True,
                users_ids=[user.id],
                to_email="test@test.com",
            )

            # Validate that the original practitioner has been removed from user's care team
            original_prac_mpas = (
                db.session.query(MemberPractitionerAssociation)
                .filter_by(user_id=user.id)
                .filter_by(practitioner_id=original_practitioner.id)
                .all()
            )
            assert len(original_prac_mpas) == 0

            # Validate that new practitioner is in user's care team
            new_prac_mpas = (
                db.session.query(MemberPractitionerAssociation)
                .filter_by(user_id=user.id)
                .filter_by(practitioner_id=new_practitioner.id)
                .all()
            )
            assert len(new_prac_mpas) == 1

            # Validate that lock has been released
            lock_instance.do_release.assert_called_once_with(
                expected_token=str(original_practitioner.id)
            )

    def test_prac_to_replace_is_appointment_remove_only_quiz_type_false_replacement_successful(
        self, factories, states
    ):
        # Setup: create practitioner, and add it to a user's care teams
        user = factories.EnterpriseUserFactory.create(tracks__name=TrackName.PREGNANCY)

        original_practitioner = factories.PractitionerUserFactory.create()
        obgy_vertical = factories.VerticalFactory(name="OB-GYN")
        original_practitioner.practitioner_profile.verticals = [obgy_vertical]
        factories.MemberPractitionerAssociationFactory.create(
            user_id=user.id,
            practitioner_id=original_practitioner.id,
            type=CareTeamTypes.APPOINTMENT,
        )

        # Create a new practitioner, and make them available
        new_practitioner = factories.PractitionerUserFactory.create()
        new_practitioner.practitioner_profile.verticals = [obgy_vertical]
        factories.PractitionerTrackVGCFactory.create(
            practitioner_id=new_practitioner.id,
            track=TrackName.PREGNANCY,
            vgc=VGC.OB_GYN,
        )
        with patch("provider_matching.services.care_team_assignment.Lock") as LockMock:
            lock_instance = LockMock.return_value
            lock_instance.locked.return_value = True

            # Call replace practitioner
            replace_practitioner_in_care_teams(
                prac_to_replace_id=original_practitioner.id,
                users_ids=[user.id],
                remove_only_quiz_type=False,
                to_email="test@test.com",
            )

            # Validate that the original practitioner has been removed from user's care team
            original_prac_mpas = (
                db.session.query(MemberPractitionerAssociation)
                .filter_by(user_id=user.id)
                .filter_by(practitioner_id=original_practitioner.id)
                .all()
            )
            assert len(original_prac_mpas) == 0

            # Validate that new practitioner is in user's care team
            new_prac_mpas = (
                db.session.query(MemberPractitionerAssociation)
                .filter_by(user_id=user.id)
                .filter_by(practitioner_id=new_practitioner.id)
                .all()
            )
            assert len(new_prac_mpas) == 1

            # Validate that lock has been released
            lock_instance.do_release.assert_called_once_with(
                expected_token=str(original_practitioner.id)
            )

    def test_prac_to_replace_is_quiz_and_appointment_remove_only_quiz_type_true_replacement_not_successful(
        self, factories, states
    ):
        # Setup: create practitioner, and add it to a user's care teams
        user = factories.EnterpriseUserFactory.create(tracks__name=TrackName.PREGNANCY)

        original_practitioner = factories.PractitionerUserFactory.create()
        obgy_vertical = factories.VerticalFactory(name="OB-GYN")
        original_practitioner.practitioner_profile.verticals = [obgy_vertical]

        factories.MemberPractitionerAssociationFactory.create(
            user_id=user.id,
            practitioner_id=original_practitioner.id,
            type=CareTeamTypes.QUIZ,
        )
        factories.MemberPractitionerAssociationFactory.create(
            user_id=user.id,
            practitioner_id=original_practitioner.id,
            type=CareTeamTypes.APPOINTMENT,
        )

        # Create a new practitioner, and make them available
        new_practitioner = factories.PractitionerUserFactory.create()
        new_practitioner.practitioner_profile.verticals = [obgy_vertical]
        factories.PractitionerTrackVGCFactory.create(
            practitioner_id=new_practitioner.id,
            track=TrackName.PREGNANCY,
            vgc=VGC.OB_GYN,
        )

        with patch("provider_matching.services.care_team_assignment.Lock") as LockMock:
            lock_instance = LockMock.return_value
            lock_instance.locked.return_value = True

            # Call replace practitioner with remove_only_quiz_type True
            replace_practitioner_in_care_teams(
                prac_to_replace_id=original_practitioner.id,
                users_ids=[user.id],
                remove_only_quiz_type=True,
                to_email="test@test.com",
            )

            # Validate that the original practitioner with type quiz has been removed
            original_prac_quiz_mpas = (
                db.session.query(MemberPractitionerAssociation)
                .filter_by(user_id=user.id)
                .filter_by(practitioner_id=original_practitioner.id)
                .filter_by(type=CareTeamTypes.QUIZ)
                .all()
            )
            assert len(original_prac_quiz_mpas) == 0

            # Validate that the original practitioner with type appointment has not been removed
            original_prac_appointment_mpas = (
                db.session.query(MemberPractitionerAssociation)
                .filter_by(user_id=user.id)
                .filter_by(practitioner_id=original_practitioner.id)
                .filter_by(type=CareTeamTypes.APPOINTMENT)
                .all()
            )
            assert len(original_prac_appointment_mpas) == 1

            # Validate that the new practitioner has not been added
            new_prac_mpas = (
                db.session.query(MemberPractitionerAssociation)
                .filter_by(user_id=user.id)
                .filter_by(practitioner_id=new_practitioner.id)
                .all()
            )
            assert len(new_prac_mpas) == 0

            # Validate that lock has been released
            lock_instance.do_release.assert_called_once_with(
                expected_token=str(original_practitioner.id)
            )

    def test_prac_to_replace_is_quiz_and_appointment_remove_only_quiz_type_false_replacement_successful(
        self, factories
    ):
        # Setup: create practitioner, and add it to a user's care teams
        user = factories.EnterpriseUserFactory.create(tracks__name=TrackName.PREGNANCY)

        original_practitioner = factories.PractitionerUserFactory.create()
        obgy_vertical = factories.VerticalFactory(name="OB-GYN")
        original_practitioner.practitioner_profile.verticals = [obgy_vertical]

        factories.MemberPractitionerAssociationFactory.create(
            user_id=user.id,
            practitioner_id=original_practitioner.id,
            type=CareTeamTypes.QUIZ,
        )
        factories.MemberPractitionerAssociationFactory.create(
            user_id=user.id,
            practitioner_id=original_practitioner.id,
            type=CareTeamTypes.APPOINTMENT,
        )

        # Create a new practitioner, and make them available
        new_practitioner = factories.PractitionerUserFactory.create()
        new_practitioner.practitioner_profile.verticals = [obgy_vertical]
        factories.PractitionerTrackVGCFactory.create(
            practitioner_id=new_practitioner.id,
            track=TrackName.PREGNANCY,
            vgc=VGC.OB_GYN,
        )

        with patch("provider_matching.services.care_team_assignment.Lock") as LockMock:
            lock_instance = LockMock.return_value
            lock_instance.locked.return_value = True

            # Call replace practitioner with remove_only_quiz_type False
            replace_practitioner_in_care_teams(
                prac_to_replace_id=original_practitioner.id,
                users_ids=[user.id],
                remove_only_quiz_type=False,
                to_email="test@test.com",
            )

            # Validate that the original practitioner with type quiz has been removed
            original_prac_quiz_mpas = (
                db.session.query(MemberPractitionerAssociation)
                .filter_by(user_id=user.id)
                .filter_by(practitioner_id=original_practitioner.id)
                .filter_by(type=CareTeamTypes.QUIZ)
                .all()
            )
            assert len(original_prac_quiz_mpas) == 0

            # Validate that the original practitioner with type appointment has been removed
            original_prac_appointment_mpas = (
                db.session.query(MemberPractitionerAssociation)
                .filter_by(user_id=user.id)
                .filter_by(practitioner_id=original_practitioner.id)
                .filter_by(type=CareTeamTypes.APPOINTMENT)
                .all()
            )
            assert len(original_prac_appointment_mpas) == 0

            # Validate that the new original practitioner been added
            new_prac_mpas = (
                db.session.query(MemberPractitionerAssociation)
                .filter_by(user_id=user.id)
                .filter_by(practitioner_id=new_practitioner.id)
                .all()
            )
            assert len(new_prac_mpas) == 1

            # Validate that lock has been released
            lock_instance.do_release.assert_called_once_with(
                expected_token=str(original_practitioner.id)
            )

    def test_prac_to_replace_in_two_care_teams_remove_only_quiz_type_true_replacement_successful(
        self, factories, states
    ):
        # Setup: create practitioner, and add it to a users' care teams
        user1 = factories.EnterpriseUserFactory.create(tracks__name=TrackName.PREGNANCY)
        user2 = factories.EnterpriseUserFactory.create(tracks__name=TrackName.PREGNANCY)

        original_practitioner = factories.PractitionerUserFactory.create()
        obgy_vertical = factories.VerticalFactory(name="OB-GYN")
        original_practitioner.practitioner_profile.verticals = [obgy_vertical]

        factories.MemberPractitionerAssociationFactory.create(
            user_id=user1.id,
            practitioner_id=original_practitioner.id,
            type=CareTeamTypes.QUIZ,
        )
        factories.MemberPractitionerAssociationFactory.create(
            user_id=user2.id,
            practitioner_id=original_practitioner.id,
            type=CareTeamTypes.QUIZ,
        )

        # Create a new practitioner, and make them available
        new_practitioner = factories.PractitionerUserFactory.create()
        new_practitioner.practitioner_profile.verticals = [obgy_vertical]
        factories.PractitionerTrackVGCFactory.create(
            practitioner_id=new_practitioner.id,
            track=TrackName.PREGNANCY,
            vgc=VGC.OB_GYN,
        )

        with patch("provider_matching.services.care_team_assignment.Lock") as LockMock:
            lock_instance = LockMock.return_value
            lock_instance.locked.return_value = True
            # Call replace practitioner
            replace_practitioner_in_care_teams(
                prac_to_replace_id=original_practitioner.id,
                users_ids=[user1.id, user2.id],
                remove_only_quiz_type=False,
                to_email="test@test.com",
            )

            # Validate that the original practitioner with type quiz has been removed
            original_prac_quiz_mpas = (
                db.session.query(MemberPractitionerAssociation)
                .filter_by(practitioner_id=original_practitioner.id)
                .filter_by(type=CareTeamTypes.QUIZ)
                .all()
            )
            assert len(original_prac_quiz_mpas) == 0

            # Validate that the new practitioner been added to the two users teams
            new_prac_mpa_user1 = (
                db.session.query(MemberPractitionerAssociation)
                .filter_by(practitioner_id=new_practitioner.id)
                .filter_by(user_id=user1.id)
                .all()
            )
            assert len(new_prac_mpa_user1) == 1

            new_prac_mpa_user2 = (
                db.session.query(MemberPractitionerAssociation)
                .filter_by(practitioner_id=new_practitioner.id)
                .filter_by(user_id=user2.id)
                .all()
            )
            assert len(new_prac_mpa_user2) == 1

            # Validate that lock has been released
            lock_instance.do_release.assert_called_once_with(
                expected_token=str(original_practitioner.id)
            )


class TestSpinOffReplacePractitionerInCareTeamsJobs:
    def test_found_no_users_for_practitioner(self, factories):
        # Setup: create practitioner
        original_practitioner = factories.PractitionerUserFactory.create()
        obgy_vertical = factories.VerticalFactory(name="OB-GYN")
        original_practitioner.practitioner_profile.verticals = [obgy_vertical]

        with patch(
            "provider_matching.services.care_team_assignment.replace_practitioner_in_care_teams"
        ) as replace_practitioner_in_care_teams_mock:
            job_ids = spin_off_replace_practitioner_in_care_teams_jobs(
                prac_to_replace_id=original_practitioner.id,
                remove_only_quiz_type=True,
                to_email="test@maven.com",
            )

            assert not replace_practitioner_in_care_teams_mock.delay.called
            assert job_ids is None

    def test_success(self, factories):
        # Setup: create practitioner, and add it to a user's care teams
        user = factories.EnterpriseUserFactory.create(tracks__name=TrackName.PREGNANCY)

        original_practitioner = factories.PractitionerUserFactory.create()
        obgy_vertical = factories.VerticalFactory(name="OB-GYN")
        original_practitioner.practitioner_profile.verticals = [obgy_vertical]
        factories.MemberPractitionerAssociationFactory.create(
            user_id=user.id,
            practitioner_id=original_practitioner.id,
            type=CareTeamTypes.QUIZ,
        )

        # Create a new practitioner, and make them available
        new_practitioner = factories.PractitionerUserFactory.create()
        new_practitioner.practitioner_profile.verticals = [obgy_vertical]
        factories.PractitionerTrackVGCFactory.create(
            practitioner_id=new_practitioner.id,
            track=TrackName.PREGNANCY,
            vgc=VGC.OB_GYN,
        )

        with patch(
            "provider_matching.services.care_team_assignment.replace_practitioner_in_care_teams"
        ) as replace_practitioner_in_care_teams_mock:
            job_ids = spin_off_replace_practitioner_in_care_teams_jobs(
                prac_to_replace_id=original_practitioner.id,
                remove_only_quiz_type=True,
                to_email="test@maven.com",
            )

            replace_practitioner_in_care_teams_mock.delay.assert_called_once_with(
                prac_to_replace_id=original_practitioner.id,
                users_ids=[user.id],
                remove_only_quiz_type=True,
                to_email="test@maven.com",
                job_timeout=REPLACE_PRAC_JOB_TIMEOUT,
                service_ns="care_team",
                team_ns="care_discovery",
            )

            assert len(job_ids) == 1


class TestCareTeamAssignmentReassignEndpoint:
    url_prefix = "/api/v1/care-team-assignment/reassign"

    def test_unauthenticated_user(self, client, api_helpers):
        resp = client.post(
            f"{self.url_prefix}/1",
            headers=api_helpers.json_headers(),
        )
        assert resp.status_code == 401

    def test_invalid_user_id(self, client, api_helpers, default_user):
        max_id = db.session.query(func.max(User.id)).first()[0]
        invalid_user_id = max_id + 1
        resp = client.post(
            f"{self.url_prefix}/{invalid_user_id}",
            headers=api_helpers.json_headers(default_user),
        )
        assert resp.status_code == 400
        assert (
            api_helpers.load_json(resp)["message"]
            == CareTeamReassignEndpointMessage.INVALID_USER_ID
        )

    def test_valid_user(self, client, api_helpers, factories, default_user):
        member = factories.EnterpriseUserFactory.create()

        with patch(
            "provider_matching.routes.care_team_assignment.replace_care_team_members_during_onboarding"
        ) as mock_replace_care_team_members_during_onboarding, patch(
            "provider_matching.routes.care_team_assignment.db"
        ) as db_mock:
            resp = client.post(
                f"{self.url_prefix}/{member.id}",
                headers=api_helpers.json_headers(default_user),
            )
            assert resp.status_code == 200
            mock_replace_care_team_members_during_onboarding.assert_called_once_with(
                user=member
            )
            db_mock.session.commit.assert_called_once()
