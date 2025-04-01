from incentives.models.incentive import IncentiveAction, IncentiveType
from incentives.repository.incentive_organization import IncentiveOrganizationRepository
from models.tracks import TrackName
from utils.migrations.incentives.create_gift_card_incentive_organizations import (
    add_gift_card_incentive_org_wrapper,
)


def test_create_gift_card_incentive_organizations(  # type: ignore[no-untyped-def] # Function is missing a type annotation
    factories,
):
    factories.IncentiveFactory.create(
        type=IncentiveType.GIFT_CARD, name="$20 Amazon Gift Card"
    )
    org = factories.OrganizationFactory.create(
        name="Court Street Grocers", gift_card_allowed=True
    )

    add_gift_card_incentive_org_wrapper(
        TrackName.ADOPTION, "CA Intro", "$20 Amazon Gift Card", False  # type: ignore[arg-type] # Argument 2 to "add_gift_card_incentive_org_wrapper" has incompatible type "str"; expected "IncentiveAction"
    )

    # assert incentive organization is created
    incentive_orgs = IncentiveOrganizationRepository().get_incentive_orgs_by_track_action_and_active_status(
        track_name=TrackName.ADOPTION, action=IncentiveAction.CA_INTRO, is_active=True  # type: ignore[arg-type] # Argument "action" to "get_incentive_orgs_by_track_action_and_active_status" of "IncentiveOrganizationRepository" has incompatible type "IncentiveAction"; expected "str"
    )
    assert len(incentive_orgs) == 1
    assert incentive_orgs[0].organization_id == org.id
