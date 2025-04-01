from models.tracks import TrackName
from providers.models.need import Need
from providers.service.need import NeedService
from providers.service.promoted_needs.needs_configurations.config import (
    configuration as Configuration,
)


class TestNeedService:
    def test_need_service__get_needs_by_member__no_needs(self, factories, default_user):
        factories.MemberTrackFactory.create(user=default_user, name=TrackName.SURROGACY)

        # returns no needs since no needs exist in the DB in this test
        assert NeedService().get_needs_by_member(default_user) == []

    def test_need_service__get_needs_by_member__has_needs(
        self, factories, default_user
    ):
        target_track = TrackName.MENOPAUSE
        factories.MemberTrackFactory.create(user=default_user, name=target_track)

        # need 1
        slug1 = Configuration.get("data").get(target_track)[0]
        name1 = "Goats"
        description1 = "The best goats you'll e'er see"
        factories.NeedFactory.create(
            id=1, name=name1, description=description1, slug=slug1
        )

        # need 2
        slug2 = Configuration.get("data").get(target_track)[1]
        name2 = "Reindeer"
        description2 = "The smartest reindeer you ever did see"
        factories.NeedFactory.create(
            id=2, name=name2, description=description2, slug=slug2
        )

        # then assert that the correct need is returned
        assert NeedService().get_needs_by_member(default_user) == [
            Need(
                id=1,
                name=name1,
                description=description1,
                slug=slug1,
                display_order=1,
            ),
            Need(
                id=2,
                name=name2,
                description=description2,
                slug=slug2,
                display_order=2,
            ),
        ]

    def test_need_service__get_need_slugs_by_member__pregnancy_ids(
        self, default_user, factories
    ):
        target_track = TrackName.PREGNANCY
        factories.MemberTrackFactory.create(user=default_user, name=target_track)
        pregnancy_need_slugs = NeedService().get_need_slugs_by_member(default_user)

        # check that the need ids returned are the same as the data in the config file for Pregnancy track
        assert pregnancy_need_slugs == Configuration.get("data").get(target_track)

    def test_sort_needs_by_need_slug_order__confirm_sort(self):
        needs = [
            Need(
                id=100, name="Need 1", slug="need-1", description="Need 1 description"
            ),
            Need(id=2, name="Need 2", slug="need-2", description="Need 2 description"),
            Need(id=78, name="Need 3", slug="need-3", description="Need 3 description"),
        ]

        need_slug_order = ["need-1", "need-2", "need-3"]

        sorted_needs = NeedService().sort_needs_by_need_slug_order(
            needs=needs, need_slugs=need_slug_order
        )

        assert sorted_needs[0].slug == need_slug_order[0]
        assert sorted_needs[1].slug == need_slug_order[1]
        assert sorted_needs[2].slug == need_slug_order[2]
