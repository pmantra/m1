from models.forum import Post
from storage.connection import db
from utils.log import logger

log = logger(__name__)


def add_titles_to_posts():  # type: ignore[no-untyped-def] # Function is missing a return type annotation
    all_posts = db.session.query(Post).all()

    for post in all_posts:
        if post.title:
            log.debug("%s has a title... skipping.", post)
            continue

        log.debug("Migrating %s", post)

        split = post.body[:75].split()

        if len(split) > 1:
            title = " ".join(split[:-1])
        elif len(split) == 1:
            title = split[0]

        post.title = title
        log.debug("Got title: %s", post.title)

        db.session.add(post)
        db.session.commit()
    log.debug("All set with %d posts", len(all_posts))


def add_categories_to_children():  # type: ignore[no-untyped-def] # Function is missing a return type annotation
    all_children = db.session.query(Post).filter(Post.parent_id != None).all()

    for child in all_children:
        log.debug("Migrating %s", child)
        child.categories = child.parent.categories

        db.session.add(child)
        db.session.commit()
        log.debug("Migrated %s", child)

    log.debug("All set with %s children", len(all_children))
