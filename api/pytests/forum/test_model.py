from unittest.mock import patch

from .factories import PostFactory


@patch("models.forum.braze_events")
def test_notify_author_when_replier_is_author(braze_events_mock):
    post = PostFactory()
    # Reply by author to own post
    reply = PostFactory(parent=post, author=post.author)

    post.notify_author_and_other_participants(reply.author.id)
    braze_events_mock.notify_post_author_of_reply.assert_not_called()


@patch("models.forum.braze_events")
def test_notify_author_when_replier_is_not_author(braze_events_mock):
    post = PostFactory()
    # Reply by someone else
    reply = PostFactory(parent=post)

    post.notify_author_and_other_participants(reply.author.id)
    braze_events_mock.notify_post_author_of_reply.assert_called_with(
        user=post.author, post_id=post.id
    )


@patch("models.forum.braze_events")
def test_notify_participants_when_its_the_same_replier(braze_events_mock):
    post = PostFactory()
    # Same person replying twice
    reply1 = PostFactory(parent=post)
    reply2 = PostFactory(parent=post, author=reply1.author)

    post.notify_author_and_other_participants(reply2.author.id)
    braze_events_mock.notify_post_participant_of_reply.assert_not_called()


@patch("models.forum.braze_events")
def test_notify_participants_when_different_replier(braze_events_mock):
    post = PostFactory()  # Replies by two different people
    reply1 = PostFactory(parent=post)
    reply2 = PostFactory(parent=post)

    post.notify_author_and_other_participants(reply2.author.id)
    # Notify the author of reply 1 that there was another reply by someone else
    braze_events_mock.notify_post_participant_of_reply.assert_called_with(
        user=reply1.author, post_id=post.id
    )


@patch("models.forum.braze_events")
def test_notify_participants_but_not_author_twice(braze_events_mock, factories):
    post = PostFactory()
    # Reply by author to own post
    PostFactory(parent=post, author=post.author)
    # Reply by someone else
    reply = PostFactory(parent=post)

    post.notify_author_and_other_participants(reply.author.id)
    # Test that author didn't get two notifications
    braze_events_mock.notify_post_author_of_reply.assert_called_with(
        user=post.author, post_id=post.id
    )
    braze_events_mock.notify_post_participant_of_reply.assert_not_called()
