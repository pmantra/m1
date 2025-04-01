import datetime
from datetime import date

import pytest

from incentives.models.incentive_fulfillment import IncentiveStatus
from incentives.repository.incentive_fulfillment import IncentiveFulfillmentRepository


class TestCreate:
    @pytest.mark.parametrize(
        argnames="status",
        argvalues=[
            IncentiveStatus.SEEN,
            IncentiveStatus.EARNED,
        ],
    )
    def test_create__successful(self, status, user_and_incentive):
        # Given valid params to create an incentive fulfillment
        user, incentive = user_and_incentive
        incentive_id = incentive.id
        member_track_id = user.current_member_track.id
        incentivized_action = incentive.incentive_organizations[0].action
        date_status_changed = date.today()

        # When trying to create one
        incentive_fulfillment = IncentiveFulfillmentRepository().create(
            incentive_id=incentive_id,
            member_track_id=member_track_id,
            incentivized_action=incentivized_action,
            date_status_changed=date_status_changed,
            status=status,
        )

        # Then, we were able to create an incentive fulfillment, and the correct status and date fields are populated
        assert incentive_fulfillment
        assert incentive_fulfillment.status == status
        if status == IncentiveStatus.SEEN:
            assert incentive_fulfillment.date_seen == date_status_changed
        elif status == IncentiveStatus.EARNED:
            assert incentive_fulfillment.date_earned == date_status_changed
        elif status == IncentiveStatus.FULFILLED:
            assert incentive_fulfillment.date_issued == date_status_changed
        elif status == IncentiveStatus.PROCESSING:
            pass  # No date field needed to check

    @pytest.mark.parametrize(
        argnames="status",
        argvalues=[
            IncentiveStatus.PROCESSING,
            IncentiveStatus.FULFILLED,
            "a_random_status",
        ],
    )
    def test_create__unsuccessful(self, status, user_and_incentive):
        # Given invalid params to create an incentive fulfillment
        user, incentive = user_and_incentive
        incentive_id = incentive.id
        member_track_id = user.current_member_track.id
        incentivized_action = incentive.incentive_organizations[0].action
        date_status_changed = date.today()

        # When trying to create one
        incentive_fulfillment = IncentiveFulfillmentRepository().create(
            incentive_id=incentive_id,
            member_track_id=member_track_id,
            incentivized_action=incentivized_action,
            date_status_changed=date_status_changed,
            status=status,
        )

        # Then, we were not able to create an incentive fulfillment
        assert not incentive_fulfillment


class TestGetByParams:
    def test_get_by_params__incentive_fulfillment_exists(
        self, factories, user_and_incentive
    ):
        # Given an incentive fulfillment exists
        user, incentive = user_and_incentive
        member_track_id = user.current_member_track.id
        incentivized_action = incentive.incentive_organizations[0].action

        incentive_fulfillment = factories.IncentiveFulfillmentFactory.create(
            member_track=user.current_member_track,
            incentive=incentive,
            incentivized_action=incentivized_action,
        )

        # When retrieving the incentive fulfillment
        retrieved_incentive_fulfillment = (
            IncentiveFulfillmentRepository().get_by_params(
                member_track_id=member_track_id,
                incentivized_action=incentivized_action,
            )
        )

        # Then, we were able to get the incentive fulfillment
        assert incentive_fulfillment == retrieved_incentive_fulfillment

    def test_get_by_params__incentive_fulfillment_does_not_exist(
        self, user_and_incentive
    ):
        # Given no incentive fulfillment exists
        user, incentive = user_and_incentive
        member_track_id = user.current_member_track.id
        incentivized_action = incentive.incentive_organizations[0].action

        # When retrieving the incentive fulfillment
        retrieved_incentive_fulfillment = (
            IncentiveFulfillmentRepository().get_by_params(
                member_track_id=member_track_id,
                incentivized_action=incentivized_action,
            )
        )

        # Then, we are not able to get the incentive fulfillment
        assert not retrieved_incentive_fulfillment


class TestSetStatus:
    def test_set_status__successful(self, incentive_fulfillment):

        # Given an incentive fulfillment exists with status Seen
        incentive_fulfillment.status = IncentiveStatus.SEEN

        # When we update it to EARNED
        now = datetime.datetime.utcnow()
        IncentiveFulfillmentRepository().set_status(
            incentive_fulfillment, IncentiveStatus.EARNED, now
        )

        # Then the incentive_fulfillment status is updated
        assert incentive_fulfillment.status == IncentiveStatus.EARNED
        assert incentive_fulfillment.date_earned == now


class TestGetIncentiveFulfillments:
    def test_get_incentive_fulfillments__one_fulfillment(
        self, user_and_incentive, factories
    ):
        user, incentive = user_and_incentive
        incentivized_action = incentive.incentive_organizations[0].action

        incentive_fulfillment = factories.IncentiveFulfillmentFactory.create(
            member_track=user.current_member_track,
            incentive=incentive,
            incentivized_action=incentivized_action,
        )

        records = IncentiveFulfillmentRepository().get_all_by_ids(
            [incentive_fulfillment.id]
        )

        assert len(records) == 1
        assert records[0].id == incentive_fulfillment.id


class TestGetAllIncentiveFulfillments:
    def test_get_all_by_params__has_fulfillments(self, user_and_incentive, factories):
        user, incentive = user_and_incentive
        incentivized_action = incentive.incentive_organizations[0].action

        incentive_fulfillment = factories.IncentiveFulfillmentFactory.create(
            member_track=user.current_member_track,
            incentive=incentive,
            incentivized_action=incentivized_action,
        )

        incentive_fulfillments_and_esp_ids = (
            IncentiveFulfillmentRepository().get_all_by_params(
                track=user.current_member_track.name, action=incentivized_action
            )
        )

        assert len(incentive_fulfillments_and_esp_ids) == 1
        (inc_ful, _) = incentive_fulfillments_and_esp_ids[0]
        assert inc_ful.id == incentive_fulfillment.id
