from unittest import mock

import pytest


@pytest.mark.parametrize("localization_flag", [True, False])
@pytest.mark.parametrize("should_localize", [True, False])
@pytest.mark.parametrize("locale", ["en", "es"])
def test_marketing_name(
    factories, ff_test_data, localization_flag, should_localize, locale
):
    vertical = factories.VerticalFactory(slug="obgyn")
    with mock.patch("l10n.config.negotiate_locale", return_value=locale):
        ff_test_data.update(
            ff_test_data.flag("release-mono-api-localization").variation_for_all(
                localization_flag
            )
        )
        marketing_name = vertical.get_marketing_name(should_localize=should_localize)
        if localization_flag and should_localize and locale != "en":
            assert marketing_name != "vertical_obgyn_display_name"
            assert marketing_name != "OB-GYN"

        else:
            assert marketing_name == "OB-GYN"
