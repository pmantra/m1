import enum

from sqlalchemy import (
    Boolean,
    Column,
    Enum,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import backref, joinedload, relationship

from authn.models.user import User
from utils import braze_events
from utils.cache import ViewCache, redis_client
from utils.log import logger

from .base import TimeLoggedModelBase, db

log = logger(__name__)

user_bookmarks = db.Table(
    "user_bookmarks",
    Column("user_id", Integer, ForeignKey("user.id")),
    Column("post_id", Integer, ForeignKey("post.id")),
    UniqueConstraint("user_id", "post_id"),
)

post_categories = db.Table(
    "post_categories",
    Column("category_id", Integer, ForeignKey("category.id")),
    Column("post_id", Integer, ForeignKey("post.id")),
    UniqueConstraint("category_id", "post_id"),
    Index("idx_post_category", "post_id"),
)

post_phases = db.Table(
    "post_phases",
    Column("phase_id", Integer, ForeignKey("phase.id")),
    Column("post_id", Integer, ForeignKey("post.id")),
    UniqueConstraint("phase_id", "post_id"),
    Index("idx_post_phase", "post_id"),
)


class PostSpamStatus(enum.Enum):
    NONE = "NONE"
    NEEDS_REVIEW = "NEEDS_REVIEW"
    SPAM = "SPAM"


class Vote(TimeLoggedModelBase):
    __tablename__ = "vote"
    constraints = (
        UniqueConstraint("post_id", "user_id"),
        Index("idx_post_votes", "post_id"),
    )

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("user.id"), nullable=False)
    user = relationship("User", backref="votes")
    post_id = Column(Integer, ForeignKey("post.id", ondelete="CASCADE"), nullable=False)
    post = relationship(
        "Post",
        backref=backref(
            "votes",
            cascade="all, delete-orphan",
            passive_deletes=True,
            single_parent=True,
        ),
    )

    value = Column(Integer)

    def __repr__(self) -> str:
        return f"<Vote {self.id} ({self.value} by user {self.user_id}/post {self.post_id})>"

    __str__ = __repr__


class Post(TimeLoggedModelBase):
    __tablename__ = "post"
    __calculated_columns__ = frozenset(["net_votes"])

    constraints = (
        Index("idx_post_author", "author_id"),
        Index("idx_parent_id", "parent_id"),
    )

    priorities = ("HIGH", "MEDIUM", "LOW")

    id = Column(Integer, primary_key=True)

    author_id = Column(Integer, ForeignKey("user.id"), nullable=False)
    author = relationship("User", backref="posts")
    anonymous = Column(Boolean, nullable=False, default=True)

    title = Column(String(140), nullable=True)
    body = Column(Text)

    parent_id = Column(Integer, ForeignKey("post.id"), nullable=True)
    parent = relationship("Post", backref="children", remote_side="Post.id")

    sticky_priority = Column(
        Enum(*priorities, name="sticky_priority"), nullable=True, default="LOW"
    )

    bookmarks = relationship("User", backref="bookmarks", secondary=user_bookmarks)
    categories = relationship("Category", backref="posts", secondary=post_categories)
    phases = relationship("Phase", backref="posts", secondary=post_phases)

    # Spam-prevention fields
    spam_status = Column(
        Enum(PostSpamStatus), nullable=False, default=PostSpamStatus.NONE
    )

    def __repr__(self) -> str:
        return f"<Post {self.id} (Parent {self.parent_id}) [{self.created_at}]>"

    __str__ = __repr__

    @property
    def replies(self):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        return self.query.filter(self.__class__.parent_id == self.id)

    @property
    def depth(self):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        """How deep is this node? Starts at 0"""
        # TODO: denormalize? this is a very expensive chain of queries.
        return (self.parent.depth + 1) if self.parent else 0

    @property
    def bookmarks_count(self):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        return len(self.bookmarks)

    # There is no actual way to vote for a post; setting to 0 to avoid db calls
    @property
    def net_votes(self):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        return 0

    def user_has_bookmarked(self, user):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        return user.id in [u.id for u in self.bookmarks]

    def notify_author_and_other_participants(self, replier_id: int) -> None:
        """This can be impact latency and should always be called as part of a background task"""
        if self.author_id != replier_id:
            # Notify author of post that the post has a new reply,
            # if the new reply isn't also by the author
            braze_events.notify_post_author_of_reply(user=self.author, post_id=self.id)

        other_replies = Post.query.filter_by(parent_id=self.id).options(
            joinedload("author").load_only("id", "esp_id")
        )
        other_replies_not_by_author_or_replier = [
            r
            for r in other_replies
            if r.author.id != replier_id and r.author.id != self.author_id
        ]
        for reply in other_replies_not_by_author_or_replier:
            # Notify other participants on post that the post has a new reply,
            # excluding the author of the new reply and the author of the original post
            braze_events.notify_post_participant_of_reply(
                user=reply.author, post_id=self.id
            )


class PostsViewCache(ViewCache):
    id_namespace = "posts"


class UserPersonalizedPostsCache:
    def __init__(self, user):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        self.cache = redis_client()
        self.user = user

        self.votes_key = f"forum_cache_user_{self.user.id}_has_voted"
        self.bookmarks_key = f"forum_cache_user_{self.user.id}_has_bookmarked"

    def personalize(self, posts):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        _ids = [p["id"] for p in posts]
        has_bookmarked = self.has_bookmarked(_ids)

        for post in posts:
            # There is no actual way to vote for a post; setting to 0 to avoid db calls
            post["has_voted"] = False
            post["has_bookmarked"] = has_bookmarked.get(post["id"])

        return posts

    @classmethod
    def unpersonalize(cls, posts):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        """
        Undo the personalization of cache results for public views
        :param posts: personalized result
        :return: unpersonalized result
        """
        for post in posts["data"]:
            post["has_voted"] = False
            post["has_bookmarked"] = False

        return posts

    def has_bookmarked(self, ids):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        pipeline = self.cache.pipeline()
        for id in ids:
            pipeline.sismember(self.bookmarks_key, id)
        bookmarks = pipeline.execute()
        return {_: bookmarks[i] for i, _ in enumerate(ids)}

    def update_personalized(self):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        log.debug("Update personalized caches for %s", self.user)

        bookmarks_data = (
            db.session.query(user_bookmarks.c.post_id)
            .filter(user_bookmarks.c.user_id == self.user.id)
            .all()
        )
        bookmarked_post_ids = [row[0] for row in bookmarks_data]

        self.update_key_by_ids(self.bookmarks_key, bookmarked_post_ids)

    def update_key_by_ids(self, key, post_ids):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        pipeline = self.cache.pipeline()

        pipeline.delete(key)
        for _id in post_ids:
            pipeline.sadd(key, _id)
        pipeline.expire(key, (24 * 60 * 60))
        log.debug("Updated %s with %d posts", key, len(post_ids))
        return pipeline.execute()

    def add_vote(self, post_id):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        return self.cache.sadd(self.votes_key, post_id)

    def add_bookmark(self, post_id):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        return self.cache.sadd(self.bookmarks_key, post_id)

    def remove_vote(self, post_id):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        return self.cache.srem(self.votes_key, post_id)

    def remove_bookmark(self, post_id):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        return self.cache.srem(self.bookmarks_key, post_id)


class ForumBan(TimeLoggedModelBase):
    __tablename__ = "forum_ban"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("user.id"), nullable=False)
    user = relationship("User", foreign_keys=[user_id])
    created_by_user_id = Column(Integer, ForeignKey("user.id"), nullable=True)
    created_by_user = relationship("User", foreign_keys=[created_by_user_id])

    @classmethod
    def by_user(cls, user):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        return db.session.query(cls).filter(cls.user_id == user.id)

    @classmethod
    def is_user_banned(cls, user: User):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        return cls.by_user(user).count() > 0
