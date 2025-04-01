from flask import jsonify

from common.services.api import PermissionedUserResource
from preferences import repository, service


class MemberPreferencesResource(PermissionedUserResource):
    def get(self, user_id):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        user = self._user_or_404(user_id)

        preference_repo = repository.PreferenceRepository()
        preference_service = service.PreferenceService()
        member_preferences_service = service.MemberPreferencesService()

        preferences = preference_repo.all()
        preferences_object = {}
        for pref in preferences:
            member_preference = member_preferences_service.get_by_preference_name(
                member_id=user.id, preference_name=pref.name
            )
            if member_preference:
                preferences_object[pref.name] = member_preferences_service.get_value(
                    id=member_preference.id
                )
            else:
                preferences_object[pref.name] = preference_service.get_value(id=pref.id)

        return jsonify(preferences_object)
