VALID_FERTILITY_STATUS_CODES = {
    "not_ttc_learning",
    "ttc_in_six_months",
    "ttc_no_treatment",
    "considering_fertility_treatment",
    "undergoing_iui",
    "undergoing_ivf",
    "ttc_no_iui_ivf",
    "successful_pregnancy",
}


class AggregatedFertilityTreatmentStatus:
    PRECONCEPTION = ["not_ttc_learning", "ttc_in_six_months"]
    TTC = ["ttc_no_treatment", "ttc_no_iui_ivf"]


# Feature flags
MIGRATE_PREGNANCY_DATA_FROM_MONO_TO_HPS = "migrate-pregnancy-data-from-mono-to-hps"
