from datetime import datetime, timedelta, timezone

from utils.cache import redis_client

from .factories import PostFactory


def create_test_post_with_replies(replies_count=0):
    post = PostFactory.create()
    if replies_count > 0:
        PostFactory.create_batch(size=replies_count, parent_id=post.id)
    return post


def test_get_posts_recommended_for_id(client, factories, api_helpers, mock_redis):
    mock_redis.get.return_value = None
    user = factories.EnterpriseUserFactory()

    response = client.get(
        "/api/v1/posts?recommended_for_id=123",
        headers=api_helpers.json_headers(user=user),
    )

    assert response.status_code == 200
    posts = response.json["data"]
    total = response.json["pagination"]["total"]
    assert len(posts) == 0
    assert total == 0


def test_get_posts_order_by_popular(client, factories, api_helpers, mock_redis):
    mock_redis.get.return_value = None
    now = datetime.utcnow()
    user = factories.EnterpriseUserFactory()
    post = create_test_post_with_replies(replies_count=3)
    post_1 = PostFactory.create(created_at=now)
    post_2 = create_test_post_with_replies(replies_count=2)
    post_3 = create_test_post_with_replies(replies_count=4)
    post_4 = PostFactory.create(created_at=now - timedelta(days=5))
    post_5 = PostFactory.create(created_at=now - timedelta(days=1))

    response = client.get(
        "/api/v1/posts?depth=0&order_by=popular",
        headers=api_helpers.json_headers(user=user),
    )

    assert response.status_code == 200
    posts = response.json["data"]
    assert [post["id"] for post in posts] == [
        post_3.id,
        post.id,
        post_2.id,
        post_1.id,
        post_5.id,
        post_4.id,
    ]


def test_get_posts_order_by_popular_secondary_sort(
    client, factories, api_helpers, mock_redis
):
    mock_redis.get.return_value = None
    redis_client().flushall()

    user = factories.EnterpriseUserFactory()
    now = datetime.now(timezone.utc)
    post_with_latest_reply = PostFactory.create()
    post_with_old_reply = PostFactory.create()

    PostFactory.create(
        parent_id=post_with_old_reply.id, created_at=now - timedelta(days=1)
    )
    PostFactory.create(parent_id=post_with_latest_reply.id, created_at=now)

    response = client.get(
        "/api/v1/posts?depth=0&order_by=popular",
        headers=api_helpers.json_headers(user=user),
    )

    assert response.status_code == 200
    posts = response.json["data"]
    assert [post["id"] for post in posts] == [
        post_with_latest_reply.id,
        post_with_old_reply.id,
    ]


def test_get_posts_order_by_popular_exclude_replies_gt_one_week(
    client, factories, api_helpers, mock_redis
):
    mock_redis.get.return_value = None
    post = PostFactory.create()
    PostFactory.create(parent_id=post.id)
    PostFactory.create(parent_id=post.id)

    post_with_old_reply = PostFactory.create()
    PostFactory.create(parent_id=post_with_old_reply.id)
    PostFactory.create(
        parent_id=post_with_old_reply.id,
        created_at=datetime.now(timezone.utc) - timedelta(days=8),
    )

    user = factories.EnterpriseUserFactory()
    response = client.get(
        "/api/v1/posts?depth=0&order_by=popular",
        headers=api_helpers.json_headers(user=user),
    )

    assert response.status_code == 200
    posts = response.json["data"]
    assert [post["id"] for post in posts] == [
        post.id,
        post_with_old_reply.id,
    ]
