import pytest

from learn.utils import disclaimers


def test_get_disclaimer_no_locale():
    result = disclaimers.get_disclaimer_by_locale(None)
    assert result == disclaimers.EN_DISCLAIMER


def test_get_disclaimer_unknown_locale():
    result = disclaimers.get_disclaimer_by_locale("🐶")
    assert result == disclaimers.EN_DISCLAIMER


@pytest.mark.parametrize(
    argnames=["locale_code", "disclaimer"],
    argvalues=[
        (disclaimers.Locale.EN, disclaimers.EN_DISCLAIMER),
        (disclaimers.Locale.EN_US, disclaimers.EN_DISCLAIMER),
        (disclaimers.Locale.ES, disclaimers.ES_DISCLAIMER),
        (disclaimers.Locale.ES_419, disclaimers.ES_DISCLAIMER),
        (disclaimers.Locale.FR, disclaimers.FR_DISCLAIMER),
        (disclaimers.Locale.FR_CA, disclaimers.FR_DISCLAIMER),
        (disclaimers.Locale.FR_FR, disclaimers.FR_DISCLAIMER),
        (disclaimers.Locale.HI_IN, disclaimers.HI_IN_DISCLAIMER),
        (disclaimers.Locale.IT_IT, disclaimers.IT_IT_DISCLAIMER),
        (disclaimers.Locale.JA_JP, disclaimers.JA_JP_DISCLAIMER),
        (disclaimers.Locale.PL_PL, disclaimers.PL_PL_DISCLAIMER),
        (disclaimers.Locale.PT_BR, disclaimers.PT_BR_DISCLAIMER),
    ],
)
def test_get_disclaimer_known_locale(locale_code, disclaimer):
    result = disclaimers.get_disclaimer_by_locale(locale_code)
    assert result == disclaimer
