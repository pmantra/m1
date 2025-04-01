import enum
from dataclasses import dataclass


# treating zendesk as a separate service from tracks/orgs so
# redefining classes here
class ZendeskTrackName(str, enum.Enum):
    ADOPTION = "adoption"
    BREAST_MILK_SHIPPING = "breast_milk_shipping"
    EGG_FREEZING = "egg_freezing"
    FERTILITY = "fertility"
    GENERAL_WELLNESS = "general_wellness"
    GENERIC = "generic"
    PARENTING_AND_PEDIATRICS = "parenting_and_pediatrics"
    PARTNER_FERTILITY = "partner_fertility"
    PARTNER_NEWPARENT = "partner_newparent"
    PARTNER_PREGNANT = "partner_pregnant"
    POSTPARTUM = "postpartum"
    PREGNANCY = "pregnancy"
    PREGNANCYLOSS = "pregnancyloss"
    PREGNANCY_OPTIONS = "pregnancy_options"
    SPONSORED = "sponsored"
    SURROGACY = "surrogacy"
    TRYING_TO_CONCEIVE = "trying_to_conceive"
    MENOPAUSE = "menopause"


@dataclass
class ZendeskClientTrack:
    active: bool
    name: str
    display_name: str
