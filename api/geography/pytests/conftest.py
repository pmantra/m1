import pytest

from geography import repository


@pytest.fixture
def country_repository(session):
    return repository.CountryRepository(session=session)


@pytest.fixture
def subdivision_repository(session):
    return repository.SubdivisionRepository(session=session)
