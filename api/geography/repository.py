from __future__ import annotations

import dataclasses

import pycountry
import sqlalchemy.orm.scoping
from flask_babel import gettext
from maven import feature_flags

from geography.models.country_metadata import CountryMetadata
from storage import connection

__all__ = (
    "CountryRepository",
    "SubdivisionRepository",
    "Country",
    "Subdivision",
)


def convert_pycountry_to_country(country: pycountry.db.Database) -> Country | None:
    if not country:
        return None

    mapped_country = Country(
        alpha_2=country.alpha_2,
        alpha_3=country.alpha_3,
        name=country.name,
        official_name=getattr(country, "official_name", None),
        common_name=getattr(country, "common_name", None),
    )

    overrode_country = override_pycountry_defaults(mapped_country)

    localization_enabled = feature_flags.bool_variation(
        "release-pycountry-localization",
        default=False,
    )

    if localization_enabled:
        return localize_country(overrode_country)

    return overrode_country


def override_pycountry_defaults(country: Country) -> Country:
    """
    See EPEN-2738 for more context
    """
    if country.alpha_2 == "TW":
        return Country(
            alpha_2=country.alpha_2,
            alpha_3=country.alpha_3,
            name="Taiwan",
        )
    return country


def localize_country(country: Country) -> Country:
    return Country(
        alpha_2=country.alpha_2,
        alpha_3=country.alpha_3,
        name=gettext(country.name) if country.name else None,
        official_name=gettext(country.official_name) if country.official_name else None,
        common_name=gettext(country.common_name) if country.common_name else None,
    )


class CountryRepository:
    def __init__(self, session: sqlalchemy.orm.scoping.ScopedSession = None):  # type: ignore[assignment] # Incompatible default for argument "session" (default has type "None", argument has type "scoped_session")
        self.session = session or connection.db.session

    def get(self, *, country_code: str) -> Country | None:  # type: ignore[return] # Missing return statement
        if not country_code:
            return  # type: ignore[return-value] # Return value expected

        if country := pycountry.countries.get(alpha_2=country_code):
            return convert_pycountry_to_country(country)

    def get_by_name(self, *, name: str) -> Country | None:
        try:
            country = pycountry.countries.lookup(name)
            return convert_pycountry_to_country(country)
        except LookupError:
            return  # type: ignore[return-value] # Return value expected

    def get_by_subdivision_code(self, *, subdivision_code: str) -> Country | None:
        if not subdivision_code:
            return  # type: ignore[return-value] # Return value expected

        country_code = subdivision_code.split("-")[0]
        return self.get(country_code=country_code)

    def all(self) -> list[Country]:
        return [
            convert_pycountry_to_country(country) for country in pycountry.countries
        ]

    def get_metadata(self, *, country_code: str) -> CountryMetadata | None:
        if not country_code:
            return  # type: ignore[return-value] # Return value expected

        return (
            self.session.query(CountryMetadata)
            .filter_by(country_code=country_code)
            .one_or_none()
        )

    def create_metadata(
        self,
        *,
        country_code: str,
        ext_info_link: str,
        summary: str,
        emoji: str = None,  # type: ignore[assignment] # Incompatible default for argument "emoji" (default has type "None", argument has type "str")
    ) -> CountryMetadata:
        metadata = CountryMetadata(
            country_code=country_code,
            ext_info_link=ext_info_link,
            summary=summary,
            emoji=emoji,
        )
        self.session.add(metadata)
        self.session.flush()
        return metadata


def convert_pycountry_subdivision_to_subdivision(
    subdivision: pycountry.Subdivision,
) -> Subdivision | None:
    if not subdivision:
        return None

    mapped_subdivision = Subdivision(
        code=subdivision.code,
        country_code=subdivision.country_code,
        abbreviation=subdivision.code.split("-")[-1],
        name=subdivision.name,
        type=subdivision.type,
        parent_code=subdivision.parent_code,
    )

    localization_enabled = feature_flags.bool_variation(
        "release-pycountry-localization",
        default=False,
    )

    if localization_enabled:
        return localize_subdivision(mapped_subdivision)

    return mapped_subdivision


def localize_subdivision(subdivision: Subdivision) -> Subdivision:
    return Subdivision(
        code=subdivision.code,
        country_code=subdivision.country_code,
        abbreviation=subdivision.abbreviation,
        name=gettext(subdivision.name),
        type=subdivision.type,
        parent_code=subdivision.parent_code,
    )


class SubdivisionRepository:
    def __init__(self, session: sqlalchemy.orm.scoping.ScopedSession = None):  # type: ignore[assignment] # Incompatible default for argument "session" (default has type "None", argument has type "scoped_session")
        self.countries = CountryRepository(session=session)

    def get(self, *, subdivision_code: str) -> Subdivision | None:  # type: ignore[return] # Missing return statement
        if not subdivision_code:
            return  # type: ignore[return-value] # Return value expected

        if subdivision := pycountry.subdivisions.get(code=subdivision_code):
            return convert_pycountry_subdivision_to_subdivision(subdivision)
        elif subdivision_code == "US-ZZ":
            return Subdivision(
                code=subdivision_code,
                country_code="US",
                abbreviation="ZZ",
                name=gettext("geography_state_other"),
                type="MavenInternal",
            )

    def get_by_country_code_and_state(  # type: ignore[return] # Missing return statement
        self, *, country_code: str, state: str
    ) -> Subdivision | None:
        if not country_code and state:
            return  # type: ignore[return-value] # Return value expected

        if self.countries.get(country_code=country_code):
            return self.get(subdivision_code=f"{country_code}-{state}")

    def get_subdivisions_by_country_code(
        self, *, country_code: str
    ) -> list[Subdivision] | None:
        if not country_code:
            return  # type: ignore[return-value] # Return value expected

        subdivisions = pycountry.subdivisions.get(country_code=country_code)
        if subdivisions is None:
            return  # type: ignore[return-value] # Return value expected

        rv = [
            convert_pycountry_subdivision_to_subdivision(subdivision)
            for subdivision in sorted(subdivisions, key=lambda x: x.code)
        ]

        if country_code == "US":
            rv.append(
                Subdivision(
                    code="US-ZZ",
                    country_code="US",
                    abbreviation="ZZ",
                    name=gettext("geography_state_other"),
                    type="MavenInternal",
                )
            )
        return rv  # type: ignore[return-value] # Incompatible return value type (got "List[Optional[Subdivision]]", expected "Optional[List[Subdivision]]")

    def get_child_subdivisions(  # type: ignore[return] # Missing return statement
        self, *, subdivision_code: str
    ) -> list[Subdivision] | None:
        if not subdivision_code:
            return  # type: ignore[return-value] # Return value expected

        if subdivision := self.get(subdivision_code=subdivision_code):
            # get all subdivisions for this country
            if subdivisions := self.get_subdivisions_by_country_code(
                country_code=subdivision.country_code
            ):
                # get subdivisions whose parent_code is the original subdivision_suffix
                return [
                    child_subdivision
                    for child_subdivision in sorted(subdivisions, key=lambda x: x.code)
                    if child_subdivision.parent_code == subdivision.code
                ]


@dataclasses.dataclass(frozen=True)
class Country:
    alpha_2: str
    alpha_3: str
    name: str
    common_name: str | None = None
    official_name: str | None = None


@dataclasses.dataclass(frozen=True)
class Subdivision:
    code: str
    country_code: str
    abbreviation: str
    name: str
    type: str
    parent_code: str | None = None
