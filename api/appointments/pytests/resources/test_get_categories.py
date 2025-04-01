from typing import Dict, List
from unittest import mock

import pytest

from appointments.models.needs_and_categories import DEFAULT_CATEGORY_IMAGE
from models.tracks import TrackName


def make_enterprise_user_with_tracks_and_categories(
    factories,
    tracks_to_categories: Dict[str, List[str]],
    hide_multitrack_categories: List[str],
):
    member = factories.EnterpriseUserFactory.create(tracks=[])
    category_name_to_object = {}
    for track, categories in tracks_to_categories.items():
        factories.MemberTrackFactory.create(name=track, user=member)
        for category_name in categories:
            category = category_name_to_object.get(category_name)

            if not category:
                category = factories.NeedCategoryFactory.create()
                category.name = category_name
                category.hide_from_multitrack = (
                    category_name in hide_multitrack_categories
                )
                category_name_to_object[category_name] = category

            factories.NeedCategoryTrackFactory.create(
                track_name=track,
                need_category_id=category.id,
            )
    return member


def test_get_categories(
    client,
    api_helpers,
    enterprise_user_with_tracks_and_categories,
):
    track_names = ["adoption", "pregnancy"]
    member, tracks, need_categories = enterprise_user_with_tracks_and_categories(
        track_names
    )
    nc_names = {nc.name for nc in need_categories}

    res = client.get(
        "/api/v1/booking_flow/categories",
        headers=api_helpers.json_headers(member),
    )

    assert res.status_code == 200

    res_data = res.json["data"]
    assert "categories" in res_data
    actual_categories = res_data["categories"]

    assert len(actual_categories) == 2
    actual_nc_names = {
        actual_categories[0].get("name"),
        actual_categories[1].get("name"),
    }
    assert nc_names == actual_nc_names

    for actual_category in actual_categories:
        assert "image_id" in actual_category
        assert "image_url" in actual_category
        assert len(actual_category["image_id"]) > 0
        assert len(actual_category["image_url"]) > 0


def test_get_categories_with_l10n(
    client,
    api_helpers,
    enterprise_user_with_tracks_and_categories,
):
    track_names = ["adoption", "pregnancy"]
    member, tracks, need_categories = enterprise_user_with_tracks_and_categories(
        track_names
    )
    nc_names = {nc.name for nc in need_categories}

    with mock.patch(
        "appointments.resources.booking.feature_flags.bool_variation",
        return_value=True,
    ):
        res = client.get(
            "/api/v1/booking_flow/categories",
            headers=api_helpers.json_headers(member),
        )

    assert res.status_code == 200

    res_data = res.json["data"]
    assert "categories" in res_data
    actual_categories = res_data["categories"]

    assert len(actual_categories) == 2
    actual_nc_names = {
        actual_categories[0].get("name"),
        actual_categories[1].get("name"),
    }
    assert nc_names == actual_nc_names

    for actual_category in actual_categories:
        assert "image_id" in actual_category
        assert "image_url" in actual_category
        assert len(actual_category["image_id"]) > 0
        assert len(actual_category["image_url"]) > 0


def test_get_categories_for_marketplace_user(client, api_helpers, factories):
    member = factories.MemberFactory.create()

    category = factories.NeedCategoryFactory.create()
    category.name = "general wellness category"
    factories.NeedCategoryTrackFactory.create(
        track_name="general_wellness",
        need_category_id=category.id,
    )

    category2 = factories.NeedCategoryFactory.create()
    category2.name = "other category"
    factories.NeedCategoryTrackFactory.create(
        track_name="pregnancy",
        need_category_id=category.id,
    )

    res = client.get(
        "/api/v1/booking_flow/categories",
        headers=api_helpers.json_headers(member),
    )

    assert res.status_code == 200

    res_data = res.json["data"]
    assert "categories" in res_data
    assert {category.name} == {c["name"] for c in res_data["categories"]}


@pytest.mark.skip("DISCO-4961 Fix flaky need_category tests")
def test_get_categories_multitrack(
    client,
    api_helpers,
    factories,
):
    track_names = {
        "adoption": ["Adoption", "Pediatrics"],
        "parenting_and_pediatrics": ["Parenting", "Pediatrics", "Emotional Health"],
    }
    # Confirm that we are filtering out the hide_from_multitrack category
    member = make_enterprise_user_with_tracks_and_categories(
        factories, track_names, hide_multitrack_categories=["Emotional Health"]
    )

    res = client.get(
        "/api/v1/booking_flow/categories",
        headers=api_helpers.json_headers(member),
    )

    assert res.status_code == 200

    res_data = res.json["data"]
    assert "categories" in res_data
    actual_categories = res_data["categories"]
    actual_category_names = {c.get("name") for c in actual_categories}

    assert actual_category_names == {"Adoption", "Parenting", "Pediatrics"}
    # Make sure we deduped the categories before returning
    assert len(actual_categories) == 3

    for actual_category in actual_categories:
        assert "image_id" in actual_category
        assert "image_url" in actual_category
        assert len(actual_category["image_id"]) > 0
        assert len(actual_category["image_url"]) > 0


def test_get_categories_empty(
    client,
    api_helpers,
    enterprise_user,
):
    member = enterprise_user

    res = client.get(
        "/api/v1/booking_flow/categories",
        headers=api_helpers.json_headers(member),
    )

    assert res.status_code == 200

    res_data = res.json["data"]
    assert "categories" in res_data
    actual_categories = res_data["categories"]

    assert len(actual_categories) == 0


def test_get_categories_no_image(
    client,
    api_helpers,
    enterprise_user_with_tracks_and_categories,
):
    track_names = ["adoption", "pregnancy"]
    member, tracks, need_categories = enterprise_user_with_tracks_and_categories(
        track_names
    )
    nc_names = {nc.name for nc in need_categories}

    # remove image_id
    for nc in need_categories:
        nc.image_id = ""

    res = client.get(
        "/api/v1/booking_flow/categories",
        headers=api_helpers.json_headers(member),
    )

    assert res.status_code == 200

    res_data = res.json["data"]
    assert "categories" in res_data
    actual_categories = res_data["categories"]

    assert len(actual_categories) == 2
    actual_nc_names = {
        actual_categories[0].get("name"),
        actual_categories[1].get("name"),
    }
    assert nc_names == actual_nc_names

    for actual_category in actual_categories:
        assert "image_id" in actual_category
        assert "image_url" in actual_category
        assert len(actual_category["image_id"]) > 0
        assert len(actual_category["image_url"]) > 0
        assert DEFAULT_CATEGORY_IMAGE == actual_category["image_id"]
        assert DEFAULT_CATEGORY_IMAGE in actual_category["image_url"]


def test_get_categories__order_by_display_order(
    factories,
    client,
    api_helpers,
    enterprise_user,
):
    """
    Tests that categories are sorted by `display_order`, with nulls last
    """
    member = enterprise_user  # default track is pregnancy

    need_categories = []
    expected_display_orders = [3, 5, 99, None]
    display_orders = [99, 5, None, 3]
    for display_order in display_orders:
        nc = factories.NeedCategoryFactory.create(
            name=f"display_order_{display_order}",
            display_order=display_order,
        )
        need_categories.append(nc)
        factories.NeedCategoryTrackFactory.create(
            track_name=TrackName.PREGNANCY,
            need_category_id=nc.id,
        )

    res = client.get(
        "/api/v1/booking_flow/categories",
        headers=api_helpers.json_headers(member),
    )

    assert res.status_code == 200

    res_data = res.json["data"]
    assert "categories" in res_data
    actual_categories = res_data["categories"]

    assert len(actual_categories) == 4
    assert (
        actual_categories[0].get("name")
        == f"display_order_{expected_display_orders[0]}"
    )
    assert (
        actual_categories[1].get("name")
        == f"display_order_{expected_display_orders[1]}"
    )
    assert (
        actual_categories[2].get("name")
        == f"display_order_{expected_display_orders[2]}"
    )
    assert (
        actual_categories[3].get("name")
        == f"display_order_{expected_display_orders[3]}"
    )
