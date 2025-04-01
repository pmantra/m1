from unittest import mock

import pytest

from authn.domain import model
from authn.scripts import migrate_identity_providers as migrate_idps
from authn.scripts import migrate_idp_field_aliases as migrate_field_aliases


@pytest.mark.parametrize(argnames="commit", argvalues=[True, False])
def test_migrate_identity_providers(commit, patch_idp_environ, mock_idp_repository):
    # Given
    name, metadata = patch_idp_environ
    idps = [model.IdentityProvider(name=name, metadata=metadata)]
    expected_calls = [mock.call(instance=i) for i in idps]
    # When
    migrate_idps.migrate_identity_providers(commit=commit)
    calls = mock_idp_repository.create.call_args_list
    # Then
    assert calls == expected_calls
    assert mock_idp_repository.session.commit.called == commit


@pytest.mark.parametrize(argnames="commit", argvalues=[True, False])
def test_migrate_idp_field_aliases(
    commit,
    patch_idp_environ,
    mock_idp_field_alias_repository,
    mock_idp_repository,
):
    # Given
    name, metadata = patch_idp_environ
    fields = migrate_field_aliases._IDP_FIELD_MAPPINGS[name]
    idp = model.IdentityProvider(id=1, name=name, metadata=metadata)
    field_aliases = [
        model.IdentityProviderFieldAlias(field=f, alias=a, identity_provider_id=idp.id)
        for f, a in fields.items()
    ]
    mock_idp_repository.get_by_name.side_effect = lambda *, name: (
        idp if name == idp.name else None
    )
    expected_calls = [mock.call(instance=fa) for fa in field_aliases]
    # When
    migrate_field_aliases.migrate_field_mappings(commit=commit)
    calls = mock_idp_field_alias_repository.create.call_args_list
    # Then
    assert calls == expected_calls
    assert mock_idp_field_alias_repository.session.commit.called == commit
