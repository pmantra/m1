from typing import List, Tuple

from sqlalchemy.orm import Load, joinedload

from models.profiles import MemberPractitionerAssociation, PractitionerProfile
from storage.connection import db


class CareTeam:
    """Queries and retrieves the user's care team."""

    @classmethod
    def get_care_team_by_user_id(  # type: ignore[no-untyped-def] # Function is missing a type annotation for one or more arguments
        cls, user_id
    ) -> List[Tuple[PractitionerProfile, MemberPractitionerAssociation]]:
        care_team = (
            db.session.query(PractitionerProfile, MemberPractitionerAssociation)
            .options(
                Load(PractitionerProfile).load_only(  # type: ignore[attr-defined] # "Load" has no attribute "load_only"
                    PractitionerProfile.first_name,
                    PractitionerProfile.last_name,
                    PractitionerProfile.user_id,
                ),
                Load(MemberPractitionerAssociation).load_only(  # type: ignore[attr-defined] # "Load" has no attribute "load_only"
                    MemberPractitionerAssociation.type
                ),
            )
            .options(joinedload(PractitionerProfile.verticals))
            .join(MemberPractitionerAssociation)
            .filter(MemberPractitionerAssociation.user_id == user_id)
            .all()
        )

        return care_team
