import datetime

from appointments.services.schedule import update_practitioner_profile_next_availability
from appointments.utils.booking import AvailabilityCalculator
from models.products import Product


class TestBookingFlow:
    def test_30m_and_60m_timeslots(self, factories, db):
        factories.VerticalFactory.create(
            products=[{"minutes": 30, "price": 60}, {"minutes": 60, "price": 120}]
        )
        practitioner = factories.PractitionerUserFactory.create()
        thirty_m_product = Product.query.filter(Product.minutes == 30).first()
        db.session.add(thirty_m_product)
        db.session.commit()
        sixty_m_product = Product.query.filter(Product.minutes == 60).first()

        # create 30m time slot in the future
        now = datetime.datetime.utcnow().replace(microsecond=0)
        thirty_m_start = now + datetime.timedelta(minutes=30)
        factories.ScheduleEventFactory.create(
            schedule=practitioner.schedule,
            starts_at=thirty_m_start,
            ends_at=now + datetime.timedelta(hours=1),
        )
        # create 60m time slot in the future
        sixty_m_start = now + datetime.timedelta(hours=2)
        factories.ScheduleEventFactory.create(
            schedule=practitioner.schedule,
            starts_at=sixty_m_start,
            ends_at=now + datetime.timedelta(hours=3),
        )

        # get next availability
        update_practitioner_profile_next_availability(practitioner.practitioner_profile)
        next_availability = practitioner.practitioner_profile.next_availability
        assert thirty_m_start == next_availability

        # get next availability for the 60m product
        calculator = AvailabilityCalculator(practitioner.profile, sixty_m_product)
        availability = calculator.get_availability(
            start_time=now, end_time=now + datetime.timedelta(hours=5), limit=1
        ).pop()
        assert sixty_m_start == availability.scheduled_start

        assert next_availability != availability.scheduled_start
