from providers.repository.need import NeedRepository
from storage import connection


class TestNeedRepository:
    def test_get_need_by_slugs__no_slugs(self):
        random_slug = "zxcvb"
        assert (
            NeedRepository(session=connection.db.session).get_needs_by_slugs(
                need_slugs=[random_slug]
            )
            == []
        )

    def test_get_need_by_slugs__has_needs(self, factories):
        need1 = factories.NeedFactory.create(slug="slug-1")
        need2 = factories.NeedFactory.create(slug="slug-2")
        need3 = factories.NeedFactory.create(slug="slug-3")

        need_slugs = [need1.slug, need2.slug, need3.slug]
        needs_queried = NeedRepository(
            session=connection.db.session
        ).get_needs_by_slugs(need_slugs=need_slugs)

        assert needs_queried[0].slug in need_slugs
        assert needs_queried[1].slug in need_slugs
        assert needs_queried[2].slug in need_slugs
