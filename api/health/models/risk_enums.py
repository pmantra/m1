# Some Important Risk Flag Names
import enum


# Risk Flags used in code
class RiskFlagName(str, enum.Enum):
    ADVANCED_MATERNAL_AGE_35 = "Advanced Maternal Age"
    ADVANCED_MATERNAL_AGE_40 = "Advanced Maternal Age (40+)"
    AUTOIMMUNE_DISEASE = "Autoimmune disease"
    AUTOIMMUNE_DISEASE_EXISTING = "Autoimmune disease - Existing condition"
    BMI_OVERWEIGHT = "Overweight"
    BMI_OBESITY = "Obesity"
    BLOOD_LOSS = "Blood loss"
    CSECTION_PAST_PREGNANCY = "C-section delivery - Past pregnancy"
    CONGENITAL_ABNORMALITY_AFFECTING_FERTILITY = (
        "Congenital abnormality affecting fertility"
    )
    DIABETES = "Diabetes"
    DIABETES_EXISTING = "Diabetes - Existing condition"
    FEMALE_FEMALE_COUPLE = "Female female couple"
    GESTATIONAL_DIABETES_AT_RISK = "Risk for gestational diabetes"
    GESTATIONAL_DIABETES_CURRENT_PREGNANCY = "Gestational diabetes - Current pregnancy"
    GESTATIONAL_DIABETES_PAST_PREGNANCY = "Gestational diabetes - Past pregnancy"
    ECLAMPSIA_CURRENT_PREGNANCY = "Eclampsia or HELLP - Current pregnancy"
    ECLAMPSIA_PAST_PREGNANCY = "Eclampsia or HELLP - Past pregnancy"
    FERTILITY_TREATMENTS = "Fertility treatments"
    FULLTERM_LABOR_PAST_PREGNANCY = "Fullterm birth - Past pregnancy"
    INFERTILITY_DIAGNOSIS = "Unexplained infertility"
    HIGH_BLOOD_PRESSURE = "High blood pressure - Existing condition"
    HIGH_BLOOD_PRESSURE_CURRENT_PREGNANCY = "High blood pressure - Current pregnancy"
    HIGH_BLOOD_PRESSURE_PAST_PREGNANCY = "High blood pressure - Past pregnancy"
    HIV_AIDS = "HIV/AIDS"
    HIV_AIDS_EXISTING = "HIV/AIDS - Existing condition"
    KIDNEY_DISEASE = "Kidney disease"
    KIDNEY_DISEASE_EXISTING = "Kidney disease - Existing condition"
    LOW_SOCIOECONOMIC_STATUS = "Low socioeconomic status"
    SDOH_HOUSING = "SDOH Housing"
    SDOH_FOOD = "SDOH Food"
    SDOH_MEDICINE = "SDOH Medicine"
    # There is no risk flag in the production mono database named "months trying to conceive"
    MONTHS_TRYING_TO_CONCEIVE = "months trying to conceive"
    MULTIPLE_GESTATION = "Multiple gestation"
    POLYCYSTIC_OVARIAN_SYNDROME = "PCOS"
    PRETERM_LABOR_AT_RISK = "Risk for preterm birth"
    PRETERM_LABOR_PAST_PREGNANCY = "Preterm birth - Past pregnancy"
    PRETERM_LABOR_HISTORY = "History of preterm labor or delivery"
    PREECLAMPSIA_CURRENT_PREGNANCY = "Preeclampsia - Current pregnancy"
    PREECLAMPSIA_HIGH = "High risk for preeclampsia"
    PREECLAMPSIA_MODERATE = "Moderate risk for preeclampsia"
    PREECLAMPSIA_PAST_PREGNANCY = "Preeclampsia - Past pregnancy"
    SINGLE_PARENT = "Single parent"
    UNEXPLAINED_INFERTILITY = "Unexplained infertility"

    # Trimester Risk Flags
    FIRST_TRIMESTER = "First trimester - trimester at onboarding"
    SECOND_TRIMESTER = "Second trimester - trimester at onboarding"
    EARLY_THIRD_TRIMESTER = "Early Third trimester - trimester at onboarding"
    LATE_THIRD_TRIMESTER = "Late Third trimester - trimester at onboarding"


class RiskInputKey(str, enum.Enum):
    AGE = "age"
    DUE_DATE = "due_date"
    HEIGHT_IN = "height"
    WEIGHT_LB = "weight"
    RACIAL_IDENTITY = "racial_identity"


class ModifiedReason(str, enum.Enum):
    GDM_STATUS_UPDATE = "GDM Status Update"
    HDC_ASSESSMENT_IMPORT = "HDC Assessment Import"
    PREGNANCY_ONBOARDING = "Pregnancy Onboarding"
    PREGNANCY_UPDATE = "Pregnancy Update"
