from direct_payment.treatment_procedure.models.treatment_procedure import (
    TreatmentProcedure,
)
from direct_payment.treatment_procedure.pytests.factories import (
    TreatmentProcedureFactory,
)
from storage.connection import db
from wallet.models.constants import WalletState
from wallet.pytests.factories import (
    ReimbursementWalletBenefitFactory,
    ReimbursementWalletFactory,
)

WALLET_ID = 696_969
BENEFIT_ID = "121212"


def test_treatment_procedure__maven_benefit_id():
    """
    This test verifies if the TreatmentProcedure model allows querying the maven_benefit_id field from ReimbursementWalletBenefit table

    Notes:
    Ops are urgently requesting the maven_benefit_id (mbid) to improve their efficiency in Admin.

    It's better to decouple it from the TreatmentProcedure model because not every request needs mbid,
    however earlier attempts didn't seem to work well.

    @see https://gitlab.com/maven-clinic/maven/maven/-/merge_requests/9458
    """

    TreatmentProcedureFactory.create(reimbursement_wallet_id=WALLET_ID)
    rw = ReimbursementWalletFactory.create(id=WALLET_ID, state=WalletState.QUALIFIED)
    ReimbursementWalletBenefitFactory.create(
        reimbursement_wallet=rw,
        maven_benefit_id=BENEFIT_ID,
    )

    first_tp = (
        db.session.query(TreatmentProcedure)
        .filter_by(reimbursement_wallet_id=WALLET_ID)
        .first()
    )

    assert first_tp.reimbursement_wallet_benefit.maven_benefit_id == BENEFIT_ID
