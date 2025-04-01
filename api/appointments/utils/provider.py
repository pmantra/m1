# Distance between alpha codes and emoji codes
OFFSET = 127397
FILTERED_COUNTRY_CODES = ["US"]


def get_provider_country_flag(country_code, should_include_filtered_flags=False):  # type: ignore[no-untyped-def] # Function is missing a type annotation
    if country_code in FILTERED_COUNTRY_CODES and not should_include_filtered_flags:
        return ""

    return (
        chr(ord(country_code[0]) + OFFSET) + chr(ord(country_code[1]) + OFFSET)
        if country_code
        else ""
    )
