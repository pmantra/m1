import uuid

from flask import flash

from authn.models.user import User
from data_admin.maker_base import _MakerBase
from models.forum import Post
from models.profiles import Category
from storage.connection import db


class ForumPostMaker(_MakerBase):
    def create_object(self, spec, parent=None):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        author = User.query.filter_by(email=spec.get("author")).one_or_none()
        if not author:
            flash(f"Bad author for Post! {spec}", "error")
            return

        if parent and not isinstance(parent, Post):
            flash("Parent post must be an instance of Post!", "error")
            return

        post = Post(
            author=author,
            parent=parent,
            title=spec.get("title"),
            body=spec.get("body", f"Test Post {uuid.uuid4()}"),
        )

        if "category" in spec:
            category = Category.query.filter_by(name=spec["category"]).first()
            if category:
                post.categories.append(category)

        db.session.add(post)
        db.session.flush()

        if "replies" in spec:
            replies = spec["replies"]
            if not isinstance(replies, list):
                flash("Forum post replies must be an array!", "error")
                return

            for r_spec in replies:
                ForumPostMaker().create_object_and_flush(r_spec, parent=post)

        return post
