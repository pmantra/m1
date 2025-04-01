import click

from models.marketing import URLRedirectPath
from storage.connection import db
from utils.log import logger

log = logger(__name__)


URL_REDIRECT_PATHS = frozenset(
    (
        "arkansasbcbs",
        "columbia",
        "maternity-signup",
        "maternity-egg-freezing-signup",
        "maven-maternity-signup",
        "maven-maternity-benefit-signup",
        "maven-fertility-signup",
        "att",
        "mfeasp",
        "microsoft",
        "maternity",
        "maven",
        "fertilityEF",
        "maternityBMS",
        "maternityEF",
        "maternityFoundation",
        "maternityMP",
        "mavenEmployee",
        "FertilityBMS",
        "FM",
        "Fertility",
        "femasp",
        "pfemasp",
        "MaternityST",
        "google",
    )
)


def create_url_redirect_paths():  # type: ignore[no-untyped-def] # Function is missing a return type annotation
    """
    Add URLRedirectPath objects based on an existing enum.
    """
    existing_url_redirect_paths = URLRedirectPath.query.filter(
        URLRedirectPath.path.in_(URL_REDIRECT_PATHS)
    ).all()
    existing_paths = [
        url_redirect_path.path for url_redirect_path in existing_url_redirect_paths
    ]
    paths_to_add = [path for path in URL_REDIRECT_PATHS if path not in existing_paths]

    return [URLRedirectPath(path=path) for path in paths_to_add]


@click.option(
    "--dry-run",
    "-D",
    is_flag=True,
    help="Run the script but do not save the result in the database.",
)
def backfill(dry_run: bool = False):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
    from app import create_app

    with create_app(task_instance=True).app_context():
        try:
            url_redirect_paths = create_url_redirect_paths()
            db.session.bulk_save_objects(url_redirect_paths)
        except Exception as e:
            db.session.rollback()
            log.exception("Got an exception while backfilling.", exception=e)
            return

        if dry_run:
            log.info("Dry run requested. Rolling back changes.")
            db.session.rollback()
            return

        log.debug("Committing changes...")
        db.session.commit()
        log.debug("Finished.")


if __name__ == "__main__":
    backfill()
