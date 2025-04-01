from unittest.mock import patch

from pytests.factories import EnterpriseUserFactory
from pytests.forum.factories import PostFactory


@patch("models.forum.braze_events")
@patch("views.forum.send_braze_events_for_post_reply")
def test_notify_author_when_replier_is_not_author(
    send_braze_events_for_post_reply, forum_braze_events, client, api_helpers
):
    parent_post = PostFactory()
    user = EnterpriseUserFactory()

    response = client.post(
        "/api/v1/posts",
        json={
            "body": "This is a reply",
            "anonymous": False,
            "parent_id": parent_post.id,
        },
        headers=api_helpers.json_headers(user=user),
    )

    assert response.status_code == 201
    send_braze_events_for_post_reply.delay.assert_called_once_with(
        post_id=parent_post.id, replier_id=user.id
    )
    forum_braze_events.notify_post_author_of_reply.assert_not_called()
