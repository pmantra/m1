from datetime import date, datetime, timedelta
from unittest.mock import Mock, patch

import pytest
from marshmallow import ValidationError
from werkzeug.exceptions import Forbidden

from authn.models.user import User
from common.global_procedures.procedure import ProcedureService
from cost_breakdown.pytests.factories import CostBreakdownFactory
from direct_payment.clinic.constants import PROCEDURE_BACKDATE_LIMIT_DAYS
from direct_payment.clinic.pytests.factories import (
    FeeScheduleGlobalProceduresFactory,
    FertilityClinicUserProfileFactory,
)
from direct_payment.treatment_procedure.constant import (
    ENABLE_UNLIMITED_BENEFITS_FOR_TP_VALIDATION,
)
from direct_payment.treatment_procedure.models.treatment_procedure import (
    TreatmentProcedureStatus,
)
from direct_payment.treatment_procedure.pytests.factories import (
    TreatmentProcedureFactory,
)
from direct_payment.treatment_procedure.utils.procedure_helpers import (
    get_global_procedure_ids,
    get_member_procedures,
    get_wallet_patient_eligibility_state,
    process_partial_procedure,
    run_cost_breakdown,
    trigger_cost_breakdown,
    validate_annual_limit_procedure,
    validate_edit_procedure,
    validate_fc_user,
    validate_partial_global_procedure,
    validate_procedure,
    validate_procedures,
)
from eligibility.pytests import factories as eligibility_factories
from pytests.common.global_procedures import factories
from pytests.factories import DefaultUserFactory
from wallet.constants import NUM_CREDITS_PER_CYCLE
from wallet.models.constants import (
    BenefitTypes,
    FertilityProgramTypes,
    PatientInfertilityDiagnosis,
    WalletDirectPaymentState,
    WalletState,
    WalletUserStatus,
)
from wallet.models.reimbursement_wallet import ReimbursementWallet
from wallet.pytests.factories import (
    ReimbursementOrgSettingDxRequiredProceduresFactory,
    ReimbursementWalletFactory,
    ReimbursementWalletUsersFactory,
)


def test_validate_fc_user(fertility_clinic, fc_user):
    tp_args = {fertility_clinic.id}

    validate_fc_user(fc_user, tp_args)


def test_validate_fc_user_account_not_enabled(fertility_clinic, fc_user):
    fertility_clinic.payments_recipient_id = None
    tp_args = {fertility_clinic.id}

    with pytest.raises(
        ValidationError,
        match="Account not enabled to receive payouts. You will not be able to add or complete "
        "procedures until you have finished setting up your account. Please update in account "
        "settings or contact your billing administrator.",
    ):
        validate_fc_user(fc_user, tp_args)


def test_validate_fc_user_user_clinic_not_allowed(fertility_clinic):
    user = DefaultUserFactory.create()
    FertilityClinicUserProfileFactory(user_id=user.id)
    tp_args = {fertility_clinic.id}

    with pytest.raises(
        Forbidden,
        match="403 Forbidden: You don't have the permission to access the requested resource. It is either read-protected or not readable by the server.",
    ):
        validate_fc_user(user, tp_args)


def test_get_member_procedures(enterprise_user, fc_user, fertility_clinic):
    tp = TreatmentProcedureFactory(
        member_id=enterprise_user.id, fertility_clinic=fertility_clinic
    )
    fc_user.clinics = [fertility_clinic]

    member_procedures = get_member_procedures(fc_user, enterprise_user.id)

    assert member_procedures == [tp]


def test_get_member_procedures_fc_user_clinics_not_allowed(
    enterprise_user, fc_user, fertility_clinic
):
    TreatmentProcedureFactory(member_id=enterprise_user.id)
    fc_user.clinics = [fertility_clinic]

    member_procedures = get_member_procedures(fc_user, enterprise_user.id)

    assert member_procedures == []


def test_get_member_procedures_filter_partial_procedure(
    enterprise_user, fc_user, fertility_clinic
):
    tp = TreatmentProcedureFactory(
        member_id=enterprise_user.id, fertility_clinic=fertility_clinic
    )
    TreatmentProcedureFactory(
        member_id=enterprise_user.id,
        fertility_clinic_id=fertility_clinic.id,
        status=TreatmentProcedureStatus.PARTIALLY_COMPLETED,
    )
    fc_user.clinics = [fertility_clinic]

    member_procedures = get_member_procedures(fc_user, enterprise_user.id)

    assert member_procedures == [tp]


def test_validate_annual_limit_procedure(enterprise_user):
    member_id = enterprise_user.id
    global_procedure = factories.GlobalProcedureFactory.create(annual_limit=1)
    global_procedure_id = global_procedure["id"]

    TreatmentProcedureFactory(
        member_id=member_id,
        global_procedure_id=global_procedure_id,
        start_date=datetime.today(),
    )

    validate_annual_limit_procedure(global_procedure, member_id, 0)


def test_validate_annual_limit_procedure_previous_year_procedure(enterprise_user):
    member_id = enterprise_user.id
    global_procedure = factories.GlobalProcedureFactory.create(annual_limit=1)
    global_procedure_id = global_procedure["id"]

    TreatmentProcedureFactory(
        member_id=member_id,
        global_procedure_id=global_procedure_id,
        start_date=datetime.today() - timedelta(days=365),
    )

    validate_annual_limit_procedure(global_procedure, member_id, 1)


def test_validate_annual_limit_procedure_over_limit(enterprise_user):
    member_id = enterprise_user.id
    global_procedure = factories.GlobalProcedureFactory.create(annual_limit=1)
    global_procedure_id = global_procedure["id"]

    TreatmentProcedureFactory(
        member_id=member_id,
        global_procedure_id=global_procedure_id,
        start_date=datetime.today(),
    )

    with pytest.raises(
        ValidationError,
        match=f"Member reached annual limit for procedure: {global_procedure['name']}. Please remove this procedure and "
        "bill outside the portal.",
    ):
        validate_annual_limit_procedure(global_procedure, member_id, 1)


def test_validate_annual_limit_procedure_over_limit_previous_year_procedure(
    enterprise_user,
):
    member_id = enterprise_user.id
    global_procedure = factories.GlobalProcedureFactory.create(annual_limit=1)
    global_procedure_id = global_procedure["id"]

    TreatmentProcedureFactory(
        member_id=member_id,
        global_procedure_id=global_procedure_id,
        start_date=datetime.today() - timedelta(days=365),
    )

    with pytest.raises(
        ValidationError,
        match=f"Member reached annual limit for procedure: {global_procedure['name']}. Please remove this procedure and "
        "bill outside the portal.",
    ):
        validate_annual_limit_procedure(global_procedure, member_id, 2)


def test_validate_edit_procedure(treatment_procedure):
    tp_args = {
        "start_date": treatment_procedure.start_date,
        "end_date": treatment_procedure.end_date,
        "status": treatment_procedure.status,
    }

    validate_edit_procedure(tp_args, treatment_procedure)


def test_validate_edit_procedure_without_start_date(treatment_procedure):
    treatment_procedure.start_date = date.today()
    tp_args = {
        "end_date": date.today() + timedelta(days=7),
    }

    validate_edit_procedure(tp_args, treatment_procedure)


def test_validate_edit_procedure_completed(treatment_procedure):
    treatment_procedure.status = TreatmentProcedureStatus.COMPLETED
    tp_args = {
        "start_date": treatment_procedure.start_date,
        "end_date": treatment_procedure.end_date,
        "status": treatment_procedure.status,
    }

    with pytest.raises(ValidationError, match="Cannot edit a completed procedure."):
        validate_edit_procedure(tp_args, treatment_procedure)


def test_validate_edit_procedure_partially_completed(treatment_procedure):
    treatment_procedure.status = TreatmentProcedureStatus.PARTIALLY_COMPLETED
    tp_args = {
        "start_date": treatment_procedure.start_date,
        "end_date": treatment_procedure.end_date,
        "status": treatment_procedure.status,
    }

    with pytest.raises(ValidationError, match="Cannot edit a completed procedure."):
        validate_edit_procedure(tp_args, treatment_procedure)


def test_validate_edit_procedure_cancelled_no_date(treatment_procedure):
    tp_args = {
        "start_date": treatment_procedure.start_date,
        "end_date": None,
        "status": TreatmentProcedureStatus.CANCELLED.value,
    }

    with pytest.raises(ValidationError, match="Cancellation date required."):
        validate_edit_procedure(tp_args, treatment_procedure)


def test_validate_edit_procedure_completed_bad_end_date(treatment_procedure):
    tp_args = {
        "start_date": treatment_procedure.start_date,
        "end_date": date.today() + timedelta(days=1),
        "status": TreatmentProcedureStatus.COMPLETED.value,
    }

    with pytest.raises(ValidationError, match="End date must be today or in the past."):
        validate_edit_procedure(tp_args, treatment_procedure)


def test_validate_edit_procedure_partially_completed_bad_end_date(treatment_procedure):
    tp_args = {
        "start_date": treatment_procedure.start_date,
        "end_date": date.today() + timedelta(days=1),
        "status": TreatmentProcedureStatus.PARTIALLY_COMPLETED.value,
    }

    with pytest.raises(ValidationError, match="End date must be today or in the past."):
        validate_edit_procedure(tp_args, treatment_procedure)


def test_validate_edit_procedure_end_date_before_start_date(treatment_procedure):
    tp_args = {
        "start_date": date.today(),
        "end_date": date.today() - timedelta(days=1),
        "status": treatment_procedure.status,
    }

    with pytest.raises(
        ValidationError,
        match=f"End date must be on or after start date for procedure with id: {treatment_procedure.id}.",
    ):
        validate_edit_procedure(tp_args, treatment_procedure)


def test_validate_edit_procedure_no_partial_global_procedure(treatment_procedure):
    tp_args = {
        "start_date": treatment_procedure.start_date,
        "end_date": date.today(),
        "status": TreatmentProcedureStatus.PARTIALLY_COMPLETED.value,
    }

    with pytest.raises(
        ValidationError,
        match="Stage of cycle required for partially completed procedures.",
    ):
        validate_edit_procedure(tp_args, treatment_procedure)


def test_validate_edit_procedure_partial_procedure(treatment_procedure):
    tp_args = {
        "start_date": treatment_procedure.start_date,
        "end_date": date.today(),
        "status": TreatmentProcedureStatus.PARTIALLY_COMPLETED.value,
        "partial_global_procedure_id": 1,
    }

    validate_edit_procedure(tp_args, treatment_procedure)


def test_validate_procedure(treatment_procedure):
    wallet = ReimbursementWallet.query.get(treatment_procedure.reimbursement_wallet_id)
    gp_id = "3fa85f64-5717-4562-b3fc-2c963f66afa6"
    tp_args = {
        "member_id": treatment_procedure.member_id,
        "global_procedure_id": gp_id,
        "infertility_diagnosis": PatientInfertilityDiagnosis.MEDICALLY_INFERTILE,
        "start_date": date.today() + timedelta(days=8),
        "end_date": date.today() + timedelta(days=9),
    }
    gp = factories.GlobalProcedureFactory.create(id=gp_id)
    validate_procedure(
        treatment_procedure_args=tp_args,
        wallet=wallet,
        global_procedure=gp,
    )


def test_validate_procedure_excluded_procedures(treatment_procedure):
    wallet = ReimbursementWallet.query.get(treatment_procedure.reimbursement_wallet_id)
    procedure_id = "3fa85f64-5717-4562-b3fc-2c963f66afa6"
    tp_args = {
        "member_id": treatment_procedure.member_id,
        "global_procedure_id": procedure_id,
        "infertility_diagnosis": PatientInfertilityDiagnosis.MEDICALLY_INFERTILE,
        "start_date": date.today() + timedelta(days=3),
        "end_date": date.today() + timedelta(days=7),
    }
    gp = factories.GlobalProcedureFactory.create(id=procedure_id)
    with pytest.raises(
        ValidationError,
        match="Global procedure is excluded by org.",
    ):
        validate_procedure(tp_args, wallet, gp, [procedure_id])


def test_validate_procedure_start_date_exceeds_backdate_limit(treatment_procedure):
    member = User.query.get(treatment_procedure.member_id)
    wallet = ReimbursementWallet.query.get(treatment_procedure.reimbursement_wallet_id)
    categories = wallet.get_or_create_wallet_allowed_categories
    categories[
        0
    ].reimbursement_request_category.reimbursement_plan.start_date = date.today() - timedelta(
        days=365
    )

    ReimbursementWalletUsersFactory.create(
        member=member,
        reimbursement_wallet_id=treatment_procedure.reimbursement_wallet_id,
    )
    gp_id = "3fa85f64-5717-4562-b3fc-2c963f66afa6"
    procedure_start_date = date.today() - timedelta(
        days=PROCEDURE_BACKDATE_LIMIT_DAYS + 1
    )
    procedure_end_date = procedure_start_date + timedelta(days=5)
    tp_args = {
        "member_id": treatment_procedure.member_id,
        "global_procedure_id": gp_id,
        "infertility_diagnosis": PatientInfertilityDiagnosis.MEDICALLY_INFERTILE,
        "start_date": procedure_start_date,
        "end_date": procedure_end_date,
    }
    gp = factories.GlobalProcedureFactory.create(id=gp_id)
    eligibility_date = date.today() - timedelta(days=PROCEDURE_BACKDATE_LIMIT_DAYS + 10)
    e9y_member = eligibility_factories.WalletEnablementFactory.create(
        member_id=treatment_procedure.member_id,
        start_date=eligibility_date,
        eligibility_date=eligibility_date,
    )

    with patch(
        "eligibility.e9y.grpc_service.wallet_enablement_by_user_id_search"
    ) as mock_wallet_enablement:
        mock_wallet_enablement.return_value = e9y_member
        with pytest.raises(
            ValidationError,
            match=f"Start date cannot be earlier than 90 days ago for global procedure with uuid: {gp_id}.",
        ):
            validate_procedure(
                treatment_procedure_args=tp_args,
                wallet=wallet,
                global_procedure=gp,
            )


def test_validate_procedure_start_date_before_member_eligibility_start_date(
    treatment_procedure,
):
    member = User.query.get(treatment_procedure.member_id)
    wallet = ReimbursementWallet.query.get(treatment_procedure.reimbursement_wallet_id)
    ReimbursementWalletUsersFactory.create(
        member=member,
        reimbursement_wallet_id=treatment_procedure.reimbursement_wallet_id,
    )
    gp_id = "3fa85f64-5717-4562-b3fc-2c963f66afa6"
    tp_args = {
        "member_id": treatment_procedure.member_id,
        "global_procedure_id": gp_id,
        "infertility_diagnosis": PatientInfertilityDiagnosis.MEDICALLY_INFERTILE,
        "start_date": date.today() - timedelta(days=10),
    }
    gp = factories.GlobalProcedureFactory.create(id=gp_id)
    e9y_member = eligibility_factories.WalletEnablementFactory.create(
        member_id=treatment_procedure.member_id,
        start_date=date.today() - timedelta(days=1),
        eligibility_date=date.today() - timedelta(days=1),
        eligibility_end_date=date.today() + timedelta(days=100),
    )

    with patch(
        "eligibility.e9y.grpc_service.wallet_enablement_by_user_id_search"
    ) as mock_wallet_enablement:
        mock_wallet_enablement.return_value = e9y_member
        with pytest.raises(
            ValidationError,
            match=f"Start date cannot be earlier than the member's eligibility start date for global procedure with uuid: {gp_id}.",
        ):
            validate_procedure(
                treatment_procedure_args=tp_args,
                wallet=wallet,
                global_procedure=gp,
            )


def test_validate_procedure_start_date_after_member_eligibility_end_date(
    treatment_procedure,
):
    member = User.query.get(treatment_procedure.member_id)
    wallet = ReimbursementWallet.query.get(treatment_procedure.reimbursement_wallet_id)
    categories = wallet.get_or_create_wallet_allowed_categories
    categories[
        0
    ].reimbursement_request_category.reimbursement_plan.start_date = date.today() - timedelta(
        days=365
    )

    ReimbursementWalletUsersFactory.create(
        member=member,
        reimbursement_wallet_id=treatment_procedure.reimbursement_wallet_id,
    )
    gp_id = "3fa85f64-5717-4562-b3fc-2c963f66afa6"
    tp_args = {
        "member_id": treatment_procedure.member_id,
        "global_procedure_id": gp_id,
        "infertility_diagnosis": PatientInfertilityDiagnosis.MEDICALLY_INFERTILE,
        "start_date": date.today() - timedelta(days=10),
    }
    gp = factories.GlobalProcedureFactory.create(id=gp_id)
    e9y_member = eligibility_factories.WalletEnablementFactory.create(
        member_id=treatment_procedure.member_id,
        start_date=date.today() - timedelta(days=100),
        eligibility_date=date.today() - timedelta(days=100),
        eligibility_end_date=date.today() - timedelta(days=60),
    )

    with patch(
        "eligibility.e9y.grpc_service.wallet_enablement_by_user_id_search"
    ) as mock_wallet_enablement:
        mock_wallet_enablement.return_value = e9y_member
        with pytest.raises(
            ValidationError,
            match=f"Start date cannot be after the member's eligibility has ended for global procedure with uuid: {gp_id}.",
        ):
            validate_procedure(
                treatment_procedure_args=tp_args,
                wallet=wallet,
                global_procedure=gp,
            )


def test_validate_procedure_end_date_before_start(treatment_procedure):
    wallet = ReimbursementWallet.query.get(treatment_procedure.reimbursement_wallet_id)
    gp_id = "3fa85f64-5717-4562-b3fc-2c963f66afa6"
    tp_args = {
        "member_id": treatment_procedure.member_id,
        "global_procedure_id": gp_id,
        "infertility_diagnosis": PatientInfertilityDiagnosis.MEDICALLY_INFERTILE,
        "start_date": date.today() + timedelta(days=8),
        "end_date": date.today() + timedelta(days=7),
    }
    gp = factories.GlobalProcedureFactory.create(id=gp_id)

    with pytest.raises(
        ValidationError,
        match="End date must be on or after start date for "
        "global procedure with uuid: 3fa85f64-5717-4562-b3fc-2c963f66afa6.",
    ):
        validate_procedure(
            treatment_procedure_args=tp_args,
            wallet=wallet,
            global_procedure=gp,
        )


def test_validate_procedure_not_sure_is_diagnostic(treatment_procedure):
    wallet = ReimbursementWallet.query.get(treatment_procedure.reimbursement_wallet_id)
    gp_id = "3fa85f64-5717-4562-b3fc-2c963f66afa6"
    tp_args = {
        "member_id": treatment_procedure.member_id,
        "global_procedure_id": gp_id,
        "infertility_diagnosis": PatientInfertilityDiagnosis.NOT_SURE,
        "start_date": date.today() + timedelta(days=8),
        "end_date": date.today() + timedelta(days=7),
    }
    gp = factories.GlobalProcedureFactory.create(id=gp_id)

    with pytest.raises(
        ValidationError,
        match="Only Diagnostic procedures can be added.",
    ):
        validate_procedure(
            treatment_procedure_args=tp_args,
            wallet=wallet,
            global_procedure=gp,
        )


def test_validate_procedure_wallet_closed(treatment_procedure):
    wallet = ReimbursementWallet.query.get(treatment_procedure.reimbursement_wallet_id)
    wallet.state = WalletState.EXPIRED
    gp_id = "3fa85f64-5717-4562-b3fc-2c963f66afa6"
    tp_args = {
        "member_id": treatment_procedure.member_id,
        "global_procedure_id": gp_id,
        "infertility_diagnosis": PatientInfertilityDiagnosis.MEDICALLY_INFERTILE,
        "start_date": date.today() + timedelta(days=8),
        "end_date": date.today() + timedelta(days=7),
    }
    gp = factories.GlobalProcedureFactory.create(id=gp_id)

    with pytest.raises(
        ValidationError,
        match=f"User {treatment_procedure.member_id} is ineligible for this procedure: {gp_id}",
    ):
        validate_procedure(
            treatment_procedure_args=tp_args,
            wallet=wallet,
            global_procedure=gp,
        )


# TODO add more edge cases for validate_procedures
def test_validate_new_procedures(treatment_procedure, e9y_member_currency):
    member = User.query.get(treatment_procedure.member_id)
    ReimbursementWalletUsersFactory.create(
        user_id=member.id,
        reimbursement_wallet_id=treatment_procedure.reimbursement_wallet_id,
    )
    first_gp_id = "3fa85f64-5717-4562-b3fc-2c963f66afa6"
    second_gp_id = "4ba85f72-5717-4562-b3fc-fa8564123afa"
    gp_1 = factories.GlobalProcedureFactory.create(id=first_gp_id)
    gp_2 = factories.GlobalProcedureFactory.create(id=second_gp_id)
    fee_schedule = treatment_procedure.fertility_clinic.fee_schedule
    FeeScheduleGlobalProceduresFactory.create(
        global_procedure_id=first_gp_id,
        fee_schedule=fee_schedule,
        cost=12.55,
    )
    FeeScheduleGlobalProceduresFactory.create(
        global_procedure_id=second_gp_id,
        fee_schedule=fee_schedule,
        cost=89.23,
    )
    tp_args = [
        {
            "member_id": member.id,
            "global_procedure_id": first_gp_id,
            "infertility_diagnosis": PatientInfertilityDiagnosis.MEDICALLY_INFERTILE,
            "start_date": date.today() + timedelta(days=8),
            "end_date": date.today() + timedelta(days=9),
            "fertility_clinic_id": treatment_procedure.fertility_clinic_id,
            "fertility_clinic_location_id": treatment_procedure.fertility_clinic_location_id,
        },
        {
            "member_id": member.id,
            "global_procedure_id": second_gp_id,
            "infertility_diagnosis": PatientInfertilityDiagnosis.MEDICALLY_INFERTILE,
            "start_date": date.today() + timedelta(days=8),
            "end_date": date.today() + timedelta(days=9),
            "fertility_clinic_id": treatment_procedure.fertility_clinic_id,
            "fertility_clinic_location_id": treatment_procedure.fertility_clinic_location_id,
        },
    ]

    given_procedures = [gp_1, gp_2]
    with patch(
        "eligibility.e9y.grpc_service.wallet_enablement_by_user_id_search"
    ) as mock_wallet_enablement:
        mock_wallet_enablement.return_value = e9y_member_currency
        with patch.object(
            ProcedureService,
            "get_procedures_by_ids",
            return_value=given_procedures,
        ), patch(
            "direct_payment.treatment_procedure.utils.procedure_helpers.validate_annual_limit_procedure"
        ) as mock_validate_annual_limit:
            validate_procedures(tp_args)
            mock_validate_annual_limit.assert_not_called()


def test_validate_new_procedures_unlimited(
    treatment_procedure, e9y_member_currency, ff_test_data
):
    # Given
    ff_test_data.update(
        ff_test_data.flag(
            ENABLE_UNLIMITED_BENEFITS_FOR_TP_VALIDATION
        ).variation_for_all(True)
    )
    wallet = ReimbursementWallet.query.get(treatment_procedure.reimbursement_wallet_id)
    category_association = (
        wallet.reimbursement_organization_settings.allowed_reimbursement_categories[0]
    )
    category_association.is_unlimited = True
    category_association.reimbursement_request_category_maximum = None

    member = User.query.get(treatment_procedure.member_id)
    ReimbursementWalletUsersFactory.create(
        user_id=member.id,
        reimbursement_wallet_id=treatment_procedure.reimbursement_wallet_id,
    )
    first_gp_id = "3fa85f64-5717-4562-b3fc-2c963f66afa6"
    second_gp_id = "4ba85f72-5717-4562-b3fc-fa8564123afa"
    gp_1 = factories.GlobalProcedureFactory.create(id=first_gp_id)
    gp_2 = factories.GlobalProcedureFactory.create(id=second_gp_id)
    fee_schedule = treatment_procedure.fertility_clinic.fee_schedule

    FeeScheduleGlobalProceduresFactory.create(
        global_procedure_id=first_gp_id,
        fee_schedule=fee_schedule,
        cost=99999999999,
    )
    FeeScheduleGlobalProceduresFactory.create(
        global_procedure_id=second_gp_id,
        fee_schedule=fee_schedule,
        cost=99999999999,
    )
    tp_args = [
        {
            "member_id": member.id,
            "global_procedure_id": first_gp_id,
            "infertility_diagnosis": PatientInfertilityDiagnosis.MEDICALLY_INFERTILE,
            "start_date": date.today() + timedelta(days=8),
            "end_date": date.today() + timedelta(days=9),
            "fertility_clinic_id": treatment_procedure.fertility_clinic_id,
            "fertility_clinic_location_id": treatment_procedure.fertility_clinic_location_id,
        },
        {
            "member_id": member.id,
            "global_procedure_id": second_gp_id,
            "infertility_diagnosis": PatientInfertilityDiagnosis.MEDICALLY_INFERTILE,
            "start_date": date.today() + timedelta(days=8),
            "end_date": date.today() + timedelta(days=9),
            "fertility_clinic_id": treatment_procedure.fertility_clinic_id,
            "fertility_clinic_location_id": treatment_procedure.fertility_clinic_location_id,
        },
    ]

    given_procedures = [gp_1, gp_2]
    with patch(
        "eligibility.e9y.grpc_service.wallet_enablement_by_user_id_search"
    ) as mock_wallet_enablement:
        mock_wallet_enablement.return_value = e9y_member_currency
        with patch.object(
            ProcedureService,
            "get_procedures_by_ids",
            return_value=given_procedures,
        ), patch(
            "direct_payment.treatment_procedure.utils.procedure_helpers.validate_annual_limit_procedure"
        ) as mock_validate_annual_limit:
            validate_procedures(tp_args)
            mock_validate_annual_limit.assert_not_called()


def test_validate_new_procedures_member_with_qualified_and_expired_wallets(
    treatment_procedure, e9y_member_currency
):
    member = User.query.get(treatment_procedure.member_id)

    ReimbursementWalletUsersFactory.create(
        member=member,
        reimbursement_wallet_id=treatment_procedure.reimbursement_wallet_id,
    )
    expired_wallet = ReimbursementWalletFactory.create(
        member=member, state=WalletState.EXPIRED
    )
    ReimbursementWalletUsersFactory.create(
        member=member,
        reimbursement_wallet_id=expired_wallet.id,
    )
    gp_id = "3fa85f64-5717-4562-b3fc-2c963f66afa6"
    global_procedure = factories.GlobalProcedureFactory.create(id=gp_id)
    fee_schedule = treatment_procedure.fertility_clinic.fee_schedule
    FeeScheduleGlobalProceduresFactory.create(
        global_procedure_id=gp_id,
        fee_schedule=fee_schedule,
        cost=12.55,
    )

    tp_args = [
        {
            "member_id": member.id,
            "global_procedure_id": gp_id,
            "infertility_diagnosis": PatientInfertilityDiagnosis.MEDICALLY_INFERTILE,
            "start_date": date.today() + timedelta(days=8),
            "end_date": date.today() + timedelta(days=9),
            "fertility_clinic_id": treatment_procedure.fertility_clinic_id,
            "fertility_clinic_location_id": treatment_procedure.fertility_clinic_location_id,
        },
    ]

    given_procedures = [global_procedure]
    with patch(
        "eligibility.e9y.grpc_service.wallet_enablement_by_user_id_search"
    ) as mock_wallet_enablement:
        mock_wallet_enablement.return_value = e9y_member_currency
        with patch.object(
            ProcedureService,
            "get_procedures_by_ids",
            return_value=given_procedures,
        ):
            validate_procedures(tp_args)


def test_validate_new_procedures__failure_member_with_qualified_and_runout_wallets(
    treatment_procedure,
):
    member = User.query.get(treatment_procedure.member_id)

    ReimbursementWalletUsersFactory.create(
        member=member,
        reimbursement_wallet_id=treatment_procedure.reimbursement_wallet_id,
    )
    runout_wallet = ReimbursementWalletFactory.create(
        member=member, state=WalletState.RUNOUT
    )
    ReimbursementWalletUsersFactory.create(
        member=member,
        reimbursement_wallet_id=runout_wallet.id,
    )
    gp_id = "3fa85f64-5717-4562-b3fc-2c963f66afa6"
    global_procedure = factories.GlobalProcedureFactory.create(id=gp_id)
    fee_schedule = treatment_procedure.fertility_clinic.fee_schedule
    FeeScheduleGlobalProceduresFactory.create(
        global_procedure_id=gp_id,
        fee_schedule=fee_schedule,
        cost=12.55,
    )

    tp_args = [
        {
            "member_id": member.id,
            "global_procedure_id": gp_id,
            "infertility_diagnosis": PatientInfertilityDiagnosis.MEDICALLY_INFERTILE,
            "start_date": date.today() + timedelta(days=8),
            "end_date": date.today() + timedelta(days=9),
            "fertility_clinic_id": treatment_procedure.fertility_clinic_id,
            "fertility_clinic_location_id": treatment_procedure.fertility_clinic_location_id,
        },
    ]

    given_procedures = [global_procedure]
    with patch.object(
        ProcedureService,
        "get_procedures_by_ids",
        return_value=given_procedures,
    ):
        with pytest.raises(
            ValidationError, match=f"Multiple wallets found for member: {member.id}"
        ):
            validate_procedures(tp_args)


def test_validate_new_procedures__failure_wallet_status_not_active(
    treatment_procedure,
):
    member = User.query.get(treatment_procedure.member_id)

    ReimbursementWalletUsersFactory.create(
        member=member,
        reimbursement_wallet_id=treatment_procedure.reimbursement_wallet_id,
        status=WalletUserStatus.DENIED,
    )

    gp_id = "3fa85f64-5717-4562-b3fc-2c963f66afa6"
    global_procedure = factories.GlobalProcedureFactory.create(id=gp_id)
    fee_schedule = treatment_procedure.fertility_clinic.fee_schedule
    FeeScheduleGlobalProceduresFactory.create(
        global_procedure_id=gp_id,
        fee_schedule=fee_schedule,
        cost=12.55,
    )

    tp_args = [
        {
            "member_id": member.id,
            "global_procedure_id": gp_id,
            "infertility_diagnosis": PatientInfertilityDiagnosis.MEDICALLY_INFERTILE,
            "start_date": date.today() + timedelta(days=8),
            "end_date": date.today() + timedelta(days=9),
            "fertility_clinic_id": treatment_procedure.fertility_clinic_id,
            "fertility_clinic_location_id": treatment_procedure.fertility_clinic_location_id,
        },
    ]

    given_procedures = [global_procedure]
    with patch.object(
        ProcedureService,
        "get_procedures_by_ids",
        return_value=given_procedures,
    ):
        with pytest.raises(
            ValidationError, match=f"Wallet not found for member: {member.id}"
        ):
            validate_procedures(tp_args)


@pytest.mark.parametrize(
    argnames="enable_unlimited",
    argvalues=[False, True],
)
def test_validate_new_procedures__failure_over_balance(
    treatment_procedure, e9y_member_currency, enable_unlimited, ff_test_data
):
    """
    Given two new procedures, second procedure should get rejected since there is negative currency balance left
    after account for existing scheduled TP and first added procedure
    """
    ff_test_data.update(
        ff_test_data.flag(
            ENABLE_UNLIMITED_BENEFITS_FOR_TP_VALIDATION
        ).variation_for_all(enable_unlimited)
    )
    member = User.query.get(treatment_procedure.member_id)
    ReimbursementWalletUsersFactory.create(
        user_id=member.id,
        reimbursement_wallet_id=treatment_procedure.reimbursement_wallet_id,
    )
    first_gp_id = "3fa85f64-5717-4562-b3fc-2c963f66afa6"
    second_gp_id = "4ba85f72-5717-4562-b3fc-fa8564123afa"
    gp_1 = factories.GlobalProcedureFactory.create(id=first_gp_id)
    gp_2 = factories.GlobalProcedureFactory.create(id=second_gp_id)
    fee_schedule = treatment_procedure.fertility_clinic.fee_schedule
    FeeScheduleGlobalProceduresFactory.create(
        global_procedure_id=first_gp_id,
        fee_schedule=fee_schedule,
        cost=8012.55,
    )
    FeeScheduleGlobalProceduresFactory.create(
        global_procedure_id=second_gp_id,
        fee_schedule=fee_schedule,
        cost=34.23,
    )
    tp_args = [
        {
            "member_id": member.id,
            "global_procedure_id": first_gp_id,
            "infertility_diagnosis": PatientInfertilityDiagnosis.MEDICALLY_INFERTILE,
            "start_date": date.today() + timedelta(days=8),
            "end_date": date.today() + timedelta(days=9),
            "fertility_clinic_id": treatment_procedure.fertility_clinic_id,
            "fertility_clinic_location_id": treatment_procedure.fertility_clinic_location_id,
        },
        {
            "member_id": member.id,
            "global_procedure_id": second_gp_id,
            "infertility_diagnosis": PatientInfertilityDiagnosis.MEDICALLY_INFERTILE,
            "start_date": date.today() + timedelta(days=8),
            "end_date": date.today() + timedelta(days=9),
            "fertility_clinic_id": treatment_procedure.fertility_clinic_id,
            "fertility_clinic_location_id": treatment_procedure.fertility_clinic_location_id,
        },
    ]

    given_procedures = [gp_1, gp_2]
    with patch.object(
        ProcedureService,
        "get_procedures_by_ids",
        return_value=given_procedures,
    ):
        with patch(
            "eligibility.e9y.grpc_service.wallet_enablement_by_user_id_search"
        ) as mock_wallet_enablement:
            mock_wallet_enablement.return_value = e9y_member_currency
            with pytest.raises(
                ValidationError,
                match="Procedures must be either fully or partially covered by remaining Maven benefits "
                "in order to be billed through this portal. Please remove one or more of these "
                "procedures and bill the member directly at the Maven discounted rate for self-pay patients.",
            ):
                validate_procedures(tp_args)


@pytest.mark.parametrize(
    argnames="enable_unlimited",
    argvalues=[False, True],
)
def test_validate_new_procedures_credits(
    treatment_procedure, e9y_member_cycle, enable_unlimited, ff_test_data
):
    ff_test_data.update(
        ff_test_data.flag(
            ENABLE_UNLIMITED_BENEFITS_FOR_TP_VALIDATION
        ).variation_for_all(enable_unlimited)
    )
    member = User.query.get(treatment_procedure.member_id)
    wallet = ReimbursementWallet.query.get(treatment_procedure.reimbursement_wallet_id)
    category_association = (
        wallet.reimbursement_organization_settings.allowed_reimbursement_categories[0]
    )
    category_association.benefit_type = BenefitTypes.CYCLE
    category_association.num_cycles = 2
    treatment_procedure.cost_credit = 3

    first_gp_id = "3fa85f64-5717-4562-b3fc-2c963f66afa6"
    second_gp_id = "4ba85f72-5717-4562-b3fc-fa8564123afa"
    gp_1 = factories.GlobalProcedureFactory.create(
        id=first_gp_id, credits=3, is_diagnostic=True
    )
    gp_2 = factories.GlobalProcedureFactory.create(id=second_gp_id, credits=6)
    fee_schedule = treatment_procedure.fertility_clinic.fee_schedule
    FeeScheduleGlobalProceduresFactory.create(
        global_procedure_id=first_gp_id,
        fee_schedule=fee_schedule,
        cost=12.55,
    )
    FeeScheduleGlobalProceduresFactory.create(
        global_procedure_id=second_gp_id,
        fee_schedule=fee_schedule,
        cost=89.23,
    )
    tp_args = [
        {
            "member_id": member.id,
            "global_procedure_id": first_gp_id,
            "infertility_diagnosis": PatientInfertilityDiagnosis.NOT_SURE,
            "start_date": date.today() + timedelta(days=8),
            "end_date": date.today() + timedelta(days=9),
            "fertility_clinic_id": treatment_procedure.fertility_clinic_id,
            "fertility_clinic_location_id": treatment_procedure.fertility_clinic_location_id,
        },
        {
            "member_id": member.id,
            "global_procedure_id": second_gp_id,
            "infertility_diagnosis": PatientInfertilityDiagnosis.MEDICALLY_INFERTILE,
            "start_date": date.today() + timedelta(days=8),
            "end_date": date.today() + timedelta(days=9),
            "fertility_clinic_id": treatment_procedure.fertility_clinic_id,
            "fertility_clinic_location_id": treatment_procedure.fertility_clinic_location_id,
        },
    ]

    given_procedures = [gp_1, gp_2]
    with patch.object(
        ProcedureService,
        "get_procedures_by_ids",
        return_value=given_procedures,
    ):
        with patch(
            "eligibility.e9y.grpc_service.wallet_enablement_by_user_id_search"
        ) as mock_wallet_enablement, patch(
            "direct_payment.treatment_procedure.utils.procedure_helpers.validate_annual_limit_procedure"
        ) as mock_validate_annual_limit:
            mock_wallet_enablement.return_value = e9y_member_cycle
            validate_procedures(tp_args)
            assert 2 == mock_validate_annual_limit.call_count


@pytest.mark.parametrize(
    argnames="enable_unlimited",
    argvalues=[True, False],
)
def test_validate_new_procedures_credits__failure_over_balance(
    treatment_procedure_cycle_based, e9y_member_cycle, enable_unlimited, ff_test_data
):
    """
    Given two new procedures, second procedure should get rejected since there is 0 credits left
    after account for existing scheduled TP and first added procedure
    """
    ff_test_data.update(
        ff_test_data.flag(
            ENABLE_UNLIMITED_BENEFITS_FOR_TP_VALIDATION
        ).variation_for_all(enable_unlimited)
    )
    member = User.query.get(treatment_procedure_cycle_based.member_id)
    wallet = ReimbursementWallet.query.get(
        treatment_procedure_cycle_based.reimbursement_wallet_id
    )
    category_association = (
        wallet.reimbursement_organization_settings.allowed_reimbursement_categories[0]
    )
    category_association.benefit_type = BenefitTypes.CYCLE
    category_association.num_cycles = 1
    wallet.cycle_credits[0].amount = (
        category_association.num_cycles * NUM_CREDITS_PER_CYCLE
    )
    treatment_procedure_cycle_based.cost_credit = 9

    first_gp_id = "3fa85f64-5717-4562-b3fc-2c963f66afa6"
    second_gp_id = "4ba85f72-5717-4562-b3fc-fa8564123afa"
    gp_1 = factories.GlobalProcedureFactory.create(
        id=first_gp_id, credits=3, is_diagnostic=True
    )
    gp_2 = factories.GlobalProcedureFactory.create(id=second_gp_id, credits=6)
    fee_schedule = treatment_procedure_cycle_based.fertility_clinic.fee_schedule
    FeeScheduleGlobalProceduresFactory.create(
        global_procedure_id=first_gp_id,
        fee_schedule=fee_schedule,
        cost=12.55,
    )
    FeeScheduleGlobalProceduresFactory.create(
        global_procedure_id=second_gp_id,
        fee_schedule=fee_schedule,
        cost=89.23,
    )
    cost_breakdown = CostBreakdownFactory.create(
        treatment_procedure_uuid=treatment_procedure_cycle_based.uuid,
        wallet_id=wallet.id,
        total_employer_responsibility=10,
    )
    treatment_procedure_cycle_based.cost_breakdown_id = cost_breakdown.id
    tp_args = [
        {
            "member_id": member.id,
            "global_procedure_id": first_gp_id,
            "infertility_diagnosis": PatientInfertilityDiagnosis.NOT_SURE,
            "start_date": date.today() + timedelta(days=8),
            "end_date": date.today() + timedelta(days=9),
            "fertility_clinic_id": treatment_procedure_cycle_based.fertility_clinic_id,
            "fertility_clinic_location_id": treatment_procedure_cycle_based.fertility_clinic_location_id,
        },
        {
            "member_id": member.id,
            "global_procedure_id": second_gp_id,
            "infertility_diagnosis": PatientInfertilityDiagnosis.MEDICALLY_INFERTILE,
            "start_date": date.today() + timedelta(days=8),
            "end_date": date.today() + timedelta(days=9),
            "fertility_clinic_id": treatment_procedure_cycle_based.fertility_clinic_id,
            "fertility_clinic_location_id": treatment_procedure_cycle_based.fertility_clinic_location_id,
        },
    ]

    given_procedures = [gp_1, gp_2]
    with patch.object(
        ProcedureService,
        "get_procedures_by_ids",
        return_value=given_procedures,
    ):
        with patch(
            "eligibility.e9y.grpc_service.wallet_enablement_by_user_id_search"
        ) as mock_wallet_enablement:
            mock_wallet_enablement.return_value = e9y_member_cycle
            with pytest.raises(
                ValidationError,
                match="Procedures must be either fully or partially covered by remaining Maven benefits "
                "in order to be billed through this portal. Please remove one or more of these "
                "procedures and bill the member directly at the Maven discounted rate for self-pay patients.",
            ):
                validate_procedures(tp_args)


@pytest.mark.parametrize(
    argnames="enable_unlimited",
    argvalues=[False, True],
)
def test_validate_new_procedures_credits__allow_zero_credits_zero_balance(
    treatment_procedure_cycle_based, e9y_member_cycle, enable_unlimited, ff_test_data
):
    """
    Given one new zero-credit procedure, validate even though there is 0 credits left
    after accounting for existing scheduled TP
    """
    ff_test_data.update(
        ff_test_data.flag(
            ENABLE_UNLIMITED_BENEFITS_FOR_TP_VALIDATION
        ).variation_for_all(enable_unlimited)
    )
    member = User.query.get(treatment_procedure_cycle_based.member_id)
    wallet = ReimbursementWallet.query.get(
        treatment_procedure_cycle_based.reimbursement_wallet_id
    )
    category_association = (
        wallet.reimbursement_organization_settings.allowed_reimbursement_categories[0]
    )
    category_association.benefit_type = BenefitTypes.CYCLE
    category_association.num_cycles = 1
    wallet.cycle_credits[0].amount = (
        category_association.num_cycles * NUM_CREDITS_PER_CYCLE
    )

    category_association.num_cycles = 1
    treatment_procedure_cycle_based.cost_credit = 12

    first_gp_id = "3fa85f64-5717-4562-b3fc-2c963f66afa6"
    gp_1 = factories.GlobalProcedureFactory.create(
        id=first_gp_id, credits=0, is_diagnostic=True
    )
    fee_schedule = treatment_procedure_cycle_based.fertility_clinic.fee_schedule
    FeeScheduleGlobalProceduresFactory.create(
        global_procedure_id=first_gp_id,
        fee_schedule=fee_schedule,
        cost=12.55,
    )
    cost_breakdown = CostBreakdownFactory.create(
        treatment_procedure_uuid=treatment_procedure_cycle_based.uuid,
        wallet_id=wallet.id,
        total_employer_responsibility=10,
    )
    treatment_procedure_cycle_based.cost_breakdown_id = cost_breakdown.id
    tp_args = [
        {
            "member_id": member.id,
            "global_procedure_id": first_gp_id,
            "infertility_diagnosis": PatientInfertilityDiagnosis.NOT_SURE,
            "start_date": date.today() + timedelta(days=8),
            "end_date": date.today() + timedelta(days=9),
            "fertility_clinic_id": treatment_procedure_cycle_based.fertility_clinic_id,
            "fertility_clinic_location_id": treatment_procedure_cycle_based.fertility_clinic_location_id,
        },
    ]

    given_procedures = [gp_1]
    with patch.object(
        ProcedureService,
        "get_procedures_by_ids",
        return_value=given_procedures,
    ):
        with patch(
            "eligibility.e9y.grpc_service.wallet_enablement_by_user_id_search"
        ) as mock_wallet_enablement:
            mock_wallet_enablement.return_value = e9y_member_cycle
            validate_procedures(tp_args)


@pytest.mark.parametrize(
    argnames="enable_unlimited",
    argvalues=[False, True],
)
def test_validate_new_procedures_credits__allow_zero_credits_over_balance(
    treatment_procedure_cycle_based, e9y_member_cycle, enable_unlimited, ff_test_data
):
    """
    Given two new procedures, zero-credit second procedure is allowed even though there are 0 credits left
    after accounting for existing scheduled TP and first added procedure.
    """
    ff_test_data.update(
        ff_test_data.flag(
            ENABLE_UNLIMITED_BENEFITS_FOR_TP_VALIDATION
        ).variation_for_all(enable_unlimited)
    )
    member = User.query.get(treatment_procedure_cycle_based.member_id)
    wallet = ReimbursementWallet.query.get(
        treatment_procedure_cycle_based.reimbursement_wallet_id
    )
    category_association = (
        wallet.reimbursement_organization_settings.allowed_reimbursement_categories[0]
    )
    category_association.benefit_type = BenefitTypes.CYCLE
    category_association.num_cycles = 1
    wallet.cycle_credits[0].amount = (
        category_association.num_cycles * NUM_CREDITS_PER_CYCLE
    )

    treatment_procedure_cycle_based.cost_credit = 9

    first_gp_id = "3fa85f64-5717-4562-b3fc-2c963f66afa6"
    second_gp_id = "4ba85f72-5717-4562-b3fc-fa8564123afa"
    gp_1 = factories.GlobalProcedureFactory.create(
        id=first_gp_id, credits=3, is_diagnostic=True
    )
    gp_2 = factories.GlobalProcedureFactory.create(id=second_gp_id, credits=0)
    fee_schedule = treatment_procedure_cycle_based.fertility_clinic.fee_schedule
    FeeScheduleGlobalProceduresFactory.create(
        global_procedure_id=first_gp_id,
        fee_schedule=fee_schedule,
        cost=12.55,
    )
    FeeScheduleGlobalProceduresFactory.create(
        global_procedure_id=second_gp_id,
        fee_schedule=fee_schedule,
        cost=89.23,
    )
    cost_breakdown = CostBreakdownFactory.create(
        treatment_procedure_uuid=treatment_procedure_cycle_based.uuid,
        wallet_id=wallet.id,
        total_employer_responsibility=10,
    )
    treatment_procedure_cycle_based.cost_breakdown_id = cost_breakdown.id
    tp_args = [
        {
            "member_id": member.id,
            "global_procedure_id": first_gp_id,
            "infertility_diagnosis": PatientInfertilityDiagnosis.NOT_SURE,
            "start_date": date.today() + timedelta(days=8),
            "end_date": date.today() + timedelta(days=9),
            "fertility_clinic_id": treatment_procedure_cycle_based.fertility_clinic_id,
            "fertility_clinic_location_id": treatment_procedure_cycle_based.fertility_clinic_location_id,
        },
        {
            "member_id": member.id,
            "global_procedure_id": second_gp_id,
            "infertility_diagnosis": PatientInfertilityDiagnosis.MEDICALLY_INFERTILE,
            "start_date": date.today() + timedelta(days=8),
            "end_date": date.today() + timedelta(days=9),
            "fertility_clinic_id": treatment_procedure_cycle_based.fertility_clinic_id,
            "fertility_clinic_location_id": treatment_procedure_cycle_based.fertility_clinic_location_id,
        },
    ]

    given_procedures = [gp_1, gp_2]
    with patch.object(
        ProcedureService,
        "get_procedures_by_ids",
        return_value=given_procedures,
    ):
        with patch(
            "eligibility.e9y.grpc_service.wallet_enablement_by_user_id_search"
        ) as mock_wallet_enablement:
            mock_wallet_enablement.return_value = e9y_member_cycle
            validate_procedures(tp_args)


def test_calculate_cost_breakdown_currency(
    treatment_procedure, wallet, global_procedure
):
    with patch(
        "cost_breakdown.tasks.calculate_cost_breakdown.calculate_cost_breakdown_async.delay",
        return_value=Mock(),
    ) as mock_get_cost_breakdown, patch(
        "direct_payment.treatment_procedure.utils.procedure_helpers.redis_client"
    ) as mock_redis_cli:
        mock_redis_cli().lrange.return_value = []
        run_cost_breakdown(treatment_procedure)
        mock_get_cost_breakdown.assert_called_once_with(
            wallet_id=wallet.id, treatment_procedure_id=treatment_procedure.id
        )


def test_calculate_cost_breakdown_credit(
    treatment_procedure_cycle_based, wallet_cycle_based
):
    with patch(
        "cost_breakdown.tasks.calculate_cost_breakdown.calculate_cost_breakdown_async.delay",
        return_value=Mock(),
    ) as mock_get_cost_breakdown, patch(
        "direct_payment.treatment_procedure.utils.procedure_helpers.redis_client"
    ) as mock_redis_cli:
        mock_redis_cli().lrange.return_value = []
        run_cost_breakdown(treatment_procedure_cycle_based)
        mock_get_cost_breakdown.assert_called_once_with(
            wallet_id=wallet_cycle_based.id,
            treatment_procedure_id=treatment_procedure_cycle_based.id,
        )


def test_process_partial_procedure(
    treatment_procedure,
    treatment_procedure_repository,
    partial_global_procedure,
    wallet_cycle_based,
):
    with patch(
        "direct_payment.billing.tasks.rq_job_create_bill.create_and_process_member_refund_bills.delay"
    ) as trigger_refund, patch(
        "common.global_procedures.procedure.ProcedureService.get_procedure_by_id",
        return_value=partial_global_procedure,
    ):
        partial_global_procedure["parent_procedure_ids"] = [
            treatment_procedure.global_procedure_id
        ]
        treatment_procedure.reimbursement_wallet_id = wallet_cycle_based.id
        treatment_procedure.reimbursement_request_category_id = (
            wallet_cycle_based.get_direct_payment_category.id
        )

        FeeScheduleGlobalProceduresFactory.create(
            cost=34.55,
            global_procedure_id=partial_global_procedure["id"],
            fee_schedule=treatment_procedure.fee_schedule,
        )
        end_date = date.today()
        tp_args = {
            "partial_global_procedure_id": treatment_procedure.global_procedure_id,
            "end_date": end_date,
        }

        partial_procedure = process_partial_procedure(
            treatment_procedure, tp_args, treatment_procedure_repository
        )
        assert partial_procedure.member_id == treatment_procedure.member_id
        assert (
            partial_procedure.infertility_diagnosis
            == treatment_procedure.infertility_diagnosis
        )
        assert (
            partial_procedure.reimbursement_wallet_id
            == treatment_procedure.reimbursement_wallet_id
        )
        assert (
            partial_procedure.reimbursement_request_category_id
            == treatment_procedure.reimbursement_request_category_id
        )
        assert partial_procedure.fee_schedule_id == treatment_procedure.fee_schedule_id
        assert (
            partial_procedure.fertility_clinic_id
            == treatment_procedure.fertility_clinic_id
        )
        assert (
            partial_procedure.fertility_clinic_location_id
            == treatment_procedure.fertility_clinic_location_id
        )
        assert partial_procedure.start_date == treatment_procedure.start_date
        assert partial_procedure.global_procedure_id == partial_global_procedure["id"]
        assert partial_procedure.procedure_name == partial_global_procedure["name"]
        assert partial_procedure.cost_credit == partial_global_procedure["credits"]
        assert partial_procedure.end_date == end_date
        assert partial_procedure.status == TreatmentProcedureStatus.PARTIALLY_COMPLETED

        assert (
            partial_procedure.global_procedure_id
            != treatment_procedure.global_procedure_id
        )
        assert partial_procedure.procedure_name != treatment_procedure.procedure_name
        assert partial_procedure.cost != treatment_procedure.cost
        assert partial_procedure.status != treatment_procedure.status
    trigger_refund.assert_called_with(treatment_procedure_id=treatment_procedure.id)


def test_process_partial_procedure_global_procedure_not_found(
    treatment_procedure, global_procedure, treatment_procedure_repository
):
    with patch(
        "common.global_procedures.procedure.ProcedureService.get_procedure_by_id",
        return_value=None,
    ):
        with pytest.raises(
            ValidationError,
            match="Could not find reimbursement wallet global procedure",
        ):
            tp_args = {
                "partial_global_procedure_id": treatment_procedure.global_procedure_id,
                "end_date": date.today(),
            }
            process_partial_procedure(
                treatment_procedure, tp_args, treatment_procedure_repository
            )


def test_validate_partial_procedure(treatment_procedure):
    partial_procedure = {
        "parent_procedure_ids": [treatment_procedure.global_procedure_id],
        "is_partial": True,
    }

    validate_partial_global_procedure(treatment_procedure, partial_procedure)


def test_validate_partial_procedure_not_partial(treatment_procedure):
    with pytest.raises(
        ValidationError,
        match="Partial global procedure id is not a partial procedure.",
    ):
        partial_procedure = {
            "is_partial": False,
        }
        validate_partial_global_procedure(treatment_procedure, partial_procedure)


def test_validate_partial_procedure_not_child(treatment_procedure):
    with pytest.raises(
        ValidationError,
        match="Partial global procedure is not a valid child procedure of treatment procedure.",
    ):
        partial_procedure = {
            "parent_procedure_ids": [treatment_procedure.id + 1],
            "is_partial": True,
        }
        validate_partial_global_procedure(treatment_procedure, partial_procedure)


def test_trigger_cost_breakdown(treatment_procedure, global_procedure):
    with patch(
        "direct_payment.treatment_procedure.utils.procedure_helpers.run_cost_breakdown"
    ) as mock_run_cost_breakdown:
        treatment_procedure.status = TreatmentProcedureStatus.SCHEDULED
        success = trigger_cost_breakdown(
            treatment_procedure=treatment_procedure, new_procedure=True
        )

        assert success
        mock_run_cost_breakdown.assert_called_once_with(
            treatment_procedure, use_async=True
        )


def test_trigger_cost_breakdown_complete(treatment_procedure, global_procedure):
    with patch(
        "direct_payment.treatment_procedure.utils.procedure_helpers.run_cost_breakdown"
    ) as mock_run_cost_breakdown:
        treatment_procedure.status = TreatmentProcedureStatus.COMPLETED
        success = trigger_cost_breakdown(treatment_procedure=treatment_procedure)

        assert success
        mock_run_cost_breakdown.assert_called_once_with(
            treatment_procedure, use_async=True
        )


def test_trigger_cost_breakdown_cancelled(treatment_procedure, global_procedure):
    with patch(
        "direct_payment.treatment_procedure.utils.procedure_helpers.create_and_process_member_refund_bills.delay"
    ) as mock_create_and_process_member_refund_bills:
        treatment_procedure.status = TreatmentProcedureStatus.CANCELLED
        success = trigger_cost_breakdown(treatment_procedure=treatment_procedure)
        assert success
        mock_create_and_process_member_refund_bills.assert_called_once_with(
            treatment_procedure_id=treatment_procedure.id
        )


def test_trigger_cost_breakdown_fail(treatment_procedure, global_procedure):
    with patch(
        "direct_payment.treatment_procedure.utils.procedure_helpers.run_cost_breakdown",
        return_value=False,
    ) as mock_run_cost_breakdown:
        treatment_procedure.status = TreatmentProcedureStatus.COMPLETED
        success = trigger_cost_breakdown(treatment_procedure)

        assert not success
        mock_run_cost_breakdown.assert_called_once_with(
            treatment_procedure, use_async=True
        )


def test_get_wallet_patient_eligibility_state_carve_out_not_sure(
    treatment_procedure, global_procedure
):
    wallet = ReimbursementWallet.query.get(treatment_procedure.reimbursement_wallet_id)
    wallet.reimbursement_organization_settings.fertility_program_type = (
        FertilityProgramTypes.CARVE_OUT
    )

    wallet_state = get_wallet_patient_eligibility_state(
        wallet,
        PatientInfertilityDiagnosis.NOT_SURE,
        global_procedure,
    )
    assert wallet_state == WalletDirectPaymentState.WALLET_OPEN


def test_get_wallet_patient_eligibility_state_carve_out_not_sure_procedure_requires_diagnosis(
    treatment_procedure, global_procedure
):
    wallet = ReimbursementWallet.query.get(treatment_procedure.reimbursement_wallet_id)
    wallet.reimbursement_organization_settings.fertility_program_type = (
        FertilityProgramTypes.CARVE_OUT
    )

    ReimbursementOrgSettingDxRequiredProceduresFactory.create(
        reimbursement_org_settings_id=wallet.reimbursement_organization_settings.id,
        global_procedure_id=global_procedure["id"],
    )

    wallet_state = get_wallet_patient_eligibility_state(
        wallet,
        PatientInfertilityDiagnosis.NOT_SURE,
        global_procedure,
    )
    assert wallet_state == WalletDirectPaymentState.DIAGNOSTIC_ONLY


def test_get_wallet_patient_eligibility_state_carve_out_not_sure_procedure_does_not_require_diagnosis(
    treatment_procedure, global_procedure, diagnostic_global_procedure
):
    wallet = ReimbursementWallet.query.get(treatment_procedure.reimbursement_wallet_id)
    wallet.reimbursement_organization_settings.fertility_program_type = (
        FertilityProgramTypes.CARVE_OUT
    )

    ReimbursementOrgSettingDxRequiredProceduresFactory.create(
        reimbursement_org_settings_id=wallet.reimbursement_organization_settings.id,
        global_procedure_id=diagnostic_global_procedure["id"],
    )

    wallet_state = get_wallet_patient_eligibility_state(
        wallet,
        PatientInfertilityDiagnosis.NOT_SURE,
        global_procedure,
    )
    assert wallet_state == WalletDirectPaymentState.DIAGNOSTIC_ONLY


def test_get_wallet_patient_eligibility_state_carve_out_not_sure_diagnostic(
    treatment_procedure, diagnostic_global_procedure
):
    wallet = ReimbursementWallet.query.get(treatment_procedure.reimbursement_wallet_id)
    wallet.reimbursement_organization_settings.fertility_program_type = (
        FertilityProgramTypes.CARVE_OUT
    )

    wallet_state = get_wallet_patient_eligibility_state(
        wallet,
        PatientInfertilityDiagnosis.NOT_SURE,
        diagnostic_global_procedure,
    )
    assert wallet_state == WalletDirectPaymentState.WALLET_OPEN


def test_get_wallet_patient_eligibility_state_carve_out_not_sure_diagnostic_requires_diagnosis(
    treatment_procedure, global_procedure, diagnostic_global_procedure
):
    wallet = ReimbursementWallet.query.get(treatment_procedure.reimbursement_wallet_id)
    wallet.reimbursement_organization_settings.fertility_program_type = (
        FertilityProgramTypes.CARVE_OUT
    )

    ReimbursementOrgSettingDxRequiredProceduresFactory.create(
        reimbursement_org_settings_id=wallet.reimbursement_organization_settings.id,
        global_procedure_id=global_procedure["id"],
    )

    wallet_state = get_wallet_patient_eligibility_state(
        wallet,
        PatientInfertilityDiagnosis.NOT_SURE,
        diagnostic_global_procedure,
    )
    assert wallet_state == WalletDirectPaymentState.DIAGNOSTIC_ONLY


def test_get_wallet_patient_eligibility_state_carve_out_infertile(
    treatment_procedure, global_procedure
):
    wallet = ReimbursementWallet.query.get(treatment_procedure.reimbursement_wallet_id)
    wallet.reimbursement_organization_settings.fertility_program_type = (
        FertilityProgramTypes.CARVE_OUT
    )

    wallet_state = get_wallet_patient_eligibility_state(
        wallet,
        PatientInfertilityDiagnosis.MEDICALLY_INFERTILE,
        global_procedure,
    )
    assert wallet_state == WalletDirectPaymentState.WALLET_OPEN


def test_get_wallet_patient_eligibility_state_carve_out_infertile_procedure_requires_diagnosis(
    treatment_procedure, global_procedure
):
    wallet = ReimbursementWallet.query.get(treatment_procedure.reimbursement_wallet_id)
    wallet.reimbursement_organization_settings.fertility_program_type = (
        FertilityProgramTypes.CARVE_OUT
    )

    ReimbursementOrgSettingDxRequiredProceduresFactory.create(
        reimbursement_org_settings_id=wallet.reimbursement_organization_settings.id,
        global_procedure_id=global_procedure["id"],
    )

    wallet_state = get_wallet_patient_eligibility_state(
        wallet,
        PatientInfertilityDiagnosis.MEDICALLY_INFERTILE,
        global_procedure,
    )
    assert wallet_state == WalletDirectPaymentState.WALLET_OPEN


def test_get_wallet_patient_eligibility_state_carve_out_infertile_procedure_does_not_require_diagnosis(
    treatment_procedure, global_procedure, diagnostic_global_procedure
):
    wallet = ReimbursementWallet.query.get(treatment_procedure.reimbursement_wallet_id)
    wallet.reimbursement_organization_settings.fertility_program_type = (
        FertilityProgramTypes.CARVE_OUT
    )

    ReimbursementOrgSettingDxRequiredProceduresFactory.create(
        reimbursement_org_settings_id=wallet.reimbursement_organization_settings.id,
        global_procedure_id=diagnostic_global_procedure["id"],
    )

    wallet_state = get_wallet_patient_eligibility_state(
        wallet,
        PatientInfertilityDiagnosis.MEDICALLY_INFERTILE,
        global_procedure,
    )
    assert wallet_state == WalletDirectPaymentState.WALLET_OPEN


def test_get_wallet_patient_eligibility_state_carve_out_infertile_diagnostic(
    treatment_procedure, diagnostic_global_procedure
):
    wallet = ReimbursementWallet.query.get(treatment_procedure.reimbursement_wallet_id)
    wallet.reimbursement_organization_settings.fertility_program_type = (
        FertilityProgramTypes.CARVE_OUT
    )

    wallet_state = get_wallet_patient_eligibility_state(
        wallet,
        PatientInfertilityDiagnosis.MEDICALLY_INFERTILE,
        diagnostic_global_procedure,
    )
    assert wallet_state == WalletDirectPaymentState.WALLET_OPEN


def test_get_wallet_patient_eligibility_state_carve_out_infertile_diagnostic_requires_diagnosis(
    treatment_procedure, global_procedure, diagnostic_global_procedure
):
    wallet = ReimbursementWallet.query.get(treatment_procedure.reimbursement_wallet_id)
    wallet.reimbursement_organization_settings.fertility_program_type = (
        FertilityProgramTypes.CARVE_OUT
    )

    ReimbursementOrgSettingDxRequiredProceduresFactory.create(
        reimbursement_org_settings_id=wallet.reimbursement_organization_settings.id,
        global_procedure_id=global_procedure["id"],
    )

    wallet_state = get_wallet_patient_eligibility_state(
        wallet,
        PatientInfertilityDiagnosis.MEDICALLY_INFERTILE,
        diagnostic_global_procedure,
    )
    assert wallet_state == WalletDirectPaymentState.WALLET_OPEN


def test_get_wallet_patient_eligibility_state_carve_out_fertile(
    treatment_procedure, global_procedure
):
    wallet = ReimbursementWallet.query.get(treatment_procedure.reimbursement_wallet_id)
    wallet.reimbursement_organization_settings.fertility_program_type = (
        FertilityProgramTypes.CARVE_OUT
    )

    wallet_state = get_wallet_patient_eligibility_state(
        wallet,
        PatientInfertilityDiagnosis.MEDICALLY_FERTILE,
        global_procedure,
    )
    assert wallet_state == WalletDirectPaymentState.WALLET_OPEN


def test_get_wallet_patient_eligibility_state_carve_out_fertile_procedure_requires_diagnosis(
    treatment_procedure, global_procedure
):
    wallet = ReimbursementWallet.query.get(treatment_procedure.reimbursement_wallet_id)
    wallet.reimbursement_organization_settings.fertility_program_type = (
        FertilityProgramTypes.CARVE_OUT
    )

    ReimbursementOrgSettingDxRequiredProceduresFactory.create(
        reimbursement_org_settings_id=wallet.reimbursement_organization_settings.id,
        global_procedure_id=global_procedure["id"],
    )

    wallet_state = get_wallet_patient_eligibility_state(
        wallet,
        PatientInfertilityDiagnosis.MEDICALLY_FERTILE,
        global_procedure,
    )
    assert wallet_state == WalletDirectPaymentState.FERTILITY_DX_REQUIRED

    wallet_state = get_wallet_patient_eligibility_state(
        wallet,
        None,
        global_procedure,
    )
    assert wallet_state == WalletDirectPaymentState.FERTILITY_DX_REQUIRED


def test_get_wallet_patient_eligibility_state_carve_out_fertile_procedure_does_not_require_diagnosis(
    treatment_procedure, global_procedure, diagnostic_global_procedure
):
    wallet = ReimbursementWallet.query.get(treatment_procedure.reimbursement_wallet_id)
    wallet.reimbursement_organization_settings.fertility_program_type = (
        FertilityProgramTypes.CARVE_OUT
    )

    ReimbursementOrgSettingDxRequiredProceduresFactory.create(
        reimbursement_org_settings_id=wallet.reimbursement_organization_settings.id,
        global_procedure_id=diagnostic_global_procedure["id"],
    )

    wallet_state = get_wallet_patient_eligibility_state(
        wallet,
        PatientInfertilityDiagnosis.MEDICALLY_FERTILE,
        global_procedure,
    )
    assert wallet_state == WalletDirectPaymentState.WALLET_OPEN

    wallet_state = get_wallet_patient_eligibility_state(
        wallet,
        None,
        global_procedure,
    )
    assert wallet_state == WalletDirectPaymentState.WALLET_OPEN


def test_get_wallet_patient_eligibility_state_carve_out_fertile_diagnostic(
    treatment_procedure, diagnostic_global_procedure
):
    wallet = ReimbursementWallet.query.get(treatment_procedure.reimbursement_wallet_id)
    wallet.reimbursement_organization_settings.fertility_program_type = (
        FertilityProgramTypes.CARVE_OUT
    )

    wallet_state = get_wallet_patient_eligibility_state(
        wallet,
        PatientInfertilityDiagnosis.MEDICALLY_FERTILE,
        diagnostic_global_procedure,
    )
    assert wallet_state == WalletDirectPaymentState.WALLET_OPEN


def test_get_wallet_patient_eligibility_state_carve_out_fertile_diagnostic_requires_diagnosis(
    treatment_procedure, global_procedure, diagnostic_global_procedure
):
    wallet = ReimbursementWallet.query.get(treatment_procedure.reimbursement_wallet_id)
    wallet.reimbursement_organization_settings.fertility_program_type = (
        FertilityProgramTypes.CARVE_OUT
    )

    ReimbursementOrgSettingDxRequiredProceduresFactory.create(
        reimbursement_org_settings_id=wallet.reimbursement_organization_settings.id,
        global_procedure_id=global_procedure["id"],
    )

    wallet_state = get_wallet_patient_eligibility_state(
        wallet,
        PatientInfertilityDiagnosis.MEDICALLY_FERTILE,
        diagnostic_global_procedure,
    )
    assert wallet_state == WalletDirectPaymentState.WALLET_OPEN

    wallet_state = get_wallet_patient_eligibility_state(
        wallet,
        None,
        diagnostic_global_procedure,
    )
    assert wallet_state == WalletDirectPaymentState.WALLET_OPEN


class TestGetGlobalProcedureIds:
    def test_with_objects(self):
        procedure1 = TreatmentProcedureFactory.create(global_procedure_id="1")
        procedure2 = TreatmentProcedureFactory.create(global_procedure_id="2")
        procedures = [procedure1, procedure2]
        result = list(get_global_procedure_ids(procedures))
        assert result == ["1", "2"]

    def test_with_dicts(self):
        procedure1 = {"global_procedure_id": "1"}
        procedure2 = {"global_procedure_id": "2"}
        procedures = [procedure1, procedure2]
        result = list(get_global_procedure_ids(procedures))
        assert result == ["1", "2"]

    def test_mixed_objects_and_dicts(self):
        procedure1 = TreatmentProcedureFactory.create(global_procedure_id="1")
        procedure2 = {"global_procedure_id": "2"}
        procedures = [procedure1, procedure2]
        result = list(get_global_procedure_ids(procedures))
        assert result == ["1", "2"]

    def test_with_partial_procedures(self):
        partial_procedure = TreatmentProcedureFactory.create(global_procedure_id="3")
        procedure1 = TreatmentProcedureFactory.create(
            global_procedure_id="1", partial_procedure=partial_procedure
        )
        procedure2 = {
            "global_procedure_id": "2",
            "partial_procedure": {"global_procedure_id": "4"},
        }
        procedures = [procedure1, procedure2]
        result = list(get_global_procedure_ids(procedures))
        assert result == ["1", "3", "2", "4"]
