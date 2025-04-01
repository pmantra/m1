from models.tracks import TrackName
from providers.service.promoted_needs.get_needs_config import (
    get_member_active_track_name,
)
from providers.service.promoted_needs.needs_configurations.constants import (
    MARKETPLACE_MEMBER,
)


class TestPromotedNeeds:
    def test_get_active_track_name__one_track(self, factories, default_user):
        factories.MemberTrackFactory.create(
            user=default_user, name=TrackName.POSTPARTUM
        )

        assert get_member_active_track_name(default_user) == TrackName.POSTPARTUM

    def test_get_active_track_name__multi_track_with_pnp(self, factories, default_user):
        factories.MemberTrackFactory.create(user=default_user, name=TrackName.FERTILITY)
        factories.MemberTrackFactory.create(
            user=default_user, name=TrackName.PARENTING_AND_PEDIATRICS
        )

        # if multitrack, return the non p&p track
        assert get_member_active_track_name(default_user) == TrackName.FERTILITY

    def test_get_active_track_name__marketplace(self, default_user):
        assert get_member_active_track_name(default_user) == MARKETPLACE_MEMBER
