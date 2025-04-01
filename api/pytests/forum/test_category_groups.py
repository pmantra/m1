import pytest

from models.tracks import TrackName


@pytest.mark.parametrize(
    "track_name, expected_group_label",
    [
        (
            "adoption",
            [
                "Fertility & Family Building",
                "Ongoing Support",
                "Parenting & Pediatrics",
                "Pregnancy & Newborn Care",
                "Menopause & Midlife Health",
            ],
        ),
        (
            "fertility",
            [
                "Fertility & Family Building",
                "Ongoing Support",
                "Parenting & Pediatrics",
                "Pregnancy & Newborn Care",
                "Menopause & Midlife Health",
            ],
        ),
        (
            "surrogacy",
            [
                "Fertility & Family Building",
                "Ongoing Support",
                "Parenting & Pediatrics",
                "Pregnancy & Newborn Care",
                "Menopause & Midlife Health",
            ],
        ),
        (
            "egg_freezing",
            [
                "Fertility & Family Building",
                "Ongoing Support",
                "Parenting & Pediatrics",
                "Pregnancy & Newborn Care",
                "Menopause & Midlife Health",
            ],
        ),
        (
            "pregnancy",
            [
                "Pregnancy & Newborn Care",
                "Ongoing Support",
                "Parenting & Pediatrics",
                "Fertility & Family Building",
                "Menopause & Midlife Health",
            ],
        ),
        (
            "partner_pregnant",
            [
                "Pregnancy & Newborn Care",
                "Ongoing Support",
                "Parenting & Pediatrics",
                "Fertility & Family Building",
                "Menopause & Midlife Health",
            ],
        ),
        (
            "postpartum",
            [
                "Pregnancy & Newborn Care",
                "Ongoing Support",
                "Parenting & Pediatrics",
                "Fertility & Family Building",
                "Menopause & Midlife Health",
            ],
        ),
        (
            "breast_milk_shipping",
            [
                "Pregnancy & Newborn Care",
                "Ongoing Support",
                "Parenting & Pediatrics",
                "Fertility & Family Building",
                "Menopause & Midlife Health",
            ],
        ),
        (
            "pregnancyloss",
            [
                "Fertility & Family Building",
                "Ongoing Support",
                "Parenting & Pediatrics",
                "Pregnancy & Newborn Care",
                "Menopause & Midlife Health",
            ],
        ),
        (
            "pregnancy_options",
            [
                "Pregnancy & Newborn Care",
                "Ongoing Support",
                "Parenting & Pediatrics",
                "Fertility & Family Building",
                "Menopause & Midlife Health",
            ],
        ),
        (
            "parenting_and_pediatrics",
            [
                "Parenting & Pediatrics",
                "Ongoing Support",
                "Pregnancy & Newborn Care",
                "Fertility & Family Building",
                "Menopause & Midlife Health",
            ],
        ),
        (
            "partner_newparent",
            [
                "Pregnancy & Newborn Care",
                "Parenting & Pediatrics",
                "Ongoing Support",
                "Fertility & Family Building",
                "Menopause & Midlife Health",
            ],
        ),
        (
            "menopause",
            [
                "Menopause & Midlife Health",
                "Ongoing Support",
                "Parenting & Pediatrics",
                "Fertility & Family Building",
                "Pregnancy & Newborn Care",
            ],
        ),
        (
            "general_wellness",
            [
                "Ongoing Support",
                "Fertility & Family Building",
                "Parenting & Pediatrics",
                "Menopause & Midlife Health",
                "Pregnancy & Newborn Care",
            ],
        ),
    ],
)
def test_get_category_groups_by_user(
    client, factories, api_helpers, track_name, expected_group_label
):
    user = factories.EnterpriseUserFactory(tracks__name=track_name)

    response = client.get(
        "/api/v1/forums/categories",
        headers=api_helpers.json_headers(user=user),
    )

    assert response.status_code == 200
    mapped_response_labels = [val["label"] for val in response.json["data"]]
    assert mapped_response_labels == expected_group_label


@pytest.mark.parametrize(
    "non_pnp_track_name, expected_group_label",
    [
        (
            "adoption",
            [
                "Fertility & Family Building",
                "Parenting & Pediatrics",
                "Ongoing Support",
                "Pregnancy & Newborn Care",
                "Menopause & Midlife Health",
            ],
        ),
        (
            "fertility",
            [
                "Fertility & Family Building",
                "Parenting & Pediatrics",
                "Ongoing Support",
                "Pregnancy & Newborn Care",
                "Menopause & Midlife Health",
            ],
        ),
        (
            "surrogacy",
            [
                "Fertility & Family Building",
                "Parenting & Pediatrics",
                "Ongoing Support",
                "Pregnancy & Newborn Care",
                "Menopause & Midlife Health",
            ],
        ),
        (
            "egg_freezing",
            [
                "Fertility & Family Building",
                "Parenting & Pediatrics",
                "Ongoing Support",
                "Pregnancy & Newborn Care",
                "Menopause & Midlife Health",
            ],
        ),
        (
            "pregnancy",
            [
                "Pregnancy & Newborn Care",
                "Parenting & Pediatrics",
                "Ongoing Support",
                "Fertility & Family Building",
                "Menopause & Midlife Health",
            ],
        ),
        (
            "partner_pregnant",
            [
                "Pregnancy & Newborn Care",
                "Parenting & Pediatrics",
                "Ongoing Support",
                "Fertility & Family Building",
                "Menopause & Midlife Health",
            ],
        ),
        (
            "postpartum",
            [
                "Pregnancy & Newborn Care",
                "Parenting & Pediatrics",
                "Ongoing Support",
                "Fertility & Family Building",
                "Menopause & Midlife Health",
            ],
        ),
        (
            "breast_milk_shipping",
            [
                "Pregnancy & Newborn Care",
                "Parenting & Pediatrics",
                "Ongoing Support",
                "Fertility & Family Building",
                "Menopause & Midlife Health",
            ],
        ),
        (
            "pregnancyloss",
            [
                "Fertility & Family Building",
                "Parenting & Pediatrics",
                "Ongoing Support",
                "Pregnancy & Newborn Care",
                "Menopause & Midlife Health",
            ],
        ),
        (
            "pregnancy_options",
            [
                "Pregnancy & Newborn Care",
                "Parenting & Pediatrics",
                "Ongoing Support",
                "Fertility & Family Building",
                "Menopause & Midlife Health",
            ],
        ),
        (
            "partner_newparent",
            [
                "Pregnancy & Newborn Care",
                "Parenting & Pediatrics",
                "Ongoing Support",
                "Fertility & Family Building",
                "Menopause & Midlife Health",
            ],
        ),
        (
            "menopause",
            [
                "Menopause & Midlife Health",
                "Parenting & Pediatrics",
                "Ongoing Support",
                "Fertility & Family Building",
                "Pregnancy & Newborn Care",
            ],
        ),
        (
            "general_wellness",
            [
                "Ongoing Support",
                "Parenting & Pediatrics",
                "Fertility & Family Building",
                "Menopause & Midlife Health",
                "Pregnancy & Newborn Care",
            ],
        ),
    ],
)
def test_get_category_groups_by_user_multitrack(
    client, factories, api_helpers, non_pnp_track_name, expected_group_label
):
    user = factories.EnterpriseUserNoTracksFactory.create()
    factories.MemberTrackFactory.create(
        name=TrackName.PARENTING_AND_PEDIATRICS, user=user
    )
    factories.MemberTrackFactory.create(
        name=non_pnp_track_name,
        user=user,
    )

    response = client.get(
        "/api/v1/forums/categories",
        headers=api_helpers.json_headers(user=user),
    )

    assert response.status_code == 200
    mapped_response_labels = [val["label"] for val in response.json["data"]]
    assert mapped_response_labels == expected_group_label


test_categories = [
    {"name": "pregnancy", "display_name": "Pregnancy"},
    {"name": "birth-month-groups", "display_name": "Birth month groups"},
    {"name": "postpartum", "display_name": "Postpartum"},
    {"name": "ask-a-provider", "display_name": "Ask a Provider"},
    {"name": "pediatrics-parenting", "display_name": "Pediatrics and Parenting"},
    {"name": "preconception", "display_name": "TTC and fertility"},
    {"name": "fertility", "display_name": "Fertility Treatment"},
    {"name": "adoption-surrogacy", "display_name": "Adoption and surrogacy"},
    {"name": "menopause", "display_name": "Menopause"},
]


@pytest.mark.parametrize(
    "track_name, expected_order",
    [
        (
            TrackName.PREGNANCY,
            test_categories[0:3],
        ),
        (
            TrackName.POSTPARTUM,
            test_categories[0:3][::-1],
        ),
        (
            TrackName.BREAST_MILK_SHIPPING,
            test_categories[0:3][::-1],
        ),
        (
            TrackName.FERTILITY,
            test_categories[5:8],
        ),
        (
            TrackName.EGG_FREEZING,
            test_categories[5:8],
        ),
        (
            TrackName.ADOPTION,
            test_categories[5:8][::-1],
        ),
        (
            TrackName.SURROGACY,
            test_categories[5:8][::-1],
        ),
    ],
)
def test_top_category_order_variants(
    client, factories, api_helpers, track_name, expected_order
):
    category_version = factories.ForumCategoryVersionFactory.create(name="Web")
    [
        factories.ForumsCategoryFactory.create(versions=[category_version], **category)
        for category in test_categories
    ]

    user = factories.EnterpriseUserFactory(tracks__name=track_name)
    response = client.get(
        "/api/v1/forums/categories",
        headers=api_helpers.json_headers(user=user),
    )
    assert response.status_code == 200
    response_top_categories = response.json["data"][0]["categories"]

    actual_data = [
        {"display_name": category["display_name"], "name": category["name"]}
        for category in response_top_categories
    ]

    assert actual_data == expected_order
