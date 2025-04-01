from common.constants import Environment
from models.tracks import TrackName

from .constants import MARKETPLACE_MEMBER

# Pulled from https://docs.google.com/spreadsheets/d/1XlY4uJ06Hu8lsAQgq3cnTTiuTzIUr2D4nMaZrtVmHgQ/edit#gid=165668366
configuration = {
    "version": "1.0.0",
    "env": Environment.PRODUCTION,
    "data": {
        TrackName.ADOPTION: [
            "adoption-process-options",
            "preparing-for-adoption",
            "stress-anxiety-depression",
        ],
        TrackName.BREAST_MILK_SHIPPING: [
            "breastfeeding-pump-formula",
            "child-cold-flu-illness",
            "general-health-advice",
        ],  # same as Generic
        TrackName.GENERIC: [
            "breastfeeding-pump-formula",
            "child-cold-flu-illness",
            "general-health-advice",
        ],  # same as Breast Milk Shipping
        TrackName.EGG_FREEZING: [
            "ef-process-options",
            "preparing-for-ef",
            "stress-anxiety-depression",
        ],
        TrackName.FERTILITY: [
            "treatment-options-steps",
            "emotional-support",
            "fert-nutrition",
        ],
        TrackName.GENERAL_WELLNESS: [
            "general-health-advice",
            "stress-anxiety-depression",
            "nutrition",
        ],
        TrackName.MENOPAUSE: [
            "men-managing-symptoms",
            "men-nutrition",
            "men-med-options",
        ],
        TrackName.PARENTING_AND_PEDIATRICS: [
            "child-cold-flu-illness",
            "child-sleep",
            "stress-anxiety-depression",
        ],
        TrackName.PARTNER_FERTILITY: [
            "treatment-options-steps",
            "emotional-support",
            "fert-nutrition",
        ],
        TrackName.PARTNER_NEWPARENT: [
            "breastfeeding-pump-formula",
            "baby-sleep",
            "baby-cold-flu",
        ],
        TrackName.PARTNER_PREGNANT: [
            "preg-general-questions",
            "prep-labor-delivery",
            "preg-second-opinion",
        ],
        TrackName.POSTPARTUM: [
            "breastfeeding-pump-formula",
            "baby-sleep",
            "baby-cold-flu",
        ],
        TrackName.PREGNANCY: [
            "breastfeeding-pump-formula",
            "preg-general-questions",
            "prep-labor-delivery",
        ],
        TrackName.PREGNANCYLOSS: [
            "miscarriage-treatment-recovery",
            "conception-after-loss",
            "coping-with-loss",
        ],
        TrackName.PREGNANCY_OPTIONS: [
            "pregnancy-options-counseling",
            "abortion-care-recovery",
            "stress-anxiety-depression",
        ],
        TrackName.SURROGACY: [
            "surrogacy-process-options",
            "preparing-for-surrogacy",
            "stress-anxiety-depression",
        ],
        TrackName.TRYING_TO_CONCEIVE: [
            "starting-conception",
            "tracking-cycle",
            "trouble-conceiving",
        ],
        MARKETPLACE_MEMBER: [
            "general-health-advice",
            "stress-anxiety-depression",
            "nutrition",
        ],
    },
}
