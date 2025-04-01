from .factories import PostFactory


def test_post_bookmarks_self_post(client, factories, api_helpers):
    user = factories.EnterpriseUserFactory()
    post = PostFactory(author=user)

    response = client.post(
        f"/api/v1/posts/{post.id}/bookmarks",
        headers=api_helpers.json_headers(user=user),
    )

    assert response.status_code == 204


def test_post_bookmarks_duplicate_request(client, factories, api_helpers):
    user = factories.EnterpriseUserFactory()
    post = PostFactory(author=user)

    client.post(
        f"/api/v1/posts/{post.id}/bookmarks",
        headers=api_helpers.json_headers(user=user),
    )

    response = client.post(
        f"/api/v1/posts/{post.id}/bookmarks",
        headers=api_helpers.json_headers(user=user),
    )

    assert response.status_code == 409
    assert response.json["message"] == "You already followed that post!"
