from datetime import datetime

from models.profiles import AgreementAcceptance
from utils.log import logger

log = logger(__name__)


def backfill_agreement_acceptance_audits(force=False):  # type: ignore[no-untyped-def] # Function is missing a type annotation
    audits = 0
    # NOTE: Ripping out audit db.
    all_existing_acceptance_audits = set()
    for acceptance in AgreementAcceptance.query.yield_per(1000):
        try:
            # we deployed the code that introduced this auditing on 9/19 at 10:57:33am EST:
            # https://mavenclinic.slack.com/archives/C02HYFEN8/p1600441053004700
            if acceptance.created_at < datetime(2020, 9, 20):
                audit_exists_for_acceptance = (
                    acceptance.user_id,
                    acceptance.agreement_id,
                ) in all_existing_acceptance_audits

                if audit_exists_for_acceptance:
                    log.debug(
                        "Audit exists for acceptance; skipping",
                        acceptance_id=acceptance.id,
                        user_id=acceptance.user_id,
                    )
                else:
                    log.debug(
                        "Audit does not exist for acceptance",
                        acceptance_id=acceptance.id,
                        user_id=acceptance.user_id,
                    )
                    if force:
                        acceptance.audit_creation()
                    audits += 1
            else:
                log.debug(
                    "Audit exists for acceptance; skipping",
                    acceptance_id=acceptance.id,
                    user_id=acceptance.user_id,
                )

        except Exception as e:
            log.warn(
                "Error processing agreement acceptance for auditing",
                acceptance_id=acceptance.id,
                user_id=acceptance.user_id,
                error=e,
            )

    if force:
        log.info(f"Created {audits} retroactive agreement acceptance audits!")
    else:
        log.info(f"{audits} retroactive agreement acceptance audits to create.")
