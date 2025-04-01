from models.profiles import MemberProfile
from storage.connection import db


class PharmacyInfo:
    """Queries and retrieves the user's pharmacy information."""

    @classmethod
    def get_pharmacy_info_by_user_id(cls, user_id):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        member = (
            db.session.query(MemberProfile)
            .filter(MemberProfile.user_id == user_id)
            .one()
        )
        return member.get_prescription_info().get("pharmacy_info")
