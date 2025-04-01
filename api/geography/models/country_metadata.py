from sqlalchemy import Column, Integer, String, Text
from sqlalchemy.orm import validates

from models.base import TimeLoggedModelBase

from ..utils import validate_country_code


class CountryMetadata(TimeLoggedModelBase):
    __tablename__ = "country_metadata"

    id = Column(Integer, primary_key=True)
    country_code = Column(String(2), nullable=False, unique=True)
    emoji = Column(String(4))
    ext_info_link = Column(String(255))
    summary = Column(Text)

    def __repr__(self) -> str:
        return f"<CountryMetadata[{self.country_code}]>"

    @validates("country_code")
    def validate_country_code(self, key, country_code):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        return validate_country_code(country_code)
