import datetime
from unittest.mock import PropertyMock, patch

import pytest

from models.tracks.client_track import TrackModifiers
from models.verticals_and_specialties import DOULA_ONLY_VERTICALS
from payments.models.practitioner_contract import ContractType
from payments.pytests.factories import PractitionerContractFactory
from providers.domain.model import Provider
from providers.service.provider import ProviderService
from pytests.factories import VerticalFactory

NOW = datetime.datetime.utcnow()


@pytest.fixture
def states(create_state):
    return {
        "NY": create_state(name="New York", abbreviation="NY"),
        "NJ": create_state(name="New Jersey", abbreviation="NJ"),
        "CA": create_state(name="California", abbreviation="CA"),
    }


@pytest.fixture
def practitioner_can_prescribe(factories, create_practitioner):
    return factories.PractitionerUserFactory.create()


def test_can_prescribe(factories):
    # Arrange
    vertical_1 = factories.VerticalFactory.create(
        name="Adoption Coach", can_prescribe=False
    )
    vertical_2 = factories.VerticalFactory.create(name="OB-GYN")
    provider_1 = factories.PractitionerProfileFactory.create(
        user_id=factories.DefaultUserFactory.create().id,
        dosespot={"test": "hi"},
        verticals=[vertical_1],
    )
    provider_2 = factories.PractitionerProfileFactory.create(
        user_id=factories.DefaultUserFactory.create().id,
        dosespot={"test": "hi"},
        verticals=[vertical_2],
    )

    # Act
    provider_service = ProviderService()

    # Assert
    assert provider_service.can_prescribe(provider_1.user_id) is False
    assert provider_service.can_prescribe(provider_2.user_id) is True


@pytest.mark.parametrize(
    [
        "provider_can_prescribe",
        "prescribable_state",
        "expected",
    ],
    [
        (False, "NY", False),
        (True, None, False),
        (True, "NJ", False),
        (True, "NY", True),
    ],
    ids=[
        "Provider cannot prescribe",
        "Provider cannot prescribe but member cannot receive prescription in any state",
        "Provider can prescribe but member cannot receive prescription in certified state",
        "Provider can prescribe to member and the member can receive prescription in state",
    ],
)
def test_can_prescribe_to_member(
    created_provider: Provider,
    provider_can_prescribe: bool,
    prescribable_state: str,
    expected: bool,
):
    # Act
    provider_service = ProviderService()

    # Assert
    with patch.object(
        provider_service,
        "provider_can_prescribe",
        new_callable=PropertyMock,
        return_value=provider_can_prescribe,
    ):
        assert expected == provider_service.can_prescribe_to_member(
            created_provider.user_id, prescribable_state
        )


@pytest.mark.parametrize(
    [
        "clinic_key",
        "clinic_id",
        "user_id",
        "expected",
    ],
    [
        ("", "", "", False),
        ("test_clinic_key", "", "", False),
        ("test_clinic_key", "test_clinic_id", "", False),
        ("test_clinic_key", "test_clinic_id", "test_user_id", True),
    ],
    ids=[
        "Provider has no dosespot info setup, not enabled for prescribing",
        "Provider only has clinic_key dosespot info setup, not enabled for prescribing",
        "Provider only has clinic_key, clinic_id setup, not enabled for prescribing",
        "Provider has all dosespot info setup, enabled for prescribing",
    ],
)
def test_enabled_for_prescribing(
    created_provider: Provider,
    clinic_key: str,
    clinic_id: int,
    user_id: int,
    expected: bool,
):
    # Arrange
    created_provider.dosespot["clinic_key"] = clinic_key
    created_provider.dosespot["clinic_id"] = clinic_id
    created_provider.dosespot["user_id"] = user_id

    # Act
    provider_service = ProviderService()

    # Assert
    assert expected == provider_service.enabled_for_prescribing(
        created_provider.user_id
    )


@pytest.mark.parametrize(
    [
        "filter_by_state",
        "expected",
    ],
    [
        (False, False),
        (True, True),
    ],
    ids=[
        "Provider is not medical provider",
        "Provider is a medical provider",
    ],
)
def test_is_medical_provider(
    factories,
    filter_by_state: bool,
    expected: bool,
):
    # Arrange
    vertical = factories.VerticalFactory.create(
        name="Adoption Coach", filter_by_state=filter_by_state
    )
    provider = factories.PractitionerProfileFactory.create(
        user_id=factories.DefaultUserFactory.create().id,
        verticals=[vertical],
    )

    # Act
    provider_service = ProviderService()

    # Assert
    assert provider_service.is_medical_provider(provider.user_id) is expected


def test_in_certified_states(factories, states):
    # Arrange
    provider_1 = factories.PractitionerUserFactory()
    provider_2 = factories.PractitionerUserFactory()
    provider_1.practitioner_profile.certified_states = [states["NJ"], states["CA"]]
    provider_2.practitioner_profile.certified_states = [states["NY"], states["CA"]]

    # Act
    provider_service = ProviderService()

    # Assert
    assert provider_service.in_certified_states(provider_1.id, states["NY"]) is False
    assert provider_service.in_certified_states(provider_2.id, states["NY"]) is True


def test_list_available_practitioners_query_can_prescribe(factories):
    # Arrange
    vertical_1 = factories.VerticalFactory.create(
        name="Adoption Coach", can_prescribe=False
    )
    vertical_2 = factories.VerticalFactory.create(name="OB-GYN")
    provider_1 = factories.PractitionerProfileFactory.create(
        user_id=factories.DefaultUserFactory.create().id,
        next_availability=NOW + datetime.timedelta(hours=1),
        dosespot={"test": "hi"},
        verticals=[vertical_1],
    )
    provider_2 = factories.PractitionerProfileFactory.create(
        user_id=factories.DefaultUserFactory.create().id,
        next_availability=NOW + datetime.timedelta(hours=1),
        dosespot={"test": "hi"},
        verticals=[vertical_2],
    )
    member = factories.MemberFactory.create()

    # Act
    provider_service = ProviderService()

    # Assert
    assert provider_service.list_available_practitioners_query(
        member, [provider_1.user_id, provider_2.user_id], False
    ) == [provider_1, provider_2]
    assert provider_service.list_available_practitioners_query(
        member, [provider_1.user_id, provider_2.user_id], True
    ) == [provider_2]


def test_list_available_practitioners_query_member_state(factories, states):
    # Arrange
    provider_1 = factories.PractitionerProfileFactory.create(
        user_id=factories.DefaultUserFactory.create().id,
        next_availability=NOW + datetime.timedelta(hours=1),
        certified_states=[states["CA"]],
        anonymous_allowed=False,
    )
    provider_1.dosespot = {
        "clinic_key": "test_clinic_key",
        "clinic_id": "test_clinic_id",
        "user_id": "test_user_id",
    }
    provider_2 = factories.PractitionerProfileFactory.create(
        user_id=factories.DefaultUserFactory.create().id,
        next_availability=NOW + datetime.timedelta(hours=1),
        certified_states=[states["NJ"]],
        anonymous_allowed=False,
    )
    provider_2.dosespot = {
        "clinic_key": "test_clinic_key",
        "clinic_id": "test_clinic_id",
        "user_id": "test_user_id",
    }
    member = factories.MemberFactory.create(member_profile__state=states["NJ"])

    # Act
    provider_service = ProviderService()

    # Assert
    assert provider_service.list_available_practitioners_query(
        member, [provider_1.user_id, provider_2.user_id], True
    ) == [provider_2]


def test_list_available_practitioners_query_member_state_anonymous_provider(
    factories,
    states,
):
    # Arrange
    provider_1 = factories.PractitionerProfileFactory.create(
        user_id=factories.DefaultUserFactory.create().id,
        next_availability=NOW + datetime.timedelta(hours=1),
        certified_states=[states["CA"]],
        anonymous_allowed=True,
    )
    provider_1.dosespot = {
        "clinic_key": "test_clinic_key",
        "clinic_id": "test_clinic_id",
        "user_id": "test_user_id",
    }
    provider_2 = factories.PractitionerProfileFactory.create(
        user_id=factories.DefaultUserFactory.create().id,
        next_availability=NOW + datetime.timedelta(hours=1),
        certified_states=[states["NJ"]],
        anonymous_allowed=False,
    )
    provider_2.dosespot = {
        "clinic_key": "test_clinic_key",
        "clinic_id": "test_clinic_id",
        "user_id": "test_user_id",
    }
    member = factories.MemberFactory.create(member_profile__state=states["NJ"])

    # Act
    provider_service = ProviderService()

    # Assert
    assert provider_service.list_available_practitioners_query(
        member, [provider_1.user_id, provider_2.user_id], True
    ) == [provider_1, provider_2]


def test_list_available_practitioners_query_is_enterprise(
    factories, enterprise_user, vertical_wellness_coach_can_prescribe
):
    # Arrange
    provider_1 = factories.PractitionerProfileFactory.create(
        user_id=factories.DefaultUserFactory.create().id,
        next_availability=NOW + datetime.timedelta(hours=1),
        ent_national=False,
        show_in_enterprise=False,
        dosespot={"foo": "bar"},
        verticals=[vertical_wellness_coach_can_prescribe],
    )
    provider_2 = factories.PractitionerProfileFactory.create(
        user_id=factories.DefaultUserFactory.create().id,
        next_availability=NOW + datetime.timedelta(hours=1),
        ent_national=True,
        dosespot={"foo": "bar"},
        verticals=[vertical_wellness_coach_can_prescribe],
    )

    # Act
    provider_service = ProviderService()

    # Assert
    assert provider_service.list_available_practitioners_query(
        enterprise_user, [provider_1.user_id, provider_2.user_id], True
    ) == [provider_2]


@pytest.fixture
def providers_for_prescribing(factories):
    provider_1 = factories.PractitionerProfileFactory.create(
        user_id=factories.DefaultUserFactory.create().id,
        dosespot={},
    )
    provider_2 = factories.PractitionerProfileFactory.create(
        user_id=factories.DefaultUserFactory.create().id,
        dosespot={
            "clinic_key": "clinic_key",
            "clinic_id": "clinic_id",
            "user_id": "user_id",
        },
    )
    return {
        "provider_1": provider_1,
        "provider_2": provider_2,
    }


@pytest.mark.parametrize(
    [
        "provider",
        "expected",
    ],
    [
        ("provider_does_not_exist", False),
        ("provider_1", False),
        ("provider_2", True),
    ],
    ids=[
        "Provider is None ",
        "Provider cannot prescribe",
        "Provider can prescribe",
    ],
)
def test_provider_enabled_for_prescribing(
    providers_for_prescribing: dict, provider: str, expected: bool
):
    # Arrange
    p = providers_for_prescribing.get(provider, None)

    # Act
    provider_service = ProviderService()

    # Assert
    assert provider_service.provider_enabled_for_prescribing(p) == expected


def test_get_contract_priorities(factories):
    # Given 7 practitioners with different contract types, 1 without a contract
    now = datetime.datetime.utcnow()
    practitioners = [
        factories.PractitionerUserFactory.create(
            practitioner_profile__next_availability=now + datetime.timedelta(hours=i),
        )
        for i in range(0, 8)
    ]
    # practitioners[0] is a non-contract practitioner
    practitioner_contract_mapping = [
        (practitioners[1], ContractType.BY_APPOINTMENT),
        (practitioners[2], ContractType.FIXED_HOURLY),
        (practitioners[3], ContractType.HYBRID_1_0),
        (practitioners[4], ContractType.W2),
        (practitioners[5], ContractType.HYBRID_2_0),
        (practitioners[6], ContractType.FIXED_HOURLY_OVERNIGHT),
        (practitioners[7], ContractType.NON_STANDARD_BY_APPOINTMENT),
    ]
    for practitioner, contract in practitioner_contract_mapping:
        PractitionerContractFactory.create(
            practitioner=practitioner.practitioner_profile,
            contract_type=contract,
        )

    expected_contract_priority_results = [
        (practitioners[1].id, 3),
        (practitioners[2].id, 1),
        (practitioners[3].id, 2),
        (practitioners[4].id, 1),
        (practitioners[5].id, 2),
        (practitioners[6].id, 1),
        (practitioners[7].id, 3),
    ]

    practitioner_ids = [p.id for p in practitioners]

    # When we call ProviderService().get_contract_priorities
    get_contract_priority_results = ProviderService().get_contract_priorities(
        practitioner_ids
    )

    # Then the resulting practitioner_ids are mapped to the contract prioritization that we expect
    # without the non-contract practitioner
    assert set(get_contract_priority_results) == set(expected_contract_priority_results)


@pytest.mark.parametrize(
    "contract_type, expected_result",
    [
        (ContractType.BY_APPOINTMENT, True),
        (ContractType.FIXED_HOURLY, False),
        (ContractType.FIXED_HOURLY_OVERNIGHT, False),
        (ContractType.HYBRID_1_0, True),
        (ContractType.HYBRID_2_0, True),
        (ContractType.NON_STANDARD_BY_APPOINTMENT, True),
        (ContractType.W2, False),
    ],
)
def test_provider_contract_can_accept_availability_requests(
    contract_type, expected_result, factories
):
    practitioner = factories.PractitionerUserFactory.create()
    PractitionerContractFactory.create(
        practitioner=practitioner.practitioner_profile,
        contract_type=contract_type,
    )

    assert (
        ProviderService().provider_contract_can_accept_availability_requests(
            practitioner.practitioner_profile
        )
        == expected_result
    )


@pytest.mark.parametrize("l10n_flag", [True, False])
def test_get_provider_languages(l10n_flag, factories):
    # Given
    english = factories.LanguageFactory.create(
        name="English", abbreviation="en", iso_639_3="eng"
    )
    spanish = factories.LanguageFactory.create(
        name="Spanish", abbreviation="es", iso_639_3="spa"
    )
    # French should not show up
    french = factories.LanguageFactory.create(
        name="French", abbreviation="fr", iso_639_3="fra"
    )

    expected_language_ids = {english.id, spanish.id}
    expected_language_names = {english.name, spanish.name}

    p1 = factories.PractitionerUserFactory.create(
        practitioner_profile__languages=[english],
    )
    p2 = factories.PractitionerUserFactory.create(
        practitioner_profile__languages=[english, spanish],
    )
    # This practitioner is not passed to get_provider_languages
    factories.PractitionerUserFactory.create(
        practitioner_profile__languages=[french],
    )
    expected_prac_ids = [p1.id, p2.id]

    # When
    actual_languges = ProviderService.get_provider_languages(
        expected_prac_ids, l10n_flag
    )

    # Then
    assert len(actual_languges) == 2
    actual_language_ids = {actual_languges[0].id, actual_languges[1].id}
    actual_language_names = {actual_languges[0].name, actual_languges[1].name}
    assert actual_language_ids == expected_language_ids
    assert actual_language_names == expected_language_names


@pytest.mark.parametrize(
    "track_modifiers, verticals, expected_result",
    [
        ([], ["Doula and childbirth educator"], True),
        ([], ["doctor"], True),
        ([TrackModifiers.DOULA_ONLY], ["doctor"], False),
        ([TrackModifiers.DOULA_ONLY], ["Doula and childbirth educator"], True),
        (
            [
                TrackModifiers.DOULA_ONLY,
                TrackModifiers.DOULA_ONLY,
                TrackModifiers.DOULA_ONLY,
            ],
            ["doctor"],
            False,
        ),
        (
            [
                TrackModifiers.DOULA_ONLY,
                TrackModifiers.DOULA_ONLY,
                TrackModifiers.DOULA_ONLY,
            ],
            ["Doula and childbirth educator"],
            True,
        ),
        (
            [TrackModifiers.DOULA_ONLY],
            ["Doula and childbirth educator", "doctor"],
            True,
        ),
        ([TrackModifiers.DOULA_ONLY], [], False),
    ],
)
def test_provider_can_member_interact(
    track_modifiers, verticals, expected_result, factories
):
    # given
    practitioner = factories.PractitionerUserFactory.create()
    practitioner_verticals = []
    client_track_id = 1

    for vertical in verticals:
        v = VerticalFactory.create(name=vertical)
        if v.name.lower() in DOULA_ONLY_VERTICALS:
            # create a VerticalAccessByTrack record to allow vertical <> client track interaction
            factories.VerticalAccessByTrackFactory.create(
                client_track_id=client_track_id,
                vertical_id=v.id,
                track_modifiers=TrackModifiers.DOULA_ONLY,
            )
        practitioner_verticals.append(v)
    practitioner.verticals = practitioner_verticals

    # when / then
    assert (
        ProviderService().provider_can_member_interact(
            provider=practitioner,
            modifiers=track_modifiers,
            client_track_ids=[client_track_id],
        )
        == expected_result
    )


@pytest.mark.parametrize(
    "filter_by_state, is_instate_match, provider_is_international, member_is_international, member_org_is_coaching_only, expected_appointment_type",
    [
        (False, True, False, False, False, "standard"),
        (False, True, False, False, True, "standard"),
        (True, False, False, False, False, "education_only"),
        (True, True, True, False, False, "education_only"),
        (True, True, False, False, False, "standard"),
        (True, True, False, False, True, "education_only"),
        (False, True, False, True, False, "education_only"),
    ],
)
def test_get_provider_appointment_type_for_member(
    filter_by_state,
    is_instate_match,
    provider_is_international,
    member_is_international,
    member_org_is_coaching_only,
    expected_appointment_type,
):
    assert (
        expected_appointment_type
        == ProviderService.get_provider_appointment_type_for_member(
            filter_by_state,
            is_instate_match,
            provider_is_international,
            member_is_international,
            member_org_is_coaching_only,
        )
    )
