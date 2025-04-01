from incentives.models.incentive import IncentiveAction
from models.tracks import TrackName
from utils.migrations.incentives.mark_incentive_org_as_inactive import (
    mark_incentive_org_as_inactive_wrapper,
)


def test_mark_incentive_org_as_inactive(factories):  # type: ignore[no-untyped-def] # Function is missing a type annotation
    incentive_organization = factories.IncentiveOrganizationFactory.create(
        action=IncentiveAction.CA_INTRO,
        track_name=TrackName.ADOPTION,
    )

    mark_incentive_org_as_inactive_wrapper(TrackName.ADOPTION, "CA Intro", False)  # type: ignore[arg-type] # Argument 2 to "mark_incentive_org_as_inactive_wrapper" has incompatible type "str"; expected "IncentiveAction"

    assert incentive_organization.active == False
