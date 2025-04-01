from typing import TypedDict

from models.tracks import TrackName


class CategoryGroup(TypedDict):
    label: str
    category_names: list[str]


PREGNANCY_CARE_GROUP = CategoryGroup(
    label="Pregnancy & Newborn Care",
    category_names=["pregnancy", "birth-month-groups", "postpartum"],
)

POSTPARTUM_GROUP = CategoryGroup(
    label="Pregnancy & Newborn Care",
    category_names=["postpartum", "birth-month-groups", "pregnancy"],
)

ONGOING_SUPPORT_GROUP = CategoryGroup(
    label="Ongoing Support", category_names=["ask-a-provider", "health-wellness"]
)

PARENTING_PEDIATRICS_GROUP = CategoryGroup(
    label="Parenting & Pediatrics", category_names=["pediatrics-parenting"]
)

FERTILITY_GROUP = CategoryGroup(
    label="Fertility & Family Building",
    category_names=["preconception", "fertility", "adoption-surrogacy"],
)

ADOPTION_GROUP = CategoryGroup(
    label="Fertility & Family Building",
    category_names=["adoption-surrogacy", "fertility", "preconception"],
)

MENOPAUSE_GROUP = CategoryGroup(
    label="Menopause & Midlife Health", category_names=["menopause"]
)

CATEGORY_GROUPS = {
    TrackName.ADOPTION: [
        ADOPTION_GROUP,
        ONGOING_SUPPORT_GROUP,
        PARENTING_PEDIATRICS_GROUP,
        PREGNANCY_CARE_GROUP,
        MENOPAUSE_GROUP,
    ],
    TrackName.FERTILITY: [
        FERTILITY_GROUP,
        ONGOING_SUPPORT_GROUP,
        PARENTING_PEDIATRICS_GROUP,
        PREGNANCY_CARE_GROUP,
        MENOPAUSE_GROUP,
    ],
    TrackName.SURROGACY: [
        ADOPTION_GROUP,
        ONGOING_SUPPORT_GROUP,
        PARENTING_PEDIATRICS_GROUP,
        PREGNANCY_CARE_GROUP,
        MENOPAUSE_GROUP,
    ],
    TrackName.EGG_FREEZING: [
        FERTILITY_GROUP,
        ONGOING_SUPPORT_GROUP,
        PARENTING_PEDIATRICS_GROUP,
        PREGNANCY_CARE_GROUP,
        MENOPAUSE_GROUP,
    ],
    TrackName.PREGNANCY: [
        PREGNANCY_CARE_GROUP,
        ONGOING_SUPPORT_GROUP,
        PARENTING_PEDIATRICS_GROUP,
        FERTILITY_GROUP,
        MENOPAUSE_GROUP,
    ],
    TrackName.PARTNER_PREGNANT: [
        PREGNANCY_CARE_GROUP,
        ONGOING_SUPPORT_GROUP,
        PARENTING_PEDIATRICS_GROUP,
        FERTILITY_GROUP,
        MENOPAUSE_GROUP,
    ],
    TrackName.POSTPARTUM: [
        POSTPARTUM_GROUP,
        ONGOING_SUPPORT_GROUP,
        PARENTING_PEDIATRICS_GROUP,
        FERTILITY_GROUP,
        MENOPAUSE_GROUP,
    ],
    TrackName.BREAST_MILK_SHIPPING: [
        POSTPARTUM_GROUP,
        ONGOING_SUPPORT_GROUP,
        PARENTING_PEDIATRICS_GROUP,
        FERTILITY_GROUP,
        MENOPAUSE_GROUP,
    ],
    TrackName.PREGNANCYLOSS: [
        FERTILITY_GROUP,
        ONGOING_SUPPORT_GROUP,
        PARENTING_PEDIATRICS_GROUP,
        PREGNANCY_CARE_GROUP,
        MENOPAUSE_GROUP,
    ],
    TrackName.PREGNANCY_OPTIONS: [
        PREGNANCY_CARE_GROUP,
        ONGOING_SUPPORT_GROUP,
        PARENTING_PEDIATRICS_GROUP,
        FERTILITY_GROUP,
        MENOPAUSE_GROUP,
    ],
    TrackName.PARENTING_AND_PEDIATRICS: [
        PARENTING_PEDIATRICS_GROUP,
        ONGOING_SUPPORT_GROUP,
        PREGNANCY_CARE_GROUP,
        FERTILITY_GROUP,
        MENOPAUSE_GROUP,
    ],
    TrackName.PARTNER_NEWPARENT: [
        PREGNANCY_CARE_GROUP,
        PARENTING_PEDIATRICS_GROUP,
        ONGOING_SUPPORT_GROUP,
        FERTILITY_GROUP,
        MENOPAUSE_GROUP,
    ],
    TrackName.MENOPAUSE: [
        MENOPAUSE_GROUP,
        ONGOING_SUPPORT_GROUP,
        PARENTING_PEDIATRICS_GROUP,
        FERTILITY_GROUP,
        PREGNANCY_CARE_GROUP,
    ],
    TrackName.GENERAL_WELLNESS: [
        ONGOING_SUPPORT_GROUP,
        FERTILITY_GROUP,
        PARENTING_PEDIATRICS_GROUP,
        MENOPAUSE_GROUP,
        PREGNANCY_CARE_GROUP,
    ],
    "None": [
        PREGNANCY_CARE_GROUP,
        ONGOING_SUPPORT_GROUP,
        PARENTING_PEDIATRICS_GROUP,
        FERTILITY_GROUP,
        MENOPAUSE_GROUP,
    ],
}

MULTITRACK_CATEGORY_GROUPS = {
    TrackName.ADOPTION: [
        ADOPTION_GROUP,
        PARENTING_PEDIATRICS_GROUP,
        ONGOING_SUPPORT_GROUP,
        PREGNANCY_CARE_GROUP,
        MENOPAUSE_GROUP,
    ],
    TrackName.FERTILITY: [
        FERTILITY_GROUP,
        PARENTING_PEDIATRICS_GROUP,
        ONGOING_SUPPORT_GROUP,
        PREGNANCY_CARE_GROUP,
        MENOPAUSE_GROUP,
    ],
    TrackName.SURROGACY: [
        ADOPTION_GROUP,
        PARENTING_PEDIATRICS_GROUP,
        ONGOING_SUPPORT_GROUP,
        PREGNANCY_CARE_GROUP,
        MENOPAUSE_GROUP,
    ],
    TrackName.EGG_FREEZING: [
        FERTILITY_GROUP,
        PARENTING_PEDIATRICS_GROUP,
        ONGOING_SUPPORT_GROUP,
        PREGNANCY_CARE_GROUP,
        MENOPAUSE_GROUP,
    ],
    TrackName.PREGNANCY: [
        PREGNANCY_CARE_GROUP,
        PARENTING_PEDIATRICS_GROUP,
        ONGOING_SUPPORT_GROUP,
        FERTILITY_GROUP,
        MENOPAUSE_GROUP,
    ],
    TrackName.PARTNER_PREGNANT: [
        PREGNANCY_CARE_GROUP,
        PARENTING_PEDIATRICS_GROUP,
        ONGOING_SUPPORT_GROUP,
        FERTILITY_GROUP,
        MENOPAUSE_GROUP,
    ],
    TrackName.POSTPARTUM: [
        POSTPARTUM_GROUP,
        PARENTING_PEDIATRICS_GROUP,
        ONGOING_SUPPORT_GROUP,
        FERTILITY_GROUP,
        MENOPAUSE_GROUP,
    ],
    TrackName.BREAST_MILK_SHIPPING: [
        POSTPARTUM_GROUP,
        PARENTING_PEDIATRICS_GROUP,
        ONGOING_SUPPORT_GROUP,
        FERTILITY_GROUP,
        MENOPAUSE_GROUP,
    ],
    TrackName.PREGNANCYLOSS: [
        FERTILITY_GROUP,
        PARENTING_PEDIATRICS_GROUP,
        ONGOING_SUPPORT_GROUP,
        PREGNANCY_CARE_GROUP,
        MENOPAUSE_GROUP,
    ],
    TrackName.PREGNANCY_OPTIONS: [
        PREGNANCY_CARE_GROUP,
        PARENTING_PEDIATRICS_GROUP,
        ONGOING_SUPPORT_GROUP,
        FERTILITY_GROUP,
        MENOPAUSE_GROUP,
    ],
    TrackName.PARTNER_NEWPARENT: [
        PREGNANCY_CARE_GROUP,
        PARENTING_PEDIATRICS_GROUP,
        ONGOING_SUPPORT_GROUP,
        FERTILITY_GROUP,
        MENOPAUSE_GROUP,
    ],
    TrackName.MENOPAUSE: [
        MENOPAUSE_GROUP,
        PARENTING_PEDIATRICS_GROUP,
        ONGOING_SUPPORT_GROUP,
        FERTILITY_GROUP,
        PREGNANCY_CARE_GROUP,
    ],
    TrackName.GENERAL_WELLNESS: [
        ONGOING_SUPPORT_GROUP,
        PARENTING_PEDIATRICS_GROUP,
        FERTILITY_GROUP,
        MENOPAUSE_GROUP,
        PREGNANCY_CARE_GROUP,
    ],
    "None": [
        PREGNANCY_CARE_GROUP,
        ONGOING_SUPPORT_GROUP,
        PARENTING_PEDIATRICS_GROUP,
        FERTILITY_GROUP,
        MENOPAUSE_GROUP,
    ],
}
