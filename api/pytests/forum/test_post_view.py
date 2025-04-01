import json

from utils.cache import redis_client
from views.forum import PostsSchema, get_all_reply_counts

from .factories import PostFactory


class TestPostsResource:
    def test_get_posts_reply_counts(self, factories, client, api_helpers):
        redis_client().flushall()
        parent_post = PostFactory(anonymous=False)
        viewer = factories.EnterpriseUserFactory()
        practitioner = factories.PractitionerProfileFactory.create(
            user_id=factories.DefaultUserFactory.create().id
        )

        # Member response
        PostFactory(parent_id=parent_post.id)
        # Practitioner response
        PostFactory(anonymous=False, author=practitioner.user, parent_id=parent_post.id)
        res = client.get("/api/v1/posts", headers=api_helpers.json_headers(user=viewer))

        data = next(
            p for p in json.loads(res.data)["data"] if p["id"] == parent_post.id
        )
        assert data["reply_counts"]["members"] == 1
        assert data["reply_counts"]["practitioners"] == 1


class TestPostResource:
    def test_get_non_anonymous_post(self, factories, client, api_helpers):
        post = PostFactory(anonymous=False)
        viewer = factories.EnterpriseUserFactory()
        res = client.get(
            f"/api/v1/posts/{post.id}", headers=api_helpers.json_headers(user=viewer)
        )
        username = json.loads(res.data)["author"]["username"]
        assert username is not None
        assert username == post.author.username

    def test_get_anonymous_post(self, factories, client, api_helpers):
        post = PostFactory(anonymous=True)
        viewer = factories.EnterpriseUserFactory()
        res = client.get(
            f"/api/v1/posts/{post.id}", headers=api_helpers.json_headers(user=viewer)
        )
        assert json.loads(res.data)["author"] is None

    def test_get_post_reply_counts(self, factories, client, api_helpers):
        # Create parent post
        parent_post = PostFactory(anonymous=False)
        practitioner = factories.PractitionerProfileFactory.create(
            user_id=factories.DefaultUserFactory.create().id
        )
        viewer = factories.EnterpriseUserFactory()
        # Member response
        PostFactory(parent_id=parent_post.id)
        # Practitioner response
        PostFactory(anonymous=False, author=practitioner.user, parent_id=parent_post.id)

        res = client.get(
            f"/api/v1/posts/{parent_post.id}",
            headers=api_helpers.json_headers(user=viewer),
        )
        data = json.loads(res.data)
        assert data["author"]["username"] == parent_post.author.username
        assert data["reply_counts"]["members"] == 1
        assert data["reply_counts"]["practitioners"] == 1


class TestUserBookmarksResource:
    def test_get_bookmarks(self, factories, client, api_helpers):
        # Create parent post
        parent_post = PostFactory(anonymous=False)
        practitioner = factories.PractitionerProfileFactory.create(
            user_id=factories.DefaultUserFactory.create().id
        )
        # Create bookmark
        viewer = factories.EnterpriseUserFactory()
        parent_post.bookmarks.append(viewer)
        # Member response
        PostFactory(parent_id=parent_post.id)
        # Practitioner response
        PostFactory(anonymous=False, author=practitioner.user, parent_id=parent_post.id)

        res = client.get(
            "/api/v1/me/bookmarks", headers=api_helpers.json_headers(user=viewer)
        )
        bookmarks = json.loads(res.data)["data"]
        assert len(bookmarks) == 1
        assert bookmarks[0]["author"]["username"] == parent_post.author.username
        assert bookmarks[0]["reply_counts"]["members"] == 1
        assert bookmarks[0]["reply_counts"]["practitioners"] == 1


class TestPostsSchema:
    def test_posts_schema_post_dict(self):
        schema = PostsSchema()
        post = {
            "id": 3,
            "body": "i am a post",
            "has_bookmarked": False,
            "parent_id": 1,
            "bookmarks_count": 0,
            "anonymous": False,
            "author": {
                "id": 5,
                "first_name": "Thomas",
                "last_name": "Ortiz",
                "name": "Thomas Ortiz",
                "role": "practitioner",
                "profiles": {"practitioner": {"user_id": 5}},
            },
            "created_at": "2024-05-10T13:26:07",
            "title": "",
        }
        all_posts = {"data": [post]}
        reply_counts = {"members": 5, "practitioners": 3}
        schema.context["reply_counts"] = {post["id"]: reply_counts}

        response_data = schema.dump(all_posts)

        assert response_data["data"][0]["id"] == post["id"]
        assert response_data["data"][0]["author"]["id"] == post["author"]["id"]
        assert (
            response_data["data"][0]["reply_counts"]["members"]
            == reply_counts["members"]
        )
        assert (
            response_data["data"][0]["reply_counts"]["practitioners"]
            == reply_counts["practitioners"]
        )

    def test_posts_schema_post_model(self):
        schema = PostsSchema()
        post = PostFactory(anonymous=False)
        all_posts = {"data": [post]}
        reply_counts = {"members": 5, "practitioners": 3}
        schema.context["reply_counts"] = {post.id: reply_counts}

        response_data = schema.dump(all_posts)

        assert response_data["data"][0]["id"] == post.id
        assert response_data["data"][0]["author"]["id"] == post.author.id
        assert (
            response_data["data"][0]["reply_counts"]["members"]
            == reply_counts["members"]
        )
        assert (
            response_data["data"][0]["reply_counts"]["practitioners"]
            == reply_counts["practitioners"]
        )


def test_get_all_reply_counts_none():
    result = get_all_reply_counts(None)
    assert result == {}


def test_get_all_reply_counts(factories):
    parent_post = PostFactory(anonymous=False)
    practitioner = factories.PractitionerProfileFactory.create(
        user_id=factories.DefaultUserFactory.create().id
    )

    # Member response
    PostFactory(parent_id=parent_post.id)
    # Practitioner response
    PostFactory(anonymous=False, author=practitioner.user, parent_id=parent_post.id)

    result = get_all_reply_counts([parent_post.id])

    assert result[parent_post.id]["members"] == 1
    assert result[parent_post.id]["practitioners"] == 1
