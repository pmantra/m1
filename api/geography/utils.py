from geography import repository as geography_repository


def validate_country_code(country_code: str) -> str:
    countries = geography_repository.CountryRepository()
    verified_country = countries.get(country_code=country_code)

    if not verified_country:
        raise ValueError(
            f"'{country_code}' is not a valid ISO 3166-1 alpha-2 country code"
        )
    return country_code
