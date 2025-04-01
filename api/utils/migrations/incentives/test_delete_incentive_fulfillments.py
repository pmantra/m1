from incentives.models.incentive import IncentiveAction
from incentives.repository.incentive_fulfillment import IncentiveFulfillmentRepository
from utils.migrations.incentives.delete_incentive_fulfillments import (
    delete_incentive_fulfillments_wrapper,
)


def test_delete_incentive_fulfillments(factories):  # type: ignore[no-untyped-def] # Function is missing a type annotation
    # create user
    incentive_user = factories.UserOrganizationEmployeeFactory().user
    incentive_user.member_profile.country_code = "US"

    # create incentive and incentive organization
    incentive_country_code = incentive_user.member_profile.country_code
    incentive_org = incentive_user.organization_employee.organization
    incentive_track = incentive_user.current_member_track.name
    incentive_action = IncentiveAction.CA_INTRO

    incentive = factories.IncentiveFactory.create()
    incentive_organization = factories.IncentiveOrganizationFactory.create(
        incentive=incentive,
        organization=incentive_org,
        action=incentive_action,
        track_name=incentive_track,
    )
    factories.IncentiveOrganizationCountryFactory.create(
        incentive_organization=incentive_organization,
        country_code=incentive_country_code,
    )
    incentivized_action = incentive.incentive_organizations[0].action

    # create fulfillment
    incentive_fulfillment = factories.IncentiveFulfillmentFactory.create(
        member_track=incentive_user.current_member_track,
        incentive=incentive,
        incentivized_action=incentivized_action,
    )

    # assert we can find the incentive, then
    incentive_fulfillments_before = IncentiveFulfillmentRepository().get_all_by_params(
        track=incentive_track, action=incentivized_action
    )
    assert len(incentive_fulfillments_before) == 1
    assert incentive_fulfillments_before[0].id == incentive_fulfillment.id

    # delete the incentive fulfillment, then
    delete_incentive_fulfillments_wrapper(
        track=incentive_track, action=incentivized_action, dry_run=False
    )

    # assert it isn't there anymore
    incentive_fulfillments_after = IncentiveFulfillmentRepository().get_all_by_params(
        track=incentive_track, action=incentivized_action
    )
    assert len(incentive_fulfillments_after) == 0
