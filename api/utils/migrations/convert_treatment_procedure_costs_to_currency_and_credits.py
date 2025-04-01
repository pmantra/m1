import click

from common.global_procedures.procedure import ProcedureService
from direct_payment.clinic.models.fee_schedule import FeeScheduleGlobalProcedures
from direct_payment.treatment_procedure.models.treatment_procedure import (
    TreatmentProcedure,
)
from storage.connection import db
from utils.log import logger
from wallet.models.constants import BenefitTypes
from wallet.models.reimbursement_wallet import ReimbursementWallet

log = logger(__name__)


""""
    Treatment procedures previously had cost saved as currency or credit depending on member's benefit type.
    Now we save both currency and credit costs in separate fields. This script will convert treatment procedures
    with member benefit type credit to now store the currency cost as `cost` and credit cost as `cost_credit`.

    This can be rerun without limits but note that this will grab the current most up to date costs of procedures which
    may not correlate with the "quoted" cost given to member at the time of procedure add.
"""


def convert_treatment_procedure_costs_to_currency_and_credits():  # type: ignore[no-untyped-def] # Function is missing a return type annotation
    count = 0
    procedure_client = ProcedureService(internal=True)

    treatment_procedures = TreatmentProcedure.query.all()
    for tp in treatment_procedures:
        wallet = ReimbursementWallet.query.get(tp.reimbursement_wallet_id)
        benefit_type = wallet.category_benefit_type(
            request_category_id=tp.reimbursement_request_category_id
        )

        if benefit_type == BenefitTypes.CYCLE:
            fee_schedule_gp = FeeScheduleGlobalProcedures.query.filter(
                FeeScheduleGlobalProcedures.global_procedure_id
                == tp.global_procedure_id,
                FeeScheduleGlobalProcedures.fee_schedule_id == tp.fee_schedule_id,
            ).one_or_none()
            if not fee_schedule_gp:
                log.warning(
                    "FeeScheduleGlobalProcedures not found for new procedure.",
                    treatment_procedure_id=tp.id,
                    global_procedure_id=tp.global_procedure_id,
                    fee_schedule_id=tp.fee_schedule_id,
                )
            else:
                tp.cost = fee_schedule_gp.cost

            global_procedure = procedure_client.get_procedure_by_id(
                procedure_id=tp.global_procedure_id,
            )
            if not global_procedure:
                log.warning(
                    "Could not find reimbursement wallet global procedure",
                    treatment_procedure_id=tp.id,
                    global_procedure_id=tp.global_procedure_id,
                )
            else:
                tp.cost_credit = global_procedure["credits"]  # type: ignore[typeddict-item] # TypedDict "PartialProcedure" has no key "credits"

            db.session.add(tp)
            count += 1

    log.info(f"{count} treatment procedures to be processed.")


@click.command()
@click.option(
    "--dry_run",
    "-d",
    is_flag=True,
    help="Run the script but do not save the result in the database.",
)
def main(dry_run: bool = True):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
    from app import create_app

    with create_app(task_instance=True).app_context():
        try:
            convert_treatment_procedure_costs_to_currency_and_credits()
        except Exception as e:
            db.session.rollback()
            log.error("Treatment procedure conversion failed.", exception=e)
            return

        if dry_run:
            log.info("Dry run requested. Rolling back changes.")
            db.session.rollback()
            return

        log.debug("Committing changes...")
        db.session.commit()
        log.debug("Finished.")


if __name__ == "__main__":
    main()
