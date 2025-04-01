from models import virtual_events


def test_get_valid_virtual_events_for_track_registrations(factories):
    user = factories.EnterpriseUserFactory(tracks__name="fertility")
    category = factories.VirtualEventCategoryFactory(name="fertility-101")
    factories.VirtualEventCategoryTrackFactory(
        category=category, track_name="fertility"
    )

    # Creating an event with 4 registrations, including our user
    event = factories.VirtualEventFactory(virtual_event_category=category)
    factories.VirtualEventUserRegistrationFactory(
        virtual_event_id=event.id, user_id=user.id
    )
    factories.VirtualEventUserRegistrationFactory(
        virtual_event_id=event.id, user_id=factories.EnterpriseUserFactory().id
    )
    factories.VirtualEventUserRegistrationFactory(
        virtual_event_id=event.id, user_id=factories.EnterpriseUserFactory().id
    )
    factories.VirtualEventUserRegistrationFactory(
        virtual_event_id=event.id, user_id=factories.EnterpriseUserFactory().id
    )

    # Creating an event with no registrations
    factories.VirtualEventFactory(virtual_event_category=category)

    events = virtual_events.get_valid_virtual_events_for_track(
        track=user.active_tracks[0], user_id=user.id
    )
    # Ensure we're getting all events, not just ones our user is registered for
    assert len(events) == 2
    # Ensure we're not loading everyone's registrations, because we only want
    # to know if our user is registered
    assert len(events[0].user_registrations) == 1
    # Ensure the registration is attached to the right event
    assert len(events[1].user_registrations) == 0


def test_get_virtual_event_with_registration_for_one_user(factories):
    user = factories.EnterpriseUserFactory()
    event = factories.VirtualEventFactory()
    # Registration for our user
    factories.VirtualEventUserRegistrationFactory(
        virtual_event_id=event.id, user_id=user.id
    )
    # Registration for some other user
    factories.VirtualEventUserRegistrationFactory(
        virtual_event_id=event.id, user_id=factories.EnterpriseUserFactory().id
    )

    result = virtual_events.get_virtual_event_with_registration_for_one_user(
        virtual_event_id=event.id, user_id=user.id
    )
    assert len(result.user_registrations) == 1


def test_get_virtual_event_with_registration_for_one_user_no_registration(factories):
    user = factories.EnterpriseUserFactory()
    event = factories.VirtualEventFactory()
    factories.VirtualEventUserRegistrationFactory(
        virtual_event_id=event.id, user_id=user.id
    )
    event2 = factories.VirtualEventFactory()

    result = virtual_events.get_virtual_event_with_registration_for_one_user(
        virtual_event_id=event2.id, user_id=user.id
    )
    assert result.id == event2.id
    assert len(result.user_registrations) == 0


def test_get_virtual_event_with_registration_for_one_user_no_event(factories):
    user = factories.EnterpriseUserFactory()
    event = factories.VirtualEventFactory()
    factories.VirtualEventUserRegistrationFactory(
        virtual_event_id=event.id, user_id=user.id
    )

    result = virtual_events.get_virtual_event_with_registration_for_one_user(
        virtual_event_id=9999999, user_id=user.id
    )
    assert result is None
