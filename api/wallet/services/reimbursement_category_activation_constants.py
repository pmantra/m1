from typing import Type

from wallet.services.reimbursement_category_activation_rules import (
    AbstractCategoryRule,
    AmazonProgenyTOCRule,
    LowesProgenyTOCRule,
    Tenure30DaysCategoryRule,
    Tenure90DaysCategoryRule,
    Tenure180DaysCategoryRule,
    TenureOneCalendarYearCategoryRule,
)

RULE_REGISTRATION_MAP: dict[str, Type[AbstractCategoryRule]] = {
    "TENURE_ONE_CALENDAR_YEAR": TenureOneCalendarYearCategoryRule,
    "TENURE_30_DAYS": Tenure30DaysCategoryRule,
    "TENURE_90_DAYS": Tenure90DaysCategoryRule,
    "TENURE_180_DAYS": Tenure180DaysCategoryRule,
    "AMAZON_PROGENY_TOC_PERIOD": AmazonProgenyTOCRule,
    "LOWES_PROGENY_TOC_PERIOD": LowesProgenyTOCRule,
}

TENURE_RULES = [
    "TENURE_ONE_CALENDAR_YEAR",
    "TENURE_30_DAYS",
    "TENURE_90_DAYS",
    "TENURE_180_DAYS",
]

TOC_RULES = ["AMAZON_PROGENY_TOC_PERIOD"]

SYSTEM_USER = "SYSTEM_USER"
