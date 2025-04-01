from __future__ import annotations

from authn.domain import model, repository
from authn.services.integrations import saml


def fetch_identity_providers() -> list[model.IdentityProvider]:
    """Fetch IDPs from the os environment."""
    config = saml.get_onelogin_configuration()
    idps = [
        model.IdentityProvider(name=name, metadata=metadata)
        for name, metadata in config.idp_metadata.items()
    ]
    return idps


def save_identity_providers(idps: list[model.IdentityProvider], *, commit: bool = True):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
    """Store the provided IDPs in the database."""
    repo = repository.IdentityProviderRepository()
    saved = [repo.create(instance=idp) for idp in idps]
    if commit:
        repo.session.commit()
    return saved


def migrate_identity_providers(*, commit: bool = True) -> list[model.IdentityProvider]:
    """Migrate IDP configuration from the environ to the database."""
    idps = fetch_identity_providers()
    saved = save_identity_providers(idps, commit=commit)
    return saved
