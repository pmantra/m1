import datetime

NOW = datetime.datetime.utcnow().replace(microsecond=0)


def test_get_schedule_recurring_blocks_not_allowed(
    api_helpers,
    client,
    schedule_recurring_block_events,
    factories,
):
    practitioner = factories.PractitionerUserFactory.create()
    recurring_block = schedule_recurring_block_events(
        practitioner=practitioner, starts_at=NOW
    )
    schedule_start = recurring_block.starts_at
    schedule_until = recurring_block.until

    request = {
        "starts_at": schedule_start.isoformat(),
        "until": schedule_until.isoformat(),
    }

    res = client.get(
        "/api/v1/practitioners/12345/schedules/recurring_blocks",
        headers=api_helpers.json_headers(user=practitioner),
        query_string=request,
    )

    assert res.status_code == 403


def test_get_schedule_recurring_blocks(
    api_helpers,
    client,
    schedule_recurring_block_events,
    factories,
):
    practitioner = factories.PractitionerUserFactory.create()
    recurring_block = schedule_recurring_block_events(
        practitioner=practitioner, starts_at=NOW
    )
    schedule_start = recurring_block.starts_at
    schedule_until = recurring_block.until

    request = {
        "starts_at": schedule_start.isoformat(),
        "until": schedule_until.isoformat(),
    }

    res = client.get(
        f"/api/v1/practitioners/{practitioner.id}/schedules/recurring_blocks",
        headers=api_helpers.json_headers(user=practitioner),
        query_string=request,
    )

    assert res.status_code == 200
    assert all(
        key in res.json["data"][0].keys()
        for key in [
            "starts_at",
            "schedule_id",
            "week_days_index",
            "until",
            "frequency",
            "schedule_events",
            "id",
            "ends_at",
        ]
    )
    assert res.json["data"][0]["id"] == recurring_block.id
    assert res.json["data"][0]["schedule_id"] == recurring_block.schedule.id
    assert (
        res.json["data"][0]["schedule_events"][0]["id"]
        == recurring_block.schedule_events[0].id
    )
    assert res.json["data"][0]["starts_at"] == recurring_block.starts_at.isoformat()
    assert res.json["data"][0]["ends_at"] == recurring_block.ends_at.isoformat()
    assert res.json["data"][0]["until"] == recurring_block.until.isoformat()
    assert res.json["data"][0]["frequency"] == recurring_block.frequency
    assert res.json["data"][0]["week_days_index"] == sorted(
        [item.week_days_index for item in recurring_block.week_day_indices]
    )
