import enum


class VGC(str, enum.Enum):
    """
    VGC stands for Vertical Group Condensed. Its a way the Providers Team groups verticals.
    Usually there is a 1-1 relationship between a VGC and a Vertical, but its not necessarily always the case.
    VGC are mostly used to assign care teams. We want to be sure that all VGC's of a given track are covered by practitioners.
    """

    ADOPTION_COACH = "Adoption Coach"
    CAREER_COACH = "Career Coach"
    CHILDCARE_CONSULTANT = "Childcare Consultant"
    DOULA = "Doula"
    EGG_DONOR_CONSULTANT = "Egg Donor Consultant"
    FERTILITY_AWARENESS_EDUCATOR = "Fertility Awareness Educator"
    LACTATION_CONSULTANT = "Lactation Consultant"
    MENTAL_HEALTH = "Mental Health"
    NUTRITIONIST = "Nutritionist"
    OB_GYN = "OB/GYN"
    OTHER_WELLNESS = "Other - Wellness"
    PARENT_COACH = "Parent Coach"
    PEDIATRICIAN = "Pediatrician"
    PHYSICAL_THERAPY = "Physical Therapy"
    REPRODUCTIVE_ENDOCRINOLOGIST = "Reproductive Endocrinologist"
    REPRODUCTIVE_NURSE = "Reproductive Nurse"
    SEX_COACH = "Sex Coach"
    SLEEP_COACH = "Sleep Coach"
    SURROGACY_COACH = "Surrogacy Coach"
    WELLNESS_COACH = "Wellness Coach"


def validate_vgc(instance, key: str, vgc: str) -> bool:  # type: ignore[no-untyped-def] # Function is missing a type annotation for one or more arguments
    valid = vgc in [*VGC]
    if not valid:
        raise ValueError(
            f"{instance.__class__.__name__}.{key}: "
            f"{vgc} is not a valid VGC in class VGC(enum.Enum)."
        )
    return valid
