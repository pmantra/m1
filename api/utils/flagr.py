from typing import Dict

from maven import feature_flags

from utils.log import logger

log = logger(__name__)


def me_stubs() -> Dict[str, str]:
    return _get_stubs(
        "configure-flagr-stubs-me-endpoint",
        {
            "strategy": "stub",
            "stubs": {
                "mmb_clinic_directory_ios": "on",
                "reschedule_appointment_v2_android": "on",
                "mmb_wallet_ios": "on",
                "mmb_shared_wallet_ios": "on",
                "provider_selection_results_android": "on",
                "my_programs_compose_android": "on",
                "pdf_upload_ios_mpractice": "on",
                "cancellation_survey_android": "on",
                "mmb_upcoming_transactions_ios": "control",
                "expired_track_home_page_android_v2": "on",
                "early_renewal_ios": "on",
                "provider_selection_results_page_layout_v2": "on",
                "mmb_clinic_directory_and": "on",
                "early_renewal_android": "on",
                "mmb_shared_wallet_and": "on",
                "expired_track_home_page_ios": "on",
                "reconnection_ui_ios": "on",
                "mmb_upcoming_transactions_and": "off",
                "content_courses_all": "on",
                "pending_organization_agreement_modal": "on",
                "need_component_update": "on",
                "cancellation_reschedule_ios": "on",
                "mmb_questionnaire_ios": "on",
                "mmb_get_help_ios": "on",
                "data_deletion_account_deactivation_android": "on",
                "reschedule_appointment_ios": "on",
                "opt_out_renewals": "on",
                "reschedule_appointment_android": "on",
                "provider_steerage": "contract_only",
                "marketplace_cta": "on",
                "pdf_upload_ios": "on",
                "early_renewal_pnp_ios": "on",
                "provider_selection": "on",
                "pdf_upload_android": "on",
                "mmb_get_help_and": "on",
                "reschedule_appointment_v2_ios": "on",
                "provider_selection_results_provider_cards": "on",
                "sentry": "on",
            },
        },
    )


def _get_stubs(key: str, default: Dict) -> Dict[str, str]:
    cfg = feature_flags.json_variation(key, default=default)
    strategy = cfg["strategy"]
    if strategy == "stub":
        return cfg["stubs"]
    log.error(
        "The served Flagr stubs strategy is no longer supported. Serving default stubs instead.",
        flag_key=key,
        unsupported_strategy=strategy,
    )
    return default["stubs"]
