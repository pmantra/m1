from datetime import date
from unittest.mock import patch

import pytest
from sqlalchemy import func

from incentives.models.incentive import Incentive, IncentiveAction
from incentives.repository.incentive import IncentiveRepository
from models.tracks import TrackName
from storage.connection import db


class TestGet:
    def test_get__incentive_exists(self, factories):
        # Given an incentive that exists
        incentive = factories.IncentiveFactory.create()

        # When retrieving the incentive by its id
        retrieved_incentive = IncentiveRepository().get(id=incentive.id)

        # Then, we get the incentive
        assert incentive == retrieved_incentive

    def test_get__incentive_does_not_exist(self, factories):
        # Given an id of an incentive that does not exist
        max_incentive_id = db.session.query(func.max(Incentive.id)).first()[0]
        if max_incentive_id:
            fake_incentive_id = max_incentive_id + 1
        else:
            fake_incentive_id = 1

        # When retrieving the incentive by its id
        retrieved_incentive = IncentiveRepository().get(id=fake_incentive_id)

        # Then, we get no incentive
        assert not retrieved_incentive


class TestGetByParamsIncentive:
    def test_get_by_params__incentive_exists(self, user_and_incentive):
        # Given a user and an incentive configured for them
        user, incentive = user_and_incentive

        # When retrieving the incentive for the user
        user_id = user.id
        user_country_code = user.country_code
        user_org_id = user.current_member_track.client_track.organization.id
        incentivized_action = incentive.incentive_organizations[0].action
        track = incentive.incentive_organizations[0].track_name

        retrieved_incentive = IncentiveRepository().get_by_params(
            user_id=user_id,
            country_code=user_country_code,
            organization_id=user_org_id,
            incentivized_action=incentivized_action,
            track=track,
        )

        # Then, we get their incentive
        assert incentive == retrieved_incentive

    def test_get_by_params__two_tracks_two_incentives(
        self, user_and_incentive, factories
    ):
        # Given a user with two active tracks (default is pregnancy, will also add pnp)
        # and two incentives configured, one for each track
        user, pregnancy_incentive = user_and_incentive
        user_id = user.id
        user_org_id = user.current_member_track.client_track.organization.id
        user_country_code = user.member_profile.country_code
        user_org = user.current_member_track.client_track.organization
        incentivized_action = pregnancy_incentive.incentive_organizations[0].action
        pregnancy_track = pregnancy_incentive.incentive_organizations[0].track_name

        # and an additional track and additional incentive configured for that track
        pnp_track = factories.MemberTrackFactory(
            name=TrackName.PARENTING_AND_PEDIATRICS,
            user=user,
            client_track=factories.ClientTrackFactory(
                organization=user_org,
            ),
        )
        pnp_incentive = factories.IncentiveFactory.create()
        pnp_incentive_organization = factories.IncentiveOrganizationFactory.create(
            incentive=pnp_incentive,
            organization=user_org,
            action=incentivized_action,
            track_name=pnp_track.name,
        )
        factories.IncentiveOrganizationCountryFactory.create(
            incentive_organization=pnp_incentive_organization,
            country_code=user_country_code,
        )

        # When retrieving the incentive for the pregnancy track
        retrieved_pregnancy_incentive = IncentiveRepository().get_by_params(
            user_id=user_id,
            country_code=user_country_code,
            organization_id=user_org_id,
            incentivized_action=incentivized_action,
            track=pregnancy_track,
        )

        # Then, we get the pregnancy_incentive
        assert pregnancy_incentive == retrieved_pregnancy_incentive

        # When retrieving the incentive for the pnp track
        retrieved_pnp_incentive = IncentiveRepository().get_by_params(
            user_id=user_id,
            country_code=user_country_code,
            organization_id=user_org_id,
            incentivized_action=incentivized_action,
            track=pnp_track.name,
        )

        # Then, we get the pregnancy_incentive
        assert pnp_incentive == retrieved_pnp_incentive

    @patch("incentives.repository.incentive.log.warning")
    def test_get_by_params__two_incentives_for_one_track(
        self, mock_log_warn, user_and_incentive, factories
    ):
        # Given a user and an incentive configured for them
        user, pregnancy_incentive_1 = user_and_incentive
        user_id = user.id
        user_org_id = user.current_member_track.client_track.organization.id
        user_country_code = user.member_profile.country_code
        user_org = user.current_member_track.client_track.organization
        incentivized_action = pregnancy_incentive_1.incentive_organizations[0].action

        jan_1st_this_year = date(year=date.today().year, month=1, day=1)
        pregnancy_incentive_1.incentive_organizations[0].created_at = jan_1st_this_year

        pregnancy_track = user.current_member_track

        # and a second incentive configured for the same track
        pregnancy_incentive_2 = factories.IncentiveFactory.create()
        pregnancy_incentive_organization_2 = (
            factories.IncentiveOrganizationFactory.create(
                incentive=pregnancy_incentive_2,
                organization=user_org,
                action=incentivized_action,
                track_name=pregnancy_track.name,
            )
        )
        factories.IncentiveOrganizationCountryFactory.create(
            incentive_organization=pregnancy_incentive_organization_2,
            country_code=user_country_code,
        )
        jan_2nd_this_year = date(year=date.today().year, month=1, day=2)
        pregnancy_incentive_organization_2.created_at = jan_2nd_this_year

        # When retrieving the incentive for the user
        retrieved_incentive = IncentiveRepository().get_by_params(
            user_id=user_id,
            country_code=user_country_code,
            organization_id=user_org_id,
            incentivized_action=incentivized_action,
            track=pregnancy_track.name,
        )

        # Then, the log alert is raised
        mock_log_warn.assert_called_once()
        assert (
            mock_log_warn.call_args[0][0]
            == "More than one active incentive configured for user"
        )
        assert mock_log_warn.call_args[1]["user_id"] == user_id
        assert mock_log_warn.call_args[1]["country_code"] == user_country_code
        assert mock_log_warn.call_args[1]["organization_id"] == user_org.id
        assert mock_log_warn.call_args[1]["incentivized_action"] == incentivized_action
        assert mock_log_warn.call_args[1]["track"] == pregnancy_track.name
        assert sorted(mock_log_warn.call_args[1]["incentives"]) == sorted(
            [pregnancy_incentive_1.id, pregnancy_incentive_2.id]
        )

        # Then, we get the pregnancy incentive most recently created
        assert retrieved_incentive == pregnancy_incentive_2

    @pytest.mark.parametrize(
        argnames="entity_that_doesnt_exist",
        argvalues=[
            "incentive",
            "incentive_organization",
            "incentive_organization_country",
        ],
    )
    def test_get_by_params__incentive_doesnt_exist(
        self, entity_that_doesnt_exist, incentive_user, factories
    ):
        # Given a user and incentive not fully configured
        user_id = incentive_user.id
        user_country_code = incentive_user.country_code
        user_org_id = incentive_user.organization_employee.organization_id
        user_org = incentive_user.organization_employee.organization
        user_track = incentive_user.current_member_track.name
        incentivized_action = IncentiveAction.CA_INTRO

        if entity_that_doesnt_exist == "incentive":
            pass  # Do nothing

        if (
            entity_that_doesnt_exist == "incentive_organization"
        ):  # only create incentive
            factories.IncentiveFactory.create()

        if (
            entity_that_doesnt_exist == "incentive_organization_country"
        ):  # only create incentive and incentive_organization, but not incentive_organization_country
            incentive = factories.IncentiveFactory.create()
            factories.IncentiveOrganizationFactory.create(
                incentive=incentive,
                organization=user_org,
                action=incentivized_action,
                track_name=user_track,
            )

        # When retrieving the incentive for the user
        retrieved_incentive = IncentiveRepository().get_by_params(
            user_id=user_id,
            country_code=user_country_code,
            organization_id=user_org_id,
            incentivized_action=incentivized_action,
            track=user_track,
        )

        # Then, we dont get an incentive
        assert not retrieved_incentive

    @pytest.mark.parametrize(
        argnames="different_param",
        argvalues=["country_code", "organization", "track", "incentivized_action"],
    )
    def test_get_by_params__incentive_exist_but_not_for_user(
        self, different_param, user_and_incentive, factories
    ):
        # Given a user and an incentive configured with the same params as the user's, except one
        user, incentive = user_and_incentive
        user_id = user.id
        user_country_code = user.country_code
        user_org_id = user.organization_employee.organization_id
        user_track = user.current_member_track.name
        incentivized_action = incentive.incentive_organizations[0].action

        # Change one of the incentive's param to be different to the user fields
        if different_param == "country_code":
            incentive.incentive_organizations[0].countries[
                0
            ].country_code = "IR"  # default is US
        elif different_param == "organization":
            incentive.incentive_organizations[
                0
            ].organization = (
                factories.OrganizationFactory()
            )  # just a different org to the user's
        elif different_param == "track":
            incentive.incentive_organizations[
                0
            ].track_name = "adoption"  # default is pregnancy
        elif different_param == "incentivized_action":
            incentive.incentive_organizations[
                0
            ].action = IncentiveAction.OFFBOARDING_ASSESSMENT  # default is ca_intro

        # When retrieving the incentive for the user
        retrieved_incentive = IncentiveRepository().get_by_params(
            user_id=user_id,
            country_code=user_country_code,
            organization_id=user_org_id,
            incentivized_action=incentivized_action,
            track=user_track,
        )

        # Then, we dont get an incentive
        assert not retrieved_incentive

    def test_get_by_params__incentive_exist_but_inactive(
        self, user_and_incentive, factories
    ):
        # Given a user and an incentive configured for them, but inactive
        user, incentive = user_and_incentive
        user_id = user.id
        user_country_code = user.country_code
        user_org_id = user.organization_employee.organization_id
        user_track = user.current_member_track.name

        incentivized_action = incentive.incentive_organizations[0].action

        incentive.incentive_organizations[0].active = False

        # When retrieving the incentive for the user
        retrieved_incentive = IncentiveRepository().get_by_params(
            user_id=user_id,
            country_code=user_country_code,
            organization_id=user_org_id,
            incentivized_action=incentivized_action,
            track=user_track,
        )

        # Then, we dont get an incentive
        assert not retrieved_incentive
