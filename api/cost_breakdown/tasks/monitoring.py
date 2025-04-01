from direct_payment.treatment_procedure.models.treatment_procedure import (
    TreatmentProcedure,
)
from models.enterprise import Organization
from storage.connection import db
from tasks.queues import job
from utils.log import logger
from wallet.models.reimbursement_organization_settings import (
    ReimbursementOrganizationSettings,
)
from wallet.models.reimbursement_wallet import ReimbursementWallet

log = logger(__name__)

TEST_ORGANIZATION_NAMES = ["mmb test org"]


@job(service_ns="cost_breakdown", team_ns="payments_platform")
def find_treatment_procedures_without_cost_breakdown_ids() -> None:
    """
    this cron job will run at the beginning of every week to find treatment procedures that are missing
    cost breakdown id so that ops could rerun cost breakdown for those treatment procedures
    """

    entries = (
        db.session.query(
            TreatmentProcedure.id,
            TreatmentProcedure.uuid,
            TreatmentProcedure.member_id,
            TreatmentProcedure.created_at,
        )
        .join(
            ReimbursementWallet,
            ReimbursementWallet.id == TreatmentProcedure.reimbursement_wallet_id,
        )
        .join(ReimbursementOrganizationSettings)
        .join(
            Organization,
            ReimbursementOrganizationSettings.organization_id == Organization.id,
        )
        .filter(
            TreatmentProcedure.cost_breakdown_id == None,
            TreatmentProcedure.reimbursement_wallet_id == ReimbursementWallet.id,
            ReimbursementWallet.reimbursement_organization_settings_id
            == ReimbursementOrganizationSettings.id,
            ReimbursementOrganizationSettings.organization_id == Organization.id,
            *[~Organization.name.ilike(f"{name}") for name in TEST_ORGANIZATION_NAMES],
        )
        .all()
    )
    if entries:
        log.error(
            "Found treatment procedures that are missing cost breakdown id",
            count=len(entries),
            details=",\n".join(
                f"[id:{entry[0]}, uuid:{entry[1]}, member id:{entry[2]}, created at:{entry[3].date()}]"
                for entry in entries
            ),
        )
