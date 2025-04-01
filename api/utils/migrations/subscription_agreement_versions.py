from dateutil.parser import parse

from models.profiles import Agreement, AgreementAcceptance, PractitionerProfile
from storage.connection import db
from utils.log import logger

log = logger(__name__)


def migrate_all_users():  # type: ignore[no-untyped-def] # Function is missing a return type annotation
    agreement = (
        db.session.query(Agreement)
        .filter(Agreement.name == "service", Agreement.version == 1)
        .one()
    )

    for profile in PractitionerProfile.query.all():
        log.debug("Migrating %s", profile)

        data = profile.json or {}
        agreed = data.get("service_agreement")
        agreed_at = data.get("service_agreement_agreed_at")
        if agreed and agreed_at:
            try:
                agreed_at = parse(agreed_at)
            except:  # noqa  B001  TODO:  Do not use bare `except:`, it also catches unexpected events like memory errors, interrupts, system exit, and so on.  Prefer `except Exception:`.  If you're sure what you're doing, be explicit and write `except BaseException:`.
                log.debug("Bad parse for %s", profile)
                continue

            if AgreementAcceptance.query.filter_by(
                practitioner_profile=profile
            ).first():
                log.debug("Already an agreement accept for %s", profile)
                continue

            acceptance = AgreementAcceptance(
                agreement=agreement, practitioner_profile=profile, created_at=agreed_at
            )
            db.session.add(acceptance)
            db.session.commit()
        else:
            log.debug("%s did not agree - %s/%s", profile, agreed, agreed_at)

        log.debug("All set for %s", profile)

    log.debug("All set!")
