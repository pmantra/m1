from __future__ import annotations

from typing import Type

import flask_login as login
from flask import flash
from flask_admin.actions import action
from flask_admin.contrib.sqla.filters import BooleanEqualFilter
from flask_admin.form import rules
from markupsafe import Markup

from admin.views.base import USER_AJAX_REF, AdminCategory, AdminViewT, MavenAuditedView
from audit_log import utils as audit_utils
from authn.models.user import User
from models.forum import ForumBan, Post, PostSpamStatus
from models.profiles import Category, CategoryVersion
from storage.connection import RoutingSQLAlchemy, db
from tasks.forum import invalidate_posts_cache


class PostViewIsSpamFilter(BooleanEqualFilter):
    def apply(self, query, value, alias=None):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        if value == "1":
            return query.filter(Post.spam_status == PostSpamStatus.SPAM)
        else:
            return query.filter(Post.spam_status != PostSpamStatus.SPAM)


class PostView(MavenAuditedView):
    read_permission = "read:post"
    delete_permission = "delete:post"
    create_permission = "create:post"
    edit_permission = "edit:post"

    required_capability = "admin_forum"  # type: ignore[assignment] # Incompatible types in assignment (expression has type "str", base class "AdminAuth" defined the type as "None")
    list_template = "forum_list_template.html"

    column_list = (
        "id",
        "title",
        "parent",
        "spam_status",
        "created_at",
    )
    column_sortable_list = ("created_at",)
    column_searchable_list = ("body", "title", "id")
    column_filters = (
        User.username,
        Post.sticky_priority,
        Post.id,
        Post.parent_id,
        PostViewIsSpamFilter(None, "Is Spam"),
    )

    form_excluded_columns = [
        "parent_id",
        "modified_at",
        "replies",
        "parent",
        "children",
        "bookmarks",
        "votes",
    ]

    form_rules = [
        rules.FieldSet(("body", "title"), "Content"),
        rules.FieldSet(
            (
                "created_at",
                "categories",
                "phases",
                "tags",
                "author",
                "anonymous",
                "sticky_priority",
            ),
            "Meta",
        ),
        rules.FieldSet(("spam_status",), "Spam info"),
    ]

    form_ajax_refs = {"author": USER_AJAX_REF}

    @classmethod
    def factory(  # type: ignore[no-untyped-def] # Function is missing a type annotation for one or more arguments
        cls: Type[AdminViewT],
        *,
        session: RoutingSQLAlchemy = None,  # type: ignore[assignment] # Incompatible default for argument "session" (default has type "None", argument has type "RoutingSQLAlchemy")
        category: AdminCategory = None,  # type: ignore[assignment] # Incompatible default for argument "category" (default has type "None", argument has type "AdminCategory")
        name: str = None,  # type: ignore[assignment] # Incompatible default for argument "name" (default has type "None", argument has type "str")
        endpoint: str = None,  # type: ignore[assignment] # Incompatible default for argument "endpoint" (default has type "None", argument has type "str")
        **kwargs,
    ) -> AdminViewT:
        return cls(  # type: ignore[call-arg] # Too many arguments for "object" #type: ignore[call-arg] # Unexpected keyword argument "category" for "object" #type: ignore[call-arg] # Unexpected keyword argument "name" for "object" #type: ignore[call-arg] # Unexpected keyword argument "endpoint" for "object"
            Post,
            session or db.session,
            category=category,
            name=name,
            endpoint=endpoint,
            **kwargs,
        )

    @action("mark_as_spam", "Mark as spam and ban user(s)")
    def action_mark_as_spam(self, ids):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        posts = db.session.query(Post).filter(Post.id.in_(ids)).all()
        for post in posts:
            post.spam_status = PostSpamStatus.SPAM
        audit_utils.emit_bulk_audit_log_update(posts)

        for user_id in {post.author_id for post in posts}:
            forum_ban = ForumBan(
                user_id=user_id, created_by_user_id=login.current_user.id
            )
            db.session.add(forum_ban)
            audit_utils.emit_audit_log_update(forum_ban)

        db.session.commit()

        invalidate_posts_cache.delay()

        flash(f"{len(ids)} post(s) marked as spam.", "success")

    def _format_spam_status(view, context, model, name):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        if model.spam_status == PostSpamStatus.SPAM:
            return Markup("<span style='color:red'>SPAM</span>")
        if model.spam_status == PostSpamStatus.NONE:
            return Markup("<span style='color: grey'>not spam</span>")
        return model.spam_status.value

    column_formatters = {"spam_status": _format_spam_status}


class CategoryView(MavenAuditedView):
    read_permission = "read:category"
    delete_permission = "delete:category"
    create_permission = "create:category"
    edit_permission = "edit:category"

    required_capability = "admin_forum"  # type: ignore[assignment] # Incompatible types in assignment (expression has type "str", base class "AdminAuth" defined the type as "None")
    list_template = "forum_list_template.html"
    form_rules = ["name", "image_id", "ordering_weight", "display_name", "versions"]
    column_searchable_list = ["name"]

    form_excluded_columns = ["posts", "practitioners"]

    @classmethod
    def factory(  # type: ignore[no-untyped-def] # Function is missing a type annotation for one or more arguments
        cls: Type[AdminViewT],
        *,
        session: RoutingSQLAlchemy = None,  # type: ignore[assignment] # Incompatible default for argument "session" (default has type "None", argument has type "RoutingSQLAlchemy")
        category: AdminCategory = None,  # type: ignore[assignment] # Incompatible default for argument "category" (default has type "None", argument has type "AdminCategory")
        name: str = None,  # type: ignore[assignment] # Incompatible default for argument "name" (default has type "None", argument has type "str")
        endpoint: str = None,  # type: ignore[assignment] # Incompatible default for argument "endpoint" (default has type "None", argument has type "str")
        **kwargs,
    ) -> AdminViewT:
        return cls(  # type: ignore[call-arg] # Too many arguments for "object" #type: ignore[call-arg] # Unexpected keyword argument "category" for "object" #type: ignore[call-arg] # Unexpected keyword argument "name" for "object" #type: ignore[call-arg] # Unexpected keyword argument "endpoint" for "object"
            Category,
            session or db.session,
            category=category,
            name=name,
            endpoint=endpoint,
            **kwargs,
        )


class CategoryVersionView(MavenAuditedView):
    read_permission = "read:category-version"
    delete_permission = "delete:category-version"
    create_permission = "create:category-version"
    edit_permission = "edit:category-version"

    required_capability = "admin_forum"  # type: ignore[assignment] # Incompatible types in assignment (expression has type "str", base class "AdminAuth" defined the type as "None")
    form_rules = ["name"]
    column_searchable_list = ["name"]

    @classmethod
    def factory(  # type: ignore[no-untyped-def] # Function is missing a type annotation for one or more arguments
        cls: Type[AdminViewT],
        *,
        session: RoutingSQLAlchemy | None = None,
        category: AdminCategory | None = None,
        name: str | None = None,
        endpoint: str | None = None,
        **kwargs,
    ) -> AdminViewT:
        return cls(  # type: ignore[call-arg] # Too many arguments for "object" #type: ignore[call-arg] # Unexpected keyword argument "category" for "object" #type: ignore[call-arg] # Unexpected keyword argument "name" for "object" #type: ignore[call-arg] # Unexpected keyword argument "endpoint" for "object"
            CategoryVersion,
            session or db.session,
            category=category,
            name=name,
            endpoint=endpoint,
            **kwargs,
        )


class ForumBanView(MavenAuditedView):
    read_permission = "read:forum-ban"
    delete_permission = "delete:forum-ban"
    create_permission = "create:forum-ban"
    edit_permission = "edit:forum-ban"

    required_capability = "admin_forum"  # type: ignore[assignment] # Incompatible types in assignment (expression has type "str", base class "AdminAuth" defined the type as "None")

    column_filters = (ForumBan.user_id,)

    form_ajax_refs = {"user": USER_AJAX_REF, "created_by_user": USER_AJAX_REF}

    @classmethod
    def factory(  # type: ignore[no-untyped-def] # Function is missing a type annotation for one or more arguments
        cls: Type[AdminViewT],
        *,
        session: RoutingSQLAlchemy | None = None,
        category: AdminCategory | None = None,
        name: str | None = None,
        endpoint: str | None = None,
        **kwargs,
    ) -> AdminViewT:
        return cls(  # type: ignore[call-arg] # Too many arguments for "object" #type: ignore[call-arg] # Unexpected keyword argument "category" for "object" #type: ignore[call-arg] # Unexpected keyword argument "name" for "object" #type: ignore[call-arg] # Unexpected keyword argument "endpoint" for "object"
            ForumBan,
            session or db.session,
            category=category,
            name=name,
            endpoint=endpoint,
            **kwargs,
        )
