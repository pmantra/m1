from providers.domain.model import Provider
from providers.repository.provider import ProviderRepository


def test_get_by_user_id(
    provider_repository: ProviderRepository, created_provider: Provider
):
    # Given
    user_id = created_provider.user_id
    # When
    fetched = provider_repository.get_by_user_id(user_id=user_id)
    # Then
    assert fetched == created_provider


def get_by_user_ids(
    provider_repository: ProviderRepository, created_provider: Provider
):
    # Given
    user_id = created_provider.user_id
    # When
    fetched = provider_repository.get_by_user_ids([user_id])
    # Then
    assert len(fetched) == 1
    assert fetched[0] == created_provider
