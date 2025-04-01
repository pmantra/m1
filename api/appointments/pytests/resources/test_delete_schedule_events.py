import datetime

now = datetime.datetime.utcnow().replace(second=0, microsecond=0)


def test_can_delete_schedule_event(
    factories,
    client,
    api_helpers,
    practitioner_user,
):
    """Tests that a schedule event can be deleted"""
    practitioner = _setup_practitioner_delete_schedule_event(
        factories, practitioner_user
    )

    event = _create_schedule_event(factories, practitioner, now)

    res = client.delete(
        f"/api/v1/practitioners/{practitioner.id}/schedules/events/{event.id}",
        headers=api_helpers.json_headers(practitioner),
    )

    assert res.status_code == 204


def test_can_delete_schedule_event_when_event_is_in_past(
    factories,
    client,
    api_helpers,
    practitioner_user,
):
    """Tests that a schedule event can be deleted when schedule event is in the past"""
    practitioner = _setup_practitioner_delete_schedule_event(
        factories,
        practitioner_user,
    )

    # Create schedule event that started in the past
    event = _create_schedule_event(
        factories, practitioner, now - datetime.timedelta(days=4)
    )

    res = client.delete(
        f"/api/v1/practitioners/{practitioner.id}/schedules/events/{event.id}",
        headers=api_helpers.json_headers(practitioner),
    )

    assert res.status_code == 204


def test_can_delete_schedule_event_when_event_is_in_future(
    factories,
    client,
    api_helpers,
    practitioner_user,
):
    """Tests that a schedule event can be deleted when schedule event is in the future"""
    practitioner = _setup_practitioner_delete_schedule_event(
        factories,
        practitioner_user,
    )

    # Create schedule event
    event = _create_schedule_event(
        factories, practitioner, now + datetime.timedelta(days=4)
    )

    res = client.delete(
        f"/api/v1/practitioners/{practitioner.id}/schedules/events/{event.id}",
        headers=api_helpers.json_headers(practitioner),
    )

    assert res.status_code == 204


def _setup_practitioner_delete_schedule_event(
    factories,
    practitioner_user,
    products=None,
):
    """Create and configure practitioner with vertical/product and capability to delete schedule event"""
    practitioner = practitioner_user()

    if not products:
        # Create vertical
        vertical = factories.VerticalFactory.create()

        # Create product
        product = factories.ProductFactory.create(
            vertical=vertical,
            is_active=True,
            minutes=10,
            price=10,
        )
        products = [product]

    practitioner.products = products

    # Set the capability/role of the practitioner to enable delete schedule event
    capability = factories.CapabilityFactory.create(
        object_type="schedule_event", method="delete"
    )
    role = factories.RoleFactory.create(name="practitioner", capabilities=[capability])
    practitioner.practitioner_profile.role = role

    return practitioner


def _create_schedule_event(
    factories,
    practitioner,
    starts_at,
    duration_hours=4,
):
    """Create schedule event"""
    event = factories.ScheduleEventFactory.create(
        schedule=practitioner.schedule,
        starts_at=starts_at,
        ends_at=starts_at + datetime.timedelta(hours=duration_hours),
    )

    return event
