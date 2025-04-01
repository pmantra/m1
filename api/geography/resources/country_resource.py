from common.services.api import UnauthenticatedResource
from geography import CountryRepository
from geography.schemas.country_schema import CountrySchema


class CountryResource(UnauthenticatedResource):
    def get(self):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        schema = CountrySchema()
        countries = CountryRepository()
        country_data = countries.all()
        usa = list(filter(lambda c: c.alpha_2 == "US", country_data))[0]
        country_data.remove(usa)
        country_data.insert(0, usa)
        return schema.dump(country_data, many=True)
