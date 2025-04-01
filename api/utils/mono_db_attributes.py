MONO_DB_FK_CONSTRAINTS_DICT = {
    ###
    # [NOTICE] DO NOT DELETE THIS PART
    # Add bill to dependency map via cost_breakdown_id to cost_breakdown table
    ("bill", "cost_breakdown"): [
        ("cost_breakdown_id", "id"),
    ],
    # Add care_plan_activity_publish to dependency map via message_id to message table
    ("care_plan_activity_publish", "message"): [("message_id", "id")],
    # Add rte_transaction to dependency map via member_health_plan_id to member_health_plan table
    ("rte_transaction", "member_health_plan"): [
        ("member_health_plan_id", "id"),
    ],
    ###
    # Add virtual dependency from treatment_pressure to reimbursement_wallet
    # See https://mavenclinic.atlassian.net/browse/CPCS-1915
    ("treatment_procedure", "reimbursement_wallet"): [
        ("reimbursement_wallet_id", "id")
    ],
    ###
    # [NOTICE] DO NOT DELETE THIS PART
    # Add the production extraneous tables into deletion chain
    # For more details please check https://mavenclinic.atlassian.net/browse/CPCS-1927
    ###
    ("care_coordinator_selection", "practitioner_profile"): [
        ("practitioner_id", "user_id")
    ],
    ("coordinator_allowed_module", "module"): [("module_id", "id")],
    ("coordinator_allowed_module", "practitioner_profile"): [
        ("practitioner_id", "user_id")
    ],
    ("featured_practitioner", "practitioner_profile"): [("practitioner_id", "user_id")],
    ("free_module_transition", "module"): [
        ("from_module_id", "id"),
        ("to_module_id", "id"),
    ],
    ("organization_package", "organization"): [("organization_id", "id")],
    ("organization_allowed_coordinator", "practitioner_profile"): [
        ("practitioner_id", "user_id")
    ],
    ("organization_allowed_coordinator", "organization"): [("organization_id", "id")],
    ("fertility_clinic_user_profile", "user"): [("user_id", "id")],
    ###
    # From here, generated automatically from
    # https://gitlab.mvnapp.net/haiyang.si/hy-playground/-/blob/main/gdpr_constraints/dependency_map_generator.py
    ###
    ("address", "user"): [
        ("user_id", "id"),
    ],
    ("agreement", "language"): [
        ("language_id", "id"),
    ],
    ("agreement_acceptance", "agreement"): [
        ("agreement_id", "id"),
    ],
    ("agreement_acceptance", "user"): [
        ("user_id", "id"),
    ],
    ("answer", "question"): [
        ("question_id", "id"),
    ],
    ("appointment", "product"): [
        ("product_id", "id"),
    ],
    ("appointment", "schedule"): [
        ("member_schedule_id", "id"),
    ],
    ("appointment", "schedule_event"): [
        ("schedule_event_id", "id"),
    ],
    ("appointment", "cancellation_policy"): [
        ("cancellation_policy_id", "id"),
    ],
    ("appointment", "user"): [
        ("cancelled_by_user_id", "id"),
    ],
    ("appointment", "plan_segment"): [
        ("plan_segment_id", "id"),
    ],
    ("appointment_metadata", "appointment"): [
        ("appointment_id", "id"),
    ],
    ("appointment_metadata", "message"): [
        ("message_id", "id"),
    ],
    ("appointmet_fee_creator", "user"): [
        ("user_id", "id"),
    ],
    ("assessment", "assessment_lifecycle"): [
        ("lifecycle_id", "id"),
    ],
    ("assessment", "image"): [
        ("image_id", "id"),
    ],
    ("assessment_lifecycle_tracks", "assessment_lifecycle"): [
        ("assessment_lifecycle_id", "id"),
    ],
    ("assignable_advocate", "practitioner_profile"): [
        ("practitioner_id", "user_id"),
    ],
    ("async_encounter_summary", "user"): [
        ("provider_id", "id"),
        ("user_id", "id"),
    ],
    ("async_encounter_summary", "questionnaire"): [
        ("questionnaire_id", "id"),
    ],
    ("async_encounter_summary_answer", "answer"): [
        ("answer_id", "id"),
    ],
    ("async_encounter_summary_answer", "async_encounter_summary"): [
        ("async_encounter_summary_id", "id"),
    ],
    ("async_encounter_summary_answer", "question"): [
        ("question_id", "id"),
    ],
    ("automatic_code_application", "referral_code"): [
        ("referral_code_id", "id"),
    ],
    ("availability_notification_request", "user"): [
        ("member_id", "id"),
        ("practitioner_id", "id"),
    ],
    ("availability_request_member_times", "availability_notification_request"): [
        ("availability_notification_request_id", "id"),
    ],
    ("bill_processing_record", "bill"): [
        ("bill_id", "id"),
    ],
    ("bms_order", "user"): [
        ("user_id", "id"),
    ],
    ("bms_shipment", "bms_order"): [
        ("bms_order_id", "id"),
    ],
    ("bms_shipment", "address"): [
        ("address_id", "id"),
    ],
    ("bms_shipment_products", "bms_shipment"): [
        ("bms_shipment_id", "id"),
    ],
    ("bms_shipment_products", "bms_product"): [
        ("bms_product_id", "id"),
    ],
    ("ca_member_match_log", "user"): [
        ("user_id", "id"),
        ("care_advocate_id", "id"),
    ],
    ("ca_member_match_log", "organization"): [
        ("organization_id", "id"),
    ],
    ("ca_member_transition_log", "user"): [
        ("user_id", "id"),
    ],
    ("care_program", "user"): [
        ("user_id", "id"),
    ],
    ("care_program", "organization_employee"): [
        ("organization_employee_id", "id"),
    ],
    ("care_program", "enrollment"): [
        ("enrollment_id", "id"),
    ],
    ("care_program", "module"): [
        ("target_module_id", "id"),
    ],
    ("care_program", "organization_module_extension"): [
        ("organization_module_extension_id", "id"),
    ],
    ("care_program_phase", "phase"): [
        ("phase_id", "id"),
    ],
    ("care_program_phase", "care_program"): [
        ("program_id", "id"),
    ],
    ("category_versions", "category_version"): [
        ("category_version_id", "id"),
    ],
    ("category_versions", "category"): [
        ("category_id", "id"),
    ],
    ("channel_users", "channel"): [
        ("channel_id", "id"),
    ],
    ("channel_users", "user"): [
        ("user_id", "id"),
    ],
    ("client_track", "track_extension"): [
        ("extension_id", "id"),
    ],
    ("client_track", "organization"): [
        ("organization_id", "id"),
    ],
    ("cost_breakdown", "rte_transaction"): [
        ("rte_transaction_id", "id"),
    ],
    ("course_member_status", "user"): [
        ("user_id", "id"),
    ],
    ("credit", "user"): [
        ("user_id", "id"),
    ],
    ("credit", "referral_code_use"): [
        ("referral_code_use_id", "id"),
    ],
    ("credit", "message_billing"): [
        ("message_billing_id", "id"),
    ],
    ("credit", "organization_employee"): [
        ("organization_employee_id", "id"),
    ],
    ("device", "user"): [
        ("user_id", "id"),
    ],
    ("direct_payment_invoice", "reimbursement_organization_settings"): [
        ("reimbursement_organization_settings_id", "id"),
    ],
    ("direct_payment_invoice_bill_allocation", "direct_payment_invoice"): [
        ("direct_payment_invoice_id", "id"),
    ],
    ("eligibility_verification_state", "organization_employee"): [
        ("organization_employee_id", "id"),
    ],
    ("eligibility_verification_state", "organization"): [
        ("organization_id", "id"),
    ],
    ("eligibility_verification_state", "user"): [
        ("user_id", "id"),
    ],
    ("eligibility_verification_state", "user_organization_employee"): [
        ("user_organization_employee_id", "id"),
    ],
    ("employer_health_plan", "reimbursement_organization_settings"): [
        ("reimbursement_org_settings_id", "id"),
    ],
    ("employer_health_plan_cost_sharing", "employer_health_plan"): [
        ("employer_health_plan_id", "id"),
    ],
    ("employer_health_plan_coverage", "employer_health_plan"): [
        ("employer_health_plan_id", "id"),
    ],
    ("employer_health_plan_group_id", "employer_health_plan"): [
        ("employer_health_plan_id", "id"),
    ],
    ("enrollment", "organization"): [
        ("organization_id", "id"),
    ],
    ("external_identity", "user"): [
        ("user_id", "id"),
    ],
    ("external_identity", "organization_employee"): [
        ("organization_employee_id", "id"),
    ],
    ("external_identity", "organization"): [
        ("organization_id", "id"),
    ],
    ("feature", "feature_set"): [
        ("feature_set_id", "id"),
    ],
    ("fee_accounting_entry", "invoice"): [
        ("invoice_id", "id"),
    ],
    ("fee_accounting_entry", "message"): [
        ("message_id", "id"),
    ],
    ("fee_accounting_entry", "user"): [
        ("practitioner_id", "id"),
    ],
    ("fee_schedule_global_procedures", "fee_schedule"): [
        ("fee_schedule_id", "id"),
    ],
    ("fertility_clinic_location_contact", "fertility_clinic_location"): [
        ("fertility_clinic_location_id", "id"),
    ],
    (
        "fertility_clinic_location_employer_health_plan_tier",
        "fertility_clinic_location",
    ): [
        ("fertility_clinic_location_id", "id"),
    ],
    ("fertility_clinic_location_employer_health_plan_tier", "employer_health_plan"): [
        ("employer_health_plan_id", "id"),
    ],
    ("fertility_clinic_user_profile_fertility_clinic", "fertility_clinic"): [
        ("fertility_clinic_id", "id"),
    ],
    (
        "fertility_clinic_user_profile_fertility_clinic",
        "fertility_clinic_user_profile",
    ): [
        ("fertility_clinic_user_profile_id", "id"),
    ],
    ("fertility_treatment_status", "user"): [
        ("user_id", "id"),
    ],
    ("health_profile", "user"): [
        ("user_id", "id"),
    ],
    ("identity_provider_field_alias", "identity_provider"): [
        ("identity_provider_id", "id"),
    ],
    ("incentive_fulfillment", "incentive"): [
        ("incentive_id", "id"),
    ],
    ("incentive_organization", "incentive"): [
        ("incentive_id", "id"),
    ],
    ("incentive_organization_country", "incentive_organization"): [
        ("incentive_organization_id", "id"),
    ],
    ("incentive_payment", "referral_code_use"): [
        ("referral_code_use_id", "id"),
    ],
    ("incentive_payment", "referral_code_value"): [
        ("referral_code_value_id", "id"),
    ],
    ("invite", "user"): [
        ("created_by_user_id", "id"),
    ],
    ("matching_rule", "matching_rule_set"): [
        ("matching_rule_set_id", "id"),
    ],
    ("matching_rule_entity", "matching_rule"): [
        ("matching_rule_id", "id"),
    ],
    ("matching_rule_set", "assignable_advocate"): [
        ("assignable_advocate_id", "practitioner_id"),
    ],
    ("member_appointment_ack", "appointment"): [
        ("appointment_id", "id"),
    ],
    ("member_appointment_ack", "user"): [
        ("user_id", "id"),
    ],
    ("member_benefit", "user"): [
        ("user_id", "id"),
    ],
    ("member_care_team", "user"): [
        ("user_id", "id"),
    ],
    ("member_care_team", "practitioner_profile"): [
        ("practitioner_id", "user_id"),
    ],
    ("member_health_plan", "employer_health_plan"): [
        ("employer_health_plan_id", "id"),
    ],
    ("member_health_plan", "reimbursement_wallet"): [
        ("reimbursement_wallet_id", "id"),
    ],
    ("member_preferences", "member_profile"): [
        ("member_id", "user_id"),
    ],
    ("member_preferences", "preference"): [
        ("preference_id", "id"),
    ],
    ("member_profile", "user"): [
        ("user_id", "id"),
    ],
    ("member_profile", "role"): [
        ("role_id", "id"),
    ],
    ("member_profile", "state"): [
        ("state_id", "id"),
    ],
    ("member_profile", "country"): [
        ("country_id", "id"),
    ],
    ("member_resources", "member_profile"): [
        ("member_id", "user_id"),
    ],
    ("member_resources", "resource"): [
        ("resource_id", "id"),
    ],
    ("member_risk_flag", "risk_flag"): [
        ("risk_flag_id", "id"),
    ],
    ("member_risk_flag", "user"): [
        ("user_id", "id"),
    ],
    ("message", "user"): [
        ("user_id", "id"),
    ],
    ("message", "channel"): [
        ("channel_id", "id"),
    ],
    ("message", "availability_notification_request"): [
        ("availability_notification_request_id", "id"),
    ],
    ("message_billing", "user"): [
        ("user_id", "id"),
    ],
    ("message_billing", "message_product"): [
        ("message_product_id", "id"),
    ],
    ("message_credit", "user"): [
        ("user_id", "id"),
    ],
    ("message_credit", "message_billing"): [
        ("message_billing_id", "id"),
    ],
    ("message_credit", "message"): [
        ("message_id", "id"),
        ("response_id", "id"),
    ],
    ("message_credit", "plan_segment"): [
        ("plan_segment_id", "id"),
    ],
    ("message_users", "message"): [
        ("message_id", "id"),
    ],
    ("message_users", "user"): [
        ("user_id", "id"),
    ],
    ("module", "module"): [
        ("partner_module_id", "id"),
    ],
    ("module", "text_copy"): [
        ("intro_message_text_copy_id", "id"),
    ],
    ("module_vertical_groups", "module"): [
        ("module_id", "id"),
    ],
    ("module_vertical_groups", "vertical_group"): [
        ("vertical_group_id", "id"),
    ],
    ("need_appointment", "appointment"): [
        ("appointment_id", "id"),
    ],
    ("need_appointment", "need"): [
        ("need_id", "id"),
    ],
    ("need_category", "need_category"): [
        ("parent_category_id", "id"),
    ],
    ("need_need_category", "need_category"): [
        ("category_id", "id"),
    ],
    ("need_need_category", "need"): [
        ("need_id", "id"),
    ],
    ("need_restricted_vertical", "need_vertical"): [
        ("need_vertical_id", "id"),
    ],
    ("need_restricted_vertical", "specialty"): [
        ("specialty_id", "id"),
    ],
    ("need_specialty", "specialty"): [
        ("specialty_id", "id"),
    ],
    ("need_specialty", "need"): [
        ("need_id", "id"),
    ],
    ("need_specialty_keyword", "specialty_keyword"): [
        ("keyword_id", "id"),
    ],
    ("need_specialty_keyword", "need"): [
        ("need_id", "id"),
    ],
    ("need_vertical", "vertical"): [
        ("vertical_id", "id"),
    ],
    ("need_vertical", "need"): [
        ("need_id", "id"),
    ],
    ("needs_assessment", "appointment"): [
        ("appointment_id", "id"),
    ],
    ("needs_assessment", "user"): [
        ("user_id", "id"),
    ],
    ("needs_assessment", "assessment"): [
        ("assessment_id", "id"),
    ],
    ("org_inbound_phone_number", "organization"): [
        ("org_id", "id"),
    ],
    ("org_inbound_phone_number", "inbound_phone_number"): [
        ("inbound_phone_number_id", "id"),
    ],
    ("organization_agreements", "organization"): [
        ("organization_id", "id"),
    ],
    ("organization_agreements", "agreement"): [
        ("agreement_id", "id"),
    ],
    ("organization_approved_modules", "organization"): [
        ("organization_id", "id"),
    ],
    ("organization_approved_modules", "module"): [
        ("module_id", "id"),
    ],
    ("organization_eligibility_field", "organization"): [
        ("organization_id", "id"),
    ],
    ("organization_email_domain", "organization"): [
        ("organization_id", "id"),
    ],
    ("organization_employee_dependent", "reimbursement_wallet"): [
        ("reimbursement_wallet_id", "id"),
    ],
    ("organization_external_id", "organization"): [
        ("organization_id", "id"),
    ],
    ("organization_invoicing_settings", "organization"): [
        ("organization_id", "id"),
    ],
    ("organization_managers", "user"): [
        ("user_id", "id"),
    ],
    ("organization_managers", "organization"): [
        ("organization_id", "id"),
    ],
    ("organization_module_extension", "organization"): [
        ("organization_id", "id"),
    ],
    ("organization_module_extension", "module"): [
        ("module_id", "id"),
    ],
    ("organization_rewards_export", "organization_external_id"): [
        ("organization_external_id_id", "id"),
    ],
    ("partner_invite", "user"): [
        ("created_by_user_id", "id"),
    ],
    ("pharmacy_prescription", "reimbursement_request"): [
        ("reimbursement_request_id", "id"),
    ],
    ("pharmacy_prescription", "treatment_procedure"): [
        ("treatment_procedure_id", "id"),
    ],
    ("pharmacy_prescription", "user"): [
        ("user_id", "id"),
    ],
    ("phase", "module"): [
        ("module_id", "id"),
        ("auto_transition_module_id", "id"),
    ],
    ("phase", "assessment_lifecycle"): [
        ("onboarding_assessment_lifecycle_id", "id"),
    ],
    ("plan_purchase", "plan"): [
        ("plan_id", "id"),
    ],
    ("plan_purchase", "user"): [
        ("user_id", "id"),
    ],
    ("plan_purchase", "plan_payer"): [
        ("plan_payer_id", "id"),
    ],
    ("plan_segment", "plan_purchase"): [
        ("plan_purchase_id", "id"),
    ],
    ("post", "user"): [
        ("author_id", "id"),
    ],
    ("post", "post"): [
        ("parent_id", "id"),
    ],
    ("post_categories", "category"): [
        ("category_id", "id"),
    ],
    ("post_categories", "post"): [
        ("post_id", "id"),
    ],
    ("post_phases", "phase"): [
        ("phase_id", "id"),
    ],
    ("post_phases", "post"): [
        ("post_id", "id"),
    ],
    ("practitioner_appointment_ack", "appointment"): [
        ("appointment_id", "id"),
    ],
    ("practitioner_categories", "practitioner_profile"): [
        ("user_id", "user_id"),
    ],
    ("practitioner_categories", "category"): [
        ("category_id", "id"),
    ],
    ("practitioner_certifications", "practitioner_profile"): [
        ("user_id", "user_id"),
    ],
    ("practitioner_certifications", "certification"): [
        ("certification_id", "id"),
    ],
    ("practitioner_characteristics", "practitioner_profile"): [
        ("practitioner_id", "user_id"),
    ],
    ("practitioner_characteristics", "characteristic"): [
        ("characteristic_id", "id"),
    ],
    ("practitioner_contract", "practitioner_profile"): [
        ("practitioner_id", "user_id"),
    ],
    ("practitioner_credits", "practitioner_profile"): [
        ("user_id", "user_id"),
    ],
    ("practitioner_credits", "credit"): [
        ("credit_id", "id"),
    ],
    ("practitioner_data", "user"): [
        ("user_id", "id"),
    ],
    ("practitioner_invite", "image"): [
        ("image_id", "id"),
    ],
    ("practitioner_languages", "practitioner_profile"): [
        ("user_id", "user_id"),
    ],
    ("practitioner_languages", "language"): [
        ("language_id", "id"),
    ],
    ("practitioner_profile", "user"): [
        ("user_id", "id"),
    ],
    ("practitioner_profile", "role"): [
        ("role_id", "id"),
    ],
    ("practitioner_profile", "cancellation_policy"): [
        ("default_cancellation_policy_id", "id"),
    ],
    ("practitioner_profile", "state"): [
        ("state_id", "id"),
    ],
    ("practitioner_specialties", "practitioner_profile"): [
        ("user_id", "user_id"),
    ],
    ("practitioner_specialties", "specialty"): [
        ("specialty_id", "id"),
    ],
    ("practitioner_states", "practitioner_profile"): [
        ("user_id", "user_id"),
    ],
    ("practitioner_states", "state"): [
        ("state_id", "id"),
    ],
    ("practitioner_subdivisions", "practitioner_profile"): [
        ("practitioner_id", "user_id"),
    ],
    ("practitioner_track_vgc", "practitioner_profile"): [
        ("practitioner_id", "user_id"),
    ],
    ("practitioner_verticals", "practitioner_profile"): [
        ("user_id", "user_id"),
    ],
    ("practitioner_verticals", "vertical"): [
        ("vertical_id", "id"),
    ],
    ("product", "user"): [
        ("user_id", "id"),
    ],
    ("product", "vertical"): [
        ("vertical_id", "id"),
    ],
    ("provider_addendum", "appointment"): [
        ("appointment_id", "id"),
    ],
    ("provider_addendum", "recorded_answer"): [
        ("associated_answer_id", "id"),
    ],
    ("provider_addendum", "questionnaire"): [
        ("questionnaire_id", "id"),
    ],
    ("provider_addendum", "user"): [
        ("user_id", "id"),
    ],
    ("provider_addendum_answer", "provider_addendum"): [
        ("addendum_id", "id"),
    ],
    ("provider_addendum_answer", "answer"): [
        ("answer_id", "id"),
    ],
    ("provider_addendum_answer", "question"): [
        ("question_id", "id"),
    ],
    ("question", "question_set"): [
        ("question_set_id", "id"),
    ],
    ("question_set", "answer"): [
        ("prerequisite_answer_id", "id"),
    ],
    ("question_set", "questionnaire"): [
        ("questionnaire_id", "id"),
    ],
    ("questionnaire_global_procedure", "questionnaire"): [
        ("questionnaire_id", "id"),
    ],
    ("questionnaire_role", "role"): [
        ("role_id", "id"),
    ],
    ("questionnaire_role", "questionnaire"): [
        ("questionnaire_id", "id"),
    ],
    ("questionnaire_trigger_answer", "questionnaire"): [
        ("questionnaire_id", "id"),
    ],
    ("questionnaire_trigger_answer", "answer"): [
        ("answer_id", "id"),
    ],
    ("questionnaire_vertical", "questionnaire"): [
        ("questionnaire_id", "id"),
    ],
    ("questionnaire_vertical", "vertical"): [
        ("vertical_id", "id"),
    ],
    ("recorded_answer", "appointment"): [
        ("appointment_id", "id"),
    ],
    ("recorded_answer", "recorded_answer_set"): [
        ("recorded_answer_set_id", "id"),
    ],
    ("recorded_answer", "question"): [
        ("question_id", "id"),
    ],
    ("recorded_answer", "answer"): [
        ("answer_id", "id"),
    ],
    ("recorded_answer", "user"): [
        ("user_id", "id"),
    ],
    ("recorded_answer_set", "appointment"): [
        ("appointment_id", "id"),
    ],
    ("recorded_answer_set", "questionnaire"): [
        ("questionnaire_id", "id"),
    ],
    ("recorded_answer_set", "user"): [
        ("source_user_id", "id"),
    ],
    ("referral_code", "user"): [
        ("user_id", "id"),
    ],
    ("referral_code", "referral_code_subcategory"): [
        ("category_name", "category_name"),
    ],
    ("referral_code_subcategory", "referral_code_category"): [
        ("category_name", "name"),
    ],
    ("referral_code_use", "user"): [
        ("user_id", "id"),
    ],
    ("referral_code_use", "referral_code"): [
        ("code_id", "id"),
    ],
    ("referral_code_value", "referral_code"): [
        ("code_id", "id"),
    ],
    ("reimbursement_account", "reimbursement_wallet"): [
        ("reimbursement_wallet_id", "id"),
    ],
    ("reimbursement_account", "reimbursement_plan"): [
        ("reimbursement_plan_id", "id"),
    ],
    ("reimbursement_account", "reimbursement_account_type"): [
        ("alegeus_account_type_id", "id"),
    ],
    ("reimbursement_claim", "reimbursement_request"): [
        ("reimbursement_request_id", "id"),
    ],
    ("reimbursement_cycle_credits", "reimbursement_wallet"): [
        ("reimbursement_wallet_id", "id"),
    ],
    (
        "reimbursement_cycle_credits",
        "reimbursement_organization_settings_allowed_category",
    ): [
        ("reimbursement_organization_settings_allowed_category_id", "id"),
    ],
    ("reimbursement_cycle_member_credit_transactions", "reimbursement_cycle_credits"): [
        ("reimbursement_cycle_credits_id", "id"),
    ],
    ("reimbursement_cycle_member_credit_transactions", "reimbursement_request"): [
        ("reimbursement_request_id", "id"),
    ],
    (
        "reimbursement_cycle_member_credit_transactions",
        "reimbursement_wallet_global_procedures",
    ): [
        ("reimbursement_wallet_global_procedures_id", "id"),
    ],
    ("reimbursement_organization_settings", "resource"): [
        ("benefit_overview_resource_id", "id"),
        ("benefit_faq_resource_id", "id"),
    ],
    ("reimbursement_organization_settings", "module"): [
        ("required_module_id", "id"),
    ],
    (
        "reimbursement_organization_settings_allowed_category",
        "reimbursement_organization_settings",
    ): [
        ("reimbursement_organization_settings_id", "id"),
    ],
    (
        "reimbursement_organization_settings_allowed_category",
        "reimbursement_request_category",
    ): [
        ("reimbursement_request_category_id", "id"),
    ],
    (
        "reimbursement_organization_settings_allowed_category_rule",
        "reimbursement_organization_settings_allowed_category",
    ): [
        ("reimbursement_organization_settings_allowed_category_id", "id"),
    ],
    (
        "reimbursement_organization_settings_excluded_procedures",
        "reimbursement_organization_settings",
    ): [
        ("reimbursement_organization_settings_id", "id"),
    ],
    (
        "reimbursement_organization_settings_expense_types",
        "reimbursement_organization_settings",
    ): [
        ("reimbursement_organization_settings_id", "id"),
    ],
    (
        "reimbursement_organization_settings_invoicing",
        "reimbursement_organization_settings",
    ): [
        ("reimbursement_organization_settings_id", "id"),
    ],
    ("reimbursement_plan", "reimbursement_account_type"): [
        ("reimbursement_account_type_id", "id"),
    ],
    ("reimbursement_plan", "reimbursement_plan_coverage_tier"): [
        ("reimbursement_plan_coverage_tier_id", "id"),
    ],
    ("reimbursement_request", "reimbursement_request_category"): [
        ("reimbursement_request_category_id", "id"),
    ],
    ("reimbursement_request", "reimbursement_wallet"): [
        ("reimbursement_wallet_id", "id"),
    ],
    ("reimbursement_request", "reimbursement_request"): [
        ("appeal_of", "id"),
    ],
    ("reimbursement_request", "wallet_expense_subtype"): [
        ("wallet_expense_subtype_id", "id"),
        ("original_wallet_expense_subtype_id", "id"),
    ],
    ("reimbursement_request_category", "reimbursement_plan"): [
        ("reimbursement_plan_id", "id"),
    ],
    (
        "reimbursement_request_category_expense_types",
        "reimbursement_request_category",
    ): [
        ("reimbursement_request_category_id", "id"),
    ],
    ("reimbursement_request_exchange_rates", "organization"): [
        ("organization_id", "id"),
    ],
    ("reimbursement_request_source", "reimbursement_wallet"): [
        ("reimbursement_wallet_id", "id"),
    ],
    ("reimbursement_request_source", "user_asset"): [
        ("user_asset_id", "id"),
    ],
    ("reimbursement_request_source_requests", "reimbursement_request"): [
        ("reimbursement_request_id", "id"),
    ],
    ("reimbursement_request_source_requests", "reimbursement_request_source"): [
        ("reimbursement_request_source_id", "id"),
    ],
    ("reimbursement_request_to_cost_breakdown", "cost_breakdown"): [
        ("cost_breakdown_id", "id"),
    ],
    ("reimbursement_request_to_cost_breakdown", "reimbursement_request"): [
        ("reimbursement_request_id", "id"),
    ],
    ("reimbursement_transaction", "reimbursement_request"): [
        ("reimbursement_request_id", "id"),
    ],
    ("reimbursement_wallet", "user"): [
        ("user_id", "id"),
    ],
    ("reimbursement_wallet", "reimbursement_organization_settings"): [
        ("reimbursement_organization_settings_id", "id"),
    ],
    (
        "reimbursement_wallet_allowed_category_rule_evaluation_failure",
        "reimbursement_wallet_allowed_category_rules_evaluation_result",
    ): [
        ("evaluation_result_id", "id"),
    ],
    (
        "reimbursement_wallet_allowed_category_rules_evaluation_result",
        "reimbursement_organization_settings_allowed_category",
    ): [
        ("reimbursement_organization_settings_allowed_category_id", "id"),
    ],
    (
        "reimbursement_wallet_allowed_category_rules_evaluation_result",
        "reimbursement_wallet",
    ): [
        ("reimbursement_wallet_id", "id"),
    ],
    (
        "reimbursement_wallet_allowed_category_settings",
        "reimbursement_organization_settings_allowed_category",
    ): [
        ("reimbursement_organization_settings_allowed_category_id", "id"),
    ],
    ("reimbursement_wallet_allowed_category_settings", "reimbursement_wallet"): [
        ("reimbursement_wallet_id", "id"),
    ],
    ("reimbursement_wallet_benefit", "reimbursement_wallet"): [
        ("reimbursement_wallet_id", "id"),
    ],
    ("reimbursement_wallet_dashboard_cards", "reimbursement_wallet_dashboard"): [
        ("reimbursement_wallet_dashboard_id", "id"),
    ],
    ("reimbursement_wallet_dashboard_cards", "reimbursement_wallet_dashboard_card"): [
        ("reimbursement_wallet_dashboard_card_id", "id"),
    ],
    ("reimbursement_wallet_debit_card", "reimbursement_wallet"): [
        ("reimbursement_wallet_id", "id"),
    ],
    ("reimbursement_wallet_eligibility_blacklist", "reimbursement_wallet"): [
        ("reimbursement_wallet_id", "id"),
    ],
    ("reimbursement_wallet_eligibility_blacklist", "user"): [
        ("creator_id", "id"),
    ],
    (
        "reimbursement_wallet_eligibility_sync_meta",
        "reimbursement_organization_settings",
    ): [
        ("latest_ros_id", "id"),
        ("previous_ros_id", "id"),
    ],
    ("reimbursement_wallet_eligibility_sync_meta", "user"): [
        ("user_id", "id"),
    ],
    ("reimbursement_wallet_eligibility_sync_meta", "reimbursement_wallet"): [
        ("wallet_id", "id"),
    ],
    ("reimbursement_wallet_plan_hdhp", "reimbursement_plan"): [
        ("reimbursement_plan_id", "id"),
    ],
    ("reimbursement_wallet_plan_hdhp", "reimbursement_wallet"): [
        ("reimbursement_wallet_id", "id"),
    ],
    ("reimbursement_wallet_users", "reimbursement_wallet"): [
        ("reimbursement_wallet_id", "id"),
    ],
    ("reimbursement_wallet_users", "user"): [
        ("user_id", "id"),
    ],
    ("reimbursement_wallet_users", "channel"): [
        ("channel_id", "id"),
    ],
    ("resource", "image"): [
        ("image_id", "id"),
    ],
    ("resource_connected_content", "resource"): [
        ("resource_id", "id"),
    ],
    ("resource_connected_content", "connected_content_field"): [
        ("connected_content_field_id", "id"),
    ],
    ("resource_connected_content_phases", "resource"): [
        ("resource_id", "id"),
    ],
    ("resource_connected_content_phases", "phase"): [
        ("phase_id", "id"),
    ],
    ("resource_connected_content_track_phases", "resource"): [
        ("resource_id", "id"),
    ],
    ("resource_featured_class_track_phase", "resource_on_demand_class"): [
        ("resource_id", "resource_id"),
    ],
    ("resource_interactions", "user"): [
        ("user_id", "id"),
    ],
    ("resource_modules", "resource"): [
        ("resource_id", "id"),
    ],
    ("resource_modules", "module"): [
        ("module_id", "id"),
    ],
    ("resource_on_demand_class", "resource"): [
        ("resource_id", "id"),
    ],
    ("resource_organizations", "resource"): [
        ("resource_id", "id"),
    ],
    ("resource_organizations", "organization"): [
        ("organization_id", "id"),
    ],
    ("resource_phases", "resource"): [
        ("resource_id", "id"),
    ],
    ("resource_phases", "phase"): [
        ("phase_id", "id"),
    ],
    ("resource_track_phases", "resource"): [
        ("resource_id", "id"),
    ],
    ("resource_tracks", "resource"): [
        ("resource_id", "id"),
    ],
    ("revoked_member_tracks", "member_track"): [
        ("member_track_id", "id"),
    ],
    ("role_capability", "role"): [
        ("role_id", "id"),
    ],
    ("role_capability", "capability"): [
        ("capability_id", "id"),
    ],
    ("role_profile", "user"): [
        ("user_id", "id"),
    ],
    ("role_profile", "role"): [
        ("role_id", "id"),
    ],
    ("schedule", "user"): [
        ("user_id", "id"),
    ],
    ("schedule_element", "schedule"): [
        ("schedule_id", "id"),
    ],
    ("schedule_event", "schedule_element"): [
        ("schedule_element_id", "id"),
    ],
    ("schedule_event", "schedule"): [
        ("schedule_id", "id"),
    ],
    ("schedule_event", "schedule_recurring_block"): [
        ("schedule_recurring_block_id", "id"),
    ],
    ("schedule_recurring_block", "schedule"): [
        ("schedule_id", "id"),
    ],
    ("schedule_recurring_block_weekday_index", "schedule_recurring_block"): [
        ("schedule_recurring_block_id", "id"),
    ],
    ("specialty_specialty_keywords", "specialty"): [
        ("specialty_id", "id"),
    ],
    ("specialty_specialty_keywords", "specialty_keyword"): [
        ("specialty_keyword_id", "id"),
    ],
    ("tags_assessments", "tag"): [
        ("tag_id", "id"),
    ],
    ("tags_assessments", "assessment"): [
        ("assessment_id", "id"),
    ],
    ("tags_posts", "tag"): [
        ("tag_id", "id"),
    ],
    ("tags_posts", "post"): [
        ("post_id", "id"),
    ],
    ("tags_resources", "tag"): [
        ("tag_id", "id"),
    ],
    ("tags_resources", "resource"): [
        ("resource_id", "id"),
    ],
    ("tracks_need", "need"): [
        ("need_id", "id"),
    ],
    ("tracks_need_category", "need_category"): [
        ("need_category_id", "id"),
    ],
    ("tracks_vertical_groups", "vertical_group"): [
        ("vertical_group_id", "id"),
    ],
    ("treatment_procedure", "reimbursement_request_category"): [
        ("reimbursement_request_category_id", "id"),
    ],
    ("treatment_procedure", "fee_schedule"): [
        ("fee_schedule_id", "id"),
    ],
    ("treatment_procedure", "reimbursement_wallet_global_procedures"): [
        ("reimbursement_wallet_global_procedures_id", "id"),
    ],
    ("treatment_procedure", "fertility_clinic"): [
        ("fertility_clinic_id", "id"),
    ],
    ("treatment_procedure", "fertility_clinic_location"): [
        ("fertility_clinic_location_id", "id"),
    ],
    ("treatment_procedure", "treatment_procedure"): [
        ("partial_procedure_id", "id"),
    ],
    ("treatment_procedure_recorded_answer_set", "treatment_procedure"): [
        ("treatment_procedure_id", "id"),
    ],
    ("treatment_procedure_recorded_answer_set", "recorded_answer_set"): [
        ("recorded_answer_set_id", "id"),
    ],
    ("treatment_procedure_recorded_answer_set", "questionnaire"): [
        ("questionnaire_id", "id"),
    ],
    ("treatment_procedure_recorded_answer_set", "user"): [
        ("user_id", "id"),
    ],
    ("treatment_procedure_recorded_answer_set", "fertility_clinic"): [
        ("fertility_clinic_id", "id"),
    ],
    ("url_redirect", "organization"): [
        ("organization_id", "id"),
    ],
    ("url_redirect", "url_redirect_path"): [
        ("dest_url_path_id", "id"),
    ],
    ("user", "country"): [
        ("country_id", "id"),
    ],
    ("user", "image"): [
        ("image_id", "id"),
    ],
    ("user_activity", "user"): [
        ("user_id", "id"),
    ],
    ("user_asset", "user"): [
        ("user_id", "id"),
    ],
    ("user_asset_appointment", "user_asset"): [
        ("user_asset_id", "id"),
    ],
    ("user_asset_appointment", "appointment"): [
        ("appointment_id", "id"),
    ],
    ("user_asset_message", "user_asset"): [
        ("user_asset_id", "id"),
    ],
    ("user_asset_message", "message"): [
        ("message_id", "id"),
    ],
    ("user_auth", "user"): [
        ("user_id", "id"),
    ],
    ("user_bookmarks", "user"): [
        ("user_id", "id"),
    ],
    ("user_bookmarks", "post"): [
        ("post_id", "id"),
    ],
    ("user_external_identity", "identity_provider"): [
        ("identity_provider_id", "id"),
    ],
    ("user_external_identity", "user"): [
        ("user_id", "id"),
    ],
    ("user_file", "user"): [
        ("user_id", "id"),
    ],
    ("user_file", "appointment"): [
        ("appointment_id", "id"),
    ],
    ("user_install_attribution", "user"): [
        ("user_id", "id"),
    ],
    ("user_locale_preference", "user"): [
        ("user_id", "id"),
    ],
    ("user_onboarding_state", "user"): [
        ("user_id", "id"),
    ],
    ("user_organization_employee", "user"): [
        ("user_id", "id"),
    ],
    ("user_organization_employee", "organization_employee"): [
        ("organization_employee_id", "id"),
    ],
    ("user_practitioner_billing_rules", "user"): [
        ("user_id", "id"),
    ],
    ("user_practitioner_billing_rules", "appointmet_fee_creator"): [
        ("appointmet_fee_creator_id", "id"),
    ],
    ("user_program_history", "user"): [
        ("user_id", "id"),
    ],
    ("user_webinars", "user"): [
        ("user_id", "id"),
    ],
    ("user_webinars", "webinar"): [
        ("webinar_id", "id"),
    ],
    ("vertical_access_by_track", "vertical"): [
        ("vertical_id", "id"),
    ],
    ("vertical_group", "image"): [
        ("hero_image_id", "id"),
    ],
    ("vertical_group_specialties", "vertical_group"): [
        ("vertical_group_id", "id"),
    ],
    ("vertical_group_specialties", "specialty"): [
        ("specialty_id", "id"),
    ],
    ("vertical_grouping_versions", "vertical_group_version"): [
        ("vertical_group_version_id", "id"),
    ],
    ("vertical_grouping_versions", "vertical_group"): [
        ("vertical_group_id", "id"),
    ],
    ("vertical_groupings", "vertical"): [
        ("vertical_id", "id"),
    ],
    ("vertical_groupings", "vertical_group"): [
        ("vertical_group_id", "id"),
    ],
    ("vertical_in_state_match_state", "vertical"): [
        ("vertical_id", "id"),
    ],
    ("vertical_in_state_match_state", "state"): [
        ("state_id", "id"),
    ],
    ("vertical_in_state_matching", "vertical"): [
        ("vertical_id", "id"),
    ],
    ("virtual_event", "virtual_event_category"): [
        ("virtual_event_category_id", "id"),
    ],
    ("virtual_event_category_track", "virtual_event_category"): [
        ("virtual_event_category_id", "id"),
    ],
    ("virtual_event_user_registration", "user"): [
        ("user_id", "id"),
    ],
    ("virtual_event_user_registration", "virtual_event"): [
        ("virtual_event_id", "id"),
    ],
    ("vote", "user"): [
        ("user_id", "id"),
    ],
    ("vote", "post"): [
        ("post_id", "id"),
    ],
    ("wallet_client_report_configuration", "organization"): [
        ("organization_id", "id"),
    ],
    (
        "wallet_client_report_configuration_filter",
        "wallet_client_report_configuration_v2",
    ): [
        ("configuration_id", "id"),
    ],
    (
        "wallet_client_report_configuration_report_columns",
        "wallet_client_report_configuration_report_types",
    ): [
        ("wallet_client_report_configuration_report_type_id", "id"),
    ],
    (
        "wallet_client_report_configuration_report_columns",
        "wallet_client_report_configuration",
    ): [
        ("wallet_client_report_configuration_id", "organization_id"),
    ],
    (
        "wallet_client_report_configuration_report_columns_v2",
        "wallet_client_report_configuration_report_types",
    ): [
        ("wallet_client_report_configuration_report_type_id", "id"),
    ],
    (
        "wallet_client_report_configuration_report_columns_v2",
        "wallet_client_report_configuration_v2",
    ): [
        ("wallet_client_report_configuration_id", "id"),
    ],
    ("wallet_client_report_reimbursements", "reimbursement_request"): [
        ("reimbursement_request_id", "id"),
    ],
    ("wallet_client_report_reimbursements", "wallet_client_reports"): [
        ("wallet_client_report_id", "id"),
    ],
    ("wallet_client_report_snapshots", "reimbursement_wallet"): [
        ("reimbursement_wallet_id", "id"),
    ],
    ("wallet_client_report_snapshots", "wallet_client_reports"): [
        ("wallet_client_report_id", "id"),
    ],
    ("wallet_client_reports", "organization"): [
        ("organization_id", "id"),
    ],
    ("wallet_expense_subtype", "reimbursement_service_category"): [
        ("reimbursement_service_category_id", "id"),
    ],
    ("wallet_user_invite", "user"): [
        ("created_by_user_id", "id"),
    ],
    ("wallet_user_invite", "reimbursement_wallet"): [
        ("reimbursement_wallet_id", "id"),
    ],
}
