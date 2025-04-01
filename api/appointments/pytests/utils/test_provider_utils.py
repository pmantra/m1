import pytest

from appointments.utils.provider import get_provider_country_flag


class TestCountryFlag:
    @pytest.mark.parametrize(
        argnames="country_code,include_filtered_flags,country_flag",
        argvalues=(
            ("BR", False, "🇧🇷"),
            ("CH", False, "🇨🇭"),
            ("GB", False, "🇬🇧"),
            ("IN", False, "🇮🇳"),
            ("IS", False, "🇮🇸"),
            ("JP", False, "🇯🇵"),
            ("MX", False, "🇲🇽"),
            ("SE", False, "🇸🇪"),
            ("US", True, "🇺🇸"),
            ("US", False, ""),
            ("", False, ""),
            ("", True, ""),
        ),
    )
    def test_get_country_flags(
        self, country_code, include_filtered_flags, country_flag
    ):
        assert (
            get_provider_country_flag(country_code, include_filtered_flags)
            == country_flag
        )
