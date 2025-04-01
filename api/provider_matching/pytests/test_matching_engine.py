from unittest.mock import patch

import pytest

from provider_matching.models.constants import StateMatchType
from provider_matching.services.matching_engine import (
    calculate_state_match_type,
    calculate_state_match_type_for_practitioners_v3,
    get_practitioner_profile,
)


@pytest.fixture
def test_states(create_state):
    """States can only be created once otherwise there are SQLAlchemy errors, so they are created in this dictionary.
    Tests can then get states from this dictionary using the abbreviation as the key.
    """
    return {
        "NY": create_state(name="New York", abbreviation="NY"),
        "NJ": create_state(name="New Jersey", abbreviation="NJ"),
        "CA": create_state(name="California", abbreviation="CA"),
    }


@pytest.fixture
def test_data(factories, test_states):
    """This fixture initializes and contains all the data necessary for the pytests."""
    # NY member
    member_in_ny = factories.MemberFactory.create()
    member_in_ny.member_profile.state = test_states["NY"]

    # NJ member
    member_in_nj = factories.MemberFactory.create()
    member_in_nj.member_profile.state = test_states["NJ"]

    # International member
    intl_state = factories.StateFactory.create(name="Other", abbreviation="ZZ")
    intl_member_in_uk = factories.MemberFactory.create(
        member_profile__state=intl_state, member_profile__country_code="GB"
    )
    intl_member_in_es = factories.MemberFactory.create(
        member_profile__state=intl_state, member_profile__country_code="ES"
    )

    intl_member_in_au = factories.MemberFactory.create(
        member_profile__state=intl_state, member_profile__country_code="AU"
    )

    # member with no state set
    member_in_none = factories.MemberFactory.create()

    # profile of practitioner that is certified in NY
    prac_profile_certified_in_ny = factories.PractitionerUserFactory.create().profile
    prac_profile_certified_in_ny.certified_states = [test_states["NY"]]

    prac_profile_certified_in_ny_2 = factories.PractitionerUserFactory.create().profile
    prac_profile_certified_in_ny_2.certified_states = [test_states["NY"]]

    # profile of practitioner that is certified in NJ
    prac_profile_certified_in_nj = factories.PractitionerUserFactory.create().profile
    prac_profile_certified_in_nj.certified_states = [test_states["NJ"]]

    # profile of practitioner that is certified in CA
    prac_profile_certified_in_ca = factories.PractitionerUserFactory.create().profile
    prac_profile_certified_in_ca.certified_states = [test_states["CA"]]

    # profile of practitioner that is not certified anywhere
    prac_profile_certified_in_none = factories.PractitionerUserFactory.create().profile
    prac_profile_certified_in_none.certified_states = []

    # profile of practitioner that is in UK
    prac_profile_in_uk = factories.PractitionerProfileFactory.create(
        user=factories.PractitionerUserFactory.create(),
        country_code="GB",
        verticals=[
            factories.VerticalFactory.create(name="OB-GYN - Europe", region="Europe")
        ],
    )

    prac_profile_in_fr = factories.PractitionerProfileFactory.create(
        user=factories.PractitionerUserFactory.create(),
        country_code="FR",
        verticals=[
            factories.VerticalFactory.create(name="OB-GYN - Europe", region="Europe")
        ],
    )

    return {
        "member_in_ny": member_in_ny,
        "member_in_nj": member_in_nj,
        "member_in_none": member_in_none,
        "intl_member_in_uk": intl_member_in_uk,
        "intl_member_in_au": intl_member_in_au,
        "intl_member_in_es": intl_member_in_es,
        "prac_profile_certified_in_ny": prac_profile_certified_in_ny,
        "prac_profile_certified_in_ny_2": prac_profile_certified_in_ny_2,
        "prac_profile_certified_in_nj": prac_profile_certified_in_nj,
        "prac_profile_certified_in_ca": prac_profile_certified_in_ca,
        "prac_profile_certified_in_none": prac_profile_certified_in_none,
        "prac_profile_in_uk": prac_profile_in_uk,
        "prac_profile_in_fr": prac_profile_in_fr,
    }


class TestCalculateStateMatchType:
    def test_in_state_match_type(self, test_data):
        """Tests that the member's state and a practitioner's certified state matching is correctly detected."""
        assert (
            calculate_state_match_type(
                practitioner_profile=test_data["prac_profile_certified_in_ny"],
                user=test_data["member_in_ny"],
            )
            == StateMatchType.IN_STATE.value
        )

    def test_state_match_not_permissible_type(self, test_data):
        """Tests that the member's state and a practitioner's certified state not matching is correctly detected."""
        assert (
            calculate_state_match_type(
                practitioner_profile=test_data["prac_profile_certified_in_ny"],
                user=test_data["member_in_nj"],
            )
            == StateMatchType.OUT_OF_STATE.value
        )

    # Test cases where the member state is missing, the practitioner certified state is missing, and both are missing
    @pytest.mark.parametrize(
        "certified_profile, member",
        [
            ("prac_profile_certified_in_ny", "member_in_none"),
            ("prac_profile_certified_in_none", "member_in_ny"),
            ("prac_profile_certified_in_none", "member_in_none"),
        ],
    )
    def test_missing_state_match_type(
        self, factories, test_data, certified_profile: str, member: str
    ):
        """Tests that missing state information is correctly detected."""
        assert (
            calculate_state_match_type(
                practitioner_profile=test_data[certified_profile],
                user=test_data[member],
            )
            == StateMatchType.MISSING.value
        )


class TestGetPractitioner:
    def test_get_practitioner_profile(self, factories):
        pp = factories.PractitionerUserFactory.create().profile

        returned_existing_pp = get_practitioner_profile(pp.user_id)
        assert pp == returned_existing_pp

        returned_non_existent_pp = get_practitioner_profile(pp.user_id + 1)
        assert returned_non_existent_pp is None


class TestCalculateStateMatchTypeForPractitioners:
    def test_calculate_state_match_for_practitioners_v3__successfull(self, test_data):

        matches = calculate_state_match_type_for_practitioners_v3(
            user=test_data["member_in_ny"],
            practitioners_ids=[
                test_data["prac_profile_certified_in_ny"].user_id,
                test_data["prac_profile_certified_in_ny_2"].user_id,
                test_data["prac_profile_certified_in_nj"].user_id,
                test_data["prac_profile_certified_in_ca"].user_id,
                test_data["prac_profile_certified_in_none"].user_id,
            ],
        )

        expected_matches = {
            StateMatchType.IN_STATE.value: [
                test_data["prac_profile_certified_in_ny"].user_id,
                test_data["prac_profile_certified_in_ny_2"].user_id,
            ],
            StateMatchType.OUT_OF_STATE.value: [
                test_data["prac_profile_certified_in_nj"].user_id,
                test_data["prac_profile_certified_in_ca"].user_id,
            ],
            StateMatchType.MISSING.value: [
                test_data["prac_profile_certified_in_none"].user_id
            ],
        }

        for key in matches:
            matches[key].sort()
        for key in expected_matches:
            expected_matches[key].sort()

        assert matches == expected_matches

    def test_calculate_state_match_for_practitioners_v3__member_has_no_state(
        self, test_data
    ):
        matches = calculate_state_match_type_for_practitioners_v3(
            user=test_data["member_in_none"],
            practitioners_ids=[
                test_data["prac_profile_certified_in_ny"].user_id,
                test_data["prac_profile_certified_in_nj"].user_id,
                test_data["prac_profile_certified_in_none"].user_id,
            ],
        )

        expected_matches = {
            StateMatchType.IN_STATE.value: [],
            StateMatchType.OUT_OF_STATE.value: [],
            StateMatchType.MISSING.value: [
                test_data["prac_profile_certified_in_ny"].user_id,
                test_data["prac_profile_certified_in_nj"].user_id,
                test_data["prac_profile_certified_in_none"].user_id,
            ],
        }

        assert matches == expected_matches


class TestCalculateStateMatchTypeForInternationalPractitioners:
    def test_calculate_state_match_for_practitioners_v3__international_member(
        self, test_data
    ):
        with patch("maven.feature_flags.bool_variation", return_value=True):
            matches = calculate_state_match_type_for_practitioners_v3(
                user=test_data["intl_member_in_uk"],
                practitioners_ids=[
                    test_data["prac_profile_certified_in_ny"].user_id,
                    test_data["prac_profile_certified_in_ny_2"].user_id,
                    test_data["prac_profile_certified_in_nj"].user_id,
                    test_data["prac_profile_certified_in_ca"].user_id,
                    test_data["prac_profile_certified_in_none"].user_id,
                    test_data["prac_profile_in_uk"].user.id,
                    test_data["prac_profile_in_fr"].user.id,
                ],
            )

            expected_matches = {
                StateMatchType.IN_STATE.value: [
                    test_data["prac_profile_in_uk"].user_id,
                ],
                StateMatchType.OUT_OF_STATE.value: [
                    test_data["prac_profile_certified_in_ny"].user_id,
                    test_data["prac_profile_certified_in_ny_2"].user_id,
                    test_data["prac_profile_certified_in_nj"].user_id,
                    test_data["prac_profile_certified_in_ca"].user_id,
                    test_data["prac_profile_certified_in_none"].user_id,
                    test_data["prac_profile_in_fr"].user.id,
                ],
                StateMatchType.MISSING.value: [],
            }

            for key in matches:
                matches[key].sort()
            for key in expected_matches:
                expected_matches[key].sort()

            assert matches == expected_matches

    def test_calculate_state_match_for_practitioners_v3__international_member_no_country_match(
        self, test_data
    ):
        with patch("maven.feature_flags.bool_variation", return_value=True):
            matches = calculate_state_match_type_for_practitioners_v3(
                user=test_data["intl_member_in_es"],
                practitioners_ids=[
                    test_data["prac_profile_certified_in_ny"].user_id,
                    test_data["prac_profile_certified_in_ny_2"].user_id,
                    test_data["prac_profile_certified_in_nj"].user_id,
                    test_data["prac_profile_certified_in_ca"].user_id,
                    test_data["prac_profile_certified_in_none"].user_id,
                    test_data["prac_profile_in_uk"].user.id,
                    test_data["prac_profile_in_fr"].user.id,
                ],
            )

            expected_matches = {
                StateMatchType.IN_STATE.value: [
                    test_data["prac_profile_in_uk"].user_id,
                    test_data["prac_profile_in_fr"].user.id,
                ],
                StateMatchType.OUT_OF_STATE.value: [
                    test_data["prac_profile_certified_in_ny"].user_id,
                    test_data["prac_profile_certified_in_ny_2"].user_id,
                    test_data["prac_profile_certified_in_nj"].user_id,
                    test_data["prac_profile_certified_in_ca"].user_id,
                    test_data["prac_profile_certified_in_none"].user_id,
                ],
                StateMatchType.MISSING.value: [],
            }

            for key in matches:
                matches[key].sort()
            for key in expected_matches:
                expected_matches[key].sort()

            assert matches == expected_matches

    def test_calculate_state_match_for_practitioners_v3__international_member_no_match(
        self, test_data
    ):
        with patch("maven.feature_flags.bool_variation", return_value=True):
            matches = calculate_state_match_type_for_practitioners_v3(
                user=test_data["intl_member_in_au"],
                practitioners_ids=[
                    test_data["prac_profile_certified_in_ny"].user_id,
                    test_data["prac_profile_certified_in_ny_2"].user_id,
                    test_data["prac_profile_certified_in_nj"].user_id,
                    test_data["prac_profile_certified_in_ca"].user_id,
                    test_data["prac_profile_certified_in_none"].user_id,
                    test_data["prac_profile_in_uk"].user.id,
                ],
            )

            expected_matches = {
                StateMatchType.IN_STATE.value: [],
                StateMatchType.OUT_OF_STATE.value: [
                    test_data["prac_profile_in_uk"].user_id,
                    test_data["prac_profile_certified_in_ny"].user_id,
                    test_data["prac_profile_certified_in_ny_2"].user_id,
                    test_data["prac_profile_certified_in_nj"].user_id,
                    test_data["prac_profile_certified_in_ca"].user_id,
                ],
                StateMatchType.MISSING.value: [
                    test_data["prac_profile_certified_in_none"].user_id,
                ],
            }

            for key in matches:
                matches[key].sort()
            for key in expected_matches:
                expected_matches[key].sort()

            assert matches == expected_matches
