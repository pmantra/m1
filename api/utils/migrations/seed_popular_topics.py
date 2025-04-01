import csv

from app import create_app
from models.marketing import PopularTopic
from storage.connection import db
from utils.log import logger

log = logger(__name__)


def seed_popular_topics():  # type: ignore[no-untyped-def] # Function is missing a return type annotation
    with open("utils/migrations/seed_popular_topics.csv") as csv_file:
        reader = csv.DictReader(csv_file)
        count = 0
        fail_count = 0
        for row in reader:
            try:
                db.session.add(PopularTopic(**row))
                db.session.commit()
                log.debug(f"Successfully added popular topic: {row}")
                count += 1
            except Exception as err:
                log.error(f"Error adding popular topic: {row}", exception=err)
                fail_count += 1
        log.info(f"Successfully added {count} popular topics and {fail_count} failed")


if __name__ == "__main__":
    with create_app().app_context():
        seed_popular_topics()
