from incentives.models.incentive import IncentiveAction, IncentiveType
from incentives.repository.incentive_organization import IncentiveOrganizationRepository
from models.tracks.track import TrackName


class TestGetOffboardingIncentivesForOrg:
    def test_get_offboarding_incentives_for_org(
        self, create_incentive_org, incentive_user, default_organization, factories
    ):
        # given 3 incentive-orgs that should fall into the query
        member = (
            incentive_user.current_member_track.client_track.organization
        ) = default_organization
        incentive_org_1 = create_incentive_org(
            incentive_user=member,
            incentive_type=IncentiveType.GIFT_CARD,
            incentive_action=IncentiveAction.OFFBOARDING_ASSESSMENT,
            track=TrackName.PREGNANCY,
        )
        incentive_org_2 = create_incentive_org(
            incentive_user=member,
            incentive_type=IncentiveType.GIFT_CARD,
            incentive_action=IncentiveAction.OFFBOARDING_ASSESSMENT,
            track=TrackName.EGG_FREEZING,
        )
        incentive_org_3 = create_incentive_org(
            incentive_user=member,
            incentive_type=IncentiveType.GIFT_CARD,
            incentive_action=IncentiveAction.OFFBOARDING_ASSESSMENT,
            track=TrackName.POSTPARTUM,
        )
        # and 3 incentive-orgs that should not fall into the query
        # wrong action
        create_incentive_org(
            incentive_type=IncentiveType.GIFT_CARD,
            incentive_action=IncentiveAction.CA_INTRO,
            track=TrackName.PREGNANCY,
        )
        # wrong org
        incentive_org_4 = create_incentive_org(
            incentive_type=IncentiveType.GIFT_CARD,
            incentive_action=IncentiveAction.CA_INTRO,
            track=TrackName.PREGNANCY,
        )
        incentive_org_4.organization = factories.OrganizationFactory()
        # inactive
        incentive_org_5 = create_incentive_org(
            incentive_type=IncentiveType.GIFT_CARD,
            incentive_action=IncentiveAction.CA_INTRO,
            track=TrackName.PREGNANCY,
        )
        incentive_org_5.active = False

        expected_result = [
            (
                incentive_org_1.id,
                default_organization.id,
                incentive_org_1.incentive_id,
                TrackName.PREGNANCY.value,
                "US",
            ),
            (
                incentive_org_2.id,
                default_organization.id,
                incentive_org_2.incentive_id,
                TrackName.EGG_FREEZING.value,
                "US",
            ),
            (
                incentive_org_3.id,
                default_organization.id,
                incentive_org_3.incentive_id,
                TrackName.POSTPARTUM.value,
                "US",
            ),
        ]

        # when we call get_offboarding_incentive_orgs_for_org
        incentive_orgs = (
            IncentiveOrganizationRepository().get_offboarding_incentive_orgs_for_org(
                organization_id=default_organization.id
            )
        )

        # then we exclude the incentive-org from the different action
        assert set(expected_result) == set(incentive_orgs)


class TestGetOrgUsersWithPotentialOffboardingIncentives:
    def test_get_org_users_with_potential_offboarding_incentives(
        self, incentive_users, factories
    ):
        # Given 2 users in an org with incentive tracks and one without an incentive track
        # pregnancy, postpartum, menopause
        user_1, user_2, user_3 = incentive_users

        # and a user outside of the org
        factories.EnterpriseUserFactory.create(tracks__name=TrackName.PREGNANCY)

        expected_result = [user_1, user_2]

        # when we call get_org_users_with_potential_offboarding_incentives
        incentive_tracks = [TrackName.PREGNANCY.name, TrackName.POSTPARTUM.name]
        returned_users = IncentiveOrganizationRepository().get_org_users_with_potential_offboarding_incentives(
            user_1.organization_v2.id, incentive_tracks
        )

        # then we return only the users with the correct org and track
        assert set(expected_result) == set(returned_users)
