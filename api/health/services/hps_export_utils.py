import traceback
from datetime import date, datetime, timedelta
from typing import Any

from dateutil import parser

from authn.models.user import User
from common.health_profile.health_profile_service_client import (
    HealthProfileServiceClient,
)
from common.health_profile.health_profile_service_models import (
    ClinicalStatus,
    GestationalDiabetesStatus,
    MemberCondition,
    MethodOfConception,
    Modifier,
    Outcome,
    ValueWithModifierAndUpdatedAt,
)
from health.constants import (
    BABY_DOB_LABEL,
    CONDITION_TYPE_PREGNANCY,
    DAYS_BEFORE_ESTIMATED_DATE_PRETERM_BIRTH,
    DID_NOT_USE_IUI_IVF,
    DUE_DATE,
    FERTILITY_TREATMENTS,
    FIRST_TIME_MOM_LABEL,
    GLUCOSE_TEST_NOT_TAKEN_EXPORT_VALUE,
    GLUCOSE_TEST_RESULT_NEED_3H_TEST,
    GLUCOSE_TEST_RESULT_NO_GDM,
    GOT_PREGNANT_OUTSIDE_IUI_IVF_CYCLE,
    LOSS_WHEN,
    MEMBER_ROLE,
    PREGNANT_DURING_IUI,
    PREGNANT_DURING_IVF,
)
from utils.log import logger

PREGNANCY_WELCOME_EXPORT_LABEL = "pregnancy_welcome_export"
FERTILITY_TRANSITION_OFFBOARDING_EXPORT_LABEL = (
    "fertility_transition_offboarding_export"
)

ACTIVE_STATE_PREGNANCY_LABELS = {
    FIRST_TIME_MOM_LABEL,
    DUE_DATE,
    DID_NOT_USE_IUI_IVF,
    PREGNANT_DURING_IVF,
    PREGNANT_DURING_IUI,
    GOT_PREGNANT_OUTSIDE_IUI_IVF_CYCLE,
    FERTILITY_TREATMENTS,
    PREGNANCY_WELCOME_EXPORT_LABEL,
    FERTILITY_TRANSITION_OFFBOARDING_EXPORT_LABEL,
}
RESOLVED_STATE_PREGNANCY_LABELS = {BABY_DOB_LABEL, LOSS_WHEN}


log = logger(__name__)


def export_pregnancy_data_to_hps(user: User, label: str, value: Any) -> None:
    try:
        log.info(
            f"export_pregnancy_data_to_hps receiving data label: {label} value: {value}"
        )

        hps_client = HealthProfileServiceClient(user=user)
        pregnancy = get_or_create_pregnancy(hps_client, user)
        log.info(f"export_pregnancy_data_to_hps get pregnancy: {pregnancy}")

        # Set health profile data if available and no existing data for estimated_date
        if not pregnancy.estimated_date and user.health_profile:
            pregnancy.estimated_date = user.health_profile.due_date
            log.info(
                f"export_pregnancy_related_data export_pregnancy_data_to_hps health_profile.due_date: {user.health_profile.due_date}"
            )

        # Handle different types of data based on label
        if label == PREGNANCY_WELCOME_EXPORT_LABEL:
            handle_pregnancy_welcome(pregnancy, user, value)

        elif label == FERTILITY_TRANSITION_OFFBOARDING_EXPORT_LABEL:
            handle_fertility_transition(pregnancy, user, value)

        elif value == PREGNANT_DURING_IUI:
            update_method_of_conception(pregnancy, user, MethodOfConception.IUI.value)

        elif value == PREGNANT_DURING_IVF:
            update_method_of_conception(pregnancy, user, MethodOfConception.IVF.value)

        elif (
            value == DID_NOT_USE_IUI_IVF or value == GOT_PREGNANT_OUTSIDE_IUI_IVF_CYCLE
        ):
            update_method_of_conception(
                pregnancy, user, MethodOfConception.NO_FERTILITY_TREATMENT.value
            )

        elif label == FERTILITY_TREATMENTS:
            update_method_of_conception(
                pregnancy,
                user,
                MethodOfConception.FERTILITY_TREATMENT_NOT_SPECIFIED.value,
            )

        elif label == FIRST_TIME_MOM_LABEL:
            pregnancy.is_first_occurrence = True

        elif label == DUE_DATE:
            pregnancy.estimated_date = parser.parse(value).date()

        elif label == BABY_DOB_LABEL:
            abatement_date = parser.parse(value).date()

            # if CA already updated the pregnancy for the user prior to user submitting assessment, skip update
            should_skip_export_pregnancy_data_to_hps = (
                determine_should_skip_export_pregnancy_data_to_hps(
                    pregnancy, abatement_date, hps_client, user
                )
            )
            if should_skip_export_pregnancy_data_to_hps:
                log.info(
                    f"export_pregnancy_data_to_hps skipping export to HPS for user because data is updated updated {user.id}"
                )
                return

            handle_baby_dob(pregnancy, user, abatement_date)

        elif label == LOSS_WHEN:
            handle_loss(pregnancy, user, value)

        update_pregnancy_status(pregnancy, label)

        # validate data before sending to HPS
        if (
            pregnancy.status == ClinicalStatus.ACTIVE.value
            and pregnancy.estimated_date is None
        ):
            raise ValueError(
                "pregnancy estimated_date can not be null for active pregnancies"
            )

        if (
            pregnancy.status == ClinicalStatus.RESOLVED.value
            and pregnancy.outcome is None
        ):
            raise ValueError(
                "pregnancy outcome can not be null for resolved pregnancies"
            )

        log.info(f"Final pregnancy data {pregnancy}, label: {label}, value: {value}")
        hps_client.put_pregnancy(pregnancy)

    except Exception as e:
        log.error(
            f"Error exporting pregnancy data: {e}, user: {user.id}",
            error=str(e),
            trace=traceback.format_exc(),
        )
        raise


def get_or_create_pregnancy(
    hps_client: HealthProfileServiceClient, user: User
) -> MemberCondition:
    pregnancies = hps_client.get_pregnancy(user.id, ClinicalStatus.ACTIVE.value)
    if pregnancies:
        return pregnancies[0]

    return MemberCondition(
        condition_type=CONDITION_TYPE_PREGNANCY,
        modifier=Modifier(id=user.id, name=user.full_name, role=MEMBER_ROLE),
    )


def handle_pregnancy_welcome(
    pregnancy: MemberCondition, user: User, data: dict
) -> None:
    if not isinstance(data, dict):
        raise ValueError(
            f"Expected dict for pregnancy_welcome_export, got {type(data)}"
        )

    pregnancy.is_first_occurrence = True
    if "Fertility treatments" in data:
        update_method_of_conception(
            pregnancy, user, MethodOfConception.OTHER_FERTILITY_TREATMENT.value
        )


def handle_fertility_transition(
    pregnancy: MemberCondition, user: User, data: dict
) -> None:
    if not isinstance(data, dict):
        raise ValueError(
            f"Expected dict for fertility_transition_offboarding_export, got {type(data)}"
        )

    if DUE_DATE in data:
        pregnancy.estimated_date = parser.parse(data[DUE_DATE]).date()

    for _, value in data.items():
        if value == PREGNANT_DURING_IUI:
            update_method_of_conception(pregnancy, user, MethodOfConception.IUI.value)

        elif value == PREGNANT_DURING_IVF:
            update_method_of_conception(pregnancy, user, MethodOfConception.IVF.value)

        elif (
            value == DID_NOT_USE_IUI_IVF or value == GOT_PREGNANT_OUTSIDE_IUI_IVF_CYCLE
        ):
            update_method_of_conception(
                pregnancy, user, MethodOfConception.NO_FERTILITY_TREATMENT.value
            )


def handle_baby_dob(
    pregnancy: MemberCondition, user: User, abatement_date: date
) -> None:
    pregnancy.abatement_date = abatement_date

    birth_outcome = determine_outcome_for_birth(pregnancy)
    update_outcome(pregnancy, user, birth_outcome)


def handle_loss(pregnancy: MemberCondition, user: User, value: str) -> None:
    outcome = determine_outcome_for_loss(value)
    update_outcome(pregnancy, user, outcome)


def update_pregnancy_status(pregnancy: MemberCondition, label: str) -> None:
    if label in ACTIVE_STATE_PREGNANCY_LABELS:
        pregnancy.status = ClinicalStatus.ACTIVE.value
    elif label in RESOLVED_STATE_PREGNANCY_LABELS:
        pregnancy.status = ClinicalStatus.RESOLVED.value


def determine_outcome_for_loss(value: Any) -> Outcome:
    if value in {"5-8", "9-12", "13-19"}:
        return Outcome.MISCARRIAGE
    elif value in {"20-23", "24-or-more"}:
        return Outcome.STILLBIRTH
    return Outcome.UNKNOWN


def determine_outcome_for_birth(pregnancy: MemberCondition) -> Outcome:
    """
    Determine if a birth was term or preterm based on the baby's date of birth
    relative to the estimated due date.

    Args:
        pregnancy: The pregnancy condition with abatement_date (birth date) and estimated_date

    Returns:
        str: The outcome value (term or preterm birth)
    """
    preterm_threshold = pregnancy.estimated_date - timedelta(
        days=DAYS_BEFORE_ESTIMATED_DATE_PRETERM_BIRTH
    )

    if pregnancy.abatement_date >= preterm_threshold:
        return Outcome.LIVE_BIRTH_TERM
    else:
        return Outcome.LIVE_BIRTH_PRETERM


def update_method_of_conception(
    pregnancy: MemberCondition, user: User, method_of_conception_value: str
) -> None:
    """
    Update the value of method_of_conception in pregnancy object and sets member as the modifier
    """
    pregnancy.method_of_conception = ValueWithModifierAndUpdatedAt(
        value=method_of_conception_value,
        modifier=Modifier(
            id=user.id,
            name=user.full_name,
            role=MEMBER_ROLE,
        ),
        updated_at=datetime.utcnow(),
    )


def update_outcome(pregnancy: MemberCondition, user: User, outcome: Outcome) -> None:
    """
    Update the value of outcome in pregnancy object and sets member as the modifier
    """
    pregnancy.outcome = ValueWithModifierAndUpdatedAt(
        value=outcome.value,
        modifier=Modifier(
            id=user.id,
            name=user.full_name,
            role=MEMBER_ROLE,
        ),
        updated_at=datetime.utcnow(),
    )


def determine_should_skip_export_pregnancy_data_to_hps(
    pregnancy: MemberCondition,
    abatement_date: date,
    hps_client: HealthProfileServiceClient,
    user: User,
) -> bool:
    # if current pregnancy exists in HPS, do not skip
    if pregnancy.id is not None:
        return False

    # if current pregnancy does not exist but past pregnancy exists and there is one pregnancy that matches abatement_date, skip
    resolved_pregnancies = hps_client.get_pregnancy(
        user.id, ClinicalStatus.RESOLVED.value
    )
    if not resolved_pregnancies:
        return False

    for pregnancy in resolved_pregnancies:
        # TODO: remove this log after bug bash
        log.info(
            f"determine_should_skip_export_pregnancy_data_to_hps pregnancy.abatement_date: {pregnancy.abatement_date}, abatement_date: {abatement_date}, {pregnancy.abatement_date == abatement_date}"
        )
        if pregnancy.abatement_date == abatement_date:
            return True

    return False


def handle_glucose_test_result_export(
    user: User, value: Any, release_pregnancy_updates: bool
) -> None:
    gdm_status = None

    if value == GLUCOSE_TEST_NOT_TAKEN_EXPORT_VALUE:
        gdm_status = GestationalDiabetesStatus.NOT_TESTED
    elif value == GLUCOSE_TEST_RESULT_NO_GDM:
        gdm_status = GestationalDiabetesStatus.TESTED_NEGATIVE
    elif value == GLUCOSE_TEST_RESULT_NEED_3H_TEST:
        gdm_status = GestationalDiabetesStatus.TEST_RESULT_PENDING
    else:
        log.error("handle_glucose_test_result_export invalid gdm_status")
        return

    hps_client = HealthProfileServiceClient(
        user=user, release_pregnancy_updates=release_pregnancy_updates
    )

    # TODO: when data is read only from HPS (last stage of the migration), switch the source of due_dategi
    if not user.health_profile or not user.health_profile.due_date:
        log.error(f"no due date for pregnancy user {user.id}")
        return

    hps_client.put_current_pregnancy_and_gdm_status(
        pregnancy_due_date=user.health_profile.due_date,
        gdm_status=gdm_status,
        gdm_onset_date=None,
    )

    log.info(f"handle_glucose_test_result_export user id {user.id} has finished")
