"""
This script collects all direct dependencies that the billing service has on MONO components. These will need to be
excised and the callers repointed to service endpoints once billing service migrates to a microservice.
"""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import Iterable

from sqlalchemy.orm.exc import MultipleResultsFound, NoResultFound

from authn.models.user import User
from cost_breakdown.models.cost_breakdown import CostBreakdown
from direct_payment.billing import models
from direct_payment.billing.models import PayorType
from direct_payment.clinic.models.clinic import FertilityClinic
from direct_payment.clinic.repository.clinic_location import (
    FertilityClinicLocationRepository,
)
from direct_payment.invoicing.repository.organization_invoicing_settings import (
    OrganizationInvoicingSettingsRepository,
)
from direct_payment.treatment_procedure.repository.treatment_procedure import (
    TreatmentProcedureRepository,
)
from storage import connection
from utils.log import logger
from wallet.models.reimbursement_organization_settings import (
    ReimbursementOrganizationSettings,
)
from wallet.models.reimbursement_wallet import ReimbursementWallet
from wallet.models.reimbursement_wallet_benefit import ReimbursementWalletBenefit
from wallet.repository.member_benefit import MemberBenefitRepository

log = logger(__name__)


def get_payor_id_from_payments_customer_or_recipient_id(
    input_uuid: str,
) -> tuple[int, PayorType]:
    """
    DO NOT USE IF POSSIBLE. THIS IS SLATED FOR DECOMMISSION.

    Given the payment customer/recipient UUID returns the matching member, employer or clinic id (known as payor id in
    Billing). Will throw ValueError if exactly one result is not found. Assumes UUIDs are globally unique.
    :param input_uuid: the UUID the payment gateway knows the entity as.
    :type input_uuid: string (UUID)
    :return: payor id, payor type
    :rtype: tuple[int, PayorType]
    """
    # ordered by the assumed size of the tables
    res = (
        _get_id_from_reimbursement_org_settings(input_uuid)
        or _get_id_from_fertility_clinic(input_uuid)
        or _get_id_from_wallet(input_uuid)
    )
    if not res:
        raise ValueError(
            f"Unable to find exactly 1 matching employer clinic or member id for {input_uuid}"
        )
    return res


def get_payor(payor_type: models.PayorType, payor_id: int):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
    model = (
        ReimbursementWallet
        if payor_type == models.PayorType.MEMBER
        else ReimbursementOrganizationSettings
        if payor_type == models.PayorType.EMPLOYER
        else FertilityClinic
        if payor_type == models.PayorType.CLINIC
        else None
    )
    if model is None:
        return
    return connection.db.session.query(model).get(payor_id)


def _get_id_from_wallet(
    payment_customer_id: str,
) -> tuple[int, PayorType] | None:
    try:
        to_return = (
            connection.db.session.query(ReimbursementWallet.id)
            .filter_by(payments_customer_id=payment_customer_id)
            .one()[0]
        )
        log.info(f"Found customer {to_return} linked to {payment_customer_id}.")
        return to_return, PayorType.MEMBER
    except (NoResultFound, MultipleResultsFound):
        return None


def _get_id_from_reimbursement_org_settings(
    payment_customer_id: str,
) -> tuple[int, PayorType] | None:
    try:
        to_return = (
            connection.db.session.query(ReimbursementOrganizationSettings.id)
            .filter_by(payments_customer_id=payment_customer_id)
            .one()[0]
        )
        log.info(f"Found employer {to_return} linked to {payment_customer_id}.")
        return to_return, PayorType.EMPLOYER
    except (NoResultFound, MultipleResultsFound):
        return None


def _get_id_from_fertility_clinic(
    payments_recipient_id: str,
) -> tuple[int, PayorType] | None:
    try:
        to_return = (
            connection.db.session.query(FertilityClinic.id)
            .filter_by(payments_recipient_id=payments_recipient_id)
            .one()[0]
        )
        log.info(f"Found clinic {to_return} linked to {payments_recipient_id}.")
        return to_return, PayorType.CLINIC
    except (NoResultFound, MultipleResultsFound):
        return None


def payments_customer_id(
    payor_id: int, payor_type: models.PayorType
) -> uuid.UUID | None:
    try:
        res = None
        if payor_type in [models.PayorType.MEMBER, models.PayorType.EMPLOYER]:
            fld = (
                ReimbursementWallet.payments_customer_id
                if payor_type == models.PayorType.MEMBER
                else ReimbursementOrganizationSettings.payments_customer_id
            )
            res = connection.db.session.query(fld).filter_by(id=payor_id).one()[0]
        if payor_type == models.PayorType.CLINIC:
            res = (
                connection.db.session.query(FertilityClinic.payments_recipient_id)
                .filter_by(id=payor_id)
                .one()[0]
            )
        return uuid.UUID(res) if res else None
    except NoResultFound:
        log.info(
            "Found no payments_customer_id",
            payor_id=payor_id,
            payor_type=payor_type.value,
        )
    except MultipleResultsFound:
        log.info(
            "Found multiple payments_customer_ids",
            payor_id=payor_id,
            payor_type=payor_type.value,
        )
    return None


def get_treatment_procedure_as_dict_from_id(treatment_procedure_id: int) -> dict:
    """
    DO NOT USE IF POSSIBLE. THIS IS SLATED FOR DECOMMISSION.

    Given a treatment procedure id returns a dict representation of the treatment procedure object. Empty dict if
    procedure is not found. Implemented as dict to avoid importing TreatmentProcedure into the core billing service.
    :param treatment_procedure_id: Thr id of the treatment procedure.
    :return: Dict conversion of the treatment procedure object
    """
    to_return = {}
    treatment_procedure = TreatmentProcedureRepository().read(
        treatment_procedure_id=treatment_procedure_id
    )
    if treatment_procedure:
        to_return = treatment_procedure.__dict__
    return to_return


def get_treatment_procedures_as_dicts_from_ids(
    treatment_procedure_ids: Iterable[int] | None,
) -> dict[int, dict]:
    """
    Given an iterable of treatment procedure ids returns a dict containing dict representation of matching treatment
    procedures keyed by the treatment procedure id.
    """
    to_return = {}
    if treatment_procedure_ids:
        tps = TreatmentProcedureRepository().get_treatments_by_ids(
            treatment_procedure_ids=list(set(treatment_procedure_ids))
        )
        to_return = {tp.id: tp.__dict__ for tp in tps}
    return to_return


def get_treatment_procedure_ids_with_status_since_bill_timing_change(
    statuses: list[str],
) -> list[int]:
    cutoff = datetime.strptime("24/06/2024 13:13", "%d/%m/%Y %H:%M")
    to_return = []
    tps = TreatmentProcedureRepository().get_treatment_procedures_with_statuses_since_datetime(
        statuses=statuses, cutoff=cutoff
    )
    if tps:
        to_return = [tp.id for tp in tps]
    return to_return


def get_clinic_locations_as_dicts_from_treatment_procedure_id(
    treatment_procedure_id: int,
) -> dict | None:
    treatment_procedure = TreatmentProcedureRepository().read(
        treatment_procedure_id=treatment_procedure_id
    )
    if treatment_procedure:
        clinic_location = FertilityClinicLocationRepository().get(
            fertility_clinic_location_id=treatment_procedure.fertility_clinic_location_id
        )
        if clinic_location:
            return clinic_location.__dict__
    return None


def get_cost_breakdown_as_dict_from_id(cost_breakdown_id: int) -> dict:
    to_return = {}
    cost_breakdown = CostBreakdown.query.get(cost_breakdown_id)
    if cost_breakdown:
        to_return = cost_breakdown.__dict__
    return to_return


def get_benefit_id_from_wallet_id(wallet_id: int) -> str | None:
    """
    Given a wallet id returns the associated benefit id
    :return: The benefit id if found, None otherwise
    """
    try:
        res = (
            connection.db.session.query(ReimbursementWalletBenefit.maven_benefit_id)
            .filter(ReimbursementWalletBenefit.reimbursement_wallet_id == wallet_id)
            .one()[0]
        )
        log.info("Found maven_benefit_id", payor_id=wallet_id, maven_benefit_id=res)
        return res
    except NoResultFound:
        log.warn(
            "Found no maven_benefit_id",
            payor_id=wallet_id,
        )
    except MultipleResultsFound:
        log.warn(
            "Found multiple maven_benefit_ids",
            payor_id=wallet_id,
        )
    return None


def get_benefit_id(member_id: int) -> str:
    member_benefit_repo = MemberBenefitRepository(session=connection.db.session)
    benefit_id = member_benefit_repo.get_member_benefit_id(user_id=member_id)
    return benefit_id


def get_first_and_last_name_from_user_id(user_id: int) -> tuple[str, str]:
    """
    Given a user_id id returns users first and last name. Blank values possible.
    :return: tuple of first and last name.
    """
    try:
        res = (
            connection.db.session.query(User.first_name, User.last_name)
            .filter(User.id == user_id)
            .one()
        )
        log.info("Found User", user_id=user_id)
        return res.first_name or "", res.last_name or ""
    except NoResultFound:
        log.warn("Could not find user.", user_id=user_id)
    except MultipleResultsFound:
        log.warn("Found multiple users.", user_id=user_id)
    return "", ""


def get_org_id_for_wallet_id(wallet_id: int) -> int | None:
    query = """
            SELECT
                ros.organization_id
            FROM
                reimbursement_organization_settings ros
            JOIN 
                reimbursement_wallet rw ON rw.reimbursement_organization_settings_id =ros.id
            WHERE 
                rw.id = :wallet_id
    """
    to_return = connection.db.session.execute(query, {"wallet_id": wallet_id}).scalar()

    return to_return


def get_org_invoicing_settings_as_dict_from_ros_id(ros_id: int) -> dict:
    to_return = {}
    ois_repo = OrganizationInvoicingSettingsRepository(
        session=connection.db.session, is_in_uow=True
    )
    ois = ois_repo.get_by_reimbursement_org_settings_id(
        reimbursement_organization_settings_id=ros_id
    )
    if ois:
        to_return = ois.__dict__
    return to_return


def get_organisation_id_from_ros_id(ros_id: int) -> int:
    try:
        org_id = (
            connection.db.session.query(
                ReimbursementOrganizationSettings.organization_id
            )
            .filter(ReimbursementOrganizationSettings.id == ros_id)
            .scalar()
        )
        log.info("Org ID pulled", ros_id=str(ros_id), organization_id=str(org_id))
        return org_id
    except Exception as e:
        log.error(
            "Unable to pull org id from ros id,", ros_id=str(ros_id), reason=str(e)
        )
        return 0
