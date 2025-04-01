import pytest

from providers.domain import model
from providers.pytests import factories
from providers.repository.provider import ProviderRepository


@pytest.fixture
def provider_repository() -> ProviderRepository:
    return ProviderRepository()


@pytest.fixture
def created_provider() -> model.Provider:
    provider: model.Provider = factories.ProviderFactory.create()
    return provider


@pytest.fixture
def vertical_wellness_coach_can_prescribe(factories):
    vertical = factories.VerticalFactory.create(
        name="Wellness Coach",
        pluralized_display_name="Wellness Coaches",
        can_prescribe=True,
        filter_by_state=False,
        slug="wellness_coach",
    )

    return vertical


@pytest.fixture
def vertical_wellness_coach_cannot_prescribe(factories):
    vertical = factories.VerticalFactory.create(
        name="Wellness Coach",
        pluralized_display_name="Wellness Coaches",
        can_prescribe=False,
        filter_by_state=False,
        slug="wellness_coach",
    )

    return vertical
