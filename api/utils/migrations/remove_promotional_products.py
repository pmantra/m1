"""
remove_promotional_products

Promotional Products are causing a bug in booking flow availability.
They have also been evaluated to serve no current product purpose.
Time to get rid of the legacy complexity!

Usage:
    remove_promotional_products.py [--force]

Options:
  --force               Provide this flag to move past the dry run.
  -h --help             Show this screen.
"""
from docopt import docopt

from app import create_app
from models.products import Product
from models.verticals_and_specialties import Vertical
from storage.connection import db
from utils.log import logger

log = logger(__name__)


def remove_promotional_products_from_verticals(force):  # type: ignore[no-untyped-def] # Function is missing a type annotation
    promotional_verticals = Vertical.query.filter(
        Vertical.products.contains("is_promotional")
    ).all()
    if force:
        for vertical in promotional_verticals:
            vertical.products = [
                product
                for product in list(vertical.products)
                if "is_promotional" not in product or product["is_promotional"] is False
            ]
            db.session.add(vertical)
            log.info(f"Updated vertical {vertical.name}.")
        db.session.commit()
        log.info("Done removing promotional products from verticals.")
    else:
        for vertical in promotional_verticals:
            log.info(f"Dry Run: Did not update vertical {vertical.name}.")


def remove_promotional_products(force):  # type: ignore[no-untyped-def] # Function is missing a type annotation
    if force:
        products = Product.query.filter(Product.is_promotional.is_(True)).all()
        for p in products:
            p.is_active = False
            db.session.add(p)
        db.session.commit()
        log.info("Set all promotional Products to inactive.")


def get_promo_counts():  # type: ignore[no-untyped-def] # Function is missing a return type annotation
    promotional_verticals = Vertical.query.filter(
        Vertical.products.contains("is_promotional")
    ).count()
    log.info(f"Found {promotional_verticals} verticals with promotional products.")
    promo_products = Product.query.filter(Product.is_promotional.is_(True)).count()
    log.info(f"Found {promo_products} promotional Products.")


if __name__ == "__main__":
    args = docopt(__doc__)
    with create_app().app_context():
        get_promo_counts()
        remove_promotional_products_from_verticals(args["--force"])
        remove_promotional_products(args["--force"])
        get_promo_counts()
