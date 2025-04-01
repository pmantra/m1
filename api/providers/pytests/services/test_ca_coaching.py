import pytest

from models.profiles import CareTeamTypes
from models.tracks import TrackName
from models.verticals_and_specialties import CX_FERTILITY_CARE_COACHING_SLUG
from providers.service.provider import ProviderService
from pytests.freezegun import freeze_time
from storage.connection import db

FREEZE_TIME_STR = "2024-03-01T12:00:00"


@pytest.fixture
def vertical_ca(factories):
    return factories.VerticalFactory.create_cx_vertical()


@pytest.fixture
@freeze_time(FREEZE_TIME_STR)
def care_advocate(factories, vertical_ca):
    # practitioner_profile__verticals gets set in create_with_practitioner below
    provider = factories.PractitionerUserFactory.create(
        practitioner_profile__verticals=[],
    )
    factories.AssignableAdvocateFactory.create_with_practitioner(practitioner=provider)
    return provider


@pytest.fixture
@freeze_time(FREEZE_TIME_STR)
def member_with_ca(factories, care_advocate):
    member = factories.MemberFactory.create()
    factories.ScheduleFactory.create(user=member)
    care_team_type = CareTeamTypes.CARE_COORDINATOR
    factories.MemberPractitionerAssociationFactory.create(
        user_id=member.id,
        practitioner_id=care_advocate.id,
        type=care_team_type,
    )
    return member, care_advocate


def test_member_on_wrong_track(factories, member_with_ca):
    member, care_advocate = member_with_ca
    factories.MemberTrackFactory.create(
        name=TrackName.PARENTING_AND_PEDIATRICS,
        user=member,
    )
    service = ProviderService()
    assert not service.is_member_matched_to_coach_for_active_track(member)


def test_member_matched_with_noncoach(factories, member_with_ca):
    member, care_advocate = member_with_ca
    factories.MemberTrackFactory.create(
        name=TrackName.FERTILITY,
        user=member,
    )
    service = ProviderService()
    assert not service.is_member_matched_to_coach_for_active_track(member)


def test_member_matched_with_coach(factories, member_with_ca):
    member, care_advocate = member_with_ca
    factories.MemberTrackFactory.create(
        name=TrackName.FERTILITY,
        user=member,
    )
    coaching_specialty = factories.SpecialtyFactory(
        name=CX_FERTILITY_CARE_COACHING_SLUG, slug=CX_FERTILITY_CARE_COACHING_SLUG
    )
    care_advocate.practitioner_profile.specialties.append(coaching_specialty)
    db.session.commit()

    service = ProviderService()
    result = service.is_member_matched_to_coach_for_active_track(member)
    assert result
