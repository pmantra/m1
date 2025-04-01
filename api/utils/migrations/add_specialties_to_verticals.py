from models.verticals_and_specialties import Specialty, Vertical
from storage.connection import db
from utils.log import logger

log = logger(__name__)


# vertical_specialty_map looks like {'specialty_name': 'vertical1,vertical2'}


def add_sepcialties_to_vertical(vertical_specialty_map):  # type: ignore[no-untyped-def] # Function is missing a type annotation

    for specialty_name, vertical_names_str in vertical_specialty_map.items():
        try:
            specialty = (
                db.session.query(Specialty)
                .filter(Specialty.name == specialty_name)
                .one()
            )
        except:  # noqa  B001  TODO:  Do not use bare `except:`, it also catches unexpected events like memory errors, interrupts, system exit, and so on.  Prefer `except Exception:`.  If you're sure what you're doing, be explicit and write `except BaseException:`.
            log.debug("Bad specialty_name: %s", specialty_name)
            return

        for vertical_name in vertical_names_str.split(","):
            log.debug("Processing for vertical: %s", vertical_name)

            if not vertical_name:
                log.debug("No vert!")
                return

            try:
                vertical = (
                    db.session.query(Vertical)
                    .filter(Vertical.name == vertical_name)
                    .one()
                )
            except:  # noqa  B001  TODO:  Do not use bare `except:`, it also catches unexpected events like memory errors, interrupts, system exit, and so on.  Prefer `except Exception:`.  If you're sure what you're doing, be explicit and write `except BaseException:`.
                log.debug("Bad vertical_name: %s", vertical_name)
                return

            for practitioner_profile in vertical.practitioners:
                log.debug("Adding %s to %s", vertical, practitioner_profile)

                if specialty not in practitioner_profile.specialties:
                    practitioner_profile.specialties.append(specialty)
                    db.session.add(practitioner_profile)
                    db.session.commit()
                else:
                    log.debug("%s already in %s", practitioner_profile, specialty)

                log.debug("All set adding for %s", practitioner_profile)
            log.debug("All set adding for %s", vertical)
        log.debug("All set adding for %s", specialty)
    log.debug("All set!")
