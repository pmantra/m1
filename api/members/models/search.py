from models.profiles import MemberProfile
from tracks import TrackSelectionService


# Member Search uses a model for its search results because the MemberProfile model
# recalculates many of its properties using database calls on every access and the
# Member Search references these limited properties several times.
class MemberSearchResult:
    def __init__(self, member_profile: MemberProfile):
        self.id = member_profile.user_id
        self.first_name = member_profile.first_name
        self.last_name = member_profile.last_name
        self.email = member_profile.email
        self.care_coordinators = member_profile.care_coordinators

        track_svc = TrackSelectionService()
        self.organization = track_svc.get_organization_for_user(
            user_id=member_profile.user_id
        )
