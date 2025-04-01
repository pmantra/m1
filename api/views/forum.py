from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List

from flask import request
from flask_restful import abort
from redset.exceptions import LockTimeout
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import aliased, joinedload
from sqlalchemy.orm.exc import NoResultFound
from sqlalchemy.sql import func

from authn.models.user import User
from authz.models.roles import ROLES
from common.services.api import EnterpriseOrProviderResource, authenticate
from models.forum import (
    ForumBan,
    Post,
    PostSpamStatus,
    PostsViewCache,
    UserPersonalizedPostsCache,
    post_categories,
    user_bookmarks,
)
from models.forums.categories import get_category_groups_for_user
from models.profiles import (
    Category,
    CategoryVersion,
    MemberProfile,
    PractitionerProfile,
)
from storage.connection import db
from tasks.forum import send_braze_events_for_post_reply
from tasks.notifications import notify_about_new_post
from utils.cache import RedisLock
from utils.log import logger
from utils.recaptcha import ActionName, get_recaptcha_key, get_recaptcha_score
from utils.service_owner_mapper import service_ns_team_mapper
from views.schemas.base import PaginableArgsSchemaV3
from views.schemas.forum import PostSchema, PostsGetSchema, PostsSchema

log = logger(__name__)

MAX_POST_DEPTH = 1
ALLOWED_POSTS_PER_DAY = 5


class PostOrder:
    created_at = "created_at"
    replies = "replies"
    popular = "popular"


class PostsResource(EnterpriseOrProviderResource):
    def get(self):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        self.init_timer()
        self._user_is_enterprise_or_provider_else_403()
        self.cache = PostsViewCache(self.cache_key)

        args_schema = PostsGetSchema()
        args = args_schema.load(request.args)
        self.timer("args_time")

        protect_practitioner_anonymous_messages = False
        schema = PostsSchema()

        if args.get("author_ids"):
            # use the read replica, for consistency with _load_from_db
            authors = (
                db.s_replica1.query(User).filter(User.id.in_(args["author_ids"])).all()
            )
            for user in authors:
                if not user.is_practitioner and (
                    not self.user or (self.user and self.user.id != user.id)
                ):
                    # Return empty response if unauthorized
                    schema.context["user"] = None
                    return schema.dump(self._empty_response(args))
                elif user.is_practitioner and (
                    not self.user or (self.user and self.user.id != user.id)
                ):
                    protect_practitioner_anonymous_messages = True

        all_posts, total = self._load_from_cache()
        self.timer("check_cache_time")

        warm_cache = False
        if (all_posts is None) or (total is None):
            log.debug(f"Loading posts from DB: {total} -- {all_posts}")
            posts_from_db, total = self._load_from_db(
                args, protect_practitioner_anonymous_messages
            )

            if posts_from_db:
                warm_cache = True

            all_posts = self._empty_response(args)
            all_posts["data"] = posts_from_db
            all_posts["pagination"]["total"] = total

        schema.context["reply_counts"] = get_all_reply_counts(
            self._get_all_post_ids(all_posts["data"])
        )
        schema.context["include_parent"] = args.get("include_parent")
        if self.user:
            schema.context["user"] = self.user
        else:
            schema.context["user"] = None
        res = schema.dump(all_posts)
        self.timer("serialize_time")

        if warm_cache:
            self._warm_cache(res)

        self.timer("finish_time")
        return res

    def _get_all_post_ids(self, all_posts):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        post_ids = []
        for post in all_posts:
            if isinstance(post, dict):
                post_ids.append(post["id"])
            else:
                post_ids.append(post.id)
        return post_ids

    def _empty_response(self, args):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        return {
            "data": [],
            "pagination": {
                "limit": args["limit"],
                "offset": args["offset"],
                "total": 0,
                "order_by": args["order_by"],
                "order_direction": args["order_direction"],
            },
        }

    def _load_from_cache(self):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        results = self.cache.get()
        self.timer("cache_get")

        if results:
            if self.user:
                personalizer = UserPersonalizedPostsCache(self.user)
                results["data"] = personalizer.personalize(results["data"])
                self.timer("cache_personalize")

            return results, results.get("pagination", {}).get("total")
        else:
            log.debug("No results from cache for: %s", self.cache.uri)
            return None, None

    def _load_from_db(self, args, protect_practitioner_anonymous_messages):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        # use the read replica
        session = db.s_replica1
        posts = session.query(Post).options(
            joinedload(Post.categories),
            joinedload(Post.bookmarks),
            joinedload(Post.author),
        )

        # Prevent spam posts from appearing
        posts = posts.filter(Post.spam_status != PostSpamStatus.SPAM)

        if args["recommended_for_id"] not in (0, None):
            # This query param is deprecated, but still passed in by older iOS clients
            # Ticket to remove the iOS code is here https://mavenclinic.atlassian.net/browse/COCO-3951
            # and we can monitor that release to determine when it is safe to remove this param
            return [], 0
        elif args["order_by"] == PostOrder.replies:
            replies = aliased(Post)
            stmt = (
                session.query(replies, func.count(replies.id).label("reply_count"))
                .group_by(replies.parent_id)
                .subquery()
            )
            posts = posts.outerjoin(stmt, Post.id == stmt.c.parent_id)
            posts = posts.order_by(
                getattr(stmt.c.reply_count, args["order_direction"])()
            )
        elif args["order_by"] == PostOrder.popular:
            replies = aliased(Post)
            seven_days_ago = datetime.now(timezone.utc) - timedelta(days=7)
            recent_replies_subquery = (
                session.query(
                    replies,
                    func.count(replies.id).label("reply_count"),
                    func.max(replies.created_at).label("latest_reply_at"),
                )
                .filter(replies.created_at >= seven_days_ago)
                .group_by(replies.parent_id)
                .subquery()
            )
            posts = posts.outerjoin(
                recent_replies_subquery, Post.id == recent_replies_subquery.c.parent_id
            )
            posts = posts.order_by(
                getattr(
                    recent_replies_subquery.c.reply_count, args["order_direction"], 0
                )(),
                getattr(
                    recent_replies_subquery.c.latest_reply_at,
                    args["order_direction"],
                    0,
                )(),
                getattr(Post.created_at, args["order_direction"])(),
            )
        else:
            posts = posts.order_by(getattr(Post.created_at, args["order_direction"])())

        if args.get("ids"):
            posts = posts.filter(Post.id.in_(args["ids"]))
        if args.get("categories"):
            posts = (
                posts.join(post_categories, Post.id == post_categories.c.post_id)
                .join(Category)
                .filter(Category.name.in_(args["categories"]))
            )
        if args.get("depth") is not None:
            if (args["depth"] == 0) and (args.get("parent_ids") is None):
                posts = posts.filter(Post.parent_id == None)
            elif args["depth"] == 1:
                posts = posts.filter(Post.parent_id != None)
        if args.get("parent_ids"):
            posts = posts.filter(Post.parent_id.in_(args["parent_ids"]))
        if args.get("author_role"):
            posts = posts.join(User, User.id == Post.author_id)
            if args["author_role"] == ROLES.member:
                posts = posts.join(MemberProfile)
            elif args["author_role"] == ROLES.practitioner:
                posts = posts.join(PractitionerProfile).filter(Post.anonymous != True)

        if args.get("author_ids"):
            posts = posts.join(User, User.id == Post.author_id).filter(
                User.id.in_(args["author_ids"])
            )
            if protect_practitioner_anonymous_messages is True and self.user:
                posts = posts.filter(
                    (Post.anonymous != 1 or Post.author_id == self.user.id)
                )
            elif protect_practitioner_anonymous_messages is True:
                posts = posts.filter(Post.anonymous != 1)

        sticky = args.get("sticky") and args.get("sticky").upper()
        if sticky in Post.priorities:
            posts = posts.filter(Post.sticky_priority == sticky)
        self.timer("build_query_time")

        keywords = args.get("keywords").strip()
        if keywords:
            log.debug("Keyword search in both title and body: %s", keywords)
            kw = f"%{keywords}%"
            posts = posts.filter(Post.title.like(kw) | Post.body.like(kw))

        total = posts.count()
        self.timer("count_query_time")

        posts = posts.offset(args["offset"]).limit(args["limit"])

        posts = posts.all()
        self.timer("posts_query_time")

        return posts, total

    def _warm_cache(self, res):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        log.debug("Warming cache...")
        if not self.user:
            res = UserPersonalizedPostsCache.unpersonalize(res)

        try:
            with RedisLock(f"{self.cache_key}_lock", timeout=0.1, expires=5):
                self.cache.set(res)
                self.timer("warm_cache_time")
        except LockTimeout:
            log.info("Already warming up in forum cache view %s", self.cache_key)
            self.timer("lock_timeout_time")

    @authenticate
    def post(self):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        self.init_timer()
        self._user_is_enterprise_or_provider_else_403()

        schema = PostSchema(
            only=(
                "title",
                "body",
                "parent_id",
                "categories",
                "anonymous",
                "recaptcha_token",
            )
        )
        request_json = request.json if request.is_json else None
        args = schema.load(request_json or request.form)
        self.timer("schema_load_time")

        if not args.get("anonymous") and self.user.is_member and not self.user.username:
            abort(400, message="Username is missing!")

        if not args.get("body"):
            abort(400, message="Post body cannot be empty!")

        if ForumBan.is_user_banned(self.user):
            abort(400, message="You have been banned from posting on the forum.")

        parent = None
        if args.get("parent_id"):
            try:
                parent = Post.query.filter(Post.id == args.get("parent_id")).one()
            except NoResultFound:
                abort(404, message="That parent ID does not exist!")

        # only require recaptcha if a token is set up
        if get_recaptcha_key():
            # only require recaptcha for marketplace users
            if self.user.is_member and not self.user.is_enterprise:
                # only require recaptcha for first post
                if self._is_users_first_post():
                    if recaptcha_token := args.get("recaptcha_token"):
                        recaptcha_score, reasons = get_recaptcha_score(
                            recaptcha_token, self.user.id, ActionName.CREATE_POST
                        )
                        if recaptcha_score is None:
                            abort(400, message="Your recaptcha submission was invalid")
                        log.debug(
                            "Recaptcha token submitted, validated, and scored",
                            score=recaptcha_score,
                            user_id=self.user.id,
                            reasons=reasons,
                        )
                    else:
                        abort(400, message="No recaptcha token submitted")

        post = Post(
            author=self.user,
            title=args.get("title"),
            body=args.get("body"),
            parent=parent,
            anonymous=args["anonymous"],
        )

        if not post.title:
            split = [w for w in post.body[:75].split() if w]  # type: ignore[index] # Value of type "Optional[str]" is not indexable

            if len(split) > 1:
                title = " ".join(split[:-1])
            elif len(split) == 1:
                title = split[0]
            else:
                abort(400, message="Cannot extract post title!")

            post.title = title

        # one of these will commit
        if parent:
            post.categories = parent.categories
        else:
            for category in args.get("categories", []):
                # ONLY existing categories can be added for now
                post.categories.append(category)

        if post.depth > MAX_POST_DEPTH:
            abort(403, message="Post maximum depth exceeded.")

        db.session.commit()
        self.timer("commit_time")

        log.info("Added %s", post)

        service_ns_tag = "community_forum"
        team_ns_tag = service_ns_team_mapper.get(service_ns_tag)
        notify_about_new_post.delay(
            post.id, service_ns=service_ns_tag, team_ns=team_ns_tag
        )
        self.timer("notify_time")

        posts_cache = PostsViewCache()
        posts_cache.invalidate_path_prefix(request.path)
        if parent is not None:
            posts_cache.invalidate_id(parent.id)
        self.timer("cache_time")

        if parent:
            send_braze_events_for_post_reply.delay(
                post_id=parent.id, replier_id=self.user.id
            )

        schema = PostSchema()
        schema.context["user"] = self.user
        return schema.dump(post), 201

    def _is_users_first_post(self):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        # use the read replica just like the GET does
        # not first checking the cache as the cache key is based on HTTP URL path and arguments which would need to be
        # recreated here. Additionally, pulling just one post per user shouldn't be too expensive.
        post = db.s_replica1.query(Post).filter(Post.author_id == self.user.id).first()
        return post is None


class PostResource(EnterpriseOrProviderResource):
    def get(self, post_id):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        self._user_is_enterprise_or_provider_else_403()
        post = Post.query.get_or_404(post_id)
        schema = PostSchema()
        schema.context["reply_counts"] = get_all_reply_counts([post.id])
        if self.user:
            schema.context["user"] = self.user
        return schema.dump(post)


class PostBookmarksResource(EnterpriseOrProviderResource):
    def post(self, post_id):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        self._user_is_enterprise_or_provider_else_403()
        post = Post.query.get_or_404(post_id)

        if self.user in post.bookmarks:
            abort(409, message="You already followed that post!")
        else:
            post.bookmarks.append(self.user)
            db.session.add(post)

            try:
                db.session.commit()
            except IntegrityError:
                abort(409, message="You have already followed that post!")

            cache = UserPersonalizedPostsCache(self.user)
            cache.add_bookmark(post_id)
            cache = PostsViewCache()  # type: ignore[assignment] # Incompatible types in assignment (expression has type "PostsViewCache", variable has type "UserPersonalizedPostsCache")
            cache.invalidate_id(post_id)  # type: ignore[attr-defined] # "UserPersonalizedPostsCache" has no attribute "invalidate_id"
            return "", 204

    def delete(self, post_id):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        self._user_is_enterprise_or_provider_else_403()
        post = Post.query.get_or_404(post_id)

        if self.user in post.bookmarks:
            post.bookmarks.remove(self.user)
            db.session.add(post)

            try:
                db.session.commit()
            except IntegrityError:
                abort(409, message="You haven't followed that post!")

            cache = UserPersonalizedPostsCache(self.user)
            cache.remove_bookmark(post_id)
            cache = PostsViewCache()  # type: ignore[assignment] # Incompatible types in assignment (expression has type "PostsViewCache", variable has type "UserPersonalizedPostsCache")
            cache.invalidate_id(post_id)  # type: ignore[attr-defined] # "UserPersonalizedPostsCache" has no attribute "invalidate_id"
            return "", 204
        else:
            abort(409, message="You haven't followed that post!")


class UserBookmarksResource(EnterpriseOrProviderResource):
    def get(self):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        self._user_is_enterprise_or_provider_else_403()
        args = PaginableArgsSchemaV3().load(request.args)
        offset = args.get("offset", 0)
        limit = args.get("limit", 10)

        bookmarked_posts = (
            db.session.query(Post)
            .outerjoin(user_bookmarks)
            .join(User)
            .filter(User.id == self.user.id)
            .offset(offset)
            .limit(limit)
            .all()
        )

        data = {
            "data": bookmarked_posts,
            "pagination": {"total": len(self.user.bookmarks)},
        }

        schema = PostsSchema()
        post_ids = [post.id for post in bookmarked_posts]
        schema.context["reply_counts"] = get_all_reply_counts(post_ids)
        schema.context["user"] = self.user
        return schema.dump(data)


def get_all_reply_counts(post_ids: list[int] = None):  # type: ignore[no-untyped-def,assignment] # Function is missing a return type annotation #type: ignore[assignment] # Incompatible default for argument "post_ids" (default has type "None", argument has type "List[int]")
    """Calculates the member and practitioner reply counts for a list of posts"""
    # Normalize post IDs, which can come either from the Post model or redis cache
    if post_ids is None:
        post_ids = []

    # Fetch all reply counts for each of the posts
    all_reply_counts = (
        db.session.query(Post.parent_id, func.count(Post.id))
        .filter(Post.parent_id.in_(post_ids))
        .group_by(Post.parent_id)
        .all()
    )
    all_counts_dict = {row[0]: row[1] for row in all_reply_counts}

    # Fetch practitioner reply counts for each of the posts
    all_practitioner_reply_counts = (
        db.session.query(Post.parent_id, func.count(Post.id))
        .filter(Post.anonymous != True, Post.parent_id.in_(post_ids))
        .join(PractitionerProfile, PractitionerProfile.user_id == Post.author_id)
        .group_by(Post.parent_id)
        .all()
    )
    practitioner_counts_dict = {row[0]: row[1] for row in all_practitioner_reply_counts}

    return {
        post_id: {
            "members": all_counts_dict.get(post_id, 0)
            - practitioner_counts_dict.get(post_id, 0),
            "practitioners": practitioner_counts_dict.get(post_id, 0),
        }
        for post_id in post_ids
    }


class CategoryGroupsResource(EnterpriseOrProviderResource):
    def get(self) -> Dict[str, List[Dict[str, Any]]]:
        category_groups = get_category_groups_for_user(self.user)
        categories = (
            db.s_replica1.query(Category)
            .filter(CategoryVersion.name.in_(["Web", "iOS"]))
            .all()
        )
        category_list_dict = {category.name: category for category in categories}
        data = [
            {
                "label": category_group["label"],
                "categories": [
                    {
                        "display_name": category_list_dict[category].display_name,
                        "name": category_list_dict[category].name,
                        "id": category_list_dict[category].id,
                    }
                    for category in category_group["category_names"]
                    if category in category_list_dict
                ],
            }
            for category_group in category_groups
        ]

        return {"data": data}
