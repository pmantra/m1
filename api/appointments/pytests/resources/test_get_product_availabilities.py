import datetime
import json

from pytests import freezegun


@freezegun.freeze_time("2022-04-06 00:17:10.0")
def test_get_product_availabilities(
    factories,
    client,
    api_helpers,
    create_practitioner,
    add_schedule_event,
):
    """Tests that we can get availability for a single practitioner"""
    now = datetime.datetime.utcnow()
    member = factories.EnterpriseUserFactory.create()
    practitioner = create_practitioner(
        practitioner_profile__next_availability=now,
    )
    product_id = practitioner.products[0].id

    # Time for 3 appointment slots
    add_schedule_event(practitioner, now, 3)

    res = client.get(
        f"/api/v1/products/{product_id}/availability",
        headers=api_helpers.json_headers(member),
    )

    res_data = json.loads(res.data)
    availabilities = res_data["data"]
    assert len(availabilities) == 3
    assert availabilities[0]["scheduled_start"] == "2022-04-06T00:30:00"
    assert res_data["product_id"] == product_id
    assert res_data["product_price"] == practitioner.products[0].price
