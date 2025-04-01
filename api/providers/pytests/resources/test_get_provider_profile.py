import datetime
from types import SimpleNamespace
from unittest import mock

import pytest

from appointments.schemas.provider import get_cancellation_policy_text
from models.tracks.client_track import TrackModifiers
from pytests.factories import StateFactory


def make_state(name, abbreviation):
    return StateFactory.create(name=name, abbreviation=abbreviation)


def states():
    return {
        "NY": make_state(name="New York", abbreviation="NY"),
        "NJ": make_state(name="New Jersey", abbreviation="NJ"),
    }


def get_provider_helper(
    factories: object, vertical: object, country_code: object, certified_states: object
) -> object:
    now = datetime.datetime.utcnow().replace(microsecond=0)
    next_avail = now + datetime.timedelta(minutes=3)
    eng = factories.LanguageFactory.create(name="English")
    deu = factories.LanguageFactory.create(name="German")
    certs = [factories.CertificationFactory.create(name="cert_1")]
    specialties = [factories.SpecialtyFactory.create(name="allergies")]
    img = factories.ImageFactory.create(storage_key="test_img")
    provider = factories.PractitionerUserFactory.create(
        practitioner_profile__dosespot={"foo": "bar"},
        practitioner_profile__verticals=[vertical],
        practitioner_profile__specialties=specialties,
        practitioner_profile__work_experience="work, experience",
        practitioner_profile__education="maven institute, maven school for people who want schooling",
        practitioner_profile__country_code=country_code,
        practitioner_profile__languages=[eng, deu],
        practitioner_profile__default_cancellation_policy__name="moderate",
        practitioner_profile__next_availability=now + datetime.timedelta(minutes=3),
        practitioner_profile__certifications=certs,
        practitioner_profile__certified_states=certified_states,
        image_id=img.id,
    )

    return provider, next_avail


@pytest.fixture
def get_inactive_provider(factories: object) -> object:
    eng = factories.LanguageFactory.create(name="English")
    deu = factories.LanguageFactory.create(name="German")
    certs = [factories.CertificationFactory.create(name="cert_1")]
    verticals = [factories.VerticalFactory(name="womens_health_nurse_practitioner")]
    specialties = [factories.SpecialtyFactory.create(name="allergies")]
    img = factories.ImageFactory.create(storage_key="test_img")
    provider = factories.PractitionerUserFactory.create(
        practitioner_profile__active=False,
        practitioner_profile__dosespot={"foo": "bar"},
        practitioner_profile__verticals=verticals,
        practitioner_profile__specialties=specialties,
        practitioner_profile__work_experience="work, experience",
        practitioner_profile__education="maven institute, maven school for people who want schooling",
        practitioner_profile__country_code="US",
        practitioner_profile__languages=[eng, deu],
        practitioner_profile__default_cancellation_policy__name="moderate",
        practitioner_profile__next_availability=None,
        practitioner_profile__certifications=certs,
        practitioner_profile__certified_states=[states()["NY"]],
        image_id=img.id,
    )
    return provider


@pytest.fixture
def get_provider_usa_nonprescribing_vertical(
    factories, vertical_wellness_coach_cannot_prescribe
):
    return get_provider_helper(
        factories, vertical_wellness_coach_cannot_prescribe, "US", [states()["NY"]]
    )


def test_get_provider_profile(
    client,
    api_helpers,
    factories,
    get_provider_usa_nonprescribing_vertical,
):
    provider, next_availability = get_provider_usa_nonprescribing_vertical
    member = factories.EnterpriseUserFactory.create(
        member_profile__state=provider.practitioner_profile.certified_states[0]
    )

    res = client.get(
        f"/api/v1/providers/{provider.id}/profile",
        headers=api_helpers.json_headers(member),
    )

    assert res.status_code == 200
    expected_response = {
        "certified_states": ["NY"],
        "dynamic_subtext": "Speaks German & English",
        "full_name": provider.full_name,
        "is_vertical_state_filtered": False,
        "work_experience": ["work", "experience"],
        "cancellation_policy": "50% refund if canceled at least 24 hours ahead of time",
        "languages": ["English", "German"],
        "vertical": "Wellness Coach",
        "vertical_long_description": "This is an ob-gyn long description",
        "id": provider.id,
        "specialties": ["allergies"],
        "certifications": ["cert_1"],
        "years_experience": 0,
        "next_availability": next_availability.isoformat(),
        "country": "United States",
        "messaging_enabled": True,
        "name": provider.full_name,
        "can_prescribe": False,
        "is_care_advocate": False,
        "country_flag": "",
        "education": ["maven institute", "maven school for people who want schooling"],
        "active": True,
        "can_request_availability": False,
        "can_member_interact": True,
        "appointment_type": "standard",
    }
    response_json = res.json
    actual_image_url = response_json.pop("image_url")
    assert "test_img" in actual_image_url
    assert expected_response == response_json


def test_get_provider_profile_with_l10n(
    client,
    api_helpers,
    factories,
    get_provider_usa_nonprescribing_vertical,
):
    provider, next_availability = get_provider_usa_nonprescribing_vertical
    member = factories.EnterpriseUserFactory.create(
        member_profile__state=provider.practitioner_profile.certified_states[0]
    )

    with mock.patch(
        "appointments.resources.provider_profile.feature_flags.bool_variation",
        return_value=True,
    ):
        res = client.get(
            f"/api/v1/providers/{provider.id}/profile",
            headers=api_helpers.json_headers(member),
        )

    assert res.status_code == 200
    # The difference from the non-flagged version is that since we're looking up the strings from the flatfile,
    # we get real / different responses in 'vertical_long_description' and 'specialties'
    expected_response = {
        "certified_states": ["NY"],
        "dynamic_subtext": "Speaks German & English",
        "full_name": provider.full_name,
        "is_vertical_state_filtered": False,
        "work_experience": ["work", "experience"],
        "cancellation_policy": "50% refund if canceled at least 24 hours ahead of time",
        "languages": ["English", "German"],
        "vertical": "Wellness Coach",
        "vertical_long_description": "Wellness Coaches are personal guides to living "
        "your healthiest life, both physically and "
        "emotionally, and can offer you methods for "
        "getting better sleep, improving how you feel "
        "throughout your day, having a healthy "
        "relationship with food, and more.",
        "id": provider.id,
        "specialties": ["Allergies"],
        "certifications": ["cert_1"],
        "years_experience": 0,
        "next_availability": next_availability.isoformat(),
        "country": "United States",
        "messaging_enabled": True,
        "name": provider.full_name,
        "can_prescribe": False,
        "is_care_advocate": False,
        "country_flag": "",
        "education": ["maven institute", "maven school for people who want schooling"],
        "active": True,
        "can_request_availability": False,
        "can_member_interact": True,
        "appointment_type": "standard",
    }
    response_json = res.json
    actual_image_url = response_json.pop("image_url")
    assert "test_img" in actual_image_url
    assert expected_response == response_json


def test_get_provider_profile__user_not_provider(
    client,
    api_helpers,
    factories,
):
    user = factories.DefaultUserFactory()

    with mock.patch(
        "appointments.resources.provider_profile.feature_flags.bool_variation",
        return_value=True,
    ):
        res = client.get(
            f"/api/v1/providers/{user.id}/profile",
            headers=api_helpers.json_headers(user),
        )

    assert res.status_code == 404


def test_get_provider_profile__inactive_provider__flag_on(
    client,
    api_helpers,
    factories,
    get_inactive_provider,
):
    provider = get_inactive_provider
    member = factories.EnterpriseUserFactory.create(
        member_profile__state=provider.practitioner_profile.certified_states[0]
    )

    with mock.patch(
        "appointments.resources.provider_profile.feature_flags.bool_variation",
        return_value=True,
    ):
        res = client.get(
            f"/api/v1/providers/{provider.id}/profile",
            headers=api_helpers.json_headers(member),
        )

    assert res.status_code == 200
    expected_response = {
        "certified_states": ["NY"],
        "dynamic_subtext": "Speaks German & English",
        "full_name": provider.full_name,
        "is_vertical_state_filtered": True,
        "work_experience": ["work", "experience"],
        "cancellation_policy": "50% refund if canceled at least 24 hours ahead of time",
        "languages": ["English", "German"],
        "vertical": "Women's Health Nurse Practitioner",
        "vertical_long_description": "Women's Health Nurse Practitioners can help you "
        "understand, manage, and treat chronic "
        "illnesses, menopause symptoms, vaginal "
        "discomfort, and any conditions that could be "
        "affecting your reproductive health and "
        "well-being.",
        "id": provider.id,
        "specialties": ["Allergies"],
        "certifications": ["cert_1"],
        "years_experience": 0,
        "next_availability": None,
        "country": "United States",
        "messaging_enabled": True,
        "name": provider.full_name,
        "can_prescribe": True,
        "is_care_advocate": False,
        "country_flag": "",
        "education": ["maven institute", "maven school for people who want schooling"],
        "active": False,
        "can_request_availability": False,
        "can_member_interact": True,
        "appointment_type": "standard",
    }
    response_json = res.json
    actual_image_url = response_json.pop("image_url")
    assert "test_img" in actual_image_url
    assert expected_response == response_json


def test_get_provider_profile__inactive_provider__flag_off(
    client,
    api_helpers,
    factories,
    get_inactive_provider,
):
    provider = get_inactive_provider
    member = factories.EnterpriseUserFactory.create(
        member_profile__state=provider.practitioner_profile.certified_states[0]
    )

    res = client.get(
        f"/api/v1/providers/{provider.id}/profile",
        headers=api_helpers.json_headers(member),
    )

    assert res.status_code == 404


def test_get_provider_profile_can_prescribe(
    client, api_helpers, factories, vertical_wellness_coach_can_prescribe
):
    provider, next_availability = get_provider_helper(
        factories, vertical_wellness_coach_can_prescribe, "US", [states()["NY"]]
    )

    member = factories.EnterpriseUserFactory.create(
        member_profile__state=provider.practitioner_profile.certified_states[0]
    )

    res = client.get(
        f"/api/v1/providers/{provider.id}/profile",
        headers=api_helpers.json_headers(member),
    )

    assert res.status_code == 200
    assert res.json["can_prescribe"]


def assert_cannot_prescribe(client, api_helpers, provider, member):
    res = client.get(
        f"/api/v1/providers/{provider.id}/profile",
        headers=api_helpers.json_headers(member),
    )

    assert res.status_code == 200
    assert not res.json["can_prescribe"]


def test_get_provider_profile_cannot_prescribe_outside_US(
    client, api_helpers, factories, vertical_wellness_coach_can_prescribe
):
    provider, next_availability = get_provider_helper(
        factories, vertical_wellness_coach_can_prescribe, "UK", []
    )

    member = factories.EnterpriseUserFactory.create()
    assert_cannot_prescribe(client, api_helpers, provider, member)


def test_get_provider_profile_cannot_prescribe_state_mismatch(
    client, api_helpers, factories, vertical_wellness_coach_can_prescribe
):
    provider, next_availability = get_provider_helper(
        factories, vertical_wellness_coach_can_prescribe, "US", [states()["NY"]]
    )

    member = factories.EnterpriseUserFactory.create()
    assert_cannot_prescribe(client, api_helpers, provider, member)


def test_get_provider_profile_cannot_prescribe_member_org_no_rx(
    client, api_helpers, factories, vertical_wellness_coach_can_prescribe
):
    provider, next_availability = get_provider_helper(
        factories, vertical_wellness_coach_can_prescribe, "US", [states()["NY"]]
    )

    member = factories.EnterpriseUserFactory.create()
    member.organization.rx_enabled = False

    assert_cannot_prescribe(client, api_helpers, provider, member)


def test_get_provider_profile_cannot_prescribe_member_org_education_only(
    client, api_helpers, factories, vertical_wellness_coach_can_prescribe
):
    provider, next_availability = get_provider_helper(
        factories, vertical_wellness_coach_can_prescribe, "US", [states()["NY"]]
    )

    member = factories.EnterpriseUserFactory.create()
    # This makes the education_only check kind of redundant, but it's required to be configured this way, otherwise
    # setting education_only will throw an exception
    member.organization.rx_enabled = False
    member.organization.education_only = True

    assert_cannot_prescribe(client, api_helpers, provider, member)


def test_provider_not_found(
    client,
    api_helpers,
    enterprise_user,
):
    res = client.get(
        "/api/v1/providers/99999/profile",
        headers=api_helpers.json_headers(enterprise_user),
    )

    assert res.status_code == 404


def test_get_provider_profile__doula_only__can_interact(
    client,
    api_helpers,
    factories,
    create_doula_only_member,
):

    vertical = factories.VerticalFactory.create(name="Doula and childbirth educator")
    provider, availability = get_provider_helper(
        factories,
        vertical,
        "US",
        [states()["NY"]],
    )
    member = create_doula_only_member
    active_member_track = member.active_tracks[0]
    client_track_id = active_member_track.client_track_id

    # create a VerticalAccessByTrack record to allow vertical <> client track interaction
    factories.VerticalAccessByTrackFactory.create(
        client_track_id=client_track_id,
        vertical_id=vertical.id,
        track_modifiers=TrackModifiers.DOULA_ONLY,
    )

    with mock.patch(
        "appointments.resources.provider_profile.feature_flags.bool_variation",
        return_value=True,
    ):
        res = client.get(
            f"/api/v1/providers/{provider.id}/profile",
            headers=api_helpers.json_headers(member),
        )

    assert res.status_code == 200
    expected_response = {
        "certified_states": ["NY"],
        "dynamic_subtext": "Speaks German & English",
        "full_name": provider.full_name,
        "is_vertical_state_filtered": True,
        "work_experience": ["work", "experience"],
        "cancellation_policy": "50% refund if canceled at least 24 hours ahead of time",
        "languages": ["English", "German"],
        "vertical": "Doula and Childbirth Educator",
        "vertical_long_description": "Doulas and Childbirth Educators can tell you "
        "what to expect during labor and delivery, share "
        "ways to advocate for yourself, offer positions, "
        "breathing techniques, and medications that ease "
        "labor pain, and tips for a happy, healthy life "
        "postpartum.",
        "id": provider.id,
        "specialties": ["Allergies"],
        "certifications": ["cert_1"],
        "years_experience": 0,
        "next_availability": availability.isoformat(),
        "country": "United States",
        "messaging_enabled": True,
        "name": provider.full_name,
        "can_prescribe": False,
        "is_care_advocate": False,
        "country_flag": "",
        "education": ["maven institute", "maven school for people who want schooling"],
        "active": True,
        "can_request_availability": False,
        "can_member_interact": True,
        "appointment_type": "education_only",
    }
    response_json = res.json
    actual_image_url = response_json.pop("image_url")
    assert "test_img" in actual_image_url
    assert expected_response == response_json


def test_get_provider_profile__doula_only__cant_interact(
    client,
    api_helpers,
    get_provider_usa_nonprescribing_vertical,
    create_doula_only_member,
):
    provider, availability = get_provider_usa_nonprescribing_vertical
    member = create_doula_only_member

    with mock.patch(
        "appointments.resources.provider_profile.feature_flags.bool_variation",
        return_value=True,
    ):
        res = client.get(
            f"/api/v1/providers/{provider.id}/profile",
            headers=api_helpers.json_headers(member),
        )

    assert res.status_code == 200
    expected_response = {
        "certified_states": ["NY"],
        "dynamic_subtext": "Speaks German & English",
        "full_name": provider.full_name,
        "is_vertical_state_filtered": False,
        "work_experience": ["work", "experience"],
        "cancellation_policy": "50% refund if canceled at least 24 hours ahead of time",
        "languages": ["English", "German"],
        "vertical": "Wellness Coach",
        "vertical_long_description": "Wellness Coaches are personal guides to living "
        "your healthiest life, both physically and "
        "emotionally, and can offer you methods for "
        "getting better sleep, improving how you feel "
        "throughout your day, having a healthy "
        "relationship with food, and more.",
        "id": provider.id,
        "specialties": ["Allergies"],
        "certifications": ["cert_1"],
        "years_experience": 0,
        "next_availability": availability.isoformat(),
        "country": "United States",
        "messaging_enabled": True,
        "name": provider.full_name,
        "can_prescribe": False,
        "is_care_advocate": False,
        "country_flag": "",
        "education": ["maven institute", "maven school for people who want schooling"],
        "active": True,
        "can_request_availability": False,
        "can_member_interact": False,
        "appointment_type": "standard",
    }
    response_json = res.json
    actual_image_url = response_json.pop("image_url")
    assert "test_img" in actual_image_url
    assert expected_response == response_json


def test_get_provider_profile__marketplace__can_member_interact(
    client, api_helpers, get_provider_usa_nonprescribing_vertical, factories
):
    provider, availability = get_provider_usa_nonprescribing_vertical
    member = factories.MemberFactory()

    with mock.patch(
        "appointments.resources.provider_profile.feature_flags.bool_variation",
        return_value=True,
    ):
        res = client.get(
            f"/api/v1/providers/{provider.id}/profile",
            headers=api_helpers.json_headers(member),
        )

    response_json = res.json
    assert response_json["can_member_interact"]


@pytest.mark.parametrize("locale", [None, "en", "es", "fr"])
def test_get_provider_profile__localized_dynamic_subtext(
    locale,
    client,
    api_helpers,
    factories,
    get_provider_usa_nonprescribing_vertical,
    release_mono_api_localization_on,
):
    provider, next_availability = get_provider_usa_nonprescribing_vertical
    member = factories.EnterpriseUserFactory.create(
        member_profile__state=provider.practitioner_profile.certified_states[0]
    )

    with mock.patch(
        "appointments.resources.provider_profile.feature_flags.bool_variation",
        return_value=True,
    ):
        headers = api_helpers.with_locale_header(
            api_helpers.json_headers(member), locale
        )
        res = client.get(
            f"/api/v1/providers/{provider.id}/profile",
            headers=headers,
        )

    assert res.status_code == 200
    assert (
        res.json["dynamic_subtext"]
        != "provider_dynamic_subtext_speaks German & English"
    )


@pytest.mark.parametrize("locale", [None, "en", "es", "fr"])
@pytest.mark.parametrize(
    "policy_name", ["conservative", "flexible", "moderate", "strict"]
)
def test_get_cancellation_policy_text(locale, policy_name):
    # imitate the object being passed in
    obj = SimpleNamespace(cancellation_policy=SimpleNamespace(name=policy_name))
    keyname = f"cancellation_policy_explanation_{policy_name}"
    assert keyname != get_cancellation_policy_text(obj, True)
