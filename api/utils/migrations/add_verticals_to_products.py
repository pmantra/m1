from authn.models.user import User
from models.profiles import PractitionerProfile
from storage.connection import db
from utils.log import logger

log = logger(__name__)


def migrate_practitioners():  # type: ignore[no-untyped-def] # Function is missing a return type annotation
    all_practitioners = db.session.query(PractitionerProfile).all()

    log.debug("Got %s to migrate", len(all_practitioners))
    for profile in all_practitioners:
        add_verticals_to_products(profile.user)
        log.debug("Migrated %s", profile.user)
    log.debug("All set!")


def add_verticals_to_products(user: User):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
    log.debug("Adding verticals to products for %s", user)

    profile = user.practitioner_profile
    if len(profile.verticals) == 1:
        for product in user.products:
            log.debug("Migrating %s", product)

            product.vertical = profile.verticals[0]
            product.is_active = True

            try:
                db.session.add(product)
            except:  # noqa  B001  TODO:  Do not use bare `except:`, it also catches unexpected events like memory errors, interrupts, system exit, and so on.  Prefer `except Exception:`.  If you're sure what you're doing, be explicit and write `except BaseException:`.
                log.info("Problem with %s", user)
                return

        try:
            db.session.commit()
        except:  # noqa  B001  TODO:  Do not use bare `except:`, it also catches unexpected events like memory errors, interrupts, system exit, and so on.  Prefer `except Exception:`.  If you're sure what you're doing, be explicit and write `except BaseException:`.
            db.session.rollback()
            log.info("Problem with %s", user)
            return

        log.debug("Updated %s for %s", user.products, user)

    elif len(profile.verticals):
        log.debug("%s has too many verticals!", user)

    else:
        log.debug("%s has no verticals", user)
