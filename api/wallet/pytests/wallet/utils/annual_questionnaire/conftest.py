from wallet.utils.annual_questionnaire.models import DirectPaymentSurveyFields

HDHP_SURVEY_RESPONSE_JSON_ONE_HDHP = """
    {
      "annual_insurance_survey_trad_wallet_hdhp_survey_self_q": "yes",
      "annual_insurance_survey_trad_wallet_hdhp_survey_partner_q": "no", 
      "annual_insurance_survey_trad_wallet_hdhp_survey_q_health_pla_thru_employer": "both"
    }
    """

HDHP_SURVEY_RESPONSE_JSON_BOTH_HDHP = """
    {
      "annual_insurance_survey_trad_wallet_hdhp_survey_self_q": "yes",
      "annual_insurance_survey_trad_wallet_hdhp_survey_partner_q": "yes", 
      "annual_insurance_survey_trad_wallet_hdhp_survey_q_health_pla_thru_employer": "both"
    }
    """

HDHP_SURVEY_RESPONSE_JSON_NO_HDHP = """
    {
      "annual_insurance_survey_trad_wallet_hdhp_survey_self_q": "no",
      "annual_insurance_survey_trad_wallet_hdhp_survey_partner_q": "no", 
      "annual_insurance_survey_trad_wallet_hdhp_survey_q_health_pla_thru_employer": "both"
    }
    """

DP_RESPONSE_JSON_YES_SELF_INDIVIDUAL = """
{
  "annual_insurance_survey_dp_wallet_survey_q_01": "yes",
  "annual_insurance_survey_dp_wallet_survey_q_02": "INDIVIDUAL",
  "annual_insurance_survey_dp_wallet_survey_q_03": "MALE",
  "annual_insurance_survey_dp_wallet_survey_gp1_q_01": "12345654321",
  "annual_insurance_survey_dp_wallet_survey_gp1_q_02": " 1234568",
  "annual_insurance_survey_dp_wallet_survey_gp1_q_03": "CARDHOLDER",
  "annual_insurance_survey_dp_wallet_survey_gp1_q_04": "Dara",
  "annual_insurance_survey_dp_wallet_survey_gp1_q_05": "O'Brien",
  "annual_insurance_survey_dp_wallet_survey_gp1_q_06": "2000-01-01T05:00:00.000Z"
}"""
DP_RESPONSE_JSON_NO_DEP_EMPLOYEE_PLUS = """
{
  "annual_insurance_survey_dp_wallet_survey_q_01": "no",
  "annual_insurance_survey_dp_wallet_survey_q_02": "EMPLOYEE_PLUS",
  "annual_insurance_survey_dp_wallet_survey_q_03": "FEMALE",
  "annual_insurance_survey_dp_wallet_survey_gp1_q_01": "9009009 ",
  "annual_insurance_survey_dp_wallet_survey_gp1_q_02": "12A34_568G ",
  "annual_insurance_survey_dp_wallet_survey_gp1_q_03": "SPOUSE",
  "annual_insurance_survey_dp_wallet_survey_gp1_q_04": "Fern",
  "annual_insurance_survey_dp_wallet_survey_gp1_q_05": "Brady",
  "annual_insurance_survey_dp_wallet_survey_gp1_q_06": "1990-02-03"
}"""
DP_RESPONSE_JSON_YES_SELF_INDIVIDUAL_NOT_HDHP = """
{
  "annual_insurance_survey_dp_wallet_survey_q_01": "no",
  "annual_insurance_survey_dp_wallet_survey_q_02": "INDIVIDUAL",
  "annual_insurance_survey_dp_wallet_survey_q_03": "UNKNOWN",
  "annual_insurance_survey_dp_wallet_survey_gp1_q_01": "12345654321",
  "annual_insurance_survey_dp_wallet_survey_gp1_q_02": " 1234*+568!",
  "annual_insurance_survey_dp_wallet_survey_gp1_q_03": "CARDHOLDER",
  "annual_insurance_survey_dp_wallet_survey_gp1_q_04": "John",
  "annual_insurance_survey_dp_wallet_survey_gp1_q_05": "Kearns",
  "annual_insurance_survey_dp_wallet_survey_gp1_q_06": "2000-01-01T05:00:00.000Z"
}"""
DP_RESPONSE_JSON_NO_DEP_EMPLOYEE_PLUS_AMAZON = """
{
  "annual_insurance_survey_dp_wallet_survey_q_01": "no",
  "annual_insurance_survey_dp_wallet_survey_q_02_amazon": "EMPLOYEE_PLUS",
  "annual_insurance_survey_dp_wallet_survey_q_03": "FEMALE",
  "annual_insurance_survey_dp_wallet_survey_gp1_q_01": "9009009 ",
  "annual_insurance_survey_dp_wallet_survey_amazon_gp1_q_02": "12A34_568G ",
  "annual_insurance_survey_dp_wallet_survey_gp1_q_03": "SPOUSE",
  "annual_insurance_survey_dp_wallet_survey_gp1_q_04": "Sarah",
  "annual_insurance_survey_dp_wallet_survey_gp1_q_05": "Millican",
  "annual_insurance_survey_dp_wallet_survey_gp1_q_06": "1990-02-03"
}"""
DP_RESPONSE_JSON_YES_SELF_INDIVIDUAL_OHIO = """
{
  "annual_insurance_survey_dp_wallet_survey_q_01": "yes",
  "annual_insurance_survey_dp_wallet_survey_q_02_ohio": "INDIVIDUAL",
  "annual_insurance_survey_dp_wallet_survey_q_03": "MALE",
  "annual_insurance_survey_dp_wallet_survey_gp1_q_01": "12345654321",
  "annual_insurance_survey_dp_wallet_survey_gp1_q_02": " 1234568",
  "annual_insurance_survey_dp_wallet_survey_gp1_q_03": "CARDHOLDER",
  "annual_insurance_survey_dp_wallet_survey_gp1_q_04": "Munya",
  "annual_insurance_survey_dp_wallet_survey_gp1_q_05": "Chawawa",
  "annual_insurance_survey_dp_wallet_survey_gp1_q_06": "2000-01-01T05:00:00.000Z"
}"""
DP_RESPONSE_JSON_YES_SELF_INDIVIDUAL_BAD_MHP = """
{
  "annual_insurance_survey_dp_wallet_survey_q_01": "yes",
  "annual_insurance_survey_dp_wallet_survey_q_02": "INDIVIDUAL",
  "annual_insurance_survey_dp_wallet_survey_q_03": "MALE",
  "annual_insurance_survey_dp_wallet_survey_gp1_q_01": "12345654321",
  "annual_insurance_survey_dp_wallet_survey_gp1_q_02": "##$$$%%_)()*!!",
  "annual_insurance_survey_dp_wallet_survey_gp1_q_03": "CARDHOLDER",
  "annual_insurance_survey_dp_wallet_survey_gp1_q_04": "Julian ",
  "annual_insurance_survey_dp_wallet_survey_gp1_q_05": "Clary",
  "annual_insurance_survey_dp_wallet_survey_gp1_q_06": "2000-01-01T05:00:00.000Z"
}"""


DP_RESPONSE_DICT_YES_SELF_INDIVIDUAL = {
    DirectPaymentSurveyFields.IS_HDHP: "yes",
    DirectPaymentSurveyFields.COVERED_MEMBERS: "INDIVIDUAL",
    DirectPaymentSurveyFields.PATIENT_SEX: "MALE",
    DirectPaymentSurveyFields.PAYER_PLAN_NAME: "12345654321",
    DirectPaymentSurveyFields.INSURANCE_ID: "1234568",
    DirectPaymentSurveyFields.MEMBER_HEALTH_PLAN_PATIENT_RELATIONSHIP: "CARDHOLDER",
    DirectPaymentSurveyFields.FIRST_NAME: "Dara",
    DirectPaymentSurveyFields.LAST_NAME: "O'Brien",
    DirectPaymentSurveyFields.DOB: "2000-01-01",
}

DP_RESPONSE_DICT_NO_DEP_EMPLOYEE_PLUS = {
    DirectPaymentSurveyFields.IS_HDHP: "no",
    DirectPaymentSurveyFields.COVERED_MEMBERS: "EMPLOYEE_PLUS",
    DirectPaymentSurveyFields.PATIENT_SEX: "FEMALE",
    DirectPaymentSurveyFields.PAYER_PLAN_NAME: "9009009",
    DirectPaymentSurveyFields.INSURANCE_ID: "12A34568G",
    DirectPaymentSurveyFields.MEMBER_HEALTH_PLAN_PATIENT_RELATIONSHIP: "SPOUSE",
    DirectPaymentSurveyFields.FIRST_NAME: "Fern",
    DirectPaymentSurveyFields.LAST_NAME: "Brady",
    DirectPaymentSurveyFields.DOB: "1990-02-03",
}

DP_RESPONSE_DICT_YES_SELF_INDIVIDUAL_NOT_HDHP = {
    DirectPaymentSurveyFields.IS_HDHP: "no",
    DirectPaymentSurveyFields.COVERED_MEMBERS: "INDIVIDUAL",
    DirectPaymentSurveyFields.PATIENT_SEX: "UNKNOWN",
    DirectPaymentSurveyFields.PAYER_PLAN_NAME: "12345654321",
    DirectPaymentSurveyFields.INSURANCE_ID: "1234568",
    DirectPaymentSurveyFields.MEMBER_HEALTH_PLAN_PATIENT_RELATIONSHIP: "CARDHOLDER",
    DirectPaymentSurveyFields.FIRST_NAME: "John",
    DirectPaymentSurveyFields.LAST_NAME: "Kearns",
    DirectPaymentSurveyFields.DOB: "2000-01-01",
}

DP_RESPONSE_DICT_NO_DEP_EMPLOYEE_PLUS_AMAZON = {
    DirectPaymentSurveyFields.IS_HDHP: "no",
    DirectPaymentSurveyFields.COVERED_MEMBERS_AMAZON: "EMPLOYEE_PLUS",
    DirectPaymentSurveyFields.PATIENT_SEX: "FEMALE",
    DirectPaymentSurveyFields.PAYER_PLAN_NAME: "9009009",
    DirectPaymentSurveyFields.INSURANCE_ID_AMAZON: "12A34568G",
    DirectPaymentSurveyFields.MEMBER_HEALTH_PLAN_PATIENT_RELATIONSHIP: "SPOUSE",
    DirectPaymentSurveyFields.FIRST_NAME: "Sarah",
    DirectPaymentSurveyFields.LAST_NAME: "Millican",
    DirectPaymentSurveyFields.DOB: "1990-02-03",
}

DP_RESPONSE_DICT_YES_SELF_INDIVIDUAL_OHIO = {
    DirectPaymentSurveyFields.IS_HDHP: "yes",
    DirectPaymentSurveyFields.COVERED_MEMBERS_OHIO: "INDIVIDUAL",
    DirectPaymentSurveyFields.PATIENT_SEX: "MALE",
    DirectPaymentSurveyFields.PAYER_PLAN_NAME: "12345654321",
    DirectPaymentSurveyFields.INSURANCE_ID: "1234568",
    DirectPaymentSurveyFields.MEMBER_HEALTH_PLAN_PATIENT_RELATIONSHIP: "CARDHOLDER",
    DirectPaymentSurveyFields.FIRST_NAME: "Munya",
    DirectPaymentSurveyFields.LAST_NAME: "Chawawa",
    DirectPaymentSurveyFields.DOB: "2000-01-01",
}
