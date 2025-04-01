import pytest

from models.profiles import AgreementNames


@pytest.fixture
def english(factories):
    return factories.LanguageFactory.create(
        name="English",
        iso_639_3="eng",
    )


@pytest.fixture
def spanish(factories):
    return factories.LanguageFactory.create(
        name="Spanish",
        iso_639_3="spa",
    )


@pytest.fixture
def privacy_english(factories, english):
    return factories.AgreementFactory.create(
        name=AgreementNames.PRIVACY_POLICY,
        version=1,
        language_id=english.id,
    )


@pytest.fixture
def privacy_spanish(factories, spanish):
    return factories.AgreementFactory.create(
        name=AgreementNames.PRIVACY_POLICY,
        version=1,
        language_id=spanish.id,
    )


@pytest.fixture
def privacy_no_language(factories, english):
    return factories.AgreementFactory.create(
        name=AgreementNames.PRIVACY_POLICY,
        version=1,
    )
