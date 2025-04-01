import datetime

from admin.views.models.users import PractitionerAvailabilityFilter
from models.profiles import PractitionerProfile


class TestAdminPractitionerAvailabilityFilter:
    def test_filter_practitioner_availability(self, factories, db):
        practitioner = factories.PractitionerUserFactory.create()
        assert len(self._query_by_availability(db, 120)) == 0

        starts_at = datetime.datetime.utcnow() - datetime.timedelta(days=70)
        ends_at = starts_at + datetime.timedelta(hours=8)

        factories.ScheduleEventFactory.create(
            starts_at=starts_at, ends_at=ends_at, schedule=practitioner.schedule
        )

        assert len(self._query_by_availability(db, 120)) == 1
        assert len(self._query_by_availability(db, 60)) == 0

    @staticmethod
    def _query_by_availability(db, in_past_days):
        return (
            PractitionerAvailabilityFilter(None, None)
            .apply(db.session.query(PractitionerProfile), in_past_days)
            .all()
        )
