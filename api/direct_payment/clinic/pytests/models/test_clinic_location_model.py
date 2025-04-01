from direct_payment.clinic.models.clinic import FertilityClinicLocationContact
from direct_payment.clinic.pytests.factories import (
    FertilityClinicLocationContactFactory,
    FertilityClinicLocationFactory,
)
from storage.connection import db


def test_clinic_location_contact_relationship():
    fertility_clinic_location = FertilityClinicLocationFactory.create(name="location")
    FertilityClinicLocationContactFactory(
        name="person", fertility_clinic_location_id=fertility_clinic_location.id
    )

    assert len(fertility_clinic_location.contacts) == 1
    assert fertility_clinic_location.contacts[0].name == "person"

    db.session.delete(fertility_clinic_location)
    db.session.commit()

    remaining_contacts = db.session.query(FertilityClinicLocationContact).all()
    assert len(remaining_contacts) == 0
