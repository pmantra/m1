import ddtrace

import preferences


@ddtrace.tracer.wrap()
def get_opted_in_email_communications_preference():  # type: ignore[no-untyped-def] # Function is missing a return type annotation
    """
    Retrieves the Preference for email communications, creating one if it does not already exist
    """
    preference_service = preferences.service.PreferenceService()  # type: ignore[attr-defined] # Module has no attribute "PreferenceService"
    opt_in_email_pref = preference_service.get_by_name(
        name="opted_in_email_communications"
    )
    if not opt_in_email_pref:
        opt_in_email_pref = preference_service.create(
            name="opted_in_email_communications",
            default_value="false",
            type="bool",
        )
    return opt_in_email_pref


@ddtrace.tracer.wrap()
def get_member_communications_preference(user_id: int) -> bool:
    """
    Gets the MemberPreference for email communications for the given user, defaulting to False
    """
    member_preferences_service = preferences.service.MemberPreferencesService()  # type: ignore[attr-defined] # Module has no attribute "MemberPreferencesService"
    opt_in_email_pref = get_opted_in_email_communications_preference()
    existing_member_pref = member_preferences_service.get_by_preference_name(
        member_id=user_id,
        preference_name=opt_in_email_pref.name,
    )

    if existing_member_pref:
        existing_value = member_preferences_service.get_value(
            id=existing_member_pref.id
        )
        if existing_value:
            return existing_value

    return False


@ddtrace.tracer.wrap()
def set_member_communications_preference(user_id: int, opted_in: bool):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
    """
    Sets the MemberPreference for email communications for the given user
    """
    member_preferences_service = preferences.service.MemberPreferencesService()  # type: ignore[attr-defined] # Module has no attribute "MemberPreferencesService"

    opt_in_email_pref = get_opted_in_email_communications_preference()

    existing_member_pref = member_preferences_service.get_by_preference_name(
        member_id=user_id,
        preference_name=opt_in_email_pref.name,
    )

    if existing_member_pref:
        existing_value = member_preferences_service.get_value(
            id=existing_member_pref.id
        )
        if existing_value != opted_in:
            member_preferences_service.update_value(
                id=existing_member_pref.id,
                value=str(opted_in),
            )
    else:
        member_preferences_service.create(
            member_id=user_id,
            preference_id=opt_in_email_pref.id,
            value=str(opted_in),
        )
