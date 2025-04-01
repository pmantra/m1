import pytest

from authz.services.scope import user_has_any_scope


@pytest.mark.parametrize(
    argnames="allowed_scopes,expected",
    argvalues=[
        ([], True),
        (["maven-internal-secrets"], True),
        (["maven-external-secrets"], False),
    ],
    ids=[
        "no scopes needed",
        "scope matches one of the user scopes",
        "scope not in user's scopes",
    ],
)
def test_user_has_any_scope(auth_user, allowed_scopes, expected):
    assert user_has_any_scope(auth_user, allowed_scopes) == expected
