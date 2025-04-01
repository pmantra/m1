import pytest


@pytest.mark.parametrize(
    argnames=(
        "method",
        "route",
    ),
    argvalues=[
        ("get", "api/v1/posts"),
        ("post", "api/v1/posts"),
        ("get", "api/v1/posts/1"),
        ("post", "api/v1/posts/1/bookmarks"),
        ("delete", "api/v1/posts/1/bookmarks"),
        ("get", "api/v1/me/bookmarks"),
    ],
)
def test_marketplace_user_cannot_access(
    default_user, client, api_helpers, method, route
):
    res = getattr(client, method)(
        route, headers=api_helpers.json_headers(user=default_user)
    )
    assert res.status_code == 403
