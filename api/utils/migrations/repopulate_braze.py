"""
repopulate_braze.py

Update users' information in Braze given a csv file with a list of esp_ids in
the 'user_id' field (as if exported from Braze).

Usage:
  repopulate_braze.py <file_path>

Options:
  -h --help     Show this screen.

"""
import csv

from docopt import docopt

from app import create_app
from authn.models.user import User
from storage.connection import db
from utils.braze import track_user
from utils.log import logger

log = logger(__name__)


def repopulate_braze(file_path):  # type: ignore[no-untyped-def] # Function is missing a type annotation
    with open(file_path) as fp:
        for row in csv.DictReader(fp):
            _repopulate_user(row["user_id"])


def _repopulate_user(esp_id):  # type: ignore[no-untyped-def] # Function is missing a type annotation
    user = db.session.query(User).filter(User.esp_id == esp_id).one_or_none()
    if not user:
        log.warning(f"Could not find user with esp_id: {esp_id}")
        return
    track_user(user)


if __name__ == "__main__":
    with create_app().app_context():
        repopulate_braze(docopt(__doc__)["<file_path>"])
