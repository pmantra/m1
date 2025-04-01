from unittest.mock import patch

from pytests.forum.factories import PostFactory
from tasks.forum import send_braze_events_for_post_reply


@patch("models.forum.braze_events")
def test_braze_notifications_for_forum_one_reply(mock_braze_events):
    parent_post = PostFactory()
    reply = PostFactory(parent=parent_post)

    send_braze_events_for_post_reply(post_id=parent_post.id, replier_id=reply.author.id)
    mock_braze_events.notify_post_author_of_reply.assert_called_once_with(
        user=parent_post.author, post_id=parent_post.id
    )


@patch("models.forum.braze_events")
def test_braze_notifications_for_forum_two_replies(mock_braze_events):
    parent_post = PostFactory()
    reply1 = PostFactory(parent=parent_post)
    reply2 = PostFactory(parent=parent_post)

    send_braze_events_for_post_reply(
        post_id=parent_post.id, replier_id=reply2.author.id
    )
    mock_braze_events.notify_post_participant_of_reply.assert_called_once_with(
        user=reply1.author, post_id=parent_post.id
    )
