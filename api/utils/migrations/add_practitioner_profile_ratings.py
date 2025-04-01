from appointments.models.appointment import Appointment
from models.products import Product
from models.profiles import PractitionerProfile
from storage.connection import db


def init_practitioner_ratings():  # type: ignore[no-untyped-def] # Function is missing a return type annotation
    all_profiles = PractitionerProfile.query.all()
    print("Got %s practitioner profiles to init for rating" % len(all_profiles))

    for profile in all_profiles:
        rated_appts = (
            db.session.query(Appointment)
            .join(Product)
            .filter(
                Appointment.json.contains("ratings"), Product.user_id == profile.user_id
            )
            .all()
        )
        appt_ratings = [a.rating for a in rated_appts if a.rating]

        if appt_ratings:
            profile.rating = sum(appt_ratings) / len(appt_ratings)
            db.session.add(profile)
            db.session.commit()
            print("%s rating is updated to %s" % (profile, profile.rating))
