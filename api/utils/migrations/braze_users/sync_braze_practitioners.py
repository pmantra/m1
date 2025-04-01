import click
from flask.cli import with_appcontext

from authn.models.user import User
from storage.connection import db
from utils import braze
from utils.log import logger
from utils.query import paginate

log = logger(__name__)


@click.group()
def cli():  # type: ignore[no-untyped-def] # Function is missing a return type annotation
    ...


@cli.command()
@with_appcontext
def sync_practitioners():  # type: ignore[no-untyped-def] # Function is missing a return type annotation
    log.info("Syncing providers with Braze")
    # limit for create from their documentation
    braze_batch_size = 75

    for users in paginate(
        db.session.query(User).filter(User.is_practitioner),
        User.id,
        size=braze_batch_size,
        chunk=True,
    ):
        braze.sync_practitioners(list(users))

    log.info("Provider sync with Braze completed")


@cli.command()
@click.option(
    "--external_id_attr",
    type=str,
    default="esp_id",
    help="User attribute used for Braze `external_id`.",
)
@with_appcontext
def delete_practitioners(external_id_attr):  # type: ignore[no-untyped-def] # Function is missing a type annotation
    log.info("Deleting providers from Braze")
    # limit for delete from their documentation
    braze_batch_size = 50

    for users in paginate(
        db.session.query(User).filter(User.is_practitioner),
        User.id,
        size=braze_batch_size,
        chunk=True,
    ):
        braze.delete_practitioners(list(users), external_id_attr)

    log.info("Deleting providers from Braze completed")


if __name__ == "__main__":
    cli()
