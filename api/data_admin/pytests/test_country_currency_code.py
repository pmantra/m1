from data_admin.makers.wallet import CountryCurrencyCodeMaker


def test_country_currency_code__successful():
    # Given
    country_currency_spec = {
        "country_alpha_2": "US",
        "currency_code": "USD",
        "minor_unit": 2,
    }

    # When
    country_currency = CountryCurrencyCodeMaker().create_object_and_flush(
        spec=country_currency_spec
    )

    # Then
    assert country_currency is not None
    assert country_currency.country_alpha_2 == "US"
    assert country_currency.currency_code == "USD"
    assert country_currency.minor_unit == 2
