from cost_breakdown.models.cost_breakdown import CostBreakdown
from storage.connection import db
from utils.log import logger

log = logger(__name__)


def main(cb_ids_and_new_oop_applied: dict, dry_run: bool = True):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
    """
    Requires a dictionary with key-values pairs
    - Key represents existing cost breakdown id.
    - Value represents new oop_applied_amount to be used to update the associated cost breakdown

    Example:
        test_dict = {1: 10000, 2: 20000}
        main(cb_ids_and_new_oop_applied=test_dict)
    """
    if not cb_ids_and_new_oop_applied:
        log.error("Error: requires non-empty dictionary")
        return

    cb_ids = list(cb_ids_and_new_oop_applied.keys())
    cbs = db.session.query(CostBreakdown).filter(CostBreakdown.id.in_(cb_ids)).all()
    has_cbs = len(cbs) > 0
    if has_cbs:
        log.info(f"Found {len(cbs)} cost breakdown(s).")
    else:
        log.info("No cost breakdown(s) found.")

    for cb in cbs:
        updated_val = cb_ids_and_new_oop_applied.get(cb.id)
        cb.oop_applied = updated_val
        db.session.add(cb)

    if dry_run:
        log.info(f"Dry run enabled. Would update {len(cbs)} cost breakdowns.")
        log.info("Dry run enabled. Rolling back changes.")
        db.session.rollback()
        return

    try:
        log.debug("Committing changes...")
        db.session.commit()
        log.debug("Finished.")
    except Exception as e:
        log.exception("Error: Unable to commit. Rolling back.", error=str(e))
        db.session.rollback()
        raise e
