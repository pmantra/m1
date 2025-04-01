from marshmallow_v1 import ValidationError

from appointments.models.practitioner_appointment import PractitionerAppointmentAck
from models.phone import BlockedPhoneNumber
from models.profiles import MemberProfile, PractitionerProfile
from storage.connection import db
from utils.data import normalize_phone_number


def normalize():  # type: ignore[no-untyped-def] # Function is missing a return type annotation

    pps = PractitionerProfile.query.all()
    mps = MemberProfile.query.all()
    bps = BlockedPhoneNumber.query.all()
    pas = PractitionerAppointmentAck.query.all()
    print(f"Got {len(pps)} practitioner profiles to normalize.")
    print(f"Got {len(mps)} member profiles to normalize.")
    print(f"Got {len(bps)} blocked phone numbers to normalize.")
    print(f"Got {len(pas)} practitioner appointment acks to normalize.")

    for pp in pps:
        if pp.phone_number == "":
            continue
        try:
            # rely on model validation function to normalize
            pp.phone_number = pp.phone_number
            db.session.add(pp)
            db.session.commit()
        except ValidationError as e:
            print(
                "Could not normalize practitioner profile (user: {}) phone number ({}): {}".format(
                    pp.user_id, pp.phone_number, e
                )
            )

    for mp in mps:
        if mp.phone_number == "":
            continue
        try:
            # rely on model validation function to normalize
            mp.phone_number = mp.phone_number
            db.session.add(mp)
            db.session.commit()
        except ValidationError as e:
            print(
                "Could not normalize member profile (user: {}) phone number ({}): {}".format(
                    mp.user_id, mp.phone_number, e
                )
            )

    for bp in bps:
        try:
            bp.digits, _ = normalize_phone_number(bp.digits, None)
            db.session.add(bp)
            db.session.commit()
        except ValidationError as e:
            print(f"Could not normalize blocked phone number ({bp.digits}): {e}")

    for pa in pas:
        if pa.phone_number == "":
            continue
        try:
            # rely on model validation function to normalize
            pa.phone_number = pa.phone_number
            db.session.add(pa)
            db.session.commit()
        except ValidationError as e:
            print(
                "Could not normalize practitioner appointment ack ({}) phone number ({}): {}".format(
                    pa.id, pa.phone_number, e
                )
            )

    print("All set.")
