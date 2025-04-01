import pytest

from provider_matching.services.matching_engine import (
    StateMatchNotPermissibleError,
    StateMatchNotPermissibleMessage,
    state_match_not_permissible,
)


@pytest.fixture
def states(create_state):
    return {
        "NY": create_state(name="New York", abbreviation="NY"),
        "NJ": create_state(name="New Jersey", abbreviation="NJ"),
        "CA": create_state(name="California", abbreviation="CA"),
        "WA": create_state(name="Washington", abbreviation="WA"),
    }


class TestStateMatchNotPermissible:
    def test_practitioner_has_no_verticals(self, factories, states):
        user = factories.EnterpriseUserFactory()
        practitioner_profile = factories.PractitionerUserFactory().practitioner_profile
        practitioner_profile.verticals = []

        with pytest.raises(StateMatchNotPermissibleError) as e:
            state_match_not_permissible(
                practitioner_profile=practitioner_profile, user=user
            )
        assert (
            str(e.value)
            == StateMatchNotPermissibleMessage.PRACTITIONER_HAS_NO_VERTICALS
        )

    @pytest.mark.parametrize("flag_value", [False, True])
    def test_practitioner_is_filter_by_state_varied_certified_states(
        self, factories, states, ff_test_data, flag_value
    ):
        ff_test_data.update(
            ff_test_data.flag("relax-certified-state-check").variation_for_all(
                flag_value
            )
        )

        user = factories.EnterpriseUserFactory()
        practitioner_profile = factories.PractitionerUserFactory().practitioner_profile
        vertical = factories.VerticalFactory()
        vertical.filter_by_state = True
        practitioner_profile.verticals = [vertical]
        practitioner_profile.certified_states = []

        if not flag_value:  # If flag is False, the error should be raised
            with pytest.raises(StateMatchNotPermissibleError) as e:
                state_match_not_permissible(
                    practitioner_profile=practitioner_profile, user=user
                )
            assert (
                str(e.value)
                == StateMatchNotPermissibleMessage.VERTICAL_FILTER_BY_STATE_AND_NO_CERTIFIED_STATES
            )
        else:
            # If the flag is True, no error should be raised
            state_match_not_permissible(
                practitioner_profile=practitioner_profile, user=user
            )

    def test_user_has_no_state(self, factories):
        user = factories.EnterpriseUserFactory()
        assert user.member_profile.state is None

        practitioner_profile = factories.PractitionerUserFactory().practitioner_profile

        mpa_state_match_not_permissible = state_match_not_permissible(
            practitioner_profile=practitioner_profile, user=user
        )
        assert mpa_state_match_not_permissible is False

    def test_practitioners_vertical_filter_by_state_false(self, factories, states):
        user = factories.EnterpriseUserFactory()
        user.member_profile.state = states["NY"]

        practitioner_profile = factories.PractitionerUserFactory().practitioner_profile
        vertical = factories.VerticalFactory()
        vertical.filter_by_state = False
        practitioner_profile.verticals = [vertical]

        mpa_state_match_not_permissible = state_match_not_permissible(
            practitioner_profile=practitioner_profile, user=user
        )
        assert mpa_state_match_not_permissible is False

    def test_users_state_in_practitioner_certified_states(self, factories, states):
        user = factories.EnterpriseUserFactory()
        user.member_profile.state = states["NY"]

        practitioner_profile = factories.PractitionerUserFactory().practitioner_profile
        vertical = factories.VerticalFactory()
        vertical.filter_by_state = True
        practitioner_profile.verticals = [vertical]
        practitioner_profile.certified_states = [states["NY"], states["NJ"]]

        mpa_state_match_not_permissible = state_match_not_permissible(
            practitioner_profile=practitioner_profile, user=user
        )
        assert mpa_state_match_not_permissible is False

    def test_users_state_not_in_practitioners_vertical_in_state_matching_states(
        self, factories, states
    ):
        user = factories.EnterpriseUserFactory()
        user.member_profile.state = states["NY"]

        practitioner_profile = factories.PractitionerUserFactory().practitioner_profile
        vertical = factories.VerticalFactory()
        vertical.filter_by_state = True
        vertical.in_state_matching_states = [states["CA"]]
        practitioner_profile.verticals = [vertical]
        practitioner_profile.certified_states = [states["NJ"]]

        mpa_state_match_not_permissible = state_match_not_permissible(
            practitioner_profile=practitioner_profile, user=user
        )
        assert mpa_state_match_not_permissible is False

    def test_user_state_not_in_certified_states_but_in_practitioners_vertical_in_state_matching_states(
        self, factories, states
    ):
        user = factories.EnterpriseUserFactory()
        user.member_profile.state = states["NY"]

        practitioner_profile = factories.PractitionerUserFactory().practitioner_profile
        vertical = factories.VerticalFactory()
        vertical.filter_by_state = True
        vertical.in_state_matching_states = [states["NY"]]
        practitioner_profile.verticals = [vertical]
        practitioner_profile.certified_states = [states["NJ"]]

        mpa_state_match_not_permissible = state_match_not_permissible(
            practitioner_profile=practitioner_profile, user=user
        )
        assert mpa_state_match_not_permissible is True

    def test_state_match_not_permissible_called_with_product(self, factories, states):
        user = factories.EnterpriseUserFactory()
        user.member_profile.state = states["NY"]

        practitioner = factories.PractitionerUserFactory()
        practitioner_profile = practitioner.practitioner_profile

        vertical = factories.VerticalFactory()
        vertical.filter_by_state = True
        vertical.in_state_matching_states = [states["CA"]]

        product = factories.ProductFactory()
        product.practitioner = practitioner
        product.vertical = vertical

        mpa_state_match_not_permissible = state_match_not_permissible(
            practitioner_profile=practitioner_profile, user=user, product=product
        )
        assert mpa_state_match_not_permissible is False
